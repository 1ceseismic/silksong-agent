#pragma once
// =============================================================================
// hero.hpp — Faithful port of HeroController.cs (decompiled, ~12k lines)
//
// Each function is tagged with the C# source line range it was ported from.
// Translation rules (from plan Task 4):
//   Time.deltaTime             → dt parameter
//   rb2d.linearVelocity.x/.y   → hero.velX / hero.velY
//   rb2d.linearVelocity = V2   → hero.velX = v.x; hero.velY = v.y;
//   cState.X                   → hero.states.X
//   Config.X                   → cfg.X
//   Mathf.Abs/Max/Min          → fabsf/fmaxf/fminf
//   Animation/Audio/VFX/Camera → // [SKIP: cosmetic]
//   Coroutines                 → state flags + timers
// =============================================================================

#include <cmath>
#include <cstdint>
#include "hero_states.hpp"
#include "hero_config.hpp"

namespace silksong {

// Forward-declare Arena so hero tick can accept it for ground/wall queries.
// The actual sweep integration lives in sim.cpp.

// ─────────────────────────────────────────────────────────────────────────────
// Attack direction enum (from HeroController)
// ─────────────────────────────────────────────────────────────────────────────
enum class AttackDirection : uint8_t {
    normal  = 0,
    upward  = 1,
    downward = 2,
};

// ─────────────────────────────────────────────────────────────────────────────
// ActorStates enum (from GlobalEnums)
// ─────────────────────────────────────────────────────────────────────────────
enum class ActorStates : int8_t {
    idle         = 0,
    running      = 1,
    airborne     = 2,
    no_input     = 3,
    hard_landing = 4,
    dash_landing = 5,
    grounded     = 6,  // pseudo-state resolved to idle/running in SetState
    previous     = 7,
};

// ─────────────────────────────────────────────────────────────────────────────
// HeroState — per-world hero data, replaces PlayerKinematics
// ─────────────────────────────────────────────────────────────────────────────
struct HeroState {
    // Position + velocity (replaces rb2d)
    float posX, posY;
    float velX, velY;

    // The cState flags (HeroControllerStates.cs)
    HeroStates states;

    // Hero state machine
    ActorStates hero_state;
    ActorStates prev_hero_state;

    // --- Timers & counters from HeroController private fields ---
    // Jump
    int   jump_steps;
    int   jumped_steps;
    int   doubleJump_steps;
    bool  doubleJumped;

    // Dash
    float dash_timer;
    float dash_time;
    float dashCooldownTimer;
    bool  airDashed;
    bool  dashingDown;
    bool  dashCurrentFacing;

    // Attack
    float attack_cooldown;
    float attackDuration;
    float attack_time;
    AttackDirection prevAttackDir;
    float altAttackTime;     // timeSinceLevelLoad snapshot for alt-attack reset
    bool  wallSlashing;

    // Wall
    bool  touchingWallL;
    bool  touchingWallR;
    bool  wallSlidingL;
    bool  wallSlidingR;
    float currentWalljumpSpeed;
    float walljumpSpeedDecel;
    int   wallUnstickSteps;
    bool  wallJumpedR;
    bool  wallJumpedL;
    bool  wallLocked;
    int   wallLockSteps;
    int   wallJumpChainStepsLeft;

    // Recoil (horizontal, from hero attacks hitting boss)
    float recoilVelocity;
    int   recoilStepsLeft;

    // Damage recoil (from taking damage)
    float recoilTimer;       // counts down RECOIL_DURATION
    float recoilVecX;        // recoilVector.x from StartRecoil
    float recoilVecY;        // recoilVector.y from StartRecoil

    // Invulnerability
    float invulTimer;        // total invuln time remaining
    float invulFreezeTimer;  // DAMAGE_FREEZE_DOWN phase of invuln

    // Damage freeze (FreezeMoment)
    float damageFreezeTimer; // DAMAGE_FREEZE_WAIT + DAMAGE_FREEZE_UP

    // Gravity
    float gravityScale;      // Unity rb2d.gravityScale equivalent
    bool  gravityApplies;    // false = zero gravity

    // Move input (from LookForInput → move_input)
    float move_input;

    // Buffering
    int   ledgeBufferSteps;
    int   sprintBufferSteps;
    bool  syncBufferSteps;
    int   headBumpSteps;

    // Input queuing
    int   jumpQueueSteps;
    bool  jumpQueuing;
    int   doubleJumpQueueSteps;
    bool  doubleJumpQueuing;
    int   dashQueueSteps;
    bool  dashQueuing;
    int   attackQueueSteps;
    bool  attackQueuing;

    // Misc control
    bool  acceptingInput;
    bool  controlReqlinquished;

    // Quickening
    bool  isUsingQuickening;

    // Episode time (for alt-attack timing)
    float timeSinceLevelLoad;

    // HP / Silk
    int   health;
    int   maxHealth;
    int   silk;

    // Input from action tensor
    uint16_t prevActionBits;
};

// ─────────────────────────────────────────────────────────────────────────────
// Helper: AffectedByGravity  (used everywhere in HeroController)
// ─────────────────────────────────────────────────────────────────────────────
static inline void AffectedByGravity(HeroState &hero, bool gravityOn) {
    hero.gravityApplies = gravityOn;
    if (!gravityOn) {
        hero.gravityScale = 0.0f;
    } else {
        hero.gravityScale = 1.0f; // DEFAULT_GRAVITY
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper: SetState (port of HeroController.SetState, lines 9163-9193)
// ─────────────────────────────────────────────────────────────────────────────
static inline void SetState(HeroState &hero, ActorStates newState) {
    // Port of HeroController.cs:9163-9193
    // Simplified: no CanExitNoInput gate in sim (we don't model hazard respawn)
    switch (newState) {
    case ActorStates::grounded:
        newState = (fabsf(hero.move_input) > 1e-5f)
                       ? ActorStates::running
                       : ActorStates::idle;
        // [SKIP: cosmetic] heroBox.HeroBoxNormal()
        break;
    case ActorStates::idle:
    case ActorStates::running:
    case ActorStates::airborne:
        // [SKIP: cosmetic] heroBox state
        break;
    case ActorStates::previous:
        newState = hero.prev_hero_state;
        break;
    default:
        break;
    }
    if (newState != hero.hero_state) {
        hero.prev_hero_state = hero.hero_state;
        hero.hero_state = newState;
        // [SKIP: cosmetic] animCtrl.UpdateState(newState)
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper: GetRunSpeed / GetWalkSpeed (lines 11808-11824)
// ─────────────────────────────────────────────────────────────────────────────
static inline float GetRunSpeed(const HeroState &hero, const HeroConfig &cfg) {
    // Port of HeroController.cs:11808-11814
    if (hero.isUsingQuickening) return cfg.QUICKENING_RUN_SPEED;
    return cfg.RUN_SPEED;
}

static inline float GetWalkSpeed(const HeroState &hero, const HeroConfig &cfg) {
    // Port of HeroController.cs:11817-11824
    if (hero.isUsingQuickening) return cfg.QUICKENING_WALK_SPEED;
    return cfg.WALK_SPEED;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper: GetMaxFallVelocity (lines 4840-4848)
// ─────────────────────────────────────────────────────────────────────────────
static inline float GetMaxFallVelocity(const HeroConfig &cfg) {
    // Port of HeroController.cs:4840-4848
    // Simplified: WeightedAnklet tool not modelled in sim
    return cfg.MAX_FALL_VELOCITY;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper: FlipSprite (lines 4991-5005)
// ─────────────────────────────────────────────────────────────────────────────
static inline void FlipSprite(HeroState &hero) {
    // Port of HeroController.cs:4991-5005
    hero.states.facingRight = !hero.states.facingRight;
    // [SKIP: cosmetic] localScale, CancelOnTurn velocities, ChangedFacing
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper: FaceRight / FaceLeft (lines 4386-4407)
// ─────────────────────────────────────────────────────────────────────────────
static inline void FaceRight(HeroState &hero) {
    hero.states.facingRight = true;
}
static inline void FaceLeft(HeroState &hero) {
    hero.states.facingRight = false;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper: CancelJump (lines 9836-9843)
// ─────────────────────────────────────────────────────────────────────────────
static inline void CancelJump(HeroState &hero) {
    // Port of HeroController.cs:9836-9843
    hero.states.jumping = false;
    hero.jump_steps = 0;
    hero.wallLocked = false;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper: CancelDoubleJump (lines 9845-9849)
// ─────────────────────────────────────────────────────────────────────────────
static inline void CancelDoubleJump(HeroState &hero) {
    // Port of HeroController.cs:9845-9849
    hero.states.doubleJumping = false;
    hero.doubleJump_steps = 0;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper: CancelDash (lines 9851-9869)
// ─────────────────────────────────────────────────────────────────────────────
static inline void CancelDash(HeroState &hero) {
    // Port of HeroController.cs:9851-9869
    hero.states.shadowDashing = false;
    hero.states.dashing = false;
    hero.dashQueuing = false;
    // [SKIP: cosmetic] heroBox.HeroBoxNormal()
    hero.dashingDown = false;
    hero.states.airDashing = false;
    hero.dash_timer = 0.0f;
    AffectedByGravity(hero, true);
    // [SKIP: cosmetic] StopDashEffect
    // [SKIP: cosmetic] sprintFSM.SendEvent("CANCEL SPRINT")
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper: CancelWallsliding (lines 9875-9893)
// ─────────────────────────────────────────────────────────────────────────────
static inline void CancelWallsliding(HeroState &hero) {
    // Port of HeroController.cs:9875-9893
    // [SKIP: cosmetic] particle emission, vibration, heroBox
    if (hero.states.wallSliding) {
        hero.states.wallSliding = false;
        hero.states.wallClinging = false;
    }
    AffectedByGravity(hero, true);
    hero.states.touchingWall = false;
    hero.wallSlidingL = false;
    hero.wallSlidingR = false;
    hero.touchingWallL = false;
    hero.touchingWallR = false;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper: CancelHeroJump (lines 4793-4803)
// ─────────────────────────────────────────────────────────────────────────────
static inline void CancelHeroJump(HeroState &hero) {
    // Port of HeroController.cs:4793-4803
    if (hero.states.jumping || hero.states.doubleJumping) {
        CancelJump(hero);
        CancelDoubleJump(hero);
        if (hero.velY > 0.0f) {
            hero.velY = 0.0f;
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper: CancelRecoilHorizontal
// ─────────────────────────────────────────────────────────────────────────────
static inline void CancelRecoilHorizontal(HeroState &hero) {
    hero.states.recoilingLeft = false;
    hero.states.recoilingRight = false;
    hero.recoilStepsLeft = 0;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper: CancelBounce
// ─────────────────────────────────────────────────────────────────────────────
static inline void CancelBounce(HeroState &hero) {
    hero.states.bouncing = false;
    hero.states.shroomBouncing = false;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper: ResetAttacks (lines 10051-10063)
// ─────────────────────────────────────────────────────────────────────────────
static inline void ResetAttacks(HeroState &hero) {
    // Port of HeroController.cs:10035-10063
    hero.states.attacking = false;
    hero.states.upAttacking = false;
    hero.states.downAttacking = false;
    hero.attack_time = 0.0f;
    hero.wallSlashing = false;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper: ResetMotion (lines 10085-10111)
// ─────────────────────────────────────────────────────────────────────────────
static inline void ResetMotion(HeroState &hero) {
    // Port of HeroController.cs:10085-10111
    CancelJump(hero);
    CancelDoubleJump(hero);
    CancelDash(hero);
    hero.states.backDashing = false;
    CancelBounce(hero);
    CancelRecoilHorizontal(hero);
    CancelWallsliding(hero);
    hero.states.floating = false;
    hero.states.downSpiking = false;
    hero.states.shuttleCock = false;
    hero.velX = 0.0f;
    hero.velY = 0.0f;
    hero.wallLocked = false;
    AffectedByGravity(hero, true);
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper: ResetLook (lines 10128-10135)
// ─────────────────────────────────────────────────────────────────────────────
static inline void ResetLook(HeroState &hero) {
    hero.states.lookingUp = false;
    hero.states.lookingDown = false;
    hero.states.lookingUpAnim = false;
    hero.states.lookingDownAnim = false;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper: BackOnGround (lines 10199-10260 — simplified for sim)
// ─────────────────────────────────────────────────────────────────────────────
static inline void BackOnGround(HeroState &hero, const HeroConfig &cfg) {
    // Port of HeroController.cs:10199-10260 (simplified)
    hero.states.willHardLand = false;
    hero.sprintBufferSteps = 0;
    hero.syncBufferSteps = false;
    if (hero.states.onGround) return;
    hero.states.onGround = true;
    hero.airDashed = false;
    hero.doubleJumped = false;
    CancelDoubleJump(hero);
    CancelJump(hero);
    // [SKIP: cosmetic] landing effects, animation
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper: BecomeAirborne (lines 8756-8776)
// ─────────────────────────────────────────────────────────────────────────────
static inline void BecomeAirborne(HeroState &hero) {
    // Port of HeroController.cs:8756-8776
    bool wasOnGround = hero.states.onGround;
    // [SKIP: cosmetic] animCtrl.ResetPlays, SetCanSoftLand
    hero.states.onGround = false;
    SetState(hero, ActorStates::airborne);
    if (wasOnGround) {
        if (hero.velY < 0.0f) {
            hero.velY = 0.0f;
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper: OnHeroJumped (lines 8746-8754)
// ─────────────────────────────────────────────────────────────────────────────
static inline void OnHeroJumped(HeroState &hero) {
    // Port of HeroController.cs:8746-8754
    if (hero.states.onGround || hero.states.wallClinging || hero.states.wallSliding) {
        hero.airDashed = false;
        hero.doubleJumped = false;
    }
}

// =============================================================================
// 1. Move() — horizontal movement
// Port of HeroController.cs:3907-3981
// =============================================================================
static inline void Move(HeroState &hero, const HeroConfig &cfg,
                         float moveDirection, bool useInput)
{
    // Port of HeroController.cs:3907-3981
    if (hero.states.onGround) {
        SetState(hero, ActorStates::grounded);
    }

    // Downspike recovery blocks movement on ground
    if (hero.states.downSpikeRecovery && hero.states.onGround) {
        moveDirection = 0.0f;
    }

    // Steep slope blocking
    if (hero.states.isTouchingSlopeLeft && moveDirection < 0.0f) {
        moveDirection = 0.0f;
    } else if (hero.states.isTouchingSlopeRight && moveDirection > 0.0f) {
        moveDirection = 0.0f;
    }

    float vx = hero.velX;

    if (useInput && !hero.states.wallSliding) {
        if (hero.states.inWalkZone && hero.states.onGround) {
            vx = moveDirection * GetWalkSpeed(hero, cfg);
        } else {
            vx = moveDirection * GetRunSpeed(hero, cfg);
        }
    }

    // [SKIP: extraAirMoveVelocities — DecayingVelocity list not modelled in sim]

    hero.velX = vx;
}

// =============================================================================
// 2. HeroJump() — ground jump initiation
// Port of HeroController.cs:8691-8744
// =============================================================================
static inline void HeroJump(HeroState &hero, const HeroConfig &cfg,
                              bool checkSprint = true)
{
    // Port of HeroController.cs:8711-8744
    // [SKIP: cosmetic] animCtrl.UpdateWallScramble
    hero.states.downSpikeRecovery = false;

    // checkSprint shuttlecock logic (simplified — not modelled fully)
    // [SKIP: shuttlecock sprint-jump path]

    // [SKIP: cosmetic] jumpEffectPrefab, audio, grunt
    ResetLook(hero);
    CancelDoubleJump(hero);
    // [SKIP: cosmetic] animCtrl.ResetPlaying
    hero.states.recoiling = false;

    hero.states.jumping = true;
    hero.jumpQueueSteps = 0;
    hero.jumped_steps = 0;
    hero.dashCooldownTimer = 0.05f;
    hero.sprintBufferSteps = 0;
    hero.syncBufferSteps = false;
    hero.doubleJumpQueuing = false;

    // Cancel attack if recovery done
    if (hero.states.attacking && hero.attack_time >= cfg.attackRecoveryTime) {
        ResetAttacks(hero);
    }

    OnHeroJumped(hero);
    BecomeAirborne(hero);
    // [SKIP: cosmetic] ResetHardLandingTimer
}

// =============================================================================
// 3. Jump() — jump velocity application (per-tick while jumping)
// Port of HeroController.cs:3983-4005
// =============================================================================
static inline void Jump(HeroState &hero, const HeroConfig &cfg) {
    // Port of HeroController.cs:3983-4005
    if (hero.jump_steps <= cfg.JUMP_STEPS) {
        // isDashStabBouncing not modelled
        hero.velY = cfg.JUMP_SPEED;
        hero.jump_steps++;
        hero.jumped_steps++;
        hero.ledgeBufferSteps = 0;
        hero.sprintBufferSteps = 0;
        hero.syncBufferSteps = false;
    } else {
        CancelJump(hero);
    }
}

// =============================================================================
// 4. DoubleJump() — air jump (per-tick while double-jumping)
// Port of HeroController.cs:4007-4031
// =============================================================================
static inline void DoubleJump(HeroState &hero, const HeroConfig &cfg) {
    // Port of HeroController.cs:4007-4031
    // [SKIP: updraft/float path — not modelled]
    if (hero.doubleJump_steps <=
        cfg.DOUBLE_JUMP_RISE_STEPS + cfg.DOUBLE_JUMP_FALL_STEPS) {
        if (hero.doubleJump_steps > cfg.DOUBLE_JUMP_FALL_STEPS) {
            hero.velY = cfg.JUMP_SPEED * 1.1f;
        }
        hero.doubleJump_steps++;
    } else {
        CancelDoubleJump(hero);
    }
    if (hero.states.onGround) {
        CancelDoubleJump(hero);
    }
}

// =============================================================================
// 5. DoDoubleJump() — air jump initiation
// Port of HeroController.cs:8872-8927
// =============================================================================
static inline void DoDoubleJump(HeroState &hero, const HeroConfig &cfg) {
    // Port of HeroController.cs:8872-8927
    // [SKIP: SlideSurface, updraft, shuttlecock checks]
    if (hero.states.dashing && hero.dashingDown) {
        // FinishedDashing(wasDashingDown=true) — simplified
        CancelDash(hero);
    }
    if (hero.states.jumping) {
        Jump(hero, cfg);
    }

    // [SKIP: cosmetic] doubleJumpEffectPrefab, BrollySpike, vibration, audio

    // Clamp downward velocity
    if (hero.velY < -cfg.MAX_FALL_VELOCITY_DJUMP) {
        hero.velY = -cfg.MAX_FALL_VELOCITY_DJUMP;
    }

    // [SKIP: ShuttleCockCancel]
    ResetLook(hero);

    hero.states.downSpikeBouncing = false;
    hero.states.downSpikeBouncingShort = false;
    hero.states.jumping = false;
    hero.states.doubleJumping = true;
    hero.states.downSpikeRecovery = false;
    // [SKIP: cosmetic] animCtrl.AllowDoubleJumpReEntry

    if (hero.jumped_steps < cfg.JUMP_STEPS_MIN) {
        hero.jumped_steps = cfg.JUMP_STEPS_MIN;
    }
    hero.doubleJump_steps = 0;
    hero.doubleJumped = true;
    // [SKIP: cosmetic] ResetHardLandingTimer
}

// =============================================================================
// 6. DoWallJump() — wall kick initiation
// Port of HeroController.cs:8800-8870
// =============================================================================
static inline void DoWallJump(HeroState &hero, const HeroConfig &cfg) {
    // Port of HeroController.cs:8800-8870
    // [SKIP: cosmetic] wallPuffPrefab, audio, vibration

    if (hero.touchingWallL) {
        FaceRight(hero);
        hero.wallJumpedR = true;
        hero.wallJumpedL = false;
    } else if (hero.touchingWallR) {
        FaceLeft(hero);
        hero.wallJumpedR = false;
        hero.wallJumpedL = true;
    }

    // [SKIP: cosmetic] touchingWallObj FSM event
    CancelWallsliding(hero);
    hero.states.touchingWall = false;
    hero.touchingWallL = false;
    hero.touchingWallR = false;
    hero.airDashed = false;
    hero.doubleJumped = false;
    // [SKIP: ShuttleCockCancel]
    hero.states.mantleRecovery = false;

    hero.currentWalljumpSpeed = cfg.WJ_KICKOFF_SPEED;
    hero.walljumpSpeedDecel = (cfg.WJ_KICKOFF_SPEED - GetRunSpeed(hero, cfg))
                              / (float)cfg.WJLOCK_STEPS_LONG;

    hero.states.jumping = true;
    hero.wallLockSteps = 0;
    hero.wallLocked = true;
    hero.jumpQueueSteps = 0;
    hero.jumpQueuing = false;
    hero.jumped_steps = 5; // from C# source line 8867
    hero.doubleJumpQueuing = false;
    // [SKIP: cosmetic] animCtrl.SetWallJumped
}

// =============================================================================
// 7. Dash() — per-tick dash physics
// Port of HeroController.cs:4315-4361
// =============================================================================
static inline void Dash(HeroState &hero, const HeroConfig &cfg, float dt) {
    // Port of HeroController.cs:4315-4361
    // [SKIP: CanWallSlide() → BeginWallSlide path — handled in LookForInput]

    AffectedByGravity(hero, false);

    bool wasDashingDown = hero.dashingDown;
    if (hero.states.onGround) {
        hero.dashingDown = false;
    }
    hero.states.mantleRecovery = false;

    if (hero.dashingDown) {
        hero.states.falling = true;
    }

    // Dash finished?
    if (hero.dash_timer <= 0.0f && (!hero.dashingDown)) {
        // FinishedDashing — simplified
        CancelDash(hero);
        if (wasDashingDown) {
            // [SKIP: downDash recovery]
        }
        return;
    }

    float dashSpeed = cfg.DASH_SPEED;

    if (hero.dashingDown) {
        float maxFV = GetMaxFallVelocity(cfg);
        hero.velX = 0.0f;
        hero.velY = -maxFV;
    } else {
        // [SKIP: cosmetic] heroBox.HeroBoxAirdash
        if (hero.states.facingRight) {
            hero.velX = dashSpeed;
            hero.velY = 0.0f;
        } else {
            hero.velX = -dashSpeed;
            hero.velY = 0.0f;
        }
    }

    hero.dash_timer -= dt;
    hero.dash_time += dt;
}

// =============================================================================
// 8. HeroDash() — dash initiation
// Port of HeroController.cs:9003-9088
// =============================================================================
static inline void HeroDash(HeroState &hero, const HeroConfig &cfg,
                              bool inputDown, bool inputLeft, bool inputRight)
{
    // Port of HeroController.cs:9003-9088
    ResetAttacks(hero);
    CancelBounce(hero);
    CancelHeroJump(hero);
    // [SKIP: ShuttleCockCancelInert, audio]

    hero.dashingDown = inputDown && !hero.states.onGround && !inputLeft && !inputRight;

    ResetLook(hero);

    // dashingDown cancel on jump_steps == 0
    if (hero.dashingDown && hero.states.jumping && hero.jump_steps == 0) {
        hero.dashingDown = false;
    }

    if (hero.states.onGround && !hero.dashingDown) {
        hero.dash_timer = cfg.DASH_TIME;
        hero.states.airDashing = false;
        hero.dash_time = 0.0f;
    } else {
        hero.dash_timer = hero.dashingDown ? cfg.DOWN_DASH_TIME : cfg.AIR_DASH_TIME;
        hero.dash_time = 0.0f;
        hero.states.airDashing = true;
        hero.airDashed = true;
    }

    hero.states.recoiling = false;

    if (hero.states.wallSliding) {
        FlipSprite(hero);
    } else if (!hero.dashCurrentFacing) {
        if (inputRight && !inputLeft) {
            FaceRight(hero);
        } else if (inputLeft && !inputRight) {
            FaceLeft(hero);
        }
    }

    hero.states.dashing = true;
    hero.dashQueueSteps = 0;
    hero.wallLocked = false;

    // [SKIP: cosmetic] StartDashEffect, backDashPrefab
    // SetDashCooldownTimer
    hero.dashCooldownTimer = cfg.DASH_COOLDOWN;
    // [SKIP: cosmetic] sprintFSM.SendEvent("DASHED")
}

// =============================================================================
// 9. DoAttack() — attack initiation
// Port of HeroController.cs:4038-4066
// =============================================================================
static inline void DoAttack(HeroState &hero, const HeroConfig &cfg,
                              bool inputUp, bool inputDown)
{
    // Port of HeroController.cs:4038-4066
    ResetLook(hero);

    if (hero.states.dashing || hero.dashingDown) {
        CancelDash(hero);
    }

    hero.states.recoiling = false;

    if (inputUp) {
        // Attack(AttackDirection::upward)
        // Inline Attack() for upward:
        hero.states.floating = false;
        hero.states.attackCount++;
        hero.states.attacking = true;
        hero.attackDuration = cfg.attackDuration;
        if (hero.isUsingQuickening) {
            hero.attackDuration *= 1.0f / cfg.quickAttackSpeedMult;
        }
        hero.states.upAttacking = true;
        hero.prevAttackDir = AttackDirection::upward;
        // DidAttack
        hero.attack_cooldown = hero.isUsingQuickening
                                   ? cfg.quickAttackCooldownTime
                                   : cfg.attackCooldownTime;
        if (hero.attack_cooldown < hero.attackDuration) {
            hero.attack_cooldown = hero.attackDuration;
        }
    } else if (inputDown && !hero.states.onGround) {
        // Attack(AttackDirection::downward) — triggers downspike for Hornet
        hero.states.floating = false;
        hero.states.attackCount++;
        // DownSpike: isSlashing = false, set downSpikeAntic, etc.
        // Simplified: for sim, we model downspike as downAttacking + velocity
        hero.states.downAttacking = true;
        hero.prevAttackDir = AttackDirection::downward;
        // DidAttack
        hero.attack_cooldown = hero.isUsingQuickening
                                   ? cfg.quickAttackCooldownTime
                                   : cfg.attackCooldownTime;
        if (hero.attack_cooldown < cfg.attackDuration) {
            hero.attack_cooldown = cfg.attackDuration;
        }
    } else {
        // Attack(AttackDirection::normal)
        hero.states.floating = false;
        hero.states.attackCount++;
        hero.states.attacking = true;
        hero.attackDuration = cfg.attackDuration;
        if (hero.isUsingQuickening) {
            hero.attackDuration *= 1.0f / cfg.quickAttackSpeedMult;
        }
        hero.prevAttackDir = AttackDirection::normal;
        // DidAttack
        hero.attack_cooldown = hero.isUsingQuickening
                                   ? cfg.quickAttackCooldownTime
                                   : cfg.attackCooldownTime;
        if (hero.attack_cooldown < hero.attackDuration) {
            hero.attack_cooldown = hero.attackDuration;
        }
    }
}

// =============================================================================
// 10. Attack() — attack direction, slash setup
// Port of HeroController.cs:4073-4210
// =============================================================================
static inline void Attack(HeroState &hero, const HeroConfig &cfg,
                           AttackDirection attackDir)
{
    // Port of HeroController.cs:4073-4210
    // TrySetCorrectFacing(force: true) — simplified
    // [SKIP: cosmetic] audio

    hero.states.floating = false;
    hero.states.attackCount++;

    // Alt-attack timing reset
    if (hero.timeSinceLevelLoad - hero.altAttackTime >
        cfg.attackRecoveryTime + cfg.ALT_ATTACK_RESET ||
        attackDir != hero.prevAttackDir) {
        hero.states.altAttack = false;
    }

    if (attackDir != AttackDirection::downward) {
        hero.states.attacking = true;
        hero.attackDuration = cfg.attackDuration;
        if (hero.isUsingQuickening) {
            hero.attackDuration *= 1.0f / cfg.quickAttackSpeedMult;
        }
    }

    // Slash component selection (simplified — no actual GameObjects in sim)
    switch (attackDir) {
    case AttackDirection::normal:
        hero.states.altAttack = !hero.states.altAttack;
        break;
    case AttackDirection::upward:
        hero.states.upAttacking = true;
        hero.states.altAttack = !hero.states.altAttack;
        break;
    case AttackDirection::downward:
        // DownAttack path — DownSpike type for Hornet
        hero.states.downAttacking = true;
        break;
    }

    // Wall slash slowdown
    if ((hero.states.wallSliding || hero.states.wallScrambling) &&
        attackDir == AttackDirection::normal && cfg.wallSlashSlowdown) {
        hero.velY = hero.velY / 2.0f;
        if (hero.velY < -5.0f) hero.velY = -5.0f;
        hero.wallSlashing = true;
    } else {
        hero.wallSlashing = false;
    }

    // Slash direction angle (sim stores direction for hitbox logic externally)
    // [SKIP: cosmetic] SlashComponent, currentSlashDamager direction setup

    hero.altAttackTime = hero.timeSinceLevelLoad;
    // SlashComponent.StartSlash() — hitbox activation handled by combat system
    // DidAttack()
    hero.attack_cooldown = hero.isUsingQuickening
                               ? cfg.quickAttackCooldownTime
                               : cfg.attackCooldownTime;
    float dur = cfg.attackDuration;
    if (hero.attack_cooldown < dur) {
        hero.attack_cooldown = dur;
    }

    hero.prevAttackDir = attackDir;
}

// =============================================================================
// 11. DidAttack() — set attack_cooldown
// Port of HeroController.cs:4305-4313
// =============================================================================
static inline void DidAttack(HeroState &hero, const HeroConfig &cfg) {
    // Port of HeroController.cs:4305-4313
    float dur = cfg.attackDuration;
    hero.attack_cooldown = hero.isUsingQuickening
                               ? cfg.quickAttackCooldownTime
                               : cfg.attackCooldownTime;
    if (hero.attack_cooldown < dur) {
        hero.attack_cooldown = dur;
    }
}

// =============================================================================
// 12. CanAttack() — cooldown check
// Port of HeroController.cs:10901-10908
// =============================================================================
static inline bool CanAttack(const HeroState &hero, const HeroConfig &cfg) {
    // Port of HeroController.cs:10901-10908
    if (hero.attack_cooldown > 0.0f) return false;
    // CanAttackAction() simplified for sim (lines 10947-10953):
    // No dead/hazard/relinquished checks — sim doesn't model those
    if (hero.states.attacking) return false;
    if (hero.states.dashing && !hero.dashingDown) return false;
    if (hero.states.dead) return false;
    if (hero.hero_state == ActorStates::no_input) return false;
    if (hero.hero_state == ActorStates::hard_landing) return false;
    if (hero.hero_state == ActorStates::dash_landing) return false;
    return true;
}

// =============================================================================
// 13. CanJump() — jump eligibility
// Port of HeroController.cs:10768-10788
// =============================================================================
static inline bool CanJump(const HeroState &hero, const HeroConfig &cfg) {
    // Port of HeroController.cs:10768-10788
    if (hero.hero_state == ActorStates::no_input) return false;
    if (hero.hero_state == ActorStates::hard_landing) return false;
    if (hero.hero_state == ActorStates::dash_landing) return false;
    if (hero.states.wallSliding) return false;
    if (hero.states.dashing) return false;
    if (hero.states.isSprinting) return false;
    if (hero.states.backDashing) return false;
    if (hero.states.jumping) return false;
    if (hero.states.bouncing) return false;
    if (hero.states.shroomBouncing) return false;
    if (hero.states.downSpikeRecovery) return false;

    if (hero.states.onGround) return true;

    // Ledge buffer (coyote time)
    if (hero.ledgeBufferSteps > 0 && !hero.states.dead &&
        !hero.states.hazardDeath && !hero.controlReqlinquished &&
        hero.headBumpSteps <= 0) {
        return true;
    }

    return false;
}

// =============================================================================
// 14. CanDoubleJump() — double jump eligibility
// Port of HeroController.cs:10808-10827
// =============================================================================
static inline bool CanDoubleJump(const HeroState &hero, const HeroConfig &cfg) {
    // Port of HeroController.cs:10808-10827
    if (hero.hero_state == ActorStates::no_input) return false;
    if (hero.hero_state == ActorStates::hard_landing) return false;
    if (hero.hero_state == ActorStates::dash_landing) return false;
    if (hero.controlReqlinquished) return false;

    if (!cfg.hasDoubleJump) return false;
    if (hero.doubleJumped) return false;
    // IsDashLocked simplified
    if (hero.states.dashing && !hero.dashingDown) return false;
    if (hero.states.wallSliding) return false;
    if (hero.states.backDashing) return false;
    // IsAttackLocked simplified
    if (hero.states.attacking && hero.attack_time < cfg.attackRecoveryTime) return false;
    if (hero.states.bouncing) return false;
    if (hero.states.shroomBouncing) return false;
    if (hero.states.onGround) return false;
    if (hero.states.doubleJumping) return false;
    if (!cfg.canDoubleJump) return false;

    return true;
}

// =============================================================================
// 15. CanDash() — dash eligibility
// Port of HeroController.cs:10847-10853
// =============================================================================
static inline bool CanDash(const HeroState &hero, const HeroConfig &cfg) {
    // Port of HeroController.cs:10847-10853
    if (hero.hero_state == ActorStates::no_input) return false;
    if (hero.hero_state == ActorStates::hard_landing) return false;
    if (hero.hero_state == ActorStates::dash_landing) return false;
    if (hero.dashCooldownTimer > 0.0f) return false;
    if (hero.states.dashing) return false;
    if (hero.states.backDashing) return false;
    if (hero.states.attacking && hero.attack_time < cfg.attackRecoveryTime) return false;
    if (hero.states.preventDash) return false;
    // Can only air-dash once (unless on ground or wall)
    if (!hero.states.onGround && hero.airDashed && !hero.states.wallSliding) return false;
    if (hero.states.hazardDeath) return false;
    if (!cfg.hasDash) return false;
    return true;
}

// =============================================================================
// 16. CanWallJump() — wall jump eligibility
// Port of HeroController.cs:11205-11228
// =============================================================================
static inline bool CanWallJump(const HeroState &hero, const HeroConfig &cfg) {
    // Port of HeroController.cs:11205-11228
    if (!cfg.hasWalljump) return false;
    if (hero.states.touchingNonSlider) return false;
    if (hero.states.wallSliding) return true;
    if (hero.states.touchingWall && !hero.states.onGround) {
        // CanChainWallJumps simplified
        if (hero.dashingDown) return false;
        if (!hero.wallLocked && hero.wallJumpChainStepsLeft <= 0) {
            return fabsf(hero.move_input) > 1e-5f;
        }
        return true;
    }
    return false;
}

// =============================================================================
// 17. TakeDamage() — damage reception
// Port of HeroController.cs:5254-5630 (heavily simplified for sim)
// =============================================================================
static inline void TakeDamage(HeroState &hero, const HeroConfig &cfg,
                               int damageAmount, bool fromLeft, float &freezeTimer)
{
    // Port of HeroController.cs:5254-5630 (simplified)
    // In the sim we only deal with ENEMY hazard type (boss contact / projectile).
    // Skip: all hazard-type-specific logic, crests, charm effects.

    if (damageAmount <= 0) return;

    // Invulnerability check (simplified CanTakeDamage)
    if (hero.states.Invulnerable()) return;
    if (hero.states.recoiling) return;
    if (hero.states.dead) return;
    if (hero.states.shadowDashing) return;
    if (hero.states.evading) return;
    if (hero.states.parryAttack) return;
    if (hero.states.downspikeInvulnerabilitySteps > 0) return;

    // Apply damage
    hero.health -= damageAmount;
    if (hero.health < 0) hero.health = 0;

    // [SKIP: cosmetic] audio, VFX, charm effects

    // Cancel current actions (lines 5537-5569)
    ResetAttacks(hero);
    hero.acceptingInput = true;
    hero.controlReqlinquished = false;

    if (hero.states.wallSliding) {
        hero.states.wallSliding = false;
        hero.states.wallClinging = false;
    }
    if (hero.states.touchingWall) {
        hero.states.touchingWall = false;
    }
    if (hero.states.recoilingLeft || hero.states.recoilingRight) {
        CancelRecoilHorizontal(hero);
    }
    if (hero.states.bouncing || hero.states.shroomBouncing) {
        CancelBounce(hero);
        hero.velY = 0.0f;
    }

    // Death check (line 5570-5578)
    if (hero.health <= 0) {
        hero.states.dead = true;
        hero.velX = 0.0f;
        hero.velY = 0.0f;
        return;
    }

    // StartRecoil (inline — see below, lines 5629-5632)
    // The actual StartRecoil is a coroutine in C#. We flatten it here.
    if (!hero.states.recoiling) {
        float recoilVel = cfg.RECOIL_VELOCITY;
        float invulTime = cfg.INVUL_TIME;

        // ResetMotion (simplified — zero velocity, cancel states)
        hero.velX = 0.0f;
        hero.velY = 0.0f;
        AffectedByGravity(hero, false);

        // Recoil direction (lines 9571-9590)
        if (fromLeft) {
            // Hit from left → recoil right
            hero.recoilVecX = recoilVel;
            hero.recoilVecY = recoilVel * 0.5f;
            if (hero.states.facingRight) {
                FlipSprite(hero);
            }
        } else {
            // Hit from right → recoil left
            hero.recoilVecX = -recoilVel;
            hero.recoilVecY = recoilVel * 0.5f;
            if (!hero.states.facingRight) {
                FlipSprite(hero);
            }
        }

        SetState(hero, ActorStates::no_input);
        hero.states.recoilFrozen = true;
        hero.states.onGround = false;
        hero.states.wasOnGround = false;
        hero.ledgeBufferSteps = 0;
        hero.sprintBufferSteps = 0;
        hero.syncBufferSteps = false;

        // StartInvulnerable(invulTime) — set timer
        hero.states.invulnerable = true;
        hero.invulFreezeTimer = cfg.DAMAGE_FREEZE_DOWN;
        hero.invulTimer = invulTime;

        // FreezeMoment — set global freeze timer
        freezeTimer = cfg.DAMAGE_FREEZE_WAIT + cfg.DAMAGE_FREEZE_UP;

        // recoilFrozen will be cleared after freeze, then recoiling = true
        hero.damageFreezeTimer = cfg.DAMAGE_FREEZE_WAIT + cfg.DAMAGE_FREEZE_UP;
        hero.recoilTimer = cfg.RECOIL_DURATION;
    }
}

// =============================================================================
// 18. StartRecoil() — recoil vector, gravity disable
// Port of HeroController.cs:9556-9613
// NOTE: Inlined into TakeDamage above. This standalone version is provided
//       for reference / direct call if needed.
// =============================================================================
static inline void StartRecoil(HeroState &hero, const HeroConfig &cfg,
                                bool fromLeft, int damageAmount, float &freezeTimer)
{
    // Port of HeroController.cs:9556-9613
    if (hero.states.recoiling) return;

    float recoilVel = cfg.RECOIL_VELOCITY;
    float invulTime = cfg.INVUL_TIME;
    // [SKIP: WeightedAnklet tool multipliers]

    // ResetMotion
    hero.velX = 0.0f;
    hero.velY = 0.0f;
    AffectedByGravity(hero, false);

    if (fromLeft) {
        hero.recoilVecX = recoilVel;
        hero.recoilVecY = recoilVel * 0.5f;
        if (hero.states.facingRight) FlipSprite(hero);
    } else {
        hero.recoilVecX = -recoilVel;
        hero.recoilVecY = recoilVel * 0.5f;
        if (!hero.states.facingRight) FlipSprite(hero);
    }

    SetState(hero, ActorStates::no_input);
    hero.states.recoilFrozen = true;
    hero.states.onGround = false;
    hero.states.wasOnGround = false;
    hero.ledgeBufferSteps = 0;
    hero.sprintBufferSteps = 0;
    hero.syncBufferSteps = false;

    // [SKIP: cosmetic] damageEffectFSM

    // StartInvulnerable(invulTime) — lines 9615-9636
    hero.states.invulnerable = true;
    hero.invulFreezeTimer = cfg.DAMAGE_FREEZE_DOWN;
    hero.invulTimer = invulTime;

    // FreezeMoment
    freezeTimer = cfg.DAMAGE_FREEZE_WAIT + cfg.DAMAGE_FREEZE_UP;

    hero.damageFreezeTimer = cfg.DAMAGE_FREEZE_WAIT + cfg.DAMAGE_FREEZE_UP;
    hero.recoilTimer = cfg.RECOIL_DURATION;
}

// =============================================================================
// 19. BeginWallSlide() — wall slide initiation
// Port of HeroController.cs:8406-8473
// =============================================================================
static inline void BeginWallSlide(HeroState &hero, const HeroConfig &cfg,
                                   bool requireInput,
                                   bool inputLeft, bool inputRight)
{
    // Port of HeroController.cs:8406-8473
    if (hero.states.wallSliding) return;

    bool started = false;
    if (hero.touchingWallL && (!requireInput || inputLeft)) {
        hero.wallSlidingL = true;
        hero.wallSlidingR = false;
        FaceLeft(hero);
        started = true;
    }
    if (hero.touchingWallR && (!requireInput || inputRight)) {
        hero.wallSlidingL = false;
        hero.wallSlidingR = true;
        FaceRight(hero);
        started = true;
    }
    if (!started) return;

    // [SKIP: ShuttleCock handling, cosmetic]

    CancelJump(hero);
    if (hero.states.dashing) {
        CancelDash(hero);
    }
    hero.airDashed = false;
    hero.doubleJumped = false;
    hero.states.wallSliding = true;
    AffectedByGravity(hero, false);
    hero.states.willHardLand = false;
    // [SKIP: extraAirMoveVelocities.Clear()]
    hero.dashCooldownTimer = 0.0f;
    // [SKIP: cosmetic] CancelFallEffects, heroBox.HeroBoxWallSlide
}

// =============================================================================
// 20. CanWallSlide() — simplified for sim
// Port of HeroController.cs:11142-11158
// =============================================================================
static inline bool CanWallSlide(const HeroState &hero) {
    // Port of HeroController.cs:11142-11158
    // CanInput + CanContinueWallSlide simplified
    if (!hero.acceptingInput) return false;
    if (hero.controlReqlinquished) return false;
    if (!hero.touchingWallL && !hero.touchingWallR) return false;
    // CanStartWithWallSlide — we don't check all conditions,
    // but the essential one is that hero must be airborne
    if (hero.states.onGround) return false;
    return true;
}

// =============================================================================
// 21. DoMovement() — movement dispatch
// Port of HeroController.cs:3372-3396
// =============================================================================
static inline void DoMovement(HeroState &hero, const HeroConfig &cfg,
                                bool useInput)
{
    // Port of HeroController.cs:3372-3396
    if (hero.states.backDashing || hero.states.dashing) return;

    Move(hero, cfg, hero.move_input, useInput);

    // TrySetCorrectFacing (simplified) — face movement direction
    if ((!hero.states.attacking ||
         hero.attack_time >= cfg.attackRecoveryTime) &&
        !hero.states.wallSliding && !hero.wallLocked &&
        !hero.states.shuttleCock && !hero.states.isToolThrowing) {
        if (hero.move_input > 0.0f && !hero.states.facingRight) {
            hero.states.facingRight = true;
            if (!cfg.canTurnWhileSlashing) {
                ResetAttacks(hero);
            }
        } else if (hero.move_input < 0.0f && hero.states.facingRight) {
            hero.states.facingRight = false;
            if (!cfg.canTurnWhileSlashing) {
                ResetAttacks(hero);
            }
        }
    }

    // DoRecoilMovement (lines 3398-3410)
    if (hero.states.recoilingLeft) {
        float rv = hero.recoilVelocity;
        if (hero.velX - rv > -rv) {
            hero.velX = -rv;
        } else {
            hero.velX -= rv;
        }
    }
    if (hero.states.recoilingRight) {
        float rv = hero.recoilVelocity;
        if (hero.velX + rv < rv) {
            hero.velX = rv;
        } else {
            hero.velX += rv;
        }
    }
}

// =============================================================================
// 22. LookForInput() — input -> state transitions
// Port of HeroController.cs:8312-8690
// (Merged with LookForQueueInput lines 8514-8673 for simplicity)
//
// In the sim, input comes from the RL action tensor, mapped to:
//   inputLeft, inputRight, inputUp, inputDown,
//   jumpPressed, jumpHeld, attackPressed, dashPressed
// =============================================================================
static inline void LookForInput(HeroState &hero, const HeroConfig &cfg,
                                  bool inputLeft, bool inputRight,
                                  bool inputUp, bool inputDown,
                                  bool jumpPressed, bool jumpHeld,
                                  bool attackPressed, bool dashPressed,
                                  bool jumpWasReleased)
{
    // Port of HeroController.cs:8312-8690

    // Compute move_input
    hero.move_input = 0.0f;
    if (inputRight && !inputLeft) hero.move_input = 1.0f;
    else if (inputLeft && !inputRight) hero.move_input = -1.0f;

    if (!hero.acceptingInput) return;

    // --- Wall slide detection (line 8342-8345) ---
    if (CanWallSlide(hero) && !hero.states.attacking) {
        BeginWallSlide(hero, cfg, true, inputLeft, inputRight);
    }

    // --- Wall slide cancel on down press (line 8347-8351) ---
    if (hero.states.wallSliding && inputDown &&
        !(hero.touchingWallL && inputLeft) &&
        !(hero.touchingWallR && inputRight)) {
        CancelWallsliding(hero);
        FlipSprite(hero);
    }

    // --- Wall lock release (lines 8352-8358) ---
    if (hero.wallLocked && hero.wallJumpedL && inputRight &&
        hero.wallLockSteps >= cfg.WJLOCK_STEPS_SHORT) {
        hero.wallLocked = false;
    }
    if (hero.wallLocked && hero.wallJumpedR && inputLeft &&
        hero.wallLockSteps >= cfg.WJLOCK_STEPS_SHORT) {
        hero.wallLocked = false;
    }

    // --- Jump release (lines 8360-8375) ---
    if (jumpWasReleased) {
        if (hero.states.floating) {
            hero.states.floating = false;
        }
    }
    if (!jumpHeld) {
        // JumpReleased — cut upward velocity
        if (hero.states.jumping && hero.jump_steps >= cfg.JUMP_STEPS_MIN) {
            CancelJump(hero);
            if (hero.velY > 0.0f) {
                hero.velY *= 0.5f;  // jump release velocity cut
                if (hero.velY < cfg.MIN_JUMP_SPEED) {
                    hero.velY = cfg.MIN_JUMP_SPEED;
                }
            }
        }
    }

    // --- Dash release (lines 8376-8383) ---
    if (!dashPressed) {
        if (hero.states.preventDash && !hero.states.dashCooldown) {
            hero.states.preventDash = false;
        }
        hero.dashQueuing = false;
    }

    // --- Attack release (lines 8384-8387) ---
    if (!attackPressed) {
        hero.attackQueuing = false;
    }

    // =====================================================
    // LookForQueueInput (merged, lines 8514-8673)
    // =====================================================

    // --- Jump pressed ---
    if (jumpPressed) {
        if (hero.acceptingInput && CanWallJump(hero, cfg)) {
            DoWallJump(hero, cfg);
        } else if (hero.acceptingInput && CanJump(hero, cfg)) {
            HeroJump(hero, cfg);
        } else if (hero.acceptingInput && !hero.wallLocked &&
                   CanDoubleJump(hero, cfg)) {
            DoDoubleJump(hero, cfg);
        } else {
            // Queue jump
            hero.jumpQueueSteps = 0;
            hero.jumpQueuing = true;
            if (!hero.states.jumping) {
                hero.doubleJumpQueueSteps = 0;
                hero.doubleJumpQueuing = true;
            }
        }
    }

    // --- Dash pressed ---
    if (dashPressed) {
        if (hero.acceptingInput && CanDash(hero, cfg)) {
            HeroDash(hero, cfg, inputDown, inputLeft, inputRight);
        } else {
            hero.dashQueueSteps = 0;
            hero.dashQueuing = true;
        }
    }

    // --- Attack pressed ---
    if (attackPressed) {
        if (hero.acceptingInput && CanAttack(hero, cfg)) {
            DoAttack(hero, cfg, inputUp, inputDown);
        } else {
            hero.attackQueueSteps = 0;
            hero.attackQueuing = true;
        }
    }

    // --- Queue processing (held buttons, lines 8634-8672) ---
    if (jumpHeld) {
        if (hero.jumpQueueSteps <= cfg.JUMP_QUEUE_STEPS && hero.jumpQueuing &&
            CanJump(hero, cfg)) {
            HeroJump(hero, cfg);
        } else if (hero.doubleJumpQueueSteps <= cfg.DOUBLE_JUMP_QUEUE_STEPS &&
                   hero.doubleJumpQueuing && CanDoubleJump(hero, cfg)) {
            if (hero.states.onGround) {
                HeroJump(hero, cfg);
            } else {
                DoDoubleJump(hero, cfg);
            }
        }
    }

    if (dashPressed && hero.dashQueueSteps <= cfg.DASH_QUEUE_STEPS &&
        hero.dashQueuing && CanDash(hero, cfg)) {
        HeroDash(hero, cfg, inputDown, inputLeft, inputRight);
    }

    if (attackPressed && hero.attackQueueSteps <= cfg.ATTACK_QUEUE_STEPS &&
        CanAttack(hero, cfg) && hero.attackQueuing) {
        DoAttack(hero, cfg, inputUp, inputDown);
    }
}

// =============================================================================
// 23. heroFixedUpdate() — per-frame dispatcher
// Port of HeroController.cs FixedUpdate (lines 2966-3280)
// This is the main entry point called each sim tick.
// =============================================================================
static inline void heroFixedUpdate(HeroState &hero, const HeroConfig &cfg,
                                    float dt)
{
    // Port of HeroController.cs:2966-3280

    // --- Horizontal recoil countdown (lines 2968-2978) ---
    if (hero.states.recoilingLeft || hero.states.recoilingRight) {
        if (hero.recoilStepsLeft > 0) {
            hero.recoilStepsLeft--;
        } else {
            CancelRecoilHorizontal(hero);
        }
    }

    // [SKIP: extraAirMoveVelocities decay loop — not modelled]

    // --- Dead state (lines 2992-2995) ---
    if (hero.states.dead) {
        hero.velX = 0.0f;
        hero.velY = 0.0f;
        return;
    }

    // [SKIP: UpdateSteepSlopes — not modelled in sim tilemap]

    // --- Hard/dash landing (lines 2997-3001) ---
    if (hero.hero_state == ActorStates::hard_landing ||
        hero.hero_state == ActorStates::dash_landing) {
        ResetMotion(hero);
        return;
    }

    // --- no_input state (lines 3002-3040) ---
    if (hero.hero_state == ActorStates::no_input) {
        if (hero.states.recoiling) {
            AffectedByGravity(hero, false);
            hero.velX = hero.recoilVecX;
            hero.velY = hero.recoilVecY;
        }
        // [SKIP: transitioning paths — not modelled in sim]
        // Fall through — don't run normal movement during no_input
    }

    // --- Normal movement (lines 3041-3186) ---
    if (hero.hero_state != ActorStates::no_input) {
        if (hero.states.transitioning) return;

        DoMovement(hero, cfg, hero.acceptingInput);

        // [SKIP: ResetLook on move during look (lines 3048-3051)]

        // Jump tick (lines 3052-3055)
        if (hero.states.jumping && !hero.states.dashing &&
            !hero.states.isSprinting) {
            Jump(hero, cfg);
        }

        // Double jump tick (lines 3057-3059)
        if (hero.states.doubleJumping) {
            DoubleJump(hero, cfg);
        }

        // Dash tick (lines 3060-3062)
        if (hero.states.dashing) {
            Dash(hero, cfg, dt);
        }

        // [SKIP: downSpiking, floating, casting, bouncing — simplified]

        // Bouncing (line 3091-3094)
        if (hero.states.bouncing) {
            hero.velY = cfg.BOUNCE_VELOCITY;
        }

        // Wall jump lock movement (lines 3111-3132)
        if (hero.wallJumpChainStepsLeft > 0) {
            hero.wallJumpChainStepsLeft--;
        }
        if (hero.wallLocked) {
            if (hero.wallJumpedR) {
                hero.velX = hero.currentWalljumpSpeed;
            } else if (hero.wallJumpedL) {
                hero.velX = -hero.currentWalljumpSpeed;
            }
            hero.wallLockSteps++;
            if (hero.wallLockSteps > cfg.WJLOCK_STEPS_LONG) {
                hero.wallLocked = false;
                hero.wallJumpChainStepsLeft = cfg.WJLOCK_CHAIN_STEPS;
            }
            hero.currentWalljumpSpeed -= hero.walljumpSpeedDecel;
        }

        // Wall slide unstick (lines 3133-3174) — handled in LookForInput
    }

    // --- Terminal velocity clamp (lines 3191-3195) ---
    float maxFV = GetMaxFallVelocity(cfg);
    if (hero.velY < -maxFV) {
        hero.velY = -maxFV;
    }

    // --- Queue step counters (lines 3196-3218) ---
    if (hero.jumpQueuing)       hero.jumpQueueSteps++;
    if (hero.doubleJumpQueuing) hero.doubleJumpQueueSteps++;
    if (hero.dashQueuing)       hero.dashQueueSteps++;
    if (hero.attackQueuing)     hero.attackQueueSteps++;
}

// =============================================================================
// 24. heroUpdateTimers() — decrement real-time timers each tick
//     This handles the per-frame timer decrements that were scattered across
//     HeroController.Update() and FixedUpdate() in the C# source.
// =============================================================================
static inline void heroUpdateTimers(HeroState &hero, const HeroConfig &cfg,
                                     float dt)
{
    // Attack cooldown (decremented in Update in C#, we do it per fixed step)
    if (hero.attack_cooldown > 0.0f) {
        hero.attack_cooldown -= dt;
        if (hero.attack_cooldown < 0.0f) hero.attack_cooldown = 0.0f;
    }

    // Attack duration timer
    if (hero.states.attacking) {
        hero.attack_time += dt;
        hero.attackDuration -= dt;
        if (hero.attackDuration <= 0.0f) {
            hero.states.attacking = false;
            hero.states.upAttacking = false;
            hero.states.downAttacking = false;
        }
    } else {
        hero.attack_time = 0.0f;
    }

    // Dash cooldown
    if (hero.dashCooldownTimer > 0.0f) {
        hero.dashCooldownTimer -= dt;
        if (hero.dashCooldownTimer < 0.0f) hero.dashCooldownTimer = 0.0f;
    }

    // Ledge buffer (coyote time — decrements per fixed tick, not dt)
    if (hero.ledgeBufferSteps > 0 && !hero.states.onGround) {
        hero.ledgeBufferSteps--;
    }

    // Head bump steps
    if (hero.headBumpSteps > 0) {
        hero.headBumpSteps--;
    }

    // Sprint buffer steps
    if (hero.sprintBufferSteps > 0) {
        hero.sprintBufferSteps--;
    }
    if (hero.syncBufferSteps && hero.ledgeBufferSteps > 0) {
        hero.sprintBufferSteps = hero.ledgeBufferSteps;
    }

    // Invulnerability timer (flattened from coroutine Invulnerable)
    if (hero.states.invulnerable) {
        if (hero.invulFreezeTimer > 0.0f) {
            hero.invulFreezeTimer -= dt;
        } else {
            hero.invulTimer -= dt;
            if (hero.invulTimer <= 0.0f) {
                hero.states.invulnerable = false;
                hero.states.recoiling = false;
            }
        }
    }

    // Damage freeze → recoil transition
    // (flattened from StartRecoil coroutine: freeze phase, then recoil phase)
    if (hero.damageFreezeTimer > 0.0f) {
        hero.damageFreezeTimer -= dt;
        if (hero.damageFreezeTimer <= 0.0f) {
            hero.damageFreezeTimer = 0.0f;
            hero.states.recoilFrozen = false;
            hero.states.recoiling = true;
        }
    }

    // Recoil duration
    if (hero.states.recoiling) {
        hero.recoilTimer -= dt;
        if (hero.recoilTimer <= 0.0f) {
            hero.states.recoiling = false;
            hero.states.recoilFrozen = false;
            AffectedByGravity(hero, true);
            SetState(hero, ActorStates::airborne);
            hero.acceptingInput = true;
        }
    }

    // Wall slide velocity (gravity replacement when wall sliding)
    if (hero.states.wallSliding) {
        // Wall slide: override velocity to slide down slowly
        // In the real game this is done via rb2d.gravityScale = 0 + manual vel
        // WALLSLIDE_ACCEL not extracted — use a fixed slide speed
        if (hero.velY < -8.0f) { // WALLSLIDE max fall speed = 8.0
            hero.velY = -8.0f;
        }
    }

    // Episode time
    hero.timeSinceLevelLoad += dt;
}

// =============================================================================
// 25. heroTick() — top-level per-frame hero update
//     Called by sim.cpp's heroStepSystem. Combines LookForInput + FixedUpdate.
//     Arena is passed for ground/wall detection (done by sim.cpp integration).
// =============================================================================
static inline void heroTick(HeroState &hero, const HeroConfig &cfg,
                             bool inputLeft, bool inputRight,
                             bool inputUp, bool inputDown,
                             bool jumpPressed, bool jumpHeld,
                             bool attackPressed, bool dashPressed,
                             uint16_t prevBits, uint16_t curBits,
                             float dt, float &freezeTimer)
{
    // Determine "was released" from bit transitions
    bool jumpWasReleased = (prevBits & (1u << 4)) && !(curBits & (1u << 4));

    // 1. Input processing (LookForInput + LookForQueueInput)
    LookForInput(hero, cfg,
                 inputLeft, inputRight, inputUp, inputDown,
                 jumpPressed, jumpHeld,
                 attackPressed, dashPressed,
                 jumpWasReleased);

    // 2. Physics tick (FixedUpdate)
    heroFixedUpdate(hero, cfg, dt);

    // 3. Timer decrements
    heroUpdateTimers(hero, cfg, dt);

    // Store current bits for next frame's edge detection
    hero.prevActionBits = curBits;
}

// =============================================================================
// 26. heroStateInit() — initialize HeroState for episode start
// =============================================================================
static inline void heroStateInit(HeroState &hero, const HeroConfig &cfg,
                                  float spawnX, float spawnY)
{
    hero.posX = spawnX;
    hero.posY = spawnY;
    hero.velX = 0.0f;
    hero.velY = 0.0f;

    hero.states.Reset();
    hero.states.facingRight = true;
    hero.states.onGround = true;

    hero.hero_state = ActorStates::idle;
    hero.prev_hero_state = ActorStates::idle;

    hero.jump_steps = 0;
    hero.jumped_steps = 0;
    hero.doubleJump_steps = 0;
    hero.doubleJumped = false;

    hero.dash_timer = 0.0f;
    hero.dash_time = 0.0f;
    hero.dashCooldownTimer = 0.0f;
    hero.airDashed = false;
    hero.dashingDown = false;
    hero.dashCurrentFacing = false;

    hero.attack_cooldown = 0.0f;
    hero.attackDuration = 0.0f;
    hero.attack_time = 0.0f;
    hero.prevAttackDir = AttackDirection::normal;
    hero.altAttackTime = 0.0f;
    hero.wallSlashing = false;

    hero.touchingWallL = false;
    hero.touchingWallR = false;
    hero.wallSlidingL = false;
    hero.wallSlidingR = false;
    hero.currentWalljumpSpeed = 0.0f;
    hero.walljumpSpeedDecel = 0.0f;
    hero.wallUnstickSteps = 0;
    hero.wallJumpedR = false;
    hero.wallJumpedL = false;
    hero.wallLocked = false;
    hero.wallLockSteps = 0;
    hero.wallJumpChainStepsLeft = 0;

    hero.recoilVelocity = cfg.RECOIL_HOR_VELOCITY;
    hero.recoilStepsLeft = 0;

    hero.recoilTimer = 0.0f;
    hero.recoilVecX = 0.0f;
    hero.recoilVecY = 0.0f;

    hero.invulTimer = 0.0f;
    hero.invulFreezeTimer = 0.0f;
    hero.damageFreezeTimer = 0.0f;

    hero.gravityScale = 1.0f;
    hero.gravityApplies = true;

    hero.move_input = 0.0f;

    hero.ledgeBufferSteps = 0;
    hero.sprintBufferSteps = 0;
    hero.syncBufferSteps = false;
    hero.headBumpSteps = 0;

    hero.jumpQueueSteps = 0;
    hero.jumpQueuing = false;
    hero.doubleJumpQueueSteps = 0;
    hero.doubleJumpQueuing = false;
    hero.dashQueueSteps = 0;
    hero.dashQueuing = false;
    hero.attackQueueSteps = 0;
    hero.attackQueuing = false;

    hero.acceptingInput = true;
    hero.controlReqlinquished = false;
    hero.isUsingQuickening = false;
    hero.timeSinceLevelLoad = 0.0f;

    hero.health = cfg.hasDash ? 9 : 9; // playerMaxHealth
    hero.maxHealth = 9;
    hero.silk = 12; // playerMaxSilk

    hero.prevActionBits = 0;
}

} // namespace silksong
