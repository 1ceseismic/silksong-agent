# docs/

Canonical documentation for the Silksong RL training framework.

## Read in this order

1. **[`framework-requirements.md`](./framework-requirements.md)** — durable spec. Obs/action contract, throughput floor, substrate + toolchain, build instructions, file tree, phase status. Start here if you are resuming work.
2. **[`phase5-physics-requirements.md`](./phase5-physics-requirements.md)** — hot-path performance rulebook. Read before writing any physics code.
3. **[`phase5.4-calibration.md`](./phase5.4-calibration.md)** — oracle-diff workflow for calibrating physics constants against recorded Silksong traces.
4. **[`audit/synthesis.md`](./audit/synthesis.md)** — master plan, phase roadmap, measured numbers.

## Reference (deep-dive audits)

Source material for the requirements docs above.

- [`audit/python-audit.md`](./audit/python-audit.md) — Python hot path + IPC + RL pipeline
- [`audit/csharp-audit.md`](./audit/csharp-audit.md) — BepInEx plugin + Unity-side waste + frozen obs/action spec
- [`audit/decompilation-plan.md`](./audit/decompilation-plan.md) — game-logic extraction plan + fidelity oracle design
- [`audit/sota-architecture.md`](./audit/sota-architecture.md) — substrate comparison (Madrona / Brax / PufferLib / etc.)
- [`audit/type-map.md`](./audit/type-map.md) — every game-internal type the sim must reproduce
- [`audit/lace-fsm.md`](./audit/lace-fsm.md) — Lace boss state graph (all 71 animation states)

Invariants (hardware, substrate, obs/action, cadence, fidelity, 50 M tps floor) live in `framework-requirements.md`. This file is a table of contents, not a spec.
