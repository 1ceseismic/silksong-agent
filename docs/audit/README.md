# docs/audit/

The deep-dive audits that produced the canonical spec. Not the spec itself
— for that, read the parent directory:

- `../README.md` — docs index
- `../framework-requirements.md` — the durable spec (start here if resuming)
- `../phase5-physics-requirements.md` — Phase 5 physics perf constraints

## How to use this directory

Each file is labelled at the top as **REFERENCE** (keep open during
implementation of a specific phase) or **HISTORICAL** (preserved for
reasoning archive, not required reading).

| File | Status | What it's for |
|---|---|---|
| [`synthesis.md`](./synthesis.md) | HISTORICAL + active roadmap | narrative: how we got here, phase table, measured numbers |
| [`type-map.md`](./type-map.md) | **REFERENCE — Phase 5 + Phase 7** | every game-internal field the sim must reproduce |
| [`lace-fsm.md`](./lace-fsm.md) | **REFERENCE — Phase 7** | complete Lace state graph, 71 animation states, phase thresholds |
| [`decompilation-plan.md`](./decompilation-plan.md) | **REFERENCE — Phase 5 + Phase 7** | toolchain, effort estimate, fidelity-oracle design |
| [`csharp-audit.md`](./csharp-audit.md) | MIXED | §3 + §4 + §5 are REFERENCE (frozen obs/action spec + fidelity checklist); rest is historical |
| [`python-audit.md`](./python-audit.md) | HISTORICAL | why the Unity + SB3 pipeline was replaced |
| [`sota-architecture.md`](./sota-architecture.md) | HISTORICAL | why Madrona was chosen and what was rejected |

## Triage for a new reader

- **You are about to write Phase 5 physics**: read
  `../phase5-physics-requirements.md`, then `type-map.md`,
  then `decompilation-plan.md`.
- **You are about to port the Lace FSM (Phase 7)**: read `lace-fsm.md`,
  then `type-map.md` (boss section), then `csharp-audit.md` §3.3.
- **You are writing the Phase 6 raycast sensor**: read `csharp-audit.md`
  §3.4, then `phase5-physics-requirements.md` §5.
- **You are tuning the learner (Phase 8)**: read `../framework-requirements.md`
  §3 (obs/action contract) and §6 (substrate + learner). Nothing in this
  folder is required.
- **You want the "why did we pick this stack" history**: read
  `synthesis.md` §1-§2, then skim `sota-architecture.md`.

## Don't duplicate

If you find yourself restating something from `../framework-requirements.md`
or `../phase5-physics-requirements.md` in here, you're duplicating the
canonical spec. Link to the canonical doc instead. The audit files are
history + reference detail; the canonical docs are the binding contract.
