"""Read binary trace files recorded by TraceRecorder."""

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np

MAGIC = b"SKTR"
VERSION_LATEST = 2
SUPPORTED_VERSIONS = {1, 2}

ACTION_NAMES = [
    "left", "right", "up", "down", "jump",
    "attack", "dash", "clawline", "skill", "heal",
]

GAME_STATE_DTYPE = np.dtype([
    ("playerPosX", "<f4"),
    ("playerPosY", "<f4"),
    ("playerVelX", "<f4"),
    ("playerVelY", "<f4"),
    ("playerHealth", "<i4"),
    ("playerMaxHealth", "<i4"),
    ("playerSilk", "<i4"),
    ("playerAnimationState", "<i4"),
    ("playerAnimationProgress", "<f4"),
    ("playerGrounded", "u1"),
    ("playerCanDash", "u1"),
    ("playerFacingRight", "u1"),
    ("playerInvincible", "u1"),
    ("playerCanAttack", "u1"),
    ("_pad0", "V3"),
    ("bossPosX", "<f4"),
    ("bossPosY", "<f4"),
    ("bossVelX", "<f4"),
    ("bossVelY", "<f4"),
    ("bossHealth", "<i4"),
    ("bossMaxHealth", "<i4"),
    ("bossPhase", "<i4"),
    ("bossAnimationState", "<i4"),
    ("bossAnimationProgress", "<f4"),
    ("bossFacingRight", "u1"),
    ("_pad1", "V3"),
    ("episodeTime", "<f4"),
    ("terminated", "u1"),
    ("truncated", "u1"),
    ("_pad2", "V2"),
    ("raycastDistances", "<f4", (32,)),
    ("raycastHitTypes", "<i4", (32,)),
])

GAME_STATE_SIZE = GAME_STATE_DTYPE.itemsize

_EXPECTED_GAME_STATE_SIZE = 348
assert GAME_STATE_SIZE == _EXPECTED_GAME_STATE_SIZE, (
    f"GAME_STATE_DTYPE size {GAME_STATE_SIZE} != expected {_EXPECTED_GAME_STATE_SIZE}"
)

HERO_PRIVATE_DTYPE = np.dtype([
    ("cStateBits", "<u4"),
    ("heroState", "<i4"),
    ("transitionState", "<i4"),
    ("jumpSteps", "<i4"),
    ("jumpedSteps", "<i4"),
    ("doubleJumpSteps", "<i4"),
    ("dashTimer", "<f4"),
    ("dashTime", "<f4"),
    ("dashCooldownTimer", "<f4"),
    ("airDashed", "u1"),
    ("doubleJumped", "u1"),
    ("didAirHang", "u1"),
    ("controlReqlinquished", "u1"),
    ("ledgeBufferSteps", "<i4"),
    ("sprintBufferSteps", "<i4"),
    ("jumpQueueSteps", "<i4"),
    ("dashQueueSteps", "<i4"),
    ("jumpReleaseQueueSteps", "<i4"),
    ("landingBufferSteps", "<i4"),
    ("headBumpSteps", "<i4"),
    ("wallLockSteps", "<i4"),
    ("wallUnstickSteps", "<i4"),
    ("wallJumpChainStepsLeft", "<i4"),
    ("fallTimer", "<f4"),
    ("gravityScale", "<f4"),
    ("moveInput", "<f4"),
    ("verticalInput", "<f4"),
    ("currentWalljumpSpeed", "<f4"),
    ("wallStickTimer", "<f4"),
    ("shuttlecockSpeed", "<f4"),
    ("shuttleCockJumpSteps", "<i4"),
    ("recoilStepsLeft", "<i4"),
    ("recoilVelocity", "<f4"),
    ("recoilTimer", "<f4"),
    ("extraBits", "<u4"),
    ("sprintFsmStateHash", "<u4"),
    ("sprintAddSpeed", "<f4"),
    ("extraAirMoveCount", "<i4"),
    ("ext0Vx", "<f4"), ("ext0Vy", "<f4"), ("ext0Decay", "<f4"), ("ext0Flags", "<u4"),
    ("ext1Vx", "<f4"), ("ext1Vy", "<f4"), ("ext1Decay", "<f4"), ("ext1Flags", "<u4"),
    ("ext2Vx", "<f4"), ("ext2Vy", "<f4"), ("ext2Decay", "<f4"), ("ext2Flags", "<u4"),
    ("ext3Vx", "<f4"), ("ext3Vy", "<f4"), ("ext3Decay", "<f4"), ("ext3Flags", "<u4"),
])
HERO_PRIVATE_SIZE = HERO_PRIVATE_DTYPE.itemsize
_EXPECTED_HERO_PRIVATE_SIZE = 204
assert HERO_PRIVATE_SIZE == _EXPECTED_HERO_PRIVATE_SIZE, (
    f"HERO_PRIVATE_DTYPE size {HERO_PRIVATE_SIZE} != expected {_EXPECTED_HERO_PRIVATE_SIZE}"
)

CSTATE_BITS = [
    "facingRight", "onGround", "jumping", "falling", "dashing",
    "isSprinting", "isBackSprinting", "touchingWall", "wallSliding", "wallClinging",
    "wallJumping", "doubleJumping", "wasOnGround", "floating", "shuttleCock",
    "bouncing", "downSpiking", "downSpikeBouncing", "willHardLand", "transitioning",
    "inWalkZone", "onConveyor", "recoiling", "touchingSlopeL", "touchingSlopeR",
    "attacking", "preventDash", "dashCooldown", "inUpdraft", "airDashing",
    "invulnerable", "shroomBouncing",
]

EXTRA_BITS = [
    "wallJumpedL", "wallJumpedR", "wallSlidingL", "wallSlidingR",
    "touchingWallL", "touchingWallR", "wallLocked", "dashingDown",
    "acceptingInput", "jumpQueuing", "doubleJumpQueuing", "dashQueuing",
    "jumpReleaseQueuing", "canSoftLand", "fallCheckFlagged", "tryShove",
]

RECORD_DTYPE = np.dtype([
    ("tick", "<u4"),
    ("actions", [(name, "u1") for name in ACTION_NAMES]),
    ("state", GAME_STATE_DTYPE),
])

RECORD_V2_DTYPE = np.dtype([
    ("tick", "<u4"),
    ("actions", [(name, "u1") for name in ACTION_NAMES]),
    ("state", GAME_STATE_DTYPE),
    ("hero", HERO_PRIVATE_DTYPE),
])


@dataclass
class TraceRecord:
    tick: int
    actions: dict[str, bool]
    player_pos: tuple[float, float]
    player_vel: tuple[float, float]
    player_health: int
    player_silk: int
    player_anim_state: int
    player_anim_progress: float
    player_grounded: bool
    player_can_dash: bool
    player_facing_right: bool
    player_invincible: bool
    player_can_attack: bool
    boss_pos: tuple[float, float]
    boss_vel: tuple[float, float]
    boss_health: int
    boss_phase: int
    boss_anim_state: int
    boss_anim_progress: float
    boss_facing_right: bool
    episode_time: float
    raycast_distances: np.ndarray
    raycast_hit_types: np.ndarray


def _read_header(buf: bytes, path: Path) -> tuple[int, int, int]:
    if len(buf) < 12:
        raise ValueError(f"Trace file {path} truncated: header requires ≥ 12 bytes, got {len(buf)}")
    if buf[:4] != MAGIC:
        raise ValueError(f"Invalid trace file {path}: expected magic {MAGIC!r}, got {bytes(buf[:4])!r}")
    version = int(np.frombuffer(buf[4:8], dtype="<u4")[0])
    if version not in SUPPORTED_VERSIONS:
        raise ValueError(f"Unsupported trace version in {path}: {version} "
                         f"(reader supports {sorted(SUPPORTED_VERSIONS)})")
    gamestate_size = int(np.frombuffer(buf[8:12], dtype="<u4")[0])
    if gamestate_size != GAME_STATE_SIZE:
        raise ValueError(
            f"GameState size mismatch in {path}: file={gamestate_size}, reader={GAME_STATE_SIZE}. "
            f"C# GameState struct layout has changed; update GAME_STATE_DTYPE in {__file__}."
        )
    hero_size = 0
    if version >= 2:
        if len(buf) < 16:
            raise ValueError(f"Trace file {path} truncated: v{version} header requires 16 bytes")
        hero_size = int(np.frombuffer(buf[12:16], dtype="<u4")[0])
        if hero_size != HERO_PRIVATE_SIZE:
            raise ValueError(
                f"HeroPrivate size mismatch in {path}: file={hero_size}, reader={HERO_PRIVATE_SIZE}. "
                f"C# HeroPrivate struct layout has changed; update HERO_PRIVATE_DTYPE in {__file__}."
            )
    return version, gamestate_size, hero_size


def read_trace_np(path: str | Path) -> np.ndarray:
    path = Path(path)
    raw = path.read_bytes()
    version, _, _ = _read_header(raw, path)
    header_len = 16 if version >= 2 else 12
    dtype = RECORD_V2_DTYPE if version >= 2 else RECORD_DTYPE

    n_full = (len(raw) - header_len) // dtype.itemsize
    return np.frombuffer(raw, dtype=dtype, count=n_full, offset=header_len).copy()


def read_trace(path: str | Path) -> list[TraceRecord]:
    arr = read_trace_np(path)
    state = arr["state"]
    acts = arr["actions"]

    return [
        TraceRecord(
            tick=int(arr["tick"][i]),
            actions={name: bool(acts[name][i]) for name in ACTION_NAMES},
            player_pos=(float(state["playerPosX"][i]), float(state["playerPosY"][i])),
            player_vel=(float(state["playerVelX"][i]), float(state["playerVelY"][i])),
            player_health=int(state["playerHealth"][i]),
            player_silk=int(state["playerSilk"][i]),
            player_anim_state=int(state["playerAnimationState"][i]),
            player_anim_progress=float(state["playerAnimationProgress"][i]),
            player_grounded=bool(state["playerGrounded"][i]),
            player_can_dash=bool(state["playerCanDash"][i]),
            player_facing_right=bool(state["playerFacingRight"][i]),
            player_invincible=bool(state["playerInvincible"][i]),
            player_can_attack=bool(state["playerCanAttack"][i]),
            boss_pos=(float(state["bossPosX"][i]), float(state["bossPosY"][i])),
            boss_vel=(float(state["bossVelX"][i]), float(state["bossVelY"][i])),
            boss_health=int(state["bossHealth"][i]),
            boss_phase=int(state["bossPhase"][i]),
            boss_anim_state=int(state["bossAnimationState"][i]),
            boss_anim_progress=float(state["bossAnimationProgress"][i]),
            boss_facing_right=bool(state["bossFacingRight"][i]),
            episode_time=float(state["episodeTime"][i]),
            raycast_distances=np.array(state["raycastDistances"][i], dtype=np.float32),
            raycast_hit_types=np.array(state["raycastHitTypes"][i], dtype=np.int32),
        )
        for i in range(len(arr))
    ]


def print_summary(arr: np.ndarray) -> None:
    from rich.console import Console
    from rich.table import Table

    console = Console()

    if len(arr) == 0:
        console.print("Empty trace.")
        return

    state = arr["state"]
    acts = arr["actions"]
    n = len(arr)

    overview = Table(title=f"Trace ({n} ticks)", show_header=False, box=None)
    overview.add_row("Duration", f"{float(state['episodeTime'][-1]):.2f}s")
    overview.add_row(
        "Player health",
        f"{int(state['playerHealth'][0])} -> {int(state['playerHealth'][-1])}",
    )
    overview.add_row(
        "Boss health",
        f"{int(state['bossHealth'][0])} -> {int(state['bossHealth'][-1])}",
    )
    overview.add_row("Boss phases seen", str(sorted(np.unique(state["bossPhase"]).tolist())))
    console.print(overview)

    table = Table(title="Action press counts")
    table.add_column("Action")
    table.add_column("Count", justify="right")
    table.add_column("% ticks", justify="right")
    for name in ACTION_NAMES:
        count = int(acts[name].sum())
        table.add_row(name, str(count), f"{100 * count / n:.1f}%")
    console.print(table)


def dump_csv(arr: np.ndarray, path: str | Path) -> None:
    path = Path(path)
    state = arr["state"]
    acts = arr["actions"]

    header = [
        "tick", "episode_time",
        "player_x", "player_y", "player_vx", "player_vy",
        "player_health", "player_silk", "player_anim", "player_grounded",
        "boss_x", "boss_y", "boss_vx", "boss_vy",
        "boss_health", "boss_phase", "boss_anim",
        *(f"act_{n}" for n in ACTION_NAMES),
    ]

    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for i in range(len(arr)):
            w.writerow([
                int(arr["tick"][i]),
                f"{float(state['episodeTime'][i]):.4f}",
                f"{float(state['playerPosX'][i]):.4f}",
                f"{float(state['playerPosY'][i]):.4f}",
                f"{float(state['playerVelX'][i]):.4f}",
                f"{float(state['playerVelY'][i]):.4f}",
                int(state["playerHealth"][i]),
                int(state["playerSilk"][i]),
                int(state["playerAnimationState"][i]),
                int(state["playerGrounded"][i]),
                f"{float(state['bossPosX'][i]):.4f}",
                f"{float(state['bossPosY'][i]):.4f}",
                f"{float(state['bossVelX'][i]):.4f}",
                f"{float(state['bossVelY'][i]):.4f}",
                int(state["bossHealth"][i]),
                int(state["bossPhase"][i]),
                int(state["bossAnimationState"][i]),
                *(int(acts[name][i]) for name in ACTION_NAMES),
            ])
    print(f"Wrote {len(arr)} records to {path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Read Silksong trace files")
    parser.add_argument("trace", help="Path to .bin trace file")
    parser.add_argument("--summary", action="store_true", help="Print summary stats")
    parser.add_argument("--dump-csv", type=str, help="Export to CSV")
    args = parser.parse_args()

    arr = read_trace_np(args.trace)

    if args.summary or not args.dump_csv:
        print_summary(arr)

    if args.dump_csv:
        dump_csv(arr, args.dump_csv)
