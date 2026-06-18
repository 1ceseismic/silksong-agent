# Phase 5 Physics — Performance Constraints

Throughput floor and measured Phase 4 ceiling are in
`framework-requirements.md` §2. This doc is the catalogue of what to write
(and what to avoid) so Phase 5 does not collapse that throughput when real
physics replaces the no-op scaffold.

## 1. The per-step budget

```
   per-world per-step cost at Phase 4 ceiling = 12.5 ns   (80 M tps)
   per-world per-step cost at Phase 5 floor   = 20 ns     (50 M tps)
```

20 ns of GPU work per world per step buys:
- ~20 FMA instructions on a 4070S SM at peak, or
- ~2–4 coalesced global-memory loads, or
- ~1 uncoalesced / pointer-chased load.

Implication: **every load coalesced, every branch predicated, nothing
allocates, nothing dispatches virtually.** Reaching for `std::vector`,
`std::function`, `std::any`, `std::shared_ptr`, `dynamic_cast`, or `virtual`
is a stop signal.

## 2. Data layout (non-negotiable)

### Use ECS components, never pointer-chased objects

```cpp
// GOOD — Madrona stores these column-wise, loads coalesce
struct PlayerKinematics {
    float posX, posY;
    float velX, velY;
    float remainingIFrames;
    uint32_t groundedFlags;  // bitfield, not vector<bool>
};

// BAD — heap alloc, uncoalesced loads, cache miss per access
class Player {
    std::unique_ptr<State> state_;
    std::vector<Buff> activeBuffs_;
    virtual void update(float dt) = 0;
};
```

### Fixed-size arrays only

No `std::vector<Projectile>` in a component. No dynamic grow/shrink per step.
Instead:

```cpp
// Compile-time-capped active-projectile ring buffer per world
struct ActiveProjectiles {
    static constexpr int MAX = 32;
    float posX[MAX];
    float posY[MAX];
    float velX[MAX];
    float velY[MAX];
    uint8_t  kind[MAX];    // enum ProjectileKind
    uint16_t ttl[MAX];     // remaining frames; 0 = slot free
    uint32_t activeMask;   // bitmask of occupied slots
};
```

Spawning = find first clear bit, set fields, set TTL. Despawning = clear
TTL, `activeMask ^= (1 << idx)`. No allocator touched.

### SoA everywhere if we need cross-entity sweeps

If Phase 6 raycasts iterate across all projectiles, the `ActiveProjectiles`
struct above is already column-wise (all `posX`s contiguous), so the ray
vs projectile test vectorises.

## 3. Branchless / predicated updates

Warp threads execute in lockstep; a divergent branch idles half the warp.
Hero FSM ~40 states, boss FSM ~70 — a naive `switch(state)` in the step
kernel is the worst case.

### Rules

- **Integrator is branchless.** Position/velocity update is always the same
  arithmetic; gravity/friction applied unconditionally. Grounded state
  clamps velY via `min/max`, not `if`.
- **FSM transitions use predication.** For a state machine with N states,
  precompute transition masks at load time. The per-step kernel does
  table lookups + predicated writes, not `switch`.
- **Per-state behaviors via function-pointer tables is a lie.** Function
  pointers in CUDA device code are slow. Instead:
  1. Implement each state's `tick()` as an `inline` function.
  2. In the task graph, dispatch to N parallel-for nodes, one per state,
     filtered by an `InState<N>` tag component.
  3. Madrona schedules them; entities in different states run in different
     kernel launches but the same warp is homogeneous.
- **Attack-telegraph / damage-window logic** uses time comparisons, not
  per-frame string checks. Pre-compute `(firstActiveFrame, lastActiveFrame)`
  at attack spawn; the per-step test is `frame >= firstActive && frame < lastActive`
  — two comparisons, one predicated write.

## 4. Integrator: semi-implicit Euler, fixed timestep

```cpp
inline void integrateHero(PlayerKinematics &p, const PlayerInput &in, float dt)
{
    const float gravity = -58.0f;               // matches HeroController
    const float moveAccel = 230.0f;
    const float maxSpeed  = 17.0f;

    // semi-implicit Euler: update velocity first, then position
    float wantVX = (in.right - in.left) * moveAccel;
    p.velX = fminf(fmaxf(p.velX + wantVX * dt, -maxSpeed), maxSpeed);
    p.velY = p.velY + gravity * dt;

    p.posX += p.velX * dt;
    p.posY += p.velY * dt;
}
```

Two lines of arithmetic per axis.

- **Do NOT import Box2D, MuJoCo, or Bullet.** Silksong has handcrafted curves
  (dash velocity, jump-release cutoff, wall-slide friction); a general solver
  wastes ops approximating them. Hand-write the integrator from decompiled
  `HeroController` constants.
- **`deltaT = 0.02`, 2 substeps per agent step** — see framework-requirements §4.
  Substeps are a loop in the kernel, not a task-graph dependency.
- **No CCD.** At 50 Hz with hero speeds ≤ 70 u/s, max per-step displacement
  ≈ 1.4 u; arena tiles are ≥ 1 u thick. Tunnelling is not a concern.

## 5. Collision

### Arena geometry is static and baked

Extract arena colliders at dev time (via Unity AssetRipper per the
decompilation plan). Bake to a 2D binary tilemap — texture-style array of
`uint32` bitfields, each bit = "this tile solid."

```cpp
struct Arena {
    static constexpr int W = 256, H = 128;   // covers Lace Tower + some margin
    uint32_t solid[H][(W + 31) / 32];        // bitmap
    float originX, originY;                  // world-space offset
    float tileSize;                          // = 1.0 units typically
};
```

Point-in-solid test is a single bit extract: `O(1)`, no branching, no
indirection. Swept-AABB test is 4 bitmap reads + arithmetic.

### Hero vs arena

Swept AABB each sub-step. 4 bitmap probes, clamp velocity on hit.

### Hero vs projectile

O(n) loop over the ≤32 projectile slots. SIMD-friendly because
`ActiveProjectiles` is SoA.

### Hero vs boss

Single AABB or disc test, explicit inline.

### Raycast sensor (Phase 6)

32 rays × at most 8 tiles traversed each = 256 bitmap probes per step.
Brute-force beats a BVH here until the arena grows substantially. Do NOT
build a BVH until profiling shows it's needed.

## 6. FSM implementation

### Lace boss: 71 animation states + 3 phases. Don't switch on all of them.

- Group states into **action categories** (`Combo`, `Charge`, `Rapid`, …;
  see `docs/audit/lace-fsm.md` for the full grouping). The component stores
  `(categoryId, subStateId, frameInState)`, three `uint8`s.
- Per category, one `inline` tick function in the step kernel, dispatched
  via a task-graph node filtered on `categoryId`. Each tick function
  handles its own substates via a small local `switch` (≤10 branches =
  compiler turns into a jump table).
- Phase transitions happen at health thresholds (P2 at 600 HP, P3 at
  320 HP — see the FSM doc). Check once per step with two comparisons,
  not per-state.

### Hero: ~40 animation states, not an FSM for behavior

Hero behaviour is driven by the 10 input flags + cState + timers, not
by the animation FSM (animation is a consequence). Implement:

- `integrateHero()` — branchless physics
- `applyInputToHero()` — reads input, updates `queuedAttack`, `queuedDash`,
  etc. All state is timer/counter, not a discrete FSM.
- Animation state is DERIVED from physics+input state at the end of
  the step — one big table lookup, not a separate simulation.

## 7. What we are NOT porting from Unity

Out of scope — the policy doesn't need them:

- Audio / music / SFX triggers.
- Particles, sprite flashes, post-processing.
- Camera shake / pan / zoom.
- Save-file I/O.
- NPC dialogue / cutscenes.
- Every menu / UI system.
- The `PlayMakerFSM` host itself — Lace's FSM is ported *semantically*
  (see `docs/audit/lace-fsm.md`), not by emulating PlayMaker's action runtime.
- Most of `HeroController.Update()` (800 LoC) — only movement, combat, and
  damage. Everything cosmetic is dropped.

If a trace diff forces emulation of a cosmetic Unity behaviour to match
position/velocity, document that specific sequence as an exception — not as
carte blanche to pull in more Unity scaffolding.

## 8. Benchmarking & regression gates

- `scripts/benchmark.py` runs the 3-regime × 4-batch-size sweep.
- Phase 5 acceptance: at 65 k worlds, policy regime **≥ 50 M tps**.
- CI target: auto-run on every PR touching `sim/silksong_sim/src/**`.
  Fail if any row's tps drops > 10 % vs the checked-in baseline.
- Baseline CSV: `docs/benchmarks/phase4-baseline.csv` (to be committed
  with the first Phase 5 PR as the reference point).

## 9. Exception process

Before committing a violation:

1. **Flip to a conformant pattern** — vector → fixed array, virtual → task-graph
   dispatch, branch → predication. First resort.
2. **Check it's off the hot path.** Setup/teardown can be as slow and
   allocator-friendly as you like. The hot path is `stepSystem` and everything
   it transitively calls.
3. **Profile.** <1 % of per-step time → merge with a comment. Otherwise
   redesign.

## 10. Cross-references

- `docs/framework-requirements.md` — obs/action contract (§3), substrate (§6),
  phase status (§10)
- `docs/audit/lace-fsm.md` — complete Lace state graph (71 states, 3 phases)
- `docs/audit/type-map.md` — every field/method the sim must reproduce
- `docs/audit/decompilation-plan.md` — how to extract HeroController constants
- `sim/silksong_sim/src/consts.hpp` — current tunables
- `sim/silksong_sim/src/types.hpp` — current ECS components (will grow in Phase 5)
