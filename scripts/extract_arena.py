#!/usr/bin/env python3
"""Extract ALL collision geometry from a Silksong scene for C++ sim consumption.

Computes world-space geometry for every collider, extracts MonoBehaviours,
Rigidbody2Ds, and builds a full hierarchy map.

Usage:
    python3 scripts/extract_arena.py                          # list scenes
    python3 scripts/extract_arena.py memory_silk_heart_lacetower
    python3 scripts/extract_arena.py memory_silk_heart_lacetower --boss-prefab laceboss
    python3 scripts/extract_arena.py memory_silk_heart_lacetower --game-path /other/path
"""

import argparse
import json
import math
import sys
import warnings
from collections import defaultdict
from pathlib import Path

warnings.filterwarnings("ignore")

import UnityPy
from UnityPy.enums import ClassIDType

UnityPy.config.FALLBACK_UNITY_VERSION = "6000.0.50f1"

DEFAULT_GAME_DATA = Path(
    "/home/seis/game/Hollow Knight Silksong/Hollow Knight Silksong_Data"
)
DEFAULT_BUNDLE_DIR = DEFAULT_GAME_DATA / "StreamingAssets" / "aa" / "StandaloneLinux64"
SCENE_SUPER_BUNDLE = "scenes_scenes_scenes"

OUT_DIR = Path(__file__).resolve().parent

# Map from friendly boss names to their prefab bundle filenames
BOSS_PREFAB_MAP = {
    "laceboss": "localpoolprefabs_assets_laceboss.bundle",
    "lace": "localpoolprefabs_assets_laceboss.bundle",
    "lace_area": "localpoolprefabs_assets_areacloverareamosslaceboss.bundle",
    "boss": "localpoolprefabs_assets_boss.bundle",
}

# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def quat_to_z_angle(qx, qy, qz, qw):
    """Extract Z-axis rotation angle (radians) from a quaternion."""
    siny_cosp = 2.0 * (qw * qz + qx * qy)
    cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
    return math.atan2(siny_cosp, cosy_cosp)


def rotate_point_2d(px, py, angle):
    """Rotate (px, py) by angle radians around origin."""
    c, s = math.cos(angle), math.sin(angle)
    return px * c - py * s, px * s + py * c


def local_to_world(transforms, tf_pid, lx=0.0, ly=0.0):
    """Transform a local-space point to world-space by walking up the hierarchy.

    Accumulates position, rotation, and scale from each ancestor.
    """
    x, y = lx, ly
    current = tf_pid
    while current and current in transforms:
        t = transforms[current]
        pos = t.get("m_LocalPosition", {})
        rot = t.get("m_LocalRotation", {})
        scl = t.get("m_LocalScale", {})
        sx = scl.get("x", 1.0)
        sy = scl.get("y", 1.0)
        angle = quat_to_z_angle(
            rot.get("x", 0), rot.get("y", 0), rot.get("z", 0), rot.get("w", 1)
        )
        # Apply parent's scale
        x *= sx
        y *= sy
        # Apply parent's rotation
        x, y = rotate_point_2d(x, y, angle)
        # Apply parent's translation
        x += pos.get("x", 0)
        y += pos.get("y", 0)
        parent_ref = t.get("m_Father", {})
        parent_pid = parent_ref.get("m_PathID", 0) if isinstance(parent_ref, dict) else 0
        if parent_pid == 0 or parent_pid == current:
            break
        current = parent_pid
    return round(x, 6), round(y, 6)


def get_world_scale(transforms, tf_pid):
    """Get cumulative scale by walking up the transform hierarchy."""
    sx_total, sy_total = 1.0, 1.0
    current = tf_pid
    while current and current in transforms:
        t = transforms[current]
        scl = t.get("m_LocalScale", {})
        sx_total *= scl.get("x", 1.0)
        sy_total *= scl.get("y", 1.0)
        parent_ref = t.get("m_Father", {})
        parent_pid = parent_ref.get("m_PathID", 0) if isinstance(parent_ref, dict) else 0
        if parent_pid == 0 or parent_pid == current:
            break
        current = parent_pid
    return sx_total, sy_total


def get_world_rotation(transforms, tf_pid):
    """Get cumulative Z rotation (radians) by walking up the transform hierarchy."""
    angle_total = 0.0
    current = tf_pid
    while current and current in transforms:
        t = transforms[current]
        rot = t.get("m_LocalRotation", {})
        angle_total += quat_to_z_angle(
            rot.get("x", 0), rot.get("y", 0), rot.get("z", 0), rot.get("w", 1)
        )
        parent_ref = t.get("m_Father", {})
        parent_pid = parent_ref.get("m_PathID", 0) if isinstance(parent_ref, dict) else 0
        if parent_pid == 0 or parent_pid == current:
            break
        current = parent_pid
    return angle_total


# ---------------------------------------------------------------------------
# Scene indexing
# ---------------------------------------------------------------------------

class SceneIndex:
    """Pre-read and index all objects in a scene for fast lookup."""

    def __init__(self, objects, label="scene"):
        self.label = label
        self.game_objects = {}       # pid -> typetree dict
        self.transforms = {}         # pid -> typetree dict
        self.go_to_tf = {}           # go_pid -> tf_pid
        self.tf_to_go = {}           # tf_pid -> go_pid
        self.go_parent = {}          # go_pid -> parent_go_pid
        self.go_children = defaultdict(list)  # go_pid -> [child_go_pids]
        self.go_components = defaultdict(list)  # go_pid -> [component_obj]
        self.obj_by_pid = {}         # pid -> obj

        self._all_objects = list(objects)
        for obj in self._all_objects:
            self.obj_by_pid[obj.path_id] = obj

        self._index_gameobjects()
        self._index_transforms()
        self._index_hierarchy()
        self._index_components()

    def _index_gameobjects(self):
        for obj in self._all_objects:
            if obj.type == ClassIDType.GameObject:
                try:
                    tree = obj.read_typetree()
                    self.game_objects[obj.path_id] = tree
                except Exception:
                    pass

    def _index_transforms(self):
        for obj in self._all_objects:
            if obj.type in (ClassIDType.Transform, ClassIDType.RectTransform):
                try:
                    tree = obj.read_typetree()
                    self.transforms[obj.path_id] = tree
                    go_pid = tree.get("m_GameObject", {}).get("m_PathID", 0)
                    if go_pid:
                        self.go_to_tf[go_pid] = obj.path_id
                        self.tf_to_go[obj.path_id] = go_pid
                except Exception:
                    pass

    def _index_hierarchy(self):
        for tf_pid, tf in self.transforms.items():
            parent_go = self.tf_to_go.get(tf_pid, 0)
            for child_ref in tf.get("m_Children", []):
                child_tf_pid = child_ref.get("m_PathID", 0)
                if child_tf_pid in self.transforms:
                    child_go = self.tf_to_go.get(child_tf_pid, 0)
                    if child_go and parent_go:
                        self.go_children[parent_go].append(child_go)
                        self.go_parent[child_go] = parent_go

    def _index_components(self):
        for go_pid, go in self.game_objects.items():
            for comp_pair in go.get("m_Component", []):
                comp_pid = comp_pair.get("component", {}).get("m_PathID", 0)
                if comp_pid and comp_pid in self.obj_by_pid:
                    self.go_components[go_pid].append(self.obj_by_pid[comp_pid])

    def go_name(self, go_pid):
        return self.game_objects.get(go_pid, {}).get("m_Name", f"?({go_pid})")

    def go_layer(self, go_pid):
        return self.game_objects.get(go_pid, {}).get("m_Layer", -1)

    def go_active(self, go_pid):
        return self.game_objects.get(go_pid, {}).get("m_IsActive", True)

    def hierarchy_path(self, go_pid):
        """Build the full hierarchy path for a GameObject."""
        parts = []
        current = go_pid
        depth = 0
        while current and depth < 50:
            parts.append(self.go_name(current))
            current = self.go_parent.get(current, 0)
            depth += 1
        parts.reverse()
        return "/".join(parts)

    def root_gos(self):
        return [pid for pid in self.game_objects if pid not in self.go_parent]


# ---------------------------------------------------------------------------
# Collider extraction
# ---------------------------------------------------------------------------

COLLIDER_TYPES = {
    "BoxCollider2D", "CircleCollider2D", "EdgeCollider2D", "PolygonCollider2D",
}


def extract_colliders(idx):
    """Extract all 2D colliders with world-space geometry."""
    colliders = []
    for go_pid, comps in idx.go_components.items():
        tf_pid = idx.go_to_tf.get(go_pid, 0)
        for obj in comps:
            tname = obj.type.name
            if tname not in COLLIDER_TYPES:
                continue
            try:
                tree = obj.read_typetree()
            except Exception:
                continue

            base = {
                "name": idx.go_name(go_pid),
                "hierarchy": idx.hierarchy_path(go_pid),
                "is_trigger": bool(tree.get("m_IsTrigger", False)),
                "layer": idx.go_layer(go_pid),
                "enabled": bool(tree.get("m_Enabled", True)),
                "go_active": idx.go_active(go_pid),
                "path_id": obj.path_id,
            }

            offset = tree.get("m_Offset", {})
            ox = offset.get("x", 0.0)
            oy = offset.get("y", 0.0)

            if tname == "BoxCollider2D":
                size = tree.get("m_Size", {})
                sw = size.get("x", 0.0)
                sh = size.get("y", 0.0)
                # World center = transform world pos + offset in world space
                wx, wy = local_to_world(idx.transforms, tf_pid, ox, oy)
                wsx, wsy = get_world_scale(idx.transforms, tf_pid)
                world_angle = get_world_rotation(idx.transforms, tf_pid)
                base.update({
                    "type": "box",
                    "world_x": wx,
                    "world_y": wy,
                    "width": round(abs(sw * wsx), 6),
                    "height": round(abs(sh * wsy), 6),
                    "offset_x": ox,
                    "offset_y": oy,
                    "local_size_x": sw,
                    "local_size_y": sh,
                    "rotation_deg": round(math.degrees(world_angle), 4),
                })

            elif tname == "CircleCollider2D":
                radius = tree.get("m_Radius", 0.0)
                wx, wy = local_to_world(idx.transforms, tf_pid, ox, oy)
                wsx, wsy = get_world_scale(idx.transforms, tf_pid)
                # Circle radius scales by the max of x/y scale
                world_radius = radius * max(abs(wsx), abs(wsy))
                base.update({
                    "type": "circle",
                    "world_x": wx,
                    "world_y": wy,
                    "radius": round(world_radius, 6),
                    "local_radius": radius,
                    "offset_x": ox,
                    "offset_y": oy,
                })

            elif tname == "EdgeCollider2D":
                points_local = tree.get("m_Points", [])
                world_points = []
                if isinstance(points_local, list):
                    for pt in points_local:
                        if isinstance(pt, dict):
                            px = pt.get("x", 0.0) + ox
                            py = pt.get("y", 0.0) + oy
                            wpx, wpy = local_to_world(idx.transforms, tf_pid, px, py)
                            world_points.append([round(wpx, 6), round(wpy, 6)])
                base.update({
                    "type": "edge",
                    "points": world_points,
                    "point_count": len(world_points),
                    "offset_x": ox,
                    "offset_y": oy,
                })

            elif tname == "PolygonCollider2D":
                points_data = tree.get("m_Points", {})
                paths_raw = []
                if isinstance(points_data, dict):
                    paths_raw = points_data.get("m_Paths", [])
                elif isinstance(points_data, list):
                    paths_raw = [points_data]

                all_world_points = []
                for path in (paths_raw if isinstance(paths_raw, list) else []):
                    path_pts = []
                    if isinstance(path, list):
                        for pt in path:
                            if isinstance(pt, dict):
                                px = pt.get("x", 0.0) + ox
                                py = pt.get("y", 0.0) + oy
                                wpx, wpy = local_to_world(idx.transforms, tf_pid, px, py)
                                path_pts.append([round(wpx, 6), round(wpy, 6)])
                    if path_pts:
                        all_world_points.append(path_pts)

                base.update({
                    "type": "polygon",
                    "paths": all_world_points,
                    "path_count": len(all_world_points),
                    "total_points": sum(len(p) for p in all_world_points),
                    "offset_x": ox,
                    "offset_y": oy,
                })

            colliders.append(base)

    return colliders


# ---------------------------------------------------------------------------
# Rigidbody2D extraction
# ---------------------------------------------------------------------------

def extract_rigidbodies(idx):
    """Extract all Rigidbody2D components."""
    bodies = []
    for go_pid, comps in idx.go_components.items():
        for obj in comps:
            if obj.type.name != "Rigidbody2D":
                continue
            try:
                tree = obj.read_typetree()
            except Exception:
                continue
            tf_pid = idx.go_to_tf.get(go_pid, 0)
            wx, wy = local_to_world(idx.transforms, tf_pid)
            bodies.append({
                "name": idx.go_name(go_pid),
                "hierarchy": idx.hierarchy_path(go_pid),
                "world_x": wx,
                "world_y": wy,
                "gravity_scale": tree.get("m_GravityScale", 1.0),
                "mass": tree.get("m_Mass", 1.0),
                "body_type": tree.get("m_BodyType", 0),
                "linear_drag": tree.get("m_LinearDrag", 0.0),
                "angular_drag": tree.get("m_AngularDrag", 0.05),
                "layer": idx.go_layer(go_pid),
                "path_id": obj.path_id,
            })
    return bodies


# ---------------------------------------------------------------------------
# MonoBehaviour extraction
# ---------------------------------------------------------------------------

def extract_monobehaviours(idx):
    """Extract interesting MonoBehaviours: FSMs, DamageHero, HealthManager, HeroController."""
    results = []
    for go_pid, comps in idx.go_components.items():
        go_name = idx.go_name(go_pid)
        for obj in comps:
            if obj.type.name != "MonoBehaviour":
                continue
            try:
                tree = obj.read_typetree()
            except Exception:
                continue
            if not isinstance(tree, dict):
                continue

            keys = set(tree.keys())
            entry = {
                "name": go_name,
                "hierarchy": idx.hierarchy_path(go_pid),
                "path_id": obj.path_id,
                "layer": idx.go_layer(go_pid),
            }

            # PlayMaker FSM
            if "fsm" in keys:
                fsm = tree.get("fsm", {})
                if not isinstance(fsm, dict):
                    continue
                fsm_name = fsm.get("name", "")
                states = fsm.get("states", [])
                state_names = []
                if isinstance(states, list):
                    state_names = [s.get("name", "?") for s in states if isinstance(s, dict)]
                variables = fsm.get("variables", {})
                var_dict = {}
                if isinstance(variables, dict):
                    for vtype in ("floatVariables", "intVariables", "boolVariables", "stringVariables"):
                        for v in variables.get(vtype, []):
                            if isinstance(v, dict) and v.get("name"):
                                var_dict[v["name"]] = v.get("value")

                entry.update({
                    "component_type": "FSM",
                    "fsm_name": fsm_name,
                    "state_count": len(state_names),
                    "states": state_names,
                    "variables": var_dict,
                })
                results.append(entry)
                continue

            # DamageHero
            if "damageDealt" in keys:
                entry.update({
                    "component_type": "DamageHero",
                    "damageDealt": tree.get("damageDealt"),
                    "hazardType": tree.get("hazardType"),
                    "canClashTink": tree.get("canClashTink"),
                    "forceParry": tree.get("forceParry"),
                    "shadowDashHazard": tree.get("shadowDashHazard"),
                })
                results.append(entry)
                continue

            # HealthManager
            if "hp" in keys and ("stunHits" in keys or "stunDuration" in keys or "IsInvincible" in keys):
                scalar_fields = {}
                for k in sorted(keys):
                    v = tree[k]
                    if isinstance(v, (int, float, bool, str)) and not k.startswith("m_"):
                        scalar_fields[k] = v
                entry.update({
                    "component_type": "HealthManager",
                    **scalar_fields,
                })
                results.append(entry)
                continue

            # HeroController
            if "INVUL_TIME" in keys or "RECOIL_HOR_VELOCITY" in keys or "RUN_SPEED" in keys:
                scalar_fields = {}
                for k in sorted(keys):
                    v = tree[k]
                    if isinstance(v, (int, float, bool, str)) and not k.startswith("m_"):
                        scalar_fields[k] = v
                entry.update({
                    "component_type": "HeroController",
                    **scalar_fields,
                })
                results.append(entry)
                continue

            # Anything on a "boss/lace/hero"-named GO
            go_lower = go_name.lower()
            if any(kw in go_lower for kw in ("lace", "boss", "hero")):
                scalar_fields = {}
                for k in sorted(keys):
                    v = tree[k]
                    if isinstance(v, (int, float, bool, str)) and not k.startswith("m_"):
                        scalar_fields[k] = v
                if scalar_fields:
                    entry.update({
                        "component_type": "MonoBehaviour",
                        "fields": scalar_fields,
                    })
                    results.append(entry)

    return results


# ---------------------------------------------------------------------------
# Hierarchy dump
# ---------------------------------------------------------------------------

def dump_hierarchy(idx, max_depth=20):
    """Build a list of all GameObjects with world positions."""
    hierarchy = []

    def walk(go_pid, depth=0):
        if depth > max_depth:
            return
        tf_pid = idx.go_to_tf.get(go_pid, 0)
        wx, wy = local_to_world(idx.transforms, tf_pid)
        hierarchy.append({
            "name": idx.go_name(go_pid),
            "path": idx.hierarchy_path(go_pid),
            "depth": depth,
            "world_x": wx,
            "world_y": wy,
            "layer": idx.go_layer(go_pid),
            "active": idx.go_active(go_pid),
            "child_count": len(idx.go_children.get(go_pid, [])),
        })
        for child in idx.go_children.get(go_pid, []):
            walk(child, depth + 1)

    for root in sorted(idx.root_gos()):
        walk(root)

    return hierarchy


# ---------------------------------------------------------------------------
# ASCII map generation
# ---------------------------------------------------------------------------

def generate_ascii_map(colliders, width=100, height=40):
    """Generate an ASCII map of the arena from non-trigger solid colliders."""
    solid = [c for c in colliders if not c.get("is_trigger") and c.get("enabled", True)]
    if not solid:
        return "No solid colliders found."

    # Gather all world-space points for bounds
    all_x, all_y = [], []
    for c in solid:
        if c["type"] == "box":
            cx, cy = c["world_x"], c["world_y"]
            hw, hh = c["width"] / 2, c["height"] / 2
            all_x.extend([cx - hw, cx + hw])
            all_y.extend([cy - hh, cy + hh])
        elif c["type"] == "circle":
            cx, cy = c["world_x"], c["world_y"]
            r = c["radius"]
            all_x.extend([cx - r, cx + r])
            all_y.extend([cy - r, cy + r])
        elif c["type"] in ("edge", "polygon"):
            pts = c.get("points", [])
            if c["type"] == "polygon":
                pts = [pt for path in c.get("paths", []) for pt in path]
            for pt in pts:
                if isinstance(pt, list) and len(pt) >= 2:
                    all_x.append(pt[0])
                    all_y.append(pt[1])

    if not all_x:
        return "No geometry points found."

    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)

    # Add padding
    pad_x = (max_x - min_x) * 0.05 + 1
    pad_y = (max_y - min_y) * 0.05 + 1
    min_x -= pad_x
    max_x += pad_x
    min_y -= pad_y
    max_y += pad_y

    range_x = max_x - min_x
    range_y = max_y - min_y
    if range_x == 0 or range_y == 0:
        return "Degenerate bounds."

    # Build grid (y=0 is top)
    grid = [[" " for _ in range(width)] for _ in range(height)]

    def plot(wx, wy, ch):
        col = int((wx - min_x) / range_x * (width - 1))
        row = int((1.0 - (wy - min_y) / range_y) * (height - 1))  # flip y
        if 0 <= col < width and 0 <= row < height:
            grid[row][col] = ch

    def plot_line(x1, y1, x2, y2, ch):
        steps = max(abs(int((x2 - x1) / range_x * width)),
                     abs(int((y2 - y1) / range_y * height)), 1)
        for i in range(steps + 1):
            t = i / steps
            plot(x1 + t * (x2 - x1), y1 + t * (y2 - y1), ch)

    for c in solid:
        name_lower = c.get("name", "").lower()
        # Choose character
        if "floor" in name_lower or "ground" in name_lower:
            ch = "="
        elif "wall" in name_lower:
            ch = "|"
        elif "plat" in name_lower:
            ch = "-"
        elif "spike" in name_lower or "hazard" in name_lower or "lava" in name_lower:
            ch = "!"
        else:
            ch = "#"

        if c["type"] == "box":
            cx, cy = c["world_x"], c["world_y"]
            hw, hh = c["width"] / 2, c["height"] / 2
            # Draw rectangle edges
            plot_line(cx - hw, cy - hh, cx + hw, cy - hh, ch)
            plot_line(cx - hw, cy + hh, cx + hw, cy + hh, ch)
            plot_line(cx - hw, cy - hh, cx - hw, cy + hh, ch)
            plot_line(cx + hw, cy - hh, cx + hw, cy + hh, ch)
        elif c["type"] == "circle":
            cx, cy = c["world_x"], c["world_y"]
            r = c["radius"]
            for angle_deg in range(0, 360, 5):
                a = math.radians(angle_deg)
                plot(cx + r * math.cos(a), cy + r * math.sin(a), ch)
        elif c["type"] in ("edge", "polygon"):
            pts = c.get("points", [])
            if c["type"] == "polygon":
                pts = [pt for path in c.get("paths", []) for pt in path]
            for i in range(len(pts) - 1):
                if isinstance(pts[i], list) and isinstance(pts[i + 1], list):
                    plot_line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], ch)
            # Close polygon
            if c["type"] == "polygon" and len(pts) >= 3:
                plot_line(pts[-1][0], pts[-1][1], pts[0][0], pts[0][1], ch)

    lines = ["".join(row).rstrip() for row in grid]
    # Trim empty lines from top and bottom
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()

    header = f"Bounds: x=[{min_x:.1f}, {max_x:.1f}] y=[{min_y:.1f}, {max_y:.1f}]"
    return header + "\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# Summary generation
# ---------------------------------------------------------------------------

def generate_summary(scene_name, colliders, rigidbodies, monobehaviours, hierarchy):
    """Generate a human-readable markdown summary."""
    lines = [f"# Arena Summary: {scene_name}", ""]

    # Stats
    lines.append("## Statistics")
    lines.append(f"- Total colliders: {len(colliders)}")
    from collections import Counter
    type_counts = Counter(c["type"] for c in colliders)
    for t, cnt in type_counts.most_common():
        lines.append(f"  - {t}: {cnt}")
    trigger_count = sum(1 for c in colliders if c.get("is_trigger"))
    solid_count = len(colliders) - trigger_count
    lines.append(f"- Solid colliders: {solid_count}")
    lines.append(f"- Trigger colliders: {trigger_count}")
    lines.append(f"- Rigidbody2D count: {len(rigidbodies)}")
    lines.append(f"- MonoBehaviour count: {len(monobehaviours)}")
    lines.append(f"- GameObject count: {len(hierarchy)}")
    lines.append("")

    # ASCII map
    lines.append("## Arena Map (ASCII)")
    lines.append("```")
    lines.append(generate_ascii_map(colliders))
    lines.append("```")
    lines.append("")

    # Colliders sorted by type then position
    lines.append("## Colliders by Type")
    for ctype in ("box", "edge", "polygon", "circle"):
        typed = [c for c in colliders if c["type"] == ctype]
        if not typed:
            continue
        lines.append(f"\n### {ctype.title()} Colliders ({len(typed)})")
        typed.sort(key=lambda c: (c.get("world_x", 0), c.get("world_y", 0)))
        for c in typed:
            trigger_str = " [TRIGGER]" if c.get("is_trigger") else ""
            disabled_str = " [DISABLED]" if not c.get("enabled", True) else ""
            if ctype == "box":
                lines.append(
                    f"- **{c['name']}** at ({c['world_x']:.2f}, {c['world_y']:.2f}) "
                    f"size {c['width']:.2f}x{c['height']:.2f}"
                    f"{trigger_str}{disabled_str}"
                )
                if abs(c.get("rotation_deg", 0)) > 0.1:
                    lines.append(f"  - rotation: {c['rotation_deg']:.1f} deg")
            elif ctype == "circle":
                lines.append(
                    f"- **{c['name']}** at ({c['world_x']:.2f}, {c['world_y']:.2f}) "
                    f"r={c['radius']:.2f}"
                    f"{trigger_str}{disabled_str}"
                )
            elif ctype == "edge":
                lines.append(
                    f"- **{c['name']}** {c['point_count']} points"
                    f"{trigger_str}{disabled_str}"
                )
                if c.get("points"):
                    xs = [p[0] for p in c["points"]]
                    ys = [p[1] for p in c["points"]]
                    lines.append(
                        f"  - x range: [{min(xs):.2f}, {max(xs):.2f}] "
                        f"y range: [{min(ys):.2f}, {max(ys):.2f}]"
                    )
            elif ctype == "polygon":
                lines.append(
                    f"- **{c['name']}** {c['path_count']} paths, "
                    f"{c['total_points']} points"
                    f"{trigger_str}{disabled_str}"
                )
        lines.append(f"  - hierarchy: {c.get('hierarchy', '')}")

    # Hazard zones
    hazards = [c for c in colliders
               if any(kw in c.get("name", "").lower()
                      for kw in ("spike", "hazard", "lava", "acid", "thorn", "kill"))]
    if hazards:
        lines.append("\n## Hazard Zones")
        for h in hazards:
            lines.append(f"- **{h['name']}** ({h['type']}) at ({h.get('world_x', 0):.2f}, {h.get('world_y', 0):.2f})")

    # Spawn points
    lines.append("\n## Notable GameObjects")
    for go in hierarchy:
        name_lower = go["name"].lower()
        if any(kw in name_lower for kw in ("spawn", "boss", "hero", "lace", "start", "entry", "bench")):
            lines.append(f"- **{go['name']}** at ({go['world_x']:.2f}, {go['world_y']:.2f}) [layer={go['layer']}]")

    # Rigidbodies
    if rigidbodies:
        lines.append("\n## Rigidbody2D Components")
        for rb in rigidbodies:
            lines.append(
                f"- **{rb['name']}** gravity={rb['gravity_scale']} mass={rb['mass']} "
                f"bodyType={rb['body_type']}"
            )

    # FSMs
    fsms = [m for m in monobehaviours if m.get("component_type") == "FSM"]
    if fsms:
        lines.append("\n## PlayMaker FSMs")
        for f in fsms:
            lines.append(f"- **{f['name']}** / {f['fsm_name']} ({f['state_count']} states)")
            if f.get("variables"):
                for vname, vval in sorted(f["variables"].items()):
                    lines.append(f"  - {vname}: {vval}")

    # DamageHero
    dmg_heroes = [m for m in monobehaviours if m.get("component_type") == "DamageHero"]
    if dmg_heroes:
        lines.append("\n## DamageHero Components")
        for d in dmg_heroes:
            lines.append(f"- **{d['name']}** damage={d.get('damageDealt')} hazardType={d.get('hazardType')}")

    # HealthManagers
    hms = [m for m in monobehaviours if m.get("component_type") == "HealthManager"]
    if hms:
        lines.append("\n## HealthManager Components")
        for h in hms:
            lines.append(f"- **{h['name']}** hp={h.get('hp')}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Scene listing
# ---------------------------------------------------------------------------

def list_scenes(bundle_dir):
    """List all available scenes in the super-bundle."""
    super_path = bundle_dir / SCENE_SUPER_BUNDLE
    if not super_path.exists():
        print(f"ERROR: Scene super-bundle not found at {super_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading scene catalog from {super_path}...")
    env = UnityPy.load(str(super_path))

    # Extract scene names from the file keys
    scenes = []
    prefix = str(super_path) + "/"
    for k in sorted(env.files.keys()):
        name = k
        if name.startswith(prefix):
            name = name[len(prefix):]
        if name.endswith(".bundle"):
            name = name[:-7]
        scenes.append(name)

    print(f"\nAvailable scenes ({len(scenes)}):")
    for s in scenes:
        print(f"  {s}")
    return scenes


# ---------------------------------------------------------------------------
# Main extraction
# ---------------------------------------------------------------------------

def extract_scene(scene_name, bundle_dir, boss_prefab=None):
    """Extract all collision geometry and metadata from a scene."""
    super_path = bundle_dir / SCENE_SUPER_BUNDLE
    if not super_path.exists():
        print(f"ERROR: Scene super-bundle not found at {super_path}", file=sys.stderr)
        sys.exit(1)

    # Load super-bundle
    print(f"Loading scene super-bundle...")
    env = UnityPy.load(str(super_path))

    # Find the scene bundle
    scene_key = None
    for k in env.files:
        if scene_name in k:
            scene_key = k
            break

    if not scene_key:
        print(f"ERROR: Scene '{scene_name}' not found in super-bundle.", file=sys.stderr)
        print("Available scenes containing your query:", file=sys.stderr)
        for k in sorted(env.files.keys()):
            if scene_name.split("_")[0] in k.lower():
                print(f"  {k}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading scene: {scene_key}")
    scene_bundle = env.files[scene_key]
    scene_objects = scene_bundle.get_objects()

    print("Indexing scene objects...")
    idx = SceneIndex(scene_objects, label=scene_name)
    print(f"  GameObjects: {len(idx.game_objects)}")
    print(f"  Transforms: {len(idx.transforms)}")

    # Extract
    print("Extracting colliders...")
    colliders = extract_colliders(idx)
    print(f"  Found {len(colliders)} colliders")

    print("Extracting rigidbodies...")
    rigidbodies = extract_rigidbodies(idx)
    print(f"  Found {len(rigidbodies)} rigidbodies")

    print("Extracting MonoBehaviours...")
    monobehaviours = extract_monobehaviours(idx)
    print(f"  Found {len(monobehaviours)} interesting MonoBehaviours")

    print("Building hierarchy...")
    hierarchy = dump_hierarchy(idx)
    print(f"  {len(hierarchy)} GameObjects in hierarchy")

    # Build output
    output = {
        "scene": scene_name,
        "colliders": colliders,
        "rigidbodies": rigidbodies,
        "monobehaviours": monobehaviours,
        "hierarchy": hierarchy,
    }

    # Boss prefab extraction
    if boss_prefab:
        prefab_filename = BOSS_PREFAB_MAP.get(boss_prefab.lower())
        if not prefab_filename:
            # Try direct filename
            prefab_filename = boss_prefab
            if not prefab_filename.endswith(".bundle"):
                prefab_filename += ".bundle"

        prefab_path = bundle_dir / prefab_filename
        if prefab_path.exists():
            print(f"\nLoading boss prefab: {prefab_path.name}")
            prefab_env = UnityPy.load(str(prefab_path))
            prefab_idx = SceneIndex(prefab_env.objects, label=f"prefab:{boss_prefab}")
            print(f"  GameObjects: {len(prefab_idx.game_objects)}")

            prefab_colliders = extract_colliders(prefab_idx)
            prefab_rigidbodies = extract_rigidbodies(prefab_idx)
            prefab_monobehaviours = extract_monobehaviours(prefab_idx)
            prefab_hierarchy = dump_hierarchy(prefab_idx)

            output["boss_prefab"] = {
                "bundle": prefab_filename,
                "colliders": prefab_colliders,
                "rigidbodies": prefab_rigidbodies,
                "monobehaviours": prefab_monobehaviours,
                "hierarchy": prefab_hierarchy,
            }
            print(f"  Prefab colliders: {len(prefab_colliders)}")
            print(f"  Prefab rigidbodies: {len(prefab_rigidbodies)}")
            print(f"  Prefab MonoBehaviours: {len(prefab_monobehaviours)}")
        else:
            print(f"WARNING: Boss prefab bundle not found: {prefab_path}", file=sys.stderr)

    return output, colliders, rigidbodies, monobehaviours, hierarchy


def main():
    parser = argparse.ArgumentParser(
        description="Extract collision geometry from Silksong scenes."
    )
    parser.add_argument(
        "scene",
        nargs="?",
        help="Scene name (e.g. memory_silk_heart_lacetower). Omit to list all scenes.",
    )
    parser.add_argument(
        "--boss-prefab",
        default=None,
        help="Also extract boss prefab colliders (e.g. laceboss, boss).",
    )
    parser.add_argument(
        "--game-path",
        default=None,
        help="Override game data path.",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Output directory (default: scripts/).",
    )
    parser.add_argument(
        "--no-summary",
        action="store_true",
        help="Skip generating the markdown summary.",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Only output JSON to stdout, no files.",
    )

    args = parser.parse_args()

    bundle_dir = DEFAULT_BUNDLE_DIR
    if args.game_path:
        game_data = Path(args.game_path)
        bundle_dir = game_data / "StreamingAssets" / "aa" / "StandaloneLinux64"

    out_dir = Path(args.out_dir) if args.out_dir else OUT_DIR

    # No scene specified: list available scenes
    if not args.scene:
        list_scenes(bundle_dir)
        return

    scene_name = args.scene

    # Auto-detect boss prefab for known scenes
    boss_prefab = args.boss_prefab
    if boss_prefab is None and "lacetower" in scene_name.lower():
        boss_prefab = "laceboss"
        print(f"Auto-detected boss prefab: {boss_prefab}")

    output, colliders, rigidbodies, monobehaviours, hierarchy = extract_scene(
        scene_name, bundle_dir, boss_prefab=boss_prefab
    )

    if args.json_only:
        print(json.dumps(output, indent=2, default=str))
        return

    # Write JSON
    json_path = out_dir / "arena_colliders.json"
    with open(json_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nJSON saved to: {json_path}")

    # Write summary
    if not args.no_summary:
        summary = generate_summary(scene_name, colliders, rigidbodies, monobehaviours, hierarchy)

        # Include boss prefab in summary if available
        if "boss_prefab" in output:
            bp = output["boss_prefab"]
            summary += f"\n\n---\n\n# Boss Prefab: {bp['bundle']}\n"
            summary += f"\n## Prefab Colliders ({len(bp['colliders'])})\n"
            for c in bp["colliders"]:
                trigger_str = " [TRIGGER]" if c.get("is_trigger") else ""
                if c["type"] == "box":
                    summary += (
                        f"- **{c['name']}** box at ({c['world_x']:.2f}, {c['world_y']:.2f}) "
                        f"size {c['width']:.2f}x{c['height']:.2f}{trigger_str}\n"
                    )
                elif c["type"] == "circle":
                    summary += (
                        f"- **{c['name']}** circle at ({c['world_x']:.2f}, {c['world_y']:.2f}) "
                        f"r={c['radius']:.2f}{trigger_str}\n"
                    )
                elif c["type"] == "polygon":
                    summary += (
                        f"- **{c['name']}** polygon {c['path_count']} paths, "
                        f"{c['total_points']} pts{trigger_str}\n"
                    )
                elif c["type"] == "edge":
                    summary += (
                        f"- **{c['name']}** edge {c['point_count']} pts{trigger_str}\n"
                    )

            if bp["rigidbodies"]:
                summary += f"\n## Prefab Rigidbody2D ({len(bp['rigidbodies'])})\n"
                for rb in bp["rigidbodies"]:
                    summary += (
                        f"- **{rb['name']}** gravity={rb['gravity_scale']} "
                        f"mass={rb['mass']} bodyType={rb['body_type']}\n"
                    )

            dmg = [m for m in bp["monobehaviours"] if m.get("component_type") == "DamageHero"]
            if dmg:
                summary += f"\n## Prefab DamageHero ({len(dmg)})\n"
                for d in dmg:
                    summary += f"- **{d['name']}** damage={d.get('damageDealt')} hazardType={d.get('hazardType')}\n"

            fsms = [m for m in bp["monobehaviours"] if m.get("component_type") == "FSM"]
            if fsms:
                summary += f"\n## Prefab FSMs ({len(fsms)})\n"
                for f in fsms:
                    summary += f"- **{f['name']}** / {f['fsm_name']} ({f['state_count']} states)\n"

        summary_path = out_dir / "arena_summary.md"
        with open(summary_path, "w") as f:
            f.write(summary)
        print(f"Summary saved to: {summary_path}")

    # Print quick stats
    print(f"\n--- Quick Stats ---")
    print(f"Scene: {scene_name}")
    print(f"Colliders: {len(colliders)} ({sum(1 for c in colliders if not c.get('is_trigger'))} solid, {sum(1 for c in colliders if c.get('is_trigger'))} trigger)")
    from collections import Counter
    tc = Counter(c["type"] for c in colliders)
    for t, cnt in tc.most_common():
        print(f"  {t}: {cnt}")
    print(f"Rigidbodies: {len(rigidbodies)}")
    print(f"MonoBehaviours: {len(monobehaviours)}")
    if "boss_prefab" in output:
        bp = output["boss_prefab"]
        print(f"Boss prefab colliders: {len(bp['colliders'])}")
        print(f"Boss prefab MonoBehaviours: {len(bp['monobehaviours'])}")


if __name__ == "__main__":
    main()
