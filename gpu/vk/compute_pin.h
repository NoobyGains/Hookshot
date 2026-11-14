// (hookshot) Which of the game's compute programs are held to 32 lanes (vk_draw.cpp compute_pipeline_info, pin_subgroup).
//
// The translated programs assume the guest's warp: 32 lanes that run together. A stage is held to that where the GPU
// can (VkPipelineShaderStageRequiredSubgroupSizeCreateInfo), and every compute program was. On Mesa's Intel driver that
// is what the compiles cost: held to 32 lanes the compiler makes the SIMD32 program alone, whose register allocation
// takes minutes and gigabytes for one of the game's large programs (an Iris Xe with 32 GB: compiles that had passed
// 5 GB each and were not done after five minutes, a preparation that was killed for memory or never ended, and in
// play the one build thread stuck behind such a program). Left to itself the driver makes the SIMD8 and SIMD16
// programs, in seconds.
//
// A program that cannot tell its lanes computes the same at any lane count, so it needs no pin. What tells them:
// - the subgroup operations (votes, ballots and lane masks, shuffles, the lane's index, quad shuffles, FSWZADD) and
//   the matrices, whose fragments are the warp's lanes: Shader::Info says which a stage uses, and the SPIR-V
//   emitter declares its GroupNonUniform capabilities and the cooperative matrices from the same flags;
// - shared memory in a workgroup of one warp (32 invocations or fewer): NVIDIA's compiler may leave out the barriers
//   such a workgroup does not need on the Switch, and at fewer lanes its invocations would race. A larger workgroup
//   orders its invocations' shared memory through its barriers (BAR.SYNC), which hold at any lane count. (The
//   translator's barrier of the subgroup between a warp's STS and its next LDS, lower_to_maxwell.h, is there for the
//   matrix programs, which keep their pin for their matrices.)
// Everything here is read from the program's record alone (its head and its stage's Shader::Info), never from its
// SPIR-V: a program read from the cache without its code (vk_progcache.cpp) must ask for the same pipeline as the
// preparation built.
//
// RX_VK_COMPUTE_PIN=all: every compute program pinned, as before; =lanes: only those that see their lanes, on any
// GPU. Unset: lanes on Mesa's Intel driver, where it was measured, all elsewhere. tests/test_compute_pin.py.
#pragma once

#include <cstdint>
#include <cstring>

namespace compute_pin {

/// What a compute program has that can tell the lanes it runs on (Shader::Info's flags of its stage, and the
/// program's shared memory in bytes)
struct Uses {
    bool vote = false, mask = false, invocation_id = false, shuffles = false, quad_shuffles = false;
    bool matrix = false, fswzadd = false;
    uint32_t shared_memory = 0;
    uint64_t invocations = 0;   // (the workgroup's: x * y * z)
};

/// The subgroup operations and matrices alone
inline bool sees_lanes_ops(const Uses& u) {
    return u.vote || u.mask || u.invocation_id || u.shuffles || u.quad_shuffles || u.matrix || u.fswzadd;
}
inline bool sees_lanes(const Uses& u) {
    return sees_lanes_ops(u) || (u.shared_memory != 0 && u.invocations <= 32);
}

enum class Mode { All, Lanes };

/// RX_VK_COMPUTE_PIN over the default: lanes on Mesa's Intel driver, all elsewhere. Any other text: the default
inline Mode mode_for(bool intel_mesa, const char* env) {
    if (env && !std::strcmp(env, "all")) return Mode::All;
    if (env && !std::strcmp(env, "lanes")) return Mode::Lanes;
    return intel_mesa ? Mode::Lanes : Mode::All;
}

/// Whether the program's stage is held to 32 lanes. known: its stage's flags could be read (a program with no stage
/// is pinned, as before)
inline bool needed(Mode mode, bool known, const Uses& u) { return mode == Mode::All || !known || sees_lanes(u); }

// Too big for Mesa's Intel compiler held to 32 lanes (vk_draw.cpp ComputeTurn). Its time goes to register allocation:
// at SIMD32 an Iris Xe thread has 32 registers a lane, and a program needing far more spills them in rounds, each one
// allocating the whole program again. Two of MKW's compute programs are about 12,400 phis each (045df6f2e27d05e6 and
// 184791cd4644065f: 2.2 MB of SPIR-V, one function with 5,700 small branches); every other one held to 32 lanes has
// 2,650 phis or fewer. Measured alone (i9-13900H, Iris Xe, Mesa 26.2.4): 045df6f2e27d05e6 was at 17.6 GB and not done
// after 30 minutes held to 32 lanes, and at 8.4 GB and not done after 4.5 minutes at the lanes the driver chose; the
// worst below the limit, 7a548525c239b91b (2,534 phis), took 531 s and 7.6 GB. In play the build would hold Intel's one
// compute build lane for the half hour and take the memory the game needs. Neither program is in the shipped state list
// or in this PC's play: nobody's recorded play has dispatched them. Their dispatches are left out, as a program the
// driver refuses.
constexpr uint32_t kIntelPhiLimit = 6000;   // (between the 2,650 that build in seconds to minutes and the 12,300 that never did)

/// A compute stage not given to the driver: Mesa's Intel, held to 32 lanes, over the limit (0: no limit). The mesh
/// fallback's stages are not judged here (fallback_size_policy.h)
inline bool too_big(bool intel_mesa, bool pinned, uint32_t phis, uint32_t limit) {
    return intel_mesa && pinned && limit && phis > limit;
}

}  // namespace compute_pin
