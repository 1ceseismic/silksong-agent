#include "mgr.hpp"

#include <madrona/macros.hpp>
#include <madrona/py/bindings.hpp>

namespace nb = nanobind;

namespace silksong {

// `.to_torch()` on any returned Tensor yields a zero-copy PyTorch view.
NB_MODULE(silksong_sim, m) {
    madrona::py::setupMadronaSubmodule(m);

    nb::class_<Manager>(m, "SimManager")
        .def("__init__", [](Manager *self,
                            madrona::py::PyExecMode exec_mode,
                            int64_t gpu_id,
                            int64_t num_worlds,
                            int64_t rand_seed,
                            bool auto_reset) {
            new (self) Manager(Manager::Config{
                .execMode = exec_mode,
                .gpuID = (int)gpu_id,
                .numWorlds = (uint32_t)num_worlds,
                .randSeed = (uint32_t)rand_seed,
                .autoReset = auto_reset,
            });
        },
        nb::arg("exec_mode"),
        nb::arg("gpu_id"),
        nb::arg("num_worlds"),
        nb::arg("rand_seed"),
        nb::arg("auto_reset"))
        .def("step", &Manager::step)
        .def("reset_tensor", &Manager::resetTensor)
        .def("hero_init_tensor", &Manager::heroInitTensor)
        .def("action_tensor", &Manager::actionTensor)
        .def("player_obs_tensor", &Manager::playerObsTensor)
        .def("boss_obs_tensor", &Manager::bossObsTensor)
        .def("raycast_distances_tensor", &Manager::raycastDistancesTensor)
        .def("raycast_hit_types_tensor", &Manager::raycastHitTypesTensor)
        .def("episode_state_tensor", &Manager::episodeStateTensor)
        .def("reward_tensor", &Manager::rewardTensor)
        .def("done_tensor", &Manager::doneTensor)
    ;
}

}
