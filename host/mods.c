/* Mods, in the layout emulators use, so RomFS mods made for them work as they are:
     <mods>/<name>/romfs/...          files that replace (or add to) the game's RomFS
   <mods> is the "mods" folder beside the executable, or HOS_MODS=<dir>. A mod may sit deeper, as emulators keep them
   (<mods>/contents/<title id>/<name>/romfs): any folder holding a romfs or exefs folder is a mod. Folders whose names
   start with '-' or '_' are left out (off). When two mods have the same file, the one that loads later wins.
   (hookshot) The player turns mods on and off and sets their load order in the Insert menu's Mods page (Gameplay, Mods),
   which keeps the choice in <mods>/hookshot-mods.ini (hos_mods_save) rather than renaming the player's folders: a line a
   mod, its name (its folder under <mods>, '/' between folders) then "= on" or "= off", in load order. The mods it names
   load first, in its order (those it turns off not at all); the others after them, the one whose path sorts last last, as
   before the file (name them 01-..., 02-... to order them without it). A folder off by its name stays off whatever the
   file says; the mods in it are listed for the menu, off. The resource size table that wins gets the button prompts'
   entries merged into it (prompts.c), so the prompts' larger files still fit.
   Every mod file is indexed once at the start (no disk lookups per open); nn_fs.c asks hos_mods_romfs for each rom:
   path and lists a folder's mod-only entries with the game's own (hos_mods_dir_extras). HOS_FS_OVERLAY (nn_fs.c) is
   looked at after this, so a test overlay wins over mods.
   exefs patches (.pchtxt, .ips) are not applied: the code is compiled ahead of time from the original instructions, and
   the game folder has no module map (image.json) to place data patches with. A mod's exefs folder is logged as left out.
   From Skybound's loader (NotRexed/SkyboundTotk a64-kit/hos/mods.c, MIT): its RomFS part. */
#include "hos.h"
#include "hos_paths.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#define WIN32_LEAN_AND_MEAN
#include <windows.h>

typedef struct { char *key; char *host; uint64_t size; int is_dir, logged; } Entry;   /* key: romfs path, lower case, '/' */
static Entry *table;
static size_t table_cap, table_n;

static uint64_t hash_str(const char *s) {
    uint64_t h = 0xcbf29ce484222325ull;
    for (; *s; s++) h = (h ^ (uint8_t)*s) * 0x100000001b3ull;
    return h;
}
static void lower_slash(char *s) {
    for (; *s; s++) *s = *s == '\\' ? '/' : (char)tolower((unsigned char)*s);
}
static const char *last_sep(const char *s) {   /* (a host path: '\' on Windows, '/' from host/posix) */
    const char *b = strrchr(s, '\\'), *f = strrchr(s, '/');
    return b > f ? b : f;
}
static Entry *find(const char *key) {
    if (!table_cap) return NULL;
    for (size_t i = hash_str(key) & (table_cap - 1);; i = (i + 1) & (table_cap - 1)) {
        if (!table[i].key) return NULL;
        if (!strcmp(table[i].key, key)) return &table[i];
    }
}
static void put(const char *key, const char *host, uint64_t size, int is_dir) {
    if ((table_n + 1) * 2 > table_cap) {   /* (grow: rehash) */
        Entry *old = table;
        const size_t old_cap = table_cap;
        table_cap = table_cap ? table_cap * 2 : 1024;
        table = (Entry *)calloc(table_cap, sizeof *table);
        table_n = 0;
        for (size_t i = 0; i < old_cap; i++)
            if (old[i].key) {
                size_t j = hash_str(old[i].key) & (table_cap - 1);
                while (table[j].key) j = (j + 1) & (table_cap - 1);
                table[j] = old[i];
                table_n++;
            }
        free(old);
    }
    size_t i = hash_str(key) & (table_cap - 1);
    while (table[i].key && strcmp(table[i].key, key)) i = (i + 1) & (table_cap - 1);
    if (!table[i].key) table[i].key = _strdup(key), table_n++;
    else free(table[i].host);
    table[i].host = _strdup(host);
    table[i].size = size;
    table[i].is_dir = is_dir;
}

/* (hookshot) every file of every mod, on or off, as its key's hash and the mod's place: what two mods both have
   (count_shared, hos_mods_shared: the Mods page's conflicts, for whichever mods the player turns on) */
typedef struct { uint64_t hash; int mod; } FileOf;
static FileOf *files_of;
static size_t files_n, files_cap;
static void note_file(const char *key, int mod) {
    if (files_n == files_cap) {
        const size_t cap = files_cap ? files_cap * 2 : 4096;
        FileOf *grown = (FileOf *)realloc(files_of, cap * sizeof *files_of);
        if (!grown) return;   /* (no memory: the shared counts come out short, nothing else) */
        files_of = grown, files_cap = cap;
    }
    files_of[files_n].hash = hash_str(key);
    files_of[files_n++].mod = mod;
}

/* a mod's romfs folder, recursively: rel is the path inside the RomFS so far ("" at its root). (hookshot) mod: its place in
   the load order; load: 0 for a mod that is off, whose files are counted (and noted) but not served */
static int index_romfs(const char *host_dir, const char *rel, int depth, int mod, int load) {
    if (depth > 32) return 0;   /* (hookshot: no RomFS is this deep) */
    if (!depth) {   /* (hookshot) the romfs folder itself a link (to / in a mod's archive): the walk covered the whole disk */
        const DWORD at = GetFileAttributesA(host_dir);
        if (at != INVALID_FILE_ATTRIBUTES && (at & FILE_ATTRIBUTE_REPARSE_POINT)) {
            if (load) hos_log("mods: %s is a link to a folder: left out", host_dir);
            return 0;
        }
    }
    char pat[MAX_PATH];
    snprintf(pat, sizeof pat, "%s\\*", host_dir);
    WIN32_FIND_DATAA fd;
    HANDLE f = FindFirstFileA(pat, &fd);
    if (f == INVALID_HANDLE_VALUE) return 0;
    int files = 0;
    do {
        if (!strcmp(fd.cFileName, ".") || !strcmp(fd.cFileName, "..")) continue;
        char host[MAX_PATH], key[MAX_PATH];
        snprintf(host, sizeof host, "%s\\%s", host_dir, fd.cFileName);
        /* (hookshot) a link to a folder is not followed (two links back up made the walk endless); links to files are
           (mod managers place files as links) */
        if ((fd.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) && (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)) {
            if (load) hos_log("mods: %s is a link to a folder: left out", host);
            continue;
        }
        snprintf(key, sizeof key, "%s%s%s", rel, *rel ? "/" : "", fd.cFileName);
        lower_slash(key);
        const int is_dir = (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0;
        if (load) put(key, host, ((uint64_t)fd.nFileSizeHigh << 32) | fd.nFileSizeLow, is_dir);
        if (is_dir) {
            char sub_rel[MAX_PATH];
            snprintf(sub_rel, sizeof sub_rel, "%s%s%s", rel, *rel ? "/" : "", fd.cFileName);
            files += index_romfs(host, sub_rel, depth + 1, mod, load);
        } else {
            files++;
            note_file(key, mod);
        }
    } while (FindNextFileA(f, &fd));
    FindClose(f);
    return files;
}

/* the mod folders under root (a mod: a folder holding romfs or exefs), in load order once hos_mods_init has sorted them */
typedef struct {
    char path[MAX_PATH], name[MAX_PATH];
    int renamed;   /* (hookshot) off by its folder's name: '-' or '_' first, its own or a folder's it is in */
    int listed;    /* (hookshot) its line in hookshot-mods.ini, -1 when the file does not name it */
    int on;        /* (hookshot) loaded in this run */
    int files;     /* (hookshot) its RomFS files */
    int exefs;     /* (hookshot) it has an exefs folder (left out) */
} Mod;
static Mod *mods;
static int nmods, cap_mods;
static char mods_root[MAX_PATH];   /* (hookshot) the mods folder, "" when there is none: hos_mods_save writes into it */
static void find_mods(const char *dir, const char *name, int depth, int renamed) {
    char probe[MAX_PATH];
    snprintf(probe, sizeof probe, "%s\\romfs", dir);
    const int has_romfs = GetFileAttributesA(probe) != INVALID_FILE_ATTRIBUTES;
    snprintf(probe, sizeof probe, "%s\\exefs", dir);
    const int has_exefs = GetFileAttributesA(probe) != INVALID_FILE_ATTRIBUTES;
    if ((has_romfs || has_exefs) && depth > 0) {
        if (nmods == cap_mods) {
            const int cap = cap_mods ? cap_mods * 2 : 16;
            Mod *grown = (Mod *)realloc(mods, sizeof *mods * (size_t)cap);
            if (!grown) return;
            mods = grown, cap_mods = cap;
        }
        memset(&mods[nmods], 0, sizeof *mods);
        snprintf(mods[nmods].path, MAX_PATH, "%s", dir);
        snprintf(mods[nmods].name, MAX_PATH, "%s", name);
        mods[nmods].renamed = renamed, mods[nmods].listed = -1;
        nmods++;
        return;
    }
    if (depth >= 4) return;
    char pat[MAX_PATH];
    snprintf(pat, sizeof pat, "%s\\*", dir);
    WIN32_FIND_DATAA fd;
    HANDLE f = FindFirstFileA(pat, &fd);
    if (f == INVALID_HANDLE_VALUE) return;
    do {
        if (!(fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) || fd.cFileName[0] == '.') continue;
        /* (hookshot) a folder off by its name is still walked: the mods in it are listed for the Mods page, off */
        const int off = fd.cFileName[0] == '-' || fd.cFileName[0] == '_';
        if (off && !renamed) hos_log("mods: %s\\%s is off (its name starts with %c)", dir, fd.cFileName, fd.cFileName[0]);
        char sub[MAX_PATH], sub_name[MAX_PATH];
        snprintf(sub, sizeof sub, "%s\\%s", dir, fd.cFileName);
        snprintf(sub_name, sizeof sub_name, "%s%s%s", name, *name ? "/" : "", fd.cFileName);
        find_mods(sub, sub_name, depth + 1, renamed || off);
    } while (FindNextFileA(f, &fd));
    FindClose(f);
}
/* (hookshot) the load order: hookshot-mods.ini's lines in its order, then the mods it does not name by their names (the one
   that sorts last last, as before the file), then those off by their folder's name */
static int mod_cmp(const void *a, const void *b) {
    const Mod *x = (const Mod *)a, *y = (const Mod *)b;
    const int gx = x->renamed ? 2 : x->listed >= 0 ? 0 : 1, gy = y->renamed ? 2 : y->listed >= 0 ? 0 : 1;
    if (gx != gy) return gx - gy;
    if (gx == 0 && x->listed != y->listed) return x->listed - y->listed;
    const int c = _stricmp(x->name, y->name);
    return c ? c : strcmp(x->name, y->name);   /* (two names apart only by case, on Linux: still one order) */
}

/* ---- (hookshot) hookshot-mods.ini: the Mods page's choice. A line a mod: its name, then "= on" or "= off" (1, yes, true;
   0, no, false), split at the last '=' (a folder's name may hold one); a name alone, or one whose value is none of those,
   is on. Lines starting with ';' are comments (a name starting with ';' or a space is written after "./"). Names are matched
   without regard to case, '\' as '/'; a name given twice counts once, the first time ---- */
typedef struct { char name[MAX_PATH]; int on, used; } IniLine;
static void ini_file(char *out, size_t cap) {
#ifdef _WIN32
    snprintf(out, cap, "%s\\hookshot-mods.ini", mods_root);
#else   /* (fopen, not host/posix's Win32 calls: '/' only) */
    snprintf(out, cap, "%s/hookshot-mods.ini", mods_root);
#endif
}
static int ini_value(const char *v) {
    static const char *const yes[] = {"on", "1", "yes", "true"}, *const no[] = {"off", "0", "no", "false"};
    for (int i = 0; i < 4; i++) {
        if (!_stricmp(v, yes[i])) return 1;
        if (!_stricmp(v, no[i])) return 0;
    }
    return -1;
}
static char *trim(char *s) {
    while (*s == ' ' || *s == '\t') s++;
    size_t n = strlen(s);
    while (n && (s[n - 1] == ' ' || s[n - 1] == '\t' || s[n - 1] == '\r')) s[--n] = 0;
    return s;
}
/* a name as hookshot-mods.ini and the mods list compare it: '\' as '/', no "./" before it, no '/' after it */
static void ini_name(char *s) {
    for (char *p = s; *p; p++)
        if (*p == '\\') *p = '/';
    if (s[0] == '.' && s[1] == '/') memmove(s, s + 2, strlen(s + 2) + 1);
    size_t n = strlen(s);
    while (n && s[n - 1] == '/') s[--n] = 0;
}
/* the file's lines in order (NULL, *count 0: no file) */
static IniLine *ini_read(int *count) {
    *count = 0;
    char path[MAX_PATH];
    ini_file(path, sizeof path);
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    enum { kMaxBytes = 1 << 20 };   /* (a list of mods: far under a megabyte) */
    char *text = (char *)malloc(kMaxBytes + 1);
    const size_t n = text ? fread(text, 1, kMaxBytes, f) : 0;
    fclose(f);
    if (!text) return NULL;
    text[n] = 0;
    IniLine *lines = NULL;
    int cap = 0;
    char *at = text;
    if ((unsigned char)at[0] == 0xEF && (unsigned char)at[1] == 0xBB && (unsigned char)at[2] == 0xBF) at += 3;   /* (Notepad's BOM) */
    while (*at) {
        char *end = strchr(at, '\n');
        if (end) *end = 0;
        char *line = trim(at);
        at = end ? end + 1 : at + strlen(at);
        if (!*line || *line == ';') continue;
        int on = 1;
        char *eq = strrchr(line, '=');
        if (eq) {
            const int v = ini_value(trim(eq + 1));
            if (v >= 0) on = v, *eq = 0, line = trim(line);
        }
        ini_name(line);
        if (!*line || strlen(line) >= MAX_PATH) continue;
        int dup = 0;
        for (int k = 0; k < *count && !dup; k++) dup = !_stricmp(lines[k].name, line);
        if (dup) continue;
        if (*count == cap) {
            cap = cap ? cap * 2 : 32;
            IniLine *grown = (IniLine *)realloc(lines, sizeof *lines * (size_t)cap);
            if (!grown) break;
            lines = grown;
        }
        snprintf(lines[*count].name, MAX_PATH, "%s", line);
        lines[*count].on = on, lines[*count].used = 0;
        (*count)++;
    }
    free(text);
    return lines;
}

/* (hookshot) how many files each two mods both have (count_shared), nmods x nmods; NULL when no two mods have files, or there
   are too many mods to keep it for */
static uint32_t *shared;
static int file_cmp(const void *a, const void *b) {
    const FileOf *x = (const FileOf *)a, *y = (const FileOf *)b;
    return x->hash != y->hash ? (x->hash < y->hash ? -1 : 1) : x->mod - y->mod;
}
static void count_shared(void) {
    enum { kMaxMods = 2048 };   /* (16 MB of counts at most) */
    if (nmods >= 2 && nmods <= kMaxMods && files_n) {
        qsort(files_of, files_n, sizeof *files_of, file_cmp);
        shared = (uint32_t *)calloc((size_t)nmods * (size_t)nmods, sizeof *shared);
        for (size_t i = 0; shared && i < files_n;) {
            size_t j = i + 1;
            while (j < files_n && files_of[j].hash == files_of[i].hash) j++;
            for (size_t a = i; a < j; a++)   /* (each pair of mods in the run once: a mod's own key twice, on Linux, once) */
                if (a == i || files_of[a].mod != files_of[a - 1].mod)
                    for (size_t b = a + 1; b < j; b++)
                        if (files_of[b].mod != files_of[b - 1].mod) {
                            const size_t x = (size_t)files_of[a].mod, y = (size_t)files_of[b].mod;
                            shared[x * (size_t)nmods + y]++, shared[y * (size_t)nmods + x]++;
                        }
            i = j;
        }
    } else if (nmods > kMaxMods) {
        hos_log("mods: %d mods: too many to say which have the same files", nmods);
    }
    free(files_of);
    files_of = NULL, files_n = files_cap = 0;
}

/* hos_main.c, once the image is loaded (image_path: kept for exefs patches, which are not applied here) */
void hos_mods_init(const char *image_path) {
    (void)image_path;
    char root[MAX_PATH];
    if (getenv("HOS_MODS")) {
        snprintf(root, sizeof root, "%s", getenv("HOS_MODS"));
    } else {
        hos_game_path_a(root, sizeof root);
        char *slash = (char *)last_sep(root);
        if (!slash) return;
        snprintf(slash + 1, sizeof root - (size_t)(slash + 1 - root), "mods");
    }
    if (GetFileAttributesA(root) == INVALID_FILE_ATTRIBUTES) return;
    snprintf(mods_root, sizeof mods_root, "%s", root);
    find_mods(root, "", 0, 0);
    if (!nmods) {
        hos_log("mods: none in %s (a mod: <name>\\romfs)", root);
        return;
    }
    /* (hookshot) the player's list: which are off, and the order */
    int nlines = 0;
    IniLine *lines = ini_read(&nlines);
    for (int i = 0; i < nmods; i++)   /* (a line for a folder off by its name is that folder's, and has no say: listed stays -1) */
        for (int k = 0; k < nlines && mods[i].listed < 0; k++)
            if (!_stricmp(lines[k].name, mods[i].name)) {
                lines[k].used = 1;
                if (mods[i].renamed) break;
                mods[i].listed = k;
            }
    if (lines) {
        int off = 0, missing = 0;
        for (int k = 0; k < nlines; k++) {
            off += !lines[k].on;
            if (!lines[k].used && ++missing <= 16)
                hos_log("mods: hookshot-mods.ini names %s, which is not in the mods folder: kept for when it is back", lines[k].name);
        }
        hos_log("mods: hookshot-mods.ini: %d mods named, %d of them off", nlines, off);
    }
    for (int i = 0; i < nmods; i++) mods[i].on = !mods[i].renamed && (mods[i].listed < 0 || lines[mods[i].listed].on);
    free(lines);
    qsort(mods, (size_t)nmods, sizeof *mods, mod_cmp);
    int loaded = 0;
    for (int i = 0; i < nmods; i++) {   /* (in load order: a later mod's file replaces an earlier one's, put) */
        char dir[MAX_PATH];
        snprintf(dir, sizeof dir, "%s\\romfs", mods[i].path);
        mods[i].files = index_romfs(dir, "", 0, i, mods[i].on);
        snprintf(dir, sizeof dir, "%s\\exefs", mods[i].path);
        mods[i].exefs = GetFileAttributesA(dir) != INVALID_FILE_ATTRIBUTES;
        if (!mods[i].on) continue;
        loaded++;
        if (mods[i].exefs) hos_log("mods: %s: exefs patches are left out (the code is compiled ahead of time)", mods[i].name);
        hos_log("mods: %s: %d RomFS files", mods[i].name, mods[i].files);
    }
    count_shared();
    /* (hookshot) one line a mod: its place in the load order, on or off and why, its files; then the mods on that have the
       same files, the later one's loading */
    for (int i = 0, place = 0; i < nmods; i++) {
        const Mod *m = &mods[i];
        char at[16] = "";
        if (!m->renamed) snprintf(at, sizeof at, "#%d ", ++place);
        hos_log("mods: %s%s: %s, %d RomFS files", at, m->name,
                m->on ? "on" : m->renamed ? "off (its folder's name starts with - or _)" : "off (hookshot-mods.ini)", m->files);
    }
    int said = 0;
    for (int a = 0; shared && a < nmods; a++)
        for (int b = a + 1; b < nmods && mods[a].on; b++)
            if (mods[b].on && shared[(size_t)a * (size_t)nmods + (size_t)b] && ++said <= 64)
                hos_log("mods: %s and %s have %u files in common: %s's load (it comes later)", mods[a].name, mods[b].name,
                        shared[(size_t)a * (size_t)nmods + (size_t)b], mods[b].name);
    hos_log("mods: %d mods from %s: %zu RomFS entries", loaded, root, table_n);
}

/* (hookshot) the Insert menu's Mods page (rx_backend.c, MkwVkHost.mod): the index-th mod in hos_mods_init's order (the load
   order, then those off by their folder's name); 0 past the last */
int hos_mods_info(int index, const char **name, int *on, int *files, int *renamed, int *exefs) {
    if (index < 0 || index >= nmods) return 0;
    const Mod *m = &mods[index];
    *name = m->name, *on = m->on, *files = m->files, *renamed = m->renamed, *exefs = m->exefs;
    return 1;
}
/* (MkwVkHost.mod_shared) how many RomFS files the a-th and b-th mods both have, on or off */
int hos_mods_shared(int a, int b) {
    if (!shared || a < 0 || b < 0 || a >= nmods || b >= nmods || a == b) return 0;
    return (int)shared[(size_t)a * (size_t)nmods + (size_t)b];
}
/* (MkwVkHost.mods_save) the mods for the next start, written to hookshot-mods.ini: order holds the index of every mod not off
   by its folder's name (they come first in hos_mods_init's order), each once, in the load order wanted; on[i] whether
   order[i] loads. Lines of the file that name no mod here are kept, after them (a folder away for now keeps its choice).
   Written to a part file, then moved over the file in one step: 1 written, 0 not (the file as it was) */
static void put_text(char **buf, size_t *n, size_t *cap, const char *s) {
    const size_t k = strlen(s);
    if (*n + k + 1 > *cap) {
        size_t c = *cap ? *cap : 4096;
        while (*n + k + 1 > c) c *= 2;
        char *grown = (char *)realloc(*buf, c);
        if (!grown) return;
        *buf = grown, *cap = c;
    }
    memcpy(*buf + *n, s, k + 1);
    *n += k;
}
static void put_line(char **buf, size_t *n, size_t *cap, const char *name, int on) {
    if (strchr(name, '\n') || strchr(name, '\r')) return;   /* (no line can hold it: left unnamed, so on) */
    char line[MAX_PATH + 16];
    const int escape = name[0] == ';' || name[0] == ' ' || name[0] == '\t';   /* (else read as a comment, or trimmed) */
    snprintf(line, sizeof line, "%s%s = %s\n", escape ? "./" : "", name, on ? "on" : "off");
    put_text(buf, n, cap, line);
}
int hos_mods_save(const int *order, const int *on, int n) {
    int movable = 0;
    while (movable < nmods && !mods[movable].renamed) movable++;
    if (!mods_root[0] || !order || !on || n != movable || !n) return 0;
    char *seen = (char *)calloc((size_t)n, 1);
    int ok = seen != NULL;
    for (int i = 0; ok && i < n; i++) ok = order[i] >= 0 && order[i] < n && !seen[order[i]]++;
    free(seen);
    if (!ok) {
        hos_log("mods: the Mods page's list is not every mod once: hookshot-mods.ini left as it was");
        return 0;
    }
    int nlines = 0;
    IniLine *lines = ini_read(&nlines);   /* (again: the player may have edited it since the start) */
    char *buf = NULL;
    size_t len = 0, cap = 0;
    put_text(&buf, &len, &cap,
             "; Hookshot's mod list. The Insert menu's Mods page (Gameplay, Mods) writes it; edit it with the game closed.\n"
             "; A line a mod: its folder in the mods folder ('/' between folders), then = on or = off.\n"
             "; The lines are the load order: when two mods have the same file, the one lower down wins.\n"
             "; Mods not named here load after these, in name order. A folder whose name starts with - or _ stays off.\n");
    int off = 0;
    for (int i = 0; i < n; i++) put_line(&buf, &len, &cap, mods[order[i]].name, on[i] != 0), off += !on[i];
    int kept = 0;
    for (int k = 0; k < nlines; k++) {
        int here = 0;
        for (int i = 0; i < movable && !here; i++) here = !_stricmp(lines[k].name, mods[i].name);
        if (here) continue;
        if (!kept++) put_text(&buf, &len, &cap, "; Not in the mods folder now, kept for when they are back:\n");
        put_line(&buf, &len, &cap, lines[k].name, lines[k].on);
    }
    free(lines);
    char path[MAX_PATH], part[MAX_PATH + 8];
    ini_file(path, sizeof path);
    snprintf(part, sizeof part, "%s.new", path);
    FILE *f = buf ? fopen(part, "wb") : NULL;
    ok = f != NULL;
    if (f) {
        ok = fwrite(buf, 1, len, f) == len;
        ok = fclose(f) == 0 && ok;
        ok = ok && MoveFileExA(part, path, MOVEFILE_REPLACE_EXISTING);
        if (!ok) remove(part);
    }
    free(buf);
    if (ok) hos_log("mods: hookshot-mods.ini written for the next start: %d mods, %d of them off", n, off);
    else hos_log("mods: hookshot-mods.ini could not be written (%s): the mods stay as they were", path);
    return ok;
}

/* nn_fs.c: the mod file for a RomFS path ("UI/x.zs", no mount, no leading slash), or 0 */
int hos_mods_romfs(const char *rel, char *out, size_t cap) {
    char key[MAX_PATH];
    snprintf(key, sizeof key, "%s", rel);
    lower_slash(key);
    int hos_prompts_romfs(const char *key, const char *mod, char *out, size_t cap);   /* prompts.c: the button prompts */
    Entry *e = table_n ? find(key) : NULL;
    if (!e || e->is_dir) return hos_prompts_romfs(key, NULL, out, cap);
    const int merged = hos_prompts_romfs(key, e->host, out, cap);   /* (the size table: the prompts' entries merged in) */
    if (!merged) snprintf(out, cap, "%s", e->host);
    static volatile LONG logged;
    if (!e->logged && InterlockedIncrement(&logged) <= 200)
        hos_log("mods: %s <- %s%s", rel, e->host, merged ? " (with the button prompts' sizes merged in)" : "");
    e->logged = 1;
    return 1;
}

/* prompts.c: the mod file for this exact RomFS path, before the prompts' replacements */
int hos_mods_file(const char *rel, char *out, size_t cap) {
    char key[MAX_PATH];
    snprintf(key, sizeof key, "%s", rel);
    lower_slash(key);
    const Entry *e = table_n ? find(key) : NULL;
    if (!e || e->is_dir) return 0;
    snprintf(out, cap, "%s", e->host);
    return 1;
}

/* nn_fs.c, listing a RomFS folder: fn(arg, name, is_dir, size) for each mod entry directly in it that the game's own
   folder (base_dir, a host path; may not exist) does not have. Returns how many. */
int hos_mods_dir_extras(const char *rel, const char *base_dir, void (*fn)(void *, const char *, int, uint64_t),
                        void *arg) {
    if (!table_n) return 0;
    char prefix[MAX_PATH];
    snprintf(prefix, sizeof prefix, "%s", rel);
    lower_slash(prefix);
    size_t pn = strlen(prefix);
    while (pn && prefix[pn - 1] == '/') prefix[--pn] = 0;
    int n = 0;
    for (size_t i = 0; i < table_cap; i++) {
        const Entry *e = &table[i];
        if (!e->key) continue;
        const char *k = e->key;
        if (pn && (strncmp(k, prefix, pn) || k[pn] != '/')) continue;
        const char *name = pn ? k + pn + 1 : k;
        if (!*name || strchr(name, '/')) continue;   /* (deeper) */
        const char *real = last_sep(e->host);   /* (the name as the mod spells it) */
        real = real ? real + 1 : e->host;
        char base[MAX_PATH];
        snprintf(base, sizeof base, "%s\\%s", base_dir, real);
        if (GetFileAttributesA(base) != INVALID_FILE_ATTRIBUTES) continue;
        fn(arg, real, e->is_dir, e->size);
        n++;
    }
    return n;
}
