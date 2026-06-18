"""Throughput benchmark for silksong_sim (raw_sim, random_acts, policy regimes)."""

from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

import torch
import torch.nn as nn

import silksong_sim

OBS_DIM = 14 + 10 + 32 + 32
NUM_ACTIONS = 10


class BenchPolicy(nn.Module):

    def __init__(self, obs_dim: int = OBS_DIM, num_actions: int = NUM_ACTIONS, hidden: int = 128):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(obs_dim, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden), nn.ReLU(),
            nn.Linear(hidden, num_actions),
        )

    def forward(self, obs: torch.Tensor) -> torch.Tensor:
        return self.net(obs)


def make_sim(backend: str, num_worlds: int, seed: int = 0):
    mode = (silksong_sim.madrona.ExecMode.CUDA if backend == "CUDA"
            else silksong_sim.madrona.ExecMode.CPU)
    return silksong_sim.SimManager(
        exec_mode=mode,
        gpu_id=0,
        num_worlds=num_worlds,
        rand_seed=seed,
        auto_reset=True,
    )


def bench_raw(sim, num_steps: int) -> float:
    torch.cuda.synchronize() if torch.cuda.is_available() else None
    t0 = time.perf_counter()
    for _ in range(num_steps):
        sim.step()
    torch.cuda.synchronize() if torch.cuda.is_available() else None
    return time.perf_counter() - t0


def bench_random_actions(sim, num_steps: int) -> float:
    actions = sim.action_tensor().to_torch()
    torch.cuda.synchronize() if torch.cuda.is_available() else None
    t0 = time.perf_counter()
    for _ in range(num_steps):
        actions.random_(0, 2)
        sim.step()
    torch.cuda.synchronize() if torch.cuda.is_available() else None
    return time.perf_counter() - t0


def bench_policy(sim, num_steps: int, device: str, compile_policy: bool) -> float:
    policy = BenchPolicy().to(device)
    if compile_policy:
        policy = torch.compile(policy, mode="reduce-overhead")

    player_t = sim.player_obs_tensor().to_torch()
    boss_t = sim.boss_obs_tensor().to_torch()
    rayd_t = sim.raycast_distances_tensor().to_torch()
    rayh_t = sim.raycast_hit_types_tensor().to_torch()
    action_t = sim.action_tensor().to_torch()

    with torch.no_grad():
        for _ in range(3):
            obs = torch.cat([
                player_t.squeeze(1), boss_t.squeeze(1),
                rayd_t.squeeze(1), rayh_t.squeeze(1).float(),
            ], dim=-1)
            logits = policy(obs)
            action_t.copy_(torch.bernoulli(torch.sigmoid(logits)).to(torch.int32).unsqueeze(1))
            sim.step()

    torch.cuda.synchronize() if torch.cuda.is_available() else None
    t0 = time.perf_counter()
    with torch.no_grad():
        for _ in range(num_steps):
            obs = torch.cat([
                player_t.squeeze(1), boss_t.squeeze(1),
                rayd_t.squeeze(1), rayh_t.squeeze(1).float(),
            ], dim=-1)
            logits = policy(obs)
            action_t.copy_(torch.bernoulli(torch.sigmoid(logits)).to(torch.int32).unsqueeze(1))
            sim.step()
    torch.cuda.synchronize() if torch.cuda.is_available() else None
    return time.perf_counter() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["CPU", "CUDA"], default="CUDA")
    ap.add_argument("--num-worlds", type=int, required=True)
    ap.add_argument("--num-steps", type=int, default=1000)
    ap.add_argument("--regime", choices=["raw_sim", "random_acts", "policy", "all"],
                    default="all",
                    help="Which benchmark regime to run. Use one-per-invocation "
                         "to sweep batch sizes safely — Madrona's CUDA heap "
                         "doesn't cleanly re-init across multiple SimManagers "
                         "in the same process.")
    ap.add_argument("--out", type=str, default=None,
                    help="Optional path to append CSV results (header written "
                         "if file doesn't exist).")
    ap.add_argument("--no-compile", action="store_true")
    args = ap.parse_args()

    device = "cuda" if args.backend == "CUDA" else "cpu"

    sim = make_sim(args.backend, args.num_worlds)
    total_steps_env = args.num_steps * args.num_worlds
    results: list[tuple[str, int, str, float, float]] = []

    regimes = ["raw_sim", "random_acts", "policy"] if args.regime == "all" else [args.regime]

    print(f"--- backend={args.backend}  num_worlds={args.num_worlds} ---")
    if "raw_sim" in regimes:
        wall = bench_raw(sim, args.num_steps)
        tps = total_steps_env / wall
        print(f"  raw_sim      wall={wall:.3f}s  tps={tps:>14,.0f}")
        results.append((args.backend, args.num_worlds, "raw_sim", wall, tps))

    if "random_acts" in regimes:
        wall = bench_random_actions(sim, args.num_steps)
        tps = total_steps_env / wall
        print(f"  random_acts  wall={wall:.3f}s  tps={tps:>14,.0f}")
        results.append((args.backend, args.num_worlds, "random_acts", wall, tps))

    if "policy" in regimes:
        wall = bench_policy(sim, args.num_steps, device, not args.no_compile)
        tps = total_steps_env / wall
        print(f"  policy       wall={wall:.3f}s  tps={tps:>14,.0f}")
        results.append((args.backend, args.num_worlds, "policy", wall, tps))

    if args.out:
        out = Path(args.out)
        new_file = not out.exists()
        with out.open("a", newline="") as f:
            w = csv.writer(f)
            if new_file:
                w.writerow(["backend", "num_worlds", "regime", "wall_seconds", "tps"])
            for row in results:
                w.writerow(row)


if __name__ == "__main__":
    main()
