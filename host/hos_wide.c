/* nx2/oot_wide.py reads these when the game sizes its picture and builds views. */
#include "hos_wide.h"
#include <stdatomic.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>

void hos_log(const char *fmt, ...);

volatile uint64_t hos_wide_out, hos_wide_scene;
volatile float hos_wide_ratio, hos_wide_squeeze, hos_wide_margin;
volatile uint32_t hos_wide_keep_mask = 0xf;
static _Atomic float window_aspect;
int hos_wide_window = 0;
extern float hos_aspect_ratio;

float hos_wide_aspect(void) {
    const float live = atomic_load_explicit(&window_aspect, memory_order_relaxed);
    /* No window (HOS_HEADLESS): keep the picture/camera shape chosen at boot. */
    return hos_wide_window && live > 0.0f ? live : hos_aspect_ratio;
}

float hos_wide_thumb_ratio(void) { return hos_wide_window ? hos_wide_aspect() : hos_wide_ratio; }

void hos_wide_resize(unsigned width, unsigned height) {
    if (!hos_wide_window || !width || !height) return;
    const float aspect = (float)hos_wide_clamp((double)width / height);
    atomic_store_explicit(&window_aspect, aspect, memory_order_relaxed);
    const float shape = aspect / (16.0f / 9.0f);
    hos_wide_squeeze = shape < 1.0f ? 1.0f : 1.0f / shape;
    hos_wide_margin = (1.0f - hos_wide_squeeze) * 0.5f;
}

void hos_wide_start(unsigned width, unsigned height) {
    if (!hos_wide_window || !width || !height) return;
    uint32_t hos_output_size(int height);
    const HosWideSize size = hos_wide_window_size(width, height, hos_output_size(1));
    hos_wide_out = size.picture;
    hos_wide_scene = size.scene;
    hos_wide_ratio = size.aspect;
    hos_wide_resize(width, height);
    hos_log("display: fill window %ux%u, picture %ux%u, scene %ux%u, camera %.6f (%s)", width, height,
            (unsigned)size.picture, (unsigned)(size.picture >> 32), (unsigned)size.scene, (unsigned)(size.scene >> 32),
            (double)size.aspect, size.aspect < 16.0f / 9.0f ? "Vert+" : "Hor+");
}

/* Projection objects are reused and some are only visited after a menu opens.
   Remember each original tangent, not just the last window shape. Otherwise a
   narrow projection stored for culling grows its FOV again on every update. */
int hos_wide_projection(uint64_t projection, float *tangent, float *aspect) {
    typedef struct { uint64_t address; HosWideProjection view; } Entry;
    static SRWLOCK lock = SRWLOCK_INIT;
    static Entry *entries;
    static size_t count, capacity;
    static int allocation_reported;
    const float want = hos_wide_aspect();
    if (!(want > 0.0f)) return 0;
    AcquireSRWLockExclusive(&lock);
    size_t lo = 0, hi = count;
    while (lo < hi) {
        const size_t mid = lo + (hi - lo) / 2;
        if (entries[mid].address < projection) lo = mid + 1;
        else hi = mid;
    }
    const size_t i = lo;
    if (i == count || entries[i].address != projection) {
        /* Only original 16:9 views enter the table. In a square window an
           authored square shadow view must not be mistaken for our camera. */
        if (fabsf(*aspect - 16.0f / 9.0f) > 0.01f) {
            ReleaseSRWLockExclusive(&lock);
            return 0;
        }
        if (count == capacity) {
            const size_t next = capacity ? capacity * 2 : 64;
            Entry *grown = next > capacity && next <= SIZE_MAX / sizeof *entries
                         ? realloc(entries, next * sizeof *entries) : NULL;
            if (!grown) {
                if (!allocation_reported) {
                    allocation_reported = 1;
                    hos_log("display: cannot track projection originals; view left unchanged");
                }
                ReleaseSRWLockExclusive(&lock);
                return 0;
            }
            entries = grown;
            capacity = next;
        }
        memmove(entries + i + 1, entries + i, (count - i) * sizeof *entries);
        entries[i] = (Entry){projection, {0}};
        ++count;
    }
    const int changed = hos_wide_perspective(&entries[i].view, want, tangent, aspect);
    if (!changed) {
        /* This address now belongs to another kind of view. Do not retain its
           old patched aspect, or a later shadow view could look like a camera. */
        memmove(entries + i, entries + i + 1, (count - i - 1) * sizeof *entries);
        --count;
    }
    ReleaseSRWLockExclusive(&lock);
    return changed;
}
