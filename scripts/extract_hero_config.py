#!/usr/bin/env python3
"""Extract HeroControllerConfig values from Silksong game assets.

Reads the Hero_Hornet prefab from the heroloading bundle and dumps all
HeroController CAPS constants.  Attempts to follow the Config reference
to the HeroControllerConfig ScriptableObject for attack timing fields.

Usage:
    python scripts/extract_hero_config.py

Requires: UnityPy (pip install unitypy)
"""

import json
import sys
import warnings

warnings.filterwarnings("ignore")

import UnityPy

UnityPy.config.FALLBACK_UNITY_VERSION = "6000.0.50f1"

BUNDLE_PATH = (
    "/home/seis/game/Hollow Knight Silksong/"
    "Hollow Knight Silksong_Data/StreamingAssets/aa/"
    "StandaloneLinux64/heroloading_assets_all.bundle"
)

# Fields we want from the HeroControllerConfig ScriptableObject
CONFIG_FIELDS = [
    # Abilities (bool)
    "canPlayNeedolin", "canBrolly", "canDoubleJump",
    "canNailCharge", "canBind", "canHarpoonDash",
    "forceBareInventory",
    # Down slash
    "downSlashType", "downSlashEvent",
    "downspikeAnticTime", "downspikeTime", "downspikeSpeed",
    "downspikeRecoveryTime", "downspikeBurstEffect", "downspikeThrusts",
    # Dash stab
    "dashStabSpeed", "dashStabTime", "forceShortDashStabBounce",
    "dashStabBounceJumpSpeed", "dashStabSteps",
    # Attack timing
    "attackDuration", "quickAttackSpeedMult", "attackRecoveryTime",
    "attackCooldownTime", "quickAttackCooldownTime",
    "canTurnWhileSlashing",
    # Charge slash
    "chargeSlashRecoils", "chargeSlashLungeSpeed",
    "chargeSlashLungeDeceleration", "chargeSlashChain",
    "wallSlashSlowdown",
]

# Warrior-specific overrides
WARRIOR_FIELDS = [
    "rageAttackDuration", "rageAttackRecoveryTime",
    "rageAttackCooldownTime", "rageQuickAttackCooldownTime",
]


def extract_hero_controller(env):
    """Find and extract CAPS constants from HeroController MonoBehaviour."""
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            tree = obj.read_typetree()
        except Exception:
            continue
        if "INVUL_TIME" not in tree:
            continue

        print("=== HeroController CAPS Constants ===")
        print(f"path_id = {obj.path_id}")
        print()

        # Collect all CAPS-style constants
        caps = {}
        for k in sorted(tree.keys()):
            if k[0].isupper() and "_" in k:
                v = tree[k]
                if isinstance(v, (int, float)):
                    caps[k] = v
                elif isinstance(v, dict):
                    caps[k] = v  # e.g. MinMaxFloat

        for k, v in caps.items():
            print(f"  {k} = {v}")

        print()

        # Extract config references
        configs = tree.get("configs", [])
        print(f"Config references ({len(configs)} entries):")
        for i, cfg in enumerate(configs):
            ref = cfg.get("Config", {})
            print(f"  configs[{i}]: m_FileID={ref.get('m_FileID')}, "
                  f"m_PathID={ref.get('m_PathID')}")

        return tree, caps

    return None, None


def try_resolve_config(env, tree):
    """Attempt to resolve the Config ScriptableObject reference."""
    configs = tree.get("configs", [])
    if not configs:
        print("No config references found.")
        return None

    first_ref = configs[0].get("Config", {})
    file_id = first_ref.get("m_FileID", 0)
    path_id = first_ref.get("m_PathID", 0)

    print(f"\nAttempting to resolve configs[0] reference:")
    print(f"  m_FileID={file_id}, m_PathID={path_id}")

    if file_id == 0:
        # Same file - search by path_id
        for obj in env.objects:
            if obj.path_id == path_id:
                try:
                    cfg_tree = obj.read_typetree()
                    print("  RESOLVED (same file)")
                    return cfg_tree
                except Exception as e:
                    print(f"  Found object but can't read: {e}")
                    return None
    else:
        # External reference - find the CAB name
        for name, f in env.files.items():
            if hasattr(f, "files"):
                for subname, subf in f.files.items():
                    if hasattr(subf, "externals"):
                        idx = file_id - 1
                        if idx < len(subf.externals):
                            ext = subf.externals[idx]
                            print(f"  External CAB: {ext.name}")
                            print(f"  External path: {ext.path}")
                            print("  Cannot resolve - ScriptableObject is in "
                                  "a separate bundle.")
                            return None

    print("  Could not resolve reference.")
    return None


def search_all_bundles_for_config():
    """Search all bundles for a MonoBehaviour with attackDuration field."""
    import os
    bundle_dir = (
        "/home/seis/game/Hollow Knight Silksong/"
        "Hollow Knight Silksong_Data/StreamingAssets/aa/StandaloneLinux64/"
    )

    print("\nSearching all bundles for attackDuration field...")
    count = 0
    for fname in sorted(os.listdir(bundle_dir)):
        if not fname.endswith(".bundle"):
            continue
        count += 1
        fpath = os.path.join(bundle_dir, fname)
        try:
            env = UnityPy.load(fpath)
            for obj in env.objects:
                if obj.type.name != "MonoBehaviour":
                    continue
                try:
                    tree = obj.read_typetree()
                    if "attackDuration" in tree:
                        print(f"  FOUND in {fname} (path_id={obj.path_id})")
                        for field in CONFIG_FIELDS:
                            if field in tree:
                                print(f"    {field} = {tree[field]}")
                        return tree
                except Exception:
                    pass
        except Exception:
            pass

    print(f"  Not found in {count} bundles.")
    return None


def main():
    print(f"Loading bundle: {BUNDLE_PATH}")
    env = UnityPy.load(BUNDLE_PATH)
    print(f"Objects: {len(env.objects)}")
    print()

    # Step 1: Extract CAPS constants from HeroController
    tree, caps = extract_hero_controller(env)
    if tree is None:
        print("ERROR: HeroController not found!")
        sys.exit(1)

    # Step 2: Try to resolve Config ScriptableObject
    config_tree = try_resolve_config(env, tree)

    if config_tree is None:
        # Step 3: Search all bundles
        config_tree = search_all_bundles_for_config()

    if config_tree:
        print("\n=== HeroControllerConfig Values ===")
        for field in CONFIG_FIELDS:
            if field in config_tree:
                print(f"  {field} = {config_tree[field]}")
    else:
        print("\n=== HeroControllerConfig: NOT EXTRACTED ===")
        print("The ScriptableObject could not be found in any bundle.")
        print("Config fields must be determined from code analysis.")

    # Output JSON for easy consumption
    result = {"caps_constants": caps or {}}
    if config_tree:
        result["config_fields"] = {
            k: config_tree[k] for k in CONFIG_FIELDS
            if k in config_tree and isinstance(config_tree[k], (int, float, bool, str))
        }
    print(f"\n=== JSON ===")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
