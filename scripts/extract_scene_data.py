#!/usr/bin/env python3
"""Extract all ground-truth values from the Abyss Cocoon scene (Lace boss fight).

Now that we know:
  - Scene: abyss_cocoon.bundle (inside scenes_scenes_scenes)
  - Boss GO: "Lost Lace Boss" at PathID=919, 28 components
  - Lace Control FSM: PathID=13742
  - Stun Control FSM: PathID=13822

This script:
  1. Loads ONLY the abyss_cocoon scene
  2. Walks the Lost Lace Boss hierarchy (body collider, attack hitboxes)
  3. Finds terrain colliders (arena walls/floor)
  4. Reads all DamageHero components
  5. Reads Stun Control FSM actions in detail
"""

import json
import sys
import warnings
from pathlib import Path
from collections import defaultdict

import UnityPy
from UnityPy.enums import ClassIDType

warnings.filterwarnings("ignore")
UnityPy.config.FALLBACK_UNITY_VERSION = "6000.0.50f1"

GAME_DATA = Path("/home/seis/game/Hollow Knight Silksong/Hollow Knight Silksong_Data")
BUNDLE_DIR = GAME_DATA / "StreamingAssets" / "aa" / "StandaloneLinux64"
SCENE_BUNDLE = BUNDLE_DIR / "scenes_scenes_scenes"

OUT_DIR = Path("/home/seis/code/silksong-agent/scripts")
results = {}


def section(title):
    print(f"\n{'='*80}\n  {title}\n{'='*80}")


def load_abyss_cocoon():
    """Load the abyss_cocoon scene from the scenes bundle."""
    env = UnityPy.load(str(SCENE_BUNDLE))

    scene_key = None
    for k in env.files:
        if 'abyss_cocoon' in k.lower():
            scene_key = k
            break

    if not scene_key:
        print("ERROR: abyss_cocoon scene not found!")
        sys.exit(1)

    scene_file = env.files[scene_key]

    # Get the main serialized file (not sharedAssets)
    for inner_name, inner_file in scene_file.files.items():
        if 'sharedAssets' not in inner_name and hasattr(inner_file, 'objects'):
            return inner_file

    print("ERROR: Could not find inner serialized file!")
    sys.exit(1)


def main():
    section("Loading Abyss Cocoon scene (Lace boss fight)")
    sf = load_abyss_cocoon()

    obj_count = len(sf.objects)
    type_counts = defaultdict(int)
    for pid, obj in sf.objects.items():
        type_counts[obj.type.name] += 1

    print(f"  Objects: {obj_count}")
    for tn, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"    {tn}: {c}")

    # -----------------------------------------------------------------------
    # Index all objects
    # -----------------------------------------------------------------------
    section("Building object index")

    # Read ALL GameObjects
    game_objects = {}  # pid -> tree
    for pid, obj in sf.objects.items():
        if obj.type == ClassIDType.GameObject:
            try:
                tree = obj.read_typetree()
                game_objects[pid] = tree
            except Exception:
                pass

    print(f"  GameObjects: {len(game_objects)}")

    # Read ALL Transforms
    transforms = {}  # pid -> tree
    go_to_tf = {}   # go_pid -> tf_pid
    for pid, obj in sf.objects.items():
        if obj.type in (ClassIDType.Transform, ClassIDType.RectTransform):
            try:
                tree = obj.read_typetree()
                transforms[pid] = tree
                go_pid = tree.get("m_GameObject", {}).get("m_PathID", 0)
                if go_pid:
                    go_to_tf[go_pid] = pid
            except Exception:
                pass

    print(f"  Transforms: {len(transforms)}")

    # Build parent/child hierarchy
    go_children = defaultdict(list)
    go_parent = {}
    for tf_pid, tf in transforms.items():
        parent_go = tf.get("m_GameObject", {}).get("m_PathID", 0)
        for child_ref in tf.get("m_Children", []):
            child_tf_pid = child_ref.get("m_PathID", 0)
            if child_tf_pid in transforms:
                child_go = transforms[child_tf_pid].get("m_GameObject", {}).get("m_PathID", 0)
                if child_go and parent_go:
                    go_children[parent_go].append(child_go)
                    go_parent[child_go] = parent_go

    # Build component map
    go_comp_pids = defaultdict(list)
    for go_pid, go in game_objects.items():
        for cp in go.get("m_Component", []):
            cpid = cp.get("component", {}).get("m_PathID", 0)
            if cpid:
                go_comp_pids[go_pid].append(cpid)

    # -----------------------------------------------------------------------
    # Find Lost Lace Boss (GO pid=919)
    # -----------------------------------------------------------------------
    section("Lost Lace Boss hierarchy")

    boss_go = game_objects.get(919)
    if not boss_go:
        print("  ERROR: GO 919 not found!")
        return

    print(f"  Name: {boss_go.get('m_Name', '?')}")
    print(f"  Active: {boss_go.get('m_IsActive', '?')}")
    print(f"  Components: {len(boss_go.get('m_Component', []))}")

    def get_go_path(go_pid, depth=0):
        name = game_objects.get(go_pid, {}).get("m_Name", f"?({go_pid})")
        if go_pid in go_parent and depth < 10:
            return f"{get_go_path(go_parent[go_pid], depth+1)}/{name}"
        return name

    def read_component(pid):
        """Read a component by path_id from the scene file."""
        if pid in sf.objects:
            obj = sf.objects[pid]
            try:
                return obj.type.name, obj.read_typetree()
            except Exception:
                return obj.type.name, None
        return "?", None

    def print_colliders_and_components(go_pid, depth=0):
        """Print colliders and DamageHero for a GO and all descendants."""
        go = game_objects.get(go_pid, {})
        name = go.get("m_Name", "?")
        active = go.get("m_IsActive", "?")
        full_path = get_go_path(go_pid)
        indent = "  " * (depth + 1)

        # Get transform position
        tf_pid = go_to_tf.get(go_pid)
        pos = {}
        if tf_pid and tf_pid in transforms:
            pos = transforms[tf_pid].get("m_LocalPosition", {})

        pos_str = ""
        if pos:
            px, py = pos.get('x', 0), pos.get('y', 0)
            if abs(px) > 0.001 or abs(py) > 0.001:
                pos_str = f" pos=({px:.3f}, {py:.3f})"

        # Check if this GO has any interesting components
        has_interesting = False
        comp_data = []
        for cpid in go_comp_pids.get(go_pid, []):
            tname, tree = read_component(cpid)
            if tree is None:
                continue

            if tname == "BoxCollider2D":
                size = tree.get("m_Size", {})
                offset = tree.get("m_Offset", {})
                trigger = tree.get("m_IsTrigger", False)
                enabled = tree.get("m_Enabled", 1)
                comp_data.append(("BoxCollider2D", {
                    "size_x": size.get("x", 0), "size_y": size.get("y", 0),
                    "offset_x": offset.get("x", 0), "offset_y": offset.get("y", 0),
                    "is_trigger": trigger, "enabled": enabled
                }))
                has_interesting = True

            elif tname == "CircleCollider2D":
                radius = tree.get("m_Radius", 0)
                offset = tree.get("m_Offset", {})
                trigger = tree.get("m_IsTrigger", False)
                enabled = tree.get("m_Enabled", 1)
                comp_data.append(("CircleCollider2D", {
                    "radius": radius,
                    "offset_x": offset.get("x", 0), "offset_y": offset.get("y", 0),
                    "is_trigger": trigger, "enabled": enabled
                }))
                has_interesting = True

            elif tname == "PolygonCollider2D":
                offset = tree.get("m_Offset", {})
                trigger = tree.get("m_IsTrigger", False)
                enabled = tree.get("m_Enabled", 1)
                points_data = tree.get("m_Points", {})
                paths = points_data.get("m_Paths", []) if isinstance(points_data, dict) else []
                point_list = []
                if paths:
                    for path in paths:
                        if isinstance(path, list):
                            for pt in path:
                                if isinstance(pt, dict):
                                    point_list.append((round(pt.get("x", 0), 4), round(pt.get("y", 0), 4)))
                comp_data.append(("PolygonCollider2D", {
                    "offset_x": offset.get("x", 0), "offset_y": offset.get("y", 0),
                    "points": point_list, "is_trigger": trigger, "enabled": enabled
                }))
                has_interesting = True

            elif tname == "EdgeCollider2D":
                offset = tree.get("m_Offset", {})
                points = tree.get("m_Points", [])
                trigger = tree.get("m_IsTrigger", False)
                comp_data.append(("EdgeCollider2D", {
                    "offset_x": offset.get("x", 0), "offset_y": offset.get("y", 0),
                    "num_points": len(points) if isinstance(points, list) else 0,
                    "is_trigger": trigger
                }))
                has_interesting = True

            elif tname == "Rigidbody2D":
                grav = tree.get("m_GravityScale", 0)
                mass = tree.get("m_Mass", 0)
                body_type = tree.get("m_BodyType", 0)
                linear_drag = tree.get("m_LinearDrag", 0)
                comp_data.append(("Rigidbody2D", {
                    "gravityScale": grav, "mass": mass,
                    "bodyType": body_type, "linearDrag": linear_drag
                }))
                has_interesting = True

            elif tname == "MonoBehaviour":
                keys = set(tree.keys()) if isinstance(tree, dict) else set()
                if "damageDealt" in keys:
                    comp_data.append(("DamageHero", {
                        "damageDealt": tree.get("damageDealt"),
                        "hazardType": tree.get("hazardType", "?"),
                        "canClashTink": tree.get("canClashTink", "?"),
                        "forceParry": tree.get("forceParry", "?"),
                        "collisionSide": tree.get("collisionSide", "?"),
                    }))
                    has_interesting = True
                elif "fsm" in keys:
                    fsm = tree["fsm"]
                    fsm_name = fsm.get("name", "?")
                    states = fsm.get("states", [])
                    comp_data.append(("FSM", {"name": fsm_name, "states": len(states)}))
                    has_interesting = True
                elif "hp" in keys and len(keys) > 8:
                    hm_fields = {k: tree[k] for k in keys if isinstance(tree[k], (int, float, bool, str)) and not k.startswith("m_")}
                    comp_data.append(("HealthManager", hm_fields))
                    has_interesting = True

        # Print this GO if it has interesting stuff or is the boss
        if has_interesting or go_pid == 919 or depth <= 1:
            print(f"{indent}[{name}] (pid={go_pid}, active={active}){pos_str}")
            for ctype, cdata in comp_data:
                if ctype == "BoxCollider2D":
                    sx, sy = cdata["size_x"], cdata["size_y"]
                    ox, oy = cdata["offset_x"], cdata["offset_y"]
                    print(f"{indent}  + BoxCollider2D: size=({sx:.4f}, {sy:.4f}) offset=({ox:.4f}, {oy:.4f}) trigger={cdata['is_trigger']} enabled={cdata['enabled']}")
                    results[f"boss:{full_path}:BoxCollider2D"] = cdata

                elif ctype == "CircleCollider2D":
                    print(f"{indent}  + CircleCollider2D: radius={cdata['radius']:.4f} offset=({cdata['offset_x']:.4f}, {cdata['offset_y']:.4f}) trigger={cdata['is_trigger']} enabled={cdata['enabled']}")
                    results[f"boss:{full_path}:CircleCollider2D"] = cdata

                elif ctype == "PolygonCollider2D":
                    pts = cdata["points"]
                    print(f"{indent}  + PolygonCollider2D: {len(pts)} points trigger={cdata['is_trigger']} enabled={cdata['enabled']}")
                    if pts:
                        xs = [p[0] for p in pts]
                        ys = [p[1] for p in pts]
                        print(f"{indent}      extents: x=[{min(xs):.4f}, {max(xs):.4f}] y=[{min(ys):.4f}, {max(ys):.4f}]")
                    results[f"boss:{full_path}:PolygonCollider2D"] = cdata

                elif ctype == "EdgeCollider2D":
                    print(f"{indent}  + EdgeCollider2D: {cdata['num_points']} points trigger={cdata['is_trigger']}")

                elif ctype == "Rigidbody2D":
                    print(f"{indent}  + Rigidbody2D: gravityScale={cdata['gravityScale']} mass={cdata['mass']} bodyType={cdata['bodyType']}")
                    results[f"boss:{full_path}:Rigidbody2D"] = cdata

                elif ctype == "DamageHero":
                    print(f"{indent}  + DamageHero: dmg={cdata['damageDealt']} hazard={cdata['hazardType']} clash={cdata['canClashTink']} parry={cdata['forceParry']}")
                    results[f"boss:{full_path}:DamageHero"] = cdata

                elif ctype == "FSM":
                    print(f"{indent}  + FSM: {cdata['name']} ({cdata['states']} states)")

                elif ctype == "HealthManager":
                    print(f"{indent}  + HealthManager:")
                    for k, v in sorted(cdata.items()):
                        print(f"{indent}      {k}: {v}")
                    results[f"boss:{full_path}:HealthManager"] = cdata

        # Recurse into children
        for child_pid in go_children.get(go_pid, []):
            print_colliders_and_components(child_pid, depth + 1)

    print_colliders_and_components(919)

    # -----------------------------------------------------------------------
    # Stun Control FSM detailed extraction
    # -----------------------------------------------------------------------
    section("Stun Control FSM (pid=13822)")

    stun_obj = sf.objects.get(13822)
    if stun_obj:
        tree = stun_obj.read_typetree()
        fsm = tree.get("fsm", {})

        variables = fsm.get("variables", {})
        var_dict = {}
        print("  Variables:")
        for vtype in ["floatVariables", "intVariables", "boolVariables", "stringVariables"]:
            for v in variables.get(vtype, []):
                if isinstance(v, dict) and v.get("name"):
                    var_dict[v["name"]] = v.get("value")
                    print(f"    {v['name']}: {v.get('value')}")

        states = fsm.get("states", [])
        print(f"\n  States ({len(states)}):")
        for s in states:
            sname = s.get("name", "?")
            transitions = s.get("transitions", [])
            trans_str = ", ".join(f"{t.get('fsmEvent',{}).get('name','?')}->{t.get('toState','?')}" for t in transitions)
            print(f"    {sname}: [{trans_str}]")

        results["stun_control_fsm"] = {
            "variables": var_dict,
            "states": [s.get("name", "?") for s in states]
        }

    # -----------------------------------------------------------------------
    # Arena terrain colliders
    # -----------------------------------------------------------------------
    section("Arena terrain colliders")

    # Find all GOs with "terrain", "collider", "wall", "floor", "boundary" in name
    terrain_gos = []
    for go_pid, go in game_objects.items():
        name = go.get("m_Name", "").lower()
        if any(kw in name for kw in ["terrain collider", "wall", "floor", "boundary", "arena boundary",
                                       "arena wall", "ground"]):
            terrain_gos.append(go_pid)

    print(f"  Found {len(terrain_gos)} terrain/wall GOs")

    for go_pid in sorted(terrain_gos):
        name = game_objects[go_pid].get("m_Name", "?")
        active = game_objects[go_pid].get("m_IsActive", True)

        # Get position
        tf_pid = go_to_tf.get(go_pid)
        pos = {}
        if tf_pid and tf_pid in transforms:
            pos = transforms[tf_pid].get("m_LocalPosition", {})

        px = pos.get("x", 0)
        py = pos.get("y", 0)

        # Get colliders
        for cpid in go_comp_pids.get(go_pid, []):
            tname, tree = read_component(cpid)
            if tree is None:
                continue

            if tname == "BoxCollider2D":
                size = tree.get("m_Size", {})
                offset = tree.get("m_Offset", {})
                trigger = tree.get("m_IsTrigger", False)
                sx = size.get("x", 0)
                sy = size.get("y", 0)
                ox = offset.get("x", 0)
                oy = offset.get("y", 0)
                cx = px + ox
                cy = py + oy

                print(f"  [{name}] pos=({px:.2f},{py:.2f}) BoxCollider2D: size=({sx:.2f},{sy:.2f}) offset=({ox:.2f},{oy:.2f}) trigger={trigger} active={active}")
                if not trigger:
                    print(f"    SOLID wall: center=({cx:.2f},{cy:.2f}) bounds=[{cx-sx/2:.2f},{cx+sx/2:.2f}]x[{cy-sy/2:.2f},{cy+sy/2:.2f}]")
                    results[f"terrain:{name}:{cpid}:BoxCollider2D"] = {
                        "pos_x": px, "pos_y": py,
                        "size_x": sx, "size_y": sy,
                        "offset_x": ox, "offset_y": oy,
                        "world_min_x": cx - sx/2, "world_max_x": cx + sx/2,
                        "world_min_y": cy - sy/2, "world_max_y": cy + sy/2,
                        "is_trigger": trigger
                    }

            elif tname == "EdgeCollider2D":
                points = tree.get("m_Points", [])
                trigger = tree.get("m_IsTrigger", False)
                offset = tree.get("m_Offset", {})
                ox = offset.get("x", 0)
                oy = offset.get("y", 0)

                print(f"  [{name}] pos=({px:.2f},{py:.2f}) EdgeCollider2D: {len(points) if isinstance(points, list) else '?'} points trigger={trigger}")
                if isinstance(points, list) and not trigger:
                    world_points = []
                    for pt in points:
                        if isinstance(pt, dict):
                            wx = px + ox + pt.get("x", 0)
                            wy = py + oy + pt.get("y", 0)
                            world_points.append((wx, wy))
                    if world_points:
                        xs = [p[0] for p in world_points]
                        ys = [p[1] for p in world_points]
                        print(f"    world extent: x=[{min(xs):.2f},{max(xs):.2f}] y=[{min(ys):.2f},{max(ys):.2f}]")
                        # Print first and last few points
                        for i, (wx, wy) in enumerate(world_points):
                            if i < 5 or i >= len(world_points) - 3:
                                print(f"    pt[{i}]: ({wx:.2f}, {wy:.2f})")
                            elif i == 5:
                                print(f"    ...")
                        results[f"terrain:{name}:{cpid}:EdgeCollider2D"] = {
                            "pos_x": px, "pos_y": py,
                            "world_points": world_points,
                            "world_min_x": min(xs), "world_max_x": max(xs),
                            "world_min_y": min(ys), "world_max_y": max(ys),
                        }

    # Also search for ANY BoxCollider2D that is not a trigger (solid colliders = walls)
    section("All non-trigger BoxCollider2D in scene (solid terrain)")
    solid_colliders = []
    for pid, obj in sf.objects.items():
        if obj.type.name != "BoxCollider2D":
            continue
        try:
            tree = obj.read_typetree()
            trigger = tree.get("m_IsTrigger", False)
            if not trigger:
                go_ref = tree.get("m_GameObject", {})
                go_pid = go_ref.get("m_PathID", 0)
                go_name = game_objects.get(go_pid, {}).get("m_Name", f"?({go_pid})")
                size = tree.get("m_Size", {})
                offset = tree.get("m_Offset", {})

                # Get world position
                tf_pid = go_to_tf.get(go_pid)
                pos = {}
                if tf_pid and tf_pid in transforms:
                    pos = transforms[tf_pid].get("m_LocalPosition", {})
                px = pos.get("x", 0)
                py = pos.get("y", 0)
                sx = size.get("x", 0)
                sy = size.get("y", 0)
                ox = offset.get("x", 0)
                oy = offset.get("y", 0)

                solid_colliders.append({
                    "name": go_name, "pid": pid, "go_pid": go_pid,
                    "pos_x": px, "pos_y": py,
                    "size_x": sx, "size_y": sy,
                    "offset_x": ox, "offset_y": oy,
                    "world_cx": px + ox, "world_cy": py + oy,
                })
        except Exception:
            pass

    print(f"  Found {len(solid_colliders)} non-trigger BoxCollider2D")
    for sc in sorted(solid_colliders, key=lambda x: (x["pos_x"], x["pos_y"])):
        cx = sc["world_cx"]
        cy = sc["world_cy"]
        hw = sc["size_x"] / 2
        hh = sc["size_y"] / 2
        print(f"  [{sc['name']}] pos=({sc['pos_x']:.2f},{sc['pos_y']:.2f}) size=({sc['size_x']:.2f},{sc['size_y']:.2f}) world=[{cx-hw:.2f},{cx+hw:.2f}]x[{cy-hh:.2f},{cy+hh:.2f}]")
        results[f"solid:{sc['name']}:{sc['pid']}"] = sc

    # -----------------------------------------------------------------------
    # Also check non-trigger EdgeCollider2D
    # -----------------------------------------------------------------------
    section("All non-trigger EdgeCollider2D in scene")
    for pid, obj in sf.objects.items():
        if obj.type.name != "EdgeCollider2D":
            continue
        try:
            tree = obj.read_typetree()
            trigger = tree.get("m_IsTrigger", False)
            if not trigger:
                go_ref = tree.get("m_GameObject", {})
                go_pid = go_ref.get("m_PathID", 0)
                go_name = game_objects.get(go_pid, {}).get("m_Name", f"?({go_pid})")
                points = tree.get("m_Points", [])
                offset = tree.get("m_Offset", {})

                tf_pid = go_to_tf.get(go_pid)
                pos = {}
                if tf_pid and tf_pid in transforms:
                    pos = transforms[tf_pid].get("m_LocalPosition", {})
                px = pos.get("x", 0)
                py = pos.get("y", 0)
                ox = offset.get("x", 0)
                oy = offset.get("y", 0)

                print(f"  [{go_name}] pos=({px:.2f},{py:.2f}) EdgeCollider2D: {len(points)} points")
                if isinstance(points, list):
                    world_pts = [(px+ox+pt.get("x",0), py+oy+pt.get("y",0)) for pt in points if isinstance(pt, dict)]
                    if world_pts:
                        xs = [p[0] for p in world_pts]
                        ys = [p[1] for p in world_pts]
                        print(f"    world: x=[{min(xs):.2f},{max(xs):.2f}] y=[{min(ys):.2f},{max(ys):.2f}]")
                        for i, (wx, wy) in enumerate(world_pts):
                            if i < 3 or i >= len(world_pts) - 2:
                                print(f"    [{i}] ({wx:.2f}, {wy:.2f})")
                            elif i == 3:
                                print(f"    ...")
                        results[f"edge:{go_name}:{pid}"] = {
                            "world_points": world_pts,
                            "world_min_x": min(xs), "world_max_x": max(xs),
                            "world_min_y": min(ys), "world_max_y": max(ys),
                        }
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # All DamageHero in scene
    # -----------------------------------------------------------------------
    section("All DamageHero components in scene")
    for pid, obj in sf.objects.items():
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            tree = obj.read_typetree()
            if not isinstance(tree, dict):
                continue
            if "damageDealt" not in tree:
                continue
            go_ref = tree.get("m_GameObject", {})
            go_pid = go_ref.get("m_PathID", 0)
            go_name = game_objects.get(go_pid, {}).get("m_Name", f"?({go_pid})")
            full_path = get_go_path(go_pid)
            dmg = tree.get("damageDealt")
            hz = tree.get("hazardType", "?")
            clash = tree.get("canClashTink", "?")
            parry = tree.get("forceParry", "?")
            print(f"  [{full_path}] dmg={dmg} hazard={hz} clash={clash} parry={parry}")
            results[f"damage:{full_path}:{pid}"] = {
                "damageDealt": dmg, "hazardType": hz,
                "canClashTink": clash, "forceParry": parry,
                "go_name": go_name, "full_path": full_path
            }
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    section("FINAL RESULTS")
    print(json.dumps(results, indent=2, default=str))

    out_path = OUT_DIR / "scene_data_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
