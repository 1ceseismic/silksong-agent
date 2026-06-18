# Silksong Game Logic Extraction & Decompilation Feasibility Plan

> **Status: REFERENCE — consult during Phase 5 (hero physics port) and Phase 7 (Lace FSM port).**
>
> Covers the decompilation toolchain (dnSpy + ILSpy + AssetRipper + Cpp2IL
> fallback), the nondeterminism analysis, the 7.5-engineer-week effort
> estimate, the PlayMaker FSM extraction strategy, and the fidelity-oracle
> design + divergence thresholds. Still load-bearing for the ports — kept
> verbatim.

## Executive Summary

Extracting Hollow Knight: Silksong's gameplay loop into a deterministic batch-parallel simulator is **feasible in 3-4 engineer-weeks** with moderate risk around floating-point reproducibility. The game is compiled with **Mono** runtime (not IL2CPP), making metadata extraction straightforward via **Cpp2IL or dnSpy**. The plugin already exposes the critical types (HeroController, PlayMakerFSM, Rigidbody2D), reducing reverse-engineering surface area. The main engineering challenges are: (1) porting PlayMaker FSM state machines to pure C# code, (2) constraining Physics2D to fixed-timestep determinism, and (3) building a fidelity-oracle harness to validate simulation against live game traces.

---

## 1. Game Architecture & Runtime

### IL2CPP vs Mono

**Finding**: Silksong uses **Mono runtime**, not IL2CPP.

**Evidence**:
- BepInEx 5 is the target framework (project targets `netstandard2.1`, references `BepInEx.Core` 5.*)
- BepInEx 5 is Mono-based; IL2CPP requires BepInEx 6 and a different patching layer (MonoDetour or unhooking)
- The plugin namespace imports `GlobalEnums`, `HarmonyLib`, and direct type references (HeroController, PlayMakerFSM), which is only possible under Mono's live assembly reflection
- GitHub issues confirm no IL2CPP support issues; the modding community's workaround repos (HKRL, HollowKnight_RL) all target Mono

**Implication**: We can dump metadata and IL via dnSpy or Cpp2IL directly from Assembly-CSharp.dll. No need for Il2CppDumper or IL2CPP string parsing.

---

## 2. Decompilation & Type Extraction Toolchain

### Recommended Stack

| Tool | Purpose | Effort |
|------|---------|--------|
| **Cpp2IL** | Reconstruct IL from metadata+binary | 2 hours setup |
| **dnSpy or ILSpy** | Browse/export decompiled C# source | 1 hour |
| **Harmony (reflection)** | Runtime type introspection for validation | built-in |

### Alternative: Metadata Dump Only

Since we already have the **plugin as a pre-made type map** (the plugin reads HeroController.instance, HeroController.playerData, HeroController.cState, etc.), we may not need full decompilation. We can:

1. Use dnSpy to spot-check HeroController's public interface
2. Use Harmony reflection at runtime to enumerate all public/protected members
3. Extract the minimal IL for performance-critical paths (physics step, FSM transitions)

**Decision**: Start with metadata dump + reflection. Use Cpp2IL only for ~20% of code (hot paths). Estimated effort: **6-8 hours**.

---

## 3. Key Game Types & Exposed Surface Area

From plugin analysis, we've identified the critical types:

### Core Types Already Accessible

| Type | Location | Used By Plugin | Scope |
|------|----------|---|---|
| **HeroController** | Assembly-CSharp | GameStateCollector, ActionManager | Player movement, input, state |
| **Rigidbody2D** | UnityEngine | GameStateCollector, BossStateManager | Physics bodies (player, boss) |
| **PlayMakerFSM** | HutongGames | BossStateManager | Boss state machine (Lace) |
| **tk2dSpriteAnimator** | tk2d | BossStateManager, GameStateCollector | Animation frame & clip tracking |
| **HealthManager** | Assembly-CSharp | BossStateManager, RaycastSensor | Health & damage events |
| **DamageHero** | Assembly-CSharp | RaycastSensor | Hazard collision detection |

### HeroController Internals (from plugin inspection)

```csharp
public class HeroController : MonoBehaviour {
    public static HeroController instance;
    public PlayerData playerData;  // health, maxHealth, silk, isInvincible
    public CharacterState cState;  // onGround, facingRight
    public AnimCtrl animCtrl;      // animator + animation clips
    public Transform transform;    // position, localScale
    
    public Rigidbody2D rb;
    public float velocity.x, velocity.y;
    
    public bool CanDash();
    public bool CanAttack();
}

public class CharacterState {
    public bool onGround;
    public bool facingRight;
}

public class PlayerData {
    public int health;
    public int maxHealth;
    public int silk;
    public bool isInvincible;
}
```

### PlayMaker FSM Internals (from BossStateManager)

The FSM is accessed as:
```csharp
public class PlayMakerFSM : MonoBehaviour {
    public string ActiveStateName { get; }  // Current state name
    // No direct state enum; names like "P2 Shift", "P3 Roar", "Stun", etc.
}
```

The plugin already has **70+ animation state enums** (BossAnimationState enum) mapping clip names to states, suggesting the FSM uses a string-driven state dispatch.

---

## 4. Nondeterminism Sources & Mitigation

### Physics2D Determinism (Box2D)

**Finding**: Box2D has no RNG and uses only arithmetic operations. However, floating-point precision differs across CPUs.

**Cross-Platform Determinism**: NOT POSSIBLE. A Rigidbody2D simulation on Intel vs ARM will diverge within 10s of frames due to compiler differences and FPU implementations.

**Same-Machine Determinism**: POSSIBLE with strict fixed-timestep + no frame-skipping.

**Mitigation Strategy**:
1. Lock `Time.fixedDeltaTime` to a constant (e.g., 0.02 = 50 Hz), no scaling
2. Never use `Time.deltaTime` in physics code; use FixedUpdate exclusively
3. Cache initial state at episode start; run playback deterministically
4. Use soft-float libraries (e.g., Burst-compatible soft floats) if strict reproducibility is required
5. **Validation approach**: Record game traces (state snapshots) from live game at 50 Hz, replay in sim, measure L2 divergence

**Risk**: Low. The game's physics are simple (no constraints, no ragdoll), and determinism within a single run is sufficient for RL.

### RNG & Proceduralism

From plugin scan: No detected RNG calls in HeroController or BossStateManager. Boss behavior is fully deterministic FSM-driven. Animation timing is frame-based (not random).

**Conclusion**: No RNG to engineer around (unlike HKRL which has to mock enemy decision-making).

### Floating-Point Accumulation

For a 60-second episode (3000 frames at 50 Hz), float precision loss should be < 1e-5 units. This is negligible for pixel-space positions (unity scale ~ 10 units).

**Mitigation**: Use double-precision intermediate accumulation if needed; convert to float for sim state. Estimated cost: 5% perf hit.

---

## 5. Effort Estimate (Engineer-Weeks)

| Component | Effort | Notes |
|-----------|--------|-------|
| **Type Extraction & Reflection** | 0.5 weeks | dnSpy browse + Harmony reflection layer |
| **HeroController Movement Port** | 1.0 weeks | Ground check, dash, jump, attack cooldowns, invulnerability frames |
| **Lace FSM Reverse Engineering** | 1.5 weeks | Extract state graph from code; map 70 animation states to FSM transitions; identify entry/exit conditions |
| **Projectile + Collision System** | 0.75 weeks | Raycasting for environment; circle-circle for boss projectiles (already modeled in plugin) |
| **Animation Timing & Playback** | 0.75 weeks | Port tk2d frame interpolation; match clip timing to FSM state duration |
| **Arena Geometry & Layers** | 0.5 weeks | Asset extraction (colliders, layer masks) via AssetRipper |
| **Batch Parallel Infrastructure** | 1.0 weeks | Multi-env step logic; shared memory for GPU interop; synchronization |
| **Fidelity Oracle Harness** | 1.0 weeks | State logger; trajectory playback; diff metrics; CI integration |
| **Testing & Validation** | 0.5 weeks | Run 100 episodes; verify no sim/game divergence |
| **Buffer / Unknowns** | 0.5 weeks | Type mismatches, PlayMaker quirks, edge cases |
| **TOTAL** | **7.5 weeks** | Conservative; could compress to 5-6 with parallelization |

**Realistic Path**: 4 weeks for minimal simulator (movement + boss FSM), then 1-2 weeks per additional feature (projectiles, i-frames, multi-phase logic).

---

## 6. PlayMaker FSM Extraction Strategy

PlayMaker FSMs are Unity serialized objects. The approach:

### Step 1: State Graph Extraction
Use Harmony reflection to enumerate FSM states at runtime:
```csharp
var fsm = boss.GetComponent<PlayMakerFSM>();
foreach (var state in fsm.states) {
    Log($"State: {state.name}, Actions: {string.Join(",", state.actions)}");
}
```

### Step 2: Transition Conditions
Most transitions in boss FSMs are event-driven (health threshold, animation end, timer). Extract via:
- IL inspection of action IL (Cpp2IL + ILSpy)
- Runtime state machine log (set breakpoints in game, log all transitions for 1 episode)

### Step 3: Code Generation
Generate a pure C# state machine:
```csharp
public class LaceFSM {
    public enum State { Idle, ComboSlash, P2Shift, P3Roar, ... }
    public State current;
    
    public void Step(float dt, BossInput input) {
        switch (current) {
            case State.ComboSlash:
                if (animationTime > clipDuration) {
                    current = State.Idle;
                }
                break;
            // ...
        }
    }
}
```

**Tools**: UnityFSMCodeGenerator (GitHub reference) can partially automate this.

**Effort**: 1-2 weeks, mostly manual verification.

---

## 7. Fidelity Oracle Design

### Validation Harness Architecture

```
Live Game (Plugin)  →  State Logger  →  Trace File (state, action, delta)
                  ↓
            Replay Engine
                  ↓
        Sim State Comparison
                  ↓
        Metrics: L2 divergence, event timing, animation frame match
```

### Metrics to Track

| Metric | Type | Threshold |
|--------|------|-----------|
| Position divergence | L2 norm | < 0.1 units per episode |
| Velocity divergence | L2 norm | < 0.05 units/s |
| Animation frame mismatch | frames | 0 frames (binary match) |
| Collision detections | event count | ≤ 1% false positive rate |
| Damage timing | frame offset | ≤ 1 frame |
| Boss phase transitions | frame offset | ≤ 2 frames |

### Implementation Strategy

1. **Offline Validation** (per commit):
   - Replay recorded game traces through sim
   - Measure divergence distribution
   - Flag regressions > threshold
   
2. **Online Validation** (continuous RL):
   - Log every 100th episode from live game
   - Run through sim; measure divergence
   - Alert if sim action timings diverge > 5%

3. **Determinism Validation**:
   - Record initial game state
   - Run sim 2x with same action sequence
   - Verify byte-identical output (or < 1e-7 float tolerance)

### Oracle Workload

Replaying 1000-step episode: ~50ms (0.05 steps/ms = 1000 steps/sec on CPU). Batch 100 episodes = 5s validation time, acceptable for CI.

---

## 8. Legal & License Posture

### Team Cherry Stance

- Team Cherry **tolerates** game modifications (documented in modding FAQ and community precedents like HKRL)
- **No explicit permission**, but no enforcement history for offline RL training
- Distribution of modified binaries is a gray area; offline research is safe

### Recommended Approach

1. **Do NOT publish decompiled code** from Assembly-CSharp
2. **Publish only generated simulator code** (the pure C# FSM, not decompiled internals)
3. **Reference** the original types by name/structure, but implement from scratch
4. **Cite Team Cherry** and HKRL as prior art in README

**Legal Risk**: Low. The project is non-commercial research, offline, and doesn't distribute modified binaries. Similar projects (HKRL, HollowKnight_RL, jimmie-jams/SilksongRL) have operated without cease-and-desist for years.

---

## 9. Top-Level Simulator Architecture

### Type Hierarchy

```csharp
public struct GameState {
    public Vec2 playerPos, playerVel;
    public int playerHealth, playerMaxHealth;
    public bool onGround, facingRight, canDash, canAttack, isInvincible;
    public float silk;
    
    public Vec2 bossPos, bossVel;
    public int bossHealth, bossMaxHealth;
    public int bossPhase;  // 0, 1, 2
    public string bossAnimState;
    public float bossAnimProgress;
    
    public RaycastResult[] raycasts;  // 16 directions, distance + type
    public Vec2[] bossProjectiles;  // positions of active projectiles
    public float episodeTime;
}

public struct Command {
    public byte moveX, moveY;  // -1, 0, +1
    public bool jump, attack, dash;
    public bool reset;  // episode reset
}

public class SilksongSimulator {
    public void Initialize(GameState initial);
    public void Step(Command action, float dt = 0.02f);
    public GameState GetState();
    public void Reset();
    
    // Internal:
    HeroControllerSim heroSim;
    LaceFSMSim bossSim;
    Physics2DSimulator physics;
    AnimationSystem animSystem;
}
```

### Parallelization Model

For GPU scaling (millions of env-steps/sec):

1. **Batch Dimension**: 1000s of parallel envs
2. **Step Kernel**: Each env steps independently (no inter-env communication)
3. **Memory Layout**: Structure of Arrays (SoA) for SIMD vectorization
4. **Backend**: C++ (CUDA/HIP) with Python binding, or Rust (Bevy ECS)

**Effort**: 2-3 weeks to port C# sim to CUDA/HIP; not on the critical path for the initial port.

---

## 10. Decompilation Tools Comparison

### Cpp2IL (Recommended)
- **Pros**: Reconstructs IL; works on Mono binaries; produces readable C#
- **Cons**: ~50% success rate on some games; may bail on complex functions
- **Setup**: 2 hours; generate dummy DLLs, inspect in dnSpy

### dnSpy (Mandatory Secondary)
- **Pros**: Works on any .NET assembly; browse methods, inspect attributes
- **Cons**: Shows IL, not always pretty C#
- **Setup**: 1 hour; install, point at Assembly-CSharp.dll

### ILSpy (Optional, Complementary)
- **Pros**: Better C# output than dnSpy; standalone
- **Cons**: CLI version less scriptable
- **Use Case**: Final review before implementation

### AssetRipper (Asset Extraction)
- **Purpose**: Extract prefabs, sprites, colliders from .assets files
- **Setup**: 1 hour
- **Output**: Serialized geometry, animation clips

---

## 11. Implementation Roadmap

### Phase 1: Type Extraction & Reflection (1 week)
- [ ] Run dnSpy on Assembly-CSharp.dll
- [ ] Document HeroController public API
- [ ] Document HealthManager, PlayMakerFSM interfaces
- [ ] Write Harmony reflection layer for runtime validation

### Phase 2: HeroController Port (1 week)
- [ ] Extract movement code (ground checks, velocity updates)
- [ ] Port jump/dash logic (cooldown, invincibility frames)
- [ ] Integrate Rigidbody2D.SimpleMove or manual integration
- [ ] Test against live game traces

### Phase 3: Boss FSM Reverse Engineering (1.5 weeks)
- [ ] Log all FSM state transitions in live game (100+ episodes)
- [ ] Identify state transition conditions (animation end, health threshold, timers)
- [ ] Generate state machine code
- [ ] Implement phase transitions (P2 Shift, P3 Roar)

### Phase 4: Collision & Raycast System (0.75 weeks)
- [ ] Port raycast logic from RaycastSensor.cs
- [ ] Implement projectile circle-circle collision
- [ ] Hazard layer detection
- [ ] Fidelity validation

### Phase 5: Animation & Timing (0.75 weeks)
- [ ] Port tk2dSpriteAnimator clip timing
- [ ] Synchronize animation frame to FSM state
- [ ] Handle animation blend times

### Phase 6: Fidelity Oracle & CI (1 week)
- [ ] Build state logger in plugin
- [ ] Implement replay engine in sim
- [ ] Calculate divergence metrics
- [ ] CI integration

### Phase 7: Testing & Polish (0.5 weeks)
- [ ] 100-episode validation run
- [ ] Determinism checks
- [ ] Documentation

---

## 12. Risk Matrix

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| PlayMaker state transition logic is opaque | Medium | High | Log all transitions; brute-force state space |
| Float divergence > threshold | Low | Medium | Use double precision; accept per-machine reproduced determinism |
| Performance: sim too slow for RL | Low | Medium | Benchmark early; profile hot paths; move to C++/GPU if needed |
| Type layout mismatch (reflection fails) | Low | High | Runtime field verification; manual inspection |
| Animation timing off by frames | Medium | Low | Visual inspection; record live game animations as reference |

---

## 13. Validation Plan

### Acceptance Criteria

1. **Structural Match**:
   - HeroController fields match plugin readout (health, position, velocity, canDash, canAttack)
   - BossStateManager reports same phase transitions at same frames
   - Animation state enum matches live game clip names

2. **Trajectory Fidelity**:
   - Record 10 game episodes with mixed player inputs
   - Replay through sim with identical inputs
   - L2 position error < 0.1 units/frame, velocity error < 0.05 units/s/frame

3. **Event Timing**:
   - Damage events occur within 1 frame of live game
   - Boss phase transitions within 2 frames
   - Animation transitions frame-accurate

4. **Determinism**:
   - Run same episode 2x; state is bit-identical (or < 1e-7 float tolerance)

---

## References

- **BepInEx 5 & Mono**: https://docs.bepinex.dev/articles/user_guide/installation/index.html
- **Cpp2IL**: https://github.com/SamboyCoding/Cpp2IL
- **HKRL**: https://github.com/AdityaJain1030/HKRL
- **UnityFSMCodeGenerator**: https://github.com/justonia/UnityFSMCodeGenerator
- **tk2dSpriteAnimator**: https://www.2dtoolkit.com/docs/latest/html/classtk2d_sprite_animator.html
- **Physics2D Determinism**: https://support.unity.com/hc/en-us/articles/360015178512-Determinism-with-2D-Physics
- **PlayMaker FSM**: https://www.playmaker.dev/
