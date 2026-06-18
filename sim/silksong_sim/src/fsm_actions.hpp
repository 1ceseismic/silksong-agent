#pragma once

// ======================================================================
// FSM Action Implementations
//
// Two functions per action type:
//   fsmActionOnEnter()  -- called once when state is entered
//   fsmActionOnUpdate() -- called each frame for continuous actions
//
// Each case reads params from the flat float array at the action's
// paramOffset. The FsmActionDef.flags bit 0 marks continuous actions.
//
// Source of truth: scripts/lace_boss1_control_fsm.json
// ======================================================================

#include "fsm_types.hpp"

#include <madrona/rand.hpp>
#include <cmath>

namespace silksong {

// -----------------------------------------------------------------------
// Context passed through every action call.  Avoids long param lists.
// -----------------------------------------------------------------------
struct FsmActionCtx {
    FsmRuntime     &rt;
    BossKinematics &bk;
    StunControl    &sc;
    float           heroX;
    float           heroY;
    float           heroIFrameRem;   // hero invuln timer (frames remaining)
    madrona::RNG   &rng;
    float           dt;              // fixed timestep (e.g. 0.02)
    int32_t        &bossHP;          // direct ref to boss HP pool
    float           gravityBase;     // base gravity (e.g. -60)
    float          &gravityScale;    // current gravity scale
    bool           &isKinematic;     // kinematic flag (no physics)
    // Hitbox state (collider on/off)
    bool           &hitboxActive;
    float          &hitboxHalfW;
    float          &hitboxHalfH;
    float          &hitboxOffsetX;
    float          &hitboxOffsetY;
    int16_t        &hitboxDamage;
    // Global freeze (applied to both boss and hero)
    float          &freezeTimer;
    // Hero damage callback -- returns true if hero was damaged
    float          &heroDamageOut;    // > 0 means hero takes this damage
    bool           &heroDamageBypass; // true = skip hero i-frame checks
    // Facing direction: +1 right, -1 left
    float          &facingScale;     // the X scale value (positive = right)
};

// Helper: facing direction as +1 or -1
static inline float fsmFacing(const FsmActionCtx &ctx) {
    return ctx.rt.facingScale >= 0.f ? 1.f : -1.f;
}

// Helper: fire an event (set pending, checked after all actions in pass)
static inline void fsmSetPendingEvent(FsmRuntime &rt, uint8_t eventId) {
    if (eventId != FSM_EVENT_NONE && rt.pendingEvent == FSM_EVENT_NONE) {
        rt.pendingEvent = eventId;
    }
}

// fsmFireEventF is defined after fsmReadVar (below) due to dependency

// Variable reference encoding: the bake script encodes variable references as
//   VAR_REF_OFFSET + type*256 + index
// where VAR_REF_OFFSET = 10000.0, type: 0=float, 1=int, 2=bool, 3=string.
// Values below 10000 are literal values (or small direct indices for legacy
// actions that use separate isVar flags).
constexpr float VAR_REF_OFFSET = 10000.f;

// Decode a variable reference.  Returns true if param is a var ref.
static inline bool fsmIsVarRef(float param) {
    return param >= VAR_REF_OFFSET;
}

// Check if a param is the NaN sentinel (meaning "None / leave unchanged").
static inline bool fsmIsNone(float param) {
    return std::isnan(param);
}

static inline void fsmDecodeVarRef(float param, int &type, int &index) {
    int encoded = (int)(param - VAR_REF_OFFSET);
    type  = encoded / 256;
    index = encoded % 256;
}

// Helper: read a value that may be a variable reference or a literal.
// If it's a var ref, read the variable; otherwise return the literal.
static inline float fsmReadVar(const FsmRuntime &rt, float param) {
    if (!fsmIsVarRef(param)) return param;
    int type, index;
    fsmDecodeVarRef(param, type, index);
    switch (type) {
    case 0: // float
        return (index >= 0 && index < FSM_MAX_FLOAT_VARS) ? rt.floatVars[index] : 0.f;
    case 1: // int
        return (index >= 0 && index < FSM_MAX_INT_VARS) ? (float)rt.intVars[index] : 0.f;
    case 2: // bool
        return (index >= 0 && index < FSM_MAX_BOOL_VARS) ? (float)rt.boolVars[index] : 0.f;
    default:
        return 0.f;
    }
}

// Helper: read a float variable (param may be var ref or literal)
static inline float fsmReadFloatVar(const FsmRuntime &rt, float param) {
    return fsmReadVar(rt, param);
}

// Helper: fire an event from a float param (may be literal ID or var ref)
static inline void fsmFireEventF(FsmRuntime &rt, float param) {
    float resolved = fsmIsVarRef(param) ? fsmReadVar(rt, param) : param;
    int id = (int)resolved;
    if (id >= 0 && id < 255) {
        fsmSetPendingEvent(rt, (uint8_t)id);
    }
}

// Helper: read an int variable (param may be var ref or literal)
static inline int32_t fsmReadIntVar(const FsmRuntime &rt, float param) {
    if (fsmIsVarRef(param)) {
        int type, index;
        fsmDecodeVarRef(param, type, index);
        if (type == 1 && index >= 0 && index < FSM_MAX_INT_VARS)
            return rt.intVars[index];
        if (type == 0 && index >= 0 && index < FSM_MAX_FLOAT_VARS)
            return (int32_t)rt.floatVars[index];
        return 0;
    }
    return (int32_t)param;
}

// Helper: read a bool variable (param may be var ref or literal)
static inline bool fsmReadBoolVar(const FsmRuntime &rt, float param) {
    if (fsmIsVarRef(param)) {
        int type, index;
        fsmDecodeVarRef(param, type, index);
        if (type == 2 && index >= 0 && index < FSM_MAX_BOOL_VARS)
            return rt.boolVars[index] != 0;
        return false;
    }
    return param != 0.f;
}

// Helper: write to a variable given its encoded reference.
// For SetBoolValue, SetFloatValue, SetIntValue, etc.
static inline void fsmWriteFloatVar(FsmRuntime &rt, float param, float value) {
    if (fsmIsVarRef(param)) {
        int type, index;
        fsmDecodeVarRef(param, type, index);
        if (type == 0 && index >= 0 && index < FSM_MAX_FLOAT_VARS)
            rt.floatVars[index] = value;
        return;
    }
    int idx = (int)param;
    if (idx >= 0 && idx < FSM_MAX_FLOAT_VARS)
        rt.floatVars[idx] = value;
}

static inline void fsmWriteIntVar(FsmRuntime &rt, float param, int32_t value) {
    if (fsmIsVarRef(param)) {
        int type, index;
        fsmDecodeVarRef(param, type, index);
        if (type == 1 && index >= 0 && index < FSM_MAX_INT_VARS)
            rt.intVars[index] = value;
        return;
    }
    int idx = (int)param;
    if (idx >= 0 && idx < FSM_MAX_INT_VARS)
        rt.intVars[idx] = value;
}

static inline void fsmWriteBoolVar(FsmRuntime &rt, float param, bool value) {
    if (fsmIsVarRef(param)) {
        int type, index;
        fsmDecodeVarRef(param, type, index);
        if (type == 2 && index >= 0 && index < FSM_MAX_BOOL_VARS)
            rt.boolVars[index] = value ? 1 : 0;
        return;
    }
    int idx = (int)param;
    if (idx >= 0 && idx < FSM_MAX_BOOL_VARS)
        rt.boolVars[idx] = value ? 1 : 0;
}

// Helper: get the raw int index from a var ref (for cases where we need
// the slot index directly, e.g. EaseFloat target var)
static inline int fsmVarIndex(float param) {
    if (fsmIsVarRef(param)) {
        int type, index;
        fsmDecodeVarRef(param, type, index);
        return index;
    }
    return (int)param;
}

// -----------------------------------------------------------------------
// fsmActionOnEnter -- called once per action when state is entered
// -----------------------------------------------------------------------
static inline void fsmActionOnEnter(const FsmActionDef &act,
                                     const float *p,
                                     FsmActionCtx &ctx)
{
    FsmRuntime &rt = ctx.rt;

    switch (act.type) {

    // ---- Movement ----

    case FsmActionType::SetVelocityByScale: {
        // p[0] = speed (always set), p[1] = ySpeed (NaN = None / leave unchanged)
        // Game: velX = speed * sign(localScale.x), velY only set if !ySpeed.IsNone
        ctx.bk.velX = fsmReadVar(rt, p[0]) * fsmFacing(ctx);
        if (!fsmIsNone(p[1])) {
            ctx.bk.velY = fsmReadVar(rt, p[1]);
        }
        break;
    }

    case FsmActionType::SetVelocity2d: {
        // p[0] = x, p[1] = y
        // SetVelocity2d uses a Vector2 field that sets both axes.
        // Literal 0.0 means "set to 0" (stop), not "leave unchanged".
        ctx.bk.velX = fsmReadVar(rt, p[0]);
        ctx.bk.velY = fsmReadVar(rt, p[1]);
        break;
    }

    case FsmActionType::SetIsKinematic2d: {
        // p[0] = isKinematic (1.0 or 0.0)
        ctx.isKinematic = (p[0] != 0.f);
        break;
    }

    case FsmActionType::SetGravity2dScale: {
        // p[0] = gravity scale (may be var ref or literal)
        ctx.gravityScale = fsmReadVar(rt, p[0]);
        break;
    }

    case FsmActionType::SetPosition2d: {
        // p[0] = x, p[1] = y
        // None (NaN) means "leave axis unchanged". Otherwise apply the value
        // (which may be a literal float or a variable reference).
        if (!fsmIsNone(p[0]))
            ctx.bk.posX = fsmReadVar(rt, p[0]);
        if (!fsmIsNone(p[1]))
            ctx.bk.posY = fsmReadVar(rt, p[1]);
        break;
    }

    case FsmActionType::GetPosition2d: {
        // p[0] = xVarRef, p[1] = yVarRef
        if (!fsmIsNone(p[0])) fsmWriteFloatVar(rt, p[0], ctx.bk.posX);
        if (!fsmIsNone(p[1])) fsmWriteFloatVar(rt, p[1], ctx.bk.posY);
        break;
    }

    case FsmActionType::GetSelfPosition: {
        // p[0] = xVarRef, p[1] = yVarRef, p[2] = zVarRef
        if (!fsmIsNone(p[0])) fsmWriteFloatVar(rt, p[0], ctx.bk.posX);
        if (!fsmIsNone(p[1])) fsmWriteFloatVar(rt, p[1], ctx.bk.posY);
        break;
    }

    case FsmActionType::Translate: {
        // p[0] = x (may be var ref), p[1] = y (may be var ref), p[2] = z (ignored)
        // C# defaults: everyFrame=true, perSecond=true -> multiply by dt
        float dx = fsmReadVar(rt, p[0]) * ctx.dt;
        float dy = fsmReadVar(rt, p[1]) * ctx.dt;
        ctx.bk.posX += dx;
        ctx.bk.posY += dy;
        break;
    }

    case FsmActionType::ClampPosition: {
        // p[0]=minX, p[1]=maxX, p[2]=minY, p[3]=maxY
        if (p[0] != 0.f || p[1] != 0.f) {
            ctx.bk.posX = fmaxf(fminf(ctx.bk.posX, p[1]), p[0]);
        }
        if (p[2] != 0.f || p[3] != 0.f) {
            ctx.bk.posY = fmaxf(fminf(ctx.bk.posY, p[3]), p[2]);
        }
        break;
    }

    // ---- Facing ----

    case FsmActionType::FaceObjectV2:
    case FsmActionType::FaceObjectV4: {
        bool spriteFacesRight = (p[0] != 0.f);
        bool heroIsRight = (ctx.heroX > ctx.bk.posX);
        if (heroIsRight == spriteFacesRight)
            ctx.rt.facingScale = 1.f;
        else
            ctx.rt.facingScale = -1.f;
        ctx.facingScale = ctx.rt.facingScale;
        break;
    }

    case FsmActionType::FlipScale: {
        ctx.rt.facingScale = -ctx.rt.facingScale;
        ctx.facingScale = ctx.rt.facingScale;
        break;
    }

    case FsmActionType::SetScale: {
        ctx.rt.facingScale = (p[0] >= 0.f) ? 1.f : -1.f;
        ctx.facingScale = ctx.rt.facingScale;
        break;
    }

    case FsmActionType::GetScale: {
        // p[0] = xScaleVarRef, p[1] = yScaleVarRef, p[2] = zScaleVarRef
        fsmWriteFloatVar(rt, p[0], ctx.facingScale);
        break;
    }

    // ---- Variables ----

    case FsmActionType::SetBoolValue: {
        // p[0] = varRef, p[1] = value (0 or 1)
        fsmWriteBoolVar(rt, p[0], p[1] != 0.f);
        break;
    }

    case FsmActionType::SetFloatValue: {
        // p[0] = varRef, p[1] = value
        fsmWriteFloatVar(rt, p[0], fsmReadVar(rt, p[1]));
        break;
    }

    case FsmActionType::SetIntValue: {
        // p[0] = varRef, p[1] = value
        fsmWriteIntVar(rt, p[0], (int32_t)p[1]);
        break;
    }

    case FsmActionType::IntAdd: {
        // p[0] = varRef, p[1] = addValue
        int32_t cur = fsmReadIntVar(rt, p[0]);
        fsmWriteIntVar(rt, p[0], cur + (int32_t)p[1]);
        break;
    }

    case FsmActionType::FloatAdd: {
        // p[0] = varRef, p[1] = addValue
        float cur = fsmReadVar(rt, p[0]);
        fsmWriteFloatVar(rt, p[0], cur + fsmReadVar(rt, p[1]));
        break;
    }

    case FsmActionType::FloatMultiply: {
        // p[0] = varRef, p[1] = multiplyBy
        float cur = fsmReadVar(rt, p[0]);
        fsmWriteFloatVar(rt, p[0], cur * p[1]);
        break;
    }

    case FsmActionType::FloatClamp: {
        // p[0] = varRef, p[1] = minValue, p[2] = maxValue
        float cur = fsmReadVar(rt, p[0]);
        fsmWriteFloatVar(rt, p[0], fmaxf(fminf(cur, p[2]), p[1]));
        break;
    }

    case FsmActionType::MultiplyIntByFloat: {
        // p[0] = intVarRef (source), p[1] = multiplyFloat, p[2] = resultIntVarRef
        int32_t src = fsmReadIntVar(rt, p[0]);
        fsmWriteIntVar(rt, p[2], (int32_t)((float)src * p[1]));
        break;
    }

    case FsmActionType::RandomFloat: {
        // p[0] = min, p[1] = max, p[2] = resultVarRef
        float t = ctx.rng.sampleUniform();
        fsmWriteFloatVar(rt, p[2], p[0] + t * (p[1] - p[0]));
        break;
    }

    case FsmActionType::RandomInt: {
        // p[0] = min, p[1] = max, p[2] = resultVarRef, p[3] = noRepeat
        int lo = (int)p[0];
        int hi = (int)p[1];
        fsmWriteIntVar(rt, p[2], ctx.rng.sampleI32(lo, hi));
        break;
    }

    // ---- Comparisons / Tests ----

    case FsmActionType::BoolTest: {
        // p[0] = varRef, p[1] = trueEvent, p[2] = falseEvent
        bool val = fsmReadBoolVar(rt, p[0]);
        if (val)
            fsmFireEventF(rt, p[1]);
        else
            fsmFireEventF(rt, p[2]);
        break;
    }

    case FsmActionType::BoolTestMulti: {
        // p[0]=trueEvent, p[1]=falseEvent, p[2]=storeResult, p[3]=numPairs
        // p[4..4+n-1]=boolVariables, p[4+n..4+2n-1]=boolStates
        int n = (int)p[3];
        bool allMatch = (n > 0);
        for (int i = 0; i < n; ++i) {
            bool varVal = fsmReadBoolVar(rt, p[4 + i]);
            bool stateVal = fsmReadBoolVar(rt, p[4 + n + i]);
            if (varVal != stateVal) {
                allMatch = false;
                break;
            }
        }
        if (!fsmIsNone(p[2])) fsmWriteBoolVar(rt, p[2], allMatch);
        if (allMatch)
            fsmFireEventF(rt, p[0]);
        else
            fsmFireEventF(rt, p[1]);
        break;
    }

    case FsmActionType::BoolAllTrue: {
        // p[0]=sendEvent, p[1]=storeResult, p[2]=numBools, p[3..]=boolVarRefs
        int n = (int)p[2];
        bool allTrue = (n > 0);
        for (int i = 0; i < n; ++i) {
            if (!fsmReadBoolVar(rt, p[3 + i])) {
                allTrue = false;
                break;
            }
        }
        if (!fsmIsNone(p[1])) fsmWriteBoolVar(rt, p[1], allTrue);
        if (allTrue) fsmFireEventF(rt, p[0]);
        break;
    }

    case FsmActionType::FloatCompare: {
        // p[0] = float1 (var ref or literal), p[1] = float2 (var ref or literal)
        // p[2] = tolerance, p[3] = eqEvent, p[4] = ltEvent, p[5] = gtEvent
        float v1 = fsmReadVar(rt, p[0]);
        float v2 = fsmReadVar(rt, p[1]);
        float tol = p[2];
        float diff = v1 - v2;
        if (fabsf(diff) <= tol)
            fsmFireEventF(rt, p[3]);
        else if (diff < -tol)
            fsmFireEventF(rt, p[4]);
        else
            fsmFireEventF(rt, p[5]);
        break;
    }

    case FsmActionType::FloatTestToBool: {
        // p[0] = float1 (var ref or literal), p[1] = float2 (var ref or literal)
        // p[2] = tolerance, p[3] = eqBoolRef, p[4] = ltBoolRef, p[5] = gtBoolRef
        float f1 = fsmReadVar(rt, p[0]);
        float f2 = fsmReadVar(rt, p[1]);
        float tol = p[2];
        float diff = f1 - f2;
        bool eq = fabsf(diff) <= tol;
        bool lt = diff < -tol;
        bool gt = diff >  tol;
        fsmWriteBoolVar(rt, p[3], eq);
        fsmWriteBoolVar(rt, p[4], lt);
        fsmWriteBoolVar(rt, p[5], gt);
        break;
    }

    case FsmActionType::IntCompare: {
        // p[0] = integer1 (var ref or literal), p[1] = integer2 (var ref or literal)
        // p[2] = eqEvent, p[3] = ltEvent, p[4] = gtEvent
        int32_t v1 = fsmReadIntVar(rt, p[0]);
        int32_t v2 = fsmReadIntVar(rt, p[1]);
        if (v1 == v2)
            fsmFireEventF(rt, p[2]);
        else if (v1 < v2)
            fsmFireEventF(rt, p[3]);
        else
            fsmFireEventF(rt, p[4]);
        break;
    }

    case FsmActionType::FloatInRange: {
        // p[0] = varRef, p[1] = lowerValue, p[2] = upperValue
        // p[3] = boolVarRef, p[4] = trueEvent, p[5] = falseEvent
        float val = fsmReadVar(rt, p[0]);
        bool inRange = val >= p[1] && val <= p[2];
        if (!fsmIsNone(p[3])) fsmWriteBoolVar(rt, p[3], inRange);
        if (inRange)
            fsmFireEventF(rt, p[4]);
        else
            fsmFireEventF(rt, p[5]);
        break;
    }

    // ---- Distance / Position queries ----

    case FsmActionType::GetDistance: {
        // p[0] = resultVarRef
        float dx = ctx.bk.posX - ctx.heroX;
        float dy = ctx.bk.posY - ctx.heroY;
        fsmWriteFloatVar(rt, p[0], sqrtf(dx*dx + dy*dy));
        break;
    }

    case FsmActionType::GetXDistance: {
        // p[0] = resultVarRef
        // In the game GetXDistance stores abs(target.x - owner.x)
        fsmWriteFloatVar(rt, p[0], fabsf(ctx.heroX - ctx.bk.posX));
        break;
    }

    case FsmActionType::CheckXPosition: {
        // p[0] = compareTo (var ref or literal), p[1] = compareToOffset, p[2] = tolerance
        // p[3] = eqEvent, p[4] = eqBoolRef, p[5] = ltEvent, p[6] = ltBoolRef
        // p[7] = gtEvent, p[8] = gtBoolRef
        float compareVal = fsmReadVar(rt, p[0]) + p[1];
        float tol = p[2];
        float diff = ctx.bk.posX - compareVal;
        bool eq = fabsf(diff) <= tol;
        bool lt = diff < -tol;
        bool gt = diff >  tol;

        if (eq)      fsmFireEventF(rt, p[3]);
        else if (lt) fsmFireEventF(rt, p[5]);
        else         fsmFireEventF(rt, p[7]);

        fsmWriteBoolVar(rt, p[4], eq);
        fsmWriteBoolVar(rt, p[6], lt);
        fsmWriteBoolVar(rt, p[8], gt);
        break;
    }

    case FsmActionType::CheckYPosition: {
        // p[0] = compareTo (var ref or literal), p[1] = compareToOffset, p[2] = tolerance
        // p[3] = eqEvent, p[4] = ltEvent, p[5] = gtEvent
        float compareVal = fsmReadVar(rt, p[0]) + p[1];
        float tol = p[2];
        float diff = ctx.bk.posY - compareVal;
        if (fabsf(diff) <= tol)      fsmFireEventF(rt, p[3]);
        else if (diff < -tol)        fsmFireEventF(rt, p[4]);
        else                         fsmFireEventF(rt, p[5]);
        break;
    }

    case FsmActionType::CheckYPositionV2: {
        // p[0] = compareTo (var ref or literal), p[1] = compareToOffset, p[2] = tolerance
        // p[3] = eqEvent, p[4] = eqBoolRef, p[5] = ltEvent, p[6] = ltBoolRef
        // p[7] = gtEvent, p[8] = gtBoolRef
        float compareVal = fsmReadVar(rt, p[0]) + p[1];
        float tol = p[2];
        float diff = ctx.bk.posY - compareVal;
        bool eq = fabsf(diff) <= tol;
        bool lt = diff < -tol;
        bool gt = diff >  tol;

        if (eq)      fsmFireEventF(rt, p[3]);
        else if (lt) fsmFireEventF(rt, p[5]);
        else         fsmFireEventF(rt, p[7]);

        fsmWriteBoolVar(rt, p[4], eq);
        fsmWriteBoolVar(rt, p[6], lt);
        fsmWriteBoolVar(rt, p[8], gt);
        break;
    }

    case FsmActionType::CheckTargetDirection: {
        // p[0] = aboveEvent, p[1] = belowEvent, p[2] = rightEvent, p[3] = leftEvent
        // p[4] = aboveBoolRef, p[5] = belowBoolRef, p[6] = rightBoolRef, p[7] = leftBoolRef
        // p[8] = selfOffsetX, p[9] = selfOffsetY
        float sx = ctx.bk.posX + p[8];
        float sy = ctx.bk.posY + p[9];
        bool above = ctx.heroY > sy;
        bool below = ctx.heroY < sy;
        bool right = ctx.heroX > sx;
        bool left  = ctx.heroX < sx;

        if (above) fsmFireEventF(rt, p[0]);
        if (below) fsmFireEventF(rt, p[1]);
        if (right) fsmFireEventF(rt, p[2]);
        if (left)  fsmFireEventF(rt, p[3]);

        fsmWriteBoolVar(rt, p[4], above);
        fsmWriteBoolVar(rt, p[5], below);
        fsmWriteBoolVar(rt, p[6], right);
        fsmWriteBoolVar(rt, p[7], left);
        break;
    }

    case FsmActionType::CheckIsCharacterGrounded: {
        // Simple ground check: boss Y near floor
        // p[0] = groundDistance, p[1] = groundedEvent, p[2] = notGroundedEvent
        // We approximate: grounded if velY <= 0 and position is near floor
        // The real check uses raycasts; we simplify for the sim.
        // Actual grounding is handled by the integrator; this just fires events.
        // For the FSM, we check if boss is within groundDistance of the floor.
        // This is a continuous action but we handle the initial check in OnEnter.
        break;
    }

    // ---- Timers ----

    case FsmActionType::Wait: {
        // p[0] = time, p[1] = finishEventId
        rt.waitTimer = p[0];
        break;
    }

    case FsmActionType::WaitRandom: {
        // p[0] = min, p[1] = max, p[2] = finishEventId
        float t = ctx.rng.sampleUniform();
        rt.waitTimer = p[0] + t * (p[1] - p[0]);
        break;
    }

    // NextFrameEvent: fires on first OnUpdate, no OnEnter work needed.
    case FsmActionType::NextFrameEvent:
        break;

    case FsmActionType::EaseFloat: {
        // p[0] = fromValue, p[1] = toValue, p[2] = varRef, p[3] = time
        // p[4] = speed, p[5] = delay, p[6] = reverse, p[7] = finishEvent
        rt.easeFrom  = p[0];
        rt.easeTo    = p[1];
        rt.easeVarIdx = (uint8_t)fsmVarIndex(p[2]);
        rt.easeTimer = 0.f;
        if (rt.easeVarIdx < FSM_MAX_FLOAT_VARS)
            rt.floatVars[rt.easeVarIdx] = p[0];
        break;
    }

    // ---- Combat ----

    case FsmActionType::SetDamageHeroAmount: {
        // p[0] = amount
        ctx.sc.damageAmount = (int16_t)p[0];
        break;
    }

    case FsmActionType::SetRecoilSpeed: {
        // p[0] = speed
        ctx.sc.recoilSpeed = (int)p[0];
        break;
    }

    case FsmActionType::SetRecoilBlocked: {
        // p[0] = blocked (1 = all directions blocked)
        ctx.sc.recoilBlocked = (p[0] != 0.f);
        break;
    }

    case FsmActionType::SetSpecialDeath: {
        // p[0] = hasSpecialDeath
        ctx.sc.specialDeath = (p[0] != 0.f);
        break;
    }

    case FsmActionType::SetInvincible: {
        // p[0] = invincible, p[1] = InvincibleFromDirection (var ref, ignored)
        // p[2] = resetOnStateExit
        ctx.sc.isInvincible = (p[0] != 0.f);
        if (p[2] != 0.f && rt.numExitActions < FSM_MAX_EXIT_ACTIONS) {
            rt.exitActions[rt.numExitActions++] = {act.type, act.paramOffset};
        }
        break;
    }

    case FsmActionType::SubtractHP: {
        // p[0] = amount
        ctx.bossHP -= (int32_t)p[0];
        break;
    }

    case FsmActionType::CompareHP: {
        // p[0] = compare value (var ref or literal), p[1] = eqEvent, p[2] = ltEvent, p[3] = gtEvent
        int32_t compareVal = fsmReadIntVar(rt, p[0]);
        if (ctx.bossHP == compareVal)      fsmFireEventF(rt, p[1]);
        else if (ctx.bossHP < compareVal)  fsmFireEventF(rt, p[2]);
        else                                fsmFireEventF(rt, p[3]);
        break;
    }

    case FsmActionType::GetHP: {
        // p[0] = storeVarRef (int var)
        fsmWriteIntVar(rt, p[0], ctx.bossHP);
        break;
    }

    case FsmActionType::DamageHeroDirectly: {
        // p[0] = damageAmount
        ctx.heroDamageOut = p[0];
        ctx.heroDamageBypass = true;
        break;
    }

    case FsmActionType::CanHeroTakeDamage: {
        // p[0] = canTakeDmgEvent, p[1] = cannotTakeDmgEvent (cancelEvent)
        if (ctx.heroIFrameRem > 0.f) {
            fsmFireEventF(rt, p[1]);  // hero is invuln -> cancel
        } else {
            fsmFireEventF(rt, p[0]);
        }
        break;
    }

    case FsmActionType::FreezeMoment: {
        static constexpr float FREEZE_DURATIONS[] = {
            0.28f,   // 0: HeroDamage
            0.024f,  // 1: EnemyDeath
            0.35f,   // 2: BossDeathStrike
            0.25f,   // 3: NailClashEffect
            0.25f,   // 4: BossStun
            0.015f,  // 5: EnemyDeathShort
            0.02f,   // 6: QuickFreeze
            0.1f,    // 7: ZapFreeze
            0.03f,   // 8: WitchBindHit
            0.15f,   // 9: HeroDamageShort
        };
        int type = (int)p[0];
        if (type >= 0 && type < 10)
            ctx.freezeTimer = FREEZE_DURATIONS[type];
        else
            ctx.freezeTimer = 0.1f;
        break;
    }

    // ---- Colliders ----

    case FsmActionType::SetHitboxGeometry: {
        // p[0]=halfW, p[1]=halfH, p[2]=offsetX, p[3]=offsetY, p[4]=activate (1/0)
        // Write through ctx references so the write-back in sim.cpp picks up changes
        ctx.hitboxHalfW = p[0];
        ctx.hitboxHalfH = p[1];
        ctx.hitboxOffsetX = p[2];
        ctx.hitboxOffsetY = p[3];
        ctx.hitboxActive = (p[4] != 0.f);
        // Also set on rt so FSM state is consistent within the tick
        ctx.rt.hitboxHalfW = p[0];
        ctx.rt.hitboxHalfH = p[1];
        ctx.rt.hitboxOffsetX = p[2];
        ctx.rt.hitboxOffsetY = p[3];
        ctx.rt.hitboxActive = (p[4] != 0.f);
        break;
    }

    case FsmActionType::SetCollider: {
        // p[0] = active (1 or 0), p[1] = resetOnExit
        ctx.hitboxActive = (p[0] != 0.f);
        ctx.rt.hitboxActive = ctx.hitboxActive;
        if (p[1] != 0.f && rt.numExitActions < FSM_MAX_EXIT_ACTIONS) {
            rt.exitActions[rt.numExitActions++] = {act.type, act.paramOffset};
        }
        break;
    }

    case FsmActionType::SetPolygonCollider: {
        // p[0] = active (1 or 0), p[1] = resetOnExit
        ctx.hitboxActive = (p[0] != 0.f);
        ctx.rt.hitboxActive = ctx.hitboxActive;
        if (p[1] != 0.f && rt.numExitActions < FSM_MAX_EXIT_ACTIONS) {
            rt.exitActions[rt.numExitActions++] = {act.type, act.paramOffset};
        }
        break;
    }

    // ---- Events ----

    case FsmActionType::SendEvent: {
        // p[0] = eventId, p[1] = delay (ignored -- instant in sim)
        fsmFireEventF(rt, p[0]);
        break;
    }

    case FsmActionType::SendEventByName: {
        // p[0] = eventId (baked from name lookup), p[1] = delay
        fsmFireEventF(rt, p[0]);
        break;
    }

    case FsmActionType::SendEventByNameV2: {
        // p[0] = eventId, p[1] = delay
        fsmFireEventF(rt, p[0]);
        break;
    }

    case FsmActionType::SendEventByScale: {
        // Fire one of two events based on facing direction.
        // p[0] = positiveScaleEvent, p[1] = negativeScaleEvent
        if (ctx.facingScale >= 0.f)
            fsmFireEventF(rt, p[0]);
        else
            fsmFireEventF(rt, p[1]);
        break;
    }

    case FsmActionType::SendRandomEvent: {
        // p[0] = numEvents
        // p[1..n] = eventIds
        // p[n+1..2n] = weights
        int n = (int)p[0];
        if (n <= 0) break;

        float totalWeight = 0.f;
        for (int i = 0; i < n; ++i)
            totalWeight += p[n + 1 + i];

        if (totalWeight <= 0.f) break;

        float roll = ctx.rng.sampleUniform() * totalWeight;
        float cumulative = 0.f;
        int picked = 0;
        for (int i = 0; i < n; ++i) {
            cumulative += p[n + 1 + i];
            if (roll < cumulative) { picked = i; break; }
            if (i == n - 1) picked = i;
        }
        fsmFireEventF(rt, p[1 + picked]);
        break;
    }

    case FsmActionType::SendRandomEventV3: {
        // Weighted random with consecutive/missed tracking.
        // p[0] = numEvents
        // p[1..n] = eventIds
        // p[n+1..2n] = weights
        // p[2n+1..3n] = eventMax (max consecutive)
        // p[3n+1..4n] = missedMax
        int n = (int)p[0];
        if (n <= 0) break;

        const float *eventIds   = &p[1];
        const float *weights    = &p[1 + n];
        const float *eventMaxes = &p[1 + 2 * n];
        const float *missedMaxes = &p[1 + 3 * n];

        float adjWeights[8];
        float totalWeight = 0.f;
        int forceIdx = -1;

        for (int i = 0; i < n && i < 8; ++i) {
            float w = weights[i];
            // Suppress if exceeded consecutive limit
            int evMax = (int)eventMaxes[i];
            if ((int)eventIds[i] == (int)rt.lastAttack
                && (int)rt.consecutiveCount >= evMax) {
                w = 0.f;
            }
            // Force if missed too many
            int msMax = (int)missedMaxes[i];
            uint8_t eid = (uint8_t)eventIds[i];
            if (msMax > 0 && (int)rt.missedCounts[eid % 8] >= msMax) {
                forceIdx = i;
            }
            adjWeights[i] = w;
            totalWeight += w;
        }

        int picked;
        if (forceIdx >= 0) {
            picked = forceIdx;
        } else if (totalWeight <= 0.f) {
            picked = (int)(ctx.rng.sampleUniform() * (float)n);
            if (picked >= n) picked = n - 1;
        } else {
            float roll = ctx.rng.sampleUniform() * totalWeight;
            float cumulative = 0.f;
            picked = 0;
            for (int i = 0; i < n; ++i) {
                cumulative += adjWeights[i];
                if (roll < cumulative) { picked = i; break; }
                if (i == n - 1) picked = i;
            }
        }

        uint8_t evId = (uint8_t)eventIds[picked];

        // Update consecutive tracking
        if (evId == rt.lastAttack) {
            rt.consecutiveCount = (uint8_t)(rt.consecutiveCount + 1);
        } else {
            rt.consecutiveCount = 1;
        }
        rt.lastAttack = evId;

        // Update missed counters (keyed by event ID, not slot position)
        for (int i = 0; i < n && i < 8; ++i) {
            uint8_t eid = (uint8_t)eventIds[i];
            if (i == picked)
                rt.missedCounts[eid % 8] = 0;
            else if (rt.missedCounts[eid % 8] < 255)
                rt.missedCounts[eid % 8] = (uint8_t)(rt.missedCounts[eid % 8] + 1);
        }

        fsmSetPendingEvent(rt, evId);
        break;
    }

    // ---- Raycasting ----

    case FsmActionType::RayCast2dV2: {
        // Simplified: store hit bool in storeDidHit var.
        // p[0] = distance, p[1] = repeatInterval, p[2] = hitEvent, p[3] = noHitEvent
        // p[4] = storeDidHitBoolRef, p[5] = storeHitDist, p[6] = storeDist
        float facing = fsmFacing(ctx);
        float probeX = ctx.bk.posX + facing * p[0];
        bool wallHit = (probeX < 82.4f || probeX > 105.6f);
        fsmWriteBoolVar(rt, p[4], wallHit);
        if (wallHit)
            fsmFireEventF(rt, p[2]);
        else
            fsmFireEventF(rt, p[3]);
        break;
    }

    // ---- Animation position (AnimatePositionTo) ----

    case FsmActionType::AnimatePositionTo: {
        // Tween boss position toward a target over time.
        // Bake encodes: p[0] = time, p[1] = speed, p[2] = delay, p[3] = reverse, p[4] = finishEvent
        // For CrossSlash: animates to hero position over p[0] seconds.
        rt.easeFrom = ctx.bk.posX;
        rt.easeTo   = ctx.heroX;  // target is always hero position at time of entry
        rt.easeTimer = 0.f;
        rt.waitTimer = p[0];  // duration
        break;
    }

    // ---- Misc ----

    case FsmActionType::PreventInvincibleEffect:
    case FsmActionType::ReceivedDamage:
    case FsmActionType::SetHitEffectOrigin:
    case FsmActionType::SetStringValue:
        // ReceivedDamage: event routing for damage types (dormant states only)
        break;

    case FsmActionType::GetFsmFloat: {
        fsmWriteFloatVar(rt, p[0], p[1]);
        break;
    }

    case FsmActionType::DecelerateXY:
        // Continuous-only action. OnEnter is a noop.
        break;

    case FsmActionType::CheckAlertRange:
    case FsmActionType::CheckAlertRangeByName: {
        rt.alertRangeTimer = 0.f;
        rt.alertRangeInRange = false;
        break;
    }

    case FsmActionType::CheckHeroPerformanceRegionV2:
        // Continuous action -- sing detection.
        rt.singReactTimer = 0.f;
        break;

    case FsmActionType::CheckCollisionSide:
        break;
    case FsmActionType::CheckCollisionSideEnter:
        rt.collisionSidePrev = 0;
        break;

    case FsmActionType::Noop:
    default:
        break;
    }
}

// -----------------------------------------------------------------------
// fsmActionOnUpdate -- called each frame for continuous (flagged) actions
//
// Returns: true if the action is finished (no more OnUpdate calls needed)
// -----------------------------------------------------------------------
static inline bool fsmActionOnUpdate(const FsmActionDef &act,
                                      const float *p,
                                      FsmActionCtx &ctx)
{
    FsmRuntime &rt = ctx.rt;

    switch (act.type) {

    case FsmActionType::DecelerateXY: {
        // p[0] = decelX, p[1] = decelY  (NaN = None / leave axis unchanged)
        // Per-frame velocity scaling (multiplicative deceleration).
        if (!fsmIsNone(p[0])) ctx.bk.velX *= p[0];
        if (!fsmIsNone(p[1])) ctx.bk.velY *= p[1];
        return false;  // never finishes
    }

    case FsmActionType::Wait: {
        // p[0] = time (initial -- stored in waitTimer on enter)
        // p[1] = finishEventId
        rt.waitTimer -= ctx.dt;
        if (rt.waitTimer <= 0.f) {
            fsmFireEventF(rt, p[1]);
            return true;
        }
        return false;
    }

    case FsmActionType::WaitRandom: {
        // p[0] = min, p[1] = max, p[2] = finishEventId
        rt.waitTimer -= ctx.dt;
        if (rt.waitTimer <= 0.f) {
            fsmFireEventF(rt, p[2]);
            return true;
        }
        return false;
    }

    case FsmActionType::NextFrameEvent: {
        // Fire event on first OnUpdate call (simulates "next frame" behavior).
        // p[0] = eventId
        fsmFireEventF(rt, p[0]);
        return true;  // only fires once
    }

    case FsmActionType::EaseFloat: {
        // p[0] = fromValue, p[1] = toValue, p[2] = varIdx, p[3] = time
        if (p[3] <= 0.f) return true;
        rt.easeTimer += ctx.dt;
        float t = rt.easeTimer / p[3];
        if (t >= 1.f) t = 1.f;
        float val = rt.easeFrom + (rt.easeTo - rt.easeFrom) * t;
        if (rt.easeVarIdx < FSM_MAX_FLOAT_VARS)
            rt.floatVars[rt.easeVarIdx] = val;
        return (t >= 1.f);
    }

    case FsmActionType::CheckAlertRange:
    case FsmActionType::CheckAlertRangeByName: {
        float rangeHalfW = 6.123f;
        float rangeOffsetX = -0.46f;
        float rangeCenterX = ctx.bk.posX + rangeOffsetX;
        bool inRange = (ctx.heroX >= rangeCenterX - rangeHalfW)
                    && (ctx.heroX <= rangeCenterX + rangeHalfW);

        if (inRange != rt.alertRangeInRange) {
            rt.alertRangeTimer = 0.f;
            rt.alertRangeInRange = inRange;
        }

        if (inRange) {
            float delay = p[2];
            if (delay <= 0.f) {
                fsmFireEventF(rt, p[1]);
            } else {
                rt.alertRangeTimer += ctx.dt;
                if (rt.alertRangeTimer >= delay)
                    fsmFireEventF(rt, p[1]);
            }
        } else {
            float delay = p[4];
            if (delay <= 0.f) {
                fsmFireEventF(rt, p[3]);
            } else {
                rt.alertRangeTimer += ctx.dt;
                if (rt.alertRangeTimer >= delay)
                    fsmFireEventF(rt, p[3]);
            }
        }
        return false;
    }

    case FsmActionType::CheckHeroPerformanceRegionV2: {
        // Detects hero singing (needolin).
        // p[0] = minReactDelay, p[1] = maxReactDelay
        // p[2] = activeInnerEvent, p[3] = activeOuterEvent
        // In the sim, we don't model singing, so this is mostly a noop.
        // If we wanted to model it, we'd check hero state here.
        return false;
    }

    case FsmActionType::CheckCollisionSide: {
        // p[0] = topHitEvent, p[1] = rightHitEvent
        // p[2] = bottomHitEvent, p[3] = leftHitEvent
        // Check if boss has collided with arena boundaries (level trigger).
        bool hitTop   = (ctx.bk.posY >= 27.0f);
        bool hitRight = (ctx.bk.posX >= 105.5f);
        bool onGround = (ctx.bk.posY <= 7.3f && ctx.bk.velY <= 0.f);
        bool hitLeft  = (ctx.bk.posX <= 82.5f);

        if (hitTop)    fsmFireEventF(rt, p[0]);
        if (hitRight)  fsmFireEventF(rt, p[1]);
        if (onGround)  fsmFireEventF(rt, p[2]);
        if (hitLeft)   fsmFireEventF(rt, p[3]);
        return false;
    }

    case FsmActionType::CheckCollisionSideEnter: {
        // Edge-triggered: fire events only on rising edges (0->1 transitions).
        bool hitTop   = (ctx.bk.posY >= 27.0f);
        bool hitRight = (ctx.bk.posX >= 105.5f);
        bool onGround = (ctx.bk.posY <= 7.3f && ctx.bk.velY <= 0.f);
        bool hitLeft  = (ctx.bk.posX <= 82.5f);

        uint8_t cur = (hitTop ? 1 : 0) | (hitRight ? 2 : 0)
                    | (onGround ? 4 : 0) | (hitLeft ? 8 : 0);
        uint8_t rising = cur & ~rt.collisionSidePrev;
        rt.collisionSidePrev = cur;

        if (rising & 1) fsmFireEventF(rt, p[0]);  // top
        if (rising & 2) fsmFireEventF(rt, p[1]);  // right
        if (rising & 4) fsmFireEventF(rt, p[2]);  // bottom
        if (rising & 8) fsmFireEventF(rt, p[3]);  // left
        return false;
    }

    case FsmActionType::CheckYPosition: {
        // Continuous version: re-check each frame. Same params as OnEnter.
        float compareVal = fsmReadVar(rt, p[0]) + p[1];
        float tol = p[2];
        float diff = ctx.bk.posY - compareVal;
        if (fabsf(diff) <= tol)      fsmFireEventF(rt, p[3]);
        else if (diff < -tol)        fsmFireEventF(rt, p[4]);
        else                         fsmFireEventF(rt, p[5]);
        return false;
    }

    case FsmActionType::CheckYPositionV2: {
        // Continuous: re-check each frame with bool output.
        float compareVal = fsmReadVar(rt, p[0]) + p[1];
        float tol = p[2];
        float diff = ctx.bk.posY - compareVal;
        bool eq = fabsf(diff) <= tol;
        bool lt = diff < -tol;
        bool gt = diff >  tol;

        if (eq)      fsmFireEventF(rt, p[3]);
        else if (lt) fsmFireEventF(rt, p[5]);
        else         fsmFireEventF(rt, p[7]);

        fsmWriteBoolVar(rt, p[4], eq);
        fsmWriteBoolVar(rt, p[6], lt);
        fsmWriteBoolVar(rt, p[8], gt);
        return false;
    }

    case FsmActionType::CheckIsCharacterGrounded: {
        // p[0] = groundDistance, p[1] = groundedEvent, p[2] = notGroundedEvent
        // Approximate ground check based on position and velocity.
        bool grounded = (ctx.bk.velY <= 0.f &&
                         ctx.bk.posY <= 7.3f + p[0]);
        if (grounded)
            fsmFireEventF(rt, p[1]);
        else
            fsmFireEventF(rt, p[2]);
        return false;
    }

    case FsmActionType::AnimatePositionTo: {
        // Lerp boss position toward target over time.
        // Uses waitTimer for total duration.
        if (rt.waitTimer <= 0.f) return true;
        rt.easeTimer += ctx.dt;
        float t = rt.easeTimer / rt.waitTimer;
        if (t >= 1.f) t = 1.f;
        // Lerp X toward hero (target set at enter or resolved at bake)
        ctx.bk.posX = rt.easeFrom + (ctx.heroX - rt.easeFrom) * t;
        if (t >= 1.f) {
            fsmFireEventF(rt, -1.f);  // finishEvent if baked
            return true;
        }
        return false;
    }

    case FsmActionType::FloatCompare: {
        // Continuous variant: re-check each frame.
        // p[0] = float1 (var ref or literal), p[1] = float2, p[2] = tolerance
        // p[3] = eqEvent, p[4] = ltEvent, p[5] = gtEvent
        float v1 = fsmReadVar(rt, p[0]);
        float v2 = fsmReadVar(rt, p[1]);
        float tol = p[2];
        float diff = v1 - v2;
        if (fabsf(diff) <= tol)
            fsmFireEventF(rt, p[3]);
        else if (diff < -tol)
            fsmFireEventF(rt, p[4]);
        else
            fsmFireEventF(rt, p[5]);
        return false;
    }

    case FsmActionType::FloatTestToBool: {
        // Continuous variant: re-test each frame.
        // p[0] = float1, p[1] = float2, p[2] = tolerance
        // p[3] = eqBoolRef, p[4] = ltBoolRef, p[5] = gtBoolRef
        float f1 = fsmReadVar(rt, p[0]);
        float f2 = fsmReadVar(rt, p[1]);
        float tol = p[2];
        float diff = f1 - f2;
        bool eq = fabsf(diff) <= tol;
        bool lt = diff < -tol;
        bool gt = diff >  tol;
        fsmWriteBoolVar(rt, p[3], eq);
        fsmWriteBoolVar(rt, p[4], lt);
        fsmWriteBoolVar(rt, p[5], gt);
        return false;
    }

    case FsmActionType::BoolAllTrue: {
        // p[0]=sendEvent, p[1]=storeResult, p[2]=numBools, p[3..]=boolVarRefs
        int n = (int)p[2];
        bool allTrue = (n > 0);
        for (int i = 0; i < n; ++i) {
            if (!fsmReadBoolVar(rt, p[3 + i])) {
                allTrue = false;
                break;
            }
        }
        if (!fsmIsNone(p[1])) fsmWriteBoolVar(rt, p[1], allTrue);
        if (allTrue) fsmFireEventF(rt, p[0]);
        return false;
    }

    case FsmActionType::BoolTestMulti: {
        // p[0]=trueEvent, p[1]=falseEvent, p[2]=storeResult, p[3]=numPairs
        // p[4..4+n-1]=boolVariables, p[4+n..4+2n-1]=boolStates
        int n = (int)p[3];
        bool allMatch = (n > 0);
        for (int i = 0; i < n; ++i) {
            bool varVal = fsmReadBoolVar(rt, p[4 + i]);
            bool stateVal = fsmReadBoolVar(rt, p[4 + n + i]);
            if (varVal != stateVal) {
                allMatch = false;
                break;
            }
        }
        if (!fsmIsNone(p[2])) fsmWriteBoolVar(rt, p[2], allMatch);
        if (allMatch)
            fsmFireEventF(rt, p[0]);
        else
            fsmFireEventF(rt, p[1]);
        return false;
    }

    case FsmActionType::FloatAdd: {
        // Continuous FloatAdd: add each frame (used in Stunned for timer).
        // p[0] = varRef, p[1] = addValue
        float cur = fsmReadVar(rt, p[0]);
        fsmWriteFloatVar(rt, p[0], cur + fsmReadVar(rt, p[1]) * ctx.dt);
        return false;
    }

    case FsmActionType::CompareHP: {
        int32_t compareVal = fsmReadIntVar(rt, p[0]);
        if (ctx.bossHP == compareVal)      fsmFireEventF(rt, p[1]);
        else if (ctx.bossHP < compareVal)  fsmFireEventF(rt, p[2]);
        else                                fsmFireEventF(rt, p[3]);
        return false;
    }

    case FsmActionType::CheckTargetDirection: {
        float sx = ctx.bk.posX + p[8];
        float sy = ctx.bk.posY + p[9];
        bool above = ctx.heroY > sy;
        bool below = ctx.heroY < sy;
        bool right = ctx.heroX > sx;
        bool left  = ctx.heroX < sx;

        if (above) fsmFireEventF(rt, p[0]);
        if (below) fsmFireEventF(rt, p[1]);
        if (right) fsmFireEventF(rt, p[2]);
        if (left)  fsmFireEventF(rt, p[3]);

        fsmWriteBoolVar(rt, p[4], above);
        fsmWriteBoolVar(rt, p[5], below);
        fsmWriteBoolVar(rt, p[6], right);
        fsmWriteBoolVar(rt, p[7], left);
        return false;
    }

    case FsmActionType::CheckXPosition: {
        float compareVal = fsmReadVar(rt, p[0]) + p[1];
        float tol = p[2];
        float diff = ctx.bk.posX - compareVal;
        bool eq = fabsf(diff) <= tol;
        bool lt = diff < -tol;
        bool gt = diff >  tol;

        if (eq)      fsmFireEventF(rt, p[3]);
        else if (lt) fsmFireEventF(rt, p[5]);
        else         fsmFireEventF(rt, p[7]);

        fsmWriteBoolVar(rt, p[4], eq);
        fsmWriteBoolVar(rt, p[6], lt);
        fsmWriteBoolVar(rt, p[8], gt);
        return false;
    }

    case FsmActionType::Translate: {
        // Continuous: translate by (x,y) * dt each frame (perSecond=true)
        float dx = fsmReadVar(rt, p[0]) * ctx.dt;
        float dy = fsmReadVar(rt, p[1]) * ctx.dt;
        ctx.bk.posX += dx;
        ctx.bk.posY += dy;
        return false;
    }

    case FsmActionType::GetDistance: {
        float dx = ctx.bk.posX - ctx.heroX;
        float dy = ctx.bk.posY - ctx.heroY;
        fsmWriteFloatVar(rt, p[0], sqrtf(dx*dx + dy*dy));
        return false;
    }

    case FsmActionType::GetXDistance: {
        fsmWriteFloatVar(rt, p[0], fabsf(ctx.heroX - ctx.bk.posX));
        return false;
    }

    case FsmActionType::Noop:
    default:
        return false;
    }
}

// -----------------------------------------------------------------------
// fsmActionsOnExit -- run registered exit callbacks before state transition
// -----------------------------------------------------------------------
static inline void fsmActionsOnExit(FsmRuntime &rt, FsmActionCtx &ctx)
{
    for (int i = 0; i < rt.numExitActions; ++i) {
        const FsmExitAction &ea = rt.exitActions[i];
        switch (ea.type) {
        case FsmActionType::SetCollider:
        case FsmActionType::SetPolygonCollider:
            ctx.rt.hitboxActive = !ctx.rt.hitboxActive;
            break;
        case FsmActionType::SetInvincible:
            ctx.sc.isInvincible = !ctx.sc.isInvincible;
            break;
        default:
            break;
        }
    }
    rt.numExitActions = 0;
}

} // namespace silksong
