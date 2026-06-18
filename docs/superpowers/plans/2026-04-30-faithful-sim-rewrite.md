# Faithful Sim Rewrite — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all hand-written gameplay logic with mechanical translations of the actual game source (decompiled C#, extracted FSM JSON), so behavior is correct by construction.

**Architecture:** Boss behavior driven by a data-driven FSM interpreter that executes baked PlayMaker state data. Hero physics is a method-by-method port of HeroController.cs. Combat is a port of HealthManager.Hit() and HeroController.StartRecoil(). All values come from game source, not guesses.

**Tech Stack:** C++ (Madrona ECS GPU sim), Python (FSM bake script), Unity asset extraction (UnityPy)

**Spec:** `docs/superpowers/specs/2026-04-30-faithful-sim-rewrite-design.md`

---

## Parallelization Map

```
Task 1 (FSM types)     ──┐
Task 2 (bake script)   ──┼──> Task 5 (boss integration)  ──┐
Task 3 (FSM actions)   ──┘                                  │
                                                             ├──> Task 7 (combat port)
Task 4 (hero port)     ──────────────────────────────────────┤    Task 8 (sim.cpp wiring)
                                                             │    Task 9 (verification)
Task 6 (hero config    ──────────────────────────────────────┘
        extraction)
```

Tasks 1-4 and 6 are independent. Task 5 depends on 1-3. Tasks 7-9 depend on 4-6.

---

### Task 1: FSM Data Types

**Files:**
- Create: `sim/silksong_sim/src/fsm_types.hpp`

All struct definitions for the FSM interpreter. No logic, just types. Must compile standalone (included by other FSM files).

- [ ] **Step 1: Create fsm_types.hpp**

```cpp
#pragma once
#include <cstdint>

namespace silksong {

// Action type IDs — one per gameplay-relevant PlayMaker action
enum class FsmActionType : uint8_t {
    Noop = 0,
    SetVelocityByScale, SetVelocity2d, DecelerateXY,
    Wait, WaitRandom, NextFrameEvent,
    SetIsKinematic2d, SetGravity2dScale,
    SetPosition2d, Translate, ClampPosition, AnimatePositionTo,
    FaceObjectV2, FaceObjectV4, FlipScale,
    SetBoolValue, SetFloatValue, SetIntValue,
    BoolTest, BoolTestMulti, BoolAllTrue,
    FloatCompare, FloatTestToBool, IntCompare, IntAdd,
    FloatAdd, FloatMultiply, FloatClamp, FloatInRange,
    RandomFloat, RandomInt, MultiplyIntByFloat,
    EaseFloat,
    GetDistance, GetXDistance, GetSelfPosition, GetPosition2d, GetScale,
    SetDamageHeroAmount, SetRecoilSpeed, SetRecoilBlocked,
    SetSpecialDeath, SetInvincible,
    SubtractHP, CompareHP, GetHP,
    CheckAlertRange, CheckAlertRangeByName,
    CheckHeroPerformanceRegionV2,
    SendEvent, SendEventByName, SendEventByNameV2, SendEventByScale,
    SendRandomEvent, SendRandomEventV3,
    FreezeMoment,
    DamageHeroDirectly, CanHeroTakeDamage,
    RayCast2dV2,
    CheckCollisionSide, CheckCollisionSideEnter,
    CheckXPosition, CheckYPosition, CheckYPositionV2,
    CheckIsCharacterGrounded, CheckTargetDirection,
    SetCollider, SetPolygonCollider,
    SetStringValue, GetFsmFloat,
    PreventInvincibleEffect,
    ReceivedDamage,
    SetHitEffectOrigin,
    Count
};

// Event IDs — baked from FSM JSON event list
// Each boss FSM defines its own event enum in its generated header.
// These are indices into the FSM's event table.
constexpr uint8_t FSM_EVENT_NONE = 255;

struct FsmStateDef {
    uint16_t actionStart;      // index into actions array
    uint8_t  actionCount;
    uint8_t  transitionStart;  // index into transitions array
    uint8_t  transitionCount;
    uint8_t  nameIdx;          // debug: index into name table
    uint8_t  _pad[2];
};

struct FsmActionDef {
    FsmActionType type;
    uint8_t  flags;        // bit 0: is continuous (has OnUpdate)
    uint16_t paramOffset;  // index into float params array
};

struct FsmTransitionDef {
    uint8_t eventId;
    uint8_t targetState;
};

// Variable indices — typed slots in the runtime variable table
struct FsmVarSlot {
    uint8_t  type;   // 0=float, 1=int, 2=bool
    uint8_t  index;  // slot index within typed array
};

// Compile-time FSM definition — shared across all worlds, immutable
struct FsmDef {
    const FsmStateDef*      states;
    const FsmActionDef*     actions;
    const FsmTransitionDef* transitions;
    const float*            params;       // flat parameter storage
    int numStates;
    int numActions;
    int numTransitions;
    int numParams;
    int numFloatVars;
    int numIntVars;
    int numBoolVars;
    uint8_t startState;
    // Global transitions (checked every frame before state processing)
    const FsmTransitionDef* globalTransitions;
    int numGlobalTransitions;
};

// Per-world runtime state
constexpr int FSM_MAX_ACTIONS_PER_STATE = 24;
constexpr int FSM_MAX_FLOAT_VARS = 16;
constexpr int FSM_MAX_INT_VARS = 16;
constexpr int FSM_MAX_BOOL_VARS = 24;

struct FsmRuntime {
    uint8_t  currentState;
    uint8_t  pendingEvent;
    uint8_t  actionFinished[FSM_MAX_ACTIONS_PER_STATE];

    float    floatVars[FSM_MAX_FLOAT_VARS];
    int32_t  intVars[FSM_MAX_INT_VARS];
    uint8_t  boolVars[FSM_MAX_BOOL_VARS];

    float    waitTimer;
    float    easeTimer;
    float    easeFrom;
    float    easeTo;
    uint8_t  easeVarIdx;

    // SendRandomEventV3 tracking
    uint8_t  lastAttack;
    uint8_t  consecutiveCount;
    uint8_t  missedCounts[8];

    // CheckAlertRange state
    float    alertRangeTimer;

    // Performance region state
    float    singReactTimer;
};

// Boss kinematics (unchanged from current)
struct BossKinematics {
    float posX, posY;
    float velX, velY;
};

// Stun Control companion (port of the 17-state Stun Control FSM)
struct StunControl {
    float comboCounter;
    float comboTime;       // 1.0s window
    float hitsTotal;
    int   stunCombo;       // 8
    int   stunHitMax;      // 10
    int   recoilSpeed;     // from FSM SetRecoilSpeed
    bool  recoilBlocked;
    bool  isInvincible;
    bool  specialDeath;
    int16_t invincTimer;
    int16_t hitFreezeRem;
    int16_t recoilRem;
    int16_t damageAmount;  // current hitbox damage
};

}
```

- [ ] **Step 2: Verify it compiles**

Run: `cmake --build sim/silksong_sim/build/ -j$(nproc) 2>&1 | grep error`
Expected: May have errors from other files referencing old types — that's fine, this file itself must parse.

---

### Task 2: FSM Bake Script

**Files:**
- Create: `scripts/bake_fsm.py`

Python script that reads `lace_boss1_control_fsm.json` and outputs a C++ constexpr header. The bake script is the single source of truth translator — it must preserve every state, transition, action, and parameter from the JSON.

- [ ] **Step 1: Write the bake script**

The script must:
1. Read the FSM JSON
2. Filter to battle-active states (skip dialogue/dormant/setup — list defined in script)
3. Remap state indices to contiguous 0-based
4. Classify each action as gameplay-relevant or cosmetic (Noop)
5. Extract parameters for each action into a flat float array
6. Extract variable definitions with initial values
7. Output a C++ header with constexpr arrays

Key implementation details:
- The action parameter extraction must handle every action type's param structure from the JSON. Reference: the `params` dict in each action in the JSON.
- Variable references like `"$Distance"` in params must be resolved to variable slot indices.
- Events must be mapped to uint8_t IDs.
- Transitions must reference remapped state indices.

The script reads `scripts/lace_boss1_control_fsm.json` and the `variables` dict from the FSM JSON for variable definitions.

Run: `python scripts/bake_fsm.py scripts/lace_boss1_control_fsm.json > sim/silksong_sim/src/fsm_lace_boss1.hpp`

- [ ] **Step 2: Verify generated header compiles**

Include the generated header in a test and verify it compiles:
```bash
echo '#include "fsm_types.hpp"' > /tmp/test_fsm.cpp
echo '#include "fsm_lace_boss1.hpp"' >> /tmp/test_fsm.cpp
echo 'int main() { return silksong::fsm_lace_boss1::NUM_STATES; }' >> /tmp/test_fsm.cpp
```

- [ ] **Step 3: Write verification script**

`scripts/verify_baked_fsm.py` — reads the JSON and the generated header, verifies:
- Every battle state is present with correct action count and transition count
- Every transition target maps to the correct state name
- Every action's parameters match the JSON values
- Every variable has the correct initial value

---

### Task 3: FSM Action Implementations + Interpreter Engine

**Files:**
- Create: `sim/silksong_sim/src/fsm_actions.hpp`
- Create: `sim/silksong_sim/src/fsm_interpreter.hpp`

- [ ] **Step 1: Create fsm_actions.hpp**

Implement each `FsmActionType` as a pair of functions: `onEnter` and `onUpdate`. Each reads params from the flat param array at the action's `paramOffset`.

The source of truth for what each action does is the decompiled C# PlayMaker actions in `decompiled/HutongGames/PlayMaker/Actions/` (if available) or the observable behavior from the FSM JSON. Key actions:

| Action | OnEnter | OnUpdate |
|--------|---------|----------|
| `SetVelocityByScale` | `velX = params[0] * facing; velY = params[1];` | — |
| `SetVelocity2d` | `velX = params[0]; velY = params[1];` | — |
| `DecelerateXY` | — | `velX *= params[0]; velY *= params[1];` |
| `Wait` | `waitTimer = params[0];` | `waitTimer -= dt; if (<=0) fire(params[1])` |
| `WaitRandom` | `waitTimer = randRange(params[0], params[1]);` | same as Wait |
| `NextFrameEvent` | — | fire event (first frame only) |
| `FaceObjectV2/V4` | set facing toward hero | — |
| `FlipScale` | toggle facing | — |
| `SetBoolValue` | `boolVars[idx] = val;` | — |
| `SetFloatValue` | `floatVars[idx] = val;` | — |
| `BoolTest` | `if (boolVars[idx]) fire(trueEvent); else fire(falseEvent);` | — |
| `FloatCompare` | compare two floats, fire lt/eq/gt event | — |
| `FloatTestToBool` | float threshold → set bool var | — |
| `BoolAllTrue` | AND gate, fire event if all true | — |
| `IntCompare` | compare two ints, fire lt/eq/gt event | — |
| `IntAdd` | `intVars[idx] += val;` | — |
| `FloatAdd/Multiply/Clamp` | arithmetic on float vars | — |
| `EaseFloat` | — | ramp float var over time |
| `GetDistance` | `floatVars[idx] = abs(bossX - heroX);` | — |
| `GetXDistance` | `floatVars[idx] = bossX - heroX;` (signed) | — |
| `GetSelfPosition` | store boss pos in vars | — |
| `GetPosition2d` | store position components | — |
| `GetScale` | store facing scale | — |
| `SetIsKinematic2d` | toggle kinematic flag | — |
| `SetGravity2dScale` | set gravity scale var | — |
| `SetPosition2d` | set boss position from vars | — |
| `Translate` | offset boss position | — |
| `ClampPosition` | clamp boss position | — |
| `SetDamageHeroAmount` | set hitbox damage | — |
| `SetRecoilSpeed` | set stun control recoil speed | — |
| `SetRecoilBlocked` | toggle recoil blocked | — |
| `SetSpecialDeath` | set death flag | — |
| `SetInvincible` | toggle invincibility | — |
| `SubtractHP` | `hp -= amount;` | — |
| `CompareHP` | compare hp to var, fire event | — |
| `GetHP` | store hp in var | — |
| `CheckAlertRange` | — | check distance, fire in/out range events |
| `CheckHeroPerformanceRegionV2` | — | check hero singing, fire event with delay |
| `SendRandomEvent` | weighted random pick, fire event | — |
| `SendRandomEventV3` | weighted random with consecutive/missed tracking | — |
| `SendEvent/ByName/ByScale` | fire event directly | — |
| `FreezeMoment` | set global freeze timer | — |
| `DamageHeroDirectly` | apply damage to hero | — |
| `CanHeroTakeDamage` | check hero i-frames, fire cancel if invuln | — |
| `RayCast2dV2` | simple directional ray for wall detection | — |
| `CheckCollisionSide` | check which side boss hit wall/ground | — |
| `CheckXPosition/YPosition` | compare position to threshold | — |
| `CheckIsCharacterGrounded` | check if boss on ground | — |
| `SetCollider/SetPolygonCollider` | toggle hitbox active | — |
| `RandomFloat/Int` | store random value in var | — |

Every action that isn't gameplay-relevant (animation, audio, particles) maps to `Noop`.

- [ ] **Step 2: Create fsm_interpreter.hpp**

The interpreter engine — `fsmTick()`, `fsmEnterState()`, `fsmFireEvent()`:

```cpp
static inline void fsmEnterState(const FsmDef& def, FsmRuntime& rt,
                                  BossKinematics& bk, StunControl& sc,
                                  float heroX, float heroY,
                                  madrona::RNG& rng, uint8_t stateIdx)
{
    rt.currentState = stateIdx;
    rt.pendingEvent = FSM_EVENT_NONE;
    const FsmStateDef& state = def.states[stateIdx];
    // Clear action finished flags
    for (int i = 0; i < state.actionCount; ++i)
        rt.actionFinished[i] = 0;
    // Run OnEnter for each action
    for (int i = 0; i < state.actionCount; ++i) {
        const FsmActionDef& act = def.actions[state.actionStart + i];
        fsmActionOnEnter(act, def.params + act.paramOffset,
                         rt, bk, sc, heroX, heroY, rng);
        if (rt.pendingEvent != FSM_EVENT_NONE) break;
    }
    // Check if an event was fired during OnEnter
    if (rt.pendingEvent != FSM_EVENT_NONE)
        fsmProcessEvent(def, rt, bk, sc, heroX, heroY, rng);
}

static inline void fsmTick(const FsmDef& def, FsmRuntime& rt,
                            BossKinematics& bk, StunControl& sc,
                            float heroX, float heroY,
                            madrona::RNG& rng, float dt)
{
    // Global transitions first
    for (int i = 0; i < def.numGlobalTransitions; ++i) {
        // Check if event condition is met (STUN, LAVA DAMAGE)
        // These are checked by the stun control / lava detection
    }

    const FsmStateDef& state = def.states[rt.currentState];
    // Run OnUpdate for each unfinished continuous action
    for (int i = 0; i < state.actionCount; ++i) {
        if (rt.actionFinished[i]) continue;
        const FsmActionDef& act = def.actions[state.actionStart + i];
        if (!(act.flags & 1)) continue; // not continuous
        fsmActionOnUpdate(act, def.params + act.paramOffset,
                          rt, bk, sc, heroX, heroY, rng, dt);
        if (rt.pendingEvent != FSM_EVENT_NONE) break;
    }
    // Process pending event
    if (rt.pendingEvent != FSM_EVENT_NONE)
        fsmProcessEvent(def, rt, bk, sc, heroX, heroY, rng);
}

static inline void fsmProcessEvent(const FsmDef& def, FsmRuntime& rt, ...)
{
    const FsmStateDef& state = def.states[rt.currentState];
    for (int i = 0; i < state.transitionCount; ++i) {
        const FsmTransitionDef& tr = def.transitions[state.transitionStart + i];
        if (tr.eventId == rt.pendingEvent) {
            rt.pendingEvent = FSM_EVENT_NONE;
            fsmEnterState(def, rt, ..., tr.targetState);
            return;
        }
    }
    rt.pendingEvent = FSM_EVENT_NONE; // no matching transition
}
```

- [ ] **Step 3: Build and verify**

Run: `cmake --build sim/silksong_sim/build/ -j$(nproc) 2>&1 | grep error`

---

### Task 4: Hero Physics Port

**Files:**
- Create: `sim/silksong_sim/src/hero.hpp`
- Create: `sim/silksong_sim/src/hero_states.hpp`

This is the largest task. Port the following HeroController.cs methods to C++, preserving variable names and control flow:

- [ ] **Step 1: Create hero_states.hpp**

Port `HeroControllerStates` (decompiled/HeroControllerStates.cs, 353 lines). This is the `cState` struct — all the boolean state flags.

Reference: `decompiled/HeroControllerStates.cs`

- [ ] **Step 2: Create hero.hpp — movement core**

Port these methods from `decompiled/HeroController.cs`:

| Method | Lines | What to port |
|--------|-------|-------------|
| `Move()` | 3907-4037 | Horizontal movement with run/walk/sprint |
| `DoMovement()` | (called from FixedUpdate) | Movement dispatch |
| `HeroJump()` | 8691-8777 | Ground jump + sprint check |
| `Jump()` | 853-901 | Jump physics (velocity application) |
| `DoubleJump()` | 903-1004 | Air jump |
| `WallJump()` | 1005-1032 | Wall kick |
| `Dash()` | 4315-4530 | All dash variants |
| `WallSlide()` / `BeginWallSlide()` | 4212-4282 | Wall slide mechanics |

Each C++ function should have a comment `// Port of HeroController.cs:{line_start}-{line_end}` for diffing.

Skip: animation triggers (`animCtrl.Play*`), audio (`PlayAudio*`), particle effects, camera, UI. Keep the comment `// [SKIP: animation/audio]` where cosmetic code is omitted.

- [ ] **Step 3: hero.hpp — attack system**

Port:
| Method | Lines | What to port |
|--------|-------|-------------|
| `DoAttack()` | 4038-4072 | Attack initiation |
| `Attack()` | 4073-4210 | Attack direction, hitbox, slash component |
| `DidAttack()` | 4305-4313 | Set attack_cooldown = Config.AttackCooldownTime |
| `CanAttack()` | 10901-10908 | `attack_cooldown > 0 → false` |
| `ResetAttacks()` | (find it) | Clear attacking state |

Key difference from current sim: `attack_cooldown` is a real-time float (seconds), NOT a frame counter. `attackDuration` is also real-time. `AttackRecoveryTime` defines when the hero can cancel into other actions.

- [ ] **Step 4: hero.hpp — damage and recoil**

Port:
| Method | Lines | What to port |
|--------|-------|-------------|
| `TakeDamage()` | 5254-5630 | Damage reception, invuln check |
| `StartRecoil()` | 9556-9613 | Recoil vector, gravity disable, FreezeMoment |
| `StartInvulnerable()` | 9615-9635 | Invulnerability timer |

- [ ] **Step 5: hero.hpp — FixedUpdate tick**

Port the FixedUpdate dispatcher (lines 2966-3115). This is the per-frame entry point that calls Move, Jump, Dash, etc. based on cState flags.

Key: the game uses Unity's `rb2d.linearVelocity` for physics. In our sim, we apply velocity manually with tile-based collision (sweepAxisX/Y). The velocity writes from HeroController become velocity assignments that our existing sweep integration handles.

- [ ] **Step 6: hero.hpp — LookForInput**

Port `LookForInput()` (lines 8312-8690). This maps input buttons to state transitions. In our sim, the RL agent's action tensor maps to the input buttons. The LookForInput logic determines what happens when attack/jump/dash/heal is pressed based on current state.

- [ ] **Step 7: Build hero.hpp standalone**

Verify it compiles (it won't be wired into sim.cpp yet, but should parse):
```bash
cmake --build sim/silksong_sim/build/ -j$(nproc) 2>&1 | grep error
```

---

### Task 5: Boss FSM Integration

**Files:**
- Create: `sim/silksong_sim/src/fsm_lace_boss1.hpp` (generated by bake script)
- Modify: `sim/silksong_sim/src/sim.cpp` (wire fsmTick into bossStepSystem)

Depends on: Tasks 1, 2, 3

- [ ] **Step 1: Generate the baked header**

```bash
cd /home/seis/code/silksong-agent
python scripts/bake_fsm.py scripts/lace_boss1_control_fsm.json > sim/silksong_sim/src/fsm_lace_boss1.hpp
```

- [ ] **Step 2: Wire into bossStepSystem**

Replace the `#include "boss.hpp"` in sim.cpp with:
```cpp
#include "fsm_types.hpp"
#include "fsm_actions.hpp"
#include "fsm_interpreter.hpp"
#include "fsm_lace_boss1.hpp"
```

Update `bossStepSystem` to call `fsmTick()` instead of `bossTickDispatch()`.

Update `Sim` constructor to initialize the FsmDef singleton from the baked data.

- [ ] **Step 3: Update level_gen.cpp**

Initialize `FsmRuntime` and `StunControl` with values from the baked variable definitions.

- [ ] **Step 4: Build and smoke test**

```bash
cmake --build sim/silksong_sim/build/ -j$(nproc)
./sim/silksong_sim/build/headless CPU 8 5000 --rand-actions
```

- [ ] **Step 5: Verify state distribution**

Run the Python state distribution check — boss should enter all expected categories (Idle, Charge, JSlash, Combo, Counter, Evade, Stun, CrossSlash, Lava, Pose).

---

### Task 6: Hero Config Extraction

**Files:**
- Create: `sim/silksong_sim/src/hero_config.hpp`
- Create: `scripts/extract_hero_config.py`

- [ ] **Step 1: Write extraction script**

`scripts/extract_hero_config.py` reads the Hero_Hornet prefab from the game bundle and dumps all HeroControllerConfig and HeroControllerConfigWarrior serialized fields.

Bundle path: `/home/seis/game/Hollow Knight Silksong/Hollow Knight Silksong_Data/StreamingAssets/aa/StandaloneLinux64/heroloading_assets_all.bundle`

The script must find the MonoBehaviour that has `attackDuration`, `attackCooldownTime`, etc. and output their values. If typetree extraction fails for Config (it's a ScriptableObject reference), extract from the HeroController MonoBehaviour's serialized `config` field reference, then find the referenced object.

Fallback: if programmatic extraction fails, manually inspect the binary for float patterns near known field offsets and cross-reference with the decompiled field order in HeroControllerConfig.cs.

- [ ] **Step 2: Create hero_config.hpp**

Using the extracted values (or best-effort values from code analysis where extraction fails):

```cpp
struct HeroConfig {
    // Ability toggles
    bool canDoubleJump = true;
    bool canBind = false;
    bool canBrolly = false;
    bool canHarpoonDash = false;
    bool canNailCharge = false;
    bool canPlayNeedolin = false;
    bool isWarriorRage = false;

    // Attack timing (from prefab)
    float attackDuration;          // Config.AttackDuration
    float attackCooldownTime;      // Config.AttackCooldownTime
    float quickAttackCooldownTime; // Config.QuickAttackCooldownTime
    float attackRecoveryTime;      // Config.AttackRecoveryTime
    float quickAttackSpeedMult;    // Config.QuickAttackSpeedMult

    // Movement (from HeroController prefab fields)
    float RUN_SPEED = 8.25f;
    float WALK_SPEED = 5.0f;
    // ... all CAPS constants from HeroController
};
```

---

### Task 7: Combat System Port

**Files:**
- Rewrite: `sim/silksong_sim/src/combat.hpp`

Depends on: Tasks 4, 5

- [ ] **Step 1: Port HealthManager.Hit()**

Reference: `decompiled/HealthManager.cs` lines 930-1100.

The function handles: damage application, invulnerability check, recoil, hit event to FSM, stun control update. In our sim this is `bossReceiveHit()`.

Key: NO FreezeMoment on normal hero attacks (only on CriticalHit, which we don't model). Hero gets RECOIL_HOR knockback only.

- [ ] **Step 2: Port HeroController.TakeDamage() + StartRecoil()**

Reference: `decompiled/HeroController.cs` lines 5254-5630 (TakeDamage) and 9556-9613 (StartRecoil).

This is `heroReceiveDamage()`. Applies: FreezeMoment(DAMAGE_FREEZE_*), StartInvulnerable(INVUL_TIME), recoil vector, gravity disable.

- [ ] **Step 3: Stun Control companion**

Port the counter logic from the Stun Control FSM variables:
- `comboCounter` increments on hit, resets when `comboTime` (1.0s) expires
- `hitsTotal` increments on hit, resets on stun
- Stun fires when `comboCounter >= stunCombo (8)` OR `hitsTotal >= stunHitMax (10)`

---

### Task 8: sim.cpp Wiring + level_gen

**Files:**
- Modify: `sim/silksong_sim/src/sim.cpp`
- Modify: `sim/silksong_sim/src/types.hpp`
- Modify: `sim/silksong_sim/src/level_gen.cpp`
- Delete: `sim/silksong_sim/src/boss.hpp`
- Delete: `sim/silksong_sim/src/consts.hpp` (replaced by hero_config.hpp + fsm data)

Depends on: Tasks 5, 7

- [ ] **Step 1: Update types.hpp**

Replace `BossFSM` with `FsmRuntime` + `StunControl`. Replace `PlayerKinematics` with the hero state struct from hero.hpp. Keep `PlayerObs`, `BossObs`, `Arena`, `ActiveProjectiles` unchanged (these are the RL-facing interface).

- [ ] **Step 2: Update sim.cpp heroStepSystem**

Replace the inline hero physics with a call to the hero.hpp port:
```cpp
inline void heroStepSystem(Engine &ctx, const Action &a,
                            HeroState &hero, PlayerObs &obs) {
    // Global freeze check
    if (ctx.singleton<GlobalFreeze>().timer > 0.f) {
        ctx.singleton<GlobalFreeze>().timer -= consts::deltaT;
        return;
    }
    heroTick(ctx.singleton<Arena>(), hero, a, obs, consts::deltaT);
}
```

- [ ] **Step 3: Update sim.cpp bossStepSystem**

Replace `bossTickDispatch` + `bossIntegrate` with:
```cpp
inline void bossStepSystem(Engine &ctx, ...) {
    if (ctx.singleton<GlobalFreeze>().timer > 0.f) return;
    const FsmDef& def = ctx.singleton<FsmDefSingleton>().def;
    fsmTick(def, fsm, bk, sc, hero.posX, hero.posY, ctx.data().rng, consts::deltaT);
    bossIntegrate(bk, sc, consts::deltaT); // gravity + position clamp
}
```

- [ ] **Step 4: Add GlobalFreeze singleton**

```cpp
struct GlobalFreeze { float timer; };
```
Register in `registerTypes`, initialize in `resetEpisodeState`.

- [ ] **Step 5: Update level_gen.cpp**

Initialize all new structs: `FsmRuntime` (from baked initial values), `StunControl`, `HeroState` (from HeroConfig), `GlobalFreeze`.

- [ ] **Step 6: Delete old files**

Remove `boss.hpp` and `consts.hpp`. All their content is now in the FSM data + hero_config.hpp.

- [ ] **Step 7: Build and headless smoke test**

```bash
cmake --build sim/silksong_sim/build/ -j$(nproc) 2>&1 | grep error
./sim/silksong_sim/build/headless CPU 8 5000 --rand-actions
```

- [ ] **Step 8: Python smoke test**

```python
PYTHONPATH=sim/silksong_sim/build uv run python -c "
import silksong_sim, torch
mgr = silksong_sim.SimManager(exec_mode=silksong_sim.madrona.ExecMode.CPU,
    gpu_id=0, num_worlds=8, rand_seed=42, auto_reset=True)
act = mgr.action_tensor().to_torch()
for step in range(5000):
    act[:] = torch.randint(0, 2, act.shape)
    mgr.step()
boss = mgr.boss_obs_tensor().to_torch()
hero = mgr.player_obs_tensor().to_torch()
print(f'Boss HP: {boss[0,0,4].item():.0f}/250')
print(f'Hero HP: {hero[0,0,4].item():.0f}/9')
print('OK')
"
```

---

### Task 9: Verification

**Files:**
- Create: `scripts/verify_sim_fidelity.py`

- [ ] **Step 1: Structural FSM verification**

`scripts/verify_baked_fsm.py` (from Task 2 step 3) — run it and verify zero discrepancies:
```bash
python scripts/verify_baked_fsm.py scripts/lace_boss1_control_fsm.json sim/silksong_sim/src/fsm_lace_boss1.hpp
```

- [ ] **Step 2: Hero method coverage check**

Grep hero.hpp for `// Port of HeroController.cs:` comments and verify every key method is covered:
```bash
grep "Port of HeroController" sim/silksong_sim/src/hero.hpp | sort
```

Expected: Move, HeroJump, DoubleJump, WallJump, Dash, DoAttack, Attack, DidAttack, CanAttack, TakeDamage, StartRecoil, LookForInput, FixedUpdate.

- [ ] **Step 3: Behavioral smoke test**

```python
# Run 16 worlds for 10k steps with random actions
# Verify: boss enters all state categories, hero takes and deals damage,
# stun triggers, CrossSlash fires at rage, lava triggers
PYTHONPATH=sim/silksong_sim/build uv run python -c "
import silksong_sim, torch
mgr = silksong_sim.SimManager(exec_mode=silksong_sim.madrona.ExecMode.CPU,
    gpu_id=0, num_worlds=16, rand_seed=42, auto_reset=True)
act = mgr.action_tensor().to_torch()

boss_cats_seen = set()
hero_hit = 0
boss_hit = 0
stun_seen = False
prev_hp = [250.0]*16

for step in range(10000):
    act[:] = torch.randint(0, 2, act.shape)
    mgr.step()
    boss = mgr.boss_obs_tensor().to_torch()
    hero = mgr.player_obs_tensor().to_torch()
    for w in range(16):
        cat = int(boss[w,0,8].item())
        boss_cats_seen.add(cat)
        bhp = boss[w,0,4].item()
        if bhp < prev_hp[w]: boss_hit += 1
        prev_hp[w] = bhp

print(f'Boss categories seen: {sorted(boss_cats_seen)}')
print(f'Boss hit count: {boss_hit}')
print(f'Expected categories: at least Idle(0), Combo(1), Charge(2), JSlash(3), Counter(4), Evade(7)')
"
```

- [ ] **Step 4: Training sanity check**

```bash
./train --preset seis --total-steps 100000000 --no-wandb
```

Verify: reward increases over time, policy learns to approach and attack boss, boss HP goes down.

---

## Notes for Agents

**Critical principle:** Every value in the sim must trace back to either:
1. A number in `lace_boss1_control_fsm.json` (boss behavior)
2. A number in `HeroController.cs` or `HeroControllerConfig` (hero behavior)
3. A number in `HealthManager.cs` (combat)
4. A number extracted from the game prefab (serialized fields)

If you can't find the source for a value, flag it — don't guess.

**C# → C++ translation rules:**
- `Time.deltaTime` → `dt` parameter
- `rb2d.linearVelocity` → direct velocity assignment (our sweep integration handles collision)
- `cState.X` → `hero.states.X`
- `Config.X` → `hero.config.X`
- `MonoBehaviour` coroutines → state flags + timers (no coroutines in sim)
- `Mathf.X` → `fmaxf`/`fminf`/`fabsf`/etc.
- `Vector2(x, y)` → separate float assignments

**Files to reference:**
- `decompiled/HeroController.cs` — hero physics (12k lines)
- `decompiled/HealthManager.cs` — enemy hit handling (2.5k lines)
- `decompiled/GameManager.cs` — FreezeMoment (5.5k lines)
- `decompiled/HeroControllerStates.cs` — cState struct (353 lines)
- `decompiled/HeroControllerConfig.cs` — config fields (236 lines)
- `decompiled/HeroControllerConfigWarrior.cs` — warrior overrides (65 lines)
- `scripts/lace_boss1_control_fsm.json` — boss FSM data
- `scripts/lace_boss1_fsm_summary.md` — human-readable FSM reference (for context, not as source of truth)
- `scripts/hero_constants_dump.md` — extracted prefab values (for cross-reference)
- `scripts/arena_summary.md` — arena collider data
