"""PPO for Silksong boss fights via the Madrona-backed sim."""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

_build_dir = str(Path(__file__).resolve().parent.parent / "build")
if os.path.isdir(_build_dir) and _build_dir not in sys.path:
    sys.path.insert(0, _build_dir)

import torch
import torch.nn as nn
from torch.distributions import Bernoulli

import silksong_sim

OBS_DIM = 14 + 10 + 32 + 32
NUM_BINARY_ACTIONS = 10


@dataclass
class PPOConfig:
    num_worlds: int = 4096
    total_steps: int = 1_000_000
    rollout_len: int = 128
    minibatch_size: int = 8192
    update_epochs: int = 4
    lr: float = 3e-4
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_coef: float = 0.2
    ent_coef: float = 0.001
    vf_coef: float = 0.5
    max_grad_norm: float = 0.5
    device: str = "cuda"
    compile: bool = True
    seed: int = 42


class Policy(nn.Module):

    def __init__(self, obs_dim: int, num_actions: int, hidden: int = 128):
        super().__init__()
        self.trunk = nn.Sequential(
            nn.Linear(obs_dim, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden), nn.ReLU(),
        )
        self.action_logits = nn.Linear(hidden, num_actions)
        self.value = nn.Linear(hidden, 1)

    def forward(self, obs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        h = self.trunk(obs)
        return self.action_logits(h), self.value(h).squeeze(-1)


def gather_obs(
    player: torch.Tensor,
    boss: torch.Tensor,
    ray_dist: torch.Tensor,
    ray_hit: torch.Tensor,
) -> torch.Tensor:
    return torch.cat([
        player.squeeze(1),
        boss.squeeze(1),
        ray_dist.squeeze(1),
        ray_hit.squeeze(1).float(),
    ], dim=-1)


def compute_gae(
    rewards: torch.Tensor,
    values: torch.Tensor,
    dones: torch.Tensor,
    next_value: torch.Tensor,
    gamma: float,
    gae_lambda: float,
) -> tuple[torch.Tensor, torch.Tensor]:
    T = rewards.shape[0]
    advantages = torch.zeros_like(rewards)
    last_gae = torch.zeros_like(next_value)
    for t in reversed(range(T)):
        next_not_done = 1.0 - dones[t]
        next_v = next_value if t == T - 1 else values[t + 1]
        delta = rewards[t] + gamma * next_v * next_not_done - values[t]
        last_gae = delta + gamma * gae_lambda * next_not_done * last_gae
        advantages[t] = last_gae
    returns = advantages + values
    return advantages, returns


def train(cfg: PPOConfig, use_wandb: bool = False, save_path: str = "policy.pt"):
    device = torch.device(cfg.device)
    torch.manual_seed(cfg.seed)

    exec_mode = (silksong_sim.madrona.ExecMode.CUDA if cfg.device == "cuda"
                 else silksong_sim.madrona.ExecMode.CPU)

    sim = silksong_sim.SimManager(
        exec_mode=exec_mode,
        gpu_id=0,
        num_worlds=cfg.num_worlds,
        rand_seed=cfg.seed,
        auto_reset=True,
    )

    player_t = sim.player_obs_tensor().to_torch()
    boss_t = sim.boss_obs_tensor().to_torch()
    rayd_t = sim.raycast_distances_tensor().to_torch()
    rayh_t = sim.raycast_hit_types_tensor().to_torch()
    action_t = sim.action_tensor().to_torch()
    reward_t = sim.reward_tensor().to_torch()
    done_t = sim.done_tensor().to_torch()

    policy = Policy(OBS_DIM, NUM_BINARY_ACTIONS).to(device)
    optim = torch.optim.Adam(policy.parameters(), lr=cfg.lr)

    if cfg.compile:
        policy_fwd = torch.compile(policy, mode="reduce-overhead")
    else:
        policy_fwd = policy

    T, N = cfg.rollout_len, cfg.num_worlds
    obs_buf = torch.zeros(T, N, OBS_DIM, device=device, dtype=torch.float32)
    act_buf = torch.zeros(T, N, NUM_BINARY_ACTIONS, device=device, dtype=torch.float32)
    logp_buf = torch.zeros(T, N, device=device, dtype=torch.float32)
    val_buf = torch.zeros(T, N, device=device, dtype=torch.float32)
    rew_buf = torch.zeros(T, N, device=device, dtype=torch.float32)
    done_buf = torch.zeros(T, N, device=device, dtype=torch.float32)

    total_env_steps = 0
    iter_num = 0
    start = time.perf_counter()

    while total_env_steps < cfg.total_steps:
        iter_num += 1

        with torch.no_grad():
            for t in range(T):
                obs = gather_obs(player_t, boss_t, rayd_t, rayh_t)
                logits, value = policy_fwd(obs)
                dist = Bernoulli(logits=logits)
                action = dist.sample()
                logp = dist.log_prob(action).sum(-1)

                obs_buf[t] = obs
                act_buf[t] = action
                logp_buf[t] = logp
                val_buf[t] = value

                action_t.copy_(action.to(torch.int32).unsqueeze(1))
                sim.step()

                rew_buf[t] = reward_t.squeeze(-1).squeeze(-1)
                done_buf[t] = done_t.squeeze(-1).squeeze(-1).float()

            bootstrap_obs = gather_obs(player_t, boss_t, rayd_t, rayh_t)
            _, bootstrap_v = policy_fwd(bootstrap_obs)

        advantages, returns = compute_gae(
            rew_buf, val_buf, done_buf, bootstrap_v,
            cfg.gamma, cfg.gae_lambda,
        )
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        flat_obs = obs_buf.reshape(T * N, OBS_DIM)
        flat_act = act_buf.reshape(T * N, NUM_BINARY_ACTIONS)
        flat_logp = logp_buf.reshape(T * N)
        flat_adv = advantages.reshape(T * N)
        flat_ret = returns.reshape(T * N)

        batch = T * N
        mb = cfg.minibatch_size
        idx = torch.randperm(batch, device=device)

        pg_loss_sum = v_loss_sum = ent_sum = n_mbs = 0
        for _ in range(cfg.update_epochs):
            for s in range(0, batch, mb):
                b = idx[s:s + mb]
                logits, value = policy_fwd(flat_obs[b])
                dist = Bernoulli(logits=logits)
                new_logp = dist.log_prob(flat_act[b]).sum(-1)
                entropy = dist.entropy().sum(-1).mean()

                ratio = (new_logp - flat_logp[b]).exp()
                surr1 = ratio * flat_adv[b]
                surr2 = torch.clamp(ratio, 1 - cfg.clip_coef, 1 + cfg.clip_coef) * flat_adv[b]
                pg_loss = -torch.min(surr1, surr2).mean()
                v_loss = 0.5 * (value - flat_ret[b]).pow(2).mean()
                loss = pg_loss + cfg.vf_coef * v_loss - cfg.ent_coef * entropy

                optim.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(policy.parameters(), cfg.max_grad_norm)
                optim.step()

                pg_loss_sum += pg_loss.item()
                v_loss_sum += v_loss.item()
                ent_sum += entropy.item()
                n_mbs += 1

        total_env_steps += T * N
        elapsed = time.perf_counter() - start
        tps = total_env_steps / elapsed
        avg_pg_loss = pg_loss_sum / n_mbs
        avg_v_loss = v_loss_sum / n_mbs
        avg_entropy = ent_sum / n_mbs

        print(
            f"iter={iter_num:4d}  env_steps={total_env_steps:>10,}  "
            f"tps={tps:>12,.0f}  "
            f"pg_loss={avg_pg_loss:+.4f}  "
            f"v_loss={avg_v_loss:.4f}  "
            f"entropy={avg_entropy:.3f}"
        )

        if use_wandb:
            import wandb
            wandb.log({
                "train/pg_loss": avg_pg_loss,
                "train/v_loss": avg_v_loss,
                "train/entropy": avg_entropy,
                "train/tps": tps,
                "train/env_steps": total_env_steps,
                "train/iteration": iter_num,
            }, step=total_env_steps)

    # Save final checkpoint
    torch.save(policy.state_dict(), save_path)
    print(f"Policy saved to {save_path}")

    if use_wandb:
        import wandb
        wandb.save(save_path)
        wandb.finish()


PRESETS = {
    "seis": {  # RTX 4070 Super 12GB
        "num_worlds": 32768,
        "rollout_len": 256,
        "minibatch_size": 16384,
        "total_steps": 2_000_000_000,
    },
    "nyx": {  # RTX 3050 6GB
        "num_worlds": 8192,
        "rollout_len": 128,
        "minibatch_size": 8192,
        "total_steps": 2_000_000_000,
    },
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", choices=list(PRESETS.keys()),
                    help="hardware preset (overrides num-worlds/rollout-len/minibatch-size)")
    ap.add_argument("--num-worlds", type=int, default=4096)
    ap.add_argument("--total-steps", type=int, default=1_000_000)
    ap.add_argument("--rollout-len", type=int, default=128)
    ap.add_argument("--minibatch-size", type=int, default=8192)
    ap.add_argument("--device", choices=["cuda", "cpu"], default="cuda")
    ap.add_argument("--no-compile", action="store_true")
    ap.add_argument("--no-wandb", action="store_true", help="disable Weights & Biases logging")
    ap.add_argument("--wandb-project", type=str, default="silksong-agent",
                    help="wandb project name (default: silksong-agent)")
    ap.add_argument("--wandb-entity", type=str, default=None,
                    help="wandb entity / team (default: wandb default)")
    args = ap.parse_args()

    if args.preset:
        p = PRESETS[args.preset]
        args.num_worlds = p["num_worlds"]
        args.rollout_len = p["rollout_len"]
        args.minibatch_size = p["minibatch_size"]
        args.total_steps = p["total_steps"]

    cfg = PPOConfig(
        num_worlds=args.num_worlds,
        total_steps=args.total_steps,
        rollout_len=args.rollout_len,
        minibatch_size=args.minibatch_size,
        device=args.device,
        compile=not args.no_compile,
    )

    use_wandb = not args.no_wandb
    if use_wandb:
        import wandb
        wandb.init(
            project=args.wandb_project,
            entity=args.wandb_entity,
            config=vars(cfg),
            name=None,
        )

    train(cfg, use_wandb=use_wandb)


if __name__ == "__main__":
    main()
