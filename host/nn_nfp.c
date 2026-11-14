/* (hookshot) nn::nfp, the console's NFC tag library, on a library of the player's own tag dumps.
 *
 * The game asks for an NFC tag with StartDetection, polls GetDeviceState until a tag is found, mounts it and reads what it
 * wants (GetTagInfo, GetModelInfo, the application area), then StopDetection. Here the reader is a pretended one: the tags
 * are files in the player's NFC folder (hos_nfc_dir: put there by hand), and the
 * Insert menu's NFC tab holds one of them to the reader (hos_nfc_tap), as tapping a figure on the controller does.
 *
 * A file is a dump of an NTAG215 tag: 540 bytes as they are on the tag (".bin", as most tools write them; 532 and 572 byte
 * ones too), or a Flipper Zero NFC file (".nfc": text, a "Page N: xx xx xx xx" line per page). The tag's UID and the figure's
 * model (pages 21 and 22) are plain on the tag and are all that is read from it. The rest of a real tag (its owner, its
 * write counter, the games' application areas) is encrypted with keys this code does not have and does not need: a tag here
 * is never written back, so what a game keeps on it (its application area, by the game's access ID) is kept in a file of
 * Hookshot's own beside the saves instead (user/nfc/<uid>.area), and an NFC tag is always shown as registered.
 *
 * Nothing of a dump leaves the PC, and none is in the repository. */
#include "hos.h"
#include "hos_paths.h"

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifndef _WIN32
#include <dirent.h>
#include <sys/stat.h>
#endif

void hos_event_init(uint64_t guest_event, int signaled, int clear_mode);   /* nn_os_sync.c */

#define NFC_MAX 256
#define TAG_SIZE 540          /* (an NTAG215's 135 pages) */
#define AREA_SIZE 0xd8        /* (an NFC tag's application area) */

/* nn::Result: module 115 (nfp), a description */
#define NFP_RESULT(desc) ((uint32_t)(115 | ((desc) << 9)))
#define NFP_DEVICE_NOT_FOUND NFP_RESULT(64)
#define NFP_WRONG_STATE NFP_RESULT(73)        /* (WrongDeviceState) */
#define NFP_AREA_NEEDS_CREATE NFP_RESULT(128) /* (ApplicationAreaIsNotInitialized) */
#define NFP_WRONG_ACCESS_ID NFP_RESULT(152)
#define NFP_AREA_EXISTS NFP_RESULT(168)

enum { ST_INIT = 0, ST_SEARCHING = 1, ST_FOUND = 2, ST_REMOVED = 3, ST_MOUNTED = 4, ST_UNAVAILABLE = 5 };

typedef struct {
    char name[128];   /* (the file's name without its ending, UTF-8: what the menu and the launcher show) */
    char path[600];
} NfcFile;

static SRWLOCK nfc_lk = SRWLOCK_INIT;
static NfcFile nfc_files[NFC_MAX];
static int nfc_n;
static int64_t nfc_listed_ns;
static uint8_t tag[TAG_SIZE];
static char tag_name[128];
static int tag_held;          /* (a tag is at the reader: the menu's tap) */
static int dev_state = ST_INIT, nfp_ready;
static uint8_t area[AREA_SIZE];
static uint32_t area_id;
static int area_there, area_open;

/* The NFC tag folder: HOOKSHOT_NFC_DIR; else %LOCALAPPDATA%\Hookshot\nfc (Windows), $XDG_DATA_HOME/hookshot/nfc
   (Linux, ~/.local/share by default): every build of the game and the launcher share it */
const char *hos_nfc_dir(void) {
    static char dir[520];
    if (dir[0]) return dir;
    const char *e = getenv("HOOKSHOT_NFC_DIR");
    if (e && *e) {
        snprintf(dir, sizeof dir, "%s", e);
        return dir;
    }
#ifdef _WIN32
    wchar_t w[MAX_PATH];
    const DWORD n = GetEnvironmentVariableW(L"LOCALAPPDATA", w, MAX_PATH);
    char base[400] = "";
    if (n && n < MAX_PATH) WideCharToMultiByte(CP_UTF8, 0, w, -1, base, sizeof base, NULL, NULL);
    snprintf(dir, sizeof dir, "%s\\Hookshot\\nfc", base[0] ? base : ".");
#else
    const char *xdg = getenv("XDG_DATA_HOME"), *home = getenv("HOME");
    if (xdg && *xdg) snprintf(dir, sizeof dir, "%s/hookshot/nfc", xdg);
    else snprintf(dir, sizeof dir, "%s/.local/share/hookshot/nfc", home && *home ? home : ".");
#endif
    return dir;
}

static FILE *open_utf8(const char *path, const char *mode) {
#ifdef _WIN32
    wchar_t w[700], m[8];
    if (!MultiByteToWideChar(CP_UTF8, 0, path, -1, w, 700) || !MultiByteToWideChar(CP_UTF8, 0, mode, -1, m, 8)) return NULL;
    return _wfopen(w, m);
#else
    return fopen(path, mode);
#endif
}

static int tag_ending(const char *name) {   /* (the length of the name without ".bin" or ".nfc"; 0: not a tag's file) */
    const size_t n = strlen(name);
    if (n < 5) return 0;
    const char *e = name + n - 4;
    if (e[0] != '.') return 0;
    char low[4] = {(char)tolower((unsigned char)e[1]), (char)tolower((unsigned char)e[2]), (char)tolower((unsigned char)e[3]), 0};
    return !strcmp(low, "bin") || !strcmp(low, "nfc") ? (int)(n - 4) : 0;
}
/* (by name, letters' case aside, as the launcher's NFC page lists them) */
static int by_name(const void *a, const void *b) {
    const unsigned char *x = (const unsigned char *)((const NfcFile *)a)->name, *y = (const unsigned char *)((const NfcFile *)b)->name;
    for (; *x && *y; x++, y++) {
        const int d = toupper(*x) - toupper(*y);
        if (d) return d;
    }
    return *x ? 1 : *y ? -1 : strcmp(((const NfcFile *)a)->name, ((const NfcFile *)b)->name);
}

/* A file of the folder, when it is a tag's by its name. The list holds NFC_MAX at the most, and they are the first by name
   whatever order the folder gives its files in: once it is full, a file takes the place of the last by name when it comes
   before it. (It stopped taking files at NFC_MAX while the folder was still being read, and sorted after: past 256 files
   the menu had whichever the folder gave first, and the launcher's page could not say which.) */
static void add_file(const char *dir, const char *name) {
    const int stem = tag_ending(name);
    if (!stem || (tolower((unsigned char)name[0]) == 'k' && tolower((unsigned char)name[1]) == 'e' &&
                  tolower((unsigned char)name[2]) == 'y' && name[3] == '_')) return;   /* (key_retail.bin: a key file, not a tag) */
    NfcFile file;
    snprintf(file.name, sizeof file.name, "%.*s", stem > 120 ? 120 : stem, name);
#ifdef _WIN32
    snprintf(file.path, sizeof file.path, "%s\\%s", dir, name);
#else
    snprintf(file.path, sizeof file.path, "%s/%s", dir, name);
#endif
    if (nfc_n < NFC_MAX) {
        nfc_files[nfc_n++] = file;
        return;
    }
    int last = 0;
    for (int i = 1; i < nfc_n; i++)
        if (by_name(&nfc_files[i], &nfc_files[last]) > 0) last = i;
    if (by_name(&file, &nfc_files[last]) < 0) nfc_files[last] = file;
}

/* The folder listed again, at most once a second (nfc_lk held) */
static void list_files(void) {
    const int64_t now = hos_now_ns();
    if (nfc_listed_ns && now - nfc_listed_ns < 1000000000LL) return;
    nfc_listed_ns = now ? now : 1;
    nfc_n = 0;
    const char *dir = hos_nfc_dir();
#ifdef _WIN32
    char pattern[560];
    wchar_t w[700];
    snprintf(pattern, sizeof pattern, "%s\\*", dir);
    if (!MultiByteToWideChar(CP_UTF8, 0, pattern, -1, w, 700)) return;
    WIN32_FIND_DATAW fd;
    const HANDLE h = FindFirstFileW(w, &fd);
    if (h == INVALID_HANDLE_VALUE) return;
    do {
        char name[400];
        if ((fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) || !WideCharToMultiByte(CP_UTF8, 0, fd.cFileName, -1, name, sizeof name, NULL, NULL))
            continue;
        add_file(dir, name);
    } while (FindNextFileW(h, &fd));
    FindClose(h);
#else
    DIR *d = opendir(dir);
    if (!d) return;
    for (struct dirent *e; (e = readdir(d)) != NULL;) add_file(dir, e->d_name);
    closedir(d);
#endif
    qsort(nfc_files, (size_t)nfc_n, sizeof nfc_files[0], by_name);
}

/* A tag's bytes from its file: 1 when it is an NTAG215 dump with an NFC tag's model on it */
static int load_tag(const char *path, uint8_t out[TAG_SIZE]) {
    FILE *f = open_utf8(path, "rb");
    if (!f) return 0;
    static uint8_t raw[16384];
    const size_t n = fread(raw, 1, sizeof raw - 1, f);
    fclose(f);
    raw[n] = 0;
    memset(out, 0, TAG_SIZE);
    int pages = 0;
    if (n > 20 && !memcmp(raw, "Filetype:", 9)) {   /* (a Flipper Zero NFC file) */
        for (const char *p = (const char *)raw; (p = strstr(p, "Page ")) != NULL; p += 5) {
            unsigned page, b[4];
            if (p != (const char *)raw && p[-1] != '\n') continue;
            if (sscanf(p, "Page %u: %x %x %x %x", &page, &b[0], &b[1], &b[2], &b[3]) != 5 || page >= TAG_SIZE / 4) continue;
            for (int k = 0; k < 4; k++) out[page * 4 + k] = (uint8_t)b[k];
            pages++;
        }
        if (pages < 130) return 0;
    } else if (n == 532 || n == 540 || n == 572) {
        memcpy(out, raw, n < TAG_SIZE ? n : TAG_SIZE);
    } else {
        return 0;
    }
    /* (an NFC tag: an NFC Forum type 2 tag whose capability container says NTAG215, and a model that ends in 02) */
    return out[0x0c] == 0xf1 && out[0x0d] == 0x10 && out[0x0e] == 0xff && out[0x0f] == 0xee && out[0x5b] == 0x02;
}

/* ---- the application area a game keeps on the tag: Hookshot's own file, by the tag's UID ------------------------------------ */
static void make_dir(const char *path) {
#ifdef _WIN32
    wchar_t w[700];
    if (MultiByteToWideChar(CP_UTF8, 0, path, -1, w, 700)) CreateDirectoryW(w, NULL);
#else
    mkdir(path, 0755);
#endif
}
static void area_path(char *out, size_t size) {   /* (UTF-8) */
    char exe[MAX_PATH * 3] = "";
#ifdef _WIN32
    wchar_t w[MAX_PATH];
    if (hos_game_path_w(w, MAX_PATH)) WideCharToMultiByte(CP_UTF8, 0, w, -1, exe, sizeof exe, NULL, NULL);
    const size_t n = strlen(exe);
#else
    const DWORD n = hos_game_path_a(exe, MAX_PATH);
#endif
    size_t dir = n;
    while (dir && exe[dir - 1] != '\\' && exe[dir - 1] != '/') dir--;
    snprintf(out, size, "%.*suser/nfc/%02x%02x%02x%02x%02x%02x%02x.area", (int)dir, exe, tag[0], tag[1], tag[2], tag[4], tag[5],
             tag[6], tag[7]);
}
static void area_load(void) {
    char path[MAX_PATH * 3 + 64];
    area_there = area_open = 0, area_id = 0;
    memset(area, 0, sizeof area);
    area_path(path, sizeof path);
    FILE *f = open_utf8(path, "rb");
    if (!f) return;
    uint8_t head[8];
    if (fread(head, 1, 8, f) == 8 && !memcmp(head, "LSA1", 4) && fread(area, 1, AREA_SIZE, f) == AREA_SIZE)
        memcpy(&area_id, head + 4, 4), area_there = 1;
    fclose(f);
}
static void area_save(void) {
    char path[MAX_PATH * 3 + 64], dir[MAX_PATH * 3 + 64];
    area_path(path, sizeof path);
    snprintf(dir, sizeof dir, "%s", path);
    char *slash = strrchr(dir, '/');
    if (slash) {
        *slash = 0;
        char *up = strrchr(dir, '/');   /* (user, then user/nfc) */
        if (up) {
            *up = 0;
            make_dir(dir);
            *up = '/';
        }
        make_dir(dir);
    }
    FILE *f = open_utf8(path, "wb");
    if (!f) {
        hos_log("nfp: the NFC tag's application area could not be kept (%s)", path);
        return;
    }
    fwrite("LSA1", 1, 4, f), fwrite(&area_id, 1, 4, f), fwrite(area, 1, AREA_SIZE, f);
    fclose(f);
}

/* ---- the Insert menu's side (MkwVkHost: nfc_count, nfc_name, nfc_tap, nfc_state) ---------------------------------------------- */
int hos_nfc_count(void) {
    AcquireSRWLockExclusive(&nfc_lk);
    list_files();
    const int n = nfc_n;
    ReleaseSRWLockExclusive(&nfc_lk);
    return n;
}
const char *hos_nfc_name(int index) {
    static char name[128];   /* (the menu's thread alone asks) */
    AcquireSRWLockExclusive(&nfc_lk);
    snprintf(name, sizeof name, "%s", index >= 0 && index < nfc_n ? nfc_files[index].name : "");
    ReleaseSRWLockExclusive(&nfc_lk);
    return name;
}
/* The NFC tag of that place in the list held to the reader (-1: taken away). 1: done; 0: its file is not a tag's */
int hos_nfc_tap(int index) {
    int ok = 1;
    AcquireSRWLockExclusive(&nfc_lk);
    if (index < 0 || index >= nfc_n) {
        if (tag_held) hos_log("nfp: the NFC tag \"%s\" taken off the reader", tag_name);
        tag_held = 0;
        if (dev_state == ST_FOUND || dev_state == ST_MOUNTED) dev_state = ST_REMOVED;
    } else if (load_tag(nfc_files[index].path, tag)) {
        snprintf(tag_name, sizeof tag_name, "%s", nfc_files[index].name);
        tag_held = 1;
        area_load();
        if (dev_state == ST_SEARCHING) dev_state = ST_FOUND;
        hos_log("nfp: the NFC tag \"%s\" held to the reader (model %02x%02x%02x%02x%02x%02x%02x%02x); the game %s", tag_name,
                tag[0x54], tag[0x55], tag[0x56], tag[0x57], tag[0x58], tag[0x59], tag[0x5a], tag[0x5b],
                dev_state == ST_FOUND ? "was waiting for one" : "is not asking for one now: it stays there until it does");
    } else {
        hos_log("nfp: \"%s\" is not an NFC tag's dump (an NTAG215's 540 bytes, or a Flipper NFC file of one)", nfc_files[index].name);
        ok = 0;
    }
    ReleaseSRWLockExclusive(&nfc_lk);
    return ok;
}
/* What the reader is doing, as bits: 1 the game uses NFC tags (nn::nfp started), 2 it is waiting for one now, 4 one is held
   to it, 8 the game has read it */
int hos_nfc_state(void) {
    AcquireSRWLockShared(&nfc_lk);
    const int s = (nfp_ready ? 1 : 0) | (dev_state == ST_SEARCHING ? 2 : 0) | (tag_held ? 4 : 0) | (dev_state == ST_MOUNTED ? 8 : 0);
    ReleaseSRWLockShared(&nfc_lk);
    return s;
}

/* ---- the Switch 2 Pro Controller's own reader (host/pad_switch2.c: the controller over USB) --------------------------------------
   While the game waits for a tag and none of the folder's is held to the pretended reader, the controller's reader looks for
   a real one: command 0x01's subcommands, as the controller answered them here (the community's notes name them without their
   answers: github.com/ndeadly/switch2_controller_research):
     0x03  start looking (data 00 e8 03 2c 01);  0x04  stop
     0x05  the state: byte 0 is 0 idle, 1 looking, 9 a tag found (then 01 01, the tag's type, its UID's length and UID at 4),
           4 a read done, 7 an error (its code in byte 1: 0x48 when the tag refuses the password)
     0x06  read: a timeout in ms (2 bytes), 7 bytes of zeros (any tag), 1 to log in with the figure tags' password first or 0
           not to, the number of page ranges and each one's first and last page
     0x15  what was read, from an offset (2 bytes): a byte 1 for the last part, the part's length, a zero, the bytes. 60 bytes
           of the tag's description come first, then the pages
   A tag is read with the password first, as a figure's tag wants, and without it when that is refused (a plain NTAG215). Only
   a tag that is a figure's (load_tag's test) is given to the game; nothing is ever written to one */
#ifdef _WIN32
int hos_switch2_command(const uint8_t *out, unsigned out_n, uint8_t *in, unsigned in_max);
int hos_switch2_connected(void);

static int reader_cmd(uint8_t sub, const uint8_t *data, unsigned n, uint8_t *in, unsigned in_max) {
    uint8_t out[40] = {0x01, 0x91, (uint8_t)(sub == 0x15 || sub == 0x0c ? 1 : 0), sub, 0x00, (uint8_t)n, 0x00, 0x00};
    if (n > sizeof out - 8) return -1;
    if (n) memcpy(out + 8, data, n);
    return hos_switch2_command(out, 8 + n, in, in_max);
}
static int reader_state(uint8_t st[24]) {
    uint8_t in[128];
    const int n = reader_cmd(0x05, NULL, 0, in, sizeof in);
    if (n < 8 + 16) return -1;
    memcpy(st, in + 8, 16);
    return st[0];
}
/* The tag at the controller read whole (135 pages): 1 when out holds its 540 bytes */
static int reader_read(int password, uint8_t out[TAG_SIZE]) {
    const uint8_t ask[19] = {0xd0, 0x07, 0, 0, 0, 0, 0, 0, 0, (uint8_t)(password ? 1 : 0), 0x03, 0x00, 0x3b, 0x3c, 0x77, 0x78, 0x86, 0, 0};
    uint8_t in[160], st[24], all[60 + TAG_SIZE + 96];
    if (reader_cmd(0x06, ask, sizeof ask, in, sizeof in) < 0) return 0;
    int state = 9;
    for (int i = 0; i < 40 && state != 4 && state != 7 && state >= 0; i++) Sleep(50), state = reader_state(st);
    if (state != 4) return 0;
    unsigned got = 0;
    for (int part = 0; part < 12 && got < 60 + TAG_SIZE; part++) {
        const uint8_t at[2] = {(uint8_t)(got & 0xff), (uint8_t)(got >> 8)};
        const int n = reader_cmd(0x15, at, 2, in, sizeof in);
        if (n < 12 || !in[9] || (unsigned)in[9] > (unsigned)n - 11 || got + in[9] > sizeof all) return 0;
        memcpy(all + got, in + 11, in[9]);
        got += in[9];
        if (in[8]) break;   /* (the last part) */
    }
    if (got < 60 + TAG_SIZE) return 0;
    memcpy(out, all + 60, TAG_SIZE);
    return 1;
}
/* ---- a scan: the tag on the controller copied into the player's folder (the Insert menu's Scan row) -------------------------- */
enum { SCAN_IDLE, SCAN_LOOKING, SCAN_SAVED, SCAN_NO_TAG, SCAN_NOT_A_FIGURE, SCAN_NO_CONTROLLER, SCAN_FAILED };
static volatile LONG scan_state = SCAN_IDLE, scan_asked;
static char scan_name[64];

static int reader_look(void) {   /* (looking started again) */
    static const uint8_t start[5] = {0x00, 0xe8, 0x03, 0x2c, 0x01};
    uint8_t in[64];
    reader_cmd(0x04, NULL, 0, in, sizeof in);
    Sleep(120);
    return reader_cmd(0x03, start, sizeof start, in, sizeof in) >= 0;
}
/* The tag at the reader, with the figure tags' password and, when that is refused, without: 1 when read */
static int reader_take(uint8_t out[TAG_SIZE]) {
    uint8_t st[24];
    if (reader_read(1, out)) return 1;
    if (!reader_look()) return 0;
    int s = 1;
    for (int i = 0; i < 20 && s != 9; i++) Sleep(50), s = reader_state(st);
    return s == 9 && reader_read(0, out);
}
static int is_figure(const uint8_t *t) { return t[0x0c] == 0xf1 && t[0x0d] == 0x10 && t[0x0e] == 0xff && t[0x0f] == 0xee && t[0x5b] == 0x02; }

/* Ten seconds for a tag to be held to the controller; a figure's is written to the folder as "Scanned <its UID>.bin" */
static void scan_run(void) {
    static uint8_t read[TAG_SIZE];
    uint8_t st[24];
    InterlockedExchange(&scan_state, SCAN_LOOKING);
    if (!hos_switch2_connected() || !reader_look()) {
        hos_log("nfp: scan: no Switch 2 Pro Controller over USB to read a tag with");
        InterlockedExchange(&scan_state, SCAN_NO_CONTROLLER);
        return;
    }
    hos_log("nfp: scan: waiting ten seconds for a tag on the controller");
    int state = 1;
    for (int i = 0; i < 100 && state != 9; i++) {
        Sleep(100);
        state = reader_state(st);
        if (state == 0 || state == 7) reader_look();
    }
    if (state != 9) {
        uint8_t in[64];
        reader_cmd(0x04, NULL, 0, in, sizeof in);
        hos_log("nfp: scan: no tag was held to the controller");
        InterlockedExchange(&scan_state, SCAN_NO_TAG);
        return;
    }
    if (!reader_take(read)) {
        hos_log("nfp: scan: the tag (UID %02x%02x%02x%02x%02x%02x%02x) could not be read", st[9], st[10], st[11], st[12], st[13], st[14], st[15]);
        InterlockedExchange(&scan_state, SCAN_FAILED);
        return;
    }
    if (!is_figure(read)) {
        hos_log("nfp: scan: the tag (UID %02x%02x%02x%02x%02x%02x%02x) was read, but it is not a figure's tag: not saved", read[0], read[1],
                read[2], read[4], read[5], read[6], read[7]);
        InterlockedExchange(&scan_state, SCAN_NOT_A_FIGURE);
        return;
    }
    char path[700];
    snprintf(scan_name, sizeof scan_name, "Scanned %02X%02X%02X%02X%02X%02X%02X", read[0], read[1], read[2], read[4], read[5], read[6], read[7]);
    make_dir(hos_nfc_dir());
#ifdef _WIN32
    snprintf(path, sizeof path, "%s\\%s.bin", hos_nfc_dir(), scan_name);
#else
    snprintf(path, sizeof path, "%s/%s.bin", hos_nfc_dir(), scan_name);
#endif
    FILE *f = open_utf8(path, "wb");
    if (!f || fwrite(read, 1, TAG_SIZE, f) != TAG_SIZE) {
        if (f) fclose(f);
        hos_log("nfp: the scanned tag could not be written to %s", path);
        InterlockedExchange(&scan_state, SCAN_FAILED);
        return;
    }
    fclose(f);
    AcquireSRWLockExclusive(&nfc_lk);
    nfc_listed_ns = 0;   /* (the folder listed again when next asked) */
    ReleaseSRWLockExclusive(&nfc_lk);
    hos_log("nfp: the tag on the controller was scanned into the folder as \"%s\" (model %02x%02x%02x%02x%02x%02x%02x%02x)", scan_name,
            read[0x54], read[0x55], read[0x56], read[0x57], read[0x58], read[0x59], read[0x5a], read[0x5b]);
    InterlockedExchange(&scan_state, SCAN_SAVED);
}

static DWORD WINAPI reader_main(LPVOID unused) {
    (void)unused;
    int looking = 0, told_plain = 0, away = 0;
    uint8_t seen_uid[7] = {0};
    for (;;) {
        Sleep(100);
        if (InterlockedExchange(&scan_asked, 0)) {
            scan_run();
            looking = 0;
            continue;
        }
        AcquireSRWLockShared(&nfc_lk);
        const int want = nfp_ready && dev_state == ST_SEARCHING && !tag_held;
        ReleaseSRWLockShared(&nfc_lk);
        if (!hos_switch2_connected()) {
            looking = 0;
            continue;
        }
        uint8_t in[64], st[24];
        if (!want) {
            if (looking) reader_cmd(0x04, NULL, 0, in, sizeof in), looking = 0;
            continue;
        }
        if (!looking) {
            static const uint8_t start[5] = {0x00, 0xe8, 0x03, 0x2c, 0x01};
            reader_cmd(0x04, NULL, 0, in, sizeof in);
            Sleep(120);
            if (reader_cmd(0x03, start, sizeof start, in, sizeof in) < 0) continue;
            looking = 1;
        }
        const int state = reader_state(st);
        if (state == 0 || state == 7) looking = 0;   /* (it gave up, or stopped on an error: started again) */
        if (state != 9) {
            if (state == 1 && ++away > 15) memset(seen_uid, 0, sizeof seen_uid), told_plain = 0;   /* (the tag was taken away) */
            continue;
        }
        away = 0;
        if (!memcmp(seen_uid, st + 9, 7) && told_plain) continue;   /* (the same tag that was no figure's: not read again) */
        memcpy(seen_uid, st + 9, 7);
        static uint8_t read[TAG_SIZE];
        const int ok = reader_take(read);
        looking = 0;
        const int figure = ok && is_figure(read);
        if (!figure) {
            if (!told_plain)
                hos_log(ok ? "nfp: the tag on the controller (UID %02x%02x%02x%02x%02x%02x%02x) was read, but it is not a figure's tag: the game "
                             "is not given it" : "nfp: the tag on the controller (UID %02x%02x%02x%02x%02x%02x%02x) could not be read",
                        seen_uid[0], seen_uid[1], seen_uid[2], seen_uid[3], seen_uid[4], seen_uid[5], seen_uid[6]);
            told_plain = 1;
            continue;
        }
        AcquireSRWLockExclusive(&nfc_lk);
        if (dev_state == ST_SEARCHING && !tag_held) {
            memcpy(tag, read, TAG_SIZE);
            snprintf(tag_name, sizeof tag_name, "Tag on the controller");
            tag_held = 1;
            area_load();
            dev_state = ST_FOUND;
            hos_log("nfp: a tag read on the controller (model %02x%02x%02x%02x%02x%02x%02x%02x): given to the game", tag[0x54], tag[0x55],
                    tag[0x56], tag[0x57], tag[0x58], tag[0x59], tag[0x5a], tag[0x5b]);
        }
        ReleaseSRWLockExclusive(&nfc_lk);
    }
    return 0;
}
static void reader_start(void) {
    static LONG started;
    if (!InterlockedExchange(&started, 1)) CreateThread(NULL, 0, reader_main, NULL, 0, NULL);
}
/* The Insert menu's Scan row (MkwVkHost.nfc_scan): start 1 begins a scan; returns its state (SCAN_*: 0 none, 1 looking for a
   tag, 2 saved, 3 no tag in ten seconds, 4 the tag is no figure's, 5 no controller, 6 failed). The saved file's name: hos_nfc_scan_name */
int hos_nfc_scan(int start) {
    if (start && scan_state != SCAN_LOOKING) {
        reader_start();
        InterlockedExchange(&scan_state, SCAN_LOOKING);
        InterlockedExchange(&scan_asked, 1);
    }
    return (int)scan_state;
}
const char *hos_nfc_scan_name(void) { return scan_name; }
#else
static void reader_start(void) {}
int hos_nfc_scan(int start) {
    (void)start;
    return 5;
}
const char *hos_nfc_scan_name(void) { return ""; }
#endif

/* ---- nn::nfp ------------------------------------------------------------------------------------------------------------------ */
static int traced(void) {
    static int on = -1;
    if (on < 0) on = getenv("HOS_NFP_TRACE") != NULL && atoi(getenv("HOS_NFP_TRACE")) != 0;
    return on;
}
#define NFP_TRACE(...) do { if (traced()) hos_log(__VA_ARGS__); } while (0)

HLE(_ZN2nn3nfp10InitializeEv) {
    AcquireSRWLockExclusive(&nfc_lk);
    nfp_ready = 1, dev_state = ST_INIT;
    /* (HOS_NFP_SEARCH=1, a test's: the reader looks for a tag from the start, without the game's NFC screen) */
    if (getenv("HOS_NFP_SEARCH") && atoi(getenv("HOS_NFP_SEARCH"))) dev_state = ST_SEARCHING;
    ReleaseSRWLockExclusive(&nfc_lk);
    reader_start();
    hos_log("nfp: the game uses NFC tags: the Insert menu's NFC tab holds one of %s's to the reader", hos_nfc_dir());
}
HLE(_ZN2nn3nfp8FinalizeEv) {
    AcquireSRWLockExclusive(&nfc_lk);
    nfp_ready = 0, dev_state = ST_INIT;
    ReleaseSRWLockExclusive(&nfc_lk);
}
/* (the reader coming and going: it is always there. Made, and signalled once, so a game that waits for it goes on) */
HLE(_ZN2nn3nfp29AttachAvailabilityChangeEventEPNS_2os15SystemEventTypeE) {
    hos_event_init(ARG(0), 1, 1);
    RET(0);
}
/* ListDevices(DeviceHandle *out, int *count, int max): the one reader, the first controller's */
HLE(_ZN2nn3nfp11ListDevicesEPNS0_12DeviceHandleEPii) {
    if ((int)ARG(2) < 1 || !ARG(0)) {
        if (ARG(1)) *(int32_t *)GP(ARG(1)) = 0;
        RET(NFP_DEVICE_NOT_FOUND);
        return;
    }
    memset(GP(ARG(0)), 0, 8);   /* (DeviceHandle: 8 bytes, the npad's id first: No.1) */
    if (ARG(1)) *(int32_t *)GP(ARG(1)) = 1;
    RET(0);
}
HLE(_ZN2nn3nfp9GetNpadIdEPjRKNS0_12DeviceHandleE) {
    if (ARG(0)) *(uint32_t *)GP(ARG(0)) = 0;
    RET(0);
}
HLE(_ZN2nn3nfp14GetDeviceStateERKNS0_12DeviceHandleE) {
    AcquireSRWLockShared(&nfc_lk);
    const int s = nfp_ready ? dev_state : ST_UNAVAILABLE;
    ReleaseSRWLockShared(&nfc_lk);
    RET(s);
}
HLE(_ZN2nn3nfp14StartDetectionERKNS0_12DeviceHandleE) {
    AcquireSRWLockExclusive(&nfc_lk);
    dev_state = tag_held ? ST_FOUND : ST_SEARCHING;
    const int held = tag_held;
    ReleaseSRWLockExclusive(&nfc_lk);
    hos_log("nfp: the game waits for an NFC tag%s", held ? ": one is at the reader" : " (the Insert menu's NFC tab holds one to the reader)");
    RET(0);
}
/* (the game is done with the reader: the tag is taken off it too, so the next time it asks one is tapped again) */
HLE(_ZN2nn3nfp13StopDetectionERKNS0_12DeviceHandleE) {
    AcquireSRWLockExclusive(&nfc_lk);
    if (dev_state != ST_INIT) hos_log("nfp: the game stopped waiting for an NFC tag");
    dev_state = ST_INIT, tag_held = 0, area_open = 0;
    ReleaseSRWLockExclusive(&nfc_lk);
    RET(0);
}
/* TagInfo (0x58): the UID (10 bytes, its length, 0x15 reserved), the protocol (1: type A), the tag's type (2: type 2) */
HLE(_ZN2nn3nfp10GetTagInfoEPNS0_7TagInfoERKNS0_12DeviceHandleE) {
    AcquireSRWLockShared(&nfc_lk);
    const int ok = dev_state == ST_FOUND || dev_state == ST_MOUNTED;
    if (ok && ARG(0)) {
        uint8_t *t = GP(ARG(0));
        memset(t, 0, 0x58);
        memcpy(t, tag, 3), memcpy(t + 3, tag + 4, 4);   /* (the UID's 7 bytes: page 0's first three, page 1) */
        t[10] = 7;
        const uint32_t protocol = 1, type = 2;
        memcpy(t + 0x20, &protocol, 4), memcpy(t + 0x24, &type, 4);
    }
    ReleaseSRWLockShared(&nfc_lk);
    RET(ok ? 0 : NFP_WRONG_STATE);
}
HLE(_ZN2nn3nfp5MountERKNS0_12DeviceHandleENS0_9ModelTypeENS0_11MountTargetE) {
    AcquireSRWLockExclusive(&nfc_lk);
    const int ok = dev_state == ST_FOUND || dev_state == ST_MOUNTED;
    if (ok) dev_state = ST_MOUNTED;
    ReleaseSRWLockExclusive(&nfc_lk);
    if (ok) hos_log("nfp: the game reads the NFC tag \"%s\"", tag_name);
    RET(ok ? 0 : NFP_WRONG_STATE);
}
/* ModelInfo (0x40): the tag's model as it is on it (page 21 and page 22's first three bytes: the character, its variant, the
   figure's type, the model's number, the series) */
HLE(_ZN2nn3nfp12GetModelInfoEPNS0_9ModelInfoERKNS0_12DeviceHandleE) {
    AcquireSRWLockShared(&nfc_lk);
    const int ok = dev_state == ST_MOUNTED;
    if (ok && ARG(0)) {
        uint8_t *m = GP(ARG(0));
        memset(m, 0, 0x40);
        memcpy(m, tag + 0x54, 7);
    }
    ReleaseSRWLockShared(&nfc_lk);
    RET(ok ? 0 : NFP_WRONG_STATE);
}
/* CommonInfo (0x40): the last write's date, the write counter, the version, the application area's size. A tag here was
   never written: 2000-01-01, no writes */
HLE(_ZN2nn3nfp13GetCommonInfoEPNS0_10CommonInfoERKNS0_12DeviceHandleE) {
    AcquireSRWLockShared(&nfc_lk);
    const int ok = dev_state == ST_MOUNTED;
    if (ok && ARG(0)) {
        uint8_t *m = GP(ARG(0));
        memset(m, 0, 0x40);
        const uint16_t year = 2000;
        const uint32_t size = AREA_SIZE;
        memcpy(m, &year, 2), m[2] = 1, m[3] = 1;
        memcpy(m + 8, &size, 4);
    }
    ReleaseSRWLockShared(&nfc_lk);
    RET(ok ? 0 : NFP_WRONG_STATE);
}
/* RegisterInfo (0x100): the owner's Mii (0x58), the first write's date, the NFC tag's name (UTF-8, 40 bytes and its end), the
   font's region. The owner is nobody's Mii (zeros); the name is the file's */
HLE(_ZN2nn3nfp15GetRegisterInfoEPNS0_12RegisterInfoERKNS0_12DeviceHandleE) {
    AcquireSRWLockShared(&nfc_lk);
    const int ok = dev_state == ST_MOUNTED;
    if (ok && ARG(0)) {
        uint8_t *m = GP(ARG(0));
        memset(m, 0, 0x100);
        const uint16_t year = 2000;
        memcpy(m + 0x58, &year, 2), m[0x5a] = 1, m[0x5b] = 1;
        size_t n = strlen(tag_name);
        if (n > 40) n = 40;
        while (n && ((unsigned char)tag_name[n] & 0xc0) == 0x80) n--;   /* (cut at a character's start) */
        memcpy(m + 0x5c, tag_name, n);
    }
    ReleaseSRWLockShared(&nfc_lk);
    RET(ok ? 0 : NFP_WRONG_STATE);
}

/* ---- the application area ----------------------------------------------------------------------------------------------------- */
HLE(_ZN2nn3nfp19OpenApplicationAreaERKNS0_12DeviceHandleEj) {
    const uint32_t id = (uint32_t)ARG(1);
    AcquireSRWLockExclusive(&nfc_lk);
    uint32_t r = 0;
    if (dev_state != ST_MOUNTED) r = NFP_WRONG_STATE;
    else if (!area_there) r = NFP_AREA_NEEDS_CREATE;
    else if (area_id != id) r = NFP_WRONG_ACCESS_ID;
    else area_open = 1;
    ReleaseSRWLockExclusive(&nfc_lk);
    NFP_TRACE("nfp: OpenApplicationArea(%08x) -> %08x", id, r);
    RET(r);
}
/* GetApplicationArea(void *out, size_t *size, handle, size_t max) */
HLE(_ZN2nn3nfp18GetApplicationAreaEPvPmRKNS0_12DeviceHandleEm) {
    AcquireSRWLockShared(&nfc_lk);
    const int ok = dev_state == ST_MOUNTED && area_open;
    if (ok) {
        const size_t n = ARG(3) < AREA_SIZE ? (size_t)ARG(3) : AREA_SIZE;
        if (ARG(0)) memcpy(GP(ARG(0)), area, n);
        if (ARG(1)) *(uint64_t *)GP(ARG(1)) = AREA_SIZE;
    }
    ReleaseSRWLockShared(&nfc_lk);
    RET(ok ? 0 : NFP_WRONG_STATE);
}
/* SetApplicationArea(handle, const void *data, size_t size) */
HLE(_ZN2nn3nfp18SetApplicationAreaERKNS0_12DeviceHandleEPKvm) {
    AcquireSRWLockExclusive(&nfc_lk);
    const int ok = dev_state == ST_MOUNTED && area_open;
    if (ok && ARG(1)) {
        const size_t n = ARG(2) < AREA_SIZE ? (size_t)ARG(2) : AREA_SIZE;
        memset(area, 0, sizeof area);
        memcpy(area, GP(ARG(1)), n);
    }
    ReleaseSRWLockExclusive(&nfc_lk);
    RET(ok ? 0 : NFP_WRONG_STATE);
}
/* ApplicationAreaCreateInfo: the access ID, the first data's pointer (at 8) and its size (at 16) */
static uint32_t area_create(Ctx *c, int again) {
    const uint8_t *info = GP(ARG(1));
    uint32_t id, size;
    uint64_t data;
    memcpy(&id, info, 4), memcpy(&data, info + 8, 8), memcpy(&size, info + 16, 4);
    AcquireSRWLockExclusive(&nfc_lk);
    uint32_t r = 0;
    if (dev_state != ST_MOUNTED) r = NFP_WRONG_STATE;
    else if (area_there && !again) r = NFP_AREA_EXISTS;
    else {
        memset(area, 0, sizeof area);
        if (data) memcpy(area, GP(data), size < AREA_SIZE ? size : AREA_SIZE);
        area_id = id, area_there = 1, area_open = 1;
        area_save();
    }
    ReleaseSRWLockExclusive(&nfc_lk);
    NFP_TRACE("nfp: %sCreateApplicationArea(%08x, %u bytes) -> %08x", again ? "Re" : "", id, size, r);
    return r;
}
HLE(_ZN2nn3nfp21CreateApplicationAreaERKNS0_12DeviceHandleERKNS0_25ApplicationAreaCreateInfoE) { RET(area_create(c, 0)); }
HLE(_ZN2nn3nfp23RecreateApplicationAreaERKNS0_12DeviceHandleERKNS0_25ApplicationAreaCreateInfoE) { RET(area_create(c, 1)); }
/* (what was set is written to the tag: here, to its file) */
HLE(_ZN2nn3nfp5FlushERKNS0_12DeviceHandleE) {
    AcquireSRWLockExclusive(&nfc_lk);
    const int ok = dev_state == ST_MOUNTED;
    if (ok && area_there) area_save();
    ReleaseSRWLockExclusive(&nfc_lk);
    RET(ok ? 0 : NFP_WRONG_STATE);
}

/* ---- the console's tag settings (its own screens: the owner and nickname, erasing a game's data, restoring a tag). There
   is no such screen here: each returns as when the player backs out of it, with nothing changed ------------------------------ */
HLE(_ZN2nn3nfp29StartNicknameAndOwnerSettingsEPNS0_12DeviceHandleEPbPNS0_12RegisterInfoERKNS0_24AmiiboSettingsStartParamERKNS0_7TagInfoE) {
    if (ARG(1)) *(uint8_t *)GP(ARG(1)) = 0;   /* (not registered anew) */
    RET(0);
}
HLE(_ZN2nn3nfp29StartNicknameAndOwnerSettingsEPNS0_12DeviceHandleEPbPNS0_12RegisterInfoERKNS0_24AmiiboSettingsStartParamERKNS0_7TagInfoERKS4_) {
    if (ARG(1)) *(uint8_t *)GP(ARG(1)) = 0;
    RET(0);
}
HLE(_ZN2nn3nfp19StartGameDataEraserEPNS0_12DeviceHandleERKNS0_24AmiiboSettingsStartParamERKNS0_7TagInfoE) { RET(0); }
HLE(_ZN2nn3nfp13StartRestorerEPNS0_12DeviceHandleERKNS0_24AmiiboSettingsStartParamERKNS0_7TagInfoE) { RET(0); }
