# silksong_sim

GPU-batched standalone simulator of Hollow Knight: Silksong for RL training.
Built on the [Madrona Engine](https://github.com/shacklettbp/madrona). Replaces
the Unity game in the bulk-training loop; the game itself is demoted to
fidelity-oracle duty.

**Status:** Phase 4 scaffold complete (no-op physics, PPO loop end-to-end).
Phase 5 in progress — porting real physics under the hard performance floor
in [`../../docs/phase5-physics-requirements.md`](../../docs/phase5-physics-requirements.md).

## Read these docs first

Canonical specs live under [`../../docs/`](../../docs/README.md); do not
duplicate them here.

- [`../../docs/framework-requirements.md`](../../docs/framework-requirements.md) — overall framework spec: obs/action contract, throughput floor, toolchain, build instructions (§7), file tree, phase status, measured Phase 4 throughput.
- [`../../docs/phase5-physics-requirements.md`](../../docs/phase5-physics-requirements.md) — performance constraints for Phase 5 physics.
- [`../../docs/audit/synthesis.md`](../../docs/audit/synthesis.md) — master plan + phase status + measured numbers.
- [`../../docs/audit/type-map.md`](../../docs/audit/type-map.md) — every game field/method the sim must reproduce.
- [`../../docs/audit/lace-fsm.md`](../../docs/audit/lace-fsm.md) — complete Lace boss state graph.

## Build

See [`../../docs/framework-requirements.md`](../../docs/framework-requirements.md) §7 for the
full recipe (project-local CUDA 12.8 via micromamba + the two load-bearing
`MADRONA_*_VERSION` overrides). The short form, once CUDA 12.8 is in
`./.cuda128/`:

```bash
cmake -S . -B build -GNinja \
  -DCUDAToolkit_ROOT=$PWD/.cuda128 \
  -DCMAKE_CUDA_COMPILER=$PWD/.cuda128/bin/nvcc \
  -DPython_EXECUTABLE=$(uv run --project ../.. python -c "import sys; print(sys.executable)") \
  -DMADRONA_TOOLCHAIN_VERSION=8c0b55b \
  -DMADRONA_DEPS_VERSION=8d57788
ninja -C build -j$(nproc)
```

## Smoke tests

```bash
# C++-side benchmark
./build/headless CUDA 4096 1000 --rand-actions

# Python-side throughput sweep
cd ../..  # back to repo root
PYTHONPATH=sim/silksong_sim/build uv run python sim/silksong_sim/scripts/benchmark.py \
  --backend CUDA --num-worlds 65536 --num-steps 500 --regime all

# End-to-end PPO smoke test
PYTHONPATH=sim/silksong_sim/build uv run python sim/silksong_sim/scripts/train_ppo.py \
  --num-worlds 4096 --total-steps 2000000
```

Expected numbers and the CI regression gate are in
`../../docs/framework-requirements.md` §2 and §11.

## Source layout

| File | Purpose |
|---|---|
| `src/consts.hpp` | Constants — ray count, arena bounds, max HP, etc. (match C# plugin) |
| `src/types.hpp` | ECS components — `Action`, `PlayerObs`, `BossObs`, `RaycastDistances`, `RaycastHitTypes`, `EpisodeState`, `Reward`, `Done` |
| `src/sim.hpp` / `src/sim.cpp` | `registerTypes` + task-graph + step kernel |
| `src/level_gen.{hpp,cpp}` | Persistent entity creation + episode reset |
| `src/mgr.{hpp,cpp}` | `Manager` with CPU and CUDA impls + tensor exports |
| `src/bindings.cpp` | nanobind `NB_MODULE(silksong_sim, …)` |
| `src/headless.cpp` | CLI benchmark binary |
| `scripts/sim_bench.py` | Quick throughput probe |
| `scripts/benchmark.py` | Formal sweep: 3 regimes × N batch sizes, CSV out |
| `scripts/train_ppo.py` | CleanRL-style single-file PPO |
| `.cuda128/` | Project-local CUDA 12.8 toolkit (micromamba env) |
| `external/madrona/` | Vendored Madrona engine + its deps |

## Phase 4 scaffold behavior

The `stepSystem` currently advances step/time counters and zeroes rewards —
it intentionally doesn't apply `Action` or update positions. The purpose of
the scaffold was to prove the pipeline (C++ ECS → nanobind → PyTorch → PPO
update → action write → ECS step) end-to-end. Phase 5 replaces the no-op
body with real Silksong physics per `../../docs/phase5-physics-requirements.md`.

## Credits

Forked from [`madrona_escape_room`](https://github.com/shacklettbp/madrona_escape_room)
(Shacklett et al.). Upstream template lives at `../madrona_escape_room/` in
this repo for reference — do not modify.
