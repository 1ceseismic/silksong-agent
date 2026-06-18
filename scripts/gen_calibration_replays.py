"""Generate .skrp scripted-replay files for physics calibration."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from write_replay import ActionScript


def preset_jumps() -> ActionScript:
    s = ActionScript(seed=0x5005)
    s.idle(2.0)
    s.hold(0.04, jump=True); s.idle(2.0)
    s.hold(0.2, jump=True); s.idle(2.0)
    s.hold(0.4, jump=True); s.idle(2.5)
    s.hold(0.04, jump=True); s.idle(2.0)
    s.hold(0.2, jump=True); s.idle(2.0)
    s.hold(0.4, jump=True); s.idle(2.5)
    return s


def preset_run() -> ActionScript:
    s = ActionScript(seed=0x5006)
    s.idle(2.0)
    s.hold(1.0, right=True); s.idle(1.5)
    s.hold(1.0, left=True);  s.idle(1.5)
    s.hold(1.0, right=True); s.idle(1.5)
    s.hold(1.0, left=True);  s.idle(1.5)
    return s


def preset_dash_tap() -> ActionScript:
    s = ActionScript(seed=0x5007)
    s.idle(2.0)
    s.hold(0.04, dash=True); s.idle(1.0)
    s.hold(0.04, dash=True); s.idle(1.0)
    s.hold(0.04, left=True, dash=True); s.idle(1.0)
    s.hold(0.04, right=True, dash=True); s.idle(1.0)
    return s


def preset_dash_sprint() -> ActionScript:
    s = ActionScript(seed=0x5008)
    s.idle(2.0)
    s.hold(1.0, dash=True, right=True); s.idle(1.5)
    s.hold(1.0, dash=True, left=True);  s.idle(1.5)
    return s


def preset_jump_sprint() -> ActionScript:
    s = ActionScript(seed=0x5009)
    s.idle(2.0)
    s.hold(0.8, right=True, dash=True)
    s.hold(0.3, right=True, dash=True, jump=True)
    s.hold(0.5, right=True, dash=True)
    s.idle(1.5)
    s.hold(0.3, jump=True)
    s.idle(0.2)
    s.hold(0.3, jump=True)
    s.idle(2.0)
    return s


PRESETS = {
    "1_jumps":        preset_jumps,
    "2_run":          preset_run,
    "3_dash_tap":     preset_dash_tap,
    "4_dash_sprint":  preset_dash_sprint,
    "5_jump_sprint":  preset_jump_sprint,
}


def main() -> int:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("replays")
    out_dir.mkdir(parents=True, exist_ok=True)

    for name, builder in PRESETS.items():
        path = out_dir / f"{name}.skrp"
        n = builder().write(path)
        print(f"  wrote {path}  ({n} ticks = {n * 0.02:.1f}s)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
