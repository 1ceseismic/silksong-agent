# Animation-State Sprite Visualizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the pygame visualizer to render per-animation-state game sprites for boss and hero, replacing the idle-only sprite cycling.

**Architecture:** Offline extraction script crops sprites from tk2d atlas textures using UV coordinates, organizes them by animation clip name, and generates a sprite_map.json mapping sim states to clips. The visualizer preloads all sprites at startup (pre-scaled, `convert_alpha()`), then does O(1) dict lookups per tick with zero I/O in the render loop.

**Tech Stack:** UnityPy (extraction, python3), pygame (visualization, uv run), PIL/Pillow (atlas cropping)

---

## Data Model

### Sprite Map JSON (`assets/sprites/sprite_map.json`)

```json
{
  "boss": {
    "clips": {
      "Idle": {"fps": 12, "frames": 6},
      "Charge Antic": {"fps": 12, "frames": 4},
      ...
    },
    "state_map": {
      "0": {"0": "Idle"},
      "1": {"0": "Antic", "1": "Combo Strike 1", "2": "Combo Slash", "3": "Combo Strike 2", "4": "Combo Slash"},
      "2": {"0": "Charge Antic", "1": "Charge Antic", "2": "Charge", "3": "Charge Recover"},
      ...
    }
  },
  "hero": {
    "clips": {
      "idle": {"fps": 12, "frames": 6},
      "Hornet_run_new": {"fps": 12, "frames": 10},
      ...
    },
    "state_map": {
      "idle": "idle",
      "run": "Hornet_run_new",
      "airborne": "Hornet_jump_fast",
      "fall": "Hornet_fall",
      "dash": "Hornet_dash",
      "attack": "Hornet_slashes",
      "hurt": "Hornet_wound",
      "wall": "Tool_Wall_Cling"
    }
  }
}
```

### Directory Structure

```
assets/sprites/
  boss/
    Idle/0000.png, 0001.png, ...
    Charge Antic/0000.png, ...
    Combo Slash/0000.png, ...
    ...
  hero/
    idle/0000.png, ...
    Hornet_run_new/0000.png, ...
    Hornet_dash/0000.png, ...
    ...
  sprite_map.json
```

### Boss (categoryId, subStateId) → Clip Name Mapping

Derived from `sim/silksong_sim/src/boss.hpp` state machine:

| Category | Sub | Clip | Notes |
|----------|-----|------|-------|
| 0 (Idle) | 0 | Idle | |
| 1 (ComboSlash) | 0 | Antic | Windup |
| 1 | 1 | Combo Strike 1 | Lunge strike |
| 1 | 2 | Combo Slash | Standing strike |
| 1 | 3 | Combo Strike 2 | Lunge strike |
| 1 | 4 | Combo Slash | Final |
| 2 (Charge) | 0 | Charge Antic | Backward windup |
| 2 | 1 | Charge Antic | Break pause |
| 2 | 2 | Charge | Forward dash |
| 2 | 3 | Charge Recover | Decel |
| 3 (JSlash) | 0 | Jump Antic | Windup |
| 3 | 1 | Rising Slash | Diagonal launch |
| 3 | 2 | Fall | Decel in air |
| 3 | 3 | Downstab Antic | |
| 3 | 4 | Downstab | Diagonal dive |
| 3 | 5 | Wall Bounce | Wallcling |
| 4 (Counter) | 0 | Counter Antic | |
| 4 | 1 | Counter Stance | Invincible |
| 4 | 2 | Counter Hit | |
| 5 (RapidSlash) | 0 | RapidSlash Charge | Rush |
| 5 | 1 | RapidSlash Loop | |
| 5 | 2 | MultiHit Slash | |
| 5 | 3 | RapidSlash End | |
| 6 (Downstab) | 0 | Downstab | (rarely used, enters idle) |
| 7 (EvadeHop) | 0 | Evade | Backward dodge |
| 7 | 1 | Evade | Recover |
| 7 | 2 | Forward Hop | Move pick |
| 7 | 10 | Forward Hop | Hop check |
| 7 | 11 | Forward Hop | Hop forward |
| 7 | 12 | Forward Hop | Hop recover |
| 8 (Stun) | 0 | Stun | Knockback |
| 8 | 1 | Stun Air | |
| 8 | 2 | Stun | Land |
| 8 | 3 | Stun | Stunned timer |
| 8 | 4 | Stun Recover | |
| 9 (CrossSlash) | 0 | CrossSlash Antic | Invincible windup |
| 9 | 1 | CrossSlash Antic | Kinematic dash |
| 9 | 2 | MultiHit Slash | Appear at hero |
| 9 | 3 | Fall | Slam down |
| 10 (Lava) | 0 | Lava Damage | |
| 11 (Pose) | 0 | Pose Lean | |
| 11 | 1 | Pose Upright | |
| 11 | 2 | Pose Swish | |
| 12 (Sing) | 0 | Sing | |
| 13 (Death) | 0 | Death Stagger | |

### Hero State Inference

The sim does NOT populate `PlayerObs.animState` — it's always 0. Infer from other obs fields:

```
p[0]=posX, p[1]=posY, p[2]=velX, p[3]=velY,
p[4]=health, p[5]=maxHealth, p[6]=silk, p[7]=grounded,
p[8]=canDash, p[9]=facingRight, p[10]=invincible, p[11]=canAttack
```

Priority order (first match wins):
1. `invincible` → "hurt" (iframes after hit)
2. `!canAttack` → "attack" (attack cooldown active)
3. `!grounded && velY > 0` → "airborne" (rising)
4. `!grounded && velY <= 0` → "fall"
5. `grounded && |velX| > 2.0` → "run"
6. `grounded` → "idle"

---

## Task 1: Sprite Extraction Script

**Files:**
- Create: `scripts/extract_all_sprites.py`

- [ ] **Step 1: Write the extraction script skeleton**

Create `scripts/extract_all_sprites.py` with argument parsing, bundle path constants, and the main structure:

```python
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
from UnityPy.enums import ClassIDType
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
```

- [ ] **Step 2: Implement atlas loading and sprite cropping**

Add functions to load atlas textures and crop sprites using UV coordinates:

```python
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
```

- [ ] **Step 3: Implement collection loading**

Add a function to load a tk2dSpriteCollectionData MonoBehaviour and resolve its atlas textures:

```python
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
```

- [ ] **Step 4: Implement animation clip loading**

Load tk2dSpriteAnimation clips and resolve which collection they reference:

```python
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
```

- [ ] **Step 5: Implement boss sprite extraction**

Extract all Lace Cln sprites organized by animation clip name:

```python
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
```

- [ ] **Step 6: Implement hero sprite extraction**

Extract Knight sprites grouped by name prefix (no animation clips bundle for hero):

```python
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
```

- [ ] **Step 7: Implement sprite_map.json generation and main()**

Build the state map and write sprite_map.json:

```python
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
    "10": {"0": "Idle"},
    "11": {"0": "Pose Lean", "1": "Pose Upright", "2": "Pose Swish"},
    "12": {"0": "Idle"},
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
```

- [ ] **Step 8: Run the extraction script**

Run: `python3 scripts/extract_all_sprites.py`

Expected: Sprites extracted to `assets/sprites/boss/` and `assets/sprites/hero/`, `sprite_map.json` written. Verify a few PNGs look correct (open them).

- [ ] **Step 9: Commit extraction script and assets**

```bash
git add scripts/extract_all_sprites.py assets/sprites/sprite_map.json
git commit -m "feat: bulk tk2d sprite extraction for all animation clips"
```

Note: Don't commit the PNG files to git — they're large binary assets generated from the game bundles. Add `assets/sprites/boss/` and `assets/sprites/hero/` to `.gitignore` if not already ignored.

---

## Task 2: Visualizer Sprite Loading (Performant Preload)

**Files:**
- Modify: `sim/silksong_sim/scripts/visualize.py`

- [ ] **Step 1: Add sprite map loading and clip cache class**

Add a `SpriteCache` class that preloads ALL sprites at startup. This replaces the old `load_sprite_frames` / `scale_sprite_frames` approach. All I/O happens once during init; the render loop does only dict lookups and blits.

Add after the existing imports and constants (replace old `load_sprite_frames`, `scale_sprite_frames` functions):

```python
import json

ANIM_RATE_DEFAULT = 8  # ticks per frame when FPS not specified


class SpriteCache:
    """Preloads and caches all sprite clips at startup.

    All file I/O and scaling happens in __init__. The render loop
    calls get_frames() which is a pure dict lookup — no allocations,
    no file reads, no transforms.
    """

    def __init__(self, sprite_dir: Path, view: WorldView):
        self.clips: dict[str, dict[str, list[pygame.Surface]]] = {
            "boss": {},
            "hero": {},
        }
        self.boss_state_map: dict[int, dict[int, str]] = {}
        self.hero_state_map: dict[str, str] = {}
        self.clip_fps: dict[str, float] = {}

        map_path = sprite_dir / "sprite_map.json"
        if not map_path.exists():
            print("sprite_map.json not found — using idle-only fallback")
            self._load_legacy_idle(sprite_dir, view)
            return

        with open(map_path) as f:
            sprite_map = json.load(f)

        # Parse boss state map: str keys → int keys
        raw_boss_map = sprite_map.get("boss", {}).get("state_map", {})
        for cat_s, sub_map in raw_boss_map.items():
            cat = int(cat_s)
            self.boss_state_map[cat] = {}
            for sub_s, clip_name in sub_map.items():
                self.boss_state_map[cat][int(sub_s)] = clip_name

        # Parse hero state map
        self.hero_state_map = sprite_map.get("hero", {}).get("state_map", {})

        # Store clip FPS info
        for role in ("boss", "hero"):
            for clip_name, info in sprite_map.get(role, {}).get("clips", {}).items():
                self.clip_fps[clip_name] = info.get("fps", 12)

        # Preload boss sprites
        boss_dir = sprite_dir / "boss"
        boss_w = max(int(view.scale_x(BOSS_HALF_W * 2)), 4)
        boss_h = max(int(view.scale_y(BOSS_HALF_H * 2)), 4)
        self._preload_role("boss", boss_dir, boss_w, boss_h)

        # Preload hero sprites
        hero_dir = sprite_dir / "hero"
        hero_w = max(int(view.scale_x(HERO_HALF_W * 2)), 4)
        hero_h = max(int(view.scale_y(HERO_HALF_H * 2)), 4)
        self._preload_role("hero", hero_dir, hero_w, hero_h)

        total = sum(len(frames) for role in self.clips.values() for frames in role.values())
        print(f"SpriteCache: {total} frames preloaded ({len(self.clips['boss'])} boss clips, {len(self.clips['hero'])} hero clips)")

    def _preload_role(self, role: str, base_dir: Path, target_w: int, target_h: int):
        if not base_dir.exists():
            return
        for clip_dir in sorted(base_dir.iterdir()):
            if not clip_dir.is_dir():
                continue
            pngs = sorted(clip_dir.glob("*.png"))
            if not pngs:
                continue
            frames = []
            for png in pngs:
                try:
                    surf = pygame.image.load(str(png)).convert_alpha()
                    surf = pygame.transform.smoothscale(surf, (max(target_w, 1), max(target_h, 1)))
                    frames.append(surf)
                except pygame.error:
                    continue
            if frames:
                self.clips[role][clip_dir.name] = frames

    def _load_legacy_idle(self, sprite_dir: Path, view: WorldView):
        """Fallback: load old-style idle frames from flat sprite_dir."""
        hero_files = [sprite_dir / f for f in HERO_IDLE_FRAMES]
        boss_files = [sprite_dir / f for f in BOSS_IDLE_FRAMES]
        hero_w = max(int(view.scale_x(HERO_HALF_W * 2)), 4)
        hero_h = max(int(view.scale_y(HERO_HALF_H * 2)), 4)
        boss_w = max(int(view.scale_x(BOSS_HALF_W * 2)), 4)
        boss_h = max(int(view.scale_y(BOSS_HALF_H * 2)), 4)

        hero_frames = self._try_load_files(hero_files, hero_w, hero_h)
        if hero_frames:
            self.clips["hero"]["idle"] = hero_frames

        boss_frames = self._try_load_files(boss_files, boss_w, boss_h)
        if boss_frames:
            self.clips["boss"]["Idle"] = boss_frames

    def _try_load_files(self, paths: list[Path], tw: int, th: int) -> list[pygame.Surface]:
        frames = []
        for p in paths:
            if not p.exists():
                return []
            try:
                surf = pygame.image.load(str(p)).convert_alpha()
                surf = pygame.transform.smoothscale(surf, (max(tw, 1), max(th, 1)))
                frames.append(surf)
            except pygame.error:
                return []
        return frames

    def get_boss_frames(self, category: int, sub_state: int) -> Optional[list[pygame.Surface]]:
        """O(1) lookup: (categoryId, subStateId) → pre-scaled frames list."""
        sub_map = self.boss_state_map.get(category)
        if sub_map:
            clip = sub_map.get(sub_state) or sub_map.get(0)
            if clip and clip in self.clips["boss"]:
                return self.clips["boss"][clip]
        # Category-level fallback: sub 0
        if sub_map:
            clip = sub_map.get(0)
            if clip and clip in self.clips["boss"]:
                return self.clips["boss"][clip]
        # Ultimate fallback: Idle
        return self.clips["boss"].get("Idle")

    def get_hero_frames(self, state_key: str) -> Optional[list[pygame.Surface]]:
        """O(1) lookup: inferred state key → pre-scaled frames list."""
        clip = self.hero_state_map.get(state_key)
        if clip and clip in self.clips["hero"]:
            return self.clips["hero"][clip]
        return self.clips["hero"].get("idle")

    def get_clip_ticks_per_frame(self, clip_name: str, sim_fps: int = 50) -> int:
        """Convert clip FPS to sim ticks per frame for animation cycling."""
        clip_fps = self.clip_fps.get(clip_name, 12.0)
        if clip_fps <= 0:
            return ANIM_RATE_DEFAULT
        return max(int(sim_fps / clip_fps), 1)
```

- [ ] **Step 2: Add hero animation state inference function**

Add a function that derives the hero's visual state from observation fields:

```python
def infer_hero_state(p) -> str:
    """Infer hero animation state from PlayerObs tensor fields.

    Priority order (first match wins). Values from PlayerObs struct:
    p[7]=grounded, p[2]=velX, p[3]=velY, p[10]=invincible, p[11]=canAttack
    """
    invincible = p[10].item() > 0.5
    can_attack = p[11].item() > 0.5
    grounded = p[7].item() > 0.5
    vel_x = p[2].item()
    vel_y = p[3].item()

    if invincible:
        return "hurt"
    if not can_attack:
        return "attack"
    if not grounded and vel_y > 1.0:
        return "airborne"
    if not grounded:
        return "fall"
    if grounded and abs(vel_x) > 2.0:
        return "run"
    return "idle"
```

- [ ] **Step 3: Update blit_sprite to accept ticks_per_frame**

Replace the old `blit_sprite` with a version that uses per-clip animation rate:

```python
def blit_sprite(
    screen: pygame.Surface,
    frames: list[pygame.Surface],
    tick: int,
    sx: int, sy: int,
    facing_right: bool,
    ticks_per_frame: int = ANIM_RATE_DEFAULT,
):
    """Blit an animated sprite centered at (sx, sy), flipping if needed."""
    frame_idx = (tick // ticks_per_frame) % len(frames)
    sprite = frames[frame_idx]
    if not facing_right:
        sprite = pygame.transform.flip(sprite, True, False)
    w, h = sprite.get_size()
    screen.blit(sprite, (sx - w // 2, sy - h // 2))
```

- [ ] **Step 4: Update main() to use SpriteCache**

Replace the old sprite loading block in `main()` and update the render loop. Key changes:

1. Replace the sprite loading section (lines ~297-316) with:

```python
    # --- Sprite loading (all I/O happens here, before render loop) ---
    sprite_cache = SpriteCache(SPRITE_DIR, view)
```

2. Replace hero rendering (lines ~384-396) with:

```python
        # --- Hero rendering ---
        hero_sx, hero_sy = view.to_screen(hero_x, hero_y)
        hero_state = infer_hero_state(p)
        hero_frames = sprite_cache.get_hero_frames(hero_state)
        if hero_frames is not None:
            clip_name = sprite_cache.hero_state_map.get(hero_state, "idle")
            tpf = sprite_cache.get_clip_ticks_per_frame(clip_name, args.fps)
            blit_sprite(screen, hero_frames, tick_counter, hero_sx, hero_sy, hero_facing_right, tpf)
            if hero_invincible and (tick_counter // 4) % 2 == 0:
                w, h = hero_frames[0].get_size()
                flash_surf = pygame.Surface((w, h), pygame.SRCALPHA)
                flash_surf.fill((255, 255, 255, 100))
                screen.blit(flash_surf, (hero_sx - w // 2, hero_sy - h // 2))
        else:
            hero_color = COL_FLASH if hero_invincible else COL_HERO
            draw_rect_entity(screen, view, hero_x, hero_y, HERO_HALF_W, HERO_HALF_H, hero_color)
```

3. Replace boss rendering (lines ~399-404) with:

```python
        # --- Boss rendering ---
        boss_sx, boss_sy = view.to_screen(boss_x, boss_y)
        draw_boss_hitbox_overlay(screen, view, boss_x, boss_y, boss_category)
        boss_frames = sprite_cache.get_boss_frames(boss_category, boss_sub_state)
        if boss_frames is not None:
            sub_map = sprite_cache.boss_state_map.get(boss_category, {})
            clip_name = sub_map.get(boss_sub_state, sub_map.get(0, "Idle"))
            tpf = sprite_cache.get_clip_ticks_per_frame(clip_name, args.fps)
            blit_sprite(screen, boss_frames, tick_counter, boss_sx, boss_sy, boss_facing_right, tpf)
        else:
            draw_rect_entity(screen, view, boss_x, boss_y, BOSS_HALF_W, BOSS_HALF_H, COL_BOSS)
```

4. Remove the old `hero_sprites` / `boss_sprites` variables and the old loading block. Remove the now-unused `load_sprite_frames` and `scale_sprite_frames` functions.

- [ ] **Step 5: Run the visualizer and verify**

Run: `cd /home/seis/code/silksong-agent && uv run python sim/silksong_sim/scripts/visualize.py`

Verify:
- Sprites load at startup with a summary line like "SpriteCache: 847 frames preloaded (103 boss clips, 17 hero clips)"
- Boss shows different sprites when attacking, charging, idling, stunned
- Hero shows different sprites when running, jumping, attacking, getting hit
- FPS stays at target (50 fps) — no frame drops from sprite rendering
- Fallback to idle sprites when a clip isn't found
- Fallback to rectangles if no sprites exist at all

- [ ] **Step 6: Commit visualizer update**

```bash
git add sim/silksong_sim/scripts/visualize.py
git commit -m "feat: animation-state sprite rendering in visualizer"
```

---

## Task 3: Verify and Polish

- [ ] **Step 1: Run extraction and verify sprite output**

```bash
python3 scripts/extract_all_sprites.py --dry-run  # check what will be extracted
python3 scripts/extract_all_sprites.py             # extract
ls assets/sprites/boss/ | head -20                  # verify clip dirs exist
ls assets/sprites/hero/ | head -10                  # verify hero clips
cat assets/sprites/sprite_map.json | python3 -m json.tool | head -30  # verify map
```

- [ ] **Step 2: Visual smoke test**

Run the visualizer and observe:
1. Boss idle → Idle clip cycling
2. Boss charges → Charge Antic → Charge → Charge Recover clips switch
3. Boss combo → Antic → strikes cycling
4. Hero running → run sprites
5. Hero jumping → airborne sprites
6. Hero getting hit → hurt/wound sprites with invincibility flash
7. No FPS drops below 45 during heavy action

- [ ] **Step 3: Add .gitignore entries for extracted PNGs**

Add to `.gitignore`:
```
assets/sprites/boss/
assets/sprites/hero/
```

The sprite_map.json and the extraction script are committed; PNGs are generated locally from game bundles.

- [ ] **Step 4: Final commit**

```bash
git add .gitignore scripts/extract_all_sprites.py sim/silksong_sim/scripts/visualize.py
git commit -m "feat: animation-state sprite visualizer with tk2d extraction"
```
