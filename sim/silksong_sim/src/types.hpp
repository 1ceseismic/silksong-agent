#pragma once

#include <madrona/components.hpp>
#include <madrona/math.hpp>
#include <madrona/rand.hpp>

#include "consts.hpp"
#include "fsm_types.hpp"
#include "hero.hpp"

namespace silksong {

using madrona::Entity;
using madrona::RandKey;
using madrona::CountT;

struct WorldReset {
    int32_t reset;
};

struct HeroInit {
    int32_t useCustom;
    float   posX;
    float   posY;
    float   velX;
    float   velY;
    int32_t prevActionBits;
    int32_t facingRight;
    float   ceilingY;
    float   ceilingMinX;
    float   ceilingMaxX;
};
static_assert(sizeof(HeroInit) == 40);

struct Arena {
    static constexpr int W = 64;
    static constexpr int H = 32;
    static constexpr float tileSize = 1.0f;

    uint32_t solid[H][W / 32];
    float originX;
    float originY;
    float ceilingY;       // sub-tile ceiling clamp; <=0 disabled
    float ceilingMinX;
    float ceilingMaxX;
};

struct Action {
    int32_t left;
    int32_t right;
    int32_t up;
    int32_t down;
    int32_t jump;
    int32_t attack;
    int32_t dash;
    int32_t clawline;
    int32_t skill;
    int32_t heal;
};
static_assert(sizeof(Action) == sizeof(int32_t) * consts::numActions);

enum ActionBit : uint16_t {
    AB_Left = 0, AB_Right, AB_Up, AB_Down,
    AB_Jump, AB_Attack, AB_Dash,
    AB_Clawline, AB_Skill, AB_Heal,
};

// GlobalFreeze singleton: when timer > 0, both hero and boss skip ticking.
struct GlobalFreeze {
    float timer;
};

struct ActiveProjectiles {
    static constexpr int MAX = 32;
    float    posX[MAX], posY[MAX];
    float    velX[MAX], velY[MAX];
    float    halfW[MAX], halfH[MAX];
    int16_t  ttl[MAX];
    uint8_t  damage[MAX];
    uint32_t activeMask;
};

// FsmDefSingleton: holds the immutable FsmDef for boss FSM.
struct FsmDefSingleton {
    FsmDef def;
};

// HeroConfigSingleton: holds the hero config (populated from Sim::Config at init).
struct HeroConfigSingleton {
    HeroConfig config;
};

struct Reward {
    float v;
};

struct Done {
    int32_t v;
};

// ================================================================
// Observation tensors — RL-facing interface. KEEP UNCHANGED.
// ================================================================

struct PlayerObs {
    float posX;
    float posY;
    float velX;
    float velY;
    float health;
    float maxHealth;
    float silk;
    float grounded;
    float canDash;
    float facingRight;
    float invincible;
    float canAttack;
    float animState;
    float animProgress;
};
static_assert(sizeof(PlayerObs) == sizeof(float) * 14);

struct BossObs {
    float posX;
    float posY;
    float velX;
    float velY;
    float health;
    float maxHealth;
    float phase;
    float facingRight;
    float animState;
    float animProgress;
};
static_assert(sizeof(BossObs) == sizeof(float) * 10);

struct RaycastDistances {
    float v[consts::numRays];
};
static_assert(sizeof(RaycastDistances) == sizeof(float) * consts::numRays);

struct RaycastHitTypes {
    int32_t v[consts::numRays];
};
static_assert(sizeof(RaycastHitTypes) == sizeof(int32_t) * consts::numRays);

struct EpisodeState {
    float episodeTime;
    int32_t stepsTaken;
    int32_t stepsRemaining;
};

// ================================================================
// Agent archetype — uses new FSM + hero components
// ================================================================

struct Agent : public madrona::Archetype<
    Action,
    HeroState,
    PlayerObs,
    BossKinematics,
    FsmRuntime,
    StunControl,
    BossObs,
    RaycastDistances,
    RaycastHitTypes,
    EpisodeState,
    Reward,
    Done
> {};

}
