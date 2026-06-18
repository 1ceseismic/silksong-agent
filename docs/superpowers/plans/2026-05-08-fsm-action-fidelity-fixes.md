# FSM Action Fidelity Fixes

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 14 critical and 18 moderate behavioral differences between our C++ FSM interpreter and the original Unity/C# PlayMaker actions, as identified by the cross-language audit.

**Architecture:** Three files carry 95% of the changes: `scripts/bake_fsm.py` (parameter extraction), `sim/silksong_sim/src/fsm_actions.hpp` (action logic), and `sim/silksong_sim/src/fsm_types.hpp` (runtime state). Changes are organized into independent fix groups that can be parallelized across agents working in git worktrees. After all fixes, re-bake and rebuild to verify.

**Tech Stack:** Python 3 (bake script), C++17 (sim), CMake (build), `oracle_diff.py` (trace-based verification)

**Key files:**
- `scripts/bake_fsm.py` — JSON-to-C++ FSM data compiler
- `sim/silksong_sim/src/fsm_actions.hpp` — C++ action implementations
- `sim/silksong_sim/src/fsm_types.hpp` — runtime data structures
- `sim/silksong_sim/src/fsm_lace_boss1.hpp` — auto-generated (re-bake target)
- `sim/silksong_sim/src/sim.cpp` — tick loop / action context wiring
- `scripts/lace_boss1_control_fsm.json` — raw FSM data

**Verification:** After all changes, re-bake and rebuild:
```bash
python scripts/bake_fsm.py scripts/lace_boss1_control_fsm.json \
    > sim/silksong_sim/src/fsm_lace_boss1.hpp
cd sim/silksong_sim/build && ninja
```

---

## Task 1: None Sentinel System (foundational — all other tasks may depend on this)

**Why:** The bake script serializes `FsmFloat { UseVariable = true }` (meaning "leave unchanged / None") as `0.0`, which is indistinguishable from literal zero. This causes `DecelerateXY` to zero velocities, `SetVelocityByScale` to ambiguously handle ySpeed, and `SetDamageHeroAmount` to potentially zero damage. NaN is the correct sentinel because it propagates visibly if misused, never equals anything (including itself), and C++ has `isnan()`.

**Files:**
- Modify: `scripts/bake_fsm.py` — add `p_none()` helper, update action extractors
- Modify: `sim/silksong_sim/src/fsm_actions.hpp` — add `fsmIsNone()`, guard affected actions

- [ ] **Step 1: Add NaN sentinel to bake script**

In `scripts/bake_fsm.py`, add a `NONE_SENTINEL` constant and a `p_none()` helper that returns NaN when the JSON value is missing or represents a None FsmFloat (value 0.0 for fields whose C# `Reset()` default is `UseVariable = true`).

```python
# Near the top, after EVENT_NONE = 255
NONE_SENTINEL = float('nan')
```

Add a new helper inside `extract_action_params`, alongside `p()` and `p_var()`:

```python
    def p_none(key: str) -> float:
        """Resolve a param that defaults to None (UseVariable=true) in C#.
        
        If the JSON value is missing or 0.0, return NaN (None sentinel).
        Non-zero literal values pass through as-is.
        Variable references ($Foo) are resolved normally.
        """
        v = params.get(key)
        if v is None:
            return NONE_SENTINEL
        if isinstance(v, str) and v.startswith("$"):
            var_name = v[1:]
            if var_table.has(var_name):
                return var_table.encode_ref(var_name)
            return NONE_SENTINEL
        if isinstance(v, (int, float)) and float(v) == 0.0:
            return NONE_SENTINEL
        return float(v)
```

- [ ] **Step 2: Update DecelerateXY extraction to use p_none**

In `bake_fsm.py`, in the `DecelerateXY` extraction block (around line 367):

```python
    elif action_name == "DecelerateXY":
        if json_action_name == "DecelerateV2":
            d = p_none("deceleration")
            out.append(d)
            out.append(d)
        else:
            out.append(p_none("decelerationX"))
            out.append(p_none("decelerationY"))
```

- [ ] **Step 3: Update SetVelocityByScale extraction**

In `bake_fsm.py`, the `SetVelocityByScale` block (around line 362):

```python
    if action_name == "SetVelocityByScale":
        out.append(p("speed"))
        out.append(p_none("ySpeed"))
```

`ySpeed` defaults to `UseVariable = true` in C# Reset, so `p_none` is correct here.

- [ ] **Step 4: Add fsmIsNone helper to C++**

In `fsm_actions.hpp`, after the `fsmIsVarRef` function (around line 78):

```cpp
static inline bool fsmIsNone(float param) {
    return std::isnan(param);
}
```

- [ ] **Step 5: Fix DecelerateXY in C++ to skip None axes**

In `fsm_actions.hpp`, the `DecelerateXY` OnUpdate case (around line 908):

```cpp
    case FsmActionType::DecelerateXY: {
        if (!fsmIsNone(p[0])) ctx.bk.velX *= p[0];
        if (!fsmIsNone(p[1])) ctx.bk.velY *= p[1];
        return false;
    }
```

- [ ] **Step 6: Fix SetVelocityByScale in C++ to use fsmIsNone**

In `fsm_actions.hpp`, the `SetVelocityByScale` OnEnter case (around line 209):

```cpp
    case FsmActionType::SetVelocityByScale: {
        ctx.bk.velX = fsmReadVar(rt, p[0]) * fsmFacing(ctx);
        if (!fsmIsNone(p[1])) {
            ctx.bk.velY = fsmReadVar(rt, p[1]);
        }
        break;
    }
```

- [ ] **Step 7: Verify bake output has NaN for known None fields**

```bash
python scripts/bake_fsm.py scripts/lace_boss1_control_fsm.json > /tmp/baked_test.hpp
grep -c "NAN" /tmp/baked_test.hpp
# Should be > 0 (NaN appears for DecelerateXY None axes, SetVelocityByScale None ySpeed)
```

- [ ] **Step 8: Commit**

```bash
git add scripts/bake_fsm.py sim/silksong_sim/src/fsm_actions.hpp
git commit -m "$(cat <<'EOF'
fix: introduce NaN sentinel for None FsmFloat fields

DecelerateXY was zeroing velocity on None axes (vel *= 0.0).
SetVelocityByScale used a fragile != 0 heuristic for ySpeed.
The bake script now emits NaN for fields whose C# Reset() uses
UseVariable=true, and the C++ checks isnan() before applying.
EOF
)"
```

---

## Task 2: Write-Target Fixes (SetIsKinematic2d, SetGravity2dScale)

**Why:** Both actions write to `ctx.rt.isKinematic` / `ctx.rt.gravityScale` (the FsmRuntime struct), but `sim.cpp` copies locals into `actx.*` at line 438-439 and writes them back at line 455-456, overwriting whatever the action stored in `ctx.rt.*`. The fix: write to `ctx.isKinematic` / `ctx.gravityScale` (the actx locals that get written back correctly).

**Files:**
- Modify: `sim/silksong_sim/src/fsm_actions.hpp` — two one-line fixes

- [ ] **Step 1: Fix SetIsKinematic2d write target**

In `fsm_actions.hpp` around line 232, change:

```cpp
// Before:
ctx.rt.isKinematic = (p[0] != 0.f);

// After:
ctx.isKinematic = (p[0] != 0.f);
```

- [ ] **Step 2: Fix SetGravity2dScale write target**

In `fsm_actions.hpp` around line 238, change:

```cpp
// Before:
ctx.rt.gravityScale = fsmReadVar(rt, p[0]);

// After:
ctx.gravityScale = fsmReadVar(rt, p[0]);
```

- [ ] **Step 3: Commit**

```bash
git add sim/silksong_sim/src/fsm_actions.hpp
git commit -m "$(cat <<'EOF'
fix: SetIsKinematic2d and SetGravity2dScale write to actx locals

Both wrote to ctx.rt.* which was immediately overwritten by sim.cpp's
local-to-runtime writeback. Now writes to ctx.* (the actx locals)
so the values survive into bossIntegrate().
EOF
)"
```

---

## Task 3: SendEventByName Param Order Fix

**Why:** The bake script emits `[delay, eventId]` but the C++ reads `p[0]` as eventId. With `delay=0.0`, the C++ fires event 0 (EVT_FINISHED) instead of the intended event. Affects 12 battle states.

**Files:**
- Modify: `scripts/bake_fsm.py` — swap param order in `SendEventByName` block

- [ ] **Step 1: Fix param order**

In `bake_fsm.py` around line 592, change the `SendEventByName` block:

```python
    elif action_name == "SendEventByName":
        se = params.get("sendEvent")
        if isinstance(se, str) and se and not isinstance(se, dict):
            out.append(p("sendEvent", is_event=True))
        else:
            out.append(float(EVENT_NONE))
        out.append(p("delay"))
```

This puts eventId at `p[0]` and delay at `p[1]`, matching the C++ read order and the `SendEvent` / `SendEventByNameV2` param layouts.

- [ ] **Step 2: Commit**

```bash
git add scripts/bake_fsm.py
git commit -m "$(cat <<'EOF'
fix: SendEventByName bake emits [eventId, delay] matching C++ read order

Was [delay, eventId], causing p[0]=0.0 to fire EVT_FINISHED instead
of the intended event in 12 battle states.
EOF
)"
```

---

## Task 4: SendRandomEventV3 Param Layout Fix

**Why:** The bake emits `[n, events, weights, counterVarIdxs, eventMax, missedVarIdxs, missedMax]` but the C++ expects `[n, events, weights, eventMax, missedMax]`. The interleaved var idx arrays cause the C++ to read encoded variable references (~10000) as eventMax limits, making consecutive/missed tracking inoperative.

Also, the C++ uses positional `rt.missedCounts[slot]` tracking, but the Close and Far states map different events to the same slot positions. The C# uses named FSM variables. Fix: key missed tracking by event ID instead of slot index.

**Files:**
- Modify: `scripts/bake_fsm.py` — reorder to `[n, events, weights, eventMax, missedMax]`
- Modify: `sim/silksong_sim/src/fsm_actions.hpp` — fix param offsets, key missedCounts by event ID

- [ ] **Step 1: Simplify bake output to match C++ layout**

In `bake_fsm.py`, replace the `SendRandomEventV3` block (around line 619-674) with:

```python
    elif action_name == "SendRandomEventV3":
        events = params.get("events", [])
        weights_raw = params.get("weights", [])
        event_max_raw = params.get("eventMax", [])
        missed_max_raw = params.get("missedMax", [])
        n = len(events)
        out.append(float(n))
        # Events
        for ev in events:
            out.append(float(event_table.get_or_add(ev)) if ev else float(EVENT_NONE))
        # Weights (first N entries only, before the '?' separator)
        for i in range(n):
            w = weights_raw[i] if i < len(weights_raw) else 0.0
            if isinstance(w, (int, float)):
                out.append(float(w))
            else:
                out.append(0.0)
        # Event max (first N entries only, before the '?' separator)
        for i in range(n):
            em = event_max_raw[i] if i < len(event_max_raw) else 0
            if isinstance(em, (int, float)):
                out.append(float(em))
            else:
                out.append(0.0)
        # Missed max (plain int list, first N)
        for i in range(n):
            mm = missed_max_raw[i] if i < len(missed_max_raw) else 0
            if isinstance(mm, (int, float)):
                out.append(float(mm))
            else:
                out.append(0.0)
```

This produces the layout `[n, eventIds(n), weights(n), eventMax(n), missedMax(n)]` — exactly what the C++ expects at lines 761-764.

- [ ] **Step 2: Fix missed tracking to use event ID as key**

In `fsm_actions.hpp`, in the `SendRandomEventV3` OnEnter case, change the missed counter update loop (around line 815-820). The `missedCounts` array should be indexed by event ID, not by slot position:

```cpp
        // Update missed counters — keyed by event ID, not slot position
        for (int i = 0; i < n && i < 8; ++i) {
            uint8_t eid = (uint8_t)eventIds[i];
            if (eid == evId)
                rt.missedCounts[eid % 8] = 0;
            else if (rt.missedCounts[eid % 8] < 255)
                rt.missedCounts[eid % 8] = (uint8_t)(rt.missedCounts[eid % 8] + 1);
        }
```

And update the force check (around line 779-781):

```cpp
            int msMax = (int)missedMaxes[i];
            uint8_t eid = (uint8_t)eventIds[i];
            if (msMax > 0 && (int)rt.missedCounts[eid % 8] >= msMax) {
                forceIdx = i;
            }
```

- [ ] **Step 3: Commit**

```bash
git add scripts/bake_fsm.py sim/silksong_sim/src/fsm_actions.hpp
git commit -m "$(cat <<'EOF'
fix: SendRandomEventV3 param layout and event-keyed miss tracking

Bake now emits [n, events, weights, eventMax, missedMax] without
interleaved var idx arrays. Missed counts keyed by event ID instead
of slot position, fixing corruption when Close and Far states map
different events to the same slot.
EOF
)"
```

---

## Task 5: Facing Fixes (FaceObjectV2 + FlipScale/SetScale)

**Why:** FaceObjectV2 ignores the `spriteFacesRight` param (already baked at `p[0]`), causing Kickoff state to face toward the hero instead of away. SetScale is mapped to FlipScale but FlipScale ignores params — SetScale sets absolute facing (x=1.0/-1.0) while FlipScale negates.

**Files:**
- Modify: `sim/silksong_sim/src/fsm_actions.hpp` — fix FaceObjectV2, split FlipScale/SetScale logic
- Modify: `sim/silksong_sim/src/fsm_types.hpp` — add `SetScale` to action type enum
- Modify: `scripts/bake_fsm.py` — map SetScale to its own type instead of FlipScale

- [ ] **Step 1: Fix FaceObjectV2 to respect spriteFacesRight**

In `fsm_actions.hpp`, the `FaceObjectV2` / `FaceObjectV4` OnEnter case (around line 291):

```cpp
    case FsmActionType::FaceObjectV2:
    case FsmActionType::FaceObjectV4: {
        // p[0] = spriteFacesRight (1.0 = sprite faces right, 0.0 = faces left)
        bool spriteFacesRight = (p[0] != 0.f);
        bool heroIsRight = (ctx.heroX > ctx.bk.posX);
        // If sprite faces right: face toward hero means positive scale when hero is right
        // If sprite faces left: face toward hero means negative scale when hero is right
        if (heroIsRight == spriteFacesRight)
            ctx.rt.facingScale = 1.f;
        else
            ctx.rt.facingScale = -1.f;
        ctx.facingScale = ctx.rt.facingScale;
        break;
    }
```

- [ ] **Step 2: Add SetScale action type**

In `fsm_types.hpp`, add `SetScale` to the `FsmActionType` enum, before `Count`:

```cpp
    SetHitEffectOrigin,
    SetScale,
    Count
```

- [ ] **Step 3: Map SetScale to its own type in bake script**

In `bake_fsm.py`, change the SetScale mapping (line 160):

```python
    "SetScale": "SetScale",  # absolute facing from x value
```

- [ ] **Step 4: Add SetScale param extraction in bake script**

In `bake_fsm.py`, in `extract_action_params`, after the FlipScale block (around line 425-429), remove the SetScale handling from FlipScale and add a new block:

```python
    elif action_name == "FlipScale":
        pass  # FlipScale has no params — just negates facing
    elif action_name == "SetScale":
        out.append(p("x"))
```

- [ ] **Step 5: Add SetScale OnEnter handler in C++**

In `fsm_actions.hpp`, after the `FlipScale` case (around line 306):

```cpp
    case FsmActionType::SetScale: {
        // p[0] = x scale value. Positive = face right, negative = face left.
        ctx.rt.facingScale = (p[0] >= 0.f) ? 1.f : -1.f;
        ctx.facingScale = ctx.rt.facingScale;
        break;
    }
```

- [ ] **Step 6: Commit**

```bash
git add scripts/bake_fsm.py sim/silksong_sim/src/fsm_actions.hpp sim/silksong_sim/src/fsm_types.hpp
git commit -m "$(cat <<'EOF'
fix: FaceObjectV2 respects spriteFacesRight, SetScale sets absolute facing

FaceObjectV2 now reads p[0] (spriteFacesRight) to determine face
direction. SetScale is a new action type that sets facing from the
sign of p[0], instead of being mapped to FlipScale (which negates).
EOF
)"
```

---

## Task 6: BoolAllTrue Implementation

**Why:** BoolAllTrue is completely non-functional — both OnEnter and OnUpdate are no-ops. The `boolVariables` array is not extracted from the FSM JSON. This breaks the Counter mechanic (Idle state) and Downstab wall detection.

The FSM JSON does not contain the `boolVariables` array (it was lost during extraction). We need to find the bool variable names from the decompiled C# or from contextual analysis of the FSM states that use BoolAllTrue.

**Files:**
- Modify: `scripts/bake_fsm.py` — extract boolVariables or hardcode known mappings
- Modify: `sim/silksong_sim/src/fsm_actions.hpp` — implement BoolAllTrue logic

- [ ] **Step 1: Identify which bool variables BoolAllTrue tests**

Check the FSM JSON and the decompiled C# for each BoolAllTrue usage. In the Idle state, BoolAllTrue fires "COUNTER" — the bool variables tested are likely the counter-ready booleans. In Downstab states, it fires "WALL" — testing wall-hit booleans.

Search the FSM JSON for BoolAllTrue instances:

```bash
python3 -c "
import json
with open('scripts/lace_boss1_control_fsm.json') as f:
    fsm = json.load(f)
for s in fsm['states']:
    for a in s['actions']:
        if a['name'] == 'BoolAllTrue':
            print(f'State: {s[\"name\"]}')
            print(json.dumps(a, indent=2))
            print()
"
```

If the `boolVariables` array is missing from the JSON, check the decompiled C# for which bools are tested. Common patterns:
- Idle/COUNTER: tests `$Alert` + other readiness bools
- Downstab/WALL: tests wall-hit bools from CheckCollisionSide

- [ ] **Step 2: Add boolVariables extraction to bake script**

In `bake_fsm.py`, update the `BoolAllTrue` block to emit the bool variable references:

```python
    elif action_name == "BoolAllTrue":
        out.append(p("sendEvent", is_event=True))
        out.append(p("storeResult"))
        # boolVariables array: list of bool var names
        bool_vars = params.get("boolVariables", [])
        out.append(float(len(bool_vars)))
        for bv in bool_vars:
            if isinstance(bv, str) and bv.startswith("$"):
                out.append(var_table.encode_ref(bv[1:]))
            else:
                out.append(0.0)
```

If `boolVariables` is absent from the JSON, hardcode known mappings instead (add a `BOOL_ALL_TRUE_FIXUP` dict keyed by state name).

- [ ] **Step 3: Implement BoolAllTrue in C++ OnEnter**

In `fsm_actions.hpp`, replace the BoolAllTrue OnEnter noop:

```cpp
    case FsmActionType::BoolAllTrue: {
        // p[0]=sendEvent, p[1]=storeResult, p[2]=numBools, p[3..]=boolVarRefs
        int n = (int)p[2];
        bool allTrue = (n > 0);
        for (int i = 0; i < n; ++i) {
            if (!fsmReadBoolVar(rt, p[3 + i])) {
                allTrue = false;
                break;
            }
        }
        fsmWriteBoolVar(rt, p[1], allTrue);
        if (allTrue) fsmFireEventF(rt, p[0]);
        break;
    }
```

- [ ] **Step 4: Implement BoolAllTrue in C++ OnUpdate**

In `fsm_actions.hpp`, replace the BoolAllTrue OnUpdate noop:

```cpp
    case FsmActionType::BoolAllTrue: {
        int n = (int)p[2];
        bool allTrue = (n > 0);
        for (int i = 0; i < n; ++i) {
            if (!fsmReadBoolVar(rt, p[3 + i])) {
                allTrue = false;
                break;
            }
        }
        fsmWriteBoolVar(rt, p[1], allTrue);
        if (allTrue) fsmFireEventF(rt, p[0]);
        return false;
    }
```

- [ ] **Step 5: Commit**

```bash
git add scripts/bake_fsm.py sim/silksong_sim/src/fsm_actions.hpp
git commit -m "$(cat <<'EOF'
fix: implement BoolAllTrue with boolVariables extraction

Was completely non-functional. Now tests all referenced bool vars and
fires sendEvent when all are true. Enables Counter mechanic and
Downstab wall detection.
EOF
)"
```

---

## Task 7: FreezeMoment Type Lookup

**Why:** FreezeMoment ignores the freeze type enum and hardcodes 0.1s. Real freeze durations range from 0.02s to 0.35s for combat-relevant types. The bake script extracts nothing.

**Files:**
- Modify: `scripts/bake_fsm.py` — extract FreezeMomentType param
- Modify: `sim/silksong_sim/src/fsm_actions.hpp` — add duration lookup table

- [ ] **Step 1: Extract FreezeMomentType in bake script**

In `bake_fsm.py`, replace the FreezeMoment `pass` (around line 677-678):

```python
    elif action_name == "FreezeMoment":
        out.append(p("FreezeMomentType"))
```

- [ ] **Step 2: Add freeze duration lookup in C++**

In `fsm_actions.hpp`, replace the FreezeMoment OnEnter case (around line 674):

```cpp
    case FsmActionType::FreezeMoment: {
        // p[0] = FreezeMomentType enum value
        // Durations from GameManager.FreezeMoment (waitTime field per type)
        static constexpr float FREEZE_DURATIONS[] = {
            0.28f,  // 0: HeroDamage
            0.024f, // 1: EnemyDeath
            0.35f,  // 2: BossDeathStrike
            0.25f,  // 3: NailClashEffect
            0.35f,  // 4: AltBossDeathStrike
            0.25f,  // 5: BossStun
            0.02f,  // 6: QuickFreeze
            0.02f,  // 7: MediumFreeze (rampDown=0.05)
            0.04f,  // 8: LongFreeze (rampDown=0.05)
            0.1f,   // 9: AltFreeze (rampDown=0.1)
        };
        int type = (int)p[0];
        if (type >= 0 && type < 10)
            ctx.freezeTimer = FREEZE_DURATIONS[type];
        else
            ctx.freezeTimer = 0.1f;
        break;
    }
```

- [ ] **Step 3: Commit**

```bash
git add scripts/bake_fsm.py sim/silksong_sim/src/fsm_actions.hpp
git commit -m "$(cat <<'EOF'
fix: FreezeMoment uses per-type duration lookup instead of hardcoded 0.1s

Extracts FreezeMomentType enum from bake and maps to the correct
waitTime from GameManager.FreezeMoment (0.02s-0.35s range).
EOF
)"
```

---

## Task 8: DamageHeroDirectly Invincibility Bypass

**Why:** DamageHeroDirectly in C# forces off hero invincibility, cancels parry, and cancels downspike invuln before dealing damage. The C++ just writes a damage value. If the sim's damage pipeline checks i-frames, guaranteed-hit attacks become dodgeable.

**Files:**
- Modify: `sim/silksong_sim/src/fsm_actions.hpp` — add bypass flag to FsmActionCtx, set it in DamageHeroDirectly
- Modify: `sim/silksong_sim/src/sim.cpp` — check bypass flag when applying hero damage

- [ ] **Step 1: Add heroDamageBypass field to FsmActionCtx**

In `fsm_actions.hpp`, add to the `FsmActionCtx` struct (after `heroDamageOut`):

```cpp
    bool           &heroDamageBypass; // true = skip hero i-frame checks
```

- [ ] **Step 2: Set bypass in DamageHeroDirectly**

In `fsm_actions.hpp`, update the DamageHeroDirectly OnEnter case:

```cpp
    case FsmActionType::DamageHeroDirectly: {
        ctx.heroDamageOut = p[0];
        ctx.heroDamageBypass = true;
        break;
    }
```

- [ ] **Step 3: Wire up in sim.cpp**

In `sim.cpp`, add the bypass local and bind it in the FsmActionCtx initializer (after `heroDamageOut`):

```cpp
        bool heroDamageBypass = false;
```

In the actx initializer, add:

```cpp
            .heroDamageBypass = heroDamageBypass,
```

Then, wherever hero damage is applied (search for uses of `heroDamageOut`), use `heroDamageBypass` to skip the i-frame check:

```cpp
        if (heroDamageOut > 0.f && (heroDamageBypass || hero.invulTimer <= 0.f)) {
            // apply damage
        }
```

- [ ] **Step 4: Commit**

```bash
git add sim/silksong_sim/src/fsm_actions.hpp sim/silksong_sim/src/sim.cpp
git commit -m "$(cat <<'EOF'
fix: DamageHeroDirectly bypasses hero i-frame checks

Guaranteed-hit attacks (grabs, environmental) now set a bypass flag
that skips the invulnerability timer check, matching C# behavior
where invincibility is forced off before dealing damage.
EOF
)"
```

---

## Task 9: CheckAlertRange Timer Reset + CheckAlertRangeByName Params

**Why:** CheckAlertRange's timer never resets when the hero crosses the range boundary (C# resets it on state change). CheckAlertRangeByName only bakes 1 param but the C++ OnUpdate reads p[1]-p[4] from adjacent actions.

**Files:**
- Modify: `sim/silksong_sim/src/fsm_types.hpp` — add `alertRangeInRange` bool to FsmRuntime
- Modify: `sim/silksong_sim/src/fsm_actions.hpp` — fix timer reset logic
- Modify: `scripts/bake_fsm.py` — add missing params for CheckAlertRangeByName

- [ ] **Step 1: Add alertRangeInRange flag to FsmRuntime**

In `fsm_types.hpp`, after `alertRangeTimer` (around line 160):

```cpp
    float    alertRangeTimer;
    bool     alertRangeInRange;  // previous frame's in-range state
```

- [ ] **Step 2: Fix CheckAlertRange OnUpdate timer reset**

In `fsm_actions.hpp`, replace the `CheckAlertRange` / `CheckAlertRangeByName` OnUpdate case (around line 956):

```cpp
    case FsmActionType::CheckAlertRange:
    case FsmActionType::CheckAlertRangeByName: {
        float rangeHalfW = 6.123f;
        float rangeOffsetX = -0.46f;
        float rangeCenterX = ctx.bk.posX + rangeOffsetX;
        bool inRange = (ctx.heroX >= rangeCenterX - rangeHalfW)
                    && (ctx.heroX <= rangeCenterX + rangeHalfW);

        // Reset timer on state change (C# behavior)
        if (inRange != rt.alertRangeInRange) {
            rt.alertRangeTimer = 0.f;
            rt.alertRangeInRange = inRange;
        }

        if (inRange) {
            float delay = p[2];
            if (delay <= 0.f) {
                fsmFireEventF(rt, p[1]);
            } else {
                rt.alertRangeTimer += ctx.dt;
                if (rt.alertRangeTimer >= delay)
                    fsmFireEventF(rt, p[1]);
            }
        } else {
            float delay = p[4];
            if (delay <= 0.f) {
                fsmFireEventF(rt, p[3]);
            } else {
                rt.alertRangeTimer += ctx.dt;
                if (rt.alertRangeTimer >= delay)
                    fsmFireEventF(rt, p[3]);
            }
        }
        return false;
    }
```

- [ ] **Step 3: Add full params for CheckAlertRangeByName in bake script**

In `bake_fsm.py`, replace the `CheckAlertRangeByName` block (around line 575-576):

```python
    elif action_name == "CheckAlertRangeByName":
        out.append(p("storeResult"))
        out.append(p("sendEvent", is_event=True))
        out.append(p("InRangeDelay"))
        out.append(p("outOfRangeEvent", is_event=True))
        out.append(p("OutOfRangeDelay"))
```

This matches the param layout of CheckAlertRange: `[storeResult, InRangeEvent, InRangeDelay, OutOfRangeEvent, OutOfRangeDelay]`.

- [ ] **Step 4: Initialize alertRangeInRange in OnEnter**

In `fsm_actions.hpp`, update both CheckAlertRange and CheckAlertRangeByName OnEnter cases (around line 868-877):

```cpp
    case FsmActionType::CheckAlertRange:
    case FsmActionType::CheckAlertRangeByName: {
        rt.alertRangeTimer = 0.f;
        rt.alertRangeInRange = false;
        break;
    }
```

- [ ] **Step 5: Commit**

```bash
git add scripts/bake_fsm.py sim/silksong_sim/src/fsm_actions.hpp sim/silksong_sim/src/fsm_types.hpp
git commit -m "$(cat <<'EOF'
fix: CheckAlertRange timer resets on boundary crossing

Timer was accumulating monotonically — now resets when hero enters/exits
range, matching C# behavior. Also fixes CheckAlertRangeByName which was
reading out-of-bounds params (only 1 baked, needed 5).
EOF
)"
```

---

## Task 10: CompareHP everyFrame + RayCast2dV2 Events

**Why:** CompareHP can't run continuously (no OnUpdate handler, not in CONTINUOUS_ACTIONS). If any instance has `everyFrame=true`, HP threshold checks during long states never fire. RayCast2dV2 never fires hitEvent/noHitEvent despite having them baked.

**Files:**
- Modify: `sim/silksong_sim/src/fsm_actions.hpp` — add CompareHP OnUpdate, fire RayCast2dV2 events
- Modify: `scripts/bake_fsm.py` — add CompareHP to CONTINUOUS_ACTIONS

- [ ] **Step 1: Add CompareHP to CONTINUOUS_ACTIONS**

In `bake_fsm.py`, add `"CompareHP"` to the `CONTINUOUS_ACTIONS` set (around line 164):

```python
CONTINUOUS_ACTIONS = {
    "DecelerateXY",
    ...
    "CompareHP",
    "BoolAllTrue",
    ...
}
```

- [ ] **Step 2: Add CompareHP OnUpdate handler in C++**

In `fsm_actions.hpp`, add a case in `fsmActionOnUpdate` (inside the switch, before `default`):

```cpp
    case FsmActionType::CompareHP: {
        int32_t compareVal = fsmReadIntVar(rt, p[0]);
        if (ctx.bossHP == compareVal)      fsmFireEventF(rt, p[1]);
        else if (ctx.bossHP < compareVal)  fsmFireEventF(rt, p[2]);
        else                                fsmFireEventF(rt, p[3]);
        return false;
    }
```

- [ ] **Step 3: Fire RayCast2dV2 hitEvent/noHitEvent**

In `fsm_actions.hpp`, update the RayCast2dV2 OnEnter case (around line 828):

```cpp
    case FsmActionType::RayCast2dV2: {
        float facing = fsmFacing(ctx);
        float probeX = ctx.bk.posX + facing * p[0];
        bool wallHit = (probeX < 82.4f || probeX > 105.6f);
        fsmWriteBoolVar(rt, p[4], wallHit);
        if (wallHit)
            fsmFireEventF(rt, p[2]);  // hitEvent
        else
            fsmFireEventF(rt, p[3]);  // noHitEvent
        break;
    }
```

- [ ] **Step 4: Commit**

```bash
git add scripts/bake_fsm.py sim/silksong_sim/src/fsm_actions.hpp
git commit -m "$(cat <<'EOF'
fix: CompareHP runs continuously, RayCast2dV2 fires hit/noHit events

CompareHP now has an OnUpdate handler and is marked continuous, enabling
HP threshold checks during long states. RayCast2dV2 now fires hitEvent
and noHitEvent in addition to writing the storeDidHit bool.
EOF
)"
```

---

## Task 11: Re-bake, Rebuild, Verify

**Why:** All bake script changes require regenerating `fsm_lace_boss1.hpp`, and all C++ changes require rebuilding the sim. The `oracle_diff.py` script replays Unity traces against the sim to detect behavioral drift.

**Files:**
- Regenerate: `sim/silksong_sim/src/fsm_lace_boss1.hpp`

- [ ] **Step 1: Re-bake FSM**

```bash
cd /home/seis/code/silksong-agent
python scripts/bake_fsm.py scripts/lace_boss1_control_fsm.json \
    > sim/silksong_sim/src/fsm_lace_boss1.hpp
```

Verify the output:
```bash
# Check NaN sentinels appear for DecelerateXY None axes
grep -c "NAN" sim/silksong_sim/src/fsm_lace_boss1.hpp

# Check param count didn't change drastically
head -10 sim/silksong_sim/src/fsm_lace_boss1.hpp
```

- [ ] **Step 2: Rebuild sim**

```bash
cd sim/silksong_sim/build && ninja
```

Verify clean build with no warnings.

- [ ] **Step 3: Run oracle diff (if traces available)**

```bash
cd /home/seis/code/silksong-agent
python sim/silksong_sim/scripts/oracle_diff.py replays/*.bin 2>&1 | tail -30
```

Look for reduced drift in boss position/velocity during aerial states (gravity/kinematic fixes), correct facing after Kickoff, and correct freeze frame durations.

- [ ] **Step 4: Run benchmark to verify no performance regression**

```bash
python sim/silksong_sim/scripts/benchmark.py --num-worlds 1024 --steps 1000
```

Verify throughput is within 5% of baseline.

- [ ] **Step 5: Commit generated file**

```bash
git add sim/silksong_sim/src/fsm_lace_boss1.hpp
git commit -m "$(cat <<'EOF'
chore: re-bake FSM with all fidelity fixes

Regenerated from lace_boss1_control_fsm.json with corrected param
layouts, NaN sentinels, and new action types.
EOF
)"
```

---

## Parallelization Guide

Tasks can be dispatched to agents in parallel as follows:

| Wave | Tasks | Why parallel |
|------|-------|-------------|
| **Wave 1** | Task 1 (None sentinel) | Foundational — others may depend on NaN sentinel |
| **Wave 2** | Tasks 2, 3, 4, 5, 6, 7, 8, 9, 10 | All independent fix groups. Each touches different sections of the same files. Use worktrees or coordinate merges. |
| **Wave 3** | Task 11 (re-bake + rebuild + verify) | Depends on all prior tasks being merged |

For team dispatch with worktrees, group by file conflict risk:

- **Agent A (bake-only):** Tasks 3, 4 bake parts, 7 bake part, 9 bake part, 10 bake part
- **Agent B (C++ actions):** Tasks 2, 5 C++ parts, 7 C++ part, 8, 10 C++ part
- **Agent C (foundational):** Task 1 (both bake + C++), Task 6 (both bake + C++)
- **Agent D (integration):** Task 9 C++ part (needs fsm_types.hpp change), Task 11

Or simpler: do Task 1 first, then dispatch Tasks 2-10 as a single sequential pass through the two files (avoiding merge conflicts entirely), then Task 11.

---

## Known Issues NOT Fixed Here (future work)

These were identified in the audit but are lower priority or require more investigation:

- **Translate:** Missing `perSecond`/`everyFrame` flags (default true in C#). Current data may use non-default values.
- **EaseFloat:** Linear-only easing; missing finishEvent, speed, delay, reverse support.
- **CheckCollisionSide:** Missing velocity gating, bool variable writes, collision exit reset.
- **CheckYPosition:** Missing `activeBool` guard and `Space.Self` handling.
- **SetCollider/SetPolygonCollider:** Missing `resetOnExit` support.
- **CanHeroTakeDamage:** Simplified invuln check (i-frame timer only vs 11 C# conditions).
- **FloatCompare:** Always continuous (should respect `everyFrame` default of false per-instance).
- **Wait/WaitRandom:** Missing `realTime` flag support.
- **SetDamageHeroAmount:** Missing IsNone guard (None baked as 0 could zero damage).
