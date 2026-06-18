# Lace Boss1 "Control" FSM -- Complete Reference

Extracted from `scenes_scenes_scenes` bundle, bone_east_12 scene, path_id=6175.
132 states, 39 events, 46 variables, 2 global transitions.

This is the **first Lace encounter** (Bone East Docks / Needolin Grotto), simpler than the Lost Lace rematch (206 states). No phase shifts, no teleport-dive, no tendril summon, no vomit, no bullet summon, no abyss wave. The fight is grounded melee combat with a CrossSlash rage mechanic.

---

## Core Loop

```
Init -> Use Wall Range? -> Grotto Refight Setup -> Dormant
  -> Scene Start -> Location Check
    DOCKS -> Encountered? -> Take Control -> Convo chain -> Start Battle
    GROTTO -> Grotto Fight -> Take Control New -> Convo chain -> Start Battle

Start Battle -> Evade (opening dodge) -> Evade Recover -> Evade Move -> [attack]

Main loop:
  Idle (wait 0.75s)
    ATTACK / TOOK DAMAGE -> CrossSlash? -> Distance Check -> [Close or Far]
    COUNTER             -> Counter Antic
    RANGE OUT           -> Evade 2 (out-of-range evasion chain)
    SING                -> Sing Antic

  CrossSlash? (rage check):
    HP > Rage HP (50% max HP)  -> Distance Check (normal attack)
    HP <= Rage HP AND Ct CrossSlash <= 0 -> CrossSlash Aim -> CrossSlash sequence
    Decrements Ct CrossSlash each time

  Distance Check:
    Distance <= 6.0 -> Close
    Distance > 6.0  -> Far
    SING (hero performing) -> Sing Antic

  Close: SendRandomEventV3 picks EVADE / COMBO / J SLASH (equal weight 1.0)
    Each has eventMax=2, missedMax=4
    Also checks AlertRange -> if in range, can trigger J SLASH directly
    Note: J SLASH transition in Close goes to Charge Antic (name mismatch, but confirmed from data)

  Far: SendRandomEventV3 picks COMBO / CHARGE / J SLASH (equal weight 1.0)
    Each has eventMax=2 (CHARGE max=1), missedMax=4
    Resets $Hops to 0, then routes through Hop To [attack] -> Hop chain

  After attack completes:
    -> Will Counter? (33% chance counter, 67% skip) -> Pose -> Idle
```

---

## Attack Selection Weights

### Close Range (Distance <= 6.0) -- SendRandomEventV3
| Attack | Event | Weight | EventMax | MissedMax | Target |
|--------|-------|--------|----------|-----------|--------|
| Evade | EVADE | 1.0 | 2 | 4 | Evade |
| Combo | COMBO | 1.0 | 2 | 4 | ComboSlash 1 |
| J Slash | J SLASH | 1.0 | 2 | 4 | Charge Antic |

Counters: $Ct Evade, $Ct Combo, $Ct J Slash
Missed counters: $Ms Evade, $Ms Combo, $Ms J Slash

### Far Range (Distance > 6.0) -- SendRandomEventV3
| Attack | Event | Weight | EventMax | MissedMax | Target |
|--------|-------|--------|----------|-----------|--------|
| Combo | COMBO | 1.0 | 2 | 4 | Hop To Combo |
| Charge | CHARGE | 1.0 | 1 | 4 | Hop To Charge |
| J Slash | J SLASH | 1.0 | 2 | 4 | Hop To J Slash |

### After Evade -- SendRandomEvent
| Attack | Event | Weight | Target |
|--------|-------|--------|--------|
| Combo | COMBO | 1.0 | Hop To Combo |
| Charge | CHARGE | 1.0 | Charge Antic |
| J Slash | J SLASH | 1.0 | J Slash Antic |

Note: If $Will CrossSlash is true (set during CS Evade), Evade Move goes directly to CrossSlash Aim instead.

---

## States by Attack Category

### Setup/Init (5 states)
- **Init** [0]: GetHP, set Rage HP = HP * 0.5, find child objects
- **Use Wall Range?** [131]: Check player data, find wall range child, move off-screen (y=500)
- **Grotto Refight Setup** [99]: Position and scale setup for grotto variant
- **Pause** [80]: NextFrameEvent -> Init
- **Dormant** [40]: Kinematic, wait for ENTER event, respond to BLOCKED HIT

### Scene Start / Location (7 states)
- **Scene Start** [43] -> Location Check
- **Location Check** [81]: $Needolin Fight ? GROTTO : DOCKS
- **Encountered?** [41]: PlayerData check -> Take Control or Refight
- **Grotto Fight** [82]: Sets Land Y=8.54, Centre X=39.66 for grotto arena
- **Location Check 2** [117] -> Capture Hero / Capture Hero 2
- **Take Control** [42] / **Take Control New** [114]: Start cutscene FSMs

### Dialogue (14+ states)
- **Wait** [79], **Wait 2** [84], **Wait Shorter** [119], **Wait Lace Anim** [121]
- **Convo 1** [44], **Convo 2** [45], **Convo 3** [107], **Convo 4** [46]
- **End Dialogue** [48], **End Dialogue 2** [108]
- **Met in Docks?** [85], **Grotto Meet 1** [86], **Grotto Meet 2** [87], **Grotto Meet 3** [88]
- **Grotto Remeet 1** [89], **Grotto Remeet 2** [90], **Grotto Remeet 3** [91]
- **Get Up Start** [100], **Get Up Start 2** [101]
- **Conduct End** [112], **Turn To Idle** [113], **To Idle** [115]
- **Hero Turn** [120], **Capture Hero** [116], **Capture Hero 2** [118]
- **Take Control 2** [83]: Alternate take control path for grotto

### Battle Start (3 states)
- **Start Battle** [47]: Apply music cue, display boss title, set not kinematic -> Evade
- **Refight** [49]: Play voice, wait -> Start Battle
- **Grotto Refight** [102] -> Start Battle

### Idle/Decision (2 states)
- **Idle** [1]: Wait 0.75s, face hero, check counter range (<6), check performance region (radius=0, react 0.2s), check alert range
- **CrossSlash?** [57]: HP check vs $Rage HP, CrossSlash counter check

### Distance Check / Movement (2 states)
- **Distance Check** [25]: GetDistance, compare to 6.0 -> CLOSE or FAR; also checks hero sing
- **Close** [26]: Close-range attack selection
- **Far** [27]: Far-range attack selection, reset hops

### Combo Slash (5 states)
5-hit melee combo. ComboSlash 2 and 4 lunge forward.
```
ComboSlash 1 (face hero, slash anim)
  -> ComboSlash 2 (speed=30 forward, activate damager)
  -> ComboSlash 3 (stop, decel 0.8)
  -> ComboSlash 4 (speed=30 forward, activate damager)
  -> ComboSlash 5 (stop, decel 0.8, Do Pose=true)
  -> Will Counter?
```

### Charge (3 states)
Fast horizontal dash attack.
```
Charge Antic (face hero, speed=-32 backward, decel 0.825, wait 0.2s)
  -> Charge Break (stop, wait 0.6s)
  -> Charge (speed=80 forward, wait 0.3s, activate damagers, decel 0.89)
  -> Charge Recover (Do Pose=true, decel 0.875)
  -> Will Counter?
```

### J Slash / Rising Slash (5 states)
Multi-phase rising slash ending in downstab.
```
J Slash Antic (face hero, wait 0.65s)
  -> J Slash 1 (speed=60x, 87y diagonal launch, gravity=0)
  -> J Slash 2 (anim trigger, decel 0.825)
  -> J Slash 3 (anim trigger, decel 0.825)
  -> J Slash 4 (anim complete, decel 0.825)
  -> Dstab Constrain? (check X in [86, 102])
  -> Downstab Antic (face hero, decel)
  -> Downstab (speed=45x, -45y diagonal dive)
    LAND -> Downstab Land (clamp to Land Y, Do Pose=true)
           -> Will Counter?
    WALL -> Wallcling
```

**Wallcling -> Kickoff:**
```
Wallcling (gravity=0, speed=30 into wall, wait for anim)
  -> Kickoff (face hero, check distance)
    If distance > 2: face hero normally -> J Slash 1 (re-enter rising slash)
    If distance <= 2: face away -> J Slash 1 (kick off wall away from hero)
```

**Dstab Constrain?** [129]: If X position outside [86, 102], skip constraints and go to Downstab Antic directly. If inside range, sends messages (likely constraining movement).

**Downstab wall check:** During Downstab, checks $Wall Ahead (raycast), $Not Above Hero, and $Below Ground. If conditions met, transitions to Wallcling.

### Counter (5 states)
Parry/counter-attack triggered from Idle when hero is within 6.0 distance.
```
Counter Antic (Will Counter=false, face hero)
  -> Counter Dir (set invincibility direction based on facing)
  -> Counter Stance (invincible, wait 0.75s)
    BLOCKED HIT -> Counter Hit (face hero) -> RapidSlash Charge
    END (timer expires) -> Counter End (Do Pose=false) -> Pose
```

**Counter trigger logic (in Idle):**
- EaseFloat ramps $Counter Pause from 0 to 1 over 1.0s
- FloatTestToBool: $Distance < 6.0 -> $Counter Range = true
- FloatTestToBool: $Counter Pause > 0.25 -> $Counter Ready = true
- BoolAllTrue [Counter Range, Counter Ready] -> COUNTER event

### RapidSlash (3 states)
Rapid multi-hit slashing. Only triggered after Counter Hit.
```
RapidSlash Charge (speed=19 forward, damage=0, check hero collide)
  HERO COLLIDE -> Collide To Multihit -> Hero Facing -> Multihitting
  FINISHED -> RapidSlash Loop (decel 0.75, wait 0.65s)
    MULTI HIT CONNECT -> Hero Facing -> Multihitting
    FINISHED -> RapidSlash End (damage=1, Do Pose=false) -> Pose
```

### Evade/Hop (11 states)
Repositioning moves used for closing distance or dodging.

**Primary Evade (from Close/Distance Check):**
```
Evade (face hero, speed=-30 backward)
  -> Evade Recover (stop)
  -> Evade Move (pick follow-up attack: COMBO/CHARGE/J SLASH or CROSS SLASH if $Will CrossSlash)
```

**Range Out Evade chain (from Idle RANGE OUT):**
```
Evade 2 (speed=-30 backward)
  -> Evade Recover 2 (stop)
  -> Keep Evading? (check if hero is right vs Lace is right of centre)
    If positions allow more evading -> Evade 2 (loop)
    Otherwise -> Range Out (invincible, face hero, wait 4-8s random)
      RANGE IN -> Range Return -> CrossSlash? -> resume combat
      BLOCKED HIT / WAIT -> Swish Block -> Range Out (loop)
```

**Hop chain (from Far):**
```
Hop To Charge: set Target Distance=16.0, store "CHARGE" in $Next Event
Hop To J Slash: set Target Distance=12.0, store "J SLASH" in $Next Event
Hop To Combo: set Target Distance=9.25, store "COMBO" in $Next Event
  -> Hop Check (compare $Distance to $Target Distance)
    Distance <= Target -> Hop End -> [attack by name]
    $Hops > 3 -> Hop End (max hop cap)
    In alert range -> Hop Antic
      -> Hop (speed=24 forward, $Hops += 1)
      -> Hop Recover (decel 0.75)
      -> Hop Check (loop)
```

### Stun (5 states)
Triggered globally via STUN event.
```
Stun Start (recoil=7, Stun Timer=2.0, gravity=$Gravity, speed=-6x/23y knockback)
  -> Stun Air (check ground collision, damage=0, special death=true)
  -> Stun Land (stop, damage=1, special death=false)
  -> Stunned (decel 0.85, timer decrements by 1.0/frame)
    END (timer <= 0) -> Stun Recover (recoil=15, Do Pose=false) -> Pose
    TOOK DAMAGE -> Stun Damage (timer -= 0.25)
      Timer > 0 -> Stunned (continue stun)
      Timer <= 0 -> Damage Recover -> Stun Recover
    SING -> Sing Antic (hero can sing during stun)
```

### Multihit (4 states)
Triggered on MULTI HIT CONNECT or HERO COLLIDE during RapidSlash.
```
Collide To Multihit (check BindBell, check CanHeroTakeDamage)
  CANCEL -> Collide Cancel -> RapidSlash Loop (resume)
  BIND BELL -> Bind Bell Damage (1 damage) -> RapidSlash End
  FINISHED -> Hero Facing (face hero direction)
    -> Multihitting (stop velocity, camera shake, animate to hero, wait 0.75s)
    -> Multihit Slash (translate y+0.5, deal 1 damage directly, Do Pose=true)
    -> Pose
```

### CrossSlash (6 states)
Special rage attack triggered when HP <= 50% max HP ($Rage HP). Uses a countdown counter ($Ct CrossSlash) initialized randomly to 2-4.

```
CrossSlash? (HP <= Rage HP AND Ct CrossSlash <= 0?)
  -> CrossSlash Aim (face hero, check distance)
    Distance < 6.0 -> CS Evade (evade first, set Will CrossSlash=true)
      Evade Attempts < 2 -> Evade (dodge back, then Evade Move with Will CrossSlash)
      Evade Attempts >= 2 -> CS Evade Cancel (force CrossSlash regardless, face centre)
    Distance >= 6.0 AND not facing wrong way -> CrossSlash Antic
    If on wrong side (facing towards wall) -> CS Evade

  CrossSlash Antic (Evade Attempts=0, new Ct CrossSlash=random 2-4, recoil=0, wait 0.9s)
    -> CrossSlash (kinematic, hide mesh, hide collider, wait 0.8s, move to hero position)
    -> Finish Multihit (show mesh, position at hero +0.75y, deal 1 damage directly)
    -> Slash Slam (translate y-0.3, recoil=15, show all, Do Pose=true)
    -> Pose -> Idle
```

**CrossSlash Aim position logic:**
- Gets self X position, compares to $Centre X (93.78 docks / 39.66 grotto)
- $Right Side = self X > Centre X
- $Facing Right = X scale > 0
- If Right Side AND Facing Right: EVADE (facing wall, need to reposition)
- If !Right Side AND !Facing Right: EVADE (facing wall on left side)
- Otherwise: proceed to CrossSlash Antic

### Sing (3 states)
Triggered when hero performs (sing/needle) near Lace. Can interrupt from Idle, Distance Check, or Stunned.
```
Sing Antic (face hero, stop audio)
  -> Sing (EnemySingControl, no puppet string, check hero region with 0.5s react delay)
    END (hero stops performing) -> Sing End
    SING DURATION END -> Sing End
  -> Sing End -> Will Counter?
```

### Lava Mechanics (6 states)
Triggered globally via LAVA DAMAGE event. Lace takes 40 HP damage from lava.
```
Lava Damage (stop velocity, subtract 40 HP, freeze moment, clamp X to [79, 109],
             position at lava Y + 0.2, gravity=0, recoil blocked, jitter effect, wait 0.85s)
  -> Lava Hop (velocity y=80 upward, decel Y 0.85, damage=1, wait 0.4s)
  -> Lava Tele Out (stop, play disappear anim)
  -> Set Tele Pos X (position at Centre X, Land Y)
    If distance to hero < 3.0: translate by X Scale * 8.0 (offset away from hero)
  -> Tele In (play appear anim)
  -> Lava End (restore gravity, recoil unblocked, special death=false, damage=1)
  -> Idle
```

### Pose Variants (5 states)
After attacks, if $Do Pose is true, Lace performs a taunt pose.
```
Pose:
  $Hornet Dead -> Death Pose
  $Do Pose = false -> FINISHED -> Idle (skip pose)
  $Do Pose = true -> random SWISH / LEAN / UPRIGHT (equal weight)

Pose Swish -> check alert range -> Pose Swish 2 or Pose Lean (if CANCEL)
  -> Pose Swish 2 -> Idle
Pose Lean (play anim, audio, face hero) -> Idle
Pose Upright (play anim, audio) -> Idle
Pose Swish 3 -> Idle
```

### Death / Misc (2 states)
- **Death Pose** [76]: Check distance < 2.0 -> EVADE -> Idle (evade if hero too close). Face hero, play death animation.
- **Trap Stun** [77]: Play stun animation, stop velocity -> Idle. Triggered by environmental traps.

### Dormant Block Chain (3 states)
Handles hits while dormant (before battle starts).
```
Dormant -> BLOCKED HIT -> Block Voice (set NPC Blocked Hit, play voice)
  -> Dormant Block (create noise, spawn hit effect, face hero, play anim)
    BLOCKED HIT -> Dormant Block (loop)
    FINISHED -> Dormant Blocked Idle (idle anim, wait for more hits or ENTER)
    ENTER -> Location Check 2
```

---

## Key Variables

### Timing
| Variable | Default | Description |
|----------|---------|-------------|
| Counter Pause | 0.0 | Ramps 0->1 over 1.0s in Idle; counter fires when > 0.25 |
| Stun Timer | 0.0 | Set to 2.0 on stun, decrements each frame |

### Distance/Position
| Variable | Default | Description |
|----------|---------|-------------|
| Centre X | 93.78 | Arena centre (docks); 39.66 in grotto |
| Land Y | 7.60 | Ground Y level (docks); 8.54 in grotto |
| Distance | 0.0 | Current distance to hero |
| Target Distance | 0.0 | Target hop distance for current attack |
| Self X | 0.0 | Current X position (temp) |
| Hero Y | 0.0 | Hero Y position (temp) |
| X Scale | 0.0 | Current facing scale (temp) |
| Lava Pos Y | 0.0 | Y position of lava surface |

### Combat Counters (SendRandomEvent tracking)
| Variable | Default | Description |
|----------|---------|-------------|
| Ct Charge | 0 | Consecutive charge picks |
| Ct Combo | 0 | Consecutive combo picks |
| Ct CrossSlash | 0 | CrossSlash countdown (random 2-4, decrements per attack cycle) |
| Ct Evade | 0 | Consecutive evade picks |
| Ct J Slash | 0 | Consecutive J Slash picks |
| Evade Attempts | 0 | CS Evade retry counter (max 2) |
| Hops | 0 | Current hop count (max 3) |
| Ms Charge | 0 | Missed charge counter |
| Ms Combo | 0 | Missed combo counter |
| Ms Evade | 0 | Missed evade counter |
| Ms J Slash | 0 | Missed J Slash counter |
| Rage HP | 0 | 50% of max HP; CrossSlash threshold |
| Invincibility Direction | 0 | Direction for counter invincibility |

### Boolean Flags
| Variable | Default | Description |
|----------|---------|-------------|
| Counter Range | false | Hero within 6.0 distance |
| Counter Ready | false | Counter Pause > 0.25 (ready to counter) |
| CrossSlashing Hero | false | Currently in CrossSlash grab |
| Do Pose | false | Perform taunt pose after attack |
| Facing Right | false | Lace facing right (X scale > 0) |
| Hero Is Right | false | Hero is to the right |
| Hornet Dead | false | Fight over flag |
| Lace Is Right | false | Lace is right of centre |
| Needolin Fight | false | True for grotto arena variant |
| Right Side | false | Lace on right side of arena |
| Will Counter | false | Will counter after next attack |
| Will CrossSlash | false | Will CrossSlash after evade |
| Bind Bell Hit | false | Bind bell interaction flag |
| NPC Blocked Hit | false | Hit while in NPC/dormant mode |
| Dormant Block | false | In dormant blocking state |
| Above Wallcling Min | false | Above minimum wallcling Y |
| Not Above Hero | false | Not above hero (for wall check) |
| Wall Ahead | false | Wall detected by raycast |
| Below Ground | false | Below ground level |

### String Variables
| Variable | Default | Description |
|----------|---------|-------------|
| Next Event | "" | Stores attack event name for hop chain (CHARGE/J SLASH/COMBO) |

### Vector3 Variables
| Variable | Default | Description |
|----------|---------|-------------|
| CS Lace Pos | (0,0,0) | Lace position during CrossSlash |
| Multihit Pos | (0,0,0) | Position during multihit grab |

---

## Global Transitions (always active)

| Event | Target State |
|-------|-------------|
| STUN | Stun Start |
| LAVA DAMAGE | Lava Damage |

Note: Only 2 global transitions vs Lost Lace's 4. No CS TELE/CS READY globals -- CrossSlash is handled entirely through the FSM flow.

---

## Key Timing Summary

| State | Wait Duration | Effect |
|-------|---------------|--------|
| Idle | 0.75s | Time between attacks |
| Charge Antic | 0.2s | Backward windup |
| Charge Break | 0.6s | Pause at wall/edge before re-charging |
| Charge | 0.3s | Forward dash duration |
| Counter Stance | 0.75s | Counter window (invincible) |
| J Slash Antic | 0.65s | Rising slash windup |
| RapidSlash Loop | 0.65s | Rapid slash duration |
| Multihitting | 0.75s | Multihit grab freeze |
| CrossSlash Antic | 0.9s | CrossSlash windup (recoil=0, invulnerable) |
| CrossSlash | 0.8s | Invisible dash to hero |
| Lava Damage | 0.85s | Lava stun freeze |
| Lava Hop | 0.4s | Upward escape from lava |
| Range Out | 4.0-8.0s (random) | Idle at range while invincible |

---

## Velocity Reference

| State | Speed X | Speed Y | Notes |
|-------|---------|---------|-------|
| Charge Antic | -32 (scaled) | 0 | Backward wind-up |
| Charge | 80 (scaled) | 0 | Forward dash |
| Evade / Evade 2 | -30 (scaled) | 0 | Backward dodge |
| Hop | 24 (scaled) | 0 | Forward hop |
| ComboSlash 2/4 | 30 (scaled) | 0 | Combo lunge |
| RapidSlash Charge | 19 (scaled) | 0 | Rush in (after counter) |
| J Slash 1 | 60 (scaled) | 87 | Diagonal launch (steep upward) |
| Downstab | 45 (scaled) | -45 | Diagonal dive |
| Stun Start | -6 (scaled) | 23 | Knockback arc |
| Wallcling | 30 (scaled) | 0 | Into wall |
| Lava Hop | 0 | 80 | Vertical escape from lava |

"Scaled" velocities use `SetVelocityByScale` which multiplies X by facing direction (+1 or -1).

---

## Key Differences from Lost Lace (206-state FSM)

### Boss1 has, Lost Lace does not:
- **Distance Check / Close / Far** branching (Boss1 uses explicit close/far split; Lost Lace uses Movement Check with min/max distance)
- **Hop To [Attack]** system with target distances (Charge=16, J Slash=12, Combo=9.25)
- **Lava Damage** chain (40 HP self-damage, hop escape, teleport to centre)
- **Wallcling -> Kickoff** (cling to wall during downstab, kick off into J Slash 1)
- **Dstab Constrain?** (X range check [86, 102] before downstab)
- **Grotto variant** with different Centre X (39.66) and Land Y (8.54)
- **Dialogue system** (14+ conversation states for first encounter / re-encounter)
- **Range Out** evasion chain (invincible idle at range, 4-8s wait)
- **Dormant Block** chain (responding to hits before battle)

### Lost Lace has, Boss1 does not:
- Phase shifts (P2/P3/P4 with HP thresholds)
- Teleport/Dive system (20 states, underground movement)
- Tendril attacks (ground and air variants)
- Tendril Summon
- Vomit/Cast (projectile spray)
- Bullet Summon
- Abyss Wave (arena-wide wave)
- Quick Slash chain
- Downstab IntoDive variant
- TeleDive
- Multiple CrossSlash variants (CS Tele/CS Ready globals, CS Summon/CS Thwip)
- Combo Strike (multihit combo variant)
- Combo Interrupt logic
- J Slash Multi (air variant of rising slash)
- Hop Up (vertical hop)
- P3 Roar / Sing/Conduct chain
- Splash In (water entry)

### Shared mechanics (different tuning):
| Parameter | Boss1 | Lost Lace |
|-----------|-------|-----------|
| Idle Time | 0.75s (fixed) | 0.7s (0.5s after P2) |
| Charge Speed | 80 | 70 |
| Charge Antic Speed | -32 | -32 |
| Charge Wait | 0.3s | 0.25s |
| Evade Speed | -30 | -28 |
| Hop Speed | 24 | 36 |
| ComboSlash Speed | 30 | 40 |
| J Slash Launch | 60x, 87y | 60x, 60y |
| RapidSlash Speed | 19 | 30 |
| Counter Stance | 0.75s | 0.5s |
| Stun Timer | 2.0s | 0.0s (variable) |
| Stun Knockback | -6x, 23y | -8x, 24y |
| Gravity | 2.0 | 2.0 |
| CrossSlash Antic | 0.9s | 0.25s (CS Antic) |
| CrossSlash Duration | 0.8s | 1.2s (Do CrossSlash) |
| Lava Damage | 40 HP | N/A |

---

## Evade/Counter Reaction Logic (Idle)

Lace reacts to the hero while idling:

1. **Counter reaction** (if hero attacks nearby):
   - `GetDistance` -> store in `$Distance`
   - `FloatTestToBool`: if distance < 6.0, set `$Counter Range = true`
   - `EaseFloat`: ramps `$Counter Pause` from 0.0 to 1.0 over 1.0s
   - `FloatTestToBool`: if `$Counter Pause` > 0.25, set `$Counter Ready = true`
   - `BoolAllTrue` [Counter Range, Counter Ready] -> COUNTER event
   - This means counter cannot fire until 0.25s into idle (the ease ramp reaches 0.25 at 25% of 1.0s)

2. **Sing reaction** (hero performing):
   - `CheckHeroPerformanceRegionV2`: radius=0, react delay 0.2s
   - ActiveInner = "SING" -> Sing Antic

3. **Range Out** (hero too far):
   - `CheckAlertRange`: OutOfRangeEvent = "RANGE OUT" -> Evade 2 chain

4. **Took Damage** (anytime):
   - Treated same as ATTACK -> CrossSlash? -> Distance Check

---

## Will Counter? Logic

After each attack resolves (ComboSlash 5, Charge Recover, Downstab Land, Sing End):
- `SendRandomEvent` with weights [0.33, 0.66] for ["", "FINISHED"]
  - 33% chance: sets $Will Counter = true (does NOT send event, falls through)
  - 67% chance: sends FINISHED -> Pose
- If $Will Counter was set, next Idle may trigger COUNTER sooner
- Note: $Will Counter is reset to false in Counter Antic

---

## Arena Bounds

### Docks (bone_east_12 default)
- Centre X: 93.78
- Land Y: 7.60
- Downstab Land X range: [81, 107] (outside = wall transition)
- Dstab Constrain X range: [86, 102]
- Lava clamp X: [79, 109]
- CrossSlash Aim reference: Centre X for side check

### Grotto (Needolin Fight variant)
- Centre X: 39.66
- Land Y: 8.54
- Same FSM with position overrides set in Grotto Fight state
