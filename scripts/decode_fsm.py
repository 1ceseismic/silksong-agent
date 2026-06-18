#!/usr/bin/env python3
"""Decode PlayMaker Sprint FSM from Silksong asset bundles."""

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
TARGET_BUNDLE = BUNDLE_DIR / "fsmtemplates_assets_shared.bundle"
TARGET_PATH_ID = -5601421137281451283

METHOD_ENUM = {
    0: "SetAllowNailChargingWhileRelinquished",
    1: "RelinquishControlNotVelocity",
    2: "StopAnimationControl",
    3: "FlipSprite",
    4: "ShouldHardLand",
    5: "StartAnimationControlToIdle",
    6: "RegainControl",
    7: "RelinquishControl",
    8: "DoHardLanding",
    9: "SetAllowRecoilWhileRelinquished",
    10: "ResetGravity",
    11: "TryFsmCancelToWallSlide",
    12: "DashCooldownReady",
    13: "SetStartWithDash",
    14: "CouldJumpCancel",
    15: "SetStartWithAnyJump",
    16: "AffectedByGravity",
    17: "StartAnimationControl",
    18: "IncrementAttackCounter",
    19: "AllowShuttleCock",
    20: "SetSilkRegenBlocked",
    21: "MaxHealthKeepBlue",
    22: "StopPlayingAudio",
    23: "CancelAttack",
    24: "RefreshAnimationEvents",
    25: "CancelQueuedBounces",
    26: "SetToolCooldown",
    27: "ForceClampTerminalVelocity",
    28: "IsParryInvulnerable",
    29: "TrySpawnSoftLandEffect",
    30: "IsParryingActive",
    31: "BlockSteepSlopes",
    32: "PlayIdle",
    33: "IsHurt",
    34: "ThrowToolCooldownReady",
    35: "CanTryHarpoonDash",
    36: "StartAnimationControlToIdleForcePlay",
}


def decode_hcm_method(action_data: dict, action_index: int) -> str:
    start_indices = action_data.get("actionStartIndex", [])
    byte_data = action_data.get("byteData", [])
    param_data_pos = action_data.get("paramDataPos", [])
    param_data_type = action_data.get("paramDataType", [])
    param_byte_data_size = action_data.get("paramByteDataSize", [])

    if not (param_data_pos and param_data_type and param_byte_data_size):
        return "<?>"

    pstart = start_indices[action_index] if action_index < len(start_indices) else 0
    pend = (
        start_indices[action_index + 1]
        if action_index + 1 < len(start_indices)
        else len(param_data_type)
    )

    for pi in range(pstart, min(pend, len(param_data_type))):
        psize = param_byte_data_size[pi] if pi < len(param_byte_data_size) else 0
        ppos = param_data_pos[pi] if pi < len(param_data_pos) else -1
        if psize == 4 and ppos >= 0 and ppos + 4 <= len(byte_data):
            val = (
                byte_data[ppos]
                | (byte_data[ppos + 1] << 8)
                | (byte_data[ppos + 2] << 16)
                | (byte_data[ppos + 3] << 24)
            )
            return METHOD_ENUM.get(val, f"<enum:{val}>")
    return "<?>"


def main():
    print("=" * 80)
    print("Sprint FSM Decoder — Air Hang / gravityScale Investigation")
    print("=" * 80)

    env = UnityPy.load(str(TARGET_BUNDLE))
    target_obj = None
    for obj in env.objects:
        if obj.path_id == TARGET_PATH_ID:
            target_obj = obj
            break

    if target_obj is None:
        print(f"ERROR: path_id {TARGET_PATH_ID} not found!")
        sys.exit(1)

    tree = target_obj.read_typetree()
    fsm_data = tree.get("fsm", tree)
    states = fsm_data.get("states", [])
    state_names = {i: s.get("name", f"<{i}>") for i, s in enumerate(states)}

    print(f"\nFSM: {fsm_data.get('name', '?')}")
    print(f"States: {len(states)}")
    print(f"Bundle: {TARGET_BUNDLE.name}")
    print(f"path_id: {TARGET_PATH_ID}")

    variables = fsm_data.get("variables", {})
    if isinstance(variables, dict):
        print("\n--- FSM Variables (floats) ---")
        for var in variables.get("floatVariables", []):
            if isinstance(var, dict):
                print(f"  {var.get('name', '?')} = {var.get('value', '?')}")

    gravity_keywords = [
        "gravity", "grav", "air hang", "airhang", "bump",
        "SetGravity2dScale", "SetHeroAffectedByGravity",
        "HeroCheckForBumpV2", "ResetGravity",
    ]

    print("\n" + "=" * 80)
    print("GRAVITY / AIR-HANG RELATED STATES")
    print("=" * 80)

    for i, state in enumerate(states):
        sname = state.get("name", "")
        action_data = state.get("actionData", {})
        action_names = action_data.get("actionNames", [])
        ad_str = json.dumps(action_data, default=str)

        is_relevant = any(kw.lower() in (sname + ad_str).lower() for kw in gravity_keywords)
        if not is_relevant:
            continue

        print(f"\n{'='*60}")
        print(f"STATE [{i}]: {sname}")
        print(f"{'='*60}")

        transitions = state.get("transitions", [])
        if transitions:
            print("  Transitions:")
            for tr in transitions:
                event = tr.get("fsmEvent", {})
                ename = event.get("name", "?") if isinstance(event, dict) else str(event)
                to_state = tr.get("toState", -1)
                to_name = state_names.get(to_state, f"<{to_state}>")
                print(f"    {ename} -> [{to_state}] {to_name}")

        if action_names:
            print(f"  Actions ({len(action_names)}):")
            for ai, an in enumerate(action_names):
                short = an.split(".")[-1]
                extra = ""
                if "HeroControllerMethods" in an:
                    method = decode_hcm_method(action_data, ai)
                    extra = f" => {method}"
                elif "SetGravity2dScale" in an:
                    extra = " [SETS rb2d.gravityScale]"
                elif "SetHeroAffectedByGravity" in an:
                    extra = " [gravityScale 0/restore toggle]"
                elif "HeroCheckForBumpV2" in an:
                    extra = " [ceiling bump check, sends BUMP event]"
                print(f"    [{ai}] {short}{extra}")

    # Save full FSM JSON
    out_path = Path("/home/seis/code/silksong-agent/scripts/sprint_fsm_full.json")
    with open(out_path, "w") as f:
        json.dump(fsm_data, f, default=str, indent=2)
    print(f"\nFull FSM JSON saved to: {out_path}")
    print("Done.")


if __name__ == "__main__":
    main()
