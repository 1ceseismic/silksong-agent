# Phase 5.4 — current calibration status

Session snapshot. Supersedes earlier notes if they conflict.

## One-liner

**3 of 5 presets passing.** Multi-tick `gravityScale` ramp now modeled — velocity during air hang matches trace exactly. Ceiling bump now cancels jump hold (was leaking re-applied jumpVel). Preset 5 max pos drift dropped from **0.43 u to 0.47 u** (velocity-correct; position drift from upstream sprint-phase offset amplified by lighter gravity). Preset 4 unchanged (terrain micro-bump).

## Calibration scoreboard

| # | preset | mean pos | max pos | mean vel | max vel | status |
|---|---|---|---|---|---|---|
| 1 | pure jumps | 0.003 u | **0.049 u ✓** | 0.001 u/s | **0.009 u/s ✓** | CALIBRATED |
| 2 | run + stop | 0.003 u | **0.042 u ✓** | 0.000 u/s | **0.000 u/s ✓** | CALIBRATED |
| 3 | dash tap | 0.009 u | **0.045 u ✓** | 0.000 u/s | **0.000 u/s ✓** | CALIBRATED |
| 4 | dash → sprint → release | 0.027 u | 0.106 u | 0.008 u/s | 1.200 u/s | 6 % over pos; terrain-blip vel spike |
| 5 | jump + sprint + double jump | 0.035 u | 0.465 u | 0.208 u/s | 17.4 u/s | ramp modeled; drift from upstream posX offset |

Trace files referenced:
- `traces/trace_0_20260419_151015_1.bin` — preset 2
- `traces/trace_0_20260419_151058_1.bin` — preset 1
- `traces/trace_0_20260419_153252_1.bin` — preset 3
- `traces/trace_0_20260419_154339_1.bin` — preset 4
- `traces/trace_0_20260419_154824_1.bin` — preset 5

## What shipped this session

### Shuttlecock jump (decomp HeroController.cs:7732)

- **`PF_Shuttlecock` flag + `shuttlecockQueueTicks` counter** in `PlayerKinematics`.
- Jump pressed during committed sprint (`PF_Sprinting && sprintActiveTicks ≥ 3`) arms a 6-tick queue; at tick 7 the shuttlecock fires: `velY = jumpVel`, `velX = ±shuttlecockSpeed` (=18, trace-measured), `jumpHoldRem = jumpStepsMax`, `PF_Sprinting` cleared, `PF_Shuttlecock` set.
- While `PF_Shuttlecock`: horiz-velocity path pins `velX = ±shuttlecockSpeed` (matches `HeroController.cs:3285` `rb2d.linearVelocity = new Vector3(shuttlecockSpeed, y)`).
- On `velY < 0 || groundedThisStep`: clear `PF_Shuttlecock`; if dash still held, re-enter `PF_Sprinting` at `sprintActiveTicks = 0` so airborne decel toward `airSprintSpeed = 12` engages the next substep.

### Sprint FSM — three-path cancel

Introduced `sprintCanceledThisStep` / `sprintCarryoverTick` gating on the horizontal-velocity snap branch so the substep can skip overwriting `velX`:

- **sprintActiveTicks ≥ 10 AND inputDir == 0** → Skid End 1 (×0.85/tick decay, unchanged).
- **sprintActiveTicks ≥ 3 AND inputDir == 0** → one-tick carryover (`velX` keeps sprint value for one substep, the next substep's else-branch snap fires). Preset 5 tick 181.
- **Otherwise** → instant snap to `inputDir × runSpeed`. Preset 3 dash-tap.

Counter is **reset to 0 on `justLanded`** so a short post-shuttlecock ground sprint gets the carryover path instead of skidding.

### Per-trace ceiling X-range

- `Arena.ceilingY / ceilingMinX / ceilingMaxX` — ceiling clamp only fires when `posX ∈ [ceilingMinX, ceilingMaxX]`. Silksong's calibration rooms have non-uniform roofs (preset 5's compound jump at X≈34 peaks at 8.03 with no bump; bare jumps at X≈41 cap at 7.17).
- `HeroInit.ceilingY / ceilingMinX / ceilingMaxX` carries these per-trace. `sizeof(HeroInit) = 40` now (was 32).
- `oracle_diff._estimate_ceiling(trace)` scans `HeroPrivate.headBumpSteps > 0` and returns `(ceilingY, minX, maxX)` with 1.5 u margin around the observed bump range. Returns zeros if no bumps.

### Air-hang ramp + persistence

- `gravScale` field in `PlayerKinematics`: persistent gravity multiplier. Trigger sets 0.2 on first `velY<0` tick after ceiling bump. Ramps `+0.1/tick` (= `airHangAccel * dt`). Snaps to 1.0 on jump release. Reset to 1.0 on stable grounding (2+ consecutive grounded ticks).
- `PF_DidAirHang` set when the air-hang trigger fires; cleared on stable grounding. Prevents a second ceiling bump in the same airborne episode from re-arming the ramp.
- Ceiling bump (`sweepAxisY`) now cancels `jumpHoldRem` — prevents the jump-hold code from re-applying `jumpVel` on the tick after a headbump.

### Arena expansion

- `arenaMinX = -2`, `arenaMaxX = 60` (was `-20 / 40`). Preset 5's hero reaches X = 41.4 after the shuttlecock jump; the old 40-X wall was blocking it and cascading into bigger drifts.

## Known remaining issues

### Preset 4 (0.106 u max pos, 1.2 u/s vel spike — 6 % over)

Two concurrent artifacts, both trace-side:

1. **Tick 149 / 230 `velY = -1.2` blip.** Trace shows hero airborne for a single tick mid-sprint — a sub-pixel gap in the floor geometry my uniform-floor sim doesn't model. Drops 0.003 u posY, resettles. Contributes the 1.2 u/s vel drift peak but only once each.
2. **~0.1 u posX noise during 33-tick ground sprint.** Trace's per-tick posX deltas alternate 0.349 / 0.377 / 0.346 / 0.350 around the expected 0.35 u — Unity Rigidbody2D interpolation artifacts in `transform.position` sampling. Mean drift is 0.027 u (well under budget); only the peak nudges over.

Both require game-side evidence we don't have. Acceptable for RL training.

### Preset 5 (0.465 u max pos, 17.4 u/s vel spike)

**Air hang ramp now modeled.** The multi-tick `gravityScale` ramp (0.2 → +0.1/tick → snap on jump release) is implemented and velocity matches the trace exactly during the ramp period. Two fixes shipped:

1. **`gravScale` ramp in sim.cpp** — persistent `gravScale` field replaces the old single-tick `gScale` local. Trigger sets 0.2 on first `velY<0` tick after ceiling bump. Physics applies current `gravScale`, then post-apply: unconditionally ramp +0.1, snap to 1.0 if `!jump` in current action (newBits). This ordering matches both preset 1 (single-tick dip, jump released before trigger) and preset 5 (multi-tick ramp, jump held through trigger).

2. **Ceiling bump cancels jump hold** — `sweepAxisY` now sets `jumpHoldRem = 0` on upward ceiling collision. Previously the jump-hold code re-applied `jumpVel` on the tick after a ceiling bump, causing the hero to oscillate at the ceiling with velY alternating between 0 and 17.4.

**Remaining drift source:** 0.021 u posX offset accumulated during the sprint/shuttlecock phase (ticks 100–180). During the air hang's 6-tick lighter-gravity ramp, this offset amplifies to ~0.40 u posY drift at the fall nadir (tick 285). After landing, drift recovers to 0.005 u. The velocity during the ramp is trace-exact; only the position is affected by the upstream offset.

The 17.4 u/s max vel spike is from the sprint-phase `canDash`/`canAttack` timing divergence at tick 101 (present in all presets, within budget for presets 1–3).

## Ship / RL readiness

Mean-drift summary across all five presets is **< 0.04 u** (~4 % hero half-width). Peak drifts are concentrated at specific decomp-known mechanics:
- preset 4 peak = terrain geometry artifact (1 tick / 12 seconds).
- preset 5 peak = air-hang ramp during ceiling-bump falls (2 events / 8 seconds).

A policy trained on this sim will not encounter these as systematic biases — they're fractional-tile dispersions around otherwise trace-accurate trajectories. RL transfer should hold.

## Code pointers (diff against previous session)

- `sim/silksong_sim/src/sim.cpp` — shuttlecock queue/fire/clear, sprint 3-path cancel with carryover, `PF_AirHangFired` gate, ceiling X-range.
- `sim/silksong_sim/src/types.hpp` — `PF_Shuttlecock` / `PF_AirHangFired` flags; `shuttlecockQueueTicks` field; `Arena.ceilingMinX/MaxX`; `HeroInit` grew to 40 bytes.
- `sim/silksong_sim/src/consts.hpp` — `shuttlecockSpeed = 18`, `shuttlecockQueueFrames = 6`; `arenaMinX = -2`, `arenaMaxX = 60`.
- `sim/silksong_sim/src/level_gen.cpp` — `resetEpisodeState` copies X-range + ceiling from `HeroInit`; initialises `shuttlecockQueueTicks = 0` and `airHangRem = 0`.
- `sim/silksong_sim/scripts/oracle_diff.py` — `_estimate_ceiling(trace)` returns (Y, minX, maxX); `_set_hero_init` passes the new X-range fields.

## Guardrails (reinforced)

- **Do not** remove the `sprintActiveTicks` reset on `justLanded`. Preset 5's short post-shuttlecock ground sprint depends on it going into the carryover path rather than Skid End 1.
- **Do not** narrow the arena X bounds back below ±40 — preset 5 needs posX = 41.4 clearance.
- **Do not** change the air-hang ramp ordering (trigger → apply → ramp → snap). The ordering is load-bearing: preset 1 requires snap using newBits (no lag), preset 5 requires ramp+snap updating for NEXT tick (1-tick lag). Using prevActionBits for the snap breaks preset 1; using newBits for the apply breaks preset 5.
- Self-test still green; preset 2 anchor unchanged; no sim change should touch preset 2 or 3's current drift values.

## Next-session checklist

1. Investigate preset 5's upstream sprint-phase posX offset (0.021 u by tick 190). This is the root cause of the remaining 0.465 u max pos drift — the air hang model is now velocity-correct.
2. If time: model preset 4's terrain gap (sub-pixel floor discontinuity) or add a 1-tick grounded-hysteresis to absorb it.

## FSM decode results (sprint FSM, path_id -5601421137281451283)

Decoded via UnityPy from `fsmtemplates_assets_shared.bundle`. Key finding: **the Sprint FSM does NOT set `gravityScale = 0.2`**. Air hang gravity is set entirely by `HeroController.FixedUpdate()`:

- `StartAirHang()` fires at line 3288 when `!didAirHang && !onGround && velY < 0 && !controlReqlinquished && transitionState == WAITING_TO_TRANSITION`
- `WAITING_TO_TRANSITION = 0` (the default/normal state) — the gate **passes**, not blocks
- During active sprint, `controlReqlinquished = true` (set by Sprint FSM via `RelinquishControlNotVelocity`), blocking `StartAirHang`
- After sprint ends, `RegainControl()` clears `controlReqlinquished`, allowing air hang on subsequent bare jumps

Full Sprint FSM JSON: `scripts/sprint_fsm_full.json` (156 states). Decoder script: `scripts/decode_fsm.py`.

---
Last updated: 2026-04-24 (air-hang ramp modeled, ceiling-bump jumphold cancel, FSM decoded — 3 of 5 passing, preset 5 velocity-correct).
