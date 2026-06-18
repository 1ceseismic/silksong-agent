# Remaining Correctness Parity — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close three remaining architectural gaps: real animation clip durations (38 instances), state-exit callbacks for resetOnExit (7 instances), and GetFsmFloat for lava Y position (1 instance).

**Architecture:** Task 1 replaces hardcoded animation timings with real clip durations from `sprite_map.json`. Task 2 adds state-exit callback plumbing to the FSM interpreter. Task 3 implements GetFsmFloat with a baked constant. Task 4 re-bakes and rebuilds.

**Tech Stack:** Python 3 (bake script), C++17 (sim interpreter)

---

## File Map

| File | Changes |
|------|---------|
| `scripts/bake_fsm.py` | Load sprite_map.json, use real durations in handle_anim_event_action; extract resetOnExit params; implement GetFsmFloat extraction |
| `assets/sprites/sprite_map.json` | Read-only — animation clip data source |
| `sim/silksong_sim/src/fsm_types.hpp` | Add FsmExitAction struct and exit action array to FsmRuntime |
| `sim/silksong_sim/src/fsm_actions.hpp` | Register exit actions in OnEnter; add fsmActionsOnExit; implement GetFsmFloat |
| `sim/silksong_sim/src/fsm_interpreter.hpp` | Call fsmActionsOnExit before state transitions |
| `sim/silksong_sim/src/fsm_lace_boss1.hpp` | Regenerated |

---

### Task 1: Real Animation Clip Durations

**Files:**
- Modify: `scripts/bake_fsm.py`

- [ ] **Step 1: Add sprite map loading and state-to-clip mapping**

At the top of `bake_fsm.py` (after the imports, around line 24), add:

```python
from pathlib import Path

SPRITE_MAP_PATH = Path(__file__).parent.parent / "assets" / "sprites" / "sprite_map.json"
```

After the `ANIM_EVENT_ACTIONS` set (around line 198), add the state-to-clip mapping and a duration resolver:

```python
STATE_TO_CLIP: dict[str, str] = {
    "Idle": "Idle",
    "Charge Recover": "Charge Recover",
    "J Slash 1": "Rising Slash",
    "J Slash 2": "Rising Slash",
    "J Slash 3": "Rising Slash",
    "J Slash 4": "Rising Slash",
    "Downstab Antic": "Downstab Antic",
    "Downstab Land": "Downstab End",
    "Counter Antic": "Counter Antic",
    "Counter End": "Counter End",
    "Counter Hit": "Counter Hit",
    "RapidSlash Charge": "RapidSlash Charge",
    "RapidSlash End": "RapidSlash End",
    "ComboSlash 1": "Combo Strike 1",
    "ComboSlash 2": "Combo Strike 2",
    "ComboSlash 3": "Combo Strike 1",
    "ComboSlash 4": "Combo Strike 2",
    "ComboSlash 5": "Combo Slash",
    "Evade": "Evade",
    "Evade Recover": "Evade",
    "Hop Antic": "Jump Antic",
    "Hop": "Forward Hop",
    "Hop Recover": "Land",
    "Stun Recover": "Stun Recover",
    "Slash Slam": "Downstab Strike",
    "Multihit Slash": "MultiHit Slash",
    "Pose Swish": "Pose Swish",
    "Pose Swish 2": "Pose Swish",
    "Pose Swish 3": "Pose Swish",
    "Collide Cancel": "Evade",
    "Evade 2": "Evade",
    "Evade Recover 2": "Evade",
    "Swish Block": "Swish Block",
    "Sing Antic": "Sing",
    "Sing End": "Sing End",
    "Lava Tele Out": "Tele Out",
    "Tele In": "Tele In",
    "Wallcling": "Wall Bounce",
}


def _load_clip_durations() -> dict[str, float]:
    """Load boss animation clip durations from sprite_map.json."""
    if not SPRITE_MAP_PATH.exists():
        print(f"WARNING: {SPRITE_MAP_PATH} not found, using fallback durations",
              file=sys.stderr)
        return {}
    with open(SPRITE_MAP_PATH) as f:
        data = json.load(f)
    clips = data.get("boss", {}).get("clips", {})
    durations = {}
    for name, info in clips.items():
        fps = info.get("fps", 12.0)
        frames = info.get("frames", 1)
        durations[name] = frames / fps if fps > 0 else 0.35
    return durations


CLIP_DURATIONS: dict[str, float] = _load_clip_durations()
```

- [ ] **Step 2: Update handle_anim_event_action to use real durations**

Find the `handle_anim_event_action` function (around line 778). Replace the hardcoded duration logic.

Currently:
```python
    if trigger_event and not complete_event:
        out.append(0.1)  # time
```

Replace the entire duration section (from `out: list[float] = []` onward) with:

```python
    out: list[float] = []

    # Resolve clip duration from state-to-clip mapping
    clip_name = STATE_TO_CLIP.get(state_name)
    clip_dur = CLIP_DURATIONS.get(clip_name, 0.35) if clip_name else 0.35

    if trigger_event and not complete_event:
        # Trigger fires partway through the clip.
        # Heuristic: 50% of clip duration for attack triggers.
        out.append(clip_dur * 0.5)
        out.append(float(event_table.get_or_add(trigger_event)))
        return "Wait", out, False
    elif complete_event and not trigger_event:
        out.append(clip_dur)
        out.append(float(event_table.get_or_add(complete_event)))
        return "Wait", out, False
    elif trigger_event and complete_event:
        # Both: fire trigger at 50% of clip
        out.append(clip_dur * 0.5)
        out.append(float(event_table.get_or_add(trigger_event)))
        return "Wait", out, False

    return None
```

Note: the function signature needs to accept `state_name`. Update the signature:

```python
def handle_anim_event_action(
    json_name: str,
    params: dict[str, Any],
    event_table: EventTable,
    enabled: bool,
    state_name: str = "",
) -> tuple[str, list[float], bool] | None:
```

- [ ] **Step 3: Pass state_name to handle_anim_event_action**

In the `main()` function, find where `handle_anim_event_action` is called (around line 904). Add `state_name=s["name"]`:

```python
            anim_result = handle_anim_event_action(
                json_name, params, event_table, enabled,
                state_name=s["name"],
            )
```

- [ ] **Step 4: Verify bake output has real durations**

```bash
python scripts/bake_fsm.py scripts/lace_boss1_control_fsm.json > /tmp/test_bake.hpp 2>&1
# Check a known state — Charge Recover should be ~0.167s, not 0.35s
grep -A2 "Charge Recover" /tmp/test_bake.hpp | head -5
# Check the PARAMS array for non-0.35 durations
grep "0.167f\|0.278f\|0.500f\|0.467f\|0.733f" /tmp/test_bake.hpp | head -10
```

- [ ] **Step 5: Commit**

```bash
git add scripts/bake_fsm.py
git commit -m "fix: use real animation clip durations from sprite_map.json

Replaces hardcoded 0.1s/0.35s animation wait times with actual clip
durations (frames/fps) from assets/sprites/sprite_map.json. Maps
38 animation states to their clips via STATE_TO_CLIP table."
```

---

### Task 2: State-Exit Callbacks

**Files:**
- Modify: `sim/silksong_sim/src/fsm_types.hpp`
- Modify: `sim/silksong_sim/src/fsm_actions.hpp`
- Modify: `sim/silksong_sim/src/fsm_interpreter.hpp`
- Modify: `scripts/bake_fsm.py`

- [ ] **Step 1: Add FsmExitAction struct and array to FsmRuntime**

In `sim/silksong_sim/src/fsm_types.hpp`, after the `FsmVarSlot` struct (around line 80), add:

```cpp
struct FsmExitAction {
    FsmActionType type;
    uint16_t paramOffset;
};
constexpr int FSM_MAX_EXIT_ACTIONS = 8;
```

In the `FsmRuntime` struct, after `collisionSidePrev` (near the end), add:

```cpp
    FsmExitAction exitActions[FSM_MAX_EXIT_ACTIONS];
    uint8_t numExitActions;
```

- [ ] **Step 2: Extract resetOnExit params in bake script**

In `scripts/bake_fsm.py`, update the SetCollider extraction (around line 747):

```python
    elif action_name == "SetCollider":
        out.append(p("active"))
        out.append(p("resetOnExit"))
```

Update SetPolygonCollider (around line 749):

```python
    elif action_name == "SetPolygonCollider":
        out.append(p("active"))
        out.append(p("resetOnExit"))
```

Update SetInvincible (around line 594). Add `resetOnStateExit` as a third param:

```python
    elif action_name == "SetInvincible":
        out.append(p("Invincible"))
        out.append(p_var("InvincibleFromDirection"))
        out.append(p("resetOnStateExit"))
```

- [ ] **Step 3: Add fsmActionsOnExit function in fsm_actions.hpp**

At the end of `fsm_actions.hpp` (before the closing `} // namespace silksong`), add:

```cpp
static inline void fsmActionsOnExit(FsmRuntime &rt, FsmActionCtx &ctx)
{
    for (int i = 0; i < rt.numExitActions; ++i) {
        const FsmExitAction &ea = rt.exitActions[i];
        switch (ea.type) {
        case FsmActionType::SetCollider:
        case FsmActionType::SetPolygonCollider:
            ctx.rt.hitboxActive = !ctx.rt.hitboxActive;
            break;
        case FsmActionType::SetInvincible:
            ctx.sc.isInvincible = !ctx.sc.isInvincible;
            break;
        default:
            break;
        }
    }
    rt.numExitActions = 0;
}
```

- [ ] **Step 4: Register exit actions in OnEnter handlers**

In `fsm_actions.hpp`, update the SetCollider OnEnter case (around line 717). After setting hitboxActive, check p[1] (resetOnExit) and register:

```cpp
    case FsmActionType::SetCollider: {
        ctx.rt.hitboxActive = (p[0] != 0.f);
        if (p[1] != 0.f && rt.numExitActions < FSM_MAX_EXIT_ACTIONS) {
            rt.exitActions[rt.numExitActions++] = {act.type, act.paramOffset};
        }
        break;
    }
```

Update SetPolygonCollider similarly (around line 723):

```cpp
    case FsmActionType::SetPolygonCollider: {
        ctx.rt.hitboxActive = (p[0] != 0.f);
        if (p[1] != 0.f && rt.numExitActions < FSM_MAX_EXIT_ACTIONS) {
            rt.exitActions[rt.numExitActions++] = {act.type, act.paramOffset};
        }
        break;
    }
```

Update SetInvincible (around line 650). p[2] is now resetOnStateExit:

```cpp
    case FsmActionType::SetInvincible: {
        ctx.sc.isInvincible = (p[0] != 0.f);
        if (p[2] != 0.f && rt.numExitActions < FSM_MAX_EXIT_ACTIONS) {
            rt.exitActions[rt.numExitActions++] = {act.type, act.paramOffset};
        }
        break;
    }
```

- [ ] **Step 5: Call fsmActionsOnExit in the interpreter before state transitions**

In `sim/silksong_sim/src/fsm_interpreter.hpp`, find the `fsmEnterState` function (around line 101). At the top of the for-loop body, before `rt.currentState = stateIdx`, add:

```cpp
        // Run exit actions from the previous state
        fsmActionsOnExit(rt, ctx);
```

Also in `fsmProcessEvent` (around line 193), before calling `fsmEnterState`:

```cpp
    // Run exit actions before leaving current state
    fsmActionsOnExit(rt, ctx);
    fsmEnterState(def, ctx, tr.targetState);
```

Wait — `fsmEnterState` is also called from `fsmProcessEvent`, and `fsmEnterState` itself loops for chain transitions. The exit should happen once per state exit. The cleanest place is at the top of `fsmEnterState`'s loop, before entering the new state. The first call enters from the current state; subsequent iterations enter from intermediate chain states.

In `fsmEnterState`, the exit actions call should be at the start of each loop iteration (around line 107):

```cpp
    for (int chain = 0; chain < MAX_CHAIN; ++chain) {
        fsmActionsOnExit(rt, ctx);
        rt.currentState = stateIdx;
```

This handles both the initial transition and chain transitions. `fsmActionsOnExit` clears the array after executing, so calling it when there are no exit actions is a no-op.

- [ ] **Step 6: Initialize numExitActions in fsmInit**

In `fsm_interpreter.hpp`, in `fsmInit` (around line 86), add:

```cpp
    rt.numExitActions = 0;
```

- [ ] **Step 7: Commit**

```bash
git add sim/silksong_sim/src/fsm_types.hpp sim/silksong_sim/src/fsm_actions.hpp \
      sim/silksong_sim/src/fsm_interpreter.hpp scripts/bake_fsm.py
git commit -m "feat: state-exit callbacks for SetCollider/SetPolygonCollider/SetInvincible

Adds FsmExitAction tracking to FsmRuntime. Actions with resetOnExit
register themselves on enter; fsmActionsOnExit undoes their effect
before each state transition. Bake extracts resetOnExit params."
```

---

### Task 3: GetFsmFloat (Lava Y Position)

**Files:**
- Modify: `scripts/bake_fsm.py`
- Modify: `sim/silksong_sim/src/fsm_actions.hpp`

- [ ] **Step 1: Add external FSM value resolution to bake script**

In `scripts/bake_fsm.py`, after `STATE_TO_CLIP` (or wherever convenient, before `extract_action_params`), add:

```python
EXTERNAL_FSM_VALUES: dict[tuple[str, str], float] = {
    ("Lava Control", "Lava Pos Y"): -0.5,
}
```

The value -0.5 comes from `consts.hpp` line 108: `bossLavaY = -0.5f`.

Note: the FSM JSON stores `fsmName` and `variableName` as objects `{"x": 0.0, "y": 0.0}` (Vector2 placeholders, not actual strings). The actual FSM name and variable name were lost during extraction. Since there's only one GetFsmFloat instance, we hardcode the resolution.

- [ ] **Step 2: Update GetFsmFloat extraction**

In `scripts/bake_fsm.py`, find the GetFsmFloat extraction (around line 759). Replace:

```python
    elif action_name == "GetFsmFloat":
        out.append(p_var("storeValue"))
```

With:

```python
    elif action_name == "GetFsmFloat":
        out.append(p_var("storeValue"))
        # Resolve external FSM float to a baked constant.
        # The FSM JSON lost the fsmName/variableName strings during extraction.
        # For the single known instance (Lava Damage reads Lava Pos Y),
        # we hardcode the value from consts.hpp bossLavaY.
        out.append(-0.5)  # bossLavaY from consts.hpp
```

- [ ] **Step 3: Implement GetFsmFloat in C++**

In `sim/silksong_sim/src/fsm_actions.hpp`, find the GetFsmFloat case in `fsmActionOnEnter` (currently grouped with noops around line 893). Replace the noop with:

```cpp
    case FsmActionType::GetFsmFloat: {
        // p[0] = target variable ref, p[1] = resolved constant value
        fsmWriteFloatVar(rt, p[0], p[1]);
        break;
    }
```

- [ ] **Step 4: Commit**

```bash
git add scripts/bake_fsm.py sim/silksong_sim/src/fsm_actions.hpp
git commit -m "fix: GetFsmFloat writes baked lava Y position to target variable

The single GetFsmFloat instance reads Lava Pos Y from an external FSM.
Since the value is constant per arena (-0.5), the bake resolves it to
a literal and the C++ writes it to the target float variable."
```

---

### Task 4: Re-bake, Rebuild, Verify

**Files:**
- Regenerate: `sim/silksong_sim/src/fsm_lace_boss1.hpp`

- [ ] **Step 1: Re-bake FSM**

```bash
python scripts/bake_fsm.py scripts/lace_boss1_control_fsm.json \
    > sim/silksong_sim/src/fsm_lace_boss1.hpp
```

- [ ] **Step 2: Verify animation durations in baked output**

```bash
# Spot-check: Charge Recover should be ~0.167s (was 0.35s)
# J Slash states should be ~0.139s trigger (0.278 * 0.5) (was 0.1s)
# Evade should be ~0.233s trigger (0.467 * 0.5) (was 0.1s)
python3 -c "
import json
with open('assets/sprites/sprite_map.json') as f:
    sm = json.load(f)
clips = sm['boss']['clips']
print('Expected durations:')
for state, clip in [('Charge Recover', 'Charge Recover'), ('J Slash 1', 'Rising Slash'), 
                     ('Evade', 'Evade'), ('Counter Hit', 'Counter Hit')]:
    info = clips[clip]
    dur = info['frames'] / info['fps']
    print(f'  {state}: complete={dur:.3f}s trigger={dur*0.5:.3f}s')
"
```

- [ ] **Step 3: Verify resetOnExit params are baked**

```bash
# SetCollider should now have 2 params instead of 1
# SetInvincible should now have 3 params instead of 2
head -12 sim/silksong_sim/src/fsm_lace_boss1.hpp
```

Check NUM_PARAMS is ≤ 800.

- [ ] **Step 4: Rebuild sim**

```bash
cd sim/silksong_sim/build && ninja
```

Must compile with zero errors.

- [ ] **Step 5: Run benchmark**

```bash
python sim/silksong_sim/scripts/benchmark.py --num-worlds 1024 --steps 1000
```

Throughput must be within 5% of baseline.

- [ ] **Step 6: Commit generated file**

```bash
git add sim/silksong_sim/src/fsm_lace_boss1.hpp
git commit -m "chore: re-bake FSM with real animation durations, exit callbacks, lava Y"
```

---

## Parallelization

Tasks 1, 2, and 3 are independent — they touch different sections of the same files. Sequential execution is safest to avoid merge conflicts, but Tasks 1 and 3 could run in parallel (Task 1 modifies handle_anim_event_action, Task 3 modifies GetFsmFloat extraction — different code regions in bake_fsm.py).

Task 4 depends on all of Tasks 1-3.
