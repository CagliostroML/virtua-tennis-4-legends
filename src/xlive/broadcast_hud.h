/*
 * Official TV Broadcast Scoreboard & Telemetry HUD for Virtua Tennis 4: Legends & Next-Gen Edition.
 *
 * Self-contained header included in src/xlive/xlive.c after overlay primitives
 * (draw_screen_quad, draw_font_text, begin_overlay_state, end_overlay_state,
 *  init_menu_fonts, g_pFont, g_pFontTitle, g_pSprite, g_d3dx_createtex,
 *  g_real_drawprimitiveup, g_game_dir) and hk_StoLookup / g_tr_common_sto.
 *
 * Features:
 *   - Modular sprite layers (D3DPOOL_MANAGED textures loaded lazily per active tournament theme:
 *     ao, rg, wim, uso, mad, tour) + shared 27-flag IOC atlas (flags_ioc.png)
 *   - Reads live Match -> TennisStatus score from VT4.exe RAM (Sets, Games per Set,
 *     Points 0/15/30/40/AD or Tie-Break, Server indicator, Match Clock, Fault & Break/Set/Match Point)
 *   - Live ball speed radar (km/h), match Peak Speed, and live Rally Counter
 *   - Toggleable live with [F7] or via Options -> Graficos HD y Legends (BroadcastHUD=0/1)
 */
#ifndef VT4_BROADCAST_HUD_H
#define VT4_BROADCAST_HUD_H

#include <ctype.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <windows.h>

enum {
    BHUD_THEME_AO   = 0,
    BHUD_THEME_RG   = 1,
    BHUD_THEME_WIM  = 2,
    BHUD_THEME_USO  = 3,
    BHUD_THEME_MAD  = 4,
    BHUD_THEME_TOUR = 5,
    BHUD_THEME_COUNT = 6
};

typedef struct {
    int         theme_idx;
    const char *theme_key;
    const char *title;
    DWORD       accent_argb;
    DWORD       point_ink_argb;
} BhudTournamentInfo;

typedef struct {
    int      valid;
    int      num_sets_cfg;
    int      cur_set;
    int      sets[2];
    int      games[2];
    int      pts[2];
    int      adv[2];
    int      set_games[2][5];
    int      is_p1_serving; /* 1=P1 serving, 0=P2 serving, -1=unknown */
    int      is_fault;
    int      is_tiebreak;
    int      pressure_flag; /* 0=none, 1=BREAK POINT, 2=SET POINT, 3=MATCH POINT */
    int      match_sec;
} BhudLiveScore;

typedef struct {
    int   attempted;
    void *panel;
    void *emblem;
    void *point_box;
    void *serve_dot;
    void *alert_bar;
} BhudThemeTextures;

static BhudTournamentInfo g_bhud_stage = {
    BHUD_THEME_TOUR, "tour", "WORLD TOUR", 0xFF349EF6, 0xFF101622
};
static BhudLiveScore g_bhud_score = { 0 };
static BhudThemeTextures g_bhud_tex[BHUD_THEME_COUNT] = { { 0 } };
static void *g_bhud_flags_tex = NULL;
static int   g_bhud_flags_attempted = 0;

static int      g_bhud_last_kmh     = 0;
static int      g_bhud_max_kmh      = 0;
static uint32_t g_bhud_rally        = 0;
static uint32_t g_bhud_best_rally   = 0;
static float    g_bhud_last_vz      = 0.0f;
static uint32_t g_bhud_last_shot_ms = 0;

static inline int bhud_ci_contains(const char *hay, const char *needle) {
    if (!hay || !needle) return 0;
    size_t nlen = strlen(needle);
    if (nlen == 0) return 0;
    for (const char *p = hay; *p; p++) {
        if (_strnicmp(p, needle, nlen) == 0) return 1;
    }
    return 0;
}

static inline void bhud_reset_match_telemetry(void) {
    g_bhud_last_kmh = 0;
    g_bhud_max_kmh = 0;
    g_bhud_rally = 0;
    g_bhud_best_rally = 0;
    g_bhud_last_vz = 0.0f;
    g_bhud_last_shot_ms = 0;
    memset(&g_bhud_score, 0, sizeof(g_bhud_score));
    g_bhud_score.is_p1_serving = -1;
}

static inline void bhud_on_archive_lookup(const char *rel_path) {
    if (!rel_path || !bhud_ci_contains(rel_path, "Stage") || !bhud_ci_contains(rel_path, "TA_S_")) {
        return;
    }
    BhudTournamentInfo info = { BHUD_THEME_TOUR, "tour", "WORLD TOUR", 0xFF349EF6, 0xFF101622 };
    if (bhud_ci_contains(rel_path, "Aus1") || bhud_ci_contains(rel_path, "Aus4")) {
        info.theme_idx = BHUD_THEME_AO;
        info.theme_key = "ao";
        info.title = "AUSTRALIAN OPEN";
        info.accent_argb = 0xFF00A8F0;
        info.point_ink_argb = 0xFF0A1838;
    } else if (bhud_ci_contains(rel_path, "Fra1") || bhud_ci_contains(rel_path, "Fra4")) {
        info.theme_idx = BHUD_THEME_RG;
        info.theme_key = "rg";
        info.title = "ROLAND-GARROS";
        info.accent_argb = 0xFFDA602C;
        info.point_ink_argb = 0xFF122C20;
    } else if (bhud_ci_contains(rel_path, "Eng1") || bhud_ci_contains(rel_path, "Eng4")) {
        info.theme_idx = BHUD_THEME_WIM;
        info.theme_key = "wim";
        info.title = "WIMBLEDON";
        info.accent_argb = 0xFFD8B458;
        info.point_ink_argb = 0xFFFFFFFF;
    } else if (bhud_ci_contains(rel_path, "Usa1") || bhud_ci_contains(rel_path, "Usa4")) {
        info.theme_idx = BHUD_THEME_USO;
        info.theme_key = "uso";
        info.title = "US OPEN";
        info.accent_argb = 0xFFF2D238;
        info.point_ink_argb = 0xFF0C1834;
    } else if (bhud_ci_contains(rel_path, "Spa2")) {
        info.theme_idx = BHUD_THEME_MAD;
        info.theme_key = "mad";
        info.title = "MUTUA MADRID OPEN";
        info.accent_argb = 0xFF24B2FA;
        info.point_ink_argb = 0xFFFFFFFF;
    } else if (bhud_ci_contains(rel_path, "Fin0")) {
        info.title = "TOUR FINALS";
        info.accent_argb = 0xFFD4A838;
    } else if (bhud_ci_contains(rel_path, "Kin0")) {
        info.title = "KING COURT";
        info.accent_argb = 0xFFE04858;
    } else if (bhud_ci_contains(rel_path, "Exh")) {
        info.title = "INDOOR ARENA";
        info.accent_argb = 0xFF687CE8;
    } else if (bhud_ci_contains(rel_path, "Cla")) {
        info.title = "MASTERS 1000 CLAY";
        info.accent_argb = 0xFFC85A32;
    } else if (bhud_ci_contains(rel_path, "Gra")) {
        info.title = "GRASS CLASSIC";
        info.accent_argb = 0xFF34A853;
    } else if (bhud_ci_contains(rel_path, "Har")) {
        info.title = "ATP 500 HARD";
        info.accent_argb = 0xFF3A9BDC;
    }
    if (strcmp(g_bhud_stage.title, info.title) != 0) {
        g_bhud_stage = info;
        log_msg("[VT4-Mod] [BHUD] Active tournament detected: %s (%s)", info.title, rel_path);
    }
}

static inline void bhud_on_ball_launch(int is_serve) {
    if (is_serve) {
        g_bhud_rally = 0;
        g_bhud_last_vz = 0.0f;
    }
}

static inline void bhud_on_ball_simulate(const float *vel, int debug_log) {
    if (!vel) return;
    float vx = vel[0], vy = vel[1], vz = vel[2];
    if (!isfinite(vx) || !isfinite(vy) || !isfinite(vz)) return;
    float spd = sqrtf(vx * vx + vy * vy + vz * vz);
    /* Ignore gentle drop/toss ticks */
    if (spd < 1.2f || fabsf(vz) < 0.8f) return;

    uint32_t now = (uint32_t)GetTickCount();
    /* VT4 velocity uses decimeters per 60Hz tick: dm/f * 60 * 0.36 = speed * 21.6 km/h */
    int kmh = (int)(spd * 21.6f + 0.5f);
    if (kmh > 265) kmh = 265;
    if (kmh < 45) return;

    int flipped = (g_bhud_last_vz == 0.0f) || ((vz * g_bhud_last_vz) < 0.0f);
    if ((now - g_bhud_last_shot_ms) > 4800u) {
        g_bhud_rally = 1u;
    } else if (flipped && (now - g_bhud_last_shot_ms) >= 180u) {
        g_bhud_rally++;
    } else if (g_bhud_rally == 0u) {
        g_bhud_rally = 1u;
    }

    if (g_bhud_rally > g_bhud_best_rally) {
        g_bhud_best_rally = g_bhud_rally;
    }
    g_bhud_last_kmh = kmh;
    if (kmh > g_bhud_max_kmh) g_bhud_max_kmh = kmh;
    g_bhud_last_vz = vz;
    g_bhud_last_shot_ms = now;

    if (debug_log) {
        static uint32_t s_bhud_dbg = 0;
        if (s_bhud_dbg < 12) {
            s_bhud_dbg++;
            log_msg("[VT4-Mod] [BHUD] Shot spd=%.2f -> %d km/h (max=%d) rally=%u",
                    spd, kmh, g_bhud_max_kmh, g_bhud_rally);
        }
    }
}

static inline int bhud_is_readable(const void *ptr, size_t bytes) {
    if (!ptr || (uintptr_t)ptr < 0x10000u) return 0;
    const uintptr_t start = (uintptr_t)ptr;
    const uintptr_t end = start + bytes;
    uintptr_t cur = start;
    while (cur < end) {
        MEMORY_BASIC_INFORMATION mbi;
        if (VirtualQuery((LPCVOID)cur, &mbi, sizeof(mbi)) == 0) return 0;
        if (mbi.State != MEM_COMMIT) return 0;
        DWORD prot = mbi.Protect & 0xFFu;
        if (prot != PAGE_READONLY && prot != PAGE_READWRITE && prot != PAGE_WRITECOPY &&
            prot != PAGE_EXECUTE_READ && prot != PAGE_EXECUTE_READWRITE && prot != PAGE_EXECUTE_WRITECOPY) {
            return 0;
        }
        uintptr_t next = (uintptr_t)mbi.BaseAddress + mbi.RegionSize;
        if (next <= cur) return 0;
        cur = next;
    }
    return 1;
}

static inline void bhud_update_live_score(void *match_self, int debug_log) {
    /* match_self is Match* (0x164 bytes); Match+0x04 holds TennisStatus* */
    if (!bhud_is_readable(match_self, 0x0164)) {
        g_bhud_score.valid = 0;
        return;
    }
    void *ts = *(void **)((const char *)match_self + 0x04);
    if (!bhud_is_readable(ts, 0x1d0)) {
        g_bhud_score.valid = 0;
        return;
    }

    BhudLiveScore sc;
    memset(&sc, 0, sizeof(sc));
    sc.is_p1_serving = -1;

    int cfg_sets = *(const int *)0x00821604;
    sc.num_sets_cfg = (cfg_sets >= 1 && cfg_sets <= 5) ? cfg_sets : 3;

    sc.sets[0]  = *(const int *)((const char *)ts + 0x18);
    sc.games[0] = *(const int *)((const char *)ts + 0x1c);
    sc.pts[0]   = *(const int *)((const char *)ts + 0x20);
    sc.adv[0]   = *(const uint8_t *)((const char *)ts + 0x28) ? 1 : 0;

    sc.sets[1]  = *(const int *)((const char *)ts + 0x2c);
    sc.games[1] = *(const int *)((const char *)ts + 0x30);
    sc.pts[1]   = *(const int *)((const char *)ts + 0x34);
    sc.adv[1]   = *(const uint8_t *)((const char *)ts + 0x3c) ? 1 : 0;

    int cur_s = *(const int *)((const char *)ts + 0x1a0);
    if (cur_s < 0 || cur_s >= 5 ||
        sc.sets[0] < 0 || sc.sets[0] > 5 || sc.sets[1] < 0 || sc.sets[1] > 5 ||
        sc.pts[0] < 0 || sc.pts[0] > 99 || sc.pts[1] < 0 || sc.pts[1] > 99) {
        g_bhud_score.valid = 0;
        return;
    }
    sc.cur_set = cur_s;
    for (int s = 0; s < 5; s++) {
        int g0 = *(const int *)((const char *)ts + 0x0a0 + s * 4);
        int g1 = *(const int *)((const char *)ts + 0x0e0 + s * 4);
        sc.set_games[0][s] = (g0 >= 0 && g0 <= 99) ? g0 : 0;
        sc.set_games[1][s] = (g1 >= 0 && g1 <= 99) ? g1 : 0;
    }
    if (sc.set_games[0][cur_s] == 0 && sc.games[0] > 0 && sc.games[0] <= 99) {
        sc.set_games[0][cur_s] = sc.games[0];
    }
    if (sc.set_games[1][cur_s] == 0 && sc.games[1] > 0 && sc.games[1] <= 99) {
        sc.set_games[1][cur_s] = sc.games[1];
    }

    sc.is_fault    = *(const uint8_t *)((const char *)ts + 0x1a8) ? 1 : 0;
    sc.is_tiebreak = *(const uint8_t *)((const char *)ts + 0x1a9) ? 1 : 0;

    int bp = (*(const uint8_t *)((const char *)ts + 0x0b9)) || (*(const uint8_t *)((const char *)ts + 0x0f9));
    int sp = (*(const uint8_t *)((const char *)ts + 0x0ba)) || (*(const uint8_t *)((const char *)ts + 0x0fa));
    int mp = (*(const uint8_t *)((const char *)ts + 0x0bb)) || (*(const uint8_t *)((const char *)ts + 0x0fb));
    if (mp) sc.pressure_flag = 3;
    else if (sp) sc.pressure_flag = 2;
    else if (bp) sc.pressure_flag = 1;

    int ticks = *(const int *)((const char *)ts + 0x1c4);
    sc.match_sec = (ticks > 0 && ticks < 2160000) ? (ticks / 60) : 0;

    typedef int (__thiscall *BhudIsServerFn_t)(void *, int);
    int srv_id = ((BhudIsServerFn_t)0x0045fc50)(ts, 0);
    int num_p  = *(const int *)0x0082160c;
    if (srv_id >= 0 && srv_id < 4) {
        sc.is_p1_serving = (num_p <= 2) ? (srv_id == 0 ? 1 : 0) : (srv_id < 2 ? 1 : 0);
    }

    sc.valid = 1;

    if (debug_log) {
        static int s_last_logged[7] = { -1, -1, -1, -1, -1, -1, -1 };
        int raw84 = *(const int *)((const char *)ts + 0x84);
        int raw88 = *(const int *)((const char *)ts + 0x88);
        int raw8c = *(const int *)((const char *)ts + 0x8c);
        if (sc.pts[0] != s_last_logged[0] || sc.pts[1] != s_last_logged[1] ||
            sc.games[0] != s_last_logged[2] || sc.games[1] != s_last_logged[3] ||
            sc.sets[0] != s_last_logged[4] || sc.sets[1] != s_last_logged[5] ||
            sc.is_p1_serving != s_last_logged[6]) {
            s_last_logged[0] = sc.pts[0];
            s_last_logged[1] = sc.pts[1];
            s_last_logged[2] = sc.games[0];
            s_last_logged[3] = sc.games[1];
            s_last_logged[4] = sc.sets[0];
            s_last_logged[5] = sc.sets[1];
            s_last_logged[6] = sc.is_p1_serving;
            log_msg("[VT4-Mod] [BHUD] LiveScore: cur_set=%d sets=%d-%d games=%d-%d pts=%d-%d adv=%d-%d srv=%d(srv_id=%d,np=%d,r84=%d,r88=%d,r8c=%d) tb=%d flt=%d pres=%d t=%d",
                    sc.cur_set, sc.sets[0], sc.sets[1], sc.games[0], sc.games[1],
                    sc.pts[0], sc.pts[1], sc.adv[0], sc.adv[1],
                    sc.is_p1_serving, srv_id, num_p, raw84, raw88, raw8c,
                    sc.is_tiebreak, sc.is_fault, sc.pressure_flag, sc.match_sec);
        }
    }

    g_bhud_score = sc;
}

static inline void bhud_draw_textured_quad_uv(void *dev, void *tex,
                                              float x1, float y1, float x2, float y2,
                                              float u1, float v1, float u2, float v2,
                                              DWORD color) {
    if (!dev || !tex || !g_real_drawprimitiveup) return;
    TexturedVertex verts[4] = {
        { x1 - 0.5f, y1 - 0.5f, 0.0f, 1.0f, color, u1, v1 },
        { x2 - 0.5f, y1 - 0.5f, 0.0f, 1.0f, color, u2, v1 },
        { x1 - 0.5f, y2 - 0.5f, 0.0f, 1.0f, color, u1, v2 },
        { x2 - 0.5f, y2 - 0.5f, 0.0f, 1.0f, color, u2, v2 }
    };

    void **vtbl = *(void ***)dev;
    typedef HRESULT (__stdcall *SetFVF_t)(void *, DWORD);
    typedef HRESULT (__stdcall *SetRenderState_t)(void *, DWORD, DWORD);
    typedef HRESULT (__stdcall *SetTexture_t)(void *, DWORD, void *);
    typedef HRESULT (__stdcall *SetTextureStageState_t)(void *, DWORD, DWORD, DWORD);
    typedef HRESULT (__stdcall *SetSamplerState_t)(void *, DWORD, DWORD, DWORD);
    typedef HRESULT (__stdcall *SetVertexShader_t)(void *, void *);
    typedef HRESULT (__stdcall *SetPixelShader_t)(void *, void *);

    SetFVF_t set_fvf = (SetFVF_t)vtbl[89];
    SetRenderState_t set_rs = (SetRenderState_t)vtbl[57];
    SetTexture_t set_tex = (SetTexture_t)vtbl[65];
    SetTextureStageState_t set_tss = (SetTextureStageState_t)vtbl[67];
    SetSamplerState_t set_samp = (SetSamplerState_t)vtbl[69];
    SetVertexShader_t set_vs = (SetVertexShader_t)vtbl[92];
    SetPixelShader_t set_ps = (SetPixelShader_t)vtbl[107];

    if (set_vs) set_vs(dev, NULL);
    if (set_ps) set_ps(dev, NULL);

    if (set_rs) {
        set_rs(dev, 27, 1);
        set_rs(dev, 19, 5);
        set_rs(dev, 20, 6);
        set_rs(dev, 15, 0);
        set_rs(dev, 137, 0);
        set_rs(dev, 22, 1);
        set_rs(dev, 7, 0);
    }
    if (set_tss) {
        set_tss(dev, 0, 1, 4);
        set_tss(dev, 0, 2, 2);
        set_tss(dev, 0, 3, 0);
        set_tss(dev, 0, 4, 4);
        set_tss(dev, 0, 5, 2);
        set_tss(dev, 0, 6, 0);
        set_tss(dev, 1, 1, 1);
        set_tss(dev, 1, 4, 1);
    }
    if (set_samp) {
        set_samp(dev, 0, 1, 2);
        set_samp(dev, 0, 2, 2);
    }

    if (set_tex) set_tex(dev, 0, tex);
    if (set_fvf) set_fvf(dev, FVF_TEXTURED_VERTEX);
    g_real_drawprimitiveup(dev, 5, 2, verts, sizeof(TexturedVertex));
    if (set_tex) set_tex(dev, 0, NULL);
}

static inline void bhud_ensure_theme_textures(void *dev, int theme_idx, const char *key) {
    if (!dev || !g_d3dx_createtex || !g_game_dir[0]) return;
    if (theme_idx < 0 || theme_idx >= BHUD_THEME_COUNT) return;

    if (!g_bhud_flags_attempted) {
        g_bhud_flags_attempted = 1;
        char path[MAX_PATH];
        snprintf(path, sizeof(path), "%s\\archive\\hud\\scoreboards\\flags_ioc.png", g_game_dir);
        if (FAILED(g_d3dx_createtex(dev, path, &g_bhud_flags_tex))) {
            g_bhud_flags_tex = NULL;
        }
    }

    BhudThemeTextures *t = &g_bhud_tex[theme_idx];
    if (t->attempted) return;
    t->attempted = 1;

    char path[MAX_PATH];
    const char *names[5] = { "panel", "emblem", "point_box", "serve_dot", "alert_bar" };
    void **ptrs[5] = { &t->panel, &t->emblem, &t->point_box, &t->serve_dot, &t->alert_bar };
    for (int i = 0; i < 5; i++) {
        snprintf(path, sizeof(path), "%s\\archive\\hud\\scoreboards\\%s_%s.png", g_game_dir, names[i], key);
        if (FAILED(g_d3dx_createtex(dev, path, ptrs[i]))) {
            *(ptrs[i]) = NULL;
        }
    }
    log_msg("[VT4-Mod] [BHUD] Loaded scoreboard sprites for '%s' (panel=%p flags=%p)",
            key, t->panel, g_bhud_flags_tex);
}

static inline int bhud_lookup_flag_idx(const char *ioc) {
    static const char *const k_codes[26] = {
        "ARG", "AUS", "AUT", "BEL", "BLR", "BRA",
        "CHI", "CRO", "CZE", "DEN", "ESP", "FRA",
        "GBR", "GER", "GRE", "ITA", "JPN", "KAZ",
        "NOR", "POL", "ROU", "RUS", "SRB", "SUI",
        "SWE", "USA"
    };
    if (!ioc || !ioc[0]) return 26;
    for (int i = 0; i < 26; i++) {
        if (_stricmp(ioc, k_codes[i]) == 0) return i;
    }
    /* Map alternate country aliases cleanly */
    if (_stricmp(ioc, "UK") == 0 || _stricmp(ioc, "ENG") == 0) return 12; /* GBR */
    if (_stricmp(ioc, "YUG") == 0) return 22; /* SRB */
    if (_stricmp(ioc, "CHL") == 0) return 6;  /* CHI */
    if (_stricmp(ioc, "CHE") == 0) return 23; /* SUI */
    if (_stricmp(ioc, "DEU") == 0) return 13; /* GER */
    if (_stricmp(ioc, "HRV") == 0) return 7;  /* CRO */
    if (_stricmp(ioc, "DNK") == 0) return 9;  /* DEN */
    return 26;
}

static inline void bhud_format_tv_name(const char *src, char *dst, size_t cap) {
    if (!dst || cap == 0) return;
    if (!src || !src[0]) {
        snprintf(dst, cap, "PLAYER");
        return;
    }
    /* Transliterate UTF-8 accented letters to clean uppercase ASCII for D3DXFont ANSI */
    char clean[64];
    size_t oi = 0;
    const unsigned char *s = (const unsigned char *)src;
    while (*s && oi + 1 < sizeof(clean)) {
        unsigned char c = *s;
        if (c < 0x80u) {
            clean[oi++] = (char)toupper((int)c);
            s++;
        } else if (c == 0xC3u && s[1]) {
            unsigned char b = s[1];
            char rep = ' ';
            if (b >= 0x80u && b <= 0x85u) rep = 'A';
            else if (b >= 0xA0u && b <= 0xA5u) rep = 'A';
            else if (b == 0x87u || b == 0xA7u) rep = 'C';
            else if (b >= 0x88u && b <= 0x8Bu) rep = 'E';
            else if (b >= 0xA8u && b <= 0xABu) rep = 'E';
            else if (b >= 0x8Cu && b <= 0x8Fu) rep = 'I';
            else if (b >= 0xACu && b <= 0xAFu) rep = 'I';
            else if (b == 0x91u || b == 0xB1u) rep = 'N';
            else if ((b >= 0x92u && b <= 0x96u) || (b >= 0xB2u && b <= 0xB6u)) rep = 'O';
            else if ((b >= 0x99u && b <= 0x9Cu) || (b >= 0xB9u && b <= 0xBCu)) rep = 'U';
            else if (b == 0x9Du || b == 0xBDu || b == 0xBFu) rep = 'Y';
            if (rep != ' ') clean[oi++] = rep;
            s += 2;
        } else if ((c == 0xC4u || c == 0xC5u) && s[1]) {
            unsigned char b = s[1];
            char rep = '?';
            if (c == 0xC5u && (b == 0x9Au || b == 0x9Bu || b == 0xA0u || b == 0xA1u)) rep = 'S';
            else if (c == 0xC4u && (b == 0x84u || b == 0x85u)) rep = 'A';
            else if (c == 0xC4u && (b == 0x86u || b == 0x87u || b == 0x8Cu || b == 0x8Du)) rep = 'C';
            else if (c == 0xC4u && (b == 0x98u || b == 0x99u)) rep = 'E';
            else if (c == 0xC5u && (b == 0x81u || b == 0x82u)) rep = 'L';
            else if (c == 0xC5u && (b == 0x83u || b == 0x84u)) rep = 'N';
            else if (c == 0xC5u && (b == 0xB9u || b == 0xBAu || b == 0xBBu || b == 0xBCu || b == 0xBDu || b == 0xBEu)) rep = 'Z';
            if (rep != '?') clean[oi++] = rep;
            s += 2;
        } else {
            s++;
        }
    }
    clean[oi] = '\0';

    /* Convert "CARLOS ALCARAZ" -> "C. ALCARAZ", preserving short forms like "B.J. KING" */
    char *dot = strchr(clean, '.');
    char *sp = strchr(clean, ' ');
    if (dot && dot < sp) {
        snprintf(dst, cap, "%s", clean);
    } else if (sp && sp[1] && strlen(clean) > 13) {
        snprintf(dst, cap, "%c. %s", clean[0], sp + 1);
    } else {
        snprintf(dst, cap, "%s", clean);
    }
}

static inline void bhud_format_point(int pts, int adv, int is_tb, char *out, size_t cap) {
    if (is_tb) {
        snprintf(out, cap, "%d", pts);
        return;
    }
    if (adv) {
        snprintf(out, cap, "AD");
        return;
    }
    switch (pts) {
        case 0:  snprintf(out, cap, "0");  break;
        case 1:  snprintf(out, cap, "15"); break;
        case 2:  snprintf(out, cap, "30"); break;
        default: snprintf(out, cap, "40"); break;
    }
}

static inline void render_broadcast_tv_hud(void *dev, int in_live_match, uint32_t enabled,
                                           int menu_vis, int np_vis, int ee1_fury,
                                           int p1_id, int p2_id,
                                           float sx, float sy) {
    if (!dev || !in_live_match || !enabled || menu_vis || np_vis) return;
    init_menu_fonts(dev);
    if (!g_pFont || !g_pSprite) return;

    (void)ee1_fury;
    bhud_ensure_theme_textures(dev, g_bhud_stage.theme_idx, g_bhud_stage.theme_key);
    const BhudThemeTextures *tex = &g_bhud_tex[g_bhud_stage.theme_idx];
    const BhudLiveScore sc = g_bhud_score;

    int num_sets_vis = (sc.valid && sc.cur_set >= 0 && sc.cur_set < 5) ? (sc.cur_set + 1) : 1;
    int extra_sets = num_sets_vis - 1;

    /* Official TV Scorebug anchored top-left in 1280x720 reference space (clear of native popups) */
    float pw = (338.0f + (float)extra_sets * 20.0f) * sx;
    float ph = 86.0f * sy;
    float px1 = 16.0f * sx;
    float px2 = px1 + pw;
    float py1 = 10.0f * sy;
    float py2 = py1 + ph;
    float sub_y1 = py2 + 3.0f * sy;
    float sub_y2 = sub_y1 + 22.0f * sy;

    if (!begin_overlay_state(dev)) return;

    /* 1. Main scoreboard panel + tournament emblem + alert sub-bar */
    if (tex->panel) {
        bhud_draw_textured_quad_uv(dev, tex->panel, px1, py1, px2, py2, 0.0f, 0.0f, 1.0f, 1.0f, 0xFFFFFFFF);
    } else {
        draw_screen_quad(dev, px1, py1, px2, py2, 0xE20B1220);
        draw_screen_quad(dev, px1, py1, px1 + 5.0f * sx, py2, g_bhud_stage.accent_argb);
        draw_screen_quad(dev, px1, py1, px2, py1 + 22.0f * sy, g_bhud_stage.accent_argb);
    }
    if (tex->emblem) {
        bhud_draw_textured_quad_uv(dev, tex->emblem,
                                   px1 + 10.0f * sx, py1 + 2.5f * sy,
                                   px1 + 27.0f * sx, py1 + 19.5f * sy,
                                   0.0f, 0.0f, 1.0f, 1.0f, 0xFFFFFFFF);
    }
    if (tex->alert_bar) {
        bhud_draw_textured_quad_uv(dev, tex->alert_bar, px1, sub_y1, px2, sub_y2, 0.0f, 0.0f, 1.0f, 1.0f, 0xFFFFFFFF);
    } else {
        draw_screen_quad(dev, px1, sub_y1, px2, sub_y2, 0xD8080D18);
        draw_screen_quad(dev, px1, sub_y1, px1 + 5.0f * sx, sub_y2, g_bhud_stage.accent_argb);
    }

    /* 2. Lookup names & IOC codes cleanly via TR_COMMON */
    char p1_raw[48] = "PLAYER 1";
    char p2_raw[48] = "PLAYER 2";
    const char *ioc1 = "";
    const char *ioc2 = "";
    if (g_tr_common_sto) {
        if (p1_id >= 0 && p1_id < MAX_ROSTER_PLAYERS) {
            const char *nm = hk_StoLookup(g_tr_common_sto, NULL, 4, p1_id);
            const char *cc = hk_StoLookup(g_tr_common_sto, NULL, 6, p1_id);
            if (nm && nm[0]) snprintf(p1_raw, sizeof(p1_raw), "%s", nm);
            if (cc && cc[0]) ioc1 = cc;
        }
        if (p2_id >= 0 && p2_id < MAX_ROSTER_PLAYERS) {
            const char *nm = hk_StoLookup(g_tr_common_sto, NULL, 4, p2_id);
            const char *cc = hk_StoLookup(g_tr_common_sto, NULL, 6, p2_id);
            if (nm && nm[0]) snprintf(p2_raw, sizeof(p2_raw), "%s", nm);
            if (cc && cc[0]) ioc2 = cc;
        }
    }
    char p1_name[48], p2_name[48];
    bhud_format_tv_name(p1_raw, p1_name, sizeof(p1_name));
    bhud_format_tv_name(p2_raw, p2_name, sizeof(p2_name));

    const char *p_names[2] = { p1_name, p2_name };
    const char *p_iocs[2]  = { ioc1, ioc2 };

    float pt_x2 = px2 - 7.0f * sx;
    float pt_x1 = pt_x2 - 42.0f * sx;
    float sets_right = pt_x1 - 5.0f * sx;
    float sets_x0 = sets_right - (float)num_sets_vis * 22.0f * sx;
    float srv_x1 = sets_x0 - 15.0f * sx;

    /* 3. Render per-row sprites: Flag + Serve Dot + Point Box */
    for (int row = 0; row < 2; row++) {
        float ry1 = py1 + (row == 0 ? 23.0f : 54.0f) * sy;
        float ry2 = ry1 + 30.0f * sy;

        if (g_bhud_flags_tex) {
            int fidx = bhud_lookup_flag_idx(p_iocs[row]);
            int fcol = fidx % 6;
            int frow = fidx / 6;
            float u1 = (float)fcol / 6.0f;
            float u2 = (float)(fcol + 1) / 6.0f;
            float v1 = (float)frow / 5.0f;
            float v2 = (float)(frow + 1) / 5.0f;
            bhud_draw_textured_quad_uv(dev, g_bhud_flags_tex,
                                       px1 + 11.0f * sx, ry1 + 8.0f * sy,
                                       px1 + 32.0f * sx, ry1 + 21.5f * sy,
                                       u1, v1, u2, v2, 0xFFFFFFFF);
        }

        int is_srv = (sc.valid && ((row == 0 && sc.is_p1_serving == 1) || (row == 1 && sc.is_p1_serving == 0)));
        if (is_srv) {
            if (tex->serve_dot) {
                bhud_draw_textured_quad_uv(dev, tex->serve_dot,
                                           srv_x1, ry1 + 9.0f * sy,
                                           srv_x1 + 12.0f * sx, ry1 + 21.0f * sy,
                                           0.0f, 0.0f, 1.0f, 1.0f, 0xFFFFFFFF);
            } else {
                draw_screen_quad(dev, srv_x1 + 2.0f * sx, ry1 + 11.0f * sy,
                                 srv_x1 + 10.0f * sx, ry1 + 19.0f * sy, 0xFFE8FA44);
            }
        }

        if (tex->point_box) {
            bhud_draw_textured_quad_uv(dev, tex->point_box,
                                       pt_x1, ry1 + 2.5f * sy, pt_x2, ry2 - 2.5f * sy,
                                       0.0f, 0.0f, 1.0f, 1.0f, 0xFFFFFFFF);
        } else {
            draw_screen_quad(dev, pt_x1, ry1 + 2.5f * sy, pt_x2, ry2 - 2.5f * sy, 0xFFF2F5FA);
        }
    }

    /* 4. Render typography cleanly on top via ID3DXSprite */
    char clock_buf[16];
    int m_min = (sc.valid ? sc.match_sec : 0) / 60;
    int m_sec = (sc.valid ? sc.match_sec : 0) % 60;
    snprintf(clock_buf, sizeof(clock_buf), "%02d:%02d", m_min, m_sec);

    char sub_buf[128];
    DWORD sub_col = 0xFFDCE8FC;
    uint32_t now = (uint32_t)GetTickCount();
    int recent_shot = (g_bhud_last_kmh > 0 && (now - g_bhud_last_shot_ms) < 5500u);
    const char *pres_str = NULL;
    if (sc.valid) {
        if (sc.pressure_flag == 3) { pres_str = "MATCH POINT"; sub_col = 0xFFFF6854; }
        else if (sc.pressure_flag == 2) { pres_str = "SET POINT"; sub_col = 0xFFFFB848; }
        else if (sc.pressure_flag == 1) { pres_str = "BREAK POINT"; sub_col = 0xFFFFE058; }
        else if (sc.is_tiebreak) { pres_str = "TIE-BREAK"; sub_col = 0xFF7AD8FF; }
    }
    if (pres_str && recent_shot) {
        snprintf(sub_buf, sizeof(sub_buf), "%s  |  BOLA %d km/h  |  RALLY %02u",
                 pres_str, g_bhud_last_kmh, (unsigned)g_bhud_rally);
    } else if (pres_str) {
        snprintf(sub_buf, sizeof(sub_buf), "%s  |  SETS AL MEJOR DE %d",
                 pres_str, sc.num_sets_cfg);
    } else if (recent_shot) {
        if (g_bhud_last_kmh >= 205) sub_col = 0xFFFF7858;
        else if (g_bhud_last_kmh >= 170) sub_col = 0xFFFFDC62;
        snprintf(sub_buf, sizeof(sub_buf), "BOLA %d km/h  |  MAX %d  |  RALLY %02u",
                 g_bhud_last_kmh, g_bhud_max_kmh, (unsigned)g_bhud_rally);
    } else if (sc.valid && sc.is_fault) {
        sub_col = 0xFFFFC868;
        snprintf(sub_buf, sizeof(sub_buf), "2ND SERVE  |  TV RADAR ACTIVO  |  [F7]");
    } else {
        snprintf(sub_buf, sizeof(sub_buf), "TV BROADCAST  |  RADAR ACTIVO  |  [F7] HUD");
    }

    void *f_bold = g_pFontTitle ? g_pFontTitle : g_pFont;
    void **svtbl = *(void ***)g_pSprite;
    typedef HRESULT (__stdcall *SpriteBegin_t)(void *, DWORD);
    typedef HRESULT (__stdcall *SpriteEnd_t)(void *);
    SpriteBegin_t sp_begin = (SpriteBegin_t)svtbl[8];
    SpriteEnd_t   sp_end   = (SpriteEnd_t)svtbl[11];
    if (!sp_begin || sp_begin(g_pSprite, 0x10) >= 0) {
        RECT r;
        /* Header tournament title & live match clock */
        r.left = (LONG)(px1 + 31.0f * sx);
        r.top = (LONG)(py1 + 1.0f * sy);
        r.right = (LONG)(px2 - 58.0f * sx);
        r.bottom = (LONG)(py1 + 21.0f * sy);
        draw_font_text(g_pFont, g_bhud_stage.title, &r, 0xFFFFFFFF, 0);

        r.left = (LONG)(px2 - 58.0f * sx);
        r.right = (LONG)(px2 - 10.0f * sx);
        draw_font_text(g_pFont, clock_buf, &r, 0xFFEAF2FF, 2);

        /* Rows: Name + Set Games + Point Box */
        for (int row = 0; row < 2; row++) {
            float ry1 = py1 + (row == 0 ? 23.0f : 54.0f) * sy;
            float ry2 = ry1 + 30.0f * sy;

            r.left = (LONG)(px1 + 36.0f * sx);
            r.top = (LONG)ry1;
            r.right = (LONG)(srv_x1 - 4.0f * sx);
            r.bottom = (LONG)ry2;
            draw_font_text(f_bold, p_names[row], &r, 0xFFFFFFFF, 0);

            for (int s = 0; s < num_sets_vis; s++) {
                char sg[12];
                int gval = sc.valid ? sc.set_games[row][s] : 0;
                snprintf(sg, sizeof(sg), "%d", gval);
                DWORD scol = (s == num_sets_vis - 1) ? 0xFFFFFFFF : 0xFFB8C6DE;
                r.left = (LONG)(sets_x0 + (float)s * 22.0f * sx);
                r.right = (LONG)(r.left + 21.0f * sx);
                draw_font_text(f_bold, sg, &r, scol, 1);
            }

            char pbuf[12];
            if (sc.valid) {
                bhud_format_point(sc.pts[row], sc.adv[row], sc.is_tiebreak, pbuf, sizeof(pbuf));
            } else {
                snprintf(pbuf, sizeof(pbuf), "0");
            }
            r.left = (LONG)pt_x1;
            r.right = (LONG)pt_x2;
            draw_font_text(f_bold, pbuf, &r, g_bhud_stage.point_ink_argb, 1);
        }

        /* Bottom telemetry & pressure alert sub-bar */
        r.left = (LONG)(px1 + 12.0f * sx);
        r.top = (LONG)sub_y1;
        r.right = (LONG)(px2 - 10.0f * sx);
        r.bottom = (LONG)sub_y2;
        draw_font_text(g_pFont, sub_buf, &r, sub_col, 0);

        if (sp_end) sp_end(g_pSprite);
    }

    end_overlay_state(dev);
}

#endif /* VT4_BROADCAST_HUD_H */
