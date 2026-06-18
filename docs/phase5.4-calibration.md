# Phase 5.4 — Physics constants calibration workflow

Phase 5.1 / 5.2 / 5.3 shipped real Silksong physics with **placeholder constants**
(gravity = −58 u/s², moveAccel = 230, jumpVel = 22, etc.). Phase 5.4 dials those
constants in against **oracle traces** recorded from the live Unity game, so
a policy trained in the sim behaves identically when deployed back to Silksong.

## The harness

`sim/silksong_sim/scripts/oracle_diff.py` replays a recorded trace through the
sim and reports per-frame position / velocity L2 drift. Pass / fail thresholds
come from `docs/framework-requirements.md` §5:

| Metric | Budget |
|---|---|
| L2 position drift / frame | < 0.1 u |
| L2 velocity drift / frame | < 0.05 u/s |

## Self-test (do this first, any time you change `sim.cpp`)

```bash
PYTHONPATH=sim/silksong_sim/build uv run python \
    sim/silksong_sim/scripts/oracle_diff.py --self-test
```

Generates a synthetic trace by running the sim forward with a varied action
stream, then replays it back through the same sim. **Drift must be exactly 0.**
If not, the harness has regressed — fix that before trusting real-trace diffs.

## Recording a real trace

1. Install the BepInEx plugin in your Silksong install (see `framework-requirements.md` §7).
2. Launch Silksong via the plugin loader: `./run_bepinex.sh "Hollow Knight Silksong"`.
3. Navigate to the Lace arena (the save file at `resources/user1.dat` spawns you next to the fight door).
4. **Press `F10` to start recording.**
5. Do something varied but keep it at least initially on flat ground — walk, jump, dash, attack, heal. Maybe 15–30 seconds.
6. **Press `F10` again to stop.** A `trace_<id>_<timestamp>_<n>.bin` file lands in `<silksong_dir>/traces/`.

Best traces for physics calibration specifically:
- Start with 1–2 seconds of **no input** so the hero settles on the ground. This lets the harness seed from a calm state where hidden timer fields (airJumps, coyote frames) don't matter.
- Mix in pure movement (walk/run) separately from combat. Clean-mechanic traces help isolate which constant is off.

## Running the diff

```bash
PYTHONPATH=sim/silksong_sim/build uv run python \
    sim/silksong_sim/scripts/oracle_diff.py <path-to-trace.bin> --verbose
```

Output shape:

```
=== Oracle diff: /path/to/trace.bin ===
  ticks compared:         842
  pos drift: mean=0.0142u  max=0.0891u  (threshold 0.1u)
  vel drift: mean=0.0081 u/s  max=0.0412 u/s  (threshold 0.05 u/s)
  pos drift quartiles:    p50=0.0120  p90=0.0270  p99=0.0612
  VERDICT: PASS ✓
```

If VERDICT is FAIL, read the per-tick drift table (`--verbose` prints every ~5th tick) to locate WHERE the drift spikes. That pinpoints which mechanic's constants are off.

## Tuning loop

1. Record 3–5 traces covering different mechanics (walk only / walk+jump / add dash / add heal / mixed).
2. Run `oracle_diff.py` on each. Identify the mechanic whose constants are most off (largest drift spike around its frames).
3. Edit `sim/silksong_sim/src/consts.hpp`.
4. Rebuild: `ninja -C sim/silksong_sim/build`.
5. Re-run all traces. Stop when every trace passes the budgets.

### Which constant → which drift symptom

| Drift signature | Likely culprit in `consts.hpp` |
|---|---|
| Hero falls too fast / too slow when airborne | `gravity` |
| Hero accelerates to max speed too fast / slow | `moveAccel` |
| Hero coasts too long / stops too abruptly when input released | `friction` |
| Max walking speed diverges linearly on straight runs | `maxHorizSpeed` |
| Jump peak too high / too low | `jumpVel` |
| Jump cutoff on release lifts too much / too little | `jumpReleaseCut` |
| Dash distance wrong | `dashVel`, `dashDurationFrames` |
| Wall jump arc wrong | `wallJumpVelX`, `wallJumpVelY` |
| Hero collides / passes through walls | `heroHalfWidth`, `heroHalfHeight` |

## Known limitations

- `HeroInit` seeds only `{pos, vel, prevActionBits}`. Timer state (`airJumpsRem`, `coyoteRem`, `dashTimerRem`, `iFrameRem`, etc.) falls back to reset defaults. So replays that start mid-action (mid-dash, mid-heal) will have elevated drift in their early frames. **Start your recordings from a calm grounded pose to avoid this.**
- The sim's attack / heal / dash mechanics use placeholder frame counts and damage values — those aren't in the calibration's physics scope. Phase 7 (boss FSM + damage events) revisits combat timings.
- The trivial Lace Tower arena baked in `sim.cpp::bakeLaceTowerArena` is a rectangular outer-wall approximation. Position drift in the middle-of-arena columns or terraces is expected and is a Phase 9 scope item (load real collider data).

## Pass criterion for Phase 5.4

All 5+ recorded traces pass both budgets. At that point `docs/framework-requirements.md` §5's fidelity contract is satisfied for the physics layer; combat fidelity waits for Phase 7.
