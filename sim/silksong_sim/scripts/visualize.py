"""Pygame visualizer for the Silksong sim."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

_build_dir = str(Path(__file__).resolve().parent.parent / "build")
if os.path.isdir(_build_dir) and _build_dir not in sys.path:
    sys.path.insert(0, _build_dir)

sys.path.insert(0, str(Path(__file__).resolve().parent))

import torch
import pygame

import silksong_sim
from train_ppo import Policy, OBS_DIM, NUM_BINARY_ACTIONS, gather_obs

SPRITE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "assets" / "sprites"

# Idle frame filenames (order matters for animation cycling)
HERO_IDLE_FRAMES = [
    "idle0000.png", "idle0001.png", "idle0002.png",
    "idle0003.png", "idle0004.png", "idle0005.png",
]
BOSS_IDLE_FRAMES = [
    "battle_idle0000.png", "battle_idle0001.png", "battle_idle0002.png",
]

# Animation: advance one frame every N ticks
IDLE_ANIM_RATE = 8
ANIM_RATE_DEFAULT = 8

# Boss attack categories (1-7 are melee/attack categories in BOSS_CATEGORIES)
BOSS_ATTACK_CATEGORIES = set(range(1, 8))

BOSS_CATEGORIES = [
    "Idle", "ComboSlash", "Charge", "JSlash", "Counter", "RapidSlash",
    "Downstab", "EvadeHop", "Stun", "CrossSlash", "Lava", "Pose",
    "Sing", "Death",
]

BOSS_MAX_HP = 250
BOSS_PHASE_THRESHOLDS = []

HERO_HALF_W = 0.4
HERO_HALF_H = 0.568
BOSS_HALF_W = 0.415
BOSS_HALF_H = 1.28

BOSS_TELE_X_MIN = 82.4
BOSS_TELE_X_MAX = 105.6
BOSS_LAND_Y = 6.00

HERO_MAX_HP = 9

COL_BG         = (26, 26, 46)
COL_FLOOR_WALL = (85, 85, 85)
COL_HERO       = (68, 136, 255)
COL_BOSS       = (255, 68, 68)
COL_FLASH      = (255, 255, 255)
COL_HP_HERO    = (68, 255, 68)
COL_HP_BOSS    = (255, 68, 68)
COL_TEXT        = (255, 255, 255)
COL_TEXT_DIM    = (180, 180, 180)


class WorldView:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        # bone_east_12 arena. Platform at Y≈5.8, walls X=[82,106], lava below.
        self.world_min_x = 78.0
        self.world_max_x = 110.0
        self.world_min_y = -2.0
        self.world_max_y = 28.0
        self.margin = 50  # screen-edge padding in pixels

    def to_screen(self, wx: float, wy: float) -> tuple[int, int]:
        usable_w = self.width - 2 * self.margin
        usable_h = self.height - 2 * self.margin
        sx = self.margin + (wx - self.world_min_x) / (self.world_max_x - self.world_min_x) * usable_w
        sy = (self.height - self.margin) - (wy - self.world_min_y) / (self.world_max_y - self.world_min_y) * usable_h
        return int(sx), int(sy)

    def scale_x(self, w: float) -> float:
        usable_w = self.width - 2 * self.margin
        return w / (self.world_max_x - self.world_min_x) * usable_w

    def scale_y(self, h: float) -> float:
        usable_h = self.height - 2 * self.margin
        return h / (self.world_max_y - self.world_min_y) * usable_h


def draw_arena(screen: pygame.Surface, view: WorldView):
    fl_left = view.to_screen(BOSS_TELE_X_MIN, BOSS_LAND_Y)
    fl_right = view.to_screen(BOSS_TELE_X_MAX, BOSS_LAND_Y)
    pygame.draw.line(screen, COL_FLOOR_WALL, fl_left, fl_right, 2)

    wl_bot = view.to_screen(BOSS_TELE_X_MIN, BOSS_LAND_Y)
    wl_top = view.to_screen(BOSS_TELE_X_MIN, 28.0)
    pygame.draw.line(screen, COL_FLOOR_WALL, wl_bot, wl_top, 2)

    wr_bot = view.to_screen(BOSS_TELE_X_MAX, BOSS_LAND_Y)
    wr_top = view.to_screen(BOSS_TELE_X_MAX, 28.0)
    pygame.draw.line(screen, COL_FLOOR_WALL, wr_bot, wr_top, 2)


def draw_rect_entity(
    screen: pygame.Surface,
    view: WorldView,
    cx: float, cy: float,
    half_w: float, half_h: float,
    color: tuple[int, int, int],
):
    sx, sy = view.to_screen(cx - half_w, cy + half_h)
    w_px = max(int(view.scale_x(half_w * 2)), 2)
    h_px = max(int(view.scale_y(half_h * 2)), 2)
    pygame.draw.rect(screen, color, (sx, sy, w_px, h_px))


def draw_hp_bar_hero(screen: pygame.Surface, hp: int, max_hp: int, font: pygame.font.Font):
    bar_x, bar_y = 20, 20
    seg_w, seg_h = 20, 16
    gap = 3
    for i in range(max_hp):
        rect = pygame.Rect(bar_x + i * (seg_w + gap), bar_y, seg_w, seg_h)
        if i < hp:
            pygame.draw.rect(screen, COL_HP_HERO, rect)
        pygame.draw.rect(screen, COL_TEXT_DIM, rect, 1)
    label = font.render(f"Hero HP: {hp}/{max_hp}", True, COL_TEXT)
    screen.blit(label, (bar_x, bar_y + seg_h + 4))


def draw_hp_bar_boss(screen: pygame.Surface, hp: int, max_hp: int, width: int, font: pygame.font.Font):
    bar_x, bar_y = 20, 60
    bar_w = width - 40
    bar_h = 14

    pygame.draw.rect(screen, (60, 20, 20), (bar_x, bar_y, bar_w, bar_h))
    fill_w = max(int(hp / max_hp * bar_w), 0)
    pygame.draw.rect(screen, COL_HP_BOSS, (bar_x, bar_y, fill_w, bar_h))
    pygame.draw.rect(screen, COL_TEXT_DIM, (bar_x, bar_y, bar_w, bar_h), 1)

    for thresh in BOSS_PHASE_THRESHOLDS:
        tx = bar_x + int(thresh / max_hp * bar_w)
        pygame.draw.line(screen, COL_TEXT, (tx, bar_y), (tx, bar_y + bar_h), 1)

    label = font.render(f"Boss HP: {hp}/{max_hp}", True, COL_TEXT)
    screen.blit(label, (bar_x, bar_y + bar_h + 4))


def draw_boss_state(screen: pygame.Surface, category_id: int, sub_state: int, phase: float, font: pygame.font.Font):
    cat_name = BOSS_CATEGORIES[category_id] if 0 <= category_id < len(BOSS_CATEGORIES) else f"?{category_id}"
    label = font.render(f"Boss: {cat_name}.{sub_state}  P{int(phase)}", True, COL_TEXT)
    screen.blit(label, (20, 98))


def draw_fps(screen: pygame.Surface, fps: float, width: int, font: pygame.font.Font):
    label = font.render(f"FPS: {fps:.0f}", True, COL_TEXT_DIM)
    screen.blit(label, (width - label.get_width() - 20, 20))


def draw_episode_info(screen: pygame.Surface, reward_accum: float, episode_count: int, font: pygame.font.Font, width: int):
    label = font.render(f"Ep: {episode_count}  Reward: {reward_accum:+.1f}", True, COL_TEXT_DIM)
    screen.blit(label, (width - label.get_width() - 20, 40))


def draw_action_labels(screen: pygame.Surface, actions: torch.Tensor, font: pygame.font.Font, height: int):
    names = ["L", "R", "U", "D", "Jmp", "Atk", "Dsh", "Claw", "Skl", "Heal"]
    active = []
    for i, name in enumerate(names):
        if actions[i].item() > 0:
            active.append(name)
    text = "Actions: " + " ".join(active) if active else "Actions: (none)"
    label = font.render(text, True, COL_TEXT_DIM)
    screen.blit(label, (20, height - 30))


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

        raw_boss_map = sprite_map.get("boss", {}).get("state_map", {})
        for cat_s, sub_map in raw_boss_map.items():
            cat = int(cat_s)
            self.boss_state_map[cat] = {}
            for sub_s, clip_name in sub_map.items():
                self.boss_state_map[cat][int(sub_s)] = clip_name

        self.hero_state_map = sprite_map.get("hero", {}).get("state_map", {})

        for role in ("boss", "hero"):
            for clip_name, info in sprite_map.get(role, {}).get("clips", {}).items():
                self.clip_fps[clip_name] = info.get("fps", 12)

        boss_dir = sprite_dir / "boss"
        boss_w = max(int(view.scale_x(BOSS_HALF_W * 2)), 4)
        boss_h = max(int(view.scale_y(BOSS_HALF_H * 2)), 4)
        self._preload_role("boss", boss_dir, boss_w, boss_h)

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
        sub_map = self.boss_state_map.get(category)
        if sub_map:
            clip = sub_map.get(sub_state) or sub_map.get(0)
            if clip and clip in self.clips["boss"]:
                return self.clips["boss"][clip]
        if sub_map:
            clip = sub_map.get(0)
            if clip and clip in self.clips["boss"]:
                return self.clips["boss"][clip]
        return self.clips["boss"].get("Idle")

    def get_hero_frames(self, state_key: str) -> Optional[list[pygame.Surface]]:
        clip = self.hero_state_map.get(state_key)
        if clip and clip in self.clips["hero"]:
            return self.clips["hero"][clip]
        return self.clips["hero"].get("idle")

    def get_clip_ticks_per_frame(self, clip_name: str, sim_fps: int = 50) -> int:
        clip_fps = self.clip_fps.get(clip_name, 12.0)
        if clip_fps <= 0:
            return ANIM_RATE_DEFAULT
        return max(int(sim_fps / clip_fps), 1)


def infer_hero_state(p) -> str:
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


def blit_sprite(
    screen: pygame.Surface,
    frames: list[pygame.Surface],
    tick: int,
    sx: int, sy: int,
    facing_right: bool,
    ticks_per_frame: int = ANIM_RATE_DEFAULT,
):
    frame_idx = (tick // ticks_per_frame) % len(frames)
    sprite = frames[frame_idx]
    if not facing_right:
        sprite = pygame.transform.flip(sprite, True, False)
    w, h = sprite.get_size()
    screen.blit(sprite, (sx - w // 2, sy - h // 2))


def draw_boss_hitbox_overlay(
    screen: pygame.Surface,
    view: WorldView,
    boss_x: float, boss_y: float,
    boss_category: int,
):
    """Draw a semi-transparent orange rectangle when boss is in an attack category."""
    if boss_category not in BOSS_ATTACK_CATEGORIES:
        return
    # Attack hitbox extends beyond the boss body; use a wider box.
    atk_half_w = BOSS_HALF_W * 1.8
    atk_half_h = BOSS_HALF_H * 1.3
    sx, sy = view.to_screen(boss_x - atk_half_w, boss_y + atk_half_h)
    w_px = max(int(view.scale_x(atk_half_w * 2)), 2)
    h_px = max(int(view.scale_y(atk_half_h * 2)), 2)
    overlay = pygame.Surface((w_px, h_px), pygame.SRCALPHA)
    overlay.fill((255, 140, 0, 70))  # semi-transparent orange
    screen.blit(overlay, (sx, sy))


def main():
    ap = argparse.ArgumentParser(description="Silksong sim visualizer")
    ap.add_argument("--checkpoint", type=str, default=None,
                    help="path to policy .pt file")
    # keyboard control is the default when no --checkpoint is given
    ap.add_argument("--width", type=int, default=1200)
    ap.add_argument("--height", type=int, default=600)
    ap.add_argument("--fps", type=int, default=50)
    ap.add_argument("--device", default="cpu")
    args = ap.parse_args()

    sim = silksong_sim.SimManager(
        exec_mode=silksong_sim.madrona.ExecMode.CPU,
        gpu_id=0,
        num_worlds=1,
        rand_seed=42,
        auto_reset=True,
    )

    player_t = sim.player_obs_tensor().to_torch()
    boss_t = sim.boss_obs_tensor().to_torch()
    rayd_t = sim.raycast_distances_tensor().to_torch()
    rayh_t = sim.raycast_hit_types_tensor().to_torch()
    action_t = sim.action_tensor().to_torch()
    reward_t = sim.reward_tensor().to_torch()
    done_t = sim.done_tensor().to_torch()

    use_policy = args.checkpoint is not None
    device = torch.device(args.device)

    policy = Policy(OBS_DIM, NUM_BINARY_ACTIONS).to(device)
    if args.checkpoint:
        policy.load_state_dict(torch.load(args.checkpoint, weights_only=True))
        print(f"Loaded checkpoint: {args.checkpoint}")
    else:
        print("No checkpoint provided — using random actions")
    policy.eval()

    pygame.init()
    screen = pygame.display.set_mode((args.width, args.height))
    pygame.display.set_caption("Silksong Sim — Lace Boss Fight")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("monospace", 16)

    view = WorldView(args.width, args.height)

    # sprite loading, all i/o happens here before render loop
    sprite_cache = SpriteCache(SPRITE_DIR, view)

    arena_bg: Optional[pygame.Surface] = None
    arena_bg_path = SPRITE_DIR / "arena_bg.png"
    if arena_bg_path.exists():
        try:
            raw_bg = pygame.image.load(str(arena_bg_path)).convert()
            arena_bg = pygame.transform.smoothscale(raw_bg, (args.width - 2 * view.margin, args.height - 2 * view.margin))
            print(f"Loaded arena background: {arena_bg.get_size()}")
        except pygame.error:
            pass

    reward_accum = 0.0
    episode_count = 1
    tick_counter = 0
    current_action = torch.zeros(NUM_BINARY_ACTIONS, dtype=torch.int32)
    paused = False

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    paused = not paused

        if paused:
            fps_val = clock.get_fps()
            pygame.display.flip()
            clock.tick(args.fps)
            continue

        with torch.no_grad():
            obs = gather_obs(player_t, boss_t, rayd_t, rayh_t).to(device)
            if use_policy:
                logits, _ = policy(obs)
                action = (torch.sigmoid(logits) > 0.5).to(torch.int32)
                current_action = action[0].cpu()
                action_t.copy_(action.cpu().unsqueeze(1))
            else:
                # Keyboard control: WASD/arrows + J(attack) K(dash) Space(jump)
                keys = pygame.key.get_pressed()
                kb = torch.zeros(NUM_BINARY_ACTIONS, dtype=torch.int32)
                kb[0] = int(keys[pygame.K_LEFT] or keys[pygame.K_a])   # left
                kb[1] = int(keys[pygame.K_RIGHT] or keys[pygame.K_d])  # right
                kb[2] = int(keys[pygame.K_UP] or keys[pygame.K_w])     # up
                kb[3] = int(keys[pygame.K_DOWN] or keys[pygame.K_s])   # down
                kb[4] = int(keys[pygame.K_SPACE])                      # jump
                kb[5] = int(keys[pygame.K_j])                          # attack
                kb[6] = int(keys[pygame.K_k] or keys[pygame.K_LSHIFT]) # dash
                current_action = kb
                action_t[0, 0] = kb

        sim.step()

        p = player_t[0, 0].cpu()
        b = boss_t[0, 0].cpu()
        r = reward_t[0, 0, 0].item()
        d = done_t[0, 0, 0].item()

        reward_accum += r
        if d:
            episode_count += 1
            reward_accum = 0.0

        tick_counter += 1

        hero_x = p[0].item()
        hero_y = p[1].item()
        hero_hp = int(p[4].item())
        hero_max_hp = int(p[5].item())
        hero_facing_right = p[9].item() > 0.5
        hero_invincible = p[10].item() > 0.5

        boss_x = b[0].item()
        boss_y = b[1].item()
        boss_hp = int(b[4].item())
        boss_max_hp = int(b[5].item())
        boss_phase = b[6].item()
        boss_facing_right = b[7].item() > 0.5
        boss_category = int(b[8].item())
        boss_sub_state = int(b[9].item())

        screen.fill(COL_BG)
        if arena_bg is not None:
            screen.blit(arena_bg, (view.margin, view.margin))
        else:
            draw_arena(screen, view)

        # hero render
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

        draw_hp_bar_hero(screen, hero_hp, hero_max_hp or HERO_MAX_HP, font)
        draw_hp_bar_boss(screen, boss_hp, boss_max_hp or BOSS_MAX_HP, args.width, font)
        draw_boss_state(screen, boss_category, boss_sub_state, boss_phase, font)
        draw_action_labels(screen, current_action, font, args.height)

        sub_map = sprite_cache.boss_state_map.get(boss_category, {})
        boss_clip_dbg = sub_map.get(boss_sub_state, sub_map.get(0, "?"))
        dbg = font.render(
            f"Hero({hero_x:.1f},{hero_y:.1f}) [{hero_state}]  Boss({boss_x:.1f},{boss_y:.1f}) [{boss_clip_dbg}]",
            True, COL_TEXT_DIM)
        screen.blit(dbg, (20, args.height - 55))

        fps_val = clock.get_fps()
        draw_fps(screen, fps_val, args.width, font)
        draw_episode_info(screen, reward_accum, episode_count, font, args.width)

        pygame.display.flip()
        clock.tick(args.fps)

    pygame.quit()


if __name__ == "__main__":
    main()
