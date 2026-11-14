"""Run the production geometry and injected C without game data or a GPU.

python -I nx2/test_oot_wide.py [--cc clang]
"""
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import oot_wide

ROOT = Path(__file__).resolve().parents[1]
RUN_ALL_SKIP = {"windows": "compiles the Linux POSIX host shim"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="clang")
    args = parser.parse_args()
    source = r'''
#include <assert.h>
#include <stdarg.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "host/hos_wide.h"
#include "gpu/vk/oot_ui_squeeze.h"

typedef struct { uint64_t x[32]; uint8_t vreg[32][16]; } Ctx;
static uint8_t memory[4096];
float hos_aspect_ratio;
uint32_t hos_output_size(int height) { return height ? 1440 : 2560; }
void hos_log(const char *fmt, ...) { va_list args; va_start(args, fmt); vprintf(fmt, args); puts(""); va_end(args); }
static uint32_t recomp_load32(Ctx *c, uint64_t p) { (void)c; uint32_t v; memcpy(&v, memory + p, 4); return v; }
static uint64_t recomp_load64(Ctx *c, uint64_t p) { (void)c; uint64_t v; memcpy(&v, memory + p, 8); return v; }
static void recomp_store32(Ctx *c, uint64_t p, uint32_t v) { (void)c; memcpy(memory + p, &v, 4); }
static void a64_vset64(void *p, uint64_t v) { memcpy(p, &v, 8); memset((uint8_t *)p + 8, 0, 8); }
static void put(Ctx *c, int r, float f) { memcpy(c->vreg[r], &f, 4); }
static float get(Ctx *c, int r) { float f; memcpy(&f, c->vreg[r], 4); return f; }
static void eq(float a, float b) { if (fabsf(a-b) > 0.00001f) { fprintf(stderr, "%g != %g\n", a, b); assert(0); } }
'''
    for reg, base in ((1, 0), (3, 21), (3, 0), (1, 2)):
        source += (f"static void matrix_{reg}_{base}(Ctx *c) {{ "
                   + oot_wide._ratio(reg, base) + " }\n")
    source += "static void hud(Ctx *c) { " + oot_wide.HUD + " }\n"
    source += "static void movie(Ctx *c) { " + oot_wide.MOVIE + " }\n"
    source += "static void thumb(Ctx *c) { " + oot_wide.THUMB + " }\n"
    backend = (ROOT / "host/rx_backend.c").read_text()
    start = backend.index("void rx_resize(int width, int height) {")
    end = backend.index("\nconst char *rx_describe", start)
    source += r'''
static int resize_calls, last_width, last_height;
static void observed_resize(int width, int height) { ++resize_calls; last_width=width; last_height=height; }
static struct { void (*resize)(int, int); } renderer = {observed_resize}, *vk = &renderer;
static void wgr_resize(int width, int height) { observed_resize(width,height); }
'''
    source += backend[start:end] + "\n"

    source += r'''
int main(void) {
    hos_wide_window = 1;
    const unsigned windows[][2] = {{1920,1080},{2560,1080},{3440,1440},{5120,1440},
        {1920,1200},{1600,1200},{2448,1848},{1150,1000},{800,1200},{7680,1080},{1000,1000}};
    void (*matrices[])(Ctx *) = {matrix_1_0, matrix_3_21, matrix_3_0, matrix_1_2};
    const unsigned regs[] = {1,3,3,1}, bases[] = {0,21,0,2};
    for (unsigned i=0; i<sizeof windows/sizeof windows[0]; ++i) {
        const unsigned w = windows[i][0], h = windows[i][1];
        HosWideSize size = hos_wide_window_size(w, h, 1440);
        // The game's BaseResolution/upscale network still uses 1920x1080.
        // Vert+ grows height; it must not shrink targets below those constants.
        assert((uint64_t)(uint32_t)size.picture * (size.picture >> 32) <= hos_wide_max_px());
        assert((uint32_t)size.picture >= 1920);
        assert((uint32_t)size.scene >= 1440);
        assert((uint32_t)size.picture % 8 == 0 && (uint32_t)size.scene % 8 == 0);
        assert(fabs((double)(uint32_t)size.picture / (size.picture >> 32) - hos_wide_clamp((double)w/h)) <= 0.01);
        eq(size.aspect, (float)hos_wide_clamp((double)w/h));
        hos_wide_resize(w, h);
        const float shape = size.aspect / (16.0f/9.0f);
        Ctx context = {0}, *c = &context;
        for (unsigned m=0; m<4; ++m) {
            const unsigned r=regs[m], b=bases[m];
            c->x[b]=1024;
            const float original_half=atanf(0.5f), original_fsc[3]={2*original_half,sinf(original_half),cosf(original_half)};
            memcpy(memory+1024+0xa0,original_fsc,sizeof original_fsc);
            put(c,r,16.0f/9.0f); put(c,r-1,0.5f);
            // Re-reading the fields written for culling must not compound FOV.
            for (unsigned updated=0; updated<2; ++updated) {
                matrices[m](c);
                eq(get(c,r),size.aspect);
                const float tangent = get(c,r-1);
                eq(tangent,shape < 1 ? 0.5f/shape : 0.5f);
                // Narrow: tan(hfov/2) stays exactly the 16:9 value (Vert+).
                eq(tangent * size.aspect,shape < 1 ? 0.5f*16.0f/9.0f : 0.5f*size.aspect);
                uint32_t u = recomp_load32(c,1024+0xb0); float stored; memcpy(&stored,&u,4);
                eq(stored,size.aspect);
                u = recomp_load32(c,1024+0xac); memcpy(&stored,&u,4);
                eq(stored,tangent);
                // Culling also reads fovy, sin(fovy/2), cos(fovy/2), not just tan.
                float fsc[3]; memcpy(fsc,memory+1024+0xa0,sizeof fsc);
                const float half=atanf(tangent);
                eq(fsc[0],2*half); eq(fsc[1],sinf(half)); eq(fsc[2],cosf(half));
                c->x[b]=1536+m*256;
                put(c,r,1.0f); put(c,r-1,0.5f); matrices[m](c);
                eq(get(c,r),1.0f); eq(get(c,r-1),0.5f);
                c->x[b]=1024;
                u=recomp_load32(c,1024+0xac); memcpy(c->vreg[r-1],&u,4);
                u=recomp_load32(c,1024+0xb0); memcpy(c->vreg[r],&u,4);
            }
        }
    }
    // The instruction loads q1 and q4, NOT q4+4..q5+4 (#2015).
    // Scale every lane of q4; the neighbouring q5 register must remain untouched.
    for (unsigned i=0; i<sizeof windows/sizeof windows[0]; ++i) {
        const float aspect=(float)hos_wide_clamp((double)windows[i][0]/windows[i][1]), shape=aspect/(16.0f/9.0f);
        hos_wide_resize(windows[i][0],windows[i][1]);
        Ctx c={0}; c.x[0]=512;
        const float x[4]={2.0f/3840,0,0,0}, y[4]={3,2.0f/2160,5,7}, sentinel[4]={11,13,17,19};
        memcpy(c.vreg[1],x,16);memcpy(c.vreg[4],y,16);memcpy(c.vreg[5],sentinel,16);
        memset(memory,0,sizeof memory);
        hud(&c);
        float result[4];memcpy(result,c.vreg[4],16);
        for (int k=0;k<4;++k) eq(result[k],y[k]*(shape<1?shape:1));
        assert(!memcmp(c.vreg[5],sentinel,16));
        eq(get(&c,1),x[0]*(shape>1?1/shape:1)*OOT_UI_MARK);
        // A submitted canvas, cached by the game, follows each resize at replay.
        float block[36]={0};
        block[0]=block[16]=get(&c,1);block[5]=result[1];block[21]=-result[1];
        block[10]=block[26]=-1.0f/150;block[15]=block[31]=1;
        block[32]=block[34]=3840;block[33]=block[35]=2160;
        for (unsigned j=0;j<sizeof windows/sizeof windows[0];++j) {
            const float next=(float)windows[j][0]/windows[j][1], ratio=next/(16.0f/9.0f);
            assert(oot_ui_squeeze((unsigned char*)block,sizeof block,next));
            eq(block[0],x[0]*(ratio>1?1/ratio:1)*OOT_UI_MARK);
            eq(block[5],y[1]*(ratio<1?ratio:1));
            eq(block[21],-block[5]);
            float kept[36];memcpy(kept,block,sizeof block);
            assert(oot_ui_squeeze((unsigned char*)block,sizeof block,next));
            assert(!memcmp(kept,block,sizeof block));
        }
        // Full-screen canvases and unrelated buffers stay unchanged.
        block[0]=block[16]=2.0f/3840;
        float kept[36];memcpy(kept,block,sizeof block);
        assert(!oot_ui_squeeze((unsigned char*)block,sizeof block,aspect));
        assert(!memcmp(kept,block,sizeof block));
        assert(!oot_ui_squeeze((unsigned char*)block,sizeof block,0));
        assert(!oot_ui_squeeze((unsigned char*)block,sizeof block,NAN));
        assert(!oot_ui_squeeze((unsigned char*)block,128,aspect));
    }
    const HosWideSize four_k = hos_wide_window_size(3840,2160,2160);
    assert(four_k.picture == ((uint64_t)2160 << 32 | 3840));
    assert(four_k.scene == ((uint64_t)1620 << 32 | 2880));
    assert(hos_wide_window_size(0,1080,1440).picture == 0);
    assert(hos_wide_window_size(1920,0,1440).picture == 0);
    assert(hos_wide_window_size(1920,1080,0).picture == 0);
    // Live changes revisit a projection's stored fields, including when a menu
    // was not visited at the intermediate window sizes. No FOV compounding.
    float tangent = 0.5f, aspect = 16.0f/9.0f;
    const unsigned sizes[][2] = {{1600,1200},{3440,1440},{1150,1000},{1920,1080}};
    for (unsigned loop=0; loop<100; ++loop) {
        const unsigned k=loop%4;
        hos_wide_resize(sizes[k][0],sizes[k][1]);
        assert(hos_wide_projection(0x12345678,&tangent,&aspect));
        const float want=hos_wide_aspect();
        eq(aspect,want); eq(tangent,want < 16.0f/9.0f ? 0.5f*(16.0f/9.0f)/want : 0.5f);
        assert(hos_wide_projection(0x12345678,&tangent,&aspect));
        eq(tangent,want < 16.0f/9.0f ? 0.5f*(16.0f/9.0f)/want : 0.5f);
    }
    float delayed_t=0.5f, delayed_a=16.0f/9.0f;
    hos_wide_resize(1600,1200); assert(hos_wide_projection(0x76543210,&delayed_t,&delayed_a));
    hos_wide_resize(3440,1440); hos_wide_resize(1150,1000); hos_wide_resize(1920,1200);
    assert(hos_wide_projection(0x76543210,&delayed_t,&delayed_a));
    eq(delayed_a,1.6f); eq(delayed_t,0.5f*(16.0f/9.0f)/1.6f);
    // Minimize does not publish zero/NaN or lose the previous valid shape.
    hos_wide_resize(0,0); eq(hos_wide_aspect(),1.6f);
    for (unsigned i=0; i<1024; ++i) {
        float t=0.5f, a=16.0f/9.0f;
        assert(hos_wide_projection(0x10000000+i*256,&t,&a));
    }
    hos_wide_start(1920,1080);
    extern volatile uint64_t hos_wide_out;
    const uint64_t initial=hos_wide_out;
    hos_wide_resize(2448,1848);
    assert(hos_wide_out == initial); // no guest target recreation on a live resize
    eq(hos_wide_aspect(),2448.0f/1848.0f);
    // Exercise the production host callback, not only the aspect setter.
    rx_resize(1600,1200); eq(hos_wide_aspect(),1600.0f/1200.0f);
    assert(resize_calls == 1 && last_width == 1600 && last_height == 1200);
    rx_resize(0,0); rx_resize(-1,200); eq(hos_wide_aspect(),1600.0f/1200.0f);
    assert(resize_calls == 1);
    vk = NULL; rx_resize(3440,1440); eq(hos_wide_aspect(),3440.0f/1440.0f);
    assert(resize_calls == 2 && last_width == 3440 && last_height == 1440);
    assert(hos_wide_out == initial);
    // Execute MOVIE and THUMB after a resize; the target/jitter ratio stays fixed.
    hos_wide_start(1280,720);
    extern volatile float hos_wide_ratio, hos_wide_margin;
    const float jitter = hos_wide_ratio;
    const unsigned live[][2] = {{2520,1080},{2448,1848},{1280,720}};
    for (unsigned i=0;i<3;++i) {
        hos_wide_resize(live[i][0],live[i][1]);
        const float ratio=hos_wide_aspect();
        Ctx c={0}; c.x[29]=128;
        const float left=0,right=1;
        memcpy(memory+96,&left,4);memcpy(memory+104,&right,4);
        movie(&c);
        float l,r;memcpy(&l,memory+96,4);memcpy(&r,memory+104,4);
        const float margin=ratio>16.0f/9.0f?(1-(16.0f/9.0f)/ratio)/2:0;
        eq(l,margin);eq(r,1-margin);eq(hos_wide_margin,margin);
        c.x[3]=543;c.x[4]=306;thumb(&c);
        assert(c.x[3] == (ratio>16.0f/9.0f?(unsigned)(543*ratio/(16.0f/9.0f)+0.5f):543));
        assert(c.x[4] == (ratio<16.0f/9.0f?(unsigned)(306*(16.0f/9.0f)/ratio+0.5f):306));
        eq(hos_wide_ratio,jitter);
    }
    puts("PASS: live movie/thumbnail, 11 shapes, 4 matrix sites, live host callbacks and 1024 cached views");
}
'''
    with tempfile.TemporaryDirectory(prefix="oot-wide-") as temp:
        path = Path(temp)
        fixture, exe = path / "wide.c", path / "wide"
        fixture.write_text(source)
        subprocess.run([args.cc, "-std=c11", "-Wall", "-Wextra", "-Werror", "-D_GNU_SOURCE", "-I", str(ROOT), "-I", str(ROOT / "host/posix"),
                        str(fixture), str(ROOT / "host/hos_wide.c"), "-pthread", "-lm", "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    main()
