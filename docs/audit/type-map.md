# Game-Internal Type Map

> **Status: REFERENCE — consult during Phase 5 (hero physics) and Phase 7 (Lace FSM) implementation.**
>
> This is the catalogue the sim port reads *from*. Every field/method listed
> here is something the plugin actually touches in the live game; if the sim
> needs to reproduce the same observable behaviour, this is the contract.
> Kept verbatim.

This document is an exhaustive catalogue of every game-internal type referenced in `plugin/Source/`. For each type it lists every field/property accessed and every method called, the location (file:line), the data type and semantics, and whether the access is read-only observation or read-write actuation. This becomes the contract the standalone Madrona simulator must implement.

---

## HeroController

`HeroController` is the singleton player-character controller. Accessed via `HeroController.instance`.

### Static Members

| Member | Location | Type | Access | Semantics |
|--------|----------|------|--------|-----------|
| `instance` (static) | GameStateCollector.cs:19, EpisodeResetter.cs:374,402, SharedMemoryManager.cs:327, SkipIntroPatch.cs:41,48,50,51,53,64,66,71,73, DebugOverlayManager.cs:379,389,408 | `HeroController` | Read (singleton) | Singleton reference; null when player is not alive or scene not loaded |

### Fields / Properties — Observation (Read)

| Member | Location | Type | Semantics |
|--------|----------|------|-----------|
| `transform.position.x` | GameStateCollector.cs:22, GameStateCollector.cs:37 | `float` | Player world X position (Unity units) |
| `transform.position.y` | GameStateCollector.cs:23, GameStateCollector.cs:37 | `float` | Player world Y position |
| `playerData.health` | GameStateCollector.cs:28 | `int` | Current player HP |
| `playerData.maxHealth` | GameStateCollector.cs:29 | `int` | Max player HP |
| `playerData.silk` | GameStateCollector.cs:30 | `int` | Current silk (resource/mana) |
| `playerData.isInvincible` | GameStateCollector.cs:34 | `bool` | True while player has active invincibility |
| `playerData.silkRegenMax` | EpisodeResetter.cs:668 | `int` | Max silk (used to full-restore on reset) |
| `playerData.encounteredLaceTower` | EpisodeResetter.cs:670, ResetEpisode:1341 | `bool` | Save-flag: player has entered Lace Tower |
| `playerData.defeatedLaceTower` | EpisodeResetter.cs:671, ResetEpisode:1342 | `bool` | Save-flag: Lace boss defeated |
| `playerData.laceTowerDoorOpened` | EpisodeResetter.cs:672, ResetEpisode:1343 | `bool` | Save-flag: tower door opened |
| `playerData.atBench` | SkipIntroPatch.cs:41 | `bool` | True while player is sitting at bench |
| `cState.onGround` | GameStateCollector.cs:31 | `bool` | True when player is grounded |
| `cState.facingRight` | GameStateCollector.cs:33 | `bool` | True when player faces right |
| `cState.invulnerable` | EpisodeResetter.cs:443 | `bool` | True when player is invincible frame-flag |
| `cState.dead` | EpisodeResetter.cs:490 | `bool` | True when player is in death state |
| `cState.hazardDeath` | EpisodeResetter.cs:489 | `bool` | True when killed by a hazard |
| `cState.recoiling` | EpisodeResetter.cs:491 | `bool` | True while playing recoil animation |
| `cState.jumping` | EpisodeResetter.cs:498 | `bool` | True during jump |
| `cState.falling` | EpisodeResetter.cs:497 | `bool` | True during fall |
| `cState.dashing` | EpisodeResetter.cs:500 | `bool` | True during dash |
| `cState.attacking` | EpisodeResetter.cs:502 | `bool` | True during attack |
| `cState.wallSliding` | EpisodeResetter.cs:507 | `bool` | True while sliding down a wall |
| `cState.doubleJumping` | EpisodeResetter.cs:499 | `bool` | True during double jump |
| `animCtrl.animator` | GameStateCollector.cs:46 | `tk2dSpriteAnimator` | Player's sprite animator controller |
| `animCtrl.animator.CurrentClip` | GameStateCollector.cs:49 | `tk2dSpriteAnimationClip` | Currently playing animation clip |
| `animCtrl.animator.CurrentClip.name` | GameStateCollector.cs:52 | `string` | Clip name used for animation state lookup |
| `animCtrl.animator.CurrentClip.frames` | GameStateCollector.cs:50,53 | `tk2dSpriteAnimationFrame[]` | Frame array — length used for progress calc |
| `animCtrl.animator.CurrentFrame` | GameStateCollector.cs:54 | `int` | Current frame index within clip |
| `doingHazardRespawn` | EpisodeResetter.cs:1324 | `bool` | True while the hazard-respawn coroutine is running |
| `acceptingInput` | EpisodeResetter.cs:1362 | `bool` | True when player controller accepts movement input |
| `DEFAULT_GRAVITY` | EpisodeResetter.cs:483,629,630 | `float` | Default gravity scale constant |
| `parryInvulnTimer` | EpisodeResetter.cs:563 | `float` | Timer for parry invincibility window |
| `touchingWallL` | EpisodeResetter.cs:593 | `bool` | True when touching wall on the left |
| `touchingWallR` | EpisodeResetter.cs:594 | `bool` | True when touching wall on the right |
| `wallLocked` | EpisodeResetter.cs:592 | `bool` | True when stuck to wall |
| `controlReqlinquished` | EpisodeResetter.cs:552 | `bool` | True when control has been surrendered to a cutscene |
| `hero_state` | EpisodeResetter.cs:663 | `ActorStates` (enum) | High-level state machine enum value |
| `acceptingInput` | EpisodeResetter.cs:665 | `bool` | Whether input is being accepted |
| `dashingDown` | EpisodeResetter.cs:627 | `bool` | True during downward dash |

### Fields / Properties — Actuation (Write)

| Member | Location | Type | Semantics |
|--------|----------|------|-----------|
| `damageMode` | EpisodeResetter.cs:418, 440 | `DamageMode` (enum) | Set to `NO_DAMAGE` during reset, `FULL_DAMAGE` after |
| `playerData.isInvincible` | EpisodeResetter.cs:419, 441 | `bool` | Toggled to prevent damage during reset |
| `playerData.health` | EpisodeResetter.cs:1344 | `int` | Restored to maxHealth on hard reset |
| `playerData.silk` | EpisodeResetter.cs:1345 | `int` | Restored to silkRegenMax on hard reset |
| `playerData.encounteredLaceTower` | EpisodeResetter.cs:670, 1341 | `bool` | Set true to ensure boss encounter |
| `playerData.defeatedLaceTower` | EpisodeResetter.cs:671, 1342 | `bool` | Set false to prevent win-state skip |
| `playerData.laceTowerDoorOpened` | EpisodeResetter.cs:672, 1343 | `bool` | Set false |
| `playerData.atBench` | SkipIntroPatch.cs:50 | `bool` | Set false to remove player from bench |
| `cState.*` (many fields) | EpisodeResetter.cs:489–550 | `bool` | All Boolean CharacterState flags zeroed on soft reset |
| `cState.onGround` | EpisodeResetter.cs:499 | `bool` | Set true to start reset in grounded state |
| `cState.invulnerable` | EpisodeResetter.cs:443 | `bool` | Cleared after reset |
| `hero_state` | EpisodeResetter.cs:663 | `ActorStates` | Set to `ActorStates.idle` |
| `transform.position` | EpisodeResetter.cs:479 | `Vector3` | Teleported to spawn position on soft reset |
| `acceptingInput` | EpisodeResetter.cs:665 | `bool` | Set true |
| `controlReqlinquished` | EpisodeResetter.cs:552 | `bool` | Set false |
| `dashingDown` | EpisodeResetter.cs:627 | `bool` | Set false |
| `touchingWallL`, `touchingWallR`, `wallLocked` | EpisodeResetter.cs:592–594 | `bool` | Cleared on reset |
| `parryInvulnTimer` | EpisodeResetter.cs:563 | `float` | Zeroed on reset |

### Methods Called

| Method | Location | Semantics |
|--------|----------|-----------|
| `GetComponent<Rigidbody2D>()` | GameStateCollector.cs:21, EpisodeResetter.cs:481 | Retrieves the physics body |
| `CanDash()` | GameStateCollector.cs:32 | Returns true when dash action is available |
| `CanAttack()` | GameStateCollector.cs:35 | Returns true when attack action is available |
| `StopAllCoroutines()` | EpisodeResetter.cs:458 | Halts all running coroutines on the player |
| `GetComponents<PlayMakerFSM>()` | EpisodeResetter.cs:684 | Enumerates all FSMs on the player |
| `MaxHealth()` | EpisodeResetter.cs:667 | Restores HP to maximum |
| `FaceRight()` | EpisodeResetter.cs:675 | Forces player to face right |
| `RegainControl()` | SkipIntroPatch.cs:51 | Restores player control after cutscene |
| `AcceptInput()` | SkipIntroPatch.cs:52 | Enables input acceptance |
| `StartAnimationControlToIdle()` | SkipIntroPatch.cs:53 | Plays idle animation |
| `Die()` | PlayerDeathPatch.cs:9 | **Patched to no-op** — player death is suppressed |

### Private Fields Accessed via Reflection (on `HeroController`)

The following private fields are accessed via `System.Reflection.FieldInfo.GetValue/SetValue` in `EpisodeResetter.cs`. They represent timers, counters, and boolean flags that must be zeroed on soft reset. In the simulator these would be explicit state variables.

| Private Field Name | Type | Semantics |
|--------------------|------|-----------|
| `hazardRespawnRoutine` | `Coroutine` | Running hazard respawn coroutine |
| `hazardInvulnRoutine` | `Coroutine` | Running invulnerability coroutine |
| `takeDamageCoroutine` | `Coroutine` | Running take-damage coroutine |
| `doingHazardRespawn` | `bool` | Hazard-respawn in progress flag |
| `recoilRoutine` | `Coroutine` | Running recoil coroutine |
| `tilemapTestCoroutine` | `Coroutine` | Tilemap overlap test coroutine |
| `frostedFadeOutRoutine` | `Coroutine` | Frost effect fade coroutine |
| `cocoonFloatRoutine` | `Coroutine` | Float-up effect coroutine |
| `attack_time` | `float` | Time since last attack started |
| `dash_timer` | `float` | Dash duration timer |
| `dashCooldownTimer` | `float` | Cooldown before next dash |
| `nailChargeTimer` | `float` | Nail/weapon charge timer |
| `preventCastByDialogueEndTimer` | `float` | Post-dialogue cast lockout |
| `airDashed` | `bool` | Whether air dash has been used |
| `bounceTimer` | `float` | Wall/floor bounce timer |
| `recoilTimer` | `float` | Duration of current recoil |
| `shadowDashTimer` | `float` | Shadow dash variant timer |
| `jumpQueuing` / `doubleJumpQueuing` / `attackQueuing` / `dashQueuing` / `jumpReleaseQueuing` / `harpoonQueuing` / `toolThrowQueueing` | `bool` | Input queue flags |
| `wallSlidingL` / `wallSlidingR` | `bool` | Per-side wall-slide flags |
| `doubleJumped` / `wallJumpedL` / `wallJumpedR` / `hardLanded` / `didAirHang` | `bool` | Aerial state flags |
| `attack_cooldown` / `attackDuration` | `float` | Attack timing |
| `recoilStepsLeft` / `recoilVelocity` | `int/float` | Physics recoil state |
| `jump_steps` / `jumped_steps` / `doubleJump_steps` | `int` | Jump physics step counters |
| `wallLockSteps` / `wallJumpChainStepsLeft` / `wallUnstickSteps` | `int` | Wall-interaction step counters |
| `currentWalljumpSpeed` / `walljumpSpeedDecel` | `float` | Wall jump speed |
| `landingBufferSteps` / `ledgeBufferSteps` / `headBumpSteps` | `int` | Buffered-input step counts |
| `dashQueueSteps` / `jumpQueueSteps` / `doubleJumpQueueSteps` / `jumpReleaseQueueSteps` / `attackQueueSteps` / `harpoonQueueSteps` / `toolThrowQueueSteps` | `int` | Queued action step counters |
| `hardLandingTimer` / `dashLandingTimer` / `hardLandFailSafeTimer` | `float` | Landing timers |
| `lookDelayTimer` | `float` | Look-up/down input delay |
| `wallslideClipTimer` / `wallStickTimer` / `wallClingCooldownTimer` | `float` | Wall interaction timers |
| `hazardDeathTimer` / `floatingBufferTimerField` | `float` | Hazard/float timers |
| `softLandTime` | `int` | Soft landing timer |
| `canSoftLand` | `bool` | Whether soft landing is available |
| `fallRumble` / `fallCheckFlagged` | `bool` | Fall detection flags |
| `wallSlashing` | `bool` | True while doing a wall slash |
| `evadingDidClash` | `bool` | True if evade met a clash |
| `currentGravity` / `prevGravityScale` | `float` | Gravity state |
| `startWith*` (30 fields) | `bool` | Startup flags for the state machine — determine which animation/action begins the next update |
| `dashCurrentFacing` | `bool` | Facing direction at dash start |
| `queued*` flags | `bool` | Queued transition flags |
| `evasionByHitRemaining` / `rapidBulletTimer` / `rapidBulletCount` / `rapidBombTimer` / `rapidBombCount` / `rapidStormTimer` / `rapidStormCount` | `float/int` | Anti-spam hit counters (these are on `HealthManager` for the boss but reflected names match) |

---

## PlayerData

Accessed via `HeroController.instance.playerData`. Not a standalone component; it is a plain data object attached to the player.

| Member | Location | Type | Semantics |
|--------|----------|------|-----------|
| `health` | GameStateCollector.cs:28, EpisodeResetter.cs:1344 | `int` | Current HP (0 = dead) |
| `maxHealth` | GameStateCollector.cs:29, EpisodeResetter.cs:1344 | `int` | Maximum HP |
| `silk` | GameStateCollector.cs:30, EpisodeResetter.cs:668, 1345 | `int` | Silk resource (spell/ability energy) |
| `silkRegenMax` | EpisodeResetter.cs:668, 1345 | `int` | Max silk |
| `isInvincible` | GameStateCollector.cs:34, EpisodeResetter.cs:419, 441 | `bool` | Global invincibility flag |
| `encounteredLaceTower` | EpisodeResetter.cs:670, 1341 | `bool` | Progress flag |
| `defeatedLaceTower` | EpisodeResetter.cs:671, 1342 | `bool` | Progress flag |
| `laceTowerDoorOpened` | EpisodeResetter.cs:672, 1343 | `bool` | Progress flag |
| `atBench` | SkipIntroPatch.cs:41, 50 | `bool` | Sitting-at-bench flag |

---

## CharacterState (`cState`)

`HeroController.cState` is a struct/class holding Boolean movement-state flags.

All flags are documented with every access in EpisodeResetter.cs (lines 489–550). The simulator must track at minimum:

| Flag | Semantics |
|------|-----------|
| `onGround` | Grounded contact |
| `facingRight` | Facing direction |
| `invulnerable` | I-frame active |
| `dead` | Death state |
| `hazardDeath` | Hazard-kill state |
| `recoiling` / `recoilingLeft` / `recoilingRight` / `recoilingDrill` / `recoilFrozen` | Recoil sub-states |
| `hazardRespawning` / `transitioning` | Scene-transition states |
| `falling` / `jumping` / `doubleJumping` | Aerial states |
| `dashing` / `backDashing` / `preventDash` / `dashCooldown` | Dash states |
| `attacking` / `nailCharging` / `parrying` / `altAttack` / `upAttacking` / `downAttacking` / `parryAttack` | Attack states |
| `wallSliding` / `wallClinging` / `wallJumping` | Wall states |
| `bouncing` / `shroomBouncing` / `downSpiking` / `downSpikeAntic` / `downSpikeBouncing` / `downSpikeRecovery` | Bounce/spike states |
| `casting` / `castRecoiling` / `evading` / `floating` / `shuttleCock` | Ability states |
| `lookingUp` / `lookingUpAnim` / `lookingDown` / `lookingDownAnim` | Look states |
| `touchingWall` / `isSprinting` / `isBackSprinting` / `isBackScuttling` | Movement qualifiers |
| `whipLashing` / `isTriggerEventsPaused` / `inConveyorZone` / `onConveyor` / `onConveyorV` | Environment interaction |
| `isTouchingSlopeLeft` / `isTouchingSlopeRight` | Slope contact |
| `isToolThrowing` / `mantleRecovery` / `swimming` / `inUpdraft` / `fakeHurt` / `willHardLand` | Miscellaneous |
| `downSpikeBouncingShort` | Short bounce variant |

---

## HealthManager

`HealthManager` is attached to any entity that can take damage — both the player's boss object and random scene enemies.

### Properties / Fields — Observation

| Member | Location | Type | Semantics |
|--------|----------|------|-----------|
| `hp` | BossStateManager.cs:130,134, GameStateCollector.cs:76 | `int` | Current entity HP |
| `name` (via `GameObject.name`) | BossStateManager.cs:131,132 | `string` | GameObject name — used to identify the boss |
| `transform.position` | GameStateCollector.cs:70,71, EpisodeResetter.cs:706 | `Vector3` | World position |
| `transform.localScale.x` | GameStateCollector.cs:82 | `float` | x-scale; negative means facing left |

### Methods — Observation / Component Access

| Method | Location | Semantics |
|--------|----------|-----------|
| `GetComponent<Rigidbody2D>()` | BossStateManager.cs:139 | Get physics body |
| `GetComponent<PlayMakerFSM>()` | BossStateManager.cs:140 | Get the boss's primary FSM |
| `GetComponent<tk2dSpriteAnimator>()` | BossStateManager.cs:141 | Get the boss's sprite animator |
| `GetComponentsInChildren<T>(true)` | EpisodeResetter.cs: multiple lines | Retrieve all child components of various types for reset |
| `CancelAllLagHits()` | EpisodeResetter.cs:718 | Cancel pending lag-hit damage events |
| `tinkTimer` (public field) | EpisodeResetter.cs:910 | `float` — tink (parry) timer, zeroed on reset |

### Methods — Actuation (Patched)

| Method | Location | Semantics |
|--------|----------|-----------|
| `Die(...)` (3 overloads) | BossDeathPatch.cs:10–33 | **All patched to no-op for the boss** — boss death is suppressed to allow episode continuation |

### Private Fields Accessed via Reflection

| Private Field | Type | Semantics |
|---------------|------|-----------|
| `evasionByHitRemaining` | `float` | Evasion budget — set to -1 on reset |
| `rapidBulletTimer` / `rapidBulletCount` | `float` / `int` | Rapid-bullet hit-rate limiter |
| `rapidBombTimer` / `rapidBombCount` | `float` / `int` | Rapid-bomb hit-rate limiter |
| `rapidStormTimer` / `rapidStormCount` | `float` / `int` | Rapid-storm hit-rate limiter |
| `hasTakenDamage` | `bool` | Whether entity was hit this encounter |
| `invincible` | `bool` | Invincibility flag |
| `invincibleFromDirection` | `int` | Directional invincibility |
| `directionOfLastAttack` | `int` | Direction of last received attack |
| `notifiedBattleScene` | `bool` | Whether the battle scene has been notified |
| `damageTagHitsLeftTracker` | `IDictionary` | Per-tag hit counter |
| `tagDamageTaker` | `TagDamageTaker` | Tag-damage accounting object |
| `runningSingleLagHits` | `IDictionary` | Running lag-hit tracker |
| `lastAttackType` | `AttackTypes` | Type of last attack |
| `lastHitInstance` | `HitInstance` | Last hit data |

### Static Methods

| Method | Location | Semantics |
|--------|----------|-----------|
| `Object.FindObjectsByType<HealthManager>(FindObjectsSortMode.None)` | BossStateManager.cs:128 | Scene scan to locate the boss — **expensive, called only at episode start** |

---

## PlayMakerFSM

`PlayMakerFSM` is PlayMaker's finite-state-machine component. Attached to both the boss and several child GameObjects.

### Properties — Observation

| Member | Location | Type | Semantics |
|--------|----------|------|-----------|
| `ActiveStateName` | BossStateManager.cs:175, BossProjectileManager.cs:37,139 | `string` | Name of the currently active FSM state |
| `FsmName` | EpisodeResetter.cs:984 | `string` | Name of this FSM (e.g. "Control", "Multicircle") |
| `FsmStates` | EpisodeResetter.cs:689,991,1001,1026,1036,1054 | `FsmState[]` | All states in this FSM |
| `FsmVariables.FindFsmBool(name)` | EpisodeResetter.cs:1185 | `FsmBool` | Look up a named boolean variable |
| `FsmVariables.FindFsmInt(name)` | EpisodeResetter.cs:1190 | `FsmInt` | Look up a named integer variable |
| `FsmVariables.FindFsmFloat(name)` | EpisodeResetter.cs:1195 | `FsmFloat` | Look up a named float variable |
| `FsmVariables.FindFsmString(name)` | EpisodeResetter.cs:1200 | `FsmString` | Look up a named string variable |

### Methods — Actuation

| Method | Location | Semantics |
|--------|----------|-----------|
| `SetState(string)` | EpisodeResetter.cs:993,1003,1028,1037,1055,1060 | Force the FSM into a specific named state |
| `Fsm.KillDelayedEvents()` | EpisodeResetter.cs:982 | Cancel all pending delayed FSM events |

### Named FSM Variables Set on Reset (Boss "Control" FSM)

See `ResetPhaseFsmVariables()` in EpisodeResetter.cs (lines 1096–1181). Full list of variables:

**Booleans:** `Above Wallcling Min`, `Can Bomb Slash`, `Counter Range`, `Counter Ready`, `CrossSlashing Hero`, `Did P2 Shift`, `Did P3 Shift`, `Do Pose`, `Evade Bomb`, `Facing Right`, `Floor Ahead`, `Hero Is R`, `Hero on Wall`, `Hornet Dead`, `Not Above Hero`, `Right Side`, `Wall Ahead`, `Will Counter`, `Will CrossSlash`, `In Evade Range`, `Can Evade`, `Evade Floor Safe`, `Evade Flipper`

**Integers:** `Ct Charge`, `Ct Combo`, `Ct CrossSlash`, `Ct Evade`, `Ct J Slash`, `Evade Attempts`, `Hops`, `Ms Charge`, `Ms Combo`, `Ms Evade`, `Ms J Slash`, `Ct Bomb Slash`, `Ms Bomb Slash`, `Phase` (reset to 1), `P2 HP` (reset to 600), `P3 HP` (reset to 320), `Rage Slashes`, `Charges Performed`

**Floats:** `Angle`, `Angle Max`, `Angle Min`, `Anim Start Time`, `Bomb Max X/Y`, `Bomb Min X/Y`, `Bomb X/Y`, `Centre X`, `Charge Time`, `Combo Slash Speed`, `Counter Pause`, `CrossSlash Antic Time`, `Distance`, `Double Strike Pause`, `Gravity`, `Hero X`, `Idle Time`, `Land Y`, `Self X`, `Stun Timer`, `Target Distance`, `Tele Offset`, `Tele Out Floor`, `Tele X`, `Velocity Y`, `Wallcling Min Y`, `X Scale`, `Arena Plat Bot Y`, `Fall Check Speed`

**Strings:** `Cross Slash Anim`, `Next Event` (reset to "COMBO"), `Anim`

---

## Rigidbody2D

Unity's 2D physics rigid body. Used for both player and boss.

### Properties — Observation

| Member | Location | Type | Semantics |
|--------|----------|------|-----------|
| `linearVelocity.x` | GameStateCollector.cs:25,73 | `float` | X velocity (units/sec) |
| `linearVelocity.y` | GameStateCollector.cs:26,74 | `float` | Y velocity |

### Fields — Actuation

| Member | Location | Type | Semantics |
|--------|----------|------|-----------|
| `linearVelocity` | EpisodeResetter.cs:484,712 | `Vector2` | Set to `Vector2.zero` on reset |
| `angularVelocity` | EpisodeResetter.cs:485,713 | `float` | Set to 0 on reset |
| `gravityScale` | EpisodeResetter.cs:486 | `float` | Reset to `DEFAULT_GRAVITY` |

---

## tk2dSpriteAnimator

TextMesh Pro / 2D Toolkit sprite animator. Drives frame-based sprite animations.

### Properties — Observation

| Member | Location | Type | Semantics |
|--------|----------|------|-----------|
| `CurrentClip` | GameStateCollector.cs:49,87 | `tk2dSpriteAnimationClip` | Currently playing clip |
| `CurrentClip.name` | GameStateCollector.cs:52,90 | `string` | Clip name — mapped to `BossAnimationState` / `PlayerAnimationState` enum |
| `CurrentClip.frames` | GameStateCollector.cs:50,53,88,92 | `tk2dSpriteAnimationFrame[]` | Frame array; `.Length` used for progress calculation |
| `CurrentFrame` | GameStateCollector.cs:54,92 | `int` | Current frame index; `CurrentFrame / frames.Length` = animation progress ∈ [0,1] |

The player's animator is reached via `HeroController.instance.animCtrl.animator` (GameStateCollector.cs:48).  
The boss's animator is stored directly in `BossStateManager.CurrentBossAnimator` (GameStateCollector.cs:84).

---

## GameManager

`GameManager.instance` is the scene-level singleton managing game flow, scene loading, and time control.

### Properties / Fields — Observation

| Member | Location | Type | Semantics |
|--------|----------|------|-----------|
| `instance` (static) | SharedMemoryManager.cs:327, Plugin.cs:71,73, EpisodeResetter.cs:463,1357, SkipIntroPatch.cs:25,96, PlayerDeathPatch.cs:17 | `GameManager` | Singleton reference |
| `gameSettings.particleEffectsLevel` | Plugin.cs:73 | `int` | Particle level — set to 0 for performance |

### Methods — Actuation

| Method | Location | Semantics |
|--------|----------|-----------|
| `StartCoroutine(IEnumerator)` | SharedMemoryManager.cs:347,352, EpisodeResetter.cs:463 | Launches a coroutine on the GameManager's MonoBehaviour |
| `StopCoroutine(Coroutine)` | EpisodeResetter.cs:463 | Stops a specific coroutine |
| `BeginSceneTransition(SceneLoadInfo)` | EpisodeResetter.cs:1357 | Initiates a full scene load (hard reset path) |
| `FreezeMoment(...)` | FreezeMomentPatch.cs:12–44 | **All overloads patched to no-op** — hit-stop freeze moments are suppressed to avoid training disruption |
| `FreezeMomentGC(...)` | FreezeMomentPatch.cs:37 | Same — patched to no-op |
| `PlayerDead()` | PlayerDeathPatch.cs:16 | **Patched to no-op** — game-over handling suppressed |

---

## DamageHero

`DamageHero` is a component that applies damage to the player on contact. Attached to boss hitboxes and hazards.

### Usage — Observation

| Access | Location | Semantics |
|--------|----------|-----------|
| `GetComponent<DamageHero>()` | RaycastSensor.cs:94 | Identifies a collider as a hazard in the raycast sensor |
| `GetComponentsInChildren<DamageHero>(true)` | EpisodeResetter.cs:848 | Enumerate all boss damagers for reset |

### Methods — Actuation

| Method | Location | Semantics |
|--------|----------|-----------|
| `DamageHero.ResetRecordedDamagers()` (static) | EpisodeResetter.cs:846, EpisodeResetter.cs:1276 | Clears the engine's record of which DamageHero instances have dealt damage this frame |
| `StopCoroutine(Coroutine)` | EpisodeResetter.cs:854 | Stops running nail-clash coroutine |

### Private Fields via Reflection

| Field | Type | Semantics |
|-------|------|-----------|
| `preventClashTink` | `bool` | Prevents the tink (parry) sound from playing |
| `damageAllowedTime` | `double` | Timestamp after which damage is allowed again |
| `nailClashRoutine` | `Coroutine` | Running clash coroutine |
| `cancelAttack` | `bool` | Flag to cancel the current attack |

---

## Recoil

Physics recoil component attached to the boss.

### Private Fields via Reflection

| Field | Type | Semantics |
|-------|------|-----------|
| `state` | `int` | Recoil state enum value |
| `recoilTimeRemaining` | `float` | Time left in recoil |
| `recoilSpeed` | `float` | Speed of recoil movement |
| `isRecoilSweeping` | `bool` | Sweeping vs. linear recoil |
| `previousRecoilAngle` | `float` | Previous angle (for sweeping) |

### Public Properties — Actuation

| Member | Location | Type | Semantics |
|--------|----------|------|-----------|
| `SkipFreezingByController` | EpisodeResetter.cs:876 | `bool` | Set false on reset |
| `IsLeftBlocked` / `IsRightBlocked` | EpisodeResetter.cs:877,878 | `bool` | Directional block flags, cleared on reset |

---

## Additional Types (Supporting Cast)

These types appear in EpisodeResetter.cs for boss-reset plumbing. They are not primary observation targets but the simulator must model their existence if it tracks hit/effect state.

| Type | Location | Usage |
|------|----------|-------|
| `SpriteFlash` | EpisodeResetter.cs:793–811 | Visual flash effect; `CancelFlash()` called on reset |
| `InvulnerablePulse` | EpisodeResetter.cs:813–820 | Invulnerability pulse effect; `StopInvulnerablePulse()` called |
| `AlertRange` | EpisodeResetter.cs:822–831 | Aggro-range sensor; `unalertTimer`, `isHeroInRange`, `haveLineOfSight`, `hasHero` zeroed |
| `EnemyDeathEffects` | EpisodeResetter.cs:834–842 | Death VFX; `didFire`, `isBlackThreaded` zeroed |
| `EnemyHitEffectsRegular` | EpisodeResetter.cs:783–791 | Hit VFX; `didFireThisFrame`, `isBlackThreaded` zeroed |
| `TriggerEnterEvent` | EpisodeResetter.cs:951–971 | Trigger-enter event dispatcher; all state zeroed |
| `DamageEnemies` | EpisodeResetter.cs:758–769 | Player-side damage-dealer; `ClearLists()`, `ClearPreventDamage()` called |
| `HazardRespawnMarker` | EpisodeResetter.cs:1278–1284 | Hazard respawn point; `StopAllCoroutines()` called |
| `HazardRespawnTrigger` | EpisodeResetter.cs:1287–1293 | Hazard trigger zone; `StopAllCoroutines()` called |
| `TagDamageTaker` | EpisodeResetter.cs:902 | Tag-based damage accounting; `ClearTagDamage()` called |
| `BouncePod` | EpisodeResetter.cs:356 | Static counter `_lastAttackCount` set to -1 |
| `RandomEvent` / `ArrayGetRandom` / `PlayRandomSound` / `RandomInt` | EpisodeResetter.cs:1076–1093 | PlayMaker random-action types; `lastIndex` / `lastEventIndex` reset to -1 for determinism |

---

## Summary Table — Simulator Contract

| Type | Min Fields to Simulate | Notes |
|------|----------------------|-------|
| `HeroController` | position (x,y), velocity (x,y), health, silk, grounded, facingRight, canDash, canAttack, invincible, animState, animProgress | Plus the ~50 private timer/flag fields if soft-reset is needed |
| `PlayerData` | health, maxHealth, silk, silkRegenMax, isInvincible, progress flags | Embedded in HeroController |
| `CharacterState` | All ~45 boolean flags | Full list in EpisodeResetter.cs:489–550 |
| `HealthManager` (boss) | hp, position (x,y), localScale.x | Must suppress `Die()` |
| `PlayMakerFSM` (boss) | `ActiveStateName`, named variables | ~25 bool, ~18 int, ~30 float, 3 string vars |
| `Rigidbody2D` (boss) | linearVelocity (x,y) | Write: zero on reset |
| `tk2dSpriteAnimator` | CurrentClip.name, CurrentFrame, frames.Length | For both player and boss |
| `DamageHero` | Component presence on colliders | Needed for hazard classification in raycast |
| `GameManager` | Scene load, coroutine host | FreezeMoment patched away |
