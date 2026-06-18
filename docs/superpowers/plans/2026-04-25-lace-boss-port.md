# Lace Boss Port Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port Lace's 206-state PlayMaker FSM + combat mechanics into the Madrona C++ simulator so we can train an RL agent against a faithful boss recreation at ≥50M tps.

**Architecture:** Two-level FSM `(categoryId, subStateId, frameInState)` with one inline tick function per attack category. Boss components live on the same Agent archetype as hero (single entity per world). Combat is AABB-based hitbox checks. Projectiles use a fixed-size ring buffer singleton.

**Tech Stack:** C++ (Madrona ECS), CUDA, nanobind Python bindings, PyTorch PPO trainer.

**Source references:**
- FSM data: `scripts/lace_control_fsm.json` (206 states)
- FSM summary: `scripts/lace_fsm_summary.md`
- Decompiled C#: `decompiled/BOSS_CLASSES_INDEX.md`
- Design spec: `docs/superpowers/specs/2026-04-25-lace-boss-port-design.md`

---

## File Structure

### New files
| File | Responsibility |
|------|---------------|
| `src/boss.hpp` | BossCategory/BossFlag enums, boss constants, all inline boss tick functions (included by sim.cpp) |
| `src/combat.hpp` | AABB overlap test, hero→boss and boss→hero damage functions (included by sim.cpp) |
| `src/raycast.hpp` | 32-ray sensor sweep against arena + boss + projectiles (included by sim.cpp) |

### Modified files
| File | Changes |
|------|---------|
| `src/types.hpp` | Add BossKinematics, BossFSM, BossAttackHitbox, ActiveProjectiles components; add to Agent archetype |
| `src/consts.hpp` | Add boss constants section (HP, velocities, timings, arena bounds) |
| `src/sim.hpp` | No changes needed (ExportID slots already exist for BossObs) |
| `src/sim.cpp` | Include boss.hpp/combat.hpp/raycast.hpp; add bossStepSystem, combatSystem to task graph; wire reward/done |
| `src/level_gen.cpp` | Reset BossKinematics, BossFSM, BossAttackHitbox, ActiveProjectiles on episode reset |
| `src/CMakeLists.txt` | No changes needed (new files are headers included by existing .cpp) |

---

## Step 1: Boss Skeleton + Arena

### Task 1.1: Add boss ECS components to types.hpp

**Files:**
- Modify: `src/types.hpp`

- [ ] **Step 1: Add BossCategory and BossFlag enums**

Add after the `PlayerFlag` enum:

```cpp
enum BossCategory : uint8_t {
    BC_Idle = 0,
    BC_ComboSlash,    // 1
    BC_Charge,        // 2
    BC_JSlash,        // 3
    BC_Counter,       // 4
    BC_RapidSlash,    // 5
    BC_Downstab,      // 6
    BC_EvadeHop,      // 7
    BC_Stun,          // 8
    BC_TeleDive,      // 9
    BC_Tendril,       // 10
    BC_Vomit,         // 11
    BC_BulletSummon,  // 12
    BC_AbyssWave,     // 13
    BC_CrossSlash,    // 14
    BC_PhaseShift,    // 15
    BC_Intro,         // 16
    BC_Death,         // 17
    BC_NumCategories,
};

enum BossFlag : uint32_t {
    BF_FacingRight    = 1u << 0,
    BF_Kinematic      = 1u << 1,   // no physics during tele/dive
    BF_Invincible     = 1u << 2,   // blocks all damage
    BF_HitboxActive   = 1u << 3,   // boss attack hitbox is live
    BF_Phase2         = 1u << 4,
    BF_Phase3         = 1u << 5,
    BF_Phase4         = 1u << 6,
    BF_CounterRange   = 1u << 7,   // hero within counter distance (<6)
    BF_CounterReady   = 1u << 8,   // counter armed after delay
    BF_WillCounter    = 1u << 9,   // 50% post-attack counter
    BF_CanEvade       = 1u << 10,  // evade available
    BF_InEvadeRange   = 1u << 11,
    BF_ForceTele      = 1u << 12,
    BF_EvadeFlipper   = 1u << 13,  // alternates evade direction
    BF_DivingIn       = 1u << 14,
};
```

- [ ] **Step 2: Add BossKinematics struct**

Add after the `PlayerKinematics` struct:

```cpp
struct BossKinematics {
    float posX, posY;
    float velX, velY;
};
```

- [ ] **Step 3: Add BossFSM struct**

```cpp
struct BossFSM {
    uint8_t  categoryId;
    uint8_t  subStateId;
    int16_t  frameInState;       // ticks remaining in current sub-state
    int16_t  hp;                 // 800 max
    int16_t  phase;              // 1-4

    // Stun
    int16_t  stunGauge;          // accumulates toward stunThreshold
    int16_t  stunTimer;          // remaining stun ticks

    // Attack selection (SendRandomEventV4)
    uint8_t  lastAttack;
    uint8_t  consecutiveCount;
    uint8_t  missedCounts[8];    // per-attack-slot missed counter

    // FSM counters
    int16_t  chargesPerformed;
    int16_t  abyssWaveCountdown; // decrements each idle, triggers at <= 1
    int16_t  idleTimer;          // ticks remaining in idle
    int16_t  invincTimer;        // invincibility ticks remaining after hit
    int16_t  counterDelayTimer;  // counter ready delay

    // Movement check state
    float    distanceMin;        // current attack's min range
    float    distanceMax;        // current attack's max range

    // Attack hitbox (active during damage windows)
    float    hitboxHalfW;
    float    hitboxHalfH;
    float    hitboxOffsetX;
    float    hitboxOffsetY;
    int16_t  hitboxDamage;       // 1 for most attacks

    uint32_t flags;              // BossFlag packed
};
```

- [ ] **Step 4: Add ActiveProjectiles singleton**

```cpp
struct ActiveProjectiles {
    static constexpr int MAX = 32;
    float    posX[MAX], posY[MAX];
    float    velX[MAX], velY[MAX];
    float    halfW[MAX], halfH[MAX];
    int16_t  ttl[MAX];
    uint8_t  damage[MAX];
    uint32_t activeMask;
};
```

- [ ] **Step 5: Add components to Agent archetype and register**

Modify the `Agent` archetype to include the new components:

```cpp
struct Agent : public madrona::Archetype<
    Action,
    PlayerKinematics,
    PlayerObs,
    BossKinematics,
    BossFSM,
    BossObs,
    RaycastDistances,
    RaycastHitTypes,
    EpisodeState,
    Reward,
    Done
> {};
```

- [ ] **Step 6: Build and verify**

Run: `cmake --build sim/silksong_sim/build/ -j$(nproc)`
Expected: Clean compilation with no errors. Static asserts pass.

- [ ] **Step 7: Commit**

```bash
git add sim/silksong_sim/src/types.hpp
git commit -m "types: add BossKinematics, BossFSM, ActiveProjectiles components"
```

---

### Task 1.2: Add boss constants to consts.hpp

**Files:**
- Modify: `src/consts.hpp`

- [ ] **Step 1: Add boss constants section**

Add at the end of the `consts` namespace, before the closing braces. All values sourced from `scripts/lace_fsm_summary.md` and `decompiled/BOSS_CLASSES_INDEX.md`:

```cpp
// ---- Boss (Lace) ---------------------------------------------------------
inline constexpr int16_t bossMaxHP          = 800;
inline constexpr float   bossGravity        = -2.0f;    // FSM var "Gravity"
inline constexpr float   bossLandY          = 6.4f;     // FSM var "Land Y"
inline constexpr float   bossIdleTimeP1     = 0.7f;     // seconds
inline constexpr float   bossIdleTimeP2     = 0.5f;     // reduced after P2 shift
inline constexpr int16_t bossP2HP           = 600;      // phase 2 threshold
inline constexpr int16_t bossP3HP           = 450;      // phase 3 threshold (estimate)
inline constexpr int16_t bossP4HP           = 320;      // phase 4 threshold
inline constexpr int16_t bossStunThreshold  = 7;        // hits to stun (estimate, needs Stun Control FSM)
inline constexpr int16_t bossStunDuration   = 80;       // 1.6s stun
inline constexpr int16_t bossInvincFrames   = 12;       // i-frames after hit
inline constexpr float   bossRecoilDefault  = 12.0f;    // FSM var "Recoil Default"
inline constexpr float   bossRecoilReduced  = 5.0f;     // FSM var "Recoil Reduced"

// Boss attack velocities (from FSM extraction, all "scaled" = multiplied by facing ±1)
inline constexpr float   bossChargeAnticVel = -32.0f;   // backward wind-up
inline constexpr float   bossChargeVel      = 70.0f;    // forward dash
inline constexpr float   bossComboLungeVel  = 40.0f;    // FSM var "Combo Slash Speed"
inline constexpr float   bossEvadeVel       = -28.0f;   // backward dodge
inline constexpr float   bossHopVel         = 36.0f;    // forward hop
inline constexpr float   bossRapidGroundVel = 30.0f;    // rush in
inline constexpr float   bossRapidAirVelX   = 35.0f;    // diagonal air slash
inline constexpr float   bossRapidAirVelY   = -22.5f;
inline constexpr float   bossJSlashVelX     = 60.0f;    // diagonal launch
inline constexpr float   bossJSlashVelY     = 60.0f;
inline constexpr float   bossStunKnockVelX  = -8.0f;    // stun knockback arc
inline constexpr float   bossStunKnockVelY  = 24.0f;
inline constexpr float   bossTendrilDashVel = 20.0f;    // ground tendril rush
inline constexpr float   bossBounceBackVelX = -10.0f;   // post-air-slash
inline constexpr float   bossBounceBackVelY = 15.0f;
inline constexpr float   bossCSFlipVelX     = -14.0f;   // after cross slash
inline constexpr float   bossCSFlipVelY     = 20.0f;

// Boss attack timing (frames at 50 Hz)
inline constexpr int16_t bossChargeAnticFrames   = 10;  // 0.2s
inline constexpr int16_t bossChargeFrames        = 13;  // 0.25s (FSM var "Charge Time")
inline constexpr int16_t bossChargeRecoverFrames = 15;
inline constexpr int16_t bossComboStrikeFrames   = 8;   // per-strike duration
inline constexpr int16_t bossCounterStanceFrames = 25;  // 0.5s
inline constexpr int16_t bossCounterAnticFrames  = 8;   // 0.15s
inline constexpr int16_t bossRapidLoopFrames     = 33;  // 0.65s
inline constexpr int16_t bossJSlashAnticFrames   = 30;  // 0.6s
inline constexpr int16_t bossTendrilWhipFrames   = 30;  // 0.6s
inline constexpr int16_t bossStunRecoverPause    = 38;  // 0.75s
inline constexpr int16_t bossPhaseShiftFrames    = 65;  // 1.3s
inline constexpr int16_t bossMultihitPause       = 38;  // 0.75s

// Boss hitbox dimensions (estimates — refine from scene data)
inline constexpr float   bossBodyHalfW      = 0.8f;
inline constexpr float   bossBodyHalfH      = 1.2f;
inline constexpr float   bossSlashHalfW     = 1.5f;     // combo/rapid slash reach
inline constexpr float   bossSlashHalfH     = 1.0f;
inline constexpr float   bossChargeHalfW    = 1.0f;     // charge hitbox
inline constexpr float   bossChargeHalfH    = 1.0f;

// Boss distance thresholds (from FSM)
inline constexpr float   bossCounterDist    = 6.0f;     // counter trigger range
inline constexpr float   bossForceAttackDist = 20.0f;   // anti-camping range
inline constexpr float   bossEvadeCheckDist = 8.0f;     // evade reaction radius
inline constexpr float   bossTeleMinDist    = 5.0f;     // min distance from hero after tele
inline constexpr float   bossTeleXMin       = 6.0f;     // FSM "Tele X Min"
inline constexpr float   bossTeleXMax       = 51.0f;    // FSM "Tele X Max"

// Hero combat constants (from decompiled HeroController / HeroBox)
inline constexpr float   heroHurtNormalHalfW = 0.23f;
inline constexpr float   heroHurtNormalHalfH = 1.125f;
inline constexpr float   heroHurtNormalOffY  = -0.38f;
inline constexpr float   heroRecoilSpeed     = 15.0f;    // RECOIL_HOR_VELOCITY (estimate)
inline constexpr int16_t heroRecoilFrames    = 5;        // RECOIL_HOR_STEPS (estimate)
inline constexpr int16_t heroInvulFrames     = 50;       // INVUL_TIME ~1s
```

- [ ] **Step 2: Build and verify**

Run: `cmake --build sim/silksong_sim/build/ -j$(nproc)`

- [ ] **Step 3: Commit**

```bash
git add sim/silksong_sim/src/consts.hpp
git commit -m "consts: add Lace boss velocities, timings, hitbox dimensions"
```

---

### Task 1.3: Register new components and wire boss reset

**Files:**
- Modify: `src/sim.cpp` (registerTypes section only)
- Modify: `src/level_gen.cpp`

- [ ] **Step 1: Register new components in sim.cpp**

In `Sim::registerTypes`, add after the existing component registrations:

```cpp
registry.registerComponent<BossKinematics>();
registry.registerComponent<BossFSM>();

registry.registerSingleton<ActiveProjectiles>();
```

And add the export for BossKinematics if needed for debugging (optional — BossObs already covers the obs contract).

- [ ] **Step 2: Reset boss state in level_gen.cpp**

In `resetEpisodeState`, add after the `BossObs` initialization:

```cpp
ctx.get<BossKinematics>(e) = BossKinematics{
    .posX = consts::bossSpawnX,
    .posY = consts::bossSpawnY,
    .velX = 0.f,
    .velY = 0.f,
};

ctx.get<BossFSM>(e) = BossFSM{
    .categoryId = BC_Idle,
    .subStateId = 0,
    .frameInState = (int16_t)(consts::bossIdleTimeP1 / consts::deltaT),
    .hp = consts::bossMaxHP,
    .phase = 1,
    .stunGauge = 0,
    .stunTimer = 0,
    .lastAttack = 0,
    .consecutiveCount = 0,
    .missedCounts = {},
    .chargesPerformed = 0,
    .abyssWaveCountdown = 2,
    .idleTimer = 0,
    .invincTimer = 0,
    .counterDelayTimer = 0,
    .distanceMin = 0.f,
    .distanceMax = 0.f,
    .hitboxHalfW = 0.f,
    .hitboxHalfH = 0.f,
    .hitboxOffsetX = 0.f,
    .hitboxOffsetY = 0.f,
    .hitboxDamage = 1,
    .flags = BF_FacingRight,
};
```

Also reset the ActiveProjectiles singleton:

```cpp
ActiveProjectiles &proj = ctx.singleton<ActiveProjectiles>();
proj.activeMask = 0;
for (int i = 0; i < ActiveProjectiles::MAX; ++i) proj.ttl[i] = 0;
```

- [ ] **Step 3: Build and verify**

Run: `cmake --build sim/silksong_sim/build/ -j$(nproc)`

- [ ] **Step 4: Run self-test to verify no regression**

Run: `PYTHONPATH=sim/silksong_sim/build uv run python sim/silksong_sim/scripts/oracle_diff.py --self-test`
Expected: PASS with 0 drift (hero physics unchanged).

- [ ] **Step 5: Commit**

```bash
git add sim/silksong_sim/src/sim.cpp sim/silksong_sim/src/level_gen.cpp
git commit -m "sim: register boss components, reset boss state on episode start"
```

---

### Task 1.4: Implement boss physics + idle/attack-choice loop

**Files:**
- Create: `src/boss.hpp`
- Modify: `src/sim.cpp` (include boss.hpp, add bossStepSystem to task graph)

- [ ] **Step 1: Create boss.hpp with physics integration and idle loop**

Create `src/boss.hpp`. This file contains all inline boss tick functions included by sim.cpp. Start with the skeleton: physics integration, idle state, and attack choice (random selection with stub transitions).

```cpp
#pragma once
#include "types.hpp"
#include "consts.hpp"

namespace silksong {

// Forward-declared arena collision from sim.cpp
static inline bool isTileSolid(const Arena &a, float worldX, float worldY);

// ---- Boss physics integration ----

static inline void bossIntegrate(const Arena &arena, BossKinematics &bk,
                                  BossFSM &fsm, float dt)
{
    if (fsm.flags & BF_Kinematic) return;

    bk.velY += consts::bossGravity * dt;
    bk.posX += bk.velX * dt;
    bk.posY += bk.velY * dt;

    // Floor clamp
    const float floorY = consts::bossLandY + consts::bossBodyHalfH;
    if (bk.posY < floorY) {
        bk.posY = floorY;
        bk.velY = 0.f;
    }
    // Arena X clamp
    if (bk.posX < consts::bossTeleXMin + consts::bossBodyHalfW) {
        bk.posX = consts::bossTeleXMin + consts::bossBodyHalfW;
        bk.velX = 0.f;
    }
    if (bk.posX > consts::bossTeleXMax - consts::bossBodyHalfW) {
        bk.posX = consts::bossTeleXMax - consts::bossBodyHalfW;
        bk.velX = 0.f;
    }
}

// ---- Facing helper ----

static inline float bossScaleVel(const BossFSM &fsm, float speed)
{
    return (fsm.flags & BF_FacingRight) ? speed : -speed;
}

static inline void bossFaceHero(BossFSM &fsm, float bossX, float heroX)
{
    if (heroX > bossX)
        fsm.flags |= BF_FacingRight;
    else
        fsm.flags &= ~BF_FacingRight;
}

// ---- Attack selection (SendRandomEventV4) ----

static inline uint8_t bossPickAttack(BossFSM &fsm, madrona::RNG &rng)
{
    // Phase-dependent attack pool
    int numAttacks = 4; // P1: COMBO, CHARGE, J_SLASH, TENDRIL
    if (fsm.flags & BF_Phase2) numAttacks = 7;
    if (fsm.flags & BF_Phase4) numAttacks = 8;

    // Weights with eventMax/missedMax anti-repetition
    float weights[8] = {};
    int eventMax = (fsm.flags & BF_Phase2) ? 2 : 2;
    int missedMax = 4;
    if (fsm.flags & BF_Phase2) missedMax = 7;
    if (fsm.flags & BF_Phase4) missedMax = 8;

    for (int i = 0; i < numAttacks; ++i) {
        weights[i] = 1.0f;
        // Phase 4 CROSS_SLASH (slot 7) has weight 0
        if (i == 7) weights[i] = 0.f;
        // Suppress if hit consecutive max
        if (i == fsm.lastAttack && fsm.consecutiveCount >= eventMax)
            weights[i] = 0.f;
        // Force if missed too many times
        if (fsm.missedCounts[i] >= missedMax)
            weights[i] = 100.f;
    }

    float totalWeight = 0.f;
    for (int i = 0; i < numAttacks; ++i) totalWeight += weights[i];
    if (totalWeight <= 0.f) { totalWeight = 1.f; weights[0] = 1.f; }

    float roll = rng.sampleUniform() * totalWeight;
    uint8_t pick = 0;
    float cumulative = 0.f;
    for (int i = 0; i < numAttacks; ++i) {
        cumulative += weights[i];
        if (roll < cumulative) { pick = (uint8_t)i; break; }
    }

    // Map pool index to BossCategory
    static constexpr uint8_t poolToCategory[] = {
        BC_ComboSlash, BC_Charge, BC_JSlash, BC_Tendril,
        BC_Vomit, BC_BulletSummon, BC_Tendril, // slot 6 = TendrilSummon, reuse BC_Tendril
        BC_CrossSlash,
    };
    uint8_t cat = poolToCategory[pick];

    // Update anti-repetition state
    for (int i = 0; i < numAttacks; ++i) {
        if (i == pick) {
            fsm.missedCounts[i] = 0;
        } else {
            fsm.missedCounts[i] = (uint8_t)fminf(fsm.missedCounts[i] + 1, 255);
        }
    }
    if (pick == fsm.lastAttack) {
        fsm.consecutiveCount++;
    } else {
        fsm.consecutiveCount = 1;
    }
    fsm.lastAttack = pick;

    return cat;
}

// ---- Category tick stubs (Step 1 = idle only, rest are stubs) ----

static inline void bossTickIdle(BossKinematics &bk, BossFSM &fsm,
                                 float heroX, float heroY, madrona::RNG &rng)
{
    bk.velX = 0.f;
    fsm.flags &= ~BF_HitboxActive;

    if (fsm.frameInState > 0) {
        fsm.frameInState--;
        return;
    }

    // Idle timer expired → attack choice
    bossFaceHero(fsm, bk.posX, heroX);
    float dist = fabsf(bk.posX - heroX);

    // Anti-camping: force attack if hero > 20 units away
    // Counter check: distance < 6 and counter ready (skipped in Step 1)

    uint8_t cat = bossPickAttack(fsm, rng);
    fsm.categoryId = cat;
    fsm.subStateId = 0;
    fsm.frameInState = 10; // placeholder — each category sets its own
}

static inline void bossTickStub(BossKinematics &bk, BossFSM &fsm)
{
    // Placeholder for unimplemented categories: wait then return to idle
    if (fsm.frameInState > 0) {
        fsm.frameInState--;
        return;
    }
    fsm.categoryId = BC_Idle;
    fsm.subStateId = 0;
    float idleTime = (fsm.flags & BF_Phase2) ? consts::bossIdleTimeP2 : consts::bossIdleTimeP1;
    fsm.frameInState = (int16_t)(idleTime / consts::deltaT);
}

// ---- Main boss step dispatch ----

static inline void bossTickDispatch(BossKinematics &bk, BossFSM &fsm,
                                     float heroX, float heroY,
                                     madrona::RNG &rng)
{
    switch (fsm.categoryId) {
        case BC_Idle:
            bossTickIdle(bk, fsm, heroX, heroY, rng);
            break;
        default:
            bossTickStub(bk, fsm);
            break;
    }
}

} // namespace silksong
```

- [ ] **Step 2: Add bossStepSystem to sim.cpp**

In sim.cpp, add `#include "boss.hpp"` after the existing includes. Then add the boss step system function and wire it into the task graph.

Add the system function before `stepSystem`:

```cpp
inline void bossStepSystem(Engine &ctx,
                           const Action &,
                           PlayerKinematics &pk,
                           BossKinematics &bk,
                           BossFSM &fsm,
                           BossObs &bossObs)
{
    const Arena &arena = ctx.singleton<Arena>();

    // Tick FSM
    bossTickDispatch(bk, fsm, pk.posX, pk.posY, ctx.data().rng);

    // Integrate boss physics
    bossIntegrate(arena, bk, fsm, consts::deltaT);

    // Project observation
    bossObs.posX = bk.posX;
    bossObs.posY = bk.posY;
    bossObs.velX = bk.velX;
    bossObs.velY = bk.velY;
    bossObs.health = (float)fsm.hp;
    bossObs.maxHealth = (float)consts::bossMaxHP;
    bossObs.phase = (float)fsm.phase;
    bossObs.facingRight = (fsm.flags & BF_FacingRight) ? 1.f : 0.f;
    bossObs.animState = (float)fsm.categoryId;
    bossObs.animProgress = (float)fsm.subStateId;
}
```

In `setupTasks`, add the boss step after hero step:

```cpp
auto boss_tasks = builder.addToGraph<ParallelForNode<Engine,
    bossStepSystem,
        Action,
        PlayerKinematics,
        BossKinematics,
        BossFSM,
        BossObs
    >>({hero_tasks});

// Change stepSystem's dependency from hero_tasks to boss_tasks
builder.addToGraph<ParallelForNode<Engine,
    stepSystem,
        EpisodeState,
        Reward,
        Done
    >>({boss_tasks});
```

- [ ] **Step 3: Build and verify**

Run: `cmake --build sim/silksong_sim/build/ -j$(nproc)`

- [ ] **Step 4: Run headless benchmark to verify throughput**

Run: `sim/silksong_sim/build/headless CPU 1024 100`
Expected: Boss picks random attacks, returns to idle. Throughput remains high.

- [ ] **Step 5: Run self-test**

Run: `PYTHONPATH=sim/silksong_sim/build uv run python sim/silksong_sim/scripts/oracle_diff.py --self-test`
Expected: PASS (hero physics unchanged).

- [ ] **Step 6: Commit**

```bash
git add sim/silksong_sim/src/boss.hpp sim/silksong_sim/src/sim.cpp
git commit -m "boss: skeleton FSM with idle/attack-choice loop and physics integration"
```

---

## Step 2: Melee Attacks + Combat

### Task 2.1: Implement Charge category

**Files:**
- Modify: `src/boss.hpp`

- [ ] **Step 1: Replace bossTickStub for BC_Charge with full implementation**

The Charge FSM sequence from `lace_fsm_summary.md`:
```
ChargeAntic (vel=-32, 0.2s) → Charge (vel=70, 0.25s) → ChargeRecover (15f)
```

Sub-state IDs: 0=Antic, 1=Charge, 2=Recover.

```cpp
static inline void bossTickCharge(BossKinematics &bk, BossFSM &fsm,
                                   float heroX)
{
    const float facing = (fsm.flags & BF_FacingRight) ? 1.f : -1.f;
    switch (fsm.subStateId) {
    case 0: // Antic: backward wind-up
        bk.velX = facing * consts::bossChargeAnticVel;
        bk.velY = 0.f;
        fsm.flags &= ~BF_HitboxActive;
        if (--fsm.frameInState <= 0) {
            fsm.subStateId = 1;
            fsm.frameInState = consts::bossChargeFrames;
        }
        break;
    case 1: // Charge: forward dash, hitbox active
        bk.velX = facing * consts::bossChargeVel;
        bk.velY = 0.f;
        fsm.flags |= BF_HitboxActive;
        fsm.hitboxHalfW = consts::bossChargeHalfW;
        fsm.hitboxHalfH = consts::bossChargeHalfH;
        fsm.hitboxOffsetX = facing * 1.0f;
        fsm.hitboxOffsetY = 0.f;
        fsm.hitboxDamage = 1;
        if (--fsm.frameInState <= 0) {
            fsm.subStateId = 2;
            fsm.frameInState = consts::bossChargeRecoverFrames;
        }
        break;
    case 2: // Recover: punish window
        bk.velX = 0.f;
        fsm.flags &= ~BF_HitboxActive;
        if (--fsm.frameInState <= 0) {
            // Return to idle
            fsm.categoryId = BC_Idle;
            fsm.subStateId = 0;
            float idleTime = (fsm.flags & BF_Phase2)
                ? consts::bossIdleTimeP2 : consts::bossIdleTimeP1;
            fsm.frameInState = (int16_t)(idleTime / consts::deltaT);
        }
        break;
    }
}
```

- [ ] **Step 2: Wire into dispatch**

In `bossTickDispatch`, replace the default stub case for `BC_Charge`:

```cpp
case BC_Charge:
    bossTickCharge(bk, fsm, heroX);
    break;
```

- [ ] **Step 3: Set initial frame count in attack choice**

In `bossTickIdle`, when the pick maps to `BC_Charge`, set the antic frame count:

```cpp
if (cat == BC_Charge) {
    fsm.frameInState = consts::bossChargeAnticFrames;
    bossFaceHero(fsm, bk.posX, heroX);
}
```

- [ ] **Step 4: Build, verify**

Run: `cmake --build sim/silksong_sim/build/ -j$(nproc)`

- [ ] **Step 5: Commit**

```bash
git add sim/silksong_sim/src/boss.hpp
git commit -m "boss: implement Charge category (antic → dash → recover)"
```

---

### Task 2.2: Implement ComboSlash category

**Files:**
- Modify: `src/boss.hpp`

- [ ] **Step 1: Add bossTickComboSlash**

7-strike combo. Strikes 2/4/6 have forward lunge at comboSlashSpeed. Hitbox active during strike frames.

Sub-states: 0-6 = ComboSlash 1-7. Each lasts bossComboStrikeFrames. Even-indexed sub-states (1, 3, 5 = strikes 2, 4, 6) apply lunge velocity.

```cpp
static inline void bossTickComboSlash(BossKinematics &bk, BossFSM &fsm,
                                       float heroX)
{
    const float facing = (fsm.flags & BF_FacingRight) ? 1.f : -1.f;
    // Lunge on even sub-states (strikes 2, 4, 6 in 0-indexed: 1, 3, 5)
    bool isLunge = (fsm.subStateId & 1) != 0;
    bk.velX = isLunge ? facing * consts::bossComboLungeVel : 0.f;
    bk.velY = 0.f;

    // Hitbox active during all strikes
    fsm.flags |= BF_HitboxActive;
    fsm.hitboxHalfW = consts::bossSlashHalfW;
    fsm.hitboxHalfH = consts::bossSlashHalfH;
    fsm.hitboxOffsetX = facing * 1.2f;
    fsm.hitboxOffsetY = 0.f;
    fsm.hitboxDamage = 1;

    if (--fsm.frameInState <= 0) {
        fsm.subStateId++;
        if (fsm.subStateId >= 7) {
            // Combo complete → idle
            fsm.categoryId = BC_Idle;
            fsm.subStateId = 0;
            float idleTime = (fsm.flags & BF_Phase2)
                ? consts::bossIdleTimeP2 : consts::bossIdleTimeP1;
            fsm.frameInState = (int16_t)(idleTime / consts::deltaT);
            fsm.flags &= ~BF_HitboxActive;
        } else {
            fsm.frameInState = consts::bossComboStrikeFrames;
        }
    }
}
```

- [ ] **Step 2: Wire into dispatch and set initial frames in attack choice**

- [ ] **Step 3: Build, commit**

```bash
git commit -m "boss: implement ComboSlash category (7-strike melee combo)"
```

---

### Task 2.3: Implement remaining melee categories

**Files:**
- Modify: `src/boss.hpp`

Implement each category following the same pattern as Charge and ComboSlash. Each is an inline function with sub-state switch, velocity profiles from the FSM summary, and hitbox activation during active frames.

- [ ] **Step 1: Implement bossTickJSlash** — antic (30f) → diagonal launch (vel=60x/60y) → land → recover. Hitbox active during launch.

- [ ] **Step 2: Implement bossTickCounter** — antic (8f) → stance (25f, invincible) → end. On hero attack during stance: counter hit.

- [ ] **Step 3: Implement bossTickRapidSlash** — charge (vel=30, approach) → loop (33f, hitbox) → end. Air variant: vel=35x/-22.5y.

- [ ] **Step 4: Implement bossTickDownstab** — antic → downward (velY increasing until ground) → land → recover.

- [ ] **Step 5: Implement bossTickEvadeHop** — evade: vel=-28, 15f. Hop: vel=36, cancel at distance < 6. Hop Up: vertical.

- [ ] **Step 6: Implement bossTickStun** — knockback arc (vel=-8x/24y) → air → land → stunned (timer) → recover (38f) → idle. Global STUN transition handled in dispatch.

- [ ] **Step 7: Implement bossTickTeleDive** — set kinematic, hide (vel=0), compute target position (clamped to [TeleXMin, TeleXMax], >5 from hero), emerge at target, unset kinematic.

- [ ] **Step 8: Wire all into dispatch, build, run headless, commit**

```bash
git commit -m "boss: implement all melee attack categories (JSlash, Counter, RapidSlash, Downstab, EvadeHop, Stun, TeleDive)"
```

---

### Task 2.4: Implement combat system (hitbox checks + damage)

**Files:**
- Create: `src/combat.hpp`
- Modify: `src/sim.cpp` (add combatSystem to task graph, wire reward)

- [ ] **Step 1: Create combat.hpp with AABB overlap and damage functions**

```cpp
#pragma once
#include "types.hpp"
#include "consts.hpp"

namespace silksong {

static inline bool aabbOverlap(float ax, float ay, float ahw, float ahh,
                                float bx, float by, float bhw, float bhh)
{
    return fabsf(ax - bx) < (ahw + bhw) && fabsf(ay - by) < (ahh + bhh);
}

// Hero attacks boss: check PF_AttackActive + AABB overlap with boss body
static inline float heroHitsBoss(const PlayerKinematics &pk,
                                  BossKinematics &bk, BossFSM &fsm)
{
    if (!(pk.flags & PF_AttackActive)) return 0.f;
    if (fsm.invincTimer > 0) return 0.f;
    if (fsm.flags & BF_Invincible) return 0.f;

    const float facing = (pk.flags & PF_FacingRight) ? 1.f : -1.f;
    const float attackX = pk.posX + facing * consts::attackRange * 0.5f;
    const float attackY = pk.posY;

    if (!aabbOverlap(attackX, attackY, consts::attackRange * 0.5f, consts::heroHalfHeight,
                     bk.posX, bk.posY, consts::bossBodyHalfW, consts::bossBodyHalfH))
        return 0.f;

    // Apply damage
    int16_t dmg = consts::attackDamage;
    fsm.hp = (int16_t)(fsm.hp - dmg);
    fsm.invincTimer = consts::bossInvincFrames;
    fsm.stunGauge++;

    // Stun check
    if (fsm.stunGauge >= consts::bossStunThreshold
        && fsm.categoryId != BC_Stun) {
        fsm.categoryId = BC_Stun;
        fsm.subStateId = 0;
        fsm.frameInState = 10; // stun start frames
        fsm.stunGauge = 0;
    }

    return (float)dmg / (float)consts::bossMaxHP;
}

// Boss attacks hero: check BF_HitboxActive + AABB overlap with hero hurtbox
static inline float bossHitsHero(const BossKinematics &bk, const BossFSM &fsm,
                                  PlayerKinematics &pk, PlayerObs &obs)
{
    if (!(fsm.flags & BF_HitboxActive)) return 0.f;
    if (pk.iFrameRem > 0) return 0.f;

    float hitX = bk.posX + fsm.hitboxOffsetX;
    float hitY = bk.posY + fsm.hitboxOffsetY;

    if (!aabbOverlap(hitX, hitY, fsm.hitboxHalfW, fsm.hitboxHalfH,
                     pk.posX, pk.posY + consts::heroHurtNormalOffY,
                     consts::heroHurtNormalHalfW, consts::heroHurtNormalHalfH))
        return 0.f;

    // Apply damage to hero
    obs.health = fmaxf(obs.health - (float)fsm.hitboxDamage, 0.f);
    pk.iFrameRem = consts::heroInvulFrames;

    // Recoil hero away from boss
    float recoilDir = (pk.posX > bk.posX) ? 1.f : -1.f;
    pk.velX = recoilDir * consts::heroRecoilSpeed;

    return 1.0f / (float)consts::playerMaxHealth;
}

} // namespace silksong
```

- [ ] **Step 2: Add combatSystem to sim.cpp**

Include `combat.hpp`. Add a combat system that runs after boss step:

```cpp
inline void combatSystem(Engine &ctx,
                         PlayerKinematics &pk,
                         PlayerObs &obs,
                         BossKinematics &bk,
                         BossFSM &fsm,
                         Reward &reward,
                         Done &done)
{
    float r = 0.f;

    // Hero → Boss
    r += heroHitsBoss(pk, bk, fsm);

    // Boss → Hero
    r -= bossHitsHero(bk, fsm, pk, obs);

    // Win/loss
    if (fsm.hp <= 0) {
        r += 10.f;
        done.v = 1;
    }
    if (obs.health <= 0.f) {
        r -= 5.f;
        done.v = 1;
    }

    reward.v += r;

    // Tick boss timers
    if (fsm.invincTimer > 0) fsm.invincTimer--;
}
```

Wire into the task graph after boss_tasks, and modify stepSystem to accumulate reward (move `reward.v = 0.f` to the START of stepSystem so combatSystem can write to it before stepSystem runs, or restructure so combatSystem writes directly and stepSystem doesn't zero it).

- [ ] **Step 3: Update stepSystem to not zero reward**

Change stepSystem to zero the reward BEFORE combat runs. The cleanest approach: zero reward in a pre-step system or at the start of heroStepSystem. Replace:

```cpp
reward.v = 0.f;  // Phase 5.3+ wires real combat rewards.
```

with nothing (remove it), and instead zero it at the start of combatSystem:

```cpp
reward.v = 0.f; // reset each step
float r = 0.f;
// ... rest of combat
reward.v = r;
```

- [ ] **Step 4: Add combatSystem to task graph**

```cpp
auto combat_tasks = builder.addToGraph<ParallelForNode<Engine,
    combatSystem,
        PlayerKinematics,
        PlayerObs,
        BossKinematics,
        BossFSM,
        Reward,
        Done
    >>({boss_tasks});

builder.addToGraph<ParallelForNode<Engine,
    stepSystem,
        EpisodeState,
        Reward,
        Done
    >>({combat_tasks});
```

- [ ] **Step 5: Build, run headless**

Run: `cmake --build sim/silksong_sim/build/ -j$(nproc) && sim/silksong_sim/build/headless CPU 1024 100`

- [ ] **Step 6: Run a short training test**

Run: `PYTHONPATH=sim/silksong_sim/build uv run python sim/silksong_sim/scripts/train_ppo.py --num-worlds 4096 --total-steps 65536`
Expected: Non-zero rewards appear. Loss decreases. This is the first training signal.

- [ ] **Step 7: Commit**

```bash
git add sim/silksong_sim/src/combat.hpp sim/silksong_sim/src/sim.cpp
git commit -m "combat: AABB hitbox checks, hero↔boss damage, reward signal wired"
```

---

## Step 3: Projectile Attacks + Raycasts

### Task 3.1: Implement projectile spawning + physics

**Files:**
- Modify: `src/boss.hpp` (add Vomit, BulletSummon, TendrilSummon categories)
- Modify: `src/sim.cpp` (add projectileStepSystem)

- [ ] **Step 1: Add projectile spawn helper to boss.hpp**

```cpp
static inline void spawnProjectile(ActiveProjectiles &proj,
                                    float px, float py,
                                    float vx, float vy,
                                    float hw, float hh,
                                    int16_t ttl, uint8_t dmg)
{
    if (proj.activeMask == 0xFFFFFFFF) return; // full
    int slot = __builtin_ctz(~proj.activeMask); // first free bit
    proj.posX[slot] = px; proj.posY[slot] = py;
    proj.velX[slot] = vx; proj.velY[slot] = vy;
    proj.halfW[slot] = hw; proj.halfH[slot] = hh;
    proj.ttl[slot] = ttl;
    proj.damage[slot] = dmg;
    proj.activeMask |= (1u << slot);
}
```

- [ ] **Step 2: Implement bossTickVomit**

Vomit fires projectile volleys with velocity ramp: each repeat adds +6.5 to X velocity, +2.0 to Y. Wait 0.1s between volleys.

- [ ] **Step 3: Implement bossTickBulletSummon and bossTickTendril (summon variant)**

- [ ] **Step 4: Add projectileStepSystem to sim.cpp**

Integrates all active projectiles, checks TTL, checks arena collision, checks hero AABB overlap for damage. Runs after combatSystem.

```cpp
inline void projectileStepSystem(Engine &ctx,
                                  PlayerKinematics &pk,
                                  PlayerObs &obs,
                                  Reward &reward,
                                  Done &done)
{
    ActiveProjectiles &proj = ctx.singleton<ActiveProjectiles>();
    const Arena &arena = ctx.singleton<Arena>();
    uint32_t mask = proj.activeMask;
    while (mask) {
        int i = __builtin_ctz(mask);
        mask &= mask - 1;

        // Integrate
        proj.posX[i] += proj.velX[i] * consts::deltaT;
        proj.posY[i] += proj.velY[i] * consts::deltaT;
        proj.ttl[i]--;

        // Despawn on TTL or arena collision
        bool oob = proj.posX[i] < consts::bossTeleXMin
                || proj.posX[i] > consts::bossTeleXMax
                || proj.posY[i] < consts::bossLandY;
        if (proj.ttl[i] <= 0 || oob) {
            proj.activeMask &= ~(1u << i);
            continue;
        }

        // Hero hit check
        if (pk.iFrameRem > 0) continue;
        if (aabbOverlap(proj.posX[i], proj.posY[i], proj.halfW[i], proj.halfH[i],
                        pk.posX, pk.posY + consts::heroHurtNormalOffY,
                        consts::heroHurtNormalHalfW, consts::heroHurtNormalHalfH)) {
            obs.health = fmaxf(obs.health - (float)proj.damage[i], 0.f);
            pk.iFrameRem = consts::heroInvulFrames;
            reward.v -= 1.0f / (float)consts::playerMaxHealth;
            proj.activeMask &= ~(1u << i);
            if (obs.health <= 0.f) { reward.v -= 5.f; done.v = 1; }
        }
    }
}
```

- [ ] **Step 5: Wire into task graph, build, test, commit**

```bash
git commit -m "projectiles: ring buffer spawn/integrate/despawn, vomit + bullet summon attacks"
```

---

### Task 3.2: Implement 32-ray sensor

**Files:**
- Create: `src/raycast.hpp`
- Modify: `src/sim.cpp` (add raycastSystem)

- [ ] **Step 1: Create raycast.hpp**

32 rays evenly distributed around the hero. Each ray marches through the arena tilemap, then distance-tests against boss body and active projectiles.

```cpp
#pragma once
#include "types.hpp"
#include "consts.hpp"
#include <cmath>

namespace silksong {

static inline bool isTileSolid(const Arena &a, float worldX, float worldY);

enum RayHitType : int32_t {
    RHT_None = 0,
    RHT_Terrain = 1,
    RHT_Enemy = 2,
    RHT_Projectile = 3,
    RHT_Hazard = 4,
    RHT_BossProjectile = 5,
};

static inline void castRays(const Arena &arena,
                             const PlayerKinematics &pk,
                             const BossKinematics &bk,
                             const BossFSM &fsm,
                             const ActiveProjectiles &proj,
                             RaycastDistances &rd,
                             RaycastHitTypes &rh)
{
    constexpr float maxDist = consts::maxRayDistance;
    constexpr float step = 0.5f; // march step size
    constexpr int maxSteps = (int)(maxDist / step);

    for (int r = 0; r < consts::numRays; ++r) {
        float angle = (float)r / (float)consts::numRays * 2.f * 3.14159265f;
        float dx = cosf(angle) * step;
        float dy = sinf(angle) * step;

        float rx = pk.posX;
        float ry = pk.posY;
        float bestDist = maxDist;
        int32_t bestType = RHT_None;

        // March through arena
        for (int s = 1; s <= maxSteps; ++s) {
            rx += dx;
            ry += dy;
            float d = (float)s * step;

            if (isTileSolid(arena, rx, ry)) {
                bestDist = d;
                bestType = RHT_Terrain;
                break;
            }
        }

        // Check boss body (closer?)
        {
            // Simple ray-AABB: compute distance along ray to boss AABB
            float toBossX = bk.posX - pk.posX;
            float toBossY = bk.posY - pk.posY;
            float proj_d = toBossX * cosf(angle) + toBossY * sinf(angle);
            if (proj_d > 0.f && proj_d < bestDist) {
                float perpX = toBossX - proj_d * cosf(angle);
                float perpY = toBossY - proj_d * sinf(angle);
                if (fabsf(perpX) < consts::bossBodyHalfW + 0.2f
                    && fabsf(perpY) < consts::bossBodyHalfH + 0.2f) {
                    bestDist = proj_d;
                    bestType = RHT_Enemy;
                }
            }
        }

        // Check active projectiles
        uint32_t pmask = proj.activeMask;
        while (pmask) {
            int pi = __builtin_ctz(pmask);
            pmask &= pmask - 1;
            float toProjX = proj.posX[pi] - pk.posX;
            float toProjY = proj.posY[pi] - pk.posY;
            float proj_d = toProjX * cosf(angle) + toProjY * sinf(angle);
            if (proj_d > 0.f && proj_d < bestDist) {
                float perpX = toProjX - proj_d * cosf(angle);
                float perpY = toProjY - proj_d * sinf(angle);
                if (fabsf(perpX) < proj.halfW[pi] + 0.2f
                    && fabsf(perpY) < proj.halfH[pi] + 0.2f) {
                    bestDist = proj_d;
                    bestType = RHT_BossProjectile;
                }
            }
        }

        rd.v[r] = bestDist / maxDist; // normalized [0, 1]
        rh.v[r] = bestType;
    }
}

} // namespace silksong
```

- [ ] **Step 2: Add raycastSystem to sim.cpp, wire into task graph after projectiles**

- [ ] **Step 3: Build, benchmark throughput**

Run: `PYTHONPATH=sim/silksong_sim/build uv run python sim/silksong_sim/scripts/benchmark.py --backend CPU --num-worlds 1024 --num-steps 100 --regime raw_sim`
**Gate:** Must hold ≥50M tps at 65k worlds with policy. If raycasts are too expensive, reduce march step count or switch to analytic ray-AABB.

- [ ] **Step 4: Commit**

```bash
git add sim/silksong_sim/src/raycast.hpp sim/silksong_sim/src/sim.cpp
git commit -m "raycasts: 32-ray sensor against arena, boss, and projectiles"
```

---

## Step 4: Full Phases + Advanced Mechanics

### Task 4.1: Implement phase transitions

**Files:**
- Modify: `src/boss.hpp`

- [ ] **Step 1: Add HP threshold checks in attack choice**

In `bossTickIdle`, before picking an attack, check phase transitions:

```cpp
if (!(fsm.flags & BF_Phase2) && fsm.hp <= consts::bossP2HP) {
    fsm.categoryId = BC_PhaseShift;
    fsm.subStateId = 0; // P2 shift
    fsm.frameInState = consts::bossPhaseShiftFrames;
    fsm.flags |= BF_Phase2;
    return;
}
if (!(fsm.flags & BF_Phase4) && fsm.hp <= consts::bossP4HP) {
    fsm.categoryId = BC_PhaseShift;
    fsm.subStateId = 2; // P4 shift
    fsm.frameInState = consts::bossPhaseShiftFrames;
    fsm.flags |= BF_Phase4;
    return;
}
```

- [ ] **Step 2: Implement bossTickPhaseShift**

Boss is invincible during shift, idle time changes to P2 value after P2 shift.

- [ ] **Step 3: Build, commit**

```bash
git commit -m "boss: phase transitions (P2/P3/P4) with HP threshold checks"
```

---

### Task 4.2: Implement AbyssWave and CrossSlash categories

**Files:**
- Modify: `src/boss.hpp`

- [ ] **Step 1: Implement bossTickAbyssWave**

Countdown tracked by `abyssWaveCountdown`, decremented each idle. At ≤1: arena-wide wave attack with 2.1s telegraph.

- [ ] **Step 2: Implement bossTickCrossSlash**

Teleport + 1.2s slash, flip back vel=-14x/20y. Only triggered by `caughtHornet` flag (can be skipped for initial training).

- [ ] **Step 3: Build, commit**

```bash
git commit -m "boss: AbyssWave and CrossSlash categories"
```

---

### Task 4.3: Implement Tendril attack category

**Files:**
- Modify: `src/boss.hpp`

- [ ] **Step 1: Implement bossTickTendril**

50/50 air vs ground variant. Ground: dash (vel=20) → whip (0.6s, hitbox active). Air: antic → whip → end. Tendril Emerge: ground tendrils (1.5s).

- [ ] **Step 2: Build, commit**

```bash
git commit -m "boss: Tendril attack category (ground + air variants)"
```

---

### Task 4.4: Full training validation

**Files:**
- Modify: `src/sim.cpp` (if any remaining task graph tweaks)

- [ ] **Step 1: Run CUDA throughput benchmark**

Run: `PYTHONPATH=sim/silksong_sim/build uv run python sim/silksong_sim/scripts/benchmark.py --backend CUDA --num-worlds 65536 --num-steps 500 --regime policy`
**Gate:** ≥50M tps with full policy.

- [ ] **Step 2: Run full training**

Run: `PYTHONPATH=sim/silksong_sim/build uv run python sim/silksong_sim/scripts/train_ppo.py --num-worlds 4096 --total-steps 1000000`
Expected: Reward trends upward. Agent learns to dodge charges and punish recovery windows. Boss HP decreases over episodes.

- [ ] **Step 3: Run GPU build if not yet tested**

Ensure the sim builds and runs on CUDA:
```bash
cmake --build sim/silksong_sim/build/ -j$(nproc)
sim/silksong_sim/build/headless CUDA 4096 100
```

- [ ] **Step 4: Final commit**

```bash
git commit -m "phase 7: complete Lace boss port — all attack categories, combat, projectiles, raycasts, phase transitions"
```

---

## Notes

- **`__builtin_ctz` on GPU:** Use `__ffs(x) - 1` for CUDA device code instead of `__builtin_ctz`. Madrona's CPU/GPU split means the CPU build uses GCC builtins and the GPU build needs CUDA intrinsics. Wrap in a helper: `static inline int firstSetBit(uint32_t x) { return __builtin_ctz(x); }` and `#ifdef __CUDA_ARCH__` for the GPU variant.
- **Arena bounds:** Current arena is baked for the flat-area calibration room. Lace Tower arena needs different bounds. Update `consts::arenaMinX/MaxX/MinY/MaxY` and re-bake in `bakeLaceTowerArena()` once Lace Tower geometry is resolved. For initial training, the rectangular approximation from FSM teleport bounds works.
- **Boss hitbox sizes:** The values in consts.hpp are estimates. Refine from scene data extraction (AssetRipper) or by recording boss fight traces and measuring collision distances.
- **Stun threshold:** Estimated at 7 hits. Extract the actual value from the "Stun Control" FSM in the scene bundle.
