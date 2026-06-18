# Hero Controller Constants — Ground-Truth Dump

**Source**: `Hero_Hornet.prefab` in `heroloading_assets_all.bundle`
Extracted via UnityPy typetree deserialization of the HeroController MonoBehaviour
on the root Hero_Hornet GameObject.

**Game version**: Unity 6000.0.50f1 (Hollow Knight: Silksong)
**Date**: 2026-04-30

---

## Primary Target Constants

| Constant | Ground Truth | Type | Our Sim Value | Delta |
|----------|-------------|------|---------------|-------|
| **INVUL_TIME** | **1.0 s** (= 50 frames @ 50Hz) | float | 25 frames (0.5 s) | **2x too low** |
| **INVUL_TIME_PARRY** | **0.15 s** (= 7.5 frames) | float | — | N/A |
| **RECOIL_HOR_VELOCITY** | **3.75** | float | — | — |
| **RECOIL_HOR_STEPS** | **8** (fixed-update ticks) | int | — | — |
| **RECOIL_DURATION** | **0.2 s** (= 10 frames) | float | — | — |
| **RECOIL_VELOCITY** | **15.0** | float | (guessed 15.0) | exact match |

### INVUL_TIME Details

- `INVUL_TIME = 1.0` seconds — hero invulnerability after taking damage.
  Used in `StartRecoil()`: `StartInvulnerable(INVUL_TIME)` (may be modified
  by Weighted Anklet tool: `INVUL_TIME * WeightedAnkletDmgInvulnMult`).
- `INVUL_TIME * 2 + 0.3 = 2.3s` used for hazard respawn invuln.
- Our sim has `iFrameAfterHitFrames = 25` (0.5s). The correct value is **50 frames**.

### Recoil Details

- **Damage recoil** (vertical knockback): `RECOIL_VELOCITY = 15.0`, with
  `RECOIL_DURATION = 0.2s` controlling how long the recoil state lasts.
  Recoil vector = `(+/-RECOIL_VELOCITY, RECOIL_VELOCITY * 0.5)` depending on
  hit side. Gravity is disabled during recoil.
- **Horizontal recoil** (attack knockback on enemies): `RECOIL_HOR_VELOCITY = 3.75`,
  applied for `RECOIL_HOR_STEPS = 8` fixed-update ticks.
- `RECOIL_HOR_VELOCITY_LONG = 16.0` (used for heavy/long attacks)
- `RECOIL_HOR_VELOCITY_DRILLDASH = 10.0`
- `RECOIL_DOWN_VELOCITY = 0.0` (no downward recoil)

---

## All INVUL Constants

| Constant | Value (seconds) | Frames @50Hz |
|----------|----------------|-------------|
| INVUL_TIME | 1.0 | 50 |
| INVUL_TIME_PARRY | 0.15 | 7-8 |
| INVUL_TIME_QUAKE | 0.4 | 20 |
| INVUL_TIME_CROSS_STITCH | 0.35 | 17-18 |
| INVUL_TIME_SILKDASH | 0.5 | 25 |

---

## All RECOIL Constants

| Constant | Value | Type |
|----------|-------|------|
| RECOIL_HOR_VELOCITY | 3.75 | float (units/tick) |
| RECOIL_HOR_VELOCITY_LONG | 16.0 | float |
| RECOIL_HOR_VELOCITY_DRILLDASH | 10.0 | float |
| RECOIL_HOR_STEPS | 8 | int (ticks) |
| RECOIL_DOWN_VELOCITY | 0.0 | float |
| RECOIL_DURATION | 0.2 | float (seconds) |
| RECOIL_VELOCITY | 15.0 | float (units/s) |
| CAST_RECOIL_VELOCITY | 10.0 | float |

---

## Damage Freeze Constants

| Constant | Value |
|----------|-------|
| DAMAGE_FREEZE_DOWN | 0.0 |
| DAMAGE_FREEZE_WAIT | 0.1 s |
| DAMAGE_FREEZE_UP | 0.1 s |
| DAMAGE_FREEZE_SPEED | 0.0 |

---

## Boss Phase HP Thresholds

**Source**: `scripts/lace_control_fsm.json` — Init state actions.

The FSM calls `GetHP` (reads boss max HP = 800) then multiplies:

| Phase | Fraction | HP Threshold | Our Sim | Correct? |
|-------|----------|-------------|---------|----------|
| P2 | 0.75 | **600** | 600 | YES |
| P3 | 0.55 | **440** | 450 | **NO** (off by 10) |
| P4 | 0.30 | **240** | 320 | **NO** (off by 80!) |

### P3 Trigger Mechanism

P3 is NOT checked inline in the Attack Choice state (unlike P2/P4).
The `TO P3` event is sent externally when HP <= P3 HP (440). It leads
to `Stop` -> `Mid Cocoon Break` -> eventually `P3 Dive Out` -> `P3 Roar`
-> `P3 Start` -> `P3 Roar End`. P3 primarily adds roar/wave mechanics,
same attack pool as P2.

### P4 Threshold Critical Fix

Our sim has `bossP4HP = 320`, but the real value is **240** (= 800 * 0.30).
This means our agent is seeing P4 attacks (Cross Slash, Abyss Wave) 80 HP
too early, which significantly affects training.

---

## Additional Movement Constants (for cross-reference)

| Constant | Value |
|----------|-------|
| RUN_SPEED | 8.25 |
| WALK_SPEED | 5.0 |
| JUMP_SPEED | 18.6 |
| MIN_JUMP_SPEED | 3.0 |
| JUMP_STEPS | 8 |
| DASH_SPEED | 28.0 |
| DASH_TIME | 0.1 s |
| AIR_DASH_TIME | 0.02 s |
| DOWN_DASH_TIME | 0.25 s |
| DASH_COOLDOWN | 0.425 s |
| DEFAULT_GRAVITY | 1.0 (gravity scale) |
| MAX_FALL_VELOCITY | 30.0 |
| MAX_FALL_VELOCITY_DJUMP | 10.0 |
| DOWNSPIKE_INVULNERABILITY_STEPS | 8 |
| DOWNSPIKE_INVULNERABILITY_STEPS_LONG | 16 |
| BOUNCE_VELOCITY | 12.0 |
| SHROOM_BOUNCE_VELOCITY | 25.0 |
| QUICKENING_DURATION | 10.0 s |
| QUICKENING_RUN_SPEED | 11.5 |
| QUICKENING_WALK_SPEED | 7.0 |
| REVENGE_WINDOW_TIME | 0.15 s |
| DASHCOMBO_WINDOW_TIME | 0.15 s |
| FIRST_SILK_REGEN_DELAY | 0.65 s |
| FIRST_SILK_REGEN_DURATION | 0.8 s |
| SILK_REGEN_DELAY | 2.0 s |
| SILK_REGEN_DURATION | 1.9 s |
