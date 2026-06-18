# Fidelity Gaps Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all 32 fidelity gaps found by audit agents, bringing the Lace Boss1 sim to ground-truth accuracy.

**Architecture:** All changes are in the sim C++ code (6 files). Tasks are grouped so independent file changes can execute in parallel. The dependency chain is: Task 1 (types/consts) → Tasks 2-5 (parallel: boss.hpp sections, combat.hpp, sim.cpp) → Task 6 (level_gen init + build verify).

**Tech Stack:** C++ (Madrona ECS), cmake/ninja build, Python smoke tests

---

## Task 1: Types & Constants Foundation

**Files:**
- Modify: `sim/silksong_sim/src/types.hpp` (BossFSM struct)
- Modify: `sim/silksong_sim/src/consts.hpp`

All subsequent tasks depend on these new fields/constants existing.

- [ ] **Step 1: Add stun window + hitMax fields to BossFSM**

In `types.hpp`, add after the existing `stunTimer` field:

```cpp
    int16_t  stunGauge;
    int16_t  stunTimer;       // frames remaining in stun
    float    stunWindowTimer; // 1.0s rolling window — resets on hit, decays per tick
    int16_t  totalHitsSinceStun; // absolute hit counter for bossStunHitMax
```

- [ ] **Step 2: Add lava box top constant to consts.hpp**

```cpp
inline constexpr float   bossLavaBoxTop     =   2.41f;  // -0.46 + 5.74/2 (Lava Box trigger top surface)
```

- [ ] **Step 3: Fix damageFreezeFrames to cover WAIT+UP**

Change in `consts.hpp`:
```cpp
inline constexpr int16_t damageFreezeFrames  = 10;       // DAMAGE_FREEZE_WAIT(0.1s) + DAMAGE_FREEZE_UP(0.1s)
```

- [ ] **Step 4: Fix dashDurationFramesGround**

Change in `consts.hpp`:
```cpp
inline constexpr int16_t dashDurationFramesGround = 5;    // DASH_TIME=0.1s (was 6)
```

- [ ] **Step 5: Build to verify struct changes compile**

Run: `cmake --build sim/silksong_sim/build/ -j$(nproc) 2>&1 | grep error`
Expected: Errors about uninitialized new fields in `level_gen.cpp` (fixed in Task 6). No other errors.

---

## Task 2: Boss FSM Fixes — CrossSlash, Will Counter, Idle Reactions

**Files:**
- Modify: `sim/silksong_sim/src/boss.hpp` (functions: `bossCrossSlashCheck`, `bossWillCounter`, `bossTickIdle`, `bossTickDispatch`)

Covers gaps: C1, C2, C3, I1, I12, I13

- [ ] **Step 1: Fix CrossSlash countdown decrement (C1)**

In `bossCrossSlashCheck`, when the CS does NOT fire (the `bossDistanceCheck` path), decrement the countdown:

```cpp
static inline void bossCrossSlashCheck(BossFSM &fsm, BossKinematics &bk,
                                        float heroX, madrona::RNG &rng)
{
    if (fsm.flags & BF_Enraged) {
        fsm.crossSlashCountdown = (int16_t)(fsm.crossSlashCountdown - 1);
        if (fsm.crossSlashCountdown <= 0) {
            // CrossSlash Aim: wall-side check (C3)
            bool rightSide = bk.posX > consts::bossCentreX;
            bool facingRight = (fsm.flags & BF_FacingRight) != 0;
            bool facingWall = (rightSide && facingRight) || (!rightSide && !facingRight);

            float dist = fabsf(bk.posX - heroX);
            if (dist < consts::bossDistThreshold || facingWall) {
                // Too close or facing wall — CS Evade first (I1)
                fsm.evadeAttempts = (int16_t)(fsm.evadeAttempts + 1);
                if (fsm.evadeAttempts > consts::bossCSEvadeMax) {
                    // CS Evade Cancel: force CS facing centre
                    if (bk.posX > consts::bossCentreX)
                        fsm.flags &= ~BF_FacingRight;
                    else
                        fsm.flags |= BF_FacingRight;
                    bossEnterCrossSlash(fsm);
                } else {
                    fsm.flags |= BF_WillCrossSlash;
                    bossEnterEvade(fsm, 0);
                }
            } else {
                bossEnterCrossSlash(fsm);
            }
            return;
        }
    }
    bossDistanceCheck(fsm, bk, heroX, rng);
}
```

- [ ] **Step 2: Fix Will Counter to skip Pose on 33% path (I13)**

```cpp
static inline void bossWillCounter(BossFSM &fsm, madrona::RNG &rng)
{
    if (rng.sampleUniform() < consts::bossCounterChance) {
        fsm.flags |= BF_WillCounter;
        bossEnterIdle(fsm);  // 33%: skip pose, go straight to idle
    } else {
        bossEnterPose(fsm, rng);  // 67%: pose then idle
    }
}
```

- [ ] **Step 3: Add TOOK DAMAGE early exit in Idle (I12)**

In `bossTickIdle`, after the rage check and before the counter reaction, add:

```cpp
    // TOOK DAMAGE: if boss was just hit this frame, exit idle early
    if (fsm.invincTimer == consts::bossInvincFrames) {
        bossCrossSlashCheck(fsm, bk, heroX, rng);
        return;
    }
```

- [ ] **Step 4: Wire bossCheckStun into dispatch (C2)**

In `bossTickDispatch`, after the lava check:

```cpp
    if (bossCheckLava(bk, fsm)) return;
    if (bossCheckStun(fsm)) return;
```

---

## Task 3: Boss FSM Fixes — Attack Mechanics

**Files:**
- Modify: `sim/silksong_sim/src/boss.hpp` (functions: `bossTickComboSlash`, `bossTickJSlash`, `bossTickStun`, `bossTickLava`, `bossTickRapidSlash`, `bossTickEvadeHop`, `bossCheckLava`)

Covers gaps: I2, I3, I4, I5, I6, I7, I8, I9, I14, I15, I16

- [ ] **Step 1: Fix combo decel — only in stop phases (I14)**

```cpp
static inline void bossTickComboSlash(BossKinematics &bk, BossFSM &fsm,
                                       float heroX, madrona::RNG &rng)
{
    fsm.frameInState = (int16_t)(fsm.frameInState - 1);

    // Decel only during stop phases (even sub-states: 0, 2, 4)
    if (fsm.subStateId == 0 || fsm.subStateId == 2 || fsm.subStateId == 4) {
        bk.velX *= consts::bossDecelCombo;
    }
    bossSetHitbox(fsm, consts::bossSlashHalfW, consts::bossSlashHalfH,
                  bossScaleVel(fsm, 1.2f), 0.f, 1);

    if (fsm.frameInState <= 0) {
        if (fsm.subStateId >= 4) {
            fsm.flags |= BF_DoPose;
            bossWillCounter(fsm, rng);
        } else {
            fsm.subStateId = (uint8_t)(fsm.subStateId + 1);
            fsm.frameInState = (int16_t)consts::bossComboStrikeFrames;
            bossFaceHero(fsm, bk.posX, heroX);
            if (fsm.subStateId == 1 || fsm.subStateId == 3) {
                bk.velX = bossScaleVel(fsm, consts::bossComboLungeVel);
            }
        }
    }
}
```

- [ ] **Step 2: Fix J Slash decel — X only, not Y (I3)**

In `bossTickJSlash` case 2, change:
```cpp
    case 2: // J Slash 2-4 — decel in air, gravity active
        bk.velX *= consts::bossDecelDefault;
        // velY handled by gravity in bossIntegrate (not decelerated)
        fsm.flags &= ~BF_HitboxActive;
```

- [ ] **Step 3: Add Dstab Constrain check (I4)**

In `bossTickJSlash`, transition from case 2 → case 3:
```cpp
        if (fsm.frameInState <= 0) {
            // Dstab Constrain? — only apply if X within [86, 102]
            if (bk.posX >= consts::bossDstabXMin && bk.posX <= consts::bossDstabXMax) {
                // Inside constraint range — proceed normally
            }
            fsm.subStateId = 3;
            fsm.frameInState = secToFrames(0.2f);
        }
```

- [ ] **Step 4: Fix wallcling velocity (I5)**

In `bossTickJSlash` case 5, apply velocity into wall:
```cpp
    case 5: // Wallcling — gravity=0, pressing into wall
        fsm.flags &= ~BF_HitboxActive;
        // Press into wall (wall clamp in integrate prevents movement)
        bk.velX = bossScaleVel(fsm, consts::bossWallclingVel);
        bk.velY = 0.f;
        // Manual position update since BF_Kinematic
        bk.posX += bk.velX * consts::deltaT;
        if (bk.posX < consts::bossConstraintXMin) bk.posX = consts::bossConstraintXMin;
        if (bk.posX > consts::bossConstraintXMax) bk.posX = consts::bossConstraintXMax;
        if (fsm.frameInState <= 0) {
```

- [ ] **Step 5: Fix stun knockback — one-time impulse (I8)**

Move velocity setting out of the per-tick loop. The impulse is already set when entering BC_Stun from `combat.hpp` or `bossCheckStun`. In `bossTickStun` case 0, just count down:

```cpp
    case 0: // Stun Start — knockback arc (impulse set on entry)
        fsm.flags &= ~BF_HitboxActive;
        if (fsm.frameInState <= 0) {
            fsm.subStateId = 1;
            fsm.frameInState = secToFrames(1.5f);
        }
        break;
```

And set the impulse in `bossCheckStun`:
```cpp
static inline bool bossCheckStun(BossFSM &fsm, BossKinematics &bk)
{
    if (fsm.categoryId == BC_Stun) return false;
    if (fsm.stunGauge >= consts::bossStunCombo) {
        fsm.categoryId = BC_Stun;
        fsm.subStateId = 0;
        fsm.frameInState = secToFrames(0.2f);
        fsm.stunGauge = 0;
        bk.velX = bossScaleVel(fsm, consts::bossStunKnockVelX);
        bk.velY = consts::bossStunKnockVelY;
        return true;
    }
    return false;
}
```

Update dispatch call to pass bk: `if (bossCheckStun(fsm, bk)) return;`

- [ ] **Step 6: Fix lava hop — impulse on entry (I9)**

In `bossTickLava`, set velocity on transition from case 0→1, not every tick:

```cpp
        if (fsm.frameInState <= 0) {
            bk.velY = consts::bossLavaHopVelY;  // impulse: set ONCE
            fsm.subStateId = 1;
            fsm.frameInState = secToFrames(consts::bossLavaHopTime);
        }
        break;
    case 1: // Lava Hop — decel only
        bk.velX = 0.f;
        bk.velY *= 0.85f;  // decel per tick
```

- [ ] **Step 7: Fix lava teleport hero-proximity offset (I15)**

In `bossTickLava` case 2→3 transition, after setting posX to centreX:

```cpp
            bk.posX = consts::bossCentreX;
            bk.posY = consts::bossLandY + consts::bossBodyHalfH;
            // Hero proximity offset: if within 3 units, offset 8 units away
            if (fabsf(bk.posX - heroX) < 3.0f) {
                float facing = (fsm.flags & BF_FacingRight) ? 1.f : -1.f;
                bk.posX += facing * 8.0f;
                bk.posX = fminf(fmaxf(bk.posX, consts::bossConstraintXMin), consts::bossConstraintXMax);
            }
```

Note: `bossTickLava` currently doesn't take `heroX`. Add it as a parameter and update the dispatch call.

- [ ] **Step 8: Fix lava trigger threshold (I16)**

In `bossCheckLava`:
```cpp
static inline bool bossCheckLava(BossKinematics &bk, BossFSM &fsm)
{
    if (fsm.categoryId == BC_Lava) return false;
    // Boss feet enter lava box when posY - halfH < lavaBoxTop
    if (bk.posY - consts::bossBodyHalfH < consts::bossLavaBoxTop) {
        bossEnterLava(fsm);
        return true;
    }
    return false;
}
```

- [ ] **Step 9: Fix RapidSlash multihit i-frame check (I6) and loop MULTI HIT (I7)**

In `bossTickRapidSlash` sub-state 0, check hero i-frames before multihit. This function needs `pk` passed in (add parameter). Also add proximity check in sub-state 1:

```cpp
    case 0: // RapidSlash Charge
        bk.velX = bossScaleVel(fsm, consts::bossRapidGroundVel);
        fsm.flags &= ~BF_HitboxActive;
        if (fabsf(bk.posX - heroX) < 2.0f) {
            if (heroIFrameRem > 0) {
                // Hero invincible — cancel multihit, go to loop
                fsm.subStateId = 1;
                fsm.frameInState = secToFrames(consts::bossRapidLoopTime);
                bk.velX = 0.f;
            } else {
                fsm.subStateId = 2;
                fsm.frameInState = secToFrames(consts::bossMultihitTime);
                bk.velX = 0.f;
            }
        }
        if (fsm.frameInState <= 0) {
            fsm.subStateId = 1;
            fsm.frameInState = secToFrames(consts::bossRapidLoopTime);
        }
        break;
    case 1: // RapidSlash Loop — add MULTI HIT CONNECT check (I7)
        bk.velX *= consts::bossDecelHop;
        bossSetHitbox(fsm, consts::bossSlashHalfW, consts::bossSlashHalfH,
                      bossScaleVel(fsm, 1.0f), 0.f, 1);
        if (fabsf(bk.posX - heroX) < 2.0f && heroIFrameRem <= 0) {
            fsm.subStateId = 2;
            fsm.frameInState = secToFrames(consts::bossMultihitTime);
            bk.velX = 0.f;
        }
        if (fsm.frameInState <= 0) {
            fsm.flags &= ~BF_HitboxActive;
            fsm.flags &= ~BF_DoPose;
            bossEnterPose(fsm, rng);
        }
        break;
```

Note: `bossTickRapidSlash` needs hero i-frame info. Pass `pk.iFrameRem` via parameter or read from hero obs.

- [ ] **Step 10: Fix post-evade attack selection to simple random (I2)**

In `bossTickEvadeHop` sub-state 2, replace `sendRandomEventV3` with simple weighted random:

```cpp
            } else {
                // Post-evade: simple equal-weight random (SendRandomEvent, not V3)
                float roll = rng.sampleUniform() * 3.f;
                bossFaceHero(fsm, bk.posX, heroX);
                if (roll < 1.f) {
                    bossEnterHopChain(fsm, BC_ComboSlash, consts::bossHopTargetCombo);
                } else if (roll < 2.f) {
                    bossEnterCharge(fsm, bk);
                } else {
                    bossEnterJSlash(fsm);
                }
            }
```

---

## Task 4: Combat System Fixes

**Files:**
- Modify: `sim/silksong_sim/src/combat.hpp`
- Modify: `sim/silksong_sim/src/sim.cpp` (combatSystem, hero recoil block, boss freeze block)

Covers gaps: C4, C5, C6, I17, I18, I19, L7

- [ ] **Step 1: Fix stun combo window + hitMax in combat.hpp (C4, C5)**

Replace the stun logic in `heroHitsBoss`:

```cpp
    // --- Stun gauge with 1.0s rolling window (C4) ---
    fsm.stunGauge = (int16_t)(fsm.stunGauge + 1);
    fsm.stunWindowTimer = 1.0f;  // reset window on each hit
    fsm.totalHitsSinceStun = (int16_t)(fsm.totalHitsSinceStun + 1);

    if (fsm.categoryId == BC_Stun && fsm.subStateId == 3) {
        fsm.stunTimer = (int16_t)(fsm.stunTimer -
            (int16_t)(consts::bossStunHitReduce / consts::deltaT));
    }
    // Note: stun transition itself is handled by bossCheckStun in boss.hpp dispatch
    // The hitMax check also happens there
```

Remove the stun transition from `heroHitsBoss` (C2/L6 — consolidate to `bossCheckStun` only).

- [ ] **Step 2: Add stun window decay to combatSystem in sim.cpp**

In `combatSystem`, after the invincTimer tick:

```cpp
    if (fsm.invincTimer > 0) fsm.invincTimer = (int16_t)(fsm.invincTimer - 1);

    // Stun combo window decay (C4)
    if (fsm.stunWindowTimer > 0.f) {
        fsm.stunWindowTimer -= consts::deltaT;
        if (fsm.stunWindowTimer <= 0.f) {
            fsm.stunGauge = 0;  // window expired, reset combo counter
            fsm.stunWindowTimer = 0.f;
        }
    }
```

- [ ] **Step 3: Fix invincTimer to tick unconditionally (C6)**

In `combatSystem`, change:
```cpp
    if (fsm.invincTimer > 0) fsm.invincTimer = (int16_t)(fsm.invincTimer - 1);
```
Remove the `hitFreezeRem <= 0` gate that was added previously (it should already be removed based on C6).

- [ ] **Step 4: Add hitMax check to bossCheckStun in boss.hpp**

Update `bossCheckStun` to also check `totalHitsSinceStun`:

```cpp
static inline bool bossCheckStun(BossFSM &fsm, BossKinematics &bk)
{
    if (fsm.categoryId == BC_Stun) return false;
    if (fsm.stunGauge >= consts::bossStunCombo
        || fsm.totalHitsSinceStun >= consts::bossStunHitMax) {
        fsm.categoryId = BC_Stun;
        fsm.subStateId = 0;
        fsm.frameInState = secToFrames(0.2f);
        fsm.stunGauge = 0;
        fsm.totalHitsSinceStun = 0;
        bk.velX = bossScaleVel(fsm, consts::bossStunKnockVelX);
        bk.velY = consts::bossStunKnockVelY;
        return true;
    }
    return false;
}
```

- [ ] **Step 5: Fix hero damage recoil Y-component (I17)**

In `combat.hpp` `bossHitsHero`, set Y recoil:
```cpp
    pk.recoilRem = consts::heroRecoilFrames;
    pk.recoilVelX = recoilDir * consts::heroRecoilSpeed;
    pk.recoilVelY = consts::heroRecoilSpeed * 0.5f;  // upward launch
```

In `sim.cpp` hero recoil block, apply Y and suppress gravity:
```cpp
    if (p.recoilRem > 0) {
        const Arena &arena = ctx.singleton<Arena>();
        p.velX = p.recoilVelX;
        p.velY = (p.recoilRem == consts::heroRecoilFrames) ? p.recoilVelY : p.velY;
        // Gravity disabled during recoil
        sweepAxisX(arena, p, p.velX * consts::deltaT,
                   consts::heroHalfWidth, consts::heroHalfHeight);
        bool dummy = false;
        sweepAxisY(arena, p, p.velY * consts::deltaT,
                   consts::heroHalfWidth, consts::heroHalfHeight, dummy);
        p.recoilRem = (int16_t)(p.recoilRem - 1);
        p.iFrameRem = p.iFrameRem > 0 ? (int16_t)(p.iFrameRem - 1) : (int16_t)0;
        obs.posX = p.posX; obs.posY = p.posY;
        obs.velX = p.velX; obs.velY = p.velY;
        obs.invincible = (p.iFrameRem > 0) ? 1.f : 0.f;
        return;
    }
```

Note: requires `recoilVelY` field in `PlayerKinematics` (already added as `recoilVelX` — just needs the Y companion, or use a single launch approach).

- [ ] **Step 6: Fix jump release cut (I19)**

In `sim.cpp`, change the jump release block:
```cpp
    if (jumpRelease && p.velY > 0.f && p.dashTimerRem == 0) {
        p.velY *= consts::jumpReleaseCut;  // 0.5x, not hard zero
        p.jumpHoldRem = 0;
    }
```

- [ ] **Step 7: Fix stun reward timing (L7)**

In `combatSystem`, move `bossStunned` check after the hit:
```cpp
    const bool hit  = heroHitsBoss(pk, bk, fsm);
    const bool hurt = bossHitsHero(bk, fsm, pk, obs);
    const bool bossStunned = (fsm.categoryId == BC_Stun);  // check AFTER hit

    if (hit)  r += bossStunned ? 2.f : 1.f;
    if (hurt) r -= bossStunned ? 2.f : 1.f;
```

---

## Task 5: Low-Priority Fixes

**Files:**
- Modify: `sim/silksong_sim/src/boss.hpp` (Pose, CS Evade vel, kickoff)
- Modify: `sim/silksong_sim/src/consts.hpp` (if needed)

Covers gaps: L1 (done in Task 1), L2, L3, L4

- [ ] **Step 1: Fix kickoff facing timing (L2)**

Already handled by the wallcling rewrite in Task 3.

- [ ] **Step 2: Use bossCSEvadeVel for CrossSlash evade (L4)**

In `bossCrossSlashCheck`, when entering CS evade, use the dedicated velocity:

```cpp
                    fsm.flags |= BF_WillCrossSlash;
                    // Use CS-specific evade velocity (-45 instead of -30)
                    fsm.categoryId = BC_EvadeHop;
                    fsm.subStateId = 0;
                    fsm.frameInState = secToFrames(0.3f);
                    fsm.flags &= ~BF_HitboxActive;
```

Then in `bossTickEvadeHop` case 0, check if this is a CS evade and use the appropriate velocity:
```cpp
    case 0: // Evade backward
        if (fsm.flags & BF_WillCrossSlash)
            bk.velX = bossScaleVel(fsm, consts::bossCSEvadeVel);  // -45
        else
            bk.velX = bossScaleVel(fsm, consts::bossEvadeVel);    // -30
```

---

## Task 6: Level Gen Init + Build + Smoke Test

**Files:**
- Modify: `sim/silksong_sim/src/level_gen.cpp` (initialize new BossFSM fields)

- [ ] **Step 1: Initialize new BossFSM fields**

Add to the BossFSM initializer in `resetEpisodeState`:
```cpp
            .stunWindowTimer = 0.f,
            .totalHitsSinceStun = 0,
```

- [ ] **Step 2: Build**

Run: `cmake --build sim/silksong_sim/build/ -j$(nproc) 2>&1 | grep error`
Expected: Zero errors.

- [ ] **Step 3: Headless smoke test**

Run: `./sim/silksong_sim/build/headless CPU 8 5000 --rand-actions`
Expected: Non-zero FPS, no crash.

- [ ] **Step 4: Python combat timing verification**

```bash
PYTHONPATH=sim/silksong_sim/build uv run python -c "
import silksong_sim, torch
mgr = silksong_sim.SimManager(exec_mode=silksong_sim.madrona.ExecMode.CPU, gpu_id=0, num_worlds=1, rand_seed=99, auto_reset=True)
act = mgr.action_tensor().to_torch()

# Walk to boss, spam attack, verify timing
for step in range(80):
    act[:] = 0; act[0,0,1] = 1
    mgr.step()

prev_hp = 250.0
hits = []
for step in range(500):
    act[:] = 0
    bx = mgr.boss_obs_tensor().to_torch()[0,0,0].item()
    hx = mgr.player_obs_tensor().to_torch()[0,0,0].item()
    if hx < bx - 1.5: act[0,0,1] = 1
    elif hx > bx + 1.5: act[0,0,0] = 1
    if step % 2 == 0: act[0,0,5] = 1
    mgr.step()
    bhp = mgr.boss_obs_tensor().to_torch()[0,0,4].item()
    if bhp < prev_hp:
        hits.append(step)
    prev_hp = bhp

if len(hits) > 1:
    gaps = [hits[i]-hits[i-1] for i in range(1, len(hits))]
    print(f'Avg gap: {sum(gaps)/len(gaps):.1f}f = {sum(gaps)/len(gaps)*0.02:.2f}s')
    print(f'Min gap: {min(gaps)}f = {min(gaps)*0.02:.2f}s')
    print(f'Expected min ~13f = 0.26s (invincFrames only, freeze is visual)')
"
```

- [ ] **Step 5: Commit**

```bash
git add sim/silksong_sim/src/
git commit -m "fix: close all 32 fidelity gaps from audit

- Stun: 1.0s combo window, hitMax=10 failsafe, global transition wired
- CrossSlash: countdown decrement, wall-side check, evade retry loop
- Combat: invincTimer ticks during freeze, jump release 0.5x cut
- Hero: damage recoil Y-component (velY=7.5), freeze extended to 10f
- Boss: combo decel stop-phase only, JSlash Y decel removed, lava
  hop/tele/trigger fixed, stun knockback impulse, wallcling velocity
- Will Counter 33% skips pose, took-damage exits idle early
- RapidSlash multihit respects i-frames, loop MULTI HIT path added
- Post-evade uses simple random, CS evade uses -45 velocity
- dashDurationFramesGround 6→5"
```

---

## Parallelization Map

```
Task 1 (types + consts) ──┬──> Task 2 (boss: CrossSlash/Idle/WillCounter)
                           ├──> Task 3 (boss: attack mechanics)
                           ├──> Task 4 (combat + sim.cpp)
                           └──> Task 5 (low-priority boss)
                                        │
                           All ────────> Task 6 (level_gen init + build + verify)
```

Tasks 2, 3, 4, 5 can run in parallel after Task 1 completes (they touch different functions within the same files, but boss.hpp edits are in non-overlapping function bodies). Task 6 must run last.
