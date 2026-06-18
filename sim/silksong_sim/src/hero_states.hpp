#pragma once
// Port of decompiled/HeroControllerStates.cs (353 lines)
// Every public bool field from the C# class is ported as a bool member.
// Integer fields (attackCount, downspikeInvulnerabilitySteps, etc.) are kept
// as int32_t.  The Reset() method mirrors the C# Reset() exactly.

#include <cstdint>

namespace silksong {

struct HeroStates {
    // --- Bool flags (match C# field order) ---
    bool facingRight;
    bool onGround;
    bool jumping;
    bool shuttleCock;
    bool floating;
    bool wallJumping;
    bool doubleJumping;
    bool nailCharging;
    bool shadowDashing;
    bool swimming;
    bool falling;
    bool dashing;
    bool isSprinting;
    bool isBackSprinting;
    bool isBackScuttling;
    bool airDashing;
    bool superDashing;
    bool superDashOnWall;
    bool backDashing;
    bool touchingWall;
    bool wallSliding;
    bool wallClinging;
    bool wallScrambling;
    bool transitioning;
    bool attacking;

    int32_t attackCount;

    bool lookingUp;
    bool lookingDown;
    bool lookingUpRing;
    bool lookingDownRing;
    bool lookingUpAnim;
    bool lookingDownAnim;
    bool altAttack;
    bool upAttacking;
    bool downAttacking;
    bool downTravelling;
    bool downSpikeAntic;
    bool downSpiking;
    bool downSpikeBouncing;
    bool downSpikeBouncingShort;
    bool downSpikeRecovery;
    bool bouncing;
    bool shroomBouncing;
    bool recoilingRight;
    bool recoilingLeft;
    bool recoilingDrill;
    bool dead;
    bool isFrostDeath;
    bool hazardDeath;
    bool hazardRespawning;
    bool willHardLand;
    bool recoilFrozen;
    bool recoiling;
    bool invulnerable;

    // Private in C# but needed for the Invulnerable property
    int32_t invulnerableCount;

    bool casting;
    bool castRecoiling;
    bool preventDash;
    bool preventBackDash;
    bool dashCooldown;
    bool backDashCooldown;
    bool nearBench;
    bool inWalkZone;
    bool isPaused;
    bool onConveyor;
    bool onConveyorV;
    bool inConveyorZone;
    bool spellQuake;
    bool freezeCharge;
    bool focusing;
    bool inAcid;
    bool touchingNonSlider;
    bool wasOnGround;
    bool parrying;
    bool parryAttack;
    bool mantling;
    bool mantleRecovery;
    bool inUpdraft;

    int32_t downspikeInvulnerabilitySteps;

    bool isToolThrowing;
    int32_t toolThrowCount;
    int32_t throwingToolVertical;

    bool isInCancelableFSMMove;
    bool inWindRegion;
    bool isMaggoted;
    bool inFrostRegion;
    bool isFrosted;
    bool isTouchingSlopeLeft;
    bool isTouchingSlopeRight;
    bool isBinding;
    bool needolinPlayingMemory;
    bool isScrewDownAttacking;
    bool evading;
    bool whipLashing;
    bool fakeHurt;
    bool isInCutsceneMovement;
    bool isTriggerEventsPaused;

    // --- Property mirroring C# Invulnerable getter ---
    inline bool Invulnerable() const {
        return invulnerable || (invulnerableCount > 0);
    }

    // --- Reset — mirrors C# Reset() exactly (lines 279-329) ---
    inline void Reset() {
        onGround = false;
        jumping = false;
        falling = false;
        dashing = false;
        isSprinting = false;
        isBackSprinting = false;
        backDashing = false;
        touchingWall = false;
        wallSliding = false;
        wallClinging = false;
        transitioning = false;
        attacking = false;
        lookingUp = false;
        lookingDown = false;
        altAttack = false;
        upAttacking = false;
        downAttacking = false;
        downTravelling = false;
        bouncing = false;
        dead = false;
        isFrostDeath = false;
        hazardDeath = false;
        willHardLand = false;
        recoiling = false;
        recoilFrozen = false;
        invulnerable = false;
        casting = false;
        castRecoiling = false;
        preventDash = false;
        preventBackDash = false;
        dashCooldown = false;
        backDashCooldown = false;
        attackCount = 0;
        downspikeInvulnerabilitySteps = 0;
        isToolThrowing = false;
        toolThrowCount = 0;
        throwingToolVertical = 0;
        isInCancelableFSMMove = false;
        mantling = false;
        isBinding = false;
        needolinPlayingMemory = false;
        isScrewDownAttacking = false;
        evading = false;
        fakeHurt = false;
        invulnerableCount = 0;
        isTriggerEventsPaused = false;
        isInCutsceneMovement = false;

        // Fields not explicitly reset in C# Reset() but initialised to defaults
        facingRight = false;
        shuttleCock = false;
        floating = false;
        wallJumping = false;
        doubleJumping = false;
        nailCharging = false;
        shadowDashing = false;
        swimming = false;
        airDashing = false;
        superDashing = false;
        superDashOnWall = false;
        wallScrambling = false;
        lookingUpRing = false;
        lookingDownRing = false;
        lookingUpAnim = false;
        lookingDownAnim = false;
        downSpikeAntic = false;
        downSpiking = false;
        downSpikeBouncing = false;
        downSpikeBouncingShort = false;
        downSpikeRecovery = false;
        shroomBouncing = false;
        recoilingRight = false;
        recoilingLeft = false;
        recoilingDrill = false;
        hazardRespawning = false;
        nearBench = false;
        inWalkZone = false;
        isPaused = false;
        onConveyor = false;
        onConveyorV = false;
        inConveyorZone = false;
        spellQuake = false;
        freezeCharge = false;
        focusing = false;
        inAcid = false;
        touchingNonSlider = false;
        wasOnGround = false;
        parrying = false;
        parryAttack = false;
        mantleRecovery = false;
        inUpdraft = false;
        inWindRegion = false;
        isMaggoted = false;
        inFrostRegion = false;
        isFrosted = false;
        isTouchingSlopeLeft = false;
        isTouchingSlopeRight = false;
        whipLashing = false;
        isInCutsceneMovement = false;
    }
};

} // namespace silksong
