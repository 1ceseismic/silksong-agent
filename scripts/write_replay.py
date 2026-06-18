"""Serializer for the .skrp scripted-replay action file."""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

MAGIC = b"SKRP"
VERSION = 1
DEFAULT_DT = 0.02

ACTION_NAMES = [
    "left", "right", "up", "down", "jump",
    "attack", "dash", "clawline", "skill", "heal",
]
_IDX = {n: i for i, n in enumerate(ACTION_NAMES)}


@dataclass
class ActionScript:
    dt: float = DEFAULT_DT
    seed: int = 42
    _ticks: list[list[int]] = field(default_factory=list)

    def hold(self, seconds: float, **buttons: bool) -> "ActionScript":
        n = int(round(seconds / self.dt))
        row = [0] * 10
        for name, v in buttons.items():
            row[_IDX[name]] = 1 if v else 0
        for _ in range(n):
            self._ticks.append(row.copy())
        return self

    def tap(self, **buttons: bool) -> "ActionScript":
        row = [0] * 10
        for name, v in buttons.items():
            row[_IDX[name]] = 1 if v else 0
        self._ticks.append(row)
        return self

    def idle(self, seconds: float) -> "ActionScript":
        return self.hold(seconds)

    def write(self, path: str | Path) -> int:
        path = Path(path)
        n = len(self._ticks)
        with open(path, "wb") as f:
            f.write(MAGIC)
            f.write(struct.pack("<I", VERSION))
            f.write(struct.pack("<f", self.dt))
            f.write(struct.pack("<I", int(self.seed) & 0xFFFFFFFF))
            f.write(struct.pack("<I", n))
            for row in self._ticks:
                f.write(bytes(row))
        return n


def read_replay(path: str | Path) -> tuple[float, int, list[list[int]]]:
    path = Path(path)
    raw = path.read_bytes()
    if len(raw) < 20 or raw[:4] != MAGIC:
        raise ValueError(f"{path} is not a SKRP file")
    version, = struct.unpack_from("<I", raw, 4)
    if version != VERSION:
        raise ValueError(f"{path} version {version}, expected {VERSION}")
    dt, = struct.unpack_from("<f", raw, 8)
    seed, = struct.unpack_from("<I", raw, 12)
    count, = struct.unpack_from("<I", raw, 16)
    if len(raw) < 20 + count * 10:
        raise ValueError(f"{path} truncated")
    rows = []
    for i in range(count):
        o = 20 + i * 10
        rows.append(list(raw[o:o + 10]))
    return dt, int(seed), rows
