# Lace Boss State Graph

> **Status: REFERENCE — consult during Phase 7 (Lace FSM port) implementation.**
>
> This is the complete observed Lace state graph: the 71 animation states, the
> state groupings, phase-transition thresholds (P2 Shift @ 600 HP, P3 Roar @
> 320 HP), and the player animation enum. Port target for Phase 7. Kept
> verbatim.

This document is extracted from `plugin/Source/Managers/BossStateManager.cs` and `plugin/Source/Managers/SharedMemoryManager.cs`. It covers the complete boss state machine as observed by the plugin, the phase transition logic, and the full player animation state enum.

---

## Overview

Lace's state is observed through two parallel channels:

1. **PlayMakerFSM** (`ActiveStateName`) — the behavior FSM driving decisions and transitions. Phase detection uses FSM state names ("P2 Shift…", "P3 Roar…").
2. **tk2dSpriteAnimator** (`CurrentClip.name`) — the animation clip playing at render time. The `AnimationMap` dictionary translates clip names to the `BossAnimationState` enum exposed in shared memory.

The two channels are independent. The FSM can be in a state whose animation clip is mapped to `Unknown` (e.g. during transition, NPC, or death animations).

---

## BossAnimationState Enum — All 71 Values

Values 0–69 are named states; value 70 is `Unknown`.

| Value | Enum Name | Clip Name (AnimationMap key) | Group | Notes |
|-------|-----------|------------------------------|-------|-------|
| 0 | `Idle` | "Idle" | Neutral | Default stance |
| 1 | `ComboSlash` | "Combo Slash" | Combo Slashes | Multi-hit close-range combo |
| 2 | `Antic` | "Antic" | Combo Slashes | Generic windup before a slash |
| 3 | `RisingSlash` | "Rising Slash" | Combo Slashes | Upward slash variant |
| 4 | `ChargeAntic` | "Charge Antic" | Charges | Windup before charge |
| 5 | `RapidSlashCharge` | "RapidSlash Charge" | Rapid Slashes | Charge into rapid-slash sequence |
| 6 | `CounterStance` | "Counter Stance" | Counters | Parry-ready stance |
| 7 | `Evade` | "Evade" | Evasion | Evasive maneuver |
| 8 | `ForwardHop` | "Forward Hop" | Movement | Short hop toward player |
| 9 | `Stun` | "Stun" | Stun | Staggered/stunned on ground |
| 10 | `Charge` | "Charge" | Charges | Active charge movement |
| 11 | `ChargeRecover` | "Charge Recover" | Charges | Recovery after charge ends |
| 12 | `DownstabAntic` | "Downstab Antic" | Downstabs | Windup for downstab |
| 13 | `Downstab` | "Downstab" | Downstabs | Active downward stab |
| 14 | `DownstabEnd` | "Downstab End" | Downstabs | Recovery after downstab |
| 15 | `CounterAntic` | "Counter Antic" | Counters | Windup for counter attack |
| 16 | `CounterEnd` | "Counter End" | Counters | Recovery after counter |
| 17 | `CounterHit` | "Counter Hit" | Counters | Counter connects with player |
| 18 | `RapidSlashEnd` | "RapidSlash End" | Rapid Slashes | Recovery after rapid slashes |
| 19 | `RapidSlashLoop` | "RapidSlash Loop" | Rapid Slashes | Looping rapid-slash animation |
| 20 | `RapidSlashEffect` | "RapidSlash Effect" | Rapid Slashes | Particle/effect frame |
| 21 | `JumpAntic` | "Jump Antic" | Aerial / Downstabs | Windup before aerial jump |
| 22 | `Conduct` | "Conduct" | Conducts | Conducts/summons projectiles |
| 23 | `CrossSlashAntic` | "CrossSlash Antic" | Projectiles | Windup for cross-slash projectile |
| 24 | `ConductEnd` | "Conduct End" | Conducts | End of conduct sequence |
| 25 | `StunAir` | "Stun Air" | Stun | Staggered mid-air |
| 26 | `StunRecover` | "Stun Recover" | Stun | Recovery from stun |
| 27 | `JumpAnticQ` | "Jump AnticQ" | Aerial / Downstabs | Quick variant of jump antic |
| 28 | `JumpAway` | "Jump Away" | Movement | Retreat jump |
| 29 | `MultiHitSlash` | "MultiHit Slash" | Combo Slashes | Multi-hit ground slash |
| 30 | `DashBurst` | "Dash Burst" | Charges | Burst at end of dash |
| 31 | `AirDashBurst` | "AirDash Burst" | Charges | Aerial dash burst |
| 32 | `StunHit` | "Stun Hit" | Stun | Hit during stun |
| 33 | `TrapStun` | "Trap Stun" | Stun | Environmental stun |
| 34 | `SwishBlock` | "Swish Block" | Counters | Short parry/block |
| 35 | `ComboSlashQ` | "Combo Slash Q" | Combo Slashes | Quick combo variant |
| 36 | `DownstabAnticQ` | "Downstab Antic Q" | Downstabs | Quick downstab windup |
| 37 | `BombSlashAntic` | "Bomb Slash Antic" | Projectiles | Windup for bomb-slash |
| 38 | `BombSlash` | "Bomb Slash" | Projectiles | Active bomb-slash (spawns explosive) |
| 39 | `ComboSlashTriple` | "Combo Slash Triple" | Combo Slashes | Three-hit combo variant |
| 40 | `P2ShiftOld` | "P2 Shift Old" | Phase Transitions | Legacy P2 transition animation |
| 41 | `ChargeMultiAntic` | "ChargeMulti Antic" | Charges | Windup for multi-charge |
| 42 | `ChargeMulti` | "ChargeMulti" | Charges | Active multi-charge sequence |
| 43 | `ChargeMultiRecover` | "ChargeMulti Recover" | Charges | Recovery after multi-charge |
| 44 | `RisingSlashMulti` | "Rising Slash Multi" | Combo Slashes | Multi-hit rising slash |
| 45 | `TeleIn` | "Tele In" | Teleports | Materialize after teleport |
| 46 | `TeleOut` | "Tele Out" | Teleports | Dematerialize before teleport |
| 47 | `WallBounce` | "Wall Bounce" | Movement | Bounce off arena wall |
| 48 | `ChargeCrossup` | "Charge Crossup" | Charges | Charge that crosses through player |
| 49 | `QuickSlash` | "Quick Slash" | Combo Slashes | Single fast slash |
| 50 | `RapidSlashAirTeleIn` | "RapidSlashAir TeleIn" | Rapid Slashes / Teleports | Teleport in to begin aerial rapid slashes |
| 51 | `RapidSlashAir` | "RapidSlashAir" | Rapid Slashes | Aerial rapid-slash loop |
| 52 | `RapidSlashAirEnd` | "RapidSlashAir End" | Rapid Slashes | End of aerial rapid slashes |
| 53 | `TeleOutFast` | "Tele Out Fast" | Teleports | Fast/short teleport out |
| 54 | `CounterAnticFast` | "Counter Antic Fast" | Counters | Fast counter windup variant |
| 55 | `MultiHitSlashAir` | "MultiHit Slash Air" | Combo Slashes | Aerial multi-hit slash |
| 56 | `MultihitAirEnd` | "Multihit AirEnd" | Combo Slashes | Recovery after aerial multi-hit |
| 57 | `P2Shift` | "P2 Shift" | Phase Transitions | Phase 1→2 transition |
| 58 | `CounterFlash` | "Counter Flash" | Counters | Flash frame during counter |
| 59 | `RapidSlashAirEndQ` | "RapidSlashAir End Q" | Rapid Slashes | Quick end variant of aerial rapids |
| 60 | `SwishBlockLong` | "Swish Block Long" | Counters | Extended parry/block |
| 61 | `ComboStrike1` | "Combo Strike 1" | Combo Slashes | First strike of a combo |
| 62 | `ComboStrike2` | "Combo Strike 2" | Combo Slashes | Second strike of a combo |
| 63 | `ChargeStrike` | "Charge Strike" | Charges | Strike at end of charge |
| 64 | `DownstabStrike` | "Downstab Strike" | Downstabs | Active strike frame of downstab |
| 65 | `DownstabFollowup` | "Downstab Followup" | Downstabs | Follow-up hit after downstab |
| 66 | `ForwardHopIntro` | "Forward Hop Intro" | Movement | Introductory hop variant |
| 67 | `ComboSlashLongAntic` | "Combo Slash LongAntic" | Combo Slashes | Long windup for combo slash |
| 68 | `ForwardHopSlow` | "Forward Hop Slow" | Movement | Slow hop variant |
| 69 | `TeleInFast` | "Tele In Fast" | Teleports | Fast materialize |
| 70 | `Unknown` | *(see below)* | — | Unmapped clip |

---

## States Mapped to Unknown

The following clip names exist in the game and appear in the `AnimationMap` but are mapped to `BossAnimationState.Unknown` (value 70). These require investigation during decompilation to determine their semantic role.

| Clip Name | Probable Category | Notes |
|-----------|------------------|-------|
| "TurnToIdle" | Transition | Turn-around recovery to idle |
| "Engarde" | Transition / Intro | Opening stance (seen on refight start: FSM set to "Refight Engarde") |
| "NPC Idle Right" | NPC / Cutscene | Non-combat idle facing right |
| "NPC Idle Turn Left" | NPC / Cutscene | Turn animation |
| "NPC Idle Left" | NPC / Cutscene | Non-combat idle facing left |
| "NPC Idle Turn Right" | NPC / Cutscene | Turn animation |
| "Possession" | Cutscene | Lace being possessed by foreign entity |
| "Eye Flash" | Visual Effect | Eye glow / phase signal |
| "Pose Lean" | Cutscene | Victory/taunt pose variant |
| "Pose Upright" | Cutscene | Victory/taunt pose variant |
| "Pose Swish" | Cutscene | Victory/taunt pose with weapon swish |
| "Pose Hornet Defeated" | Cutscene | Pose played when Hornet-linked enemy is defeated |
| "NPC Sit" | NPC / Cutscene | Sitting idle |
| "ConductToIdle" | Transition | Return to idle from Conduct |
| "NPC Sit Antic" | NPC / Cutscene | Transition into sit |
| "NPC SitLook" | NPC / Cutscene | Looking while sitting |
| "SitToIdle" | Transition | Rise from sit to idle |
| "Fall" | Movement | Airborne fall (no attack) |
| "Land" | Movement | Landing after fall |
| "Death 1" | Death | First death animation frame |
| "Death 2" | Death | Second death animation frame |
| "Lie" | Death | Lying on ground (dead) |
| "LieToWake" | Death / Cutscene | Rising from lying position |
| "Roar" | Phase Transition | Phase 3 entry roar — **triggers P3 detection** (FSM state "P3 Roar…") |
| "Death Stagger" | Death | Stagger before collapse |
| "Laugh" | Cutscene | Lace laughing taunt |
| "Sing" | Cutscene | Singing (Lace's musical motif) |
| "Sing End" | Cutscene | End of sing animation |
| "Mid Battle Roar" | Phase Signal | Mid-fight roar (intermediate phase signal) |
| "Death Air" | Death | Death while airborne |
| "Death Land Stun" | Death | Stunned landing after aerial death |
| "Lava Damage" | Environment | Damage from lava contact |

---

## Phase Transition Logic

Implemented in `BossStateManager.UpdateBossPhase()` (lines 170–196). Phase is tracked in the integer `currentBossPhase` (0-indexed) and exposed as `bossPhase` in shared memory.

```
Phase 0 (P1):  Initial phase. HP range: ~800 → 600.
Phase 1 (P2):  Triggers when FSM ActiveStateName.StartsWith("P2 Shift").
               FSM variable "P2 HP" = 600 (from ResetPhaseFsmVariables).
Phase 2 (P3):  Triggers when FSM ActiveStateName.StartsWith("P3 Roar").
               FSM variable "P3 HP" = 320 (from ResetPhaseFsmVariables).
```

The check is one-way and monotonic: once phase 1 is reached it can never drop back to 0, and once phase 2 is reached it can never drop back to 1. Phase is reset to 0 via `ResetBossPhase()` at the start of each episode.

The FSM variable `Phase` is reset to 1 (not 0) by `ResetPhaseFsmVariables`. This is an internal FSM counter distinct from the externally observed `currentBossPhase`.

Health thresholds inferred from FSM variables:
- P2 transition: boss HP reaches ~600 (FSM variable `P2 HP` = 600)
- P3 transition: boss HP reaches ~320 (FSM variable `P3 HP` = 320)
- Boss max HP: 800 (constant `LaceBossMaxHealth`)

---

## States Grouped by Attack Pattern

### Neutral / Idle
- `Idle` (0)

### Combo Slashes
Multi-hit melee attacks at close range.
- `Antic` (2) — generic windup
- `ComboSlash` (1)
- `ComboSlashQ` (35) — quick variant
- `ComboSlashTriple` (39) — three-hit
- `ComboSlashLongAntic` (67) — extended windup
- `ComboStrike1` (61) — first strike frame
- `ComboStrike2` (62) — second strike frame
- `MultiHitSlash` (29) — multi-hit ground
- `MultiHitSlashAir` (55) — aerial multi-hit
- `MultihitAirEnd` (56) — aerial multi-hit recovery
- `RisingSlash` (3) — upward slash
- `RisingSlashMulti` (44) — multi-hit rising slash
- `QuickSlash` (49) — single fast slash

### Charges
Boss closes distance rapidly.
- `ChargeAntic` (4)
- `Charge` (10)
- `ChargeRecover` (11)
- `DashBurst` (30) — burst at dash end
- `AirDashBurst` (31) — aerial dash burst
- `ChargeCrossup` (48) — passes through player
- `ChargeStrike` (63) — strike at charge end
- `ChargeMultiAntic` (41) — multi-charge windup
- `ChargeMulti` (42) — multi-charge active
- `ChargeMultiRecover` (43) — multi-charge recovery

### Rapid Slashes
High-frequency slash sequences.
- `RapidSlashCharge` (5) — charge into rapid slashes
- `RapidSlashLoop` (19) — looping rapid slashes
- `RapidSlashEffect` (20) — effect frame mid-rapid
- `RapidSlashEnd` (18) — ground rapid-slash end
- `RapidSlashAirTeleIn` (50) — teleport in to start aerial rapids
- `RapidSlashAir` (51) — aerial rapid-slash loop
- `RapidSlashAirEnd` (52) — aerial rapid-slash end
- `RapidSlashAirEndQ` (59) — quick aerial rapid-slash end

### Downstabs
Plunging attacks aimed at the player.
- `JumpAntic` (21) — windup before jump
- `JumpAnticQ` (27) — quick windup
- `DownstabAntic` (12)
- `DownstabAnticQ` (36) — quick variant
- `Downstab` (13)
- `DownstabStrike` (64) — active strike frame
- `DownstabFollowup` (65) — follow-up hit
- `DownstabEnd` (14) — recovery

### Counters / Parries
Reactive attacks that trigger when the player attacks.
- `CounterStance` (6) — parry-ready idle
- `CounterAntic` (15) — counter windup
- `CounterAnticFast` (54) — fast counter windup
- `CounterFlash` (58) — flash frame on counter
- `CounterHit` (17) — counter connects
- `CounterEnd` (16) — recovery
- `SwishBlock` (34) — short parry
- `SwishBlockLong` (60) — extended parry

### Conducts (Projectile Summons)
Lace "conducts" to call projectile attacks.
- `Conduct` (22) — active conduct / summoning
- `ConductEnd` (24) — end of conduct

### Projectile-Spawning States (by name pattern)
These states are strongly implied to spawn projectiles based on their names and the projectile-tracking code in `BossProjectileManager.cs`:

| State | Evidence |
|-------|---------|
| `CrossSlashAntic` (23) | BossProjectileManager scans for "Cross Slash" GameObjects on FSM state change; "CrossSlash Antic" FSM state is the likely trigger |
| `BombSlashAntic` (37) | Paired with BombSlash — windup before bomb projectile |
| `BombSlash` (38) | Name directly implies a projectile (explosive slash) |
| `Conduct` (22) | "Conduct" implies musical-themed area-effect projectile(s) |
| `RapidSlashAirTeleIn` (50) | Paired with aerial rapid slashes which may spawn circle-slash projectiles tracked as "lace_circle_slash" |

The projectile tracker in `BossProjectileManager.cs` identifies two projectile types:
- **`lace_circle_slash`** — circular slash area-of-effect, tracked by child "damager" collider, radius = 3.0 units
- **`Cross Slash`** — cross-shaped slash projectile, tracked by child "hero damager" transform and its own `PlayMakerFSM`, radius = 5.0 units

### Teleports
- `TeleOut` (46) — dematerialize
- `TeleOutFast` (53) — fast dematerialize
- `TeleIn` (45) — materialize
- `TeleInFast` (69) — fast materialize
- `RapidSlashAirTeleIn` (50) — teleport-in specifically for aerial rapid slashes

### Movement / Repositioning
- `ForwardHop` (8) — hop toward player
- `ForwardHopIntro` (66) — intro hop variant
- `ForwardHopSlow` (68) — slow hop
- `JumpAway` (28) — retreat jump
- `WallBounce` (47) — bounce off wall
- `Evade` (7) — active evasive movement

### Stun
- `Stun` (9) — ground stun
- `StunAir` (25) — aerial stun
- `StunHit` (32) — hit during stun
- `StunRecover` (26) — stun recovery
- `TrapStun` (33) — environment-induced stun

### Phase Transitions
- `P2Shift` (57) — Phase 1→2 transition animation; **FSM state "P2 Shift…" triggers currentBossPhase = 1**
- `P2ShiftOld` (40) — Legacy P2 shift animation (may appear in older encounter versions)

---

## Boss FSM Variables (Reset Values)

The following variables are set in `EpisodeResetter.ResetPhaseFsmVariables()` on the FSM named "Control" on the "Lace Boss" GameObject. These reflect the internal decision variables the FSM uses.

### Boolean Variables (reset values)

| Variable | Reset Value | Probable Semantics |
|----------|-------------|-------------------|
| `Above Wallcling Min` | false | Boss is above wall-cling height |
| `Can Bomb Slash` | false | Bomb Slash available this turn |
| `Counter Range` | false | Player is in counter-trigger range |
| `Counter Ready` | false | Counter action armed |
| `CrossSlashing Hero` | false | Cross-slash is currently active on hero |
| `Did P2 Shift` | false | Phase 2 shift has occurred |
| `Did P3 Shift` | false | Phase 3 shift has occurred |
| `Do Pose` | false | Execute a cutscene pose |
| `Evade Bomb` | false | Evade in response to bomb |
| `Facing Right` | false | Boss facing right flag |
| `Floor Ahead` | true | Floor exists in the direction of travel |
| `Hero Is R` | false | Hero is to the right of boss |
| `Hero on Wall` | false | Hero is wall-clinging |
| `Hornet Dead` | false | (Lace's Hornet-themed partner) defeated |
| `Not Above Hero` | false | Boss is not above hero |
| `Right Side` | false | Boss is on right side of arena |
| `Wall Ahead` | false | Wall detected ahead |
| `Will Counter` | false | Boss will attempt a counter next |
| `Will CrossSlash` | false | Boss will launch cross-slash next |
| `In Evade Range` | false | Hero is within evade trigger range |
| `Can Evade` | false | Evade action is available |
| `Evade Floor Safe` | false | Floor is safe to evade onto |
| `Evade Flipper` | false | Evade flipper mechanic active |

### Integer Variables (reset values)

| Variable | Reset | Semantics |
|----------|-------|-----------|
| `Ct Charge` | 0 | Charge cooldown counter |
| `Ct Combo` | 1 | Combo cooldown counter |
| `Ct CrossSlash` | 0 | CrossSlash cooldown counter |
| `Ct Evade` | 0 | Evade cooldown counter |
| `Ct J Slash` | 0 | Jump-slash cooldown counter |
| `Ct Bomb Slash` | 0 | Bomb-slash cooldown counter |
| `Evade Attempts` | 0 | Number of evades attempted this phase |
| `Hops` | 2 | Remaining forward hops in current sequence |
| `Ms Charge` | 1 | Max consecutive charges |
| `Ms Combo` | 0 | Max consecutive combos |
| `Ms Evade` | 0 | Max consecutive evades |
| `Ms J Slash` | 1 | Max jump-slashes |
| `Ms Bomb Slash` | 0 | Max bomb-slashes |
| `Phase` | 1 | Internal FSM phase counter (distinct from `currentBossPhase`) |
| `P2 HP` | 600 | HP threshold that triggers P2 shift |
| `P3 HP` | 320 | HP threshold that triggers P3 roar |
| `Rage Slashes` | 2 | Number of rapid slashes in rage mode |
| `Charges Performed` | 0 | Consecutive charge count |

### Float Variables (reset values)

| Variable | Reset | Semantics |
|----------|-------|-----------|
| `Angle`, `Angle Max`, `Angle Min` | 0 | Projectile angle calculations |
| `Anim Start Time` | 0 | Animation phase timing |
| `Bomb Max X` | 66.5 | Bomb-slash spawn zone right bound |
| `Bomb Max Y` | 106 | Bomb-slash spawn zone top bound |
| `Bomb Min X` | 40.5 | Bomb-slash spawn zone left bound |
| `Bomb Min Y` | 101 | Bomb-slash spawn zone bottom bound |
| `Bomb X`, `Bomb Y` | 0 | Computed bomb target coordinates |
| `Centre X` | 54 | Arena center X coordinate |
| `Charge Time` | 0 | Duration of current charge |
| `Combo Slash Speed` | 30 | Speed during combo slash |
| `Counter Pause` | 0 | Pause duration before counter |
| `CrossSlash Antic Time` | 0 | Duration of cross-slash windup |
| `Distance` | 9.923786 | Computed hero-boss distance |
| `Double Strike Pause` | 0.2 | Pause between double-strike hits |
| `Gravity` | 2 | Boss gravity scale |
| `Hero X` | 0 | Last observed hero X position |
| `Idle Time` | 0.65 | Duration to wait in idle before next action |
| `Land Y` | 100.25 | Y position where boss lands after jump |
| `Self X` | 0 | Boss X position (self-reference) |
| `Stun Timer` | 0 | Current stun duration |
| `Target Distance` | 6 | Preferred engagement distance |
| `Tele Offset` | 0 | Offset applied to teleport target |
| `Tele Out Floor` | 95 | Minimum Y for teleport-out |
| `Tele X` | 0 | Computed teleport target X |
| `Velocity Y` | 0 | Vertical velocity during arcing attacks |
| `Wallcling Min Y` | 99 | Minimum Y for wall-cling detection |
| `X Scale` | 0 | Sprite X scale (sign = facing) |
| `Arena Plat Bot Y` | 99.5 | Arena platform bottom Y |
| `Fall Check Speed` | -6 | Downward velocity threshold for fall detection |

### String Variables (reset values)

| Variable | Reset | Semantics |
|----------|-------|-----------|
| `Cross Slash Anim` | "" | Animation clip name for cross-slash |
| `Next Event` | "COMBO" | Next action selector — defaults to COMBO on reset |
| `Anim` | "" | Currently requested animation |

---

## Player Animation States (83 States)

Defined in `PlayerAnimationState` enum in `SharedMemoryManager.cs` (lines 27–111) and mapped from clip names in `PlayerAnimationMapper.cs`.

| Value | Enum Name | Clip Name | Category |
|-------|-----------|-----------|----------|
| 0 | `Idle` | "Idle" | Ground Neutral |
| 1 | `Airborne` | "Airborne" | Aerial |
| 2 | `Land` | "Land" | Landing |
| 3 | `IdleToRun` | "Idle To Run" | Ground Movement |
| 4 | `RunToIdle` | "Run To Idle" | Ground Movement |
| 5 | `Turn` | "Turn" | Ground Movement |
| 6 | `WoundDoubleStrike` | "Wound Double Strike" | Damage Reaction |
| 7 | `Stun` | "Stun" | Damage Reaction |
| 8 | `Recoil` | "Recoil" | Damage Reaction |
| 9 | `Dash` | "Dash" | Dash |
| 10 | `Sprint` | "Sprint" | Sprint |
| 11 | `DashToIdle` | "Dash To Idle" | Dash |
| 12 | `SlashAlt` | "SlashAlt" | Attack |
| 13 | `SlashLandRunAlt` | "Slash Land Run Alt" | Attack + Movement |
| 14 | `DashAttackAntic` | "Dash Attack Antic" | Attack |
| 15 | `SlashLand` | "Slash Land" | Attack + Movement |
| 16 | `DashToRun` | "Dash To Run" | Dash |
| 17 | `UpSlash` | "UpSlash" | Attack |
| 18 | `Slash` | "Slash" | Attack |
| 19 | `DownSpikeAntic` | "DownSpike Antic" | Downstab |
| 20 | `DownSpike` | "DownSpike" | Downstab |
| 21 | `DownspikeRecovery` | "Downspike Recovery" | Downstab |
| 22 | `DownSpikeBounce2` | "DownSpikeBounce 2" | Downstab |
| 23 | `DownSpikeBounce1` | "DownSpikeBounce 1" | Downstab |
| 24 | `RecoilTwirl` | "Recoil Twirl" | Damage Reaction |
| 25 | `LandToRun` | "Land To Run" | Landing |
| 26 | `SkidEnd1` | "Skid End 1" | Ground Movement |
| 27 | `HarpoonAntic` | "Harpoon Antic" | Clawline |
| 28 | `HarpoonThrow` | "Harpoon Throw" | Clawline |
| 29 | `HarpoonDash` | "Harpoon Dash" | Clawline |
| 30 | `HarpoonCatch` | "Harpoon Catch" | Clawline |
| 31 | `SilkChargeEnd` | "Silk Charge End" | Special |
| 32 | `AirDash` | "Air Dash" | Aerial Dash |
| 33 | `SprintAir` | "Sprint Air" | Aerial Sprint |
| 34 | `SprintAirLoop` | "Sprint Air Loop" | Aerial Sprint |
| 35 | `NeedleThrowAnticG` | "NeedleThrow AnticG" | Needle/Tool |
| 36 | `NeedleThrowThrowing` | "NeedleThrow Throwing" | Needle/Tool |
| 37 | `NeedleThrowCatch` | "NeedleThrow Catch" | Needle/Tool |
| 38 | `DoubleJump` | "Double Jump" | Aerial |
| 39 | `Walljump` | "Walljump" | Wall |
| 40 | `WallSlide` | "Wall Slide" | Wall |
| 41 | `DashAttack` | "Dash Attack" | Attack |
| 42 | `DashAttackRecover` | "Dash Attack Recover" | Attack |
| 43 | `SlashToRun` | "Slash To Run" | Attack + Movement |
| 44 | `Run` | "Run" | Ground Movement |
| 45 | `SkidEnd2` | "Skid End 2" | Ground Movement |
| 46 | `SprintAirShort` | "Sprint Air Short" | Aerial Sprint |
| 47 | `MantleCling` | "Mantle Cling" | Mantle |
| 48 | `MantleVault` | "Mantle Vault" | Mantle |
| 49 | `SlashLandRun` | "Slash Land Run" | Attack + Movement |
| 50 | `Wound` | "Wound" | Damage Reaction |
| 51 | `HazardRespawn` | "Hazard Respawn" | Death/Respawn |
| 52 | `MantleLand` | "Mantle Land" | Mantle |
| 53 | `MantleLandToRun` | "Mantle Land To Run" | Mantle |
| 54 | `SprintTurn` | "Sprint Turn" | Sprint |
| 55 | `NeedleThrowAnticA` | "NeedleThrow AnticA" | Needle/Tool (aerial) |
| 56 | `UmbrellaInflateAntic` | "Umbrella Inflate Antic" | Umbrella/Float |
| 57 | `UmbrellaInflate` | "Umbrella Inflate" | Umbrella/Float |
| 58 | `UmbrellaFloat` | "Umbrella Float" | Umbrella/Float |
| 59 | `DownspikeRecoveryLand` | "Downspike Recovery Land" | Downstab |
| 60 | `DashDown` | "Dash Down" | Aerial Dash |
| 61 | `ShuttlecockAntic` | "Shuttlecock Antic" | Special |
| 62 | `Shuttlecock` | "Shuttlecock" | Special |
| 63 | `SprintBackflip` | "Sprint Backflip" | Sprint |
| 64 | `UmbrellaDeflate` | "Umbrella Deflate" | Umbrella/Float |
| 65 | `DashDownLand` | "Dash Down Land" | Aerial Dash |
| 66 | `UmbrellaTurn` | "Umbrella Turn" | Umbrella/Float |
| 67 | `MantleCancelToJump` | "Mantle Cancel To Jump" | Mantle |
| 68 | `IdleHurt` | "Idle Hurt" | Damage Reaction |
| 69 | `LookDown` | "LookDown" | Look |
| 70 | `LookDownEnd` | "LookDownEnd" | Look |
| 71 | `LookUp` | "LookUp" | Look |
| 72 | `LookUpEnd` | "LookUpEnd" | Look |
| 73 | `BindChargeGround` | "BindCharge Ground" | Bind/Special |
| 74 | `BindBurstGround` | "BindBurst Ground" | Bind/Special |
| 75 | `BindChargeAir` | "BindCharge Air" | Bind/Special |
| 76 | `BindBurstAir` | "BindBurst Air" | Bind/Special |
| 77 | `Fall` | "Fall" | Aerial |
| 78 | `WallCling` | "Wall Cling" | Wall |
| 79 | `WalljumpAntic` | "Walljump Antic" | Wall |
| 80 | `HardLand` | "HardLand" | Landing |
| 81 | `Walk` | "Walk" | Ground Movement |
| 82 | `Unknown` | *(no clip match)* | — |

Note: The enum has 83 values (0–82). The constant `NumPlayerAnimationStates = 83` in `Constants.cs` confirms this count.

---

## Arena Geometry Constants

Extracted from FSM reset values and `Constants.cs`:

| Value | Meaning |
|-------|---------|
| Hero spawn: (49.27, 100.57) | Player start position |
| Boss spawn: (59.19, 100.59) | Boss start position |
| Arena centre X: 54.0 | Midpoint of arena |
| Arena left bound (Bomb Min X): 40.5 | Left edge for bomb spawning |
| Arena right bound (Bomb Max X): 66.5 | Right edge for bomb spawning |
| Arena platform bottom Y: 99.5 | Floor of main platform |
| Land Y: 100.25 | Boss landing height after jumps |
| Tele Out Floor: 95.0 | Minimum Y for teleport-out targets |
| Wallcling Min Y: 99.0 | Minimum height for wall-cling detection |
| Bomb Y range: 101–106 | Vertical range for bomb-slash spawns |
