# Silksong Ground-Truth Values Extracted from Unity Assets

**Date:** 2026-04-30
**Scene:** `abyss_cocoon` (inside `scenes_scenes_scenes` bundle)
**Boss GO:** "Lost Lace Boss" at PathID=919 in the abyss_cocoon scene
**Hero bundle:** `heroloading_assets_all.bundle`

---

## 1. Boss Body Collider

The Lost Lace Boss has **no BoxCollider2D** on its main GO. Instead it uses a **DamageHero** component directly (dmg=2, hazardType=1) and a **Rigidbody2D**.

There is no explicit "body" BoxCollider2D on the Lace boss root. The boss body collision appears to be handled via the `DamageHero` component (which marks the whole GO as damaging) combined with child hitbox colliders for specific attacks.

**Rigidbody2D:**
- gravityScale = **2.0** (confirms our sim's `bossGravity = gravity * 2.0 = -120`)
- mass = 1.0
- bodyType = 1 (Kinematic)
- linearDrag = 0

The "body" hitbox for normal contact is likely determined by one of the child PolygonCollider2D shapes or the `Combo Slash BodyCatcher` BoxCollider2D:

**Combo Slash BodyCatcher** (child of Lost Lace Boss):
- BoxCollider2D: size=(1.5321, 2.8130) offset=(0.4828, 0.0000)
- half_w = 0.7660, half_h = 1.4065
- This is the body-catcher during combo slashes, NOT the resting body collider.

**Note:** The boss body collision for the sim likely relies on the PolygonCollider shapes of attacks, with the boss's position + the HealthManager handling hit detection. The sim's current `bossBodyHalfW=0.8, bossBodyHalfH=1.2` is a reasonable approximation.

---

## 2. Boss Attack Hitbox Sizes

### Direct children of Lost Lace Boss:

| Attack | Collider Type | Extents (x min,max / y min,max) | half_w | half_h |
|--------|--------------|----------------------------------|--------|--------|
| Charge Hit | Polygon (5pt) | x=[0.14, 3.07] y=[-1.31, 0.94] | 3.07 | 1.31 |
| Downstab Hit | Polygon (5pt) | x=[-0.62, 1.62] y=[-2.00, 0.28] | 1.62 | 2.00 |
| MultiHit | Polygon (7pt, disabled) | x=[-0.14, 7.50] y=[-1.35, 1.20] | 7.50 | 1.35 |
| Combo Slash 1 | Polygon (10pt) | x=[-1.88, 5.12] y=[-1.20, 2.66] | 5.12 | 2.66 |
| Combo Slash 2 | Polygon (9pt) | x=[-2.37, 4.79] y=[-0.94, 2.73] | 4.79 | 2.73 |
| Combo Slash BodyCatcher | Box | size=(1.53, 2.81) offset=(0.48, 0) | 0.77 | 1.41 |
| Thwip Slash | Polygon (7pt) | x=[-1.63, 1.98] y=[-0.36, 1.64] | 1.98 | 1.64 |
| Circle Slash Multi | Circle r=2.26 | radius=2.26 | 2.26 | 2.26 |
| MultiHit Air | Polygon (6pt, disabled) | x=[-0.12, 7.67] y=[-1.35, 0.53] | 7.67 | 1.35 |

### Grandchildren (tendril/whip damagers):

| Attack | Collider Type | Extents | half_w | half_h |
|--------|--------------|---------|--------|--------|
| Whip Attack G/Damager | Polygon (7pt) | x=[-3.47, 3.89] y=[-1.63, 1.73] | 3.89 | 1.73 |
| Whip Attack A/Damager | Polygon (8pt) | x=[-3.47, 3.89] y=[-1.63, 1.73] | 3.89 | 1.73 |

### Range checkers (not damage hitboxes):

| Name | Type | Size | Offset |
|------|------|------|--------|
| NoThwip Range | Box | (9.47, 6.15) | (0, 1.13) |
| Evade Range | Box | (12.00, 8.45) | (0, 2.28) |
| Above Range | Box | (12.00, 12.79) | (0, 8.32) |

### Cross Slash Lace Collider:
- BoxCollider2D: size=(1.0, 1.0) offset=(0, 0) - DamageHero dmg=1
- This is the "lace collider" child of Lost_Lace_Cross_Slash

### DamageHero values (all attacks):
| Source | Damage | hazardType | canClashTink | forceParry |
|--------|--------|------------|-------------|------------|
| Lost Lace Boss (body) | 2 | 1 | 0 | 0 |
| Charge Hit | 0 | 1 | 1 | 0 |
| Downstab Hit | 0 | 1 | 1 | 0 |
| Combo Slash 1 | 0 | 1 | 1 | 0 |
| Combo Slash 2 | 0 | 1 | 1 | 0 |
| Combo Slash BodyCatcher | 0 | 1 | 0 | 0 |
| MultiHit | 0 | 1 | 1 | 0 |
| MultiHit Air | 0 | 1 | 1 | 0 |
| Thwip Slash | 1 | 1 | 1 | 0 |
| Circle Slash Multi | 0 | 1 | 1 | 0 |
| Whip Attack G/Damager | 0 | 1 | 0 | 0 |
| Whip Attack A/Damager | 0 | 1 | 0 | 0 |
| Cross Slash/lace collider | 1 | 1 | 0 | 0 |
| Slam Tendril damagers | 2 | 1 | 0 | 0 |

**Note:** `damageDealt=0` with `canClashTink=1` means the damage is applied via the `hornet_multi_wounder` FSM, not the DamageHero component directly. The FSM controls how many hits per attack animation.

---

## 3. Stun Control FSM

**FSM name:** "Stun Control"
**PathID:** 13822 (on GO "Lost Lace Boss", pid=919)
**States:** Init, Idle, In Combo, Reset Counter, Continue Combo, Stun, Max Check, Stop, Unstun Increment, Reset, Dazed Effect, Stun End, Stunned, Quick End, Stop Daze Effect, Stop Daze Effect 2, Stop Daze Effect 3

### Key Variables:
| Variable | Value | Description |
|----------|-------|-------------|
| **Stun Combo** | **16** | Hits in a combo window to trigger stun |
| **Stun Hit Max** | **18** | Absolute max hits before forced stun |
| **Combo Time** | **1.0** | Seconds -- combo window duration |
| Epsilon | 0.01 | Float comparison threshold |
| Stun Damage | 0.0 | Runtime counter (starts at 0) |
| Hits Total | 0.0 | Runtime counter |
| Combo Counter | 0.0 | Runtime counter |
| Daze Effect Active | 0 | Runtime flag |
| Abyss Attacking | 0 | Runtime flag |

**Current sim:** `bossStunThreshold = 7` -- this is WRONG.  
**Ground truth:** Stun Combo = 16, Stun Hit Max = 18.

The stun system works as a combo counter: if you hit the boss 16 times within a 1-second combo window, it triggers a stun. OR if you accumulate 18 total hits (Stun Hit Max), it forces a stun regardless of combo timing.

---

## 4. Arena Geometry (Terrain Colliders)

The Abyss Cocoon arena uses **EdgeCollider2D** chunks for terrain, NOT BoxCollider2D.

### Terrain EdgeCollider2D layout:

The arena is divided into tilemap chunks. The key chunk for the Lace boss fight platform is:

**Chunk 0 1** (covers world x=[32,64], y=[0,32]):
- Floor runs from x=32 to x=55 at y=4 (the flat platform area)
- Right wall from x=55 slopes up from y=4 to y=16, then continues as a cliff
- Left side connects at x=32, y=4 going left

**Chunk 0 0** (covers world x=[0,32], y=[0,32]):  
- Floor at y=4 from x=3 to x=32
- Left wall at x=3, running from y=4 up to y=17, then stepping up

**Chunk 1 1** (covers world x=[32,64], y=[32,64]):
- Full rectangular outline (walls on all sides)

### Arena bounds summary:
The flat fighting platform floor is at **y=4** (in the scene's local coordinate space).

Key walls:
- **Left wall:** x ~ 3 (from Chunk 0 0, floor at y=4 rising to cliffs)
- **Right wall:** x ~ 55 (from Chunk 0 1, floor at y=4 rising to cliffs)
- **Floor:** y = 4 (flat platform between x=3 and x=55)
- **Right boundary:** x=64-65 (hard wall edge colliders on right)
- **Ceiling:** No explicit ceiling in the fighting area

### Interpretation for sim:
The boss spawn position is (38.0, 7.07) in scene coordinates. The hero spawn from FSM data was (49.27, 100.57) in a different coordinate system. The FSM "Land Y" = 6.4, and "Bomb Min X" / "Bomb Max X" are 40.5 / 66.5 which were in a different scene's coordinates.

The **Abyss Cocoon** scene uses its own coordinate system:
- Floor Y = 4.0 (tile edge) -- boss feet land ~5.0-6.0 (boss pos Y = 7.07 with half-height ~1.0)
- Arena left ~ X=3, Arena right ~ X=55
- The FSM variables "Tele X Min=6" and "Tele X Max=51" are **relative** (6 and 51 are world X in this scene)

**Note:** The previously extracted spawn positions (49.27, 100.57) were from a DIFFERENT scene (not abyss_cocoon). The actual Lace boss position in abyss_cocoon is (38.0, 7.07).

The **solid BoxCollider2D** terrain colliders found (6 total) are mostly small (1x1) positioning colliders, except for two "non slider" platforms at Y~13-15 which are upper platforms above the main arena.

---

## 5. HeroController Serialized Constants

Found in `heroloading_assets_all.bundle`.

### Key values for our sim:

| Field | Ground Truth | Current Sim | Status |
|-------|-------------|-------------|--------|
| **INVUL_TIME** | **1.0** | heroInvulFrames=50 (1.0s @ 50Hz) | CORRECT |
| **RECOIL_HOR_VELOCITY** | **3.75** | heroRecoilSpeed=15.0 | WRONG - 15.0 is `RECOIL_VELOCITY` |
| **RECOIL_HOR_STEPS** | **8** | heroRecoilFrames=5 | WRONG - should be 8 |
| **RECOIL_DURATION** | **0.2** | (not used directly) | - |
| **RECOIL_VELOCITY** | **15.0** | heroRecoilSpeed=15.0 | CORRECT (vertical recoil) |
| RUN_SPEED | 8.25 | runSpeed=8.25 | CORRECT |
| WALK_SPEED | 5.0 | walkSpeed=5.0 | CORRECT |
| DASH_SPEED | 28.0 | dashSpeed=28.0 | CORRECT |
| DASH_COOLDOWN | 0.425 | dashCooldownFrames=21 (0.42s) | CORRECT |
| DASH_TIME | 0.1 | dashDurationFramesGround=6 (0.12s) | CLOSE |
| AIR_DASH_TIME | 0.02 | dashDurationFramesAir=1 (0.02s) | CORRECT |
| DOWN_DASH_TIME | 0.25 | dashDurationFramesDown=13 (0.26s) | CORRECT |
| JUMP_SPEED | 18.6 | jumpVel=18.6 | CORRECT |
| JUMP_STEPS | 8 | jumpStepsMax=9 | CLOSE (8 vs 9) |
| JUMP_STEPS_MIN | 2 | jumpStepsMinCut=2 | CORRECT |
| MIN_JUMP_SPEED | 3.0 | minJumpSpeed=3.0 | CORRECT |
| DEFAULT_GRAVITY | 1.0 | (hero gravity scale) | CORRECT |
| AIR_HANG_GRAVITY | 0.1 | airHangGravScale=0.2 | WRONG - should be 0.1 |
| AIR_HANG_ACCEL | 5.0 | airHangAccel=5.0 | CORRECT |
| MAX_FALL_VELOCITY | 30.0 | maxFallSpeed=30.0 | CORRECT |
| MAX_FALL_VELOCITY_DJUMP | 10.0 | maxFallSpeedDjump=10.0 | CORRECT |
| DOUBLE_JUMP_RISE_STEPS | 4 | doubleJumpRiseSteps=4 | CORRECT |
| DOUBLE_JUMP_FALL_STEPS | 4 | doubleJumpFallSteps=4 | CORRECT |
| SHUTTLECOCK_SPEED | 18.0 | shuttlecockSpeed=18.0 | CORRECT |
| WALL_STICKY_STEPS | 3 | wallJumpLockFrames=3 | CORRECT |
| WALLSLIDE_ACCEL | -24.0 | (wallslide deceleration) | NEW |
| WJ_KICKOFF_SPEED | 25.0 | wallJumpVelX=15.0 | WRONG? |

### Additional HeroController constants discovered:
| Field | Value |
|-------|-------|
| RECOIL_HOR_VELOCITY_LONG | 16.0 |
| RECOIL_HOR_VELOCITY_DRILLDASH | 10.0 |
| RECOIL_DOWN_VELOCITY | 0.0 |
| BOUNCE_VELOCITY | 12.0 |
| BOUNCE_TIME | 0.25 |
| INVUL_TIME_CROSS_STITCH | 0.35 |
| INVUL_TIME_PARRY | 0.15 |
| INVUL_TIME_QUAKE | 0.4 |
| INVUL_TIME_SILKDASH | 0.5 |
| CAST_RECOIL_VELOCITY | 10.0 |
| DOWNSPIKE_REBOUND_SPEED | 20.0 |
| DOWNSPIKE_REBOUND_STEPS | 6 |
| WALLSLIDE_SHUTTLECOCK_VEL | 12.0 |
| WJLOCK_STEPS_SHORT | 5 |
| WJLOCK_STEPS_LONG | 15 |
| WJLOCK_CHAIN_STEPS | 10 |
| QUICKENING_RUN_SPEED | 11.5 |
| QUICKENING_WALK_SPEED | 7.0 |
| QUICKENING_DURATION | 10.0 |

### Hero Colliders:
| Collider | Type | Size | Offset |
|----------|------|------|--------|
| **Hero_Hornet** (physics body) | BoxCollider2D | (0.5000, 2.0789) | (0.0000, -0.5132) |
| **HeroBox** (hurtbox/trigger) | BoxCollider2D | (0.4554, 1.9864) | (0.0000, -0.0868) |

**Hero_Hornet** (physics collider, non-trigger):
- half_w = 0.25, half_h = 1.04
- offset = (0, -0.51)
- Current sim: heroHalfWidth=0.4, heroHalfHeight=0.568 -- both WRONG

**HeroBox** (hurtbox, trigger):
- half_w = 0.2277, half_h = 0.9932
- offset = (0, -0.0868)
- Current sim: heroHurtNormalHalfW=0.23, heroHurtNormalHalfH=1.125, heroHurtNormalOffY=-0.38

---

## 6. Boss HealthManager

| Field | Value |
|-------|-------|
| hp | **1800** |
| invulnerableTime | **0.25** |
| preventDeathAfterHero | 1 |
| hasSpecialDeath | 1 |
| preventInvincibleEffect | 1 |
| stunHits | NOT present (stun is FSM-controlled) |

**Current sim:** bossMaxHP=800, bossInvincFrames=12 (0.24s @ 50Hz)  
**Ground truth:** hp=1800, invulnerableTime=0.25s (12.5 frames @ 50Hz)

The boss HP of 800 in our sim was set for the current sim's difficulty/phase model. The ground truth is 1800.

---

## 7. Key FSM Variables from Lace Control FSM (pid=13742)

| Variable | Value |
|----------|-------|
| Gravity | 2.0 (= gravityScale on Rigidbody2D) |
| Idle Time | 0.7 |
| Land Y | 6.4 (scene-relative) |
| Combo Slash Speed | 40.0 |
| Counter Pause | 0.15 |
| Recoil Default | 12.0 |
| Recoil Reduced | 5.0 |
| Tele X Min | 6.0 |
| Tele X Max | 51.0 |
| Wallcling Min Y | 99.0 (NOTE: likely from a different coordinate system) |
| Dive In Splash Y | 7.5 |
| Abyss Wave Countdown | 2 |

---

## Summary of Values That Need Updating in Sim

### Critical corrections:
1. **bossStunThreshold: 7 -> 16** (Stun Combo) with Stun Hit Max = 18
2. **bossMaxHP: 800 -> 1800** (ground truth; may want to keep scaled for training)
3. **heroHalfWidth: 0.4 -> 0.25** (Hero_Hornet physics collider)
4. **heroHalfHeight: 0.568 -> 1.04** (Hero_Hornet physics collider)
5. **heroRecoilFrames: 5 -> 8** (RECOIL_HOR_STEPS)
6. **airHangGravScale: 0.2 -> 0.1** (AIR_HANG_GRAVITY)
7. **jumpStepsMax: 9 -> 8** (JUMP_STEPS)
8. **RECOIL_HOR_VELOCITY = 3.75** (horizontal recoil speed when hit, distinct from RECOIL_VELOCITY=15.0 which is knockback)

### Values confirmed correct:
- runSpeed=8.25, walkSpeed=5.0, dashSpeed=28.0
- jumpVel=18.6, minJumpSpeed=3.0
- gravity=-60 with hero gravityScale=1.0
- bossGravity=-120 (gravity * boss gravityScale 2.0)
- maxFallSpeed=30.0, maxFallSpeedDjump=10.0
- INVUL_TIME=1.0 (heroInvulFrames=50 is correct)
- dashCooldown, doubleJump parameters, shuttlecockSpeed
- bossRecoilDefault=12.0, bossRecoilReduced=5.0
- bossIdleTimeP1=0.7
- bossInvincFrames=12 (0.24s vs 0.25s ground truth -- close enough)
