#pragma once

// Hero configuration extracted from game assets.
//
// Source: Hero_Hornet.prefab in heroloading_assets_all.bundle
//   - CAPS constants: HeroController MonoBehaviour (path_id=8558487498826258638)
//     extracted via UnityPy typetree deserialization. All values verified.
//   - Config fields (attackDuration, etc.): HeroControllerConfig ScriptableObject
//     referenced via m_FileID=45, m_PathID=8141267232388582512 (configs[0]).
//     This ScriptableObject lives in an external CAB that could not be resolved
//     from any accessible bundle. Fields marked TODO are best-effort defaults
//     derived from code analysis of HeroController.cs.
//   - HeroControllerConfigWarrior adds rage-mode overrides for attack timing.
//
// Game version: Unity 6000.0.50f1 (Hollow Knight: Silksong)
// Extraction date: 2026-04-30

namespace silksong {

struct HeroConfig {
    // ================================================================
    // Ability toggles (from HeroControllerConfig ScriptableObject)
    // These are per-crest config; defaults below are for configs[0]
    // (no crest / base loadout).
    // ================================================================
    bool canDoubleJump     = true;
    bool canBind           = false;
    bool canBrolly         = false;
    bool canHarpoonDash    = false;
    bool canNailCharge     = false;
    bool canPlayNeedolin   = false;

    // Warrior rage mode (HeroControllerConfigWarrior overrides attack timing)
    bool isWarriorRage     = false;

    // ================================================================
    // Attack timing (from HeroControllerConfig ScriptableObject)
    //
    // TODO: These values could not be programmatically extracted.
    // The ScriptableObject is in an external CAB (CAB-7532a93d...)
    // that is not present in any accessible Addressables bundle.
    //
    // Defaults below are derived from code analysis:
    //   - attackDuration: sets how long the slash animation/hitbox lasts.
    //     From code: `attackDuration = Config.AttackDuration` (line 4094).
    //     Quickening multiplier: `attackDuration *= 1/QuickAttackSpeedMult`.
    //     The sim currently uses 7 frames total (windup+active+recovery)
    //     = 0.14s. A reasonable default for the raw duration is ~0.35s
    //     (matching Hollow Knight 1's slash duration).
    //   - attackCooldownTime: minimum time between attacks.
    //     From code: `attack_cooldown = Config.AttackCooldownTime` (line 4308)
    //     then clamped: `if (attack_cooldown < num) attack_cooldown = num;`
    //     where num = AttackDuration. Hardcoded overrides in HeroController:
    //     0.1 (dashStabBounce short), 0.15 (various bounces), 0.2 (chargeSlash
    //     type2), 0.35 (chargeSlash type1). Default is likely >= attackDuration.
    //   - quickAttackCooldownTime: used when Quickening is active.
    //   - attackRecoveryTime: how long after attack start before other
    //     actions (dash, jump, etc.) are allowed. Many guards check
    //     `attack_time < Config.AttackRecoveryTime`.
    //   - quickAttackSpeedMult: multiplier for attack animation speed.
    //     From code: `attackDuration *= 1f / Config.QuickAttackSpeedMult`.
    // ================================================================

    float attackDuration         = 0.35f;  // TODO: extract from game assets
    float attackCooldownTime     = 0.35f;  // TODO: extract (>= attackDuration)
    float quickAttackCooldownTime = 0.25f; // TODO: extract (quickening variant)
    float attackRecoveryTime     = 0.20f;  // TODO: extract (action unlock time)
    float quickAttackSpeedMult   = 1.5f;   // TODO: extract (quickening speed multiplier)

    // Warrior rage mode attack overrides (HeroControllerConfigWarrior)
    float rageAttackDuration          = 0.25f;  // TODO: extract
    float rageAttackRecoveryTime      = 0.15f;  // TODO: extract
    float rageAttackCooldownTime      = 0.25f;  // TODO: extract
    float rageQuickAttackCooldownTime = 0.20f;  // TODO: extract

    // ================================================================
    // Down slash / downspike config (from HeroControllerConfig)
    // ================================================================
    //   DownSlashType enum: 0=DownSpike, 1=Slash, 2=Custom
    int   downSlashType          = 0;      // TODO: extract (DownSpike for base config)
    float downspikeAnticTime     = 0.15f;  // TODO: extract
    float downspikeTime          = 0.25f;  // TODO: extract
    float downspikeSpeed         = 45.0f;  // TODO: extract
    float downspikeRecoveryTime  = 0.2f;   // TODO: extract
    bool  downspikeBurstEffect   = true;   // default in source
    bool  downspikeThrusts       = true;   // default in source

    // ================================================================
    // Dash stab config (from HeroControllerConfig)
    // ================================================================
    float dashStabSpeed              = 28.0f;  // TODO: extract (likely ~DASH_SPEED)
    float dashStabTime               = 0.1f;   // TODO: extract
    bool  forceShortDashStabBounce   = false;  // TODO: extract
    float dashStabBounceJumpSpeed    = 12.0f;  // TODO: extract (likely ~BOUNCE_VELOCITY)
    int   dashStabSteps              = 1;      // default in source

    // ================================================================
    // Charge slash config (from HeroControllerConfig)
    // ================================================================
    bool  canTurnWhileSlashing           = false;  // TODO: extract
    bool  chargeSlashRecoils             = false;  // TODO: extract
    float chargeSlashLungeSpeed          = 25.0f;  // TODO: extract
    float chargeSlashLungeDeceleration   = 1.0f;   // default in source
    int   chargeSlashChain               = 0;      // TODO: extract
    bool  wallSlashSlowdown              = false;  // TODO: extract

    // ================================================================
    // Movement constants (from HeroController MonoBehaviour)
    // ALL VALUES BELOW ARE GROUND TRUTH — extracted directly from game.
    // ================================================================
    float RUN_SPEED                     = 8.25f;
    float WALK_SPEED                    = 5.0f;
    float JUMP_SPEED                    = 18.6f;
    float MIN_JUMP_SPEED                = 3.0f;
    int   JUMP_STEPS                    = 8;
    int   JUMP_STEPS_MIN                = 2;
    float AIR_HANG_GRAVITY              = 0.1f;
    float AIR_HANG_ACCEL                = 5.0f;
    float SHUTTLECOCK_SPEED             = 18.0f;
    float FLOAT_SPEED                   = -3.0f;
    int   DOUBLE_JUMP_RISE_STEPS        = 4;
    int   DOUBLE_JUMP_FALL_STEPS        = 4;

    // Jump / wall jump geometry
    float JUMP_ABILITY_GROUND_RAY_LENGTH = 1.0f;
    float WALLJUMP_RAY_LENGTH            = 0.6f;
    float WALLJUMP_BROLLY_RAY_LENGTH     = 1.0f;
    int   WJLOCK_STEPS_SHORT             = 5;
    int   WJLOCK_STEPS_LONG              = 15;
    int   WJLOCK_CHAIN_STEPS             = 10;
    float WJ_KICKOFF_SPEED               = 25.0f;
    int   WALL_STICKY_STEPS              = 3;

    // Dash
    float DASH_SPEED                    = 28.0f;
    float DASH_TIME                     = 0.1f;
    float AIR_DASH_TIME                 = 0.02f;
    float DOWN_DASH_TIME                = 0.25f;
    int   DASH_QUEUE_STEPS              = 10;
    float DASH_COOLDOWN                 = 0.425f;

    // Wall sliding
    float WALLSLIDE_STICK_TIME          = 0.15f;
    float WALLSLIDE_ACCEL               = -24.0f;
    float WALLSLIDE_SHUTTLECOCK_VEL     = 12.0f;
    float WALLCLING_DECEL               = 80.0f;
    float WALLCLING_COOLDOWN            = 0.3f;
    float WALLSLIDE_CLIP_DELAY          = 0.1f;

    // Nail charge
    float NAIL_CHARGE_TIME              = 1.35f;
    float NAIL_CHARGE_TIME_QUICK        = 0.8f;
    float NAIL_CHARGE_BEGIN_TIME        = 0.3f;
    float NAIL_CHARGE_BEGIN_TIME_QUICK  = 0.225f;

    // Gravity / falling
    float DEFAULT_GRAVITY               = 1.0f;     // gravity scale
    float UNDERWATER_GRAVITY            = 0.225f;
    float MAX_FALL_VELOCITY             = 30.0f;
    float MAX_FALL_VELOCITY_WEIGHTED    = 38.0f;
    float MAX_FALL_VELOCITY_DJUMP       = 10.0f;

    // Scene entry (not relevant for sim, included for completeness)
    float TIME_TO_ENTER_SCENE_BOT       = 0.1f;
    float SPEED_TO_ENTER_SCENE_HOR      = 8.0f;
    float SPEED_TO_ENTER_SCENE_UP       = 9.4f;
    float SPEED_TO_ENTER_SCENE_DOWN     = -12.0f;

    // Alt attack
    float ALT_ATTACK_RESET              = 0.5f;

    // Downspike rebound / invulnerability
    int   DOWNSPIKE_REBOUND_STEPS       = 6;
    float DOWNSPIKE_REBOUND_SPEED       = 20.0f;
    float DOWNSPIKE_LAND_RECOVERY_TIME  = 0.1667f;  // ~1/6 second
    float DOWNSPIKE_ANTIC_DECELERATION  = 0.8f;
    float DOWNSPIKE_ANTIC_CLAMP_VEL_Y_MIN = -12.0f;
    float DOWNSPIKE_ANTIC_CLAMP_VEL_Y_MAX =  12.0f;
    float JUMP_SPEED_UPDRAFT_EXIT       = 20.0f;
    int   DOWNSPIKE_INVULNERABILITY_STEPS      = 8;
    int   DOWNSPIKE_INVULNERABILITY_STEPS_LONG = 16;

    // Bounce
    float BOUNCE_TIME                   = 0.25f;
    float BOUNCE_VELOCITY               = 12.0f;
    float SHROOM_BOUNCE_VELOCITY        = 25.0f;

    // Recoil (hero hit knockback)
    float RECOIL_HOR_VELOCITY           = 3.75f;
    float RECOIL_HOR_VELOCITY_LONG      = 16.0f;
    float RECOIL_HOR_VELOCITY_DRILLDASH = 10.0f;
    int   RECOIL_HOR_STEPS              = 8;
    float RECOIL_DOWN_VELOCITY           = 0.0f;
    float RECOIL_DURATION               = 0.2f;
    float RECOIL_VELOCITY               = 15.0f;
    float CAST_RECOIL_VELOCITY          = 10.0f;

    // Fall / landing
    float BIG_FALL_TIME                 = 0.5f;
    float HARD_LANDING_TIME             = 0.67f;
    float DOWN_DASH_RECOVER_TIME        = 0.115f;

    // Damage freeze
    float DAMAGE_FREEZE_DOWN            = 0.0f;
    float DAMAGE_FREEZE_WAIT            = 0.1f;
    float DAMAGE_FREEZE_UP              = 0.1f;
    float DAMAGE_FREEZE_SPEED           = 0.0f;

    // Invulnerability
    float INVUL_TIME                    = 1.0f;
    float INVUL_TIME_PARRY              = 0.15f;
    float INVUL_TIME_QUAKE              = 0.4f;
    float INVUL_TIME_CROSS_STITCH       = 0.35f;
    float INVUL_TIME_SILKDASH           = 0.5f;

    // Combat windows
    float REVENGE_WINDOW_TIME           = 0.15f;
    float DASHCOMBO_WINDOW_TIME         = 0.15f;

    // Quickening (speed buff)
    float QUICKENING_DURATION           = 10.0f;
    float QUICKENING_RUN_SPEED          = 11.5f;
    float QUICKENING_WALK_SPEED         = 7.0f;

    // Silk regen
    float FIRST_SILK_REGEN_DELAY        = 0.65f;
    float FIRST_SILK_REGEN_DURATION     = 0.8f;
    float SILK_REGEN_DELAY              = 2.0f;
    float SILK_REGEN_DURATION           = 1.9f;

    // Cursed/maggoted silk eating
    float CURSED_SILK_EAT_DELAY_FIRST   = 2.0f;
    float CURSED_SILK_EAT_DELAY         = 0.4f;
    float CURSED_SILK_EAT_DURATION      = 1.0833f;
    float MAGGOTED_SILK_EAT_DELAY_FIRST = 0.0f;
    float MAGGOTED_SILK_EAT_DELAY       = 0.0f;
    float MAGGOTED_SILK_EAT_DURATION    = 7.0f;

    // ================================================================
    // Queue step limits (from HeroController MonoBehaviour)
    // ================================================================
    int   JUMP_QUEUE_STEPS              = 2;
    int   JUMP_RELEASE_QUEUE_STEPS      = 2;
    int   DOUBLE_JUMP_QUEUE_STEPS       = 10;
    int   ATTACK_QUEUE_STEPS            = 8;
    int   LEDGE_BUFFER_STEPS            = 4;

    // Player data booleans assumed true for boss fight
    bool hasDash        = true;
    bool hasDoubleJump  = true;
    bool hasWalljump    = true;

    // ================================================================
    // Helper: get effective attack duration (accounts for rage mode)
    // ================================================================
    float getAttackDuration() const {
        return isWarriorRage ? rageAttackDuration : attackDuration;
    }

    float getAttackCooldownTime(bool quickening) const {
        if (isWarriorRage)
            return quickening ? rageQuickAttackCooldownTime : rageAttackCooldownTime;
        return quickening ? quickAttackCooldownTime : attackCooldownTime;
    }

    float getAttackRecoveryTime() const {
        return isWarriorRage ? rageAttackRecoveryTime : attackRecoveryTime;
    }
};

// Default config for the Lace Boss 1 encounter (no crest equipped, configs[0]).
// canDoubleJump = true because the player has double jump by this point.
// Other abilities depend on crest — base loadout has none.
inline constexpr HeroConfig HERO_CONFIG_DEFAULT = {};

} // namespace silksong
