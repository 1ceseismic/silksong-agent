# Faithful FSM Action Port — Design Spec

**Date:** 2026-05-14  
**Goal:** Make every one of the 78 gameplay-mapped action types in the C++ FSM interpreter behave identically to the decompiled C# PlayMaker source, line-for-line.

**Non-goal:** Redesigning the interpreter architecture, adding new abstractions, or porting the ~50 cosmetic/unused action types (audio, particles, dialogue, skip-state-only actions).

---

## Background

The sim's FSM interpreter (`fsm_actions.hpp`) ports PlayMaker actions from the original Unity/C# game into C++ for GPU-accelerated RL training. A prior audit of 30 of the 78 ported actions found 14 critical behavioral differences — wrong events, zeroed gravity, broken attack selection, dead code. These were fixed.

However:
- 48 action types have never been audited
- The 30 audited actions still have ~15 known moderate/low unfixed issues
- The first audit may have missed subtleties

This spec describes a complete, fresh audit of all 78 action types followed by systematic fixes.

## Scope

### In scope
All 78 action types listed in `GAMEPLAY_ACTIONS` in `scripts/bake_fsm.py` that map to a non-Noop `FsmActionType`. These are the actions that affect boss movement, facing, timing, variable state, combat, events, and physics.

### Out of scope
- 33 truly cosmetic action types (audio, particles, camera, dialogue, animation visuals)
- 18 noop-but-possibly-relevant action types (ActivateGameObject, SendMessage, etc.) — these are a separate future workstream
- Unity physics engine reimplementation (Box2D raycasts, polygon colliders)
- Animation clip duration extraction from asset bundles
- Hero-side fidelity (separate from boss FSM)

## Source Files

| File | Role |
|------|------|
| `decompiled/HutongGames/PlayMaker/Actions/*.cs` | Ground truth — original C# action implementations |
| `sim/silksong_sim/src/fsm_actions.hpp` | C++ interpreter — what we're fixing |
| `sim/silksong_sim/src/fsm_types.hpp` | Runtime data structures (FsmRuntime, FsmActionCtx, etc.) |
| `scripts/bake_fsm.py` | JSON→C++ data compiler — param extraction |
| `scripts/lace_boss1_control_fsm.json` | Raw FSM data for Lace Boss1 |
| `sim/silksong_sim/src/fsm_lace_boss1.hpp` | Auto-generated baked output (re-bake target) |
| `sim/silksong_sim/src/sim.cpp` | Tick loop, action context wiring |

## Phase 1: Full Audit

### Method

Split all 78 action types into 8 groups of ~10 actions. Dispatch 8 parallel audit agents. Each agent, for each action in its group:

1. Reads the decompiled C# source at `decompiled/HutongGames/PlayMaker/Actions/{ActionName}.cs`
2. Reads the C++ implementation in `fsm_actions.hpp` (both OnEnter and OnUpdate)
3. Reads the bake extraction in `bake_fsm.py`
4. Reports every behavioral difference with:
   - What the C# does (with line numbers)
   - What the C++ does (with line numbers)
   - Whether the bake script preserves the information needed
   - Severity: CRITICAL / MODERATE / LOW

### Audit checklist per action

Each action must be checked for:

- **Reset() defaults:** Which fields use `UseVariable = true` (None)? Does the bake distinguish None from literal zero?
- **OnEnter vs OnUpdate:** Does the C# `Finish()` in OnEnter (one-shot) or run continuously? Does the C++ match?
- **everyFrame flag:** Is it extracted from the JSON or hardcoded via `CONTINUOUS_ACTIONS`? Does the default match C#'s `Reset()`?
- **Param extraction:** Are all params extracted? Using `p()` vs `p_var()` vs `p_none()` correctly?
- **Param layout:** Does the C++ read params at the same offsets the bake emits them?
- **Variable reads/writes:** Does the C++ resolve variable references where the C# does?
- **Space handling:** For position/translation actions, does the C++ handle Space.Self vs Space.World?
- **Event firing:** Are all events that C# fires also fired in C++?
- **Finish() pattern:** Does the C++ return the correct value from OnUpdate (true = finished)?
- **State writes:** Does the C++ write to the correct target (ctx.* vs ctx.rt.* vs ctx.sc.*)?

### Action groups for audit dispatch

| Group | Actions |
|-------|---------|
| 1 — Movement | SetVelocityByScale, SetVelocity2d, DecelerateXY, SetPosition2d, Translate, ClampPosition, AnimatePositionTo |
| 2 — Physics/Facing | SetIsKinematic2d, SetGravity2dScale, FaceObjectV2, FaceObjectV4, FlipScale, SetScale, GetScale |
| 3 — Variables (set) | SetBoolValue, SetFloatValue, SetIntValue, IntAdd, FloatAdd, FloatMultiply, FloatClamp, SetStringValue |
| 4 — Variables (read/test) | BoolTest, BoolTestMulti, BoolAllTrue, FloatCompare, FloatTestToBool, IntCompare, FloatInRange |
| 5 — Random/Ease/Arithmetic | RandomFloat, RandomInt, MultiplyIntByFloat, EaseFloat, GetDistance, GetXDistance |
| 6 — Position queries | GetSelfPosition, GetPosition2d, CheckXPosition, CheckYPosition, CheckYPositionV2, CheckIsCharacterGrounded, CheckTargetDirection |
| 7 — Events/Timing | Wait, WaitRandom, NextFrameEvent, SendEvent, SendEventByName, SendEventByNameV2, SendEventByScale, SendRandomEvent, SendRandomEventV3 |
| 8 — Combat/Collision | SetDamageHeroAmount, SetRecoilSpeed, SetRecoilBlocked, SetSpecialDeath, SetInvincible, SubtractHP, CompareHP, GetHP, DamageHeroDirectly, CanHeroTakeDamage, FreezeMoment, CheckAlertRange, CheckAlertRangeByName, CheckHeroPerformanceRegionV2, RayCast2dV2, CheckCollisionSide, CheckCollisionSideEnter, SetCollider, SetPolygonCollider, ReceivedDamage, PreventInvincibleEffect, SetHitEffectOrigin, GetFsmFloat |

### Audit output format

Each agent produces a report with this structure per action:

```
### {ActionName}
**C# behavior:** {summary with line numbers}
**C++ behavior:** {summary with line numbers}
**Bake extraction:** {what params are extracted, how}
**Differences:**
1. {description} — Severity: {CRITICAL/MODERATE/LOW}
2. ...
**Already fixed:** {list any issues fixed in the prior round}
```

## Phase 2: Systematic Fix

### Fix grouping

After all audit reports are collected, group findings by root cause:

1. **None sentinel gaps** — Fields that need `p_none()` but use `p()` or `p_var()`. Systemic fix in bake script + C++ guards.
2. **Missing param extraction** — Fields present in C# but not extracted by the bake script. Add extraction.
3. **Missing OnUpdate handlers** — Actions that should be continuous but lack an OnUpdate case. Add the handler, update CONTINUOUS_ACTIONS if needed.
4. **everyFrame per-instance** — Actions where everyFrame should come from the JSON, not the hardcoded set. May require adding a per-instance flag or extracting everyFrame from JSON.
5. **Logic differences** — C++ logic that doesn't match C# control flow (wrong comparisons, missing branches, wrong field access).
6. **Write-target errors** — Actions writing to the wrong struct field (ctx.rt.* vs ctx.* vs ctx.sc.*).
7. **Plumbing gaps** — Fields missing from FsmRuntime, FsmActionCtx, or StunControl that are needed for faithful behavior.

### Fix execution

Fixes are implemented via subagent-driven development (same process as the first round):
- One subagent per fix group
- Each subagent edits bake_fsm.py, fsm_actions.hpp, fsm_types.hpp, and/or sim.cpp as needed
- Commit per fix group
- Re-bake and rebuild after all fixes

### Constraints

- No new abstractions beyond what's needed for correctness
- No refactoring of unrelated code
- Preserve the existing param layout contract between bake and C++ where it's already correct
- Keep the generated header within FSM_MAX_PARAMS (800) — currently at 749

## Verification

After all fixes:

1. **Re-bake:** `python scripts/bake_fsm.py scripts/lace_boss1_control_fsm.json > sim/silksong_sim/src/fsm_lace_boss1.hpp`
2. **Rebuild:** `cd sim/silksong_sim/build && ninja` — must compile cleanly
3. **Benchmark:** `python sim/silksong_sim/scripts/benchmark.py` — throughput within 5% of baseline
4. **Oracle diff (hero):** `python sim/silksong_sim/scripts/oracle_diff.py` — if traces available, hero drift should not regress
5. **Manual spot-check:** Verify specific known-bad states (CrossSlash gravity, Kickoff facing, Lava Hop deceleration) now match expected C# behavior

## Success Criteria

- Every CRITICAL finding from the audit is fixed
- Every MODERATE finding is either fixed or documented with a clear reason why it's acceptable (e.g., requires Unity physics engine)
- LOW findings are fixed where practical, documented otherwise
- Sim builds and runs without regressions
