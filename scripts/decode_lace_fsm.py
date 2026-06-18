#!/usr/bin/env python3
"""Decode the Lace Boss 'Control' PlayMaker FSM from Silksong scene data."""

import json
import sys
import warnings
from pathlib import Path

import UnityPy

warnings.filterwarnings("ignore")
UnityPy.config.FALLBACK_UNITY_VERSION = "6000.0.50f1"

GAME_DATA = Path(
    "/home/seis/game/Hollow Knight Silksong/Hollow Knight Silksong_Data"
)
BUNDLE_DIR = GAME_DATA / "StreamingAssets" / "aa" / "StandaloneLinux64"
TARGET_BUNDLE = BUNDLE_DIR / "scenes_scenes_scenes"
TARGET_PATH_ID = 13742

SCRIPTS_DIR = Path("/home/seis/code/silksong-agent/scripts")

LACE_FINGERPRINT_STATES = [
    "combo slash", "counter stance", "rapidslash",
    "downstab", "p2 shift", "tele in",
]


def find_lace_fsm(env):
    lace_unique = LACE_FINGERPRINT_STATES

    count = 0
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        count += 1
        if count % 100000 == 0:
            print(f"  ... scanned {count} MonoBehaviours", file=sys.stderr)
        try:
            tree = obj.read_typetree()
            fsm = tree.get("fsm", {})
            states = fsm.get("states", [])
            if len(states) < 100:
                continue
            state_names = [s.get("name", "?") for s in states]
            sn_lower = " | ".join(state_names).lower()
            found = [kw for kw in lace_unique if kw in sn_lower]
            if len(found) >= 5:
                print(f"Found Lace FSM: path_id={obj.path_id} "
                      f"states={len(states)} matches={found}")
                return tree, fsm
        except Exception:
            pass
    return None, None


def decode_state_actions(state, fsm_events):
    ad = state.get("actionData", {})
    action_names = ad.get("actionNames", [])
    action_enabled = ad.get("actionEnabled", [])
    action_start = ad.get("actionStartIndex", [])
    param_names = ad.get("paramName", [])
    param_data_type = ad.get("paramDataType", [])
    param_data_pos = ad.get("paramDataPos", [])

    fsm_float_params = ad.get("fsmFloatParams", [])
    fsm_int_params = ad.get("fsmIntParams", [])
    fsm_bool_params = ad.get("fsmBoolParams", [])
    fsm_string_params = ad.get("fsmStringParams", [])
    string_params = ad.get("stringParams", [])
    fsm_vector2_params = ad.get("fsmVector2Params", [])
    fsm_vector3_params = ad.get("fsmVector3Params", [])
    fsm_enum_params = ad.get("fsmEnumParams", [])
    fsm_game_object_params = ad.get("fsmGameObjectParams", [])
    fsm_owner_default_params = ad.get("fsmOwnerDefaultParams", [])

    def get_param_value(pi):
        if pi >= len(param_data_type):
            return None
        ptype = param_data_type[pi]
        ppos = param_data_pos[pi] if pi < len(param_data_pos) else -1
        if ppos < 0:
            return None

        if ptype == 15 and ppos < len(fsm_float_params):
            fp = fsm_float_params[ppos]
            if isinstance(fp, dict):
                if fp.get("useVariable") and fp.get("name"):
                    return f"${fp['name']}"
                return fp.get("value")
            return fp
        elif ptype == 16 and ppos < len(fsm_int_params):
            ip = fsm_int_params[ppos]
            if isinstance(ip, dict):
                if ip.get("useVariable") and ip.get("name"):
                    return f"${ip['name']}"
                return ip.get("value")
            return ip
        elif ptype == 17 and ppos < len(fsm_bool_params):
            bp = fsm_bool_params[ppos]
            if isinstance(bp, dict):
                if bp.get("useVariable") and bp.get("name"):
                    return f"${bp['name']}"
                return bool(bp.get("value", 0))
            return bp
        elif ptype == 23 and ppos < len(string_params):
            return string_params[ppos]
        elif ptype == 18 and ppos < len(fsm_vector2_params):
            vp = fsm_vector2_params[ppos]
            if isinstance(vp, dict):
                val = vp.get("value", {})
                return {"x": val.get("x", 0), "y": val.get("y", 0)}
            return vp
        elif ptype == 19 and ppos < len(fsm_vector3_params):
            vp = fsm_vector3_params[ppos]
            if isinstance(vp, dict):
                val = vp.get("value", {})
                return {"x": val.get("x", 0), "y": val.get("y", 0), "z": val.get("z", 0)}
            return vp
        elif ptype == 27 and ppos < len(fsm_enum_params):
            ep = fsm_enum_params[ppos]
            if isinstance(ep, dict):
                return ep.get("value", ep.get("intValue"))
            return ep
        elif ptype == 25 and ppos < len(fsm_game_object_params):
            gp = fsm_game_object_params[ppos]
            if isinstance(gp, dict):
                return gp.get("name", "")
            return gp
        elif ptype == 26 and ppos < len(fsm_owner_default_params):
            op = fsm_owner_default_params[ppos]
            if isinstance(op, dict):
                return "Owner" if op.get("ownerOption", 0) == 0 else op.get("gameObject", {}).get("name", "?")
            return op
        return None

    actions = []
    for ai, an in enumerate(action_names):
        short = an.split(".")[-1]
        enabled = action_enabled[ai] if ai < len(action_enabled) else 1

        pstart = action_start[ai] if ai < len(action_start) else 0
        pend = action_start[ai + 1] if ai + 1 < len(action_start) else len(param_names)

        params = {}
        for pi in range(pstart, min(pend, len(param_names))):
            pname = param_names[pi] if pi < len(param_names) else f"p{pi}"
            if not pname:
                continue
            val = get_param_value(pi)
            if val is not None and pname not in ("everyFrame", "tooltip",
                                                  "showInInspector", "networkSync"):
                params[pname] = val

        if "SendRandomEvent" in short:
            events_list = []
            weights_list = []
            event_max_list = []
            missed_max_list = []
            active_bool = None

            current_section = None
            for pi in range(pstart, min(pend, len(param_names))):
                pname = param_names[pi]
                ptype = param_data_type[pi] if pi < len(param_data_type) else -1

                if pname == "events":
                    current_section = "events"
                    continue
                elif pname == "weights":
                    current_section = "weights"
                    continue
                elif pname == "eventMax":
                    current_section = "eventMax"
                    continue
                elif pname == "missedMax":
                    current_section = "missedMax"
                    continue
                elif pname == "activeBool":
                    val = get_param_value(pi)
                    active_bool = val
                    continue

                val = get_param_value(pi)
                if val is None:
                    val = "?"

                if current_section == "events":
                    events_list.append(val)
                elif current_section == "weights":
                    weights_list.append(val)
                elif current_section == "eventMax":
                    event_max_list.append(val)
                elif current_section == "missedMax":
                    missed_max_list.append(val)

            params = {
                "events": events_list,
                "weights": weights_list,
                "eventMax": event_max_list,
                "missedMax": missed_max_list,
            }
            if active_bool is not None:
                params["activeBool"] = active_bool

        if short == "Wait":
            for pi in range(pstart, min(pend, len(param_names))):
                pname = param_names[pi]
                if pname == "time":
                    val = get_param_value(pi)
                    if val is not None:
                        params["time"] = val
                elif pname == "finishEvent":
                    val = get_param_value(pi)
                    if val is not None:
                        params["finishEvent"] = val

        action_entry = {"name": short, "enabled": bool(enabled)}
        if params:
            action_entry["params"] = params
        actions.append(action_entry)

    return actions


def resolve_state_name(states, to_state):
    if isinstance(to_state, int) and 0 <= to_state < len(states):
        return states[to_state].get("name", f"<{to_state}>")
    if isinstance(to_state, str):
        return to_state
    return f"<{to_state}>"


def decode_fsm(fsm_data):
    states = fsm_data.get("states", [])
    events = fsm_data.get("events", [])

    result = {
        "name": fsm_data.get("name", "Control"),
        "bundle": "scenes_scenes_scenes",
        "path_id": TARGET_PATH_ID,
        "num_states": len(states),
        "start_state": fsm_data.get("startState", 0),
    }

    variables = fsm_data.get("variables", {})
    result["variables"] = {}
    for vtype in ["floatVariables", "intVariables", "boolVariables",
                  "stringVariables", "vector3Variables"]:
        for v in variables.get(vtype, []):
            if isinstance(v, dict) and v.get("name"):
                result["variables"][v["name"]] = {
                    "type": vtype.replace("Variables", ""),
                    "value": v.get("value"),
                }

    result["events"] = []
    for e in events:
        if isinstance(e, dict):
            result["events"].append({
                "name": e.get("name", "?"),
                "isGlobal": bool(e.get("isGlobal", 0)),
            })

    result["global_transitions"] = []
    for t in fsm_data.get("globalTransitions", []):
        if isinstance(t, dict):
            evt = t.get("fsmEvent", {})
            ename = evt.get("name", "?") if isinstance(evt, dict) else str(evt)
            to = resolve_state_name(states, t.get("toState", -1))
            result["global_transitions"].append({"event": ename, "to": to})

    result["states"] = []
    for idx, s in enumerate(states):
        state_data = {
            "index": idx,
            "name": s.get("name", f"<{idx}>"),
            "transitions": [],
            "actions": [],
        }

        for t in s.get("transitions", []):
            evt = t.get("fsmEvent", {})
            ename = evt.get("name", "?") if isinstance(evt, dict) else str(evt)
            to = resolve_state_name(states, t.get("toState", -1))
            state_data["transitions"].append({"event": ename, "to": to})

        state_data["actions"] = decode_state_actions(s, events)
        result["states"].append(state_data)

    return result


def main():
    print("=" * 80)
    print("Lace Boss 'Control' FSM Decoder")
    print("=" * 80)

    print(f"\nLoading bundle: {TARGET_BUNDLE.name}")
    print("(This bundle has 4M+ objects — scanning for Lace FSM...)")

    env = UnityPy.load(str(TARGET_BUNDLE))
    tree, fsm_data = find_lace_fsm(env)

    if fsm_data is None:
        print("ERROR: Lace boss FSM not found!")
        sys.exit(1)

    states = fsm_data.get("states", [])
    print(f"\nFSM: Control")
    print(f"States: {len(states)}")
    print(f"Bundle: {TARGET_BUNDLE.name}")
    print(f"path_id: {TARGET_PATH_ID}")

    print("\nDecoding actions and parameters...")
    decoded = decode_fsm(fsm_data)

    out_json = SCRIPTS_DIR / "lace_control_fsm.json"
    with open(out_json, "w") as f:
        json.dump(decoded, f, indent=2, default=str)
    print(f"\nFull decoded FSM saved to: {out_json}")

    print(f"\n{'=' * 80}")
    print("FSM SUMMARY")
    print(f"{'=' * 80}")
    print(f"Total states: {decoded['num_states']}")
    print(f"Total events: {len(decoded['events'])}")
    print(f"Total variables: {len(decoded['variables'])}")
    print(f"Global transitions: {len(decoded['global_transitions'])}")

    categories = {
        "Setup/Init": [],
        "Idle/Movement": [],
        "Combo Slash": [],
        "Charge": [],
        "J Slash / Rising Slash": [],
        "Counter": [],
        "RapidSlash": [],
        "Downstab": [],
        "Evade/Hop": [],
        "Stun": [],
        "Multihit": [],
        "Teleport/Dive": [],
        "Quick Slash": [],
        "Tendril": [],
        "Vomit/Cast": [],
        "Bullet Summon": [],
        "Abyss Wave": [],
        "Cross Slash": [],
        "Phase Shifts": [],
        "Sing/Conduct": [],
        "Intro/Death": [],
        "Decision": [],
        "Other": [],
    }

    for s in decoded["states"]:
        name = s["name"]
        nl = name.lower()
        if nl in ("init", "start pause", "pause", "dormant", "start",
                   "setup refight", "stop", "lock end"):
            categories["Setup/Init"].append(name)
        elif "idle" in nl or "movement" in nl or "hero facing" in nl:
            categories["Idle/Movement"].append(name)
        elif "comboslash" in nl or "combo slash" in nl or "combo strike" in nl:
            categories["Combo Slash"].append(name)
        elif "charge" in nl and "rapid" not in nl:
            categories["Charge"].append(name)
        elif "j slash" in nl or "rising" in nl:
            categories["J Slash / Rising Slash"].append(name)
        elif "counter" in nl:
            categories["Counter"].append(name)
        elif "rapidslash" in nl:
            categories["RapidSlash"].append(name)
        elif "downstab" in nl or "dstab" in nl:
            categories["Downstab"].append(name)
        elif "evade" in nl or "hop" in nl:
            categories["Evade/Hop"].append(name)
        elif "stun" in nl or "damage" in nl:
            categories["Stun"].append(name)
        elif "multihit" in nl:
            categories["Multihit"].append(name)
        elif "tele" in nl or "dive" in nl or "splash" in nl:
            categories["Teleport/Dive"].append(name)
        elif "quick slash" in nl:
            categories["Quick Slash"].append(name)
        elif "tendril" in nl:
            categories["Tendril"].append(name)
        elif "vomit" in nl or "cast" in nl:
            categories["Vomit/Cast"].append(name)
        elif "bullet" in nl or "shot" in nl:
            categories["Bullet Summon"].append(name)
        elif "abyss" in nl or "wave" in nl:
            categories["Abyss Wave"].append(name)
        elif "cross" in nl or "cs " in nl or "thread" in nl:
            categories["Cross Slash"].append(name)
        elif "p2" in nl or "p3" in nl or "p4" in nl or "phase" in nl or "shift" in nl:
            categories["Phase Shifts"].append(name)
        elif "sing" in nl or "conduct" in nl or "roar" in nl:
            categories["Sing/Conduct"].append(name)
        elif "intro" in nl or "death" in nl or "pose" in nl or "silk" in nl:
            categories["Intro/Death"].append(name)
        elif "choice" in nl or "check" in nl or "set " in nl or "to attack" in nl:
            categories["Decision"].append(name)
        else:
            categories["Other"].append(name)

    print(f"\n--- States by Category ---")
    for cat, names in categories.items():
        if names:
            print(f"\n{cat} ({len(names)}):")
            for n in names:
                print(f"  - {n}")

    # Print key decision logic
    print(f"\n{'=' * 80}")
    print("KEY DECISION LOGIC — Attack Choice")
    print(f"{'=' * 80}")
    for s in decoded["states"]:
        if s["name"] == "Attack Choice":
            print("\nTransitions (what attacks are possible):")
            for t in s["transitions"]:
                print(f"  {t['event']} -> {t['to']}")
            print("\nActions:")
            for a in s["actions"]:
                print(f"  {a['name']}:", json.dumps(a.get("params", {}), indent=4))
            break

    print(f"\nDone.")


if __name__ == "__main__":
    main()
