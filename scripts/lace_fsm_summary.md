# Lace Boss "Control" FSM — Complete Reference

Extracted from `scenes_scenes_scenes` bundle, path_id=13742.
206 states, 50 events, 86 variables, 4 global transitions.

---

## Phase Structure

Lace has **4 phases**, controlled by boolean variables and HP-threshold checks:

| Phase | Variable | HP Variable | Attack Pool |
|-------|----------|-------------|-------------|
| 1 (default) | — | — | COMBO, CHARGE, J SLASH, TENDRIL |
| 2 | `Phase 2` | `P2 HP` | + VOMIT, BULLET SUMMON, TENDRIL SUMMON |
| 3 | `Phase 3` | `P3 HP` | Same as P2 (adds roar/wave mechanics) |
| 4 | `Phase 4` | `P4 HP` | + CROSS SLASH (weight=0), ABYSS WAVE |

Phase shifts are triggered in **Attack Choice** via `CompareHPBool`:
- HP <= `P2 HP` -> `TO P2` event -> `P2 Shift 1` -> `P2 Shift 2` (sets `Phase 2=true`, `Idle Time=0.5`)
- HP <= `P4 HP` -> `TO P4` event -> `P4 Shift 1` -> `P4 Shift 2`
- P3 is triggered separately via `P3 Roar` -> `P3 Start`

---

## Core Loop

```
Init -> Dormant -> Start -> Intro Antic -> Intro Roar -> Start Pause -> Idle

Idle:
  - Waits for $Idle Time (default 0.7s, becomes 0.5s after P2)
  - Checks distance to hero (counter range < 6, far attack > 20)
  - Checks hero performance region (radius 8, react delay 0.2-0.3s)
  - Transitions:
    ATTACK (after idle timer) -> Attack Choice
    TOOK DAMAGE              -> Attack Choice
    COUNTER                  -> Counter Antic (if in range and counter ready)
    EVADE                    -> Evade Type (if hero attacking and in evade range)

Attack Choice:
  - Checks HP for phase shifts (TO P2, TO P4)
  - Checks Abyss Wave Countdown <= 1 for ABYSS WAVE
  - Then rolls SendRandomEventV4 (phase-dependent pool, see below)
  -> Selected attack "Set" state

"Set" states:
  - Configure distance/movement requirements
  -> Movement Check

Movement Check:
  - Checks if already in range ($Distance Min to $Distance Max)
  - If in range -> To Attack -> execute the attack
  - If too close -> Hop or Evade? (dodge back)
  - If too far or forced -> Tele (dive underground and emerge near hero)
  - Random choice between TELE and HOP if out of range

After attack completes:
  -> Will Counter? -> (50/50 random) -> Idle or Counter
  -> Idle
```

---

## Attack Selection Weights (SendRandomEventV4)

### Phase 1 (default)
| Attack | Weight | EventMax | MissedMax |
|--------|--------|----------|-----------|
| COMBO | 1.0 | 2 | 4 |
| CHARGE | 1.0 | 2 | 4 |
| J SLASH | 1.0 | 2 | 4 |
| TENDRIL | 1.0 | 2 | 4 |

### Phase 2 (activeBool = $Phase 2)
| Attack | Weight | EventMax | MissedMax |
|--------|--------|----------|-----------|
| COMBO | 1.0 | 2 | 7 |
| CHARGE | 1.0 | 2 | 7 |
| J SLASH | 1.0 | 2 | 7 |
| TENDRIL | 1.0 | 2 | 7 |
| VOMIT | 1.0 | 2 | 7 |
| BULLET SUMMON | 1.0 | 1 | 7 |
| TENDRIL SUMMON | 1.0 | 1 | 7 |

### Phase 4 (activeBool = $Phase 4)
| Attack | Weight | EventMax | MissedMax |
|--------|--------|----------|-----------|
| COMBO | 1.0 | 2 | 8 |
| CHARGE | 1.0 | 2 | 8 |
| J SLASH | 1.0 | 2 | 8 |
| TENDRIL | 1.0 | 2 | 8 |
| VOMIT | 1.0 | 2 | 8 |
| BULLET SUMMON | 1.0 | 1 | 8 |
| TENDRIL SUMMON | 1.0 | 1 | 8 |
| CROSS SLASH | 0.0 | 1 | 4 |

**Note:** SendRandomEventV4 uses eventMax (max consecutive picks of that event) and missedMax (max times skipped before forced pick). Phase 4 adds CROSS SLASH with weight=0 (never randomly selected, likely only forced via `Caught Hornet` flag).

---

## States by Attack Category

### Combo Slash (12 states)
Core melee combo. ComboSlash 1-7 are individual slash animations.
```
Set Combo Slash -> Movement Check -> To Attack
  -> ComboSlash 1 -> ComboSlash 2 (speed=$Combo Slash Speed=40) -> ComboSlash 3
  -> ComboSlash 4 (speed=$Combo Slash Speed=40) -> ComboSlash 5 -> ComboSlash 6
  -> ComboSlash 7 -> Will Counter? -> Idle

Combo Interrupt? (at ComboSlash 5/6):
  - If hero distance > 15: CANCEL (abort combo)
  - If hero distance > 9: CANCEL
  - 25% chance: TENDRIL (interrupt into tendril attack)
  - 75% chance: continue combo
```

**Combo Strike (multihit variant):**
```
Combo Strike 1 -> Combo Strike 2 -> Combo Strike Finisher
  On MULTI HIT CONNECT -> Combo Strike (wait $Double Strike Pause, then FINISHED)
```

### Charge (7 states)
Fast horizontal dash attack.
```
Set Charge -> Charge Antic (speed=-32 backward, wait 0.2s)
  -> Charge (speed=70 forward, wait=$Charge Time=0.25s default)
  -> Charge Crossup? (checks distance: <18 -> re-CHARGE, >=18 -> Charge Recover)
  -> Charge Recover -> Will Counter? -> Idle

On wall/edge: Charge Break (stop, wait 0.5s)
On MULTI HIT CONNECT during charge: Charge Strike -> (wait $Double Strike Pause)
Charges Performed counter tracks repeat charges.
```

### J Slash / Rising Slash (6 states)
Jumping slash attack.
```
Set J Slash -> (50/50 air vs ground):
  Air: J Slash M Antic (wait 0.6s) -> J Slash Multi (speed=60x, 60y diagonal launch)
  Ground: same path

On MULTI HIT CONNECT: J Slash Strike
On WALL: Wallcling (speed=30 into wall) -> Sing/Conduct sequence
```

**J Slash Followup** (after landing):
- If distance > 15: FINISHED (return to idle)
- 75% continue, 25% TENDRIL follow-up

### Counter (8 states)
Parry/counter-attack stance.
```
Counter Antic -> Counter Stance (invincible, wait 0.5s)
  BLOCKED HIT -> Counter Hit (triggered when hero attacks during stance)
  END (timer expires) -> Counter End -> Idle

Counter Type (after teleport): 50/50 ground vs air counter
  GROUND -> Counter Antic (normal)
  AIR -> RapidSlashAir Antic -> RapidSlash Air
```

**Counter TeleOut/TeleIn:** Lace can teleport before counter-attacking.

### RapidSlash (5 states)
Rapid multi-hit slashing.
```
RapidSlash Charge (speed=30 forward) -> RapidSlash Loop (wait 0.65s) -> RapidSlash End

Air variant:
  RapidSlashAir Antic -> RapidSlash Air (speed=35x, -22.5y, wait 0.65s)
  -> Bounce Back (speed=-10x, 15y)
```

### Downstab (7 states)
Aerial downward stab.
```
Downstab Antic -> Downstab (velY check: LAND when velY <= 0)
  -> Downstab Land -> DStab IntoDive? (50/50: continue or dive out)

On MULTI HIT CONNECT: Dstab Strike (wait $Double Strike Pause)
Dstab Angle: diagonal variant
```

### Evade/Hop (11 states)
Repositioning moves.
```
Evade: speed=-28 (backward dodge)
  -> Evade Recover (stop) -> Idle

Hop: speed=36 (forward hop toward hero)
  Cancel if distance < 6
  -> Hop Recover -> Idle

Hop Up: vertical hop for aerial positioning
  -> Hop Up Antic -> Hop Up

Hop or Evade? (decision):
  If distance < $Distance Min: EVADE (too close)
  Otherwise: random HOP/TELE
```

### Stun (8 states)
Triggered globally via STUN event.
```
Stun Start (speed=-8x, 24y — knockback arc)
  -> Stun Air -> Stun Land (on ground) -> Stunned
  -> Stunned (timer=$Stun Timer, counts down)
  TOOK DAMAGE -> Stun Damage (extends stun)
  END (timer expires) -> Stun Recover -> Stun Recover Pause (0.75s) -> Idle
```

### Multihit (6 states)
Triggered on MULTI HIT CONNECT global event during various attacks.
```
Multihitting (stop velocity, wait 0.75s) -> Multihit Slash -> Multihit Slash End
Multihitting 2 (variant) -> Multihit Slash 2
```

### Teleport/Dive (20 states)
Lace dives underground and emerges at a new position.
```
Dive In 1 -> Dive In 2 -> Tele Init (setKinematic, hide mesh, wait 0.15s)
  -> Tele Pos (calculate target position):
    - X clamped to [Tele X Min=6, Tele X Max=51]
    - Must be within arena bounds [Tele Arena Min, Tele Arena Max]
    - Must be > 5 units from hero
    - Must be > $Self Distance Check from self
    - Retries up to limit on failure
  -> Emerge Type:
    If Tele Y <= Land Y: Dive Out G (ground emerge)
    If Tele Y > Land Y: Dive Out A (air emerge)

Splash In: water/pool entry (wait $Wait Time)
Cancel Tele: abort teleport
Force Tele Out: forced disappear
```

### Quick Slash (4 states)
Fast slash attacks, likely part of combo chains.
```
Quick Slash 1 -> Quick Slash 2 -> Quick Slash 3 -> Quick Slash 4
```

### Tendril (16 states)
Silk thread whip attacks — ground and air variants.
```
Set Tendril -> (50/50 AIR vs GROUND):

Ground:
  Tendril G Antic -> Tendril G Dash (speed=20 forward)
    -> Tendril G Whip (activate damager, wait 0.6s)
    -> Tendril G Whip End

Air:
  Set Air Tendril -> Tendril Type -> Tendril A Antic (stop)
    -> Tendril A Whip (wait 0.6s) -> Tendril A End

Tendril Emerge: tendrils from ground (wait 1.5s)
  Extra Tendril Loop: repeating tendril spawns

Tendril Cooldown tracked via $Tendril Cooldown variable.
```

### Tendril Summon (via Set Tendril Summon)
```
Set Tendril Summon -> (cooldown check)
  -> Summon Antic -> Summon Thwip -> Summon Tendril -> Summon Loop
  -> Summon Turn (can change direction mid-summon)
```

### Vomit/Cast (13 states)
Projectile spray attack.
```
Set Vomit -> (50/50 AIR vs GROUND):

Ground:
  Vomit G -> Vomit Antic -> Vomit Start (wait 0.5s)
    -> Vomit Fire (spawns projectiles with velocity):
      Left projectile: velX = $Velocity X L, velY = $Velocity Y
      Right projectile: velX = $Velocity X R, velY = $Velocity Y
      Each repeat: X += 6.5 outward, Y += 2.0 upward
      Wait 0.1s between volleys
    -> Vomit Repeat? -> (loop or) Vomit End -> Vomit Cooldown (0.5s)

Air:
  Vomit Air -> Cast To Air -> Vomit To Drop
```

### Bullet Summon (7 states)
```
Set Bullets -> (50/50 AIR vs GROUND):
  Bullet S Ground 1 / Bullet S Ground 2
  Bullet S Air / Bullet S Air 2
$Shots counter tracks bullet count.
```

### Abyss Wave (11 states)
Arena-wide wave attack. Cooldown tracked by `$Abyss Wave Countdown` (decremented each Idle, triggers at <= 1).
```
Set Abyss Wave -> Abyss Wave Start Init -> Abyss Wave Start
  -> Antic Wave (wait 2.1s or 1.1s variant)
  -> Wave Ptn (50/50 L vs R):
    Wave L: (wait 2.0s then 3.0s)
    Wave R: (wait 2.0s then 3.0s)
  -> Wave Check (wait 1.5s) -> Wave Pause (1.0s)
  -> Abyss Return -> Abyss Wave Wait (0.25s) -> Idle
```

### Cross Slash (12 states)
Special attack involving teleport and cross-shaped slash.
```
Set Cross Slash -> Thread Roar Antic -> Thread Roar (wait 0.6s)
  -> CS Tele (teleport, set velocity 0)
  -> CS Ready (stop, prepare)
  -> CS Antic (wait 0.25s) -> Do CrossSlash (wait 1.2s)
  -> CS Slam -> CS Flip Back (speed=-14x, 20y)
  -> (50/50: TELE or continue)

CS Summon (wait 0.25s) -> CS Thwip Out (wait 1.8s)
```

Triggered by `Caught Hornet` bool via global CS TELE/CS READY transitions.

### Phase Shifts (9 states)
```
To P2 Shift -> P2 Shift 1 (set Phase 2=true, Idle Time=0.5) -> P2 Shift 2 (wait 1.3s) -> Idle
To P4 Shift -> P4 Shift 1 -> P4 Shift 2 (wait 1.3s)

P3 Roar (roar, stun hero, wait 2.0s) -> P3 Start -> P3 Dive Out
  -> Set Roar Pos (wait 1.0s) -> P3 Roar End
```

### Sing/Conduct (6 states)
Initiated when Lace clings to a wall after J Slash.
```
Sing Antic -> Sing -> Sing End
```

### Intro/Death (5 states)
```
Intro: Dormant -> Start -> Intro Antic -> Intro Roar (wait 3.0s)
       Intro Dive 1 -> Intro Dive 2

Death: Death Pose (checks distance < 2, might evade)
       Silk Scream (wait 4.0s) -> Silk Fall (wait 1.5s)
```

---

## Key Variables

### Timing
| Variable | Default | Description |
|----------|---------|-------------|
| Idle Time | 0.7 | Time in idle before attacking (reduced to 0.5 at P2) |
| Charge Time | 0.25 | Duration of charge dash (variable) |
| Counter Pause | 0.15 | Delay before counter becomes active |
| Double Strike Pause | 0.0 | Delay between multihit strikes |
| Stun Timer | 0.0 | Remaining stun duration |
| Wait Time | 0.0 | Generic wait (used in Splash In) |
| Tendril Cooldown | 0.0 | Cooldown between tendril attacks |

### Distance/Position
| Variable | Default | Description |
|----------|---------|-------------|
| Distance | 0.0 | Current distance to hero |
| Distance Min | 0.0 | Minimum attack range |
| Distance Max | 0.0 | Maximum attack range |
| Distance Fail Max | 0.0 | If too far after move, repick attack |
| Hop Stop Distance | 0.0 | Distance at which hop stops |
| Tele X Min | 6.0 | Min X for teleport destination |
| Tele X Max | 51.0 | Max X for teleport destination |
| Tele Arena Min | 0.0 | Arena left bound |
| Tele Arena Max | 9999999.0 | Arena right bound |
| Land Y | 6.4 | Ground Y level |
| Wallcling Min Y | 99.0 | Minimum Y for wall cling |
| Dive In Splash Y | 7.5 | Y threshold for splash entrance |

### Combat State
| Variable | Default | Description |
|----------|---------|-------------|
| Phase | 1 | Current phase (int) |
| Combo Slash Speed | 40.0 | Speed during combo slash movement |
| Gravity | 2.0 | Boss gravity scale |
| Recoil Default | 12.0 | Normal recoil on hit |
| Recoil Reduced | 5.0 | Reduced recoil during certain states |
| Hops | 0 | Hop counter |
| Charges Performed | 0 | Number of charges in current sequence |
| Shots | 0 | Bullet count |
| Abyss Wave Countdown | 2 | Decrements each idle; triggers at <= 1 |

### Boolean Flags
| Variable | Default | Description |
|----------|---------|-------------|
| Phase 2 | false | Phase 2 active |
| Phase 3 | false | Phase 3 active |
| Phase 4 | false | Phase 4 active |
| Can Evade | false | Set true after 0.05s in idle |
| Can Hop Up | false | Can perform hop up |
| Can Tendril Emerge | false | Tendrils can emerge from ground |
| Counter Range | false | Hero within counter distance (<6) |
| Counter Ready | false | Set true after $Counter Pause delay |
| Will Counter | false | Whether to counter after attack |
| In Range | false | Hero within attack range |
| In Evade Range | false | Hero in evade reaction range |
| Force Tele | false | Force teleport on next move |
| Prefer Hop | false | Prefer hop over tele |
| Caught Hornet | false | Cross slash trigger flag |
| Did Thread Roar | false | Has performed thread roar |
| Diving In | false | Currently diving underground |
| Splashed In | false | Entered via splash |
| Do Pose | false | Should perform pose after action |
| Hornet Dead | false | Fight over flag |
| Evade Flipper | false | Alternates evade direction |
| Abyss Wave Ready | false | Wave attack ready |
| Prevent Black Thread | false | Block certain thread attacks |
| Under HP Check | false | Temp bool for HP comparison result |
| Wave Left | false | Wave direction flag |
| Abyss Intro | false | Has done abyss intro |
| Close To Ground | false | Near ground check |

---

## Global Transitions (always active)

| Event | Target State |
|-------|-------------|
| STUN | Stun Start |
| CS TELE | CS Tele |
| CS READY | CS Ready |
| STOP | Stop |

---

## Key Timing Summary

| State | Wait Duration | Effect |
|-------|---------------|--------|
| Idle | $Idle Time (0.7s / 0.5s P2+) | Time between attacks |
| Charge Antic | 0.2s | Windup before charge |
| Charge | $Charge Time (0.25s) | Charge dash duration |
| Counter Stance | 0.5s | Counter window |
| RapidSlash Loop | 0.65s | Rapid slash duration |
| RapidSlash Air | 0.65s | Air rapid slash duration |
| J Slash M Antic | 0.6s | Rising slash windup |
| Multihitting | 0.75s | Multihit recovery |
| Tendril G/A Whip | 0.6s | Tendril whip duration |
| Vomit Start | 0.5s | Vomit charge |
| Vomit Fire | 0.1s per volley | Projectile interval |
| Thread Roar | 0.6s | Roar before cross slash |
| Do CrossSlash | 1.2s | Cross slash execution |
| P2/P4 Shift 2 | 1.3s | Phase transition animation |
| P3 Roar | 2.0s | Phase 3 roar duration |
| Abyss Wave Wait | 0.25s | Between wave hits |
| Antic Wave | 2.1s / 1.1s | Wave telegraph |
| Wave L/R | 2.0s + 3.0s | Wave active duration |
| Stun Recover Pause | 0.75s | Post-stun recovery |
| CS Thwip Out | 1.8s | Cross slash thread duration |

---

## Velocity Reference

| State | Speed X | Speed Y | Notes |
|-------|---------|---------|-------|
| Charge Antic | -32 (scaled) | 0 | Backward wind-up |
| Charge | 70 (scaled) | 0 | Forward dash |
| Evade | -28 (scaled) | 0 | Backward dodge |
| Hop | 36 (scaled) | 0 | Forward hop |
| ComboSlash 2/4/6 | $Combo Slash Speed=40 | 0 | Combo lunge |
| RapidSlash Charge | 30 (scaled) | 0 | Rush in |
| RapidSlash Air | 35 (scaled) | -22.5 | Diagonal air slash |
| J Slash Multi | 60 (scaled) | 60 | Diagonal launch |
| Stun Start | -8 (scaled) | 24 | Knockback arc |
| Bounce Back | -10 (scaled) | 15 | Post-air-slash bounce |
| Tendril G Dash | 20 (scaled) | 0 | Ground tendril rush |
| CS Flip Back | -14 (scaled) | 20 | After cross slash |
| Wallcling | 30 (scaled) | 0 | Into wall |
| Vomit G launch | 0 | 15 | Jump for air vomit |

"Scaled" velocities use `SetVelocityByScale` which multiplies by facing direction (+1 or -1).

---

## Evade/Counter Reaction Logic (Idle state)

Lace reacts to the hero while idling:

1. **Counter reaction** (if hero attacks):
   - `GetDistance` -> store in `$Distance`
   - `FloatTestToBool`: if distance < 6.0, set `$Counter Range = true`
   - `SetBoolValueAtTime`: after `$Counter Pause` (0.15s), set `$Counter Ready = true`
   - `BoolAllTrue` [Counter Range, Counter Ready] -> COUNTER event

2. **Evade reaction** (if hero is attacking, checked via `CheckHeroPerformanceRegionV2`):
   - Radius 8, react delay 0.2-0.3s, responds to SING (hero performance)
   - `CheckAlertRangeByName` -> `$In Evade Range`
   - `SetBoolValueAtTime`: after 0.05s, `$Can Evade = true`
   - `BoolAllTrue` [In Evade Range, Can Evade, Evade Flipper] -> EVADE
   - `BoolAllTrue` [In Evade Range, Can Evade, !Evade Flipper] -> EVADE (alternate)

3. **Force attack at range** (anti-camping):
   - `GetXDistance` -> `$Distance`
   - `FloatCompare`: if distance > 20 -> ATTACK (force attack)
