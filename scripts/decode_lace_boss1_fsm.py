#!/usr/bin/env python3
"""Decode the Lace Boss1 'Control' PlayMaker FSM from bone_east_12 scene."""

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

SCRIPTS_DIR = Path("/home/seis/code/silksong-agent/scripts")

# Fingerprint states unique to Lace Boss1 (not in Lost Lace)
BOSS1_FINGERPRINT_STATES = [
    "distance check", "close", "far", "hop check",
    "lava damage", "lava hop", "kickoff", "wallcling",
]


def find_boss1_fsm(env):
    """Find the Lace Boss1 Control FSM in bone_east_12."""
    # Find the bone_east_12 bundle
    scene_key = None
    for k in env.files:
        if "bone_east_12" in k.lower():
            scene_key = k
            break

    if scene_key:
        print(f"Found scene key: {scene_key}")
        bundle_file = env.files[scene_key]

        # BundleFile has sub-files (SerializedFiles) — iterate those
        sub_files = {}
        if hasattr(bundle_file, "files"):
            sub_files = bundle_file.files

        for sf_key, sf in sub_files.items():
            if not hasattr(sf, "objects"):
                continue
            objs = sf.objects.values() if isinstance(sf.objects, dict) else sf.objects
            count = 0
            for obj in objs:
                if obj.type.name != "MonoBehaviour":
                    continue
                count += 1
                try:
                    tree = obj.read_typetree()
                    fsm = tree.get("fsm", {})
                    states = fsm.get("states", [])
                    if len(states) < 100:
                        continue
                    state_names = [s.get("name", "?") for s in states]
                    sn_lower = " | ".join(state_names).lower()
                    found = [kw for kw in BOSS1_FINGERPRINT_STATES if kw in sn_lower]
                    if len(found) >= 5:
                        print(f"Found Lace Boss1 FSM: path_id={obj.path_id} "
                              f"states={len(states)} matches={found}")
                        return tree, fsm, obj.path_id
                except Exception:
                    pass
            print(f"  Scanned {count} MonoBehaviours in {sf_key}")

    # Fallback: scan all objects across all files
    print("Scene-specific search failed, scanning all objects...")
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
            if len(states) < 100 or len(states) > 150:
                continue
            state_names = [s.get("name", "?") for s in states]
            sn_lower = " | ".join(state_names).lower()
            found = [kw for kw in BOSS1_FINGERPRINT_STATES if kw in sn_lower]
            if len(found) >= 5:
                print(f"Found Lace Boss1 FSM: path_id={obj.path_id} "
                      f"states={len(states)} matches={found}")
                return tree, fsm, obj.path_id
        except Exception:
            pass
    return None, None, None


def decode_state_actions(state, fsm_events):
    """Decode all actions and their parameters for a state."""
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

        # Special handling for SendRandomEvent variants
        if "SendRandomEvent" in short:
            events_list = []
            weights_list = []
            event_max_list = []
            missed_max_list = []
            active_bool = None

            current_section = None
            for pi in range(pstart, min(pend, len(param_names))):
                pname = param_names[pi]

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

        # Special handling for Wait actions
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


def decode_fsm(fsm_data, path_id):
    states = fsm_data.get("states", [])
    events = fsm_data.get("events", [])

    result = {
        "name": "Control",
        "gameObject": "Lace Boss1",
        "scene": "bone_east_12",
        "bundle": "scenes_scenes_scenes",
        "path_id": path_id,
        "num_states": len(states),
        "start_state": fsm_data.get("startState", 0),
    }

    # Variables
    variables = fsm_data.get("variables", {})
    result["variables"] = {}
    for vtype in ["floatVariables", "intVariables", "boolVariables",
                  "stringVariables", "vector3Variables", "vector2Variables"]:
        for v in variables.get(vtype, []):
            if isinstance(v, dict) and v.get("name"):
                result["variables"][v["name"]] = {
                    "type": vtype.replace("Variables", ""),
                    "value": v.get("value"),
                }

    # Events
    result["events"] = []
    for e in events:
        if isinstance(e, dict):
            result["events"].append({
                "name": e.get("name", "?"),
                "isGlobal": bool(e.get("isGlobal", 0)),
            })

    # Global transitions
    result["global_transitions"] = []
    for t in fsm_data.get("globalTransitions", []):
        if isinstance(t, dict):
            evt = t.get("fsmEvent", {})
            ename = evt.get("name", "?") if isinstance(evt, dict) else str(evt)
            to = resolve_state_name(states, t.get("toState", -1))
            result["global_transitions"].append({"event": ename, "to": to})

    # States
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
    print("Lace Boss1 'Control' FSM Decoder (bone_east_12)")
    print("=" * 80)

    print(f"\nLoading bundle: {TARGET_BUNDLE.name}")
    env = UnityPy.load(str(TARGET_BUNDLE))

    tree, fsm_data, path_id = find_boss1_fsm(env)

    if fsm_data is None:
        print("ERROR: Lace Boss1 FSM not found!")
        sys.exit(1)

    states = fsm_data.get("states", [])
    print(f"\nFSM: Control")
    print(f"States: {len(states)}")
    print(f"path_id: {path_id}")

    print("\nDecoding actions and parameters...")
    decoded = decode_fsm(fsm_data, path_id)

    out_json = SCRIPTS_DIR / "lace_boss1_control_fsm.json"
    with open(out_json, "w") as f:
        json.dump(decoded, f, indent=2, default=str)
    print(f"\nFull decoded FSM saved to: {out_json}")

    # Print summary
    print(f"\n{'=' * 80}")
    print("FSM SUMMARY")
    print(f"{'=' * 80}")
    print(f"Total states: {decoded['num_states']}")
    print(f"Total events: {len(decoded['events'])}")
    print(f"Total variables: {len(decoded['variables'])}")
    print(f"Global transitions: {len(decoded['global_transitions'])}")

    print("\n--- State List ---")
    for s in decoded["states"]:
        transitions_str = ", ".join(
            f"{t['event']}->{t['to']}" for t in s["transitions"]
        )
        action_names = [a["name"] for a in s["actions"]]
        print(f"  [{s['index']:3d}] {s['name']}")
        if transitions_str:
            print(f"        transitions: {transitions_str}")
        if action_names:
            print(f"        actions: {', '.join(action_names[:8])}"
                  f"{'...' if len(action_names) > 8 else ''}")

    print(f"\n--- Variables ---")
    for vname, vinfo in decoded["variables"].items():
        print(f"  {vname}: {vinfo['value']} ({vinfo['type']})")

    print(f"\n--- Global Transitions ---")
    for gt in decoded["global_transitions"]:
        print(f"  {gt['event']} -> {gt['to']}")

    print(f"\n--- Events ---")
    for e in decoded["events"]:
        g = " [GLOBAL]" if e["isGlobal"] else ""
        print(f"  {e['name']}{g}")

    print(f"\nDone.")


if __name__ == "__main__":
    main()
