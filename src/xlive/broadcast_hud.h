/*
 * Modern Broadcast TV HUD Overlay for Virtua Tennis 4: Legends & Next-Gen Edition.
 *
 * Self-contained header included in src/xlive/xlive.c after overlay primitives
 * (draw_screen_quad, draw_font_text, begin_overlay_state, end_overlay_state,
 *  init_menu_fonts, g_pFont, g_pFontTitle, g_pSprite) and hk_StoLookup / g_tr_common_sto.
 *
 * Features:
 *   - Zero extra D3D9 GPU objects (100% Reset/Alt+Tab/DXVK/Winlator safe)
 *   - Auto-detects active Grand Slam / Tour stadium when stage .sdo is opened
 *   - Live shot speed radar (km/h), match Peak Speed, and live Rally Counter
 *   - Displays authentic TV matchup line ("C. Alcaraz (ESP) vs J. Sinner (ITA)")
 *   - Toggleable live with [F7] or via Options -> Graficos HD y Legends (BroadcastHUD=0/1)
 */
#ifndef VT4_BROADCAST_HUD_H
#define VT4_BROADCAST_HUD_H

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <windows.h>

typedef struct {
    const char *title;
    DWORD       accent_argb;
} BhudTournamentInfo;

static BhudTournamentInfo g_bhud_stage = { "WORLD TOUR - STADIUM", 0xFF2AA6DF };
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
}

static inline void bhud_on_archive_lookup(const char *rel_path) {
    if (!rel_path || !bhud_ci_contains(rel_path, "Stage") || !bhud_ci_contains(rel_path, "TA_S_")) {
        return;
    }
    BhudTournamentInfo info = { "WORLD TOUR - STADIUM", 0xFF2AA6DF };
    if (bhud_ci_contains(rel_path, "Aus1") || bhud_ci_contains(rel_path, "Aus4")) {
        info.title = "AUSTRALIAN OPEN - HARD";
        info.accent_argb = 0xFF0091D2;
    } else if (bhud_ci_contains(rel_path, "Fra1") || bhud_ci_contains(rel_path, "Fra4")) {
        info.title = "ROLAND-GARROS - CLAY";
        info.accent_argb = 0xFFD96432;
    } else if (bhud_ci_contains(rel_path, "Eng1") || bhud_ci_contains(rel_path, "Eng4")) {
        info.title = "WIMBLEDON - GRASS";
        info.accent_argb = 0xFF289E5E;
    } else if (bhud_ci_contains(rel_path, "Usa1") || bhud_ci_contains(rel_path, "Usa4")) {
        info.title = "US OPEN - HARD";
        info.accent_argb = 0xFF2E6FD8;
    } else if (bhud_ci_contains(rel_path, "Spa2")) {
        info.title = "MUTUA MADRID - BLUE CLAY";
        info.accent_argb = 0xFF1BA0F2;
    } else if (bhud_ci_contains(rel_path, "Fin0")) {
        info.title = "TOUR FINALS - INDOOR";
        info.accent_argb = 0xFFD4A838;
    } else if (bhud_ci_contains(rel_path, "Kin0")) {
        info.title = "KING COURT - EXHIBITION";
        info.accent_argb = 0xFFE04858;
    } else if (bhud_ci_contains(rel_path, "Exh")) {
        info.title = "INDOOR ARENA - HARD";
        info.accent_argb = 0xFF687CE8;
    } else if (bhud_ci_contains(rel_path, "Cla")) {
        info.title = "MASTERS 1000 - CLAY";
        info.accent_argb = 0xFFC85A32;
    } else if (bhud_ci_contains(rel_path, "Gra")) {
        info.title = "GRASS CLASSIC - GRASS";
        info.accent_argb = 0xFF34A853;
    } else if (bhud_ci_contains(rel_path, "Har")) {
        info.title = "ATP 500 - HARD";
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

static inline void render_broadcast_tv_hud(void *dev, int in_live_match, uint32_t enabled,
                                           int menu_vis, int np_vis, int ee1_fury,
                                           int p1_id, int p2_id,
                                           float sx, float sy) {
    if (!dev || !in_live_match || !enabled || menu_vis || np_vis) return;
    init_menu_fonts(dev);
    if (!g_pFont || !g_pSprite) return;

    /* Top-left broadcast card in 1280x720 reference space (clear of scoreboard & PlayStyle bar) */
    (void)ee1_fury;
    float pw = 348.0f * sx;
    float ph = 60.0f * sy;
    float px1 = 16.0f * sx;
    float px2 = px1 + pw;
    float py1 = 10.0f * sy;
    float py2 = py1 + ph;

    if (!begin_overlay_state(dev)) return;

    /* Translucent obsidian TV card + tournament left accent stripe + bottom hairline */
    draw_screen_quad(dev, px1, py1, px2, py2, 0xD20B101C);
    draw_screen_quad(dev, px1, py1, px1 + 5.0f * sx, py2, g_bhud_stage.accent_argb);
    draw_screen_quad(dev, px1, py1, px2, py1 + 2.0f * sy, g_bhud_stage.accent_argb);
    draw_screen_quad(dev, px1, py2 - 1.5f * sy, px2, py2, 0x60FFFFFF);
    draw_screen_quad(dev, px1 + 10.0f * sx, py1 + 20.0f * sy, px2 - 10.0f * sx, py1 + 21.0f * sy, 0x38FFFFFF);

    /* Matchup strings via hk_StoLookup when TR_COMMON is ready */
    char p1_buf[48] = "PLAYER 1";
    char p2_buf[48] = "PLAYER 2";
    const char *ioc1 = "";
    const char *ioc2 = "";
    if (g_tr_common_sto) {
        if (p1_id >= 0 && p1_id < MAX_ROSTER_PLAYERS) {
            const char *nm = hk_StoLookup(g_tr_common_sto, NULL, 4, p1_id);
            const char *cc = hk_StoLookup(g_tr_common_sto, NULL, 6, p1_id);
            if (nm && nm[0]) snprintf(p1_buf, sizeof(p1_buf), "%s", nm);
            if (cc && cc[0]) ioc1 = cc;
        }
        if (p2_id >= 0 && p2_id < MAX_ROSTER_PLAYERS) {
            const char *nm = hk_StoLookup(g_tr_common_sto, NULL, 4, p2_id);
            const char *cc = hk_StoLookup(g_tr_common_sto, NULL, 6, p2_id);
            if (nm && nm[0]) snprintf(p2_buf, sizeof(p2_buf), "%s", nm);
            if (cc && cc[0]) ioc2 = cc;
        }
    }

    char matchup_line[128];
    if (ioc1[0] && ioc2[0]) {
        snprintf(matchup_line, sizeof(matchup_line), "%s (%s)  vs  %s (%s)", p1_buf, ioc1, p2_buf, ioc2);
    } else {
        snprintf(matchup_line, sizeof(matchup_line), "%s  vs  %s", p1_buf, p2_buf);
    }

    char radar_line[96];
    if (g_bhud_last_kmh > 0) {
        snprintf(radar_line, sizeof(radar_line), "BOLA %d km/h  |  MAX %d  |  RALLY %02u",
                 g_bhud_last_kmh, g_bhud_max_kmh, (unsigned)g_bhud_rally);
    } else {
        snprintf(radar_line, sizeof(radar_line), "TV RADAR ACTIVO  |  [F7] HUD");
    }

    DWORD radar_col = 0xFFD8E4F8;
    if (g_bhud_last_kmh >= 205) radar_col = 0xFFFF7050;
    else if (g_bhud_last_kmh >= 170) radar_col = 0xFFFFD858;

    void **svtbl = *(void ***)g_pSprite;
    typedef HRESULT (__stdcall *SpriteBegin_t)(void *, DWORD);
    typedef HRESULT (__stdcall *SpriteEnd_t)(void *);
    SpriteBegin_t sp_begin = (SpriteBegin_t)svtbl[8];
    SpriteEnd_t   sp_end   = (SpriteEnd_t)svtbl[11];
    if (!sp_begin || sp_begin(g_pSprite, 0x10) >= 0) {
        RECT r;
        r.left = (LONG)(px1 + 12.0f * sx);
        r.top = (LONG)(py1 + 2.0f * sy);
        r.right = (LONG)(px2 - 10.0f * sx);
        r.bottom = (LONG)(py1 + 20.0f * sy);
        draw_font_text(g_pFont, g_bhud_stage.title, &r, 0xFFEAF2FF, 0);

        r.top = (LONG)(py1 + 21.0f * sy);
        r.bottom = (LONG)(py1 + 40.0f * sy);
        draw_font_text(g_pFont, matchup_line, &r, 0xFFFFFFFF, 0);

        r.top = (LONG)(py1 + 40.0f * sy);
        r.bottom = (LONG)(py2 - 2.0f * sy);
        draw_font_text(g_pFont, radar_line, &r, radar_col, 0);

        if (sp_end) sp_end(g_pSprite);
    }

    end_overlay_state(dev);
}

#endif /* VT4_BROADCAST_HUD_H */
