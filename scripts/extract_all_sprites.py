#!/usr/bin/env python3
"""Extract all animation sprites from tk2d atlas bundles.

Reads tk2dSpriteCollectionData and tk2dSpriteAnimation from Unity bundles,
crops individual frames from atlas textures using UV coordinates, and
saves them organized by clip name.

Usage:
    python3 scripts/extract_all_sprites.py
    python3 scripts/extract_all_sprites.py --dry-run
    python3 scripts/extract_all_sprites.py --game-path /other/path
"""

import argparse
import json
import re
import sys
import warnings
from collections import defaultdict
from pathlib import Path

warnings.filterwarnings("ignore")

import UnityPy
from PIL import Image

UnityPy.config.FALLBACK_UNITY_VERSION = "6000.0.50f1"

DEFAULT_GAME_DATA = Path(
    "/home/seis/game/Hollow Knight Silksong/Hollow Knight Silksong_Data"
)
BUNDLE_DIR = DEFAULT_GAME_DATA / "StreamingAssets" / "aa" / "StandaloneLinux64"
OUT_DIR = Path(__file__).resolve().parent.parent / "assets" / "sprites"

BOSS_COLLECTION_BUNDLE = "tk2dcollections_assets_laceboss.bundle"
BOSS_ANIMATION_BUNDLE = "tk2danimations_assets_laceboss.bundle"
HERO_COLLECTION_BUNDLE = "herocollections_assets_shared.bundle"

TARGET_BOSS_COLLECTION = "Lace Cln"
TARGET_HERO_COLLECTION = "Knight"


def load_atlas_textures(env):
    """Load all Texture2D objects from a bundle, keyed by path_id."""
    textures = {}
    for obj in env.objects:
        if obj.type.name == "Texture2D":
            data = obj.read()
            img = data.image
            textures[obj.path_id] = img
            print(f"  Loaded texture: {data.m_Name} {img.width}x{img.height}")
    return textures


def crop_sprite(atlas: Image.Image, uvs: list[dict]) -> Image.Image:
    """Crop a sprite from an atlas using UV coordinates.

    UVs are normalized [0,1]. The 4 UV coords define a quad:
    [0]=bottom-left, [1]=bottom-right, [2]=top-left, [3]=top-right
    """
    w, h = atlas.size
    u_coords = [uv["x"] for uv in uvs]
    v_coords = [uv["y"] for uv in uvs]
    left = int(min(u_coords) * w)
    right = int(max(u_coords) * w)
    top = int((1.0 - max(v_coords)) * h)
    bottom = int((1.0 - min(v_coords)) * h)
    left = max(0, left)
    top = max(0, top)
    right = min(w, right)
    bottom = min(h, bottom)
    if right <= left or bottom <= top:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    return atlas.crop((left, top, right, bottom))


def load_collection(env, collection_name: str):
    """Load a named sprite collection from a bundle.

    Returns (sprite_defs, atlas_images) where atlas_images is indexed by materialId.
    """
    textures_by_pid = load_atlas_textures(env)

    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        tree = obj.read_typetree()
        if not isinstance(tree, dict):
            continue
        if tree.get("spriteCollectionName") != collection_name:
            continue

        defs = tree["spriteDefinitions"]
        tex_refs = tree.get("textures", [])
        atlases = {}
        for i, ref in enumerate(tex_refs):
            pid = ref.get("m_PathID", 0)
            if pid in textures_by_pid:
                atlases[i] = textures_by_pid[pid]

        print(f"  Collection '{collection_name}': {len(defs)} sprites, {len(atlases)} atlas(es)")
        return defs, atlases, obj.path_id

    print(f"  ERROR: Collection '{collection_name}' not found", file=sys.stderr)
    sys.exit(1)


def load_animation_clips(env, target_collection_pid: int):
    """Load animation clips that reference a specific sprite collection.

    Returns list of {name, fps, frame_sprite_ids}.
    """
    clips = []
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        tree = obj.read_typetree()
        if not isinstance(tree, dict) or "clips" not in tree:
            continue

        raw_clips = tree["clips"]
        if not raw_clips:
            continue

        first_frame = raw_clips[0].get("frames", [{}])[0]
        sc_ref = first_frame.get("spriteCollection", {})
        sc_pid = sc_ref.get("m_PathID", 0)
        if sc_pid != target_collection_pid:
            continue

        for c in raw_clips:
            name = c.get("name", "")
            if not name:
                continue
            fps = c.get("fps", 12.0)
            frames = c.get("frames", [])
            sprite_ids = [f.get("spriteId", 0) for f in frames]
            clips.append({"name": name, "fps": fps, "sprite_ids": sprite_ids})

        print(f"  Loaded {len(clips)} animation clips")
        return clips

    print("  WARNING: No matching animation clips found")
    return []


def extract_boss_sprites(bundle_dir: Path, out_dir: Path, dry_run: bool = False):
    """Extract boss (Lace) sprites organized by animation clip."""
    print("\n=== Extracting boss sprites ===")
    coll_env = UnityPy.load(str(bundle_dir / BOSS_COLLECTION_BUNDLE))
    defs, atlases, coll_pid = load_collection(coll_env, TARGET_BOSS_COLLECTION)

    anim_env = UnityPy.load(str(bundle_dir / BOSS_ANIMATION_BUNDLE))
    clips = load_animation_clips(anim_env, coll_pid)

    boss_dir = out_dir / "boss"
    clip_info = {}
    extracted = 0

    for clip in clips:
        clip_dir = boss_dir / clip["name"]
        if not dry_run:
            clip_dir.mkdir(parents=True, exist_ok=True)

        frame_count = 0
        for i, sid in enumerate(clip["sprite_ids"]):
            if sid >= len(defs):
                continue
            sd = defs[sid]
            mat_id = sd.get("materialId", 0)
            atlas = atlases.get(mat_id)
            if atlas is None:
                continue
            sprite_img = crop_sprite(atlas, sd["uvs"])
            if not dry_run:
                sprite_img.save(str(clip_dir / f"{i:04d}.png"))
            frame_count += 1
            extracted += 1

        if frame_count > 0:
            clip_info[clip["name"]] = {"fps": clip["fps"], "frames": frame_count}

    print(f"  Extracted {extracted} frames across {len(clip_info)} clips")
    return clip_info


HERO_CLIP_MAP = {
    "idle": "idle",
    "run": "Hornet_run_new",
    "airborne": "Hornet_jump_fast",
    "fall": "Hornet_fall",
    "dash": "Hornet_dash",
    "dash_air": "Hornet_dash_air",
    "attack": "Hornet_slashes",
    "attack_up": "Hornet_slash_up",
    "hurt": "Hornet_wound",
    "wall": "Tool_Wall_Cling",
    "hard_land": "Hornet_hard_land",
    "sprint": "Hornet_sprint",
    "double_jump": "Hornet_jump_double",
    "stun": "stun_ground",
    "recoil": "recoil_twirl",
    "turn": "turn",
    "land": "to_idle",
}

HERO_GROUPS_TO_EXTRACT = set(HERO_CLIP_MAP.values())


def extract_hero_sprites(bundle_dir: Path, out_dir: Path, dry_run: bool = False):
    """Extract hero (Hornet/Knight) sprites grouped by name prefix."""
    print("\n=== Extracting hero sprites ===")
    env = UnityPy.load(str(bundle_dir / HERO_COLLECTION_BUNDLE))
    defs, atlases, _ = load_collection(env, TARGET_HERO_COLLECTION)

    groups: dict[str, list[tuple[int, dict]]] = defaultdict(list)
    for idx, sd in enumerate(defs):
        name = sd.get("name", "")
        m = re.match(r"^(.+?)(\d{4})$", name)
        if m:
            prefix, frame_num = m.group(1), int(m.group(2))
            groups[prefix].append((frame_num, sd))
        else:
            groups[name].append((0, sd))

    hero_dir = out_dir / "hero"
    clip_info = {}
    extracted = 0

    for prefix in sorted(groups.keys()):
        if prefix not in HERO_GROUPS_TO_EXTRACT:
            continue
        frames = sorted(groups[prefix], key=lambda x: x[0])
        clip_dir = hero_dir / prefix
        if not dry_run:
            clip_dir.mkdir(parents=True, exist_ok=True)

        frame_count = 0
        for i, (_, sd) in enumerate(frames):
            mat_id = sd.get("materialId", 0)
            atlas = atlases.get(mat_id)
            if atlas is None:
                continue
            sprite_img = crop_sprite(atlas, sd["uvs"])
            if not dry_run:
                sprite_img.save(str(clip_dir / f"{i:04d}.png"))
            frame_count += 1
            extracted += 1

        if frame_count > 0:
            clip_info[prefix] = {"fps": 12, "frames": frame_count}

    print(f"  Extracted {extracted} frames across {len(clip_info)} clips")
    return clip_info


BOSS_STATE_MAP = {
    "0":  {"0": "Idle"},
    "1":  {"0": "Antic", "1": "Combo Strike 1", "2": "Combo Slash", "3": "Combo Strike 2", "4": "Combo Slash"},
    "2":  {"0": "Charge Antic", "1": "Charge Antic", "2": "Charge", "3": "Charge Recover"},
    "3":  {"0": "Jump Antic", "1": "Rising Slash", "2": "Fall", "3": "Downstab Antic", "4": "Downstab", "5": "Wall Bounce"},
    "4":  {"0": "Counter Antic", "1": "Counter Stance", "2": "Counter Hit"},
    "5":  {"0": "RapidSlash Charge", "1": "RapidSlash Loop", "2": "MultiHit Slash", "3": "RapidSlash End"},
    "6":  {"0": "Downstab"},
    "7":  {"0": "Evade", "1": "Evade", "2": "Forward Hop", "10": "Forward Hop", "11": "Forward Hop", "12": "Forward Hop"},
    "8":  {"0": "Stun", "1": "Stun Air", "2": "Stun", "3": "Stun", "4": "Stun Recover"},
    "9":  {"0": "CrossSlash Antic", "1": "CrossSlash Antic", "2": "MultiHit Slash", "3": "Fall"},
    "10": {"0": "Lava Damage"},
    "11": {"0": "Pose Lean", "1": "Pose Upright", "2": "Pose Swish"},
    "12": {"0": "Sing", "1": "Sing End"},
    "13": {"0": "Death Stagger"},
}


def main():
    parser = argparse.ArgumentParser(description="Extract all animation sprites from tk2d bundles.")
    parser.add_argument("--game-path", default=None, help="Override game data path")
    parser.add_argument("--dry-run", action="store_true", help="Don't write files, just report what would be extracted")
    args = parser.parse_args()

    bundle_dir = BUNDLE_DIR
    if args.game_path:
        bundle_dir = Path(args.game_path) / "StreamingAssets" / "aa" / "StandaloneLinux64"

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    boss_clips = extract_boss_sprites(bundle_dir, OUT_DIR, dry_run=args.dry_run)
    hero_clips = extract_hero_sprites(bundle_dir, OUT_DIR, dry_run=args.dry_run)

    sprite_map = {
        "boss": {
            "clips": boss_clips,
            "state_map": BOSS_STATE_MAP,
        },
        "hero": {
            "clips": hero_clips,
            "state_map": HERO_CLIP_MAP,
        },
    }

    map_path = OUT_DIR / "sprite_map.json"
    if not args.dry_run:
        with open(map_path, "w") as f:
            json.dump(sprite_map, f, indent=2)
        print(f"\nSprite map written to {map_path}")
    else:
        print(f"\n[dry-run] Would write sprite map to {map_path}")
        print(json.dumps(sprite_map, indent=2))

    print("\nDone.")


if __name__ == "__main__":
    main()
