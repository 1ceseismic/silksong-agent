#include "mgr.hpp"
#include "sim.hpp"
#include "fsm_lace_boss1.hpp"

#include <madrona/utils.hpp>
#include <madrona/tracing.hpp>
#include <madrona/mw_cpu.hpp>

#include <array>

#ifdef MADRONA_CUDA_SUPPORT
#include <madrona/mw_gpu.hpp>
#include <madrona/cuda_utils.hpp>
#endif

using namespace madrona;
using namespace madrona::py;

namespace silksong {

struct Manager::Impl {
    Config cfg;
    WorldReset *worldResetBuffer;
    Action *agentActionsBuffer;

    inline Impl(const Manager::Config &mgr_cfg,
                WorldReset *reset_buffer,
                Action *action_buffer)
        : cfg(mgr_cfg),
          worldResetBuffer(reset_buffer),
          agentActionsBuffer(action_buffer)
    {}

    inline virtual ~Impl() {}

    virtual void run() = 0;

    virtual Tensor exportTensor(ExportID slot,
        TensorElementType type,
        madrona::Span<const int64_t> dimensions) const = 0;

    static inline Impl *init(const Config &cfg);
};

struct Manager::CPUImpl final : Manager::Impl {
    using TaskGraphT =
        TaskGraphExecutor<Engine, Sim, Sim::Config, Sim::WorldInit>;

    TaskGraphT cpuExec;

    inline CPUImpl(const Manager::Config &mgr_cfg,
                   WorldReset *reset_buffer,
                   Action *action_buffer,
                   TaskGraphT &&cpu_exec)
        : Impl(mgr_cfg, reset_buffer, action_buffer),
          cpuExec(std::move(cpu_exec))
    {}

    inline virtual ~CPUImpl() final {}

    inline virtual void run() final
    {
        cpuExec.run();
    }

    virtual inline Tensor exportTensor(ExportID slot,
        TensorElementType type,
        madrona::Span<const int64_t> dims) const final
    {
        void *dev_ptr = cpuExec.getExported((uint32_t)slot);
        return Tensor(dev_ptr, type, dims, Optional<int>::none());
    }
};

#ifdef MADRONA_CUDA_SUPPORT
struct Manager::CUDAImpl final : Manager::Impl {
    MWCudaExecutor gpuExec;
    MWCudaLaunchGraph stepGraph;

    inline CUDAImpl(const Manager::Config &mgr_cfg,
                    WorldReset *reset_buffer,
                    Action *action_buffer,
                    MWCudaExecutor &&gpu_exec)
        : Impl(mgr_cfg, reset_buffer, action_buffer),
          gpuExec(std::move(gpu_exec)),
          stepGraph(gpuExec.buildLaunchGraphAllTaskGraphs())
    {}

    inline virtual ~CUDAImpl() final {}

    inline virtual void run() final
    {
        gpuExec.run(stepGraph);
    }

    virtual inline Tensor exportTensor(ExportID slot,
        TensorElementType type,
        madrona::Span<const int64_t> dims) const final
    {
        void *dev_ptr = gpuExec.getExported((uint32_t)slot);
        return Tensor(dev_ptr, type, dims, cfg.gpuID);
    }
};
#endif

Manager::Impl *Manager::Impl::init(const Manager::Config &mgr_cfg)
{
    Sim::Config sim_cfg{};
    sim_cfg.autoReset = mgr_cfg.autoReset;
    sim_cfg.initRandKey = rand::initKey(mgr_cfg.randSeed);
    sim_cfg.fsmDef = silksong::fsm_lace_boss1::makeDef();
    sim_cfg.heroConfig = silksong::HERO_CONFIG_DEFAULT;

    switch (mgr_cfg.execMode) {
    case ExecMode::CUDA: {
#ifdef MADRONA_CUDA_SUPPORT
        CUcontext cu_ctx = MWCudaExecutor::initCUDA(mgr_cfg.gpuID);

        HeapArray<Sim::WorldInit> world_inits(mgr_cfg.numWorlds);

        MWCudaExecutor gpu_exec({
            .worldInitPtr = world_inits.data(),
            .numWorldInitBytes = sizeof(Sim::WorldInit),
            .userConfigPtr = (void *)&sim_cfg,
            .numUserConfigBytes = sizeof(Sim::Config),
            .numWorldDataBytes = sizeof(Sim),
            .worldDataAlignment = alignof(Sim),
            .numWorlds = mgr_cfg.numWorlds,
            .numTaskGraphs = 1,
            .numExportedBuffers = (uint32_t)ExportID::NumExports,
        }, {
            { SILKSONG_SIM_SRC_LIST },
            { SILKSONG_SIM_COMPILE_FLAGS },
            CompileConfig::OptMode::LTO,
        }, cu_ctx);

        WorldReset *world_reset_buffer =
            (WorldReset *)gpu_exec.getExported((uint32_t)ExportID::Reset);
        Action *agent_actions_buffer =
            (Action *)gpu_exec.getExported((uint32_t)ExportID::Action);

        return new CUDAImpl{
            mgr_cfg,
            world_reset_buffer,
            agent_actions_buffer,
            std::move(gpu_exec),
        };
#else
        FATAL("Madrona was not compiled with CUDA support");
#endif
    } break;

    case ExecMode::CPU: {
        HeapArray<Sim::WorldInit> world_inits(mgr_cfg.numWorlds);

        CPUImpl::TaskGraphT cpu_exec{
            ThreadPoolExecutor::Config{
                .numWorlds = mgr_cfg.numWorlds,
                .numExportedBuffers = (uint32_t)ExportID::NumExports,
            },
            sim_cfg,
            world_inits.data(),
            (uint32_t)TaskGraphID::NumTaskGraphs,
        };

        WorldReset *world_reset_buffer =
            (WorldReset *)cpu_exec.getExported((uint32_t)ExportID::Reset);
        Action *agent_actions_buffer =
            (Action *)cpu_exec.getExported((uint32_t)ExportID::Action);

        return new CPUImpl{
            mgr_cfg,
            world_reset_buffer,
            agent_actions_buffer,
            std::move(cpu_exec),
        };
    } break;

    default: MADRONA_UNREACHABLE();
    }
}

Manager::Manager(const Config &cfg)
    : impl_(Impl::init(cfg))
{
    for (int32_t i = 0; i < (int32_t)cfg.numWorlds; ++i) {
        triggerReset(i);
    }
    step();
}

Manager::~Manager() = default;

void Manager::step()
{
    impl_->run();
}

Tensor Manager::resetTensor() const
{
    return impl_->exportTensor(ExportID::Reset, TensorElementType::Int32, {
        impl_->cfg.numWorlds, 1,
    });
}

Tensor Manager::heroInitTensor() const
{
    return impl_->exportTensor(ExportID::HeroInit, TensorElementType::Int32, {
        impl_->cfg.numWorlds, (int64_t)(sizeof(HeroInit) / 4),
    });
}

Tensor Manager::actionTensor() const
{
    return impl_->exportTensor(ExportID::Action, TensorElementType::Int32, {
        impl_->cfg.numWorlds, consts::numAgents, (int64_t)consts::numActions,
    });
}

Tensor Manager::playerObsTensor() const
{
    return impl_->exportTensor(ExportID::PlayerObs, TensorElementType::Float32, {
        impl_->cfg.numWorlds, consts::numAgents, (int64_t)(sizeof(PlayerObs) / sizeof(float)),
    });
}

Tensor Manager::bossObsTensor() const
{
    return impl_->exportTensor(ExportID::BossObs, TensorElementType::Float32, {
        impl_->cfg.numWorlds, consts::numAgents, (int64_t)(sizeof(BossObs) / sizeof(float)),
    });
}

Tensor Manager::raycastDistancesTensor() const
{
    return impl_->exportTensor(ExportID::RaycastDistances,
                               TensorElementType::Float32, {
        impl_->cfg.numWorlds, consts::numAgents, (int64_t)consts::numRays,
    });
}

Tensor Manager::raycastHitTypesTensor() const
{
    return impl_->exportTensor(ExportID::RaycastHitTypes,
                               TensorElementType::Int32, {
        impl_->cfg.numWorlds, consts::numAgents, (int64_t)consts::numRays,
    });
}

Tensor Manager::episodeStateTensor() const
{
    return impl_->exportTensor(ExportID::EpisodeState,
                               TensorElementType::Int32, {
        impl_->cfg.numWorlds, consts::numAgents, 3,
    });
}

Tensor Manager::rewardTensor() const
{
    return impl_->exportTensor(ExportID::Reward, TensorElementType::Float32, {
        impl_->cfg.numWorlds, consts::numAgents, 1,
    });
}

Tensor Manager::doneTensor() const
{
    return impl_->exportTensor(ExportID::Done, TensorElementType::Int32, {
        impl_->cfg.numWorlds, consts::numAgents, 1,
    });
}

void Manager::triggerReset(int32_t world_idx)
{
    WorldReset reset{1};

    WorldReset *reset_ptr = impl_->worldResetBuffer + world_idx;

    if (impl_->cfg.execMode == ExecMode::CUDA) {
#ifdef MADRONA_CUDA_SUPPORT
        cudaMemcpy(reset_ptr, &reset, sizeof(WorldReset),
                   cudaMemcpyHostToDevice);
#endif
    } else {
        *reset_ptr = reset;
    }
}

void Manager::setAction(int32_t world_idx,
                        int32_t agent_idx,
                        int32_t left, int32_t right,
                        int32_t up, int32_t down,
                        int32_t jump, int32_t attack,
                        int32_t dash, int32_t clawline,
                        int32_t skill, int32_t heal)
{
    Action action{
        .left = left,       .right = right,
        .up = up,           .down = down,
        .jump = jump,       .attack = attack,
        .dash = dash,       .clawline = clawline,
        .skill = skill,     .heal = heal,
    };

    Action *action_ptr = impl_->agentActionsBuffer +
        world_idx * consts::numAgents + agent_idx;

    if (impl_->cfg.execMode == ExecMode::CUDA) {
#ifdef MADRONA_CUDA_SUPPORT
        cudaMemcpy(action_ptr, &action, sizeof(Action),
                   cudaMemcpyHostToDevice);
#endif
    } else {
        *action_ptr = action;
    }
}

}
