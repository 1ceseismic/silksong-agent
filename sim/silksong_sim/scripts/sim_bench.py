"""Random-policy throughput benchmark on CPU or CUDA backend."""

import argparse
import time

import torch

import silksong_sim


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["CPU", "CUDA"], required=True)
    ap.add_argument("--num-worlds", type=int, required=True)
    ap.add_argument("--num-steps", type=int, required=True)
    ap.add_argument("--gpu-id", type=int, default=0)
    ap.add_argument("--rand-actions", action="store_true")
    args = ap.parse_args()

    exec_mode = (silksong_sim.madrona.ExecMode.CUDA
                 if args.backend == "CUDA"
                 else silksong_sim.madrona.ExecMode.CPU)

    sim = silksong_sim.SimManager(
        exec_mode=exec_mode,
        gpu_id=args.gpu_id,
        num_worlds=args.num_worlds,
        rand_seed=5,
        auto_reset=True,
    )

    actions = sim.action_tensor().to_torch()

    start = time.perf_counter()
    for _ in range(args.num_steps):
        if args.rand_actions:
            actions.random_(0, 2)
        sim.step()
    end = time.perf_counter()

    elapsed = end - start
    total_steps = args.num_steps * args.num_worlds
    print(f"backend={args.backend}  worlds={args.num_worlds}  steps={args.num_steps}")
    print(f"wall={elapsed:.3f}s  tps={total_steps / elapsed:,.0f}")


if __name__ == "__main__":
    main()
