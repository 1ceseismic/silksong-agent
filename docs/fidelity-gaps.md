# Sim Fidelity Gaps — Full Audit (2026-04-30)

Source: 3 parallel audit agents compared sim code against extracted ground truth
(lace_boss1_fsm_summary.md, hero_constants_dump.md, arena_summary.md, handoff doc).

## CRITICAL (6)

### C1: CrossSlash countdown never decrements
- **Ground truth:** `$Ct CrossSlash` decrements each attack cycle while enraged; CS fires when it reaches 0 (2-4 attacks between each CS)
- **Sim:** `crossSlashCountdown` initialized to 3, never decremented. CS never fires after rage.
- **Files:** `boss.hpp` `bossCrossSlashCheck`, `bossTickIdle`
- **Fix:** In `bossCrossSlashCheck`, when the `bossDistanceCheck` path is taken (CS did not fire), decrement `crossSlashCountdown` by 1.

### C2: `bossCheckStun` defined but never called from dispatch
- **Ground truth:** STUN is a global transition from ANY state when stun gauge is met
- **Sim:** `bossCheckStun` at line ~979 exists but `bossTickDispatch` only calls `bossCheckLava`, not `bossCheckStun`. combat.hpp has a separate stun trigger inside `heroHitsBoss` that does work for the combo-8 path.
- **Files:** `boss.hpp` `bossTickDispatch`
- **Fix:** Add `if (bossCheckStun(fsm)) return;` call in `bossTickDispatch` after the lava check. Remove the duplicate stun trigger from `combat.hpp` (or keep combat.hpp as the sole trigger and delete `bossCheckStun`).

### C3: CrossSlash Aim wall-side check missing
- **Ground truth:** Before CS, checks if Lace faces a wall (`$Right Side = self X > Centre X`, `$Facing Right = X scale > 0`). If facing wall, evade first.
- **Sim:** Only checks `dist < 6.0`, never checks facing/wall-side
- **Files:** `boss.hpp` `bossCrossSlashCheck`
- **Fix:** Add wall-side check: if `(bossX > bossCentreX && facingRight) || (bossX < bossCentreX && !facingRight)` → evade first.

### C4: Stun combo 1-second TIME WINDOW missing
- **Ground truth:** `Combo Time: 1.0` — 8 hits must land within a 1.0s rolling window. Counter resets if window expires.
- **Sim:** `stunGauge` is a simple increment counter that never resets/decays. 8 hits over ANY timespan triggers stun.
- **Files:** `combat.hpp`, `types.hpp` (BossFSM needs `stunWindowTimer`)
- **Fix:** Add `stunWindowTimer` float to BossFSM. On each hit, reset to 1.0s. Each tick, decrement by deltaT. When it reaches 0, reset `stunGauge` to 0.

### C5: `bossStunHitMax=10` absolute cap never checked
- **Ground truth:** `Stun Hit Max: 10` — forced stun after 10 total hits since last stun regardless of timing
- **Sim:** `consts::bossStunHitMax` defined but never referenced anywhere
- **Files:** `combat.hpp`, `types.hpp` (BossFSM needs `totalHitsSinceStun`)
- **Fix:** Track separate `totalHitsSinceStun` counter. Increment on any hit, reset on stun. Force stun when it reaches `bossStunHitMax`.

### C6: `invincTimer` paused during hit-freeze (wrong — should tick)
- **Ground truth:** Damage freeze is a visual/physics pause (TimeScale=0 effect on movement), but invulnerability countdown continues independently
- **Sim:** `invincTimer` only ticks when `hitFreezeRem <= 0`, making effective invuln 0.36s (13+5) instead of 0.25s (13)
- **Files:** `sim.cpp` combatSystem
- **Fix:** Remove the `hitFreezeRem <= 0` gate on `invincTimer` decrement. Tick unconditionally.

## IMPORTANT (19)

### I1: CS Evade retry loop + CS Evade Cancel missing
- **Ground truth:** Up to 2 evade attempts before CS. On 3rd attempt, `CS Evade Cancel` forces CS facing centre.
- **Sim:** `evadeAttempts` field exists but is never incremented. No CS Evade Cancel path.
- **Files:** `boss.hpp` `bossCrossSlashCheck`, `bossTickEvadeHop` sub-state 2
- **Fix:** Increment `evadeAttempts` each time CS evade fires. When `evadeAttempts >= 2`, skip evade and force `bossEnterCrossSlash` with boss facing centre.

### I2: Post-evade attack uses V3 (with counters) instead of simple random
- **Ground truth:** Post-evade uses `SendRandomEvent` (simple weighted random, no eventMax/missedMax)
- **Sim:** Uses `sendRandomEventV3` with `eventMax=2, missedMax=4`
- **Files:** `boss.hpp` `bossTickEvadeHop` sub-state 2
- **Fix:** Replace with simple `rng.sampleUniform() * 3` pick (equal weight, no tracking).

### I3: J Slash 2/3/4 collapsed + Y decel wrong
- **Ground truth:** 3 separate states each with decel 0.825 on X only; gravity handles Y
- **Sim:** Single substate with decel applied to both X and Y
- **Files:** `boss.hpp` `bossTickJSlash` case 2
- **Fix:** Only apply decel to velX. Let gravity handle velY naturally.

### I4: Dstab Constrain? check not implemented
- **Ground truth:** Check X in [86, 102] before downstab; skip constraints if outside range
- **Sim:** `bossDstabXMin`/`bossDstabXMax` defined in consts.hpp but never referenced
- **Files:** `boss.hpp` `bossTickJSlash` transition from case 2 to case 3
- **Fix:** Add X range check before entering downstab antic.

### I5: Wallcling velocity never applied
- **Ground truth:** Wallcling sets `speed=30 into wall`
- **Sim:** `bossWallclingVel=30` defined but dead code; boss hangs with vel=0
- **Files:** `boss.hpp` `bossTickJSlash` case 5
- **Fix:** Apply `bk.velX = bossScaleVel(fsm, bossWallclingVel)` toward wall during wallcling.

### I6: Multihit ignores hero i-frames / Bind Bell cancel
- **Ground truth:** `Collide To Multihit` checks `CanHeroTakeDamage` and Bind Bell. If hero invincible → `Collide Cancel` → resume RapidSlash Loop.
- **Sim:** Grabs hero regardless of i-frame state
- **Files:** `boss.hpp` `bossTickRapidSlash` sub-state 0→2 transition
- **Fix:** Check `pk.iFrameRem > 0` before transitioning to multihit; if invincible, go to RapidSlash Loop instead.

### I7: RapidSlash Loop MULTI HIT CONNECT missing
- **Ground truth:** RapidSlash Loop can trigger multihit via separate `MULTI HIT CONNECT` event
- **Sim:** Only triggers multihit from charge rush proximity
- **Files:** `boss.hpp` `bossTickRapidSlash` sub-state 1
- **Fix:** Add proximity check in sub-state 1 similar to sub-state 0.

### I8: Stun knockback reapplied every frame
- **Ground truth:** Stun Start applies knockback `-6x, 23y` as one-time impulse
- **Sim:** velX/velY set every tick for 10 frames
- **Files:** `boss.hpp` `bossTickStun` case 0
- **Fix:** Move velocity assignment to the entry transition; in the tick just count down frames.

### I9: Lava Hop velocity overwritten every frame
- **Ground truth:** Set vel=80 once on entry, then 0.85 decel per frame
- **Sim:** Sets `bk.velY = 80` then `*= 0.85` every tick → constant 68
- **Files:** `boss.hpp` `bossTickLava` case 1
- **Fix:** Set `bk.velY = 80` only on transition from case 0→1. In case 1, only apply `bk.velY *= 0.85`.

### I10: Range Out / Evade 2 chain absent
- **Ground truth:** Full defensive evasion chain: Evade 2 → Evade Recover 2 → Keep Evading? → Range Out (invincible 4-8s, reacts to RANGE IN/BLOCKED HIT)
- **Sim:** Not implemented at all. Boss has no long-range disengage behavior.
- **Files:** `boss.hpp` `bossTickIdle`
- **Fix:** Add alert range check in Idle. When hero exceeds range, enter Evade 2 chain.

### I11: Sing interrupt unreachable
- **Ground truth:** SING event from Idle, Distance Check, or Stunned → Sing Antic
- **Sim:** `BC_Sing` category handled by `bossTickSing` but no path enters it
- **Files:** `boss.hpp` `bossTickIdle`, `bossTickStun`
- **Fix:** Add hero-performing detection in Idle and Stunned. (Low priority for RL since hero doesn't sing in training.)

### I12: TOOK DAMAGE in Idle doesn't trigger early attack
- **Ground truth:** Boss hit during idle → CrossSlash? → Distance Check (exits idle early)
- **Sim:** Boss waits out full idle timer even when hit
- **Files:** `boss.hpp` `bossTickIdle`
- **Fix:** Check if boss was hit this frame (e.g., `invincTimer == bossInvincFrames` means just-hit). If so, exit idle early into `bossCrossSlashCheck`.

### I13: Will Counter 33% path always goes to Pose
- **Ground truth:** 33% chance: skip Pose entirely, go directly to Idle (with `$Will Counter = true`)
- **Sim:** Both 33% and 67% paths call `bossEnterPose`
- **Files:** `boss.hpp` `bossWillCounter`
- **Fix:** 33% path: set `BF_WillCounter`, call `bossEnterIdle` directly. 67% path: `bossEnterPose`.

### I14: Combo decel applied during lunge substates
- **Ground truth:** Decel 0.8 only during stop phases (ComboSlash 3, 5)
- **Sim:** `bk.velX *= bossDecelCombo` applied unconditionally every frame including during lunges
- **Files:** `boss.hpp` `bossTickComboSlash`
- **Fix:** Only apply decel when subStateId is 2 or 4 (stop phases after lunges).

### I15: Lava teleport missing hero-proximity offset
- **Ground truth:** After teleporting to Centre X, if distance to hero < 3.0, offset by `X Scale * 8.0`
- **Sim:** Teleports directly to `bossCentreX` with no proximity check
- **Files:** `boss.hpp` `bossTickLava` case 2→3 transition
- **Fix:** After setting posX to centreX, check distance to hero. If < 3.0, offset ±8.0 based on facing.

### I16: Lava trigger Y threshold wrong
- **Ground truth:** Lava Box top surface at Y=2.41 (centre=-0.46, height=5.74). Boss triggers when feet enter box.
- **Sim:** Triggers at `posY < -0.5 + 1.28 + 1.0 = 1.78` instead of `posY < 3.69`
- **Files:** `boss.hpp` `bossCheckLava`, `consts.hpp`
- **Fix:** Change threshold to `bossLavaBoxTop + bossBodyHalfH` where `bossLavaBoxTop = -0.46 + 5.74/2 = 2.41`. Trigger when `posY - bossBodyHalfH < 2.41` → `posY < 3.69`.

### I17: Hero damage recoil missing Y-component
- **Ground truth:** `Recoil vector = (+/-RECOIL_VELOCITY, RECOIL_VELOCITY * 0.5)` = (15.0, 7.5), gravity disabled during recoil
- **Sim:** Only horizontal knockback; `velY = 0` forced every tick during recoil
- **Files:** `combat.hpp` `bossHitsHero`, `sim.cpp` hero recoil block
- **Fix:** Add `recoilVelY` field. Set to `heroRecoilSpeed * 0.5 = 7.5`. Apply in recoil block. Suppress gravity during recoil frames.

### I18: DAMAGE_FREEZE_UP phase missing
- **Ground truth:** `DAMAGE_FREEZE_WAIT=0.1s` + `DAMAGE_FREEZE_UP=0.1s` (slow-ramp back to full speed). Total ~10 frames.
- **Sim:** Only 5 frames (WAIT). UP phase absent.
- **Files:** `consts.hpp`, `sim.cpp` hero/boss freeze blocks
- **Fix:** Extend `damageFreezeFrames` to 10, or add a second `hitFreezeUpRem` counter for the ramp phase.

### I19: Jump release uses hard-zero instead of 0.5x
- **Ground truth:** `jumpReleaseCut = 0.5` → `velY *= 0.5`
- **Sim:** `velY = 0.f` — constant defined but unused
- **Files:** `sim.cpp` line ~558, `consts.hpp` `jumpReleaseCut`
- **Fix:** Change `p.velY = 0.f` to `p.velY *= consts::jumpReleaseCut`.

## LOW (7)

### L1: Ground dash 1 frame too long
- DASH_TIME=0.1s=5 frames, sim has `dashDurationFramesGround=6`
- **Fix:** Change to 5.

### L2: Kickoff facing logic minor timing
- Re-face happens at top of wallcling state, may be stale by kickoff time
- **Fix:** Move `bossFaceHero` to kickoff transition point.

### L3: Pose Swish alert-range early-exit missing
- Pose Swish checks alert range; can cancel to Pose Lean if hero in range
- **Fix:** Add alert range check during Pose sub-state 0.

### L4: `bossCSEvadeVel=-45` defined but dead code
- CS Evade should use -45 velocity, not the regular -30 evade velocity
- **Fix:** Use `bossCSEvadeVel` when evading for CrossSlash.

### L5: All boss attacks use 2 generic AABB sizes
- Ground truth has per-attack polygon colliders (Combo Slash 1, Charge Hit, etc.)
- **Fix:** Extract AABB approximations from each polygon collider and use per-attack sizes.

### L6: `bossCheckStun` is dead code alongside combat.hpp stun
- Maintenance hazard — two stun paths, one dead
- **Fix:** Consolidate into one stun trigger path.

### L7: Stun-causing hit reward captured pre-stun
- `bossStunned` checked before `heroHitsBoss` — the stun-triggering hit gets +1 not +2
- **Fix:** Evaluate `bossStunned` after the hit, or accept as-is (minor).
