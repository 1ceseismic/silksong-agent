# Audit Synthesis & Phase-History Narrative

> **Status: MIXED — phase history is HISTORICAL reference; the roadmap at §3 still guides active work.**
>
> For the current binding spec, read `../framework-requirements.md` first.
> For Phase 5 rules, read `../phase5-physics-requirements.md`.
> This doc is kept as the connecting narrative between the audit deep-dives
> and the canonical spec — it tells the story of how we got here.

## Audit inputs

This synthesis was built from four parallel workstreams:

- [`python-audit.md`](./python-audit.md) — Python hot path + IPC + SB3 learner (**historical**: the Python path is being deleted)
- [`csharp-audit.md`](./csharp-audit.md) — BepInEx plugin audit (**historical + reference**: §3/§4 define the frozen obs/action contract, the rest is history)
- [`decompilation-plan.md`](./decompilation-plan.md) — game-logic extraction plan (**reference** for Phases 5 + 7)
- [`sota-architecture.md`](./sota-architecture.md) — substrate survey (**historical**: Madrona was chosen, decision locked)
- [`type-map.md`](./type-map.md) — every game-internal field the sim must reproduce (**reference** for Phases 5 + 7)
- [`lace-fsm.md`](./lace-fsm.md) — Lace state graph (**reference** for Phase 7)

## 1. Starting state (measured before Phase 4)

The Unity → Python pipeline ran at **~150–380 steps/sec/instance**, with this cost breakdown:

| Layer | Cost | Source |
|---|---|---|
| Unity per-step wall-clock | **2.6–6.6 ms** | `csharp-audit.md` §1.4 and §5.1 |
| └─ `BossProjectileManager.RefreshProjectileCache` full scene scan | **2–5 ms** | dominated per-step cost |
| └─ `WaitForFixedUpdate` × 2 @ timescale 10 | ~3.3 ms | structural |
| └─ `GameStateCollector` + 32-ray sensor + anim dict | ~0.3 ms | |
| Python per-step overhead (single env) | **91–187 µs** | struct×11 + 4× `np.concatenate` + one-hots |
| `SubprocVecEnv` pickling | ~50 µs / env | pipes |
| Linux `_wait_for_event` | busy-spin, no sleep | wastes a core per env |
| SB3 PPO learner | ~90 % GPU idle | sync on-policy, no `torch.compile` |

Hard ceiling of any "keep Unity" path: ~1–2 k steps/sec/instance. ≥500× short of the goal. The conclusion was unavoidable: **replace the simulator**, don't optimise it.

## 2. Decisions locked in (Phase 3)

| # | Decision | Why |
|---|---|---|
| 1 | Single-GPU 4070 Super / 12 GB VRAM, Linux | user's hardware |
| 2 | Substrate: **Madrona** (CUDA C++ ECS) with nanobind bindings | only substrate where Lace's ~70-state FSM lives in the same GPU kernel as physics; see `sota-architecture.md` |
| 3 | Fallback: PufferLib + custom C | never needed once Phase 4 scaffold worked |
| 4 | Reference boss: **Lace** (3-phase FSM) | matches real training target; switching later costs more than one-shotting Lace |
| 5 | Learner: CleanRL-style single-file PPO with `torch.compile` | avoids SB3's sync overhead; zero-copy tensor interop with Madrona |
| 6 | Fidelity contract: oracle diff + < 5 % Unity win-rate gap | see `decompilation-plan.md` §7 for thresholds |
| 7 | Obs / action wire format: frozen per `csharp-audit.md` §3/§4 | plugin stays as oracle; sim reproduces byte-for-byte |
| 8 | Cross-version game-binary pinning: **not required** | sim is authoritative, Unity is oracle |
| 9 | Framework generality: arena + boss as data, not per-boss code | Phase 9 |

## 3. Phased roadmap

| Phase | Duration | Milestone | Target | Status |
|---|---|---|---|---|
| **0. Baseline** | 1 d | measure actual steps/sec in current pipeline | — | deferred (user's box) |
| **1. Kill projectile-scan hack** | 1 d | replace `RefreshProjectileCache`'s `FindObjectsByType` with spawn/despawn event hooks; pre-allocate raycast arrays | ~2–3× current | ✅ done |
| **2. Repo hygiene** | 2 d | eventfd poll / `np.concatenate` removal / `torch.compile` | minor | deferred — Python path is going away |
| **3. Decompilation & type map** | 1 w | dnSpy dump, Harmony FSM tracer, arena collider export, trace recorder | — | ✅ tracer + `type-map.md` + `lace-fsm.md` docs done; manual dnSpy dump still pending |
| **4. Madrona scaffold** | 1 w | empty ECS project stepping N envs with no-op physics + CleanRL PPO; prove pipeline end-to-end | ~10 M no-op tps | ✅ **1.82 B raw / 1.25 B random-acts / 80 M with policy** @ 65 k worlds on 4070S |
| **5. Physics port** (HeroController) | 1.5 w | `Rigidbody2D` semantics, ground check, dash, jump, i-frames; oracle diff < 0.1 u | **hold ≥ 50 M tps with policy** | pending |
| **6. Raycast sensor** | 3 d | 32-ray distance + 6 hit types against static arena bitmap | holds | pending |
| **7. Lace FSM port** | 1.5 w | FSM components + attack spawners + phase transitions; 0 anim-state mismatches | holds | pending |
| **8. Training run** | ongoing | PPO to parity with existing agent, then push beyond; Unity oracle eval every N steps | convergence in minutes | pending |
| **9. Framework generalisation** | ongoing | a second boss = YAML + small FSM port, no code rewrite | — | pending |

Critical path: **5 → 6 → 7 → 8.**

## 4. Phase 4 measured results (RTX 4070 Super, 12 GB VRAM, Python 3.13, torch 2.9)

| worlds | raw sim | + random-action writes | + full MLP policy |
|---|---|---|---|
| 1 024 | 57 M tps | 34 M tps | 4 M tps |
| 4 096 | 192 M tps | 120 M tps | 18 M tps |
| 16 384 | 628 M tps | 431 M tps | 62 M tps |
| **65 536** | **1.82 B tps** | **1.25 B tps** | **80 M tps** |

Ratio vs Unity baseline (~300 tps/instance): **~270 000× at raw sim, ~210 000× with the full policy**. Full benchmark CSV in `framework-requirements.md` §11; harness at `sim/silksong_sim/scripts/benchmark.py`.

The 80 M tps with policy is why the Phase 5 floor is **≥ 50 M tps with policy** — we have ~40 % headroom to spend on real physics before dropping below that floor.

## 5. What got cut from the repo after Phase 4

- `silksong/shared_memory.py` — kept, used only by the fidelity harness now.
- `silksong/env.py` `to_observation` concat chain — replaced by Madrona's zero-copy tensor exports.
- `silksong/networks.py` `MultiHeadFeatureExtractor` — worth porting to the new learner.
- SB3 `train.py` / `tune.py` — deprecated in favour of `sim/silksong_sim/scripts/train_ppo.py`.
- `plugin/Source/Core/EpisodeResetter.cs` (1532 LoC, 116 reflection resets) — **deleted on the sim side**; plugin keeps it for oracle mode only.
- `plugin/Source/Managers/BossProjectileManager.cs` — projectiles become fixed-size ECS ring-buffer components in the sim (see `phase5-physics-requirements.md` §2).

## 6. Where to find current specs

- Canonical spec (hardware, throughput floor, obs/action contract, physics cadence, build instructions, CUDA patches, file tree, phase status): **`../framework-requirements.md`**
- Phase 5 physics rules (data layout, branchless integrator, collision tilemap, FSM dispatch, what-we-don't-port): **`../phase5-physics-requirements.md`**
- Obs / action wire format byte-for-byte: **`csharp-audit.md` §3 and §4**
- Every game field the sim must reproduce: **`type-map.md`**
- Lace state graph and phase thresholds: **`lace-fsm.md`**
- Decompilation toolchain and fidelity oracle design: **`decompilation-plan.md`**
