// Mesh fallback compute stages too big for RADV on GCN 1-4 (vk_draw.cpp fallback_compute_pipelines). tests/test_fallback_size_policy.py
//
// On a card without mesh shaders a task or mesh program runs as a compute shader. A few of OoT's mesh programs are huge:
// 11,000 native blocks, which come out as about 28,000 SPIR-V blocks and 80,000 phis (93e3e999f2fb9fd8 and ea4dd64df9c8f2b7,
// 4.3 MB of SPIR-V each). Around 400 values are live at once, far over the 256 VGPRs and ~100 SGPRs a wave has, so ACO spills
// tens of thousands of them. RADV builds that in about 14 s and 2.9 GB on GFX9 and later (Vega, RDNA). On GFX6-8 (GCN 1-4:
// the RX 400/500 cards, R9 2xx/3xx/Fury) its spiller never finishes and grows past 25 GB, and the driver's thread keeps the
// memory: the shader preparation's precompile was killed by the OOM killer on an RX 580. The next biggest mesh programs have
// up to 29,400 phis and build there in 4-6 s and under 700 MB. Those cards are the ones RADV gives no 16-bit shader inputs
// and outputs (storageInputOutput16: packed 16-bit math, GFX9 on), which is how the device tells them apart.
//
// (hookshot) Mesa's Intel driver (Iris Xe, Mesa 26.2.4, 32 lanes) has its own: four mesh programs call a function of the
// translator's 251-263 times (2b152050cd96ce1d, 9bb6c724ae90c9cf, 48f1d2eeff6160fd, fbba1b21bfafa666: the lookup of a guest
// address among the stage's storage buffers, 137 instructions with a return for each buffer). The driver inlines every call,
// and its compiler took one of them alone to a 14 GB cap in 27 minutes, unfinished; two at once took the preparation's
// process to 19.8 GB on a 32 GB PC. The next most calls any mesh program makes are 153, and those build in seconds. So on
// that driver a stage with more than kIntelCallLimit calls is not built either (too_many_calls). Nor one of more than
// kIntelPhiLimit phis: alone, 93e3e999f2fb9fd8 (79,947 phis) reached a 14 GB cap in 8.5 minutes and ecbbff63280b68e2 (29,372)
// in 10, both unfinished, where 5c9454152ebde335 (16,837) built in 304 s.
#pragma once
#include <cstddef>
#include <cstdint>

namespace fallback_size {

// (between the 29,400 phis that build in seconds and the 80,000 that never finish)
constexpr uint32_t kRadvGcnPhiLimit = 50000;

// The OpPhi instructions in a SPIR-V module: the values merged where control flow joins, which is what grows with the
// blocks and the values live across them. 0 for a module that is not SPIR-V or is cut short.
inline uint32_t spirv_phis(const uint32_t* words, size_t count) {
    if (count < 5 || words[0] != 0x07230203u) return 0;
    uint32_t phis = 0;
    for (size_t at = 5; at < count;) {
        const uint32_t op = words[at] & 0xFFFFu, length = words[at] >> 16;
        if (length == 0 || length > count - at) return 0;
        phis += op == 245u;   // (OpPhi)
        at += length;
    }
    return phis;
}

// (hookshot, Mesa's Intel driver: between the 17,242 phis of the biggest it builds and the 28,506 of the next, which it did not
// finish within 14 GB)
constexpr uint32_t kIntelPhiLimit = 20000;

// (hookshot: between the 153 calls that build in seconds and the 251 that never finished)
constexpr uint32_t kIntelCallLimit = 200;

// The OpFunctionCall instructions in a SPIR-V module: each one a copy of its function once the driver has inlined it. 0 for a
// module that is not SPIR-V or is cut short.
inline uint32_t spirv_calls(const uint32_t* words, size_t count) {
    if (count < 5 || words[0] != 0x07230203u) return 0;
    uint32_t calls = 0;
    for (size_t at = 5; at < count;) {
        const uint32_t op = words[at] & 0xFFFFu, length = words[at] >> 16;
        if (length == 0 || length > count - at) return 0;
        calls += op == 57u;   // (OpFunctionCall)
        at += length;
    }
    return calls;
}

// RX_VK_FALLBACK_PHI_LIMIT's value: decimal digits only (no sign, no space, nothing after), at most 4294967295. false for
// anything else, which the caller ignores with a warning: atoi/strtoul read "off" as 0 (no limit) and "-1" as 4294967295
inline bool parse_limit(const char* text, uint32_t& out) {
    if (!text || !*text) return false;
    uint64_t v = 0;
    for (const char* c = text; *c; c++) {
        if (*c < '0' || *c > '9') return false;
        v = v * 10 + (uint64_t)(*c - '0');
        if (v > 0xFFFFFFFFull) return false;
    }
    out = (uint32_t)v;
    return true;
}

// A fallback compute stage not to give the driver: RADV on GCN 1-4 (or Mesa's Intel driver, with its own limit), over the limit
// (0: no limit). Its draws are left out, as
// for a pipeline the driver refuses.
inline bool too_big(bool radv_gcn, uint32_t phis, uint32_t limit) { return radv_gcn && limit && phis > limit; }

// (hookshot) A fallback compute stage not to give Mesa's Intel driver: more calls than the limit (0: no limit). Left out as above.
inline bool too_many_calls(bool mesa_intel, uint32_t calls, uint32_t limit) { return mesa_intel && limit && calls > limit; }

} // namespace fallback_size
