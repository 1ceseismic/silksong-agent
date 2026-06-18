#pragma once

#include <memory>

#include <madrona/py/utils.hpp>
#include <madrona/exec_mode.hpp>

namespace silksong {

class Manager {
public:
    struct Config {
        madrona::ExecMode execMode;
        int gpuID;
        uint32_t numWorlds;
        uint32_t randSeed;
        bool autoReset;
    };

    Manager(const Config &cfg);
    ~Manager();

    void step();

    madrona::py::Tensor resetTensor() const;
    madrona::py::Tensor heroInitTensor() const;
    madrona::py::Tensor actionTensor() const;

    madrona::py::Tensor playerObsTensor() const;
    madrona::py::Tensor bossObsTensor() const;
    madrona::py::Tensor raycastDistancesTensor() const;
    madrona::py::Tensor raycastHitTypesTensor() const;
    madrona::py::Tensor episodeStateTensor() const;

    madrona::py::Tensor rewardTensor() const;
    madrona::py::Tensor doneTensor() const;

    void triggerReset(int32_t world_idx);
    void setAction(int32_t world_idx,
                   int32_t agent_idx,
                   int32_t left, int32_t right,
                   int32_t up, int32_t down,
                   int32_t jump, int32_t attack,
                   int32_t dash, int32_t clawline,
                   int32_t skill, int32_t heal);

private:
    struct Impl;
    struct CPUImpl;
    struct CUDAImpl;

    std::unique_ptr<Impl> impl_;
};

}
