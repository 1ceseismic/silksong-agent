#pragma once

// Hit types: 0=None, 1=Terrain, 2=Enemy, 5=BossProjectile
static inline void castRays(const Arena &arena,
                             const HeroState &pk,
                             const BossKinematics &bk,
                             const ActiveProjectiles &proj,
                             RaycastDistances &rd,
                             RaycastHitTypes &rh)
{
    constexpr float maxDist = consts::maxRayDistance;
    constexpr float step = 0.5f;
    constexpr int maxSteps = (int)(maxDist / step);
    constexpr float PI2 = 6.28318530718f;

    for (int r = 0; r < consts::numRays; ++r) {
        float angle = (float)r / (float)consts::numRays * PI2;
        float cosA = cosf(angle);
        float sinA = sinf(angle);
        float dx = cosA * step;
        float dy = sinA * step;

        float bestDist = maxDist;
        int32_t bestType = 0;

        float rx = pk.posX;
        float ry = pk.posY;
        for (int s = 1; s <= maxSteps; ++s) {
            rx += dx;
            ry += dy;
            if (isTileSolid(arena, rx, ry)) {
                bestDist = (float)s * step;
                bestType = 1;
                break;
            }
        }

        float toBossX = bk.posX - pk.posX;
        float toBossY = bk.posY - pk.posY;
        float projD = toBossX * cosA + toBossY * sinA;
        if (projD > 0.f && projD < bestDist) {
            float perpX = toBossX - projD * cosA;
            float perpY = toBossY - projD * sinA;
            if (fabsf(perpX) < consts::bossBodyHalfW + 0.3f
                && fabsf(perpY) < consts::bossBodyHalfH + 0.3f) {
                bestDist = projD;
                bestType = 2;
            }
        }

        uint32_t pmask = proj.activeMask;
        while (pmask) {
            int pi = 0;
            uint32_t ptmp = pmask;
            while (!(ptmp & 1u)) { ptmp >>= 1; pi++; }
            pmask &= ~(1u << pi);

            float toProjX = proj.posX[pi] - pk.posX;
            float toProjY = proj.posY[pi] - pk.posY;
            float pd = toProjX * cosA + toProjY * sinA;
            if (pd > 0.f && pd < bestDist) {
                float ppX = toProjX - pd * cosA;
                float ppY = toProjY - pd * sinA;
                if (fabsf(ppX) < proj.halfW[pi] + 0.3f
                    && fabsf(ppY) < proj.halfH[pi] + 0.3f) {
                    bestDist = pd;
                    bestType = 5;
                }
            }
        }

        rd.v[r] = bestDist / maxDist;
        rh.v[r] = bestType;
    }
}
