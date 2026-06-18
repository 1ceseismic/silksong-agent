# Python / IPC Pipeline Audit

> **Status: HISTORICAL — preserved for reasoning archive, not required reading for forward work.**
>
> Written when the training loop was SB3 PPO talking to a single Unity
> instance over a 4 KB mmap. Its thesis — "the Python+Unity pipeline
> fundamentally can't reach the throughput we need" — was confirmed and
> superseded by Phase 4: the Madrona sim now hits 1.25 B tps with random
> actions and 80 M tps with the full policy. The whole Unity→Python path
> is being demoted to oracle-only.
>
> The rest of this file is the short version of the surviving findings.
> For current spec, read `docs/framework-requirements.md`.

---

## The one number worth remembering

The effective per-instance ceiling of the Unity→Python pipeline was **~150–380 steps/sec**, bounded roughly equally by:

| bottleneck | cost / step | why it can't be cheaply fixed |
|---|---|---|
| Unity `WaitForFixedUpdate` × 2 @ 10× timescale | ~3.3 ms | structural — FixedUpdate is the step |
| `BossProjectileManager.RefreshProjectileCache` full scene scan | 2–5 ms | fixable (cache on spawn/despawn events — Phase 1 did this) |
| mmap round-trip + struct pack/unpack (×11) | 91–187 µs | fixable (zero-copy numpy view) |
| SB3 `SubprocVecEnv` pickle/unpickle per env | ~50 µs | fixable (SharedMemoryVecEnv) |
| `_wait_for_event` Linux busy-spin, no sleep | burns a core | fixable (eventfd / 1 ms sleep) |
| PPO learner GPU idle ~90 % | — | needs async collection / torch.compile |

Every fix above was scoped but **not pursued**, because the envelope is still Unity-bound. Unity at 10× timescale with FixedUpdate coroutine scheduling caps out around 1–2 k steps/sec/instance even with every optimisation applied. That's ≥500× short of what a GPU-batched sim delivers.

## What survived into the forward stack

- The IPC wire format (`CommandData` → 10 binary flags; `GameState` → 626 bytes) is the fidelity-trace format now. Preserved.
- `silksong/shared_memory.py` stays, used only by the trace recorder / oracle harness.
- `MultiHeadFeatureExtractor` in `silksong/networks.py` is worth porting to the new learner; the 32-ray + scalar split survives.
- `scripts/read_trace.py` is the structured-dtype replacement for the old per-step IPC loop — same struct, read offline in bulk.

## What got deleted

- SB3 `PPO` + `SubprocVecEnv` + `VecNormalize` training loop (replaced by CleanRL-style single-file PPO in `sim/silksong_sim/scripts/train_ppo.py`).
- `to_observation()` concat chain (replaced by Madrona's zero-copy tensor exports).
- One-hot animation encoding (will become an integer categorical fed to an embedding layer in the new policy).
- `EpisodeResetter.cs` (replaced by a one-memcpy sim-side reset).

## Original substrate recommendation

Called for "Brax first, Madrona later." Madrona was in fact chosen directly — see the condensed note in `sota-architecture.md` for why.
