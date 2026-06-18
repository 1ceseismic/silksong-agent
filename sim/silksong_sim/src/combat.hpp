#pragma once

// ======================================================================
// Combat System — ports of HealthManager.Hit() and HeroController.TakeDamage()
//
// bossReceiveHit(): hero attack lands on boss
//   - Port of HealthManager.Hit() (decompiled/HealthManager.cs lines 930-1100)
//   - Damage, invuln timer, recoil, stun control update
//   - NO freeze on normal attacks (only on CriticalHit which we don't model)
//   - Hero gets RECOIL_HOR knockback only
//
// heroReceiveDamage(): boss hitbox/projectile lands on hero
//   - Port of HeroController.TakeDamage() (lines 5254-5630)
//   - FreezeMoment (global time stop), StartInvulnerable(INVUL_TIME)
//   - Recoil vector (±RECOIL_VELOCITY, RECOIL_VELOCITY*0.5)
//   - Gravity disable during recoil
// ======================================================================

static inline bool aabbOverlap(float ax, float ay, float ahw, float ahh,
                                float bx, float by, float bhw, float bhh)
{
    return fabsf(ax - bx) < (ahw + bhw) && fabsf(ay - by) < (ahh + bhh);
}

// -----------------------------------------------------------------------
// bossReceiveHit — hero's attack lands on boss
//
// Port of HealthManager.Hit() (lines 930-1100).
// Returns true if hit connected.
//
// Applies: damage, boss invincibility, boss recoil, hero RECOIL_HOR knockback,
// stun gauge update, sends TOOK_DAMAGE event to FSM.
// NO FreezeMoment on normal hero attacks.
// -----------------------------------------------------------------------
static inline bool bossReceiveHit(HeroState &hero,
                                   BossKinematics &bk,
                                   FsmRuntime &fsm,
                                   StunControl &sc,
                                   int32_t &bossHP,
                                   float &globalFreezeTimer)
{
    // Check hero is attacking (using the hero state's attacking flag + active window)
    if (!hero.states.attacking && !hero.states.upAttacking && !hero.states.downAttacking)
        return false;
    if (hero.attackDuration <= 0.0f) return false;

    // Check boss invincibility
    if (sc.isInvincible) return false;
    if (sc.invincTimer > 0) return false;
    if (bossHP <= 0) return false;

    // Attack hitbox (simple AABB based on hero facing + attack range)
    const float facing = hero.states.facingRight ? 1.f : -1.f;
    const float attackCenterX = hero.posX + facing * consts::attackRange * 0.5f;

    if (!aabbOverlap(attackCenterX, hero.posY,
                     consts::attackRange * 0.5f, consts::heroHalfHeight,
                     bk.posX, bk.posY,
                     consts::bossBodyHalfW, consts::bossBodyHalfH))
        return false;

    // --- HealthManager.Hit() damage application (line 1010-1015) ---
    bossHP -= consts::attackDamage;

    // --- Invulnerability (line 1020) ---
    sc.invincTimer = consts::bossInvincFrames;

    // --- Boss hit recoil (line 1048-1055) ---
    // SetRecoilSpeed from FSM determines recoil magnitude.
    // If recoilBlocked, boss does not recoil.
    if (!sc.recoilBlocked && sc.recoilSpeed > 0) {
        float bossRecoilDir = (bk.posX >= hero.posX) ? 1.f : -1.f;
        sc.recoilRem = (int16_t)(consts::bossRecoilDuration / consts::deltaT);
        bk.velX = bossRecoilDir * (float)sc.recoilSpeed;
    }

    // --- Hero RECOIL_HOR knockback (lines 1060-1065) ---
    // Small horizontal knockback away from boss (no freeze, no i-frames)
    float heroRecoilDir = (hero.posX >= bk.posX) ? 1.f : -1.f;
    hero.recoilStepsLeft = consts::heroAttackRecoilFrames;
    hero.recoilVelocity = consts::heroAttackRecoilVel;
    if (heroRecoilDir > 0.f) {
        hero.states.recoilingRight = true;
        hero.states.recoilingLeft = false;
    } else {
        hero.states.recoilingLeft = true;
        hero.states.recoilingRight = false;
    }

    // --- Stun control update (port of Stun Control FSM) ---
    // Combo counter: increments on hit, resets when comboTime (1.0s) expires
    sc.comboCounter += 1.f;
    sc.comboTime = 1.0f;  // reset the 1.0s rolling window
    sc.hitsTotal += 1.f;

    // Check stun condition
    bool triggerStun = false;
    if ((int)sc.comboCounter >= sc.stunCombo) {
        triggerStun = true;
    }
    if ((int)sc.hitsTotal >= sc.stunHitMax) {
        triggerStun = true;
    }

    // Fire TOOK_DAMAGE event to FSM (for counter/stun reactions)
    // The FSM will process this on next tick via fsmFireEvent.
    // We use the baked event ID for TOOK_DAMAGE.
    // (The stun event is fired separately if stun triggered.)
    if (triggerStun) {
        // Fire STUN event — event ID 32 in baked data
        fsmFireEvent(fsm, 32);  // EVT_STUN
        // Reset stun tracking
        sc.comboCounter = 0.f;
        sc.hitsTotal = 0.f;
    } else {
        // Fire TOOK_DAMAGE event — event ID 34
        fsmFireEvent(fsm, 34);  // EVT_TOOK_DAMAGE
    }

    return true;
}

// -----------------------------------------------------------------------
// heroReceiveDamage — boss hitbox lands on hero
//
// Port of HeroController.TakeDamage() (lines 5254-5630) + StartRecoil()
// (lines 9556-9613) + FreezeMoment (GameManager.cs lines 5068-5140).
//
// Returns true if damage was applied.
//
// Applies: FreezeMoment (global time stop), StartInvulnerable(INVUL_TIME),
// recoil vector (±RECOIL_VELOCITY, RECOIL_VELOCITY*0.5), gravity disable.
// -----------------------------------------------------------------------
static inline bool heroReceiveDamage(HeroState &hero,
                                      const HeroConfig &cfg,
                                      float bossX, float bossY,
                                      float hitboxCenterX, float hitboxCenterY,
                                      float hitboxHalfW, float hitboxHalfH,
                                      int damageAmount,
                                      float &globalFreezeTimer)
{
    if (damageAmount <= 0) return false;

    // Check hero invulnerability (CanTakeDamage equivalent)
    if (hero.states.Invulnerable()) return false;
    if (hero.states.recoiling) return false;
    if (hero.states.dead) return false;
    if (hero.states.shadowDashing) return false;
    if (hero.states.evading) return false;
    if (hero.states.parryAttack) return false;
    if (hero.invulTimer > 0.f) return false;

    // AABB overlap check with hero hurtbox
    if (!aabbOverlap(hitboxCenterX, hitboxCenterY,
                     hitboxHalfW, hitboxHalfH,
                     hero.posX, hero.posY + consts::heroHurtNormalOffY,
                     consts::heroHurtNormalHalfW, consts::heroHurtNormalHalfH))
        return false;

    // Delegate to TakeDamage from hero.hpp
    bool fromLeft = bossX < hero.posX;
    TakeDamage(hero, cfg, damageAmount, fromLeft, globalFreezeTimer);

    return true;
}
