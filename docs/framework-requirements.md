# Silksong RL Framework — Canonical Requirements

Durable spec for the Silksong RL training framework. If the implementation
drifts from this file, fix the implementation or update this file with a dated
note — never silently desync. Reasoning behind these decisions lives in
`docs/audit/*`.

## 0. What this project is

A GPU-batched standalone simulator of Silksong's 2D platformer physics + boss
FSM, with a PPO learner attached. The Unity game itself is demoted to oracle:
it emits fidelity traces + validates trained policies, but does not participate
in bulk training.

Reference boss for MVP: **Lace** (3-phase FSM). Any other boss is a data
drop-in (arena colliders + FSM component), not a code rewrite.

## 1. Hardware target

Single NVIDIA RTX 4070 Super, 12 GB VRAM, Linux. Multi-GPU is not a goal.
Policy + rollout buffers + 65 k-world ECS state + CUDA toolchain all share
12 GB.

## 2. Throughput contract

| regime | floor on 4070 Super | measured Phase 4 (no-op sim) |
|---|---|---|
| raw sim only | 500 M tps | 1.82 B tps |
| sim + random-action writes | 300 M tps | 1.25 B tps |
| sim + full MLP policy + PPO updates | **50 M tps** | 80 M tps |

**The 50 M tps floor with the full policy is THE load-bearing number.** Every
downstream choice defends it. A PR that drops it does not ship without a
logged, reviewed reason. Context: Unity pipeline managed ~300 tps; 50 M is
~170 000× that — 1 hour of human-equivalent play trains in ~0.1 s.

## 3. Observation / action contract (frozen)

Matches the C# plugin's `GameState` struct (`plugin/Source/Managers/SharedMemoryManager.cs`)
byte-for-byte. Any change to this contract must happen on both sides
simultaneously — the contract IS how the fidelity oracle works.

### Observation, 88 floats flat:

| Component | Dim | Source |
|---|---|---|
| `PlayerObs` | 14 float32 | pos(2) · vel(2) · health · maxHealth · silk · 5 flags · animState · animProgress |
| `BossObs` | 10 float32 | pos(2) · vel(2) · health · maxHealth · phase · facingRight · animState · animProgress |
| `RaycastDistances` | 32 float32 | normalised to `[0, 1]` by `maxRayDistance` = 25 units |
| `RaycastHitTypes` | 32 int32 (cast to float in policy) | enum: None · Terrain · Enemy · Projectile · Hazard · BossProjectile |
| `EpisodeState` | 3 (1f + 2i) | episodeTime, stepsTaken, stepsRemaining (not fed to policy by default) |

Per-step byte budget: **88 floats = 352 bytes of live obs per env**.

### Action: 10 discrete binary heads

`left right up down jump attack dash clawline skill heal`

- Integer tensor shape `[num_worlds, num_agents=1, 10]` in `int32`.
- Policy outputs 10 independent Bernoulli logits; samples 10 binary values.
- The C# plugin reads these exact 10 flags off the command mmap and routes
  them through Harmony-patched input getters.

## 4. Physics cadence

- Fixed timestep: **50 Hz**, `deltaT = 0.02` seconds.
- Physics sub-steps per agent step: **2** (matches Unity's `FramesPerStep = 2`
  and `fixedDeltaTime = 0.02`).
- Episode cap: 2 000 agent steps (= 80 s of game time).

## 5. Fidelity oracle

Sim behaviour is validated against real Silksong via trace-diff. This is how
"a policy trained in sim works in the real game" is guaranteed.

**Trace format.** Plugin records `{tick, action[10], GameState}` tuples at
50 Hz via F10 toggle. Reader: `scripts/read_trace.py` (structured numpy dtype,
`read_trace_np` for hot-loop access).

**Divergence budgets (must pass on every Phase 5+ release candidate).**

| Metric | Threshold |
|---|---|
| L2 position drift / frame | < 0.1 units |
| L2 velocity drift / frame | < 0.05 u/s |
| Animation state mismatch | 0 frames |
| Damage-event timing offset | ≤ 1 frame |
| Boss-phase transition offset | ≤ 2 frames |
| Win-rate gap (sim vs Unity on trained policy, 100 episodes) | < 5 % |

Any failing metric on a release candidate blocks the release.

## 6. Substrate & toolchain

- **Simulator:** [Madrona Engine](https://github.com/shacklettbp/madrona) — CUDA C++ ECS, batched task graphs, nanobind Python bindings.
- **Template:** `madrona_escape_room` — kept pristine at `sim/madrona_escape_room/` for reference.
- **Our code:** `sim/silksong_sim/` (forked & renamed).
- **CUDA:** 12.8 (not system CUDA 13 — Madrona's NVRTC-compiled device code is incompatible with CUDA 13's CCCL headers). Installed project-locally at `sim/silksong_sim/.cuda128/` via micromamba. System CUDA 13 at `/opt/cuda` is untouched.
- **Python:** 3.13 (matches repo's uv venv). Rebuild sim if venv Python version changes.
- **Learner:** CleanRL-style single-file PPO, in `sim/silksong_sim/scripts/train_ppo.py`. `torch.compile` on. Rollout buffer on-GPU, no CPU roundtrip per step.
- **Action API:** Madrona `Tensor.to_torch()` returns zero-copy PyTorch views into ECS columns. Policy writes to `action_tensor`, reads from `player_obs_tensor` / `boss_obs_tensor` / `raycast_distances_tensor` / `raycast_hit_types_tensor` / `reward_tensor` / `done_tensor`. Never serialise, never pickle.

## 7. Build instructions

Overrides are required because (a) `external/madrona/` is a plain directory,
not a real submodule, so `git rev-parse HEAD` falls through to the outer repo
HEAD and grabs the wrong commit; (b) the NVRTC path needs CUDA 12.8 to avoid
CCCL header incompat.

```bash
cd sim/silksong_sim

# First-time only: install project-local CUDA 12.8 (≈ 5.5 GB)
~/.local/bin/micromamba create -y -p ./.cuda128 -c nvidia -c conda-forge 'cuda-toolkit=12.8'
# (micromamba itself: curl -sL https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xj -C /tmp bin/micromamba && mv /tmp/bin/micromamba ~/.local/bin/)

# Configure — the two VERSION overrides are load-bearing
cmake -S . -B build -GNinja \
  -DCUDAToolkit_ROOT=$PWD/.cuda128 \
  -DCMAKE_CUDA_COMPILER=$PWD/.cuda128/bin/nvcc \
  -DPython_EXECUTABLE=$(uv run --project /home/seis/code/silksong-agent python -c "import sys; print(sys.executable)") \
  -DMADRONA_TOOLCHAIN_VERSION=8c0b55b \
  -DMADRONA_DEPS_VERSION=8d57788

ninja -C build -j$(nproc)

# Smoke test
./build/headless CPU 1024 1000          # expect ≈ 8-10 M FPS
./build/headless CUDA 4096 1000         # expect ≈ 500 M FPS-plus
```

## 8. CUDA 13 compat patches

Two upstream files were patched for CUDA 13 compat. They live in vendored
madrona — when re-syncing upstream, re-apply:

1. `external/madrona/src/render/vk/backend.cpp` — guard the `cudaDeviceProp::computeMode` check with `#if CUDART_VERSION < 13000` (field removed in CUDA 13).
2. `external/madrona/src/mw/cuda_exec.cpp` — `cuMemAdvise` shim at top of file: CUDA 13 changed the 4th arg from `CUdevice` to `CUmemLocation`. Shim under the old name so call sites are unchanged.

Both patches are no-ops under CUDA 12.x (guarded by `CUDART_VERSION`).

## 9. File-tree map

```
silksong-agent/
├── plugin/                                 Unity-side C# plugin (→ oracle mode post-Phase 5)
│   └── Source/
│       ├── Core/
│       │   ├── Constants.cs                RayCount, MaxRayDistance, LaceBossMaxHealth, etc.
│       │   ├── GameStateCollector.cs       builds the 626-byte wire struct
│       │   ├── RaycastSensor.cs            32-ray sensor (static pre-allocated buffers)
│       │   └── TraceRecorder.cs            F10 → binary trace dump (oracle source)
│       ├── Managers/
│       │   ├── SharedMemoryManager.cs      mmap IPC with Python
│       │   ├── BossProjectileManager.cs    FSM-state-gated projectile tracking
│       │   ├── BossStateManager.cs         Lace FSM watch + phase transition
│       │   └── ActionManager.cs            10-binary input → Harmony key-getter patch
│       └── Patches/                        Harmony patches for NoFx, input, death, etc.
├── scripts/
│   └── read_trace.py                       numpy structured-dtype reader for .bin traces
├── sim/
│   ├── silksong_sim/                       OUR TRAINING TARGET
│   │   ├── src/
│   │   │   ├── consts.hpp                  all tunable constants matching C# plugin
│   │   │   ├── types.hpp                   ECS components (Action, PlayerObs, BossObs, ...)
│   │   │   ├── sim.hpp / sim.cpp           registerTypes, step kernel, task graph
│   │   │   ├── level_gen.{hpp,cpp}         persistent entity creation, episode reset
│   │   │   ├── mgr.{hpp,cpp}               Manager (CPU + CUDA impls, tensor exports)
│   │   │   ├── bindings.cpp                nanobind NB_MODULE(silksong_sim, ...)
│   │   │   └── headless.cpp                CLI benchmark
│   │   ├── scripts/
│   │   │   ├── sim_bench.py                quick throughput probe
│   │   │   ├── benchmark.py                formal sweep (raw / random / policy × batch sizes)
│   │   │   └── train_ppo.py                CleanRL-style PPO
│   │   ├── train_src/silksong_sim_learn/   upstream PPO infra (reference only for now)
│   │   ├── .cuda128/                       project-local CUDA 12.8
│   │   └── external/madrona/               vendored engine (with the 2 compat patches)
│   └── madrona_escape_room/                pristine upstream template — untouched
├── silksong/                               old SB3 Python env (oracle-mode reference)
├── train.py / tune.py                      old SB3 trainers (deprecated)
├── docs/
│   ├── framework-requirements.md           THIS FILE
│   ├── phase5-physics-requirements.md      Phase 5 perf constraint catalogue
│   └── audit/                              7 audit reports + synthesis
├── checkpoints/30m.zip                     30 M-step SB3 checkpoint from upstream
├── resources/user1.dat                     Silksong save file positioned next to Lace
└── pyproject.toml                          uv-managed Python deps for the repo
```

## 10. Phase status (as of last update)

| Phase | Status |
|---|---|
| 1. Kill projectile-scan hack | ✅ done + audited |
| 3. Decompilation + type map + FSM doc + trace recorder | ✅ done (manual dnSpy dump still pending) |
| 4. Madrona scaffold + PPO + benchmark | ✅ **done and wildly over target** (measured 80 M tps with policy vs 10 M target) |
| 5. Physics port (HeroController) | pending — **must preserve ≥ 50 M tps with policy** |
| 6. Raycast sensor | pending |
| 7. Lace FSM port | pending |
| 8. Training run to policy convergence | pending |
| 9. Framework generalisation (second boss as data) | pending |

Critical path: 5 → 6 → 7 → 8. See `audit/synthesis.md` §6 for full plan.

## 11. Phase 4 benchmark reproduction

Harness: `sim/silksong_sim/scripts/benchmark.py`. Run one batch size per
process — Madrona's CUDA heap doesn't re-init cleanly across `SimManager`
instances in the same process.

```bash
cd /home/seis/code/silksong-agent
for W in 1024 4096 16384 65536; do
  PYTHONPATH=sim/silksong_sim/build uv run python sim/silksong_sim/scripts/benchmark.py \
    --backend CUDA --num-worlds $W --num-steps 500 --regime all --out /tmp/bench.csv
done
```

Phase 4 CSV snapshot (4070 Super, no-op physics, Python 3.13, torch 2.9):

```
CUDA,1024,raw_sim,       0.009, 56,948,760
CUDA,1024,random_acts,   0.015, 33,821,747
CUDA,1024,policy,        0.119,  4,288,793
CUDA,4096,raw_sim,       0.011, 191,927,931
CUDA,4096,random_acts,   0.017, 119,730,604
CUDA,4096,policy,        0.116,  17,618,247
CUDA,16384,raw_sim,      0.013, 627,630,240
CUDA,16384,random_acts,  0.019, 430,702,439
CUDA,16384,policy,       0.132,  62,092,231
CUDA,65536,raw_sim,      0.018, 1,819,679,674
CUDA,65536,random_acts,  0.026, 1,247,820,655
CUDA,65536,policy,       0.410,  79,964,732
```

CI regression gate (pending): re-run this sweep on main-branch builds, fail
if any row drops > 10 %.
