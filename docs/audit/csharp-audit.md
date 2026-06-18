# C# BepInEx Plugin Audit

> **Status: MIXED.**
>
> - **§3 (observation spec) and §4 (actuation spec) are REFERENCE** — they
>   define the frozen wire contract the Madrona sim reproduces byte-for-byte.
>   Consult during Phase 5 / Phase 6 / Phase 7 implementation.
> - **§1, §2, §5, §6, §7 (per-step waste analysis, reset latency, IPC
>   improvements, NoFx manager, incomplete-resets report) are HISTORICAL.**
>   They justified why the Unity training path was replaced. They are
>   condensed below to a one-paragraph summary.
>
> For current spec, read `docs/framework-requirements.md`.

---

## 1. Historical summary — why the Unity training path was replaced

The plugin achieved ~150–380 steps/sec/instance. Per-step wall-clock was **2.6–6.6 ms**, dominated by:

- `BossProjectileManager.RefreshProjectileCache()` — full `FindObjectsByType<GameObject>()` scene scan every step, 2–5 ms. Addressed in Phase 1 by event-hooking projectile spawn/despawn; pre-allocated raycast buffers at the same time.
- `WaitForFixedUpdate` × `FramesPerStep=2` at timescale=10 — ~3.3 ms, structural (this IS the step).
- Everything else (IPC write, reflection-heavy reset, GetComponent-per-rayhit, Harmony hook overhead) was in the noise by comparison.

The `EpisodeResetter.cs` soft reset path (~116 `FieldInfo.SetValue` calls + 3× `WaitForEndOfFrame`) took ~60–70 ms per reset. Hard reset (scene unload/reload) cost 500–2000 ms.

The plugin is now demoted to **oracle mode**: it still collects `GameState` and records traces via `TraceRecorder.cs`, but no longer participates in bulk training. The parts being deleted or replaced in the Madrona sim:

- `EpisodeResetter.cs` (1532 LoC reflection reset) → one memcpy from a baked reference state.
- `BossProjectileManager.cs` full-scan cache → projectiles become fixed-size ECS ring-buffer components (see `phase5-physics-requirements.md` §2).
- All the rendering/audio disabling (`NoFxManager.cs`, `AudioSourcePatch.cs`, `FreezeMomentPatch.cs`, …) is irrelevant in a headless sim.

Everything below §3 onward is the contract the sim must honour. Consult those sections.

---

## 2. Harmony patches still in play

The plugin still applies these (all survive because the plugin still runs as the oracle):

- `ButtonControlPatch` / `GetKeyPatch` — routes `ActionManager` binary flags into Unity's input system.
- `AudioSourcePatch` — every `AudioSource.Play*` → no-op.
- `FreezeMomentPatch` — `GameManager.FreezeMoment()` → empty coroutine.
- `SkipIntroPatch`, `BossDeathPatch`, `PlayerDeathPatch`, `CameraRenderScaledPatch`, `CursorLockPatch`, `SteamDisablePatch`.
- `NoFxManager` disables shadows, particles, post-processing, real-time reflections, etc., and mutes audio globally.

None of these need porting to the sim. The sim doesn't render or play audio.

---

## 3. Observation Specification (Fidelity Requirements) — REFERENCE

### 3.1 GameState Struct (SharedMemoryManager.cs:132–166)
```csharp
public unsafe struct GameState {
  // Player (11 floats + 3 ints + 5 bytes = 52 bytes)
  public float playerPosX, playerPosY, playerVelX, playerVelY;
  public int playerHealth, playerMaxHealth, playerSilk;
  public int playerAnimationState;
  public float playerAnimationProgress;
  public byte playerGrounded, playerCanDash, playerFacingRight, playerInvincible, playerCanAttack;

  // Boss (9 floats + 3 ints + 1 byte = 48 bytes)
  public float bossPosX, bossPosY, bossVelX, bossVelY;
  public int bossHealth, bossMaxHealth, bossPhase;
  public int bossAnimationState;
  public float bossAnimationProgress;
  public byte bossFacingRight;

  // Episode metadata (3 floats + 2 bytes = 14 bytes)
  public float episodeTime;
  public byte terminated, truncated;

  // Raycast observations (32×4 floats + 32×4 ints = 512 bytes)
  public fixed float raycastDistances[32];
  public fixed int raycastHitTypes[32];
}
```
**Total: 626 bytes per observation**

### 3.2 Player Observations (GameStateCollector.cs:18–62)
**Position & Velocity:**
- `playerPosX/Y`: from `HeroController.transform.position` (world space)
- `playerVelX/Y`: from `Rigidbody2D.linearVelocity` (m/s)

**Health & Resources:**
- `playerHealth`: from `HeroController.playerData.health` (0–maxHealth)
- `playerMaxHealth`: from `HeroController.playerData.maxHealth` (constant)
- `playerSilk`: from `HeroController.playerData.silk` (0–maxSilk)

**Capability Flags:**
- `playerGrounded`: from `HeroController.cState.onGround` (bool → byte)
- `playerCanDash`: from `HeroController.CanDash()` (ability check)
- `playerCanAttack`: from `HeroController.CanAttack()` (ability check)
- `playerFacingRight`: from `HeroController.cState.facingRight` (bool → byte)
- `playerInvincible`: from `HeroController.playerData.isInvincible` (bool → byte)

**Animation State:**
- `playerAnimationState`: from `PlayerAnimationMapper.GetAnimationState(clip.name)`
  - Enum: 83 states (0–82, see Constants.RayCount:30)
  - Maps animator clip name → enum (hardcoded dict in PlayerAnimationMapper)
- `playerAnimationProgress`: animator.CurrentFrame / clip.frames.Length ∈ [0, 1]

**Standalone simulator must reproduce:**
- Same position/velocity reporting (physics engine output)
- Same health/silk/capability logic (all rule-based)
- Same 83 animation states + mapping (requires clip name dict)
- Same playerData struct fields
- Same cState flags (onGround, facingRight, etc.)

### 3.3 Boss Observations (GameStateCollector.cs:65–106)
**Position & Velocity:**
- `bossPosX/Y`: from `BossStateManager.CurrentBoss.transform.position`
- `bossVelX/Y`: from `BossStateManager.CurrentBossRb.linearVelocity` (null-safe)

**Health & Phase:**
- `bossHealth`: from `BossStateManager.CurrentBoss.hp`
- `bossMaxHealth`: from `Constants.LaceBossMaxHealth` (800)
- `bossPhase`: from `BossStateManager.UpdateBossPhase()` + `CurrentPhase`
  - Phase detection logic: health thresholds (P2 at 600 HP, P3 at 320 HP; see `lace-fsm.md`)

**Animation State:**
- `bossAnimationState`: mapped from `BossStateManager.AnimationMap` (71 entries, see `lace-fsm.md`)
- `bossAnimationProgress`: animator.CurrentFrame / clip.frames.Length

**Direction:**
- `bossFacingRight`: from `boss.transform.localScale.x > 0` (scale-based facing)

**Standalone simulator must reproduce:**
- Boss AI state machine + animation sequences
- Health damage mechanics
- Phase transitions (infer from BossStateManager.UpdateBossPhase)
- Facing/scale synchronization

### 3.4 Raycast Sensor Observations (RaycastSensor.cs:53–118)
**32 rays in all directions:**
- **Ray configuration:**
  - 32 rays equally spaced: angle = (360 / 32) × i = 11.25° increments
  - Max distance: 25.0m (Constants.MaxRayDistance)
  - Origin: player position (world space)
  - Normalized distance: distance / 25.0 ∈ [0, 1]

- **Hit types (RaycastHitType enum):**
  - 0: None (no hit within 25m)
  - 1: Terrain (TerrainLayer=8)
  - 2: Enemy (EnemyLayer=11, or has HealthManager component)
  - 3: Projectile (ProjectileLayer=12)
  - 4: Hazard (has DamageHero component)
  - 5: BossProjectile (tracked by BossProjectileManager)

- **Detection logic:**
  - `Physics2D.RaycastNonAlloc()` for Terrain/Enemy/Projectile layers
  - Component checks: `GetComponent<HealthManager>()` → Enemy; `GetComponent<DamageHero>()` → Hazard
  - Boss projectiles: circle intersection (boss summons circles with radius 3.0m)
  - **Caveat:** Ignores layer-based filtering in favor of component checks → loose coupling, may pick up unintended GameObjects

**Standalone simulator must reproduce:**
- 32-ray sensor in all directions
- Collider/terrain detection
- Boss projectile detection (needs projectile spawning simulation)
- Component-based hit type classification

### 3.5 Episode Metadata
- `episodeTime`: `Time.time - episodeStartTime` (elapsed seconds)
- `terminated`: (unused, always 0 in collect)
- `truncated`: (unused, always 0 in collect)

---

## 4. Actuation Specification (Control Inputs) — REFERENCE

### 4.1 ActionManager.cs (Lines 9–36)
**Agent control flags (all bool):**
```csharp
public static bool IsLeftPressed { get; set; }
public static bool IsRightPressed { get; set; }
public static bool IsUpPressed { get; set; }
public static bool IsDownPressed { get; set; }
public static bool IsJumpPressed { get; set; }
public static bool IsAttackPressed { get; set; }
public static bool IsDashPressed { get; set; }
public static bool IsClawlinePressed { get; set; }
public static bool IsSkillPressed { get; set; }
public static bool IsHealPressed { get; set; }
```
**Total: 10 discrete actions (0 or 1)**

### 4.2 CommandData Struct (SharedMemoryManager.cs:114–128)
**IPC wire format:**
```csharp
public struct CommandData {
  public int commandType;        // 0=None, 1=Step, 2=Reset
  public byte left, right, up, down;
  public byte jump, attack, dash, clawline, skill, heal;
  public int commandReady;       // 1=ready, 0=processed
}
```
**Total: 28 bytes**

### 4.3 Input Patching (ActionManager.cs, ButtonControlPatch, GetKeyPatch)
**Two patching mechanisms:**

1. **ButtonControl.isPressed (NewInputSystem)** (Lines 39–84):
   - Intercepts `InputSystem.ButtonControl.isPressed` getter
   - Matches key name: "leftArrow", "rightArrow", "z" (jump), "x" (attack), "c" (dash), "s" (clawline), "f" (skill), "a" (heal)
   - Bypasses hardware input when `ActionManager.IsAgentControlEnabled == true`

2. **Input.GetKey(KeyCode) (LegacyInputSystem)** (Lines 99–142):
   - Intercepts `Input.GetKey()` with KeyCode enum
   - Matches: KeyCode.LeftArrow, KeyCode.Z, KeyCode.X, KeyCode.C, KeyCode.S, KeyCode.F, KeyCode.A

**Control mapping:**
| Action | InputSystem | LegacyInput |
|--------|-------------|------------|
| Left | "leftArrow" | KeyCode.LeftArrow |
| Right | "rightArrow" | KeyCode.RightArrow |
| Up | "upArrow" | KeyCode.UpArrow |
| Down | "downArrow" | KeyCode.DownArrow |
| Jump | "z" | KeyCode.Z |
| Attack | "x" | KeyCode.X |
| Dash | "c" | KeyCode.C |
| Clawline | "s" | KeyCode.S |
| Skill | "f" | KeyCode.F |
| Heal | "a" | KeyCode.A |

**Standalone simulator must reproduce:**
- 10 discrete binary actions
- Same action-to-movement mapping (horizontal/vertical 2D movement, jump, attack chain, dash, abilities)
- Same ability-to-key bindings

---

## 5. Standalone Simulator Fidelity Checklist — REFERENCE

Every item here must be reproduced by the Madrona sim to pass the oracle diff (thresholds in `decompilation-plan.md` §7 and `framework-requirements.md` §5):

- [ ] 10 discrete binary action inputs (left, right, up, down, jump, attack, dash, clawline, skill, heal)
- [ ] Player position + velocity (2D, physics-based)
- [ ] Player health, silk, grounded, dash/attack capability, facing direction, invincibility state
- [ ] Player animation state (83 distinct states) + progress
- [ ] Boss position + velocity
- [ ] Boss health (damage mechanics, 800 max)
- [ ] Boss phase transitions (P2 @ 600 HP, P3 @ 320 HP)
- [ ] Boss animation state (71 states — see `lace-fsm.md`) + progress
- [ ] 32-ray sensor in all directions, max 25m, normalized ∈ [0, 1]
- [ ] Raycast hit types: None, Terrain, Enemy, Projectile, Hazard, BossProjectile
- [ ] Boss projectile types: Lace circle slash (radius 3.0m), Cross Slash (radius 5.0m)
- [ ] Soft reset (teleport, clear timers, preserve HP/phase)
- [ ] Hard reset (reload from checkpoint or scene)
- [ ] Episode time tracking (elapsed seconds)

---

## 6. Key metrics of the original Unity pipeline (historical)

Kept so the "why we switched" numbers survive.

| Metric | Value |
|--------|-------|
| Per-step wall-clock | 2.6–6.6 ms (RefreshProjectileCache dominates) |
| Max step rate per instance | ~150–380 steps/sec |
| Observation size | 626 bytes |
| Action space size | 10 (discrete binary) |
| Soft reset time | ~60–70 ms |
| Hard reset time | ~500–2000 ms |
| GC per step | ~256 bytes from `RaycastSensor` array allocations (fixed in Phase 1) |
| Player animation states | 83 |
| Boss animation states | 71 (0..69 named + 70=Unknown) |
| Max boss projectile types | 2 (lace_circle_slash r=3.0m, Cross Slash r=5.0m) |
