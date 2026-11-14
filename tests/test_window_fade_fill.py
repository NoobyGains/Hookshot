"""Run the loading pane's injected size hook and real canvas projection, game-free."""
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "nx2"))
import oot_wide


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="clang")
    args = parser.parse_args()
    hook = next((text for off, _, text in oot_wide.SITES if off == 0x152ac40), "(void)c;")
    source = r'''
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "gpu/vk/oot_ui_squeeze.h"
typedef struct { uint64_t x[32]; uint8_t vreg[32][16]; } Ctx;
static uint8_t memory[8192];
int hos_wide_window;
volatile uint32_t hos_wide_keep_mask;
volatile float hos_wide_squeeze;
volatile uint64_t hos_wide_cover_screen;   /* (the HUD site notes the loading cover's screen) */
static float aspect;
float hos_wide_aspect(void) { return aspect; }
uint64_t recomp_load64(Ctx *c, uint64_t a) { (void)c; uint64_t v; assert(a+8<=sizeof memory); memcpy(&v,memory+a,8); return v; }
uint32_t recomp_load32(Ctx *c, uint64_t a) { (void)c; uint32_t v; assert(a+4<=sizeof memory); memcpy(&v,memory+a,4); return v; }
uint8_t recomp_load8(Ctx *c, uint64_t a) { (void)c; assert(a<sizeof memory); return memory[a]; }
static void put64(uint64_t a, uint64_t v) { memcpy(memory+a,&v,8); }
static void put32(uint64_t a, uint32_t v) { memcpy(memory+a,&v,4); }
static void putf(uint64_t a, float v) { memcpy(memory+a,&v,4); }
static float lane(Ctx *c, int r) { float v; memcpy(&v,c->vreg[r],4); return v; }
static void eq(float a, float b) { if (fabsf(a-b)>0.001f) { fprintf(stderr,"FAIL: %g != %g\n",a,b); assert(0); } }
FADE_IMPLEMENTATION
static void size(Ctx *c) { SIZE_HOOK }
static void hud(Ctx *c) { HUD_HOOK }
static void pane(Ctx *c, float w, float h) {
    memset(c,0,sizeof *c); c->x[0]=512;
    memcpy(c->vreg[0],&w,4); memcpy(c->vreg[1],&h,4);
    putf(512+0x58,w); putf(512+0x5c,h);
    putf(512+0x28,1); putf(512+0x38,1);
    putf(512+0x4c,0); putf(512+0x50,0);
    put32(512+0xa8,(1u<<22)|(40u<<11)); // picture; origin 40 decodes to centre/centre (base 3)
    put64(512+0x18,1024); put64(1024+0xf8,2048); put64(2048+0x18,3072);
    strcpy((char*)memory+3072,"LoadingFade_00");
}
static void projection(float block[36], uint64_t vt) {
    Ctx c={0}; c.x[0]=4096;
    put64(4096-0x1b8,vt);
    const float x=2.0f/3840,y=2.0f/2160;
    memcpy(c.vreg[1],&x,4);memcpy(c.vreg[4]+4,&y,4);hud(&c);
    memset(block,0,36*sizeof(float));
    block[0]=block[16]=lane(&c,1);memcpy(&block[5],c.vreg[4]+4,4);block[21]=-block[5];
    block[15]=block[31]=1;block[32]=block[34]=3840;block[33]=block[35]=2160;
}
int main(void) {
    const float shapes[]={2448.0f/1848,4.0f/3,5.0f/4,16.0f/9,21.0f/9,32.0f/9,48.0f/9};
    for (int window=0;window<=1;++window) for (int mode=0;mode<3;++mode) {
        hos_wide_window=window;hos_wide_keep_mask=mode ? 0x5 : 0xf;
        for (unsigned i=0;i<sizeof shapes/sizeof shapes[0];++i) {
            aspect=shapes[i];hos_wide_squeeze=aspect>16.0f/9 ? (16.0f/9)/aspect : 1;
            Ctx c;pane(&c,3840,2160);size(&c);
            float block[36];projection(block,LOADING_VTABLE);
            if (window) {
                oot_ui_squeeze((unsigned char*)block,sizeof block,aspect);
                // Full fade coverage on both axes, while its canvas/icon remain fitted.
                eq(lane(&c,0)*block[0],2.0f);eq(lane(&c,1)*block[5],2.0f);
            } else { eq(lane(&c,0),3840);eq(lane(&c,1),2160); }
            // The event fade has always kept the entire picture.
            projection(block,EVENT_VTABLE);eq(block[0]*3840,2);eq(block[5]*2160,2);
            // The icon's size and every byte of its guest pane stay unchanged.
            pane(&c,80,80);uint8_t saved[sizeof memory];memcpy(saved,memory,sizeof memory);size(&c);
            eq(lane(&c,0),80);eq(lane(&c,1),80);assert(!memcmp(saved,memory,sizeof memory));
            // A same-sized pane in another layout is not a fade.
            pane(&c,3840,2160);strcpy((char*)memory+3072,"PauseMenu_00");size(&c);
            eq(lane(&c,0),3840);eq(lane(&c,1),2160);
            // Off-centre and non-spanning loading panes are not enlarged.
            pane(&c,3840,2160);putf(512+0x4c,200);size(&c);eq(lane(&c,0),3840);eq(lane(&c,1),2160);
            pane(&c,3840,50);size(&c);eq(lane(&c,0),3840);eq(lane(&c,1),50);
        }
    }
    // Repeated resize cycles use authored dimensions, never grow cumulatively.
    hos_wide_window=1;hos_wide_keep_mask=5;
    for (int n=0;n<50;++n) {
        aspect=shapes[n%7];Ctx c;pane(&c,3840,2160);size(&c);
        const float shape=aspect/(16.0f/9);
        eq(lane(&c,0),3840*(shape>1 ? shape : 1));eq(lane(&c,1),2160*(shape<1 ? 1/shape : 1));
        float w;memcpy(&w,memory+512+0x58,4);eq(w,3840);
    }
    puts("PASS: Window fades fill both axes; icons, unrelated panes, event fades and Monitor unchanged");
}
'''
    implementation = ROOT / "host/hos_wide_fade.c"
    text = implementation.read_text().replace('#include "hos.h"', '') if implementation.exists() else ''
    source = source.replace("FADE_IMPLEMENTATION", text).replace("SIZE_HOOK", hook).replace("HUD_HOOK", oot_wide.HUD)
    source = source.replace("LOADING_VTABLE", hex(oot_wide.KEEP_VTABLES[3])).replace("EVENT_VTABLE", hex(oot_wide.KEEP_VTABLES[2]))
    with tempfile.TemporaryDirectory(prefix="window-fade-") as temp:
        fixture, exe = Path(temp)/"test.c", Path(temp)/"test"
        fixture.write_text(source)
        subprocess.run([args.cc,"-std=c11","-Wall","-Wextra","-Werror","-D_CRT_SECURE_NO_WARNINGS","-I",str(ROOT),str(fixture),*([] if sys.platform=="win32" else ["-lm"]),"-o",str(exe)],check=True)
        subprocess.run([str(exe)],check=True)


if __name__ == "__main__":
    main()
