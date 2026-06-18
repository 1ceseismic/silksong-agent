"""Replay a recorded trace through silksong_sim and report per-frame drift against Unity ground truth."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch

import os
_build_dir = str(Path(__file__).resolve().parent.parent / "build")
if os.path.isdir(_build_dir) and _build_dir not in sys.path:
    sys.path.insert(0, _build_dir)

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
from scripts.read_trace import (  # noqa: E402
    read_trace_np,
    ACTION_NAMES,
    MAGIC,
    VERSION_LATEST,
    GAME_STATE_DTYPE,
    RECORD_DTYPE,
)

import silksong_sim  # noqa: E402


OBS_POS_X, OBS_POS_Y = 0, 1
OBS_VEL_X, OBS_VEL_Y = 2, 3
OBS_HEALTH, OBS_MAX_HEALTH, OBS_SILK = 4, 5, 6
OBS_GROUNDED = 7
OBS_CAN_DASH = 8
OBS_FACING_RIGHT = 9
OBS_INVINCIBLE = 10
OBS_CAN_ATTACK = 11
OBS_ANIM_STATE = 12
OBS_ANIM_PROGRESS = 13


@dataclass
class DiffReport:
    n_ticks: int
    pos_err: np.ndarray          # per-tick L2 position drift
    vel_err: np.ndarray          # per-tick L2 velocity drift
    pos_err_mean: float
    pos_err_max: float
    vel_err_mean: float
    vel_err_max: float
    pos_err_threshold: float
    vel_err_threshold: float
    passed: bool
    per_field: dict = None

FIELD_EPSILONS = {
    "posX": 1e-4, "posY": 1e-4,
    "velX": 1e-4, "velY": 1e-4,
    "grounded": 0.5,      # 0/1 comparison
    "facingRight": 0.5,
    "canDash": 0.5,
    "canAttack": 0.5,
    "invincible": 0.5,
}


POS_ERR_THRESHOLD = 0.1
VEL_ERR_THRESHOLD = 0.05


def _build_sim(backend: str) -> "silksong_sim.SimManager":
    mode = (silksong_sim.madrona.ExecMode.CUDA if backend == "CUDA"
            else silksong_sim.madrona.ExecMode.CPU)
    return silksong_sim.SimManager(
        exec_mode=mode, gpu_id=0, num_worlds=1, rand_seed=0, auto_reset=False,
    )


def _estimate_ceiling(trace: np.ndarray):
    """Estimate scene ceiling Y + X-range from headBumpSteps in v2 traces."""
    HALF_H = 0.568
    if trace.dtype.names is None or "hero" not in trace.dtype.names:
        return 0.0, 0.0, 0.0
    hb = trace["hero"]["headBumpSteps"].astype(np.int32)
    py = trace["state"]["playerPosY"].astype(np.float32)
    px = trace["state"]["playerPosX"].astype(np.float32)
    mask = hb > 0
    if not np.any(mask):
        return 0.0, 0.0, 0.0
    cy = float(py[mask].max()) + HALF_H
    margin = 1.5
    return cy, float(px[mask].min()) - margin, float(px[mask].max()) + margin


def _estimate_ceiling_y(trace: np.ndarray) -> float:
    cy, _, _ = _estimate_ceiling(trace)
    return cy


def _set_hero_init(sim, pos_x: float, pos_y: float,
                   vel_x: float, vel_y: float,
                   prev_action_bits: int = 0,
                   facing_right: int = 1,
                   ceiling_y: float = 0.0,
                   ceiling_min_x: float = 0.0,
                   ceiling_max_x: float = 0.0) -> None:
    hero_init = sim.hero_init_tensor().to_torch()
    hero_init[0, 0] = 1  # useCustom
    hero_init[0, 1:5].view(torch.float32)[:] = torch.tensor(
        [pos_x, pos_y, vel_x, vel_y], dtype=torch.float32,
    )
    hero_init[0, 5] = int(prev_action_bits)
    hero_init[0, 6] = int(facing_right)
    hero_init[0, 7:10].view(torch.float32)[:] = torch.tensor(
        [ceiling_y, ceiling_min_x, ceiling_max_x], dtype=torch.float32,
    )


def _pack_action_bits(rec: np.ndarray) -> int:
    bits = 0
    for i, name in enumerate(ACTION_NAMES):
        if int(rec["actions"][name]):
            bits |= (1 << i)
    return bits


def _set_action_from_trace(action_t: torch.Tensor, rec: np.ndarray) -> None:
    for i, name in enumerate(ACTION_NAMES):
        action_t[0, 0, i] = int(rec["actions"][name])


def replay(trace: np.ndarray, backend: str = "CPU",
           verbose: bool = False) -> DiffReport:
    if len(trace) < 2:
        raise ValueError("trace too short to replay")

    sim = _build_sim(backend)
    player = sim.player_obs_tensor().to_torch()
    action = sim.action_tensor().to_torch()
    reset   = sim.reset_tensor().to_torch()

    s0 = trace["state"][0]
    cy, cmin, cmax = _estimate_ceiling(trace)
    _set_hero_init(
        sim,
        float(s0["playerPosX"]), float(s0["playerPosY"]),
        float(s0["playerVelX"]), float(s0["playerVelY"]),
        prev_action_bits=0,
        facing_right=int(s0["playerFacingRight"]),
        ceiling_y=cy,
        ceiling_min_x=cmin,
        ceiling_max_x=cmax,
    )
    reset[0, 0] = 1

    n = len(trace) - 1
    pos_err = np.zeros(n, dtype=np.float32)
    vel_err = np.zeros(n, dtype=np.float32)
    per_field = {
        "posX":        np.zeros(n, dtype=np.float32),
        "posY":        np.zeros(n, dtype=np.float32),
        "velX":        np.zeros(n, dtype=np.float32),
        "velY":        np.zeros(n, dtype=np.float32),
        "grounded":    np.zeros(n, dtype=np.float32),
        "facingRight": np.zeros(n, dtype=np.float32),
        "canDash":     np.zeros(n, dtype=np.float32),
        "canAttack":   np.zeros(n, dtype=np.float32),
        "invincible":  np.zeros(n, dtype=np.float32),
    }

    for i in range(1, len(trace)):
        _set_action_from_trace(action, trace[i - 1])
        sim.step()

        if i == 1:
            sim.hero_init_tensor().to_torch()[0, 0] = 0

        sim_x  = float(player[0, 0, OBS_POS_X])
        sim_y  = float(player[0, 0, OBS_POS_Y])
        sim_vx = float(player[0, 0, OBS_VEL_X])
        sim_vy = float(player[0, 0, OBS_VEL_Y])

        rec = trace["state"][i]
        dx = sim_x  - float(rec["playerPosX"])
        dy = sim_y  - float(rec["playerPosY"])
        dvx = sim_vx - float(rec["playerVelX"])
        dvy = sim_vy - float(rec["playerVelY"])

        pos_err[i - 1] = (dx * dx + dy * dy) ** 0.5
        vel_err[i - 1] = (dvx * dvx + dvy * dvy) ** 0.5

        per_field["posX"][i - 1] = dx
        per_field["posY"][i - 1] = dy
        per_field["velX"][i - 1] = dvx
        per_field["velY"][i - 1] = dvy
        per_field["grounded"][i - 1]    = float(player[0, 0, OBS_GROUNDED]) - float(rec["playerGrounded"])
        per_field["facingRight"][i - 1] = float(player[0, 0, OBS_FACING_RIGHT]) - float(rec["playerFacingRight"])
        per_field["canDash"][i - 1]     = float(player[0, 0, OBS_CAN_DASH]) - float(rec["playerCanDash"])
        per_field["canAttack"][i - 1]   = float(player[0, 0, OBS_CAN_ATTACK]) - float(rec["playerCanAttack"])
        per_field["invincible"][i - 1]  = float(player[0, 0, OBS_INVINCIBLE]) - float(rec["playerInvincible"])

        if verbose and (i <= 5 or i % max(1, (len(trace) // 20)) == 0):
            print(f"  tick {i:5d}: "
                  f"sim=({sim_x:7.3f},{sim_y:7.3f}) "
                  f"rec=({float(rec['playerPosX']):7.3f},{float(rec['playerPosY']):7.3f})  "
                  f"Δpos={pos_err[i-1]:6.3f}  Δvel={vel_err[i-1]:6.3f}")

    return DiffReport(
        n_ticks=n,
        pos_err=pos_err, vel_err=vel_err,
        pos_err_mean=float(pos_err.mean()),
        pos_err_max=float(pos_err.max()),
        vel_err_mean=float(vel_err.mean()),
        vel_err_max=float(vel_err.max()),
        pos_err_threshold=POS_ERR_THRESHOLD,
        vel_err_threshold=VEL_ERR_THRESHOLD,
        passed=(pos_err.max() < POS_ERR_THRESHOLD
                and vel_err.max() < VEL_ERR_THRESHOLD),
        per_field=per_field,
    )


def print_report(rep: DiffReport, trace_path: str = "<trace>") -> None:
    print(f"\n=== Oracle diff: {trace_path} ===")
    print(f"  ticks compared:         {rep.n_ticks:,}")
    print(f"  pos drift: mean={rep.pos_err_mean:.4f}u  "
          f"max={rep.pos_err_max:.4f}u  "
          f"(threshold {rep.pos_err_threshold}u)")
    print(f"  vel drift: mean={rep.vel_err_mean:.4f} u/s  "
          f"max={rep.vel_err_max:.4f} u/s  "
          f"(threshold {rep.vel_err_threshold} u/s)")

    if rep.n_ticks > 0:
        quartiles = np.quantile(rep.pos_err, [0.5, 0.9, 0.99])
        print(f"  pos drift quartiles:    p50={quartiles[0]:.4f}  "
              f"p90={quartiles[1]:.4f}  p99={quartiles[2]:.4f}")

    if rep.per_field is not None and rep.n_ticks > 0:
        rows = []
        for name, arr in rep.per_field.items():
            eps = FIELD_EPSILONS.get(name, 1e-4)
            mask = np.abs(arr) > eps
            if np.any(mask):
                tick = int(np.argmax(mask)) + 1
                rows.append((tick, name, float(arr[tick - 1])))
        if rows:
            rows.sort()
            print("  first divergence by field:")
            for tick, name, delta in rows[:10]:
                sign = "+" if delta >= 0 else "-"
                print(f"    tick {tick:>5}  {name:<12}  sim−trace = {sign}{abs(delta):.4f}")
        else:
            print("  first divergence: none — every field matched to epsilon")

    print(f"  VERDICT: {'PASS ✓' if rep.passed else 'FAIL ✗'}")


def _synth_trace(num_ticks: int = 500) -> np.ndarray:
    sim = _build_sim("CPU")
    player = sim.player_obs_tensor().to_torch()
    action = sim.action_tensor().to_torch()

    action[...] = 0
    for _ in range(30):
        sim.step()

    records = np.zeros(num_ticks, dtype=RECORD_DTYPE)
    for t in range(num_ticks):
        a = [0] * 10
        a[1 if (t // 20) % 2 == 0 else 0] = 1
        if t > 0 and t % 47 == 0:   a[4] = 1
        if t > 0 and t % 101 == 0:  a[6] = 1
        if t > 0 and t % 37 == 0:   a[5] = 1

        records[t]["tick"] = t + 1
        for i, name in enumerate(ACTION_NAMES):
            records[t]["actions"][name] = np.uint8(a[i])
        s = records[t]["state"]
        s["playerPosX"] = float(player[0, 0, OBS_POS_X])
        s["playerPosY"] = float(player[0, 0, OBS_POS_Y])
        s["playerVelX"] = float(player[0, 0, OBS_VEL_X])
        s["playerVelY"] = float(player[0, 0, OBS_VEL_Y])
        s["playerHealth"]    = int(player[0, 0, OBS_HEALTH])
        s["playerMaxHealth"] = int(player[0, 0, OBS_MAX_HEALTH])
        s["playerSilk"]      = int(player[0, 0, OBS_SILK])
        s["playerGrounded"]  = int(player[0, 0, OBS_GROUNDED])
        s["playerCanDash"]   = int(player[0, 0, OBS_CAN_DASH])
        s["playerFacingRight"] = int(player[0, 0, OBS_FACING_RIGHT])
        s["playerInvincible"]  = int(player[0, 0, OBS_INVINCIBLE])
        s["playerCanAttack"]   = int(player[0, 0, OBS_CAN_ATTACK])

        for i, v in enumerate(a):
            action[0, 0, i] = int(v)
        sim.step()

    return records


def self_test() -> DiffReport:
    print("=== Self-test: sim → synthetic trace → replay → expect ~0 drift ===")
    trace = _synth_trace(num_ticks=500)
    rep = replay(trace, backend="CPU", verbose=False)
    print_report(rep, trace_path="<self-test>")
    if not rep.passed:
        print("  ⚠ SELF-TEST FAILED — oracle_diff.py has a bug; do not trust "
              "real-trace diffs until this is green.")
    return rep


def inspect_trace(path: str) -> None:
    from scripts.read_trace import CSTATE_BITS, EXTRA_BITS
    t = read_trace_np(path)
    if t.dtype.names is None or "hero" not in t.dtype.names:
        print(f"Trace {path} is v1 (no HeroPrivate). Re-record with the v2 plugin.")
        return
    n = len(t)
    h = t["hero"]
    s = t["state"]
    print(f"=== Inspect: {path}  ({n} ticks) ===")
    interesting = set([0, n - 1])
    for key, thr in [("jumpSteps", 0), ("dashTimer", 0.0), ("extraAirMoveCount", 0)]:
        arr = h[key]
        edges = np.where(np.diff((arr != thr).astype(int)) != 0)[0] + 1
        for e in edges.tolist():
            interesting.add(max(0, e - 1))
            interesting.add(e)
    fsm = h["sprintFsmStateHash"]
    edges = np.where(np.diff(fsm.astype(np.int64)) != 0)[0] + 1
    for e in edges.tolist():
        interesting.add(max(0, e - 1))
        interesting.add(e)
    interesting = sorted(interesting)
    print(f"{'tick':>5} {'posY':>7} {'velY':>7} {'velX':>7} "
          f"{'jstep':>5} {'dTm':>5} {'ldgBuf':>6} {'eAMc':>4} "
          f"{'sprintHash':>10} {'cState':<30}")
    for i in interesting[:60]:
        cb = int(h["cStateBits"][i])
        active = [CSTATE_BITS[b] for b in range(len(CSTATE_BITS)) if (cb >> b) & 1]
        cs_summary = ",".join(active[:4]) + ("…" if len(active) > 4 else "")
        print(f"{i:>5} {float(s['playerPosY'][i]):7.2f} {float(s['playerVelY'][i]):+7.2f} {float(s['playerVelX'][i]):+7.2f} "
              f"{int(h['jumpSteps'][i]):>5} {float(h['dashTimer'][i]):5.2f} "
              f"{int(h['ledgeBufferSteps'][i]):>6} {int(h['extraAirMoveCount'][i]):>4} "
              f"{int(h['sprintFsmStateHash'][i]):>10} {cs_summary:<30}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("trace", nargs="?",
                    help="Path to a .bin trace file recorded by the plugin.")
    ap.add_argument("--backend", choices=["CPU", "CUDA"], default="CPU")
    ap.add_argument("--self-test", action="store_true",
                    help="Generate a synthetic trace from the sim and replay it "
                         "through the same sim. Drift must be near zero.")
    ap.add_argument("--verbose", action="store_true",
                    help="Print per-tick drift for sampled ticks.")
    ap.add_argument("--inspect", action="store_true",
                    help="Dump HeroPrivate trajectory at interesting ticks "
                         "(jump/dash/sprint edges). Requires v2 trace; no sim.")
    args = ap.parse_args()

    if args.self_test:
        rep = self_test()
        sys.exit(0 if rep.passed else 1)

    if args.trace is None:
        ap.error("trace path required (or use --self-test)")

    if args.inspect:
        inspect_trace(args.trace)
        sys.exit(0)

    trace = read_trace_np(args.trace)
    print(f"Loaded {len(trace):,} ticks from {args.trace}")
    rep = replay(trace, backend=args.backend, verbose=args.verbose)
    print_report(rep, trace_path=args.trace)
    sys.exit(0 if rep.passed else 1)


if __name__ == "__main__":
    main()
