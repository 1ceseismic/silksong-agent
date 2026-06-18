#include "mgr.hpp"

#include <cstdio>
#include <chrono>
#include <string>
#include <random>

using namespace madrona;

int main(int argc, char *argv[])
{
    using namespace silksong;

    if (argc < 4) {
        fprintf(stderr, "%s TYPE NUM_WORLDS NUM_STEPS [--rand-actions]\n",
                argv[0]);
        return -1;
    }

    std::string type(argv[1]);
    ExecMode exec_mode;
    if (type == "CPU") {
        exec_mode = ExecMode::CPU;
    } else if (type == "CUDA") {
        exec_mode = ExecMode::CUDA;
    } else {
        fprintf(stderr, "Invalid ExecMode (expected CPU or CUDA)\n");
        return -1;
    }

    uint64_t num_worlds = std::stoul(argv[2]);
    uint64_t num_steps = std::stoul(argv[3]);

    bool rand_actions = false;
    if (argc >= 5 && std::string(argv[4]) == "--rand-actions") {
        rand_actions = true;
    }

    Manager mgr({
        .execMode = exec_mode,
        .gpuID = 0,
        .numWorlds = (uint32_t)num_worlds,
        .randSeed = 5,
        .autoReset = true,
    });

    std::random_device rd;
    std::mt19937 rng(rd());
    std::uniform_int_distribution<int32_t> bin_rand(0, 1);

    auto start = std::chrono::system_clock::now();

    for (CountT i = 0; i < (CountT)num_steps; ++i) {
        if (rand_actions) {
            for (CountT w = 0; w < (CountT)num_worlds; ++w) {
                mgr.setAction(
                    (int32_t)w, 0,
                    bin_rand(rng), bin_rand(rng),
                    bin_rand(rng), bin_rand(rng),
                    bin_rand(rng), bin_rand(rng),
                    bin_rand(rng), bin_rand(rng),
                    bin_rand(rng), bin_rand(rng));
            }
        }
        mgr.step();
    }

    auto end = std::chrono::system_clock::now();
    std::chrono::duration<double> elapsed = end - start;

    double fps = (double)num_steps * (double)num_worlds / elapsed.count();
    printf("FPS %.2f  (worlds=%llu steps=%llu wall=%.3fs)\n",
           fps,
           (unsigned long long)num_worlds,
           (unsigned long long)num_steps,
           elapsed.count());
}
