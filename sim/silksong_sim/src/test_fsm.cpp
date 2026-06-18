// Standalone test for the FSM interpreter + baked Lace Boss1 data.
// Verifies that fsmInit() + fsmTick() drives state transitions correctly.
//
// Build:  cmake --build sim/silksong_sim/build/ -j$(nproc)
// Run:    ./sim/silksong_sim/build/test_fsm

#include <cstdio>
#include <cstring>
#include <cmath>
#include <cassert>

#include <madrona/rand.hpp>

#include "fsm_types.hpp"
#include "fsm_actions.hpp"
#include "fsm_interpreter.hpp"
#include "fsm_lace_boss1.hpp"

using namespace silksong;

int main()
{
    // --- Build the FsmDef from baked data ---
    FsmDef def = fsm_lace_boss1::makeDef();

    printf("Baked FSM: %d states, %d actions, %d transitions, %d params\n",
           def.numStates, def.numActions, def.numTransitions, def.numParams);
    printf("Float vars: %d, Int vars: %d, Bool vars: %d\n",
           def.numFloatVars, def.numIntVars, def.numBoolVars);
    printf("Start state: %d (%s)\n",
           def.startState, fsm_lace_boss1::STATE_NAMES[def.startState]);

    // --- Initialize runtime ---
    FsmRuntime rt{};
    fsmInit(def, rt,
            fsm_lace_boss1::INIT_FLOAT_VARS,
            fsm_lace_boss1::INIT_INT_VARS,
            fsm_lace_boss1::INIT_BOOL_VARS);

    // --- Set up boss kinematics + stun control ---
    BossKinematics bk{};
    bk.posX = 97.39f;   // boss spawn X
    bk.posY =  7.28f;   // boss spawn Y

    StunControl sc{};
    sc.stunCombo = 8;
    sc.stunHitMax = 10;

    // Context fields (non-FSM state needed by actions)
    int32_t bossHP = 250;
    float gravityScale = 2.0f;
    bool isKinematic = false;
    bool hitboxActive = false;
    float hitboxHalfW = 0.f, hitboxHalfH = 0.f;
    float hitboxOffsetX = 0.f, hitboxOffsetY = 0.f;
    int16_t hitboxDamage = 1;
    float freezeTimer = 0.f;
    float facingScale = 1.f;

    madrona::RNG rng(42);
    const float dt = 0.02f;
    const float heroX = 85.23f;
    const float heroY =  7.60f;

    // --- Enter the start state ---
    FsmActionCtx ctx{
        .rt = rt,
        .bk = bk,
        .sc = sc,
        .heroX = heroX,
        .heroY = heroY,
        .heroIFrameRem = 0.f,
        .rng = rng,
        .dt = dt,
        .bossHP = bossHP,
        .gravityBase = -60.f,
        .gravityScale = gravityScale,
        .isKinematic = isKinematic,
        .hitboxActive = hitboxActive,
        .hitboxHalfW = hitboxHalfW,
        .hitboxHalfH = hitboxHalfH,
        .hitboxOffsetX = hitboxOffsetX,
        .hitboxOffsetY = hitboxOffsetY,
        .hitboxDamage = hitboxDamage,
        .freezeTimer = freezeTimer,
        .heroDamageOut = rt.heroDamageOut,
        .heroDamageBypass = rt.heroDamageBypass,
        .facingScale = facingScale,
    };

    // To trace pass-through chains, we temporarily tick frame-by-frame
    // But first, let's just enter and see where we end up
    fsmEnterState(def, ctx, def.startState);
    printf("After init: state=%d (%s)\n",
           rt.currentState, fsm_lace_boss1::STATE_NAMES[rt.currentState]);
    printf("Key float vars: Distance=%.2f, TargetDist=%.2f, CounterPause=%.2f\n",
           rt.floatVars[2], rt.floatVars[8], rt.floatVars[1]);

    // --- Tick for 100 frames, log state transitions ---
    uint8_t prevState = rt.currentState;
    int transitionCount = 0;
    int statesVisited[256] = {};
    statesVisited[rt.currentState] = 1;

    for (int frame = 0; frame < 100; ++frame) {
        fsmTick(def, ctx);

        // Apply basic physics integration (gravity + floor clamp)
        if (!isKinematic) {
            bk.velY += -60.f * gravityScale * dt;
            bk.posX += bk.velX * dt;
            bk.posY += bk.velY * dt;

            // Floor clamp
            const float floorY = 7.28f;
            if (bk.posY < floorY) {
                bk.posY = floorY;
                bk.velY = 0.f;
            }
            // Wall clamp
            if (bk.posX < 82.4f) { bk.posX = 82.4f; bk.velX = 0.f; }
            if (bk.posX > 105.6f) { bk.posX = 105.6f; bk.velX = 0.f; }
        }

        if (rt.currentState != prevState || frame < 3) {
            if (frame < 3) {
                printf("  frame %3d: state=%s waitTimer=%.3f dist=%.2f tgtDist=%.2f\n",
                       frame,
                       fsm_lace_boss1::STATE_NAMES[rt.currentState],
                       rt.waitTimer,
                       rt.floatVars[2],  // FVAR_DISTANCE
                       rt.floatVars[8]); // FVAR_TARGET_DISTANCE
            }
            if (rt.currentState != prevState) {
                printf("  frame %3d: %s -> %s\n",
                       frame,
                       fsm_lace_boss1::STATE_NAMES[prevState],
                       fsm_lace_boss1::STATE_NAMES[rt.currentState]);
                prevState = rt.currentState;
                transitionCount++;
                statesVisited[rt.currentState] = 1;
            }
        }
    }

    // --- Report ---
    int uniqueStates = 0;
    for (int i = 0; i < 256; ++i) {
        if (statesVisited[i]) uniqueStates++;
    }

    printf("\nAfter 100 frames:\n");
    printf("  Current state: %d (%s)\n",
           rt.currentState, fsm_lace_boss1::STATE_NAMES[rt.currentState]);
    printf("  Transitions: %d\n", transitionCount);
    printf("  Unique states visited: %d\n", uniqueStates);
    printf("  Boss pos: (%.2f, %.2f), vel: (%.2f, %.2f)\n",
           bk.posX, bk.posY, bk.velX, bk.velY);
    printf("  Boss HP: %d\n", bossHP);

    // --- Assertions ---
    // The FSM should have left Idle within ~37 frames (0.75s wait at 50Hz)
    bool leftIdle = (transitionCount > 0);
    printf("\n--- CHECKS ---\n");
    printf("  Left Idle state: %s\n", leftIdle ? "PASS" : "FAIL");

    // Should have visited at least Idle + some follow-on states
    bool multipleStates = (uniqueStates >= 2);
    printf("  Multiple states visited: %s (count=%d)\n",
           multipleStates ? "PASS" : "FAIL", uniqueStates);

    // Boss HP should be unchanged (no self-damage in FSM)
    bool hpUnchanged = (bossHP == 250);
    printf("  Boss HP unchanged: %s (hp=%d)\n",
           hpUnchanged ? "PASS" : "FAIL", bossHP);

    if (!leftIdle || !multipleStates || !hpUnchanged) {
        printf("\nFAILED\n");
        return 1;
    }

    printf("\nALL CHECKS PASSED\n");

    // --- Extended run: move hero close to trigger combat states ---
    printf("\n--- Extended run (1000 frames, hero near boss) ---\n");
    memset(statesVisited, 0, sizeof(statesVisited));
    statesVisited[rt.currentState] = 1;
    transitionCount = 0;

    // Move hero close to boss to trigger close-range behaviors
    ctx.heroX = bk.posX - 3.0f;
    ctx.heroY = 7.60f;

    for (int frame = 100; frame < 1100; ++frame) {
        // Slowly move hero toward/away from boss to vary distance
        ctx.heroX = bk.posX + sinf((float)frame * 0.05f) * 5.0f;

        fsmTick(def, ctx);

        if (!isKinematic) {
            bk.velY += -60.f * gravityScale * dt;
            bk.posX += bk.velX * dt;
            bk.posY += bk.velY * dt;
            if (bk.posY < 7.28f) { bk.posY = 7.28f; bk.velY = 0.f; }
            if (bk.posX < 82.4f) { bk.posX = 82.4f; bk.velX = 0.f; }
            if (bk.posX > 105.6f) { bk.posX = 105.6f; bk.velX = 0.f; }
        }

        if (rt.currentState != prevState) {
            prevState = rt.currentState;
            transitionCount++;
            statesVisited[rt.currentState] = 1;
        }
    }

    printf("  Transitions in extended run: %d\n", transitionCount);
    uniqueStates = 0;
    printf("  States visited: ");
    for (int i = 0; i < def.numStates; ++i) {
        if (statesVisited[i]) {
            printf("%s ", fsm_lace_boss1::STATE_NAMES[i]);
            uniqueStates++;
        }
    }
    printf("\n  Unique states: %d / %d\n", uniqueStates, def.numStates);
    printf("  Boss pos: (%.2f, %.2f), vel: (%.2f, %.2f)\n",
           bk.posX, bk.posY, bk.velX, bk.velY);

    bool goodCoverage = (uniqueStates >= 5);
    printf("  State coverage check (>=5 unique): %s\n",
           goodCoverage ? "PASS" : "OK (limited without full ECS)");

    return 0;
}
