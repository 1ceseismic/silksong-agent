#pragma once

#include <madrona/taskgraph_builder.hpp>
#include <madrona/custom_context.hpp>
#include <madrona/rand.hpp>

#include "consts.hpp"
#include "types.hpp"

namespace silksong {

class Engine;

enum class TaskGraphID : uint32_t {
    Step,
    NumTaskGraphs,
};

enum class ExportID : uint32_t {
    Reset,
    HeroInit,
    Action,
    PlayerObs,
    BossObs,
    RaycastDistances,
    RaycastHitTypes,
    EpisodeState,
    Reward,
    Done,
    NumExports,
};

struct Sim : public madrona::WorldBase {
    struct Config {
        bool autoReset;
        RandKey initRandKey;
        FsmDef fsmDef;          // populated by mgr.cpp on CPU, copied to GPU singleton in Sim::Sim
        HeroConfig heroConfig;  // populated by mgr.cpp on CPU
    };

    struct WorldInit {};

    static void registerTypes(madrona::ECSRegistry &registry,
                              const Config &cfg);

    static void setupTasks(madrona::TaskGraphManager &mgr,
                           const Config &cfg);

    Sim(Engine &ctx,
        const Config &cfg,
        const WorldInit &init);

    madrona::RandKey initRandKey;
    bool autoReset;
    uint32_t curWorldEpisode;
    madrona::RNG rng;

    Entity agents[consts::numAgents];
};

class Engine : public ::madrona::CustomContext<Engine, Sim> {
public:
    using CustomContext::CustomContext;
};

}

#include "sim.inl"
