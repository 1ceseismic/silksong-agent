# Faithful Sim Rewrite — Design Spec

## Problem

The current sim is hand-written C++ "inspired by" human-readable FSM summaries and guessed constants. This produced 32+ fidelity gaps across three audits. Every fix introduces new assumptions. The root cause: the sim is an interpretation of an interpretation, not a port of the source.

## Solution

Replace all gameplay logic with mechanical translations of the actual game source:
- **Boss FSM:** Data-driven interpreter that executes baked PlayMaker FSM data directly from the extracted JSON
- **Hero physics:** Method-by-method C# → C++ port of HeroController.cs with ability toggles from HeroControllerConfig
- **Combat:** Direct ports of HealthManager.Hit() and HeroController.TakeDamage()/StartRecoil()

Behavior is correct by construction — if the port matches the source, the sim matches the game.

## Architecture

### 1. Boss FSM: Data-Driven Interpreter

#### Data Pipeline

```
Game bundle → Python extract → lace_boss1_control_fsm.json → bake_fsm.py → fsm_lace_boss1.hpp (constexpr)
```

No runtime JSON parsing. The bake script outputs flat C++ arrays compiled into the binary.

#### Baked Data Format

```cpp
struct FsmStateDef {
    uint16_t actionStart;      // index into ACTIONS[]
    uint8_t  actionCount;
    uint8_t  transitionStart;  // index into TRANSITIONS[]
    uint8_t  transitionCount;
};

struct FsmActionDef {
    uint8_t  type;        // ActionType enum
    uint8_t  flags;       // one-shot vs continuous
    uint16_t paramOffset; // index into PARAMS[]
};

struct FsmTransitionDef {
    uint8_t eventId;
    uint8_t targetState;
};
```

Generated header per boss:
```cpp
namespace fsm_lace_boss1 {
    constexpr int NUM_STATES = 80;  // battle-active only
    constexpr FsmStateDef STATES[] = { ... };
    constexpr FsmActionDef ACTIONS[] = { ... };
    constexpr FsmTransitionDef TRANSITIONS[] = { ... };
    constexpr float PARAMS[] = { ... };
    constexpr FsmVarInit FLOAT_VARS[] = { ... };
    constexpr FsmVarInit INT_VARS[] = { ... };
    constexpr FsmVarInit BOOL_VARS[] = { ... };
}
```

#### Runtime State (per-world ECS component)

```cpp
struct FsmRuntime {
    uint8_t  currentState;
    uint8_t  pendingEvent;       // EVENT_NONE if no event
    uint8_t  actionFinished[MAX_ACTIONS_PER_STATE]; // per-action finished flag
    float    floatVars[MAX_FLOAT_VARS];
    int32_t  intVars[MAX_INT_VARS];
    uint8_t  boolVars[MAX_BOOL_VARS];
    float    waitTimer;          // shared timer for Wait actions
    // SendRandomEventV3 tracking
    uint8_t  consecutiveCount;
    uint8_t  lastAttack;
    uint8_t  missedCounts[8];
};
```

#### Execution Model (matching PlayMaker)

1. **On state entry:** Run each action's OnEnter logic. One-shot actions (SetVelocityByScale, FaceObjectV2, SetBoolValue) execute and mark finished. Continuous actions (Wait, DecelerateXY, CheckAlertRange, EaseFloat) initialize.
2. **Each frame:** Run OnUpdate for each unfinished action. Wait decrements timer. DecelerateXY applies decel. CheckAlertRange checks hero distance. EaseFloat ramps value.
3. **Event fired:** Check current state's transitions. If matched, exit current state, enter target state (goto step 1).
4. **Global transitions:** STUN and LAVA DAMAGE checked before per-state processing. These can interrupt any state.

#### Action Types (~40 gameplay-relevant)

Each is a case in a switch statement. Direct translation of what the PlayMaker action does.

**Physics:**
- `SetVelocityByScale` — `velX = speed * facingDir; velY = ySpeed;`
- `SetVelocity2d` — `velX = x; velY = y;`
- `DecelerateXY` — `velX *= decelX; velY *= decelY;` (per frame)
- `SetIsKinematic2d` — toggle gravity
- `SetGravity2dScale` — set gravity multiplier
- `SetPosition2d` / `Translate` — direct position set/offset
- `ClampPosition` — clamp to bounds
- `CheckIsCharacterGrounded` — ground check

**Logic / Flow:**
- `Wait` — timer countdown, fire event on expire
- `WaitRandom` — random duration wait
- `NextFrameEvent` — fire event next frame
- `BoolTest` — if/else branch on bool variable
- `FloatCompare` — compare two floats, fire event
- `FloatTestToBool` — float threshold → bool
- `BoolAllTrue` — AND gate on multiple bools
- `IntCompare` — integer comparison
- `SendRandomEvent` — simple weighted random pick
- `SendRandomEventV3` — weighted random with eventMax/missedMax tracking
- `SendEventByName` — fire named event
- `SendEventByScale` — fire event based on facing direction

**Variables:**
- `SetBoolValue` / `SetFloatValue` / `SetIntValue` / `SetStringValue`
- `FloatAdd` / `FloatMultiply` / `FloatClamp` / `IntAdd`
- `RandomFloat` / `RandomInt`
- `EaseFloat` — ramp value over time (used for Counter Pause)
- `GetDistance` / `GetXDistance` — distance to hero
- `GetSelfPosition` / `GetPosition2d` / `GetScale`
- `FaceObjectV2` / `FaceObjectV4` / `FlipScale` — facing direction

**Combat:**
- `SetDamageHeroAmount` — set hitbox damage
- `SetRecoilSpeed` — set recoil on hit
- `SetRecoilBlocked` — disable recoil
- `SetSpecialDeath` — flag for death handling
- `SetInvincible` — toggle invincibility
- `SubtractHP` — direct HP reduction (lava damage)
- `CompareHP` / `GetHP` — HP checks (rage threshold)
- `FreezeMoment` — global time freeze
- `DamageHeroDirectly` — CrossSlash grab damage
- `CanHeroTakeDamage` — i-frame check before multihit

**World interaction:**
- `CheckAlertRange` — fires event if hero outside range (continuous)
- `CheckHeroPerformanceRegionV2` — hero singing detection
- `RayCast2dV2` — wall detection for downstab/wallcling
- `CheckCollisionSide` / `CheckCollisionSideEnter` — collision events
- `CheckXPosition` / `CheckYPosition` — position bounds check

**Cosmetic (no-op in sim):**
- `Tk2dPlayAnimation` / `AudioPlayerOneShotSingle` / `PlayParticleEmitterInState` / etc. — skipped entirely. The bake script marks these as no-op so the interpreter doesn't even dispatch them.

#### Adding a New Boss

1. Extract FSM JSON from game bundle (existing Python tooling)
2. Run: `python scripts/bake_fsm.py path/to/boss_fsm.json > sim/silksong_sim/src/fsm_newboss.hpp`
3. Register baked data in sim init config
4. If the boss uses a PlayMaker action type not yet implemented, add that one case to the switch (~5-10 lines)
5. No other C++ changes needed

### 2. Hero Physics: Port of HeroController.cs

#### Approach

Method-by-method C# → C++ translation. Same variable names, same control flow, same conditionals. If HeroController.cs says:

```csharp
if (attack_cooldown > 0f) { attack_cooldown -= Time.deltaTime; }
```

We write:

```cpp
if (attack_cooldown > 0.f) { attack_cooldown -= dt; }
```

#### Files

**hero_config.hpp** — port of HeroControllerConfig + HeroControllerConfigWarrior:
```cpp
struct HeroConfig {
    // Ability toggles (from HeroControllerConfig serialized fields)
    bool canDoubleJump;
    bool canBind;
    bool canBrolly;
    bool canHarpoonDash;
    bool canNailCharge;
    bool canPlayNeedolin;
    bool isWarriorRage;  // from HeroControllerConfigWarrior

    // Attack timing (serialized from prefab)
    float attackDuration;
    float attackCooldownTime;
    float quickAttackCooldownTime;
    float attackRecoveryTime;
    float quickAttackSpeedMult;

    // Dash timing
    float dashSpeed;
    float dashTime;        // DASH_TIME
    float airDashTime;     // AIR_DASH_TIME
    float downDashTime;    // DOWN_DASH_TIME
    float dashCooldown;    // DASH_COOLDOWN

    // Movement
    float runSpeed;
    float walkSpeed;
    float jumpSpeed;       // JUMP_SPEED
    float minJumpSpeed;
    int   jumpSteps;
    float maxFallVelocity;
    float wallSlideSpeed;

    // Damage
    float invulTime;       // INVUL_TIME
    float recoilVelocity;  // RECOIL_VELOCITY
    float recoilDuration;  // RECOIL_DURATION
    float recoilHorVelocity;   // RECOIL_HOR_VELOCITY
    int   recoilHorSteps;      // RECOIL_HOR_STEPS
    float damageFreezeDown;
    float damageFreezeWait;
    float damageFreezeUp;
    float damageFreezeSpeed;

    // ... remaining fields from prefab
};
```

Exposed to Python as sim configuration. Training scripts set which abilities are enabled per run.

**hero_states.hpp** — port of HeroControllerStates:
```cpp
struct HeroStates {
    bool attacking;
    bool dashing;
    bool backDashing;
    bool wallSliding;
    bool wallClinging;
    bool onGround;
    bool wasOnGround;
    bool jumping;
    bool doubleJumping;
    bool falling;
    bool recoiling;
    bool recoilFrozen;
    bool invulnerable;
    bool facingRight;
    bool dead;
    bool hazardDeath;
    // ... remaining cState fields
};
```

**hero.hpp** — the physics port. Key methods translated 1:1 from HeroController.cs:

| C# Method | Line | What It Does |
|-----------|------|-------------|
| `Move()` | 1033 | Horizontal movement, run/walk |
| `HeroJump()` | 4793 | Ground jump |
| `DoubleJump()` | 903 | Air jump |
| `WallJump()` | 1005 | Wall kick |
| `Dash()` | 483 | All dash variants |
| `DoAttack()` | 4038 | Attack initiation |
| `Attack()` | 4073 | Attack direction + hitbox activation |
| `DidAttack()` | 4305 | Set attack_cooldown |
| `CanAttack()` | 10901 | Cooldown + state check |
| `TakeDamage()` | 5254 | Damage reception |
| `StartRecoil()` | 9556 | Recoil vector, gravity disable, freeze |
| `LookForInput()` | 8312 | Input → state transitions |
| `WallSlide()` | 4212 | Wall slide mechanics |
| `FixedUpdate tick` | 1365+ | Per-frame integration (gravity, velocity, position) |

**What we skip:** Animation/audio/particle triggers, UI updates, map/menu/save, achievements, dialogue, camera. Anything that doesn't write to physics or combat state.

**What we keep that the current sim skips:**
- `attack_cooldown` as real-time float (not frame counter)
- `attackDuration` and `AttackRecoveryTime` (early cancel window)
- Full `cState` system (proper state flags, not ad-hoc bitfield)
- Gravity disable during recoil (StartRecoil sets `AffectedByGravity(false)`)
- Sprint/shuttlecock exactly as coded
- Wall cling cooldown (`WALLCLING_COOLDOWN = 0.3s`)
- Dash state machine (ground/air/down variants with proper state transitions)

### 3. Combat System

#### Boss Receiving Damage — port of HealthManager.Hit()

```
heroHitsBoss():
  - Apply damage (hitInstance.DamageDealt)
  - Set boss invulnerableTime
  - Apply boss recoil (from FSM's SetRecoilSpeed)
  - Send hit event to boss FSM (BLOCKED HIT during counter, regular otherwise)
  - Stun Control companion update
  - FreezeMoment: only on CriticalHit (not modeled) → NO freeze on normal attacks
  - Hero RECOIL_HOR knockback (3.75 vel, 8 frames, no i-frames, no freeze)
```

#### Hero Receiving Damage — port of HeroController.TakeDamage() + StartRecoil()

```
bossHitsHero():
  - Apply damage
  - StartInvulnerable(INVUL_TIME = 1.0s)
  - FreezeMoment(DOWN=0.0, WAIT=0.1, UP=0.1, SPEED=0.0) → global time stop
  - Recoil vector: (±RECOIL_VELOCITY, RECOIL_VELOCITY * 0.5)
  - AffectedByGravity(false) for RECOIL_DURATION
  - cState.recoilFrozen = true during freeze
  - cState.recoiling = true after freeze ends
```

#### FreezeMoment — port of GameManager.FreezeMoment()

Global time stop. In sim: a world-level `freezeTimer` float. When > 0, hero tick and boss FSM tick both skip. All gameplay timers pause. Decremented by `Time.unscaledDeltaTime` (which in our sim = `deltaT` always, since we don't actually scale time).

#### Stun Control — port of the 17-state companion FSM

Small enough to be a dedicated struct, not a full interpreter instance:

```cpp
struct StunControl {
    float comboCounter;    // hits in current window
    float comboTime;       // 1.0s window
    float hitsTotal;       // absolute counter
    int   stunCombo;       // 8 threshold
    int   stunHitMax;      // 10 threshold
    bool  dazeEffectActive;
};
```

Updated on each hit. When `comboCounter >= stunCombo` or `hitsTotal >= stunHitMax`, sends STUN event to main FSM. `comboCounter` resets when `comboTime` expires (decremented per frame).

### 4. File Structure

#### New Files
| File | Purpose | ~Lines |
|------|---------|--------|
| `fsm_types.hpp` | FsmDef, FsmRuntime, FsmStateDef, FsmActionDef structs | 150 |
| `fsm_actions.hpp` | ~40 action type implementations (switch cases) | 400 |
| `fsm_interpreter.hpp` | fsmTick(), fsmEnterState(), event dispatch | 200 |
| `fsm_lace_boss1.hpp` | Auto-generated constexpr data for Lace Boss1 | 500+ |
| `hero.hpp` | Full hero physics port | 800-1200 |
| `hero_config.hpp` | Config fields + ability toggles | 100 |
| `hero_states.hpp` | cState struct | 50 |
| `scripts/bake_fsm.py` | JSON → constexpr C++ generator | 300 |

#### Modified Files
| File | Changes |
|------|---------|
| `types.hpp` | Replace BossFSM with FsmRuntime, PlayerKinematics with HeroState |
| `combat.hpp` | Rewrite as HealthManager.Hit + TakeDamage ports |
| `sim.cpp` | heroStepSystem calls hero.hpp, bossStepSystem calls fsmTick, add global freeze |
| `level_gen.cpp` | Init for new structs, hero config |
| `consts.hpp` | Hero constants replaced by hero_config.hpp, boss constants eliminated |

#### Deleted
| File | Replaced By |
|------|------------|
| `boss.hpp` | fsm_interpreter.hpp + fsm_lace_boss1.hpp |

#### Unchanged
| File | Reason |
|------|--------|
| `sim.hpp` / `sim.inl` | Madrona boilerplate |
| `mgr.hpp` / `mgr.cpp` | Manager (add hero config to init params) |
| `raycast.hpp` | Sensor system |
| `headless.cpp` / `bindings.cpp` | Entry points |

### 5. Implementation Order

**Phase 1 — Foundation (parallel, no dependencies)**
- FSM data types (fsm_types.hpp)
- FSM interpreter engine (fsm_interpreter.hpp)
- FSM action implementations (fsm_actions.hpp)
- Bake script (scripts/bake_fsm.py)
- Hero config + states (hero_config.hpp, hero_states.hpp)

**Phase 2 — Core logic (parallel, depends on Phase 1)**
- Hero physics port (hero.hpp) — method by method from HeroController.cs
- Boss FSM integration — bake Lace Boss1, wire interpreter into sim

**Phase 3 — Combat + Integration (sequential, depends on Phase 2)**
- Combat system port (combat.hpp)
- Stun Control companion
- sim.cpp wiring — global freeze, updated step systems
- level_gen.cpp — init for new structs

**Phase 4 — Verification**
- Structural diff: automated script comparing baked C++ data against JSON (every param, transition, action)
- Hero method diff: side-by-side C# vs C++ for each ported method
- Behavioral smoke test: random actions, verify state distribution, damage dealing, stun triggers, CrossSlash at rage, lava triggers
- Training sanity check: 100M step run, verify learning signal

### 6. Scope Exclusions

- Additional bosses (architecture supports it, only bake Lace Boss1 now)
- New obs/action tensor layouts (keep current interface)
- Reward function changes (keep current)
- Oracle diff / trace comparison (separate effort requiring game recordings)
- Visualizer rewrite (minor category name update only)
