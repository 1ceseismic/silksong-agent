using System;
using System.Collections;
using System.Reflection;
using UnityEngine;
using HutongGames.PlayMaker;

namespace SilksongAgent;

public static class HeroPrivateCapture
{
    private static bool _initialized;

    private static FieldInfo _heroState;
    private static FieldInfo _transitionState;
    private static FieldInfo _jumpSteps;
    private static FieldInfo _jumpedSteps;
    private static FieldInfo _doubleJumpSteps;
    private static FieldInfo _dashTimer;
    private static FieldInfo _dashTime;
    private static FieldInfo _dashCooldownTimer;
    private static FieldInfo _airDashed;
    private static FieldInfo _doubleJumped;
    private static FieldInfo _didAirHang;
    private static FieldInfo _controlReqlinquished;
    private static FieldInfo _ledgeBufferSteps;
    private static FieldInfo _sprintBufferSteps;
    private static FieldInfo _jumpQueueSteps;
    private static FieldInfo _dashQueueSteps;
    private static FieldInfo _jumpReleaseQueueSteps;
    private static FieldInfo _landingBufferSteps;
    private static FieldInfo _headBumpSteps;
    private static FieldInfo _wallLockSteps;
    private static FieldInfo _wallUnstickSteps;
    private static FieldInfo _wallJumpChainStepsLeft;
    private static FieldInfo _fallTimer;
    private static FieldInfo _moveInput;
    private static FieldInfo _verticalInput;
    private static FieldInfo _currentWalljumpSpeed;
    private static FieldInfo _wallStickTimer;
    private static FieldInfo _shuttlecockSpeed;
    private static FieldInfo _shuttleCockJumpSteps;
    private static FieldInfo _recoilStepsLeft;
    private static FieldInfo _recoilVelocity;
    private static FieldInfo _recoilTimer;
    private static FieldInfo _wallJumpedL;
    private static FieldInfo _wallJumpedR;
    private static FieldInfo _wallSlidingL;
    private static FieldInfo _wallSlidingR;
    private static FieldInfo _touchingWallL;
    private static FieldInfo _touchingWallR;
    private static FieldInfo _wallLocked;
    private static FieldInfo _dashingDown;
    private static FieldInfo _acceptingInput;
    private static FieldInfo _jumpQueuing;
    private static FieldInfo _doubleJumpQueuing;
    private static FieldInfo _dashQueuing;
    private static FieldInfo _jumpReleaseQueuing;
    private static FieldInfo _canSoftLand;
    private static FieldInfo _fallCheckFlagged;
    private static FieldInfo _tryShove;
    private static FieldInfo _sprintFSM;
    private static FieldInfo _sprintSpeedAddFloat;
    private static FieldInfo _extraAirMoveVelocities;

    private static FieldInfo _davVelocity;
    private static FieldInfo _davDecay;
    private static FieldInfo _davCancelOnTurn;

    private static void Init()
    {
        var flags = BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public;
        var hc = typeof(HeroController);

        _heroState              = hc.GetField("hero_state", flags);
        _transitionState        = hc.GetField("transitionState", flags);
        _jumpSteps              = hc.GetField("jump_steps", flags);
        _jumpedSteps            = hc.GetField("jumped_steps", flags);
        _doubleJumpSteps        = hc.GetField("doubleJump_steps", flags);
        _dashTimer              = hc.GetField("dash_timer", flags);
        _dashTime               = hc.GetField("dash_time", flags);
        _dashCooldownTimer      = hc.GetField("dashCooldownTimer", flags);
        _airDashed              = hc.GetField("airDashed", flags);
        _doubleJumped           = hc.GetField("doubleJumped", flags);
        _didAirHang             = hc.GetField("didAirHang", flags);
        _controlReqlinquished   = hc.GetField("controlReqlinquished", flags);
        _ledgeBufferSteps       = hc.GetField("ledgeBufferSteps", flags);
        _sprintBufferSteps      = hc.GetField("sprintBufferSteps", flags);
        _jumpQueueSteps         = hc.GetField("jumpQueueSteps", flags);
        _dashQueueSteps         = hc.GetField("dashQueueSteps", flags);
        _jumpReleaseQueueSteps  = hc.GetField("jumpReleaseQueueSteps", flags);
        _landingBufferSteps     = hc.GetField("landingBufferSteps", flags);
        _headBumpSteps          = hc.GetField("headBumpSteps", flags);
        _wallLockSteps          = hc.GetField("wallLockSteps", flags);
        _wallUnstickSteps       = hc.GetField("wallUnstickSteps", flags);
        _wallJumpChainStepsLeft = hc.GetField("wallJumpChainStepsLeft", flags);
        _fallTimer              = hc.GetField("fallTimer", flags);
        _moveInput              = hc.GetField("move_input", flags);
        _verticalInput          = hc.GetField("vertical_input", flags);
        _currentWalljumpSpeed   = hc.GetField("currentWalljumpSpeed", flags);
        _wallStickTimer         = hc.GetField("wallStickTimer", flags);
        _shuttlecockSpeed       = hc.GetField("shuttlecockSpeed", flags);
        _shuttleCockJumpSteps   = hc.GetField("shuttleCockJumpSteps", flags);
        _recoilStepsLeft        = hc.GetField("recoilStepsLeft", flags);
        _recoilVelocity         = hc.GetField("recoilVelocity", flags);
        _recoilTimer            = hc.GetField("recoilTimer", flags);
        _wallJumpedL            = hc.GetField("wallJumpedL", flags);
        _wallJumpedR            = hc.GetField("wallJumpedR", flags);
        _wallSlidingL           = hc.GetField("wallSlidingL", flags);
        _wallSlidingR           = hc.GetField("wallSlidingR", flags);
        _touchingWallL          = hc.GetField("touchingWallL", flags);
        _touchingWallR          = hc.GetField("touchingWallR", flags);
        _wallLocked             = hc.GetField("wallLocked", flags);
        _dashingDown            = hc.GetField("dashingDown", flags);
        _acceptingInput         = hc.GetField("acceptingInput", flags);
        _jumpQueuing            = hc.GetField("jumpQueuing", flags);
        _doubleJumpQueuing      = hc.GetField("doubleJumpQueuing", flags);
        _dashQueuing            = hc.GetField("dashQueuing", flags);
        _jumpReleaseQueuing     = hc.GetField("jumpReleaseQueuing", flags);
        _canSoftLand            = hc.GetField("canSoftLand", flags);
        _fallCheckFlagged       = hc.GetField("fallCheckFlagged", flags);
        _tryShove               = hc.GetField("tryShove", flags);
        _sprintFSM              = hc.GetField("sprintFSM", flags);
        _sprintSpeedAddFloat    = hc.GetField("sprintSpeedAddFloat", flags);
        _extraAirMoveVelocities = hc.GetField("extraAirMoveVelocities", flags);

        if (_extraAirMoveVelocities != null)
        {
            var listType = _extraAirMoveVelocities.FieldType;
            var itemType = listType.IsGenericType ? listType.GetGenericArguments()[0] : null;
            if (itemType != null)
            {
                _davVelocity     = itemType.GetField("Velocity", flags);
                _davDecay        = itemType.GetField("Decay", flags);
                _davCancelOnTurn = itemType.GetField("CancelOnTurn", flags);
            }
        }

        _initialized = true;
    }

    private static uint Fnv1a(string s)
    {
        if (string.IsNullOrEmpty(s)) return 0u;
        uint h = 0x811C9DC5u;
        for (int i = 0; i < s.Length; i++) {
            h ^= s[i];
            h *= 0x01000193u;
        }
        return h;
    }

    private static int GetInt(FieldInfo fi, object target)
        => fi != null ? (int)fi.GetValue(target) : 0;

    private static float GetFloat(FieldInfo fi, object target)
        => fi != null ? (float)fi.GetValue(target) : 0f;

    private static bool GetBool(FieldInfo fi, object target)
        => fi != null && (bool)fi.GetValue(target);

    public static void Fill(ref HeroPrivate hp)
    {
        if (!_initialized) Init();

        hp = default;

        var hero = HeroController.instance;
        if (hero == null) return;

        var cs = hero.cState;
        uint cb = 0;
        if (cs != null)
        {
            if (cs.facingRight)         cb |= 1u << (int)CStateBit.FacingRight;
            if (cs.onGround)            cb |= 1u << (int)CStateBit.OnGround;
            if (cs.jumping)             cb |= 1u << (int)CStateBit.Jumping;
            if (cs.falling)             cb |= 1u << (int)CStateBit.Falling;
            if (cs.dashing)             cb |= 1u << (int)CStateBit.Dashing;
            if (cs.isSprinting)         cb |= 1u << (int)CStateBit.IsSprinting;
            if (cs.isBackSprinting)     cb |= 1u << (int)CStateBit.IsBackSprinting;
            if (cs.touchingWall)        cb |= 1u << (int)CStateBit.TouchingWall;
            if (cs.wallSliding)         cb |= 1u << (int)CStateBit.WallSliding;
            if (cs.wallClinging)        cb |= 1u << (int)CStateBit.WallClinging;
            if (cs.wallJumping)         cb |= 1u << (int)CStateBit.WallJumping;
            if (cs.doubleJumping)       cb |= 1u << (int)CStateBit.DoubleJumping;
            if (cs.wasOnGround)         cb |= 1u << (int)CStateBit.WasOnGround;
            if (cs.floating)            cb |= 1u << (int)CStateBit.Floating;
            if (cs.shuttleCock)         cb |= 1u << (int)CStateBit.ShuttleCock;
            if (cs.bouncing)            cb |= 1u << (int)CStateBit.Bouncing;
            if (cs.downSpiking)         cb |= 1u << (int)CStateBit.DownSpiking;
            if (cs.downSpikeBouncing)   cb |= 1u << (int)CStateBit.DownSpikeBouncing;
            if (cs.willHardLand)        cb |= 1u << (int)CStateBit.WillHardLand;
            if (cs.transitioning)       cb |= 1u << (int)CStateBit.Transitioning;
            if (cs.inWalkZone)          cb |= 1u << (int)CStateBit.InWalkZone;
            if (cs.onConveyor)          cb |= 1u << (int)CStateBit.OnConveyor;
            if (cs.recoiling)           cb |= 1u << (int)CStateBit.Recoiling;
            if (cs.isTouchingSlopeLeft) cb |= 1u << (int)CStateBit.TouchingSlopeL;
            if (cs.isTouchingSlopeRight) cb |= 1u << (int)CStateBit.TouchingSlopeR;
            if (cs.attacking)           cb |= 1u << (int)CStateBit.Attacking;
            if (cs.preventDash)         cb |= 1u << (int)CStateBit.PreventDash;
            if (cs.dashCooldown)        cb |= 1u << (int)CStateBit.DashCooldown;
            if (cs.inUpdraft)           cb |= 1u << (int)CStateBit.InUpdraft;
            if (cs.airDashing)          cb |= 1u << (int)CStateBit.AirDashing;
            if (cs.Invulnerable)        cb |= 1u << (int)CStateBit.Invulnerable;
            if (cs.shroomBouncing)      cb |= 1u << (int)CStateBit.ShroomBouncing;
        }
        hp.cStateBits = cb;

        hp.heroState              = GetInt(_heroState, hero);
        hp.transitionState        = GetInt(_transitionState, hero);
        hp.jumpSteps              = GetInt(_jumpSteps, hero);
        hp.jumpedSteps            = GetInt(_jumpedSteps, hero);
        hp.doubleJumpSteps        = GetInt(_doubleJumpSteps, hero);
        hp.dashTimer              = GetFloat(_dashTimer, hero);
        hp.dashTime               = GetFloat(_dashTime, hero);
        hp.dashCooldownTimer      = GetFloat(_dashCooldownTimer, hero);
        hp.airDashed              = GetBool(_airDashed, hero) ? (byte)1 : (byte)0;
        hp.doubleJumped           = GetBool(_doubleJumped, hero) ? (byte)1 : (byte)0;
        hp.didAirHang             = GetBool(_didAirHang, hero) ? (byte)1 : (byte)0;
        hp.controlReqlinquished   = GetBool(_controlReqlinquished, hero) ? (byte)1 : (byte)0;
        hp.ledgeBufferSteps       = GetInt(_ledgeBufferSteps, hero);
        hp.sprintBufferSteps      = GetInt(_sprintBufferSteps, hero);
        hp.jumpQueueSteps         = GetInt(_jumpQueueSteps, hero);
        hp.dashQueueSteps         = GetInt(_dashQueueSteps, hero);
        hp.jumpReleaseQueueSteps  = GetInt(_jumpReleaseQueueSteps, hero);
        hp.landingBufferSteps     = GetInt(_landingBufferSteps, hero);
        hp.headBumpSteps          = GetInt(_headBumpSteps, hero);
        hp.wallLockSteps          = GetInt(_wallLockSteps, hero);
        hp.wallUnstickSteps       = GetInt(_wallUnstickSteps, hero);
        hp.wallJumpChainStepsLeft = GetInt(_wallJumpChainStepsLeft, hero);
        hp.fallTimer              = GetFloat(_fallTimer, hero);
        hp.moveInput              = GetFloat(_moveInput, hero);
        hp.verticalInput          = GetFloat(_verticalInput, hero);
        hp.currentWalljumpSpeed   = GetFloat(_currentWalljumpSpeed, hero);
        hp.wallStickTimer         = GetFloat(_wallStickTimer, hero);
        hp.shuttlecockSpeed       = GetFloat(_shuttlecockSpeed, hero);
        hp.shuttleCockJumpSteps   = GetInt(_shuttleCockJumpSteps, hero);
        hp.recoilStepsLeft        = GetInt(_recoilStepsLeft, hero);
        hp.recoilVelocity         = GetFloat(_recoilVelocity, hero);
        hp.recoilTimer            = GetFloat(_recoilTimer, hero);

        var rb = hero.GetComponent<Rigidbody2D>();
        hp.gravityScale = rb != null ? rb.gravityScale : 1.0f;

        uint eb = 0;
        if (GetBool(_wallJumpedL, hero))        eb |= 1u << (int)ExtraBit.WallJumpedL;
        if (GetBool(_wallJumpedR, hero))        eb |= 1u << (int)ExtraBit.WallJumpedR;
        if (GetBool(_wallSlidingL, hero))       eb |= 1u << (int)ExtraBit.WallSlidingL;
        if (GetBool(_wallSlidingR, hero))       eb |= 1u << (int)ExtraBit.WallSlidingR;
        if (GetBool(_touchingWallL, hero))      eb |= 1u << (int)ExtraBit.TouchingWallL;
        if (GetBool(_touchingWallR, hero))      eb |= 1u << (int)ExtraBit.TouchingWallR;
        if (GetBool(_wallLocked, hero))         eb |= 1u << (int)ExtraBit.WallLocked;
        if (GetBool(_dashingDown, hero))        eb |= 1u << (int)ExtraBit.DashingDown;
        if (GetBool(_acceptingInput, hero))     eb |= 1u << (int)ExtraBit.AcceptingInput;
        if (GetBool(_jumpQueuing, hero))        eb |= 1u << (int)ExtraBit.JumpQueuing;
        if (GetBool(_doubleJumpQueuing, hero))  eb |= 1u << (int)ExtraBit.DoubleJumpQueuing;
        if (GetBool(_dashQueuing, hero))        eb |= 1u << (int)ExtraBit.DashQueuing;
        if (GetBool(_jumpReleaseQueuing, hero)) eb |= 1u << (int)ExtraBit.JumpReleaseQueuing;
        if (GetBool(_canSoftLand, hero))        eb |= 1u << (int)ExtraBit.CanSoftLand;
        if (GetBool(_fallCheckFlagged, hero))   eb |= 1u << (int)ExtraBit.FallCheckFlagged;
        if (GetBool(_tryShove, hero))           eb |= 1u << (int)ExtraBit.TryShove;
        hp.extraBits = eb;

        if (_sprintFSM != null)
        {
            var fsm = _sprintFSM.GetValue(hero) as PlayMakerFSM;
            if (fsm != null && fsm.ActiveStateName != null)
                hp.sprintFsmStateHash = Fnv1a(fsm.ActiveStateName);
        }
        if (_sprintSpeedAddFloat != null)
        {
            var f = _sprintSpeedAddFloat.GetValue(hero) as FsmFloat;
            if (f != null) hp.sprintAddSpeed = f.Value;
        }

        if (_extraAirMoveVelocities != null && _davVelocity != null)
        {
            var list = _extraAirMoveVelocities.GetValue(hero) as IList;
            if (list != null)
            {
                int n = list.Count;
                hp.extraAirMoveCount = n;
                int cap = n > 4 ? 4 : n;
                for (int i = 0; i < cap; i++)
                {
                    var entry = list[i];
                    var v = (Vector2)_davVelocity.GetValue(entry);
                    float decay = _davDecay != null ? (float)_davDecay.GetValue(entry) : 0f;
                    uint flags = 0u;
                    if (_davCancelOnTurn != null && (bool)_davCancelOnTurn.GetValue(entry))
                        flags |= 1u;
                    switch (i)
                    {
                        case 0: hp.ext0Vx = v.x; hp.ext0Vy = v.y; hp.ext0Decay = decay; hp.ext0Flags = flags; break;
                        case 1: hp.ext1Vx = v.x; hp.ext1Vy = v.y; hp.ext1Decay = decay; hp.ext1Flags = flags; break;
                        case 2: hp.ext2Vx = v.x; hp.ext2Vy = v.y; hp.ext2Decay = decay; hp.ext2Flags = flags; break;
                        case 3: hp.ext3Vx = v.x; hp.ext3Vy = v.y; hp.ext3Decay = decay; hp.ext3Flags = flags; break;
                    }
                }
            }
        }
    }
}
