#pragma once

#include <madrona/types.hpp>

namespace silksong {

namespace consts {

// ================================================================
// Sim infrastructure constants — arena geometry, timing, RL shape.
// Boss-specific and hero-specific gameplay constants have moved to
// fsm_lace_boss1.hpp (boss) and hero_config.hpp (hero).
// ================================================================

inline constexpr madrona::CountT numAgents = 1;

inline constexpr float deltaT = 0.02f;  // 50 Hz fixed timestep
inline constexpr madrona::CountT numPhysicsSubsteps = 1;
inline constexpr int32_t episodeLen = 2000;

inline constexpr madrona::CountT numRays = 32;
inline constexpr float maxRayDistance = 25.0f;
inline constexpr int32_t numHitTypes = 6;

inline constexpr int32_t numPlayerAnimStates = 83;
inline constexpr int32_t numBossAnimStates = 71;

// bone_east_12 arena (Lace Boss1 encounter, Bone East Docks).
// Main platform at Y≈5.8, walls at X≈82 and X≈106, lava below.
inline constexpr float arenaMinX = 78.0f;
inline constexpr float arenaMaxX = 111.0f;
inline constexpr float arenaMinY = -1.0f;
inline constexpr float arenaMaxY = 28.0f;
inline constexpr float ceilingY  = -1.0f;   // disabled

inline constexpr int32_t playerMaxHealth = 9;
inline constexpr int32_t playerMaxSilk = 12;
inline constexpr int32_t bossMaxHealth = 250;

inline constexpr madrona::CountT numActions = 10;

// Spawn positions: hero and boss start within battle range (~6 units apart)
// so the boss FSM enters attack mode immediately (not Range Out).
// Game starts after cutscene where they're already close.
inline constexpr float heroSpawnX = 91.0f;
inline constexpr float heroSpawnY =  7.60f;
inline constexpr float bossSpawnX = 97.0f;
inline constexpr float bossSpawnY =  7.28f;

// Hero collider dimensions (from Hero_Hornet.prefab)
inline constexpr float heroHalfWidth  = 0.4f;
inline constexpr float heroHalfHeight = 0.568f;

// Hero hurt box (from Hero_Hornet.prefab Normal sub-collider)
inline constexpr float heroHurtNormalHalfW = 0.23f;
inline constexpr float heroHurtNormalHalfH = 1.125f;
inline constexpr float heroHurtNormalOffY  = -0.38f;

// Boss body collider (from Lace Boss1 collider)
inline constexpr float bossBodyHalfW  = 0.415f;   // 0.83/2
inline constexpr float bossBodyHalfH  = 1.28f;    // 2.56/2

// Boss movement constraints (arena boundary for boss)
inline constexpr float bossConstraintXMin = 82.4f;
inline constexpr float bossConstraintXMax = 105.6f;

// Boss gravity + landing
inline constexpr float bossGravity   = -120.0f;   // gravity(-60) * gravityScale(2.0)
inline constexpr float bossLandY     =   6.00f;   // sim tile floor surface

// Boss HP
inline constexpr int16_t bossMaxHP   = 250;
inline constexpr int16_t bossRageHPFrac = 2;      // rage at HP <= maxHP / 2

// Boss invincibility after hit
inline constexpr int16_t bossInvincFrames = 13;    // 0.25s invulnerableTime

// Stun parameters
inline constexpr int16_t bossStunCombo    = 8;     // combo hits to trigger stun
inline constexpr int16_t bossStunHitMax   = 10;    // absolute hits for forced stun

// Hero attack parameters (from sim perspective)
inline constexpr float   attackRange      = 2.5f;
inline constexpr int32_t attackDamage     = 21;

// Hero attack recoil (knockback when hero HITS boss)
inline constexpr float   heroAttackRecoilVel    = 3.75f;   // RECOIL_HOR_VELOCITY
inline constexpr int16_t heroAttackRecoilFrames = 8;       // RECOIL_HOR_STEPS

// Hero damage recoil parameters
inline constexpr float   heroRecoilSpeed   = 15.0f;   // RECOIL_VELOCITY
inline constexpr int16_t heroRecoilFrames  = 10;      // RECOIL_DURATION=0.2s
inline constexpr int16_t heroInvulFrames   = 50;      // INVUL_TIME=1.0s

// Damage freeze
inline constexpr int16_t damageFreezeFrames = 10;     // DAMAGE_FREEZE_WAIT(0.1)+DAMAGE_FREEZE_UP(0.1)

// Heal parameters
inline constexpr int16_t healCost           = 9;
inline constexpr int16_t healHpGain         = 1;
inline constexpr int16_t healDurationFrames = 15;

// Boss recoil parameters
inline constexpr float bossRecoilSpeed    = 15.0f;
inline constexpr float bossRecoilDuration = 0.15f;

// Lava parameters
inline constexpr float bossLavaY          = -0.5f;

}

}
