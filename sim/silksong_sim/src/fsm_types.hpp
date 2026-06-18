#pragma once
#include <cstdint>

namespace silksong {

// ---------------------------------------------------------------------------
// Action type IDs -- one per gameplay-relevant PlayMaker action
// ---------------------------------------------------------------------------
enum class FsmActionType : uint8_t {
    Noop = 0,
    SetVelocityByScale, SetVelocity2d, DecelerateXY,
    Wait, WaitRandom, NextFrameEvent,
    SetIsKinematic2d, SetGravity2dScale,
    SetPosition2d, Translate, ClampPosition, AnimatePositionTo,
    FaceObjectV2, FaceObjectV4, FlipScale,
    SetBoolValue, SetFloatValue, SetIntValue,
    BoolTest, BoolTestMulti, BoolAllTrue,
    FloatCompare, FloatTestToBool, IntCompare, IntAdd,
    FloatAdd, FloatMultiply, FloatClamp, FloatInRange,
    RandomFloat, RandomInt, MultiplyIntByFloat,
    EaseFloat,
    GetDistance, GetXDistance, GetSelfPosition, GetPosition2d, GetScale,
    SetDamageHeroAmount, SetRecoilSpeed, SetRecoilBlocked,
    SetSpecialDeath, SetInvincible,
    SubtractHP, CompareHP, GetHP,
    CheckAlertRange, CheckAlertRangeByName,
    CheckHeroPerformanceRegionV2,
    SendEvent, SendEventByName, SendEventByNameV2, SendEventByScale,
    SendRandomEvent, SendRandomEventV3,
    FreezeMoment,
    DamageHeroDirectly, CanHeroTakeDamage,
    RayCast2dV2,
    CheckCollisionSide, CheckCollisionSideEnter,
    CheckXPosition, CheckYPosition, CheckYPositionV2,
    CheckIsCharacterGrounded, CheckTargetDirection,
    SetCollider, SetPolygonCollider,
    SetStringValue, GetFsmFloat,
    PreventInvincibleEffect,
    ReceivedDamage,
    SetHitEffectOrigin,
    SetScale,
    SetHitboxGeometry,
    Count
};

// ---------------------------------------------------------------------------
// Event handling
// ---------------------------------------------------------------------------
// Event IDs are baked per-FSM by the bake script.  Each boss FSM defines its
// own event enum in its generated header; these are indices into the FSM's
// event table.  FSM_EVENT_NONE means "no event pending".
constexpr uint8_t FSM_EVENT_NONE = 255;

// ---------------------------------------------------------------------------
// Compile-time FSM table entries (shared across all worlds, immutable)
// ---------------------------------------------------------------------------

struct FsmStateDef {
    uint16_t actionStart;       // index into actions array
    uint8_t  actionCount;
    uint8_t  transitionStart;   // index into transitions array
    uint8_t  transitionCount;
    uint8_t  nameIdx;           // debug: index into name table
    uint8_t  _pad[2];
};

struct FsmActionDef {
    FsmActionType type;
    uint8_t  flags;             // bit 0: is continuous (has OnUpdate)
    uint16_t paramOffset;       // index into float params array
};

struct FsmTransitionDef {
    uint8_t eventId;
    uint8_t targetState;
};

// Variable slot descriptor -- typed reference into the runtime variable arrays
struct FsmVarSlot {
    uint8_t  type;              // 0=float, 1=int, 2=bool, 3=string, 4=vector3
    uint8_t  index;             // slot index within the typed array
};

struct FsmExitAction {
    FsmActionType type;
    uint16_t paramOffset;
};
constexpr int FSM_MAX_EXIT_ACTIONS = 8;

// ---------------------------------------------------------------------------
// Compile-time FSM definition (one per boss, loaded once)
// ---------------------------------------------------------------------------

// Capacity constants for FSM variable arrays (shared by FsmDef and FsmRuntime)
constexpr int FSM_MAX_ACTIONS_PER_STATE = 36;
constexpr int FSM_MAX_FLOAT_VARS        = 24;
constexpr int FSM_MAX_INT_VARS          = 16;
constexpr int FSM_MAX_BOOL_VARS         = 24;

// Max sizes for inline FSM data (must fit the largest boss FSM).
// Lace Boss1: 88 states, 520 actions, 127 transitions, 1081 params.
constexpr int FSM_MAX_STATES = 96;
constexpr int FSM_MAX_TOTAL_ACTIONS = 576;
constexpr int FSM_MAX_TRANSITIONS = 160;
constexpr int FSM_MAX_PARAMS = 1152;
constexpr int FSM_MAX_GLOBAL_TRANSITIONS = 8;

// FSM definition — inline arrays so the struct can be copied to GPU.
struct FsmDef {
    FsmStateDef      states[FSM_MAX_STATES];
    FsmActionDef     actions[FSM_MAX_TOTAL_ACTIONS];
    FsmTransitionDef transitions[FSM_MAX_TRANSITIONS];
    float            params[FSM_MAX_PARAMS];
    FsmTransitionDef globalTransitions[FSM_MAX_GLOBAL_TRANSITIONS];
    int numStates;
    int numActions;
    int numTransitions;
    int numParams;
    int numFloatVars;
    int numIntVars;
    int numBoolVars;
    int numGlobalTransitions;
    uint8_t startState;
    // Initial variable values (copied into FsmRuntime on episode reset)
    float    initFloatVars[FSM_MAX_FLOAT_VARS];
    int32_t  initIntVars[FSM_MAX_INT_VARS];
    uint8_t  initBoolVars[FSM_MAX_BOOL_VARS];
};

// ---------------------------------------------------------------------------
// Per-world runtime FSM state
// ---------------------------------------------------------------------------

// (FSM_MAX_*_VARS and FSM_MAX_ACTIONS_PER_STATE defined above FsmDef)

struct FsmRuntime {
    uint8_t  currentState;
    uint8_t  pendingEvent;
    uint8_t  actionFinished[FSM_MAX_ACTIONS_PER_STATE];

    float    floatVars[FSM_MAX_FLOAT_VARS];
    int32_t  intVars[FSM_MAX_INT_VARS];
    uint8_t  boolVars[FSM_MAX_BOOL_VARS];

    float    waitTimer;
    float    easeTimer;
    float    easeFrom;
    float    easeTo;
    uint8_t  easeVarIdx;

    // SendRandomEventV3 tracking (max 3 choices per invocation in current FSM)
    uint8_t  lastAttack;
    uint8_t  consecutiveCount;
    uint8_t  missedCounts[8];

    // Persisted per-frame state (set by OnEnter actions, must survive across frames)
    float    facingScale;       // +1 = right, -1 = left (set by FaceObjectV2)
    float    gravityScale;      // gravity multiplier (set by SetGravity2dScale)
    bool     isKinematic;       // true = skip physics integration (set by SetIsKinematic2d)
    bool     hitboxActive;      // damager active (set by SetCollider/SetPolygonCollider)
    float    hitboxHalfW;
    float    hitboxHalfH;
    float    hitboxOffsetX;
    float    hitboxOffsetY;
    int16_t  hitboxDamage;      // current hitbox damage (set by SetDamageHeroAmount)

    // DamageHeroDirectly output (consumed by combatSystem, reset each frame)
    float    heroDamageOut;
    bool     heroDamageBypass;

    // CheckAlertRange state
    float    alertRangeTimer;
    bool     alertRangeInRange;  // previous frame's in-range state

    // CheckCollisionSideEnter edge-detection state
    uint8_t  collisionSidePrev;  // bitmask: bit0=top, bit1=right, bit2=bottom, bit3=left

    // State-exit callbacks (resetOnExit actions)
    FsmExitAction exitActions[FSM_MAX_EXIT_ACTIONS];
    uint8_t numExitActions;

    // Performance region state (CheckHeroPerformanceRegionV2)
    float    singReactTimer;
};

// ---------------------------------------------------------------------------
// Boss kinematics (position + velocity, updated by FSM actions + integrator)
// ---------------------------------------------------------------------------

struct BossKinematics {
    float posX, posY;
    float velX, velY;
};

// ---------------------------------------------------------------------------
// Stun Control companion (port of the 17-state Stun Control FSM)
// ---------------------------------------------------------------------------

struct StunControl {
    float comboCounter;
    float comboTime;       // 1.0s window
    float hitsTotal;
    int   stunCombo;       // 8  (combo hits to trigger stun)
    int   stunHitMax;      // 10 (total hits to trigger stun)
    int   recoilSpeed;     // from FSM SetRecoilSpeed action
    bool  recoilBlocked;
    bool  isInvincible;
    bool  specialDeath;
    int16_t invincTimer;
    int16_t hitFreezeRem;
    int16_t recoilRem;
    int16_t damageAmount;  // current hitbox damage
};

} // namespace silksong
