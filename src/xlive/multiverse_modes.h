/*
 * multiverse_modes.h — Step 2 Feature Implementations for VT4 Legends & Next-Gen Edition
 *
 * Self-contained header designed for `#include "multiverse_modes.h"` in src/xlive/xlive.c
 * (right after overlay helpers: draw_screen_quad, draw_font_text, begin_overlay_state,
 * end_overlay_state, is_key_down, log_msg, and globals: g_cfg_width, g_cfg_height,
 * g_cfg_multiverse_mode, g_game_dir, g_pFont, g_pFontTitle, g_present_calls, g_menu_visible).
 *
 * Modules provided:
 *   EE-3 : Real 3D Racket Meshes (Wooden 70s, Metallic Frying Pan, Giant Baguette),
 *          multi-mip DDS texture injection in SDO RAM load, and weapon ball physics.
 *   EE-1 : [C] Modo McEnroe Desatado ("¡YOU CANNOT BE SERIOUS!") 2.5s protest QTE,
 *          [Z]/[SPACE] meter targeting 0.65..0.95, HUD & camera shake, +15% Fury buff.
 *   EE-4 : DBZ / Mario Power Tennis additive (D3DBLEND_ONE) ball aura & comet trail
 *          color-coded by live ball velocity, projected via VT4's active Camera matrix.
 *
 * Expected integration hooks in src/xlive/xlive.c:
 *   - Apply call hooks on SDO parser callsites:
 *       0x004583e7 (call 0x00498310) -> hk_ParseSdoBuffer
 *       0x00531591 (call 0x00498310) -> hk_ParseSdoBuffer
 *       (Inside hk_ParseSdoBuffer: call ee_patch_sdo_buffer(dec_buf, dec_len) before orig)
 *   - In hk_LiveMatchTracker_4803e0 (0x00482aa1), when match active:
 *       ee_on_live_match_tick(self);
 *   - In hk_SetMatchCamera (0x0054ca10), before calling orig:
 *       ee_apply_camera_shake(eye_pos, target_pos);
 *   - In hk_BallLaunch_480561 (0x00480561), after orig 0x00478c20:
 *       ee_on_ball_launch(ball_obj, hit_info);
 *   - In hk_BallSimulateTrajectory (0x00478bf3), before calling orig 0x00477740:
 *       ee_on_ball_simulate(ball_phys, start_pos, vel);
 *   - In hk_EndScene (after other HUD overlays):
 *       ee_render_match_overlay(dev, sx, sy);
 *   - Optionally expose g_cfg_weapon_mode (0..3) in config load/save & menu UI.
 */
#ifndef MULTIVERSE_MODES_H
#define MULTIVERSE_MODES_H

#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <math.h>
#include <windows.h>

/* =========================================================================
 * D3D9 / Configuration Globals & Constants
 * ========================================================================= */
#define EE_WEAPON_NORMAL   0
#define EE_WEAPON_WOOD70   1
#define EE_WEAPON_PAN      2
#define EE_WEAPON_BAGUETTE 3

#define EE_D3DPT_TRIANGLELIST   4
#define EE_D3DFVF_XYZRHW_DIFF   0x0044u
#define EE_D3DRS_ZENABLE        7u
#define EE_D3DRS_SRCBLEND       19u
#define EE_D3DRS_DESTBLEND      20u
#define EE_D3DRS_CULLMODE       22u
#define EE_D3DRS_ALPHABLENDEN   27u
#define EE_D3DRS_LIGHTING       137u
#define EE_D3DBLEND_ONE         2u
#define EE_D3DBLEND_SRCALPHA    5u
#define EE_D3DBLEND_INVSRCALPHA 6u
#define EE_D3DCULL_NONE         1u

/* Weapon mode: 0=Normal, 1=1970s Wooden, 2=Metallic Frying Pan, 3=Giant Baguette */
#ifndef EE_CFG_WEAPON_MODE_DEFINED
static uint32_t g_cfg_weapon_mode = 0;
#endif

typedef struct {
    float x, y, z, rhw;
    DWORD color;
} EE_ScreenVertex;

static inline float ee_clampf(float v, float lo, float hi) {
    return (v < lo) ? lo : ((v > hi) ? hi : v);
}

static inline uint32_t ee_rd_be32(const uint8_t *p) {
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | (uint32_t)p[3];
}

static inline uint16_t ee_rd_be16(const uint8_t *p) {
    return (uint16_t)(((uint16_t)p[0] << 8) | (uint16_t)p[1]);
}

static inline float ee_rd_bef32(const uint8_t *p) {
    uint32_t u = ee_rd_be32(p);
    float f = 0.0f;
    memcpy(&f, &u, 4);
    return f;
}

static inline void ee_wr_be32(uint8_t *p, uint32_t v) {
    p[0] = (uint8_t)(v >> 24);
    p[1] = (uint8_t)(v >> 16);
    p[2] = (uint8_t)(v >> 8);
    p[3] = (uint8_t)v;
}

static inline void ee_wr_be16(uint8_t *p, uint16_t v) {
    p[0] = (uint8_t)(v >> 8);
    p[1] = (uint8_t)v;
}

static inline void ee_wr_bef32(uint8_t *p, float f) {
    uint32_t u = 0;
    memcpy(&u, &f, 4);
    ee_wr_be32(p, u);
}

static inline const uint8_t *ee_memfind(const uint8_t *hay, size_t hay_len, const void *needle, size_t nlen) {
    if (!hay || !needle || nlen == 0 || hay_len < nlen) return NULL;
    uint8_t first = ((const uint8_t *)needle)[0];
    size_t limit = hay_len - nlen;
    for (size_t i = 0; i <= limit; i++) {
        if (hay[i] == first && memcmp(hay + i, needle, nlen) == 0) {
            return hay + i;
        }
    }
    return NULL;
}

static inline uint32_t ee_now_ms(void) {
    return (uint32_t)GetTickCount();
}

static inline void ee_set_render_state(void *dev, uint32_t state, uint32_t val) {
    typedef HRESULT(__stdcall *Fn_t)(void *, uint32_t, uint32_t);
    void **vtbl = *(void ***)dev;
    ((Fn_t)vtbl[57])(dev, state, val);
}

static inline void ee_draw_tri_list_up(void *dev, const EE_ScreenVertex *verts, uint32_t tri_count) {
    typedef HRESULT(__stdcall *SetFVF_t)(void *, uint32_t);
    typedef HRESULT(__stdcall *SetTex_t)(void *, uint32_t, void *);
    typedef HRESULT(__stdcall *SetShader_t)(void *, void *);
    typedef HRESULT(__stdcall *DrawUP_t)(void *, uint32_t, uint32_t, const void *, uint32_t);
    void **vtbl = *(void ***)dev;
    if (!dev || !verts || tri_count == 0) return;
    ((SetTex_t)vtbl[65])(dev, 0, NULL);
    ((SetShader_t)vtbl[92])(dev, NULL);   /* SetVertexShader(NULL) */
    ((SetShader_t)vtbl[107])(dev, NULL);  /* SetPixelShader(NULL) */
    ((SetFVF_t)vtbl[89])(dev, EE_D3DFVF_XYZRHW_DIFF);
    ((DrawUP_t)vtbl[83])(dev, EE_D3DPT_TRIANGLELIST, tri_count, verts, (uint32_t)sizeof(EE_ScreenVertex));
}

/* =========================================================================
 * EE-3: Real 3D Racket Meshes, Textures & Ball Physics
 * ========================================================================= */
#pragma pack(push, 1)
typedef struct {
    float x, y, z;
    int16_t nx, ny, nz, nw;
    int16_t u, v;
} EE3Vertex;
#pragma pack(pop)

typedef struct {
    uint32_t id;
    uint32_t n_verts;
    uint32_t n_indices;
    float bmin[3];
    float bmax[3];
    EE3Vertex *verts;
    uint16_t *indices;
} EE3Mesh;

typedef struct {
    uint8_t *b_256_dxt1;  /* 43704B */
    uint8_t *b_256_dxt5;  /* 87408B */
    uint8_t *b_512_dxt1;  /* 174776B */
    uint8_t *s_256_dxt1;  /* 43704B */
    uint8_t *s_256_dxt5;  /* 87408B */
    uint8_t *s_512_dxt1;  /* 174776B */
    uint8_t *gut_64_dxt5; /* 5488B */
} EE3ModeTextures;

static int g_ee3_assets_attempted = 0;
static int g_ee3_assets_ok = 0;
static EE3Mesh g_ee3_meshes[4];        /* 0=PAN_LOD0, 1=PAN_LODL, 2=BAGUETTE_LOD0, 3=BAGUETTE_LODL */
static EE3ModeTextures g_ee3_tex[4];   /* index 1=wood70, 2=pan, 3=baguette */

typedef BOOL (__stdcall *EE_PlaySoundA_t)(LPCSTR, HMODULE, DWORD);
static EE_PlaySoundA_t g_ee_PlaySoundA = NULL;
static uint8_t *g_ee_umpire_dds = NULL; /* full 349,680B (0x555f0) 512x512 DXT5 10-mip DDS */
static uint8_t *g_ee_sfx_wood70 = NULL;
static uint8_t *g_ee_sfx_pan = NULL;
static uint8_t *g_ee_sfx_baguette = NULL;
static uint8_t *g_ee_sfx_protest = NULL;
static uint8_t *g_ee_sfx_win = NULL;
static uint8_t *g_ee_sfx_lose = NULL;

static inline uint8_t *ee_read_whole_file(const char *path, size_t min_bytes, size_t *out_sz) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    if (sz < (long)min_bytes || sz > (8L * 1024L * 1024L)) {
        fclose(f);
        return NULL;
    }
    uint8_t *buf = (uint8_t *)malloc((size_t)sz);
    if (!buf || fread(buf, 1, (size_t)sz, f) != (size_t)sz) {
        free(buf);
        fclose(f);
        return NULL;
    }
    fclose(f);
    if (out_sz) *out_sz = (size_t)sz;
    return buf;
}

static inline void ee_play_wav_mem(const uint8_t *wav_buf, const char *tag) {
    if (!g_ee_PlaySoundA || !wav_buf) return;
    /* SND_ASYNC (1) | SND_NODEFAULT (2) | SND_MEMORY (4) = 0x0007 */
    g_ee_PlaySoundA((LPCSTR)wav_buf, NULL, 0x0007u);
    log_msg("[EE-3] Sound played (%s)", tag ? tag : "sfx");
}

static inline uint8_t *ee_read_dds_payload(const char *path, size_t expected_payload_len) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    if (sz < 128 + (long)expected_payload_len) {
        fclose(f);
        return NULL;
    }
    uint8_t hdr[128];
    if (fread(hdr, 1, 128, f) != 128 || memcmp(hdr, "DDS ", 4) != 0) {
        fclose(f);
        return NULL;
    }
    uint8_t *buf = (uint8_t *)malloc(expected_payload_len);
    if (!buf || fread(buf, 1, expected_payload_len, f) != expected_payload_len) {
        free(buf);
        fclose(f);
        return NULL;
    }
    fclose(f);
    return buf;
}

static inline int ee_load_racket_assets(void) {
    if (g_ee3_assets_attempted) return g_ee3_assets_ok;
    g_ee3_assets_attempted = 1;

    char gdir[MAX_PATH];
    snprintf(gdir, sizeof(gdir), "%s", g_game_dir);
    size_t glen = strlen(gdir);
    while (glen > 0 && (gdir[glen - 1] == '\\' || gdir[glen - 1] == '/')) {
        gdir[--glen] = '\0';
    }

    char base[MAX_PATH];
    snprintf(base, sizeof(base), "%s\\archive\\ee3", gdir);

    /* Load ee3_meshes.bin */
    char mpath[MAX_PATH];
    snprintf(mpath, sizeof(mpath), "%s\\ee3_meshes.bin", base);
    FILE *mf = fopen(mpath, "rb");
    if (mf) {
        uint8_t hdr[12];
        if (fread(hdr, 1, 12, mf) == 12 && memcmp(hdr, "EE3M", 4) == 0) {
            uint32_t ver = 0, cnt = 0;
            memcpy(&ver, hdr + 4, 4);
            memcpy(&cnt, hdr + 8, 4);
            if (ver == 1 && cnt <= 4) {
                for (uint32_t i = 0; i < cnt; i++) {
                    uint32_t rh[4];
                    float bb[6];
                    if (fread(rh, 4, 4, mf) != 4 || fread(bb, 4, 6, mf) != 6) break;
                    uint32_t rid = rh[0], nv = rh[1], ni = rh[2];
                    if (rid < 4 && nv > 0 && nv < 4096 && ni > 0 && ni < 8192) {
                        EE3Mesh *m = &g_ee3_meshes[rid];
                        m->id = rid;
                        m->n_verts = nv;
                        m->n_indices = ni;
                        memcpy(m->bmin, bb, 12);
                        memcpy(m->bmax, bb + 3, 12);
                        m->verts = (EE3Vertex *)malloc((size_t)nv * sizeof(EE3Vertex));
                        m->indices = (uint16_t *)malloc((size_t)ni * sizeof(uint16_t));
                        if (m->verts && m->indices) {
                            fread(m->verts, sizeof(EE3Vertex), nv, mf);
                            fread(m->indices, sizeof(uint16_t), ni, mf);
                            if (ni & 1u) fseek(mf, 2, SEEK_CUR);
                        }
                    }
                }
            }
        }
        fclose(mf);
    }

    const char *mnames[4] = { NULL, "wood70", "pan", "baguette" };
    char tpath[MAX_PATH];
    for (int m = 1; m <= 3; m++) {
        snprintf(tpath, sizeof(tpath), "%s\\%s_B_256_dxt1.dds", base, mnames[m]);
        g_ee3_tex[m].b_256_dxt1 = ee_read_dds_payload(tpath, 43704);
        snprintf(tpath, sizeof(tpath), "%s\\%s_B_256_dxt5.dds", base, mnames[m]);
        g_ee3_tex[m].b_256_dxt5 = ee_read_dds_payload(tpath, 87408);
        snprintf(tpath, sizeof(tpath), "%s\\%s_B_512_dxt1.dds", base, mnames[m]);
        g_ee3_tex[m].b_512_dxt1 = ee_read_dds_payload(tpath, 174776);

        snprintf(tpath, sizeof(tpath), "%s\\%s_S_256_dxt1.dds", base, mnames[m]);
        g_ee3_tex[m].s_256_dxt1 = ee_read_dds_payload(tpath, 43704);
        snprintf(tpath, sizeof(tpath), "%s\\%s_S_256_dxt5.dds", base, mnames[m]);
        g_ee3_tex[m].s_256_dxt5 = ee_read_dds_payload(tpath, 87408);
        snprintf(tpath, sizeof(tpath), "%s\\%s_S_512_dxt1.dds", base, mnames[m]);
        g_ee3_tex[m].s_512_dxt1 = ee_read_dds_payload(tpath, 174776);

        snprintf(tpath, sizeof(tpath), "%s\\%s_gut_64_dxt5.dds", base, mnames[m]);
        g_ee3_tex[m].gut_64_dxt5 = ee_read_dds_payload(tpath, 5488);
    }

    if (!g_ee_PlaySoundA) {
        HMODULE hWinmm = LoadLibraryA("winmm.dll");
        if (hWinmm) {
            g_ee_PlaySoundA = (EE_PlaySoundA_t)GetProcAddress(hWinmm, "PlaySoundA");
        }
    }
    snprintf(tpath, sizeof(tpath), "%s\\umpire_meme.dds", base);
    size_t udds_sz = 0;
    g_ee_umpire_dds = ee_read_whole_file(tpath, 0x555f0u, &udds_sz);
    if (g_ee_umpire_dds && (udds_sz != 0x555f0u || memcmp(g_ee_umpire_dds, "DDS ", 4) != 0)) {
        free(g_ee_umpire_dds);
        g_ee_umpire_dds = NULL;
    }

    snprintf(tpath, sizeof(tpath), "%s\\hit_wood70.wav", base);
    g_ee_sfx_wood70 = ee_read_whole_file(tpath, 64, NULL);
    snprintf(tpath, sizeof(tpath), "%s\\hit_pan.wav", base);
    g_ee_sfx_pan = ee_read_whole_file(tpath, 64, NULL);
    snprintf(tpath, sizeof(tpath), "%s\\hit_baguette.wav", base);
    g_ee_sfx_baguette = ee_read_whole_file(tpath, 64, NULL);
    snprintf(tpath, sizeof(tpath), "%s\\ee1_protest.wav", base);
    g_ee_sfx_protest = ee_read_whole_file(tpath, 64, NULL);
    snprintf(tpath, sizeof(tpath), "%s\\ee1_win.wav", base);
    g_ee_sfx_win = ee_read_whole_file(tpath, 64, NULL);
    snprintf(tpath, sizeof(tpath), "%s\\ee1_lose.wav", base);
    g_ee_sfx_lose = ee_read_whole_file(tpath, 64, NULL);

    g_ee3_assets_ok = (g_ee3_meshes[0].verts != NULL && g_ee3_meshes[2].verts != NULL &&
                       g_ee3_tex[1].b_256_dxt1 != NULL && g_ee3_tex[2].b_256_dxt1 != NULL &&
                       g_ee3_tex[3].b_256_dxt1 != NULL);
    log_msg("[EE-3] assets loaded: ok=%d (pan_v=%u bag_v=%u umpire=%d wav=%d playsnd=%d)",
            g_ee3_assets_ok, g_ee3_meshes[0].n_verts, g_ee3_meshes[2].n_verts,
            g_ee_umpire_dds != NULL, g_ee_sfx_pan != NULL, g_ee_PlaySoundA != NULL);
    return g_ee3_assets_ok;
}

static inline size_t ee_dds_payload_size(uint32_t w, uint32_t h, uint32_t mips, const uint8_t *fourcc) {
    size_t bs = (memcmp(fourcc, "DXT1", 4) == 0) ? 8 : 16;
    size_t total = 0;
    if (mips < 1) mips = 1;
    if (mips > 12) mips = 12;
    for (uint32_t i = 0; i < mips; i++) {
        size_t bw = (w + 3) / 4; if (bw < 1) bw = 1;
        size_t bh = (h + 3) / 4; if (bh < 1) bh = 1;
        total += bw * bh * bs;
        w = (w > 1) ? (w / 2) : 1;
        h = (h > 1) ? (h / 2) : 1;
    }
    return total;
}

static inline void ee_patch_racket_dds_slots(uint8_t *buf, uint32_t len, uint32_t mode) {
    if (mode < 1 || mode > 3) return;
    const EE3ModeTextures *mt = &g_ee3_tex[mode];
    size_t pos = 0;
    while (pos + 128 < len) {
        const uint8_t *hit = ee_memfind(buf + pos, len - pos, "DDS ", 4);
        if (!hit) break;
        size_t off = (size_t)(hit - buf);
        if (off + 128 <= len) {
            uint32_t h, w, mips;
            memcpy(&h, buf + off + 12, 4);
            memcpy(&w, buf + off + 16, 4);
            memcpy(&mips, buf + off + 28, 4);
            const uint8_t *fourcc = buf + off + 84;
            if ((memcmp(fourcc, "DXT1", 4) == 0 || memcmp(fourcc, "DXT5", 4) == 0) &&
                (w == 64 || w == 256 || w == 512) && h == w) {
                size_t p_len = ee_dds_payload_size(w, h, mips, fourcc);
                size_t win_start = (off > 96) ? (off - 96) : 0;
                size_t win_len = off - win_start;
                if (ee_memfind(buf + win_start, win_len, "G_racket_", 9) && off + 128 + p_len <= len) {
                    const uint8_t *src = NULL;
                    int is_gut = (ee_memfind(buf + win_start, win_len, "lodGut", 6) != NULL) || (w == 64);
                    int is_spec = (ee_memfind(buf + win_start, win_len, "_S_", 3) != NULL);
                    if (is_gut && p_len == 5488) {
                        src = mt->gut_64_dxt5;
                    } else if (is_spec) {
                        if (w == 256 && p_len == 43704) src = mt->s_256_dxt1;
                        else if (w == 256 && p_len == 87408) src = mt->s_256_dxt5;
                        else if (w == 512 && p_len == 174776) src = mt->s_512_dxt1;
                    } else {
                        if (w == 256 && p_len == 43704) src = mt->b_256_dxt1;
                        else if (w == 256 && p_len == 87408) src = mt->b_256_dxt5;
                        else if (w == 512 && p_len == 174776) src = mt->b_512_dxt1;
                    }
                    if (src) {
                        memcpy(buf + off + 128, src, p_len);
                    }
                }
            }
        }
        pos = off + 4;
    }
}

typedef struct {
    uint32_t off;
    uint32_t bytes;
    uint32_t stride;
    uint32_t nverts;
    int off_pos;
    int off_nrm;
    int off_col;
    int off_uv;
} EE3StreamDesc;

static inline void ee_wood70_morph_stream(uint8_t *vbase, const EE3StreamDesc *st, int is_gut) {
    if (st->off_pos < 0) return;
    for (uint32_t i = 0; i < st->nverts; i++) {
        uint8_t *vp = vbase + (size_t)i * st->stride;
        float x = ee_rd_bef32(vp + st->off_pos + 0);
        float y = ee_rd_bef32(vp + st->off_pos + 4);
        float z = ee_rd_bef32(vp + st->off_pos + 8);
        float xs = 1.0f, ys = 1.0f;
        float zn = z;
        if (is_gut) {
            xs = 0.76f;
            if (z > 3.20f) zn = 3.20f + (z - 3.20f) * 0.96f;
        } else {
            float t = ee_clampf((z - 1.70f) / 1.70f, 0.0f, 1.0f);
            float sm = t * t * (3.0f - 2.0f * t);
            xs = 1.0f - 0.24f * sm;
            if (z > 1.70f && z < 3.45f && fabsf(x) > 0.04f) xs *= 0.88f;
            if (z > 2.40f && fabsf(y) > 0.025f) ys = 1.22f;
            if (z > 3.20f) zn = 3.20f + (z - 3.20f) * 0.96f;
        }
        ee_wr_bef32(vp + st->off_pos + 0, x * xs);
        ee_wr_bef32(vp + st->off_pos + 4, y * ys);
        ee_wr_bef32(vp + st->off_pos + 8, zn);
        if (st->off_nrm >= 0) {
            float nx = (float)(int16_t)ee_rd_be16(vp + st->off_nrm + 0) / xs;
            float ny = (float)(int16_t)ee_rd_be16(vp + st->off_nrm + 2) / ys;
            float nz = (float)(int16_t)ee_rd_be16(vp + st->off_nrm + 4);
            float nl = sqrtf(nx * nx + ny * ny + nz * nz);
            if (nl > 1e-4f) {
                float sc = 16384.0f / nl;
                ee_wr_be16(vp + st->off_nrm + 0, (uint16_t)(int16_t)ee_clampf(nx * sc, -16384.0f, 16384.0f));
                ee_wr_be16(vp + st->off_nrm + 2, (uint16_t)(int16_t)ee_clampf(ny * sc, -16384.0f, 16384.0f));
                ee_wr_be16(vp + st->off_nrm + 4, (uint16_t)(int16_t)ee_clampf(nz * sc, -16384.0f, 16384.0f));
            }
        }
    }
}

static inline void ee_collapse_stream(uint8_t *vbase, const EE3StreamDesc *st, float cx, float cy, float cz) {
    if (st->off_pos < 0) return;
    for (uint32_t i = 0; i < st->nverts; i++) {
        uint8_t *vp = vbase + (size_t)i * st->stride;
        ee_wr_bef32(vp + st->off_pos + 0, cx);
        ee_wr_bef32(vp + st->off_pos + 4, cy);
        ee_wr_bef32(vp + st->off_pos + 8, cz);
    }
}

static inline void ee_write_mesh_to_stream(uint8_t *vbase, const EE3StreamDesc *st, const EE3Mesh *mesh) {
    if (!mesh || !mesh->verts || st->nverts < mesh->n_verts || st->off_pos < 0) return;
    for (uint32_t i = 0; i < st->nverts; i++) {
        uint32_t si = (i < mesh->n_verts) ? i : (mesh->n_verts - 1);
        const EE3Vertex *sv = &mesh->verts[si];
        uint8_t *vp = vbase + (size_t)i * st->stride;
        ee_wr_bef32(vp + st->off_pos + 0, sv->x);
        ee_wr_bef32(vp + st->off_pos + 4, sv->y);
        ee_wr_bef32(vp + st->off_pos + 8, sv->z);
        if (st->off_nrm >= 0) {
            ee_wr_be16(vp + st->off_nrm + 0, (uint16_t)sv->nx);
            ee_wr_be16(vp + st->off_nrm + 2, (uint16_t)sv->ny);
            ee_wr_be16(vp + st->off_nrm + 4, (uint16_t)sv->nz);
            ee_wr_be16(vp + st->off_nrm + 6, (uint16_t)sv->nw);
        }
        if (st->off_col >= 0) {
            vp[st->off_col + 0] = 192;
            vp[st->off_col + 1] = 192;
            vp[st->off_col + 2] = 192;
            vp[st->off_col + 3] = 255;
        }
        if (st->off_uv >= 0) {
            ee_wr_be16(vp + st->off_uv + 0, (uint16_t)sv->u);
            ee_wr_be16(vp + st->off_uv + 2, (uint16_t)sv->v);
        }
    }
}

static inline void ee_shadow_morph_stream(uint8_t *vbase, const EE3StreamDesc *st, uint32_t mode, int is_gut) {
    if (st->off_pos < 0) return;
    for (uint32_t i = 0; i < st->nverts; i++) {
        uint8_t *vp = vbase + (size_t)i * st->stride;
        float x = ee_rd_bef32(vp + st->off_pos + 0);
        float y = ee_rd_bef32(vp + st->off_pos + 4);
        float z = ee_rd_bef32(vp + st->off_pos + 8);
        if (mode == EE_WEAPON_WOOD70) {
            if (is_gut || z > 1.70f) x *= 0.76f;
        } else if (mode == EE_WEAPON_PAN) {
            if (is_gut) {
                x = 0.0f; y = 0.0f; z = 1.50f;
            } else if (z > 2.20f) {
                float dx = x * 1.33f;
                float dz = (z - 4.80f) * 1.08f;
                float r = sqrtf(dx * dx + dz * dz);
                if (r > 1.74f) {
                    float k = 1.74f / r;
                    dx *= k; dz *= k;
                }
                x = dx;
                z = 4.46f + dz;
            }
        } else if (mode == EE_WEAPON_BAGUETTE) {
            if (is_gut) {
                x = 0.0f; y = 0.0f; z = 1.50f;
            } else {
                x *= 0.38f;
                if (z < 0.0f) z = 0.0f;
                if (z > 6.80f) z = 6.80f;
            }
        }
        ee_wr_bef32(vp + st->off_pos + 0, x);
        ee_wr_bef32(vp + st->off_pos + 4, y);
        ee_wr_bef32(vp + st->off_pos + 8, z);
    }
}

/* Patch decompressed SEGA .sdo buffer in RAM right before VT4's ParseSdoBuffer (0x00498310). */
static inline void ee_patch_sdo_buffer(void *dec_buf, uint32_t dec_len) {
    uint32_t mode = g_cfg_weapon_mode;
    if (mode == EE_WEAPON_NORMAL || mode > EE_WEAPON_BAGUETTE || !dec_buf || dec_len < 64) return;
    if (!ee_load_racket_assets()) return;

    uint8_t *buf = (uint8_t *)dec_buf;
    if (!ee_memfind(buf, dec_len, "racket_model", 12)) return;

    /* 1. Replace G_racket_* DDS textures in-place */
    ee_patch_racket_dds_slots(buf, dec_len, mode);

    /* 2. Patch VertexBuffers */
    const uint8_t vb_tag[14] = "\x0cVertexBuffer\x00";
    size_t pos = 0;
    while (pos + 32 < dec_len) {
        const uint8_t *hit = ee_memfind(buf + pos, dec_len - pos, vb_tag, 14);
        if (!hit) break;
        size_t p = (size_t)(hit - buf) + 14;
        if (p + 2 >= dec_len) break;
        uint8_t l1 = buf[p++];
        if (p + l1 + 1 >= dec_len) { pos = p; continue; }
        const char *full_name = (const char *)(buf + p);
        p += l1;
        uint8_t l2 = buf[p++];
        if (p + l2 + 10 >= dec_len) { pos = p; continue; }
        p += l2 + 1; /* skip short_name + flag */
        /* total_verts, total_bytes, num_streams */
        uint32_t total_bytes = ee_rd_be32(buf + p + 4);
        uint8_t num_streams = buf[p + 8];
        p += 9;
        if (num_streams < 1 || num_streams > 8 || total_bytes > dec_len) { pos = p; continue; }

        EE3StreamDesc streams[8];
        memset(streams, 0, sizeof(streams));
        int valid = 1;
        for (uint8_t si = 0; si < num_streams; si++) {
            if (p + 9 > dec_len) { valid = 0; break; }
            uint32_t s_off = ee_rd_be32(buf + p);
            uint32_t s_bytes = ee_rd_be32(buf + p + 4);
            uint8_t n_attrs = buf[p + 8];
            p += 9;
            if (p + (size_t)n_attrs * 2 > dec_len) { valid = 0; break; }
            EE3StreamDesc *sd = &streams[si];
            sd->off = s_off;
            sd->bytes = s_bytes;
            sd->off_pos = sd->off_nrm = sd->off_col = sd->off_uv = -1;
            int aoff = 0;
            for (uint8_t ai = 0; ai < n_attrs; ai++) {
                uint8_t tp = buf[p + ai * 2];
                uint8_t cnt = buf[p + ai * 2 + 1];
                int sz = (tp == 1 ? 1 : (tp == 2 ? 2 : (tp == 4 ? 4 : 0))) * (int)cnt;
                if (sz <= 0) { valid = 0; break; }
                if (tp == 4 && cnt == 3 && sd->off_pos < 0) sd->off_pos = aoff;
                else if (tp == 2 && cnt == 4 && sd->off_nrm < 0) sd->off_nrm = aoff;
                else if (tp == 1 && cnt == 4 && sd->off_col < 0) sd->off_col = aoff;
                else if (tp == 2 && cnt == 2 && sd->off_uv < 0) sd->off_uv = aoff;
                aoff += sz;
            }
            p += (size_t)n_attrs * 2;
            if (!valid || aoff <= 0 || s_bytes % (uint32_t)aoff != 0) { valid = 0; break; }
            sd->stride = (uint32_t)aoff;
            sd->nverts = s_bytes / (uint32_t)aoff;
        }
        if (!valid || p + total_bytes > dec_len) { pos += 14; continue; }

        if (ee_memfind((const uint8_t *)full_name, l1, "racket_model", 12)) {
            int is_shadow = (ee_memfind((const uint8_t *)full_name, l1, "racket_shadow", 13) != NULL);
            int is_lodL = (ee_memfind((const uint8_t *)full_name, l1, "racket_render_lodL", 18) != NULL);
            int is_render = !is_shadow && !is_lodL &&
                            (ee_memfind((const uint8_t *)full_name, l1, "racket_render", 13) != NULL);

            if (is_render || is_lodL) {
                /* Identify main frame stream (largest non-gut stream: >=500 LOD0, >=200 LODL) */
                int main_si = -1;
                uint32_t best_nv = 0;
                for (uint8_t si = 0; si < num_streams; si++) {
                    int is_gut = (streams[si].nverts == 140 || (is_lodL && streams[si].nverts >= 10 && streams[si].nverts <= 20));
                    if (!is_gut && streams[si].nverts > best_nv) {
                        best_nv = streams[si].nverts;
                        main_si = (int)si;
                    }
                }
                if (mode == EE_WEAPON_WOOD70) {
                    for (uint8_t si = 0; si < num_streams; si++) {
                        int is_gut = ((int)si != main_si && (streams[si].nverts == 140 || (is_lodL && streams[si].nverts <= 20)));
                        ee_wood70_morph_stream(buf + p + streams[si].off, &streams[si], is_gut);
                    }
                } else {
                    const EE3Mesh *m = (mode == EE_WEAPON_PAN)
                        ? (is_lodL ? &g_ee3_meshes[1] : &g_ee3_meshes[0])
                        : (is_lodL ? &g_ee3_meshes[3] : &g_ee3_meshes[2]);
                    for (uint8_t si = 0; si < num_streams; si++) {
                        uint8_t *vbase = buf + p + streams[si].off;
                        if ((int)si == main_si) {
                            ee_write_mesh_to_stream(vbase, &streams[si], m);
                        } else {
                            ee_collapse_stream(vbase, &streams[si], 0.0f, 0.0f, 1.50f);
                        }
                    }
                }
            } else if (is_shadow) {
                for (uint8_t si = 0; si < num_streams; si++) {
                    int is_gut = (si > 0 && streams[si].nverts <= 20);
                    ee_shadow_morph_stream(buf + p + streams[si].off, &streams[si], mode, is_gut);
                }
            }
        }
        pos = p + total_bytes;
    }

    /* 3. Patch IndexBuffers for Frying Pan & Giant Baguette */
    if (mode == EE_WEAPON_PAN || mode == EE_WEAPON_BAGUETTE) {
        const uint8_t ib_tag[13] = "\x0bIndexBuffer\x00";
        pos = 0;
        while (pos + 24 < dec_len) {
            const uint8_t *hit = ee_memfind(buf + pos, dec_len - pos, ib_tag, 13);
            if (!hit) break;
            size_t p = (size_t)(hit - buf) + 13;
            if (p + 2 >= dec_len) break;
            uint8_t l1 = buf[p++];
            if (p + l1 + 1 >= dec_len) { pos = p; continue; }
            const char *fn = (const char *)(buf + p);
            p += l1;
            uint8_t l2 = buf[p++];
            if (p + l2 + 5 >= dec_len) { pos = p; continue; }
            p += l2;
            uint32_t cnt = ee_rd_be32(buf + p + 1);
            size_t idata = p + 5;
            if (idata + (size_t)cnt * 2 > dec_len) { pos = p + 1; continue; }

            if (ee_memfind((const uint8_t *)fn, l1, "racket_model", 12)) {
                int is_lodL = (ee_memfind((const uint8_t *)fn, l1, "racket_render_lodL-", 19) != NULL);
                int is_main_render = !is_lodL && (ee_memfind((const uint8_t *)fn, l1, "racket_render-", 14) != NULL);
                int is_gut = (ee_memfind((const uint8_t *)fn, l1, "double", 6) != NULL) ||
                             (ee_memfind((const uint8_t *)fn, l1, "lodGut", 6) != NULL);
                if (!is_gut && ((is_main_render && cnt >= 900) || (is_lodL && cnt >= 400))) {
                    const EE3Mesh *m = (mode == EE_WEAPON_PAN)
                        ? (is_lodL ? &g_ee3_meshes[1] : &g_ee3_meshes[0])
                        : (is_lodL ? &g_ee3_meshes[3] : &g_ee3_meshes[2]);
                    if (m->indices && m->n_indices > 0 && cnt >= m->n_indices) {
                        uint16_t pad_v = m->indices[m->n_indices - 1];
                        for (uint32_t i = 0; i < cnt; i++) {
                            uint16_t val = (i < m->n_indices) ? m->indices[i] : pad_v;
                            ee_wr_be16(buf + idata + (size_t)i * 2, val);
                        }
                    }
                }
            }
            pos = idata + (size_t)cnt * 2;
        }
    }

    /* 4. Widen BoundingBoxSize near racket_render nodes so wide pan/long baguette never culls */
    if (mode == EE_WEAPON_PAN || mode == EE_WEAPON_BAGUETTE) {
        size_t tail_start = (dec_len > 262144u) ? (dec_len - 262144u) : 0;
        pos = tail_start;
        while (pos + 64 < dec_len) {
            const uint8_t *hit = ee_memfind(buf + pos, dec_len - pos, "racket_render", 13);
            if (!hit) break;
            size_t h_off = (size_t)(hit - buf);
            size_t scan_end = (h_off + 768 < dec_len) ? (h_off + 768) : dec_len;
            const uint8_t *bb = ee_memfind(buf + h_off, scan_end - h_off, "BoundingBoxSize", 15);
            if (bb) {
                const uint8_t *vp = ee_memfind(bb, (size_t)(buf + scan_end - bb), "Variant\x02", 8);
                if (vp && (size_t)(vp - buf) + 20 <= dec_len) {
                    uint8_t *fp = buf + (size_t)(vp - buf) + 8;
                    float sx = ee_rd_bef32(fp + 0);
                    float sy = ee_rd_bef32(fp + 4);
                    float sz = ee_rd_bef32(fp + 8);
                    if (sx > 0.1f && sx < 20.0f && sy > 0.05f && sy < 20.0f && sz > 0.1f && sz < 20.0f) {
                        if (sx < 3.60f) ee_wr_bef32(fp + 0, 3.60f);
                        if (sy < 0.85f) ee_wr_bef32(fp + 4, 0.85f);
                        if (sz < 7.00f) ee_wr_bef32(fp + 8, 7.00f);
                    }
                }
            }
            pos = h_off + 13;
        }
    }
}

static inline int ee_memfind_ci(const uint8_t *hay, size_t hay_len, const char *needle) {
    if (!hay || !needle) return 0;
    size_t nlen = strlen(needle);
    if (nlen == 0 || hay_len < nlen) return 0;
    size_t limit = hay_len - nlen;
    for (size_t i = 0; i <= limit; i++) {
        size_t j = 0;
        for (; j < nlen; j++) {
            uint8_t a = hay[i + j];
            uint8_t b = (uint8_t)needle[j];
            if (a >= 'A' && a <= 'Z') a = (uint8_t)(a + 32);
            if (b >= 'A' && b <= 'Z') b = (uint8_t)(b + 32);
            if (a != b) break;
        }
        if (j == nlen) return 1;
    }
    return 0;
}

static inline uint16_t ee_pack_rgb565(int r, int g, int b) {
    if (r < 0) r = 0; else if (r > 255) r = 255;
    if (g < 0) g = 0; else if (g > 255) g = 255;
    if (b < 0) b = 0; else if (b > 255) b = 255;
    return (uint16_t)(((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3));
}

static inline void ee_recolor_bc1_block(uint8_t *blk, int mode_tint, int is_ice, int is_seam) {
    uint16_t c0 = (uint16_t)blk[0] | ((uint16_t)blk[1] << 8);
    uint16_t c1 = (uint16_t)blk[2] | ((uint16_t)blk[3] << 8);
    uint32_t bits = (uint32_t)blk[4] | ((uint32_t)blk[5] << 8) |
                    ((uint32_t)blk[6] << 16) | ((uint32_t)blk[7] << 24);

    int rgb[2][3];
    rgb[0][0] = (((c0 >> 11) & 0x1F) * 255) / 31;
    rgb[0][1] = (((c0 >> 5) & 0x3F) * 255) / 63;
    rgb[0][2] = ((c0 & 0x1F) * 255) / 31;
    rgb[1][0] = (((c1 >> 11) & 0x1F) * 255) / 31;
    rgb[1][1] = (((c1 >> 5) & 0x3F) * 255) / 63;
    rgb[1][2] = ((c1 & 0x1F) * 255) / 31;

    uint16_t nc[2];
    for (int k = 0; k < 2; k++) {
        float luma = 0.299f * (float)rgb[k][0] + 0.587f * (float)rgb[k][1] + 0.114f * (float)rgb[k][2];
        int nr, ng, nb;
        if (mode_tint == 0) {
            /* Neutralize tiled court surface detail toward textured white-gray */
            int gval = (int)(168.0f + luma * 0.28f);
            nr = gval; ng = gval + 2; nb = gval + 4;
        } else if (is_seam) {
            nr = (int)(200.0f + luma * 0.20f);
            ng = (int)(236.0f + luma * 0.08f);
            nb = 255;
        } else if (is_ice) {
            /* Glacial Ice Blue (-Z half) */
            nr = (int)(luma * 0.36f + 16.0f);
            ng = (int)(luma * 0.86f + 38.0f);
            nb = (int)(luma * 1.40f + 82.0f);
        } else {
            /* Wet Dark Mud Brown (+Z half) */
            nr = (int)(luma * 0.72f + 18.0f);
            ng = (int)(luma * 0.36f + 4.0f);
            nb = (int)(luma * 0.14f);
        }
        nc[k] = ee_pack_rgb565(nr, ng, nb);
    }

    uint16_t nc0 = nc[0], nc1 = nc[1];
    if ((c0 > c1) && (nc0 <= nc1)) {
        if (nc0 == nc1) {
            if (nc0 < 0xFFFFu) nc0++; else nc1--;
        } else {
            uint16_t t = nc0; nc0 = nc1; nc1 = t;
            bits ^= 0x55555555u;
        }
    } else if ((c0 <= c1) && (nc0 > nc1)) {
        uint16_t t = nc0; nc0 = nc1; nc1 = t;
        uint32_t nb = 0;
        for (int i = 0; i < 16; i++) {
            uint32_t idx = (bits >> (i * 2)) & 3u;
            if (idx == 0u) idx = 1u; else if (idx == 1u) idx = 0u;
            nb |= (idx << (i * 2));
        }
        bits = nb;
    }

    blk[0] = (uint8_t)(nc0 & 0xFFu); blk[1] = (uint8_t)(nc0 >> 8);
    blk[2] = (uint8_t)(nc1 & 0xFFu); blk[3] = (uint8_t)(nc1 >> 8);
    blk[4] = (uint8_t)(bits & 0xFFu);
    blk[5] = (uint8_t)((bits >> 8) & 0xFFu);
    blk[6] = (uint8_t)((bits >> 16) & 0xFFu);
    blk[7] = (uint8_t)((bits >> 24) & 0xFFu);
}

static inline int ee_patch_stage_ee2_surface(uint8_t *buf, uint32_t len) {
    if (g_cfg_multiverse_mode != 1u && g_cfg_multiverse_mode != 3u) return 0;
    int patched_il = 0, patched_uv = 0;
    size_t pos = 0;
    while (pos + 128 < len) {
        const uint8_t *hit = ee_memfind(buf + pos, len - pos, "DDS ", 4);
        if (!hit) break;
        size_t off = (size_t)(hit - buf);
        uint32_t h, w, mips;
        memcpy(&h, buf + off + 12, 4);
        memcpy(&w, buf + off + 16, 4);
        memcpy(&mips, buf + off + 28, 4);
        const uint8_t *fourcc = buf + off + 84;
        int is_dxt1 = (memcmp(fourcc, "DXT1", 4) == 0);
        int is_dxt5 = (memcmp(fourcc, "DXT5", 4) == 0);
        if ((is_dxt1 || is_dxt5) && w >= 64u && h >= 64u) {
            if (mips < 1u) mips = 1u;
            if (mips > 12u) mips = 12u;
            size_t p_len = ee_dds_payload_size(w, h, mips, fourcc);
            size_t win_start = (off > 96u) ? (off - 96u) : 0u;
            const uint8_t *ctx = buf + win_start;
            size_t ctx_len = off - win_start;
            if (off + 128u + p_len <= len) {
                uint32_t blk_sz = is_dxt1 ? 8u : 16u;
                uint32_t col_off = is_dxt1 ? 0u : 8u;
                int is_full_court = (w == 2048u && h == 2048u &&
                                     ee_memfind_ci(ctx, ctx_len, "surface") &&
                                     !ee_memfind_ci(ctx, ctx_len, "line") &&
                                     !ee_memfind_ci(ctx, ctx_len, "outside") &&
                                     !ee_memfind_ci(ctx, ctx_len, "stand") &&
                                     !ee_memfind_ci(ctx, ctx_len, "building") &&
                                     !ee_memfind_ci(ctx, ctx_len, "obj"));
                int is_detail = (w <= 512u && h <= 512u && w == h &&
                                 (ee_memfind_ci(ctx, ctx_len, "uv_surface") ||
                                  ee_memfind_ci(ctx, ctx_len, "surfacedetail") ||
                                  ee_memfind_ci(ctx, ctx_len, "claydetail") ||
                                  ee_memfind_ci(ctx, ctx_len, "surface_detail")));
                if (is_full_court || is_detail) {
                    size_t mp = off + 128u;
                    size_t endp = off + 128u + p_len;
                    uint32_t mw = w, mh = h;
                    for (uint32_t lvl = 0; lvl < mips && mp < endp; lvl++) {
                        uint32_t bw = (mw + 3u) / 4u; if (bw < 1u) bw = 1u;
                        uint32_t bh = (mh + 3u) / 4u; if (bh < 1u) bh = 1u;
                        for (uint32_t by = 0; by < bh && mp + (size_t)bw * blk_sz <= endp; by++) {
                            int is_ice = (by < (bh / 2u));
                            int is_seam = (bh >= 16u && (by == (bh / 2u) - 1u || by == (bh / 2u)));
                            for (uint32_t bx = 0; bx < bw; bx++) {
                                ee_recolor_bc1_block(buf + mp + col_off, is_full_court ? 1 : 0, is_ice, is_seam);
                                mp += blk_sz;
                            }
                        }
                        mw = (mw > 1u) ? (mw / 2u) : 1u;
                        mh = (mh > 1u) ? (mh / 2u) : 1u;
                    }
                    if (is_full_court) patched_il++;
                    else patched_uv++;
                }
            }
        }
        pos = off + 4u;
    }
    if (patched_il > 0 || patched_uv > 0) {
        log_msg("[EE-2] Patched stage IL_surface in RAM (50%% Ice / 50%% Mud, il=%d uv=%d)", patched_il, patched_uv);
        return 1;
    }
    return 0;
}

static inline void ee_patch_umpire_sdo(uint8_t *buf, uint32_t len) {
    if (!g_ee_umpire_dds) return;
    int replaced = 0;
    size_t pos = 0;
    while (pos + 0x555f0u <= len) {
        const uint8_t *hit = ee_memfind(buf + pos, len - pos, "DDS ", 4);
        if (!hit) break;
        size_t off = (size_t)(hit - buf);
        uint32_t h, w, mips;
        memcpy(&h, buf + off + 12, 4);
        memcpy(&w, buf + off + 16, 4);
        memcpy(&mips, buf + off + 28, 4);
        size_t win_start = (off > 96u) ? (off - 96u) : 0u;
        const uint8_t *ctx = buf + win_start;
        size_t ctx_len = off - win_start;
        if (w == 512u && h == 512u && mips == 10u &&
            memcmp(buf + off + 84, "DXT5", 4) == 0 &&
            ee_memfind_ci(ctx, ctx_len, "u_ump_b_") &&
            off + 0x555f0u <= len) {
            memcpy(buf + off, g_ee_umpire_dds, 0x555f0u);
            replaced++;
        }
        pos = off + 4u;
    }
    if (replaced > 0) {
        log_msg("[EE-3] Patched Umpire SDO in RAM (replaced %d textures)", replaced);
    }
}

/* Decompress SEGA LZSS container -> patch racket / stage / umpire in RAM -> re-wrap literal LZSS -> parse via 0x004cf570. */
static inline void *ee_parse_and_patch_sdo(void *sdo_buf, uint32_t sdo_len) {
    typedef void *(__cdecl *ParseSdoFn_t)(void *, uint32_t);
    ParseSdoFn_t orig_parse = (ParseSdoFn_t)0x004cf570;

    uint32_t wmode = g_cfg_weapon_mode;
    uint32_t mv = g_cfg_multiverse_mode;
    int want_racket = (wmode >= 1u && wmode <= EE_WEAPON_BAGUETTE);
    int want_stage  = (mv == 1u || mv == 3u);
    int want_umpire = (mv != 0u || wmode != 0u);
    if ((!want_racket && !want_stage && !want_umpire) || !sdo_buf || sdo_len < 32u) {
        return orig_parse(sdo_buf, sdo_len);
    }

    const uint8_t *b = (const uint8_t *)sdo_buf;
    if (!ee_memfind(b + 8, (sdo_len - 8u < 24u) ? (sdo_len - 8u) : 24u, "SEGA", 4)) {
        return orig_parse(sdo_buf, sdo_len);
    }

    uint32_t uncomp_sz = ee_rd_be32(b);
    uint32_t comp_sz = ee_rd_be32(b + 4);
    if (uncomp_sz < 64u || uncomp_sz > (64u * 1024u * 1024u) || comp_sz < 16u || 8u + comp_sz > sdo_len) {
        return orig_parse(sdo_buf, sdo_len);
    }

    uint8_t *dec = (uint8_t *)malloc(uncomp_sz);
    if (!dec) {
        return orig_parse(sdo_buf, sdo_len);
    }

    const uint8_t *src = b + 8;
    uint32_t sp = 0;
    uint32_t dp = 0;
    while (sp < comp_sz && dp < uncomp_sz) {
        uint8_t ctrl = src[sp++];
        if (ctrl < 0x80u) {
            uint32_t run = (uint32_t)ctrl + 1u;
            if (sp + run > comp_sz || dp + run > uncomp_sz) { dp = 0; break; }
            memcpy(dec + dp, src + sp, run);
            sp += run;
            dp += run;
        } else {
            if (sp >= comp_sz) { dp = 0; break; }
            uint8_t b2 = src[sp++];
            uint32_t len = (uint32_t)(ctrl & 0x0Fu) + 3u;
            uint32_t dist = (((uint32_t)(ctrl & 0x70u) << 4) | (uint32_t)b2) + 1u;
            if (dist > dp || dp + len > uncomp_sz) { dp = 0; break; }
            for (uint32_t k = 0; k < len; k++) {
                dec[dp] = dec[dp - dist];
                dp++;
            }
        }
    }

    if (dp != uncomp_sz) {
        free(dec);
        return orig_parse(sdo_buf, sdo_len);
    }

    int is_racket = want_racket && (ee_memfind(dec, uncomp_sz, "racket_model", 12) != NULL);
    int is_umpire = want_umpire && (ee_memfind(dec, uncomp_sz, "U_UMP_B_", 8) != NULL);
    int did_stage = 0;

    if (is_racket || is_umpire) {
        ee_load_racket_assets();
        if (is_racket) ee_patch_sdo_buffer(dec, uncomp_sz);
        if (is_umpire) ee_patch_umpire_sdo(dec, uncomp_sz);
    }
    if (want_stage && uncomp_sz > 8000000u) {
        did_stage = ee_patch_stage_ee2_surface(dec, uncomp_sz);
    }

    if (!is_racket && !is_umpire && !did_stage) {
        free(dec);
        return orig_parse(sdo_buf, sdo_len);
    }

    uint32_t n_chunks = (uncomp_sz + 127u) / 128u;
    uint32_t out_comp_sz = uncomp_sz + n_chunks;
    uint32_t out_total = 8u + out_comp_sz;
    uint8_t *recomp = (uint8_t *)malloc(out_total);
    if (!recomp) {
        free(dec);
        return orig_parse(sdo_buf, sdo_len);
    }

    ee_wr_be32(recomp, uncomp_sz);
    ee_wr_be32(recomp + 4, out_comp_sz);
    uint32_t wp = 8;
    uint32_t rp = 0;
    while (rp < uncomp_sz) {
        uint32_t run = uncomp_sz - rp;
        if (run > 128u) run = 128u;
        recomp[wp++] = (uint8_t)(run - 1u);
        memcpy(recomp + wp, dec + rp, run);
        wp += run;
        rp += run;
    }
    free(dec);

    void *res = orig_parse(recomp, out_total);
    if (is_racket) {
        log_msg("[EE-3] Patched SDO in RAM (mode=%u, dec=%u, lzss=%u) -> parse=%p",
                wmode, uncomp_sz, out_total, res);
    }
    free(recomp);
    return res;
}

/* =========================================================================
 * EE-1: [C] Modo McEnroe Desatado ("¡YOU CANNOT BE SERIOUS!") State Machine
 * ========================================================================= */
enum {
    EE_MCENROE_IDLE = 0,
    EE_MCENROE_QTE = 1,
    EE_MCENROE_BANNER = 2
};

static int      g_ee1_state = EE_MCENROE_IDLE;
static float    g_ee1_qte_timer = 0.0f;
static float    g_ee1_banner_timer = 0.0f;
static float    g_ee1_cooldown = 0.0f;
static float    g_ee1_meter = 0.0f;
static int      g_ee1_win = 0;
static float    g_ee1_shake_timer = 0.0f;
static int      g_ee1_fury_active = 0;
static float    g_ee1_fury_timer = 0.0f;
static uint32_t g_ee1_last_ms = 0;
static int      g_ee1_prev_c = 0;
static int      g_ee1_prev_z = 0;
static int      g_ee1_prev_sp = 0;

/* Track live match heartbeat independently of xlive.c definition ordering */
static uint32_t g_ee_live_match_present_frame = 0;
static void    *g_ee_last_match_mgr = NULL;

static inline void ee_mcenroe_tick(int in_live_match) {
    uint32_t now = ee_now_ms();
    if (g_ee1_last_ms == 0) g_ee1_last_ms = now;
    float dt = (float)(now - g_ee1_last_ms) * 0.001f;
    g_ee1_last_ms = now;
    if (dt < 0.0f) dt = 0.0f;
    if (dt > 0.08f) dt = 0.08f;

    int k_c  = is_key_down('C');
    int k_z  = is_key_down('Z');
    int k_sp = is_key_down(VK_SPACE);

    int edge_c  = (k_c && !g_ee1_prev_c);
    int edge_z  = (k_z && !g_ee1_prev_z);
    int edge_sp = (k_sp && !g_ee1_prev_sp);
    g_ee1_prev_c = k_c;
    g_ee1_prev_z = k_z;
    g_ee1_prev_sp = k_sp;

    if (!in_live_match || g_menu_visible) {
        if (!in_live_match) {
            g_ee1_state = EE_MCENROE_IDLE;
            g_ee1_qte_timer = 0.0f;
            g_ee1_banner_timer = 0.0f;
            g_ee1_shake_timer = 0.0f;
            g_ee1_fury_active = 0;
            g_ee1_fury_timer = 0.0f;
        }
        return;
    }

    if (g_ee1_cooldown > 0.0f) g_ee1_cooldown = ee_clampf(g_ee1_cooldown - dt, 0.0f, 60.0f);
    if (g_ee1_shake_timer > 0.0f) g_ee1_shake_timer = ee_clampf(g_ee1_shake_timer - dt, 0.0f, 10.0f);
    if (g_ee1_fury_active) {
        g_ee1_fury_timer -= dt;
        if (g_ee1_fury_timer <= 0.0f) {
            g_ee1_fury_active = 0;
            g_ee1_fury_timer = 0.0f;
        }
    }

    if (g_ee1_state == EE_MCENROE_IDLE) {
        if (edge_c && g_ee1_cooldown <= 0.0f) {
            ee_load_racket_assets();
            g_ee1_state = EE_MCENROE_QTE;
            g_ee1_qte_timer = 2.5f;
            g_ee1_meter = 0.22f;
            g_ee1_shake_timer = 2.5f;
            g_ee1_win = 0;
            if (!vp_try_play_event(g_vp_p1_id, g_vp_p2_id, VP_EV_PROTEST)) {
                ee_play_wav_mem(g_ee_sfx_protest, "ee1_protest");
            }
        }
    } else if (g_ee1_state == EE_MCENROE_QTE) {
        g_ee1_meter -= 0.40f * dt;
        if (edge_z)  g_ee1_meter += 0.135f;
        if (edge_sp) g_ee1_meter += 0.135f;
        g_ee1_meter = ee_clampf(g_ee1_meter, 0.0f, 1.0f);

        g_ee1_qte_timer -= dt;
        if (g_ee1_qte_timer <= 0.0f) {
            g_ee1_qte_timer = 0.0f;
            g_ee1_win = (g_ee1_meter >= 0.65f && g_ee1_meter <= 0.95f) ? 1 : 0;
            g_ee1_state = EE_MCENROE_BANNER;
            g_ee1_banner_timer = 2.6f;
            if (g_ee1_win) {
                g_ee1_fury_active = 1;
                g_ee1_fury_timer = 15.0f;
                g_ee1_cooldown = 10.0f;
                g_ee1_shake_timer = 0.55f;
                if (!vp_try_play_event(g_vp_p1_id, g_vp_p2_id, VP_EV_POINT_WIN)) {
                    ee_play_wav_mem(g_ee_sfx_win, "ee1_win");
                }
            } else {
                g_ee1_fury_active = 0;
                g_ee1_cooldown = 8.0f;
                g_ee1_shake_timer = 0.40f;
                if (!vp_try_play_event(g_vp_p1_id, g_vp_p2_id, VP_EV_POINT_LOSE)) {
                    ee_play_wav_mem(g_ee_sfx_lose, "ee1_lose");
                }
            }
        }
    } else if (g_ee1_state == EE_MCENROE_BANNER) {
        g_ee1_banner_timer -= dt;
        if (g_ee1_banner_timer <= 0.0f) {
            g_ee1_state = EE_MCENROE_IDLE;
            g_ee1_banner_timer = 0.0f;
        }
    }
}

/* Camera shake helper for hk_SetMatchCamera (0x0054ca10) */
static inline void ee_apply_camera_shake(float *eye_pos, float *target_pos) {
    if (g_ee1_shake_timer <= 0.0f) return;
    float amp = (g_ee1_state == EE_MCENROE_QTE)
        ? (0.04f + 0.12f * g_ee1_meter)
        : (0.18f * ee_clampf(g_ee1_shake_timer * 2.0f, 0.0f, 1.0f));
    float t = (float)ee_now_ms() * 0.055f;
    float ox = sinf(t * 1.9f) * amp;
    float oy = cosf(t * 2.7f) * amp * 0.7f;
    if (eye_pos) {
        eye_pos[0] += ox;
        eye_pos[1] += oy;
    }
    if (target_pos) {
        target_pos[0] += ox * 0.55f;
        target_pos[1] += oy * 0.55f;
    }
}

static inline void ee_mcenroe_render(void *dev, float sx, float sy) {
    if (!dev || g_menu_visible) return;
    init_menu_fonts(dev);
    float t = (float)ee_now_ms() * 0.06f;
    float jx = 0.0f, jy = 0.0f;
    if (g_ee1_shake_timer > 0.0f) {
        float mag = (g_ee1_state == EE_MCENROE_QTE) ? (2.5f + 5.5f * g_ee1_meter) : (7.0f * ee_clampf(g_ee1_shake_timer * 1.8f, 0.0f, 1.0f));
        jx = sinf(t * 2.1f) * mag * sx;
        jy = cosf(t * 3.1f) * mag * sy;
    }

    int has_any = (g_ee1_state == EE_MCENROE_QTE || g_ee1_state == EE_MCENROE_BANNER || g_ee1_fury_active);
    if (!has_any) return;

    if (g_ee1_state == EE_MCENROE_QTE) {
        float px = (340.0f * sx) + jx;
        float py = (88.0f * sy) + jy;
        float pw = 600.0f * sx;
        float ph = 114.0f * sy;

        draw_screen_quad(dev, px, py, px + pw, py + ph, 0xD8140C10);
        draw_screen_quad(dev, px, py, px + pw, py + 4.0f * sy, 0xFFFF3838);
        draw_screen_quad(dev, px, py + ph - 3.0f * sy, px + pw, py + ph, 0xFFFFB020);

        /* Meter bar with 0.65..0.95 green target zone and >0.95 red danger zone */
        float bx = px + 36.0f * sx;
        float by = py + 48.0f * sy;
        float bw = pw - 72.0f * sx;
        float bh = 24.0f * sy;
        draw_screen_quad(dev, bx - 2.0f, by - 2.0f, bx + bw + 2.0f, by + bh + 2.0f, 0xFFCCCCCC);
        draw_screen_quad(dev, bx, by, bx + bw, by + bh, 0xFF1E222A);
        draw_screen_quad(dev, bx + bw * 0.65f, by, bx + bw * 0.95f, by + bh, 0xAA28D860);
        draw_screen_quad(dev, bx + bw * 0.95f, by, bx + bw, by + bh, 0xAAE82828);

        int in_sweet = (g_ee1_meter >= 0.65f && g_ee1_meter <= 0.95f);
        DWORD fill_col = in_sweet ? 0xFF40FF80 : ((g_ee1_meter > 0.95f) ? 0xFFFF3838 : 0xFFFFAA28);
        draw_screen_quad(dev, bx, by + 4.0f * sy, bx + bw * g_ee1_meter, by + bh - 4.0f * sy, fill_col);
        float cur_x = bx + bw * g_ee1_meter;
        draw_screen_quad(dev, cur_x - 2.5f * sx, by - 4.0f * sy, cur_x + 2.5f * sx, by + bh + 4.0f * sy, 0xFFFFFFFF);
    } else if (g_ee1_state == EE_MCENROE_BANNER) {
        float px = (340.0f * sx) + jx;
        float py = (98.0f * sy) + jy;
        float pw = 600.0f * sx;
        float ph = 72.0f * sy;
        DWORD bg = g_ee1_win ? 0xE0102B18 : 0xE03A0D10;
        DWORD brd = g_ee1_win ? 0xFF44FF88 : 0xFFFF3A3A;
        draw_screen_quad(dev, px, py, px + pw, py + ph, bg);
        draw_screen_quad(dev, px, py, px + pw, py + 4.0f * sy, brd);
        draw_screen_quad(dev, px, py + ph - 4.0f * sy, px + pw, py + ph, brd);
    }

    if (g_ee1_fury_active) {
        float bx = 970.0f * sx, by = 18.0f * sy;
        draw_screen_quad(dev, bx, by, bx + 286.0f * sx, by + 28.0f * sy, 0xC81C2E14);
    }

    if (g_pFont && g_pSprite) {
        void **svtbl = *(void ***)g_pSprite;
        typedef HRESULT(__stdcall *SpriteBegin_t)(void *, DWORD);
        typedef HRESULT(__stdcall *SpriteEnd_t)(void *);
        SpriteBegin_t sp_begin = (SpriteBegin_t)svtbl[8];
        SpriteEnd_t sp_end = (SpriteEnd_t)svtbl[11];
        if (!sp_begin || sp_begin(g_pSprite, 0x10) >= 0) {
            if (g_ee1_state == EE_MCENROE_QTE) {
                float px = (340.0f * sx) + jx;
                float py = (88.0f * sy) + jy;
                float pw = 600.0f * sx;
                float ph = 114.0f * sy;
                int in_sweet = (g_ee1_meter >= 0.65f && g_ee1_meter <= 0.95f);
                char title[128];
                snprintf(title, sizeof(title), "!PROTESTA AL JUEZ!: !YOU CANNOT BE SERIOUS!  [%.1fs]", g_ee1_qte_timer);
                RECT rt = { (LONG)(px + 12.0f * sx), (LONG)(py + 8.0f * sy), (LONG)(px + pw - 12.0f * sx), (LONG)(py + 38.0f * sy) };
                draw_font_text(g_pFontTitle ? g_pFontTitle : g_pFont, title, &rt, 0xFFFFE050, 1);

                const char *hint = in_sweet
                    ? "ZONA VERDE! MANTEN EL EQUILIBRIO ([Z]/[SPACE])"
                    : ((g_ee1_meter > 0.95f) ? "DEMASIADA FURIA! AFLOJA!" : "PULSA RAPIDO [Z] / [ESPACIO] -> ZONA VERDE (65-95%)");
                RECT rh = { (LONG)px, (LONG)(py + 78.0f * sy), (LONG)(px + pw), (LONG)(py + ph - 6.0f * sy) };
                draw_font_text(g_pFont, hint, &rh, in_sweet ? 0xFF80FF98 : 0xFFEEEEEE, 1);
            } else if (g_ee1_state == EE_MCENROE_BANNER) {
                float px = (340.0f * sx) + jx;
                float py = (98.0f * sy) + jy;
                float pw = 600.0f * sx;
                float ph = 72.0f * sy;
                const char *msg = g_ee1_win ? "!DECISION REVOCADA! +15% FURIA" : "WARNING ARBITRAL";
                RECT rb = { (LONG)px, (LONG)py, (LONG)(px + pw), (LONG)(py + ph) };
                draw_font_text(g_pFontTitle ? g_pFontTitle : g_pFont, msg, &rb, g_ee1_win ? 0xFFFFF060 : 0xFFFF7070, 1);
            }

            if (g_ee1_fury_active) {
                float bx = 970.0f * sx, by = 18.0f * sy;
                char ftxt[64];
                snprintf(ftxt, sizeof(ftxt), "FURIA MCENROE +15%% (%.0fs)", g_ee1_fury_timer);
                RECT rf = { (LONG)bx, (LONG)by, (LONG)(bx + 286.0f * sx), (LONG)(by + 28.0f * sy) };
                draw_font_text(g_pFont, ftxt, &rf, 0xFF70FF80, 1);
            }
            if (sp_end) sp_end(g_pSprite);
        }
    }
}

/* =========================================================================
 * EE-3 + EE-1 Combined Weapon / Fury Ball Physics Hooks
 * ========================================================================= */
static inline void ee_apply_weapon_physics(float *speed_out, float *vel_xyz, int consume_fury) {
    if (speed_out) {
        if (g_cfg_weapon_mode == EE_WEAPON_WOOD70) {
            *speed_out *= 0.90f;
        } else if (g_cfg_weapon_mode == EE_WEAPON_PAN) {
            *speed_out *= 1.24f;
        } else if (g_cfg_weapon_mode == EE_WEAPON_BAGUETTE) {
            *speed_out *= 1.32f;
        }
        if (consume_fury && g_ee1_fury_active) {
            *speed_out *= 1.15f;
            g_ee1_fury_active = 0;
            g_ee1_fury_timer = 0.0f;
        }
    }
    if (vel_xyz) {
        if (g_cfg_weapon_mode == EE_WEAPON_WOOD70) {
            /* Classic 70s loop: slightly lower pace, controlled dip */
            vel_xyz[0] *= 0.95f;
            vel_xyz[2] *= 0.95f;
        } else if (g_cfg_weapon_mode == EE_WEAPON_PAN) {
            /* Heavy metallic frying pan: flatter crisp drive */
            vel_xyz[0] *= 1.12f;
            vel_xyz[1] *= 0.90f;
            vel_xyz[2] *= 1.14f;
        } else if (g_cfg_weapon_mode == EE_WEAPON_BAGUETTE) {
            /* Giant Baguette: goofy heavy loft */
            vel_xyz[0] *= 1.15f;
            vel_xyz[1] *= 1.22f;
            vel_xyz[2] *= 1.12f;
        }
    }
}

static inline void ee_vp_notify_score_event(int winner_slot, int is_match_win) {
    int win_id  = (winner_slot == 0) ? g_vp_p1_id : g_vp_p2_id;
    int lose_id = (winner_slot == 0) ? g_vp_p2_id : g_vp_p1_id;
    if (win_id >= 0) {
        if (!vp_try_play_event(win_id, lose_id, is_match_win ? VP_EV_MATCH_WIN : VP_EV_POINT_WIN)) {
            if (lose_id >= 0 && !is_match_win) {
                vp_try_play_event(lose_id, win_id, VP_EV_POINT_LOSE);
            }
        }
    }
}

static inline void ee_on_ball_launch(void *ball_obj, void *hit_info) {
    (void)ball_obj;
    if (!hit_info) return;
    float *spd = (float *)((char *)hit_info + 0x18);
    ee_apply_weapon_physics(spd, NULL, 1);

    /* Per-player custom voice pack grunt / serve hook (zero overhead when no WAVs present) */
    if (g_vp.initialized && g_vp.enabled && (g_vp.active[0].total_bytes > 0 || g_vp.active[1].total_bytes > 0)) {
        float ball_z = *(const float *)((const char *)hit_info + 0x08);
        int is_p1 = (!isfinite(ball_z) || ball_z >= 0.0f) ? 1 : 0;
        int hitter_id = is_p1 ? g_vp_p1_id : g_vp_p2_id;
        int opp_id    = is_p1 ? g_vp_p2_id : g_vp_p1_id;
        int is_serve  = (*(const uint32_t *)((const char *)hit_info + 0x00) == 0u);
        vp_try_play_event(hitter_id, opp_id, is_serve ? VP_EV_SERVE : VP_EV_GRUNT);
    }

    if (g_cfg_weapon_mode >= EE_WEAPON_WOOD70 && g_cfg_weapon_mode <= EE_WEAPON_BAGUETTE) {
        static uint32_t s_last_hit_sfx_ms = 0;
        uint32_t now = ee_now_ms();
        if (now - s_last_hit_sfx_ms >= 120u) {
            s_last_hit_sfx_ms = now;
            ee_load_racket_assets();
            if (g_cfg_weapon_mode == EE_WEAPON_WOOD70) {
                ee_play_wav_mem(g_ee_sfx_wood70, "wood70");
            } else if (g_cfg_weapon_mode == EE_WEAPON_PAN) {
                ee_play_wav_mem(g_ee_sfx_pan, "pan");
            } else if (g_cfg_weapon_mode == EE_WEAPON_BAGUETTE) {
                ee_play_wav_mem(g_ee_sfx_baguette, "baguette");
            }
        }
    }
}

/* =========================================================================
 * EE-4: Ball Energy Trail / DBZ & Mario Power Tennis Additive Aura
 * ========================================================================= */
#define EE4_TRAIL_MAX 22

typedef struct {
    float x, y, z;
    float vx, vy, vz;
    float speed;
    uint32_t ms;
} EE4TrailPt;

static EE4TrailPt g_ee4_trail[EE4_TRAIL_MAX];
static int        g_ee4_count = 0;
static float      g_ee4_last_pos[3] = { 0.0f, 0.0f, 0.0f };
static float      g_ee4_last_vel[3] = { 0.0f, 0.0f, 0.0f };

static inline void ee_record_ball_pos(const float *pos, const float *vel) {
    if (!pos) return;
    float x = pos[0], y = pos[1], z = pos[2];
    if (!isfinite(x) || !isfinite(y) || !isfinite(z) || fabsf(x) > 500.0f || fabsf(y) > 500.0f || fabsf(z) > 500.0f) {
        return;
    }
    float vx = vel ? vel[0] : 0.0f;
    float vy = vel ? vel[1] : 0.0f;
    float vz = vel ? vel[2] : 0.0f;
    if (!isfinite(vx) || !isfinite(vy) || !isfinite(vz)) vx = vy = vz = 0.0f;
    float spd = sqrtf(vx * vx + vy * vy + vz * vz);

    g_ee4_last_pos[0] = x; g_ee4_last_pos[1] = y; g_ee4_last_pos[2] = z;
    g_ee4_last_vel[0] = vx; g_ee4_last_vel[1] = vy; g_ee4_last_vel[2] = vz;

    uint32_t now = ee_now_ms();
    if (g_ee4_count > 0) {
        EE4TrailPt *top = &g_ee4_trail[g_ee4_count - 1];
        float dx = x - top->x, dy = y - top->y, dz = z - top->z;
        float dist2 = dx * dx + dy * dy + dz * dz;
        /* Reset trail cleanly on teleport / new point serve */
        if (dist2 > 900.0f) {
            g_ee4_count = 0;
        } else if (dist2 < 0.015f && (now - top->ms) < 20u) {
            top->vx = vx; top->vy = vy; top->vz = vz;
            top->speed = spd;
            return;
        }
    }
    if (g_ee4_count >= EE4_TRAIL_MAX) {
        memmove(&g_ee4_trail[0], &g_ee4_trail[1], (EE4_TRAIL_MAX - 1) * sizeof(EE4TrailPt));
        g_ee4_count = EE4_TRAIL_MAX - 1;
    }
    EE4TrailPt *pt = &g_ee4_trail[g_ee4_count++];
    pt->x = x; pt->y = y; pt->z = z;
    pt->vx = vx; pt->vy = vy; pt->vz = vz;
    pt->speed = spd;
    pt->ms = now;
}

static inline void ee_sample_ball_from_match(void *match_mgr) {
    if (!match_mgr) return;
    void *ball_obj = (void *)((char *)match_mgr + 0x10);
    void *ball_phys = *(void **)((char *)ball_obj + 4);
    if (!ball_phys) return;
    uint32_t max_frames = *(uint32_t *)((char *)ball_phys + 0x65fc);
    if (max_frames == 0 || max_frames > 4096) return;

    float frame_out[10];
    memset(frame_out, 0, sizeof(frame_out));
    typedef void(__thiscall *BallEval_t)(void *, float *, int);
    ((BallEval_t)0x00476c90)(ball_obj, frame_out, 0);
    ee_record_ball_pos(frame_out, frame_out + 5);
}

static inline void ee_on_ball_simulate(void *ball_phys, float *start_pos, float *vel) {
    (void)ball_phys;
    ee_apply_weapon_physics(NULL, vel, 0);
    ee_record_ball_pos(start_pos, vel);
}

static inline void ee_on_live_match_tick(void *match_mgr) {
    g_ee_live_match_present_frame = g_present_calls;
    g_ee_last_match_mgr = match_mgr;
    ee_sample_ball_from_match(match_mgr);
    ee_mcenroe_tick(1);
}

/*
 * Project 3D world point using VT4's active CameraManager (0x00836698):
 *   cam = *(mgr + *(int*)(mgr + 8) * 56 + 0x28)
 *   View 3x4 at cam + 0xc0; Proj rows at *(cam + 0x0c) + 0x68.
 * Returns 1 when point lies in front of camera (cw > 0.05f).
 */
static inline int ee_world_to_screen(float x, float y, float z, float *out_sx, float *out_sy) {
    uintptr_t mgr = *(volatile uintptr_t *)0x00836698;
    if (!mgr) return 0;
    int idx = *(int *)(mgr + 8);
    if (idx < 0 || idx >= 16) return 0;
    uintptr_t cam = *(uintptr_t *)(mgr + (uintptr_t)idx * 56u + 0x28u);
    if (!cam) return 0;
    uintptr_t proj_obj = *(uintptr_t *)(cam + 0x0cu);
    if (!proj_obj) return 0;

    const float *vm = (const float *)(cam + 0xc0u);
    const float *pm = (const float *)(proj_obj + 0x68u);

    float vx = vm[0] * x + vm[1] * y + vm[2] * z + vm[3];
    float vy = vm[4] * x + vm[5] * y + vm[6] * z + vm[7];
    float vz = vm[8] * x + vm[9] * y + vm[10] * z + vm[11];

    float cx = pm[0] * vx + pm[1] * vy + pm[2] * vz + pm[3];
    float cy = pm[4] * vx + pm[5] * vy + pm[6] * vz + pm[7];
    float cw = pm[8] * vx + pm[9] * vy + pm[10] * vz + pm[11];
    if (!isfinite(cw) || cw <= 0.05f) return 0;

    float nx = cx / cw;
    float ny = cy / cw;
    float w = (float)(g_cfg_width > 0 ? g_cfg_width : 1280);
    float h = (float)(g_cfg_height > 0 ? g_cfg_height : 720);
    if (*(const uint8_t *)(mgr + 4) != 0) w *= 0.5f;

    *out_sx = (nx + 1.0f) * 0.5f * w;
    *out_sy = (1.0f - ny) * 0.5f * h;
    return isfinite(*out_sx) && isfinite(*out_sy);
}

static inline DWORD ee_velocity_aura_color(float vx, float vy, float vz, float speed, uint8_t alpha) {
    uint8_t r, g, b;
    (void)vx;
    /* Color-code by vy (lift vs smash) and vz (depth pace): DBZ / Mario Power Tennis */
    if (vy < -0.14f && speed > 0.65f) {
        /* Downward smash -> Solar Flare Fiery Orange-Crimson */
        r = 255; g = 105; b = 24;
    } else if (vy > 0.28f) {
        /* Heavy topspin moonball / baguette loft -> Emerald-Violet Ki */
        r = 175; g = 255; b = 55;
    } else if (speed > 1.20f || fabsf(vz) > 0.95f) {
        /* Super Shot / blazing drive -> DBZ Super-Gold / Magenta */
        r = 255; g = 215; b = 45;
    } else {
        /* Standard charged shot -> Electric Cyan Ki */
        r = 45; g = 210; b = 255;
    }
    return ((DWORD)alpha << 24) | ((DWORD)r << 16) | ((DWORD)g << 8) | (DWORD)b;
}

static inline void ee_render_ball_aura_and_trail(void *dev, float sx, float sy) {
    if (g_cfg_multiverse_mode != 2 && g_cfg_multiverse_mode != 3) return;
    if (g_ee4_count <= 0) return;

    uint32_t now = ee_now_ms();
    if ((now - g_ee4_trail[g_ee4_count - 1].ms) > 900u) return;

    float ps_pts[EE4_TRAIL_MAX][2];
    int   ps_ok[EE4_TRAIL_MAX];
    for (int i = 0; i < g_ee4_count; i++) {
        ps_ok[i] = ee_world_to_screen(g_ee4_trail[i].x, g_ee4_trail[i].y, g_ee4_trail[i].z,
                                      &ps_pts[i][0], &ps_pts[i][1]);
    }

    EE_ScreenVertex verts[EE4_TRAIL_MAX * 18 + 96];
    uint32_t tri_cnt = 0;
    float scale = 0.5f * (sx + sy);
    if (scale < 0.4f) scale = 1.0f;

    /* Switch to Additive Blending (D3DBLEND_ONE) */
    ee_set_render_state(dev, EE_D3DRS_ALPHABLENDEN, 1u);
    ee_set_render_state(dev, EE_D3DRS_SRCBLEND, EE_D3DBLEND_SRCALPHA);
    ee_set_render_state(dev, EE_D3DRS_DESTBLEND, EE_D3DBLEND_ONE);
    ee_set_render_state(dev, EE_D3DRS_ZENABLE, 0u);
    ee_set_render_state(dev, EE_D3DRS_LIGHTING, 0u);
    ee_set_render_state(dev, EE_D3DRS_CULLMODE, EE_D3DCULL_NONE);

    /* Multi-segment comet ribbon behind ball */
    for (int i = 0; i < g_ee4_count - 1 && tri_cnt + 4 < (sizeof(verts) / sizeof(verts[0])) / 3; i++) {
        if (!ps_ok[i] || !ps_ok[i + 1]) continue;
        float age0 = (float)(now - g_ee4_trail[i].ms) * 0.001f;
        float age1 = (float)(now - g_ee4_trail[i + 1].ms) * 0.001f;
        if (age0 > 0.70f && age1 > 0.70f) continue;

        float t0 = (float)(i + 1) / (float)g_ee4_count;
        float t1 = (float)(i + 2) / (float)g_ee4_count;
        float fade0 = ee_clampf(1.0f - age0 / 0.70f, 0.0f, 1.0f) * t0 * t0;
        float fade1 = ee_clampf(1.0f - age1 / 0.70f, 0.0f, 1.0f) * t1 * t1;

        float x0 = ps_pts[i][0], y0 = ps_pts[i][1];
        float x1 = ps_pts[i + 1][0], y1 = ps_pts[i + 1][1];
        float dx = x1 - x0, dy = y1 - y0;
        float seg_len = sqrtf(dx * dx + dy * dy);
        if (seg_len < 0.25f || seg_len > 420.0f * scale) continue;

        float nx = -dy / seg_len, ny = dx / seg_len;
        float r0 = (2.0f + 16.0f * t0) * scale;
        float r1 = (2.0f + 16.0f * t1) * scale;

        DWORD c0 = ee_velocity_aura_color(g_ee4_trail[i].vx, g_ee4_trail[i].vy, g_ee4_trail[i].vz,
                                          g_ee4_trail[i].speed, (uint8_t)(165.0f * fade0));
        DWORD c1 = ee_velocity_aura_color(g_ee4_trail[i + 1].vx, g_ee4_trail[i + 1].vy, g_ee4_trail[i + 1].vz,
                                          g_ee4_trail[i + 1].speed, (uint8_t)(210.0f * fade1));

        /* Outer glow quad (2 tris) */
        EE_ScreenVertex a0 = { x0 - nx * r0, y0 - ny * r0, 0.0f, 1.0f, c0 };
        EE_ScreenVertex b0 = { x0 + nx * r0, y0 + ny * r0, 0.0f, 1.0f, c0 };
        EE_ScreenVertex a1 = { x1 - nx * r1, y1 - ny * r1, 0.0f, 1.0f, c1 };
        EE_ScreenVertex b1 = { x1 + nx * r1, y1 + ny * r1, 0.0f, 1.0f, c1 };
        uint32_t base = tri_cnt * 3u;
        verts[base + 0] = a0; verts[base + 1] = b0; verts[base + 2] = a1;
        verts[base + 3] = b0; verts[base + 4] = b1; verts[base + 5] = a1;
        tri_cnt += 2u;

        /* Bright inner white-hot core ribbon */
        DWORD wc0 = ((DWORD)(uint8_t)(150.0f * fade0) << 24) | 0x00FFFFFFu;
        DWORD wc1 = ((DWORD)(uint8_t)(220.0f * fade1) << 24) | 0x00FFFFFFu;
        float cr0 = r0 * 0.38f, cr1 = r1 * 0.38f;
        EE_ScreenVertex ca0 = { x0 - nx * cr0, y0 - ny * cr0, 0.0f, 1.0f, wc0 };
        EE_ScreenVertex cb0 = { x0 + nx * cr0, y0 + ny * cr0, 0.0f, 1.0f, wc0 };
        EE_ScreenVertex ca1 = { x1 - nx * cr1, y1 - ny * cr1, 0.0f, 1.0f, wc1 };
        EE_ScreenVertex cb1 = { x1 + nx * cr1, y1 + ny * cr1, 0.0f, 1.0f, wc1 };
        base = tri_cnt * 3u;
        verts[base + 0] = ca0; verts[base + 1] = cb0; verts[base + 2] = ca1;
        verts[base + 3] = cb0; verts[base + 4] = cb1; verts[base + 5] = ca1;
        tri_cnt += 2u;
    }

    /* Pulsing layered aura halo at current live ball head */
    int hi = g_ee4_count - 1;
    if (ps_ok[hi]) {
        const EE4TrailPt *head = &g_ee4_trail[hi];
        float hx = ps_pts[hi][0], hy = ps_pts[hi][1];
        float pulse = 1.0f + 0.16f * sinf((float)now * 0.032f);
        float rad_outer = (28.0f + ee_clampf(head->speed * 10.0f, 0.0f, 18.0f)) * scale * pulse;
        float rad_inner = rad_outer * 0.45f;
        DWORD c_center = ((DWORD)215u << 24) | 0x00FFFFFFu;
        DWORD c_edge   = ee_velocity_aura_color(head->vx, head->vy, head->vz, head->speed, 10u);
        DWORD c_mid    = ee_velocity_aura_color(head->vx, head->vy, head->vz, head->speed, 185u);

        const int segs = 12;
        for (int s = 0; s < segs && tri_cnt + 2 < (sizeof(verts) / sizeof(verts[0])) / 3; s++) {
            float a0 = (float)s * (6.2831853f / (float)segs);
            float a1 = (float)(s + 1) * (6.2831853f / (float)segs);
            uint32_t base = tri_cnt * 3u;
            verts[base + 0] = (EE_ScreenVertex){ hx, hy, 0.0f, 1.0f, c_mid };
            verts[base + 1] = (EE_ScreenVertex){ hx + cosf(a0) * rad_outer, hy + sinf(a0) * rad_outer, 0.0f, 1.0f, c_edge };
            verts[base + 2] = (EE_ScreenVertex){ hx + cosf(a1) * rad_outer, hy + sinf(a1) * rad_outer, 0.0f, 1.0f, c_edge };
            tri_cnt += 1u;

            base = tri_cnt * 3u;
            verts[base + 0] = (EE_ScreenVertex){ hx, hy, 0.0f, 1.0f, c_center };
            verts[base + 1] = (EE_ScreenVertex){ hx + cosf(a0) * rad_inner, hy + sinf(a0) * rad_inner, 0.0f, 1.0f, c_edge };
            verts[base + 2] = (EE_ScreenVertex){ hx + cosf(a1) * rad_inner, hy + sinf(a1) * rad_inner, 0.0f, 1.0f, c_edge };
            tri_cnt += 1u;
        }
    }

    if (tri_cnt > 0) {
        ee_draw_tri_list_up(dev, verts, tri_cnt);
    }

    /* Restore standard alpha blend before drawing HUD elements */
    ee_set_render_state(dev, EE_D3DRS_DESTBLEND, EE_D3DBLEND_INVSRCALPHA);
}

/* Unified render entrypoint called from hk_EndScene */
static inline void ee_render_match_overlay(void *dev, float sx, float sy) {
    if (!dev || g_menu_visible) return;
    uint32_t diff = g_present_calls - g_ee_live_match_present_frame;
    if (g_ee_live_match_present_frame == 0 || diff > 4u) {
        /* If not currently inside active LiveMatch frame, ensure McEnroe QTE resets safely */
        if (diff > 15u && g_ee1_state != EE_MCENROE_IDLE) {
            ee_mcenroe_tick(0);
        }
        return;
    }

    /* Re-sample ball at render cadence for zero-latency visual aura */
    if (g_ee_last_match_mgr) {
        ee_sample_ball_from_match(g_ee_last_match_mgr);
    }

    if (!begin_overlay_state(dev)) return;
    ee_render_ball_aura_and_trail(dev, sx, sy);
    ee_mcenroe_render(dev, sx, sy);
    end_overlay_state(dev);
}

#endif /* MULTIVERSE_MODES_H */
