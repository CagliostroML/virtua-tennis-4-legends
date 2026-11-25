/*
 * Per-Player Contextual Voice Pack Engine for Virtua Tennis 4: Legends & Next-Gen Edition.
 *
 * Self-contained header-only C module (zero extra linker flags; resolves winmm!PlaySoundA
 * dynamically so it links cleanly with build.ps1 and degrades safely on Android/Winlator).
 *
 * Directory layout (under <game_dir>\archive\voices\):
 *   <player_dir>\
 *     grunt\*.wav        (VP_EV_GRUNT      - rally hit grunt)
 *     serve\*.wav        (VP_EV_SERVE      - serve effort grunt)
 *     point_win\*.wav    (VP_EV_POINT_WIN  - "Vamos!", "Come on!", celebrations)
 *     point_lose\*.wav   (VP_EV_POINT_LOSE - frustration / reaction)
 *     protest\*.wav      (VP_EV_PROTEST    - umpire protest / meltdown / iconic quotes)
 *     match_win\*.wav    (VP_EV_MATCH_WIN  - match victory celebration)
 *     vs_<opp>\*.wav     (rivalry-specific quotes, e.g. 39_MED\vs_41_TSI\*.wav or vs_TSI\*.wav)
 *
 * Zero-stutter design:
 *   - vp_init(game_dir) scans only top-level player folders once at startup.
 *   - vp_on_match_start(p1_id, p2_id) preloads WAV bytes for ONLY the two active players
 *     (and their mutual rivalry clips) into RAM, freeing any previous match's cache.
 *   - vp_try_play_event(...) performs ZERO disk I/O during gameplay, playing directly
 *     from memory via PlaySoundA(..., SND_MEMORY | SND_ASYNC | SND_NODEFAULT).
 *   - Returns 0 when no custom clip is available so VT4's native SEGA voice plays untouched.
 */
#ifndef VT4_VOICE_PACKS_H
#define VT4_VOICE_PACKS_H

#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    VP_EV_GRUNT      = 0,
    VP_EV_SERVE      = 1,
    VP_EV_POINT_WIN  = 2,
    VP_EV_POINT_LOSE = 3,
    VP_EV_PROTEST    = 4,
    VP_EV_MATCH_WIN  = 5,
    VP_EV_COUNT      = 6
} vp_event_t;

#define VP_MAX_ROSTER_IDS      84
#define VP_MAX_CLIPS_PER_SLOT  16
#define VP_MAX_WAV_BYTES       (2u * 1024u * 1024u)  /* 2 MB cap per clip */
#define VP_MAX_PLAYER_BYTES    (12u * 1024u * 1024u) /* 12 MB RAM cap per active player */

typedef BOOL (WINAPI *vp_PlaySoundA_t)(LPCSTR pszSound, HMODULE hmod, DWORD fdwSound);

typedef struct {
    uint8_t *data;
    uint32_t size;
} vp_clip_t;

typedef struct {
    vp_clip_t clips[VP_MAX_CLIPS_PER_SLOT];
    int       count;
    int       last_idx;
} vp_slot_t;

typedef struct {
    int       player_id;
    int       opp_id;
    uint32_t  total_bytes;
    vp_slot_t events[VP_EV_COUNT];
    vp_slot_t rivalry;
} vp_active_player_t;

typedef struct {
    int                initialized;
    int                enabled;
    int                rivalry_prob_pct; /* 0..100, default 65 */
    char               voices_root[MAX_PATH];
    uint8_t            has_folder[VP_MAX_ROSTER_IDS];
    vp_PlaySoundA_t    fn_PlaySoundA;
    HMODULE            h_winmm;
    vp_active_player_t active[2];
    DWORD              last_play_tick[2];
    DWORD              last_quote_tick[2];
    uint32_t           rng_state;
} vp_state_t;

static vp_state_t g_vp = { 0 };

static const char *const g_vp_event_dirs[VP_EV_COUNT] = {
    "grunt",
    "serve",
    "point_win",
    "point_lose",
    "protest",
    "match_win"
};

/* Exact 3-letter codes for all 84 roster IDs (0..83) */
static const char *const g_vp_codes[VP_MAX_ROSTER_IDS] = {
    "FED","NAD","DJV","MRY","DEL","ROD","MON","GON","KOH","SEP", /* 00..09 */
    "HAS","BEC","RAF","COU","EDB","KIN","DUK","SHA","WIL","KUZ", /* 10..19 */
    "IVA","CHA","WOZ","ROB","VTM","VTF","ALC","SIN","SAM","AGA", /* 20..29 */
    "BOR","MCE","GRA","SER","SWI","SAB","KUE","NAV","WAW","MED", /* 30..39 */
    "ZVE","TSI","THI","KYR","HEW","SAF","TSO","FRR","MOY","FER", /* 40..49 */
    "NAL","LEN","CON","VIL","IVN","EVE","SEL","HEN","MUG","SHE", /* 50..59 */
    "RUB","RUU","FRI","GAU","RYB","BAD","HAL","COR","GAS","NIS", /* 60..69 */
    "SOD","BER","CHN","RIO","MUS","BRU","CRT","WLD","LAV","ASV", /* 70..79 */
    "CMT","CLI","AND","BJK"                                       /* 80..83 */
};

static inline uint32_t vp_rng_next(void) {
    uint32_t x = g_vp.rng_state;
    if (x == 0) x = 0x243F6A88u ^ (uint32_t)GetTickCount();
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    g_vp.rng_state = x;
    return x;
}

static inline int vp_format_player_dir(int player_id, char *out, size_t out_sz) {
    if (player_id < 0 || player_id >= VP_MAX_ROSTER_IDS || !out || out_sz < 8) return 0;
    snprintf(out, out_sz, "%02d_%s", player_id, g_vp_codes[player_id]);
    return 1;
}

static inline void vp_free_slot(vp_slot_t *sl) {
    if (!sl) return;
    for (int i = 0; i < sl->count; i++) {
        if (sl->clips[i].data) {
            free(sl->clips[i].data);
            sl->clips[i].data = NULL;
        }
        sl->clips[i].size = 0;
    }
    sl->count = 0;
    sl->last_idx = -1;
}

static inline void vp_free_active_player(vp_active_player_t *ap) {
    if (!ap) return;
    for (int e = 0; e < VP_EV_COUNT; e++) {
        vp_free_slot(&ap->events[e]);
    }
    vp_free_slot(&ap->rivalry);
    ap->player_id = -1;
    ap->opp_id = -1;
    ap->total_bytes = 0;
}

static inline int vp_dir_exists(const char *path) {
    DWORD attr = GetFileAttributesA(path);
    return (attr != INVALID_FILE_ATTRIBUTES) && ((attr & FILE_ATTRIBUTE_DIRECTORY) != 0);
}

static inline int vp_load_wav_file(const char *path, uint8_t **out_buf, uint32_t *out_sz) {
    FILE *f = fopen(path, "rb");
    if (!f) return 0;
    if (fseek(f, 0, SEEK_END) != 0) { fclose(f); return 0; }
    long sz = ftell(f);
    if (sz < 44 || (uint32_t)sz > VP_MAX_WAV_BYTES) { fclose(f); return 0; }
    rewind(f);
    uint8_t *buf = (uint8_t *)malloc((size_t)sz);
    if (!buf) { fclose(f); return 0; }
    if (fread(buf, 1, (size_t)sz, f) != (size_t)sz) {
        free(buf);
        fclose(f);
        return 0;
    }
    fclose(f);
    /* Validate RIFF....WAVE header */
    if (memcmp(buf, "RIFF", 4) != 0 || memcmp(buf + 8, "WAVE", 4) != 0) {
        free(buf);
        return 0;
    }
    *out_buf = buf;
    *out_sz = (uint32_t)sz;
    return 1;
}

static inline void vp_load_slot_dir(vp_slot_t *sl, const char *dir_path, uint32_t *total_bytes) {
    if (!sl || !dir_path || !vp_dir_exists(dir_path)) return;
    char pattern[MAX_PATH];
    snprintf(pattern, sizeof(pattern), "%s\\*.wav", dir_path);
    WIN32_FIND_DATAA fd;
    HANDLE h = FindFirstFileA(pattern, &fd);
    if (h == INVALID_HANDLE_VALUE) return;
    do {
        if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) continue;
        if (sl->count >= VP_MAX_CLIPS_PER_SLOT) break;
        if (*total_bytes >= VP_MAX_PLAYER_BYTES) break;
        char full[MAX_PATH];
        snprintf(full, sizeof(full), "%s\\%s", dir_path, fd.cFileName);
        uint8_t *buf = NULL;
        uint32_t sz = 0;
        if (vp_load_wav_file(full, &buf, &sz)) {
            if (*total_bytes + sz <= VP_MAX_PLAYER_BYTES) {
                sl->clips[sl->count].data = buf;
                sl->clips[sl->count].size = sz;
                sl->count++;
                *total_bytes += sz;
            } else {
                free(buf);
            }
        }
    } while (FindNextFileA(h, &fd));
    FindClose(h);
}

static inline void vp_load_active_player(int slot_idx, int player_id, int opp_id) {
    if (slot_idx < 0 || slot_idx > 1) return;
    vp_active_player_t *ap = &g_vp.active[slot_idx];
    vp_free_active_player(ap);
    ap->player_id = player_id;
    ap->opp_id = opp_id;
    if (!g_vp.initialized || !g_vp.enabled) return;
    if (player_id < 0 || player_id >= VP_MAX_ROSTER_IDS) return;
    if (!g_vp.has_folder[player_id]) return;

    char pdir[32];
    vp_format_player_dir(player_id, pdir, sizeof(pdir));
    char base_dir[MAX_PATH];
    snprintf(base_dir, sizeof(base_dir), "%s\\%s", g_vp.voices_root, pdir);

    for (int e = 0; e < VP_EV_COUNT; e++) {
        char ev_dir[MAX_PATH];
        snprintf(ev_dir, sizeof(ev_dir), "%s\\%s", base_dir, g_vp_event_dirs[e]);
        vp_load_slot_dir(&ap->events[e], ev_dir, &ap->total_bytes);
    }

    /* Rivalry folder: check both vs_<id>_<CODE> (e.g. vs_41_TSI) and vs_<CODE> (e.g. vs_TSI) */
    if (opp_id >= 0 && opp_id < VP_MAX_ROSTER_IDS) {
        char rdir[MAX_PATH];
        snprintf(rdir, sizeof(rdir), "%s\\vs_%02d_%s", base_dir, opp_id, g_vp_codes[opp_id]);
        vp_load_slot_dir(&ap->rivalry, rdir, &ap->total_bytes);
        if (ap->rivalry.count == 0) {
            snprintf(rdir, sizeof(rdir), "%s\\vs_%s", base_dir, g_vp_codes[opp_id]);
            vp_load_slot_dir(&ap->rivalry, rdir, &ap->total_bytes);
        }
    }
}

/*
 * Initialize the voice pack engine once at startup.
 * game_dir: path to VT4 game directory (e.g. "C:\\...\\game").
 */
static inline void vp_init(const char *game_dir) {
    memset(&g_vp, 0, sizeof(g_vp));
    g_vp.active[0].player_id = -1;
    g_vp.active[1].player_id = -1;
    g_vp.rivalry_prob_pct = 65;
    g_vp.rng_state = 0x9E3779B9u ^ (uint32_t)GetTickCount();

    if (!game_dir || !game_dir[0]) return;
    snprintf(g_vp.voices_root, sizeof(g_vp.voices_root), "%s\\archive\\voices", game_dir);

    g_vp.h_winmm = LoadLibraryA("winmm.dll");
    if (g_vp.h_winmm) {
        g_vp.fn_PlaySoundA = (vp_PlaySoundA_t)GetProcAddress(g_vp.h_winmm, "PlaySoundA");
    }

    /* One-time folder presence scan (0 disk I/O during matches for uncustomized players) */
    if (vp_dir_exists(g_vp.voices_root)) {
        for (int id = 0; id < VP_MAX_ROSTER_IDS; id++) {
            char pdir[32], full[MAX_PATH];
            vp_format_player_dir(id, pdir, sizeof(pdir));
            snprintf(full, sizeof(full), "%s\\%s", g_vp.voices_root, pdir);
            if (vp_dir_exists(full)) {
                g_vp.has_folder[id] = 1;
            }
        }
    }
    g_vp.enabled = (g_vp.fn_PlaySoundA != NULL) ? 1 : 0;
    g_vp.initialized = 1;
}

/*
 * Preload WAV clips into RAM for both match participants (call when match loads).
 */
static inline void vp_on_match_start(int p1_id, int p2_id) {
    if (!g_vp.initialized) return;
    vp_load_active_player(0, p1_id, p2_id);
    vp_load_active_player(1, p2_id, p1_id);
    g_vp.last_play_tick[0] = 0;
    g_vp.last_play_tick[1] = 0;
    g_vp.last_quote_tick[0] = 0;
    g_vp.last_quote_tick[1] = 0;
}

/*
 * Attempt to play a contextual custom voice clip from memory.
 * Returns 1 if a custom WAV was played, 0 if none exists (let VT4's native voice play).
 */
static inline int vp_try_play_event(int player_id, int opp_id, vp_event_t ev) {
    if (!g_vp.initialized || !g_vp.enabled || !g_vp.fn_PlaySoundA) return 0;
    if ((int)ev < 0 || ev >= VP_EV_COUNT) return 0;

    int slot_idx = -1;
    if (g_vp.active[0].player_id == player_id) slot_idx = 0;
    else if (g_vp.active[1].player_id == player_id) slot_idx = 1;
    else return 0;

    vp_active_player_t *ap = &g_vp.active[slot_idx];
    DWORD now = GetTickCount();
    int is_quote = (ev >= VP_EV_POINT_WIN);

    /* Cooldown check to prevent overlapping audio spam */
    if (is_quote) {
        if (g_vp.last_quote_tick[slot_idx] != 0 && (now - g_vp.last_quote_tick[slot_idx]) < 2200u) {
            return 0;
        }
    } else {
        if (g_vp.last_play_tick[slot_idx] != 0 && (now - g_vp.last_play_tick[slot_idx]) < 400u) {
            return 0;
        }
    }

    vp_slot_t *chosen = NULL;
    /* For quote events, prefer rivalry clip with configurable probability when opponent matches */
    if (is_quote && ap->rivalry.count > 0 && (opp_id < 0 || opp_id == ap->opp_id)) {
        if ((int)(vp_rng_next() % 100u) < g_vp.rivalry_prob_pct) {
            chosen = &ap->rivalry;
        }
    }
    if (!chosen || chosen->count == 0) {
        chosen = &ap->events[(int)ev];
    }
    if (!chosen || chosen->count == 0) return 0;

    int idx = (int)(vp_rng_next() % (uint32_t)chosen->count);
    if (chosen->count > 1 && idx == chosen->last_idx) {
        idx = (idx + 1) % chosen->count;
    }
    chosen->last_idx = idx;

    vp_clip_t *clip = &chosen->clips[idx];
    if (!clip->data || clip->size < 44) return 0;

    /* SND_MEMORY (0x0004) | SND_ASYNC (0x0001) | SND_NODEFAULT (0x0002) */
    DWORD flags = 0x0004u | 0x0001u | 0x0002u;
    if (!is_quote) {
        /* Do not interrupt an active quote with a short grunt: SND_NOSTOP (0x0010) */
        flags |= 0x0010u;
    }
    if (g_vp.fn_PlaySoundA((LPCSTR)clip->data, NULL, flags)) {
        g_vp.last_play_tick[slot_idx] = now;
        if (is_quote) g_vp.last_quote_tick[slot_idx] = now;
        return 1;
    }
    return 0;
}

static inline void vp_shutdown(void) {
    if (!g_vp.initialized) return;
    if (g_vp.fn_PlaySoundA) {
        g_vp.fn_PlaySoundA(NULL, NULL, 0);
    }
    vp_free_active_player(&g_vp.active[0]);
    vp_free_active_player(&g_vp.active[1]);
    if (g_vp.h_winmm) {
        FreeLibrary(g_vp.h_winmm);
        g_vp.h_winmm = NULL;
    }
    g_vp.fn_PlaySoundA = NULL;
    g_vp.initialized = 0;
}

#ifdef __cplusplus
}
#endif

#endif /* VT4_VOICE_PACKS_H */
