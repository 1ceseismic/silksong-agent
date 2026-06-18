set(SIMULATOR_SRCS
    types.hpp
    sim.hpp sim.inl sim.cpp
    level_gen.hpp level_gen.cpp
)

add_library(silksong_sim_cpu_impl STATIC
    ${SIMULATOR_SRCS}
)

target_link_libraries(silksong_sim_cpu_impl
    PUBLIC
        madrona_mw_core
    PRIVATE
        madrona_common
)

add_library(silksong_sim_mgr STATIC
    mgr.hpp mgr.cpp
)

target_link_libraries(silksong_sim_mgr
    PUBLIC
        madrona_python_utils
    PRIVATE
        silksong_sim_cpu_impl
        madrona_mw_cpu
        madrona_common
)

if (TARGET madrona_mw_gpu)
    madrona_build_compile_defns(
        OUT_TARGET
            silksong_sim_gpu_srcs
        SOURCES_DEFN
            SILKSONG_SIM_SRC_LIST
        FLAGS_DEFN
            SILKSONG_SIM_COMPILE_FLAGS
        SRCS
            ${SIMULATOR_SRCS}
    )

    target_link_libraries(silksong_sim_mgr PRIVATE
        silksong_sim_gpu_srcs
        madrona_mw_gpu
    )
endif ()

madrona_python_module(silksong_sim
    bindings.cpp
)

target_link_libraries(silksong_sim PRIVATE
    silksong_sim_mgr
)

add_executable(headless headless.cpp)
target_link_libraries(headless madrona_mw_core silksong_sim_mgr)

# Standalone FSM interpreter test (minimal Madrona dependency for RNG only)
add_executable(test_fsm test_fsm.cpp)
target_include_directories(test_fsm PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(test_fsm PRIVATE madrona_common)
