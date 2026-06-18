# Faithful FSM Action Port — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Audit all 74 gameplay-mapped C++ FSM action types against their decompiled C# source and fix every behavioral difference, making the sim's boss FSM interpreter faithful to the original game.

**Architecture:** Phase 1 dispatches 8 parallel read-only audit agents that compare C# vs C++ vs bake for every action, producing structured diff reports. Phase 2 collects all findings and fixes them in groups organized by root cause (bake gaps, missing OnUpdate, logic errors, etc.). Re-bake and rebuild after all fixes.

**Tech Stack:** Python 3 (bake script), C++17 (sim interpreter), decompiled C# (ground truth)

---

## File Map

| File | Role | Phase |
|------|------|-------|
| `decompiled/HutongGames/PlayMaker/Actions/*.cs` | Ground truth C# source | Read-only (Phase 1) |
| `decompiled/CheckAlertRange.cs` | Custom game action (not in PlayMaker namespace) | Read-only (Phase 1) |
| `decompiled/CheckAlertRangeByName.cs` | Custom game action | Read-only (Phase 1) |
| `decompiled/CheckIsCharacterGrounded.cs` | Custom game action | Read-only (Phase 1) |
| `decompiled/FreezeMoment.cs` | Custom game action | Read-only (Phase 1) |
| `scripts/bake_fsm.py` | JSON→C++ param compiler | Read (Phase 1), Modify (Phase 2) |
| `sim/silksong_sim/src/fsm_actions.hpp` | C++ action interpreter | Read (Phase 1), Modify (Phase 2) |
| `sim/silksong_sim/src/fsm_types.hpp` | Runtime structs | Read (Phase 1), Modify (Phase 2) |
| `sim/silksong_sim/src/sim.cpp` | Tick loop / action context | Read (Phase 1), Modify (Phase 2) |
| `sim/silksong_sim/src/fsm_lace_boss1.hpp` | Auto-generated baked output | Regenerate (Phase 2) |
| `scripts/lace_boss1_control_fsm.json` | Raw FSM data | Read-only (both phases) |

---

## Phase 1: Full Audit (8 parallel tasks)

Each audit task is dispatched to a read-only agent. No code changes — only research and reporting. All 8 can run in parallel.

### C# Source Paths

Some actions have C# files outside the standard PlayMaker namespace. The audit agents must check these alternate paths:

| C++ Action Type | C# Source Path |
|----------------|----------------|
| CheckAlertRange | `decompiled/CheckAlertRange.cs` |
| CheckAlertRangeByName | `decompiled/CheckAlertRangeByName.cs` |
| CheckIsCharacterGrounded | `decompiled/CheckIsCharacterGrounded.cs` |
| FreezeMoment | `decompiled/FreezeMoment.cs` |
| GetPosition2d | `decompiled/HutongGames/PlayMaker/Actions/GetPosition2D.cs` (note: capital D) |
| GetSelfPosition | `decompiled/HutongGames/PlayMaker/Actions/GetPosition.cs` (mapped from GetPosition) |
| SetPosition2d | `decompiled/HutongGames/PlayMaker/Actions/SetPosition2D.cs` (note: capital D) |

All others: `decompiled/HutongGames/PlayMaker/Actions/{ActionName}.cs`

### Audit Checklist (applies to every action)

Each action must be checked for ALL of the following:

1. **Reset() defaults:** Which FsmFloat/FsmBool/FsmInt/FsmVector fields use `UseVariable = true` (None) in Reset()? Does the bake use `p_none()` for those fields, or does it conflate None with literal zero via `p()`?
2. **OnEnter behavior:** Does C# call `Finish()` in OnEnter? Does C++ match (one-shot vs continuous)?
3. **OnUpdate behavior:** Does C# have OnUpdate/OnFixedUpdate? Does C++ have a matching case in `fsmActionOnUpdate`?
4. **everyFrame flag:** Is the C# default `everyFrame = false` or `true`? Is the bake using `CONTINUOUS_ACTIONS` hardcoded set or extracting per-instance? Does the default match?
5. **Param extraction completeness:** List every param the C# reads. Is each one extracted by the bake script? Using the right helper (`p()` for literals, `p_var()` for variable refs, `p_none()` for None-defaulting fields)?
6. **Param layout match:** Does the C++ read p[0], p[1], ... at the same offsets the bake emits them?
7. **Variable resolution:** Where C# reads `FsmFloat.Value` (which resolves variable refs), does C++ call `fsmReadVar()`? Where C# writes to a variable, does C++ call `fsmWriteVar()`?
8. **Event firing:** List every event C# fires (sendEvent, finishEvent, trueEvent, etc.). Does C++ fire them all?
9. **Space handling:** For position/translation actions, does C# use Space.Self or Space.World? Does C++ match?
10. **Finish() pattern:** Does C++ OnUpdate return `true` when the action should finish? Does it return `false` for continuous actions?
11. **Write targets:** Does C++ write to the correct struct (ctx.* for actx locals, ctx.rt.* for FsmRuntime, ctx.sc.* for StunControl)?
12. **Already fixed:** Note which issues were already fixed in the prior audit round (commits 4c76361a through 46b7bce5).

### Output Format

For each action, produce:

```
### {ActionName}
**C# file:** {path}
**C# behavior:** {1-3 sentence summary with key line numbers}
**C++ behavior:** {1-3 sentence summary with key line numbers}  
**Bake:** {which params extracted, which helpers used}
**Differences:**
1. {what C# does} vs {what C++ does} — {CRITICAL/MODERATE/LOW}
**Previously fixed:** {list any, or "none"}
```

If an action has NO differences, report: `**Differences:** None — faithful port.`

---

### Task 1: Audit Group 1 — Movement

**Actions:** SetVelocityByScale, SetVelocity2d, DecelerateXY, SetPosition2d, Translate, ClampPosition, AnimatePositionTo

**C# source files:**
- `decompiled/HutongGames/PlayMaker/Actions/SetVelocityByScale.cs`
- `decompiled/HutongGames/PlayMaker/Actions/SetVelocity2d.cs`
- `decompiled/HutongGames/PlayMaker/Actions/DecelerateXY.cs`
- `decompiled/HutongGames/PlayMaker/Actions/SetPosition2D.cs`
- `decompiled/HutongGames/PlayMaker/Actions/SetPosition.cs`
- `decompiled/HutongGames/PlayMaker/Actions/Translate.cs`
- `decompiled/HutongGames/PlayMaker/Actions/ClampPosition.cs`
- `decompiled/HutongGames/PlayMaker/Actions/AnimatePositionTo.cs`

**C++ file:** `sim/silksong_sim/src/fsm_actions.hpp` (search for `case FsmActionType::{Name}`)
**Bake file:** `scripts/bake_fsm.py` (search for `action_name == "{Name}"`)

- [ ] **Step 1: Read each C# file, the corresponding C++ case, and bake extraction**
- [ ] **Step 2: Apply the audit checklist (all 12 points) to each action**
- [ ] **Step 3: Produce the structured report for all 7 actions**

---

### Task 2: Audit Group 2 — Physics & Facing

**Actions:** SetIsKinematic2d, SetGravity2dScale, FaceObjectV2, FaceObjectV4, FlipScale, SetScale, GetScale

**C# source files:**
- `decompiled/HutongGames/PlayMaker/Actions/SetIsKinematic2d.cs`
- `decompiled/HutongGames/PlayMaker/Actions/SetGravity2dScale.cs`
- `decompiled/HutongGames/PlayMaker/Actions/FaceObjectV2.cs`
- `decompiled/HutongGames/PlayMaker/Actions/FaceObjectV4.cs`
- `decompiled/HutongGames/PlayMaker/Actions/FlipScale.cs`
- `decompiled/HutongGames/PlayMaker/Actions/SetScale.cs`
- `decompiled/HutongGames/PlayMaker/Actions/GetScale.cs`

**C++ file:** `sim/silksong_sim/src/fsm_actions.hpp`
**Bake file:** `scripts/bake_fsm.py`

- [ ] **Step 1: Read each C# file, the corresponding C++ case, and bake extraction**
- [ ] **Step 2: Apply the audit checklist (all 12 points) to each action**
- [ ] **Step 3: Produce the structured report for all 7 actions**

---

### Task 3: Audit Group 3 — Variable Setters

**Actions:** SetBoolValue, SetFloatValue, SetIntValue, IntAdd, FloatAdd, FloatMultiply, FloatClamp, SetStringValue, MultiplyIntByFloat

**C# source files:**
- `decompiled/HutongGames/PlayMaker/Actions/SetBoolValue.cs`
- `decompiled/HutongGames/PlayMaker/Actions/SetFloatValue.cs`
- `decompiled/HutongGames/PlayMaker/Actions/SetIntValue.cs`
- `decompiled/HutongGames/PlayMaker/Actions/IntAdd.cs`
- `decompiled/HutongGames/PlayMaker/Actions/FloatAdd.cs`
- `decompiled/HutongGames/PlayMaker/Actions/FloatMultiply.cs`
- `decompiled/HutongGames/PlayMaker/Actions/FloatClamp.cs`
- `decompiled/HutongGames/PlayMaker/Actions/SetStringValue.cs`
- `decompiled/HutongGames/PlayMaker/Actions/MultiplyIntByFloat.cs`

**C++ file:** `sim/silksong_sim/src/fsm_actions.hpp`
**Bake file:** `scripts/bake_fsm.py`

- [ ] **Step 1: Read each C# file, the corresponding C++ case, and bake extraction**
- [ ] **Step 2: Apply the audit checklist (all 12 points) to each action**
- [ ] **Step 3: Produce the structured report for all 9 actions**

---

### Task 4: Audit Group 4 — Comparisons & Tests

**Actions:** BoolTest, BoolTestMulti, BoolAllTrue, FloatCompare, FloatTestToBool, IntCompare, FloatInRange

**C# source files:**
- `decompiled/HutongGames/PlayMaker/Actions/BoolTest.cs`
- `decompiled/HutongGames/PlayMaker/Actions/BoolTestMulti.cs`
- `decompiled/HutongGames/PlayMaker/Actions/BoolAllTrue.cs`
- `decompiled/HutongGames/PlayMaker/Actions/FloatCompare.cs`
- `decompiled/HutongGames/PlayMaker/Actions/FloatTestToBool.cs`
- `decompiled/HutongGames/PlayMaker/Actions/IntCompare.cs`
- `decompiled/HutongGames/PlayMaker/Actions/FloatInRange.cs`

**C++ file:** `sim/silksong_sim/src/fsm_actions.hpp`
**Bake file:** `scripts/bake_fsm.py`

- [ ] **Step 1: Read each C# file, the corresponding C++ case, and bake extraction**
- [ ] **Step 2: Apply the audit checklist (all 12 points) to each action**
- [ ] **Step 3: Produce the structured report for all 7 actions**

---

### Task 5: Audit Group 5 — Random, Ease & Spatial Queries

**Actions:** RandomFloat, RandomInt, EaseFloat, GetDistance, GetXDistance, GetSelfPosition, GetPosition2d

**C# source files:**
- `decompiled/HutongGames/PlayMaker/Actions/RandomFloat.cs`
- `decompiled/HutongGames/PlayMaker/Actions/RandomInt.cs`
- `decompiled/HutongGames/PlayMaker/Actions/EaseFloat.cs` and `decompiled/HutongGames/PlayMaker/Actions/EaseFsmAction.cs` (base class)
- `decompiled/HutongGames/PlayMaker/Actions/GetDistance.cs`
- `decompiled/HutongGames/PlayMaker/Actions/GetXDistance.cs`
- `decompiled/HutongGames/PlayMaker/Actions/GetPosition.cs` (mapped as GetSelfPosition)
- `decompiled/HutongGames/PlayMaker/Actions/GetPosition2D.cs`

**C++ file:** `sim/silksong_sim/src/fsm_actions.hpp`
**Bake file:** `scripts/bake_fsm.py`

**Note for EaseFloat:** The easing logic lives in the base class `EaseFsmAction.cs`. Read BOTH files. Check all 28 easing function types — the C++ currently only implements linear.

- [ ] **Step 1: Read each C# file, the corresponding C++ case, and bake extraction**
- [ ] **Step 2: Apply the audit checklist (all 12 points) to each action**
- [ ] **Step 3: Produce the structured report for all 7 actions**

---

### Task 6: Audit Group 6 — Position Checks

**Actions:** CheckXPosition, CheckYPosition, CheckYPositionV2, CheckIsCharacterGrounded, CheckTargetDirection, CheckCollisionSide, CheckCollisionSideEnter

**C# source files:**
- `decompiled/HutongGames/PlayMaker/Actions/CheckXPosition.cs`
- `decompiled/HutongGames/PlayMaker/Actions/CheckYPosition.cs`
- `decompiled/HutongGames/PlayMaker/Actions/CheckYPositionV2.cs`
- `decompiled/CheckIsCharacterGrounded.cs`
- `decompiled/HutongGames/PlayMaker/Actions/CheckTargetDirection.cs`
- `decompiled/HutongGames/PlayMaker/Actions/CheckCollisionSide.cs`
- `decompiled/HutongGames/PlayMaker/Actions/CheckCollisionSideEnter.cs`

**C++ file:** `sim/silksong_sim/src/fsm_actions.hpp`
**Bake file:** `scripts/bake_fsm.py`

- [ ] **Step 1: Read each C# file, the corresponding C++ case, and bake extraction**
- [ ] **Step 2: Apply the audit checklist (all 12 points) to each action**
- [ ] **Step 3: Produce the structured report for all 7 actions**

---

### Task 7: Audit Group 7 — Events & Timing

**Actions:** Wait, WaitRandom, NextFrameEvent, SendEvent, SendEventByName, SendEventByNameV2, SendEventByScale, SendRandomEvent, SendRandomEventV3

**C# source files:**
- `decompiled/HutongGames/PlayMaker/Actions/Wait.cs`
- `decompiled/HutongGames/PlayMaker/Actions/WaitRandom.cs`
- `decompiled/HutongGames/PlayMaker/Actions/NextFrameEvent.cs`
- `decompiled/HutongGames/PlayMaker/Actions/SendEvent.cs`
- `decompiled/HutongGames/PlayMaker/Actions/SendEventByName.cs`
- `decompiled/HutongGames/PlayMaker/Actions/SendEventByNameV2.cs`
- `decompiled/HutongGames/PlayMaker/Actions/SendEventByScale.cs`
- `decompiled/HutongGames/PlayMaker/Actions/SendRandomEvent.cs`
- `decompiled/HutongGames/PlayMaker/Actions/SendRandomEventV3.cs`

**C++ file:** `sim/silksong_sim/src/fsm_actions.hpp`
**Bake file:** `scripts/bake_fsm.py`

- [ ] **Step 1: Read each C# file, the corresponding C++ case, and bake extraction**
- [ ] **Step 2: Apply the audit checklist (all 12 points) to each action**
- [ ] **Step 3: Produce the structured report for all 9 actions**

---

### Task 8: Audit Group 8 — Combat, Alerts & Colliders

**Actions:** SetDamageHeroAmount, SetRecoilSpeed, SetRecoilBlocked, SetSpecialDeath, SetInvincible, SubtractHP, CompareHP, GetHP, DamageHeroDirectly, CanHeroTakeDamage, FreezeMoment, CheckAlertRange, CheckAlertRangeByName, CheckHeroPerformanceRegionV2, RayCast2dV2, SetCollider, SetPolygonCollider, ReceivedDamage, PreventInvincibleEffect, SetHitEffectOrigin, GetFsmFloat

**C# source files:**
- `decompiled/HutongGames/PlayMaker/Actions/SetDamageHeroAmount.cs`
- `decompiled/HutongGames/PlayMaker/Actions/SetRecoilSpeed.cs`
- `decompiled/HutongGames/PlayMaker/Actions/SetRecoilBlocked.cs`
- `decompiled/HutongGames/PlayMaker/Actions/SetSpecialDeath.cs`
- `decompiled/HutongGames/PlayMaker/Actions/SetInvincible.cs`
- `decompiled/HutongGames/PlayMaker/Actions/SubtractHP.cs`
- `decompiled/HutongGames/PlayMaker/Actions/CompareHP.cs`
- `decompiled/HutongGames/PlayMaker/Actions/GetHP.cs`
- `decompiled/HutongGames/PlayMaker/Actions/DamageHeroDirectly.cs`
- `decompiled/HutongGames/PlayMaker/Actions/CanHeroTakeDamage.cs`
- `decompiled/FreezeMoment.cs`
- `decompiled/CheckAlertRange.cs`
- `decompiled/CheckAlertRangeByName.cs`
- `decompiled/HutongGames/PlayMaker/Actions/CheckHeroPerformanceRegionV2.cs`
- `decompiled/HutongGames/PlayMaker/Actions/RayCast2dV2.cs`
- `decompiled/HutongGames/PlayMaker/Actions/SetCollider.cs`
- `decompiled/HutongGames/PlayMaker/Actions/SetPolygonCollider.cs`
- `decompiled/HutongGames/PlayMaker/Actions/ReceivedDamage.cs`
- `decompiled/HutongGames/PlayMaker/Actions/PreventInvincibleEffect.cs`
- `decompiled/HutongGames/PlayMaker/Actions/SetHitEffectOrigin.cs`
- `decompiled/HutongGames/PlayMaker/Actions/GetFsmFloat.cs`

**C++ file:** `sim/silksong_sim/src/fsm_actions.hpp`
**Bake file:** `scripts/bake_fsm.py`

- [ ] **Step 1: Read each C# file, the corresponding C++ case, and bake extraction**
- [ ] **Step 2: Apply the audit checklist (all 12 points) to each action**
- [ ] **Step 3: Produce the structured report for all 21 actions**

---

## Phase 2: Systematic Fixes (generated after Phase 1)

Phase 2 tasks are created AFTER all 8 audit reports are collected. The orchestrator will:

### Task 9: Consolidate audit findings

- [ ] **Step 1: Collect all 8 audit reports**
- [ ] **Step 2: Deduplicate findings (some issues span multiple actions)**
- [ ] **Step 3: Group by root cause category:**
  - **A. None sentinel gaps** — fields needing `p_none()` in the bake
  - **B. Missing param extraction** — C# params not extracted at all
  - **C. Missing OnUpdate handlers** — actions that should be continuous but aren't
  - **D. everyFrame per-instance** — hardcoded CONTINUOUS_ACTIONS vs JSON extraction
  - **E. Logic differences** — C++ control flow doesn't match C#
  - **F. Write-target errors** — writing to wrong struct field
  - **G. Plumbing gaps** — missing fields in FsmRuntime/FsmActionCtx/StunControl
- [ ] **Step 4: Write a fix plan document listing every finding, its category, and the specific code change needed**
- [ ] **Step 5: Prioritize: CRITICAL fixes first, then MODERATE, then LOW**

### Task 10: Apply fixes — Category A (None sentinel gaps)

**Files:**
- Modify: `scripts/bake_fsm.py` — change `p()` to `p_none()` for affected fields
- Modify: `sim/silksong_sim/src/fsm_actions.hpp` — add `fsmIsNone()` guards

- [ ] **Step 1: For each field identified in Category A, change the bake extraction from `p()` to `p_none()`**
- [ ] **Step 2: For each affected C++ action, add `if (!fsmIsNone(p[N]))` guard before using the value**
- [ ] **Step 3: Commit**

```bash
git add scripts/bake_fsm.py sim/silksong_sim/src/fsm_actions.hpp
git commit -m "fix: apply NaN sentinel to all None-defaulting FsmFloat fields"
```

### Task 11: Apply fixes — Category B (Missing param extraction)

**Files:**
- Modify: `scripts/bake_fsm.py` — add missing param extraction lines
- Modify: `sim/silksong_sim/src/fsm_actions.hpp` — read the newly-available params

- [ ] **Step 1: For each missing param identified in Category B, add the extraction line in the bake script using the correct helper (`p()`, `p_var()`, or `p_none()`)**
- [ ] **Step 2: Update the C++ action to read the new param at the correct offset**
- [ ] **Step 3: Update any param offset comments in the C++ to reflect the new layout**
- [ ] **Step 4: Commit**

```bash
git add scripts/bake_fsm.py sim/silksong_sim/src/fsm_actions.hpp
git commit -m "fix: extract all missing C# params in bake script"
```

### Task 12: Apply fixes — Category C (Missing OnUpdate handlers)

**Files:**
- Modify: `sim/silksong_sim/src/fsm_actions.hpp` — add OnUpdate cases

- [ ] **Step 1: For each action identified in Category C, add a `case FsmActionType::{Name}` in `fsmActionOnUpdate`**
- [ ] **Step 2: Port the OnUpdate logic line-for-line from the C# OnUpdate/OnFixedUpdate method**
- [ ] **Step 3: Commit**

```bash
git add sim/silksong_sim/src/fsm_actions.hpp
git commit -m "fix: add missing OnUpdate handlers for continuous actions"
```

### Task 13: Apply fixes — Category D (everyFrame per-instance)

**Files:**
- Modify: `scripts/bake_fsm.py` — extract everyFrame from JSON per-instance
- Possibly modify: `sim/silksong_sim/src/fsm_types.hpp` — if flags field needs expansion

- [ ] **Step 1: For each action identified in Category D, extract the `everyFrame` field from the JSON params**
- [ ] **Step 2: Set the continuous flag based on the extracted value instead of the hardcoded `CONTINUOUS_ACTIONS` set**
- [ ] **Step 3: Remove the action from `CONTINUOUS_ACTIONS` if it's now per-instance**
- [ ] **Step 4: Commit**

```bash
git add scripts/bake_fsm.py
git commit -m "fix: extract everyFrame per-instance instead of hardcoded continuous set"
```

### Task 14: Apply fixes — Categories E, F, G (Logic, write-targets, plumbing)

**Files:**
- Modify: `sim/silksong_sim/src/fsm_actions.hpp` — fix logic and write targets
- Modify: `sim/silksong_sim/src/fsm_types.hpp` — add missing struct fields
- Modify: `sim/silksong_sim/src/sim.cpp` — wire new fields into FsmActionCtx

- [ ] **Step 1: Fix each logic difference (Category E) — port the C# control flow line-for-line**
- [ ] **Step 2: Fix each write-target error (Category F) — change ctx.rt.* to ctx.* or vice versa as needed**
- [ ] **Step 3: Add missing struct fields (Category G) — add to FsmRuntime/FsmActionCtx, wire in sim.cpp**
- [ ] **Step 4: Commit**

```bash
git add sim/silksong_sim/src/fsm_actions.hpp sim/silksong_sim/src/fsm_types.hpp sim/silksong_sim/src/sim.cpp
git commit -m "fix: correct logic, write-targets, and struct plumbing for faithful C# match"
```

### Task 15: Re-bake, rebuild, verify

- [ ] **Step 1: Re-bake FSM**

```bash
python scripts/bake_fsm.py scripts/lace_boss1_control_fsm.json \
    > sim/silksong_sim/src/fsm_lace_boss1.hpp
```

Verify: `grep -c "NAN" sim/silksong_sim/src/fsm_lace_boss1.hpp` should show NaN sentinels.
Verify: `head -12 sim/silksong_sim/src/fsm_lace_boss1.hpp` — NUM_PARAMS must be ≤ 800.

- [ ] **Step 2: Rebuild sim**

```bash
cd sim/silksong_sim/build && ninja
```

Must compile with zero errors. Pre-existing warnings (unused parameters) are acceptable.

- [ ] **Step 3: Run benchmark**

```bash
python sim/silksong_sim/scripts/benchmark.py --num-worlds 1024 --steps 1000
```

Throughput must be within 5% of baseline.

- [ ] **Step 4: Commit generated file**

```bash
git add sim/silksong_sim/src/fsm_lace_boss1.hpp
git commit -m "chore: re-bake FSM with all faithful port fixes"
```

---

## Execution Notes

### Phase 1 parallelism
Tasks 1-8 are fully independent and should be dispatched simultaneously. Each is a read-only research task — no file conflicts possible.

### Phase 2 sequencing
Task 9 depends on Tasks 1-8 completing. Tasks 10-14 depend on Task 9. Tasks 10-14 can potentially run in parallel if they touch non-overlapping sections of the files, but sequential execution is safer to avoid merge conflicts in fsm_actions.hpp. Task 15 depends on all of Tasks 10-14.

### Constraint
Phase 2 tasks (10-14) are templates. Their exact content — which specific actions, which specific params, which specific code changes — is determined by the audit findings from Phase 1. The orchestrator must fill in the specifics after collecting the audit reports in Task 9.
