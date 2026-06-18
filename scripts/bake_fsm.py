#!/usr/bin/env python3
"""Bake a PlayMaker FSM JSON into a C++ constexpr header for the sim.

Reads lace_boss1_control_fsm.json and outputs a header with:
  - constexpr FsmStateDef STATES[]
  - constexpr FsmActionDef ACTIONS[]
  - constexpr FsmTransitionDef TRANSITIONS[]
  - constexpr float PARAMS[]
  - Event enum, variable slot mappings, initial values
  - NUM_STATES, start state index, global transitions

Usage:
    python scripts/bake_fsm.py scripts/lace_boss1_control_fsm.json \
        > sim/silksong_sim/src/fsm_lace_boss1.hpp
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SPRITE_MAP_PATH = Path(__file__).parent.parent / "assets" / "sprites" / "sprite_map.json"

SKIP_STATES = {
    "Init",
    "Pause",
    "Dormant",
    "Encountered?",
    "Take Control",
    "Scene Start",
    "Convo 1",
    "Convo 2",
    "Convo 3",
    "Convo 4",
    "Start Battle",
    "End Dialogue",
    "End Dialogue 2",
    "Refight",
    "Location Check",
    "Grotto Fight",
    "Take Control 2",
    "Wait 2",
    "Met in Docks?",
    "Grotto Meet 1",
    "Grotto Meet 2",
    "Grotto Meet 3",
    "Grotto Remeet 1",
    "Grotto Remeet 2",
    "Grotto Remeet 3",
    "Grotto Refight Setup",
    "Get Up Start",
    "Get Up Start 2",
    "Grotto Refight",
    "Wait",
    "Wait Shorter",
    "Conduct End",
    "Turn To Idle",
    "Take Control New",
    "To Idle",
    "Capture Hero",
    "Location Check 2",
    "Capture Hero 2",
    "Hero Turn",
    "Wait Lace Anim",
    "Dormant Block",
    "Block Voice",
    "Dormant Blocked Idle",
    "Use Wall Range?",
}

GAMEPLAY_ACTIONS: dict[str, str] = {
    "SetVelocityByScale": "SetVelocityByScale",
    "SetVelocity2d": "SetVelocity2d",
    "DecelerateXY": "DecelerateXY",
    "DecelerateV2": "DecelerateXY",  # map to same type: DecelerateV2 uses single decel for both axes
    "Wait": "Wait",
    "WaitRandom": "WaitRandom",
    "NextFrameEvent": "NextFrameEvent",
    "SetIsKinematic2d": "SetIsKinematic2d",
    "SetGravity2dScale": "SetGravity2dScale",
    "SetPosition2d": "SetPosition2d",
    "SetPosition": "SetPosition2d",  # SetPosition with x,y,z -> treat as SetPosition2d
    "Translate": "Translate",
    "ClampPosition": "ClampPosition",
    "AnimatePositionTo": "AnimatePositionTo",
    "FaceObjectV2": "FaceObjectV2",
    "FaceObjectV4": "FaceObjectV4",
    "FlipScale": "FlipScale",
    "SetBoolValue": "SetBoolValue",
    "SetFloatValue": "SetFloatValue",
    "SetIntValue": "SetIntValue",
    "BoolTest": "BoolTest",
    "BoolTestMulti": "BoolTestMulti",
    "BoolAllTrue": "BoolAllTrue",
    "FloatCompare": "FloatCompare",
    "FloatTestToBool": "FloatTestToBool",
    "IntCompare": "IntCompare",
    "IntAdd": "IntAdd",
    "FloatAdd": "FloatAdd",
    "FloatMultiply": "FloatMultiply",
    "FloatClamp": "FloatClamp",
    "FloatInRange": "FloatInRange",
    "RandomFloat": "RandomFloat",
    "RandomInt": "RandomInt",
    "MultiplyIntByFloat": "MultiplyIntByFloat",
    "EaseFloat": "EaseFloat",
    "GetDistance": "GetDistance",
    "GetXDistance": "GetXDistance",
    "GetSelfPosition": "GetSelfPosition",
    "GetPosition2d": "GetPosition2d",
    "GetPosition": "GetPosition2d",  # GetPosition with x,y,z -> store x,y
    "GetScale": "GetScale",
    "SetDamageHeroAmount": "SetDamageHeroAmount",
    "SetRecoilSpeed": "SetRecoilSpeed",
    "SetRecoilBlocked": "SetRecoilBlocked",
    "SetSpecialDeath": "SetSpecialDeath",
    "SetInvincible": "SetInvincible",
    "SubtractHP": "SubtractHP",
    "CompareHP": "CompareHP",
    "GetHP": "GetHP",
    "CheckAlertRange": "CheckAlertRange",
    "CheckAlertRangeByName": "CheckAlertRangeByName",
    "CheckHeroPerformanceRegionV2": "CheckHeroPerformanceRegionV2",
    "CheckHeroPerformanceRegion": "CheckHeroPerformanceRegionV2",  # map v1 -> v2
    "SendEvent": "SendEvent",
    "SendEventByName": "SendEventByName",
    "SendEventByNameV2": "SendEventByNameV2",
    "SendEventByScale": "SendEventByScale",
    "SendRandomEvent": "SendRandomEvent",
    "SendRandomEventV3": "SendRandomEventV3",
    "FreezeMoment": "FreezeMoment",
    "DamageHeroDirectly": "DamageHeroDirectly",
    "CanHeroTakeDamage": "CanHeroTakeDamage",
    "RayCast2dV2": "RayCast2dV2",
    "CheckCollisionSide": "CheckCollisionSide",
    "CheckCollisionSideEnter": "CheckCollisionSideEnter",
    "CheckXPosition": "CheckXPosition",
    "CheckYPosition": "CheckYPosition",
    "CheckYPositionV2": "CheckYPositionV2",
    "CheckIsCharacterGrounded": "CheckIsCharacterGrounded",
    "CheckTargetDirection": "CheckTargetDirection",
    "SetCollider": "SetCollider",
    "SetPolygonCollider": "SetPolygonCollider",
    "SetStringValue": "SetStringValue",
    "GetFsmFloat": "GetFsmFloat",
    "PreventInvincibleEffect": "PreventInvincibleEffect",
    "ReceivedDamage": "ReceivedDamage",
    "SetHitEffectOrigin": "SetHitEffectOrigin",
    "Trigger2dEventLayer": "Noop",  # collision detection handled externally
    "EnemySingControl": "Noop",  # sing animation/audio control
    "SetScale": "SetScale",
    "SetHitboxGeometry": "SetHitboxGeometry",
}

# Actions that run continuously (have OnUpdate behavior)
CONTINUOUS_ACTIONS = {
    "DecelerateXY",
    "DecelerateV2",
    "Translate",
    "Wait",
    "WaitRandom",
    "NextFrameEvent",
    "AnimatePositionTo",
    "EaseFloat",
    "CheckAlertRange",
    "CheckAlertRangeByName",
    "CheckHeroPerformanceRegionV2",
    "CheckHeroPerformanceRegion",
    "FloatAdd",
    "GetDistance",
    "GetXDistance",
    "CheckCollisionSide",
    "CheckCollisionSideEnter",
    "CheckIsCharacterGrounded",
    "CheckTargetDirection",
    "CheckXPosition",
    "CheckYPosition",
    "CheckYPositionV2",
    "CompareHP",
    "RayCast2dV2",
    "BoolAllTrue",
    "BoolTestMulti",
    "Tk2dWatchAnimationEvents",
    "Tk2dPlayAnimationWithEvents",
}

# Animation actions that fire events (we preserve the event-firing behavior)
ANIM_EVENT_ACTIONS = {
    "Tk2dWatchAnimationEvents",
    "Tk2dPlayAnimationWithEvents",
    "Tk2dPlayAnimationWait",
}

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


def _load_clip_durations() -> dict[str, tuple[float, float]]:
    """Load boss animation clip durations and trigger times from sprite_map.json.

    Returns dict mapping clip name -> (full_duration, trigger_time).
    trigger_time is the time of the first trigger frame, or duration*0.5 if none.
    """
    if not SPRITE_MAP_PATH.exists():
        print(f"WARNING: {SPRITE_MAP_PATH} not found, using fallback durations",
              file=sys.stderr)
        return {}
    with open(SPRITE_MAP_PATH) as f:
        data = json.load(f)
    clips = data.get("boss", {}).get("clips", {})
    result = {}
    for name, info in clips.items():
        fps = info.get("fps", 12.0)
        frames = info.get("frames", 1)
        dur = frames / fps if fps > 0 else 0.35
        trig_frame = info.get("triggerFrame")
        if trig_frame is not None:
            trig_time = trig_frame / fps if fps > 0 else dur * 0.5
        else:
            trig_time = dur * 0.5
        result[name] = (dur, trig_time)
    return result


CLIP_DURATIONS: dict[str, tuple[float, float]] = _load_clip_durations()

VAR_REF_OFFSET = 10000.0
# Event "none" sentinel
EVENT_NONE = 255
# Sentinel for FsmFloat fields whose C# Reset() sets UseVariable=true (None).
# Baked as NaN so the C++ interpreter can distinguish "leave unchanged" from 0.
NONE_SENTINEL = float('nan')


@dataclass
class VarTable:
    """Track FSM variable definitions and assign slot indices."""

    float_vars: list[tuple[str, float]] = field(default_factory=list)
    int_vars: list[tuple[str, int]] = field(default_factory=list)
    bool_vars: list[tuple[str, bool]] = field(default_factory=list)
    string_vars: list[tuple[str, str]] = field(default_factory=list)
    _name_to_slot: dict[str, tuple[int, int]] = field(default_factory=dict)
    # type codes: 0=float, 1=int, 2=bool, 3=string

    def add_float(self, name: str, val: float) -> int:
        idx = len(self.float_vars)
        self.float_vars.append((name, val))
        self._name_to_slot[name] = (0, idx)
        return idx

    def add_int(self, name: str, val: int) -> int:
        idx = len(self.int_vars)
        self.int_vars.append((name, val))
        self._name_to_slot[name] = (1, idx)
        return idx

    def add_bool(self, name: str, val: bool) -> int:
        idx = len(self.bool_vars)
        self.bool_vars.append((name, val))
        self._name_to_slot[name] = (2, idx)
        return idx

    def add_string(self, name: str, val: str) -> int:
        idx = len(self.string_vars)
        self.string_vars.append((name, val))
        self._name_to_slot[name] = (3, idx)
        return idx

    def resolve(self, name: str) -> tuple[int, int]:
        """Return (type, index) for a variable name."""
        return self._name_to_slot[name]

    def encode_ref(self, name: str) -> float:
        """Encode a variable reference as a float.

        Layout: VAR_REF_OFFSET + type*256 + index
        This lets the interpreter distinguish refs from literal values.
        """
        typ, idx = self.resolve(name)
        return VAR_REF_OFFSET + typ * 256.0 + idx

    def has(self, name: str) -> bool:
        return name in self._name_to_slot


@dataclass
class EventTable:
    """Map event names to uint8 IDs."""

    _events: dict[str, int] = field(default_factory=dict)
    _next_id: int = 0

    def get_or_add(self, name: str) -> int:
        if not name:
            return EVENT_NONE
        if name not in self._events:
            self._events[name] = self._next_id
            self._next_id += 1
        return self._events[name]

    def items(self) -> list[tuple[str, int]]:
        return sorted(self._events.items(), key=lambda x: x[1])

    def __len__(self) -> int:
        return len(self._events)


def resolve_param_value(
    val: Any, var_table: VarTable, event_table: EventTable, *, is_event: bool = False
) -> float:
    """Convert a param value to a float for the params array.

    - Variable references "$Foo" -> encoded float with VAR_REF_OFFSET
    - Event name strings -> event ID as float
    - Booleans -> 0.0 / 1.0
    - Numbers -> as-is
    - Dicts (Vector3 etc) -> skip (handled specially)
    - Empty strings -> EVENT_NONE if is_event, else 0.0
    """
    if isinstance(val, str):
        if val.startswith("$"):
            var_name = val[1:]
            if var_table.has(var_name):
                return var_table.encode_ref(var_name)
            # Unknown variable: encode as 0 with a warning
            print(f"WARNING: unknown variable reference '{val}'", file=sys.stderr)
            return 0.0
        if is_event:
            if not val:
                return float(EVENT_NONE)
            return float(event_table.get_or_add(val))
        # Non-event string: treat as 0
        return 0.0
    if isinstance(val, bool):
        return 1.0 if val else 0.0
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, dict):
        # Vector3/Vector2: handled by caller
        return 0.0
    return 0.0


# BoolAllTrue fixup: the FSM JSON doesn't include the boolVariables array,
# so we hardcode the known bool var names per (state_name, occurrence_index).
# occurrence_index counts BoolAllTrue actions within a single state (0-based).
BOOL_ALL_TRUE_FIXUP: dict[tuple[str, int], list[str]] = {
    ("Idle", 0): ["$Counter Range", "$Counter Ready"],
    ("Downstab", 0): ["$Wall Ahead", "$Not Above Hero"],
    ("Downstab", 1): ["$Below Ground"],
}

# BoolTestMulti fixup: the FSM JSON doesn't include the boolVariables/boolStates
# arrays, so we hardcode the known pairs per (state_name, occurrence_index).
# BoolTestMulti compares boolVariables[i] == boolStates[i] for all i.
# All match → trueEvent, any mismatch → falseEvent.
BOOL_TEST_MULTI_FIXUP: dict[tuple[str, int], tuple[list[str], list[str]]] = {
    # (state_name, occurrence_index): ([boolVariables], [boolStates])
    ("Keep Evading?", 0): (["$Hero Is Right"], ["$Lace Is Right"]),
    ("Keep Evading?", 1): (["$Hero Is Right"], ["$Lace Is Right"]),
    ("CrossSlash Aim", 0): (["$Right Side"], ["$Facing Right"]),
    ("CrossSlash Aim", 1): (["$Right Side"], ["$Facing Right"]),
}

# Attack hitbox geometry extracted from scene colliders (arena_colliders.json).
# Maps state name -> (halfW, halfH, offsetX, offsetY, activate).
# offsetX is in facing direction (positive = forward).
# These replace the noop'd ActivateGameObject actions.
ATTACK_HITBOX_GEOMETRY: dict[str, tuple[float, float, float, float, float]] = {
    "Charge":            (1.14, 0.77, 1.85, -0.65, 1.0),
    "ComboSlash 1":      (2.96, 1.83, 1.08,  0.69, 1.0),
    "ComboSlash 2":      (3.09, 1.42, 0.58,  0.56, 1.0),
    "ComboSlash 3":      (2.96, 1.83, 1.08,  0.69, 1.0),
    "ComboSlash 4":      (3.09, 1.42, 0.58,  0.56, 1.0),
    "ComboSlash 5":      (2.96, 1.83, 1.08,  0.69, 1.0),
    "J Slash 1":         (1.74, 2.37, 0.47, -0.59, 1.0),
    "J Slash 2":         (1.74, 2.37, 0.47, -0.59, 1.0),
    "J Slash 3":         (1.74, 2.37, 0.47, -0.59, 1.0),
    "J Slash 4":         (2.19, 1.44, -0.02, 1.34, 1.0),
    "Downstab":          (0.74, 1.03, 0.87, -0.98, 1.0),
    "Counter Hit":       (1.74, 2.37, 0.47, -0.59, 1.0),
    "RapidSlash Loop":   (1.79, 1.03, 0.24,  0.59, 1.0),
    "Slash Slam":        (0.74, 1.03, 0.87, -0.98, 1.0),
    "Multihit Slash":    (2.86, 1.20, 2.85, -0.10, 1.0),
    "Collide To Multihit": (2.86, 1.20, 2.85, -0.10, 1.0),
    "Multihitting":      (2.86, 1.20, 2.85, -0.10, 1.0),
    "Pose Swish":        (1.79, 1.03, 0.24,  0.59, 1.0),
    "Pose Swish 2":      (1.79, 1.03, 0.24,  0.59, 1.0),
    "Pose Swish 3":      (1.79, 1.03, 0.24,  0.59, 1.0),
    "CrossSlash":        (2.19, 1.44, 0.0,   0.0,  1.0),
    "CrossSlash Antic":  (0.0,  0.0,  0.0,   0.0,  0.0),
}

# States that deactivate all hitboxes (Stun Start deactivates everything)
HITBOX_DEACTIVATE_STATES = {"Stun Start", "Idle", "Charge Antic", "Charge Recover",
    "Evade", "Evade 2", "Evade Recover", "Evade Recover 2", "Hop Antic", "Hop",
    "Hop Recover", "Range Out", "Range Return", "Downstab Antic", "Downstab Land",
    "Counter Antic", "Counter End", "Counter Stance", "RapidSlash Charge",
    "RapidSlash End", "Stun Recover", "Pose", "Pose Lean", "Pose Upright",
    "Sing Antic", "Sing End", "Lava Damage", "Lava Hop", "Lava Tele Out",
    "Lava End", "Tele In", "Wallcling", "Death Pose", "J Slash Antic",
    "Swish Block", "CS Evade", "CS Evade Cancel", "Collide Cancel",
    "Damage Recover", "Trap Stun"}


def extract_action_params(
    action_name: str,
    json_action_name: str,
    params: dict[str, Any],
    var_table: VarTable,
    event_table: EventTable,
    enabled: bool,
) -> tuple[list[float], bool]:
    """Extract params for an action into a flat float list.

    Returns (param_floats, is_continuous).

    The param layout per action type is the contract between this script and
    fsm_actions.hpp. Every param from the JSON is preserved.
    """
    out: list[float] = []
    is_cont = json_action_name in CONTINUOUS_ACTIONS

    def p(key: str, *, is_event: bool = False) -> float:
        v = params.get(key, 0.0 if not is_event else "")
        return resolve_param_value(v, var_table, event_table, is_event=is_event)

    def p_var(key: str) -> float:
        """Resolve a param that is expected to be a variable reference."""
        v = params.get(key)
        if isinstance(v, str) and v.startswith("$"):
            return var_table.encode_ref(v[1:])
        if isinstance(v, bool):
            return 1.0 if v else 0.0
        if isinstance(v, (int, float)):
            return float(v)
        return 0.0

    def p_none(key: str) -> float:
        """For fields that default to None (UseVariable=true) in C#.
        Missing or 0.0 -> NaN sentinel.  Non-zero literals pass through.
        Variable references ($Foo) resolve normally.
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

    # Handle disabled actions as Noop (they are in the JSON but not active)
    if not enabled:
        return out, False

    if action_name == "Noop":
        return out, False

    # Velocity / movement
    if action_name == "SetVelocityByScale":
        out.append(p("speed"))
        out.append(p_none("ySpeed"))
    elif action_name == "SetVelocity2d":
        out.append(p("x"))
        out.append(p("y"))
    elif action_name == "DecelerateXY":
        if json_action_name == "DecelerateV2":
            # DecelerateV2 uses a single deceleration for both axes
            d = p_none("deceleration")
            out.append(d)
            out.append(d)
        else:
            out.append(p_none("decelerationX"))
            out.append(p_none("decelerationY"))

    # Timing
    elif action_name == "Wait":
        out.append(p("time"))
        out.append(p("finishEvent", is_event=True))
    elif action_name == "WaitRandom":
        out.append(p("timeMin"))
        out.append(p("timeMax"))
        out.append(p("finishEvent", is_event=True))
    elif action_name == "NextFrameEvent":
        out.append(p("sendEvent", is_event=True))

    # Kinematic / gravity
    elif action_name == "SetIsKinematic2d":
        out.append(p("isKinematic"))
    elif action_name == "SetGravity2dScale":
        out.append(p_var("gravityScale"))

    # Position
    elif action_name == "SetPosition2d":
        if json_action_name == "SetPosition":
            out.append(p_none("x"))
            out.append(p_none("y"))
        else:
            out.append(p_none("x"))
            out.append(p_none("y"))
    elif action_name == "Translate":
        out.append(p_var("x"))
        out.append(p_var("y"))
        out.append(p("z"))
    elif action_name == "ClampPosition":
        out.append(p("minX"))
        out.append(p("maxX"))
        out.append(p("minY"))
        out.append(p("maxY"))
    elif action_name == "AnimatePositionTo":
        out.append(p("time"))
        out.append(p("speed"))
        out.append(p("delay"))
        out.append(p("reverse"))
        out.append(p("finishEvent", is_event=True))

    # Facing
    elif action_name == "FaceObjectV2":
        out.append(p("spriteFacesRight"))
    elif action_name == "FaceObjectV4":
        out.append(p("SpriteFacesRight"))
        out.append(p("StoreDuration"))
    elif action_name == "FlipScale":
        pass  # no params, just negates facing
    elif action_name == "SetScale":
        out.append(p("x"))

    # Bool/Float/Int variable ops
    elif action_name == "SetBoolValue":
        out.append(p_var("boolVariable"))
        out.append(p("boolValue"))
    elif action_name == "SetFloatValue":
        out.append(p_var("floatVariable"))
        out.append(p_var("floatValue"))
    elif action_name == "SetIntValue":
        out.append(p_var("intVariable"))
        out.append(p("intValue"))
    elif action_name == "BoolTest":
        out.append(p_var("boolVariable"))
        out.append(p("isTrue", is_event=True))
        out.append(p("isFalse", is_event=True))
    elif action_name == "BoolTestMulti":
        out.append(p("trueEvent", is_event=True))
        out.append(p("falseEvent", is_event=True))
        out.append(p_none("storeResult"))
        # Inject boolVariables/boolStates from fixup table
        bool_vars = params.get("boolVariables", [])
        bool_states = params.get("boolStates", [])
        n = len(bool_vars)
        out.append(float(n))
        for bv in bool_vars:
            if isinstance(bv, str) and bv.startswith("$"):
                out.append(var_table.encode_ref(bv[1:]))
            else:
                out.append(0.0)
        for bs in bool_states:
            if isinstance(bs, str) and bs.startswith("$"):
                out.append(var_table.encode_ref(bs[1:]))
            else:
                out.append(1.0 if bs else 0.0)
    elif action_name == "BoolAllTrue":
        out.append(p("sendEvent", is_event=True))
        out.append(p_none("storeResult"))
        bool_vars = params.get("boolVariables", [])
        out.append(float(len(bool_vars)))
        for bv in bool_vars:
            if isinstance(bv, str) and bv.startswith("$"):
                out.append(var_table.encode_ref(bv[1:]))
            else:
                out.append(0.0)

    # Float comparisons
    elif action_name == "FloatCompare":
        out.append(p_var("float1"))
        out.append(p_var("float2"))
        out.append(p("tolerance"))
        out.append(p("equal", is_event=True))
        out.append(p("lessThan", is_event=True))
        out.append(p("greaterThan", is_event=True))
    elif action_name == "FloatTestToBool":
        out.append(p_var("float1"))
        out.append(p_var("float2"))
        out.append(p("tolerance"))
        out.append(p_var("equalBool"))
        out.append(p_var("lessThanBool"))
        out.append(p_var("greaterThanBool"))
    elif action_name == "IntCompare":
        out.append(p_var("integer1"))
        out.append(p_var("integer2"))
        out.append(p("equal", is_event=True))
        out.append(p("lessThan", is_event=True))
        out.append(p("greaterThan", is_event=True))
    elif action_name == "IntAdd":
        out.append(p_var("intVariable"))
        out.append(p("add"))

    # Float arithmetic
    elif action_name == "FloatAdd":
        out.append(p_var("floatVariable"))
        out.append(p_var("add"))
    elif action_name == "FloatMultiply":
        out.append(p_var("floatVariable"))
        out.append(p("multiplyBy"))
    elif action_name == "FloatClamp":
        out.append(p_var("floatVariable"))
        out.append(p("minValue"))
        out.append(p("maxValue"))
    elif action_name == "FloatInRange":
        out.append(p_var("floatVariable"))
        out.append(p("lowerValue"))
        out.append(p("upperValue"))
        out.append(p_none("boolVariable"))
        out.append(p("trueEvent", is_event=True))
        out.append(p("falseEvent", is_event=True))

    # Random
    elif action_name == "RandomFloat":
        out.append(p("min"))
        out.append(p("max"))
        out.append(p_var("storeResult"))
    elif action_name == "RandomInt":
        out.append(p("min"))
        out.append(p("max"))
        out.append(p_var("storeResult"))
        out.append(p("noRepeat"))
    elif action_name == "MultiplyIntByFloat":
        out.append(p_var("integer"))
        out.append(p("multiplyFloat"))
        out.append(p_var("storeResult"))

    # Ease
    elif action_name == "EaseFloat":
        out.append(p("fromValue"))
        out.append(p("toValue"))
        out.append(p_var("floatVariable"))
        out.append(p("time"))
        out.append(p("speed"))
        out.append(p("delay"))
        out.append(p("reverse"))
        out.append(p("finishEvent", is_event=True))

    # Spatial queries
    elif action_name == "GetDistance":
        out.append(p_var("storeResult"))
    elif action_name == "GetXDistance":
        out.append(p_var("storeResult"))
    elif action_name == "GetSelfPosition":
        out.append(p_none("x"))
        out.append(p_none("y"))
    elif action_name == "GetPosition2d":
        if json_action_name == "GetPosition":
            out.append(p_none("x"))
            out.append(p_none("y"))
        else:
            out.append(p_none("x"))
            out.append(p_none("y"))
    elif action_name == "GetScale":
        out.append(p_var("xScale"))
        out.append(p_var("yScale"))
        out.append(p_var("zScale"))

    # Combat
    elif action_name == "SetDamageHeroAmount":
        out.append(p("damageDealt"))
    elif action_name == "SetRecoilSpeed":
        out.append(p("newRecoilSpeed"))
    elif action_name == "SetRecoilBlocked":
        out.append(p("IsUpBlocked"))
        out.append(p("IsDownBlocked"))
        out.append(p("IsLeftBlocked"))
        out.append(p("IsRightBlocked"))
    elif action_name == "SetSpecialDeath":
        out.append(p("hasSpecialDeath"))
    elif action_name == "SetInvincible":
        out.append(p("Invincible"))
        out.append(p_var("InvincibleFromDirection"))
        out.append(p("resetOnStateExit"))
    elif action_name == "SubtractHP":
        out.append(p("amount"))
    elif action_name == "CompareHP":
        out.append(p_var("integer2"))
        out.append(p("equal", is_event=True))
        out.append(p("lessThan", is_event=True))
        out.append(p("greaterThan", is_event=True))
    elif action_name == "GetHP":
        out.append(p_var("storeValue"))

    # Alert/Performance checks
    elif action_name == "CheckAlertRange":
        out.append(p("storeResult"))
        out.append(p("InRangeEvent", is_event=True))
        out.append(p("InRangeDelay"))
        out.append(p("OutOfRangeEvent", is_event=True))
        out.append(p("OutOfRangeDelay"))
    elif action_name == "CheckAlertRangeByName":
        out.append(p("storeResult"))
        out.append(p("sendEvent", is_event=True))
        out.append(p("InRangeDelay"))
        out.append(p("outOfRangeEvent", is_event=True))
        out.append(p("OutOfRangeDelay"))
    elif action_name == "CheckHeroPerformanceRegionV2":
        out.append(p("Radius"))
        out.append(p("MinReactDelay"))
        out.append(p("MaxReactDelay"))
        out.append(p("None", is_event=True))
        out.append(p("ActiveInner", is_event=True))
        out.append(p("ActiveOuter", is_event=True))
        out.append(p("IgnoreNeedolinRange"))
        out.append(p("UseActiveBool"))
        out.append(p_var("ActiveBool"))

    # Event sending
    elif action_name == "SendEvent":
        out.append(p("sendEvent", is_event=True))
        out.append(p("delay"))
    elif action_name == "SendEventByName":
        # sendEvent may or may not be present; it references stored string var
        se = params.get("sendEvent")
        if isinstance(se, str) and se and not isinstance(se, dict):
            out.append(p("sendEvent", is_event=True))
        else:
            out.append(float(EVENT_NONE))
        out.append(p("delay"))
    elif action_name == "SendEventByNameV2":
        se = params.get("sendEvent")
        if isinstance(se, str) and se and not isinstance(se, dict):
            out.append(p("sendEvent", is_event=True))
        else:
            out.append(float(EVENT_NONE))
        out.append(p("delay"))
    elif action_name == "SendEventByScale":
        out.append(p("positiveEvent", is_event=True))
        out.append(p("negativeEvent", is_event=True))
    elif action_name == "SendRandomEvent":
        events = params.get("events", [])
        weights = params.get("weights", [])
        n = len(events)
        out.append(float(n))
        for ev in events:
            out.append(float(event_table.get_or_add(ev)) if ev else float(EVENT_NONE))
        # weights: first N are the actual weights, rest are padding/zeros
        for i in range(n):
            w = weights[i] if i < len(weights) else 0.0
            if isinstance(w, (int, float)):
                out.append(float(w))
            else:
                out.append(0.0)
    elif action_name == "SendRandomEventV3":
        events = params.get("events", [])
        weights_raw = params.get("weights", [])
        event_max_raw = params.get("eventMax", [])
        missed_max_raw = params.get("missedMax", [])
        n = len(events)
        out.append(float(n))
        for ev in events:
            out.append(float(event_table.get_or_add(ev)) if ev else float(EVENT_NONE))
        for i in range(n):
            w = weights_raw[i] if i < len(weights_raw) else 0.0
            out.append(float(w) if isinstance(w, (int, float)) else 0.0)
        for i in range(n):
            em = event_max_raw[i] if i < len(event_max_raw) else 0
            out.append(float(em) if isinstance(em, (int, float)) else 0.0)
        for i in range(n):
            mm = missed_max_raw[i] if i < len(missed_max_raw) else 0
            out.append(float(mm) if isinstance(mm, (int, float)) else 0.0)

    # Damage
    elif action_name == "FreezeMoment":
        out.append(p("FreezeMomentType"))
    elif action_name == "DamageHeroDirectly":
        out.append(p("damageAmount"))
    elif action_name == "CanHeroTakeDamage":
        out.append(p("canTakeDmgEvent", is_event=True))
        out.append(p("cannotTakeDmgEvent", is_event=True))

    # Raycast / collision
    elif action_name == "RayCast2dV2":
        out.append(p("distance"))
        out.append(p("repeatInterval"))
        out.append(p("hitEvent", is_event=True))
        out.append(p("noHitEvent", is_event=True))
        out.append(p_var("storeDidHit"))
        out.append(p("storeHitDistance"))
        out.append(p("storeDistance"))
    elif action_name == "CheckCollisionSide" or action_name == "CheckCollisionSideEnter":
        out.append(p("topHitEvent", is_event=True))
        out.append(p("rightHitEvent", is_event=True))
        out.append(p("bottomHitEvent", is_event=True))
        out.append(p("leftHitEvent", is_event=True))
    elif action_name == "CheckXPosition":
        out.append(p_var("compareTo"))
        out.append(p("compareToOffset"))
        out.append(p("tolerance"))
        out.append(p("equal", is_event=True))
        out.append(p_var("equalBool"))
        out.append(p("lessThan", is_event=True))
        out.append(p_var("lessThanBool"))
        out.append(p("greaterThan", is_event=True))
        out.append(p_var("greaterThanBool"))
    elif action_name == "CheckYPosition":
        out.append(p_var("compareTo"))
        out.append(p("compareToOffset"))
        out.append(p("tolerance"))
        out.append(p("equal", is_event=True))
        out.append(p("lessThan", is_event=True))
        out.append(p("greaterThan", is_event=True))
    elif action_name == "CheckYPositionV2":
        out.append(p_var("compareTo"))
        out.append(p("compareToOffset"))
        out.append(p("tolerance"))
        out.append(p("equal", is_event=True))
        out.append(p_var("equalBool"))
        out.append(p("lessThan", is_event=True))
        out.append(p_var("lessThanBool"))
        out.append(p("greaterThan", is_event=True))
        out.append(p_var("greaterThanBool"))
    elif action_name == "CheckIsCharacterGrounded":
        out.append(p("GroundDistance"))
        out.append(p("GroundedEvent", is_event=True))
        out.append(p("NotGroundedEvent", is_event=True))
    elif action_name == "CheckTargetDirection":
        out.append(p("aboveEvent", is_event=True))
        out.append(p("belowEvent", is_event=True))
        out.append(p("rightEvent", is_event=True))
        out.append(p("leftEvent", is_event=True))
        out.append(p_var("aboveBool"))
        out.append(p_var("belowBool"))
        out.append(p_var("rightBool"))
        out.append(p_var("leftBool"))
        out.append(p("selfOffsetX"))
        out.append(p("selfOffsetY"))

    # Collider
    elif action_name == "SetCollider":
        out.append(p("active"))
        out.append(p("resetOnExit"))
    elif action_name == "SetPolygonCollider":
        out.append(p("active"))
        out.append(p("resetOnExit"))

    # Misc
    elif action_name == "SetStringValue":
        # String variables are used for event name storage ($Next Event).
        # The extraction didn't capture the string value, so we hardcode
        # the known state-name → event-ID mapping and store as an int
        # variable ($NextEventId) instead.
        # This is handled by the post-processing step below (NEXT_EVENT_FIXUP).
        pass
    elif action_name == "GetFsmFloat":
        out.append(p_var("storeValue"))
        out.append(-0.5)  # bossLavaY from consts.hpp
    elif action_name == "PreventInvincibleEffect":
        out.append(p("preventEffect"))
    elif action_name == "ReceivedDamage":
        out.append(p("sendEvent", is_event=True))
        out.append(p("sendEventHeavy", is_event=True))
        out.append(p("sendEventLava", is_event=True))
        out.append(p("storeDamageDealt"))
        out.append(p("storeDirection"))
        out.append(p("firstHitOnly"))
    elif action_name == "SetHitEffectOrigin":
        pass  # no params
    elif action_name == "SetHitboxGeometry":
        # Synthetic action: params are injected directly, not from JSON
        pass

    return out, is_cont


def classify_action(json_name: str) -> str:
    """Return the FsmActionType enum name, or 'Noop' for cosmetic actions."""
    return GAMEPLAY_ACTIONS.get(json_name, "Noop")


def handle_anim_event_action(
    json_name: str,
    params: dict[str, Any],
    event_table: EventTable,
    enabled: bool,
    state_name: str = "",
) -> tuple[str, list[float], bool] | None:
    """Handle animation actions that fire gameplay events.

    These are cosmetic (animation) but fire events that drive FSM transitions.
    We convert them to Wait actions with the appropriate event timing.
    """
    if not enabled:
        return None
    if json_name not in ANIM_EVENT_ACTIONS:
        return None

    # Determine which events this animation fires
    trigger_event = params.get("animationTriggerEvent", "")
    complete_event = params.get("animationCompleteEvent", "")
    if json_name == "Tk2dPlayAnimationWait":
        complete_event = params.get("AnimationCompleteEvent", "")

    if not trigger_event and not complete_event:
        return None

    out: list[float] = []

    # Resolve clip duration from state-to-clip mapping
    clip_name = STATE_TO_CLIP.get(state_name)
    if clip_name and clip_name in CLIP_DURATIONS:
        clip_dur, clip_trig = CLIP_DURATIONS[clip_name]
    else:
        clip_dur, clip_trig = 0.35, 0.175

    if trigger_event and not complete_event:
        out.append(clip_trig)
        out.append(float(event_table.get_or_add(trigger_event)))
        return "Wait", out, False
    elif complete_event and not trigger_event:
        out.append(clip_dur)
        out.append(float(event_table.get_or_add(complete_event)))
        return "Wait", out, False
    elif trigger_event and complete_event:
        out.append(clip_trig)
        out.append(float(event_table.get_or_add(trigger_event)))
        return "Wait", out, False

    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: bake_fsm.py <fsm_json>", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        fsm = json.load(f)

    # Build variable table
    var_table = VarTable()
    for name, vdef in fsm["variables"].items():
        vtype = vdef["type"]
        val = vdef["value"]
        if vtype == "float":
            var_table.add_float(name, float(val))
        elif vtype == "int":
            var_table.add_int(name, int(val))
        elif vtype == "bool":
            var_table.add_bool(name, bool(val))
        elif vtype == "string":
            var_table.add_string(name, str(val))
        elif vtype == "vector3":
            # Vector3 vars: store as 3 floats (x, y, z)
            var_table.add_float(name + ".x", float(val["x"]))
            var_table.add_float(name + ".y", float(val["y"]))
            var_table.add_float(name + ".z", float(val["z"]))

    # Fixup: $Rage HP is computed in the Init state (GetHP * 0.5 = 250 * 0.5 = 125)
    # which is a skip state. Set it directly.
    if var_table.has("Rage HP"):
        typ, idx = var_table.resolve("Rage HP")
        if typ == 1:  # int
            var_table.int_vars[idx] = ("Rage HP", 125)

    # Add synthetic int variable for $Next Event → event ID mapping.
    # The original FSM uses a string variable, but our baked format uses int IDs.
    var_table.add_int("$NextEventId", 0)

    # Build event table
    event_table = EventTable()
    for ev in fsm["events"]:
        event_table.get_or_add(ev["name"])

    # Filter states
    battle_states = []
    state_name_to_orig_idx = {}
    for s in fsm["states"]:
        if s["name"] in SKIP_STATES:
            continue
        state_name_to_orig_idx[s["name"]] = s["index"]
        battle_states.append(s)

    # Remap state indices
    state_name_to_new_idx: dict[str, int] = {}
    for new_idx, s in enumerate(battle_states):
        state_name_to_new_idx[s["name"]] = new_idx

    # Find start state
    # The battle starts from "Idle" (or first battle state if Idle is missing)
    start_state_name = "Idle"
    if start_state_name not in state_name_to_new_idx:
        # Fallback: find first state that's reachable (e.g., Evade from Start Battle)
        start_state_name = battle_states[0]["name"]
    start_state_idx = state_name_to_new_idx[start_state_name]

    # Process actions and transitions
    all_actions: list[dict] = []  # {type, flags, paramOffset}
    all_transitions: list[dict] = []  # {eventId, targetState}
    all_params: list[float] = []
    state_defs: list[dict] = []  # {actionStart, actionCount, transitionStart, transitionCount, name}
    state_names: list[str] = []

    for s in battle_states:
        action_start = len(all_actions)
        action_count = 0
        bool_all_true_idx = 0  # tracks BoolAllTrue occurrence within state
        bool_test_multi_idx = 0  # tracks BoolTestMulti occurrence within state

        for act in s["actions"]:
            json_name = act["name"]
            enabled = act.get("enabled", True)
            params = act.get("params", {})

            # Inject boolVariables for BoolAllTrue via fixup table
            if json_name == "BoolAllTrue" and "boolVariables" not in params:
                fixup_key = (s["name"], bool_all_true_idx)
                if fixup_key in BOOL_ALL_TRUE_FIXUP:
                    params = dict(params)  # copy to avoid mutating original
                    params["boolVariables"] = BOOL_ALL_TRUE_FIXUP[fixup_key]
                bool_all_true_idx += 1

            # Inject boolVariables/boolStates for BoolTestMulti via fixup table
            if json_name == "BoolTestMulti" and "boolVariables" not in params:
                fixup_key = (s["name"], bool_test_multi_idx)
                if fixup_key in BOOL_TEST_MULTI_FIXUP:
                    params = dict(params)  # copy to avoid mutating original
                    bvars, bstates = BOOL_TEST_MULTI_FIXUP[fixup_key]
                    params["boolVariables"] = bvars
                    params["boolStates"] = bstates
                bool_test_multi_idx += 1

            # First check if this is an animation action that fires events
            anim_result = handle_anim_event_action(
                json_name, params, event_table, enabled,
                state_name=s["name"],
            )

            if anim_result is not None:
                action_type_name, param_floats, is_cont = anim_result
                # Actions converted from animations to Wait need continuous flag
                anim_flags = 1 if action_type_name in ("Wait", "WaitRandom") else 0
                action_def = {
                    "type": action_type_name,
                    "flags": anim_flags,
                    "paramOffset": len(all_params),
                }
                all_params.extend(param_floats)
                all_actions.append(action_def)
                action_count += 1
                continue

            # Classify
            action_type_name = classify_action(json_name)

            if not enabled:
                action_type_name = "Noop"

            if action_type_name == "Noop":
                # Still emit the action (preserves action indices) but with no params
                action_def = {
                    "type": "Noop",
                    "flags": 0,
                    "paramOffset": len(all_params),
                }
                all_actions.append(action_def)
                action_count += 1
                continue

            # Extract params
            param_floats, is_cont = extract_action_params(
                action_type_name, json_name, params, var_table, event_table, enabled
            )

            flags = 1 if is_cont else 0
            action_def = {
                "type": action_type_name,
                "flags": flags,
                "paramOffset": len(all_params),
            }
            all_params.extend(param_floats)
            all_actions.append(action_def)
            action_count += 1

        # Hitbox geometry injection
        if s["name"] in ATTACK_HITBOX_GEOMETRY:
            hw, hh, ox, oy, act = ATTACK_HITBOX_GEOMETRY[s["name"]]
            param_offset = len(all_params)
            all_params.extend([hw, hh, ox, oy, act])
            all_actions.append({
                "type": "SetHitboxGeometry",
                "flags": 0,
                "paramOffset": param_offset,
            })
            action_count += 1
        elif s["name"] in HITBOX_DEACTIVATE_STATES:
            param_offset = len(all_params)
            all_params.extend([0.0, 0.0, 0.0, 0.0, 0.0])
            all_actions.append({
                "type": "SetHitboxGeometry",
                "flags": 0,
                "paramOffset": param_offset,
            })
            action_count += 1

        # Next event fixup
        # The FSM uses a string variable $Next Event to route Hop End to the
        # correct attack. The extraction didn't capture SetStringValue params,
        # so we inject synthetic SetIntValue actions for the known mappings.
        HOP_EVENT_MAP = {
            "Hop To Charge": "CHARGE",
            "Hop To J Slash": "J SLASH",
            "Hop To Combo": "COMBO",
        }
        if s["name"] in HOP_EVENT_MAP:
            event_name = HOP_EVENT_MAP[s["name"]]
            event_id = event_table.get_or_add(event_name)
            next_event_slot = var_table.resolve("$NextEventId")
            # Inject SetIntValue: $NextEventId = event_id
            param_offset = len(all_params)
            all_params.append(float(VAR_REF_OFFSET + 1 * 256 + next_event_slot[1]))  # int var ref
            all_params.append(float(event_id))
            all_actions.append({
                "type": "SetIntValue",
                "flags": 0,
                "paramOffset": param_offset,
            })
            action_count += 1

        if s["name"] == "Hop End":
            # Replace the SendEventByName (which has no event param) with a
            # synthetic action that reads $NextEventId and fires it.
            # Find the SendEventByName action we just added and patch it.
            for i in range(action_start, action_start + action_count):
                if all_actions[i]["type"] == "SendEventByName":
                    # Rewrite to: SendEvent with event = read from $NextEventId
                    next_event_slot = var_table.resolve("$NextEventId")
                    po = all_actions[i]["paramOffset"]
                    # SendEvent params: [eventId, delay]
                    # We encode eventId as a var reference to $NextEventId
                    all_actions[i]["type"] = "SendEvent"
                    all_actions[i]["paramOffset"] = len(all_params)
                    all_params.append(float(VAR_REF_OFFSET + 1 * 256 + next_event_slot[1]))  # int var ref for event ID
                    all_params.append(0.0)  # delay
                    break

        # Transitions
        trans_start = len(all_transitions)
        trans_count = 0
        for tr in s["transitions"]:
            target_name = tr["to"]
            event_name = tr["event"]
            event_id = event_table.get_or_add(event_name)

            if target_name not in state_name_to_new_idx:
                # Target is a skipped state; skip the transition
                print(
                    f"WARNING: transition from '{s['name']}' to skipped state "
                    f"'{target_name}' (event '{event_name}'): dropped",
                    file=sys.stderr,
                )
                continue

            target_idx = state_name_to_new_idx[target_name]
            all_transitions.append(
                {"eventId": event_id, "targetState": target_idx}
            )
            trans_count += 1

        state_defs.append(
            {
                "actionStart": action_start,
                "actionCount": action_count,
                "transitionStart": trans_start,
                "transitionCount": trans_count,
                "name": s["name"],
            }
        )
        state_names.append(s["name"])

    # Global transitions
    global_transitions = []
    for gt in fsm.get("global_transitions", []):
        ev_name = gt["event"]
        target_name = gt["to"]
        if target_name in state_name_to_new_idx:
            global_transitions.append(
                {
                    "eventId": event_table.get_or_add(ev_name),
                    "targetState": state_name_to_new_idx[target_name],
                }
            )
        else:
            print(
                f"WARNING: global transition to skipped state '{target_name}': dropped",
                file=sys.stderr,
            )

    # Output C++ header
    emit_header(
        state_defs,
        state_names,
        all_actions,
        all_transitions,
        all_params,
        global_transitions,
        event_table,
        var_table,
        start_state_idx,
    )


def float_literal(v: float) -> str:
    """Format a float as a C++ literal with enough precision."""
    if v == float("inf"):
        return "INFINITY"
    if v == float("-inf"):
        return "-INFINITY"
    if math.isnan(v):
        return "NAN"
    if v == int(v) and abs(v) < 1e9:
        return f"{int(v)}.0f"
    return f"{v!r}f"


def sanitize_enum_name(name: str) -> str:
    """Convert an event/var name to a valid C++ identifier."""
    return name.replace("$", "").replace(" ", "_").replace("?", "Q").replace("-", "_").replace(".", "_").upper()


def emit_header(
    state_defs,
    state_names,
    all_actions,
    all_transitions,
    all_params,
    global_transitions,
    event_table,
    var_table,
    start_state_idx,
):
    lines = []
    w = lines.append

    w("// Auto-generated by bake_fsm.py. DO NOT EDIT.")
    w("#pragma once")
    w('#include "fsm_types.hpp"')
    w("")
    w("namespace silksong {")
    w("namespace fsm_lace_boss1 {")
    w("")

    # Constants
    w(f"constexpr int NUM_STATES = {len(state_defs)};")
    w(f"constexpr int NUM_ACTIONS = {len(all_actions)};")
    w(f"constexpr int NUM_TRANSITIONS = {len(all_transitions)};")
    w(f"constexpr int NUM_PARAMS = {len(all_params)};")
    w(f"constexpr int NUM_GLOBAL_TRANSITIONS = {len(global_transitions)};")
    w(f"constexpr uint8_t START_STATE = {start_state_idx};")
    w("")

    # Event enum
    w("// Event IDs")
    w("enum Event : uint8_t {")
    for name, eid in event_table.items():
        w(f"    EVT_{sanitize_enum_name(name)} = {eid},")
    w(f"    EVT_NONE = {EVENT_NONE}")
    w("};")
    w("")

    # State name enum
    w("// State indices (for debugging/reference)")
    w("enum StateIdx : uint8_t {")
    for i, name in enumerate(state_names):
        w(f"    ST_{sanitize_enum_name(name)} = {i},")
    w("};")
    w("")

    # Variable slots
    w("// Float variable slots")
    w("enum FloatVar : uint8_t {")
    for i, (name, val) in enumerate(var_table.float_vars):
        w(f"    FVAR_{sanitize_enum_name(name)} = {i}, // init={val}")
    w(f"    NUM_FLOAT_VARS = {len(var_table.float_vars)}")
    w("};")
    w("")

    w("// Int variable slots")
    w("enum IntVar : uint8_t {")
    for i, (name, val) in enumerate(var_table.int_vars):
        w(f"    IVAR_{sanitize_enum_name(name)} = {i}, // init={val}")
    w(f"    NUM_INT_VARS = {len(var_table.int_vars)}")
    w("};")
    w("")

    w("// Bool variable slots")
    w("enum BoolVar : uint8_t {")
    for i, (name, val) in enumerate(var_table.bool_vars):
        w(f"    BVAR_{sanitize_enum_name(name)} = {i}, // init={int(val)}")
    w(f"    NUM_BOOL_VARS = {len(var_table.bool_vars)}")
    w("};")
    w("")

    # Initial variable values
    w("// Initial float variable values")
    w("constexpr float INIT_FLOAT_VARS[] = {")
    for name, val in var_table.float_vars:
        w(f"    {float_literal(val)}, // {name}")
    if not var_table.float_vars:
        w("    0.0f")
    w("};")
    w("")

    w("// Initial int variable values")
    w("constexpr int32_t INIT_INT_VARS[] = {")
    for name, val in var_table.int_vars:
        w(f"    {val}, // {name}")
    if not var_table.int_vars:
        w("    0")
    w("};")
    w("")

    w("// Initial bool variable values")
    w("constexpr uint8_t INIT_BOOL_VARS[] = {")
    for name, val in var_table.bool_vars:
        w(f"    {int(val)}, // {name}")
    if not var_table.bool_vars:
        w("    0")
    w("};")
    w("")

    # States
    w("constexpr FsmStateDef STATES[] = {")
    for i, sd in enumerate(state_defs):
        w(
            f"    {{ {sd['actionStart']}, {sd['actionCount']}, "
            f"{sd['transitionStart']}, {sd['transitionCount']}, "
            f"{i}, {{0, 0}} }}, // [{i}] {sd['name']}"
        )
    w("};")
    w("")

    # Actions
    w("constexpr FsmActionDef ACTIONS[] = {")
    for i, ad in enumerate(all_actions):
        w(
            f"    {{ FsmActionType::{ad['type']}, {ad['flags']}, "
            f"{ad['paramOffset']} }}, // [{i}]"
        )
    w("};")
    w("")

    # Transitions
    w("constexpr FsmTransitionDef TRANSITIONS[] = {")
    for i, td in enumerate(all_transitions):
        # Find event name for comment
        ev_name = "?"
        for name, eid in event_table.items():
            if eid == td["eventId"]:
                ev_name = name
                break
        # Find target state name for comment
        target_name = (
            state_names[td["targetState"]]
            if td["targetState"] < len(state_names)
            else "?"
        )
        w(
            f"    {{ {td['eventId']}, {td['targetState']} }}, "
            f"// [{i}] {ev_name} -> {target_name}"
        )
    w("};")
    w("")

    # Params
    w("constexpr float PARAMS[] = {")
    for i in range(0, len(all_params), 8):
        chunk = all_params[i : i + 8]
        vals = ", ".join(float_literal(v) for v in chunk)
        w(f"    {vals},")
    if not all_params:
        w("    0.0f")
    w("};")
    w("")

    # Global transitions
    w("constexpr FsmTransitionDef GLOBAL_TRANSITIONS[] = {")
    for gt in global_transitions:
        ev_name = "?"
        for name, eid in event_table.items():
            if eid == gt["eventId"]:
                ev_name = name
                break
        target_name = (
            state_names[gt["targetState"]]
            if gt["targetState"] < len(state_names)
            else "?"
        )
        w(f"    {{ {gt['eventId']}, {gt['targetState']} }}, // {ev_name} -> {target_name}")
    if not global_transitions:
        w("    { 255, 0 }")
    w("};")
    w("")

    # State names (debug)
    w("// State name table (debug only)")
    w("constexpr const char* STATE_NAMES[] = {")
    for name in state_names:
        w(f'    "{name}",')
    w("};")
    w("")

    # FsmDef initializer helper
    n_fvars = len(var_table.float_vars)
    n_ivars = len(var_table.int_vars)
    n_bvars = len(var_table.bool_vars)
    w("// Build the FsmDef struct (copies into inline arrays for GPU compat)")
    w("inline FsmDef makeDef() {")
    w("    FsmDef def{};")
    w(f"    static_assert({len(state_defs)} <= FSM_MAX_STATES);")
    w(f"    static_assert({len(all_actions)} <= FSM_MAX_TOTAL_ACTIONS);")
    w(f"    static_assert({len(all_transitions)} <= FSM_MAX_TRANSITIONS);")
    w(f"    static_assert({len(all_params)} <= FSM_MAX_PARAMS);")
    w(f"    static_assert({len(global_transitions)} <= FSM_MAX_GLOBAL_TRANSITIONS);")
    w(f"    for (int i = 0; i < {len(state_defs)}; ++i) def.states[i] = STATES[i];")
    w(f"    for (int i = 0; i < {len(all_actions)}; ++i) def.actions[i] = ACTIONS[i];")
    w(f"    for (int i = 0; i < {len(all_transitions)}; ++i) def.transitions[i] = TRANSITIONS[i];")
    w(f"    for (int i = 0; i < {len(all_params)}; ++i) def.params[i] = PARAMS[i];")
    w(f"    for (int i = 0; i < {len(global_transitions)}; ++i) def.globalTransitions[i] = GLOBAL_TRANSITIONS[i];")
    w(f"    def.numStates = {len(state_defs)};")
    w(f"    def.numActions = {len(all_actions)};")
    w(f"    def.numTransitions = {len(all_transitions)};")
    w(f"    def.numParams = {len(all_params)};")
    w(f"    def.numFloatVars = {n_fvars};")
    w(f"    def.numIntVars = {n_ivars};")
    w(f"    def.numBoolVars = {n_bvars};")
    w(f"    def.numGlobalTransitions = {len(global_transitions)};")
    w(f"    def.startState = {start_state_idx};")
    # Copy init variable values into FsmDef
    w(f"    for (int i = 0; i < {n_fvars}; ++i) def.initFloatVars[i] = INIT_FLOAT_VARS[i];")
    w(f"    for (int i = 0; i < {n_ivars}; ++i) def.initIntVars[i] = INIT_INT_VARS[i];")
    w(f"    for (int i = 0; i < {n_bvars}; ++i) def.initBoolVars[i] = INIT_BOOL_VARS[i];")
    w("    return def;")
    w("}")
    w("")

    w("} // namespace fsm_lace_boss1")
    w("} // namespace silksong")
    w("")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
