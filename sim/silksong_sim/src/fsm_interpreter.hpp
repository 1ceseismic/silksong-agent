#pragma once

#include "fsm_types.hpp"
#include "fsm_actions.hpp"

namespace silksong {

static inline void fsmProcessEvent(const FsmDef &def, FsmActionCtx &ctx);
static inline void fsmEnterState(const FsmDef &def, FsmActionCtx &ctx,
                                  uint8_t stateIdx);

static inline void fsmInit(const FsmDef &def, FsmRuntime &rt,
                            const float *initFloats,
                            const int32_t *initInts,
                            const uint8_t *initBools)
{
    rt.currentState = def.startState;
    rt.pendingEvent = FSM_EVENT_NONE;

    for (int i = 0; i < FSM_MAX_ACTIONS_PER_STATE; ++i)
        rt.actionFinished[i] = 0;

    // Initialize typed variable arrays from baked initial values
    for (int i = 0; i < def.numFloatVars && i < FSM_MAX_FLOAT_VARS; ++i)
        rt.floatVars[i] = initFloats[i];
    for (int i = def.numFloatVars; i < FSM_MAX_FLOAT_VARS; ++i)
        rt.floatVars[i] = 0.f;

    for (int i = 0; i < def.numIntVars && i < FSM_MAX_INT_VARS; ++i)
        rt.intVars[i] = initInts[i];
    for (int i = def.numIntVars; i < FSM_MAX_INT_VARS; ++i)
        rt.intVars[i] = 0;

    for (int i = 0; i < def.numBoolVars && i < FSM_MAX_BOOL_VARS; ++i)
        rt.boolVars[i] = initBools[i];
    for (int i = def.numBoolVars; i < FSM_MAX_BOOL_VARS; ++i)
        rt.boolVars[i] = 0;

    // Clear timers and tracking state
    rt.waitTimer       = 0.f;
    rt.easeTimer       = 0.f;
    rt.easeFrom        = 0.f;
    rt.easeTo          = 0.f;
    rt.easeVarIdx      = 0;
    rt.lastAttack      = 255;
    rt.consecutiveCount = 0;
    for (int i = 0; i < 8; ++i)
        rt.missedCounts[i] = 0;
    rt.facingScale     = -1.f;  // Lace starts facing left (toward hero)
    rt.gravityScale    = 2.0f;  // Lace default gravity scale
    rt.isKinematic     = false;
    rt.hitboxActive    = false;
    rt.hitboxHalfW     = 0.f;
    rt.hitboxHalfH     = 0.f;
    rt.hitboxOffsetX   = 0.f;
    rt.hitboxOffsetY   = 0.f;
    rt.hitboxDamage    = 1;
    rt.alertRangeTimer = 0.f;
    rt.singReactTimer  = 0.f;
    rt.numExitActions  = 0;
}

// Chain depth bounded by state count; each transition consumes the pending event.
static inline void fsmEnterState(const FsmDef &def, FsmActionCtx &ctx,
                                  uint8_t stateIdx)
{
    FsmRuntime &rt = ctx.rt;
    constexpr int MAX_CHAIN = 32; // prevent infinite loops

    for (int chain = 0; chain < MAX_CHAIN; ++chain) {
        fsmActionsOnExit(rt, ctx);
        rt.currentState = stateIdx;
        rt.pendingEvent = FSM_EVENT_NONE;

        if (stateIdx >= (uint8_t)def.numStates) return;
        const FsmStateDef &state = def.states[stateIdx];

        for (int i = 0; i < state.actionCount && i < FSM_MAX_ACTIONS_PER_STATE; ++i)
            rt.actionFinished[i] = 0;

        // Run OnEnter for each action
        bool eventFired = false;
        for (int i = 0; i < state.actionCount && i < FSM_MAX_ACTIONS_PER_STATE; ++i) {
            int actIdx = state.actionStart + i;
            if (actIdx < 0 || actIdx >= def.numActions) return;
            const FsmActionDef &act = def.actions[actIdx];
            if (act.paramOffset >= (uint16_t)def.numParams) return;
            const float *p = def.params + act.paramOffset;

            fsmActionOnEnter(act, p, ctx);

            if (rt.pendingEvent != FSM_EVENT_NONE) {
                eventFired = true;
                break;
            }
        }

        // Auto-FINISHED for pass-through states
        if (!eventFired) {
            bool hasContinuous = false;
            for (int i = 0; i < state.actionCount && i < FSM_MAX_ACTIONS_PER_STATE; ++i) {
                int actIdx = state.actionStart + i;
                if (actIdx < 0 || actIdx >= def.numActions) break;
                const FsmActionDef &act = def.actions[actIdx];
                if ((act.flags & 1u) && !rt.actionFinished[i]) {
                    hasContinuous = true;
                    break;
                }
            }
            if (!hasContinuous) {
                rt.pendingEvent = 0; // FINISHED
                eventFired = true;
            }
        }

        if (!eventFired) return; // no event → stay in this state

        // Process event: find matching transition (iterative, not recursive)
        uint8_t ev = rt.pendingEvent;
        rt.pendingEvent = FSM_EVENT_NONE;
        uint8_t nextState = 255;

        // Check state-local transitions
        const FsmStateDef &curState = def.states[rt.currentState];
        for (int i = 0; i < curState.transitionCount; ++i) {
            int trIdx = curState.transitionStart + i;
            if (trIdx < 0 || trIdx >= def.numTransitions) break;
            if (def.transitions[trIdx].eventId == ev) {
                nextState = def.transitions[trIdx].targetState;
                break;
            }
        }
        // Check global transitions
        if (nextState == 255) {
            for (int i = 0; i < def.numGlobalTransitions; ++i) {
                if (def.globalTransitions[i].eventId == ev) {
                    nextState = def.globalTransitions[i].targetState;
                    break;
                }
            }
        }
        if (nextState == 255) return; // no matching transition → consume event

        stateIdx = nextState; // loop: enter the next state
    }
}

static inline void fsmProcessEvent(const FsmDef &def, FsmActionCtx &ctx)
{
    FsmRuntime &rt = ctx.rt;
    uint8_t ev = rt.pendingEvent;
    rt.pendingEvent = FSM_EVENT_NONE;

    if (ev == FSM_EVENT_NONE) return;

    // Search state-local transitions first
    const FsmStateDef &state = def.states[rt.currentState];
    for (int i = 0; i < state.transitionCount; ++i) {
        const FsmTransitionDef &tr =
            def.transitions[state.transitionStart + i];
        if (tr.eventId == ev) {
            fsmEnterState(def, ctx, tr.targetState);
            return;
        }
    }

    // Search global transitions (e.g., STUN, LAVA DAMAGE)
    for (int i = 0; i < def.numGlobalTransitions; ++i) {
        const FsmTransitionDef &tr = def.globalTransitions[i];
        if (tr.eventId == ev) {
            fsmEnterState(def, ctx, tr.targetState);
            return;
        }
    }

    // No matching transition: event consumed silently.
}

static inline void fsmFireEvent(FsmRuntime &rt, uint8_t eventId)
{
    if (rt.pendingEvent == FSM_EVENT_NONE)
        rt.pendingEvent = eventId;
}

static inline void fsmTick(const FsmDef &def, FsmActionCtx &ctx)
{
    FsmRuntime &rt = ctx.rt;

    // Guard: skip if FSM data not initialized (numStates==0 means empty/invalid)
    if (def.numStates <= 0 || rt.currentState >= (uint8_t)def.numStates) return;

    // Step 1: process any externally-injected event (e.g., STUN, LAVA DAMAGE)
    if (rt.pendingEvent != FSM_EVENT_NONE) {
        fsmProcessEvent(def, ctx);
        // After a state transition from external event, we still run OnUpdate
        // for the new state's continuous actions this frame (to match game
        // behavior where the new state's first OnUpdate runs immediately).
    }

    const FsmStateDef &state = def.states[rt.currentState];

    // Step 2: run OnUpdate for each unfinished continuous action
    for (int i = 0; i < state.actionCount && i < FSM_MAX_ACTIONS_PER_STATE; ++i) {
        if (rt.actionFinished[i]) continue;

        int actIdx = state.actionStart + i;
        if (actIdx < 0 || actIdx >= def.numActions) return;
        const FsmActionDef &act = def.actions[actIdx];

        // Only continuous actions have OnUpdate (flags bit 0)
        if (!(act.flags & 1u)) continue;

        if (act.paramOffset >= (uint16_t)def.numParams) return;
        const float *p = def.params + act.paramOffset;
        bool finished = fsmActionOnUpdate(act, p, ctx);

        if (finished)
            rt.actionFinished[i] = 1;

        // If an event was fired during OnUpdate, process it immediately
        // and stop running further actions for this frame.
        if (rt.pendingEvent != FSM_EVENT_NONE) {
            fsmProcessEvent(def, ctx);
            return;
        }
    }
}

static inline void fsmTickWithExternalEvents(
    const FsmDef &def,
    FsmActionCtx &ctx,
    bool stunTriggered,
    bool lavaDamageTriggered,
    uint8_t stunEventId,
    uint8_t lavaDamageEventId)
{
    FsmRuntime &rt = ctx.rt;

    // External events are injected before the FSM tick.
    // Priority: LAVA DAMAGE takes precedence (it's a damage response),
    // then STUN (combat mechanic).
    if (lavaDamageTriggered && rt.pendingEvent == FSM_EVENT_NONE) {
        rt.pendingEvent = lavaDamageEventId;
    }
    if (stunTriggered && rt.pendingEvent == FSM_EVENT_NONE) {
        rt.pendingEvent = stunEventId;
    }

    fsmTick(def, ctx);
}

} // namespace silksong
