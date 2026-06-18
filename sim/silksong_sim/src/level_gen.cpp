#include "level_gen.hpp"
#include "fsm_interpreter.hpp"

namespace silksong {

void createPersistentEntities(Engine &ctx)
{
    for (madrona::CountT i = 0; i < consts::numAgents; ++i) {
        ctx.data().agents[i] = ctx.makeEntity<Agent>();
        ctx.get<Action>(ctx.data().agents[i]) = Action{};
    }
}

void resetEpisodeState(Engine &ctx)
{
    const HeroInit &init = ctx.singleton<HeroInit>();
    const float initPosX = init.useCustom ? init.posX : consts::heroSpawnX;
    const float initPosY = init.useCustom ? init.posY : consts::heroSpawnY;

    // Per-scene ceiling override
    Arena &arena = ctx.singleton<Arena>();
    arena.ceilingY = (init.useCustom && init.ceilingY > 0.f)
        ? init.ceilingY
        : consts::ceilingY;
    if (init.useCustom && init.ceilingMaxX > init.ceilingMinX) {
        arena.ceilingMinX = init.ceilingMinX;
        arena.ceilingMaxX = init.ceilingMaxX;
    } else {
        arena.ceilingMinX = -1e9f;
        arena.ceilingMaxX = +1e9f;
    }

    ActiveProjectiles &proj = ctx.singleton<ActiveProjectiles>();
    proj.activeMask = 0;
    for (int i = 0; i < ActiveProjectiles::MAX; ++i) proj.ttl[i] = 0;

    // Reset GlobalFreeze
    ctx.singleton<GlobalFreeze>() = GlobalFreeze{0.f};

    const HeroConfig &cfg = ctx.singleton<HeroConfigSingleton>().config;

    for (madrona::CountT i = 0; i < consts::numAgents; ++i) {
        madrona::Entity e = ctx.data().agents[i];

        // Initialize HeroState using heroStateInit from hero.hpp
        HeroState &hero = ctx.get<HeroState>(e);
        heroStateInit(hero, cfg, initPosX, initPosY);

        ctx.get<PlayerObs>(e) = PlayerObs{
            .posX = initPosX,
            .posY = initPosY,
            .velX = 0.f,
            .velY = 0.f,
            .health = (float)consts::playerMaxHealth,
            .maxHealth = (float)consts::playerMaxHealth,
            .silk = (float)consts::playerMaxSilk,
            .grounded = 0.f,
            .canDash = 1.f,
            .facingRight = 1.f,
            .invincible = 0.f,
            .canAttack = 1.f,
            .animState = 0.f,
            .animProgress = 0.f,
        };
        ctx.get<BossObs>(e) = BossObs{
            .posX = consts::bossSpawnX,
            .posY = consts::bossSpawnY,
            .velX = 0.f,
            .velY = 0.f,
            .health = (float)consts::bossMaxHealth,
            .maxHealth = (float)consts::bossMaxHealth,
            .phase = 1.f,
            .facingRight = 1.f,
            .animState = 0.f,
            .animProgress = 0.f,
        };

        ctx.get<BossKinematics>(e) = BossKinematics{
            .posX = consts::bossSpawnX,
            .posY = consts::bossSpawnY,
            .velX = 0.f,
            .velY = 0.f,
        };

        // Initialize FsmRuntime from baked data
        FsmRuntime &fsm = ctx.get<FsmRuntime>(e);
        const FsmDef &def = ctx.singleton<FsmDefSingleton>().def;
        fsmInit(def, fsm,
                def.initFloatVars,
                def.initIntVars,
                def.initBoolVars);

        // Initialize StunControl
        ctx.get<StunControl>(e) = StunControl{
            .comboCounter = 0.f,
            .comboTime = 0.f,
            .hitsTotal = 0.f,
            .stunCombo = consts::bossStunCombo,
            .stunHitMax = consts::bossStunHitMax,
            .recoilSpeed = 15,
            .recoilBlocked = false,
            .isInvincible = false,
            .specialDeath = false,
            .invincTimer = 0,
            .hitFreezeRem = 0,
            .recoilRem = 0,
            .damageAmount = 1,
        };

        RaycastDistances &rd = ctx.get<RaycastDistances>(e);
        RaycastHitTypes &rh = ctx.get<RaycastHitTypes>(e);
        for (madrona::CountT r = 0; r < consts::numRays; ++r) {
            rd.v[r] = 1.f;
            rh.v[r] = 0;
        }

        ctx.get<EpisodeState>(e) = EpisodeState{
            .episodeTime = 0.f,
            .stepsTaken = 0,
            .stepsRemaining = consts::episodeLen,
        };
        ctx.get<Reward>(e) = Reward{};
        ctx.get<Done>(e) = Done{};
    }
}

}
