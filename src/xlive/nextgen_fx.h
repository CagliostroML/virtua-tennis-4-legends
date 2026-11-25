/*
 * nextgen_fx.h — Native DirectX 9 Next-Gen Post-Processing Suite (ps_3_0)
 *                for Virtua Tennis 4: Legends & Next-Gen Edition.
 *
 * Self-contained header included by src/xlive/xlive.c.
 * Zero external ReShade/compiler DLL dependencies at runtime (uses embedded
 * precompiled ps_3_0 bytecode compiled from HLSL, with full StateBlock &
 * hk_Reset device-loss safety).
 *
 * Pipeline stages in single fullscreen ps_3_0 pass:
 *   1. AMD FidelityFX CAS (Contrast Adaptive Sharpening) — brings out skin pores,
 *      iris fibers, hair strands & court texture with zero haloing.
 *   2. 3D Local Micro-Contrast / Clarity (1.5-texel bilinear ring) — enhances
 *      facial depth around eyes, nose, jaw & clothing while protecting HUD edges.
 *   3. Filmic ACES-inspired Tone Mapping + Natural Broadcast Daylight Grading +
 *      Skin-Safe Vibrance — removes VT4's washed-out 2011 yellowish haze.
 */
#ifndef VT4_NEXTGEN_FX_H
#define VT4_NEXTGEN_FX_H

#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <math.h>
#include <windows.h>

/* =========================================================================
 * Configuration & Live Toggle State ([Graphics] in vt4_settings.ini)
 * ========================================================================= */
static uint32_t g_cfg_nextgen_fx      = 1;     /* 1 = ON (default for Profile 0 & 1; auto-0 on Profile 2 Android) */
static float    g_cfg_nextgen_sharpen = 0.22f; /* 0.0 .. 1.5 (default 0.22: silky-clean, zero noise) */
static uint32_t g_cfg_nextgen_filmic  = 1;     /* 1 = ACES Filmic + Daylight Grading ON */

static void    *g_ngfx_ps             = NULL;  /* IDirect3DPixelShader9* */
static void    *g_ngfx_rt_tex         = NULL;  /* IDirect3DTexture9* */
static void    *g_ngfx_rt_surf        = NULL;  /* IDirect3DSurface9* */
static void    *g_ngfx_sb             = NULL;  /* IDirect3DStateBlock9* */
static uint32_t g_ngfx_rt_w           = 0;
static uint32_t g_ngfx_rt_h           = 0;
static uint32_t g_ngfx_rt_fmt         = 0;
static int      g_ngfx_init_failed    = 0;
static int      g_ngfx_logged_active  = 0;
static int      g_ngfx_prev_f8        = 0;
static uint32_t g_ngfx_applied_frames = 0;

/* Precompiled ps_3_0 bytecode (543 DWORDs = 2172 bytes, compiled via D3DCompile)
 * Features soft noise-floor coring (ignores <2.2% DXT/court grain) + gentle CAS +
 * noise-cored 3D micro-clarity (0.08) + silky ACES filmic daylight grading.
 * Registers:
 *   s0 : backbuffer copy sampler (bilinear, clamp)
 *   c0 : (1.0/width, 1.0/height, sharpen_strength=0.22, filmic_strength=1.0)
 *   c1 : (clarity_strength=0.08, vibrance_strength=0.09, 0, 0)
 */
static const DWORD g_ngfx_ps30_bytecode[543] = {
    0xffff0300u, 0x002efffeu, 0x42415443u, 0x0000001cu, 0x0000008bu, 0xffff0300u, 0x00000003u, 0x0000001cu,
    0x00008100u, 0x00000084u, 0x00000058u, 0x00000002u, 0x00020001u, 0x0000005cu, 0x00000000u, 0x0000006cu,
    0x00010002u, 0x00060001u, 0x0000005cu, 0x00000000u, 0x0000006fu, 0x00000003u, 0x00020001u, 0x00000074u,
    0x00000000u, 0xab003063u, 0x00030001u, 0x00040001u, 0x00000001u, 0x00000000u, 0x73003163u, 0xabab0030u,
    0x000c0004u, 0x00010001u, 0x00000001u, 0x00000000u, 0x335f7370u, 0x4d00305fu, 0x6f726369u, 0x74666f73u,
    0x29522820u, 0x534c4820u, 0x6853204cu, 0x72656461u, 0x6d6f4320u, 0x656c6970u, 0x30312072u, 0xab00312eu,
    0x05000051u, 0xa00f0002u, 0x00000000u, 0xbf800000u, 0x3f800000u, 0xbcb43958u, 0x05000051u, 0xa00f0003u,
    0x41a00000u, 0x3ee66666u, 0x40800000u, 0x40000000u, 0x05000051u, 0xa00f0004u, 0x38d1b717u, 0x3d8f5c29u,
    0x40800000u, 0x3f800000u, 0x05000051u, 0xa00f0005u, 0x3fc00000u, 0xbfc00000u, 0x3e800000u, 0xbc656042u,
    0x05000051u, 0xa00f0006u, 0x40900000u, 0x3f800000u, 0x3c23d70au, 0x3f85c28fu, 0x05000051u, 0xa00f0007u,
    0x3f818937u, 0x3f7ef9dbu, 0x3f824dd3u, 0x3e0f5c29u, 0x05000051u, 0xa00f0008u, 0x40000000u, 0x40400000u,
    0x4027de69u, 0x3cf5c28fu, 0x05000051u, 0xa00f0009u, 0x402284b6u, 0x3f170a3du, 0x3ed70a3du, 0x3e8f5c29u,
    0x05000051u, 0xa00f000au, 0x3e991687u, 0x3f1645a2u, 0x3de978d5u, 0x40200000u, 0x05000051u, 0xa00f000bu,
    0x3f0ccccdu, 0x3ee66666u, 0x00000000u, 0x00000000u, 0x0200001fu, 0x80000005u, 0x90030000u, 0x0200001fu,
    0x90000000u, 0xa00f0800u, 0x02000001u, 0x80070000u, 0xa0e40002u, 0x04000004u, 0x80030001u, 0xa0550000u,
    0x80e40000u, 0x90e40000u, 0x03000042u, 0x800f0001u, 0x80e40001u, 0xa0e40800u, 0x04000004u, 0x800f0002u,
    0xa0450000u, 0x80280000u, 0x90440000u, 0x03000042u, 0x800f0003u, 0x80e40002u, 0xa0e40800u, 0x03000042u,
    0x800f0002u, 0x80ee0002u, 0xa0e40800u, 0x0300000au, 0x80070004u, 0x80e40003u, 0x80e40001u, 0x04000004u,
    0x80030000u, 0xa0e40000u, 0x80e10000u, 0x90e40000u, 0x03000042u, 0x800f0000u, 0x80e40000u, 0xa0e40800u,
    0x0300000au, 0x80070005u, 0x80e40002u, 0x80e40000u, 0x0300000au, 0x80070006u, 0x80e40005u, 0x80e40004u,
    0x03000042u, 0x800f0004u, 0x90e40000u, 0xa0e40800u, 0x0300000au, 0x80070005u, 0x80e40006u, 0x80e40004u,
    0x0300000bu, 0x80070006u, 0x80e40001u, 0x80e40003u, 0x03000002u, 0x80070001u, 0x80e40001u, 0x80e40003u,
    0x03000002u, 0x80070001u, 0x80e40000u, 0x80e40001u, 0x0300000bu, 0x80070003u, 0x80e40000u, 0x80e40002u,
    0x03000002u, 0x80070000u, 0x80e40002u, 0x80e40001u, 0x0300000bu, 0x80070001u, 0x80e40006u, 0x80e40003u,
    0x0300000bu, 0x80070002u, 0x80e40004u, 0x80e40001u, 0x03000002u, 0x80070001u, 0x81e40002u, 0xa0ff0003u,
    0x0300000au, 0x80070003u, 0x80e40001u, 0x80e40005u, 0x03000002u, 0x80070001u, 0x81e40005u, 0x80e40002u,
    0x0300000bu, 0x80070005u, 0x80e40002u, 0xa0000004u, 0x02000006u, 0x80010002u, 0x80000005u, 0x02000006u,
    0x80020002u, 0x80550005u, 0x02000006u, 0x80040002u, 0x80aa0005u, 0x03000005u, 0x80170002u, 0x80e40002u,
    0x80e40003u, 0x02000007u, 0x80080000u, 0x80000002u, 0x02000006u, 0x80010003u, 0x80ff0000u, 0x02000007u,
    0x80080000u, 0x80550002u, 0x02000007u, 0x80080001u, 0x80aa0002u, 0x02000006u, 0x80040003u, 0x80ff0001u,
    0x02000006u, 0x80020003u, 0x80ff0000u, 0x03000002u, 0x80070002u, 0x80e40001u, 0xa0ff0002u, 0x03000002u,
    0x80070001u, 0x81e40001u, 0xa0550003u, 0x03000005u, 0x80170001u, 0x80e40001u, 0xa0aa0003u, 0x03000005u,
    0x80170002u, 0x80e40002u, 0xa0000003u, 0x03000005u, 0x80070001u, 0x80e40001u, 0x80e40002u, 0x03000005u,
    0x80070001u, 0x80e40001u, 0x80e40003u, 0x02000001u, 0x800f0002u, 0xa0e40000u, 0x03000005u, 0x80080000u,
    0x80aa0002u, 0xa0550004u, 0x03000005u, 0x80070001u, 0x80ff0000u, 0x81e40001u, 0x04000004u, 0x80070000u,
    0x80e40000u, 0x80e40001u, 0x80e40004u, 0x04000004u, 0x80070001u, 0x80e40001u, 0xa0aa0004u, 0xa0ff0004u,
    0x02000006u, 0x80010003u, 0x80000001u, 0x02000006u, 0x80020003u, 0x80550001u, 0x02000006u, 0x80040003u,
    0x80aa0001u, 0x03000005u, 0x80170000u, 0x80e40000u, 0x80e40003u, 0x04000004u, 0x80030001u, 0x80e40002u,
    0xa1000005u, 0x90e40000u, 0x03000042u, 0x800f0001u, 0x80e40001u, 0xa0e40800u, 0x04000004u, 0x800f0003u,
    0x80440002u, 0xa0140005u, 0x90440000u, 0x03000042u, 0x800f0004u, 0x80e40003u, 0xa0e40800u, 0x03000042u,
    0x800f0003u, 0x80ee0003u, 0xa0e40800u, 0x03000002u, 0x80070001u, 0x80e40001u, 0x80e40004u, 0x03000002u,
    0x80070001u, 0x80e40003u, 0x80e40001u, 0x04000004u, 0x80030002u, 0x80e40002u, 0xa0000005u, 0x90e40000u,
    0x03000042u, 0x800f0003u, 0x80e40002u, 0xa0e40800u, 0x03000002u, 0x80070001u, 0x80e40001u, 0x80e40003u,
    0x04000004u, 0x80070001u, 0x80e40001u, 0xa1aa0005u, 0x80e40000u, 0x04000058u, 0x80070003u, 0x81e40001u,
    0xa0000002u, 0xa0aa0002u, 0x04000058u, 0x80070004u, 0x80e40001u, 0xa1000002u, 0xa1aa0002u, 0x03000002u,
    0x80070003u, 0x80e40003u, 0x80e40004u, 0x03000002u, 0x80070004u, 0x8be40001u, 0xa0ff0005u, 0x04000004u,
    0x80070001u, 0x8be40001u, 0xa1000006u, 0xa0550006u, 0x0300000bu, 0x80070005u, 0x80e40001u, 0xa0000002u,
    0x03000005u, 0x80070001u, 0x80e40003u, 0x80e40004u, 0x04000058u, 0x80070001u, 0x80e40004u, 0x80e40001u,
    0xa0000002u, 0x03000005u, 0x80070001u, 0x80e40005u, 0x80e40001u, 0x03000005u, 0x80080000u, 0x80aa0002u,
    0xa0000001u, 0x04000004u, 0x80170000u, 0x80e40001u, 0x80ff0000u, 0x80e40000u, 0x03000005u, 0x80170001u,
    0x80e40000u, 0xa0e40007u, 0x04000004u, 0x80070002u, 0x80e40001u, 0xa0aa0008u, 0xa0ff0008u, 0x03000005u,
    0x80070003u, 0x80e40001u, 0xa0ff0006u, 0x03000005u, 0x80070002u, 0x80e40002u, 0x80e40003u, 0x04000004u,
    0x80070004u, 0x80e40001u, 0xa0000009u, 0xa0550009u, 0x04000004u, 0x80070003u, 0x80e40003u, 0x80e40004u,
    0xa0ff0007u, 0x02000006u, 0x80010004u, 0x80000003u, 0x02000006u, 0x80020004u, 0x80550003u, 0x02000006u,
    0x80040004u, 0x80aa0003u, 0x03000005u, 0x80170002u, 0x80e40002u, 0x80e40004u, 0x03000005u, 0x80070003u,
    0x80e40001u, 0x80e40001u, 0x04000004u, 0x80070004u, 0x80e40001u, 0xa1000008u, 0xa0550008u, 0x04000004u,
    0x80070002u, 0x80e40003u, 0x81e40004u, 0x80e40002u, 0x03000005u, 0x80070003u, 0x80e40003u, 0x80e40004u,
    0x04000004u, 0x80070002u, 0x80e40002u, 0xa0aa0009u, 0x80e40003u, 0x04000012u, 0x80070003u, 0xa0ff0009u,
    0x80e40002u, 0x80e40001u, 0x03000002u, 0x80030001u, 0x81e60003u, 0x80e10003u, 0x04000058u, 0x80050001u,
    0x80000001u, 0x80e50003u, 0x80d60003u, 0x03000005u, 0x80180000u, 0x80550001u, 0xa0ff000au, 0x03000002u,
    0x80080000u, 0x81ff0000u, 0xa0aa0002u, 0x04000004u, 0x80080000u, 0x80ff0000u, 0xa000000bu, 0xa055000bu,
    0x0300000bu, 0x80010002u, 0x80000003u, 0x80000001u, 0x0300000au, 0x80020002u, 0x80aa0001u, 0x80000003u,
    0x03000002u, 0x80010001u, 0x81550002u, 0x80000002u, 0x03000002u, 0x80010001u, 0x81000001u, 0xa0aa0002u,
    0x03000005u, 0x80010001u, 0x80000001u, 0xa0550001u, 0x04000004u, 0x80080000u, 0x80000001u, 0x80ff0000u,
    0xa0aa0002u, 0x03000008u, 0x80010001u, 0x80e40003u, 0xa0e4000au, 0x04000012u, 0x80170002u, 0x80ff0000u,
    0x80e40003u, 0x80000001u, 0x02000001u, 0x80180000u, 0xa0ff0000u, 0x04000012u, 0x80070001u, 0x80ff0000u,
    0x80e40002u, 0x80e40000u, 0x03000002u, 0x80080000u, 0x81ff0002u, 0xa0aa0006u, 0x04000058u, 0x80070800u,
    0x80ff0000u, 0x80e40000u, 0x80e40001u, 0x02000001u, 0x80080800u, 0xa0aa0002u, 0x0000ffffu
};

#pragma pack(push, 1)
typedef struct {
    float x, y, z, rhw;
    float u, v;
} NgfxVertex;
#pragma pack(pop)

#define NGFX_FVF_XYZRHW_TEX1 0x0104u

static inline void ngfx_com_release(void **pp) {
    if (pp && *pp) {
        void *obj = *pp;
        *pp = NULL;
        void **vtbl = *(void ***)obj;
        if (vtbl && vtbl[2]) {
            typedef ULONG (__stdcall *Rel_t)(void *);
            ((Rel_t)vtbl[2])(obj);
        }
    }
}

/* Called in hk_Reset before g_real_reset(dev, pp) and on DLL_PROCESS_DETACH */
static void ngfx_on_reset(void) {
    ngfx_com_release(&g_ngfx_rt_surf);
    ngfx_com_release(&g_ngfx_rt_tex);
    ngfx_com_release(&g_ngfx_sb);
    ngfx_com_release(&g_ngfx_ps);
    g_ngfx_rt_w = 0;
    g_ngfx_rt_h = 0;
    g_ngfx_rt_fmt = 0;
    g_ngfx_init_failed = 0;
}

static void ngfx_load_config(const char *ini_path, uint32_t perf_profile) {
    int def_fx = (perf_profile == 2) ? 0 : 1;
    int raw_fx = GetPrivateProfileIntA("Graphics", "NextGenFX", def_fx, ini_path);
    /* Auto-disable on PerfProfile=2 (Android/Low-Spec) unless explicitly forced via NextGenFX=2 */
    if (perf_profile == 2 && raw_fx != 2) {
        g_cfg_nextgen_fx = 0;
    } else {
        g_cfg_nextgen_fx = (raw_fx != 0) ? 1u : 0u;
    }

    char sh_buf[32] = {0};
    GetPrivateProfileStringA("Graphics", "NextGenSharpen", "0.22", sh_buf, sizeof(sh_buf), ini_path);
    float sh = (float)atof(sh_buf);
    if (sh < 0.0f) sh = 0.0f;
    if (sh > 1.5f) sh = 1.5f;
    g_cfg_nextgen_sharpen = sh;

    g_cfg_nextgen_filmic = GetPrivateProfileIntA("Graphics", "NextGenFilmic", 1, ini_path) ? 1u : 0u;

    char env_buf[32];
    if (GetEnvironmentVariableA("VT4_NEXTGEN_FX", env_buf, sizeof(env_buf)) > 0) {
        g_cfg_nextgen_fx = (env_buf[0] != '0') ? 1u : 0u;
    }

    log_msg("[NextGenFX] Config: NextGenFX=%u NextGenSharpen=%.2f NextGenFilmic=%u (PerfProfile=%u, Hotkey=F8)",
            g_cfg_nextgen_fx, g_cfg_nextgen_sharpen, g_cfg_nextgen_filmic, perf_profile);
}

static inline void ngfx_toggle_f8(void) {
    g_cfg_nextgen_fx = g_cfg_nextgen_fx ? 0u : 1u;
    log_msg("[NextGenFX] Toggled via F8: NextGenFX=%u (sharpen=%.2f filmic=%u frame=%u)",
            g_cfg_nextgen_fx, g_cfg_nextgen_sharpen, g_cfg_nextgen_filmic, g_present_calls);
}

static int ngfx_ensure_resources(void *dev, uint32_t w, uint32_t h, uint32_t fmt) {
    if (g_ngfx_init_failed || !dev || !*(void ***)dev || w == 0 || h == 0) return 0;
    void **vtbl = *(void ***)dev;

    /* 1. Create ps_3_0 Pixel Shader from embedded bytecode */
    if (!g_ngfx_ps) {
        typedef HRESULT (__stdcall *CreatePS_t)(void *, const DWORD *, void **);
        CreatePS_t create_ps = (CreatePS_t)vtbl[106];
        if (!create_ps || FAILED(create_ps(dev, g_ngfx_ps30_bytecode, &g_ngfx_ps)) || !g_ngfx_ps) {
            log_msg("[NextGenFX] CreatePixelShader(ps_3_0) failed -> disabling NextGenFX safely");
            g_ngfx_init_failed = 1;
            return 0;
        }
    }

    /* 2. Create or resize offscreen RenderTarget texture matching BackBuffer */
    if (!g_ngfx_rt_tex || !g_ngfx_rt_surf || g_ngfx_rt_w != w || g_ngfx_rt_h != h || g_ngfx_rt_fmt != fmt) {
        ngfx_com_release(&g_ngfx_rt_surf);
        ngfx_com_release(&g_ngfx_rt_tex);

        /* Use g_real_createtexture if available so we bypass any resolution-hook recursion */
        typedef HRESULT (__stdcall *CreateTex_t)(void *, UINT, UINT, UINT, DWORD, DWORD, DWORD, void **, HANDLE *);
        CreateTex_t create_tex = g_real_createtexture ? g_real_createtexture : (CreateTex_t)vtbl[23];
        uint32_t tex_fmt = (fmt == 0) ? 22u /* D3DFMT_X8R8G8B8 */ : fmt;
        HRESULT hr = create_tex(dev, w, h, 1, 1 /* D3DUSAGE_RENDERTARGET */, tex_fmt, 0 /* D3DPOOL_DEFAULT */, &g_ngfx_rt_tex, NULL);
        if (FAILED(hr) || !g_ngfx_rt_tex) {
            hr = create_tex(dev, w, h, 1, 1, 21u /* D3DFMT_A8R8G8B8 */, 0, &g_ngfx_rt_tex, NULL);
        }
        if (FAILED(hr) || !g_ngfx_rt_tex) {
            log_msg("[NextGenFX] CreateTexture(%ux%u fmt=%u) failed (hr=0x%08lx) -> disabling safely", w, h, tex_fmt, (unsigned long)hr);
            g_ngfx_init_failed = 1;
            return 0;
        }

        void **tex_vtbl = *(void ***)g_ngfx_rt_tex;
        typedef HRESULT (__stdcall *GetSurf_t)(void *, UINT, void **);
        GetSurf_t get_surf = (GetSurf_t)tex_vtbl[18];
        if (!get_surf || FAILED(get_surf(g_ngfx_rt_tex, 0, &g_ngfx_rt_surf)) || !g_ngfx_rt_surf) {
            ngfx_com_release(&g_ngfx_rt_tex);
            g_ngfx_init_failed = 1;
            return 0;
        }

        g_ngfx_rt_w = w;
        g_ngfx_rt_h = h;
        g_ngfx_rt_fmt = fmt;
    }

    /* 3. Create reusable D3DSBT_ALL StateBlock */
    if (!g_ngfx_sb) {
        typedef HRESULT (__stdcall *CreateSB_t)(void *, int, void **);
        CreateSB_t create_sb = (CreateSB_t)vtbl[59];
        if (!create_sb || FAILED(create_sb(dev, 1 /* D3DSBT_ALL */, &g_ngfx_sb)) || !g_ngfx_sb) {
            log_msg("[NextGenFX] CreateStateBlock failed -> disabling safely");
            g_ngfx_init_failed = 1;
            return 0;
        }
    }

    if (!g_ngfx_logged_active) {
        g_ngfx_logged_active = 1;
        log_msg("[NextGenFX] Active: ps_3_0 CAS+Clarity+ACES Filmic initialized (%ux%u fmt=%u sharpen=%.2f filmic=%u)",
                w, h, fmt, g_cfg_nextgen_sharpen, g_cfg_nextgen_filmic);
    }
    return 1;
}

static void ngfx_on_present(void *dev) {
    /* Edge-triggered F8 check (works with physical keyboard & PostMessage automation) */
    int f8_down = is_key_down(VK_F8);
    if (f8_down && !g_ngfx_prev_f8) {
        ngfx_toggle_f8();
    }
    g_ngfx_prev_f8 = f8_down;

    if (!g_cfg_nextgen_fx || !dev || !*(void ***)dev || g_ngfx_init_failed) return;

    void **vtbl = *(void ***)dev;
    typedef HRESULT (__stdcall *GetBackBuffer_t)(void *, UINT, UINT, int, void **);
    GetBackBuffer_t get_bb = (GetBackBuffer_t)vtbl[18];
    if (!get_bb) return;

    void *pBB = NULL;
    if (FAILED(get_bb(dev, 0, 0, 0, &pBB)) || !pBB) return;

    /* Query exact BackBuffer dimensions & format */
    typedef struct {
        DWORD Format; DWORD Type; DWORD Usage; DWORD Pool;
        DWORD MultiSampleType; DWORD MultiSampleQuality;
        UINT  Width; UINT  Height;
    } NGFX_SURFACE_DESC;
    void **bb_vtbl = *(void ***)pBB;
    typedef HRESULT (__stdcall *GetDesc_t)(void *, NGFX_SURFACE_DESC *);
    GetDesc_t get_desc = (GetDesc_t)bb_vtbl[12];
    NGFX_SURFACE_DESC desc = {0};
    if (!get_desc || FAILED(get_desc(pBB, &desc)) || desc.Width == 0 || desc.Height == 0) {
        ngfx_com_release(&pBB);
        return;
    }

    if (!ngfx_ensure_resources(dev, desc.Width, desc.Height, desc.Format)) {
        ngfx_com_release(&pBB);
        return;
    }

    /* Resolve/copy BackBuffer -> g_ngfx_rt_surf via hardware StretchRect */
    typedef HRESULT (__stdcall *StretchRect_t)(void *, void *, const RECT *, void *, const RECT *, int);
    StretchRect_t stretch_rect = (StretchRect_t)vtbl[34];
    if (!stretch_rect || FAILED(stretch_rect(dev, pBB, NULL, g_ngfx_rt_surf, NULL, 1 /* D3DTEXF_POINT */))) {
        ngfx_com_release(&pBB);
        return;
    }

    /* Save full device state & render targets */
    int prev_overlay = g_in_overlay;
    g_in_overlay = 1;

    void **sb_vtbl = *(void ***)g_ngfx_sb;
    typedef HRESULT (__stdcall *SB_Fn_t)(void *);
    ((SB_Fn_t)sb_vtbl[4])(g_ngfx_sb); /* Capture */

    typedef HRESULT (__stdcall *GetRT_t)(void *, DWORD, void **);
    typedef HRESULT (__stdcall *SetRT_t)(void *, DWORD, void *);
    typedef HRESULT (__stdcall *GetDS_t)(void *, void **);
    typedef HRESULT (__stdcall *SetDS_t)(void *, void *);
    GetRT_t get_rt = (GetRT_t)vtbl[38];
    SetRT_t set_rt = g_real_setrendertarget ? g_real_setrendertarget : (SetRT_t)vtbl[37];
    GetDS_t get_ds = (GetDS_t)vtbl[40];
    SetDS_t set_ds = (SetDS_t)vtbl[39];

    void *pOrigRT = NULL;
    void *pOrigDS = NULL;
    if (get_rt) get_rt(dev, 0, &pOrigRT);
    if (get_ds) get_ds(dev, &pOrigDS);

    typedef HRESULT (__stdcall *SceneFn_t)(void *);
    SceneFn_t begin_sc = g_real_beginscene ? g_real_beginscene : (SceneFn_t)vtbl[41];
    SceneFn_t end_sc   = g_real_endscene   ? g_real_endscene   : (SceneFn_t)vtbl[42];

    if (SUCCEEDED(begin_sc(dev))) {
        set_rt(dev, 0, pBB);
        if (set_ds) set_ds(dev, NULL);

        typedef HRESULT (__stdcall *SetVP_t)(void *, const void *);
        SetVP_t set_vp = g_real_setviewport ? g_real_setviewport : (SetVP_t)vtbl[47];
        uint32_t vp[6] = { 0, 0, desc.Width, desc.Height, 0, 0x3f800000u };
        if (set_vp) set_vp(dev, vp);

        typedef HRESULT (__stdcall *SetRS_t)(void *, DWORD, DWORD);
        typedef HRESULT (__stdcall *SetSamp_t)(void *, DWORD, DWORD, DWORD);
        typedef HRESULT (__stdcall *SetTex_t)(void *, DWORD, void *);
        typedef HRESULT (__stdcall *SetFVF_t)(void *, DWORD);
        typedef HRESULT (__stdcall *SetShader_t)(void *, void *);
        typedef HRESULT (__stdcall *SetPSConstF_t)(void *, UINT, const float *, UINT);
        typedef HRESULT (__stdcall *DrawUP_t)(void *, int, UINT, const void *, UINT);

        SetRS_t       set_rs   = (SetRS_t)vtbl[57];
        SetSamp_t     set_samp = (SetSamp_t)vtbl[69];
        SetTex_t      set_tex  = (SetTex_t)vtbl[65];
        SetFVF_t      set_fvf  = (SetFVF_t)vtbl[89];
        SetShader_t   set_vs   = (SetShader_t)vtbl[92];
        SetShader_t   set_ps   = (SetShader_t)vtbl[107];
        SetPSConstF_t set_psc  = (SetPSConstF_t)vtbl[109];
        DrawUP_t      draw_up  = g_real_drawprimitiveup ? g_real_drawprimitiveup : (DrawUP_t)vtbl[83];

        set_rs(dev, 7,   0);   /* D3DRS_ZENABLE = FALSE */
        set_rs(dev, 14,  0);   /* D3DRS_ZWRITEENABLE = FALSE */
        set_rs(dev, 15,  0);   /* D3DRS_ALPHATESTENABLE = FALSE */
        set_rs(dev, 22,  1);   /* D3DRS_CULLMODE = D3DCULL_NONE */
        set_rs(dev, 27,  0);   /* D3DRS_ALPHABLENDENABLE = FALSE */
        set_rs(dev, 28,  0);   /* D3DRS_FOGENABLE = FALSE */
        set_rs(dev, 52,  0);   /* D3DRS_STENCILENABLE = FALSE */
        set_rs(dev, 137, 0);   /* D3DRS_LIGHTING = FALSE */
        set_rs(dev, 168, 0xFu);/* D3DRS_COLORWRITEENABLE = RGBA */
        set_rs(dev, 174, 0);   /* D3DRS_SCISSORTESTENABLE = FALSE */
        set_rs(dev, 194, 0);   /* D3DRS_SRGBWRITEENABLE = FALSE */

        set_samp(dev, 0, 1,  2); /* D3DSAMP_MAGFILTER = D3DTEXF_LINEAR */
        set_samp(dev, 0, 2,  2); /* D3DSAMP_MINFILTER = D3DTEXF_LINEAR */
        set_samp(dev, 0, 3,  0); /* D3DSAMP_MIPFILTER = D3DTEXF_NONE */
        set_samp(dev, 0, 4,  3); /* D3DSAMP_ADDRESSU  = D3DTADDRESS_CLAMP */
        set_samp(dev, 0, 5,  3); /* D3DSAMP_ADDRESSV  = D3DTADDRESS_CLAMP */
        set_samp(dev, 0, 11, 0); /* D3DSAMP_SRGBTEXTURE = 0 */

        float consts[8] = {
            1.0f / (float)desc.Width,
            1.0f / (float)desc.Height,
            g_cfg_nextgen_sharpen,
            g_cfg_nextgen_filmic ? 1.0f : 0.0f,
            0.08f, /* gentle noise-cored clarity micro-contrast */
            0.09f, /* skin-safe vibrance */
            0.0f,
            0.0f
        };

        set_vs(dev, NULL);
        set_ps(dev, g_ngfx_ps);
        set_psc(dev, 0, consts, 2);
        set_tex(dev, 0, g_ngfx_rt_tex);
        set_fvf(dev, NGFX_FVF_XYZRHW_TEX1);

        /* Half-texel (-0.5f) screen-space offset for exact 1:1 D3D9 texel-center alignment */
        float fw = (float)desc.Width;
        float fh = (float)desc.Height;
        NgfxVertex quad[4] = {
            {     -0.5f,      -0.5f, 0.0f, 1.0f, 0.0f, 0.0f },
            { fw - 0.5f,      -0.5f, 0.0f, 1.0f, 1.0f, 0.0f },
            {     -0.5f, fh - 0.5f, 0.0f, 1.0f, 0.0f, 1.0f },
            { fw - 0.5f, fh - 0.5f, 0.0f, 1.0f, 1.0f, 1.0f }
        };
        draw_up(dev, 5 /* D3DPT_TRIANGLESTRIP */, 2, quad, (UINT)sizeof(NgfxVertex));

        set_tex(dev, 0, NULL);
        set_ps(dev, NULL);
        end_sc(dev);
        g_ngfx_applied_frames++;
    }

    if (pOrigRT) set_rt(dev, 0, pOrigRT);
    if (set_ds)  set_ds(dev, pOrigDS);
    ((SB_Fn_t)sb_vtbl[5])(g_ngfx_sb); /* Apply */

    ngfx_com_release(&pOrigRT);
    ngfx_com_release(&pOrigDS);
    ngfx_com_release(&pBB);
    g_in_overlay = prev_overlay;
}

#endif /* VT4_NEXTGEN_FX_H */
