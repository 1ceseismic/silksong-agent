# Simulator Substrate Audit

> **Status: HISTORICAL — preserved for reasoning archive, not required reading for forward work.**
>
> Written to decide which GPU-batched RL substrate to build on. The decision
> is locked: **Madrona**. This file is the short version of why Madrona and
> not the alternatives. For the current stack, read
> `docs/framework-requirements.md` §6.

---

## Decision

**Madrona Engine** (CUDA C++ ECS, single-kernel step, nanobind Python bindings).

Measured result: 1.82 B tps raw / 1.25 B tps random-actions / **80 M tps with the full policy** on an RTX 4070 Super at 65 536 worlds. That's ~170 000× the Unity pipeline's ceiling.

## Shortlist comparison (RTX 4090-class, single GPU)

| Substrate | Throughput | FSM fit | Determinism | Verdict |
|---|---|---|---|---|
| **Madrona** (CUDA C++ ECS) | 1.9 M tps benchmarked upstream | native ECS components | single kernel / perfect | ⭐ chosen |
| Brax / MJX (JAX) | 50 k – 200 k tps on typical MuJoCo | FSM must live outside the JAX trace | perfect | too slow + FSM decomposition forces Python↔sim sync we are trying to kill |
| PufferLib + custom C | 500 k – 1.5 M tps | FSM in C | strong | pragmatic fallback if CUDA ramp stalled (it did not) |
| IsaacLab / IsaacGym | 3 k – 50 k tps | poor (3D-centric) | **non-deterministic** (GPU scheduling) | reject |
| Sample Factory 2 | 2.5 k–3 k samples/s async | — | async by design | reject |
| EnvPool | ~1 M Atari fps on 256-core DGX | C++ wrapper | strong | CPU-bound physics, not GPU-native |
| Gymnax / Craftax / JaxMARL | MHz+ on grid/classic-control | — | perfect | not physics engines |
| Kinetix (ICLR'25) | research-grade JAX 2D physics | — | perfect | too new / research-grade |

## Why Madrona specifically

1. **FSM is first-class**: Lace's ~70 states + 3 phases live *as* ECS components in the same GPU kernel as physics. Brax forces the FSM into Python wrappers, re-introducing the sync bottleneck we are trying to delete.
2. **Deterministic by construction**: one monolithic CUDA kernel per step → bit-identical output for the same input. IsaacGym explicitly does not give this.
3. **Scales to the right batch size**: 4070 Super / 12 GB VRAM supports 16 k – 65 k concurrent worlds for the 88-float obs footprint.
4. **Oracle validation path**: Python bindings let us spawn a reference instance next to the training one and compare state histories; Brax can do this but with more glue, IsaacGym effectively can't.
5. **Template exists**: `madrona_escape_room` is the scaffold we forked for Phase 4.

## What we rejected and why (one-liners)

- **Brax**: fast enough in principle, but the JAX trace doesn't compose with a 70-state imperative FSM without evicting the FSM to Python — which is the exact problem we started with.
- **IsaacLab / IsaacGym**: 3D-biased, non-deterministic, and the throughput headline is 3–50 k tps. Wrong shape for a 2D platformer.
- **PufferLib**: solid fallback, kept in reserve when Madrona setup was risky. Once Phase 4 scaffold worked, no reason to revisit.
- **Sample Factory 2**: async pipeline is philosophically incompatible with reproducible fidelity-oracle validation.
- **EnvPool**: CPU-bound physics; the substrate is a thread pool, not a GPU simulator. Doesn't clear the throughput floor.

## Real-world RL precedents for 2D fighting games

All existing Hollow Knight / Celeste / Street Fighter RL projects (HKRL, HollowKnight_RL, SilksongRL, celesteRL, AIVO, SFAgents) use subprocess IPC to the real or emulated game client. None use a purpose-built batched simulator. Madrona being chosen here is, as far as this audit found, new for the genre.

## CUDA / build-env constraints

Madrona's NVRTC-compiled device code requires **CUDA 12.8**, not CUDA 13 — CCCL headers moved in 13 and break. We install CUDA 12.8 project-locally at `sim/silksong_sim/.cuda128/` via micromamba; system CUDA 13 is left alone. Two upstream madrona files are patched for CUDA 13 host-side compat (guarded by `#if CUDART_VERSION < 13000`, no-op under 12.x). See `framework-requirements.md` §7-§8.
