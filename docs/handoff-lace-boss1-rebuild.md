# Handoff: Lace Boss1 Rebuild

## Situation

We built a sim for the WRONG boss encounter (Lost Lace, 206-state FSM, 800 HP, abyss_cocoon scene). The correct target is **Lace Boss1** (first encounter, 132-state FSM, 250 HP, bone_east_12 scene). The sim infrastructure (Madrona ECS, PPO trainer, visualizer, hero physics) is solid; the boss FSM and arena need rebuilding.

## Extracted Ground Truth (all files in repo)

### Boss FSM
- `scripts/lace_boss1_control_fsm.json` — full 132-state FSM with decoded actions
- `scripts/lace_boss1_fsm_summary.md` — human-readable summary with attack flows, velocities, timings

### Arena Collision
- `scripts/arena_colliders.json` — all 187 colliders from bone_east_12 scene (run `python3 scripts/extract_arena.py bone_east_12` to regenerate)
- `scripts/arena_summary.md` — ASCII map + collider list

### Hero Constants
- `scripts/hero_constants_dump.md` — ground truth from Hero_Hornet.prefab

### Boss Scene Data  
- `scripts/scene_data_dump.md` — boss colliders, stun FSM, health manager (note: this was for Lost Lace/abyss_cocoon, some values differ for Boss1)
- `scripts/scene_data_results.json` — machine-readable

## Key Lace Boss1 Values (ground truth)

```
Boss HP:              250
Boss damage to hero:  1
Boss gravity scale:   2.0 (effective: -120 with base gravity -60)
Boss Centre X:        93.78 (Docks variant)
Boss Land Y:          7.60
Boss invulnerableTime: 0.25s (12-13 frames)
Boss recoilSpeed:     15.0
Boss recoilDuration:  0.15s
Boss constraint X:    [82.4, 105.6]
Boss constraint Y:    [6.5, 1000]

Stun Combo:           8 (hits in 1s window)
Stun Hit Max:         10 (absolute max before forced stun)
Stun Timer:           2.0s (reduced by 0.25 per hit while stunned)

Rage HP:              50% of max (125 HP) — triggers CrossSlash mechanic

Arena floor:          terrain collider (3) at X=[82.0, 106.0], Y=[-5.8, 5.8]
                      Surface at Y≈5.8, lava below at Y≈-0.5
Arena left wall:      inner edge ~X=82
Arena right wall:     inner edge ~X=106
Lava:                 "Lava Box" trigger at (95.1, -0.5)
                      Boss takes 40 HP self-damage on lava contact + teleports to centre
```

## Attack Categories (from FSM summary)

| Category | States | Key velocities | Notes |
|----------|--------|----------------|-------|
| Idle | Idle, CrossSlash?, Distance Check, Close, Far | — | 0.75s wait, distance split at 6.0 |
| ComboSlash | 5 states | lunge vel=30 on strikes 2/4 | 5-hit combo (not 7) |
| Charge | 3 states | antic vel=-32, charge vel=80 (not 70!), decel=0.89 | Wait 0.3s charge |
| JSlash | 5 states + downstab | launch vel=60x/87y (not 60y!), downstab vel=45x/-45y | Includes wall cling + kickoff |
| Counter | 5 states | stance 0.75s (not 0.5s), invincible | Triggers RapidSlash on hit |
| RapidSlash | 3 states | rush vel=19 (not 30) | Only after counter hit |
| Evade/Hop | 11 states | evade vel=-30, hop vel=24 (not 36) | Hop has per-attack target distances |
| Stun | 5 states | knockback vel=-6x/23y | 2.0s stun timer, -0.25 per hit |
| CrossSlash | 6 states | CS Evade vel=-45 | Rage mechanic at 50% HP |
| Lava | 5 states | — | 40 HP self-damage, tele to centre |

## Hero Constants Needing Fix

| Constant | Current | Ground Truth | Source |
|----------|---------|-------------|--------|
| airHangGravScale | 0.2 | 0.1 | HeroController prefab |
| heroRecoilSpeed | 15.0 | 3.75 (horizontal) | HeroController prefab |
| heroRecoilFrames | 5 | 8 | HeroController prefab |
| iFrameAfterHitFrames | 25 | 50 | HeroController INVUL_TIME=1.0s |
| wallJumpVelX | 15.0 | 25.0 (WJ_KICKOFF_SPEED) | HeroController prefab |
| jumpStepsMax | 9 | 8 | HeroController prefab |

## What Exists (keep)

- `sim/silksong_sim/src/sim.cpp` — hero physics (850 lines, calibrated against traces)
- `sim/silksong_sim/src/types.hpp` — ECS components (BossKinematics, BossFSM, etc.)
- `sim/silksong_sim/src/combat.hpp` — AABB hitbox checks, reward scheme
- `sim/silksong_sim/src/raycast.hpp` — 32-ray sensor
- `sim/silksong_sim/src/boss.hpp` — **NEEDS REWRITE** for Boss1 FSM
- `sim/silksong_sim/src/consts.hpp` — **NEEDS UPDATE** with Boss1 values
- `sim/silksong_sim/scripts/train_ppo.py` — PPO trainer (working, saves checkpoints)
- `sim/silksong_sim/scripts/visualize.py` — pygame visualizer with sprites
- `scripts/extract_arena.py` — reusable arena extraction tool

## What Needs Doing

1. **Update consts.hpp** — replace all boss constants with Boss1 values, fix hero constants
2. **Rewrite boss.hpp** — 132-state FSM (simpler than current 206-state), add:
   - Distance Check → Close/Far attack selection
   - Hop-to-attack chain with per-attack target distances
   - CrossSlash rage mechanic (50% HP threshold)
   - Lava damage + teleport
   - Wallcling → Kickoff chain
   - Correct velocities (charge=80, J Slash Y=87, hop=24, etc.)
3. **Rebuild arena bitmap** — bone_east_12 geometry (platform at X=[82,106], lava below)
4. **Retrain** — 2B steps on nyx (~28 min at 1.17M tps)

## Build & Run Commands

```bash
cmake --build sim/silksong_sim/build/ -j$(nproc)
./train --total-steps 2000000000      # training
./viz                                  # visualizer (auto-loads policy.pt)
PYTHONPATH=sim/silksong_sim/build uv run python sim/silksong_sim/scripts/oracle_diff.py --self-test
```

## Remote Training (nyx)

```bash
rsync -avz --exclude 'build/' --exclude '.cuda128/' --exclude '.venv/' --exclude 'wandb/' --exclude 'decompiled/' /home/seis/code/silksong-agent/ nyx:~/Documents/code/silksong-agent/
ssh nyx "cd ~/Documents/code/silksong-agent/sim/silksong_sim && ninja -C build -j\$(nproc)"
ssh nyx "cd ~/Documents/code/silksong-agent && nohup ./train-nyx --total-steps 2000000000 > train.log 2>&1 &"
```
