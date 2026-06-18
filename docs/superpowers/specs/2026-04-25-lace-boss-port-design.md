# Lace Boss Port — Design Spec

Full port of Lace's 206-state PlayMaker FSM + combat mechanics into the Madrona C++ simulator. Source material: ILSpy decompilation of Assembly-CSharp.dll (2034 files) and UnityPy extraction of the "Control" FSM from `scenes_scenes_scenes` bundle (path_id=13742).

## 1. ECS Components

### BossKinematics
```
float posX, posY, velX, velY
float gravity              // 2.0 (FSM variable)
int16_t facingRight        // +1 or -1
int16_t isKinematic        // 1 during tele/dive (no physics)
```

### BossFSM
Two-level state: `(categoryId, subStateId, frameInState)`.

```
uint8_t  categoryId        // top-level: Idle, Combo, Charge, JSlash, etc.
uint8_t  subStateId        // within category: antic, active, recover, etc.
int16_t  frameInState      // tick counter, decremented per substep
int16_t  phase             // 1-4
int16_t  hp                // 800 max
int16_t  stunGauge         // accumulates toward threshold, triggers STUN

// Attack selection state (SendRandomEventV4)
uint8_t  lastAttack        // category of last attack picked
uint8_t  consecutiveCount  // how many times same attack picked
uint8_t  missedCounts[8]   // per-attack missed counter (max 8 attack types)

// FSM variables (from extraction)
float    idleTime          // 0.7 (P1), 0.5 (P2+)
float    chargeTime        // 0.25
float    comboSlashSpeed   // 40
float    distance          // computed per tick: |heroX - bossX|
float    stunTimer         // remaining stun duration
int16_t  hops              // hop counter
int16_t  chargesPerformed  // charge repeat counter
int16_t  abyssWaveCountdown // decrements each idle, triggers at <= 1

// Boolean flags (packed into uint32)
uint32_t flags             // phase2, phase3, phase4, counterRange, counterReady,
                           // willCounter, canEvade, inEvadeRange, forceTele,
                           // caughtHornet, divingIn, evadeFlipper, etc.
```

### BossAttackHitbox
```
float    halfW, halfH      // AABB half-extents (from scene data / FSM actions)
float    offsetX, offsetY  // relative to boss position
int16_t  damageDealt       // 1 for most attacks (DamageHero default)
uint8_t  active            // 1 during damage window, 0 otherwise
uint8_t  canParry          // canClashTink flag
```

### ActiveProjectiles (ring buffer, per-world singleton)
```
static constexpr int MAX = 32
float    posX[MAX], posY[MAX]
float    velX[MAX], velY[MAX]
float    halfW[MAX], halfH[MAX]  // AABB
int16_t  ttl[MAX]                // remaining frames; 0 = slot free
uint8_t  kind[MAX]               // CircleSlash, CrossSlash, Vomit, Bullet, Tendril
uint32_t activeMask              // bitmask of occupied slots
```

## 2. Boss FSM Categories

206 extracted states grouped into 16 categories. Each category is one inline tick function.

| ID | Category | States | Key velocities |
|----|----------|--------|----------------|
| 0 | Idle | Idle, Attack Choice | — |
| 1 | ComboSlash | 12 states | lunge vel=40 on strikes 2/4/6 |
| 2 | Charge | 7 states | antic vel=-32, charge vel=70 |
| 3 | JSlash | 6 states | launch vel=60x/60y diagonal |
| 4 | Counter | 8 states | stance 0.5s invincible window |
| 5 | RapidSlash | 5 states | ground vel=30, air vel=35x/-22.5y |
| 6 | Downstab | 7 states | downward until velY≤0 |
| 7 | EvadeHop | 11 states | evade vel=-28, hop vel=36 |
| 8 | Stun | 8 states | knockback vel=-8x/24y |
| 9 | TeleDive | 20 states | kinematic repositioning |
| 10 | Tendril | 16 states | ground dash vel=20, whip 0.6s |
| 11 | Vomit | 13 states | projectile spawn with velocity ramp |
| 12 | BulletSummon | 7 states | spawns bullet projectiles |
| 13 | AbyssWave | 11 states | arena-wide wave, 2.1s telegraph |
| 14 | CrossSlash | 12 states | teleport + 1.2s slash, flipback vel=-14x/20y |
| 15 | PhaseShift | 9 states | P2/P3/P4 transitions, 1.3s animations |

Plus: Intro (5 states, run once), Death (3 states, episode end), Multihit (6 states, global interrupt), QuickSlash (4 states, sub-combo), Sing (3 states, wall-cling triggered).

## 3. Top-Level Behavior Loop

```
Idle:
  wait idleTime (0.7s P1, 0.5s P2+)
  compute distance to hero
  if distance < 6 and counterReady → COUNTER
  if hero attacking and inEvadeRange → EVADE
  if distance > 20 → force ATTACK (anti-camping)
  after timer → ATTACK

Attack Choice:
  check HP for phase shifts (P2 at P2_HP, P4 at P4_HP)
  check abyssWaveCountdown ≤ 1 → ABYSS WAVE
  roll SendRandomEventV4 (phase-dependent pool)
  → selected attack "Set" state

Movement Check:
  compute distance
  if in range [distanceMin, distanceMax] → execute attack
  if too close → evade backward
  if too far → random(hop, tele)

After attack:
  50% chance → Counter stance
  otherwise → Idle
```

### SendRandomEventV4 Implementation

Weighted random with anti-repetition:
- Each attack has: weight, eventMax (max consecutive), missedMax (max times skipped before forced)
- On pick: increment consecutiveCount for that attack, reset missedCounts for it, increment missedCounts for all others
- If consecutiveCount >= eventMax: weight temporarily set to 0
- If missedCount >= missedMax: force that attack

Phase 1: 4 attacks (COMBO, CHARGE, J_SLASH, TENDRIL), equal weight, eventMax=2, missedMax=4
Phase 2: +VOMIT, BULLET_SUMMON, TENDRIL_SUMMON (7 attacks), missedMax=7
Phase 4: +CROSS_SLASH (weight=0, triggered by caughtHornet flag), missedMax=8

## 4. Combat Mechanics

### Hero → Boss Damage
- Check each tick: if hero's `PF_AttackActive` flag is set AND AABB overlap with boss body
- On hit: apply nail damage (base damage from consts, skip multiplier chains for MVP — no crests, no imbuement)
- Boss enters hit reaction: invincibility window (FSM-driven, typically ~12 frames)
- Stun gauge: accumulate 1.0 per nail hit. Threshold lives in "Stun Control" FSM (not yet extracted — must extract from scene bundle alongside arena data. Gameplay estimate: ~6-8 hits to stun.)
- On stun: global STUN event → boss enters stun sequence (knockback arc vel=-8x/24y, stunned for stunTimer frames)
- On HP ≤ 0: episode ends (hero wins)

### Boss → Hero Damage
- Each attack category activates its hitbox during specific sub-states (the "active frames")
- Check each tick: if boss hitbox active AND AABB overlap with hero hurtbox
- Hero hurtbox sizes from HeroBox.cs:
  - Normal: halfW=0.23, halfH=1.125, offset=(0, -0.38)
  - Air: halfW=0.23, halfH=0.885, offset=(0, -0.14)
  - Sprint: halfW=0.23, halfH=0.695, offset=(0, -0.58)
- On hit: hero takes 1 damage (standard boss attack), i-frames activate (INVUL_TIME from HeroController)
- Hero recoil: push away from boss at RECOIL_HOR_VELOCITY for RECOIL_HOR_STEPS
- On hero HP ≤ 0: episode ends (hero loses)

### Projectile → Hero Damage
- Each tick: sweep active projectile slots, AABB test against hero hurtbox
- On hit: hero takes damage, projectile despawns (or persists based on kind)
- Projectile physics: `pos += vel * dt`, apply gravity to velY for arcing projectiles, despawn on TTL=0 or arena collision

## 5. Reward Function

```
reward = 0
if hero_hit_boss_this_tick:
    reward += boss_damage_dealt / BOSS_MAX_HP   // normalized, ~0.025 per hit
if boss_hit_hero_this_tick:
    reward -= 1.0 / HERO_MAX_HP                 // normalized
if boss_hp <= 0:
    reward += 10.0                               // win bonus
if hero_hp <= 0:
    reward -= 5.0                                // loss penalty
```

Small positive reward per damage encourages aggression. Large win bonus shapes toward completion. Asymmetric loss penalty (smaller than win) avoids excessive passivity.

## 6. Arena Geometry

From FSM variables:
- Arena X bounds: `Tele X Min=6` to `Tele X Max=51` (usable teleport range), walls outside
- Arena center: `Centre X=54` — likely Lace Tower world coords; tele bounds are relative offsets. Resolve during arena extraction.
- Ground Y: `Land Y=6.4`
- Hero spawn: (49.27, 100.57) — but these are Lace Tower coords, not flat-area calibration
- Boss spawn: (59.19, 100.59)

Arena bitmap needs re-baking for Lace Tower geometry (currently baked for flat-area calibration room). Need to either:
- Extract Lace Tower tilemap from scene data (AssetRipper), or
- Approximate as rectangular arena with known bounds + platforms

## 7. Raycast Sensor

32 rays, 6 hit types, sweeping against:
- Arena bitmap (Terrain)
- Boss body (Enemy)
- Active projectiles (BossProjectile)
- Boss attack hitboxes when active (Hazard)

Implementation: brute-force ray march through tilemap (max 8 tiles per ray = 256 bitmap probes), then distance-test against ≤32 projectile AABB and boss AABB. No BVH needed at this scale.

## 8. Build Sequence

### Step 1: Boss skeleton + arena
- New components: BossKinematics, BossFSM, BossAttackHitbox
- Boss physics: velocity set per state, gravity integration, arena sweep collision
- Top-level loop: Idle → Attack Choice (random) → Movement Check → attack stub (just moves, no damage) → Idle
- Re-bake arena for Lace Tower bounds
- Wire BossObs to live state
- **Gate:** boss moves, picks attacks, repositions correctly

### Step 2: Melee attacks + damage
- Implement categories: ComboSlash, Charge, Counter, Downstab, JSlash, RapidSlash, EvadeHop
- All velocity profiles and frame timings from FSM extraction
- Hero→Boss hitbox check + HealthManager (HP, stun gauge, invincibility)
- Boss→Hero hitbox check + hero damage/i-frames
- Reward signal wired
- Stun sequence
- **Gate:** agent can learn dodge + punish. First training runs.

### Step 3: Projectiles + raycasts
- ActiveProjectiles ring buffer
- Vomit, BulletSummon, TendrilSummon categories — spawn projectiles with extracted velocities
- Projectile physics (integration, TTL, arena collision)
- 32-ray sensor: arena + projectiles + boss
- **Gate:** agent learns projectile avoidance

### Step 4: Full phases + advanced
- Phase transitions (P2/P3/P4) with HP threshold checks
- Phase-dependent attack pools and timing changes (idleTime 0.7→0.5)
- AbyssWave, CrossSlash categories
- TeleDive repositioning (kinematic movement, target position calculation)
- SendRandomEventV4 with eventMax/missedMax anti-repetition
- **Gate:** full Lace fight, all phases

### Throughput checkpoint after each step: must hold ≥50M tps.

## 9. Source References

- FSM data: `scripts/lace_control_fsm.json` (206 states, 329KB)
- FSM summary: `scripts/lace_fsm_summary.md`
- Decompiled C#: `decompiled/` (2034 files)
- Boss class index: `decompiled/BOSS_CLASSES_INDEX.md`
- Damage system: `decompiled/HealthManager.cs`, `DamageEnemies.cs`, `DamageHero.cs`, `HitInstance.cs`
- Hero hurtbox: `decompiled/HeroBox.cs`
- Recoil: `decompiled/Recoil.cs`
- FSM actions: `decompiled/HutongGames/PlayMaker/Actions/` (SetVelocity2d, SetInvincible, etc.)
- Existing sim: `sim/silksong_sim/src/` (hero physics, arena collision, types, consts)
- Phase 5 perf rules: `docs/phase5-physics-requirements.md`
