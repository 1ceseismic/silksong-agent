# silksong-agent

GPU-batched reinforcement-learning training framework for Hollow Knight:
Silksong boss fights. Built on the [Madrona Engine](https://github.com/shacklettbp/madrona):
the 2D platformer physics + boss FSM are reimplemented as a CUDA ECS sim so
training can run ~65 k worlds in parallel on a single GPU. The Unity game
itself is kept around as a **fidelity oracle**: it generates ground-truth
traces and validates trained policies, but no longer participates in bulk
training.

Reference boss: **Lace** (3-phase FSM). Framework is designed so adding
another boss is a data drop-in, not a rewrite.

**Status.** Phase 4 complete (Madrona scaffold + PPO loop end-to-end,
measured well above throughput floor). Phase 5 in progress, porting real
Silksong physics while holding the ≥ 50 M tps-with-policy floor.

## Start here

All durable specs, build instructions, and phase status live in
[`docs/`](./docs/README.md). Read in this order:

1. [`docs/framework-requirements.md`](./docs/framework-requirements.md): canonical spec covering obs/action contract, throughput floor, toolchain, build, file tree, phase status.
2. [`docs/phase5-physics-requirements.md`](./docs/phase5-physics-requirements.md): hot-path performance rules for the physics port.
3. [`docs/audit/synthesis.md`](./docs/audit/synthesis.md): master plan and measured numbers.

The sim itself lives at [`sim/silksong_sim/`](./sim/silksong_sim/) (forked from
`madrona_escape_room`, upstream kept pristine at `sim/madrona_escape_room/`).

## Decompiled C# source (required for FSM auditing)

The `decompiled/` directory is gitignored (27 MB, ~5000 files). Regenerate it from the game's managed DLL:

```bash
~/.dotnet/tools/ilspycmd \
    "/home/seis/game/Hollow Knight Silksong/Hollow Knight Silksong_Data/Managed/Assembly-CSharp.dll" \
    -p -o decompiled/
```

Requires `ilspycmd` (`dotnet tool install -g ilspycmd`). The output is the ground truth for all FSM action auditing and porting work.

## Oracle-mode Unity plugin

The original Unity + BepInEx + SB3 pipeline (`plugin/`, `silksong/`,
`train.py`, `tune.py`) is retained **for fidelity-oracle use only**: running
a trained policy against the real game, or recording `{tick, action,
GameState}` traces via the plugin's F10 toggle for trace-diff validation.

If you need to bring that side up, see `docs/framework-requirements.md` §3
(obs/action contract) and §5 (fidelity oracle). In brief:

- Install a copy of [Hollow Knight: Silksong](https://store.steampowered.com/app/1030300/Hollow_Knight_Silksong/), install [BepInEx 5](https://github.com/BepInEx/BepInEx/releases) into the game folder, drop `steam_appid.txt` containing `1030300` next to the executable.
- Copy `resources/user1.dat` into the Silksong save folder
  - (Linux: `~/.config/unity3d/Team Cherry/Hollow Knight Silksong/default`
  -  Windows: `%USERPROFILE%\AppData\LocalLow\Team Cherry\Hollow Knight Silksong\default`)
- `cp plugin/Directory.Build.props.example plugin/Directory.Build.props`, `cp .env.example .env`,
    - set `SILKSONG_PATH` to the game executable
- `dotnet build plugin`, which copies the plugin into `BepInEx/plugins/` automatically.

Debug / trace keys in-game:
- `F1` state overlay,
- `F2` raycast viz, 
- `F9`minimal rendering (NoFx only),
- `F10` start/stop trace recording
    
Traces are read back via [`scripts/read_trace.py`](./scripts/read_trace.py).

Do **not** use the SB3 trainers (`train.py`, `tune.py`) for new work, they
remain only so existing 30M-step checkpoints stay reproducible.

## Acknowledgments

Sim forked from [`madrona_escape_room`](https://github.com/shacklettbp/madrona_escape_room) (Shacklett et al.).
Original Unity plugin + SB3 pipeline inspired by [HKRL](https://github.com/AdityaJain1030/HKRL);
multi-instance + Linux support carried forward from [deeean's fork](https://github.com/deeean).

license:
MIT License
