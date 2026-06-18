#include <madrona/mw_gpu_entry.hpp>

#include "sim.hpp"
#include "level_gen.hpp"
#include "fsm_actions.hpp"
#include "fsm_interpreter.hpp"

using namespace madrona;
using namespace madrona::math;

namespace silksong {

void Sim::registerTypes(ECSRegistry &registry, const Config &)
{
    base::registerTypes(registry);

    registry.registerComponent<Action>();
    registry.registerComponent<HeroState>();
    registry.registerComponent<PlayerObs>();
    registry.registerComponent<BossObs>();
    registry.registerComponent<RaycastDistances>();
    registry.registerComponent<RaycastHitTypes>();
    registry.registerComponent<EpisodeState>();
    registry.registerComponent<Reward>();
    registry.registerComponent<Done>();
    registry.registerComponent<BossKinematics>();
    registry.registerComponent<FsmRuntime>();
    registry.registerComponent<StunControl>();

    registry.registerSingleton<WorldReset>();
    registry.registerSingleton<HeroInit>();
    registry.registerSingleton<Arena>();
    registry.registerSingleton<ActiveProjectiles>();
    registry.registerSingleton<GlobalFreeze>();
    registry.registerSingleton<FsmDefSingleton>();
    registry.registerSingleton<HeroConfigSingleton>();

    registry.registerArchetype<Agent>();

    registry.exportSingleton<WorldReset>((uint32_t)ExportID::Reset);
    registry.exportSingleton<HeroInit>((uint32_t)ExportID::HeroInit);
    registry.exportColumn<Agent, Action>((uint32_t)ExportID::Action);
    registry.exportColumn<Agent, PlayerObs>((uint32_t)ExportID::PlayerObs);
    registry.exportColumn<Agent, BossObs>((uint32_t)ExportID::BossObs);
    registry.exportColumn<Agent, RaycastDistances>(
        (uint32_t)ExportID::RaycastDistances);
    registry.exportColumn<Agent, RaycastHitTypes>(
        (uint32_t)ExportID::RaycastHitTypes);
    registry.exportColumn<Agent, EpisodeState>(
        (uint32_t)ExportID::EpisodeState);
    registry.exportColumn<Agent, Reward>((uint32_t)ExportID::Reward);
    registry.exportColumn<Agent, Done>((uint32_t)ExportID::Done);
}

static inline void setTileSolid(Arena &a, int tx, int ty)
{
    if (tx < 0 || tx >= Arena::W || ty < 0 || ty >= Arena::H) return;
    a.solid[ty][tx >> 5] |= (1u << (tx & 31));
}

static void bakeBoneEast12Arena(Arena &a)
{
    a.originX = consts::arenaMinX;
    a.originY = consts::arenaMinY;
    a.ceilingY = consts::ceilingY;
    a.ceilingMinX = -1e9f;
    a.ceilingMaxX = +1e9f;

    for (int y = 0; y < Arena::H; ++y) {
        for (int i = 0; i < Arena::W / 32; ++i) {
            a.solid[y][i] = 0u;
        }
    }

    const int floorRow = (int)(5.8f - a.originY);
    const int leftCol  = (int)(82.0f - a.originX);
    const int rightCol = (int)(106.0f - a.originX);
    const int topRow   = (int)(28.0f - a.originY);

    for (int x = leftCol; x <= rightCol; ++x) {
        for (int y = floorRow - 1; y <= floorRow; ++y) {
            setTileSolid(a, x, y);
        }
    }

    for (int x = 0; x < Arena::W; ++x) {
        for (int y = 0; y < floorRow - 1; ++y) {
            setTileSolid(a, x, y);
        }
    }

    for (int y = floorRow; y <= topRow; ++y) {
        setTileSolid(a, leftCol - 1, y);
        setTileSolid(a, leftCol - 2, y);
    }

    for (int y = floorRow; y <= topRow; ++y) {
        setTileSolid(a, rightCol + 1, y);
        setTileSolid(a, rightCol + 2, y);
    }

    for (int x = leftCol - 2; x <= rightCol + 2; ++x) {
        setTileSolid(a, x, topRow);
        setTileSolid(a, x, topRow + 1);
    }
}

static inline bool isTileSolid(const Arena &a, float worldX, float worldY)
{
    const int tx = (int)(worldX - a.originX);
    const int ty = (int)(worldY - a.originY);
    if (tx < 0 || tx >= Arena::W || ty < 0 || ty >= Arena::H) return true;
    return ((a.solid[ty][tx >> 5] >> (tx & 31)) & 1u) != 0u;
}

// combat.hpp and raycast.hpp are included inside the namespace block
// since they don't have their own namespace wrappers (they use static inline).
#include "combat.hpp"
#include "raycast.hpp"

static inline void initWorld(Engine &ctx)
{
    ctx.data().rng = RNG(rand::split_i(
        ctx.data().initRandKey,
        ctx.data().curWorldEpisode++,
        (uint32_t)ctx.worldID().idx));

    resetEpisodeState(ctx);
}

inline void resetSystem(Engine &ctx, WorldReset &reset)
{
    int32_t shouldReset = reset.reset;

    if (ctx.data().autoReset) {
        for (CountT i = 0; i < consts::numAgents; ++i) {
            Entity agent = ctx.data().agents[i];
            if (ctx.get<Done>(agent).v) {
                shouldReset = 1;
            }
        }
    }

    if (shouldReset) {
        reset.reset = 0;
        initWorld(ctx);
    }
}

static inline uint16_t packActionBits(const Action &a)
{
    return static_cast<uint16_t>(
        ((a.left     != 0) << AB_Left)    |
        ((a.right    != 0) << AB_Right)   |
        ((a.up       != 0) << AB_Up)      |
        ((a.down     != 0) << AB_Down)    |
        ((a.jump     != 0) << AB_Jump)    |
        ((a.attack   != 0) << AB_Attack)  |
        ((a.dash     != 0) << AB_Dash)    |
        ((a.clawline != 0) << AB_Clawline)|
        ((a.skill    != 0) << AB_Skill)   |
        ((a.heal     != 0) << AB_Heal));
}

// sweep collision for hero  , uses HeroState pos/vel
static inline void sweepAxisX(const Arena &arena, HeroState &p,
                              float dx, float halfW, float halfH)
{
    float newX = p.posX + dx;
    const float leadX = dx >= 0.f ? newX + halfW : newX - halfW;
    constexpr float probeInset = 0.0312f;
    const bool hit =
        isTileSolid(arena, leadX, p.posY - halfH + probeInset) ||
        isTileSolid(arena, leadX, p.posY) ||
        isTileSolid(arena, leadX, p.posY + halfH - probeInset);

    const float tileLead = dx >= 0.f ? floorf(leadX) : ceilf(leadX);
    const float snapX    = dx >= 0.f ? tileLead - halfW - 1e-4f
                                     : tileLead + halfW + 1e-4f;
    p.posX = hit ? snapX : newX;
    p.velX = hit ? 0.f   : p.velX;

    //we detect wall touching for wall slide
    if (hit) {
        if (dx < 0.f) p.touchingWallL = true;
        if (dx > 0.f) p.touchingWallR = true;
        p.states.touchingWall = true;
    }
}

static inline void sweepAxisY(const Arena &arena, HeroState &p,
                              float dy, float halfW, float halfH,
                              bool &outGrounded)
{
    float newY = p.posY + dy;
    const float leadY = dy >= 0.f ? newY + halfH : newY - halfH;
    constexpr float probeInset = 0.0312f;
    const bool hit =
        isTileSolid(arena, p.posX - halfW + probeInset, leadY) ||
        isTileSolid(arena, p.posX,                      leadY) ||
        isTileSolid(arena, p.posX + halfW - probeInset, leadY);

    const float tileLead = dy >= 0.f ? floorf(leadY) : ceilf(leadY);
    const float snapY    = dy >= 0.f ? tileLead - halfH - 1e-4f
                                     : tileLead + halfH + 1e-4f;
    p.posY = hit ? snapY : newY;
    p.velY = hit ? 0.f   : p.velY;

    // Head bump
    if (hit && dy > 0.f) {
        p.headBumpSteps = 2;
    }

    // Sub-tile ceiling clamp
    const bool inCeilingX =
        p.posX >= arena.ceilingMinX && p.posX <= arena.ceilingMaxX;
    const bool ceilingHit =
        dy > 0.f && arena.ceilingY > 0.f && inCeilingX
        && p.posY + halfH > arena.ceilingY;
    if (ceilingHit) {
        p.posY = arena.ceilingY - halfH;
        p.velY = 0.f;
    }

    outGrounded = outGrounded || (hit && dy < 0.f);
}

inline void heroStepSystem(Engine &ctx,
                           const Action &a,
                           HeroState &hero,
                           PlayerObs &obs)
{
    GlobalFreeze &gf = ctx.singleton<GlobalFreeze>();

    // Global freeze: skip all hero logic
    if (gf.timer > 0.f) {
        obs.posX = hero.posX;
        obs.posY = hero.posY;
        obs.velX = 0.f;
        obs.velY = 0.f;
        obs.invincible = hero.states.Invulnerable() ? 1.f : 0.f;
        return;
    }

    // Damage freeze/recoil phase: hero is frozen during recoilFrozen
    if (hero.states.recoilFrozen && hero.damageFreezeTimer > 0.f) {
        // Still in freeze phase, no movement
        obs.posX = hero.posX;
        obs.posY = hero.posY;
        obs.velX = 0.f;
        obs.velY = 0.f;
        obs.invincible = hero.states.Invulnerable() ? 1.f : 0.f;
        return;
    }

    const Arena &arena = ctx.singleton<Arena>();
    constexpr float halfW = consts::heroHalfWidth;
    constexpr float halfH = consts::heroHalfHeight;
    constexpr float dt = consts::deltaT;
    const HeroConfig &cfg = ctx.singleton<HeroConfigSingleton>().config;

    const uint16_t newBits = packActionBits(a);
    const uint16_t prevBits = hero.prevActionBits;

    // Decode action bits
    bool inputLeft    = (newBits >> AB_Left) & 1u;
    bool inputRight   = (newBits >> AB_Right) & 1u;
    bool inputUp      = (newBits >> AB_Up) & 1u;
    bool inputDown    = (newBits >> AB_Down) & 1u;
    bool jumpPressed  = (newBits & (1u << AB_Jump)) && !(prevBits & (1u << AB_Jump));
    bool jumpHeld     = (newBits >> AB_Jump) & 1u;
    bool attackPressed = (newBits & (1u << AB_Attack)) && !(prevBits & (1u << AB_Attack));
    bool dashPressed  = (newBits & (1u << AB_Dash)) && !(prevBits & (1u << AB_Dash));

    // Reset wall contact flags each frame (will be re-set by sweep)
    hero.touchingWallL = false;
    hero.touchingWallR = false;
    hero.states.touchingWall = false;

    // Run hero tick (input + physics + timers)
    heroTick(hero, cfg,
             inputLeft, inputRight, inputUp, inputDown,
             jumpPressed, jumpHeld, attackPressed, dashPressed,
             prevBits, newBits, dt, gf.timer);

    // Gravity integration (hero.hpp sets velocities, we do tile collision)
    if (hero.gravityApplies && !hero.states.dashing) {
        hero.velY += -60.0f * hero.gravityScale * dt;  // gravity = -60 base
    }

    // Terminal velocity
    if (hero.velY < -cfg.MAX_FALL_VELOCITY) {
        hero.velY = -cfg.MAX_FALL_VELOCITY;
    }

    // Wall slide max fall speed
    if (hero.states.wallSliding && hero.velY < -8.0f) {
        hero.velY = -8.0f;
    }

    // Sweep integration (tile collision)
    bool grounded = false;
    sweepAxisX(arena, hero, hero.velX * dt, halfW, halfH);
    sweepAxisY(arena, hero, hero.velY * dt, halfW, halfH, grounded);

    // Ground detection: additional probe
    if (!grounded && hero.velY <= 0.f) {
        grounded = isTileSolid(arena, hero.posX, hero.posY - halfH - 1e-3f);
    }

    // Update ground state
    bool wasOnGround = hero.states.onGround;
    if (grounded && !wasOnGround) {
        BackOnGround(hero, cfg);
    }
    if (!grounded && wasOnGround) {
        hero.states.onGround = false;
        hero.ledgeBufferSteps = cfg.LEDGE_BUFFER_STEPS;
    }
    hero.states.onGround = grounded;

    // Populate PlayerObs
    obs.posX        = hero.posX;
    obs.posY        = hero.posY;
    obs.velX        = hero.velX;
    obs.velY        = hero.velY;
    obs.health      = (float)hero.health;
    obs.maxHealth   = (float)hero.maxHealth;
    obs.silk        = (float)hero.silk;
    obs.grounded    = grounded ? 1.f : 0.f;
    obs.facingRight = hero.states.facingRight ? 1.f : 0.f;
    obs.canDash     = CanDash(hero, cfg) ? 1.f : 0.f;
    obs.canAttack   = CanAttack(hero, cfg) ? 1.f : 0.f;
    obs.invincible  = hero.states.Invulnerable() ? 1.f : 0.f;
    obs.animState   = (float)hero.hero_state;
    obs.animProgress = 0.f;
}

static inline void bossIntegrate(BossKinematics &bk, const StunControl &sc,
                                  bool isKinematic, float gravityScale,
                                  float dt)
{
    if (isKinematic) return;

    bk.velY += -60.0f * gravityScale * dt;
    bk.posX += bk.velX * dt;
    bk.posY += bk.velY * dt;

    // Floor clamp
    const float floorY = consts::bossLandY + consts::bossBodyHalfH;
    if (bk.posY < floorY) {
        bk.posY = floorY;
        bk.velY = 0.f;
    }
    // Ceiling clamp
    const float ceilY = consts::arenaMaxY - consts::bossBodyHalfH;
    if (bk.posY > ceilY) {
        bk.posY = ceilY;
        bk.velY = 0.f;
    }
    // X constraints
    if (bk.posX < consts::bossConstraintXMin) {
        bk.posX = consts::bossConstraintXMin;
        bk.velX = 0.f;
    }
    if (bk.posX > consts::bossConstraintXMax) {
        bk.posX = consts::bossConstraintXMax;
        bk.velX = 0.f;
    }
}

// bossStepSystem: check GlobalFreeze, call fsmTick, integrate, populate obs
inline void bossStepSystem(Engine &ctx,
                           const Action &,
                           HeroState &hero,
                           BossKinematics &bk,
                           FsmRuntime &fsm,
                           StunControl &sc,
                           BossObs &bossObs)
{
    GlobalFreeze &gf = ctx.singleton<GlobalFreeze>();

    // Skip boss during global freeze
    if (gf.timer > 0.f) {
        bk.velX = 0.f;
        bk.velY = 0.f;
        goto write_obs;
    }

    // Skip boss during recoil
    if (sc.recoilRem > 0) {
        sc.recoilRem = (int16_t)(sc.recoilRem - 1);
        // During recoil, just integrate position with current velocity
        {
            float gravScale = 2.0f;
            bossIntegrate(bk, sc, false, gravScale, consts::deltaT);
        }
        goto write_obs;
    }

    {
        const FsmDef &def = ctx.singleton<FsmDefSingleton>().def;
        int32_t bossHP = (int32_t)bossObs.health;

        // Build FSM action context
        // Read persisted state from FsmRuntime (set by FSM actions, survives across frames)
        float gravityScale = fsm.gravityScale;
        bool isKinematic = fsm.isKinematic;
        bool hitboxActive = fsm.hitboxActive;
        float hitboxHalfW = fsm.hitboxHalfW;
        float hitboxHalfH = fsm.hitboxHalfH;
        float hitboxOffsetX = fsm.hitboxOffsetX;
        float hitboxOffsetY = fsm.hitboxOffsetY;
        int16_t hitboxDamage = fsm.hitboxDamage;
        fsm.heroDamageOut = 0.f;
        fsm.heroDamageBypass = false;
        float facingScale = fsm.facingScale;

        FsmActionCtx actx = {
            .rt          = fsm,
            .bk          = bk,
            .sc          = sc,
            .heroX       = hero.posX,
            .heroY       = hero.posY,
            .heroIFrameRem = hero.invulTimer,
            .rng         = ctx.data().rng,
            .dt          = consts::deltaT,
            .bossHP      = bossHP,
            .gravityBase = -60.0f,
            .gravityScale = gravityScale,
            .isKinematic = isKinematic,
            .hitboxActive = hitboxActive,
            .hitboxHalfW = hitboxHalfW,
            .hitboxHalfH = hitboxHalfH,
            .hitboxOffsetX = hitboxOffsetX,
            .hitboxOffsetY = hitboxOffsetY,
            .hitboxDamage = hitboxDamage,
            .freezeTimer = gf.timer,
            .heroDamageOut = fsm.heroDamageOut,
            .heroDamageBypass = fsm.heroDamageBypass,
            .facingScale = facingScale,
        };

        fsmTick(def, actx);

        // Write back persisted state to FsmRuntime
        bossObs.health = (float)bossHP;
        fsm.gravityScale = actx.gravityScale;
        fsm.isKinematic = actx.isKinematic;
        fsm.hitboxActive = actx.hitboxActive;
        fsm.hitboxHalfW = actx.hitboxHalfW;
        fsm.hitboxHalfH = actx.hitboxHalfH;
        fsm.hitboxOffsetX = actx.hitboxOffsetX;
        fsm.hitboxOffsetY = actx.hitboxOffsetY;
        fsm.hitboxDamage = actx.hitboxDamage;

        // Integrate boss physics
        bossIntegrate(bk, sc, fsm.isKinematic, fsm.gravityScale, consts::deltaT);

        fsm.facingScale = actx.facingScale;
        bossObs.facingRight = fsm.facingScale >= 0.f ? 1.f : 0.f;
    }

write_obs:
    bossObs.posX = bk.posX;
    bossObs.posY = bk.posY;
    bossObs.velX = bk.velX;
    bossObs.velY = bk.velY;

    // Phase: check if enraged (HP <= maxHP / rageHPFrac)
    bool enraged = bossObs.health <= (float)(consts::bossMaxHP / consts::bossRageHPFrac);
    bossObs.phase = enraged ? 2.f : 1.f;
    bossObs.maxHealth = (float)consts::bossMaxHealth;

    // animState: map FSM state to a category for RL obs
    bossObs.animState = (float)fsm.currentState;
    bossObs.animProgress = 0.f;
}

// combatSystem for: hit detection + stun control decay + invuln timer tick
inline void combatSystem(Engine &ctx,
                         HeroState &hero,
                         PlayerObs &obs,
                         BossKinematics &bk,
                         FsmRuntime &fsm,
                         StunControl &sc,
                         EpisodeState &epState,
                         Reward &reward,
                         Done &done)
{
    GlobalFreeze &gf = ctx.singleton<GlobalFreeze>();
    const HeroConfig &cfg = ctx.singleton<HeroConfigSingleton>().config;
    float r = 0.f;

    int32_t bossHP = (int32_t)obs.health; // use Bossobs health as sync point
    //acctually use the stored health from bossObs ..  but we need the boss hp
    // we store boss HP in BossObs.health. Read from there.
    Entity agent = ctx.data().agents[0];
    BossObs &bossObs = ctx.get<BossObs>(agent);
    bossHP = (int32_t)bossObs.health;

    const bool hit = bossReceiveHit(hero, bk, fsm, sc, bossHP, gf.timer);
    bossObs.health = (float)bossHP;

    // Boss hitbox hitting hero , we use FSM hitbox state
    bool hurt = false;
    if (fsm.hitboxActive && sc.damageAmount > 0) {
        float facing = fsm.facingScale >= 0.f ? 1.f : -1.f;
        float hitboxCX = bk.posX + facing * fsm.hitboxOffsetX;
        float hitboxCY = bk.posY + fsm.hitboxOffsetY;
        float hitboxHW = fsm.hitboxHalfW > 0.f ? fsm.hitboxHalfW : consts::bossBodyHalfW;
        float hitboxHH = fsm.hitboxHalfH > 0.f ? fsm.hitboxHalfH : consts::bossBodyHalfH;
        hurt = heroReceiveDamage(hero, cfg, bk.posX, bk.posY,
                                 hitboxCX, hitboxCY, hitboxHW, hitboxHH,
                                 (int)sc.damageAmount, gf.timer);
        if (hurt) obs.health = (float)hero.health;
    }

    // DamageHeroDirectly: FSM action that bypasses i-frames
    if (fsm.heroDamageOut > 0.f) {
        int dmg = (int)fsm.heroDamageOut;
        if (fsm.heroDamageBypass || (!hero.states.Invulnerable() && hero.invulTimer <= 0.f)) {
            bool fromLeft = bk.posX < hero.posX;
            TakeDamage(hero, cfg, dmg, fromLeft, gf.timer);
            obs.health = (float)hero.health;
            hurt = true;
        }
        fsm.heroDamageOut = 0.f;
        fsm.heroDamageBypass = false;
    }

    //old project ported reward
    const bool bossStunned = (fsm.currentState == 40 || fsm.currentState == 41
                           || fsm.currentState == 42 || fsm.currentState == 43);

    if (hit) {
        r += bossStunned ? 2.f : 1.f;
    }
    if (hurt) {
        r -= bossStunned ? 2.f : 1.f;
    }

    //idle penalty: -0.001 per step when nothing happens
    if (!hit && !hurt) {
        r -= 0.001f;
    }

    // distance penalties (original: -0.001 if dist > 15 or dist < 1)
    const float dist = fabsf(hero.posX - bk.posX);
    if (dist > 15.f) r -= 0.001f;
    if (dist < 1.f)  r -= 0.001f;

    //fights win/loss
    if (bossHP <= 0) {
        float healthBonus = (float)hero.health / (float)consts::playerMaxHealth;
        float timeBonus = fminf(1.f, 100.f / fmaxf(epState.episodeTime, 1.f));
        r += healthBonus + timeBonus;
        done.v = 1;
    }
    if (hero.health <= 0) {
        float bossRemaining = (float)bossHP / (float)consts::bossMaxHP;
        r -= bossRemaining;
        done.v = 1;
    }

    // Stun control decay
    if (sc.invincTimer > 0) sc.invincTimer = (int16_t)(sc.invincTimer - 1);

    if (sc.comboTime > 0.f) {
        sc.comboTime -= consts::deltaT;
        if (sc.comboTime <= 0.f) {
            sc.comboCounter = 0.f;
            sc.comboTime = 0.f;
        }
    }

    // global freeze timer tick
    if (gf.timer > 0.f) {
        gf.timer -= consts::deltaT;
        if (gf.timer < 0.f) gf.timer = 0.f;
    }

    reward.v = r;
}

inline void projectileStepSystem(Engine &ctx,
                                  HeroState &hero,
                                  PlayerObs &obs,
                                  Reward &reward,
                                  Done &done)
{
    ActiveProjectiles &proj = ctx.singleton<ActiveProjectiles>();
    const HeroConfig &cfg = ctx.singleton<HeroConfigSingleton>().config;
    GlobalFreeze &gf = ctx.singleton<GlobalFreeze>();
    uint32_t mask = proj.activeMask;
    while (mask) {
        int i = 0;
        uint32_t tmp = mask;
        while (!(tmp & 1u)) { tmp >>= 1; i++; }
        mask &= ~(1u << i);

        proj.posX[i] += proj.velX[i] * consts::deltaT;
        proj.posY[i] += proj.velY[i] * consts::deltaT;
        proj.velY[i] += consts::bossGravity * consts::deltaT;
        proj.ttl[i]--;

        bool oob = proj.posX[i] < (consts::bossConstraintXMin - 5.f)
                || proj.posX[i] > (consts::bossConstraintXMax + 5.f)
                || proj.posY[i] < consts::bossLandY;
        if (proj.ttl[i] <= 0 || oob) {
            proj.activeMask &= ~(1u << i);
            continue;
        }

        if (hero.states.Invulnerable() || hero.invulTimer > 0.f) continue;
        if (aabbOverlap(proj.posX[i], proj.posY[i], proj.halfW[i], proj.halfH[i],
                        hero.posX, hero.posY + consts::heroHurtNormalOffY,
                        consts::heroHurtNormalHalfW, consts::heroHurtNormalHalfH)) {
            bool fromLeft = proj.posX[i] < hero.posX;
            TakeDamage(hero, cfg, (int)proj.damage[i], fromLeft, gf.timer);
            obs.health = (float)hero.health;
            reward.v -= (float)proj.damage[i] / (float)consts::playerMaxHealth;
            proj.activeMask &= ~(1u << i);
            if (hero.health <= 0) { reward.v -= 5.f; done.v = 1; }
        }
    }
}

inline void raycastSystem(Engine &ctx,HeroState &hero,BossKinematics &bk,
                           RaycastDistances &rd,
                           RaycastHitTypes &rh){
    const Arena &arena = ctx.singleton<Arena>();
    const ActiveProjectiles &proj = ctx.singleton<ActiveProjectiles>();
    castRays(arena, hero, bk, proj, rd, rh);
}

inline void stepSystem(Engine &,
                       EpisodeState &epState,
                       Reward &reward,
                       Done &done) {
    epState.stepsTaken += 1;
    epState.stepsRemaining = consts::episodeLen - epState.stepsTaken;
    epState.episodeTime += consts::deltaT *
        static_cast<float>(consts::numPhysicsSubsteps);

    if (epState.stepsRemaining <= 0) done.v = 1;
}

void Sim::setupTasks(TaskGraphManager &taskgraph_mgr, const Config &)
{
    TaskGraphBuilder &builder = taskgraph_mgr.init(TaskGraphID::Step);

    auto reset_tasks = builder.addToGraph<ParallelForNode<Engine,
        resetSystem,
            WorldReset
        >>({});

    auto hero_tasks = builder.addToGraph<ParallelForNode<Engine,
        heroStepSystem,
            Action,
            HeroState,
            PlayerObs
        >>({reset_tasks});

    auto boss_tasks = builder.addToGraph<ParallelForNode<Engine,
        bossStepSystem,
            Action,
            HeroState,
            BossKinematics,
            FsmRuntime,
            StunControl,
            BossObs
        >>({hero_tasks});

    auto combat_tasks = builder.addToGraph<ParallelForNode<Engine,
        combatSystem,
            HeroState,
            PlayerObs,
            BossKinematics,
            FsmRuntime,
            StunControl,
            EpisodeState,
            Reward,
            Done
        >>({boss_tasks});

    auto proj_tasks = builder.addToGraph<ParallelForNode<Engine,
        projectileStepSystem,
            HeroState,
            PlayerObs,
            Reward,
            Done
        >>({combat_tasks});

    auto ray_tasks = builder.addToGraph<ParallelForNode<Engine,
        raycastSystem,
            HeroState,
            BossKinematics,
            RaycastDistances,
            RaycastHitTypes
        >>({proj_tasks});

    builder.addToGraph<ParallelForNode<Engine,
        stepSystem,
            EpisodeState,
            Reward,
            Done
        >>({ray_tasks});
}

Sim::Sim(Engine &ctx, const Config &cfg, const WorldInit &)
    : WorldBase(ctx),
      initRandKey(cfg.initRandKey),
      autoReset(cfg.autoReset),
      curWorldEpisode(0),
      rng(0)
{
    bakeBoneEast12Arena(ctx.singleton<Arena>());
    ctx.singleton<HeroInit>() = HeroInit{};
    ctx.singleton<GlobalFreeze>() = GlobalFreeze{0.f};

    // Initialize FsmDef singleton from baked data
    ctx.singleton<FsmDefSingleton>().def = cfg.fsmDef;
    ctx.singleton<HeroConfigSingleton>().config = cfg.heroConfig;

    createPersistentEntities(ctx);
    initWorld(ctx);
}

MADRONA_BUILD_MWGPU_ENTRY(Engine, Sim, Sim::Config, Sim::WorldInit);

}
