# Remaining Correctness Parity — Design Spec

**Date:** 2026-05-14  
**Goal:** Close the three remaining architectural gaps between the C++ FSM interpreter and the original C# game: animation timing, state-exit callbacks, and external FSM data.

**Non-goal:** ReceivedDamage (0 battle-state instances — dropped). Unity physics reimplementation. Hero-side fidelity.

---

## 1. Animation Timing

### Problem

38 animation actions (`Tk2dPlayAnimationWithEvents`, `Tk2dWatchAnimationEvents`, `Tk2dPlayAnimationWait`) are converted to `Wait` actions by the bake script with hardcoded durations: 0.1s for trigger events, 0.35s for complete events. Real clip durations from `assets/sprites/sprite_map.json` range from 0.033s (Downstab) to 1.5s (P2 Shift). Every attack timing in the sim is wrong.

### Data Source

`assets/sprites/sprite_map.json` contains all 102 boss animation clips:

```json
{
  "boss": {
    "clips": {
      "Idle": {"fps": 12.0, "frames": 7},
      "Combo Slash": {"fps": 24.0, "frames": 28},
      ...
    }
  }
}
```

Duration = `frames / fps`.

### Fix

The bake script (`handle_anim_event_action` function in `scripts/bake_fsm.py`) loads `assets/sprites/sprite_map.json` and builds a clip-name→duration lookup table. When converting animation actions to Wait:

1. Determine the clip name. The animation action itself may reference a clip via `clipName` or `AnimationClip` params. If not present, look for a preceding `Tk2dPlayAnimation` action in the same state that sets the clip.
2. Look up the clip duration from the sprite map.
3. For **trigger events**: the trigger fires at the clip's trigger frame (if known), or at the first frame (duration = 1/fps as a minimum). Since we don't have per-frame trigger data, use a heuristic: trigger fires at 50% of clip duration for attack clips, or fall back to the old 0.1s if the clip can't be identified.
4. For **complete events**: use the full clip duration.
5. Fallback: if clip name can't be resolved, use the current 0.35s.

The animation clip name is often not in the JSON params (the extraction didn't capture it). In that case, the bake script needs a state-name→clip-name mapping table built from contextual analysis. Each state typically has one `Tk2dPlayAnimation` or `Tk2dPlayAnimationWithEvents` that sets the clip, followed by a `Tk2dWatchAnimationEvents` that watches it.

### Approach for clip name resolution

Add a pre-pass in the bake script that scans each state's actions for `Tk2dPlayAnimation` / `Tk2dPlayAnimationWithEvents` to extract the clip name. Store in a `state_clip_map: dict[str, str]`. When `handle_anim_event_action` runs, it can look up the clip name from this map.

If the clip name is still unknown (not in the JSON params and no preceding play action), use a hardcoded `STATE_TO_CLIP` fallback table for known states.

### Files Modified

- `scripts/bake_fsm.py` — load sprite_map.json, build lookup table, use real durations in `handle_anim_event_action`

---

## 2. State-Exit Callbacks

### Problem

Three action types have C# `resetOnExit` / `resetOnStateExit` fields that undo the action's effect when the FSM exits the state:

| Action | Instances | Effect to undo |
|--------|-----------|----------------|
| SetCollider | 2 (CrossSlash, Slash Slam) | Toggle hitboxActive back |
| SetPolygonCollider | 2 (RapidSlash Loop, Stun Start) | Toggle hitboxActive back |
| SetInvincible | 3 (Counter Stance, Range Out, Range Return) | Toggle isInvincible back |

Currently the C++ has no state-exit mechanism — actions run on state entry and update, but nothing happens on state exit.

### Fix

#### Bake script changes

Extract the `resetOnExit` / `resetOnStateExit` boolean for each affected action type. Append it as an additional parameter:

- SetCollider: `[active, resetOnExit]` (currently `[active]`)
- SetPolygonCollider: `[active, resetOnExit]` (currently `[active]`)
- SetInvincible: `[Invincible, InvincibleFromDirection, resetOnStateExit]` (currently `[Invincible, InvincibleFromDirection]`)

#### Runtime state

Add to `FsmRuntime`:

```cpp
struct FsmExitAction {
    FsmActionType type;
    uint16_t paramOffset;
};
static constexpr int FSM_MAX_EXIT_ACTIONS = 8;

// Inside FsmRuntime:
FsmExitAction exitActions[FSM_MAX_EXIT_ACTIONS];
uint8_t numExitActions;
```

#### Action registration

In `fsmActionOnEnter`, when SetCollider/SetPolygonCollider/SetInvincible runs and the `resetOnExit` param is true (non-zero), register the action in `rt.exitActions[]`.

#### Exit execution

In the FSM interpreter (`fsm_interpreter.hpp`), when transitioning to a new state (after detecting a pending event and before calling `fsmActionOnEnter` for the new state), call `fsmActionsOnExit(rt, ctx)` which iterates `rt.exitActions[]` and undoes each:

- SetCollider/SetPolygonCollider: `ctx.rt.hitboxActive = !ctx.rt.hitboxActive` (toggle back)
- SetInvincible: `ctx.sc.isInvincible = !ctx.sc.isInvincible` (toggle back)

Then clear `rt.numExitActions = 0`.

### Files Modified

- `scripts/bake_fsm.py` — extract resetOnExit params
- `sim/silksong_sim/src/fsm_types.hpp` — add FsmExitAction struct and array to FsmRuntime
- `sim/silksong_sim/src/fsm_actions.hpp` — register exit actions in OnEnter, add fsmActionsOnExit function
- `sim/silksong_sim/src/fsm_interpreter.hpp` — call fsmActionsOnExit before state transition

---

## 3. GetFsmFloat (Lava Y Position)

### Problem

One `GetFsmFloat` instance in the Lava Damage state reads `$Lava Pos Y` from an external FSM. The C++ is a no-op stub, so `$Lava Pos Y` retains its initial value (likely 0.0).

### Fix

The lava Y position is fixed per arena (it doesn't change during the fight). The bake script resolves it to a constant at bake time.

#### Approach

In `scripts/bake_fsm.py`, add a `EXTERNAL_FSM_VALUES` dict that maps known `(fsmName, variableName)` pairs to constant float values:

```python
EXTERNAL_FSM_VALUES = {
    ("Lava Control", "Lava Pos Y"): 5.0,  # actual lava Y from arena data
}
```

The GetFsmFloat extraction emits the resolved constant as p[1]:

```python
elif action_name == "GetFsmFloat":
    out.append(p_var("storeValue"))  # p[0] = target variable
    # Resolve external FSM value to constant
    fsm_name = params.get("fsmName", "")
    var_name = params.get("variableName", "")
    value = EXTERNAL_FSM_VALUES.get((fsm_name, var_name), 0.0)
    out.append(float(value))  # p[1] = resolved constant
```

The C++ `GetFsmFloat` OnEnter writes the constant to the target variable:

```cpp
case FsmActionType::GetFsmFloat: {
    fsmWriteFloatVar(rt, p[0], p[1]);
    break;
}
```

#### Determining the actual lava Y value

Check the arena collider data or the FSM JSON for the lava position. The value may also be derivable from the ground Y position (7.3) minus some offset.

### Files Modified

- `scripts/bake_fsm.py` — add EXTERNAL_FSM_VALUES, update GetFsmFloat extraction
- `sim/silksong_sim/src/fsm_actions.hpp` — implement GetFsmFloat OnEnter

---

## Verification

After all changes:

1. Re-bake: `python scripts/bake_fsm.py scripts/lace_boss1_control_fsm.json > sim/silksong_sim/src/fsm_lace_boss1.hpp`
2. Rebuild: `cd sim/silksong_sim/build && ninja`
3. Spot-check: Verify animation Wait durations in the baked output match sprite_map.json clips
4. Benchmark: throughput within 5% of baseline

## Success Criteria

- All 38 animation→Wait conversions use real clip durations from sprite_map.json
- SetCollider, SetPolygonCollider, SetInvincible resetOnExit works correctly on state transitions
- GetFsmFloat writes the correct lava Y position to `$Lava Pos Y`
- Sim builds and runs without regressions
