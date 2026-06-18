# NVRTC Compile Time Optimization Plan

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce GPU kernel JIT compilation time from 25+ minutes (stuck/timeout) to under 60 seconds by removing unnecessary code and data from the NVRTC compilation unit.

**Root cause:** Madrona compiles `SIMULATOR_SRCS` (sim.cpp, level_gen.cpp, types.hpp) via NVRTC for GPU execution. sim.cpp `#include`s 5000+ lines of headers (fsm_actions.hpp, fsm_interpreter.hpp, fsm_lace_boss1.hpp, hero.hpp, hero_config.hpp, hero_states.hpp, combat.hpp). NVRTC must compile all of this. The old sim was ~1900 lines; the rewrite is ~5000.

**Architecture:** The system functions (heroStepSystem, bossStepSystem, etc.) MUST be in sim.cpp because Madrona's ParallelForNode needs them inline. But we can dramatically reduce what sim.cpp includes by:
1. Moving FSM baked DATA initialization out of NVRTC (into mgr.cpp)
2. Moving FSM variable initialization out of NVRTC (into mgr.cpp)
3. Tightening FsmDef struct to actual sizes (not padded maximums)
4. Reducing hero.hpp code volume (consolidate helpers, remove dead code)

---

## Analysis: What NVRTC compiles today

| File | Lines | In NVRTC? | Why |
|------|-------|-----------|-----|
| sim.cpp | 711 | YES | SIMULATOR_SRCS |
| types.hpp | 167 | YES | included by sim.cpp |
| consts.hpp | 110 | YES | included by types.hpp |
| fsm_types.hpp | 182 | YES | included by types.hpp |
| fsm_actions.hpp | 1120 | YES | included by sim.cpp |
| fsm_interpreter.hpp | 273 | YES | included by sim.cpp |
| **fsm_lace_boss1.hpp** | **1181** | **YES** | included by sim.cpp + level_gen.cpp |
| **hero.hpp** | **1751** | **YES** | included by types.hpp → sim.cpp |
| **hero_config.hpp** | **276** | **YES** | included by hero.hpp |
| **hero_states.hpp** | **228** | **YES** | included by hero.hpp |
| combat.hpp | 165 | YES | included by sim.cpp |
| level_gen.cpp | 130 | YES | SIMULATOR_SRCS |
| raycast.hpp | 75 | YES | included by sim.cpp |
| **Total** | **~6370** | | |

## Changes

### Change 1: Remove fsm_lace_boss1.hpp from NVRTC (~1181 lines saved)

The baked data (constexpr arrays, makeDef(), INIT_*_VARS) is only needed at initialization time, not during per-frame system execution.

**Move FsmDef population to mgr.cpp:**
- mgr.cpp is NOT in SIMULATOR_SRCS → not compiled by NVRTC
- mgr.cpp already runs before any GPU execution
- Add a `populateFsmDef(FsmDef&)` function in a new `fsm_lace_boss1.cpp` (added to `silksong_sim_cpu_impl` target, NOT `SIMULATOR_SRCS`)
- mgr.cpp calls `populateFsmDef()` and writes the result into the FsmDefSingleton before the first step

**Move FSM variable init out of level_gen.cpp:**
- level_gen.cpp currently includes fsm_lace_boss1.hpp for INIT_FLOAT_VARS/INIT_INT_VARS/INIT_BOOL_VARS
- Instead, store these initial values INSIDE the FsmDef struct (add `float initFloatVars[]`, `int32_t initIntVars[]`, `uint8_t initBoolVars[]` arrays)
- level_gen.cpp reads from `def.initFloatVars` etc. — no need to include the baked header

**Remove `#include "fsm_lace_boss1.hpp"` from sim.cpp and level_gen.cpp.**

### Change 2: Remove hero_config.hpp from NVRTC (~276 lines saved)

hero_config.hpp defines the `HeroConfig` struct with all default values and the `HERO_CONFIG_DEFAULT` constexpr. The config is only needed at init time and can be stored in a singleton.

- Add `HeroConfigSingleton` to types.hpp (just the struct, no defaults)
- Populate it in mgr.cpp from `HERO_CONFIG_DEFAULT` 
- hero.hpp functions take `const HeroConfig&` parameter (already do)
- level_gen.cpp reads from the singleton instead of `HERO_CONFIG_DEFAULT`
- Remove `#include "hero_config.hpp"` from hero.hpp; just forward-declare `struct HeroConfig`

### Change 3: Tighten FsmDef struct sizes

Current FsmDef has max-padded arrays:
- `FsmStateDef states[96]` — only 88 used
- `FsmActionDef actions[512]` — only 458 used  
- `float params[800]` — only 748 used
- Total padding waste: ~400 bytes

Use exact sizes (defined as constexpr in fsm_types.hpp, set to match the actual boss):
```cpp
constexpr int FSM_DEF_STATES = 88;
constexpr int FSM_DEF_ACTIONS = 458;
constexpr int FSM_DEF_TRANSITIONS = 127;
constexpr int FSM_DEF_PARAMS = 748;
constexpr int FSM_DEF_GLOBAL_TRANSITIONS = 2;
```

This reduces FsmDef from 6.2KB to ~5.4KB. Modest savings but reduces GPU memory pressure.

### Change 4: Reduce hero.hpp NVRTC volume (~500+ lines saved)

hero.hpp is 1751 lines. Many helper functions are only called from other helpers, not from the system entry points. NVRTC inlines everything.

- Move `HeroConfig` struct definition to a separate `hero_config_types.hpp` (just the struct layout, no defaults) — ~50 lines instead of 276
- Consolidate the 47 static inline helper functions: merge small 2-3 line helpers into their callers where only called once
- The `heroTick()` entry point and its direct callees must stay in the header (NVRTC needs them). But internal helpers like `CancelRecoilHorizontal()`, `ResetLook()`, `BackOnGround()` can be inlined manually into their single call site.

### Change 5: Reduce fsm_actions.hpp switch complexity

The 75-case switch in `fsmActionOnEnter` and the continuous-action switch in `fsmActionOnUpdate` are the largest single code blocks NVRTC must compile.

- Group related cases that share logic (e.g., all the variable-set actions: SetBoolValue/SetFloatValue/SetIntValue can share a helper)
- Cases for Noop actions: collapse to a single default case
- Actions that are never used in Lace Boss1's FSM data but exist "for future bosses": mark with `#ifndef SILKSONG_MINIMAL_ACTIONS` so they can be excluded from NVRTC compilation for known boss configurations

## Expected Result

| File | Before | After | Saved |
|------|--------|-------|-------|
| fsm_lace_boss1.hpp | 1181 | 0 (moved to .cpp) | 1181 |
| hero_config.hpp | 276 | ~50 (types only) | 226 |
| hero.hpp | 1751 | ~1200 (consolidated) | 551 |
| fsm_actions.hpp | 1120 | ~900 (grouped) | 220 |
| **Total NVRTC** | **~6370** | **~4190** | **~2180 (34%)** |

The 34% code reduction combined with removing constexpr array initialization (which forces constant folding) should bring compile time well under 60 seconds.

## Implementation Steps

- [ ] **Step 1:** Create `fsm_lace_boss1.cpp` with `populateFsmDef()`. Add to `silksong_sim_cpu_impl` but NOT `SIMULATOR_SRCS`. Add init var arrays to FsmDef struct.
- [ ] **Step 2:** Update mgr.cpp to call `populateFsmDef()` at construction time.
- [ ] **Step 3:** Remove `#include "fsm_lace_boss1.hpp"` from sim.cpp and level_gen.cpp. Update level_gen.cpp to read init vars from FsmDef.
- [ ] **Step 4:** Split hero_config.hpp → hero_config_types.hpp (struct layout only, in NVRTC) + hero_config.cpp (defaults, NOT in NVRTC).
- [ ] **Step 5:** Consolidate hero.hpp helpers.
- [ ] **Step 6:** Build CPU mode, verify it works.
- [ ] **Step 7:** Build GPU mode, measure NVRTC compile time.
- [ ] **Step 8:** If still too slow, apply fsm_actions.hpp switch reduction.
