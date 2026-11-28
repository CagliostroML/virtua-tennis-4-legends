#define WIN32_LEAN_AND_MEAN
#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0600
#endif
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <math.h>

static int g_signin_notified = 0;
static char g_game_dir[MAX_PATH] = { 0 };
static wchar_t g_game_dir_w[MAX_PATH] = L".";
static wchar_t g_save_path[MAX_PATH] = L".\\save\\";
static wchar_t g_config_txt_path[MAX_PATH] = L".\\save\\Config.txt";
static char g_log_path[MAX_PATH] = { 0 };
static int g_paths_initialized = 0;
static int g_has_custom_roster = 1;
static uint32_t g_cfg_use_d3d9ex = 1;
static uint32_t g_cfg_locale_lcid = 0x0c0a;
static char g_cfg_locale_str[16] = "auto";
static HMODULE g_hD3DX43 = NULL;
static int g_d3dx43_attempted = 0;
static FILE *g_log = NULL;
static uint32_t g_present_calls = 0;
static uint32_t g_logic_ticks = 0;

static void init_portable_paths(void) {
    if (g_paths_initialized) return;
    g_paths_initialized = 1;

    char dir_a[MAX_PATH] = { 0 };
    DWORD n_a = GetModuleFileNameA(NULL, dir_a, MAX_PATH);
    if (n_a > 0 && n_a < MAX_PATH) {
        char *slash = strrchr(dir_a, '\\');
        if (slash) *slash = '\0';
    } else {
        strcpy(dir_a, ".");
    }
    snprintf(g_game_dir, sizeof(g_game_dir), "%s", dir_a);
    snprintf(g_log_path, sizeof(g_log_path), "%s\\xlive_mod.log", g_game_dir);

    wchar_t dir_w[MAX_PATH] = { 0 };
    DWORD n_w = GetModuleFileNameW(NULL, dir_w, MAX_PATH);
    if (n_w > 0 && n_w < MAX_PATH) {
        wchar_t *slash_w = wcsrchr(dir_w, L'\\');
        if (slash_w) *slash_w = L'\0';
    } else {
        wcscpy(dir_w, L".");
    }
    _snwprintf(g_game_dir_w, MAX_PATH, L"%ls", dir_w);
    g_game_dir_w[MAX_PATH - 1] = L'\0';

    wchar_t save_dir_no_slash[MAX_PATH] = { 0 };
    _snwprintf(save_dir_no_slash, MAX_PATH, L"%ls\\save", g_game_dir_w);
    save_dir_no_slash[MAX_PATH - 1] = L'\0';
    CreateDirectoryW(save_dir_no_slash, NULL);

    _snwprintf(g_save_path, MAX_PATH, L"%ls\\save\\", g_game_dir_w);
    g_save_path[MAX_PATH - 1] = L'\0';
    _snwprintf(g_config_txt_path, MAX_PATH, L"%ls\\save\\Config.txt", g_game_dir_w);
    g_config_txt_path[MAX_PATH - 1] = L'\0';
}

static void log_msg(const char *fmt, ...) {
    if (!g_paths_initialized) {
        init_portable_paths();
    }
    if (!g_log && g_log_path[0]) {
        g_log = fopen(g_log_path, "a");
    }
    if (g_log) {
        va_list ap;
        va_start(ap, fmt);
        vfprintf(g_log, fmt, ap);
        fprintf(g_log, "\n");
        fflush(g_log);
        va_end(ap);
    }
}

static HMODULE get_d3dx9_43(void) {
    if (!g_d3dx43_attempted) {
        g_d3dx43_attempted = 1;
        g_hD3DX43 = LoadLibraryA("d3dx9_43.dll");
        if (g_hD3DX43) {
            log_msg("[VT4-Mod] d3dx9_43.dll loaded (%p)", g_hD3DX43);
        } else {
            log_msg("[VT4-Mod] d3dx9_43.dll not found (err=%lu) - using GDI/D3D9 fallback",
                    (unsigned long)GetLastError());
        }
    }
    return g_hD3DX43;
}

static uint32_t resolve_vt4_locale(const char *loc) {
    if (loc && loc[0]) {
        if (_stricmp(loc, "es") == 0) return 0x0c0a;
        if (_stricmp(loc, "en") == 0) return 0x0409;
        if (_stricmp(loc, "fr") == 0) return 0x040c;
        if (_stricmp(loc, "de") == 0) return 0x0407;
        if (_stricmp(loc, "it") == 0) return 0x0410;
        if (_stricmp(loc, "ja") == 0) return 0x0411;
    }
    LANGID lang = GetUserDefaultUILanguage();
    switch (PRIMARYLANGID(lang)) {
        case LANG_SPANISH:  return 0x0c0a;
        case LANG_FRENCH:   return 0x040c;
        case LANG_GERMAN:   return 0x0407;
        case LANG_ITALIAN:  return 0x0410;
        case LANG_JAPANESE: return 0x0411;
        default:            return 0x0409;
    }
}

static void patch_bytes(uintptr_t addr, const void *data, size_t len) {
    DWORD old_prot = 0;
    if (VirtualProtect((void *)addr, len, PAGE_EXECUTE_READWRITE, &old_prot)) {
        memcpy((void *)addr, data, len);
        VirtualProtect((void *)addr, len, old_prot, &old_prot);
    }
}

static void patch_call(uintptr_t call_site, void *target_fn) {
    uint8_t code[5];
    code[0] = 0xE8;
    uint32_t rel = (uint32_t)(uintptr_t)target_fn - (call_site + 5);
    memcpy(&code[1], &rel, 4);
    patch_bytes(call_site, code, 5);
}

static void patch_nops(uintptr_t addr, size_t count) {
    uint8_t nops[64];
    if (count > sizeof(nops)) count = sizeof(nops);
    memset(nops, 0x90, count);
    patch_bytes(addr, nops, count);
}

// ============================================================================
// D3D9 diagnostics hook: Direct3DCreate9 (IAT) -> IDirect3D9::CreateDevice (vtbl #16)
// ============================================================================
typedef struct {
    UINT                BackBufferWidth;
    UINT                BackBufferHeight;
    UINT                BackBufferFormat;
    UINT                BackBufferCount;
    UINT                MultiSampleType;
    DWORD               MultiSampleQuality;
    UINT                SwapEffect;
    HWND                hDeviceWindow;
    BOOL                Windowed;
    BOOL                EnableAutoDepthStencil;
    UINT                AutoDepthStencilFormat;
    DWORD               Flags;
    UINT                FullScreen_RefreshRateInHz;
    UINT                PresentationInterval;
} VT4_D3DPRESENT_PARAMETERS;

typedef void *(__stdcall *Direct3DCreate9_t)(UINT);
typedef HRESULT (__stdcall *CreateDevice_t)(void *, UINT, DWORD, HWND, DWORD, VT4_D3DPRESENT_PARAMETERS *, void **);
static Direct3DCreate9_t g_real_d3dcreate9 = NULL;
static CreateDevice_t g_real_createdevice = NULL;

static void log_pp(const char *tag, const VT4_D3DPRESENT_PARAMETERS *pp) {
    log_msg("[VT4-Mod] %s PP: BB=%ux%u fmt=%u cnt=%u ms=%u/%u swap=%u hwnd=%p win=%d autoDS=%d dsfmt=%u flags=%08x refresh=%u interval=%08x",
            tag, pp->BackBufferWidth, pp->BackBufferHeight, pp->BackBufferFormat, pp->BackBufferCount,
            pp->MultiSampleType, pp->MultiSampleQuality, pp->SwapEffect, pp->hDeviceWindow,
            pp->Windowed, pp->EnableAutoDepthStencil, pp->AutoDepthStencilFormat, pp->Flags,
            pp->FullScreen_RefreshRateInHz, pp->PresentationInterval);
}

typedef HRESULT (__stdcall *Direct3DCreate9Ex_t)(UINT, void **);
static Direct3DCreate9Ex_t g_d3dcreate9ex = NULL;
static HWND g_game_hwnd = NULL;
static void *g_d3d_device = NULL;
static WNDPROC g_orig_wndproc = NULL;

static uint32_t g_cfg_width = 1920;
static uint32_t g_cfg_height = 1080;
static uint32_t g_cfg_windowed = 0; // 0 = borderless fullscreen (native), 1 = windowed
static uint32_t g_cfg_antialiasing = 4; // 0=Off, 2=2x, 4=4x, 8=8x
static uint32_t g_cfg_vsync = 1;
static uint32_t g_cfg_anisotropic = 16;
static uint32_t g_cfg_remove_live = 1;
static uint32_t g_cfg_classic_tv_cam = 0; // 0=Off, 1=Lock Classic VT2 TV Camera & disable ShotCamera zoom
static uint32_t g_cfg_match_speed_mode = 0; // 0=Normal 1.0x, 1=VT2 Turbo 1.20x, 2=VT2 Hyper 1.35x, 3=Pro Sim 0.90x
static uint32_t g_cfg_exb_rules = 0; // 0=Manual/Estandar, 1=3 Sets x 6J + TB, 2=Grand Slam 5 Sets x 6J + TB, 3=5 Sets Ventaja
static uint32_t g_cfg_clean_postfx = 1; // 0=Original SEGA (Bloom+Blur), 1=Ultra Nitido (Sin Bloom/Blur), 2=Suave (35% Glare)
static uint32_t g_cfg_multiverse_mode = 0; // 0=Off, 1=EE-2 Batalla Hielo/Barro, 2=EE-4 Super Golpes DBZ 300%, 3=Ambos!
#define EE_CFG_WEAPON_MODE_DEFINED
static uint32_t g_cfg_weapon_mode = 0; // 0=Normal, 1=Raqueta Madera 70s, 2=Sarten Metalica, 3=Baguette Gigante
static uint32_t g_cfg_broadcast_hud = 1; // 0=Off, 1=Modern Broadcast TV HUD [F7]
static uint32_t g_cfg_pro_physics = 0; // 0=Estandar VT4, 1=Simulacion Pro (Bola Realista)
static uint32_t g_cfg_touch_hud = 0; // 0=Off, 1=Auto (Android/Wine), 2=Always Visible [F6]
static uint32_t g_cfg_debug_log = 0; // 0=Off (normal), 1=Enable diagnostic hook logs ([DIAG-*])

static int g_is_fullscreen = 0;
static int g_vp_is_full_hd = 0;
static int g_sampler_dirty = 5;
static void *g_cached_rt = NULL;
static uint32_t g_cached_rt_w = 0;
static uint32_t g_cached_rt_h = 0;
static void sync_menu_indices_from_cfg(void);
static void touch_gamepad_reset_autohide(void);
static uint32_t g_mod_menu_open_frame = 0;

#include "perf_opt.h"
#include "voice_packs.h"
#include "player_stats.h"
static void ngfx_load_config(const char *ini_path, uint32_t perf_profile);
static void ngfx_on_reset(void);
static void netplay_init(const char *ini_path);
static void netplay_shutdown(void);
static void netplay_get_local_ip(char *out, size_t cap);
static void netplay_get_config(uint32_t *mode, char *ip_out, size_t ip_cap, uint16_t *port, uint32_t *delay);
static int  netplay_reconfigure_live(uint32_t mode, const char *peer_ip, uint16_t port, uint32_t delay_frames, const char *ini_path);
static void netplay_get_status_spanish(char *buf, size_t cap, uint32_t *out_argb);
static int  netplay_lan_discover(uint16_t port, char *out_ip, size_t ip_cap, uint16_t *out_port, uint32_t *out_delay, uint32_t timeout_ms);

static int g_vp_p1_id = -1;
static int g_vp_p2_id = -1;
static uint32_t g_vp_load_frame = 0;

static void load_vt4_settings(void) {
    init_portable_paths();
    char ini_path[MAX_PATH];
    snprintf(ini_path, sizeof(ini_path), "%s\\vt4_settings.ini", g_game_dir);

    DWORD attr = GetFileAttributesA(ini_path);
    if (attr == INVALID_FILE_ATTRIBUTES) {
        FILE *f = fopen(ini_path, "w");
        if (f) {
            fprintf(f, "[Graphics]\n"
                       "; Resolucion: 1920x1080 (Full HD), 2560x1440 (2K QHD), 3840x2160 (4K UHD), 1280x720 (HD)\n"
                       "Width=1920\n"
                       "Height=1080\n"
                       "; Modo Ventana: 0 = Pantalla Completa sin bordes (Borderless), 1 = Modo Ventana\n"
                       "Windowed=0\n"
                       "; Direct3D9Ex (reduce latencia y evita flicker en Alt-Tab; 0 = D3D9 estandar para GPUs antiguas/Winlator)\n"
                       "UseD3D9Ex=1\n"
                       "; Suavizado de bordes Anti-Aliasing (MSAA): 0 = Desactivado, 2 = 2x, 4 = 4x, 8 = 8x\n"
                       "AntiAliasing=4\n"
                       "; Sincronizacion Vertical: 1 = Activado (60 FPS estables sin cortes), 0 = Desactivado\n"
                       "VSync=1\n"
                       "; Filtrado Anisotropico para texturas de pista ultra nitidas: 16 = Ultra Nitido, 0 = Normal\n"
                       "AnisotropicFiltering=16\n"
                       "; Nitidez PostFX (EXTRA-6): 0 = Bloom+Blur Original, 1 = Ultra Nitido (Sin Bloom/Blur), 2 = Suave 35%%\n"
                       "CleanPostFX=1\n"
                       "; Motor Next-Gen DirectX 9 (CAS Sharpening + ACES Filmic + Micro-Clarity, Tecla F8 en vivo): 1 = ON, 0 = OFF\n"
                       "NextGenFX=1\n"
                       "NextGenSharpen=0.22\n"
                       "NextGenFilmic=1\n\n"
                       "[Menu]\n"
                       "; Quitar el modo LIVE / Red (servidor GFWL inactivo) del menu principal\n"
                       "RemoveLiveMode=1\n"
                       "; Idioma del juego: auto (SO), en, es, fr, de, it, ja\n"
                       "Locale=auto\n\n"
                       "[Gameplay]\n"
                       "; Fijar Camara TV Clasica (estilo VT2, desactiva zooms de Super Golpe): 0 = Normal, 1 = Activo\n"
                       "ClassicTVCamera=0\n"
                       "; Velocidad de Fisica en Partido: 0 = Normal (1.00x), 1 = VT2 Arcade Turbo (1.20x), 2 = VT2 Hyper (1.35x), 3 = Simulacion Pro (0.90x), 4 = Ritmo Relajado (0.85x)\n"
                       "MatchSpeedMode=0\n"
                       "; Multiverso Arcade (Fase 3): 0 = Off, 1 = EE-2 Batalla Hielo/Barro, 2 = EE-4 Super Golpes 300%%, 3 = Ambos\n"
                       "MultiverseMode=0\n"
                       "; Arma Arcade (EE-3): 0 = Normal, 1 = Raqueta Madera 70s, 2 = Sarten Metalica, 3 = Baguette Gigante\n"
                       "WeaponMode=0\n"
                       "; HUD TV Retransmision (Tecla F7 en partido): 1 = Activo, 0 = Desactivado\n"
                       "BroadcastHUD=1\n"
                       "; Fisicas Pro de Bola: 0 = Estandar VT4, 1 = Simulacion Pro (menos flotante)\n"
                       "ProPhysics=0\n"
                       "; Mando Xbox Tactil en Pantalla (Tecla F6): 0 = Off, 1 = Auto (Android/Wine), 2 = Siempre Visible\n"
                       "TouchXboxHUD=0\n\n"
                       "[Performance]\n"
                       "; Perfil de rendimiento: 0 = Ultra PC (Default), 1 = Esports (Baja Latencia), 2 = Android/Winlator Low-Spec\n"
                       "PerfProfile=0\n"
                       "; Desbloquear FPS (solo benchmark/turbo; 0 = 60 FPS exactos velocidad 1.00x, 1 = Sin limite)\n"
                       "UnlockFPS=0\n"
                       "TargetFPS=60\n\n"
                       "[Netplay]\n"
                       "; Online P2P UDP (Crossplay PC <-> Android): Mode 0=OFF, 1=HOST(P1), 2=CLIENT(P2)\n"
                       "Mode=0\n"
                       "PeerIP=127.0.0.1\n"
                       "Port=7777\n"
                       "LocalPort=0\n"
                       "DelayFrames=3\n");
            fclose(f);
            log_msg("[VT4-Mod] Created modern settings configuration file: %s", ini_path);
        }
    }

    g_cfg_width = GetPrivateProfileIntA("Graphics", "Width", 1920, ini_path);
    g_cfg_height = GetPrivateProfileIntA("Graphics", "Height", 1080, ini_path);
    g_cfg_windowed = GetPrivateProfileIntA("Graphics", "Windowed", 0, ini_path);
    g_cfg_use_d3d9ex = GetPrivateProfileIntA("Graphics", "UseD3D9Ex", 1, ini_path) ? 1 : 0;
    g_cfg_antialiasing = GetPrivateProfileIntA("Graphics", "AntiAliasing", 4, ini_path);
    g_cfg_vsync = GetPrivateProfileIntA("Graphics", "VSync", 1, ini_path);
    g_cfg_anisotropic = GetPrivateProfileIntA("Graphics", "AnisotropicFiltering", 16, ini_path);
    g_cfg_clean_postfx = GetPrivateProfileIntA("Graphics", "CleanPostFX", 1, ini_path);
    if (g_cfg_clean_postfx > 2) g_cfg_clean_postfx = 1;
    g_cfg_remove_live = GetPrivateProfileIntA("Menu", "RemoveLiveMode", 1, ini_path);
    GetPrivateProfileStringA("Menu", "Locale", "auto", g_cfg_locale_str, sizeof(g_cfg_locale_str), ini_path);
    g_cfg_locale_lcid = resolve_vt4_locale(g_cfg_locale_str);
    g_cfg_classic_tv_cam = GetPrivateProfileIntA("Gameplay", "ClassicTVCamera", 0, ini_path) ? 1 : 0;
    g_cfg_match_speed_mode = GetPrivateProfileIntA("Gameplay", "MatchSpeedMode", 0, ini_path);
    if (g_cfg_match_speed_mode > 4) g_cfg_match_speed_mode = 0;
    g_cfg_exb_rules = GetPrivateProfileIntA("Gameplay", "ExhibitionRules", 0, ini_path);
    if (g_cfg_exb_rules > 3) g_cfg_exb_rules = 0;
    g_cfg_multiverse_mode = GetPrivateProfileIntA("Gameplay", "MultiverseMode", 0, ini_path);
    if (g_cfg_multiverse_mode > 3) g_cfg_multiverse_mode = 0;
    g_cfg_weapon_mode = GetPrivateProfileIntA("Gameplay", "WeaponMode", 0, ini_path);
    if (g_cfg_weapon_mode > 3) g_cfg_weapon_mode = 0;
    g_cfg_broadcast_hud = GetPrivateProfileIntA("Gameplay", "BroadcastHUD", 1, ini_path) ? 1 : 0;
    g_cfg_pro_physics = GetPrivateProfileIntA("Gameplay", "ProPhysics", 0, ini_path) ? 1 : 0;
    g_cfg_touch_hud = GetPrivateProfileIntA("Gameplay", "TouchXboxHUD", 0, ini_path);
    if (g_cfg_touch_hud > 2) g_cfg_touch_hud = 0;
    g_cfg_debug_log = GetPrivateProfileIntA("Debug", "DebugLog", 0, ini_path) ? 1 : 0;

    if (g_cfg_width == 0 || g_cfg_height == 0) {
        uint32_t early_prof = GetPrivateProfileIntA("Performance", "PerfProfile", 0, ini_path);
        char env_p[16] = {0};
        if (GetEnvironmentVariableA("VT4_PERF_PROFILE", env_p, sizeof(env_p)) > 0) {
            uint32_t ep = (uint32_t)atoi(env_p);
            if (ep <= 2) early_prof = ep;
        }
        int sw = GetSystemMetrics(SM_CXSCREEN);
        int sh = GetSystemMetrics(SM_CYSCREEN);
        if (sw <= 0 || sh <= 0) { sw = 1280; sh = 720; }
        uint32_t rw = (uint32_t)sw, rh = (uint32_t)sh;
        if (early_prof == 2 && rh > 540u) {
            rh = 540u;
            rw = (uint32_t)((((uint64_t)sw * 540u) / (uint64_t)sh + 1u) & ~1u);
            if (rw < 640u) rw = 640u;
        }
        g_cfg_width = rw;
        g_cfg_height = rh;
        log_msg("[VT4-Mod] Auto resolution: screen=%dx%d -> render=%ux%u (PerfProfile=%u)",
                sw, sh, g_cfg_width, g_cfg_height, early_prof);
    }

    log_msg("[VT4-Mod] Settings loaded: %ux%u (windowed=%u msaa=%u vsync=%u aniso=%u cleanfx=%u remove_live=%u tv_lock=%u speed=%u mv=%u weapon=%u)",
            g_cfg_width, g_cfg_height, g_cfg_windowed, g_cfg_antialiasing,
            g_cfg_vsync, g_cfg_anisotropic, g_cfg_clean_postfx, g_cfg_remove_live,
            g_cfg_classic_tv_cam, g_cfg_match_speed_mode, g_cfg_multiverse_mode, g_cfg_weapon_mode);
    perf_load_config(ini_path);
    ngfx_load_config(ini_path, g_cfg_perf_profile);
    vp_init(g_game_dir);
    netplay_init(ini_path);
    sync_menu_indices_from_cfg();
}

// ============================================================================
// Phase 1B: Settings Menu, Options Integration & Direct3D 9 RenderTarget Scaling
// ============================================================================

#define NUM_SETTINGS_ITEMS 16

typedef struct {
    uint32_t w, h;
    const char *desc;
} ResChoice;

static const ResChoice s_res_choices[] = {
    { 1920, 1080, "1920x1080 (Full HD 1080p)" },
    { 2560, 1440, "2560x1440 (2K QHD 1440p)" },
    { 3440, 1440, "3440x1440 (21:9 Ultrawide)" },
    { 3840, 2160, "3840x2160 (4K UHD 2160p)" },
    { 1280, 720,  "1280x720 (HD 720p)" },
    { 1280, 800,  "1280x800 (Steam Deck 16:10)" },
    { 1024, 768,  "1024x768 (4:3 Arcade)" },
    { 1280, 960,  "1280x960 (4:3 HD)" },
    { 1600, 1200, "1600x1200 (4:3 UXGA)" },
    { 960,  540,  "960x540 (Android Turbo 16:9)" },
    { 854,  480,  "854x480 (Android Ligero 480p)" },
    { 1024, 576,  "1024x576 (Android HD-Lite)" }
};
#define NUM_RES_CHOICES (sizeof(s_res_choices) / sizeof(s_res_choices[0]))

static const char *s_windowed_choices[] = {
    "Pantalla Completa Sin Bordes",
    "Modo Ventana"
};

static const struct {
    uint32_t val;
    const char *desc;
} s_msaa_choices[] = {
    { 0, "Desactivado (Off)" },
    { 2, "2x MSAA" },
    { 4, "4x MSAA (Recomendado)" },
    { 8, "8x MSAA (Ultra)" }
};
#define NUM_MSAA_CHOICES (sizeof(s_msaa_choices) / sizeof(s_msaa_choices[0]))

static const char *s_vsync_choices[] = {
    "Desactivado (Baja Latencia / Sin Limite)",
    "Activado (60 FPS)"
};

static const struct {
    uint32_t val;
    const char *desc;
} s_aniso_choices[] = {
    { 0, "Desactivado" },
    { 4, "4x" },
    { 8, "8x" },
    { 16, "16x Ultra (Pistas nitidas)" }
};
#define NUM_ANISO_CHOICES (sizeof(s_aniso_choices) / sizeof(s_aniso_choices[0]))

static const char *s_postfx_choices[] = {
    "Original SEGA (Bloom + Blur DOF)",
    "Ultra Nitido 4K (Sin Bloom ni Blur)",
    "Suave Cinematografico (35% Glare)"
};
#define NUM_POSTFX_CHOICES (sizeof(s_postfx_choices) / sizeof(s_postfx_choices[0]))

static const char *s_live_choices[] = {
    "Desactivado",
    "Activado (Recomendado)"
};

static const char *s_tvcam_choices[] = {
    "Desactivado (VT4 Original)",
    "Activado (TV Clasica VT2)"
};

static const struct {
    float mult;
    const char *desc;
} s_speed_choices[] = {
    { 1.00f, "Normal (1.00x Original)" },
    { 1.20f, "VT2 Arcade Turbo (1.20x)" },
    { 1.35f, "VT2 Hyper Arcade (1.35x)" },
    { 0.90f, "Simulacion Pro (0.90x)" },
    { 0.85f, "Ritmo Relajado (0.85x)" }
};
#define NUM_SPEED_CHOICES (sizeof(s_speed_choices) / sizeof(s_speed_choices[0]))

static const struct {
    int sets;
    int games;
    int tiebreak;
    const char *desc;
} s_exb_rules_choices[] = {
    { 1, 2, 0, "Manual / Estandar (VT4 / Avanzadas)" },
    { 3, 6, 1, "Torneo 3 Sets x 6 Juegos + TB" },
    { 5, 6, 1, "Grand Slam 5 Sets x 6J + Tie-Break" },
    { 5, 6, 0, "5 Sets x 6J Ventaja (Sin Tie-Break)" }
};
#define NUM_EXB_RULES_CHOICES (sizeof(s_exb_rules_choices) / sizeof(s_exb_rules_choices[0]))

static const char *s_multiverse_choices[] = {
    "Desactivado (Fisicas Reales)",
    "EE-2: Superficies 50% Hielo / Barro",
    "EE-4: Super Golpes DBZ (300%)",
    "EE-2 + EE-4: Caos Multiverso Total"
};
#define NUM_MULTIVERSE_CHOICES (sizeof(s_multiverse_choices) / sizeof(s_multiverse_choices[0]))

static const char *s_weapon_choices[] = {
    "Desactivado (Raqueta Oficial)",
    "EE-3: Raqueta Madera 70s",
    "EE-3: Sarten Metalica (Roddick)",
    "EE-3: Baguette Gigante"
};
#define NUM_WEAPON_CHOICES (sizeof(s_weapon_choices) / sizeof(s_weapon_choices[0]))

static const char *s_bhud_choices[] = {
    "Desactivado (Oculto)",
    "Activo (Torneo + Radar km/h + Rally)"
};

static const char *s_prophys_choices[] = {
    "Estandar (Arcade VT4 Original)",
    "Simulacion Pro (Bola Realista)"
};

static const char *s_touchhud_choices[] = {
    "Desactivado (Oculto)",
    "Auto (Android / Wine)",
    "Siempre Visible (Tactil / Demo)"
};
#define NUM_TOUCHHUD_CHOICES (sizeof(s_touchhud_choices) / sizeof(s_touchhud_choices[0]))

static int s_idx_res = 0;
static int s_idx_win = 0;
static int s_idx_msaa = 2; // 4x default
static int s_idx_vsync = 1;
static int s_idx_aniso = 3; // 16x default
static int s_idx_postfx = 1; // Clean sharp 4K default
static int s_idx_live = 1;
static int s_idx_tvcam = 0;
static int s_idx_speed = 0;
static int s_idx_exbrules = 0;
static int s_idx_multiverse = 0;
static int s_idx_weapon = 0;
static int s_idx_bhud = 1;
static int s_idx_prophys = 0;
static int s_idx_touchhud = 0;

static int g_menu_visible = 0;
static int g_menu_selection = 0;
static int g_menu_saved_banner_timer = 0;
static int g_option_mode_active = 0;
static uint32_t g_option_mode_last_frame = 0;
static int g_menu_opened_by_optionmode = 0;
static uint32_t g_menu_close_cooldown_frame = 0;
static int g_opt_root_sel = 0;
static uint32_t g_opt_root_last_frame = 0;
static int g_opt_legends_sub = 0;
static void *g_opt_mode_ptr = NULL;

static inline void play_vt4_menu_se(int se_id) {
    ((void (__cdecl *)(int, int))0x0045e480)(se_id, 0);
}

static void close_legends_settings_menu(void) {
    g_menu_visible = 0;
    g_menu_opened_by_optionmode = 0;
    g_opt_legends_sub = 0;
    g_menu_close_cooldown_frame = g_present_calls;
}

static void sync_menu_indices_from_cfg(void) {
    s_idx_res = 0;
    for (int i = 0; i < (int)NUM_RES_CHOICES; i++) {
        if (s_res_choices[i].w == g_cfg_width && s_res_choices[i].h == g_cfg_height) {
            s_idx_res = i;
            break;
        }
    }
    s_idx_win = g_cfg_windowed ? 1 : 0;

    s_idx_msaa = 0;
    for (int i = 0; i < (int)NUM_MSAA_CHOICES; i++) {
        if (s_msaa_choices[i].val == g_cfg_antialiasing) {
            s_idx_msaa = i;
            break;
        }
    }

    s_idx_vsync = g_cfg_vsync ? 1 : 0;

    s_idx_aniso = 0;
    for (int i = 0; i < (int)NUM_ANISO_CHOICES; i++) {
        if (s_aniso_choices[i].val == g_cfg_anisotropic) {
            s_idx_aniso = i;
            break;
        }
    }

    s_idx_postfx = (g_cfg_clean_postfx < (uint32_t)NUM_POSTFX_CHOICES) ? (int)g_cfg_clean_postfx : 1;
    s_idx_live = g_cfg_remove_live ? 1 : 0;
    s_idx_tvcam = g_cfg_classic_tv_cam ? 1 : 0;
    s_idx_speed = (g_cfg_match_speed_mode < (uint32_t)NUM_SPEED_CHOICES) ? (int)g_cfg_match_speed_mode : 0;
    s_idx_exbrules = (g_cfg_exb_rules < (uint32_t)NUM_EXB_RULES_CHOICES) ? (int)g_cfg_exb_rules : 0;
    s_idx_multiverse = (g_cfg_multiverse_mode < (uint32_t)NUM_MULTIVERSE_CHOICES) ? (int)g_cfg_multiverse_mode : 0;
    s_idx_weapon = (g_cfg_weapon_mode < (uint32_t)NUM_WEAPON_CHOICES) ? (int)g_cfg_weapon_mode : 0;
    s_idx_bhud = g_cfg_broadcast_hud ? 1 : 0;
    s_idx_prophys = g_cfg_pro_physics ? 1 : 0;
    s_idx_touchhud = (g_cfg_touch_hud < (uint32_t)NUM_TOUCHHUD_CHOICES) ? (int)g_cfg_touch_hud : 0;
}

static void ensure_default_config_txt(void) {
    init_portable_paths();
    DWORD attr = GetFileAttributesW(g_config_txt_path);
    if (attr != INVALID_FILE_ATTRIBUTES) return;

    FILE *fout = _wfopen(g_config_txt_path, L"wb");
    if (!fout) {
        log_msg("[VT4-Mod] WARNING: Failed to create default Config.txt at %ls (err=%lu)",
                g_config_txt_path, (unsigned long)GetLastError());
        return;
    }

    static const wchar_t *const default_keymap =
        L"90 88 67 86 100 102 103 105 83 32 0 255 0 255 2 38 40 37 39 ";
    wchar_t out[4096];
    int pos = 0;
    out[pos++] = 0xFEFF;
    pos += swprintf(&out[pos], 4096 - pos,
        L"LegendsMod\r\n"
        L"LegendsMod\r\n"
        L"\r\n"
        L"(#0)\r\n"
        L"\r\n"
        L"%u\r\n"
        L"%u\r\n"
        L"2\r\n"
        L"0\r\n"
        L"0\r\n"
        L"%u\r\n"
        L"1\r\n"
        L"1\r\n"
        L"00000001-0000-0000-0000-000000000000 00000001-0000-0000-0000-000000000000 0 0\r\n"
        L"00000002-0000-0000-0000-000000000000 00000002-0000-0000-0000-000000000000 0 0\r\n"
        L"00000000-0000-0000-0000-000000000000 00000000-0000-0000-0000-000000000000 0 0\r\n"
        L"00000000-0000-0000-0000-000000000000 00000000-0000-0000-0000-000000000000 0 0\r\n"
        L"1\r\n"
        L"00000001-0000-0000-0000-000000000000\r\n",
        g_cfg_width, g_cfg_height, g_cfg_antialiasing);
    for (int i = 0; i < 16 && pos < 3950; i++) {
        pos += swprintf(&out[pos], 4096 - pos, L"%ls\r\n", default_keymap);
    }
    fwrite(out, sizeof(wchar_t), (size_t)pos, fout);
    fclose(fout);
    log_msg("[VT4-Mod] Auto-created default portable Config.txt at %ls (%ux%u, AA=%u)",
            g_config_txt_path, g_cfg_width, g_cfg_height, g_cfg_antialiasing);
}

static void update_config_txt(void) {
    ensure_default_config_txt();
    const wchar_t *config_path = g_config_txt_path;
    FILE *f = _wfopen(config_path, L"rb");
    if (!f) return;

    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    if (sz <= 2 || sz > 65536) {
        fclose(f);
        return;
    }

    wchar_t *buf = (wchar_t *)malloc(sz + 4);
    if (!buf) {
        fclose(f);
        return;
    }

    size_t read_bytes = fread(buf, 1, sz, f);
    fclose(f);

    if (buf[0] != 0xFEFF) {
        free(buf);
        return;
    }

    size_t num_wchars = read_bytes / sizeof(wchar_t);
    buf[num_wchars] = L'\0';

    wchar_t *new_buf = (wchar_t *)malloc((sz + 1024) * sizeof(wchar_t));
    if (!new_buf) {
        free(buf);
        return;
    }

    new_buf[0] = 0xFEFF;
    size_t new_len = 1;

    wchar_t *p = buf + 1;
    int line_idx = 0;
    while (*p) {
        wchar_t line[1024];
        size_t l_idx = 0;
        while (*p && *p != L'\r' && *p != L'\n' && l_idx < 1020) {
            line[l_idx++] = *p++;
        }
        line[l_idx] = L'\0';
        if (*p == L'\r') p++;
        if (*p == L'\n') p++;

        if (line_idx == 5) {
            swprintf(line, 1024, L"%u", g_cfg_width);
        } else if (line_idx == 6) {
            swprintf(line, 1024, L"%u", g_cfg_height);
        } else if (line_idx == 10) {
            swprintf(line, 1024, L"%u", g_cfg_antialiasing);
        }

        size_t slen = wcslen(line);
        memcpy(&new_buf[new_len], line, slen * sizeof(wchar_t));
        new_len += slen;
        new_buf[new_len++] = L'\r';
        new_buf[new_len++] = L'\n';
        line_idx++;
    }

    FILE *fout = _wfopen(config_path, L"wb");
    if (fout) {
        fwrite(new_buf, sizeof(wchar_t), new_len, fout);
        fclose(fout);
        log_msg("[VT4-Mod] Successfully updated %ls (lines 5=%u, 6=%u, 10=%u)",
                config_path, g_cfg_width, g_cfg_height, g_cfg_antialiasing);
    }

    free(new_buf);
    free(buf);
}

static void save_vt4_settings(void) {
    char ini_path[MAX_PATH];
    GetModuleFileNameA(NULL, ini_path, sizeof(ini_path));
    char *last_slash = strrchr(ini_path, '\\');
    if (last_slash) *last_slash = '\0';
    strncat(ini_path, "\\vt4_settings.ini", sizeof(ini_path) - strlen(ini_path) - 1);

    char val[32];
    snprintf(val, sizeof(val), "%u", g_cfg_width);
    WritePrivateProfileStringA("Graphics", "Width", val, ini_path);
    snprintf(val, sizeof(val), "%u", g_cfg_height);
    WritePrivateProfileStringA("Graphics", "Height", val, ini_path);
    snprintf(val, sizeof(val), "%u", g_cfg_windowed);
    WritePrivateProfileStringA("Graphics", "Windowed", val, ini_path);
    snprintf(val, sizeof(val), "%u", g_cfg_antialiasing);
    WritePrivateProfileStringA("Graphics", "AntiAliasing", val, ini_path);
    snprintf(val, sizeof(val), "%u", g_cfg_vsync);
    WritePrivateProfileStringA("Graphics", "VSync", val, ini_path);
    snprintf(val, sizeof(val), "%u", g_cfg_anisotropic);
    WritePrivateProfileStringA("Graphics", "AnisotropicFiltering", val, ini_path);
    snprintf(val, sizeof(val), "%u", g_cfg_clean_postfx);
    WritePrivateProfileStringA("Graphics", "CleanPostFX", val, ini_path);
    snprintf(val, sizeof(val), "%u", g_cfg_remove_live);
    WritePrivateProfileStringA("Menu", "RemoveLiveMode", val, ini_path);
    snprintf(val, sizeof(val), "%u", g_cfg_classic_tv_cam);
    WritePrivateProfileStringA("Gameplay", "ClassicTVCamera", val, ini_path);
    snprintf(val, sizeof(val), "%u", g_cfg_match_speed_mode);
    WritePrivateProfileStringA("Gameplay", "MatchSpeedMode", val, ini_path);
    snprintf(val, sizeof(val), "%u", g_cfg_exb_rules);
    WritePrivateProfileStringA("Gameplay", "ExhibitionRules", val, ini_path);
    snprintf(val, sizeof(val), "%u", g_cfg_multiverse_mode);
    WritePrivateProfileStringA("Gameplay", "MultiverseMode", val, ini_path);
    snprintf(val, sizeof(val), "%u", g_cfg_weapon_mode);
    WritePrivateProfileStringA("Gameplay", "WeaponMode", val, ini_path);
    snprintf(val, sizeof(val), "%u", g_cfg_broadcast_hud);
    WritePrivateProfileStringA("Gameplay", "BroadcastHUD", val, ini_path);
    snprintf(val, sizeof(val), "%u", g_cfg_pro_physics);
    WritePrivateProfileStringA("Gameplay", "ProPhysics", val, ini_path);
    snprintf(val, sizeof(val), "%u", g_cfg_touch_hud);
    WritePrivateProfileStringA("Gameplay", "TouchXboxHUD", val, ini_path);

    log_msg("[VT4-Mod] Settings saved to %s", ini_path);
}

static void (__cdecl *g_real_set_match_cam)(int cam_type, int apply_now) = NULL;

static void apply_exhibition_rule_preset(void);

static void apply_and_save_menu_settings(void *dev) {
    g_cfg_width = s_res_choices[s_idx_res].w;
    g_cfg_height = s_res_choices[s_idx_res].h;
    g_cfg_windowed = s_idx_win;
    g_cfg_antialiasing = s_msaa_choices[s_idx_msaa].val;
    g_cfg_vsync = s_idx_vsync;
    g_cfg_anisotropic = s_aniso_choices[s_idx_aniso].val;
    g_cfg_clean_postfx = (uint32_t)s_idx_postfx;
    g_cfg_remove_live = s_idx_live;
    g_cfg_classic_tv_cam = s_idx_tvcam ? 1 : 0;
    g_cfg_match_speed_mode = (uint32_t)s_idx_speed;
    g_cfg_exb_rules = (uint32_t)s_idx_exbrules;
    g_cfg_multiverse_mode = (uint32_t)s_idx_multiverse;
    g_cfg_weapon_mode = (uint32_t)s_idx_weapon;
    g_cfg_broadcast_hud = s_idx_bhud ? 1u : 0u;
    g_cfg_pro_physics = s_idx_prophys ? 1u : 0u;
    g_cfg_touch_hud = (uint32_t)s_idx_touchhud;
    touch_gamepad_reset_autohide();

    save_vt4_settings();
    apply_exhibition_rule_preset();
    update_config_txt();

    *(uint32_t *)0x00a75d24 = g_cfg_width;
    *(uint32_t *)0x00a75d28 = g_cfg_height;
    *(uint32_t *)0x00a75d7c = g_cfg_antialiasing;

    uintptr_t wm = *(uintptr_t *)0x00a75ad0;
    if (wm) {
        *(uint32_t *)wm = g_cfg_width;
        *(uint32_t *)(wm + 4) = g_cfg_height;
        *(uint32_t *)(wm + 0x4c) = g_cfg_width;
        *(uint32_t *)(wm + 0x50) = g_cfg_height;
    }

    if (g_game_hwnd) {
        int scr_w = GetSystemMetrics(SM_CXSCREEN);
        int scr_h = GetSystemMetrics(SM_CYSCREEN);
        if (!g_cfg_windowed) {
            SetWindowLongA(g_game_hwnd, GWL_STYLE, WS_POPUP | WS_VISIBLE);
            SetWindowPos(g_game_hwnd, HWND_TOP, 0, 0, scr_w, scr_h, SWP_SHOWWINDOW | SWP_FRAMECHANGED);
            g_is_fullscreen = 1;
        } else {
            RECT wr = { 0, 0, g_cfg_width, g_cfg_height };
            DWORD style = WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX | WS_VISIBLE;
            AdjustWindowRect(&wr, style, FALSE);
            int win_w = wr.right - wr.left;
            int win_h = wr.bottom - wr.top;
            int pos_x = (scr_w > win_w) ? (scr_w - win_w) / 2 : 0;
            int pos_y = (scr_h > win_h) ? (scr_h - win_h) / 2 : 0;
            SetWindowLongA(g_game_hwnd, GWL_STYLE, style);
            SetWindowPos(g_game_hwnd, HWND_TOP, pos_x, pos_y, win_w, win_h, SWP_SHOWWINDOW | SWP_FRAMECHANGED);
            g_is_fullscreen = 0;
        }
        UpdateWindow(g_game_hwnd);
    }

    g_vp_is_full_hd = 0;
    g_cached_rt = NULL;
    g_sampler_dirty = 5;

    if (dev && g_cfg_anisotropic > 0) {
        void **vtbl = *(void ***)dev;
        typedef HRESULT (__stdcall *SetSamplerState_t)(void *, DWORD, DWORD, DWORD);
        SetSamplerState_t set_sampler = (SetSamplerState_t)vtbl[69];
        if (set_sampler) {
            for (DWORD s = 0; s < 8; s++) {
                set_sampler(dev, s, 1, 3);
                set_sampler(dev, s, 2, 3);
                set_sampler(dev, s, 3, 2);
                set_sampler(dev, s, 10, g_cfg_anisotropic);
            }
        }
    }

    if (g_cfg_classic_tv_cam && g_real_set_match_cam && *(uintptr_t *)0x00835ecc != 0) {
        g_real_set_match_cam(0, 1);
    }

    g_menu_saved_banner_timer = 180;
    log_msg("[VT4-Mod] Settings applied immediately: %ux%u Win=%u MSAA=%u VSync=%u Aniso=%u Live=%u TVLock=%u Speed=%u",
            g_cfg_width, g_cfg_height, g_cfg_windowed, g_cfg_antialiasing,
            g_cfg_vsync, g_cfg_anisotropic, g_cfg_remove_live,
            g_cfg_classic_tv_cam, g_cfg_match_speed_mode);
}

static int handle_settings_menu_input(int vk, void *dev) {
    if (!g_menu_visible) return 0;

    switch (vk) {
        case VK_UP:
        case 'W': {
            g_menu_selection = (g_menu_selection - 1 + NUM_SETTINGS_ITEMS) % NUM_SETTINGS_ITEMS;
            play_vt4_menu_se(3);
            log_msg("[VT4-Mod] Menu Nav: Up -> selection=%d", g_menu_selection);
            return 1;
        }
        case VK_DOWN:
        case 'S': {
            g_menu_selection = (g_menu_selection + 1) % NUM_SETTINGS_ITEMS;
            play_vt4_menu_se(3);
            log_msg("[VT4-Mod] Menu Nav: Down -> selection=%d", g_menu_selection);
            return 1;
        }
        case VK_LEFT:
        case 'A': {
            switch (g_menu_selection) {
                case 0: s_idx_res = (s_idx_res - 1 + (int)NUM_RES_CHOICES) % (int)NUM_RES_CHOICES; break;
                case 1: s_idx_win = !s_idx_win; break;
                case 2: s_idx_msaa = (s_idx_msaa - 1 + (int)NUM_MSAA_CHOICES) % (int)NUM_MSAA_CHOICES; break;
                case 3: s_idx_vsync = !s_idx_vsync; break;
                case 4: s_idx_aniso = (s_idx_aniso - 1 + (int)NUM_ANISO_CHOICES) % (int)NUM_ANISO_CHOICES; break;
                case 5: s_idx_postfx = (s_idx_postfx - 1 + (int)NUM_POSTFX_CHOICES) % (int)NUM_POSTFX_CHOICES; break;
                case 6: s_idx_live = !s_idx_live; break;
                case 7: s_idx_tvcam = !s_idx_tvcam; break;
                case 8: s_idx_speed = (s_idx_speed - 1 + (int)NUM_SPEED_CHOICES) % (int)NUM_SPEED_CHOICES; break;
                case 9: s_idx_exbrules = (s_idx_exbrules - 1 + (int)NUM_EXB_RULES_CHOICES) % (int)NUM_EXB_RULES_CHOICES; break;
                case 10: s_idx_multiverse = (s_idx_multiverse - 1 + (int)NUM_MULTIVERSE_CHOICES) % (int)NUM_MULTIVERSE_CHOICES; break;
                case 11: s_idx_weapon = (s_idx_weapon - 1 + (int)NUM_WEAPON_CHOICES) % (int)NUM_WEAPON_CHOICES; break;
                case 12: s_idx_bhud = !s_idx_bhud; break;
                case 13: s_idx_prophys = !s_idx_prophys; break;
                case 14: s_idx_touchhud = (s_idx_touchhud - 1 + (int)NUM_TOUCHHUD_CHOICES) % (int)NUM_TOUCHHUD_CHOICES; break;
            }
            play_vt4_menu_se(4);
            log_msg("[VT4-Mod] Menu Value Left: item %d changed", g_menu_selection);
            return 1;
        }
        case VK_RIGHT:
        case 'D': {
            switch (g_menu_selection) {
                case 0: s_idx_res = (s_idx_res + 1) % (int)NUM_RES_CHOICES; break;
                case 1: s_idx_win = !s_idx_win; break;
                case 2: s_idx_msaa = (s_idx_msaa + 1) % (int)NUM_MSAA_CHOICES; break;
                case 3: s_idx_vsync = !s_idx_vsync; break;
                case 4: s_idx_aniso = (s_idx_aniso + 1) % (int)NUM_ANISO_CHOICES; break;
                case 5: s_idx_postfx = (s_idx_postfx + 1) % (int)NUM_POSTFX_CHOICES; break;
                case 6: s_idx_live = !s_idx_live; break;
                case 7: s_idx_tvcam = !s_idx_tvcam; break;
                case 8: s_idx_speed = (s_idx_speed + 1) % (int)NUM_SPEED_CHOICES; break;
                case 9: s_idx_exbrules = (s_idx_exbrules + 1) % (int)NUM_EXB_RULES_CHOICES; break;
                case 10: s_idx_multiverse = (s_idx_multiverse + 1) % (int)NUM_MULTIVERSE_CHOICES; break;
                case 11: s_idx_weapon = (s_idx_weapon + 1) % (int)NUM_WEAPON_CHOICES; break;
                case 12: s_idx_bhud = !s_idx_bhud; break;
                case 13: s_idx_prophys = !s_idx_prophys; break;
                case 14: s_idx_touchhud = (s_idx_touchhud + 1) % (int)NUM_TOUCHHUD_CHOICES; break;
            }
            play_vt4_menu_se(4);
            log_msg("[VT4-Mod] Menu Value Right: item %d changed", g_menu_selection);
            return 1;
        }
        case VK_RETURN:
        case VK_SPACE: {
            apply_and_save_menu_settings(dev);
            play_vt4_menu_se(5);
            return 1;
        }
        case VK_ESCAPE:
        case VK_BACK: {
            close_legends_settings_menu();
            play_vt4_menu_se(6);
            log_msg("[VT4-Mod] Menu closed by ESC/Back");
            return 1;
        }
    }
    return 0;
}

// ----------------------------------------------------------------------------
// Overlay Rendering Structures & Shaders
// ----------------------------------------------------------------------------
#define D3DFVF_XYZRHW 0x004
#define D3DFVF_DIFFUSE 0x040
#define D3DFVF_TEX1 0x100
#define FVF_SCREEN_VERTEX (D3DFVF_XYZRHW | D3DFVF_DIFFUSE)
#define FVF_TEXTURED_VERTEX (D3DFVF_XYZRHW | D3DFVF_DIFFUSE | D3DFVF_TEX1)

typedef struct {
    float x, y, z, rhw;
    DWORD color;
} ScreenVertex;

typedef struct {
    float x, y, z, rhw;
    DWORD color;
    float u, v;
} TexturedVertex;

typedef HRESULT (WINAPI *D3DXCreateFontA_t)(
    void *pDevice,
    INT Height,
    UINT Width,
    UINT Weight,
    UINT MipLevels,
    BOOL Italic,
    DWORD CharSet,
    DWORD OutputPrecision,
    DWORD Quality,
    DWORD PitchAndFamily,
    LPCSTR pFaceName,
    void **ppFont
);

typedef INT (WINAPI *D3DXFont_DrawTextA_t)(
    void *pFont,
    void *pSprite,
    LPCSTR pString,
    INT Count,
    RECT *pRect,
    DWORD Format,
    DWORD Color
);

typedef HRESULT (WINAPI *D3DXCreateSprite_t)(void *pDevice, void **ppSprite);
static D3DXCreateSprite_t g_d3dx_createsprite = NULL;
static void *g_pSprite = NULL;

static void *g_pFont = NULL;
static void *g_pFontTitle = NULL;
static D3DXCreateFontA_t g_d3dx_createfont = NULL;

static int g_in_overlay = 0;
static void *g_pOverlaySB = NULL;

static int begin_overlay_state(void *dev) {
    if (!dev) dev = g_d3d_device;
    if (!dev || !*(void ***)dev) return 0;
    void **vtbl = *(void ***)dev;

    typedef HRESULT (__stdcall *CreateStateBlock_t)(void *, int, void **);
    CreateStateBlock_t create_sb = (CreateStateBlock_t)vtbl[59];
    if (create_sb) {
        if (g_pOverlaySB) {
            typedef ULONG (__stdcall *Rel_t)(void *);
            ((Rel_t)(*(void ***)g_pOverlaySB)[2])(g_pOverlaySB);
            g_pOverlaySB = NULL;
        }
        create_sb(dev, 1 /* D3DSBT_ALL */, &g_pOverlaySB);
    }
    g_in_overlay = 1;
    return 1;
}

static void end_overlay_state(void *dev) {
    if (g_pOverlaySB) {
        void **sb_vtbl = *(void ***)g_pOverlaySB;
        typedef HRESULT (__stdcall *Apply_t)(void *);
        typedef ULONG   (__stdcall *Release_t)(void *);
        Apply_t   sb_apply   = (Apply_t)sb_vtbl[5]; // IDirect3DStateBlock9::Apply is vtable slot 5 (4 is Capture)
        Release_t sb_release = (Release_t)sb_vtbl[2];
        if (sb_apply) sb_apply(g_pOverlaySB);
        if (sb_release) sb_release(g_pOverlaySB);
        g_pOverlaySB = NULL;
    }
    g_in_overlay = 0;
}

static void ensure_d3d9_device_hooks(void *dev);

typedef HRESULT (WINAPI *D3DXCreateTextureFromFileA_t)(void *pDevice, LPCSTR pSrcFile, void **ppTexture);
static D3DXCreateTextureFromFileA_t g_d3dx_createtex = NULL;
static void *g_pCrestTex = NULL;
static void *g_pOptBtnUnselTex = NULL;
static void *g_pOptBtnSelTex = NULL;
static void *g_pNpBgTex = NULL;
static void *g_pNpRowUnselTex = NULL;
static void *g_pNpRowSelTex = NULL;
static void *g_pNpBtnUnselTex = NULL;
static void *g_pNpBtnSelTex = NULL;
static void *g_pNpCardTex = NULL;
static int   g_np_tex_attempted = 0;

static void __attribute__((noinline)) init_menu_fonts(void *dev) {
    if (!dev) dev = g_d3d_device;
    if (!dev || !*(void ***)dev) return;
    if (!g_d3dx_createfont || !g_d3dx_createsprite || !g_d3dx_createtex) {
        HMODULE hD3DX = get_d3dx9_43();
        if (hD3DX) {
            g_d3dx_createfont = (D3DXCreateFontA_t)GetProcAddress(hD3DX, "D3DXCreateFontA");
            g_d3dx_createsprite = (D3DXCreateSprite_t)GetProcAddress(hD3DX, "D3DXCreateSprite");
            g_d3dx_createtex = (D3DXCreateTextureFromFileA_t)GetProcAddress(hD3DX, "D3DXCreateTextureFromFileA");
        }
    }
    if (g_d3dx_createtex && !g_pCrestTex && g_game_dir[0]) {
        char crest_path[MAX_PATH];
        snprintf(crest_path, sizeof(crest_path), "%s\\archive\\vt4_legends_crest.png", g_game_dir);
        HRESULT hr_c = g_d3dx_createtex(dev, crest_path, &g_pCrestTex);
        log_msg("[VT4-Mod] Loaded Nano Banana crest texture '%s': %p (hr=0x%08lx)", crest_path, g_pCrestTex, (unsigned long)hr_c);
    }
    if (g_d3dx_createtex && !g_pOptBtnUnselTex && g_game_dir[0]) {
        char btn_path[MAX_PATH];
        snprintf(btn_path, sizeof(btn_path), "%s\\archive\\opt_btn_unsel.png", g_game_dir);
        if (FAILED(g_d3dx_createtex(dev, btn_path, &g_pOptBtnUnselTex))) g_pOptBtnUnselTex = NULL;
    }
    if (g_d3dx_createtex && !g_pOptBtnSelTex && g_game_dir[0]) {
        char btn_path[MAX_PATH];
        snprintf(btn_path, sizeof(btn_path), "%s\\archive\\opt_btn_sel.png", g_game_dir);
        if (FAILED(g_d3dx_createtex(dev, btn_path, &g_pOptBtnSelTex))) g_pOptBtnSelTex = NULL;
    }
    if (g_d3dx_createtex && !g_np_tex_attempted && g_game_dir[0]) {
        g_np_tex_attempted = 1;
        char p[MAX_PATH];
        snprintf(p, sizeof(p), "%s\\archive\\hud\\netplay\\netplay_bg.png", g_game_dir);
        if (FAILED(g_d3dx_createtex(dev, p, &g_pNpBgTex))) g_pNpBgTex = NULL;
        snprintf(p, sizeof(p), "%s\\archive\\hud\\netplay\\netplay_row_unsel.png", g_game_dir);
        if (FAILED(g_d3dx_createtex(dev, p, &g_pNpRowUnselTex))) g_pNpRowUnselTex = NULL;
        snprintf(p, sizeof(p), "%s\\archive\\hud\\netplay\\netplay_row_sel.png", g_game_dir);
        if (FAILED(g_d3dx_createtex(dev, p, &g_pNpRowSelTex))) g_pNpRowSelTex = NULL;
        snprintf(p, sizeof(p), "%s\\archive\\hud\\netplay\\netplay_btn_unsel.png", g_game_dir);
        if (FAILED(g_d3dx_createtex(dev, p, &g_pNpBtnUnselTex))) g_pNpBtnUnselTex = NULL;
        snprintf(p, sizeof(p), "%s\\archive\\hud\\netplay\\netplay_btn_sel.png", g_game_dir);
        if (FAILED(g_d3dx_createtex(dev, p, &g_pNpBtnSelTex))) g_pNpBtnSelTex = NULL;
        snprintf(p, sizeof(p), "%s\\archive\\hud\\netplay\\netplay_card.png", g_game_dir);
        if (FAILED(g_d3dx_createtex(dev, p, &g_pNpCardTex))) g_pNpCardTex = NULL;
    }
    if (g_d3dx_createsprite && !g_pSprite) {
        HRESULT hr_sp = g_d3dx_createsprite(dev, &g_pSprite);
        log_msg("[VT4-Mod] Created D3DXSprite object: %p (hr=0x%08lx)", g_pSprite, (unsigned long)hr_sp);
    }
    if (g_d3dx_createfont) {
        float fscale = (g_cfg_height > 0) ? ((float)g_cfg_height / 720.0f) : 1.0f;
        int title_h = (int)(22.0f * fscale + 0.5f);
        if (title_h < 13) title_h = 13;
        if (title_h > 44) title_h = 44;
        int body_h = (int)(18.0f * fscale + 0.5f);
        if (body_h < 11) body_h = 11;
        if (body_h > 36) body_h = 36;
        if (!g_pFontTitle) {
            HRESULT hr_ft = g_d3dx_createfont(dev, title_h, 0, FW_BOLD, 1, FALSE, DEFAULT_CHARSET,
                              OUT_DEFAULT_PRECIS, ANTIALIASED_QUALITY,
                              DEFAULT_PITCH | FF_DONTCARE, "Arial", &g_pFontTitle);
            log_msg("[VT4-Mod] Created D3DXFontTitle(%dpx): %p (hr=0x%08lx)", title_h, g_pFontTitle, (unsigned long)hr_ft);
        }
        if (!g_pFont) {
            HRESULT hr_f = g_d3dx_createfont(dev, body_h, 0, FW_NORMAL, 1, FALSE, DEFAULT_CHARSET,
                              OUT_DEFAULT_PRECIS, ANTIALIASED_QUALITY,
                              DEFAULT_PITCH | FF_DONTCARE, "Arial", &g_pFont);
            log_msg("[VT4-Mod] Created D3DXFont(%dpx): %p (hr=0x%08lx)", body_h, g_pFont, (unsigned long)hr_f);
        }
    }
}

static void draw_font_text(void *pFont, const char *text, RECT *r, DWORD color, int align) {
    if (!pFont || !text) return;
    void **vtbl = *(void ***)pFont;
    D3DXFont_DrawTextA_t fn = (D3DXFont_DrawTextA_t)vtbl[14];
    if (!fn) return;
    DWORD fmt = DT_NOCLIP | DT_VCENTER;
    if (align == 1) fmt |= DT_CENTER;
    else if (align == 2) fmt |= DT_RIGHT;
    else fmt |= DT_LEFT;
    fn(pFont, g_pSprite, text, -1, r, fmt, color);
}

typedef HRESULT (__stdcall *DrawPrimitiveUP_t)(void *, int, UINT, const void *, UINT);
static DrawPrimitiveUP_t g_real_drawprimitiveup = NULL;

static void draw_screen_quad(void *dev, float x1, float y1, float x2, float y2, DWORD color) {
    ScreenVertex verts[4] = {
        { x1, y1, 0.0f, 1.0f, color },
        { x2, y1, 0.0f, 1.0f, color },
        { x1, y2, 0.0f, 1.0f, color },
        { x2, y2, 0.0f, 1.0f, color }
    };

    void **vtbl = *(void ***)dev;
    typedef HRESULT (__stdcall *SetFVF_t)(void *, DWORD);
    typedef HRESULT (__stdcall *SetRenderState_t)(void *, DWORD, DWORD);
    typedef HRESULT (__stdcall *SetTexture_t)(void *, DWORD, void *);
    typedef HRESULT (__stdcall *SetVertexShader_t)(void *, void *);
    typedef HRESULT (__stdcall *SetPixelShader_t)(void *, void *);

    SetFVF_t set_fvf = (SetFVF_t)vtbl[89];
    SetRenderState_t set_rs = (SetRenderState_t)vtbl[57];
    SetTexture_t set_tex = (SetTexture_t)vtbl[65];
    SetVertexShader_t set_vs = (SetVertexShader_t)vtbl[92];
    SetPixelShader_t set_ps = (SetPixelShader_t)vtbl[107];

    if (set_vs) set_vs(dev, NULL);
    if (set_ps) set_ps(dev, NULL);
    if (set_tex) set_tex(dev, 0, NULL);

    if (set_rs) {
        set_rs(dev, 27, 1);  // D3DRS_ALPHABLENDENABLE = TRUE
        set_rs(dev, 19, 5);  // D3DRS_SRCBLEND = D3DBLEND_SRCALPHA (5)
        set_rs(dev, 20, 6);  // D3DRS_DESTBLEND = D3DBLEND_INVSRCALPHA (6)
        set_rs(dev, 137, 0); // D3DRS_LIGHTING = FALSE
        set_rs(dev, 22, 1);  // D3DRS_CULLMODE = D3DCULL_NONE (1)
        set_rs(dev, 7, 0);   // D3DRS_ZENABLE = FALSE
    }

    if (set_fvf) set_fvf(dev, FVF_SCREEN_VERTEX);
    if (g_real_drawprimitiveup) {
        g_real_drawprimitiveup(dev, 5, 2, verts, sizeof(ScreenVertex));
    }
}

static void draw_textured_quad(void *dev, void *tex, float x1, float y1, float x2, float y2, DWORD color);

static void render_settings_hud(void *dev) {
    if (!dev) return;

    int in_opt_root = (!g_menu_visible && !g_opt_legends_sub &&
                       g_opt_mode_ptr && g_present_calls <= g_opt_root_last_frame + 2 &&
                       *(int *)((char *)g_opt_mode_ptr + 0x94) == 0 &&
                       *(void **)((char *)g_opt_mode_ptr + 0x8c) != NULL);

    if (!g_menu_visible && !in_opt_root) return;
    if (!begin_overlay_state(dev)) return;

    init_menu_fonts(dev);
    ensure_d3d9_device_hooks(dev);

    void **vtbl = *(void ***)dev;
    typedef HRESULT (__stdcall *SetViewport_t)(void *, const void *);
    SetViewport_t set_vp = (SetViewport_t)vtbl[47];
    uint32_t full_vp[6] = { 0, 0, g_cfg_width, g_cfg_height, 0, 0x3f800000 };
    if (set_vp) set_vp(dev, full_vp);

    float sx = (float)g_cfg_width / 1280.0f;
    float sy = (float)g_cfg_height / 720.0f;

    // Mode A: Native 4th item row + Nano Banana VT4 LEGENDS crest inside OPCIONES
    if (in_opt_root) {
        if (g_pCrestTex) {
            float cx = 928.0f * sx, cy = 360.0f * sy, rad = 165.0f * sy;
            draw_textured_quad(dev, g_pCrestTex, cx - rad, cy - rad, cx + rad, cy + rad, 0xF5FFFFFF);
        }

        int sel = (g_opt_root_sel == 3);
        void *btn_tex = sel ? g_pOptBtnSelTex : g_pOptBtnUnselTex;
        if (btn_tex) {
            draw_textured_quad(dev, btn_tex,
                               130.0f * sx - 0.5f, 325.0f * sy - 0.5f,
                               630.0f * sx - 0.5f, 379.0f * sy - 0.5f,
                               0xFFFFFFFF);
        } else {
            float x1 = 138.0f * sx, x2 = 585.0f * sx;
            float y1 = 329.0f * sy, y2 = 375.0f * sy;
            DWORD bg = sel ? 0xFFA115E7 : 0xFFE4E6E4;
            DWORD border = sel ? 0xFFB217FF : 0xFF737573;
            DWORD txt_col = sel ? 0xFFFFFFFF : 0xFF7A7C7E;

            draw_screen_quad(dev, x1, y1, x2, y2, bg);
            draw_screen_quad(dev, x1, y1, x2, y1 + 1.0f * sy, border);
            draw_screen_quad(dev, x1, y2 - 1.0f * sy, x2, y2, border);

            if (g_pFontTitle && g_pSprite) {
                void **svtbl = *(void ***)g_pSprite;
                typedef HRESULT (__stdcall *SpriteBegin_t)(void *, DWORD);
                typedef HRESULT (__stdcall *SpriteEnd_t)(void *);
                SpriteBegin_t sp_begin = (SpriteBegin_t)svtbl[8];
                SpriteEnd_t sp_end = (SpriteEnd_t)svtbl[11];
                if (sp_begin && sp_begin(g_pSprite, 0x10) >= 0) {
                    RECT r = { (LONG)(x1 + 30.0f * sx), (LONG)y1, (LONG)(x2 - 30.0f * sx), (LONG)y2 };
                    draw_font_text(g_pFontTitle, "GRAFICOS HD Y LEGENDS", &r, txt_col, 1);
                    if (sp_end) sp_end(g_pSprite);
                }
            }
        }

        end_overlay_state(dev);
        ensure_d3d9_device_hooks(dev);
        return;
    }

    if (g_menu_saved_banner_timer > 0) g_menu_saved_banner_timer--;

    // Mode B: Native-styled Left-Column Settings ("OPCIONES DE JUEGO" look)
    int native_style = (g_opt_legends_sub != 0);
    if (native_style) {
        // Sleek VT4 frosted silver background + right ring halo + Nano Banana Crest + bottom Elegir/Atras bar
        draw_screen_quad(dev, 0.0f, 0.0f, (float)g_cfg_width, (float)g_cfg_height, 0xFFEBEDF2);
        draw_screen_quad(dev, 600.0f * sx, 0.0f, (float)g_cfg_width, (float)g_cfg_height, 0xFFE2E4EA);
        draw_screen_quad(dev, 600.0f * sx, 0.0f, 610.0f * sx, (float)g_cfg_height, 0xFF8416DE);
        draw_screen_quad(dev, 0.0f, 656.0f * sy, (float)g_cfg_width, (float)g_cfg_height, 0xFFE0E2E8);
        draw_screen_quad(dev, 0.0f, 656.0f * sy, (float)g_cfg_width, 658.0f * sy, 0xFF9E9FA6);
        if (g_pCrestTex) {
            float crest_s = (sx < sy) ? sx : sy;
            float cx = 935.0f * sx, cy = 296.0f * sy, rad = 172.0f * crest_s;
            draw_textured_quad(dev, g_pCrestTex, cx - rad, cy - rad, cx + rad, cy + rad, 0xFFFFFFFF);
        }
    }

    float col_x1 = native_style ? (120.0f * sx) : (((float)g_cfg_width - 540.0f) * 0.5f);
    float col_x2 = native_style ? (575.0f * sx) : (col_x1 + 540.0f);
    float row_start_y = native_style ? (86.0f * sy) : (((float)g_cfg_height - 600.0f) * 0.5f + 42.0f);
    float row_pitch = 34.5f * sy;

    if (!native_style) {
        draw_screen_quad(dev, col_x1 - 18.0f * sx, row_start_y - 54.0f * sy,
                         col_x2 + 18.0f * sx, row_start_y + NUM_SETTINGS_ITEMS * row_pitch + 32.0f * sy, 0xEBEDF0F5);
        draw_screen_quad(dev, col_x1 - 18.0f * sx, row_start_y - 54.0f * sy,
                         col_x2 + 18.0f * sx, row_start_y - 51.0f * sy, 0xFF8416DE);
    }

    const char *item_labels[NUM_SETTINGS_ITEMS] = {
        "RESOLUCION",
        "MODO DE PANTALLA",
        "ANTI-ALIASING (MSAA)",
        "SINCRONIZACION (VSYNC)",
        "FILTRADO ANISOTROPICO",
        "BLOOM Y BORROSIDAD (EXTRA-6)",
        "MODO LIVE",
        "CAMARA TV CLASICA (VT2)",
        "VELOCIDAD DE FISICA",
        "REGLAS EXHIBICION",
        "MULTIVERSO ARCADE (FASE 3)",
        "ARMA ARCADE (EE-3)",
        "HUD TV RETRANSMISION [F7]",
        "FISICAS PRO DE BOLA",
        "MANDO XBOX TACTIL (ANDROID)",
        "GUARDAR Y APLICAR CAMBIOS"
    };

    const char *item_hints[NUM_SETTINGS_ITEMS] = {
        "Resolucion interna 3D (HD, Steam Deck 16:10, 4:3 Arcade, QHD, 4K)",
        "Ventana sin bordes o Pantalla Completa",
        "Suavizado 3D nativo de bordes (MSAA)",
        "Desactivar VSync libera latencia y framerate en Present",
        "Nitidez de pistas y texturas en angulo",
        "Elimina o suaviza el Bloom/Glare y blur DOF de SEGA",
        "Muestra u oculta el acceso online GFWL LIVE",
        "Fija camara TV estilo VT2 sin zooms de Super Golpe",
        "Ajusta el ritmo Arcade VT2 (1.20x/1.35x) o Pro",
        "Partidos Exhibicion: 1/3/5 Sets de 6 Juegos y Tie-Break",
        "Easter Eggs: Batalla Hielo/Barro (EE-2) y Super Golpes 300% (EE-4)",
        "Arma 3D en mano: Raqueta Madera 70s, Sarten Metalica o Baguette",
        "Overlay TV moderno en partido: Torneo, radar km/h y rally ([F7])",
        "Ajusta la gravedad y velocidad de bola para peloteos menos flotantes",
        "Mando Xbox tactil interactivo en pantalla para Android/Wine ([F6])",
        "Guarda vt4_settings.ini y aplica los ajustes ahora"
    };

    for (int i = 0; i < NUM_SETTINGS_ITEMS; i++) {
        float y0 = row_start_y + (float)i * row_pitch;
        int is_sel = (i == g_menu_selection);
        if (i == NUM_SETTINGS_ITEMS - 1) {
            float by1 = y0 + 2.0f * sy;
            float by2 = y0 + 28.0f * sy;
            DWORD bg = is_sel ? 0xF2129850 : 0xEA2B5A40;
            DWORD bd = is_sel ? 0xFF40FF98 : 0xFF559070;
            draw_screen_quad(dev, col_x1, by1, col_x2, by2, bg);
            draw_screen_quad(dev, col_x1, by1, col_x2, by1 + 1.5f * sy, bd);
            draw_screen_quad(dev, col_x1, by2 - 1.5f * sy, col_x2, by2, bd);
        } else {
            float top_y1 = y0;
            float top_y2 = y0 + 15.0f * sy;
            float bot_y1 = top_y2;
            float bot_y2 = y0 + 31.5f * sy;
            DWORD top_bg = is_sel ? 0xF28416DE : 0xFFF5F6F9;
            DWORD bot_bg = is_sel ? 0xF53B0660 : 0xFF5E6068;
            DWORD div_ln = is_sel ? 0xFFD098FF : 0xFF989AA2;
            draw_screen_quad(dev, col_x1, top_y1, col_x2, top_y2, top_bg);
            draw_screen_quad(dev, col_x1, bot_y1, col_x2, bot_y2, bot_bg);
            draw_screen_quad(dev, col_x1, top_y1, col_x2, top_y1 + 1.0f, div_ln);
            draw_screen_quad(dev, col_x1 + 14.0f * sx, top_y1 + 4.5f * sy,
                             col_x1 + 22.0f * sx, top_y1 + 10.5f * sy,
                             is_sel ? 0xFFFFFFFF : 0xFF7A7C84);
        }
    }

    if (g_pFont && g_pFontTitle && g_pSprite) {
        void **svtbl = *(void ***)g_pSprite;
        typedef HRESULT (__stdcall *SpriteBegin_t)(void *, DWORD);
        typedef HRESULT (__stdcall *SpriteEnd_t)(void *);
        SpriteBegin_t sp_begin = (SpriteBegin_t)svtbl[8];
        SpriteEnd_t sp_end = (SpriteEnd_t)svtbl[11];
        HRESULT hr_sb = sp_begin ? sp_begin(g_pSprite, 0x10) : -1;

        RECT r;
        r.left = (LONG)(col_x1 + 24.0f * sx);
        r.top = (LONG)(row_start_y - 36.0f * sy);
        r.right = (LONG)(col_x2 + 20.0f * sx);
        r.bottom = (LONG)(row_start_y - 4.0f * sy);
        draw_font_text(g_pFontTitle, "GRAFICOS HD Y LEGENDS", &r, 0xFF5C5E66, 0);

        char val_buf[128];
        for (int i = 0; i < NUM_SETTINGS_ITEMS; i++) {
            float y0 = row_start_y + (float)i * row_pitch;
            int is_sel = (i == g_menu_selection);
            if (i == NUM_SETTINGS_ITEMS - 1) {
                r.left = (LONG)(col_x1 + 10.0f * sx);
                r.top = (LONG)(y0 + 2.0f * sy);
                r.right = (LONG)(col_x2 - 10.0f * sx);
                r.bottom = (LONG)(y0 + 28.0f * sy);
                draw_font_text(g_pFontTitle, item_labels[i], &r, 0xFFFFFFFF, 1);
            } else {
                DWORD lbl_col = is_sel ? 0xFFFFFFFF : 0xFF60626C;
                DWORD val_col = is_sel ? 0xFFFFFFFF : 0xFFEAEAF0;

                r.left = (LONG)(col_x1 + 30.0f * sx);
                r.top = (LONG)y0;
                r.right = (LONG)(col_x2 - 12.0f * sx);
                r.bottom = (LONG)(y0 + 15.0f * sy);
                draw_font_text(g_pFont, item_labels[i], &r, lbl_col, 0);

                switch (i) {
                    case 0: snprintf(val_buf, sizeof(val_buf), "< %s >", s_res_choices[s_idx_res].desc); break;
                    case 1: snprintf(val_buf, sizeof(val_buf), "< %s >", s_windowed_choices[s_idx_win]); break;
                    case 2: snprintf(val_buf, sizeof(val_buf), "< %s >", s_msaa_choices[s_idx_msaa].desc); break;
                    case 3: snprintf(val_buf, sizeof(val_buf), "< %s >", s_vsync_choices[s_idx_vsync]); break;
                    case 4: snprintf(val_buf, sizeof(val_buf), "< %s >", s_aniso_choices[s_idx_aniso].desc); break;
                    case 5: snprintf(val_buf, sizeof(val_buf), "< %s >", s_postfx_choices[s_idx_postfx]); break;
                    case 6: snprintf(val_buf, sizeof(val_buf), "< %s >", s_live_choices[s_idx_live]); break;
                    case 7: snprintf(val_buf, sizeof(val_buf), "< %s >", s_tvcam_choices[s_idx_tvcam]); break;
                    case 8: snprintf(val_buf, sizeof(val_buf), "< %s >", s_speed_choices[s_idx_speed].desc); break;
                    case 9: snprintf(val_buf, sizeof(val_buf), "< %s >", s_exb_rules_choices[s_idx_exbrules].desc); break;
                    case 10: snprintf(val_buf, sizeof(val_buf), "< %s >", s_multiverse_choices[s_idx_multiverse]); break;
                    case 11: snprintf(val_buf, sizeof(val_buf), "< %s >", s_weapon_choices[s_idx_weapon]); break;
                    case 12: snprintf(val_buf, sizeof(val_buf), "< %s >", s_bhud_choices[s_idx_bhud]); break;
                    case 13: snprintf(val_buf, sizeof(val_buf), "< %s >", s_prophys_choices[s_idx_prophys]); break;
                    case 14: snprintf(val_buf, sizeof(val_buf), "< %s >", s_touchhud_choices[s_idx_touchhud]); break;
                }
                r.left = (LONG)(col_x1 + 12.0f * sx);
                r.top = (LONG)(y0 + 15.0f * sy);
                r.right = (LONG)(col_x2 - 12.0f * sx);
                r.bottom = (LONG)(y0 + 31.5f * sy);
                draw_font_text(g_pFont, val_buf, &r, val_col, 1);
            }
        }

        // Info pill & footer inside native_style
        if (native_style && g_menu_selection >= 0 && g_menu_selection < NUM_SETTINGS_ITEMS) {
            float hx1 = 640.0f * sx, hx2 = 1230.0f * sx;
            float hy1 = 550.0f * sy, hy2 = 592.0f * sy;
            draw_screen_quad(dev, hx1, hy1, hx2, hy2, 0xFFD8DBE4);
            r.left = (LONG)(hx1 + 12.0f * sx);
            r.top = (LONG)hy1;
            r.right = (LONG)(hx2 - 12.0f * sx);
            r.bottom = (LONG)hy2;
            draw_font_text(g_pFont, item_hints[g_menu_selection], &r, 0xFF383A44, 1);

            r.left = (LONG)(640.0f * sx);
            r.top = (LONG)(662.0f * sy);
            r.right = (LONG)(1230.0f * sx);
            r.bottom = (LONG)(710.0f * sy);
            draw_font_text(g_pFontTitle, "Elegir [Enter]       Cambiar [< / >]       Atras [ESC]", &r, 0xFF40424A, 1);
        }

        // Saved feedback pill cleanly positioned without blocking menu bars
        if (g_menu_saved_banner_timer > 0) {
            float bx1 = native_style ? (640.0f * sx) : col_x1;
            float bx2 = native_style ? (1230.0f * sx) : col_x2;
            float by1 = native_style ? (496.0f * sy) : (row_start_y + NUM_SETTINGS_ITEMS * row_pitch + 8.0f * sy);
            float by2 = by1 + 42.0f * sy;
            draw_screen_quad(dev, bx1, by1, bx2, by2, 0xF0105832);
            draw_screen_quad(dev, bx1, by1, bx2, by1 + 2.0f, 0xFF00FF88);
            draw_screen_quad(dev, bx1, by2 - 2.0f, bx2, by2, 0xFF00FF88);
            r.left = (LONG)bx1;
            r.top = (LONG)by1;
            r.right = (LONG)bx2;
            r.bottom = (LONG)by2;
            draw_font_text(g_pFontTitle, "AJUSTES GUARDADOS Y APLICADOS", &r, 0xFF80FFB8, 1);
        }

        HRESULT hr_se = sp_end ? sp_end(g_pSprite) : -1;
        static int s_hud_draw_logged = 0;
        if (!s_hud_draw_logged) {
            s_hud_draw_logged = 1;
            log_msg("[VT4-Mod] render_settings_hud first draw complete: native=%d crest=%p sb=%p sp_begin=0x%08lx sp_end=0x%08lx",
                    native_style, g_pCrestTex, g_pOverlaySB, (unsigned long)hr_sb, (unsigned long)hr_se);
        }
    }

    end_overlay_state(dev);
    ensure_d3d9_device_hooks(dev);
}

#include "touch_gamepad.h"

static uint8_t g_keys_down[256] = {0};
static uint32_t g_btn_hold[256] = {0};
static uint32_t g_nav_hold[6] = {0};
static int g_netplay_menu_visible = 0;

static inline int is_key_down(int vk) {
    if (vk < 0 || vk >= 256) return 0;
    if (g_keys_down[vk]) return 1;
    static uint32_t s_fg_frame = 0xFFFFFFFFu;
    static int      s_fg_ok = 1;
    static uint32_t s_vk_frame[256];
    static uint8_t  s_vk_val[256];
    uint32_t cur_f = (g_logic_ticks ? g_logic_ticks : g_present_calls) + 1u;
    if (g_game_hwnd) {
        if (s_fg_frame != cur_f) {
            HWND fg = GetForegroundWindow();
            s_fg_ok = (!fg || fg == g_game_hwnd) ? 1 : 0;
            s_fg_frame = cur_f;
        }
        if (!s_fg_ok) return 0;
    }
    if (s_vk_frame[vk] != cur_f) {
        s_vk_val[vk] = ((GetAsyncKeyState(vk) & 0x8000) != 0) ? 1 : 0;
        s_vk_frame[vk] = cur_f;
    }
    return (int)s_vk_val[vk];
}

// ----------------------------------------------------------------------------
// Dynamic XInput Controller Support + Netplay Interactive P2P Lobby Menu State
// ----------------------------------------------------------------------------
typedef struct {
    WORD  wButtons;
    BYTE  bLeftTrigger;
    BYTE  bRightTrigger;
    SHORT sThumbLX;
    SHORT sThumbLY;
    SHORT sThumbRX;
    SHORT sThumbRY;
} VT4_XINPUT_GAMEPAD;

typedef struct {
    DWORD              dwPacketNumber;
    VT4_XINPUT_GAMEPAD Gamepad;
} VT4_XINPUT_STATE;

typedef DWORD (WINAPI *VT4_XInputGetState_t)(DWORD dwUserIndex, VT4_XINPUT_STATE *pState);
typedef UINT  (WINAPI *VT4_joyGetPosEx_t)(UINT uJoyID, void *pji);

typedef struct {
    DWORD dwSize;
    DWORD dwFlags;
    DWORD dwXpos;
    DWORD dwYpos;
    DWORD dwZpos;
    DWORD dwRpos;
    DWORD dwUpos;
    DWORD dwVpos;
    DWORD dwButtons;
    DWORD dwButtonNumber;
    DWORD dwPOV;
    DWORD dwReserved1;
    DWORD dwReserved2;
} VT4_JOYINFOEX;

static VT4_XInputGetState_t g_xinput_fns[3] = { NULL, NULL, NULL };
static VT4_joyGetPosEx_t    g_joy_get_pos_ex = NULL;
static int g_xinput_searched = 0;
static int g_xinput_pad_tbl_inited = 0;
static int g_winmm_pad_logged = 0;
static int g_real_gamepad_active = 0;

static void xinput_read_xi_state(const VT4_XINPUT_STATE *st, float *ax, float *ay, WORD *btns) {
    WORD b = st->Gamepad.wButtons;
    float x = 0.0f, y = 0.0f;
    const SHORT dz = 7849;
    if (st->Gamepad.sThumbLX > dz || st->Gamepad.sThumbLX < -dz) {
        x = (float)st->Gamepad.sThumbLX / 32767.0f;
    }
    if (st->Gamepad.sThumbLY > dz || st->Gamepad.sThumbLY < -dz) {
        // XInput +Y is Up; VT4 AnalogY -1.0 is Up
        y = -(float)st->Gamepad.sThumbLY / 32767.0f;
    }
    if (b & 0x0004) x = -1.0f;
    else if (b & 0x0008) x = 1.0f;
    if (b & 0x0001) y = -1.0f;
    else if (b & 0x0002) y = 1.0f;
    *ax = x; *ay = y; *btns = b;
}

static void xinput_read_joy_state(const VT4_JOYINFOEX *ji, float *ax, float *ay, WORD *btns) {
    float x = 0.0f, y = 0.0f;
    WORD b = 0;
    int dx = (int)ji->dwXpos - 32767;
    int dy = (int)ji->dwYpos - 32767;
    const int dz = 8000;
    if (dx > dz || dx < -dz) {
        x = (float)dx / 32767.0f;
        if (x < -1.0f) x = -1.0f;
        if (x >  1.0f) x =  1.0f;
    }
    if (dy > dz || dy < -dz) {
        y = (float)dy / 32767.0f;
        if (y < -1.0f) y = -1.0f;
        if (y >  1.0f) y =  1.0f;
    }
    if (ji->dwPOV <= 35999u) {
        DWORD pov = ji->dwPOV;
        if (pov <= 4500u || pov >= 31500u)          { b |= 0x0001; y = -1.0f; }
        if (pov >= 13500u && pov <= 22500u)         { b |= 0x0002; y =  1.0f; }
        if (pov >= 22500u && pov <= 31500u)         { b |= 0x0004; x = -1.0f; }
        if (pov >= 4500u && pov <= 13500u)          { b |= 0x0008; x =  1.0f; }
    }
    DWORD jb = ji->dwButtons;
    if (jb & 0x01u) b |= 0x1000; /* A */
    if (jb & 0x02u) b |= 0x2000; /* B */
    if (jb & 0x04u) b |= 0x4000; /* X */
    if (jb & 0x08u) b |= 0x8000; /* Y */
    if (jb & 0x10u) b |= 0x0100; /* LB */
    if (jb & 0x20u) b |= 0x0200; /* RB */
    if (jb & 0x40u) b |= 0x0020; /* Back */
    if (jb & 0x80u) b |= 0x0010; /* Start */
    *ax = x; *ay = y; *btns = b;
}

static int xinput_get_p1(float *out_ax, float *out_ay, WORD *out_btns) {
    static uint32_t s_xi_tick = 0xFFFFFFFFu;
    static int      s_xi_ok = 0;
    static float    s_xi_ax = 0.0f, s_xi_ay = 0.0f;
    static WORD     s_xi_btns = 0;
    static int      s_last_xi_dll = -1;
    static DWORD    s_last_xi_user = 0;
    static int      s_last_joy_id = -1;

    if (!g_xinput_searched) {
        g_xinput_searched = 1;
        static const char *s_dlls[3] = { "xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll" };
        for (int i = 0; i < 3; i++) {
            HMODULE h = GetModuleHandleA(s_dlls[i]);
            if (!h) h = LoadLibraryA(s_dlls[i]);
            if (h) {
                g_xinput_fns[i] = (VT4_XInputGetState_t)GetProcAddress(h, "XInputGetState");
                if (g_xinput_fns[i]) {
                    log_msg("[VT4-Mod] Dynamic XInput loaded: %s", s_dlls[i]);
                }
            }
        }
        HMODULE hWinmm = GetModuleHandleA("winmm.dll");
        if (!hWinmm) hWinmm = LoadLibraryA("winmm.dll");
        if (hWinmm) {
            g_joy_get_pos_ex = (VT4_joyGetPosEx_t)GetProcAddress(hWinmm, "joyGetPosEx");
            if (g_joy_get_pos_ex) {
                log_msg("[VT4-Mod] Dynamic WinMM joyGetPosEx fallback ready");
            }
        }
    }

    uint32_t cur_t = (g_logic_ticks ? g_logic_ticks : g_present_calls) + 1u;
    if (s_xi_tick != cur_t) {
        s_xi_tick = cur_t;
        s_xi_ok = 0;
        s_xi_ax = 0.0f;
        s_xi_ay = 0.0f;
        s_xi_btns = 0;

        VT4_XINPUT_STATE st;
        if (s_last_xi_dll >= 0 && g_xinput_fns[s_last_xi_dll]) {
            memset(&st, 0, sizeof(st));
            if (g_xinput_fns[s_last_xi_dll](s_last_xi_user, &st) == 0) {
                s_xi_ok = 1;
                xinput_read_xi_state(&st, &s_xi_ax, &s_xi_ay, &s_xi_btns);
            } else {
                s_last_xi_dll = -1;
            }
        }
        if (!s_xi_ok) {
            for (int d = 0; d < 3 && !s_xi_ok; d++) {
                if (!g_xinput_fns[d]) continue;
                for (DWORD u = 0; u < 4; u++) {
                    memset(&st, 0, sizeof(st));
                    if (g_xinput_fns[d](u, &st) == 0) {
                        s_xi_ok = 1;
                        s_last_xi_dll = d;
                        s_last_xi_user = u;
                        xinput_read_xi_state(&st, &s_xi_ax, &s_xi_ay, &s_xi_btns);
                        break;
                    }
                }
            }
        }
        if (!s_xi_ok && g_joy_get_pos_ex) {
            VT4_JOYINFOEX ji;
            int order[2] = { (s_last_joy_id == 1) ? 1 : 0, (s_last_joy_id == 1) ? 0 : 1 };
            for (int k = 0; k < 2; k++) {
                UINT jid = (UINT)order[k];
                memset(&ji, 0, sizeof(ji));
                ji.dwSize = sizeof(ji);
                ji.dwFlags = 0xFFu;
                if (g_joy_get_pos_ex(jid, &ji) == 0) {
                    s_xi_ok = 1;
                    s_last_joy_id = (int)jid;
                    xinput_read_joy_state(&ji, &s_xi_ax, &s_xi_ay, &s_xi_btns);
                    if (!g_winmm_pad_logged) {
                        g_winmm_pad_logged = 1;
                        log_msg("[VT4-Mod] WinMM/DirectInput P1 joystick active (id=%u)", jid);
                    }
                    break;
                }
            }
        }
        if (s_xi_ok) {
            g_real_gamepad_active = 1;
            // Ensure native VT4 gamepad slot 0 is enabled if no Launcher config.txt ran
            if (!g_xinput_pad_tbl_inited) {
                g_xinput_pad_tbl_inited = 1;
                *(uint8_t *)0x00835ee8 = 1;
                uint32_t *pad_p1 = (uint32_t *)0x00820f38;
                if (pad_p1[13] == 0xFFFFFFFFu) {
                    memcpy(pad_p1, (const void *)0x00820db0, 21 * sizeof(uint32_t));
                }
                log_msg("[VT4-Mod] Gamepad P1 controller detected (xi=%d.%lu joy=%d) -> enabled native gamepad slot 0",
                        s_last_xi_dll, (unsigned long)s_last_xi_user, s_last_joy_id);
            }
            touch_gamepad_notify_real_xinput(s_xi_ax, s_xi_ay, s_xi_btns, g_cfg_touch_hud);
        }
    }
    float t_ax = 0.0f, t_ay = 0.0f;
    WORD  t_btns = 0;
    int   t_ok = touch_gamepad_get_p1(&t_ax, &t_ay, &t_btns);

    if (out_ax) *out_ax = (t_ok && (fabsf(t_ax) > 0.05f || fabsf(t_ay) > 0.05f)) ? t_ax : s_xi_ax;
    if (out_ay) *out_ay = (t_ok && (fabsf(t_ax) > 0.05f || fabsf(t_ay) > 0.05f)) ? t_ay : s_xi_ay;
    if (out_btns) *out_btns = (WORD)(s_xi_btns | t_btns);
    return (s_xi_ok || t_ok) ? 1 : 0;
}

#define NUM_NETPLAY_ITEMS 7
static int      s_np_sel = 0;
static uint32_t s_np_mode = 0;
static char     s_np_ip[64] = "127.0.0.1";
static uint32_t s_np_port = 7777;
static uint32_t s_np_delay = 3;
static char     s_np_local_ip[64] = "127.0.0.1";
static char     s_np_feedback[128] = "";
static int      s_np_feedback_timer = 0;
static uint32_t s_np_feedback_col = 0xFF14783C;

static void netplay_ui_sync_from_live(void) {
    uint16_t p16 = 7777;
    netplay_get_config(&s_np_mode, s_np_ip, sizeof(s_np_ip), &p16, &s_np_delay);
    s_np_port = (uint32_t)p16;
    netplay_get_local_ip(s_np_local_ip, sizeof(s_np_local_ip));
    s_np_sel = 0;
}

static void netplay_ui_build_ini_path(char *out, size_t cap) {
    if (g_game_dir[0]) {
        snprintf(out, cap, "%s\\vt4_settings.ini", g_game_dir);
    } else {
        GetModuleFileNameA(NULL, out, (DWORD)cap);
        char *sl = strrchr(out, '\\');
        if (sl) *sl = '\0';
        strncat(out, "\\vt4_settings.ini", cap - strlen(out) - 1);
    }
}

static void close_netplay_menu(void) {
    g_netplay_menu_visible = 0;
    g_menu_close_cooldown_frame = g_present_calls;
}

static int handle_netplay_menu_input(int vk) {
    if (!g_netplay_menu_visible) return 0;

    if (s_np_sel == 2) {
        char ch = 0;
        if (vk >= '0' && vk <= '9') ch = (char)vk;
        else if (vk >= VK_NUMPAD0 && vk <= VK_NUMPAD9) ch = (char)('0' + (vk - VK_NUMPAD0));
        else if (vk == VK_OEM_PERIOD || vk == VK_DECIMAL || vk == '.') ch = '.';
        if (ch) {
            size_t len = strlen(s_np_ip);
            if (len + 1 < 40) {
                s_np_ip[len] = ch;
                s_np_ip[len + 1] = '\0';
                play_vt4_menu_se(4);
            }
            return 1;
        }
        if (vk == VK_BACK) {
            size_t len = strlen(s_np_ip);
            if (len > 0) {
                s_np_ip[len - 1] = '\0';
                play_vt4_menu_se(4);
            }
            return 1;
        }
        if (vk == VK_DELETE) {
            s_np_ip[0] = '\0';
            play_vt4_menu_se(4);
            return 1;
        }
    } else if (s_np_sel == 3) {
        int digit = -1;
        if (vk >= '0' && vk <= '9') digit = vk - '0';
        else if (vk >= VK_NUMPAD0 && vk <= VK_NUMPAD9) digit = vk - VK_NUMPAD0;
        if (digit >= 0) {
            uint32_t np = s_np_port * 10u + (uint32_t)digit;
            if (np > 65535u) np = (uint32_t)digit;
            s_np_port = np;
            play_vt4_menu_se(4);
            return 1;
        }
        if (vk == VK_BACK) {
            s_np_port /= 10u;
            play_vt4_menu_se(4);
            return 1;
        }
    }

    switch (vk) {
        case VK_UP:
        case 'W':
            s_np_sel = (s_np_sel - 1 + NUM_NETPLAY_ITEMS) % NUM_NETPLAY_ITEMS;
            play_vt4_menu_se(3);
            return 1;
        case VK_DOWN:
        case 'S':
            s_np_sel = (s_np_sel + 1) % NUM_NETPLAY_ITEMS;
            play_vt4_menu_se(3);
            return 1;
        case VK_LEFT:
        case 'A':
            if (s_np_sel == 0) s_np_mode = (s_np_mode + 2u) % 3u;
            else if (s_np_sel == 3) s_np_port = (s_np_port > 1024u) ? (s_np_port - 1u) : 65535u;
            else if (s_np_sel == 4) s_np_delay = (s_np_delay > 1u) ? (s_np_delay - 1u) : 12u;
            play_vt4_menu_se(4);
            return 1;
        case VK_RIGHT:
        case 'D':
            if (s_np_sel == 0) s_np_mode = (s_np_mode + 1u) % 3u;
            else if (s_np_sel == 3) s_np_port = (s_np_port < 65535u) ? (s_np_port + 1u) : 1024u;
            else if (s_np_sel == 4) s_np_delay = (s_np_delay < 12u) ? (s_np_delay + 1u) : 1u;
            play_vt4_menu_se(4);
            return 1;
        case VK_RETURN:
        case VK_SPACE: {
            char ini_path[MAX_PATH];
            netplay_ui_build_ini_path(ini_path, sizeof(ini_path));
            if (s_np_sel == 1) {
                char found_ip[64] = {0};
                uint16_t found_port = (uint16_t)(s_np_port ? s_np_port : 7777u);
                uint32_t found_delay = s_np_delay;
                if (netplay_lan_discover(found_port, found_ip, sizeof(found_ip), &found_port, &found_delay, 320u)) {
                    strncpy(s_np_ip, found_ip, sizeof(s_np_ip) - 1);
                    s_np_ip[sizeof(s_np_ip) - 1] = '\0';
                    s_np_mode = 2u;
                    s_np_port = (uint32_t)found_port;
                    s_np_delay = found_delay;
                    snprintf(s_np_feedback, sizeof(s_np_feedback),
                             "SALA LAN ENCONTRADA: %s:%u (PULSA APLICAR)", s_np_ip, s_np_port);
                    s_np_feedback_col = 0xFF14783C;
                    play_vt4_menu_se(5);
                } else {
                    snprintf(s_np_feedback, sizeof(s_np_feedback),
                             "SIN SALAS LAN EN :%u - CREA HOST EN EL OTRO EQUIPO", (unsigned)found_port);
                    s_np_feedback_col = 0xFFB06808;
                    play_vt4_menu_se(4);
                }
                s_np_feedback_timer = 260;
                return 1;
            }
            if (s_np_sel == 6) {
                s_np_mode = 0;
                netplay_reconfigure_live(0, s_np_ip, (uint16_t)(s_np_port ? s_np_port : 7777u), s_np_delay, ini_path);
                play_vt4_menu_se(6);
                close_netplay_menu();
                return 1;
            }
            if (s_np_sel == 5 || s_np_sel < 5) {
                if (s_np_mode == 0 && s_np_sel == 5) {
                    s_np_mode = 1; // Pressing CONECTAR while OFF defaults conveniently to HOST P1
                }
                if (s_np_port == 0 || s_np_port > 65535u) s_np_port = 7777u;
                if (!s_np_ip[0]) strcpy(s_np_ip, "127.0.0.1");
                int ok = netplay_reconfigure_live(s_np_mode, s_np_ip, (uint16_t)s_np_port, s_np_delay, ini_path);
                if (ok) {
                    if (s_np_mode == 0) {
                        snprintf(s_np_feedback, sizeof(s_np_feedback), "MODO LOCAL GUARDADO");
                    } else if (s_np_mode == 1) {
                        snprintf(s_np_feedback, sizeof(s_np_feedback), "SALA ABIERTA EN :%u - PULSA ESC Y ENTRA EN EXHIBICION", s_np_port);
                    } else {
                        snprintf(s_np_feedback, sizeof(s_np_feedback), "BUSCANDO %s:%u - PULSA ESC Y ENTRA EN EXHIBICION", s_np_ip, s_np_port);
                    }
                    s_np_feedback_col = 0xFF14783C;
                } else {
                    snprintf(s_np_feedback, sizeof(s_np_feedback), "ERROR AL ABRIR UDP :%u / IP '%s'", s_np_port, s_np_ip);
                    s_np_feedback_col = 0xFFC02830;
                }
                s_np_feedback_timer = 240;
                play_vt4_menu_se(5);
                return 1;
            }
            return 1;
        }
        case VK_ESCAPE:
        case VK_BACK:
            close_netplay_menu();
            play_vt4_menu_se(6);
            log_msg("[VT4-Mod] Netplay P2P UI closed cleanly by ESC/Back");
            return 1;
    }
    return 0;
}

static void __cdecl hk_MainMenu_OpenNetplayUI(void *dialog_cfg) {
    (void)dialog_cfg;
    g_menu_visible = 0;
    netplay_ui_sync_from_live();
    g_netplay_menu_visible = 1;
    g_mod_menu_open_frame = g_present_calls;
    play_vt4_menu_se(5);
    log_msg("[VT4-Mod] Opened P2P Netplay UI from Main Menu 'EN LINEA' (local_ip=%s)", s_np_local_ip);
}

#include "multiverse_modes.h"

// ----------------------------------------------------------------------------
// Roster Pagination & Character Selection Grid
// ----------------------------------------------------------------------------
#define NUM_ROSTER_PAGES 4
#define MAX_ROSTER_PLAYERS 84
#define NUM_EXTRA_PLAYERS 46

// Canonical mapping: grid slot [0..23] -> vanilla .fraw character card/label index
static const uint8_t g_fraw_cell_char_id[24] = {
     0,  2,  3,   // Row 0
     1,  5,  4,   // Row 1
     6,  7, 10,   // Row 2
     8,  9, 13,   // Row 3
    15, 16, 22,   // Row 4
    17, 19, 18,   // Row 5
    23, 21, 20,   // Row 6
    26, 26, 27    // Row 7: CARGAR (26), ACTUAL (26), ALEATORIO (27)
};

// Page 0: Era Actual & Next-Gen (2018 - 2026: All 21 cards unique, incl. Mirra Andreeva 82!)
static const uint8_t g_roster_page_tour[24] = {
     0,  1,  2,   // Row 0: Federer(0), Nadal(1), Djokovic(2)
    26, 27, 39,   // Row 1: Alcaraz(26), Sinner(27), Medvedev(39)
    40, 41, 60,   // Row 2: Zverev(40), Tsitsipas(41), Rublev(60)
    61, 62, 59,   // Row 3: Ruud(61), Fritz(62), Shelton(59)
    43, 34, 35,   // Row 4: Kyrgios(43), Swiatek(34), Sabalenka(35)
    63, 64, 65,   // Row 5: Gauff(63), Rybakina(64), Badosa(65)
    82, 58, 66,   // Row 6: Mirra Andreeva(82), Muguruza(58), Halep(66)
    26, 26, 27    // Row 7: CARGAR (26), ACTUAL (26), ALEATORIO (27)
};

// Page 1: Era Dorada (2000s - 2010s: All 21 cards unique)
static const uint8_t g_roster_page_legends[24] = {
     3,  4, 38,   // Row 0: Murray(3), Del Potro(4), Wawrinka(38)
     5, 44, 45,   // Row 1: Roddick(5), Hewitt(44), Safin(45)
    47, 48, 49,   // Row 2: Ferrero(47), Moya(48), Ferrer(49)
    50, 67, 46,   // Row 3: Nalbandian(50), Coria(67), Tsonga(46)
     6, 68, 69,   // Row 4: Monfils(6), Gasquet(68), Nishikori(69)
     7, 10, 70,   // Row 5: Gonzalez(7), Haas(10), Soderling(70)
    71, 42, 33,   // Row 6: Berdych(71), Thiem(42), Serena(33)
    26, 26, 27    // Row 7: CARGAR (26), ACTUAL (26), ALEATORIO (27)
};

// Page 2: Leyendas 90s & WTA Dorada (All 21 cards unique)
static const uint8_t g_roster_page_legends2[24] = {
    28, 29, 13,   // Row 0: Sampras(28), Agassi(29), Courier(13)
    14, 11, 12,   // Row 1: Edberg(14), Becker(11), Rafter(12)
    54, 36, 72,   // Row 2: Ivanisevic(54), Kuerten(36), Chang(72)
    73, 74, 75,   // Row 3: Rios(73), Muster(74), Bruguera(75)
    76, 32, 56,   // Row 4: Corretja(76), Graf(32), Seles(56)
    57, 81, 79,   // Row 5: Henin(57), Clijsters(81), Arantxa(79)
    80, 18, 17,   // Row 6: Conchita(80), Venus(18), Sharapova(17)
    26, 26, 27    // Row 7: CARGAR (26), ACTUAL (26), ALEATORIO (27)
};

// Page 3: Pioneros 60s-80s & Clasicos VT4 (All 21 cards unique: 84/84 total!)
static const uint8_t g_roster_page_legends3[24] = {
    30, 31, 51,   // Row 0: Borg(30), McEnroe(31), Lendl(51)
    52, 53, 77,   // Row 1: Connors(52), Vilas(53), Wilander(77)
    78, 37, 55,   // Row 2: Laver(78), Navratilova(37), Evert(55)
    83, 22, 19,   // Row 3: Billie Jean King(83), Wozniacki(22), Kuznetsova(19)
    20, 21, 23,   // Row 4: Ivanovic(20), Chakvetadze(21), Robson(23)
     8,  9, 15,   // Row 5: Kohlschreiber(8), Seppi(9), King(15)
    16, 24, 25,   // Row 6: Duke(16), Tenniel/VTM(24), Virnie/VTF(25)
    26, 26, 27    // Row 7: CARGAR (26), ACTUAL (26), ALEATORIO (27)
};

static const uint8_t *g_roster_pages[NUM_ROSTER_PAGES] = {
    g_roster_page_tour,
    g_roster_page_legends,
    g_roster_page_legends2,
    g_roster_page_legends3
};

static const char *g_roster_page_titles[NUM_ROSTER_PAGES] = {
    "PAGINA 1/4: ERA ACTUAL & NEXT-GEN (2018-2026)",
    "PAGINA 2/4: ERA DORADA (2000s - 2010s)",
    "PAGINA 3/4: LEYENDAS 90s & WTA DORADA",
    "PAGINA 4/4: PIONEROS 60s-80s & CLASICOS VT4"
};

typedef struct {
    const char *code;
    const char *full_name;
    const char *last_first;
    const char *card_name;
    const char *first_name;
    const char *banner_name;
    const char *short_name;
    const char *ioc_code;
    const char *author;
    const char *height;
    const char *weight;
    int32_t flag;
    uint8_t man;
    uint8_t lefty;
    uint8_t bh2;
    uint8_t playstyle_proxy;
    uint8_t anim_proxy;
    uint8_t bone_proxy;
    uint8_t bio_proxy;
} ExtraPlayerDef;

static const ExtraPlayerDef g_extra_players[NUM_EXTRA_PLAYERS] = {
    { "WAW", "Stan Wawrinka",         "Wawrinka, Stan",        "Wawrinka",    "Stan",        "S. Wawrinka",    "S.WAWRINKA",    "SUI", "NG", "183", "81",  46, 1, 0, 0,  3,  0, 10,  0 }, // 38
    { "MED", "Daniil Medvedev",       "Medvedev, Daniil",      "Medvedev",    "Daniil",      "D. Medvedev",    "D.MEDVEDEV",    "RUS", "NG", "198", "83", 119, 1, 0, 1,  6,  2, 14,  2 }, // 39
    { "ZVE", "Alexander Zverev",      "Zverev, Alexander",     "Zverev",      "Alexander",   "A. Zverev",      "A.ZVEREV",      "GER", "NG", "198", "90",  16, 1, 0, 1,  5,  2,  4, 10 }, // 40
    { "TSI", "Stefanos Tsitsipas",    "Tsitsipas, Stefanos",   "Tsitsipas",   "Stefanos",    "S. Tsitsipas",   "S.TSITSIPAS",   "GRE", "NG", "193", "89",  19, 1, 0, 0,  0,  0,  1,  0 }, // 41
    { "THI", "Dominic Thiem",         "Thiem, Dominic",        "Thiem",       "Dominic",     "D. Thiem",       "D.THIEM",       "AUT", "NG", "185", "79",   3, 1, 0, 0,  4,  7, 10, 10 }, // 42
    { "KYR", "Nick Kyrgios",          "Kyrgios, Nick",         "Kyrgios",     "Nick",        "N. Kyrgios",     "N.KYRGIOS",     "AUS", "NG", "193", "85", 132, 1, 0, 1,  5,  5,  2,  6 }, // 43
    { "HEW", "Lleyton Hewitt",        "Hewitt, Lleyton",       "Hewitt",      "Lleyton",     "L. Hewitt",      "L.HEWITT",      "AUS", "LG", "178", "77", 132, 1, 0, 1,  6,  6, 13,  5 }, // 44
    { "SAF", "Marat Safin",           "Safin, Marat",          "Safin",       "Marat",       "M. Safin",       "M.SAFIN",       "RUS", "LG", "194", "88", 119, 1, 0, 1,  4,  2,  3, 11 }, // 45
    { "TSO", "Jo-Wilfried Tsonga",    "Tsonga, Jo-Wilfried",   "Tsonga",      "Jo-Wilfried", "J.-W. Tsonga",   "J.W.TSONGA",    "FRA", "LG", "188", "91",  15, 1, 0, 1,  4,  6,  2,  6 }, // 46
    { "FRR", "Juan Carlos Ferrero",   "Ferrero, Juan Carlos",  "Ferrero",     "Juan Carlos", "J.C. Ferrero",   "J.C.FERRERO",   "ESP", "LG", "183", "73",  44, 1, 0, 1,  1, 10, 10,  1 }, // 47
    { "MOY", "Carlos Moya",           "Moya, Carlos",          "Moya",        "Carlos",      "C. Moya",        "C.MOYA",        "ESP", "LG", "191", "86",  44, 1, 0, 1,  7, 13,  4,  1 }, // 48
    { "FER", "David Ferrer",          "Ferrer, David",         "Ferrer",      "David",       "D. Ferrer",      "D.FERRER",      "ESP", "LG", "175", "73",  44, 1, 0, 1,  1,  9,  0,  1 }, // 49
    { "NAL", "David Nalbandian",      "Nalbandian, David",     "Nalbandian",  "David",       "D. Nalbandian",  "D.NALBANDIAN",  "ARG", "LG", "180", "79",  74, 1, 0, 1,  9, 13,  8,  4 }, // 50
    { "LEN", "Ivan Lendl",            "Lendl, Ivan",           "Lendl",       "Ivan",        "I. Lendl",       "I.LENDL",       "CZE", "LG", "188", "79",  11, 1, 0, 0,  7,  0, 14,  0 }, // 51
    { "CON", "Jimmy Connors",         "Connors, Jimmy",        "Connors",     "Jimmy",       "J. Connors",     "J.CONNORS",     "USA", "LG", "178", "70",  73, 1, 1, 1,  2,  1,  7,  5 }, // 52
    { "VIL", "Guillermo Vilas",       "Vilas, Guillermo",      "Vilas",       "Guillermo",   "G. Vilas",       "G.VILAS",       "ARG", "LG", "180", "79",  74, 1, 1, 0,  1, 14,  1,  4 }, // 53
    { "IVN", "Goran Ivanisevic",      "Ivanisevic, Goran",     "Ivanisevic",  "Goran",       "G. Ivanisevic",  "G.IVANISEVIC",  "CRO", "LG", "193", "81",   9, 1, 1, 1,  5,  1,  4,  2 }, // 54
    { "EVE", "Chris Evert",           "Evert, Chris",          "Evert",       "Chris",       "C. Evert",       "C.EVERT",       "USA", "LG", "168", "57",  73, 0, 0, 1, 19, 19, 21, 18 }, // 55
    { "SEL", "Monica Seles",          "Seles, Monica",         "Seles",       "Monica",      "M. Seles",       "M.SELES",       "SRB", "LG", "178", "68",  41, 0, 1, 1, 17, 23, 19, 20 }, // 56
    { "HEN", "Justine Henin",         "Henin, Justine",        "Henin",       "Justine",     "J. Henin",       "J.HENIN",       "BEL", "LG", "167", "57",   6, 0, 0, 0, 22, 22, 20, 17 }, // 57
    { "MUG", "Garbine Muguruza",      "Muguruza, Garbine",     "Muguruza",    "Garbine",     "G. Muguruza",    "G.MUGURUZA",    "ESP", "NG", "182", "73",  44, 0, 0, 1, 17, 17, 23, 17 }, // 58
    { "SHE", "Ben Shelton",           "Shelton, Ben",          "Shelton",     "Ben",         "B. Shelton",     "B.SHELTON",     "USA", "NG", "193", "88",  73, 1, 1, 1,  5,  5,  6,  5 }, // 59
    { "RUB", "Andrey Rublev",         "Rublev, Andrey",        "Rublev",      "Andrey",      "A. Rublev",      "A.RUBLEV",      "RUS", "NG", "188", "75", 119, 1, 0, 1,  7,  2,  1,  2 }, // 60
    { "RUU", "Casper Ruud",           "Ruud, Casper",          "Ruud",        "Casper",      "C. Ruud",        "C.RUUD",        "NOR", "NG", "183", "81",  36, 1, 0, 1,  1, 13,  4, 14 }, // 61
    { "FRI", "Taylor Fritz",          "Fritz, Taylor",         "Fritz",       "Taylor",      "T. Fritz",       "T.FRITZ",       "USA", "NG", "196", "86",  73, 1, 0, 1,  5,  2,  0,  5 }, // 62
    { "GAU", "Coco Gauff",            "Gauff, Coco",           "Gauff",       "Coco",        "C. Gauff",       "C.GAUFF",       "USA", "NG", "175", "65",  73, 0, 0, 1, 18, 18, 18, 18 }, // 63
    { "RYB", "Elena Rybakina",        "Rybakina, Elena",       "Rybakina",    "Elena",       "E. Rybakina",    "E.RYBAKINA",    "KAZ", "NG", "184", "72", 104, 0, 0, 1, 17, 17, 17, 17 }, // 64
    { "BAD", "Paula Badosa",          "Badosa, Paula",         "Badosa",      "Paula",       "P. Badosa",      "P.BADOSA",      "ESP", "NG", "180", "72",  44, 0, 0, 1, 17, 17, 20, 17 }, // 65
    { "HAL", "Simona Halep",          "Halep, Simona",         "Halep",       "Simona",      "S. Halep",       "S.HALEP",       "ROU", "NG", "168", "60",  39, 0, 0, 1, 22, 21, 21, 22 }, // 66
    { "COR", "Guillermo Coria",       "Coria, Guillermo",      "Coria",       "Guillermo",   "G. Coria",       "G.CORIA",       "ARG", "LG", "175", "67",  74, 1, 0, 1,  6,  9, 13,  4 }, // 67
    { "GAS", "Richard Gasquet",       "Gasquet, Richard",      "Gasquet",     "Richard",     "R. Gasquet",     "R.GASQUET",     "FRA", "LG", "183", "79",  15, 1, 0, 0,  0,  0, 24,  6 }, // 68
    { "NIS", "Kei Nishikori",         "Nishikori, Kei",        "Nishikori",   "Kei",         "K. Nishikori",   "K.NISHIKORI",   "JPN", "LG", "178", "75", 102, 1, 0, 1,  3,  3,  8,  8 }, // 69
    { "SOD", "Robin Soderling",       "Soderling, Robin",      "Soderling",   "Robin",       "R. Soderling",   "R.SODERLING",   "SWE", "LG", "193", "87",  45, 1, 0, 1,  4,  2, 11, 14 }, // 70
    { "BER", "Tomas Berdych",         "Berdych, Tomas",        "Berdych",     "Tomas",       "T. Berdych",     "T.BERDYCH",     "CZE", "LG", "196", "91",  11, 1, 0, 1,  4,  9, 13, 10 }, // 71
    { "CHN", "Michael Chang",         "Chang, Michael",        "Chang",       "Michael",     "M. Chang",       "M.CHANG",       "USA", "LG", "175", "72",  73, 1, 0, 1,  6,  6, 13,  5 }, // 72
    { "RIO", "Marcelo Rios",          "Rios, Marcelo",         "Rios",        "Marcelo",     "M. Rios",        "M.RIOS",        "CHI", "LG", "175", "68",  77, 1, 1, 1,  9,  1, 12,  7 }, // 73
    { "MUS", "Thomas Muster",         "Muster, Thomas",        "Muster",      "Thomas",      "T. Muster",      "T.MUSTER",      "AUT", "LG", "180", "75",   3, 1, 1, 0,  1, 10, 10, 10 }, // 74
    { "BRU", "Sergi Bruguera",        "Bruguera, Sergi",       "Bruguera",    "Sergi",       "S. Bruguera",    "S.BRUGUERA",    "ESP", "LG", "188", "76",  44, 1, 0, 1,  1, 13, 14,  1 }, // 75
    { "CRT", "Alex Corretja",         "Corretja, Alex",        "Corretja",    "Alex",        "A. Corretja",    "A.CORRETJA",    "ESP", "LG", "180", "76",  44, 1, 0, 0,  1, 10, 10,  1 }, // 76
    { "WLD", "Mats Wilander",         "Wilander, Mats",        "Wilander",    "Mats",        "M. Wilander",    "M.WILANDER",    "SWE", "LG", "183", "77",  45, 1, 0, 1,  3,  3,  4, 14 }, // 77
    { "LAV", "Rod Laver",             "Laver, Rod",            "Laver",       "Rod",         "R. Laver",       "R.LAVER",       "AUS", "LG", "173", "68", 132, 1, 1, 0,  0, 11, 11, 12 }, // 78
    { "ASV", "Arantxa Sanchez",       "Sanchez, Arantxa",      "Arantxa",     "Arantxa",     "A. Sanchez",     "A.SANCHEZ",     "ESP", "LG", "169", "60",  44, 0, 0, 1, 22, 21, 20, 17 }, // 79
    { "CMT", "Conchita Martinez",     "Martinez, Conchita",    "Conchita",    "Conchita",    "C. Martinez",    "C.MARTINEZ",    "ESP", "LG", "173", "65",  44, 0, 0, 0, 19, 23, 23, 19 }, // 80
    { "CLI", "Kim Clijsters",         "Clijsters, Kim",        "Clijsters",   "Kim",         "K. Clijsters",   "K.CLIJSTERS",   "BEL", "LG", "174", "68",   6, 0, 0, 1, 19, 19, 23, 22 }, // 81
    { "AND", "Mirra Andreeva",        "Andreeva, Mirra",       "Andreeva",    "Mirra",       "M. Andreeva",    "M.ANDREEVA",    "RUS", "NG", "175", "62", 119, 0, 0, 1, 22, 22, 20, 22 }, // 82
    { "BJK", "Billie Jean King",      "King, Billie Jean",     "B.J. King",   "Billie Jean", "B.J. King",      "B.J.KING",      "USA", "LG", "164", "59",  73, 0, 0, 0, 21, 21, 19, 18 }  // 83
};

// ----------------------------------------------------------------------------
// Fase 2 Extended Roster Metadata (char_id 26..37)
// ----------------------------------------------------------------------------
static const char *g_custom_card_names[12] = {
    "Alcaraz", "Sinner", "Sampras", "Agassi", "Borg", "McEnroe",
    "Graf", "Serena", "Swiatek", "Sabalenka", "Kuerten", "Navratilova"
};
static const char *g_custom_first_names[12] = {
    "Carlos", "Jannik", "Pete", "Andre", "Bjorn", "John",
    "Steffi", "Serena", "Iga", "Aryna", "Gustavo", "Martina"
};
static const char *g_custom_last_first[12] = {
    "Alcaraz, Carlos", "Sinner, Jannik", "Sampras, Pete", "Agassi, Andre",
    "Borg, Bjorn", "McEnroe, John", "Graf, Steffi", "Williams, Serena",
    "Swiatek, Iga", "Sabalenka, Aryna", "Kuerten, Gustavo", "Navratilova, Martina"
};
static const char *g_custom_banner_names[12] = {
    "C. Alcaraz", "J. Sinner", "P. Sampras", "A. Agassi", "B. Borg", "J. McEnroe",
    "S. Graf", "S. Williams", "I. Swiatek", "A. Sabalenka", "G. Kuerten", "M. Navratilova"
};
static const char *g_custom_short_upper[12] = {
    "C.ALCARAZ", "J.SINNER", "P.SAMPRAS", "A.AGASSI", "B.BORG", "J.MCENROE",
    "S.GRAF", "S.WILLIAMS", "I.SWIATEK", "A.SABALENKA", "G.KUERTEN", "M.NAVRATILOVA"
};
static const char *g_custom_full_names[12] = {
    "Carlos Alcaraz", "Jannik Sinner", "Pete Sampras", "Andre Agassi",
    "Bjorn Borg", "John McEnroe", "Steffi Graf", "Serena Williams",
    "Iga Swiatek", "Aryna Sabalenka", "Gustavo Kuerten", "Martina Navratilova"
};
static const char *g_custom_ioc_codes[12] = {
    "ESP", "ITA", "USA", "USA", "SWE", "USA",
    "GER", "USA", "POL", "BLR", "BRA", "USA"
};
static const uint8_t g_custom_lefty[12]     = { 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1 };
static const uint8_t g_custom_bh2[12]       = { 1, 1, 0, 1, 1, 0, 0, 1, 1, 1, 0, 0 };
static const uint8_t g_custom_bio_proxy[12] = { 1, 9, 5, 5, 14, 5, 17, 18, 22, 17, 1, 18 };
static const char *g_custom_height_cm[12] = {
    "183", "191", "185", "180", "180", "180",
    "176", "175", "176", "182", "191", "173"
};
static const char *g_custom_weight_kg[12] = {
    "74", "77", "77", "80", "73", "75",
    "64", "72", "65", "80", "83", "66"
};
static char g_bio_ht_cm[MAX_ROSTER_PLAYERS - 26][16];
static char g_bio_ht_ft[MAX_ROSTER_PLAYERS - 26][16];
static char g_bio_wt_kg[MAX_ROSTER_PLAYERS - 26][16];
static char g_bio_wt_lb[MAX_ROSTER_PLAYERS - 26][16];

static void init_custom_bio_strings(void) {
    for (int id = 26; id < MAX_ROSTER_PLAYERS; id++) {
        int idx = id - 26;
        const char *h_s = (id < 38) ? g_custom_height_cm[idx] : g_extra_players[id - 38].height;
        const char *w_s = (id < 38) ? g_custom_weight_kg[idx] : g_extra_players[id - 38].weight;
        int cm = atoi(h_s);
        int kg = atoi(w_s);
        if (cm <= 0) cm = 180;
        if (kg <= 0) kg = 75;
        int tot_in = (int)((double)cm / 2.54 + 0.5);
        int lb = (int)((double)kg * 2.20462 + 0.5);
        snprintf(g_bio_ht_cm[idx], sizeof(g_bio_ht_cm[idx]), "%dcm.", cm);
        snprintf(g_bio_ht_ft[idx], sizeof(g_bio_ht_ft[idx]), "%d'%d$Q", tot_in / 12, tot_in % 12);
        snprintf(g_bio_wt_kg[idx], sizeof(g_bio_wt_kg[idx]), "%dkg", kg);
        snprintf(g_bio_wt_lb[idx], sizeof(g_bio_wt_lb[idx]), "%dlb", lb);
    }
}
static int32_t g_player_flags[MAX_ROSTER_PLAYERS] = {0};
static uint32_t g_player_anim_presets[MAX_ROSTER_PLAYERS * 5] = {0};
static float g_player_bone_scales[MAX_ROSTER_PLAYERS * 60] = {0};

typedef void (__thiscall *PlayStyleLoadChar_t)(void *self, int char_id);
static PlayStyleLoadChar_t g_real_playstyle_loadchar = NULL;
static const uint8_t g_custom_playstyle_proxy[12] = { 1, 2, 0, 10, 14, 11, 17, 18, 22, 20, 12, 18 };
static const uint8_t g_custom_anim_proxy[12]      = { 2, 2, 0, 13, 3, 11, 17, 18, 22, 21, 12, 18 };

static void __thiscall hk_PlayStyle_LoadChar(void *self, int char_id) {
    int orig_id = char_id;
    if (char_id >= 0 && char_id < VP_MAX_ROSTER_IDS) {
        if (g_present_calls > g_vp_load_frame + 60 || g_vp_p1_id < 0) {
            g_vp_p1_id = char_id;
            g_vp_p2_id = -1;
            g_vp_load_frame = g_present_calls;
        } else if (g_vp_p2_id < 0) {
            g_vp_p2_id = char_id;
        }
    }
    if (char_id >= 26 && char_id < 38) {
        char_id = (int)g_custom_playstyle_proxy[char_id - 26];
    } else if (char_id >= 38 && char_id < MAX_ROSTER_PLAYERS) {
        char_id = (int)g_extra_players[char_id - 38].playstyle_proxy;
    }
    if (g_real_playstyle_loadchar) g_real_playstyle_loadchar(self, char_id);
    if (orig_id >= 26 && orig_id < MAX_ROSTER_PLAYERS) {
        apply_custom_player_stats(self, orig_id, (int)g_cfg_debug_log);
    }
}

typedef void (__thiscall *SetServeMotionIdFn_t)(void *self, int id1, int id2);
static SetServeMotionIdFn_t g_real_set_serve_motion_id = NULL;
static void __thiscall hk_SetServeMotionId(void *self, int id1, int id2) {
    if (id1 >= 26 && id1 < 38) id1 = (int)g_custom_anim_proxy[id1 - 26];
    else if (id1 >= 38 && id1 < MAX_ROSTER_PLAYERS) id1 = (int)g_extra_players[id1 - 38].anim_proxy;
    if (id2 >= 26 && id2 < 38) id2 = (int)g_custom_anim_proxy[id2 - 26];
    else if (id2 >= 38 && id2 < MAX_ROSTER_PLAYERS) id2 = (int)g_extra_players[id2 - 38].anim_proxy;
    if (g_real_set_serve_motion_id) g_real_set_serve_motion_id(self, id1, id2);
}

typedef void *(__thiscall *GetMotionDataFn_t)(void *self, int slot, int motion_id);
static GetMotionDataFn_t g_real_get_motion_data = NULL;

static inline int is_valid_motion_handle(void *res) {
    uintptr_t p = (uintptr_t)res;
    if (p < 0x10000u || p >= 0x7FFE0000u || IsBadReadPtr(res, 4)) return 0;
    uintptr_t inner = *(uintptr_t *)res;
    if (inner < 0x10000u || inner >= 0x7FFE0000u || IsBadReadPtr((const void *)inner, 16)) return 0;
    return 1;
}

static void *__thiscall hk_GetMotionData(void *self, int slot, int motion_id) {
    const int16_t *map = NULL;
    if (self && slot >= 0 && slot < 16 && !IsBadReadPtr(self, 4)) {
        uint8_t *mgr = *(uint8_t **)self;
        if ((uintptr_t)mgr >= 0x10000u && !IsBadReadPtr(mgr + (size_t)slot * 0x58 + 0x10, 4)) {
            map = *(const int16_t **)(mgr + (size_t)slot * 0x58 + 0x10);
            if ((uintptr_t)map < 0x10000u) map = NULL;
        }
    }
    if (map && motion_id >= 0 && motion_id < 4096 && !IsBadReadPtr(&map[motion_id * 2], 4) && map[motion_id * 2] < 0) {
        static int s_unloaded_mot_logs = 0;
        int fb = (slot == 3) ? 0x50 : 0;
        if (IsBadReadPtr(&map[fb * 2], 4) || map[fb * 2] < 0) {
            fb = -1;
            for (int k = 0; k < 512; k++) {
                if (!IsBadReadPtr(&map[k * 2], 4) && map[k * 2] >= 0) { fb = k; break; }
            }
        }
        if (s_unloaded_mot_logs < 16) {
            s_unloaded_mot_logs++;
            log_msg("[VT4-Mod] [MOT-FIX] Unloaded motion G[%d] ID[0x%x] -> redirecting to safe loaded ID[0x%x] caller=%p",
                    slot, motion_id, fb, __builtin_return_address(0));
        }
        if (fb >= 0 && g_real_get_motion_data) {
            void *res_fb = g_real_get_motion_data(self, slot, fb);
            if (is_valid_motion_handle(res_fb)) return res_fb;
        }
    }

    void *res = g_real_get_motion_data ? g_real_get_motion_data(self, slot, motion_id) : NULL;
    if (!is_valid_motion_handle(res)) {
        static int s_bad_mot_logs = 0;
        if (s_bad_mot_logs < 16) {
            s_bad_mot_logs++;
            log_msg("[VT4-Mod] [DIAG-MOT] GetMotionData(self=%p, slot=%d, motion_id=%d/0x%x) -> BAD ptr=%p caller=%p",
                    self, slot, motion_id, motion_id, res, __builtin_return_address(0));
        }
        int fb = (slot == 3) ? 0x50 : 0;
        if (map && (IsBadReadPtr(&map[fb * 2], 4) || map[fb * 2] < 0)) {
            for (int k = 0; k < 512; k++) {
                if (!IsBadReadPtr(&map[k * 2], 4) && map[k * 2] >= 0) { fb = k; break; }
            }
        }
        void *res2 = g_real_get_motion_data ? g_real_get_motion_data(self, slot, fb) : NULL;
        if (is_valid_motion_handle(res2)) return res2;
    }
    return res;
}

static int __stdcall hk_GetPlayerFlag(int id) {
    if (id >= 0 && id < MAX_ROSTER_PLAYERS) return g_player_flags[id];
    return 200;
}

typedef const char *(__thiscall *StoLookup_t)(void *sto_obj, int table_id, int row_id);
static StoLookup_t g_real_sto_lookup = NULL;
static void *g_tr_common_sto = NULL;
static int g_sto_tbl_dob = -1;

/* Verified real birth dates (D/M/YYYY, matching TR_COMMON.sto) for custom IDs 26..83 */
static const char *g_custom_dob[MAX_ROSTER_PLAYERS - 26] = {
    "5/5/2003",   /* 26: Carlos Alcaraz */
    "16/8/2001",  /* 27: Jannik Sinner */
    "12/8/1971",  /* 28: Pete Sampras */
    "29/4/1970",  /* 29: Andre Agassi */
    "6/6/1956",   /* 30: Bjorn Borg */
    "16/2/1959",  /* 31: John McEnroe */
    "14/6/1969",  /* 32: Steffi Graf */
    "26/9/1981",  /* 33: Serena Williams */
    "31/5/2001",  /* 34: Iga Swiatek */
    "5/5/1998",   /* 35: Aryna Sabalenka */
    "10/9/1976",  /* 36: Gustavo Kuerten */
    "18/10/1956", /* 37: Martina Navratilova */
    "28/3/1985",  /* 38: Stan Wawrinka */
    "11/2/1996",  /* 39: Daniil Medvedev */
    "20/4/1997",  /* 40: Alexander Zverev */
    "12/8/1998",  /* 41: Stefanos Tsitsipas */
    "3/9/1993",   /* 42: Dominic Thiem */
    "27/4/1995",  /* 43: Nick Kyrgios */
    "24/2/1981",  /* 44: Lleyton Hewitt */
    "27/1/1980",  /* 45: Marat Safin */
    "17/4/1985",  /* 46: Jo-Wilfried Tsonga */
    "12/2/1980",  /* 47: Juan Carlos Ferrero */
    "27/8/1976",  /* 48: Carlos Moya */
    "2/4/1982",   /* 49: David Ferrer */
    "1/1/1982",   /* 50: David Nalbandian */
    "7/3/1960",   /* 51: Ivan Lendl */
    "2/9/1952",   /* 52: Jimmy Connors */
    "17/8/1952",  /* 53: Guillermo Vilas */
    "13/9/1971",  /* 54: Goran Ivanisevic */
    "21/12/1954", /* 55: Chris Evert */
    "2/12/1973",  /* 56: Monica Seles */
    "1/6/1982",   /* 57: Justine Henin */
    "8/10/1993",  /* 58: Garbine Muguruza */
    "9/10/2002",  /* 59: Ben Shelton */
    "20/10/1997", /* 60: Andrey Rublev */
    "22/12/1998", /* 61: Casper Ruud */
    "28/10/1997", /* 62: Taylor Fritz */
    "13/3/2004",  /* 63: Coco Gauff */
    "17/6/1999",  /* 64: Elena Rybakina */
    "15/11/1997", /* 65: Paula Badosa */
    "27/9/1991",  /* 66: Simona Halep */
    "13/1/1982",  /* 67: Guillermo Coria */
    "18/6/1986",  /* 68: Richard Gasquet */
    "29/12/1989", /* 69: Kei Nishikori */
    "14/8/1984",  /* 70: Robin Soderling */
    "17/9/1985",  /* 71: Tomas Berdych */
    "22/2/1972",  /* 72: Michael Chang */
    "26/12/1975", /* 73: Marcelo Rios */
    "2/10/1967",  /* 74: Thomas Muster */
    "16/1/1971",  /* 75: Sergi Bruguera */
    "11/4/1974",  /* 76: Alex Corretja */
    "22/8/1964",  /* 77: Mats Wilander */
    "9/8/1938",   /* 78: Rod Laver */
    "18/12/1971", /* 79: Arantxa Sanchez Vicario */
    "16/4/1972",  /* 80: Conchita Martinez */
    "8/6/1983",   /* 81: Kim Clijsters */
    "29/4/2007",  /* 82: Mirra Andreeva */
    "22/11/1943"  /* 83: Billie Jean King */
};

static int sto_is_federer_dob(const char *s) {
    if (!s || !s[0]) return 0;
    return (strstr(s, "8/8/1981") != NULL || strstr(s, "1981/8/8") != NULL);
}

static int      g_loading_cur_char_id = -1;
static int      g_loading_bio_char_id = -1;
static uint32_t g_loading_cur_frame   = 0;

static void __thiscall hk_Loading_SetPlayerPhoto(void *self, int slot, int char_id) {
    if (char_id >= 0 && char_id < MAX_ROSTER_PLAYERS) {
        g_loading_cur_char_id = char_id;
        g_loading_cur_frame   = g_present_calls;
    }
    typedef void (__thiscall *SetPhotoFn_t)(void *, int, int);
    ((SetPhotoFn_t)0x005E6510)(self, slot, char_id);
}

static void __thiscall hk_Loading_SetBioCard(void *self, void *info) {
    int prev = g_loading_bio_char_id;
    if (info && !IsBadReadPtr(info, 12)) {
        int cid = *(int *)((char *)info + 8);
        if (cid >= 0 && cid < MAX_ROSTER_PLAYERS) {
            g_loading_bio_char_id = cid;
        }
    }
    typedef void (__thiscall *SetBioFn_t)(void *, void *);
    ((SetBioFn_t)0x005e58a0)(self, info);
    g_loading_bio_char_id = prev;
}

static const char *__fastcall hk_StoLookup(void *sto_obj, void *edx, int table_id, int row_id) {
    (void)edx;
    if (!g_real_sto_lookup) return "";
    /* Restrict player-ID resolution and overrides strictly to player tables 0..14!
     * Tables 15..16 are 200-country IOC/name tables keyed by flag_id (must never remap row_id >= 26). */
    if (g_has_custom_roster && sto_obj == g_tr_common_sto && table_id >= 0 && table_id <= 14) {
        if (g_loading_bio_char_id >= 26 && g_loading_bio_char_id < MAX_ROSTER_PLAYERS) {
            row_id = g_loading_bio_char_id;
        } else if (row_id >= 0 && row_id < 28 && __builtin_return_address(0) == (void *)0x006693E9) {
            int resolved = -1;
            if (g_loading_cur_char_id >= 26 && g_loading_cur_char_id < MAX_ROSTER_PLAYERS &&
                g_present_calls <= g_loading_cur_frame + 10u &&
                ((g_loading_cur_char_id % 26) == row_id || (g_loading_cur_char_id % 28) == row_id)) {
                resolved = g_loading_cur_char_id;
            } else if (g_vp_p1_id >= 0) {
                static uint32_t s_lt_frame = 0;
                static int s_lt_idx = -1, s_lt_last_row = -1;
                if (g_present_calls > s_lt_frame + 3u) { s_lt_idx = -1; s_lt_last_row = -1; }
                s_lt_frame = g_present_calls;
                if (row_id != s_lt_last_row) { s_lt_idx++; s_lt_last_row = row_id; }
                int pid = (s_lt_idx == 0) ? g_vp_p1_id : (s_lt_idx == 1 ? g_vp_p2_id : -1);
                if (pid >= 26 && pid < MAX_ROSTER_PLAYERS &&
                    ((pid % 26) == row_id || (pid % 28) == row_id)) {
                    resolved = pid;
                }
            }
            if (resolved >= 26) {
                if (g_cfg_debug_log) {
                    static int s_lt_log = 0;
                    if (s_lt_log < 16) {
                        s_lt_log++;
                        log_msg("[VT4-Mod] [LOADFIX] loading text tbl=%d row %d -> real id %d", table_id, row_id, resolved);
                    }
                }
                row_id = resolved;
            }
        }
    }
    if (sto_obj && sto_obj != g_tr_common_sto) {
        const char *probe = g_real_sto_lookup(sto_obj, 0, 0);
        if (probe && strcmp(probe, "Roger Federer") == 0) {
            g_tr_common_sto = sto_obj;
            g_sto_tbl_dob = -1;
            for (int t = 7; t <= 13; t++) {
                const char *s = g_real_sto_lookup(sto_obj, t, 0);
                if (s && s[0]) {
                    log_msg("[VT4-Mod] TR_COMMON.sto tbl[%d][0] = \"%s\"", t, s);
                    if (g_sto_tbl_dob < 0 && sto_is_federer_dob(s)) {
                        g_sto_tbl_dob = t;
                    }
                }
            }
            log_msg("[VT4-Mod] Identified TR_COMMON.sto object: %p (dob_tbl=%d)", sto_obj, g_sto_tbl_dob);
        }
    }
    if (sto_obj == g_tr_common_sto) {
        if (g_sto_tbl_dob < 0 && table_id > 6 && table_id <= 14) {
            const char *fed = g_real_sto_lookup(sto_obj, table_id, 0);
            if (sto_is_federer_dob(fed)) {
                g_sto_tbl_dob = table_id;
                log_msg("[VT4-Mod] Auto-detected TR_COMMON.sto DOB table_id=%d (\"%s\")", table_id, fed);
            }
        }
        if (g_has_custom_roster && table_id >= 0 && table_id <= 14 && row_id >= 26 && row_id < MAX_ROSTER_PLAYERS) {
            if ((g_sto_tbl_dob >= 0 && table_id == g_sto_tbl_dob) || table_id == 10) {
                return g_custom_dob[row_id - 26];
            }
            if (table_id == 7) {
                int flg = g_player_flags[row_id];
                return g_real_sto_lookup(sto_obj, 16, (flg >= 0 && flg < 200) ? flg : 0);
            }
            if (table_id == 11) return g_bio_ht_cm[row_id - 26];
            if (table_id == 12) return g_bio_ht_ft[row_id - 26];
            if (table_id == 13) return g_bio_wt_kg[row_id - 26];
            if (table_id == 14) return g_bio_wt_lb[row_id - 26];
            if (row_id < 38) {
                int idx = row_id - 26;
                switch (table_id) {
                    case 0: return g_custom_full_names[idx];
                    case 1: return g_custom_last_first[idx];
                    case 2: return g_custom_card_names[idx];
                    case 3: return g_custom_first_names[idx];
                    case 4: return g_custom_banner_names[idx];
                    case 5: return g_custom_short_upper[idx];
                    case 6: return g_custom_ioc_codes[idx];
                    case 8: return g_real_sto_lookup(sto_obj, 8, g_custom_lefty[idx] ? 1 : 0);
                    case 9: return g_real_sto_lookup(sto_obj, 9, g_custom_bh2[idx] ? 2 : 0);
                    default:
                        return g_real_sto_lookup(sto_obj, table_id, (int)g_custom_bio_proxy[idx]);
                }
            } else {
                const ExtraPlayerDef *ep = &g_extra_players[row_id - 38];
                switch (table_id) {
                    case 0: return ep->full_name;
                    case 1: return ep->last_first;
                    case 2: return ep->card_name;
                    case 3: return ep->first_name;
                    case 4: return ep->banner_name;
                    case 5: return ep->short_name;
                    case 6: return ep->ioc_code;
                    case 8: return g_real_sto_lookup(sto_obj, 8, ep->lefty ? 1 : 0);
                    case 9: return g_real_sto_lookup(sto_obj, 9, ep->bh2 ? 2 : 0);
                    default:
                        return g_real_sto_lookup(sto_obj, table_id, (int)ep->bio_proxy);
                }
            }
        }
    }
    return g_real_sto_lookup(sto_obj, table_id, row_id);
}

// ----------------------------------------------------------------------------
// PlayerDB Hooks for IDs 38..58 (Page 3 Expansion beyond native 38-row blocks)
// ----------------------------------------------------------------------------
typedef int         (__cdecl *PlayerDB_GetCount_t)(void);
typedef const char *(__cdecl *PlayerDB_GetCode_t)(int id);
typedef int         (__cdecl *PlayerDB_FindByCode_t)(const char *code);
typedef uint8_t     (__cdecl *PlayerDB_BoolId_t)(int id);
typedef int         (__cdecl *PlayerDB_IntId_t)(int id);
typedef const char *(__cdecl *PlayerDB_StrId_t)(int id);
typedef void       *(__cdecl *PlayerDB_FStrOut_t)(void *out_fstr, int id);
typedef uint8_t     (__cdecl *PlayerDB_ModelPrefix_t)(void *sb, int id);
typedef void *      (__thiscall *StringBuilder_Append_t)(void *sb, const char *s);
typedef int         (__thiscall *FwDB_GetInt_t)(void *fwdb, int row);
typedef float       (__thiscall *FwDB_GetFloat_t)(void *fwdb, int row);
typedef const char *(__thiscall *FwDB_GetStr_t)(void *fwdb, int row);

static PlayerDB_GetCode_t     g_real_pdb_get_code = NULL;
static PlayerDB_FindByCode_t  g_real_pdb_find_by_code = NULL;
static PlayerDB_BoolId_t      g_real_pdb_is_man = NULL;
static PlayerDB_IntId_t       g_real_pdb_get_type = NULL;
static PlayerDB_FStrOut_t     g_real_pdb_get_style_name = NULL;
static PlayerDB_IntId_t       g_real_pdb_get_style_enum = NULL;
static PlayerDB_BoolId_t      g_real_pdb_is_type3 = NULL;
static PlayerDB_StrId_t       g_real_pdb_get_height = NULL;
static PlayerDB_StrId_t       g_real_pdb_get_weight = NULL;
static PlayerDB_BoolId_t      g_real_pdb_get_bh2 = NULL;
static PlayerDB_BoolId_t      g_real_pdb_get_lefty = NULL;
static PlayerDB_IntId_t       g_real_pdb_get_tension = NULL;
static PlayerDB_IntId_t       g_real_pdb_get_wtdbls = NULL;
static PlayerDB_StrId_t       g_real_pdb_get_short_name = NULL;
static PlayerDB_FStrOut_t     g_real_pdb_get_voice_se = NULL;
static PlayerDB_ModelPrefix_t g_real_pdb_get_model_prefix = NULL;

static int __cdecl hk_PlayerDB_GetCount(void) { return MAX_ROSTER_PLAYERS; }

static const char *__cdecl hk_PlayerDB_GetCode(int id) {
    if (id >= 38 && id < MAX_ROSTER_PLAYERS) return g_extra_players[id - 38].code;
    return g_real_pdb_get_code ? g_real_pdb_get_code(id) : "FED";
}

static int __cdecl hk_PlayerDB_FindByCode(const char *code) {
    if (code) {
        for (int i = 0; i < NUM_EXTRA_PLAYERS; i++) {
            if (_stricmp(code, g_extra_players[i].code) == 0) return 38 + i;
        }
    }
    return g_real_pdb_find_by_code ? g_real_pdb_find_by_code(code) : 0;
}

static uint8_t __cdecl hk_PlayerDB_IsMan(int id) {
    if (id >= 38 && id < MAX_ROSTER_PLAYERS) return g_extra_players[id - 38].man;
    return g_real_pdb_is_man ? g_real_pdb_is_man(id) : 1;
}

static int __cdecl hk_PlayerDB_GetType(int id) {
    if (id >= 38 && id < MAX_ROSTER_PLAYERS) return 0;
    return g_real_pdb_get_type ? g_real_pdb_get_type(id) : 0;
}

static void *__cdecl hk_PlayerDB_GetStyleName(void *out_fstr, int id) {
    if (id >= 38 && id < MAX_ROSTER_PLAYERS) id = (int)g_extra_players[id - 38].playstyle_proxy;
    return g_real_pdb_get_style_name ? g_real_pdb_get_style_name(out_fstr, id) : out_fstr;
}

static int __cdecl hk_PlayerDB_GetStyleEnum(int id) {
    if (id >= 38 && id < MAX_ROSTER_PLAYERS) id = (int)g_extra_players[id - 38].playstyle_proxy;
    return g_real_pdb_get_style_enum ? g_real_pdb_get_style_enum(id) : 0;
}

static uint8_t __cdecl hk_PlayerDB_IsType3(int id) {
    if (id >= 38 && id < MAX_ROSTER_PLAYERS) return 0;
    return g_real_pdb_is_type3 ? g_real_pdb_is_type3(id) : 0;
}

static const char *__cdecl hk_PlayerDB_GetHeight(int id) {
    if (id >= 26 && id < 38) return g_custom_height_cm[id - 26];
    if (id >= 38 && id < MAX_ROSTER_PLAYERS) return g_extra_players[id - 38].height;
    return g_real_pdb_get_height ? g_real_pdb_get_height(id) : "180";
}

static const char *__cdecl hk_PlayerDB_GetWeight(int id) {
    if (id >= 26 && id < 38) return g_custom_weight_kg[id - 26];
    if (id >= 38 && id < MAX_ROSTER_PLAYERS) return g_extra_players[id - 38].weight;
    return g_real_pdb_get_weight ? g_real_pdb_get_weight(id) : "75";
}

static uint8_t __cdecl hk_PlayerDB_GetBackHand2H(int id) {
    if (id >= 38 && id < MAX_ROSTER_PLAYERS) return g_extra_players[id - 38].bh2;
    return g_real_pdb_get_bh2 ? g_real_pdb_get_bh2(id) : 0;
}

static uint8_t __cdecl hk_PlayerDB_GetLefty(int id) {
    if (id >= 38 && id < MAX_ROSTER_PLAYERS) return g_extra_players[id - 38].lefty;
    return g_real_pdb_get_lefty ? g_real_pdb_get_lefty(id) : 0;
}

static int __cdecl hk_PlayerDB_GetTension(int id) {
    if (id >= 38 && id < MAX_ROSTER_PLAYERS) return 0;
    return g_real_pdb_get_tension ? g_real_pdb_get_tension(id) : 0;
}

static int __cdecl hk_PlayerDB_GetWtDblsPt(int id) {
    if (id >= 38 && id < MAX_ROSTER_PLAYERS) return 3500;
    return g_real_pdb_get_wtdbls ? g_real_pdb_get_wtdbls(id) : 3500;
}

static const char *__cdecl hk_PlayerDB_GetShortName(int id) {
    if (id >= 38 && id < MAX_ROSTER_PLAYERS) return g_extra_players[id - 38].short_name;
    return g_real_pdb_get_short_name ? g_real_pdb_get_short_name(id) : "";
}

static void *__cdecl hk_PlayerDB_GetVoiceSE(void *out_fstr, int id) {
    if (id >= 38 && id < MAX_ROSTER_PLAYERS) id = (int)g_extra_players[id - 38].bone_proxy;
    return g_real_pdb_get_voice_se ? g_real_pdb_get_voice_se(out_fstr, id) : out_fstr;
}

static int g_agassi_skin = 0; // 0 = '91 Melena Rubia + Cinta, 1 = '06 Calvo + Perilla
static int g_agassi_skin_dirty = 0;
static int g_agassi_hovered_cs = 0;

static uint8_t __cdecl hk_PlayerDB_GetModelPrefix(void *sb, int id) {
    if (id == 29 && g_agassi_skin == 1) {
        ((StringBuilder_Append_t)0x004157b0)(sb, "#/Player/Model/P_M_AG2");
        return 0;
    }
    if (id >= 38 && id < MAX_ROSTER_PLAYERS) {
        const ExtraPlayerDef *ep = &g_extra_players[id - 38];
        char buf[64];
        snprintf(buf, sizeof(buf), "#/Player/Model/P_%c_%s", ep->man ? 'M' : 'W', ep->code);
        ((StringBuilder_Append_t)0x004157b0)(sb, buf);
        return 0;
    }
    return g_real_pdb_get_model_prefix ? g_real_pdb_get_model_prefix(sb, id) : 0;
}

static const char *__fastcall hk_ModelSdo_GetAuthor(void *fwdb, void *edx, int row) {
    int id = row - 0x4c;
    if (id == 29) return "LG";
    if (id >= 38 && id < MAX_ROSTER_PLAYERS) return g_extra_players[id - 38].author;
    return ((FwDB_GetStr_t)0x00625340)(fwdb, row);
}

static float __fastcall hk_ServeMin_GetFloat(void *fwdb, void *edx, int row) {
    int id = row - 0x98;
    if (id >= 38 && id < MAX_ROSTER_PLAYERS) row = (int)g_extra_players[id - 38].playstyle_proxy + 0x98;
    return ((FwDB_GetFloat_t)0x006252e0)(fwdb, row);
}

static float __fastcall hk_ServeMax_GetFloat(void *fwdb, void *edx, int row) {
    int id = row - 0xbe;
    if (id >= CUSTOM_STATS_FIRST_ID && id < CUSTOM_STATS_FIRST_ID + CUSTOM_STATS_COUNT) {
        return g_custom_player_stats[id - CUSTOM_STATS_FIRST_ID].serve_max_kmh;
    }
    if (id >= 38 && id < MAX_ROSTER_PLAYERS) row = (int)g_extra_players[id - 38].playstyle_proxy + 0xbe;
    return ((FwDB_GetFloat_t)0x006252e0)(fwdb, row);
}

#include "broadcast_hud.h"

static int g_current_roster_page = 0;
static void *g_pCharaSelect = NULL;
static int g_chara_select_frames = 0;
static uint32_t g_chara_select_ticks = 0;
static int g_roster_page_dirty = 0;

static float g_arr_left_rc[4] = { 0 };
static float g_arr_right_rc[4] = { 0 };

typedef HRESULT (WINAPI *D3DXCreateTextureFromFileA_t)(void *pDevice, LPCSTR pSrcFile, void **ppTexture);
static D3DXCreateTextureFromFileA_t g_d3dx_createtexture = NULL;
static void *g_pTexArrowLeft = NULL;
static void *g_pTexArrowRight = NULL;
static int g_arrow_textures_attempted = 0;

static char s_arrow_path_l[MAX_PATH] = { 0 };
static char s_arrow_path_r[MAX_PATH] = { 0 };

static void __attribute__((noinline)) init_arrow_textures(void *dev) {
    if (g_arrow_textures_attempted) return;
    if (!dev) dev = g_d3d_device;
    if (!dev || !*(void ***)dev) return;
    g_arrow_textures_attempted = 1;
    HMODULE hD3DX = get_d3dx9_43();
    if (hD3DX) {
        g_d3dx_createtexture = (D3DXCreateTextureFromFileA_t)GetProcAddress(hD3DX, "D3DXCreateTextureFromFileA");
    }
    if (g_d3dx_createtexture) {
        snprintf(s_arrow_path_l, sizeof(s_arrow_path_l), "%s\\ui_arrow_left.png", g_game_dir);
        snprintf(s_arrow_path_r, sizeof(s_arrow_path_r), "%s\\ui_arrow_right.png", g_game_dir);
        HRESULT hr_l = g_d3dx_createtexture(dev, s_arrow_path_l, &g_pTexArrowLeft);
        HRESULT hr_r = g_d3dx_createtexture(dev, s_arrow_path_r, &g_pTexArrowRight);
        log_msg("[VT4-Mod] Loaded UI arrow textures: left=%p (hr=0x%08lx) right=%p (hr=0x%08lx)",
                g_pTexArrowLeft, (unsigned long)hr_l, g_pTexArrowRight, (unsigned long)hr_r);
    }
}

static void draw_textured_quad(void *dev, void *tex, float x1, float y1, float x2, float y2, DWORD color) {
    if (!dev || !tex) return;
    TexturedVertex verts[4] = {
        { x1, y1, 0.0f, 1.0f, color, 0.0f, 0.0f },
        { x2, y1, 0.0f, 1.0f, color, 1.0f, 0.0f },
        { x1, y2, 0.0f, 1.0f, color, 0.0f, 1.0f },
        { x2, y2, 0.0f, 1.0f, color, 1.0f, 1.0f }
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
        set_rs(dev, 27, 1);  // D3DRS_ALPHABLENDENABLE = TRUE
        set_rs(dev, 19, 5);  // D3DRS_SRCBLEND = D3DBLEND_SRCALPHA (5)
        set_rs(dev, 20, 6);  // D3DRS_DESTBLEND = D3DBLEND_INVSRCALPHA (6)
        set_rs(dev, 15, 0);  // D3DRS_ALPHATESTENABLE = FALSE
        set_rs(dev, 137, 0); // D3DRS_LIGHTING = FALSE
        set_rs(dev, 22, 1);  // D3DRS_CULLMODE = D3DCULL_NONE (1)
        set_rs(dev, 7, 0);   // D3DRS_ZENABLE = FALSE
    }

    if (set_tss) {
        set_tss(dev, 0, 1, 4); // D3DTSS_COLOROP = D3DTOP_MODULATE
        set_tss(dev, 0, 2, 2); // D3DTSS_COLORARG1 = D3DTA_TEXTURE
        set_tss(dev, 0, 3, 0); // D3DTSS_COLORARG2 = D3DTA_DIFFUSE
        set_tss(dev, 0, 4, 4); // D3DTSS_ALPHAOP = D3DTOP_MODULATE
        set_tss(dev, 0, 5, 2); // D3DTSS_ALPHAARG1 = D3DTA_TEXTURE
        set_tss(dev, 0, 6, 0); // D3DTSS_ALPHAARG2 = D3DTA_DIFFUSE
        set_tss(dev, 1, 1, 1); // stage 1 COLOROP = D3DTOP_DISABLE
        set_tss(dev, 1, 4, 1); // stage 1 ALPHAOP = D3DTOP_DISABLE
    }
    if (set_samp) {
        set_samp(dev, 0, 1, 2); // D3DSAMP_MAGFILTER = D3DTEXF_LINEAR
        set_samp(dev, 0, 2, 2); // D3DSAMP_MINFILTER = D3DTEXF_LINEAR
    }

    if (set_tex) set_tex(dev, 0, tex);
    if (set_fvf) set_fvf(dev, FVF_TEXTURED_VERTEX);
    if (g_real_drawprimitiveup) {
        g_real_drawprimitiveup(dev, 5, 2, verts, sizeof(TexturedVertex));
    }
    if (set_tex) set_tex(dev, 0, NULL);
}

static void switch_roster_page(int dir) {
    static uint32_t s_last_flip_frame = 0;
    if (g_present_calls == s_last_flip_frame && g_present_calls != 0) return;
    s_last_flip_frame = g_present_calls;

    g_current_roster_page = (g_current_roster_page + dir + NUM_ROSTER_PAGES) % NUM_ROSTER_PAGES;
    log_msg("[VT4-Mod] Switching to roster page %d (%s)", g_current_roster_page, g_roster_page_titles[g_current_roster_page]);

    // 1. Copy the 24 slot IDs of the active page to 0x007c5f6c
    memcpy((void *)0x007c5f6c, g_roster_pages[g_current_roster_page], 24);

    // 2. Mark dirty so hk_FPCharaSelect_Update immediately refreshes on next tick
    g_roster_page_dirty = 1;
}

static void toggle_agassi_skin(void) {
    g_agassi_skin = g_agassi_skin ? 0 : 1;
    g_agassi_skin_dirty = 1;
    memcpy(&g_player_bone_scales[29 * 60], &g_player_bone_scales[(g_agassi_skin ? 2 : 1) * 60], 240);
    log_msg("[VT4-Mod] Agassi skin toggled -> %d (%s)", g_agassi_skin,
            g_agassi_skin ? "2006 Calvo + Perilla" : "1991 Melena Rubia + Cinta");
}

static void toggle_weapon_mode(void) {
    g_cfg_weapon_mode = (g_cfg_weapon_mode + 1u) % 4u;
    sync_menu_indices_from_cfg();
    save_vt4_settings();
    log_msg("[VT4-Mod] [EE-3] WeaponMode toggled -> %u (%s)",
            g_cfg_weapon_mode, s_weapon_choices[g_cfg_weapon_mode]);
}

static int check_roster_arrow_click(int mx, int my) {
    if (!g_has_custom_roster || g_chara_select_frames <= 0) return 0;
    float fx = (float)mx;
    float fy = (float)my;
    float sy = (float)g_cfg_height / 1080.0f;
    float cs_x0 = (float)g_cfg_width * 0.5f - 960.0f * sy;

    if (fx >= cs_x0 + 830.0f * sy && fx <= cs_x0 + 926.0f * sy &&
        fy >= 172.0f * sy && fy <= 208.0f * sy) {
        switch_roster_page(-1);
        return 1;
    }
    if (fx >= cs_x0 + 1354.0f * sy && fx <= cs_x0 + 1450.0f * sy &&
        fy >= 172.0f * sy && fy <= 208.0f * sy) {
        switch_roster_page(1);
        return 1;
    }
    if (g_agassi_hovered_cs &&
        fx >= cs_x0 + 828.0f * sy && fx <= cs_x0 + 1451.0f * sy &&
        fy >= 854.0f * sy && fy <= 888.0f * sy) {
        toggle_agassi_skin();
        return 1;
    }
    if (fx >= cs_x0 + 828.0f * sy && fx <= cs_x0 + 1451.0f * sy &&
        fy >= 894.0f * sy && fy <= 926.0f * sy) {
        toggle_weapon_mode();
        return 1;
    }
    return 0;
}

static int s_entry_confirmed = 0;
static int __thiscall hk_FPPlayerEntry_IsReady(void *self) {
    if (!self) return 0;
    static int s_isready_logged = 0;
    char *esi = *(char **)((char *)self + 0x1c);
    if (s_isready_logged < 5) {
        s_isready_logged++;
        log_msg("[VT4-Mod] FPPlayerEntry::IsReady called #%d: self=%p esi=%p esi[0x18]=%d esi[0x10]=%d",
                s_isready_logged, self, esi,
                (esi && (uintptr_t)esi > 0x10000) ? (int)esi[0x18] : -1,
                (esi && (uintptr_t)esi > 0x10000) ? (int)esi[0x10] : -1);
    }
    WORD xb = 0;
    xinput_get_p1(NULL, NULL, &xb);
    if (is_key_down(VK_RETURN) || is_key_down(VK_SPACE) || is_key_down('C') || ((xb & (0x1000 | 0x0010)) != 0)) {
        s_entry_confirmed = 1;
        log_msg("[VT4-Mod] Player confirmed position on court -> advancing to character select!");
    }
    if (esi && (uintptr_t)esi > 0x10000) {
        if (s_entry_confirmed || esi[0x18] != 0) {
            apply_exhibition_rule_preset();
            if (*(int *)(esi + 0x30) < 1) {
                *(int *)(esi + 0x30) = 2;
                *(int *)(esi + 0x34) = 0;
                *(uint8_t *)(esi + 0x61) = 0;
                log_msg("[VT4-Mod] FPPlayerEntry::IsReady assigned Human P1 (state=2, user=0, cpu=0) esi=%p", esi);
            }
            return 1;
        }
    } else if (s_entry_confirmed) {
        return 1;
    }
    return 0;
}

typedef void (__thiscall *FPCharaSelect_Update_t)(void *self);
static FPCharaSelect_Update_t g_real_charaselect_update = (FPCharaSelect_Update_t)0x005e1340;

static int g_cs_p_slots[2] = { -1, -1 };

static void __thiscall hk_FPCharaSelect_Update(void *self) {
    if (!self) return;
    s_entry_confirmed = 0;
    g_pCharaSelect = self;
    g_chara_select_frames = 30;
    g_chara_select_ticks++;

    if (g_has_custom_roster && !g_menu_visible && !g_netplay_menu_visible) {
        WORD xb = 0;
        static WORD s_prev_cs_lr = 0;
        xinput_get_p1(NULL, NULL, &xb);
        if ((xb & 0x0100) && !(s_prev_cs_lr & 0x0100)) {
            switch_roster_page(-1);
        }
        if ((xb & 0x0200) && !(s_prev_cs_lr & 0x0200)) {
            switch_roster_page(1);
        }
        s_prev_cs_lr = xb;
    }

    static int s_logged_cs = 0;
    if (s_logged_cs++ < 5 || (s_logged_cs % 180) == 0) {
        log_msg("[VT4-Mod] FPCharaSelect_Update frame %u: self=%p", g_present_calls, self);
    }

    void *grid = *(void **)((char *)self + 0x1c);
    static void *s_last_cs_grid = NULL;
    if (grid) {
        memset((uint8_t *)grid + 0x12c, 0, 24);
        if (grid != s_last_cs_grid) {
            s_last_cs_grid = grid;
            memcpy((void *)0x007c5f6c, g_roster_pages[g_current_roster_page], 24);
            g_roster_page_dirty = 1;
        }
    }

    if (g_roster_page_dirty && grid) {
        g_roster_page_dirty = 0;
        if (*(void **)((char *)self + 4)) {
            typedef void (__thiscall *InitGridCardLabels_t)(void *cs_self);
            InitGridCardLabels_t init_labels = (InitGridCardLabels_t)0x005e0080;
            init_labels(self);
        }

        memset((uint8_t *)grid + 0x158, 0xFF, 24 * 4);
        typedef void (__thiscall *UpdateGridCards_t)(void *grid_self);
        UpdateGridCards_t update_cards = (UpdateGridCards_t)0x005df1b0;
        update_cards(grid);

        typedef void (__thiscall *UpdateDisplay_t)(void *grid_self, int player_idx);
        typedef void (__thiscall *SetPlayerCharacter_t)(void *grid_self, int player_idx);
        UpdateDisplay_t update_disp = (UpdateDisplay_t)0x005df5d0;
        SetPlayerCharacter_t set_player_char = (SetPlayerCharacter_t)0x005e03b0;
        for (int i = 0; i < 4; i++) {
            char *pi = (char *)grid + 0x0c + i * 0x48;
            if (pi[0x08] == 0 || *(int *)pi == 8 || *(int *)(pi + 0x20) != 1) {
                continue;
            }
            int col = *(int *)(pi + 0x0c);
            int row = *(int *)(pi + 0x10);
            int slot = row * 3 + col;
            if (slot >= 0 && slot < 21) {
                uint8_t new_id = g_roster_pages[g_current_roster_page][slot];
                *(int *)(pi + 0x14) = new_id;
                log_msg("[VT4-Mod] Page flip: Player %d slot %d (col=%d, row=%d) -> char ID %u",
                        i, slot, col, row, new_id);
                set_player_char(grid, i);
                update_disp(grid, i);
            }
        }
    }

    // Force reload of Agassi's 2D VR portrait (photo_L/S) when skin toggles in CharaSelect
    if (g_agassi_skin_dirty && grid) {
        g_agassi_skin_dirty = 0;
        typedef void (__thiscall *UpdateDisplay_t)(void *grid_self, int player_idx);
        typedef void (__thiscall *SetPlayerCharacter_t)(void *grid_self, int player_idx);
        UpdateDisplay_t update_disp = (UpdateDisplay_t)0x005df5d0;
        SetPlayerCharacter_t set_player_char = (SetPlayerCharacter_t)0x005e03b0;
        const uint8_t *active_slots = (const uint8_t *)0x007c5f6c;
        for (int i = 0; i < 4; i++) {
            char *pi = (char *)grid + 0x0c + i * 0x48;
            if (pi[0x08] == 0 || *(int *)pi == 8) continue;
            int col = *(int *)(pi + 0x0c);
            int row = *(int *)(pi + 0x10);
            int slot = row * 3 + col;
            if ((slot >= 0 && slot < 21 && active_slots[slot] == 29) || *(int *)(pi + 0x14) == 29) {
                *(int *)(pi + 0x14) = 29;
                set_player_char(grid, i);
                update_disp(grid, i);
                log_msg("[VT4-Mod] Refreshed Agassi VR portrait for player %d (skin=%d)", i, g_agassi_skin);
            }
        }
    }

    if (g_real_charaselect_update) {
        g_real_charaselect_update(self);
    }

    // Safely snapshot live P1/P2 grid slots while grid is guaranteed alive
    g_cs_p_slots[0] = -1;
    g_cs_p_slots[1] = -1;
    int hov_multi = 0;
    if (grid) {
        const uint8_t *active_slots = (const uint8_t *)0x007c5f6c;
        for (int p = 0; p < 2; p++) {
            char *pi = (char *)grid + 0x0c + p * 0x48;
            if (pi[0x08] != 0 && *(int *)pi != 8) {
                int col = *(int *)(pi + 0x0c);
                int row = *(int *)(pi + 0x10);
                int sl = row * 3 + col;
                if (col >= 0 && col < 3 && row >= 0 && row < 7 && sl >= 0 && sl < 21) {
                    g_cs_p_slots[p] = sl;
                    if (active_slots[sl] == 29) hov_multi = 1;
                }
                if (*(int *)(pi + 0x14) == 29) hov_multi = 1;
            }
        }
    }
    g_agassi_hovered_cs = hov_multi;
}

static void *create_text_texture(void *dev, const char *text, int w, int h, int font_px, int bold, DWORD rgb_color) {
    if (!dev || !text) return NULL;

    BITMAPINFO bmi;
    memset(&bmi, 0, sizeof(bmi));
    bmi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    bmi.bmiHeader.biWidth = w;
    bmi.bmiHeader.biHeight = -h; // top-down
    bmi.bmiHeader.biPlanes = 1;
    bmi.bmiHeader.biBitCount = 32;
    bmi.bmiHeader.biCompression = BI_RGB;

    void *dib_bits = NULL;
    HDC hdc = CreateCompatibleDC(NULL);
    if (!hdc) return NULL;
    HBITMAP hbmp = CreateDIBSection(hdc, &bmi, DIB_RGB_COLORS, &dib_bits, NULL, 0);
    if (!hbmp || !dib_bits) {
        if (hbmp) DeleteObject(hbmp);
        DeleteDC(hdc);
        return NULL;
    }

    HGDIOBJ old_bmp = SelectObject(hdc, hbmp);
    memset(dib_bits, 0, (size_t)w * (size_t)h * 4);

    HFONT hfont = CreateFontA(-font_px, 0, 0, 0, bold ? FW_BOLD : FW_SEMIBOLD, FALSE, FALSE, FALSE,
                              DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
                              ANTIALIASED_QUALITY, DEFAULT_PITCH | FF_DONTCARE, "Arial");
    HGDIOBJ old_font = hfont ? SelectObject(hdc, hfont) : NULL;
    SetBkMode(hdc, TRANSPARENT);
    SetTextColor(hdc, RGB(255, 255, 255));
    RECT rc = { 0, 0, w, h };
    wchar_t wbuf[256];
    int wn = MultiByteToWideChar(CP_UTF8, 0, text, -1, wbuf, 256);
    if (wn > 0) {
        DrawTextW(hdc, wbuf, -1, &rc, DT_CENTER | DT_VCENTER | DT_SINGLELINE | DT_NOPREFIX);
    } else {
        DrawTextA(hdc, text, -1, &rc, DT_CENTER | DT_VCENTER | DT_SINGLELINE | DT_NOPREFIX);
    }
    GdiFlush();

    if (old_font) SelectObject(hdc, old_font);
    if (hfont) DeleteObject(hfont);
    SelectObject(hdc, old_bmp);

    void *tex = NULL;
    void **vtbl = *(void ***)dev;
    typedef HRESULT (__stdcall *CreateTexture_t)(void *, UINT, UINT, UINT, DWORD, int, int, void **, void **);
    CreateTexture_t create_tex = (CreateTexture_t)vtbl[23];
    HRESULT hr_ct = create_tex ? create_tex(dev, (UINT)w, (UINT)h, 1, 0x200 /* D3DUSAGE_DYNAMIC */, 21 /* D3DFMT_A8R8G8B8 */, 0 /* D3DPOOL_DEFAULT */, &tex, NULL) : -1;
    uint32_t max_a = 0;
    if (hr_ct >= 0 && tex) {
        typedef struct { INT Pitch; void *pBits; } D3DLOCKED_RECT_Mod;
        void **tvtbl = *(void ***)tex;
        typedef HRESULT (__stdcall *LockRect_t)(void *, UINT, D3DLOCKED_RECT_Mod *, const RECT *, DWORD);
        typedef HRESULT (__stdcall *UnlockRect_t)(void *, UINT);
        LockRect_t lock_fn = (LockRect_t)tvtbl[19];
        UnlockRect_t unlock_fn = (UnlockRect_t)tvtbl[20];
        D3DLOCKED_RECT_Mod lr;
        if (lock_fn && lock_fn(tex, 0, &lr, NULL, 0x2000 /* D3DLOCK_DISCARD */) >= 0 && lr.pBits) {
            uint32_t base_rgb = rgb_color & 0x00FFFFFF;
            for (int y = 0; y < h; y++) {
                uint32_t *src = (uint32_t *)dib_bits + y * w;
                uint32_t *dst = (uint32_t *)((uint8_t *)lr.pBits + y * lr.Pitch);
                for (int x = 0; x < w; x++) {
                    uint32_t px = src[x];
                    uint32_t r = (px >> 16) & 0xFF;
                    uint32_t g = (px >> 8) & 0xFF;
                    uint32_t b = px & 0xFF;
                    uint32_t a = r > g ? (r > b ? r : b) : (g > b ? g : b);
                    if (a > max_a) max_a = a;
                    dst[x] = (a << 24) | base_rgb;
                }
            }
            if (unlock_fn) unlock_fn(tex, 0);
        }
    }
    log_msg("[VT4-Mod] create_text_texture('%s'): tex=%p hr=0x%08lx max_a=%u", text, tex, (unsigned long)hr_ct, max_a);

    DeleteObject(hbmp);
    DeleteDC(hdc);
    return tex;
}

static void *g_pTexPillLeft = NULL;
static void *g_pTexPillRight = NULL;
static void *g_pTexHeaderPage[NUM_ROSTER_PAGES] = { NULL };
static void *g_pTexSkinAg91 = NULL;
static void *g_pTexSkinAg06 = NULL;
static void *g_pTexWeaponPill[4] = { NULL };
static void *g_pEyeTex[MAX_ROSTER_PLAYERS] = { NULL };
static void *g_pEyeTexAg91 = NULL;
static void *g_pCardNameTex[MAX_ROSTER_PLAYERS] = { NULL };
static void *g_pCardNameShadowTex[MAX_ROSTER_PLAYERS] = { NULL };
static void *g_pTexBadgeP1 = NULL;
static void *g_pTexBadgeP2 = NULL;

static void init_roster_card_textures(void *dev) {
    static int s_eye_loaded = 0;
    if (!s_eye_loaded) {
        s_eye_loaded = 1;
        if (!g_d3dx_createtexture) {
            HMODULE hD3DX = get_d3dx9_43();
            if (hD3DX) g_d3dx_createtexture = (D3DXCreateTextureFromFileA_t)GetProcAddress(hD3DX, "D3DXCreateTextureFromFileA");
        }
        if (g_d3dx_createtexture) {
            char eye_path[MAX_PATH];
            int ok = 0;
            for (int id = 0; id < MAX_ROSTER_PLAYERS; id++) {
                snprintf(eye_path, sizeof(eye_path), "%s\\archive\\HIGH\\Frontend\\VR\\photo_eye\\%d.dds", g_game_dir, id);
                if (SUCCEEDED(g_d3dx_createtexture(dev, eye_path, &g_pEyeTex[id])) && g_pEyeTex[id]) ok++;
            }
            snprintf(eye_path, sizeof(eye_path), "%s\\archive\\HIGH\\Frontend\\VR\\photo_eye\\29_91.dds", g_game_dir);
            if (!SUCCEEDED(g_d3dx_createtexture(dev, eye_path, &g_pEyeTexAg91))) g_pEyeTexAg91 = NULL;
            log_msg("[VT4-Mod] Loaded %d/%d CharaSelect eye-strip textures (ag91=%p)", ok, MAX_ROSTER_PLAYERS, g_pEyeTexAg91);
        }
    }

    static int s_names_loaded = 0;
    if (!s_names_loaded && g_tr_common_sto) {
        s_names_loaded = 1;
        g_pTexBadgeP1 = create_text_texture(dev, "1", 22, 22, 15, 1, 0xFFFFFF);
        g_pTexBadgeP2 = create_text_texture(dev, "2", 22, 22, 15, 1, 0xFFFFFF);
        for (int id = 0; id < MAX_ROSTER_PLAYERS; id++) {
            const char *nm = hk_StoLookup(g_tr_common_sto, NULL, 2, id);
            if (!nm || !nm[0]) nm = "?";
            int is_man = hk_PlayerDB_IsMan(id);
            DWORD fg = is_man ? 0xFFF2F6FC : 0xFFFFCFE6;
            g_pCardNameTex[id] = create_text_texture(dev, nm, 184, 34, 19, 1, fg);
            g_pCardNameShadowTex[id] = create_text_texture(dev, nm, 184, 34, 19, 1, 0x010101);
        }
        log_msg("[VT4-Mod] Cached %d CharaSelect card surname textures", MAX_ROSTER_PLAYERS);
    }
}

static void render_roster_pagination_hud(void *dev) {
    if (!g_has_custom_roster) return;
    if (!dev) dev = g_d3d_device;
    if (!dev || !*(void ***)dev || g_chara_select_frames < 28 || g_menu_visible) return;

    if (!begin_overlay_state(dev)) return;

    void **dev_vtbl = *(void ***)dev;
    typedef HRESULT (__stdcall *SetViewport_t)(void *, const void *);
    SetViewport_t set_vp = (SetViewport_t)dev_vtbl[47];

    uint32_t full_vp[6] = { 0, 0, g_cfg_width, g_cfg_height, 0, 0x3f800000 };
    if (set_vp) set_vp(dev, full_vp);

    static int s_tex_init_done = 0;
    if (!s_tex_init_done) {
        s_tex_init_done = 1;
        g_pTexPillLeft  = create_text_texture(dev, "< Q / LB", 96, 36, 17, 1, 0xFFFFFF);
        g_pTexPillRight = create_text_texture(dev, "E / RB >", 96, 36, 17, 1, 0xFFFFFF);
        g_pTexHeaderPage[0] = create_text_texture(dev, "PAGINA 1/4: ACTUAL & NEXT-GEN (2015-2026)", 412, 36, 16, 1, 0xFFFFFF);
        g_pTexHeaderPage[1] = create_text_texture(dev, "PAGINA 2/4: ERA DORADA (2000s - 2010s)", 412, 36, 17, 1, 0x00E5FF);
        g_pTexHeaderPage[2] = create_text_texture(dev, "PAGINA 3/4: LEYENDAS 90s & WTA CLASICA", 412, 36, 17, 1, 0xFFA726);
        g_pTexHeaderPage[3] = create_text_texture(dev, "PAGINA 4/4: PIONEROS 60s-80s & VT4", 412, 36, 17, 1, 0xFFD54F);
        g_pTexSkinAg91  = create_text_texture(dev, "[F] SKIN AGASSI: 1991 MELENA RUBIA + CINTA", 623, 34, 16, 1, 0xFF70C8);
        g_pTexSkinAg06  = create_text_texture(dev, "[F] SKIN AGASSI: 2006 CALVO + PERILLA", 623, 34, 16, 1, 0xD8E2EE);
        g_pTexWeaponPill[0] = create_text_texture(dev, "[R] ARMA EE-3: RAQUETA OFICIAL (NORMAL)", 623, 32, 15, 1, 0xD0DCE8);
        g_pTexWeaponPill[1] = create_text_texture(dev, "[R] ARMA EE-3: RAQUETA DE MADERA (ANOS 70)", 623, 32, 15, 1, 0xFFD080);
        g_pTexWeaponPill[2] = create_text_texture(dev, "[R] ARMA EE-3: SARTEN METALICA (MODO RODDICK)", 623, 32, 15, 1, 0x70E8FF);
        g_pTexWeaponPill[3] = create_text_texture(dev, "[R] ARMA EE-3: BAGUETTE GIGANTE", 623, 32, 15, 1, 0xFFE66D);
    }
    init_roster_card_textures(dev);

    float sy = (float)g_cfg_height / 1080.0f;
    float sx = sy;
    float cs_x0 = (float)g_cfg_width * 0.5f - 960.0f * sy;

    // Render all 21 grid cards dynamically with each player's own cropped eye-strip & crisp surname
    int p_slots[2] = { g_cs_p_slots[0], g_cs_p_slots[1] };

    const uint8_t *active_slots = (const uint8_t *)0x007c5f6c;
    for (int slot = 0; slot < 21; slot++) {
        int col = slot % 3;
        int row = slot / 3;
        float x1 = cs_x0 + (828.0f + col * 211.5f) * sy;
        float y1 = (235.0f + row * 76.285f) * sy;
        float x2 = x1 + 200.0f * sx;
        float y2 = y1 + 71.0f * sy;
        uint8_t cid = active_slots[slot];
        if (cid >= MAX_ROSTER_PLAYERS) cid = 0;

        int is_p1 = (p_slots[0] == slot);
        int is_p2 = (p_slots[1] == slot);
        int is_hov = is_p1 || is_p2;

        void *eye_tex = (cid == 29 && g_agassi_skin == 0 && g_pEyeTexAg91) ? g_pEyeTexAg91 : g_pEyeTex[cid];
        if (eye_tex) {
            draw_textured_quad(dev, eye_tex, x1, y1, x2, y2, is_hov ? 0xFFFFFFFF : 0xFFD4DAE4);
        } else {
            draw_screen_quad(dev, x1, y1, x2, y2, 0xFF282D38);
        }

        // Subtle gold left accent stripe & dark bottom edge
        draw_screen_quad(dev, x1, y1, x1 + 3.0f * sx, y2, 0xB0D8AF48);
        draw_screen_quad(dev, x1, y2 - 2.0f * sy, x2, y2, 0x8010141C);

        // Selection cursor borders (Blue for P1, Magenta-Pink for P2)
        if (is_p1 || is_p2) {
            DWORD bcol = is_p1 ? 0xFF38B6FF : 0xFFFF4090;
            float bw = 3.0f * sx, bh = 3.0f * sy;
            draw_screen_quad(dev, x1, y1, x2, y1 + bh, bcol);
            draw_screen_quad(dev, x1, y2 - bh, x2, y2, bcol);
            draw_screen_quad(dev, x1, y1, x1 + bw, y2, bcol);
            draw_screen_quad(dev, x2 - bw, y1, x2, y2, bcol);
            if (is_p1) {
                draw_screen_quad(dev, x1 + 3.0f * sx, y1 + 3.0f * sy, x1 + 25.0f * sx, y1 + 25.0f * sy, 0xE61E88E5);
                if (g_pTexBadgeP1) draw_textured_quad(dev, g_pTexBadgeP1, x1 + 3.0f * sx, y1 + 3.0f * sy, x1 + 25.0f * sx, y1 + 25.0f * sy, 0xFFFFFFFF);
            }
            if (is_p2) {
                float bx = is_p1 ? (x1 + 27.0f * sx) : (x1 + 3.0f * sx);
                draw_screen_quad(dev, bx, y1 + 3.0f * sy, bx + 22.0f * sx, y1 + 25.0f * sy, 0xE6D81B60);
                if (g_pTexBadgeP2) draw_textured_quad(dev, g_pTexBadgeP2, bx, y1 + 3.0f * sy, bx + 22.0f * sx, y1 + 25.0f * sy, 0xFFFFFFFF);
            }
        } else {
            draw_screen_quad(dev, x1, y1, x2, y1 + 1.0f * sy, 0x55FFFFFF);
        }

        // Centered surname with dark outline shadow
        float tx1 = x1 + 8.0f * sx, tx2 = x2 - 8.0f * sx;
        float ty1 = y1 + 20.0f * sy, ty2 = y1 + 54.0f * sy;
        if (g_pCardNameShadowTex[cid]) {
            draw_textured_quad(dev, g_pCardNameShadowTex[cid], tx1 + 1.5f * sx, ty1 + 1.5f * sy, tx2 + 1.5f * sx, ty2 + 1.5f * sy, 0xDDFFFFFF);
        }
        if (g_pCardNameTex[cid]) {
            draw_textured_quad(dev, g_pCardNameTex[cid], tx1, ty1, tx2, ty2, is_hov ? 0xFFFFE57F : 0xFFFFFFFF);
        }
    }

    float pill_w = 96.0f * sx, pill_h = 36.0f * sy;
    float l_x = cs_x0 + 830.0f * sy, l_y = 172.0f * sy;
    float r_x = cs_x0 + 1354.0f * sy, r_y = 172.0f * sy;

    g_arr_left_rc[0] = l_x; g_arr_left_rc[1] = l_y;
    g_arr_left_rc[2] = l_x + pill_w; g_arr_left_rc[3] = l_y + pill_h;

    g_arr_right_rc[0] = r_x; g_arr_right_rc[1] = r_y;
    g_arr_right_rc[2] = r_x + pill_w; g_arr_right_rc[3] = r_y + pill_h;

    // Clean sleek dark pills flanking the header bar (zero overlap with portraits or cards)
    draw_screen_quad(dev, l_x, l_y, l_x + pill_w, l_y + pill_h, 0xCC0A1424);
    draw_screen_quad(dev, l_x, l_y, l_x + pill_w, l_y + 2.0f * sy, 0xFF00E5FF);
    draw_screen_quad(dev, l_x, l_y + pill_h - 2.0f * sy, l_x + pill_w, l_y + pill_h, 0xFF00E5FF);

    draw_screen_quad(dev, r_x, r_y, r_x + pill_w, r_y + pill_h, 0xCC0A1424);
    draw_screen_quad(dev, r_x, r_y, r_x + pill_w, r_y + 2.0f * sy, 0xFF00E5FF);
    draw_screen_quad(dev, r_x, r_y + pill_h - 2.0f * sy, r_x + pill_w, r_y + pill_h, 0xFF00E5FF);

    // Subtle header bar above grid (grid is x=830..1450, y=218..780)
    float hdr_x1 = cs_x0 + 934.0f * sy, hdr_y1 = 172.0f * sy, hdr_x2 = cs_x0 + 1346.0f * sy, hdr_y2 = 208.0f * sy;
    draw_screen_quad(dev, hdr_x1, hdr_y1, hdr_x2, hdr_y2, 0xCC0A1424);
    static const DWORD k_page_accents[NUM_ROSTER_PAGES] = { 0xFF4585E5, 0xFF00E5FF, 0xFFFFA726, 0xFFFFD54F };
    int p_idx = (g_current_roster_page >= 0 && g_current_roster_page < NUM_ROSTER_PAGES) ? g_current_roster_page : 0;
    draw_screen_quad(dev, hdr_x1, hdr_y2 - 3.0f * sy, hdr_x2, hdr_y2, k_page_accents[p_idx]);

    if (g_pTexPillLeft)  draw_textured_quad(dev, g_pTexPillLeft,  l_x, l_y, l_x + pill_w, l_y + pill_h, 0xFFFFFFFF);
    if (g_pTexPillRight) draw_textured_quad(dev, g_pTexPillRight, r_x, r_y, r_x + pill_w, r_y + pill_h, 0xFFFFFFFF);
    void *hdr_tex = g_pTexHeaderPage[p_idx];
    if (hdr_tex) draw_textured_quad(dev, hdr_tex, hdr_x1, hdr_y1, hdr_x2, hdr_y2, 0xFFFFFFFF);

    int has_multi_hovered = 0;
    for (int p = 0; p < 2; p++) {
        if (p_slots[p] >= 0 && p_slots[p] < 21 && active_slots[p_slots[p]] == 29) {
            has_multi_hovered = 1;
        }
    }
    if (has_multi_hovered) {
        float sk_x1 = cs_x0 + 828.0f * sy, sk_x2 = cs_x0 + 1451.0f * sy, sk_y1 = 854.0f * sy, sk_y2 = 888.0f * sy;
        draw_screen_quad(dev, sk_x1, sk_y1, sk_x2, sk_y2, 0xCC0A1424);
        DWORD sk_acc = g_agassi_skin ? 0xFFD0D8E4 : 0xFFFF40A8;
        draw_screen_quad(dev, sk_x1, sk_y2 - 3.0f * sy, sk_x2, sk_y2, sk_acc);
        void *sk_tex = g_agassi_skin ? g_pTexSkinAg06 : g_pTexSkinAg91;
        if (sk_tex) draw_textured_quad(dev, sk_tex, sk_x1, sk_y1, sk_x2, sk_y2, 0xFFFFFFFF);
    }

    {
        float wp_x1 = cs_x0 + 828.0f * sy, wp_x2 = cs_x0 + 1451.0f * sy, wp_y1 = 894.0f * sy, wp_y2 = 926.0f * sy;
        draw_screen_quad(dev, wp_x1, wp_y1, wp_x2, wp_y2, 0xC00A1424);
        static const DWORD k_wp_acc[4] = { 0xFF566880, 0xFFFF9F40, 0xFF38D4FF, 0xFFFFE040 };
        uint32_t wm = (g_cfg_weapon_mode < 4u) ? g_cfg_weapon_mode : 0u;
        draw_screen_quad(dev, wp_x1, wp_y2 - 2.5f * sy, wp_x2, wp_y2, k_wp_acc[wm]);
        if (g_pTexWeaponPill[wm]) draw_textured_quad(dev, g_pTexWeaponPill[wm], wp_x1, wp_y1, wp_x2, wp_y2, 0xFFFFFFFF);
    }

    end_overlay_state(dev);
    ensure_d3d9_device_hooks(dev);
}

// ----------------------------------------------------------------------------
// 3D Pipeline & OptionMode Hooks
// ----------------------------------------------------------------------------
typedef struct {
    uint32_t width;
    uint32_t height;
    uint32_t msaa_samples;
    uint32_t unk_0c;
    uint32_t bloom_w;
    uint32_t bloom_h;
    uint32_t shadow_w;
    uint32_t shadow_h;
} PipelineSettings;

static void __fastcall hk_Renderer_CalcPipelineSettings(PipelineSettings *settings, void *edx, int flag) {
    if (!settings) return;
    settings->width = g_cfg_width;
    settings->height = g_cfg_height;
    settings->msaa_samples = g_cfg_antialiasing;
    settings->unk_0c = 4;
    settings->bloom_w = perf_get_bloom_w();
    settings->bloom_h = perf_get_bloom_h();
    settings->shadow_w = perf_get_shadow_size();
    settings->shadow_h = perf_get_shadow_size();

    *(uint32_t *)0x00a75d24 = g_cfg_width;
    *(uint32_t *)0x00a75d28 = g_cfg_height;
    *(uint32_t *)0x00a75d7c = g_cfg_antialiasing;

    log_msg("[VT4-Mod] hk_Renderer_CalcPipelineSettings: 3D=%ux%u MSAA=%u Shadows=%ux%u Bloom=%ux%u (Profile=%u)",
            settings->width, settings->height, settings->msaa_samples,
            settings->shadow_w, settings->shadow_h, settings->bloom_w, settings->bloom_h, g_cfg_perf_profile);
}

typedef void (__thiscall *OptionMode_Update_t)(void *);
static OptionMode_Update_t g_real_optionmode_update = NULL;
static OptionMode_Update_t g_real_opt_add_submenus = NULL;
static OptionMode_Update_t g_real_opt_inner_update = NULL;
typedef void (__thiscall *OptEnterSubmenu_t)(void *, const char *);
static OptEnterSubmenu_t g_real_opt_enter_submenu = NULL;
typedef void (__thiscall *FPSubMenu_SetSel_t)(void *, int);
static FPSubMenu_SetSel_t g_real_fpsubmenu_setsel = NULL;

static void __thiscall hk_OptionMode_AddSubmenus(void *this_ptr) {
    if (g_real_opt_add_submenus) {
        g_real_opt_add_submenus(this_ptr);
    }
    if (this_ptr) {
        void *parent_seq = *(void **)((char *)this_ptr + 4);
        void *carousel = (void *)((char *)this_ptr + 8);
        typedef void (__thiscall *AddSeqItem_t)(void *, const char *, void *, int);
        ((AddSeqItem_t)0x00634e80)(carousel, "LegendsHD", parent_seq, 1);
        log_msg("[VT4-Mod] OptionMode: injected native row 3 ('LegendsHD' / GRAFICOS HD Y LEGENDS)");
    }
}

static void __thiscall hk_FPSubMenu_SetSel(void *this_ptr, int sel) {
    if (g_opt_mode_ptr && *(void **)((char *)g_opt_mode_ptr + 0x8c) == this_ptr) {
        g_opt_root_sel = sel;
    }
    if (g_real_fpsubmenu_setsel) {
        g_real_fpsubmenu_setsel(this_ptr, sel);
    }
}

static void __thiscall hk_OptionMode_EnterSubmenu(void *this_ptr, const char *name) {
    if (name && strcmp(name, "LegendsHD") == 0) {
        g_opt_legends_sub = 1;
        g_menu_visible = 1;
        g_menu_opened_by_optionmode = 1;
        g_mod_menu_open_frame = g_present_calls;
        log_msg("[VT4-Mod] Entered native OptionMode submenu -> GRAFICOS HD Y LEGENDS");
        return;
    }
    if (g_real_opt_enter_submenu) {
        g_real_opt_enter_submenu(this_ptr, name);
    }
}

static void __thiscall hk_OptionMode_InnerUpdate(void *this_ptr) {
    g_opt_mode_ptr = this_ptr;
    g_opt_root_last_frame = g_present_calls;
    if (g_opt_legends_sub) {
        if (!g_menu_visible) {
            g_opt_legends_sub = 0;
        } else {
            return;
        }
    }
    if (g_real_opt_inner_update) {
        g_real_opt_inner_update(this_ptr);
    }
}

static void __thiscall hk_OptionMode_Update(void *this_ptr) {
    if (!g_option_mode_active) {
        g_option_mode_active = 1;
        log_msg("[VT4-Mod] Entered OptionMode (Ajustes) natively (TAB/F2 optional overlay)");
    }
    g_option_mode_last_frame = g_present_calls;
    if (g_real_optionmode_update) {
        g_real_optionmode_update(this_ptr);
    }
}

// ----------------------------------------------------------------------------
// Direct3D 9 Interceptions for Native 3D RenderTargets & 2048 Shadows
// ----------------------------------------------------------------------------
typedef HRESULT (__stdcall *Reset_t)(void *, void *);
static Reset_t g_real_reset = NULL;
static HRESULT __stdcall hk_Reset(void *dev, void *pp) {
    g_vp_is_full_hd = 0;
    g_cached_rt = NULL;
    g_sampler_dirty = 5;
    if (g_pFont) {
        void **vtbl = *(void ***)g_pFont;
        typedef ULONG (__stdcall *Rel_t)(void *);
        ((Rel_t)vtbl[2])(g_pFont);
        g_pFont = NULL;
    }
    if (g_pFontTitle) {
        void **vtbl = *(void ***)g_pFontTitle;
        typedef ULONG (__stdcall *Rel_t)(void *);
        ((Rel_t)vtbl[2])(g_pFontTitle);
        g_pFontTitle = NULL;
    }
    if (g_pSprite) {
        void **vtbl = *(void ***)g_pSprite;
        typedef ULONG (__stdcall *Rel_t)(void *);
        ((Rel_t)vtbl[2])(g_pSprite);
        g_pSprite = NULL;
    }
    if (g_pOverlaySB) {
        void **vtbl = *(void ***)g_pOverlaySB;
        typedef ULONG (__stdcall *Rel_t)(void *);
        ((Rel_t)vtbl[2])(g_pOverlaySB);
        g_pOverlaySB = NULL;
    }
    ngfx_on_reset();
    return g_real_reset(dev, pp);
}

typedef HRESULT (__stdcall *CreateRenderTarget_t)(
    void *dev, UINT Width, UINT Height, DWORD Format,
    DWORD MultiSample, DWORD MultisampleQuality,
    BOOL Lockable, void **ppSurface, HANDLE *pSharedHandle);
static CreateRenderTarget_t g_real_createrendertarget = NULL;
static HRESULT __stdcall hk_CreateRenderTarget(
    void *dev, UINT Width, UINT Height, DWORD Format,
    DWORD MultiSample, DWORD MultisampleQuality,
    BOOL Lockable, void **ppSurface, HANDLE *pSharedHandle)
{
    UINT orig_w = Width, orig_h = Height;
    log_msg("[VT4-Mod] hk_CreateRenderTarget: req=%ux%u fmt=%lu msaa=%lu", orig_w, orig_h, (unsigned long)Format, (unsigned long)MultiSample);
    if ((Width == 640 && Height == 480) || (Width == 1280 && Height == 720)) {
        Width = g_cfg_width;
        Height = g_cfg_height;
        if (g_cfg_antialiasing > 0) {
            MultiSample = g_cfg_antialiasing;
            MultisampleQuality = 0;
        }
        log_msg("[VT4-Mod] hk_CreateRenderTarget: upscaling 3D target (%ux%u) -> %ux%u (MSAA=%u)",
                orig_w, orig_h, Width, Height, MultiSample);
    }

    HRESULT hr = g_real_createrendertarget(dev, Width, Height, Format, MultiSample, MultisampleQuality, Lockable, ppSurface, pSharedHandle);
    if (hr < 0 && MultiSample > 0) {
        log_msg("[VT4-Mod] hk_CreateRenderTarget: fallback without MSAA (hr=0x%08lx)", (unsigned long)hr);
        hr = g_real_createrendertarget(dev, Width, Height, Format, 0, 0, Lockable, ppSurface, pSharedHandle);
    }
    return hr;
}

typedef HRESULT (__stdcall *CreateDepthStencilSurface_t)(
    void *dev, UINT Width, UINT Height, DWORD Format,
    DWORD MultiSample, DWORD MultisampleQuality,
    BOOL Discard, void **ppSurface, HANDLE *pSharedHandle);
static CreateDepthStencilSurface_t g_real_createdepthstencilsurface = NULL;
static HRESULT __stdcall hk_CreateDepthStencilSurface(
    void *dev, UINT Width, UINT Height, DWORD Format,
    DWORD MultiSample, DWORD MultisampleQuality,
    BOOL Discard, void **ppSurface, HANDLE *pSharedHandle)
{
    UINT orig_w = Width, orig_h = Height;
    log_msg("[VT4-Mod] hk_CreateDepthStencilSurface: req=%ux%u fmt=%lu msaa=%lu", orig_w, orig_h, (unsigned long)Format, (unsigned long)MultiSample);
    if ((Width == 640 && Height == 480) || (Width == 1280 && Height == 720) ||
        (Width == g_cfg_width && Height == g_cfg_height)) {
        Width = g_cfg_width;
        Height = g_cfg_height;
        if (g_cfg_antialiasing > 0) {
            MultiSample = g_cfg_antialiasing;
            MultisampleQuality = 0;
        }
        log_msg("[VT4-Mod] hk_CreateDepthStencilSurface: depth buffer (%ux%u) -> %ux%u (MSAA=%u)",
                orig_w, orig_h, Width, Height, MultiSample);
    }

    HRESULT hr = g_real_createdepthstencilsurface(dev, Width, Height, Format, MultiSample, MultisampleQuality, Discard, ppSurface, pSharedHandle);
    if (hr < 0 && MultiSample > 0) {
        hr = g_real_createdepthstencilsurface(dev, Width, Height, Format, 0, 0, Discard, ppSurface, pSharedHandle);
    }
    return hr;
}

#ifndef D3DUSAGE_RENDERTARGET
#define D3DUSAGE_RENDERTARGET 0x00000001L
#endif
#ifndef D3DUSAGE_DEPTHSTENCIL
#define D3DUSAGE_DEPTHSTENCIL 0x00000002L
#endif

typedef HRESULT (__stdcall *CreateTexture_t)(
    void *dev, UINT Width, UINT Height, UINT Levels,
    DWORD Usage, DWORD Format, DWORD Pool,
    void **ppTexture, HANDLE *pSharedHandle);
static CreateTexture_t g_real_createtexture = NULL;
static HRESULT __stdcall hk_CreateTexture(
    void *dev, UINT Width, UINT Height, UINT Levels,
    DWORD Usage, DWORD Format, DWORD Pool,
    void **ppTexture, HANDLE *pSharedHandle)
{
    UINT orig_w = Width, orig_h = Height;
    if (Usage & (D3DUSAGE_RENDERTARGET | D3DUSAGE_DEPTHSTENCIL)) {
        log_msg("[VT4-Mod] hk_CreateTexture (RT/DS): req=%ux%u usage=0x%lx fmt=%lu", orig_w, orig_h, (unsigned long)Usage, (unsigned long)Format);
        if ((Width == 640 && Height == 480) || (Width == 1280 && Height == 720)) {
            Width = g_cfg_width;
            Height = g_cfg_height;
            log_msg("[VT4-Mod] hk_CreateTexture (RT): upscaling (%ux%u) -> %ux%u", orig_w, orig_h, Width, Height);
        }
    }
    return g_real_createtexture(dev, Width, Height, Levels, Usage, Format, Pool, ppTexture, pSharedHandle);
}

static RECT g_windowed_rect = {0};
static DWORD g_windowed_style = 0;

static void toggle_fullscreen(HWND hwnd) {
    if (!hwnd) hwnd = g_game_hwnd;
    if (!hwnd) return;

    if (!g_is_fullscreen) {
        GetWindowRect(hwnd, &g_windowed_rect);
        g_windowed_style = GetWindowLongA(hwnd, GWL_STYLE);

        int scr_w = GetSystemMetrics(SM_CXSCREEN);
        int scr_h = GetSystemMetrics(SM_CYSCREEN);

        SetWindowLongA(hwnd, GWL_STYLE, WS_POPUP | WS_VISIBLE);
        SetWindowPos(hwnd, HWND_TOP, 0, 0, scr_w, scr_h, SWP_FRAMECHANGED | SWP_SHOWWINDOW);
        ShowWindow(hwnd, SW_SHOWMAXIMIZED);
        UpdateWindow(hwnd);
        SetForegroundWindow(hwnd);

        g_is_fullscreen = 1;
        uintptr_t wm = *(uintptr_t *)0x00a75ad0;
        if (wm) {
            *(uint8_t *)(wm + 0x08) = 1;
        }
        log_msg("[VT4-Mod] Fullscreen enabled: %dx%d (borderless)", scr_w, scr_h);
    } else {
        int w = g_windowed_rect.right - g_windowed_rect.left;
        int h = g_windowed_rect.bottom - g_windowed_rect.top;
        if (w <= 0 || h <= 0) { w = 1296; h = 759; }
        int x = g_windowed_rect.left;
        int y = g_windowed_rect.top;
        if (x < 0 || y < 0) {
            int scr_w = GetSystemMetrics(SM_CXSCREEN);
            int scr_h = GetSystemMetrics(SM_CYSCREEN);
            x = (scr_w > w) ? (scr_w - w) / 2 : 50;
            y = (scr_h > h) ? (scr_h - h) / 2 : 50;
        }

        DWORD style = g_windowed_style ? g_windowed_style : (WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX | WS_VISIBLE);
        SetWindowLongA(hwnd, GWL_STYLE, style);
        SetWindowPos(hwnd, HWND_NOTOPMOST, x, y, w, h, SWP_FRAMECHANGED | SWP_SHOWWINDOW);
        ShowWindow(hwnd, SW_SHOWNORMAL);
        UpdateWindow(hwnd);
        SetForegroundWindow(hwnd);

        g_is_fullscreen = 0;
        uintptr_t wm = *(uintptr_t *)0x00a75ad0;
        if (wm) {
            *(uint8_t *)(wm + 0x08) = 0;
        }
        log_msg("[VT4-Mod] Fullscreen disabled: %dx%d pos=(%d,%d)", w, h, x, y);
    }
}

static int g_screenshot_requested = 0;
static LRESULT CALLBACK hk_GameWndProc(HWND hwnd, UINT uMsg, WPARAM wParam, LPARAM lParam) {
    switch (uMsg) {
        case WM_ACTIVATE: {
            WORD active_state = LOWORD(wParam);
            memset(g_keys_down, 0, sizeof(g_keys_down));
            memset(g_nav_hold, 0, sizeof(g_nav_hold));
            memset(g_btn_hold, 0, sizeof(g_btn_hold));
            uintptr_t wm = *(uintptr_t *)0x00a75ad0;
            if (active_state == WA_INACTIVE) {
                if (wm) {
                    *(uint8_t *)(wm + 0x0A) = 0;
                }
            } else {
                if (wm) {
                    *(uint8_t *)(wm + 0x09) = 1;
                    *(uint8_t *)(wm + 0x0A) = 1;
                    *(uint8_t *)(wm + 0x1D) = 1;
                    *(uint8_t *)(wm + 0x1E) = 0;
                }
                *(uint8_t *)0x00835eb0 = 1;
                *(uint8_t *)0x00835eb1 = 1;
            }
            break;
        }
        case WM_SETFOCUS: {
            memset(g_keys_down, 0, sizeof(g_keys_down));
            memset(g_nav_hold, 0, sizeof(g_nav_hold));
            memset(g_btn_hold, 0, sizeof(g_btn_hold));
            uintptr_t wm = *(uintptr_t *)0x00a75ad0;
            if (wm) {
                *(uint8_t *)(wm + 0x09) = 1;
                *(uint8_t *)(wm + 0x0A) = 1;
                *(uint8_t *)(wm + 0x1D) = 1;
                *(uint8_t *)(wm + 0x1E) = 0;
            }
            *(uint8_t *)0x00835eb0 = 1;
            *(uint8_t *)0x00835eb1 = 1;
            break;
        }
        case WM_KILLFOCUS: {
            memset(g_keys_down, 0, sizeof(g_keys_down));
            memset(g_nav_hold, 0, sizeof(g_nav_hold));
            memset(g_btn_hold, 0, sizeof(g_btn_hold));
            break;
        }
        case WM_SYSCOMMAND: {
            // Intercept SC_KEYMENU so tapping Alt or Alt-Tab never freezes the window into Windows modal menu mode!
            if ((wParam & 0xFFF0) == SC_KEYMENU) {
                return 0;
            }
            break;
        }
        case WM_SYSKEYDOWN: {
            if (wParam == VK_F10) {
                g_screenshot_requested = 1;
                log_msg("[VT4-Mod] Screenshot requested via F10 key (SYSKEYDOWN)");
                return 0;
            }
            if (wParam == VK_RETURN && ((GetKeyState(VK_MENU) & 0x8000) || (GetAsyncKeyState(VK_MENU) & 0x8000))) {
                toggle_fullscreen(hwnd);
                return 0;
            }
            if (wParam < 256) g_keys_down[wParam] = 1;
            break;
        }
        case WM_SYSKEYUP: {
            if (wParam < 256) g_keys_down[wParam] = 0;
            break;
        }
        case WM_KEYDOWN: {
            if (wParam == VK_F10) { // F10 take screenshot
                g_screenshot_requested = 1;
                log_msg("[VT4-Mod] Screenshot requested via F10 key");
                return 0;
            }
            if (wParam == VK_F11) { // F11 toggle
                toggle_fullscreen(hwnd);
                return 0;
            }
            if (wParam == VK_F2) { // F2 toggle graphics options menu
                if (!(lParam & (1 << 30))) {
                    g_netplay_menu_visible = 0;
                    g_menu_visible = !g_menu_visible;
                    if (g_menu_visible) {
                        g_mod_menu_open_frame = g_present_calls;
                    } else {
                        close_legends_settings_menu();
                    }
                    log_msg("[VT4-Mod] F2 pressed: g_menu_visible=%d", g_menu_visible);
                }
                return 0;
            }
            if (wParam == VK_F7) { // F7 toggle Broadcast TV HUD live
                if (!(lParam & (1 << 30))) {
                    g_cfg_broadcast_hud = g_cfg_broadcast_hud ? 0u : 1u;
                    sync_menu_indices_from_cfg();
                    save_vt4_settings();
                    log_msg("[VT4-Mod] [BHUD] F7 toggled BroadcastHUD=%u", g_cfg_broadcast_hud);
                }
                return 0;
            }
            if (wParam == VK_F6) { // F6 toggle Interactive Xbox Touch HUD live
                if (!(lParam & (1 << 30))) {
                    g_tg_auto_hidden_by_xinput = 0;
                    g_cfg_touch_hud = g_cfg_touch_hud ? 0u : 2u;
                    sync_menu_indices_from_cfg();
                    save_vt4_settings();
                    log_msg("[VT4-Mod] [TOUCHHUD] F6 toggled TouchXboxHUD=%u", g_cfg_touch_hud);
                }
                return 0;
            }
            if (wParam == VK_TAB && g_option_mode_active) {
                if (!(lParam & (1 << 30))) {
                    g_netplay_menu_visible = 0;
                    g_menu_visible = !g_menu_visible;
                    if (g_menu_visible) {
                        g_mod_menu_open_frame = g_present_calls;
                    } else {
                        close_legends_settings_menu();
                    }
                    log_msg("[VT4-Mod] TAB in OptionMode: g_menu_visible=%d", g_menu_visible);
                }
                return 0;
            }
            if (g_netplay_menu_visible) {
                int is_repeat = (lParam & (1 << 30)) != 0;
                if (is_repeat && (wParam == VK_RETURN || wParam == VK_SPACE || wParam == VK_ESCAPE)) {
                    return 0;
                }
                if (handle_netplay_menu_input((int)wParam)) {
                    if (wParam < 256) g_keys_down[wParam] = 0;
                    return 0;
                }
                if (wParam < 256) g_keys_down[wParam] = 0;
                return 0;
            }
            if (!g_menu_visible && g_chara_select_frames > 0 && !(lParam & (1 << 30))) {
                if (g_has_custom_roster) {
                    if (wParam == 'Q' || wParam == 'q' || wParam == VK_OEM_4 || wParam == VK_PRIOR) {
                        switch_roster_page(-1);
                        return 0;
                    }
                    if (wParam == 'E' || wParam == 'e' || wParam == VK_OEM_6 || wParam == VK_NEXT) {
                        switch_roster_page(1);
                        return 0;
                    }
                    if ((wParam == 'F' || wParam == 'f') && g_agassi_hovered_cs) {
                        toggle_agassi_skin();
                        return 0;
                    }
                }
                if (wParam == 'R' || wParam == 'r') {
                    toggle_weapon_mode();
                    return 0;
                }
            }
            if (g_menu_visible) {
                int is_repeat = (lParam & (1 << 30)) != 0;
                if (is_repeat && (wParam == VK_RETURN || wParam == VK_SPACE || wParam == VK_ESCAPE || wParam == VK_BACK)) {
                    return 0;
                }
                if (handle_settings_menu_input((int)wParam, NULL)) {
                    if (wParam < 256) g_keys_down[wParam] = 0;
                    return 0;
                }
            }
            if (wParam < 256) g_keys_down[wParam] = 1;
            break;
        }
        case WM_LBUTTONDOWN: {
            if (touch_gamepad_on_wndmsg(hwnd, uMsg, wParam, lParam, g_cfg_touch_hud)) {
                return 0;
            }
            int mx = (short)LOWORD(lParam);
            int my = (short)HIWORD(lParam);
            if (touch_gamepad_should_show(g_cfg_touch_hud) && g_tg_diag_logs < 6u) {
                g_tg_diag_logs++;
                log_msg("[VT4-Mod] [TOUCHHUD] miss WM_LBUTTONDOWN cx=%d cy=%d", mx, my);
            }
            if (check_roster_arrow_click(mx, my)) {
                return 0;
            }
            break;
        }
        case WM_MOUSEMOVE:
        case WM_LBUTTONUP:
        case WM_CAPTURECHANGED:
        case WM_POINTERUPDATE:
        case WM_POINTERDOWN:
        case WM_POINTERUP:
        case WM_POINTERCAPTURECHANGED: {
            if (touch_gamepad_on_wndmsg(hwnd, uMsg, wParam, lParam, g_cfg_touch_hud)) {
                return 0;
            }
            break;
        }
        case WM_RBUTTONDOWN:
        case WM_RBUTTONUP:
        case WM_RBUTTONDBLCLK:
        case WM_XBUTTONDOWN:
        case WM_XBUTTONUP:
        case 0x0319: { /* WM_APPCOMMAND: prevent Winlator two-finger right-click or Android Back gesture from cancelling menus */
            return 0;
        }
        case WM_KEYUP: {
            if (wParam < 256) g_keys_down[wParam] = 0;
            break;
        }
    }
    if (g_orig_wndproc) {
        return CallWindowProcA(g_orig_wndproc, hwnd, uMsg, wParam, lParam);
    }
    return DefWindowProcA(hwnd, uMsg, wParam, lParam);
}

typedef HRESULT (__stdcall *D3DXSaveSurfaceToFileA_t)(const char *, int, void *, const void *, const RECT *);
static D3DXSaveSurfaceToFileA_t g_d3dx_save = NULL;

typedef HRESULT (__stdcall *Present_t)(void *, const RECT *, const RECT *, HWND, const void *);
static Present_t g_real_present = NULL;
static uint32_t g_clear_calls = 0;
static uint32_t g_draw_calls = 0;
static DWORD g_last_clear_color = 0;
static void capture_d3d9_screenshot(void *dev, const char *png_path);

typedef HRESULT (__stdcall *Clear_t)(void *, DWORD, const void *, DWORD, DWORD, float, DWORD);
static Clear_t g_real_clear = NULL;

static HRESULT __stdcall hk_Clear(void *dev, DWORD count, const void *rects, DWORD flags, DWORD color, float z, DWORD stencil) {
    g_clear_calls++;
    g_last_clear_color = color;
    return g_real_clear(dev, count, rects, flags, color, z, stencil);
}

static void *g_tracked_targets[8] = {0};
static int g_num_tracked_targets = 0;
static void *g_current_target = NULL;
static void *g_last_draw_target = NULL;

typedef HRESULT (__stdcall *SetRenderTarget_t)(void *, DWORD, void *);
static SetRenderTarget_t g_real_setrendertarget = NULL;
static HRESULT __stdcall hk_SetRenderTarget(void *dev, DWORD index, void *target) {
    if (index == 0) {
        if (target != g_current_target) {
            g_cached_rt = NULL;
        }
        g_current_target = target;
        g_vp_is_full_hd = 0;
        if (target) {
            int found = 0;
            for (int i = 0; i < g_num_tracked_targets; i++) {
                if (g_tracked_targets[i] == target) { found = 1; break; }
            }
            if (!found && g_num_tracked_targets < 8) {
                g_tracked_targets[g_num_tracked_targets++] = target;
            }
        }
    }
    return g_real_setrendertarget(dev, index, target);
}

typedef HRESULT (__stdcall *SetViewport_t)(void *, const void *);
static SetViewport_t g_real_setviewport = NULL;
static HRESULT __stdcall hk_SetViewport(void *dev, const uint32_t *vp) {
    if (!dev || !vp) return g_real_setviewport ? g_real_setviewport(dev, vp) : 0;

    uint32_t rt_w = g_cfg_width, rt_h = g_cfg_height;
    if (g_current_target != NULL && g_current_target == g_cached_rt) {
        rt_w = g_cached_rt_w;
        rt_h = g_cached_rt_h;
    } else {
        void **vtbl = *(void ***)dev;
        typedef HRESULT (__stdcall *GetRenderTarget_t)(void *, DWORD, void **);
        GetRenderTarget_t get_rt = (GetRenderTarget_t)vtbl[38];
        void *pRT = NULL;
        if (get_rt && get_rt(dev, 0, &pRT) >= 0 && pRT) {
            void **rt_vtbl = *(void ***)pRT;
            typedef struct {
                DWORD Format; DWORD Type; DWORD Usage; DWORD Pool;
                DWORD MultiSampleType; DWORD MultiSampleQuality;
                UINT  Width; UINT  Height;
            } D3DSURFACE_DESC_MIN;
            typedef HRESULT (__stdcall *GetDesc_t)(void *, D3DSURFACE_DESC_MIN *);
            GetDesc_t get_desc = (GetDesc_t)rt_vtbl[12];
            D3DSURFACE_DESC_MIN desc = {0};
            if (get_desc && get_desc(pRT, &desc) >= 0) {
                if (desc.Width > 0 && desc.Height > 0) {
                    rt_w = desc.Width;
                    rt_h = desc.Height;
                }
            }
            typedef ULONG (__stdcall *Release_t)(void *);
            ((Release_t)rt_vtbl[2])(pRT);
        }
        if (g_current_target != NULL) {
            g_cached_rt = g_current_target;
            g_cached_rt_w = rt_w;
            g_cached_rt_h = rt_h;
        }
    }

    uint32_t fix[6] = { vp[0], vp[1], vp[2], vp[3], vp[4], vp[5] };
    if (fix[2] == 0 || fix[3] == 0) {
        fix[0] = 0; fix[1] = 0;
        fix[2] = rt_w;
        fix[3] = rt_h;
        static uint32_t last_zero_log = 0;
        if (g_present_calls - last_zero_log >= 60) {
            last_zero_log = g_present_calls;
            log_msg("[VT4-Mod] SetViewport zero dimensions overridden to RT bounds (%ux%u) at frame %u",
                    rt_w, rt_h, g_present_calls);
        }
    } else if ((fix[2] == 640 && fix[3] == 480) || (fix[2] == 1280 && fix[3] == 720)) {
        if (rt_w == g_cfg_width && rt_h == g_cfg_height) {
            fix[0] = 0; fix[1] = 0;
            fix[2] = g_cfg_width;
            fix[3] = g_cfg_height;
        } else {
            fix[0] = 0; fix[1] = 0;
            fix[2] = rt_w;
            fix[3] = rt_h;
        }
    }

    // Safety clamp: viewport must never exceed render target bounds to prevent D3DERR_INVALIDCALL
    if (fix[0] + fix[2] > rt_w) {
        if (fix[0] < rt_w) fix[2] = rt_w - fix[0];
        else { fix[0] = 0; fix[2] = rt_w; }
    }
    if (fix[1] + fix[3] > rt_h) {
        if (fix[1] < rt_h) fix[3] = rt_h - fix[1];
        else { fix[1] = 0; fix[3] = rt_h; }
    }

    g_vp_is_full_hd = (fix[2] > 0 && fix[3] > 0) ? 1 : 0;
    return g_real_setviewport(dev, fix);
}

static inline void ensure_valid_viewport(void *dev) {
    if (g_vp_is_full_hd) return;
    void **vtbl = *(void ***)dev;
    typedef HRESULT (__stdcall *GetViewport_t)(void *, void *);
    typedef HRESULT (__stdcall *SetViewportFn_t)(void *, const void *);
    GetViewport_t get_vp = (GetViewport_t)vtbl[48];
    SetViewportFn_t set_vp = (SetViewportFn_t)vtbl[47];
    uint32_t vp[6] = {0};
    if (get_vp && get_vp(dev, vp) >= 0) {
        if (vp[2] == 0 || vp[3] == 0) {
            typedef HRESULT (__stdcall *GetRenderTarget_t)(void *, DWORD, void **);
            GetRenderTarget_t get_rt = (GetRenderTarget_t)vtbl[38];
            void *pRT = NULL;
            uint32_t w = 1280, h = 720;
            if (get_rt && get_rt(dev, 0, &pRT) >= 0 && pRT) {
                void **rt_vtbl = *(void ***)pRT;
                typedef struct {
                    DWORD Format;
                    DWORD Type;
                    DWORD Usage;
                    DWORD Pool;
                    DWORD MultiSampleType;
                    DWORD MultiSampleQuality;
                    UINT  Width;
                    UINT  Height;
                } D3DSURFACE_DESC_MIN;
                typedef HRESULT (__stdcall *GetDesc_t)(void *, D3DSURFACE_DESC_MIN *);
                GetDesc_t get_desc = (GetDesc_t)rt_vtbl[12];
                D3DSURFACE_DESC_MIN desc = {0};
                if (get_desc && get_desc(pRT, &desc) >= 0) {
                    if (desc.Width > 0 && desc.Height > 0) {
                        w = desc.Width;
                        h = desc.Height;
                    }
                }
                typedef ULONG (__stdcall *Release_t)(void *);
                ((Release_t)rt_vtbl[2])(pRT);
            }
            uint32_t fix[6] = { 0, 0, w, h, 0, 0x3f800000 };
            if (set_vp) {
                HRESULT sv_hr = set_vp(dev, fix);
                if (sv_hr >= 0) g_vp_is_full_hd = 1;
                static uint32_t last_log = 0;
                if (g_present_calls - last_log >= 60) {
                    last_log = g_present_calls;
                    log_msg("[VT4-Mod] ensure_valid_viewport: fixed (0,0) -> %ux%u (hr=0x%08lx) at frame %u",
                            w, h, (unsigned long)sv_hr, g_present_calls);
                }
            }
        } else {
            g_vp_is_full_hd = 1;
        }
    }
}

static uint32_t g_target_draw_counts[8] = {0};
static inline void record_draw_target(void) {
    if (g_in_overlay) return;
    g_draw_calls++;
    perf_bench_on_draw();
    if (g_cfg_debug_log && g_current_target) {
        g_last_draw_target = g_current_target;
        for (int i = 0; i < g_num_tracked_targets; i++) {
            if (g_tracked_targets[i] == g_current_target) {
                g_target_draw_counts[i]++;
                break;
            }
        }
    }
}

typedef HRESULT (__stdcall *DrawPrimitive_t)(void *, int, UINT, UINT);
static DrawPrimitive_t g_real_drawprimitive = NULL;
static HRESULT __stdcall hk_DrawPrimitive(void *dev, int type, UINT start_vtx, UINT prim_count) {
    ensure_valid_viewport(dev);
    record_draw_target();
    return g_real_drawprimitive(dev, type, start_vtx, prim_count);
}

typedef HRESULT (__stdcall *DrawIndexedPrimitive_t)(void *, int, INT, UINT, UINT, UINT, UINT);
static DrawIndexedPrimitive_t g_real_drawindexedprimitive = NULL;
static HRESULT __stdcall hk_DrawIndexedPrimitive(void *dev, int type, INT base_vtx, UINT min_idx, UINT num_vtx, UINT start_idx, UINT prim_count) {
    ensure_valid_viewport(dev);
    record_draw_target();
    perf_bench_on_dip();
    return g_real_drawindexedprimitive(dev, type, base_vtx, min_idx, num_vtx, start_idx, prim_count);
}

static HRESULT __stdcall hk_DrawPrimitiveUP(void *dev, int type, UINT prim_count, const void *data, UINT stride) {
    ensure_valid_viewport(dev);
    record_draw_target();
    return g_real_drawprimitiveup(dev, type, prim_count, data, stride);
}

typedef HRESULT (__stdcall *DrawIndexedPrimitiveUP_t)(void *, int, UINT, UINT, UINT, const void *, int, const void *, UINT);
static DrawIndexedPrimitiveUP_t g_real_drawindexedprimitiveup = NULL;
static HRESULT __stdcall hk_DrawIndexedPrimitiveUP(void *dev, int type, UINT min_idx, UINT num_vtx, UINT prim_count, const void *idx_data, int idx_fmt, const void *vtx_data, UINT stride) {
    ensure_valid_viewport(dev);
    record_draw_target();
    return g_real_drawindexedprimitiveup(dev, type, min_idx, num_vtx, prim_count, idx_data, idx_fmt, vtx_data, stride);
}

static uint32_t g_begin_scene_calls = 0;
typedef HRESULT (__stdcall *BeginScene_t)(void *);
typedef HRESULT (__stdcall *EndScene_t)(void *);
static BeginScene_t g_real_beginscene = NULL;
static EndScene_t   g_real_endscene = NULL;

#include "nextgen_fx.h"
#include "netplay.h"

static void render_netplay_hud(void *dev) {
    char hud_txt[160];
    uint32_t txt_col = 0xFF80FFB0;
    if (!netplay_get_hud_text(hud_txt, sizeof(hud_txt), &txt_col)) return;
    if (!dev) dev = g_d3d_device;
    if (!dev || !*(void ***)dev) return;
    if (!g_pFont || !g_pSprite) init_menu_fonts(dev);
    if (!begin_overlay_state(dev)) return;

    float sx = (float)g_cfg_width / 1280.0f;
    float sy = (float)g_cfg_height / 720.0f;
    /* Positioned top-right so it never overlaps the Official TV Scoreboard on the top-left */
    float x1 = 768.0f * sx, y1 = 12.0f * sy, x2 = 1264.0f * sx, y2 = 40.0f * sy;
    draw_screen_quad(dev, x1, y1, x2, y2, 0xCC0A101C);
    draw_screen_quad(dev, x1, y2 - 2.0f * sy, x2, y2, txt_col);

    if (g_pFont && g_pSprite) {
        void **svtbl = *(void ***)g_pSprite;
        typedef HRESULT (__stdcall *SpriteBegin_t)(void *, DWORD);
        typedef HRESULT (__stdcall *SpriteEnd_t)(void *);
        SpriteBegin_t sp_begin = (SpriteBegin_t)svtbl[8];
        SpriteEnd_t   sp_end   = (SpriteEnd_t)svtbl[11];
        if (sp_begin && sp_begin(g_pSprite, 0x10) >= 0) {
            RECT r = { (LONG)(x1 + 10.0f * sx), (LONG)y1, (LONG)(x2 - 10.0f * sx), (LONG)y2 };
            draw_font_text(g_pFont, hud_txt, &r, txt_col, 2);
            if (sp_end) sp_end(g_pSprite);
        }
    }
    end_overlay_state(dev);
}

static void render_netplay_menu(void *dev) {
    if (!g_netplay_menu_visible) return;
    if (!dev) dev = g_d3d_device;
    if (!dev || !*(void ***)dev) return;
    if (!g_pFont || !g_pFontTitle || !g_pSprite) init_menu_fonts(dev);
    if (!begin_overlay_state(dev)) return;

    void **vtbl = *(void ***)dev;
    typedef HRESULT (__stdcall *SetViewport_t)(void *, const void *);
    SetViewport_t set_vp = (SetViewport_t)vtbl[47];
    uint32_t full_vp[6] = { 0, 0, g_cfg_width, g_cfg_height, 0, 0x3f800000 };
    if (set_vp) set_vp(dev, full_vp);

    float sx = (float)g_cfg_width / 1280.0f;
    float sy = (float)g_cfg_height / 720.0f;

    /* Native VT4 full-screen pearl/silver/magenta theme (matches OPCIONES / EXHIBICION) */
    if (g_pNpBgTex) {
        draw_textured_quad(dev, g_pNpBgTex, 0.0f, 0.0f, (float)g_cfg_width, (float)g_cfg_height, 0xFFFFFFFF);
    } else {
        draw_screen_quad(dev, 0.0f, 0.0f, (float)g_cfg_width, (float)g_cfg_height, 0xFFEBEDF2);
        draw_screen_quad(dev, 650.0f * sx, 0.0f, (float)g_cfg_width, (float)g_cfg_height, 0xFFE2E4EC);
        draw_screen_quad(dev, 0.0f, 62.0f * sy, (float)g_cfg_width, 66.0f * sy, 0xFF8416DE);
        draw_screen_quad(dev, 650.0f * sx, 62.0f * sy, 658.0f * sx, 656.0f * sy, 0xFF8416DE);
        draw_screen_quad(dev, 0.0f, 656.0f * sy, (float)g_cfg_width, (float)g_cfg_height, 0xFFE0E2E8);
    }

    const char *labels[NUM_NETPLAY_ITEMS] = {
        "MODO DE CONEXION",
        "BUSCAR SALA EN RED LOCAL (LAN)",
        "IP DEL RIVAL (ESCRIBIR)",
        "PUERTO UDP (PC <-> ANDROID)",
        "DELAY DE RED (FRAMES)",
        "CONECTAR / APLICAR NETPLAY",
        "DESCONECTAR Y VOLVER"
    };

    float col_x1 = 66.0f * sx, col_x2 = 626.0f * sx;
    float row_y0 = 104.0f * sy;
    float row_pitch = 62.0f * sy;

    for (int i = 0; i < NUM_NETPLAY_ITEMS; i++) {
        float ry1 = row_y0 + (float)i * row_pitch;
        float ry2 = ry1 + (i >= 5 ? 48.0f : 54.0f) * sy;
        int sel = (i == s_np_sel);
        void *tex = (i >= 5) ? (sel ? g_pNpBtnSelTex : g_pNpBtnUnselTex)
                             : (sel ? g_pNpRowSelTex : g_pNpRowUnselTex);
        if (tex) {
            DWORD tint = (i == 6 && sel) ? 0xFFFFD0D8 : 0xFFFFFFFF;
            draw_textured_quad(dev, tex, col_x1, ry1, col_x2, ry2, tint);
        } else {
            DWORD bg = (i == 5) ? (sel ? 0xFF149850 : 0xFFE2E6EE)
                     : (i == 6) ? (sel ? 0xFFC02848 : 0xFFE2E6EE)
                                : (sel ? 0xFF8416DE : 0xFFF5F6FA);
            draw_screen_quad(dev, col_x1, ry1, col_x2, ry2, bg);
            draw_screen_quad(dev, col_x1, ry1, col_x2, ry1 + 1.5f * sy, sel ? 0xFFD898FF : 0xFFA2A6B2);
        }
    }

    /* Right column: Legends Crest + Info Card */
    if (g_pCrestTex) {
        float cx = 964.0f * sx, cy = 148.0f * sy, rad = 70.0f * sy;
        draw_textured_quad(dev, g_pCrestTex, cx - rad, cy - rad, cx + rad, cy + rad, 0xF5FFFFFF);
    }

    float card_x1 = 696.0f * sx, card_y1 = 224.0f * sy, card_x2 = 1230.0f * sx, card_y2 = 624.0f * sy;
    if (g_pNpCardTex) {
        draw_textured_quad(dev, g_pNpCardTex, card_x1, card_y1, card_x2, card_y2, 0xFFFFFFFF);
    } else {
        draw_screen_quad(dev, card_x1, card_y1, card_x2, card_y2, 0xFFF4F6FB);
        draw_screen_quad(dev, card_x1, card_y1, card_x2, card_y1 + 42.0f * sy, 0xFF8416DE);
    }

    char status_buf[160];
    uint32_t st_col = 0xFF184C8C;
    netplay_get_status_spanish(status_buf, sizeof(status_buf), &st_col);
    /* Darken bright green/yellow slightly so it has high legibility on pearl card background */
    if (g_np.state == NP_STATE_READY_MENU || g_np.state == NP_STATE_BARRIER || g_np.state == NP_STATE_PLAYING) {
        st_col = 0xFF0E7A3E;
    } else if (g_np.state == NP_STATE_HANDSHAKE) {
        st_col = 0xFF9C5E00;
    } else if (g_np.state == NP_STATE_OFF || g_np.mode == NP_MODE_OFF) {
        st_col = 0xFF424654;
    } else {
        st_col = 0xFFB82028;
    }

    if (s_np_feedback_timer > 0) {
        s_np_feedback_timer--;
        draw_screen_quad(dev, card_x1 + 16.0f * sx, card_y2 - 58.0f * sy,
                         card_x2 - 16.0f * sx, card_y2 - 16.0f * sy, 0xFFE6F4EC);
        draw_screen_quad(dev, card_x1 + 16.0f * sx, card_y2 - 58.0f * sy,
                         card_x2 - 16.0f * sx, card_y2 - 56.0f * sy, s_np_feedback_col);
    }

    if (g_pFont && g_pFontTitle && g_pSprite) {
        void **svtbl = *(void ***)g_pSprite;
        typedef HRESULT (__stdcall *SpriteBegin_t)(void *, DWORD);
        typedef HRESULT (__stdcall *SpriteEnd_t)(void *);
        SpriteBegin_t sp_begin = (SpriteBegin_t)svtbl[8];
        SpriteEnd_t   sp_end   = (SpriteEnd_t)svtbl[11];
        if (sp_begin && sp_begin(g_pSprite, 0x10) >= 0) {
            RECT r;
            r.left = (LONG)(66.0f * sx); r.top = (LONG)(14.0f * sy);
            r.right = (LONG)(640.0f * sx); r.bottom = (LONG)(56.0f * sy);
            draw_font_text(g_pFontTitle, "EN LINEA - NETPLAY P2P (PC <-> ANDROID / LAN)", &r, 0xFF3E404C, 0);

            r.left = (LONG)(680.0f * sx); r.right = (LONG)(1230.0f * sx);
            draw_font_text(g_pFont, "Lockstep UDP 60Hz | 0 Desync", &r, 0xFF7028B8, 2);

            static const char *s_mode_names[3] = {
                "DESACTIVADO (OFF)",
                "CREAR SALA (HOST P1)",
                "UNIRSE A IP (CLIENT P2)"
            };
            char val[96];
            for (int i = 0; i < NUM_NETPLAY_ITEMS; i++) {
                float ry1 = row_y0 + (float)i * row_pitch;
                float ry2 = ry1 + (i >= 5 ? 48.0f : 54.0f) * sy;
                int sel = (i == s_np_sel);
                if (i >= 5) {
                    r.left = (LONG)(col_x1 + 16.0f * sx); r.top = (LONG)ry1;
                    r.right = (LONG)(col_x2 - 16.0f * sx); r.bottom = (LONG)ry2;
                    draw_font_text(g_pFontTitle, labels[i], &r, sel ? 0xFFFFFFFF : 0xFF363844, 1);
                } else {
                    float mid_y = ry1 + 26.0f * sy;
                    r.left = (LONG)(col_x1 + 26.0f * sx); r.top = (LONG)(ry1 + 2.0f * sy);
                    r.right = (LONG)(col_x2 - 16.0f * sx); r.bottom = (LONG)mid_y;
                    draw_font_text(g_pFont, labels[i], &r, sel ? 0xFFFFFFFF : 0xFF525462, 0);

                    if (i == 0) snprintf(val, sizeof(val), "< %s >", s_mode_names[s_np_mode % 3u]);
                    else if (i == 1) snprintf(val, sizeof(val), "[ Pulsar Enter para buscar en WiFi / LAN ]");
                    else if (i == 2) snprintf(val, sizeof(val), "%s%s", s_np_ip, (sel && ((g_present_calls / 20u) & 1u)) ? "_" : "");
                    else if (i == 3) snprintf(val, sizeof(val), "< %u >", s_np_port);
                    else snprintf(val, sizeof(val), "< %u frames (~%ums) >", s_np_delay, s_np_delay * 16u);

                    r.left = (LONG)(col_x1 + 16.0f * sx); r.top = (LONG)mid_y;
                    r.right = (LONG)(col_x2 - 18.0f * sx); r.bottom = (LONG)ry2;
                    draw_font_text(g_pFont, val, &r, sel ? 0xFFFFF0A8 : 0xFFEDF0F8, 1);
                }
            }

            /* Right-hand Info Card text */
            r.left = (LONG)(card_x1 + 16.0f * sx); r.top = (LONG)(card_y1 + 12.0f * sy);
            r.right = (LONG)(card_x2 - 16.0f * sx); r.bottom = (LONG)(card_y1 + 56.0f * sy);
            draw_font_text(g_pFontTitle, "ESTADO DE LA SALA P2P", &r, 0xFFFFFFFF, 1);

            r.left = (LONG)(card_x1 + 20.0f * sx); r.top = (LONG)(card_y1 + 66.0f * sy);
            r.right = (LONG)(card_x2 - 20.0f * sx); r.bottom = (LONG)(card_y1 + 102.0f * sy);
            draw_font_text(g_pFont, status_buf, &r, st_col, 1);

            char info_buf[160];
            snprintf(info_buf, sizeof(info_buf), "Tu IP local (para Host):  %s : %u", s_np_local_ip, s_np_port);
            r.top = (LONG)(card_y1 + 104.0f * sy); r.bottom = (LONG)(card_y1 + 136.0f * sy);
            draw_font_text(g_pFont, info_buf, &r, 0xFF2858A8, 1);

            r.left = (LONG)(card_x1 + 24.0f * sx); r.right = (LONG)(card_x2 - 24.0f * sx);
            r.top = (LONG)(card_y1 + 158.0f * sy); r.bottom = (LONG)(card_y1 + 188.0f * sy);
            draw_font_text(g_pFont, "1. En Host: elige CREAR SALA y pulsa CONECTAR", &r, 0xFF3E4250, 0);
            r.top = (LONG)(card_y1 + 194.0f * sy); r.bottom = (LONG)(card_y1 + 224.0f * sy);
            draw_font_text(g_pFont, "2. En Rival (Android/PC): pulsa BUSCAR SALA LAN", &r, 0xFF3E4250, 0);
            r.top = (LONG)(card_y1 + 230.0f * sy); r.bottom = (LONG)(card_y1 + 260.0f * sy);
            draw_font_text(g_pFont, "   (o escribe la IP de Tailscale para internet)", &r, 0xFF646878, 0);
            r.top = (LONG)(card_y1 + 266.0f * sy); r.bottom = (LONG)(card_y1 + 296.0f * sy);
            draw_font_text(g_pFont, "3. Pulsa ESC y entra ambos en EXHIBICION", &r, 0xFF3E4250, 0);

            if (s_np_feedback_timer > 0) {
                r.left = (LONG)(card_x1 + 16.0f * sx); r.top = (LONG)(card_y2 - 58.0f * sy);
                r.right = (LONG)(card_x2 - 16.0f * sx); r.bottom = (LONG)(card_y2 - 16.0f * sy);
                draw_font_text(g_pFont, s_np_feedback, &r, s_np_feedback_col, 1);
            }

            r.left = (LONG)(60.0f * sx); r.top = (LONG)(662.0f * sy);
            r.right = (LONG)(1220.0f * sx); r.bottom = (LONG)(710.0f * sy);
            draw_font_text(g_pFontTitle,
                "Elegir [Enter]     Cambiar [< / >]     Escribir IP [0-9 .]     Atras [ESC]",
                &r, 0xFF40424A, 1);

            if (sp_end) sp_end(g_pSprite);
        }
    }
    end_overlay_state(dev);
    ensure_d3d9_device_hooks(dev);
}

static HRESULT __stdcall hk_EndScene(void *dev) {
    static int s_es_hud_logged = 0;
    if (g_menu_visible && !s_es_hud_logged) {
        s_es_hud_logged = 1;
        log_msg("[VT4-Mod] hk_EndScene: rendering settings HUD (frame=%u, dev=%p)", g_present_calls, dev);
    }
    {
        float hud_sx = (float)g_cfg_width / 1280.0f;
        float hud_sy = (float)g_cfg_height / 720.0f;
        float hud_s = (hud_sx < hud_sy) ? hud_sx : hud_sy;
        ee_render_match_overlay(dev, hud_s, hud_s);
        int bhud_live = (g_ee_live_match_present_frame != 0 &&
                         g_present_calls <= g_ee_live_match_present_frame + 4 &&
                         *(uint8_t *)0x008232f6 == 0 &&
                         *(int *)0x008232f0 == 0);
        render_broadcast_tv_hud(dev, bhud_live, g_cfg_broadcast_hud,
                                g_menu_visible, g_netplay_menu_visible, g_ee1_fury_active,
                                g_vp_p1_id, g_vp_p2_id,
                                hud_s, hud_s);
        render_roster_pagination_hud(dev);
        render_settings_hud(dev);
        render_netplay_hud(dev);
        render_netplay_menu(dev);
        if (touch_gamepad_should_show(g_cfg_touch_hud)) {
            float v_ax = 0.0f, v_ay = 0.0f;
            WORD  v_btns = 0;
            xinput_get_p1(&v_ax, &v_ay, &v_btns);
            if (is_key_down(VK_LEFT)  || is_key_down('A')) v_ax = -1.0f;
            else if (is_key_down(VK_RIGHT) || is_key_down('D')) v_ax = 1.0f;
            if (is_key_down(VK_UP)    || is_key_down('W')) v_ay = -1.0f;
            else if (is_key_down(VK_DOWN)  || is_key_down('S')) v_ay = 1.0f;
            if (is_key_down('Z') || is_key_down('J') || is_key_down(VK_RETURN)) v_btns |= 0x1000;
            if (is_key_down('C') || is_key_down('K') || is_key_down(VK_ESCAPE)) v_btns |= 0x2000;
            if (is_key_down('X') || is_key_down('L')) v_btns |= 0x4000;
            if (is_key_down('V') || is_key_down('I')) v_btns |= 0x8000;
            if (is_key_down('Q')) v_btns |= 0x0100;
            if (is_key_down('E')) v_btns |= 0x0200;
            render_touch_gamepad_hud(dev, g_cfg_touch_hud, g_cfg_width, g_cfg_height,
                                     bhud_live, (g_chara_select_frames > 0), v_ax, v_ay, v_btns);
        }
    }
    HRESULT hr = g_real_endscene ? g_real_endscene(dev) : 0;
    ensure_d3d9_device_hooks(dev);
    if (hr != 0) {
        log_msg("[VT4-Mod] EndScene returned 0x%08lx caller=%p", (unsigned long)hr, __builtin_return_address(0));
    }
    return hr;
}

static HRESULT __stdcall hk_BeginScene(void *dev) {
    g_begin_scene_calls++;
    ensure_valid_viewport(dev);

    if (g_sampler_dirty > 0) {
        g_sampler_dirty--;
        if (g_cfg_antialiasing > 0 || g_cfg_anisotropic > 0) {
            void **vtbl = *(void ***)dev;
            if (g_cfg_antialiasing > 0) {
                typedef HRESULT (__stdcall *SetRenderState_t)(void *, DWORD, DWORD);
                SetRenderState_t set_rs = (SetRenderState_t)vtbl[57];
                if (set_rs) {
                    set_rs(dev, 161, 1); // D3DRS_MULTISAMPLEANTIALIAS = TRUE
                    set_rs(dev, 176, 1); // D3DRS_ANTIALIASEDLINEENABLE = TRUE
                }
            }
            if (g_cfg_anisotropic > 0) {
                typedef HRESULT (__stdcall *SetSamplerState_t)(void *, DWORD, DWORD, DWORD);
                SetSamplerState_t set_sampler = (SetSamplerState_t)vtbl[69];
                if (set_sampler) {
                    for (DWORD s = 0; s < 8; s++) {
                        set_sampler(dev, s, 1, 3); // D3DSAMP_MAGFILTER = D3DTEXF_ANISOTROPIC
                        set_sampler(dev, s, 2, 3); // D3DSAMP_MINFILTER = D3DTEXF_ANISOTROPIC
                        set_sampler(dev, s, 3, 2); // D3DSAMP_MIPFILTER = D3DTEXF_LINEAR
                        set_sampler(dev, s, 10, g_cfg_anisotropic); // D3DSAMP_MAXANISOTROPY
                    }
                }
            }
        }
    }
    HRESULT hr = g_real_beginscene ? g_real_beginscene(dev) : 0;
    if (hr != 0) {
        log_msg("[VT4-Mod] BeginScene returned 0x%08lx caller=%p", (unsigned long)hr, __builtin_return_address(0));
    }
    return hr;
}

static void check_and_restore_native_audio(void);

static HRESULT __stdcall hk_Present(void *dev, const RECT *src, const RECT *dst, HWND dstWnd, const void *dirty) {
    g_present_calls++;
    if (!g_d3d_device && dev) g_d3d_device = dev;

    if (g_present_calls == 1 || (g_present_calls % 300) == 1) {
        if (g_sampler_dirty < 1) g_sampler_dirty = 1;
    }

    if (g_option_mode_active && g_present_calls > g_option_mode_last_frame + 3) {
        log_msg("[VT4-Mod] Exited OptionMode (frame=%u, last_opt_frame=%u, menu_by_opt=%d)",
                g_present_calls, g_option_mode_last_frame, g_menu_opened_by_optionmode);
        g_option_mode_active = 0;
        if (g_menu_opened_by_optionmode) {
            g_menu_visible = 0;
            g_menu_opened_by_optionmode = 0;
        }
    }

    if (g_present_calls == 1 || (g_present_calls % 300) == 0) {
        log_msg("[VT4-Mod] Present frame %u: clears=%u (last_col=0x%08lx) draws=%u beginScenes=%u caller=%p last_rt=%p",
                g_present_calls, g_clear_calls, (unsigned long)g_last_clear_color, g_draw_calls, g_begin_scene_calls,
                __builtin_return_address(0), g_last_draw_target);
    }
    if (g_present_calls == 120 || g_present_calls == 300) {
        check_and_restore_native_audio();
    }

    netplay_poll_background();
    ngfx_on_present(dev);

    if (is_key_down(VK_F10)) {
        g_screenshot_requested = 1;
    }

    if (g_screenshot_requested || (g_cfg_debug_log && (g_present_calls == 1 || g_present_calls == 60))) {
        g_screenshot_requested = 0;
        char path[MAX_PATH];
        snprintf(path, sizeof(path), "%s\\vt4_present_%u.png", g_game_dir, g_present_calls);
        capture_d3d9_screenshot(dev, path);
    }

    HRESULT pres_hr = g_real_present(dev, src, dst, dstWnd, dirty);
    if (pres_hr == (HRESULT)0x08760878) { // S_PRESENT_OCCLUDED: window occluded/background, treat as D3D_OK so render loop never stalls
        pres_hr = 0;
    }
    if (pres_hr != 0) {
        log_msg("[VT4-Mod] hk_Present frame %u: real_present returned 0x%08lx", g_present_calls, (unsigned long)pres_hr);
    }
    perf_bench_on_present_after();
    return pres_hr;
}

static void capture_d3d9_screenshot(void *dev, const char *png_path) {
    if (!dev) return;
    if (!g_d3dx_save) {
        HMODULE hD3DX = get_d3dx9_43();
        if (hD3DX) g_d3dx_save = (D3DXSaveSurfaceToFileA_t)GetProcAddress(hD3DX, "D3DXSaveSurfaceToFileA");
    }
    if (!g_d3dx_save) {
        return;
    }

    void **vtbl = *(void ***)dev;
    typedef HRESULT (__stdcall *GetBackBuffer_t)(void *, UINT, UINT, int, void **);
    GetBackBuffer_t get_bb = (GetBackBuffer_t)vtbl[18];

    void *pSurface = NULL;
    HRESULT hr = get_bb(dev, 0, 0, 0, &pSurface);
    if (hr >= 0 && pSurface) {
        char tmp_path[MAX_PATH];
        snprintf(tmp_path, sizeof(tmp_path), "%s\\vt4_present_tmp.png", g_game_dir);
        hr = g_d3dx_save(tmp_path, 3, pSurface, NULL, NULL); // 3 = D3DXIFF_PNG
        if (SUCCEEDED(hr)) {
            if (MoveFileExA(tmp_path, png_path, MOVEFILE_REPLACE_EXISTING)) {
                log_msg("[VT4-Mod] D3D9 GPU backbuffer screenshot saved: %s", png_path);
            } else {
                log_msg("[VT4-Mod] MoveFileExA failed (%lu) for %s", (unsigned long)GetLastError(), png_path);
                DeleteFileA(tmp_path);
            }
        } else {
            log_msg("[VT4-Mod] D3DXSaveSurfaceToFileA failed: hr=%08lx", (unsigned long)hr);
            DeleteFileA(tmp_path);
        }
        void **svtbl = *(void ***)pSurface;
        typedef ULONG (__stdcall *Release_t)(void *);
        Release_t rel = (Release_t)svtbl[2];
        rel(pSurface);
    } else {
        log_msg("[VT4-Mod] GetBackBuffer failed: hr=0x%08lx pSurface=%p", (unsigned long)hr, pSurface);
    }
}

static void save_bmp(HWND hwnd, const char *path) {
    RECT rc;
    GetClientRect(hwnd, &rc);
    int w = rc.right - rc.left;
    int h = rc.bottom - rc.top;
    if (w <= 0 || h <= 0) { w = 1280; h = 720; }

    HDC hdcWin = GetDC(hwnd);
    if (!hdcWin) return;
    HDC hdcMem = CreateCompatibleDC(hdcWin);
    HBITMAP hbm = CreateCompatibleBitmap(hdcWin, w, h);
    HGDIOBJ oldBm = SelectObject(hdcMem, hbm);

    PrintWindow(hwnd, hdcMem, 2); // PW_RENDERFULLCONTENT
    BitBlt(hdcMem, 0, 0, w, h, hdcWin, 0, 0, SRCCOPY);

    BITMAPINFO bmi = {0};
    bmi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    bmi.bmiHeader.biWidth = w;
    bmi.bmiHeader.biHeight = h;
    bmi.bmiHeader.biPlanes = 1;
    bmi.bmiHeader.biBitCount = 32;
    bmi.bmiHeader.biCompression = BI_RGB;

    size_t sz = (size_t)w * h * 4;
    void *bits = malloc(sz);
    if (bits) {
        GetDIBits(hdcMem, hbm, 0, h, bits, &bmi, DIB_RGB_COLORS);
        BITMAPFILEHEADER bfh = {0};
        bfh.bfType = 0x4D42;
        bfh.bfOffBits = sizeof(BITMAPFILEHEADER) + sizeof(BITMAPINFOHEADER);
        bfh.bfSize = (DWORD)(bfh.bfOffBits + sz);

        FILE *f = fopen(path, "wb");
        if (f) {
            fwrite(&bfh, sizeof(bfh), 1, f);
            fwrite(&bmi.bmiHeader, sizeof(bmi.bmiHeader), 1, f);
            fwrite(bits, 1, sz, f);
            fclose(f);
            log_msg("[VT4-Mod] Screenshot written to %s (%dx%d)", path, w, h);
        }
        free(bits);
    }
    SelectObject(hdcMem, oldBm);
    DeleteObject(hbm);
    DeleteDC(hdcMem);
    ReleaseDC(hwnd, hdcWin);
}

static int g_d3d_is_ex = 0;
static UINT g_d3d_sdk_ver = 32;

static HRESULT __stdcall hk_CreateDevice(void *self, UINT adapter, DWORD devtype, HWND focus,
                                         DWORD flags, VT4_D3DPRESENT_PARAMETERS *pp, void **ppdev) {
    log_msg("[VT4-Mod] CreateDevice called: adapter=%u type=%u focus=%p flags=%08x", adapter, devtype, focus, flags);
    if (pp) {
        log_pp("raw in", pp);
        pp->BackBufferWidth = g_cfg_width;
        pp->BackBufferHeight = g_cfg_height;
        if (!pp->hDeviceWindow) pp->hDeviceWindow = focus;
        pp->Windowed = TRUE;
        pp->FullScreen_RefreshRateInHz = 0;
        pp->PresentationInterval = (g_perf_pacer_active || !g_cfg_vsync) ? 0x80000000u : 1u;
        if (g_cfg_perf_profile == 2) {
            pp->BackBufferCount = 2; // Triple buffering for parallel CPU/GPU pipelining on Mali/Vortek & Turnip
            pp->SwapEffect = 1; // D3DSWAPEFFECT_DISCARD (cleanest for DXVK/Turnip)
        }
        pp->MultiSampleType = g_cfg_antialiasing;
        pp->MultiSampleQuality = 0;
        pp->EnableAutoDepthStencil = TRUE;
        pp->AutoDepthStencilFormat = 75; // D3DFMT_D24S8
        if (pp->BackBufferFormat == 21) pp->BackBufferFormat = 22; // X8R8G8B8
        log_pp("sanitized", pp);
    }

    // List of candidate configs: (flags, format)
    const struct {
        DWORD flags;
        UINT fmt;
    } configs[] = {
        { 0x40, 22 }, // Hardware, D3DFMT_X8R8G8B8
        { 0x50, 22 }, // Hardware + Pure, D3DFMT_X8R8G8B8
        { 0x40, 0  }, // Hardware, D3DFMT_UNKNOWN
        { 0x50, 0  }, // Hardware + Pure, D3DFMT_UNKNOWN
        { 0x40, 21 }, // Hardware, D3DFMT_A8R8G8B8
        { 0x50, 21 }, // Hardware + Pure, D3DFMT_A8R8G8B8
        { 0x20, 22 }, // Software, D3DFMT_X8R8G8B8
    };

    HRESULT hr = -1;
    for (int ms_pass = 0; ms_pass < 2 && hr < 0; ms_pass++) {
        if (pp) {
            pp->MultiSampleType = (ms_pass == 0) ? g_cfg_antialiasing : 0;
            pp->MultiSampleQuality = 0;
        }
        for (size_t i = 0; i < sizeof(configs)/sizeof(configs[0]); i++) {
            if (pp) pp->BackBufferFormat = configs[i].fmt;
            DWORD f = configs[i].flags;
            hr = g_real_createdevice(self, adapter, devtype, focus, f, pp, ppdev);
            log_msg("[VT4-Mod] CreateDevice attempt %u (pass=%d flags=%08x fmt=%u BB=%ux%u MS=%u) -> hr=%08lx dev=%p",
                    (unsigned)i, ms_pass, f, pp ? pp->BackBufferFormat : 0,
                    pp ? pp->BackBufferWidth : 0, pp ? pp->BackBufferHeight : 0,
                    pp ? pp->MultiSampleType : 0,
                    (unsigned long)hr, ppdev ? *ppdev : NULL);
            if (hr >= 0 && ppdev && *ppdev) {
                log_msg("[VT4-Mod] CreateDevice SUCCESS on attempt %u (MSAA=%u)! Device: %p",
                        (unsigned)i, pp ? pp->MultiSampleType : 0, *ppdev);
                break;
            }
        }
    }

    if (hr < 0 && g_d3d_is_ex && g_real_d3dcreate9) {
        log_msg("[VT4-Mod] CreateDevice failed on D3D9Ex (hr=%08lx); trying standard Direct3DCreate9 fallback...", (unsigned long)hr);
        void *std_d3d = g_real_d3dcreate9(g_d3d_sdk_ver);
        if (std_d3d && *(void ***)std_d3d) {
            CreateDevice_t std_cd = (CreateDevice_t)(*(void ***)std_d3d)[16];
            if (std_cd) {
                if (pp) {
                    pp->Windowed = TRUE;
                    pp->MultiSampleType = 0;
                    pp->MultiSampleQuality = 0;
                    pp->BackBufferFormat = 22;
                }
                static const DWORD std_flags[2] = { 0x40, 0x20 };
                for (int k = 0; k < 2; k++) {
                    hr = std_cd(std_d3d, adapter, devtype, focus, std_flags[k], pp, ppdev);
                    log_msg("[VT4-Mod] Direct3DCreate9 fallback CreateDevice flags=%08x -> hr=%08lx dev=%p",
                            std_flags[k], (unsigned long)hr, ppdev ? *ppdev : NULL);
                    if (hr >= 0 && ppdev && *ppdev) {
                        g_d3d_is_ex = 0;
                        break;
                    }
                }
            }
        }
    }

    if (hr >= 0 && ppdev && *ppdev) {
        g_d3d_device = *ppdev;
        g_game_hwnd = focus ? focus : (pp ? pp->hDeviceWindow : NULL);

        int scr_w = GetSystemMetrics(SM_CXSCREEN);
        int scr_h = GetSystemMetrics(SM_CYSCREEN);

        if (!g_cfg_windowed) {
            SetWindowLongA(g_game_hwnd, GWL_STYLE, WS_POPUP | WS_VISIBLE);
            SetWindowPos(g_game_hwnd, HWND_TOP, 0, 0, scr_w, scr_h, SWP_SHOWWINDOW | SWP_FRAMECHANGED);
            ShowWindow(g_game_hwnd, SW_SHOWMAXIMIZED);
            UpdateWindow(g_game_hwnd);
            SetForegroundWindow(g_game_hwnd);
            g_is_fullscreen = 1;
            log_msg("[VT4-Mod] Window geometry: Fullscreen Borderless (%dx%d)", scr_w, scr_h);
        } else {
            RECT wr = { 0, 0, g_cfg_width, g_cfg_height };
            DWORD style = WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX | WS_VISIBLE;
            AdjustWindowRect(&wr, style, FALSE);
            int win_w = wr.right - wr.left;
            int win_h = wr.bottom - wr.top;
            int pos_x = (scr_w > win_w) ? (scr_w - win_w) / 2 : 0;
            int pos_y = (scr_h > win_h) ? (scr_h - win_h) / 2 : 0;

            SetWindowLongA(g_game_hwnd, GWL_STYLE, style);
            SetWindowPos(g_game_hwnd, HWND_TOP, pos_x, pos_y, win_w, win_h, SWP_SHOWWINDOW | SWP_FRAMECHANGED);
            ShowWindow(g_game_hwnd, SW_SHOWNORMAL);
            UpdateWindow(g_game_hwnd);
            SetForegroundWindow(g_game_hwnd);
            g_is_fullscreen = 0;
            log_msg("[VT4-Mod] Window geometry: Windowed pos=(%d,%d) size=%dx%d (client %ux%u)",
                    pos_x, pos_y, win_w, win_h, g_cfg_width, g_cfg_height);
        }

        uintptr_t wm = *(uintptr_t *)0x00a75ad0;
        if (wm) {
            *(uint32_t *)wm = g_cfg_width;
            *(uint32_t *)(wm + 4) = g_cfg_height;
            *(uint8_t *)(wm + 0xa) = 1;
            *(uint32_t *)(wm + 0x4c) = g_cfg_width;
            *(uint32_t *)(wm + 0x50) = g_cfg_height;
        }

        if (g_game_hwnd && !g_orig_wndproc) {
            g_orig_wndproc = (WNDPROC)(uintptr_t)SetWindowLongA(g_game_hwnd, GWL_WNDPROC, (LONG)(uintptr_t)hk_GameWndProc);
            log_msg("[VT4-Mod] Subclassed game window procedure (orig=%p)", g_orig_wndproc);
        }

        ensure_d3d9_device_hooks(*ppdev);
        return hr;
    }

    log_msg("[VT4-Mod] CreateDevice FAILED all attempts! Last hr=%08lx", (unsigned long)hr);
    return hr;
}

static void ensure_d3d9_device_hooks(void *dev) {
    if (!dev || !*(void ***)dev) return;
    void **dev_vtbl = *(void ***)dev;
    if (dev_vtbl[17] == (void *)hk_Present && dev_vtbl[42] == (void *)hk_EndScene) {
        return;
    }
    int first_install = (g_real_present == NULL);
    void *prev_p = dev_vtbl[17];
    void *prev_es = dev_vtbl[42];

    const struct {
        int slot;
        void *hk;
        void **real_out;
    } hooks[] = {
        { 16, (void *)hk_Reset,                   (void **)&g_real_reset },
        { 17, (void *)hk_Present,                 (void **)&g_real_present },
        { 23, (void *)hk_CreateTexture,           (void **)&g_real_createtexture },
        { 28, (void *)hk_CreateRenderTarget,      (void **)&g_real_createrendertarget },
        { 29, (void *)hk_CreateDepthStencilSurface,(void **)&g_real_createdepthstencilsurface },
        { 37, (void *)hk_SetRenderTarget,         (void **)&g_real_setrendertarget },
        { 41, (void *)hk_BeginScene,              (void **)&g_real_beginscene },
        { 42, (void *)hk_EndScene,                (void **)&g_real_endscene },
        { 43, (void *)hk_Clear,                   (void **)&g_real_clear },
        { 47, (void *)hk_SetViewport,             (void **)&g_real_setviewport },
        { 81, (void *)hk_DrawPrimitive,           (void **)&g_real_drawprimitive },
        { 82, (void *)hk_DrawIndexedPrimitive,    (void **)&g_real_drawindexedprimitive },
        { 83, (void *)hk_DrawPrimitiveUP,         (void **)&g_real_drawprimitiveup },
        { 84, (void *)hk_DrawIndexedPrimitiveUP,  (void **)&g_real_drawindexedprimitiveup }
    };

    for (size_t i = 0; i < sizeof(hooks) / sizeof(hooks[0]); i++) {
        int slot = hooks[i].slot;
        void *hk = hooks[i].hk;
        if (dev_vtbl[slot] != hk) {
            *hooks[i].real_out = dev_vtbl[slot];
            patch_bytes((uintptr_t)&dev_vtbl[slot], &hk, sizeof(hk));
        }
    }

    if (first_install) {
        log_msg("[VT4-Mod] D3D9 device hooks installed (Present, Clear, BeginScene, SetViewport, DrawPrim/Idx/UP)");
    } else {
        log_msg("[VT4-Mod] Re-hooked D3D9 device vtable %p (prev17=%p prev42=%p)", dev_vtbl, prev_p, prev_es);
    }
}

static void *__stdcall hk_Direct3DCreate9(UINT sdk) {
    void *d3d = NULL;
    g_d3d_sdk_ver = sdk;
    g_d3d_is_ex = 0;
    if (g_cfg_use_d3d9ex) {
        if (!g_d3dcreate9ex) {
            HMODULE hD3D9 = GetModuleHandleA("d3d9.dll");
            if (!hD3D9) hD3D9 = LoadLibraryA("d3d9.dll");
            if (hD3D9) g_d3dcreate9ex = (Direct3DCreate9Ex_t)GetProcAddress(hD3D9, "Direct3DCreate9Ex");
        }
        if (g_d3dcreate9ex) {
            HRESULT hr = g_d3dcreate9ex(sdk, &d3d);
            if (SUCCEEDED(hr) && d3d) g_d3d_is_ex = 1;
            log_msg("[VT4-Mod] Direct3DCreate9Ex(%u) -> hr=%08lx d3d=%p", sdk, (unsigned long)hr, d3d);
        }
    } else {
        log_msg("[VT4-Mod] UseD3D9Ex=0: using standard Direct3DCreate9(%u)", sdk);
    }
    if (!d3d) {
        g_d3d_is_ex = 0;
        d3d = g_real_d3dcreate9(sdk);
        log_msg("[VT4-Mod] Direct3DCreate9 fallback(%u) -> %p", sdk, d3d);
    }
    if (d3d) {
        void **vtbl = *(void ***)d3d;
        if (!g_real_createdevice) g_real_createdevice = (CreateDevice_t)vtbl[16];
        void *hk = (void *)hk_CreateDevice;
        patch_bytes((uintptr_t)&vtbl[16], &hk, sizeof(hk));
    }
    return d3d;
}

static void hook_iat(HMODULE mod, const char *dll, const char *func, void *hook, void **orig) {
    BYTE *base = (BYTE *)mod;
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)base;
    IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)(base + dos->e_lfanew);
    IMAGE_DATA_DIRECTORY dir = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
    if (!dir.VirtualAddress) return;
    IMAGE_IMPORT_DESCRIPTOR *imp = (IMAGE_IMPORT_DESCRIPTOR *)(base + dir.VirtualAddress);
    for (; imp->Name; imp++) {
        if (_stricmp((const char *)(base + imp->Name), dll) != 0) continue;
        IMAGE_THUNK_DATA *oft = (IMAGE_THUNK_DATA *)(base + (imp->OriginalFirstThunk ? imp->OriginalFirstThunk : imp->FirstThunk));
        IMAGE_THUNK_DATA *ft = (IMAGE_THUNK_DATA *)(base + imp->FirstThunk);
        for (; oft->u1.AddressOfData; oft++, ft++) {
            if (IMAGE_SNAP_BY_ORDINAL(oft->u1.Ordinal)) continue;
            IMAGE_IMPORT_BY_NAME *ibn = (IMAGE_IMPORT_BY_NAME *)(base + oft->u1.AddressOfData);
            if (strcmp((const char *)ibn->Name, func) == 0) {
                *orig = (void *)ft->u1.Function;
                void *h = hook;
                patch_bytes((uintptr_t)&ft->u1.Function, &h, sizeof(h));
                log_msg("[VT4-Mod] IAT hook %s!%s installed (orig=%p)", dll, func, *orig);
                return;
            }
        }
    }
    log_msg("[VT4-Mod] IAT hook %s!%s NOT found", dll, func);
}

typedef void (__stdcall *ExitProcess_t)(UINT);
static ExitProcess_t g_real_exitprocess = NULL;
static void __stdcall hk_ExitProcess(UINT code) {
    void *caller = __builtin_return_address(0);
    log_msg("[VT4-Mod] ExitProcess called with code=%u by caller %p!", code, caller);
    if (g_real_exitprocess) g_real_exitprocess(code);
    else ExitProcess(code);
}

__attribute__((used)) volatile uint32_t g_sound_play_calls = 0;

static void check_and_restore_native_audio(void) {
    void *xa2 = *(void **)0x00a66198;
    void *mvoice = *(void **)0x00a6619c;
    void *svoice = *(void **)0x00a661a0;
    uintptr_t mgr = *(uintptr_t *)0x00836afc;
    uintptr_t impl = (mgr >= 0x10000) ? *(uintptr_t *)(mgr + 4) : 0;
    uintptr_t state = (impl >= 0x10000) ? *(uintptr_t *)(impl + 4) : 0;
    float master_vol = -1.0f, cat0 = -1.0f, cat4 = -1.0f;
    if (state >= 0x10000) {
        float *pm = (float *)state;
        if (*pm < 0.05f) {
            float prev = *pm;
            *pm = 1.0f;
            log_msg("[VT4-Mod] Native Audio: MasterVolume was %.2f -> restored to 1.00", prev);
        }
        master_vol = *pm;
        int all_zero = 1;
        for (int i = 0; i < 7; i++) {
            float cv = *(float *)(state + 8 + (size_t)i * 0x112c);
            if (cv >= 0.05f) {
                all_zero = 0;
                break;
            }
        }
        if (all_zero) {
            for (int i = 0; i < 7; i++) {
                *(float *)(state + 8 + (size_t)i * 0x112c) = 0.8f;
            }
            log_msg("[VT4-Mod] Native Audio: Category volumes 0..6 were 0.0 -> restored to 0.80");
        }
        cat0 = *(float *)(state + 8);
        cat4 = *(float *)(state + 8 + 4 * 0x112c);
    }
    log_msg("[VT4-Mod] Native Audio Status: XAudio2=%p MasterVoice=%p SourceVoice=%p SoundMgr=%p SoundPlayCalls=%u MasterVol=%.2f Cat0=%.2f Cat4=%.2f",
            xa2, mvoice, svoice, (void *)mgr, (unsigned)g_sound_play_calls, master_vol, cat0, cat4);
}

static void __attribute__((naked)) hk_SoundPlay(void) {
    __asm__(
        "cmpl $0x10000, %ecx\n"
        "jb 1f\n"
        "mov 4(%ecx), %eax\n"
        "cmpl $0x10000, %eax\n"
        "jb 1f\n"
        "mov 4(%esp), %eax\n"
        "cmpl $0x10000, %eax\n"
        "jb 1f\n"
        "incl _g_sound_play_calls\n"
        "push $-1\n"
        "push $0x0077c13f\n"
        "mov $0x006375f7, %eax\n"
        "jmp *%eax\n"
        "1:\n"
        "xor %eax, %eax\n"
        "ret $4\n"
    );
}

static int is_valid_code_ptr(void *p) {
    uintptr_t addr = (uintptr_t)p;
    if (addr < 0x10000) return 0;
    if (addr >= 0x00401000 && addr < 0x00788000) return 1;
    MEMORY_BASIC_INFORMATION mbi;
    if (VirtualQuery(p, &mbi, sizeof(mbi))) {
        if ((mbi.Protect & (PAGE_EXECUTE | PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE)) &&
            mbi.Type == MEM_IMAGE) {
            return 1;
        }
    }
    return 0;
}

static inline void call_thiscall_0(void *fn, void *this_ptr) {
    __asm__ __volatile__(
        "mov %0, %%ecx\n"
        "call *%1\n"
        :
        : "r"(this_ptr), "r"(fn)
        : "eax", "ecx", "edx", "memory"
    );
}

static void __fastcall hk_CallSubsystemUpdate(void *node) {
    if ((uintptr_t)node < 0x10000) return;
    void **vtbl = *(void ***)node;
    if ((uintptr_t)vtbl < 0x10000) return;
    void *fn = vtbl[1];
    if (!is_valid_code_ptr(fn)) {
        log_msg("[VT4-Mod] SubsystemUpdate: node=%p vtbl=%p vtbl[1]=%p (NOT valid code image) -> skipped", node, vtbl, fn);
        return;
    }
    call_thiscall_0(fn, node);
}

static void __fastcall hk_CallSubsystemPostUpdate(void *node) {
    if ((uintptr_t)node < 0x10000) return;
    void **vtbl = *(void ***)node;
    if ((uintptr_t)vtbl < 0x10000) return;
    void *fn = vtbl[2];
    if (!is_valid_code_ptr(fn)) return;
    call_thiscall_0(fn, node);
}

static void __fastcall hk_CallSubsystemPreUpdate(void *node) {
    if ((uintptr_t)node < 0x10000) return;
    void **vtbl = *(void ***)node;
    if ((uintptr_t)vtbl < 0x10000) return;
    void *fn = vtbl[5];
    if (!is_valid_code_ptr(fn)) return;
    call_thiscall_0(fn, node);
}

static void __fastcall hk_SafeDestroyChild(void *child) {
    if ((uintptr_t)child < 0x10000) return;
    void **vtbl = *(void ***)child;
    if ((uintptr_t)vtbl < 0x10000) return;
    void *fn = vtbl[3];
    if (!is_valid_code_ptr(fn)) return;
    typedef void (__thiscall *Dtor_t)(void *self, int flags);
    ((Dtor_t)fn)(child, 1);
}

static int g_title_started = 0;
static int __stdcall hk_MessageBoxA(HWND hWnd, LPCSTR lpText, LPCSTR lpCaption, UINT uType) {
    log_msg("[VT4-Mod] MessageBoxA caught: Caption='%s' Text='%s'", lpCaption ? lpCaption : "null", lpText ? lpText : "null");
    return 1; // IDOK
}

static int __stdcall hk_MessageBoxW(HWND hWnd, LPCWSTR lpText, LPCWSTR lpCaption, UINT uType) {
    log_msg("[VT4-Mod] MessageBoxW caught: Caption='%ls' Text='%ls'", lpCaption ? lpCaption : L"null", lpText ? lpText : L"null");
    return 1; // IDOK
}

static int __cdecl hk_MiscWindow_GetResult(int mesId) {
    if (g_present_calls < 60) return 0;
    static uint32_t last_mw_log = 0;
    if (g_present_calls - last_mw_log >= 30) {
        last_mw_log = g_present_calls;
        log_msg("[VT4-Mod] MiscWindow::GetResult(mesId=%d/0x%x) auto-decided 1 (OK) at frame %u", mesId, mesId, g_present_calls);
    }
    return 1; // Confirmed / OK
}

static void __fastcall hk_AdvMode_Update(void *self) {
    if (!g_title_started) {
        g_title_started = 1;
        log_msg("[VT4-Mod] Launching TitleLogo sequence once at startup...");
        typedef void (__thiscall *ChangeSeq_t)(void *self, const char *name);
        ChangeSeq_t change_seq = (ChangeSeq_t)0x00635610;
        change_seq(self, "TitleLogo");
        log_msg("[VT4-Mod] TitleLogo launched successfully!");
    }
    static uint32_t last_seq_log = 0;
    if (g_present_calls - last_seq_log >= 60) {
        last_seq_log = g_present_calls;
        typedef void *(__thiscall *GetCurNode_t)(void *self);
        GetCurNode_t get_node = (GetCurNode_t)0x006360d0;
        void *node = get_node(self);
        const char *name = "null";
        if (node) {
            typedef const char *(__thiscall *GetName_t)(void *node);
            GetName_t get_name = (GetName_t)0x0062f730;
            name = get_name(node);
        }
        log_msg("[VT4-Mod] AdvMode frame %u: current sequence = '%s'", g_present_calls, name ? name : "null");
    }
    typedef void (__thiscall *AdvUpdate_t)(void *self);
    AdvUpdate_t orig = (AdvUpdate_t)0x00430700;
    orig(self);
}

static void __fastcall hk_MainMenu_Update(void *self) {
    g_option_mode_active = 0;
    static uint32_t last_log = 0;
    static uint32_t last_state = 999;
    uint32_t *pState = (uint32_t *)((char *)self + 0xe98);
    uint32_t subtask = *(uint32_t *)((char *)self + 0xf68);

    if (*pState != last_state) {
        log_msg("[VT4-Mod] MainMenu state transition: %u -> %u (subtask=%d) at frame %u",
                last_state, *pState, (int)subtask, g_present_calls);
        last_state = *pState;
    }

    void *carousel = (char *)self + 0xe9c;
    int curr_sel = *(int *)((char *)carousel + 0x2c);
    static int last_sel = -999;
    if (curr_sel != last_sel) {
        log_msg("[VT4-Mod] Carousel selection changed: %d -> %d at frame %u", last_sel, curr_sel, g_present_calls);
        last_sel = curr_sel;
    }

    if (g_present_calls - last_log >= 60) {
        last_log = g_present_calls;
        void *carousel = (char *)self + 0xe9c;
        void *carousel_vtbl = *(void **)carousel;
        log_msg("[VT4-Mod] MainMenu::Update frame %u: state=%u subtask=%d carousel=%p vtbl=%p [0x30]=%d [0x2c]=%d",
                g_present_calls, *pState, (int)subtask, carousel, carousel_vtbl,
                *(uint8_t *)((char *)carousel + 0x30), *(int *)((char *)carousel + 0x2c));
    }

    // Fallback: If still in State 1 after frame 260 on boot, call InitButtons (0x0043e730) properly
    static int g_menu_inited_once = 0;
    if (!g_menu_inited_once && *pState == 1 && g_present_calls > 260 && g_present_calls < 400) {
        g_menu_inited_once = 1;
        log_msg("[VT4-Mod] Fallback: invoking MainMenu::InitButtons (0x0043e730) at frame %u...", g_present_calls);
        typedef void (__thiscall *InitButtons_t)(void *self, uint32_t sel, uint32_t flag);
        InitButtons_t init_btn = (InitButtons_t)0x0043e730;
        uint32_t sel = *(uint32_t *)((char *)self + 0xf60);
        *pState = 2;
        init_btn(self, sel, 1);
        log_msg("[VT4-Mod] MainMenu advanced to state 2 with buttons initialized cleanly!");
    }

    typedef void (__thiscall *Orig_t)(void *self);
    Orig_t orig = (Orig_t)0x0043ed20;
    orig(self);
}

static void __fastcall hk_Loading_Update(void *self, void *edx, uint32_t arg1) {
    static uint32_t last_log = 0;
    if (g_present_calls - last_log >= 60) {
        last_log = g_present_calls;
        uint32_t state = *(uint32_t *)((char *)self + 0x10);
        uint32_t wait_frames = *(uint32_t *)((char *)self + 0x14);
        uint8_t f144 = *(uint8_t *)((char *)self + 0x144);
        uint8_t f145 = *(uint8_t *)((char *)self + 0x145);
        log_msg("[VT4-Mod] Loading::Update frame %u: state=%u wait_frames=%u f144=%u f145=%u arg1=%u",
                g_present_calls, state, wait_frames, f144, f145, arg1);
    }

    typedef void (__thiscall *Orig_t)(void *self, uint32_t arg1);
    Orig_t orig = (Orig_t)0x0043d960;
    orig(self, arg1);

    // After 90 frames (~1.5s), if loading hasn't dismissed, invoke Loading::Finish (0x0043BA30)
    static uint32_t loading_frames = 0;
    loading_frames++;
    if (loading_frames >= 90) {
        void **vtbl = *(void ***)self;
        typedef void (__thiscall *Finish_t)(void *self);
        Finish_t finish = (Finish_t)vtbl[2]; // slot +0x08 = 0x0043BA30
        log_msg("[VT4-Mod] Dismissing loading screen (invoking Loading::Finish 0x0043BA30) at frame %u", g_present_calls);
        finish(self);
        loading_frames = 0;
    }
}

static void __attribute__((naked)) hk_SafeTreeTraverse(void) {
    __asm__(
        "cmpl $0x10000, %ecx\n"
        "jb 1f\n"
        "push %esi\n"
        "mov %ecx, %esi\n"
        "cmpl $0, 4(%esi)\n"
        "mov $0x0062fbc7, %eax\n"
        "jmp *%eax\n"
        "1:\n"
        "ret\n"
    );
}

static void __attribute__((naked)) hk_SafeTreePreUpdate(void) {
    __asm__(
        "cmpl $0x10000, %ecx\n"
        "jb 1f\n"
        "push %edi\n"
        "mov %ecx, %edi\n"
        "cmpl $0, 4(%edi)\n"
        "mov $0x0062fb07, %eax\n"
        "jmp *%eax\n"
        "1:\n"
        "ret\n"
    );
}

static void __attribute__((naked)) hk_SafeTreeRender(void) {
    __asm__(
        "cmpl $0x10000, %ecx\n"
        "jb 1f\n"
        "push %esi\n"
        "mov %ecx, %esi\n"
        "cmpl $0, 4(%esi)\n"
        "mov $0x0062fb77, %eax\n"
        "jmp *%eax\n"
        "1:\n"
        "ret\n"
    );
}

static void __attribute__((naked)) hk_SafeTreePostUpdate(void) {
    __asm__(
        "cmpl $0x10000, %ecx\n"
        "jb 1f\n"
        "push %ebp\n"
        "push %esi\n"
        "mov %ecx, %esi\n"
        "mov 4(%esi), %ebp\n"
        "mov $0x0062fc67, %eax\n"
        "jmp *%eax\n"
        "1:\n"
        "ret\n"
    );
}

static void __attribute__((naked)) hk_Safe45a8d0(void) {
    __asm__(
        "test %ecx, %ecx\n"
        "jz 1f\n"
        "cmp $0x10000, %ecx\n"
        "jb 1f\n"
        "mov 0x8c(%ecx), %eax\n"
        "test %eax, %eax\n"
        "jz 1f\n"
        "cmp $0x10000, %eax\n"
        "jb 1f\n"
        "mov (%eax), %edx\n"
        "test %edx, %edx\n"
        "jz 1f\n"
        "cmp $0x10000, %edx\n"
        "jb 1f\n"
        "push $0x0045A8D8\n"
        "ret\n"
        "1:\n"
        "ret\n"
    );
}

static void __attribute__((naked)) hk_Safe628e00(void) {
    __asm__(
        "test %ecx, %ecx\n"
        "jz 1f\n"
        "cmp $0x10000, %ecx\n"
        "jb 1f\n"
        "push %ecx\n"
        "push %esi\n"
        "mov %ecx, %esi\n"
        "cmpl $0, 0x44(%esi)\n"
        "push $0x00628E08\n"
        "ret\n"
        "1:\n"
        "xor %eax, %eax\n"
        "ret $8\n"
    );
}

static void __attribute__((naked)) hk_Safe628e60(void) {
    __asm__(
        "test %ecx, %ecx\n"
        "jz 1f\n"
        "cmp $0x10000, %ecx\n"
        "jb 1f\n"
        "push %ecx\n"
        "push %esi\n"
        "mov %ecx, %esi\n"
        "cmpl $0, 0x44(%esi)\n"
        "push $0x00628E68\n"
        "ret\n"
        "1:\n"
        "fldz\n"
        "ret $8\n"
    );
}

static void install_jmp(uint32_t addr, void *target, size_t total_len) {
    uint8_t buf[16];
    memset(buf, 0x90, sizeof(buf));
    buf[0] = 0xE9;
    uint32_t rel = (uint32_t)(uintptr_t)target - (addr + 5);
    memcpy(&buf[1], &rel, 4);
    patch_bytes(addr, buf, total_len);
}

static void *make_trampoline(uint32_t src, size_t len) {
    uint8_t *tramp = (uint8_t *)VirtualAlloc(NULL, len + 5, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!tramp) return NULL;
    memcpy(tramp, (void *)src, len);
    tramp[len] = 0xE9; // JMP rel32
    uint32_t rel = (src + len) - ((uint32_t)(uintptr_t)tramp + len + 5);
    memcpy(&tramp[len + 1], &rel, 4);
    return tramp;
}

static void *make_trampoline_reloc(uint32_t src, size_t len, int e8_offset, uint32_t e8_target) {
    uint8_t *tramp = (uint8_t *)make_trampoline(src, len);
    if (tramp && e8_offset >= 0 && tramp[e8_offset] == 0xE8) {
        uint32_t fixed_rel = e8_target - ((uint32_t)(uintptr_t)tramp + (uint32_t)e8_offset + 5u);
        memcpy(&tramp[e8_offset + 1], &fixed_rel, 4);
    }
    return tramp;
}
static void __attribute__((naked)) hk_Safe6284e0(void) {
    __asm__(
        "test %ecx, %ecx\n"
        "jz 1f\n"
        "cmp $0x10000, %ecx\n"
        "jb 1f\n"
        "movzwl 0xa(%ecx), %eax\n"
        "test %eax, %eax\n"
        "jz 1f\n"
        "cmpl $0, 4(%ecx)\n"
        "jz 1f\n"
        "push %esi\n"
        "push %edi\n"
        "mov 0xc(%esp), %edi\n"
        "push $0x006284E6\n"
        "ret\n"
        "1:\n"
        "xor %eax, %eax\n"
        "ret $4\n"
    );
}

// 0x00628610 (fwFormat::FindChild - Exhibition / Arcade / Party Match Type crash fix)
static void __attribute__((naked)) hk_Safe628610(void) {
    __asm__(
        "test %ecx, %ecx\n"
        "jz 1f\n"
        "cmp $0x10000, %ecx\n"
        "jb 1f\n"
        "push $0xffffffff\n"
        "push $0x00773108\n"
        "push $0x00628617\n"
        "ret\n"
        "1:\n"
        "xor %eax, %eax\n"
        "ret $8\n"
    );
}

static void __attribute__((naked)) hk_Safe6280b0(void) {
    __asm__(
        "test %ecx, %ecx\n"
        "jz 1f\n"
        "cmp $0x10000, %ecx\n"
        "jb 1f\n"
        "cmpl $0, 0x44(%ecx)\n"
        "jz 1f\n"
        "push %ebx\n"
        "push %esi\n"
        "push %edi\n"
        "mov %ecx, %edi\n"
        "push $0x006280D2\n"
        "ret\n"
        "1:\n"
        "xor %eax, %eax\n"
        "ret\n"
    );
}

static void __attribute__((naked)) hk_Safe628ec0(void) {
    __asm__(
        "test %ecx, %ecx\n"
        "jz 1f\n"
        "cmp $0x10000, %ecx\n"
        "jb 1f\n"
        "cmpl $0, 0x44(%ecx)\n"
        "jz 1f\n"
        "push %ebx\n"
        "push %ebp\n"
        "push %esi\n"
        "push %edi\n"
        "mov %ecx, %esi\n"
        "push $0x00628EE0\n"
        "ret\n"
        "1:\n"
        "xor %eax, %eax\n"
        "ret $0x10\n"
    );
}

// 0x00628F50 (Difficulty Selection / Character Creation crash fix)
static void __attribute__((naked)) hk_Safe628f50(void) {
    __asm__(
        "test %ecx, %ecx\n"
        "jz 1f\n"
        "cmp $0x10000, %ecx\n"
        "jb 1f\n"
        "cmpl $0, 0x44(%ecx)\n"
        "jz 1f\n"
        "push %ebx\n"
        "push %ebp\n"
        "push %esi\n"
        "push %edi\n"
        "mov %ecx, %ebx\n"
        "push $0x00628F70\n"
        "ret\n"
        "1:\n"
        "xor %eax, %eax\n"
        "ret $0xc\n"
    );
}

static void __attribute__((naked)) hk_Safe628ff0(void) {
    __asm__(
        "test %ecx, %ecx\n"
        "jz 1f\n"
        "cmp $0x10000, %ecx\n"
        "jb 1f\n"
        "cmpl $0, 0x44(%ecx)\n"
        "jz 1f\n"
        "push %ebx\n"
        "push %esi\n"
        "push %edi\n"
        "mov %ecx, %esi\n"
        "push $0x0062900F\n"
        "ret\n"
        "1:\n"
        "xor %eax, %eax\n"
        "ret $0x10\n"
    );
}

static void __attribute__((naked)) hk_Safe629070(void) {
    __asm__(
        "test %ecx, %ecx\n"
        "jz 1f\n"
        "cmp $0x10000, %ecx\n"
        "jb 1f\n"
        "cmpl $0, 0x44(%ecx)\n"
        "jz 1f\n"
        "push %ebx\n"
        "push %ebp\n"
        "push %esi\n"
        "push %edi\n"
        "mov %ecx, %esi\n"
        "push $0x00629090\n"
        "ret\n"
        "1:\n"
        "xor %eax, %eax\n"
        "ret $8\n"
    );
}

static void __attribute__((naked)) hk_Safe629100(void) {
    __asm__(
        "test %ecx, %ecx\n"
        "jz 1f\n"
        "cmp $0x10000, %ecx\n"
        "jb 1f\n"
        "cmpl $0, 0x44(%ecx)\n"
        "jz 1f\n"
        "push %ebx\n"
        "push %ebp\n"
        "push %esi\n"
        "push %edi\n"
        "mov %ecx, %esi\n"
        "push $0x00629120\n"
        "ret\n"
        "1:\n"
        "xor %eax, %eax\n"
        "ret $0x10\n"
    );
}

static void __attribute__((naked)) hk_Safe6291d0(void) {
    __asm__(
        "test %ecx, %ecx\n"
        "jz 1f\n"
        "cmp $0x10000, %ecx\n"
        "jb 1f\n"
        "cmpl $0, 0x44(%ecx)\n"
        "jz 1f\n"
        "push %esi\n"
        "push %edi\n"
        "mov %ecx, %esi\n"
        "push $0x006291F1\n"
        "ret\n"
        "1:\n"
        "xor %eax, %eax\n"
        "ret $0xc\n"
    );
}

static void __attribute__((naked)) hk_Safe629230(void) {
    __asm__(
        "test %ecx, %ecx\n"
        "jz 1f\n"
        "cmp $0x10000, %ecx\n"
        "jb 1f\n"
        "cmpl $0, 0x44(%ecx)\n"
        "jz 1f\n"
        "push %esi\n"
        "push %edi\n"
        "mov %ecx, %esi\n"
        "push $0x00629251\n"
        "ret\n"
        "1:\n"
        "xor %eax, %eax\n"
        "ret $0xc\n"
    );
}

static void __attribute__((naked)) hk_Safe629290(void) {
    __asm__(
        "test %ecx, %ecx\n"
        "jz 1f\n"
        "cmp $0x10000, %ecx\n"
        "jb 1f\n"
        "cmpl $0, 0x44(%ecx)\n"
        "jz 1f\n"
        "push %esi\n"
        "push %edi\n"
        "mov %ecx, %esi\n"
        "push $0x006292B1\n"
        "ret\n"
        "1:\n"
        "xor %eax, %eax\n"
        "ret $0xc\n"
    );
}

static void __attribute__((naked)) hk_Safe6292f0(void) {
    __asm__(
        "test %ecx, %ecx\n"
        "jz 1f\n"
        "cmp $0x10000, %ecx\n"
        "jb 1f\n"
        "cmpl $0, 0x44(%ecx)\n"
        "jz 1f\n"
        "push %esi\n"
        "mov %ecx, %esi\n"
        "push $0x00629310\n"
        "ret\n"
        "1:\n"
        "xor %eax, %eax\n"
        "ret $4\n"
    );
}

static void my_invalid_parameter_handler(
    const wchar_t *expression,
    const wchar_t *function,
    const wchar_t *file,
    unsigned int line,
    uintptr_t pReserved)
{
    log_msg("[VT4-Mod] CRT Invalid Parameter caught: Expr='%ls' Func='%ls' File='%ls' Line=%u",
            expression ? expression : L"null",
            function ? function : L"null",
            file ? file : L"null",
            line);
}

typedef BOOL (WINAPI *GetKeyboardState_t)(PBYTE);
static GetKeyboardState_t g_real_getkeyboardstate = NULL;

static BOOL WINAPI hk_GetKeyboardState(PBYTE lpKeyState) {
    if (g_real_getkeyboardstate) {
        g_real_getkeyboardstate(lpKeyState);
    } else {
        GetKeyboardState(lpKeyState);
    }

    #define SYNC_KEY(vk, target) do { \
        if (is_key_down(vk)) { \
            lpKeyState[target] |= 0x80; \
        } \
    } while(0)

    // Directional arrows
    SYNC_KEY(VK_UP, VK_UP);
    SYNC_KEY(VK_DOWN, VK_DOWN);
    SYNC_KEY(VK_LEFT, VK_LEFT);
    SYNC_KEY(VK_RIGHT, VK_RIGHT);

    // WASD alternative navigation
    SYNC_KEY('W', VK_UP);
    SYNC_KEY('S', VK_DOWN);
    SYNC_KEY('A', VK_LEFT);
    SYNC_KEY('D', VK_RIGHT);

    // Map physical inputs to VT4 internal virtual button codes:
    // 0x94 = Menu Up, 0x90 = D-pad Up, 0x8E = Analog Up
    if (is_key_down(VK_UP) || is_key_down('W')) {
        lpKeyState[VK_UP] |= 0x80;
        lpKeyState[0x94] |= 0x80;
        lpKeyState[0x90] |= 0x80;
        lpKeyState[0x8E] |= 0x80;
    }
    // 0x95 = Menu Down, 0x91 = D-pad Down, 0x8F = Analog Down
    if (is_key_down(VK_DOWN) || is_key_down('S')) {
        lpKeyState[VK_DOWN] |= 0x80;
        lpKeyState[0x95] |= 0x80;
        lpKeyState[0x91] |= 0x80;
        lpKeyState[0x8F] |= 0x80;
    }
    // 0x96 = Menu Left, 0x92 = D-pad Left, 0x8C = Analog Left
    if (is_key_down(VK_LEFT) || is_key_down('A')) {
        lpKeyState[VK_LEFT] |= 0x80;
        lpKeyState[0x96] |= 0x80;
        lpKeyState[0x92] |= 0x80;
        lpKeyState[0x8C] |= 0x80;
    }
    // 0x97 = Menu Right, 0x93 = D-pad Right, 0x8D = Analog Right
    if (is_key_down(VK_RIGHT) || is_key_down('D')) {
        lpKeyState[VK_RIGHT] |= 0x80;
        lpKeyState[0x97] |= 0x80;
        lpKeyState[0x93] |= 0x80;
        lpKeyState[0x8D] |= 0x80;
    }

    // Keep physical menu keys distinct from in-match shot/pause keys so 'C' (Lob) or Enter
    // never fires VK_SPACE (Pause), and 'Z' (Topspin) never fires VK_ESCAPE.
    if (is_key_down(VK_RETURN)) {
        lpKeyState[VK_RETURN] |= 0x80;
        lpKeyState[0x81] |= 0x80; // Button A (Menu confirm)
    }
    if (is_key_down(VK_SPACE)) {
        lpKeyState[VK_SPACE] |= 0x80;
        lpKeyState[0x50] |= 0x80; // Start / Pause
    }
    if (is_key_down('P')) {
        lpKeyState[0x50] |= 0x80; // Start / Pause
    }

    if (is_key_down(VK_ESCAPE) || is_key_down(VK_BACK)) {
        lpKeyState[VK_ESCAPE] |= 0x80;
        lpKeyState[0x80] |= 0x80; // Button B (Cancel)
    }

    // Match/Menu shots: Z/J=Topspin, X/L=Slice, C/K=Lob, V/I=Dropshot
    // (Never alias Topspin Z/J to Cancel 0x80)
    if (is_key_down('Z') || is_key_down('J')) {
        lpKeyState['Z'] |= 0x80;
    }
    if (is_key_down('X') || is_key_down('L')) {
        lpKeyState['X'] |= 0x80;
        lpKeyState[0x82] |= 0x80; // Button X
    }
    if (is_key_down('C') || is_key_down('K')) {
        lpKeyState['C'] |= 0x80;
        lpKeyState[0x81] |= 0x80; // Button A
    }
    if (is_key_down('V') || is_key_down('I')) {
        lpKeyState['V'] |= 0x80;
        lpKeyState[0x83] |= 0x80; // Button Y
    }

    // LB / RB: Q / E
    if (is_key_down('Q')) lpKeyState[0x84] |= 0x80;
    if (is_key_down('E')) lpKeyState[0x85] |= 0x80;

    #undef SYNC_KEY

    return TRUE;
}

// ----------------------------------------------------------------------------
// First-Class Input Handlers (0x00415500 IsButtonDown & 0x00415530 IsButtonPressed)
// ----------------------------------------------------------------------------
static inline int original_IsButtonDown(void *self, int button) {
    if (!self) return 0;
    uint8_t *dev = *(uint8_t **)self;
    if (!dev) return 0;
    uint32_t buf = *(uint32_t *)dev;
    if (button < 0 || button >= 256) return 0;
    return dev[(buf << 8) + button + 9] != 0;
}

static inline int original_IsButtonPressed(void *self, int button) {
    if (!self) return 0;
    uint8_t *dev = *(uint8_t **)self;
    if (!dev) return 0;
    uint32_t buf = *(uint32_t *)dev;
    if (button < 0 || button >= 256) return 0;
    int cur = dev[(buf << 8) + button + 9] != 0;
    if (!cur) return 0;
    int prev = dev[((1 - buf) << 8) + button + 9] != 0;
    return (!prev);
}

static int is_mapped_button_down(int button) {
    if (g_menu_visible || g_netplay_menu_visible) return 0;
    float ax = 0.0f, ay = 0.0f;
    WORD xb = 0;
    xinput_get_p1(&ax, &ay, &xb);
    switch (button) {
        // Directions (Up, Down, Left, Right)
        case 0x94: case 0x90: case 0x8E: // Up
            return is_key_down(VK_UP) || is_key_down('W') || (xb & 0x0001) || (ay < -0.5f);
        case 0x95: case 0x91: case 0x8F: // Down
            return is_key_down(VK_DOWN) || is_key_down('S') || (xb & 0x0002) || (ay > 0.5f);
        case 0x96: case 0x92: case 0x8C: // Left
            return is_key_down(VK_LEFT) || is_key_down('A') || (xb & 0x0004) || (ax < -0.5f);
        case 0x97: case 0x93: case 0x8D: // Right
            return is_key_down(VK_RIGHT) || is_key_down('D') || (xb & 0x0008) || (ax > 0.5f);

        // Action Buttons
        case 0x81: // Confirm / A Button / Lob
            return is_key_down(VK_RETURN) || is_key_down(VK_SPACE) || is_key_down('C') || is_key_down('K') || (xb & 0x1000);
        case 0x80: // Cancel / Back / B Button
        case 0x0E: // Virtual Cancel / Escape (used by FPPlayerEntry and Sega AFC)
            return is_key_down(VK_ESCAPE) || is_key_down(VK_BACK) || (xb & 0x2000);
        case 0x82: // X Button / Slice
            return is_key_down('X') || is_key_down('L') || (xb & 0x4000);
        case 0x83: // Y Button / Dropshot
            return is_key_down('V') || is_key_down('I') || (xb & 0x8000);
        case 0x84: // LB
            return is_key_down('Q') || (xb & 0x0100);
        case 0x85: // RB
            return is_key_down('E') || (xb & 0x0200);
        case 0x50: // Start / Pause (never hijack Enter as Pause during live matches)
            return is_key_down(VK_SPACE) || is_key_down('P') || (xb & 0x0010);

        // Pass-through for standard VK codes if checked directly
        case VK_RETURN:
            return is_key_down(VK_RETURN);
        case VK_SPACE:
            return is_key_down(VK_SPACE);
        case VK_ESCAPE:
            return is_key_down(VK_ESCAPE);
        case 'Z':
            return is_key_down('Z') || is_key_down('J');
        case 'X':
            return is_key_down('X') || is_key_down('L');
        case 'C':
            return is_key_down('C') || is_key_down('K');
        case 'V':
            return is_key_down('V') || is_key_down('I');
        case VK_UP:
            return is_key_down(VK_UP) || is_key_down('W');
        case VK_DOWN:
            return is_key_down(VK_DOWN) || is_key_down('S');
        case VK_LEFT:
            return is_key_down(VK_LEFT) || is_key_down('A');
        case VK_RIGHT:
            return is_key_down(VK_RIGHT) || is_key_down('D');
        default:
            if (button >= 'A' && button <= 'Z') return is_key_down(button);
            if (button >= '0' && button <= '9') return is_key_down(button);
            return 0;
    }
}

static int __thiscall hk_IsButtonDown(void *self, int button) {
    if (g_menu_visible || g_netplay_menu_visible) return 0;
    if (is_mapped_button_down(button)) {
        return 1;
    }
    return original_IsButtonDown(self, button);
}

static int __thiscall hk_IsButtonPressed(void *self, int button) {
    if (g_menu_visible || g_netplay_menu_visible) return 0;
    if (button >= 0 && button < 256) {
        if (is_mapped_button_down(button)) {
            g_btn_hold[button]++;
            if (g_btn_hold[button] == 1) {
                if (g_present_calls < 600) {
                    log_msg("[VT4-Mod] IsButtonPressed: button=0x%02x down at frame %u", button, g_present_calls);
                }
                return 1;
            }
            // Auto-repeat for navigation keys after 18 frames, every 5 frames
            if (button >= 0x94 && button <= 0x97) {
                if (g_btn_hold[button] > 18 && ((g_btn_hold[button] % 5) == 0)) {
                    return 1;
                }
            }
            return 0;
        } else {
            g_btn_hold[button] = 0;
        }
    }
    return original_IsButtonPressed(self, button);
}

// ----------------------------------------------------------------------------
// In-Match fwInputDevice Bit Hooks (0x0062BF50 / 0x0062BF90 / 0x0062BFE0)
// Ensures Arrows+Z/X/C/V, WASD+J/K/L/I & XInput work inside live tennis matches
// ----------------------------------------------------------------------------
typedef int (__thiscall *FwInputBitFn_t)(void *self, int bit_idx);
static FwInputBitFn_t g_real_fwinput_isbitdown = NULL;
static FwInputBitFn_t g_real_fwinput_isbitpressed = NULL;
static FwInputBitFn_t g_real_fwinput_isbitreleased = NULL;

static uint32_t g_fwkbd_last_frame[256] = {0};
static uint8_t  g_fwkbd_prev[256] = {0};
static uint8_t  g_fwkbd_cur[256] = {0};

static int fwkbd_bit_down(int bit_idx) {
    if (g_menu_visible || g_netplay_menu_visible) return 0;
    float ax = 0.0f, ay = 0.0f;
    WORD xb = 0;
    xinput_get_p1(&ax, &ay, &xb);
    switch (bit_idx) {
        case VK_UP:     return is_key_down(VK_UP)    || is_key_down('W') || (xb & 0x0001) || (ay < -0.35f);
        case VK_DOWN:   return is_key_down(VK_DOWN)  || is_key_down('S') || (xb & 0x0002) || (ay > 0.35f);
        case VK_LEFT:   return is_key_down(VK_LEFT)  || is_key_down('A') || (xb & 0x0004) || (ax < -0.35f);
        case VK_RIGHT:  return is_key_down(VK_RIGHT) || is_key_down('D') || (xb & 0x0008) || (ax > 0.35f);
        case 'Z':       return is_key_down('Z') || is_key_down('J') || (g_chara_select_frames <= 0 && is_key_down(VK_RETURN)) || (xb & 0x1000);
        case 'X':       return is_key_down('X') || is_key_down('L') || (xb & 0x4000);
        case 'C':       return is_key_down('C') || is_key_down('K') || (xb & 0x2000);
        case 'V':       return is_key_down('V') || is_key_down('I') || (xb & 0x8000);
        case 'B':       return is_key_down('B');
        case VK_SPACE:  return is_key_down(VK_SPACE) || (xb & 0x0010);
        case VK_ESCAPE: return is_key_down(VK_ESCAPE);
        default:
            if (bit_idx > 0 && bit_idx < 256) return is_key_down(bit_idx);
            return 0;
    }
}

static inline uint32_t current_input_tick(void) {
    return g_logic_ticks ? g_logic_ticks : g_present_calls;
}

static void fwkbd_sync_bit(int bit_idx) {
    uint32_t f = current_input_tick() + 1u;
    if (g_fwkbd_last_frame[bit_idx] != f) {
        g_fwkbd_last_frame[bit_idx] = f;
        g_fwkbd_prev[bit_idx] = g_fwkbd_cur[bit_idx];
        g_fwkbd_cur[bit_idx] = (uint8_t)(fwkbd_bit_down(bit_idx) != 0);
    }
}

static void fwkbd_poll_frame_start(void) {
    static const int s_keys[] = {
        VK_UP, VK_DOWN, VK_LEFT, VK_RIGHT,
        'Z', 'X', 'C', 'V', 'B',
        VK_SPACE, VK_ESCAPE, VK_RETURN
    };
    uint32_t f = current_input_tick() + 1u;
    for (size_t i = 0; i < sizeof(s_keys) / sizeof(s_keys[0]); i++) {
        int k = s_keys[i];
        if (g_fwkbd_last_frame[k] != f) {
            fwkbd_sync_bit(k);
        }
    }
}

static void poll_mod_overlay_gamepad_input(void);

static void __thiscall hk_SceneTreeRootPreUpdate(void *root) {
    g_logic_ticks++;
    touch_gamepad_poll_mouse(g_game_hwnd, g_cfg_touch_hud);
    poll_mod_overlay_gamepad_input();
    fwkbd_poll_frame_start();
    typedef void (__thiscall *TreePreUpdate_t)(void *);
    ((TreePreUpdate_t)0x0062fb00)(root);
}

typedef void (__thiscall *FwInputMgr_Update_t)(void *self);
static FwInputMgr_Update_t g_real_fwinputmgr_update = NULL;
static void __thiscall hk_FwInputMgr_Update(void *self) {
    if (g_real_fwinputmgr_update) {
        g_real_fwinputmgr_update(self);
    }
}

static inline int is_fw_keyboard_device(void *self) {
    if (!self) return 0;
    uint32_t vt = *(uint32_t *)self;
    return (vt == 0x007d09e4 || vt == 0x007d08c0);
}

static int __thiscall hk_FwInput_IsBitDown(void *self, int bit_idx) {
    if (g_menu_visible || g_netplay_menu_visible) return 0;
    if (is_fw_keyboard_device(self) && bit_idx >= 0 && bit_idx < 256) {
        fwkbd_sync_bit(bit_idx);
        if (g_fwkbd_cur[bit_idx]) {
            return 1;
        }
    }
    return g_real_fwinput_isbitdown ? g_real_fwinput_isbitdown(self, bit_idx) : 0;
}

static int __thiscall hk_FwInput_IsBitPressed(void *self, int bit_idx) {
    if (g_menu_visible || g_netplay_menu_visible) return 0;
    if (is_fw_keyboard_device(self) && bit_idx >= 0 && bit_idx < 256) {
        fwkbd_sync_bit(bit_idx);
        if (!g_fwkbd_prev[bit_idx] && g_fwkbd_cur[bit_idx]) {
            return 1;
        }
    }
    return g_real_fwinput_isbitpressed ? g_real_fwinput_isbitpressed(self, bit_idx) : 0;
}

static uint32_t g_live_match_frame = 0;

static int __thiscall hk_FwInput_IsBitReleased(void *self, int bit_idx) {
    if (g_menu_visible || g_netplay_menu_visible) return 0;
    if (is_fw_keyboard_device(self) && bit_idx >= 0 && bit_idx < 256) {
        fwkbd_sync_bit(bit_idx);
        if (g_fwkbd_prev[bit_idx] && !g_fwkbd_cur[bit_idx]) return 1;
    }
    return g_real_fwinput_isbitreleased ? g_real_fwinput_isbitreleased(self, bit_idx) : 0;
}

// Live-match pause check hook (0x00480492 -> 0x00455710): allows SPACE, ESC and Xbox Start to pause gameplay
// without aliasing ESC to VK_SPACE (0x00455590 confirm/start) inside menus.
static uint8_t __thiscall hk_MatchPauseCheck(void *self, int user_id) {
    if (g_menu_visible || g_netplay_menu_visible) return 0;
    typedef uint8_t (__thiscall *OrigPause_t)(void *, int);
    if (((OrigPause_t)0x00455710)(self, user_id)) return 1;
    if (user_id == 0) {
        fwkbd_sync_bit(VK_ESCAPE);
        if (!g_fwkbd_prev[VK_ESCAPE] && g_fwkbd_cur[VK_ESCAPE]) return 1;
        WORD xb = 0;
        static WORD s_prev_start = 0;
        xinput_get_p1(NULL, NULL, &xb);
        int st_edge = ((xb & 0x0010) && !(s_prev_start & 0x0010));
        s_prev_start = xb;
        if (st_edge) return 1;
    }
    return 0;
}

// ----------------------------------------------------------------------------
// Phase 4 Extra QoL: Classic VT2 TV Camera Lock (0x0054CA10, 0x00558890)
// & Match Physics Speed Multiplier (0x00482AA1 tracker + 0x0043037B stepper)
// ----------------------------------------------------------------------------
static float g_match_speed_acc = 0.0f;

static void __cdecl hk_SetMatchCamera(int cam_type, int apply_now) {
    int eff = g_cfg_classic_tv_cam ? 0 : cam_type;
    if (g_real_set_match_cam) {
        g_real_set_match_cam(eff, apply_now);
    }
}

typedef uint8_t (__thiscall *ShotCamTriggerFn_t)(void *self, int arg1, int arg2);
static ShotCamTriggerFn_t g_real_shotcam_trigger = NULL;
static uint8_t __thiscall hk_ShotCamera_Trigger(void *self, int arg1, int arg2) {
    if (g_cfg_classic_tv_cam) return 0;
    return g_real_shotcam_trigger ? g_real_shotcam_trigger(self, arg1, arg2) : 0;
}

typedef void (__thiscall *CommitInputFn_t)(void *self, int slot, const uint8_t *pkt);
typedef void (__thiscall *RandomSetSeedFn_t)(void *self, const char *name, uint32_t seed);
static CommitInputFn_t    g_real_commit_input_482e10    = NULL;
static NpSampleInputFn_t  g_real_sample_input_483190    = NULL;
static RandomSetSeedFn_t  g_real_random_setseed_632cf0  = NULL;
static void              *g_np_match_input_mgr          = NULL;

static void __thiscall hk_CommitInput_482e10(void *self, int slot, const uint8_t *pkt) {
    g_np_match_input_mgr = self;
    if (netplay_is_stepping() && (slot == 0 || slot == 1) && pkt) {
        const uint8_t *np_pkt = netplay_get_slot_input(slot);
        if (np_pkt) {
            uint8_t sub[3];
            sub[0] = np_pkt[0];
            sub[1] = np_pkt[1];
            sub[2] = (uint8_t)((np_pkt[2] & 0x1Fu) | (pkt[2] & 0x40u));
            if (g_real_commit_input_482e10) g_real_commit_input_482e10(self, slot, sub);
            return;
        }
    }
    if (g_real_commit_input_482e10) g_real_commit_input_482e10(self, slot, pkt);
}

static int get_p1_player_state(void) {
    void *p1 = np_get_player_by_slot(0);
    if (!bhud_is_readable(p1, 0x250)) return -1;
    return *(const int *)((const char *)p1 + 0x248);
}

static void sample_p1_override_input(uint8_t *out3) {
    if (!out3 || g_menu_visible || g_netplay_menu_visible) return;
    static uint32_t s_p1_tick = 0xFFFFFFFFu;
    static uint8_t  s_p1_prev_mask = 0;
    static uint8_t  s_p1_cur_mask = 0;
    static uint8_t  s_buf_mask = 0;
    static int      s_buf_ticks = 0;

    WORD xbtns = 0;
    xinput_get_p1(NULL, NULL, &xbtns);

    uint32_t cur_t = current_input_tick() + 1u;
    uint8_t rising = 0;
    if (s_p1_tick != cur_t) {
        s_p1_tick = cur_t;
        s_p1_prev_mask = s_p1_cur_mask;
        uint8_t m = 0;
        if (is_key_down('Z') || is_key_down('J') || is_key_down(VK_RETURN) || (xbtns & 0x1000)) m |= 1u; // Topspin / A
        if (is_key_down('X') || is_key_down('L') || (xbtns & 0x4000))                           m |= 2u; // Slice   / X
        if (is_key_down('C') || is_key_down('K') || (xbtns & 0x2000))                           m |= 4u; // Lob     / B
        if (is_key_down('V') || is_key_down('I') || (xbtns & 0x8000))                           m |= 8u; // Dropshot/ Y
        s_p1_cur_mask = m;
        rising = (uint8_t)(s_p1_cur_mask & ~s_p1_prev_mask);
        if (rising) {
            s_buf_mask = rising;
            s_buf_ticks = 20;
        } else if (s_buf_ticks > 0) {
            s_buf_ticks--;
            if (s_buf_ticks == 0) s_buf_mask = 0;
        }
    } else {
        rising = (uint8_t)(s_p1_cur_mask & ~s_p1_prev_mask);
    }

    uint8_t sega_edge_only = *(const uint8_t *)0x008232d1;
    int p1_state = get_p1_player_state();
    uint8_t emit = rising;
    if (p1_state == 2 || p1_state == 3 || p1_state == 10 || p1_state == 11) {
        s_buf_ticks = 0;
        s_buf_mask = 0;
    } else if (!sega_edge_only || (p1_state >= 4 && p1_state <= 9) || p1_state == 0 || p1_state == 1 || p1_state < 0) {
        emit = (uint8_t)(rising | s_p1_cur_mask);
        if (!emit && s_buf_ticks > 0) {
            emit = s_buf_mask;
        }
    }

    if (emit & 1u) out3[2] |= 0x01u;
    if (emit & 2u) out3[2] |= 0x11u;
    if (emit & 4u) out3[2] |= 0x02u;
    if (emit & 8u) out3[2] |= 0x04u;
    if (s_p1_cur_mask & 0x0Fu) out3[2] |= 0x08u;

    static int s_itest_init = 0;
    static int s_itest_on = 0;
    static int s_itest_cnt = 0;
    if (!s_itest_init) {
        s_itest_init = 1;
        char ibuf[16];
        if (GetEnvironmentVariableA("VT4_INPUT_TEST", ibuf, sizeof(ibuf)) > 0 && ibuf[0] == '1') {
            s_itest_on = 1;
        }
    }
    if (s_itest_on && s_itest_cnt < 80 && (out3[0] || out3[1] || (out3[2] & 0x1Fu))) {
        s_itest_cnt++;
        log_msg("[VT4-InputTest] tick=%u st=%d dx=%d dy=%d btns=0x%02x mask=0x%x->0x%x emit=0x%x buf=%d",
                cur_t, p1_state, (int)(int8_t)out3[0], (int)(int8_t)out3[1], (unsigned)out3[2],
                (unsigned)s_p1_prev_mask, (unsigned)s_p1_cur_mask, (unsigned)emit, s_buf_ticks);
    }
}

static uint8_t *__thiscall hk_SamplePlayerInput_483190(void *self, uint8_t *out3, int slot, uint8_t cam_rot) {
    g_np_match_input_mgr = self;
    if (netplay_is_stepping() && (slot == 0 || slot == 1) && out3) {
        const uint8_t *np_pkt = netplay_get_slot_input(slot);
        if (np_pkt) {
            out3[0] = np_pkt[0];
            out3[1] = np_pkt[1];
            out3[2] = np_pkt[2];
        } else {
            out3[0] = 0; out3[1] = 0; out3[2] = 0;
        }
        return out3;
    }
    uint8_t *res = g_real_sample_input_483190 ? g_real_sample_input_483190(self, out3, slot, cam_rot) : out3;
    if (slot == 0 && res) {
        sample_p1_override_input(res);
    }
    return res;
}

static uint8_t *__thiscall np_sample_local_p1_483190(void *self, uint8_t *out3, int slot, uint8_t cam_rot) {
    uint8_t *res = g_real_sample_input_483190 ? g_real_sample_input_483190(self, out3, slot, cam_rot) : out3;
    if (slot == 0 && res) {
        sample_p1_override_input(res);
    }
    return res;
}

static void __thiscall hk_Random_SetSeed_632cf0(void *self, const char *name, uint32_t seed) {
    if (netplay_has_session_seed()) {
        seed = netplay_get_session_seed();
    }
    if (g_real_random_setseed_632cf0) g_real_random_setseed_632cf0(self, name, seed);
}

static void __thiscall hk_MatchInputUpdate_481a60(void *match_self) {
    if (match_self) {
        g_np_match_input_mgr = (char *)match_self + 0x60;
        netplay_ensure_p2_human(match_self);
    }
    typedef void (__thiscall *MatchInputUpd_t)(void *);
    ((MatchInputUpd_t)0x00481a60)(match_self);
}

static void __thiscall hk_LiveMatchTracker_4803e0(void *self) {
    if (self &&
        *(uint8_t *)((char *)self + 0x134) == 1 &&
        *(int *)((char *)self + 0x78) == 2 &&
        *(uint8_t *)0x008232f6 == 0 &&
        *(int *)0x008232f0 == 0) {
        g_np_match_input_mgr = (char *)self + 0x60;
        if (g_live_match_frame == 0 || g_present_calls > g_live_match_frame + 120) {
            log_msg("[VT4-Mod] LiveMatch ready at frame %u", g_present_calls);
            bhud_reset_match_telemetry();
            if (g_vp_p1_id >= 0) {
                vp_on_match_start(g_vp_p1_id, g_vp_p2_id);
            }
            netplay_on_live_match_ready(self, g_vp_p1_id, g_vp_p2_id);
        }
        g_live_match_frame = g_present_calls;
        perf_bench_on_live_match_ready();
        ee_on_live_match_tick(self);
        bhud_update_live_score(self, g_cfg_debug_log);
    }
    typedef void (__thiscall *Orig_t)(void *);
    ((Orig_t)0x004803e0)(self);
}

static void __cdecl hk_FrameStep_42fa90(int ticks, int flag) {
    typedef void (__cdecl *StepFn_t)(int, int);
    StepFn_t real_step = (StepFn_t)0x0042fa90;
    int in_live_match = (g_live_match_frame != 0 &&
                         g_present_calls <= g_live_match_frame + 1 &&
                         *(uint8_t *)0x008232f6 == 0 &&
                         *(int *)0x008232f0 == 0 &&
                         !g_menu_visible &&
                         !g_netplay_menu_visible);
    if (in_live_match && netplay_is_enabled()) {
        g_match_speed_acc = 0.0f;
        if (!netplay_pre_step(g_np_match_input_mgr, np_sample_local_p1_483190)) {
            Sleep(1);
            return;
        }
        perf_bench_on_logic_tick(1);
        real_step(1, 0);
        netplay_post_step();
        if (g_perf_pacer_active) perf_pacer_wait();
        return;
    }
    if (!in_live_match || g_cfg_match_speed_mode == 0 ||
        g_cfg_match_speed_mode >= (uint32_t)NUM_SPEED_CHOICES) {
        g_match_speed_acc = 0.0f;
        if (g_perf_pacer_active) {
            perf_bench_on_logic_tick(1);
            real_step(1, 0);
            perf_pacer_wait();
            return;
        }
        perf_bench_on_logic_tick(flag ? 1 : ticks);
        real_step(ticks, flag);
        return;
    }
    float mult = s_speed_choices[g_cfg_match_speed_mode].mult;
    g_match_speed_acc += mult * (float)(g_perf_pacer_active ? 1 : (ticks > 0 ? ticks : 1));
    int run_ticks = (int)g_match_speed_acc;
    g_match_speed_acc -= (float)run_ticks;
    if (run_ticks > 0) {
        perf_bench_on_logic_tick(run_ticks);
        // Clear flag (arg2=0) when run_ticks > 1 so 0x0042fad4 does not clamp subticks back to 1
        real_step(run_ticks, g_perf_pacer_active ? 0 : (run_ticks > 1 ? 0 : flag));
    }
    if (g_perf_pacer_active) perf_pacer_wait();
}

// ----------------------------------------------------------------------------
// EXTRA-5: Exhibition Rules Unlock & Preset Hooks (0x004351e1 & 0x00436e20)
// Allows full 5 Sets x 6 Games + Tie-Break inside Exhibition + fixes Advanced Settings Assert
// ----------------------------------------------------------------------------
static void apply_exhibition_rule_preset(void) {
    if (g_cfg_exb_rules == 0 || g_cfg_exb_rules >= (uint32_t)NUM_EXB_RULES_CHOICES) return;
    typedef void *(__cdecl *GetRulesFn_t)(void);
    typedef void (__cdecl *SetRulesFn_t)(const void *);
    uint32_t buf[5];
    memcpy(buf, ((GetRulesFn_t)0x0045f4b0)(), sizeof(buf));
    uint32_t want_sets = (uint32_t)s_exb_rules_choices[g_cfg_exb_rules].sets;
    uint32_t want_games = (uint32_t)s_exb_rules_choices[g_cfg_exb_rules].games;
    uint32_t want_tb_bit = s_exb_rules_choices[g_cfg_exb_rules].tiebreak ? 0u : 2u;
    if (buf[1] == want_sets && buf[2] == want_games && (buf[4] & 2u) == want_tb_bit) return;
    buf[1] = want_sets;
    buf[2] = want_games;
    if (s_exb_rules_choices[g_cfg_exb_rules].tiebreak) {
        buf[4] &= ~2u; // bit 1 = 0 -> Tie-Break ON
    } else {
        buf[4] |= 2u;  // bit 1 = 1 -> Tie-Break OFF (advantage set)
    }
    ((SetRulesFn_t)0x0045f480)(buf);
    log_msg("[VT4-Mod] Applied Exhibition Rules preset #%u: Sets=%u Games=%u TieBreak=%d (flags=0x%x)",
            g_cfg_exb_rules, buf[1], buf[2], s_exb_rules_choices[g_cfg_exb_rules].tiebreak, buf[4]);
}

typedef int (__cdecl *ExModeResetFn_t)(void);
static ExModeResetFn_t g_real_exmode_reset = NULL;
static int __cdecl hk_ExMode_ResetDefaults(void) {
    int r = g_real_exmode_reset ? g_real_exmode_reset() : 0;
    apply_exhibition_rule_preset();
    return r;
}

typedef void (__cdecl *SetRulesFn_orig_t)(const void *);
static SetRulesFn_orig_t g_real_set_rules = NULL;
static void __cdecl hk_SetMatchRules(const uint32_t *in_buf) {
    uint32_t tmp[5];
    memcpy(tmp, in_buf, sizeof(tmp));
    void *ret = __builtin_return_address(0);
    static uint32_t s_last_sets = 0xFFFFFFFFu, s_last_games = 0xFFFFFFFFu, s_last_flags = 0xFFFFFFFFu;
    if (g_cfg_exb_rules > 0 && g_cfg_exb_rules < (uint32_t)NUM_EXB_RULES_CHOICES) {
        uintptr_t ra = (uintptr_t)ret;
        // Preserve preset when Exhibition initializes/resets or exits Exhibition menus
        if (ra >= 0x00434000 && ra <= 0x00437000) {
            tmp[1] = (uint32_t)s_exb_rules_choices[g_cfg_exb_rules].sets;
            tmp[2] = (uint32_t)s_exb_rules_choices[g_cfg_exb_rules].games;
            if (s_exb_rules_choices[g_cfg_exb_rules].tiebreak) tmp[4] &= ~2u;
            else tmp[4] |= 2u;
        }
    }
    if (tmp[1] != s_last_sets || tmp[2] != s_last_games || tmp[4] != s_last_flags) {
        s_last_sets = tmp[1];
        s_last_games = tmp[2];
        s_last_flags = tmp[4];
        log_msg("[VT4-Mod] MatchRules active (caller=%p): valid=%u Sets=%u Games=%u TieBreak=%d flags=0x%x",
                ret, tmp[0], tmp[1], tmp[2], (tmp[4] & 2u) ? 0 : 1, tmp[4]);
    }
    if (g_real_set_rules) g_real_set_rules(tmp);
}

// ----------------------------------------------------------------------------
// EXTRA-6: Post-Effect Bloom / Glare & DOF Blur Reduction Hook (0x004a9460)
// Eliminates blurry SEGA DOF softness & excessive bloom halos on demand
// ----------------------------------------------------------------------------
typedef void (__fastcall *RenderPostFXFn_t)(void *self, void *edx_unused);
static RenderPostFXFn_t g_real_render_postfx = NULL;

static void __fastcall hk_RenderPostEffects(void *self, void *edx_unused) {
    if (!g_real_render_postfx) return;
    if (g_cfg_clean_postfx == 0 || !self) {
        g_real_render_postfx(self, edx_unused);
        return;
    }
    float orig_glare = *(float *)((char *)self + 0xf10);
    uint8_t orig_dof = *(uint8_t *)((char *)self + 0xf14);
    if (g_cfg_clean_postfx == 1) {
        *(float *)((char *)self + 0xf10) = 0.0f;
        *(uint8_t *)((char *)self + 0xf14) = 0;
    } else if (g_cfg_clean_postfx == 2) {
        *(float *)((char *)self + 0xf10) = orig_glare * 0.35f;
        *(uint8_t *)((char *)self + 0xf14) = 0;
    }
    static uint32_t s_last_pfx = 0xFFFFFFFFu;
    if (s_last_pfx != g_cfg_clean_postfx) {
        s_last_pfx = g_cfg_clean_postfx;
        log_msg("[VT4-Mod] [EXTRA-6] PostFX sharpness active: mode=%u (glare=%.3f->%.3f, dof=%u->0)",
                g_cfg_clean_postfx, orig_glare, *(float *)((char *)self + 0xf10), (unsigned)orig_dof);
    }
    g_real_render_postfx(self, edx_unused);
    *(float *)((char *)self + 0xf10) = orig_glare;
    *(uint8_t *)((char *)self + 0xf14) = orig_dof;
}

// ----------------------------------------------------------------------------
// Fase 3 Easter Eggs: EE-2 Extreme Surface Battle (Mud/Ice) & EE-4 DBZ Super Shots
// Hook on 0x00478bf3 (call 0x00477740 BallPhysics::SimulateTrajectory)
// ----------------------------------------------------------------------------
static void __fastcall hk_BallSimulateTrajectory(
    void *ball_phys, void *edx_unused,
    float *start_pos, float *vel, float arg3, uint32_t arg4, uint32_t arg5) {
    typedef void (__fastcall *SimTrajFn_t)(void *, void *, float *, float *, float, uint32_t, uint32_t);
    SimTrajFn_t real_sim = (SimTrajFn_t)0x00477740;
    if (!ball_phys || !vel ||
        (g_cfg_multiverse_mode == 0 && g_cfg_weapon_mode == 0 && !g_cfg_pro_physics &&
         !g_cfg_broadcast_hud && !g_cfg_debug_log)) {
        real_sim(ball_phys, edx_unused, start_pos, vel, arg3, arg4, arg5);
        return;
    }

    float orig_grav = *(float *)((char *)ball_phys + 0x65cc);
    float orig_bxz = *(float *)((char *)ball_phys + 0x65ec);
    float orig_by = *(float *)((char *)ball_phys + 0x65f0);
    float v0z = vel[2];

    // EE-2: 50% Ice (-Z far half: low fast skid) / 50% Mud (+Z near half: high sticky clay pop)
    // Note: in 0x4781b8..0x47822e, larger BoundXZ (0x65ec) applies stronger XZ bounce friction (slower),
    // and BoundY (0x65f0) scales vertical bounce restitution.
    if (g_cfg_multiverse_mode == 1 || g_cfg_multiverse_mode == 3) {
        if (v0z < 0.0f) {
            *(float *)((char *)ball_phys + 0x65ec) = 0.20f;
            *(float *)((char *)ball_phys + 0x65f0) = 0.38f;
        } else {
            *(float *)((char *)ball_phys + 0x65ec) = 1.55f;
            *(float *)((char *)ball_phys + 0x65f0) = 1.22f;
        }
    }

    // EE-4: DBZ 300% Super Shots — scale vel by k and gravity by k^2 so spatial arc lands in-bounds!
    if (g_cfg_multiverse_mode == 2 || g_cfg_multiverse_mode == 3) {
        const float k = 1.55f;
        vel[0] *= k;
        vel[1] *= k;
        vel[2] *= k;
        *(float *)((char *)ball_phys + 0x65cc) = orig_grav * (k * k);
    } else if (g_cfg_pro_physics && !netplay_is_enabled()) {
        // Pro Physics: crisp +12% ball pace with matching k^2 gravity so landing spot stays identical
        const float kp = 1.12f;
        vel[0] *= kp;
        vel[1] *= kp;
        vel[2] *= kp;
        *(float *)((char *)ball_phys + 0x65cc) = orig_grav * (kp * kp);
    }

    if (g_cfg_multiverse_mode != 0) {
        static uint32_t s_mv_log_count = 0;
        if (s_mv_log_count < 8) {
            s_mv_log_count++;
            log_msg("[VT4-Mod] [FASE-3] Multiverse mode=%u shot vz=%.2f -> BoundXZ=%.2f BoundY=%.2f Grav=%.2f",
                    g_cfg_multiverse_mode, vel[2],
                    *(float *)((char *)ball_phys + 0x65ec),
                    *(float *)((char *)ball_phys + 0x65f0),
                    *(float *)((char *)ball_phys + 0x65cc));
        }
    }

    ee_on_ball_simulate(ball_phys, start_pos, vel);
    bhud_on_ball_simulate(vel, (int)g_cfg_debug_log);
    real_sim(ball_phys, edx_unused, start_pos, vel, arg3, arg4, arg5);

    if (g_cfg_debug_log) {
        static uint32_t s_traj_logs = 0;
        if (s_traj_logs < 12) {
            s_traj_logs++;
            uint32_t nframes = *(uint32_t *)((char *)ball_phys + 0x65fc);
            const char *base = (const char *)ball_phys;
            int bounce_f = -1;
            float bz = 0.0f, vy_pre = 0.0f, vy_post = 0.0f, vz_pre = 0.0f, vz_post = 0.0f, peak_y = 0.0f;
            for (uint32_t f = 1; f < nframes && f < 599; f++) {
                const float *prev = (const float *)(base + (f - 1) * 40);
                const float *cur  = (const float *)(base + f * 40);
                if (bounce_f < 0 && prev[6] < 0.0f && cur[6] > 0.0f) {
                    bounce_f = (int)f;
                    bz = cur[2];
                    vy_pre = prev[6];
                    vy_post = cur[6];
                    vz_pre = prev[7];
                    vz_post = cur[7];
                } else if (bounce_f >= 0) {
                    if (cur[1] > peak_y) peak_y = cur[1];
                    if (cur[6] < 0.0f) break;
                }
            }
            log_msg("[DIAG-TRAJ] mv=%u n=%u v0z=%.2f bounce_f=%d bz=%.2f vy=%.3f->%.3f vz=%.3f->%.3f peak_y=%.2f",
                    g_cfg_multiverse_mode, nframes, vel[2], bounce_f, bz,
                    vy_pre, vy_post, vz_pre, vz_post, peak_y);
        }
    }

    *(float *)((char *)ball_phys + 0x65cc) = orig_grav;
    *(float *)((char *)ball_phys + 0x65ec) = orig_bxz;
    *(float *)((char *)ball_phys + 0x65f0) = orig_by;
}

static void __thiscall hk_BallLaunch_480561(void *ball_phys, void *hit_info, void *player_anim) {
    typedef void (__thiscall *OrigLaunch_t)(void *, void *, void *);
    ((OrigLaunch_t)0x00478c20)(ball_phys, hit_info, player_anim);
    if (hit_info) {
        if (g_cfg_multiverse_mode == 2 || g_cfg_multiverse_mode == 3) {
            *(float *)((char *)hit_info + 0x18) *= 1.55f;
        } else if (g_cfg_pro_physics && g_cfg_multiverse_mode == 0 && !netplay_is_enabled()) {
            *(float *)((char *)hit_info + 0x18) *= 1.12f;
        }
        bhud_on_ball_launch(*(const uint32_t *)((const char *)hit_info + 0x00) == 0u);
    }
    ee_on_ball_launch(ball_phys, hit_info);
}

static void *__cdecl hk_ParseSdoBuffer(void *dec_buf, uint32_t dec_len) {
    return ee_parse_and_patch_sdo(dec_buf, dec_len);
}

// ----------------------------------------------------------------------------
// Action System Handlers (0x0062D830 & 0x00633A20-0x00633AA0)
// Universal menu navigation, sliders, and options for Arrows and WASD
// ----------------------------------------------------------------------------
static uint32_t g_hold_up = 0;
static uint32_t g_hold_down = 0;
static uint32_t g_hold_left = 0;
static uint32_t g_hold_right = 0;
static uint32_t g_hold_deci = 0;
static uint32_t g_last_action_frame[5] = {0};
static int g_action_state[5] = {0};

static int eval_action_repeat(int active, uint32_t *hold, uint32_t delay, uint32_t rate) {
    if (active) {
        (*hold)++;
        if (*hold == 1) return 1;
        if (*hold > delay && ((*hold - delay) % rate) == 0) return 1;
        return 0;
    } else {
        *hold = 0;
        return 0;
    }
}

static int __thiscall hk_CheckAction_62d830(void *self, uint32_t tag, int user_id) {
    if (g_menu_visible || g_netplay_menu_visible) return 0;
    int slot = -1;
    if (tag == 0x5570) slot = 0;           // "Up"
    else if (tag == 0x446F776E) slot = 1;  // "Down"
    else if (tag == 0x4C656674) slot = 2;  // "Left"
    else if (tag == 0x52696774) slot = 3;  // "Rigt"
    else if (tag == 0x44656369) slot = 4;  // "Deci"

    if (slot >= 0) {
        uint32_t cur_tick = current_input_tick() + 1u;
        if (g_last_action_frame[slot] != cur_tick) {
            g_last_action_frame[slot] = cur_tick;
            int active = 0;
            uint32_t *hold = NULL;
            uint32_t delay = 18, rate = 6;
            float ax = 0.0f, ay = 0.0f;
            WORD xb = 0;
            xinput_get_p1(&ax, &ay, &xb);
            switch (slot) {
                case 0: // Up
                    active = is_key_down(VK_UP) || is_key_down('W') || (xb & 0x0001) || (ay < -0.5f);
                    hold = &g_hold_up;
                    break;
                case 1: // Down
                    active = is_key_down(VK_DOWN) || is_key_down('S') || (xb & 0x0002) || (ay > 0.5f);
                    hold = &g_hold_down;
                    break;
                case 2: // Left
                    active = is_key_down(VK_LEFT) || is_key_down('A') || (xb & 0x0004) || (ax < -0.5f);
                    hold = &g_hold_left;
                    break;
                case 3: // Right
                    active = is_key_down(VK_RIGHT) || is_key_down('D') || (xb & 0x0008) || (ax > 0.5f);
                    hold = &g_hold_right;
                    break;
                case 4: // Deci
                    active = is_key_down(VK_RETURN) || is_key_down(VK_SPACE) || is_key_down('C') || (xb & 0x1000);
                    hold = &g_hold_deci;
                    delay = 30; rate = 20;
                    break;
            }
            g_action_state[slot] = eval_action_repeat(active, hold, delay, rate);
            if (g_action_state[slot] && g_present_calls < 600) {
                log_msg("[VT4-Mod] Action 0x%08x triggered (slot %d) at frame %u", tag, slot, g_present_calls);
            }
        }
        if (g_action_state[slot]) return 1;
    }

    // Fallback: check original controller if attached
    if (self) {
        uintptr_t dev_mgr = *(uintptr_t *)((char *)self + 0x13c);
        if (dev_mgr && *(uint8_t *)(dev_mgr + 0x35)) {
            typedef int (__thiscall *CheckCore_t)(void *self, uint32_t tag, int user, int mode);
            return ((CheckCore_t)0x0062d700)(self, tag, user_id, 0);
        }
    }
    return 0;
}

static int __thiscall hk_ActionUp(void *self)     { return hk_CheckAction_62d830(NULL, 0x5570, -1); }
static int __thiscall hk_ActionDown(void *self)   { return hk_CheckAction_62d830(NULL, 0x446F776E, -1); }
static int __thiscall hk_ActionLeft(void *self)   { return hk_CheckAction_62d830(NULL, 0x4C656674, -1); }
static int __thiscall hk_ActionRight(void *self)  { return hk_CheckAction_62d830(NULL, 0x52696774, -1); }
static int __thiscall hk_ActionDecide(void *self) { return hk_CheckAction_62d830(NULL, 0x44656369, -1); }

// ----------------------------------------------------------------------------
// Central Menu Navigation System (0x00455180, 0x004551E0, 0x00455240, 0x004552A0, 0x00455300, 0x00455440)
// Universal across all menus, difficulty select, EditPlayer, pause and sliders
// ----------------------------------------------------------------------------
typedef uint8_t (__thiscall *MenuInputFn_t)(void *self, int user);

static uint32_t g_nav_last_frame[6] = {0};
static int      g_nav_val[6] = {0};

static inline int eval_nav_key(int slot, int active, uint32_t delay, uint32_t rate) {
    uint32_t nav_tick = (g_chara_select_frames > 0 && !g_menu_visible && !g_netplay_menu_visible) ? (0x80000000u | g_chara_select_ticks) : (current_input_tick() + 1u);
    if (g_nav_last_frame[slot] != nav_tick) {
        g_nav_last_frame[slot] = nav_tick;
        if (active) {
            g_nav_hold[slot]++;
            if (g_nav_hold[slot] == 1) {
                g_nav_val[slot] = 1;
            } else if (g_nav_hold[slot] > delay && ((g_nav_hold[slot] - delay) % rate) == 0) {
                g_nav_val[slot] = 1;
            } else {
                g_nav_val[slot] = 0;
            }
        } else {
            g_nav_hold[slot] = 0;
            g_nav_val[slot] = 0;
        }
    }
    // Return frame-persistent value so all callers within the same frame
    // (e.g. 3D carousel cylinder and 2D description subtask) receive identical input
    return g_nav_val[slot];
}

static inline int original_menu_input_offset(void *self, int user, int offset) {
    if (!self) return 0;
    uint8_t *ctrl = *(uint8_t **)((char *)self + 0x0c);
    if (!ctrl || (uintptr_t)ctrl < 0x10000) return 0;
    if (user == -1) {
        for (int u = 0; u < 4; u++) {
            uint8_t *slot = ctrl + (u << 8) + offset;
            if (slot[0x1d]) return 1;
        }
        return 0;
    }
    if (user >= 0 && user < 4) {
        uint8_t *slot = ctrl + (user << 8) + offset;
        return slot[0x1d] != 0;
    }
    return 0;
}

// 0x00455180: Menu / Slider Left
static int __thiscall hk_MenuInput_Left(void *self, int user) {
    if (g_menu_visible || g_netplay_menu_visible) return 0;
    float ax = 0.0f; WORD xb = 0;
    xinput_get_p1(&ax, NULL, &xb);
    int kbd_active = is_key_down(VK_LEFT) || is_key_down('A');
    int xi_active  = (xb & 0x0004) || (ax < -0.5f);
    int active     = kbd_active || xi_active;
    if (active) {
        if (eval_nav_key(0, 1, 14, 4)) {
            if (g_present_calls < 600) {
                log_msg("[VT4-Mod] Menu Left triggered at frame %u (user=%d)", g_present_calls, user);
            }
            return 1;
        }
        return 0;
    }
    eval_nav_key(0, 0, 14, 4);
    return original_menu_input_offset(self, user, 0x08);
}

// 0x004551E0: Menu / Slider Right
static int __thiscall hk_MenuInput_Right(void *self, int user) {
    if (g_menu_visible || g_netplay_menu_visible) return 0;
    float ax = 0.0f; WORD xb = 0;
    xinput_get_p1(&ax, NULL, &xb);
    int kbd_active = is_key_down(VK_RIGHT) || is_key_down('D');
    int xi_active  = (xb & 0x0008) || (ax > 0.5f);
    int active     = kbd_active || xi_active;
    if (active) {
        if (eval_nav_key(1, 1, 14, 4)) {
            if (g_present_calls < 600) {
                log_msg("[VT4-Mod] Menu Right triggered at frame %u (user=%d)", g_present_calls, user);
            }
            return 1;
        }
        return 0;
    }
    eval_nav_key(1, 0, 14, 4);
    return original_menu_input_offset(self, user, 0x28);
}

// 0x00455240: Menu Up
static int __thiscall hk_MenuInput_Up(void *self, int user) {
    if (g_menu_visible || g_netplay_menu_visible) return 0;
    float ay = 0.0f; WORD xb = 0;
    xinput_get_p1(NULL, &ay, &xb);
    int kbd_active = is_key_down(VK_UP) || is_key_down('W');
    int xi_active  = (xb & 0x0001) || (ay < -0.5f);
    int active     = kbd_active || xi_active;
    if (active) {
        if (eval_nav_key(2, 1, 18, 6)) {
            if (g_present_calls < 600) {
                log_msg("[VT4-Mod] Menu Up triggered at frame %u (user=%d)", g_present_calls, user);
            }
            return 1;
        }
        return 0;
    }
    eval_nav_key(2, 0, 18, 6);
    return original_menu_input_offset(self, user, 0x48);
}

// 0x004552A0: Menu Down
static int __thiscall hk_MenuInput_Down(void *self, int user) {
    if (g_menu_visible || g_netplay_menu_visible) return 0;
    float ay = 0.0f; WORD xb = 0;
    xinput_get_p1(NULL, &ay, &xb);
    int kbd_active = is_key_down(VK_DOWN) || is_key_down('S');
    int xi_active  = (xb & 0x0002) || (ay > 0.5f);
    int active     = kbd_active || xi_active;
    if (active) {
        if (eval_nav_key(3, 1, 18, 6)) {
            if (g_present_calls < 600) {
                log_msg("[VT4-Mod] Menu Down triggered at frame %u (user=%d)", g_present_calls, user);
            }
            return 1;
        }
        return 0;
    }
    eval_nav_key(3, 0, 18, 6);
    return original_menu_input_offset(self, user, 0x68);
}

// 0x0078b6d8: Carousel Navigation Handlers
// Carousel calls vtable[1] (+4) for Prev (moves backwards/up) and vtable[2] (+8) for Next (moves forwards/down)
static int __thiscall hk_Carousel_Prev(void *self) {
    if (g_menu_visible || g_netplay_menu_visible) return 0;
    float ax = 0.0f, ay = 0.0f; WORD xb = 0;
    xinput_get_p1(&ax, &ay, &xb);
    int up = is_key_down(VK_UP) || is_key_down('W') || (xb & 0x0001) || (ay < -0.5f);
    int left = is_key_down(VK_LEFT) || is_key_down('A') || (xb & 0x0004) || (ax < -0.5f);
    if (eval_nav_key(2, up || left, 18, 6)) {
        if (g_present_calls < 600) {
            log_msg("[VT4-Mod] Carousel Prev triggered (UP/LEFT) at frame %u", g_present_calls);
        }
        return 1;
    }
    return 0;
}

static int __thiscall hk_Carousel_Next(void *self) {
    if (g_menu_visible || g_netplay_menu_visible) return 0;
    float ax = 0.0f, ay = 0.0f; WORD xb = 0;
    xinput_get_p1(&ax, &ay, &xb);
    int down = is_key_down(VK_DOWN) || is_key_down('S') || (xb & 0x0002) || (ay > 0.5f);
    int right = is_key_down(VK_RIGHT) || is_key_down('D') || (xb & 0x0008) || (ax > 0.5f);
    if (eval_nav_key(3, down || right, 18, 6)) {
        if (g_present_calls < 600) {
            log_msg("[VT4-Mod] Carousel Next triggered (DOWN/RIGHT) at frame %u", g_present_calls);
        }
        return 1;
    }
    return 0;
}

static int s_menu_enter_cooldown = 0;

// 0x00455300: Menu Decide / Enter
static MenuInputFn_t g_real_menu_decide = NULL;
static int __thiscall hk_MenuInput_Decide(void *self, int user) {
    if (g_menu_visible || g_netplay_menu_visible) return 0;
    if (s_menu_enter_cooldown > 0) {
        return 0; // Debounce lockout: ignore buffered Enter while transitioning from Title
    }
    WORD xb = 0;
    xinput_get_p1(NULL, NULL, &xb);
    int kbd_active = is_key_down(VK_RETURN) || is_key_down(VK_SPACE) || is_key_down('C');
    int xi_active  = (xb & 0x1000) != 0;
    int active     = kbd_active || xi_active;
    if (g_menu_close_cooldown_frame != 0 && g_present_calls <= g_menu_close_cooldown_frame + 12) {
        eval_nav_key(4, active, 30, 20);
        return 0;
    }
    if (active) {
        if (eval_nav_key(4, 1, 30, 20)) {
            if (g_present_calls < 600) {
                log_msg("[VT4-Mod] Menu Decide triggered at frame %u (user=%d)", g_present_calls, user);
            }
            return 1;
        }
        return 0;
    }
    eval_nav_key(4, 0, 30, 20);
    if (is_key_down(VK_ESCAPE) || is_key_down('Z') || is_key_down(VK_BACK)) {
        return 0;
    }
    if (g_real_gamepad_active) {
        return 0; // Avoid double-confirming via DirectInput + XInput/WinMM
    }
    if (g_real_menu_decide) {
        return g_real_menu_decide(self, user);
    }
    return 0;
}

// 0x00455440: Menu Cancel / Escape
static MenuInputFn_t g_real_menu_cancel = NULL;
static uint32_t s_cancel_cooldown_frame = 0;
static int __thiscall hk_MenuInput_Cancel(void *self, int user) {
    if (g_menu_visible || g_netplay_menu_visible) return 0;
    WORD xb = 0;
    xinput_get_p1(NULL, NULL, &xb);
    int kbd_active = is_key_down(VK_ESCAPE) || is_key_down(VK_BACK);
    int xi_active  = (xb & 0x2000) != 0;
    int active     = kbd_active || xi_active;
    if ((g_menu_close_cooldown_frame != 0 && g_present_calls <= g_menu_close_cooldown_frame + 12) ||
        (s_cancel_cooldown_frame != 0 && g_present_calls <= s_cancel_cooldown_frame + 20)) {
        eval_nav_key(5, active, 30, 20);
        return 0;
    }
    if (active) {
        if (eval_nav_key(5, 1, 30, 20)) {
            s_cancel_cooldown_frame = g_present_calls;
            if (g_present_calls < 600) {
                log_msg("[VT4-Mod] Menu Cancel triggered at frame %u (user=%d)", g_present_calls, user);
            }
            return 1;
        }
        return 0;
    }
    eval_nav_key(5, 0, 30, 20);
    if (g_real_gamepad_active) {
        return 0; // Avoid phantom double-back from DirectInput B/Button2 release
    }
    if (g_real_menu_cancel) {
        return g_real_menu_cancel(self, user);
    }
    return 0;
}

static void poll_mod_overlay_gamepad_input(void) {
    if (!g_menu_visible && !g_netplay_menu_visible) return;
    float ax = 0.0f, ay = 0.0f;
    WORD xb = 0;
    xinput_get_p1(&ax, &ay, &xb);

    int left  = ((xb & 0x0004) != 0) || (ax < -0.5f);
    int right = ((xb & 0x0008) != 0) || (ax >  0.5f);
    int up    = ((xb & 0x0001) != 0) || (ay < -0.5f);
    int down  = ((xb & 0x0002) != 0) || (ay >  0.5f);
    int ok    = ((xb & (0x1000 | 0x0010)) != 0);
    int back  = ((xb & 0x2000) != 0);
    int entry_grace = (g_mod_menu_open_frame != 0 && g_present_calls <= g_mod_menu_open_frame + 12);

    if (eval_nav_key(0, left, 14, 4)) {
        if (g_netplay_menu_visible) handle_netplay_menu_input(VK_LEFT);
        else handle_settings_menu_input(VK_LEFT, NULL);
    }
    if (eval_nav_key(1, right, 14, 4)) {
        if (g_netplay_menu_visible) handle_netplay_menu_input(VK_RIGHT);
        else handle_settings_menu_input(VK_RIGHT, NULL);
    }
    if (eval_nav_key(2, up, 18, 6)) {
        if (g_netplay_menu_visible) handle_netplay_menu_input(VK_UP);
        else handle_settings_menu_input(VK_UP, NULL);
    }
    if (eval_nav_key(3, down, 18, 6)) {
        if (g_netplay_menu_visible) handle_netplay_menu_input(VK_DOWN);
        else handle_settings_menu_input(VK_DOWN, NULL);
    }

    int ok_trig = eval_nav_key(4, ok, 30, 20);
    if (ok_trig && !entry_grace) {
        if (g_netplay_menu_visible) handle_netplay_menu_input(VK_RETURN);
        else handle_settings_menu_input(VK_RETURN, NULL);
    }

    int bk_trig = eval_nav_key(5, back, 30, 20);
    if (bk_trig && !entry_grace) {
        s_cancel_cooldown_frame = g_present_calls;
        if (g_netplay_menu_visible) {
            close_netplay_menu();
            play_vt4_menu_se(6);
        } else {
            handle_settings_menu_input(VK_ESCAPE, NULL);
        }
    }
}

// 0x00454F80 (Analog X: Left=-1.0, Right=+1.0) & 0x00455080 (Analog Y: Up=-1.0, Down=+1.0)
typedef float (__thiscall *AnalogAxisFn_t)(void *self, int user);
static AnalogAxisFn_t g_real_analog_x = NULL;
static AnalogAxisFn_t g_real_analog_y = NULL;

static float __thiscall hk_AnalogX(void *self, int user) {
    if (g_menu_visible || g_netplay_menu_visible) return 0.0f;
    if (user <= 0) {
        if (is_key_down(VK_LEFT) || is_key_down('A')) return -1.0f;
        if (is_key_down(VK_RIGHT) || is_key_down('D')) return 1.0f;
        float ax = 0.0f;
        if (xinput_get_p1(&ax, NULL, NULL) && ax != 0.0f) return ax;
    }
    return g_real_analog_x ? g_real_analog_x(self, user) : 0.0f;
}

static float __thiscall hk_AnalogY(void *self, int user) {
    if (g_menu_visible || g_netplay_menu_visible) return 0.0f;
    if (user <= 0) {
        if (is_key_down(VK_UP) || is_key_down('W')) return -1.0f;
        if (is_key_down(VK_DOWN) || is_key_down('S')) return 1.0f;
        float ay = 0.0f;
        if (xinput_get_p1(NULL, &ay, NULL) && ay != 0.0f) return ay;
    }
    return g_real_analog_y ? g_real_analog_y(self, user) : 0.0f;
}

static void __attribute__((naked)) hk_Safe45a920(void) {
    __asm__(
        "test %ecx, %ecx\n"
        "jz 1f\n"
        "cmp $0x10000, %ecx\n"
        "jb 1f\n"
        "mov 0x8c(%ecx), %eax\n"
        "test %eax, %eax\n"
        "jz 1f\n"
        "cmp $0x10000, %eax\n"
        "jb 1f\n"
        "mov (%eax), %edx\n"
        "test %edx, %edx\n"
        "jz 1f\n"
        "cmp $0x10000, %edx\n"
        "jb 1f\n"
        "push %ecx\n"
        "push %esi\n"
        "mov %ecx, %esi\n"
        "mov $0x0045A92A, %edx\n"
        "jmp *%edx\n"
        "1:\n"
        "ret\n"
    );
}

typedef int (__thiscall *InputCheckFn_t)(void *self, int user);
static InputCheckFn_t g_real_455590 = (InputCheckFn_t)0x00455590;
static InputCheckFn_t g_real_455300 = (InputCheckFn_t)0x00455300;

static int s_prev_start_key = 0;
static int __thiscall hk_IsStartPressed(void *self, int user) {
    WORD xb = 0;
    xinput_get_p1(NULL, NULL, &xb);
    int cur_down = is_key_down(VK_RETURN) || is_key_down(VK_SPACE) || ((xb & (0x1000 | 0x0010)) != 0);
    int triggered = (cur_down && !s_prev_start_key);
    s_prev_start_key = cur_down;
    if (triggered) {
        s_menu_enter_cooldown = 30;
        return 1;
    }
    return g_real_455590 ? g_real_455590(self, user) : 0;
}

static int s_prev_title_key = 0;
static int __thiscall hk_CheckInput_455300(void *self, int user) {
    WORD xb = 0;
    xinput_get_p1(NULL, NULL, &xb);
    int cur_down = is_key_down(VK_RETURN) || is_key_down(VK_SPACE) || ((xb & (0x1000 | 0x0010)) != 0);
    int triggered = (cur_down && !s_prev_title_key);
    s_prev_title_key = cur_down;
    if (triggered) {
        s_menu_enter_cooldown = 30;
        return 1;
    }
    return g_real_455300 ? g_real_455300(self, user) : 0;
}

static int is_loose_file_override(const char *rel_path, char *out_path, size_t out_size) {
    if (!rel_path || !rel_path[0]) return 0;

    LARGE_INTEGER _io_t0;
    if (g_cfg_bench_log) {
        g_bench_io_calls++;
        QueryPerformanceCounter(&_io_t0);
    }
    
    // Ignore requests for the archive containers themselves
    if (strstr(rel_path, "resource.bin") != NULL ||
        strstr(rel_path, "resource.1.bin") != NULL) {
        if (g_cfg_bench_log) { LARGE_INTEGER _t1; QueryPerformanceCounter(&_t1); g_bench_io_qpc_ticks += (_t1.QuadPart - _io_t0.QuadPart); }
        return 0;
    }
    
    const char *sub = rel_path;
    // Strip leading "./" or ".\\"
    if (sub[0] == '.' && (sub[1] == '/' || sub[1] == '\\')) {
        sub += 2;
    }
    // Strip leading "resource/" or "resource\"
    if (strnicmp(sub, "resource/", 9) == 0 || strnicmp(sub, "resource\\", 9) == 0) {
        sub += 9;
    }
    // Strip leading "archive/" or "archive\"
    if (strnicmp(sub, "archive/", 8) == 0 || strnicmp(sub, "archive\\", 8) == 0) {
        sub += 8;
    }
    
    if (!sub[0]) {
        if (g_cfg_bench_log) { LARGE_INTEGER _t1; QueryPerformanceCounter(&_t1); g_bench_io_qpc_ticks += (_t1.QuadPart - _io_t0.QuadPart); }
        return 0;
    }
    
    char clean[MAX_PATH];
    strncpy(clean, sub, sizeof(clean) - 1);
    clean[sizeof(clean) - 1] = '\0';
    for (char *p = clean; *p; p++) {
        if (*p == '/') *p = '\\';
    }

    // Dynamic Agassi skin portrait override: skin 0 ('91 blonde) redirects 29.dds -> 29_91.dds
    if (g_agassi_skin == 0) {
        if (stricmp(clean, "HIGH\\Frontend\\VR\\photo_L\\29.dds") == 0) {
            strcpy(clean, "HIGH\\Frontend\\VR\\photo_L\\29_91.dds");
        } else if (stricmp(clean, "HIGH\\Frontend\\VR\\photo_S\\29.dds") == 0) {
            strcpy(clean, "HIGH\\Frontend\\VR\\photo_S\\29_91.dds");
        } else if (stricmp(clean, "HIGH\\Frontend\\VR\\photo_eye\\29.dds") == 0) {
            strcpy(clean, "HIGH\\Frontend\\VR\\photo_eye\\29_91.dds");
        }
    }
    
    // Fast O(1) RAM hash cache lookup (0 GetFileAttributesA disk syscalls!)
    if (g_perf_io_ready) {
        int hit = perf_io_lookup(clean, out_path, out_size);
        if (g_cfg_bench_log) {
            if (hit) g_bench_io_hits++;
            LARGE_INTEGER _t1;
            QueryPerformanceCounter(&_t1);
            g_bench_io_qpc_ticks += (_t1.QuadPart - _io_t0.QuadPart);
        }
        return hit;
    }

    char candidate[MAX_PATH * 2];
    
    // 1. Check in game/archive/<clean>
    snprintf(candidate, sizeof(candidate), "%s\\archive\\%s", g_game_dir, clean);
    if (g_cfg_bench_log) g_bench_io_syscalls++;
    DWORD attr = GetFileAttributesA(candidate);
    if (attr != INVALID_FILE_ATTRIBUTES && !(attr & FILE_ATTRIBUTE_DIRECTORY)) {
        if (out_path && out_size > 0) {
            strncpy(out_path, candidate, out_size - 1);
            out_path[out_size - 1] = '\0';
        }
        if (g_cfg_bench_log) { g_bench_io_hits++; LARGE_INTEGER _t1; QueryPerformanceCounter(&_t1); g_bench_io_qpc_ticks += (_t1.QuadPart - _io_t0.QuadPart); }
        return 1;
    }
    
    // 2. Check in game/<clean> (only for subdirectories, to avoid matching root executables/dlls)
    if (strchr(clean, '\\') != NULL) {
        snprintf(candidate, sizeof(candidate), "%s\\%s", g_game_dir, clean);
        if (g_cfg_bench_log) g_bench_io_syscalls++;
        attr = GetFileAttributesA(candidate);
        if (attr != INVALID_FILE_ATTRIBUTES && !(attr & FILE_ATTRIBUTE_DIRECTORY)) {
            if (out_path && out_size > 0) {
                strncpy(out_path, candidate, out_size - 1);
                out_path[out_size - 1] = '\0';
            }
            if (g_cfg_bench_log) { g_bench_io_hits++; LARGE_INTEGER _t1; QueryPerformanceCounter(&_t1); g_bench_io_qpc_ticks += (_t1.QuadPart - _io_t0.QuadPart); }
            return 1;
        }
    }
    
    if (g_cfg_bench_log) { LARGE_INTEGER _t1; QueryPerformanceCounter(&_t1); g_bench_io_qpc_ticks += (_t1.QuadPart - _io_t0.QuadPart); }
    return 0;
}

static uint32_t g_loose_checks = 0;
static int check_loose_file(const char *rel_path) {
    bhud_on_archive_lookup(rel_path);
    if (g_cfg_debug_log && g_loose_checks < 20) {
        log_msg("[VT4-Mod] Archive lookup #%u: '%s'", g_loose_checks, rel_path ? rel_path : "NULL");
        g_loose_checks++;
    }
    char resolved[MAX_PATH * 2];
    if (is_loose_file_override(rel_path, resolved, sizeof(resolved))) {
        if (g_cfg_debug_log) {
            log_msg("[VT4-Mod] [LOOSE] Archive override detected: %s -> %s", rel_path, resolved);
        }
        return 1;
    }
    return 0;
}

__attribute__((used)) void *g_fn_check_loose = (void *)check_loose_file;

typedef HANDLE (WINAPI *CreateFileA_t)(LPCSTR lpFileName, DWORD dwDesiredAccess, DWORD dwShareMode,
                                       LPSECURITY_ATTRIBUTES lpSecurityAttributes, DWORD dwCreationDisposition,
                                       DWORD dwFlagsAndAttributes, HANDLE hTemplateFile);
static CreateFileA_t g_real_createfilea = NULL;

static HANDLE WINAPI hk_CreateFileA(LPCSTR lpFileName, DWORD dwDesiredAccess, DWORD dwShareMode,
                                    LPSECURITY_ATTRIBUTES lpSecurityAttributes, DWORD dwCreationDisposition,
                                    DWORD dwFlagsAndAttributes, HANDLE hTemplateFile) {
    if (lpFileName && lpFileName[0]) {
        char resolved[MAX_PATH * 2];
        if (is_loose_file_override(lpFileName, resolved, sizeof(resolved))) {
            if (g_cfg_debug_log) {
                log_msg("[VT4-Mod] [LOOSE] CreateFileA redirected: %s -> %s", lpFileName, resolved);
            }
            return g_real_createfilea(resolved, dwDesiredAccess, dwShareMode,
                                      lpSecurityAttributes, dwCreationDisposition,
                                      dwFlagsAndAttributes, hTemplateFile);
        }
    }
    return g_real_createfilea(lpFileName, dwDesiredAccess, dwShareMode,
                              lpSecurityAttributes, dwCreationDisposition,
                              dwFlagsAndAttributes, hTemplateFile);
}

typedef int (__cdecl *fopen_s_t)(FILE **pFile, const char *filename, const char *mode);
static fopen_s_t g_real_fopens = NULL;

static int __cdecl hk_fopen_s(FILE **pFile, const char *filename, const char *mode) {
    if (filename && filename[0]) {
        char resolved[MAX_PATH * 2];
        if (is_loose_file_override(filename, resolved, sizeof(resolved))) {
            if (g_cfg_debug_log) {
                log_msg("[VT4-Mod] [LOOSE] fopen_s redirected: %s -> %s", filename, resolved);
            }
            return g_real_fopens(pFile, resolved, mode);
        }
    }
    return g_real_fopens(pFile, filename, mode);
}

typedef FILE *(__cdecl *fopen_t)(const char *filename, const char *mode);
static fopen_t g_real_fopen = NULL;

static FILE *__cdecl hk_fopen(const char *filename, const char *mode) {
    if (filename && filename[0]) {
        char resolved[MAX_PATH * 2];
        if (is_loose_file_override(filename, resolved, sizeof(resolved))) {
            if (g_cfg_debug_log) {
                log_msg("[VT4-Mod] [LOOSE] fopen redirected: %s -> %s", filename, resolved);
            }
            return g_real_fopen(resolved, mode);
        }
    }
    return g_real_fopen(filename, mode);
}

typedef BOOL (WINAPI *PathFileExistsA_t)(LPCSTR pszPath);
static PathFileExistsA_t g_real_pathfileexistsa = NULL;

static BOOL WINAPI hk_PathFileExistsA(LPCSTR pszPath) {
    if (pszPath && pszPath[0]) {
        char resolved[MAX_PATH * 2];
        if (is_loose_file_override(pszPath, resolved, sizeof(resolved))) {
            if (g_cfg_debug_log) {
                log_msg("[VT4-Mod] [LOOSE] PathFileExistsA redirected: %s -> %s", pszPath, resolved);
            }
            return TRUE;
        }
    }
    return g_real_pathfileexistsa(pszPath);
}

static void __attribute__((naked)) hk_Archive_CheckDirectory(void) {
    __asm__(
        "pusha\n"
        "push %ecx\n"
        "mov _g_fn_check_loose, %eax\n"
        "call *%eax\n"
        "add $4, %esp\n"
        "test %eax, %eax\n"
        "jz 1f\n"
        "popa\n"
        "xor %al, %al\n"
        "ret $0x18\n"
        
        "1:\n"
        "popa\n"
        "mov $0x004072d0, %edx\n"
        "jmp *%edx\n"
    );
}

// 0x00407380: int __thiscall ArchiveDir_FindIndex(const char *rel_path /* ecx */, void *dir_table /* [esp+4] */)
// Prologue (6 bytes): 55 (push ebp) 8b ec (mov ebp, esp) 83 e4 f8 (and esp, -8)
// Returning -1 (0xffffffff) when a loose file exists in game/archive/ forces all 5 callers
// (0x004072e1, 0x0040c256, 0x00417b51, 0x00417cc3, 0x00417e12) to take the standalone loose-file path
// via 0x00405d70 -> hk_CreateFileA, even for files packed inside parent containers (vol == -1).
static void __attribute__((naked)) hk_ArchiveDir_FindIndex(void) {
    __asm__(
        "pusha\n"
        "push %ecx\n"
        "mov _g_fn_check_loose, %eax\n"
        "call *%eax\n"
        "add $4, %esp\n"
        "test %eax, %eax\n"
        "jz 1f\n"
        "popa\n"
        "mov $0xffffffff, %eax\n"
        "ret $4\n"

        "1:\n"
        "popa\n"
        "push %ebp\n"
        "mov %esp, %ebp\n"
        "and $0xfffffff8, %esp\n"
        "mov $0x00407386, %edx\n"
        "jmp *%edx\n"
    );
}

typedef void (__thiscall *Carousel_AddItem_t)(void *self, const char *name, void *param1, int enabled);
static Carousel_AddItem_t g_real_carousel_additem = NULL;
static void __thiscall hk_Carousel_AddItem(void *self, const char *name, void *param1, int enabled) {
    log_msg("[VT4-Mod] Carousel::AddItem: name='%s' param1=%p enabled=%d self=%p",
            name ? name : "(null)", param1, enabled, self);
    if (name && (stricmp(name, "Live") == 0 || strcmp(name, "") == 0)) {
        log_msg("[VT4-Mod] Carousel::AddItem: BLOCKED Live item!");
        return;
    }
    if (g_real_carousel_additem) {
        g_real_carousel_additem(self, name, param1, enabled);
    }
}

static void apply_remove_live_mode_patch(void) {
    if (!g_cfg_remove_live) return;

    if (!g_real_carousel_additem) {
        g_real_carousel_additem = (Carousel_AddItem_t)make_trampoline(0x00634e80, 7);
        install_jmp(0x00634e80, (void *)hk_Carousel_AddItem, 7);
        log_msg("[VT4-Mod] Carousel::AddItem hooked at 0x00634e80 (Live blocker active)");
    }

    // 1. In MainMenu::SetupCarousel (0x0043ebb8), NOP out adding "Live" item (14 bytes)
    // 0x0043ebb8: 53 57 68 dc a6 78 00 8b ce e8 ba 62 1f 00
    const uint8_t nops_14[14] = {
        0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90,
        0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90
    };
    patch_bytes(0x0043ebb8, nops_14, 14);

    // 2. Adjust carousel modulo item count from 10 (0x0a) to 9 (0x09)
    const uint8_t count_9_ecx[5] = { 0xb9, 0x09, 0x00, 0x00, 0x00 };
    patch_bytes(0x0043eac8, count_9_ecx, 5);

    const uint8_t set_len_9[7] = { 0xc7, 0x46, 0x6c, 0x09, 0x00, 0x00, 0x00 };
    patch_bytes(0x00634cb9, set_len_9, 7);

    // 3. Blank out "Live" string at 0x0078a6dc
    patch_bytes(0x0078a6dc, "\0\0\0\0", 4);

    // 4. Enable all carousel items unconditionally on PC:
    // Bypass demo/platform check at 0x0043eb09 that cleared [esp+0x14] (which disabled Arcade, Exhibition, etc.)
    const uint8_t enable_all_carousel_items[20] = {
        0xeb, 0x12, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90,
        0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90
    };
    patch_bytes(0x0043eb09, enable_all_carousel_items, sizeof(enable_all_carousel_items));
    log_msg("[VT4-Mod] Patched 0x0043eb09: All Main Menu carousel items unlocked (Arcade, Exhibition, Training)");

    log_msg("[VT4-Mod] LIVE Mode cleanly eliminated from Main Menu carousel (9 items total)");
}

static int safe_check_bytes(uintptr_t va, const uint8_t *expected, size_t len) {
    MEMORY_BASIC_INFORMATION mbi;
    if (!VirtualQuery((const void *)va, &mbi, sizeof(mbi))) return 0;
    if (mbi.State != MEM_COMMIT) return 0;
    DWORD prot = mbi.Protect & 0xFF;
    if (prot != PAGE_READONLY && prot != PAGE_READWRITE && prot != PAGE_EXECUTE_READ &&
        prot != PAGE_EXECUTE_READWRITE && prot != PAGE_EXECUTE_WRITECOPY && prot != PAGE_WRITECOPY) {
        return 0;
    }
    uintptr_t region_end = (uintptr_t)mbi.BaseAddress + mbi.RegionSize;
    if (va + len > region_end) return 0;
    return memcmp((const void *)va, expected, len) == 0;
}

static void show_unsupported_exe_warning(const char *msg) {
    HMODULE hUser32 = GetModuleHandleA("user32.dll");
    if (!hUser32) hUser32 = LoadLibraryA("user32.dll");
    if (hUser32) {
        typedef int (__stdcall *MsgBoxA_t)(HWND, LPCSTR, LPCSTR, UINT);
        MsgBoxA_t fn = (MsgBoxA_t)GetProcAddress(hUser32, "MessageBoxA");
        if (fn) {
            fn(NULL, msg, "VT4 Legends - Unsupported VT4.exe", MB_OK | MB_ICONWARNING);
        }
    }
}

static int verify_vt4_exe_signature(void) {
    HMODULE hMod = GetModuleHandleA(NULL);
    if ((uintptr_t)hMod != 0x00400000u) {
        log_msg("[VT4-Mod] ERROR: Unsupported VT4.exe base address %p (expected 0x00400000)! Aborting memory patches and running vanilla.", hMod);
        show_unsupported_exe_warning(
            "Unsupported VT4.exe image base detected (expected PC v1.0 unpacked at 0x00400000).\n"
            "Memory patches were safely aborted; running vanilla GFWL compatibility only.\n"
            "See xlive_mod.log for details.");
        return 0;
    }

    static const uint8_t sig_res[12]   = { 0x80, 0x02, 0x00, 0x00, 0xC7, 0x85, 0x58, 0x01, 0x00, 0x00, 0xE0, 0x01 };
    static const uint8_t sig_chdir[12] = { 0x68, 0xF4, 0x96, 0x78, 0x00, 0xFF, 0x15, 0x4C, 0x80, 0x78, 0x00, 0x6A };
    static const uint8_t sig_fidx[12]  = { 0x55, 0x8B, 0xEC, 0x83, 0xE4, 0xF8, 0x83, 0xEC, 0x24, 0x53, 0x8B, 0x5D };
    static const uint8_t sig_unlk[12]  = { 0x8B, 0x44, 0x24, 0x04, 0x53, 0x57, 0x0F, 0xB6, 0xB8, 0x50, 0x5F, 0x7C };
    static const uint8_t sig_sto[12]   = { 0x6A, 0xFF, 0x68, 0xA8, 0xFD, 0x77, 0x00, 0x64, 0xA1, 0x00, 0x00, 0x00 };
    static const struct { uintptr_t va; const uint8_t *bytes; size_t len; } checks[5] = {
        { 0x00402694, sig_res,   sizeof(sig_res)   },
        { 0x0042FE2E, sig_chdir, sizeof(sig_chdir) },
        { 0x00407380, sig_fidx,  sizeof(sig_fidx)  },
        { 0x005DFE90, sig_unlk,  sizeof(sig_unlk)  },
        { 0x00668FA0, sig_sto,   sizeof(sig_sto)   }
    };
    for (int i = 0; i < 5; i++) {
        if (!safe_check_bytes(checks[i].va, checks[i].bytes, checks[i].len)) {
            log_msg("[VT4-Mod] ERROR: Unsupported/packed VT4.exe binary (signature mismatch at VA 0x%08x)! Aborting memory patches and running vanilla.",
                    (unsigned int)checks[i].va);
            show_unsupported_exe_warning(
                "Unsupported or packed/encrypted VT4.exe binary detected.\n"
                "VT4 Legends requires the unpacked PC v1.0 executable.\n"
                "Memory patches were safely aborted; see xlive_mod.log for details.");
            return 0;
        }
    }
    log_msg("[VT4-Mod] VT4.exe signature verified OK (PC v1.0 unpacked)");
    return 1;
}

static void detect_custom_roster_assets(void) {
    char p_sdo[MAX_PATH], p_dds[MAX_PATH];
    snprintf(p_sdo, sizeof(p_sdo), "%s\\archive\\HIGH\\Player\\Model\\P_M_ALC_NG.sdo", g_game_dir);
    snprintf(p_dds, sizeof(p_dds), "%s\\archive\\HIGH\\Frontend\\VR\\photo_L\\26.dds", g_game_dir);
    DWORD a_sdo = GetFileAttributesA(p_sdo);
    DWORD a_dds = GetFileAttributesA(p_dds);
    if (a_sdo != INVALID_FILE_ATTRIBUTES && a_dds != INVALID_FILE_ATTRIBUTES) {
        g_has_custom_roster = 1;
        log_msg("[VT4-Mod] Full Legends Roster Pack detected (84 players enabled)");
    } else {
        g_has_custom_roster = 0;
        log_msg("[VT4-Mod] Core Mode (custom roster pack not found): running 26 base + 2 unlocked bosses safely");
    }
}

static void apply_dpi_awareness(void) {
    HMODULE hUser32 = GetModuleHandleA("user32.dll");
    if (!hUser32) hUser32 = LoadLibraryA("user32.dll");
    if (hUser32) {
        typedef BOOL (__stdcall *SetProcessDPIAware_t)(void);
        SetProcessDPIAware_t fn = (SetProcessDPIAware_t)GetProcAddress(hUser32, "SetProcessDPIAware");
        if (fn) {
            BOOL ok = fn();
            log_msg("[VT4-Mod] SetProcessDPIAware() -> %d", (int)ok);
        }
    }
}

static void apply_vt4_patches(void) {
    init_portable_paths();
    log_msg("[VT4-Mod] Applying startup patches...");
    if (!verify_vt4_exe_signature()) {
        return;
    }

    apply_dpi_awareness();
    load_vt4_settings();
    ensure_default_config_txt();
    detect_custom_roster_assets();

    DWORD old_code_prot = 0;
    VirtualProtect((void *)0x00401000, 0x00400000, PAGE_EXECUTE_READWRITE, &old_code_prot);

    hook_iat(GetModuleHandleA(NULL), "kernel32.dll", "ExitProcess",
             (void *)hk_ExitProcess, (void **)&g_real_exitprocess);
    hook_iat(GetModuleHandleA(NULL), "d3d9.dll", "Direct3DCreate9",
             (void *)hk_Direct3DCreate9, (void **)&g_real_d3dcreate9);

    // 1. Registry-free save path & configured locale
    *(uint32_t *)0x00a75da0 = 1;
    *(wchar_t **)0x00a75bc4 = g_save_path;
    *(uint32_t *)0x00a75bc8 = g_cfg_locale_lcid;
    log_msg("[VT4-Mod] Save path='%ls' locale=0x%04x (%s)", g_save_path, g_cfg_locale_lcid, g_cfg_locale_str);

    // 1a. Wine / Winlator / Proton / Remote-Play startup compatibility bypasses
    {
        static const uint8_t sig_ge[6] = { 0x55, 0x8B, 0xEC, 0x83, 0xE4, 0xF8 };
        if (safe_check_bytes(0x00404f20, sig_ge, sizeof(sig_ge))) {
            const uint8_t ret_true_ge[3] = { 0xB0, 0x01, 0xC3 }; // mov al, 1; ret
            patch_bytes(0x00404f20, ret_true_ge, sizeof(ret_true_ge));
            log_msg("[VT4-Mod] Patched 0x00404f20: GameExplorer/ParentalControls privilege check bypassed (Wine/Winlator/SteamOS fix)");
        } else {
            log_msg("[VT4-Mod] WARNING: 0x00404f20 GameExplorer signature mismatch, skipping privilege bypass");
        }

        static const uint8_t sig_rdp[15] = {
            0x68, 0x00, 0x10, 0x00, 0x00, 0xFF, 0x15, 0x84, 0x84, 0x78, 0x00, 0x85, 0xC0, 0x74, 0x27
        };
        if (safe_check_bytes(0x0040532d, sig_rdp, sizeof(sig_rdp))) {
            const uint8_t jmp_short = 0xEB;
            patch_bytes(0x0040533a, &jmp_short, 1);
            log_msg("[VT4-Mod] Patched 0x0040533a: SM_REMOTESESSION check bypassed (RDP/Moonlight/Steam Remote Play fix)");
        } else {
            log_msg("[VT4-Mod] WARNING: 0x0040532d SM_REMOTESESSION signature mismatch, skipping remote session bypass");
        }
    }

    // 1b. Cleanly eliminate LIVE Mode from Main Menu carousel (9 items total)
    apply_remove_live_mode_patch();

    // 2. High Definition Resolution configuration
    uint32_t w = g_cfg_width, h = g_cfg_height;
    patch_bytes(0x00402694, &w, 4);
    patch_bytes(0x0040269e, &h, 4);
    // Prevent GetConfig() (0x00403900) from overwriting Width (0x00a75d24) and Height (0x00a75d28)
    // when parsing save/Config.txt (which shifts lines if empty lines are present):
    patch_nops(0x00403b56, 5); // mov [0x00a75d24], eax
    patch_nops(0x00403b7d, 5); // mov [0x00a75d28], eax
    *(uint32_t *)0x00a75d24 = w;
    *(uint32_t *)0x00a75d28 = h;
    log_msg("[VT4-Mod] Patched resolution: %ux%u (HD display active)", w, h);

    // 4. Loose File Mod Loader: bypass SetCurrentDirectoryA("archive") and route file queries to archive/
    const uint8_t nops_11[11] = { 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90 };
    patch_bytes(0x0042fe2e, nops_11, 11);
    log_msg("[VT4-Mod] Patched 0x0042fe2e: SetCurrentDirectory('archive') bypassed (11 NOPs)");

    uint8_t loose_flag = 0;
    patch_bytes(0x0042fe3a, &loose_flag, 1);

    hook_iat(GetModuleHandleA(NULL), "kernel32.dll", "CreateFileA",
             (void *)hk_CreateFileA, (void **)&g_real_createfilea);
    if (!g_real_createfilea) {
        g_real_createfilea = *(CreateFileA_t *)0x00788078;
        void *hk_cfa = (void *)hk_CreateFileA;
        patch_bytes(0x00788078, &hk_cfa, sizeof(hk_cfa));
    }
    log_msg("[VT4-Mod] CreateFileA hook active (orig=%p)", g_real_createfilea);

    hook_iat(GetModuleHandleA(NULL), "msvcr90.dll", "fopen_s",
             (void *)hk_fopen_s, (void **)&g_real_fopens);
    if (!g_real_fopens) {
        g_real_fopens = *(fopen_s_t *)0x007883c8;
        void *hk_fos = (void *)hk_fopen_s;
        patch_bytes(0x007883c8, &hk_fos, sizeof(hk_fos));
    }
    log_msg("[VT4-Mod] fopen_s hook active (orig=%p)", g_real_fopens);

    hook_iat(GetModuleHandleA(NULL), "msvcr90.dll", "fopen",
             (void *)hk_fopen, (void **)&g_real_fopen);
    if (!g_real_fopen) {
        g_real_fopen = *(fopen_t *)0x00788414;
        void *hk_fo = (void *)hk_fopen;
        patch_bytes(0x00788414, &hk_fo, sizeof(hk_fo));
    }
    log_msg("[VT4-Mod] fopen hook active (orig=%p)", g_real_fopen);

    hook_iat(GetModuleHandleA(NULL), "shlwapi.dll", "PathFileExistsA",
             (void *)hk_PathFileExistsA, (void **)&g_real_pathfileexistsa);
    if (!g_real_pathfileexistsa) {
        g_real_pathfileexistsa = *(PathFileExistsA_t *)0x00788464;
        void *hk_pfe = (void *)hk_PathFileExistsA;
        patch_bytes(0x00788464, &hk_pfe, sizeof(hk_pfe));
    }
    log_msg("[VT4-Mod] PathFileExistsA hook active (orig=%p)", g_real_pathfileexistsa);

    patch_call(0x004079c4, (void *)hk_Archive_CheckDirectory);
    install_jmp(0x00407380, (void *)hk_ArchiveDir_FindIndex, 6);
    // Bypass forced LZSS flag ([esp+0x24] from 0x0040c280) for standalone loose files ([ebp+0xa9] == 0)
    // at 0x0040c763 (cmp byte ptr [esp+0x24], 0; jne 0x40c76e -> 7 bytes) so uncompressed loose .bin/.txt/.dds files load raw:
    patch_nops(0x0040c763, 7);
    // In AsyncLoader::CloseSlot (0x0040c4a0), at 0x0040c589 (11 bytes + 6 bytes of 0xCC padding):
    // Clear both [esi + 0xa8] and [esi + 0xa9] (bl == 0) so reused slots don't retain stale LZSS flag [ebp+0xa9]=1
    const uint8_t clear_async_slot_flags[17] = {
        0x88, 0x9E, 0xA8, 0x00, 0x00, 0x00, // mov [esi + 0xa8], bl
        0x88, 0x9E, 0xA9, 0x00, 0x00, 0x00, // mov [esi + 0xa9], bl
        0x5B,                               // pop ebx
        0x83, 0xC4, 0x0C,                   // add esp, 0x0c
        0xC3                                // ret
    };
    patch_bytes(0x0040c589, clear_async_slot_flags, sizeof(clear_async_slot_flags));
    log_msg("[VT4-Mod] Loose file mod loader active: 0x004079c4 -> hk_Archive_CheckDirectory, 0x00407380 -> hk_ArchiveDir_FindIndex, 0x0040c763 NOPped (7 bytes), 0x0040c589 clears [esi+0xa9]");

    // 5. Unlock all legends, hidden characters, SPT catalog items, wear & play styles (EXTRA-1 100%)
    // Every UnlockManager getter uses __stdcall(int id) -> BOOL: mov eax, 1; ret 4
    const uint8_t unlock_all_patch[8] = { 0xB8, 0x01, 0x00, 0x00, 0x00, 0xC2, 0x04, 0x00 };
    patch_bytes(0x005dfe90, unlock_all_patch, 8);
    patch_bytes(0x00463b80, unlock_all_patch, 8); /* UnlockManager::IsUnlocked_Master */
    patch_bytes(0x004638c0, unlock_all_patch, 8); /* UnlockManager::IsMaleGearUnlocked */
    patch_bytes(0x00463a40, unlock_all_patch, 8); /* UnlockManager::IsFemaleGearUnlocked */
    patch_bytes(0x00463510, unlock_all_patch, 8); /* UnlockManager::IsSpecialUnlocked */
    patch_bytes(0x00463230, unlock_all_patch, 8); /* UnlockManager::IsCommonUnlocked */
    patch_bytes(0x00463390, unlock_all_patch, 8); /* UnlockManager::IsPlayStyleUnlocked */
    patch_bytes(0x004640a0, unlock_all_patch, 8); /* UnlockManager::IsPlayStyleAvailable */
    log_msg("[VT4-Mod] EXTRA-1: Unlocked 100%% characters, SPT shop gear, wear catalog & play styles");

    // 5b. Smooth transition from Court Position Select to Character Select:
    // Hook FPPlayerEntry::IsReady (0x005f62d0) so pressing Enter advances immediately
    install_jmp(0x005f62d0, (void *)hk_FPPlayerEntry_IsReady, 6);
    // Bypass 0x004545e0 device-name check (fwInputSegaLibGamePad / fwInputSegaLib) at 0x004460fd
    // so keyboard players are not stuck in FPPlayerEntry state 2 forever
    const uint8_t nops_6_pe[6] = { 0x90, 0x90, 0x90, 0x90, 0x90, 0x90 };
    patch_bytes(0x004460fd, nops_6_pe, 6);
    log_msg("[VT4-Mod] FPPlayerEntry::IsReady hooked at 0x005f62d0 (0x004460fd device check bypassed)");

    // Hook TR_COMMON.sto lookup (always active so base bio/surname caching works in both Core & Full modes)
    g_real_sto_lookup = (StoLookup_t)make_trampoline(0x00668fa0, 7);
    install_jmp(0x00668fa0, (void *)hk_StoLookup, 7);

    if (g_has_custom_roster) {
        // 5c. Roster Expansion: Roster Pagination (Page 0 = ATP/WTA, Page 1 = Legends)
        // Initialize base 24-entry grid so Slots 21..23 remain Cargar (26), Actual (26), Aleatorio (27)
        memcpy((void *)0x007c5f6c, g_roster_page_tour, 24);
        log_msg("[VT4-Mod] Character Select Grid: Initialized to Page 0 (Tour: Federer at Slot 0, Slots 21..23 intact)");

        // Hook FPCharaSelect::Update at vtable 0x007c601c + 8
        void *hk_cs = (void *)hk_FPCharaSelect_Update;
        patch_bytes(0x007c601c + 8, &hk_cs, sizeof(hk_cs));
        log_msg("[VT4-Mod] Hooked FPCharaSelect::Update at 0x007c601c+8 -> hk_FPCharaSelect_Update");

        // 5d. Enable dynamic grid card updating for all 24 slots (Federer -> Becker/Edberg/Rafter)
        // NOP the 10 bytes at 0x005df47c so Sega's card manager unconditionally reads 0x007c5f6c
        const uint8_t nops_10[10] = { 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90 };
        patch_bytes(0x005df47c, nops_10, 10);

        // Redirect .fraw label-node lookups in UpdateGridCards (0x005df4a5) & InitGridCardLabels (0x005e00ca)
        // to g_fraw_cell_char_id so paginated slots write character names into the correct UI cell nodes
        uint32_t fraw_tbl_addr = (uint32_t)(uintptr_t)g_fraw_cell_char_id;
        patch_bytes(0x005df4a5, &fraw_tbl_addr, 4);
        patch_bytes(0x005e00ca, &fraw_tbl_addr, 4);

        // Keep hovered character card label visible (replace cmp ebx,1; sete cl; movzx edx,cl with xor edx,edx + NOPs)
        const uint8_t keep_hover_label[9] = { 0x31, 0xD2, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90 };
        patch_bytes(0x005df4b1, keep_hover_label, sizeof(keep_hover_label));

        // Disable region == 2 lock check for King/Duke geometric slots 12/13 in UpdateBigPortraitAndCard & UpdateDisplay
        const uint8_t disable_region_lock[1] = { 0x63 };
        patch_bytes(0x005e03cd, disable_region_lock, 1);
        patch_bytes(0x005df62b, disable_region_lock, 1);
        log_msg("[VT4-Mod] Character Select UI patches active (fraw cell map, persistent hover labels, unlocked slots)");

        // 5e. Fase 2 + Page 3 Roster Expansion (IDs 26..37 + 38..58 -> 59 total players)
        memcpy(g_player_flags, (const void *)0x00820c18, 26 * sizeof(int32_t));
        static const int32_t new_flags[12] = { 44, 24, 73, 73, 45, 73, 16, 73, 37, 5, 76, 73 };
        memcpy(&g_player_flags[26], new_flags, sizeof(new_flags));
        for (int i = 0; i < NUM_EXTRA_PLAYERS; i++) {
            g_player_flags[38 + i] = g_extra_players[i].flag;
        }
        install_jmp(0x00452720, (void *)hk_GetPlayerFlag, 11);

        // Clone signature motion preset table (0x007a5958[26]) -> g_player_anim_presets[59]
        memcpy(g_player_anim_presets, (const void *)0x007a5958, 26 * 20);
        // Assign closest signature serve/forehand/backhand motion tuples from pro icons
        for (int i = 0; i < 12; i++) {
            memcpy(&g_player_anim_presets[(26 + i) * 5], &g_player_anim_presets[g_custom_anim_proxy[i] * 5], 20);
        }
        for (int i = 0; i < NUM_EXTRA_PLAYERS; i++) {
            memcpy(&g_player_anim_presets[(38 + i) * 5], &g_player_anim_presets[g_extra_players[i].anim_proxy * 5], 20);
        }
        uintptr_t ap_base = (uintptr_t)g_player_anim_presets;
        static const uint32_t ap_f0_refs[15] = {
            0x4e0918, 0x4e1661, 0x4e1668, 0x4e16fa, 0x4e1827, 0x4e182e, 0x4e18b6,
            0x4e1b1f, 0x4e1b8d, 0x4e1c5d, 0x4e1c9f, 0x4e1e6f, 0x4e1ecf, 0x4e1fa0, 0x4e1fdf
        };
        for (int i = 0; i < 15; i++) { uint32_t v = (uint32_t)ap_base; patch_bytes(ap_f0_refs[i], &v, 4); }
        { uint32_t v1 = (uint32_t)(ap_base + 4); patch_bytes(0x4e171a, &v1, 4); patch_bytes(0x4e18d6, &v1, 4); }
        { uint32_t v2 = (uint32_t)(ap_base + 8); patch_bytes(0x4e173c, &v2, 4); patch_bytes(0x4e18f8, &v2, 4); }
        { uint32_t v3 = (uint32_t)(ap_base + 12); patch_bytes(0x4e175e, &v3, 4); patch_bytes(0x4e191a, &v3, 4); }
        { uint32_t v4 = (uint32_t)(ap_base + 16); patch_bytes(0x4e1780, &v4, 4); patch_bytes(0x4e193c, &v4, 4); }

        // Clone 60-float bone scale table (0x007b9230[26]) -> g_player_bone_scales[59] matched to each star's base .sdo skeleton
        memcpy(g_player_bone_scales, (const void *)0x007b9230, 26 * 240);
        static const uint8_t proxy_bone_base[12] = { 2, 3, 14, 1, 1, 4, 17, 18, 20, 17, 1, 19 };
        for (int i = 0; i < 12; i++) {
            memcpy(&g_player_bone_scales[(26 + i) * 60], &g_player_bone_scales[proxy_bone_base[i] * 60], 240);
        }
        for (int i = 0; i < NUM_EXTRA_PLAYERS; i++) {
            memcpy(&g_player_bone_scales[(38 + i) * 60], &g_player_bone_scales[g_extra_players[i].bone_proxy * 60], 240);
        }
        { uint32_t bs_addr = (uint32_t)(uintptr_t)g_player_bone_scales; patch_bytes(0x0053d661, &bs_addr, 4); }

        // Hook PlayStyleParameter::LoadCharacter(char_id) at 0x00542260 (keep 0x005422ee at 0x21 for 33 PlayStyles!)
        g_real_playstyle_loadchar = (PlayStyleLoadChar_t)make_trampoline(0x00542260, 6);
        install_jmp(0x00542260, (void *)hk_PlayStyle_LoadChar, 6);

        // Map serve/return motion table indices (0x007baaa8[28]) for IDs 26..58 in 0x0053d6d0
        g_real_set_serve_motion_id = (SetServeMotionIdFn_t)make_trampoline(0x0053d6d0, 6);
        install_jmp(0x0053d6d0, (void *)hk_SetServeMotionId, 6);

        // Safe fallback + logging for GetMotionData (0x004e06f0)
        g_real_get_motion_data = (GetMotionDataFn_t)make_trampoline(0x004e06f0, 6);
        install_jmp(0x004e06f0, (void *)hk_GetMotionData, 6);

        // Extend hardcoded pro-count bounds (0x1a -> 0x3b = 59) in PlayerDB helpers and CharaSelect
        {
            const uint8_t max_ps = (uint8_t)MAX_ROSTER_PLAYERS;
            static const uint32_t db_cap_imm8[9] = {
                0x00533403, 0x00533533, 0x00533677, 0x005338a3, 0x005339b3, 0x00533a89, 0x00533b32, 0x005df6a5, 0x005b9960
            };
            for (int i = 0; i < 9; i++) patch_bytes(db_cap_imm8[i], &max_ps, 1);
            // Prevent GetFinalSelectedCharId (0x005dff30) from hijacking char_id 26 (Alcaraz) into edit_slot + 26 = 25
            const uint8_t jmp_op = 0xEB;
            patch_bytes(0x005dff33, &jmp_op, 1);
        }

        // Hook all PlayerDB getters (0x00533310..0x00533dc0) so IDs 38..58 work alongside native 38-stride fwDataDB_Player.bin
        install_jmp(0x00533310, (void *)hk_PlayerDB_GetCount, 5);
        g_real_pdb_get_code         = (PlayerDB_GetCode_t)make_trampoline_reloc(0x00533320, 7, 2, 0x00533280);
        install_jmp(0x00533320, (void *)hk_PlayerDB_GetCode, 7);
        g_real_pdb_find_by_code     = (PlayerDB_FindByCode_t)make_trampoline_reloc(0x00533360, 9, 4, 0x00533280);
        install_jmp(0x00533360, (void *)hk_PlayerDB_FindByCode, 9);
        g_real_pdb_is_man           = (PlayerDB_BoolId_t)make_trampoline(0x005333c0, 7);
        install_jmp(0x005333c0, (void *)hk_PlayerDB_IsMan, 7);
        g_real_pdb_get_type         = (PlayerDB_IntId_t)make_trampoline_reloc(0x005334d0, 5, 0, 0x00533280);
        install_jmp(0x005334d0, (void *)hk_PlayerDB_GetType, 5);
        g_real_pdb_get_style_name   = (PlayerDB_FStrOut_t)make_trampoline(0x005334f0, 7);
        install_jmp(0x005334f0, (void *)hk_PlayerDB_GetStyleName, 7);
        g_real_pdb_get_style_enum   = (PlayerDB_IntId_t)make_trampoline(0x00533630, 6);
        install_jmp(0x00533630, (void *)hk_PlayerDB_GetStyleEnum, 6);
        g_real_pdb_is_type3         = (PlayerDB_BoolId_t)make_trampoline_reloc(0x005337f0, 5, 0, 0x00533280);
        install_jmp(0x005337f0, (void *)hk_PlayerDB_IsType3, 5);
        g_real_pdb_get_height       = (PlayerDB_StrId_t)make_trampoline_reloc(0x00533820, 5, 0, 0x00533280);
        install_jmp(0x00533820, (void *)hk_PlayerDB_GetHeight, 5);
        g_real_pdb_get_weight       = (PlayerDB_StrId_t)make_trampoline_reloc(0x00533840, 5, 0, 0x00533280);
        install_jmp(0x00533840, (void *)hk_PlayerDB_GetWeight, 5);
        g_real_pdb_get_bh2          = (PlayerDB_BoolId_t)make_trampoline(0x00533860, 7);
        install_jmp(0x00533860, (void *)hk_PlayerDB_GetBackHand2H, 7);
        g_real_pdb_get_lefty        = (PlayerDB_BoolId_t)make_trampoline(0x00533970, 7);
        install_jmp(0x00533970, (void *)hk_PlayerDB_GetLefty, 7);
        g_real_pdb_get_tension      = (PlayerDB_IntId_t)make_trampoline(0x00533a80, 5);
        install_jmp(0x00533a80, (void *)hk_PlayerDB_GetTension, 5);
        g_real_pdb_get_wtdbls       = (PlayerDB_IntId_t)make_trampoline_reloc(0x00533ab0, 5, 0, 0x00533280);
        install_jmp(0x00533ab0, (void *)hk_PlayerDB_GetWtDblsPt, 5);
        g_real_pdb_get_short_name   = (PlayerDB_StrId_t)make_trampoline_reloc(0x00533ad0, 5, 0, 0x00533280);
        install_jmp(0x00533ad0, (void *)hk_PlayerDB_GetShortName, 5);
        g_real_pdb_get_voice_se     = (PlayerDB_FStrOut_t)make_trampoline(0x00533af0, 7);
        install_jmp(0x00533af0, (void *)hk_PlayerDB_GetVoiceSE, 7);
        g_real_pdb_get_model_prefix = (PlayerDB_ModelPrefix_t)make_trampoline_reloc(0x00533dc0, 8, 3, 0x00533280);
        install_jmp(0x00533dc0, (void *)hk_PlayerDB_GetModelPrefix, 8);
        patch_call(0x00533eec, (void *)hk_ModelSdo_GetAuthor);
        patch_call(0x00539441, (void *)hk_ServeMin_GetFloat);
        patch_call(0x00539456, (void *)hk_ServeMax_GetFloat);

        init_custom_bio_strings();
        patch_call(0x0043CAC9, (void *)hk_Loading_SetPlayerPhoto);
        patch_call(0x005e5e0e, (void *)hk_Loading_SetBioCard);
        log_msg("[VT4-Mod] Fase 2 + Page 3 + Page 4 Roster Expansion active: IDs 26..83 (%d players, %d pages, TR_COMMON + Loading bio/photo hooks)",
                MAX_ROSTER_PLAYERS, NUM_ROSTER_PAGES);
    } else {
        log_msg("[VT4-Mod] Safe Core Mode active: keeping vanilla 26+2 roster untouched (no custom .sdo/.dds pack)");
    }

    // 6. Fix Sega European Region ESRB infinite loop deadlock
    // In FUN_00431580 (AdvMode ctor), replace call to FUN_0044fc70 at 0x004315d1 with near jmp to 0x0043165c
    const uint8_t bypass_esrb_ctor[5] = { 0xE9, 0x86, 0x00, 0x00, 0x00 };
    patch_bytes(0x004315d1, bypass_esrb_ctor, 5);

    // 7. Single-shot clean transition to TitleLogo on startup
    void *hk_adv = (void *)hk_AdvMode_Update;
    patch_bytes(0x007897a0, &hk_adv, sizeof(hk_adv));

    // Also protect SceneGraph::DestroyChild at 0x0062f6a2 against invalid child pointers
    uint8_t dtor_patch[9] = { 0xE8, 0, 0, 0, 0, 0x90, 0x90, 0x90, 0x90 };
    uint32_t rel_dtor = (uint32_t)(uintptr_t)hk_SafeDestroyChild - (0x0062f6a2 + 5);
    memcpy(&dtor_patch[1], &rel_dtor, 4);
    patch_bytes(0x0062f6a2, dtor_patch, 9);

    // 8. Protect SoundPlay (0x006375f0) against null sound manager/device
    uint8_t sound_jmp[7] = { 0xE9, 0, 0, 0, 0, 0x90, 0x90 };
    uint32_t rel_sound = (uint32_t)(uintptr_t)hk_SoundPlay - (0x006375f0 + 5);
    memcpy(&sound_jmp[1], &rel_sound, 4);
    patch_bytes(0x006375f0, sound_jmp, 7);

    // 9. Null-safe Subsystem / SceneTree traversals
    // Protect entry points against invalid/small pointer nodes (ecx < 0x10000)
    uint8_t tree_jmp[7] = { 0xE9, 0, 0, 0, 0, 0x90, 0x90 };

    uint32_t rel_trav = (uint32_t)(uintptr_t)hk_SafeTreeTraverse - (0x0062fbc0 + 5);
    memcpy(&tree_jmp[1], &rel_trav, 4);
    patch_bytes(0x0062fbc0, tree_jmp, 7);

    uint32_t rel_tpre = (uint32_t)(uintptr_t)hk_SafeTreePreUpdate - (0x0062fb00 + 5);
    memcpy(&tree_jmp[1], &rel_tpre, 4);
    patch_bytes(0x0062fb00, tree_jmp, 7);
    patch_call(0x0062aa26, (void *)hk_SceneTreeRootPreUpdate);

    uint32_t rel_trend = (uint32_t)(uintptr_t)hk_SafeTreeRender - (0x0062fb70 + 5);
    memcpy(&tree_jmp[1], &rel_trend, 4);
    patch_bytes(0x0062fb70, tree_jmp, 7);

    uint32_t rel_tpost = (uint32_t)(uintptr_t)hk_SafeTreePostUpdate - (0x0062fc60 + 5);
    memcpy(&tree_jmp[1], &rel_tpost, 4);
    patch_bytes(0x0062fc60, tree_jmp, 7);

    // Update at 0x0062fc19 (9 bytes: 8B CE + E8 rel32 + 90 90)
    uint8_t update_patch[9] = { 0x8B, 0xCE, 0xE8, 0, 0, 0, 0, 0x90, 0x90 };
    uint32_t rel_update = (uint32_t)(uintptr_t)hk_CallSubsystemUpdate - (0x0062fc19 + 2 + 5);
    memcpy(&update_patch[3], &rel_update, 4);
    patch_bytes(0x0062fc19, update_patch, 9);

    // PreUpdate at 0x0062fb34 (9 bytes: 8B CF + E8 rel32 + 90 90)
    uint8_t pre_patch[9] = { 0x8B, 0xCF, 0xE8, 0, 0, 0, 0, 0x90, 0x90 };
    uint32_t rel_pre = (uint32_t)(uintptr_t)hk_CallSubsystemPreUpdate - (0x0062fb34 + 2 + 5);
    memcpy(&pre_patch[3], &rel_pre, 4);
    patch_bytes(0x0062fb34, pre_patch, 9);

    // PostUpdate at 0x0062fc9d (9 bytes: 8B CE + E8 rel32 + 90 90)
    uint8_t post_patch[9] = { 0x8B, 0xCE, 0xE8, 0, 0, 0, 0, 0x90, 0x90 };
    uint32_t rel_post = (uint32_t)(uintptr_t)hk_CallSubsystemPostUpdate - (0x0062fc9d + 2 + 5);
    memcpy(&post_patch[3], &rel_post, 4);
    patch_bytes(0x0062fc9d, post_patch, 9);

    // 10. TitleLogo & AdvMode Start input triggers (keyboard Enter/Space & auto-advance)
    patch_call(0x004307C0, (void *)hk_IsStartPressed);
    patch_call(0x004663F7, (void *)hk_CheckInput_455300);
    patch_call(0x00466470, (void *)hk_CheckInput_455300);

    // 11. Eliminate TitleLogo 10-second (600 frames) countdown wait at 0x00466445
    uint32_t zero_wait = 0;
    patch_bytes(0x00466448, &zero_wait, 4);

    // 12. AdvMode: bypass AcroUtil video ready check at 0x0043076d (6 NOPs)
    const uint8_t nops6[6] = { 0x90, 0x90, 0x90, 0x90, 0x90, 0x90 };
    patch_bytes(0x0043076d, nops6, 6);
    log_msg("[VT4-Mod] Patched 0x0043076d: AdvMode AcroUtil video wait bypassed (6 NOPs)");

    // 13. TitleLogo: bypass controller connected check at 0x004663e0 (6 NOPs)
    patch_bytes(0x004663e0, nops6, 6);
    log_msg("[VT4-Mod] Patched 0x004663e0: TitleLogo controller 0 check bypassed (6 NOPs)");

    const uint8_t ret_true3[3] = { 0xB0, 0x01, 0xC3 };
    // 14. FPCommonLoad bypasses (disabled - let engine load assets naturally)
    // patch_bytes(0x005de970, ret_true3, 3);
    // patch_bytes(0x005e55f0, ret_true3, 3);
    // patch_bytes(0x005e55c0, ret_true3, 3);

    // 15. Loading spinner bypasses (disabled)
    // patch_bytes(0x0043bc20, ret_true3, 3);
    // patch_bytes(0x0043dae1, nops6, 6);

    // 16. MainMenu task completion bypasses (allows natural State 1 -> 2 transition & 0x0043e730 InitButtons)
    const uint8_t ret_true_ret8[5] = { 0xB0, 0x01, 0xC2, 0x08, 0x00 };
    patch_bytes(0x0044da10, ret_true3, 3);
    patch_bytes(0x0044dc10, ret_true_ret8, 5);
    log_msg("[VT4-Mod] Patched MainMenu task completion checks at 0x44DA10, 0x44DC10");

    // 18. Auto-confirm MiscWindow modal dialogs (0x0043ff50) so SaveData doesn't block
    uint8_t jmp_mw[7] = { 0xE9, 0, 0, 0, 0, 0x90, 0x90 };
    uint32_t rel_mw = (uint32_t)(uintptr_t)hk_MiscWindow_GetResult - (0x0043ff50 + 5);
    memcpy(&jmp_mw[1], &rel_mw, 4);
    patch_bytes(0x0043ff50, jmp_mw, 7);
    log_msg("[VT4-Mod] Patched 0x0043ff50: MiscWindow::GetResult auto-decision hook installed");

    // 19. Install hooks in Loading, MainMenu and OptionMode (Ajustes) vtables
    void *hk_load = (void *)hk_Loading_Update;
    patch_bytes(0x0078a4ac, &hk_load, sizeof(hk_load));
    void *hk_menu = (void *)hk_MainMenu_Update;
    patch_bytes(0x0078a64c, &hk_menu, sizeof(hk_menu));
    g_real_optionmode_update = *(OptionMode_Update_t *)0x0078ae00;
    void *hk_opt = (void *)hk_OptionMode_Update;
    patch_bytes(0x0078ae00, &hk_opt, sizeof(hk_opt));
    g_real_opt_add_submenus = (OptionMode_Update_t)make_trampoline(0x00443540, 7);
    install_jmp(0x00443540, (void *)hk_OptionMode_AddSubmenus, 7);
    g_real_opt_enter_submenu = (OptEnterSubmenu_t)make_trampoline(0x004435b0, 6);
    install_jmp(0x004435b0, (void *)hk_OptionMode_EnterSubmenu, 6);
    g_real_opt_inner_update = (OptionMode_Update_t)make_trampoline(0x004438e0, 7);
    install_jmp(0x004438e0, (void *)hk_OptionMode_InnerUpdate, 7);
    g_real_fpsubmenu_setsel = (FPSubMenu_SetSel_t)make_trampoline(0x005e92a0, 6);
    install_jmp(0x005e92a0, (void *)hk_FPSubMenu_SetSel, 6);
    patch_call(0x0043f3f3, (void *)hk_MainMenu_OpenNetplayUI);
    log_msg("[VT4-Mod] Installed Loading, MainMenu (EN LINEA -> P2P UI), and Native OptionMode (Row 3 LegendsHD) hooks");

    // 18. Hook MessageBoxA and MessageBoxW to prevent assert popups from blocking
    void *hk_mba = (void *)hk_MessageBoxA;
    patch_bytes(0x00788498, &hk_mba, sizeof(hk_mba));
    void *hk_mbw = (void *)hk_MessageBoxW;
    patch_bytes(0x00788490, &hk_mbw, sizeof(hk_mbw));
    log_msg("[VT4-Mod] Hooked MessageBoxA and MessageBoxW in IAT");

    // 19. Protect 0x0045A920 sound/fade notification against null pointer crashes
    uint8_t patch_45a920[10] = { 0xE9, 0, 0, 0, 0, 0x90, 0x90, 0x90, 0x90, 0x90 };
    uint32_t rel_45a920 = (uint32_t)(uintptr_t)hk_Safe45a920 - (0x0045A920 + 5);
    memcpy(&patch_45a920[1], &rel_45a920, 4);
    patch_bytes(0x0045A920, patch_45a920, 10);
    log_msg("[VT4-Mod] Patched 0x0045A920: Sound/Fade null-pointer crash guard installed");

    // 20. Protect 0x0045A8D0 sound/fade notification against null pointer crashes
    uint8_t patch_45a8d0[8] = { 0xE9, 0, 0, 0, 0, 0x90, 0x90, 0x90 };
    uint32_t rel_45a8d0 = (uint32_t)(uintptr_t)hk_Safe45a8d0 - (0x0045A8D0 + 5);
    memcpy(&patch_45a8d0[1], &rel_45a8d0, 4);
    patch_bytes(0x0045A8D0, patch_45a8d0, 8);
    log_msg("[VT4-Mod] Patched 0x0045A8D0: Sound/Fade null-pointer crash guard installed");

    // 21. Protect ALL fwFormat null node dereferences with safe stack-balanced trampolines
    install_jmp(0x006284E0, (void *)hk_Safe6284e0, 6); // fwHashTable::Find crash fix
    install_jmp(0x00628610, (void *)hk_Safe628610, 7); // fwFormat::FindChild Exhibition/Arcade/Party crash fix
    install_jmp(0x006280B0, (void *)hk_Safe6280b0, 9);
    install_jmp(0x00628E00, (void *)hk_Safe628e00, 8);
    install_jmp(0x00628E60, (void *)hk_Safe628e60, 8);
    install_jmp(0x00628EC0, (void *)hk_Safe628ec0, 9);
    install_jmp(0x00628F50, (void *)hk_Safe628f50, 8); // Difficulty selection & character creation crash fix
    install_jmp(0x00628FF0, (void *)hk_Safe628ff0, 8);
    install_jmp(0x00629070, (void *)hk_Safe629070, 9);
    install_jmp(0x00629100, (void *)hk_Safe629100, 9);
    install_jmp(0x006291D0, (void *)hk_Safe6291d0, 7);
    install_jmp(0x00629230, (void *)hk_Safe629230, 7);
    install_jmp(0x00629290, (void *)hk_Safe629290, 7);
    install_jmp(0x006292F0, (void *)hk_Safe6292f0, 7);
    log_msg("[VT4-Mod] Patched 14 fwFormat methods with clean stack crash guards");

    // 22. Hook IsButtonDown (0x00415500) and IsButtonPressed (0x00415530) for 100% responsive keyboard
    install_jmp(0x00415500, (void *)hk_IsButtonDown, 8);
    install_jmp(0x00415530, (void *)hk_IsButtonPressed, 8);
    log_msg("[VT4-Mod] Patched IsButtonDown (0x00415500) and IsButtonPressed (0x00415530)");

    // 23. Hook GetKeyboardState and bypass window focus blanking for 100% reliable controls
    hook_iat(GetModuleHandleA(NULL), "user32.dll", "GetKeyboardState",
             (void *)hk_GetKeyboardState, (void **)&g_real_getkeyboardstate);
    if (!g_real_getkeyboardstate) {
        g_real_getkeyboardstate = *(GetKeyboardState_t *)0x007884bc;
        void *hk_gks = (void *)hk_GetKeyboardState;
        patch_bytes(0x007884bc, &hk_gks, sizeof(hk_gks));
    }
    const uint8_t nops2[2] = { 0x90, 0x90 };
    patch_bytes(0x00406977, nops2, 2);
    log_msg("[VT4-Mod] GetKeyboardState hook and window focus bypass installed");

    // 24. Central Menu Navigation & Slider hooks (0x455180, 0x4551E0, 0x455240, 0x4552A0, 0x455300, 0x455440)
    // Synchronized across all callers within the same frame via frame-cached eval_nav_key
    install_jmp(0x00455180, (void *)hk_MenuInput_Left, 5);
    install_jmp(0x004551E0, (void *)hk_MenuInput_Right, 5);
    install_jmp(0x00455240, (void *)hk_MenuInput_Up, 5);
    install_jmp(0x004552A0, (void *)hk_MenuInput_Down, 5);

    g_real_menu_decide = (MenuInputFn_t)make_trampoline(0x00455300, 7);
    install_jmp(0x00455300, (void *)hk_MenuInput_Decide, 7);

    g_real_menu_cancel = (MenuInputFn_t)make_trampoline(0x00455440, 7);
    install_jmp(0x00455440, (void *)hk_MenuInput_Cancel, 7);

    // 25. Analog stick hooks for movement & sliders (0x00454F80 Analog X, 0x00455080 Analog Y)
    g_real_analog_x = (AnalogAxisFn_t)make_trampoline(0x00454F80, 6);
    install_jmp(0x00454F80, (void *)hk_AnalogX, 6);
    g_real_analog_y = (AnalogAxisFn_t)make_trampoline(0x00455080, 6);
    install_jmp(0x00455080, (void *)hk_AnalogY, 6);

    log_msg("[VT4-Mod] Central Menu Navigation & Analog hooks installed (100%% synchronized frame-cached routing)");

    // 26. In-match keyboard user-index assignment, camera key remap, and fwInputDevice bit hooks
    // Assign keyboard_user_index = 0 (P1): replace mov [esi+0x408], eax (89 86) with mov [esi+0x408], ecx (89 8E)
    const uint8_t kbd_user_idx_zero[1] = { 0x8E };
    patch_bytes(0x00456392, kbd_user_idx_zero, 1);
    // Allow unconditional keyboard device registration (bypass 0x00457af7: jne 0x457bb2 and 0x00457b0e: jne 0x457b2e)
    patch_nops(0x00457af7, 6);
    patch_nops(0x00457b0e, 2);
    // Move camera toggle key from 'S' (VK 0x53) to 'B' (VK 0x42) so WASD Down ('S') works cleanly in matches
    uint32_t cam_vk = 'B';
    patch_bytes(0x00820f20, &cam_vk, sizeof(cam_vk));
    patch_bytes(0x00835a84, &cam_vk, sizeof(cam_vk));
    // Hook fwInputMgr::Update (0x0062d300) and fwInputDevice bit helpers (8-byte prologues verified non-relative)
    g_real_fwinputmgr_update = (FwInputMgr_Update_t)make_trampoline(0x0062d300, 8);
    install_jmp(0x0062d300, (void *)hk_FwInputMgr_Update, 8);
    g_real_fwinput_isbitdown = (FwInputBitFn_t)make_trampoline(0x0062bf50, 8);
    install_jmp(0x0062bf50, (void *)hk_FwInput_IsBitDown, 8);
    g_real_fwinput_isbitpressed = (FwInputBitFn_t)make_trampoline(0x0062bf90, 8);
    install_jmp(0x0062bf90, (void *)hk_FwInput_IsBitPressed, 8);
    g_real_fwinput_isbitreleased = (FwInputBitFn_t)make_trampoline(0x0062bfe0, 8);
    install_jmp(0x0062bfe0, (void *)hk_FwInput_IsBitReleased, 8);
    patch_call(0x00480492, (void *)hk_MatchPauseCheck);
    g_real_set_match_cam = (void (__cdecl *)(int, int))make_trampoline(0x0054ca10, 6);
    install_jmp(0x0054ca10, (void *)hk_SetMatchCamera, 6);
    g_real_shotcam_trigger = (ShotCamTriggerFn_t)make_trampoline(0x00558890, 8);
    install_jmp(0x00558890, (void *)hk_ShotCamera_Trigger, 8);
    patch_call(0x00482aa1, (void *)hk_LiveMatchTracker_4803e0);
    patch_call(0x00482a70, (void *)hk_MatchInputUpdate_481a60);
    g_real_commit_input_482e10 = (CommitInputFn_t)make_trampoline(0x00482e10, 8);
    install_jmp(0x00482e10, (void *)hk_CommitInput_482e10, 8);
    g_real_sample_input_483190 = (NpSampleInputFn_t)make_trampoline(0x00483190, 6);
    install_jmp(0x00483190, (void *)hk_SamplePlayerInput_483190, 6);
    g_real_random_setseed_632cf0 = (RandomSetSeedFn_t)make_trampoline(0x00632cf0, 8);
    install_jmp(0x00632cf0, (void *)hk_Random_SetSeed_632cf0, 8);
    patch_call(0x0043037b, (void *)hk_FrameStep_42fa90);
    // EXTRA-5: Fix ExhibitionAdvancedSetting NULL! assert (push 0 instead of 1 at 0x004351e0)
    const uint8_t push0_arg = 0x00;
    patch_bytes(0x004351e1, &push0_arg, 1);
    g_real_exmode_reset = (ExModeResetFn_t)make_trampoline(0x00436e20, 6);
    install_jmp(0x00436e20, (void *)hk_ExMode_ResetDefaults, 6);
    g_real_set_rules = (SetRulesFn_orig_t)make_trampoline(0x0045f480, 8);
    install_jmp(0x0045f480, (void *)hk_SetMatchRules, 8);
    g_real_render_postfx = (RenderPostFXFn_t)make_trampoline(0x004a9460, 6);
    install_jmp(0x004a9460, (void *)hk_RenderPostEffects, 6);
    patch_call(0x00478bf3, (void *)hk_BallSimulateTrajectory);
    patch_call(0x00480561, (void *)hk_BallLaunch_480561);
    patch_call(0x004583e7, (void *)hk_ParseSdoBuffer);
    patch_call(0x00531591, (void *)hk_ParseSdoBuffer);
    log_msg("[VT4-Mod] In-match P1 keyboard, fwInputMgr, Classic TV Cam, Speed, EXTRA-5, EXTRA-6 (PostFX) & Fase 3 Multiverse + EE-1/EE-3/EE-4 hooks active");

    // 27. Neutralize focus loss / blanking: force IsWindowFocused (0x00404dc0) to ALWAYS return TRUE
    const uint8_t ret_true3_focus[3] = { 0xB0, 0x01, 0xC3 }; // mov al, 1; ret
    patch_bytes(0x00404dc0, ret_true3_focus, 3);
    log_msg("[VT4-Mod] Window focus protection installed: IsWindowFocused (0x00404dc0) forced to TRUE");

    // 27b. Neutralize accidental emergency shutdown: force 0x00404d90 to return 0 (xor eax, eax; ret)
    const uint8_t ret_zero_3[3] = { 0x31, 0xC0, 0xC3 };
    patch_bytes(0x00404d90, ret_zero_3, 3);
    const uint8_t ret_op[1] = { 0xC3 };
    patch_bytes(0x00404da0, ret_op, 1);
    log_msg("[VT4-Mod] Emergency shutdown guards installed at 0x00404d90 and 0x00404da0");

    // 28. Install custom CRT invalid parameter handler to neutralize 0xc0000417 aborts
    HMODULE hCRT = GetModuleHandleA("msvcr90.dll");
    if (!hCRT) hCRT = LoadLibraryA("msvcr90.dll");
    if (hCRT) {
        typedef void (*_invalid_parameter_handler_t)(const wchar_t *, const wchar_t *, const wchar_t *, unsigned int, uintptr_t);
        typedef _invalid_parameter_handler_t (*set_iph_t)(_invalid_parameter_handler_t);
        set_iph_t set_iph = (set_iph_t)GetProcAddress(hCRT, "_set_invalid_parameter_handler");
        if (set_iph) {
            set_iph(my_invalid_parameter_handler);
            log_msg("[VT4-Mod] Custom CRT _invalid_parameter_handler registered");
        }
    }

    perf_apply_engine_patches();
    log_msg("[VT4-Mod] Startup patches applied cleanly.");
}

// ============================================================================
// 0 arguments (ret 0)
// ============================================================================
uint32_t __stdcall xlive_2(void) { return 0; }    // XWSACleanup
uint32_t __stdcall xlive_52(void) { return 0; }   // XNetCleanup
static uint32_t g_render_calls = 0;
static int g_shot_done60 = 0;
static int g_shot_done240 = 0;
static int g_start_pressed = 0;
uint32_t __stdcall xlive_5002(void) {             // XLiveRender (called every frame!)
    g_render_calls++;
    if (g_d3d_device && *(void ***)g_d3d_device) {
        ensure_d3d9_device_hooks(g_d3d_device);
    }
    if (g_render_calls == 1 || (g_render_calls % 300) == 0) {
        log_msg("[VT4-Mod] XLiveRender frame %u", g_render_calls);
    }

    if (g_chara_select_frames > 0) {
        g_chara_select_frames--;
    }

    if (s_menu_enter_cooldown > 0) {
        s_menu_enter_cooldown--;
    }

    // Ensure keyboard_user_index (+0x408) on the input config struct stays 0 (P1)
    uintptr_t inp_mgr = *(uintptr_t *)0x00835ef0;
    if (inp_mgr > 0x10000) {
        uintptr_t cfg = *(uintptr_t *)(inp_mgr + 0xc);
        if (cfg > 0x10000) {
            int cur_uid = *(int *)(cfg + 0x408);
            if (cur_uid != 0) {
                static int s_uid_logged = 0;
                if (s_uid_logged < 5) {
                    s_uid_logged++;
                    log_msg("[VT4-Mod] Fixed keyboard_user_index from %d -> 0 at frame %u", cur_uid, g_render_calls);
                }
                *(int *)(cfg + 0x408) = 0;
            }
        }
    }

    // Restore P1 default keyboard bindings (0x00820f00..0x00820f34) if zeroed when launched without Launcher.exe
    static const uint32_t s_kbd_defaults[14] = {
        'Z', 'X', 'C', 'V',
        0x64, 0x66, 0x67, 0x69,
        'B', VK_SPACE,
        VK_UP, VK_DOWN, VK_LEFT, VK_RIGHT
    };
    volatile uint32_t *kbd_tbl = (volatile uint32_t *)0x00820f00;
    if (kbd_tbl[9] == 0 || kbd_tbl[10] == 0) {
        static int s_kbd_restored_logged = 0;
        for (int i = 0; i < 14; i++) {
            if (kbd_tbl[i] == 0) kbd_tbl[i] = s_kbd_defaults[i];
        }
        if (kbd_tbl[8] == 'S') kbd_tbl[8] = 'B';
        if (!s_kbd_restored_logged) {
            s_kbd_restored_logged = 1;
            log_msg("[VT4-Mod] Restored default P1 keyboard table at 0x00820f00..0x00820f34 (Pause=SPACE, Camera=B)");
        }
    } else if (kbd_tbl[8] == 'S') {
        kbd_tbl[8] = 'B';
    }

    // Also ensure loose file flag stays 0 if FileLoader is initialized
    uintptr_t fl_ptr = *(uintptr_t *)0x00a75ae0;
    if (fl_ptr) {
        *(uint8_t *)(fl_ptr + 0x24 + 0x9e) = 0;
    }
    return 0;
}
uint32_t __stdcall xlive_5003(void) { return 0; } // XLiveUninitialize
uint32_t __stdcall xlive_5310(void) { return 0; } // XOnlineStartup
uint32_t __stdcall xlive_5311(void) { return 0; } // XOnlineCleanup

// ============================================================================
// 1 argument (ret 4)
// ============================================================================
uint32_t __stdcall xlive_4(uint32_t s) { return closesocket((SOCKET)s); } // XSocketClose
uint32_t __stdcall xlive_27(const char *cp) { return cp ? inet_addr(cp) : 0; } // XSocketInet_Addr
uint32_t __stdcall xlive_37(uint32_t hostlong) { return htonl(hostlong); } // XSocketHTONL
uint32_t __stdcall xlive_38(uint32_t netshort) { return ntohs((uint16_t)netshort); } // XSocketNTOHS
uint32_t __stdcall xlive_40(uint32_t hostshort) { return htons((uint16_t)hostshort); } // XSocketHTONS
uint32_t __stdcall xlive_51(uint32_t p) { return 0; } // XNetStartup
uint32_t __stdcall xlive_72(uint32_t p) { return 0; } // XNetQosRelease
uint32_t __stdcall xlive_73(void *pAddr) { // XNetGetTitleXnAddr
    if (pAddr) memset(pAddr, 0, 36);
    return 4; // XNET_GET_XNADDR_STATIC
}
typedef struct {
    ULONG_PTR InternalLow;
    ULONG_PTR InternalHigh;
    ULONG_PTR InternalContext;
    HANDLE    hEvent;
    PVOID     pCompletionRoutine;
    DWORD_PTR dwCompletionContext;
    DWORD     dwExtendedError;
} GFWL_OVERLAPPED;

static void complete_overlapped(void *pOverlapped, DWORD result) {
    if (!pOverlapped) return;
    GFWL_OVERLAPPED *ov = (GFWL_OVERLAPPED *)pOverlapped;
    ov->InternalLow = result;
    ov->InternalHigh = 0;
    ov->dwExtendedError = result;
    if (ov->hEvent) {
        SetEvent(ov->hEvent);
    }
}

uint32_t __stdcall xlive_1082(void *pOverlapped) { // XGetOverlappedExtendedError
    if (pOverlapped) {
        return ((GFWL_OVERLAPPED *)pOverlapped)->dwExtendedError;
    }
    return 0;
}
uint32_t __stdcall xlive_5007(uint32_t pParams) { return 0; } // XLiveOnResetDevice
uint32_t __stdcall xlive_5030(uint32_t pMsg) { return 0; } // XLivePreTranslateMessage
uint32_t __stdcall xlive_5038(uint32_t h) { return 0; } // XLiveCloseProtectedDataContext
uint32_t __stdcall xlive_5215(uint32_t idx) { return 0; } // XShowGuideUI
uint32_t __stdcall xlive_5251(uint32_t h) { return 0; } // XCloseHandle
uint32_t __stdcall xlive_5262(uint32_t idx) { // XUserGetSigninState
    uint32_t st = (idx == 0) ? 2 : 0; // 2 = eXUserSigninState_SignedInToLive
    static uint32_t last_log = 0;
    if (g_present_calls - last_log >= 180) {
        last_log = g_present_calls;
        log_msg("[VT4-Mod] XUserGetSigninState(user=%u) -> %u (SignedInToLive)", idx, st);
    }
    return st;
}
uint32_t __stdcall xlive_5275(uint32_t idx) { return 0; } // XShowFriendsUI

// ============================================================================
// 2 arguments (ret 8)
// ============================================================================
uint32_t __stdcall xlive_5(uint32_t s, uint32_t how) { return shutdown((SOCKET)s, how); } // XSocketShutdown
uint32_t __stdcall xlive_64(uint32_t a, uint32_t b) { return 0; } // XNetUnregisterInAddr
uint32_t __stdcall xlive_5005(void *pDevice, void *pParams) { // XLiveOnCreateDevice
    log_msg("[VT4-Mod] XLiveOnCreateDevice: D3D9 Device = %p", pDevice);
    return 0;
}
uint32_t __stdcall xlive_5008(uint32_t a, void **ppEngine) { // XHVCreateEngine
    if (ppEngine) *ppEngine = NULL;
    return 0x80004005; // Disable voice engine cleanly
}
uint32_t __stdcall xlive_5036(uint32_t pType, uint32_t *ph) { // XLiveCreateProtectedDataContext
    if (ph) *ph = 1;
    return 0;
}
uint32_t __stdcall xlive_5037(uint32_t h, void *pInfo) { // XLiveQueryProtectedDataInformation
    return 0;
}
uint32_t __stdcall xlive_5260(uint32_t cPanes, uint32_t dwFlags) { // XShowSigninUI
    log_msg("[VT4-Mod] XShowSigninUI called (panes=%u flags=%08x)", cPanes, dwFlags);
    return 0;
}
uint32_t __stdcall xlive_5270(uint64_t qwAreas) { // XNotifyCreateListener (uint64_t = 8 bytes!)
    return 1; // Valid non-zero listener handle
}
uint32_t __stdcall xlive_5297(void *pInit, uint32_t dwVer) { // XLiveInitializeEx
    log_msg("[VT4-Mod] XLiveInitializeEx called (ver=%u)", dwVer);
    return 0;
}
uint32_t __stdcall xlive_5315(uint32_t a, uint32_t b) { return 0x80004005; } // XInviteGetAcceptedInfo
uint32_t __stdcall xlive_5329(uint32_t a, uint32_t b) { return 0; } // XSessionCancel
uint32_t __stdcall xlive_5330(uint32_t a, uint32_t b) { return 0; } // XSessionFlushStats
uint32_t __stdcall xlive_5332(uint32_t a, uint32_t b) { return 0; } // XSessionEnd

// ============================================================================
// 3 arguments (ret 12)
// ============================================================================
uint32_t __stdcall xlive_3(uint32_t af, uint32_t type, uint32_t proto) {
    return (uint32_t)socket(af, type, proto);
}
uint32_t __stdcall xlive_6(uint32_t s, uint32_t cmd, u_long *argp) {
    return ioctlsocket((SOCKET)s, cmd, argp);
}
uint32_t __stdcall xlive_11(uint32_t s, const struct sockaddr *name, int namelen) {
    return bind((SOCKET)s, name, namelen);
}
uint32_t __stdcall xlive_57(uint32_t a, uint32_t b, uint32_t c) { return 0; } // XNetXnAddrToInAddr
uint32_t __stdcall xlive_71(uint32_t a, uint32_t b, uint32_t c) { return 0; } // XNetQosServiceLookup
uint32_t __stdcall xlive_1083(void *pOverlapped, uint32_t *pResult, uint32_t bWait) { // XGetOverlappedResult
    DWORD err = 0;
    if (pOverlapped) {
        GFWL_OVERLAPPED *ov = (GFWL_OVERLAPPED *)pOverlapped;
        err = ov->dwExtendedError;
        if (err == 0) {
            complete_overlapped(pOverlapped, 0);
        }
    }
    log_msg("[VT4-Mod] XGetOverlappedResult(pOver=%p bWait=%u) -> err=0x%08X", pOverlapped, bWait, (unsigned)err);
    if (pResult) *pResult = 0;
    return err;
}
uint32_t __stdcall xlive_5214(uint32_t a, uint32_t b, uint32_t c) { return 0; } // XShowPlayerReviewUI
uint32_t __stdcall xlive_5252(uint32_t a, uint32_t b, uint32_t c) { return 0; } // XShowGamerCardUI
uint32_t __stdcall xlive_5263(uint32_t idx, char *szName, uint32_t cchName) { // XUserGetName
    if (idx != 0) return 1;
    if (szName && cchName > 0) {
        strncpy(szName, "LegendsPlayer", cchName);
        szName[cchName - 1] = '\0';
    }
    return 0;
}
uint32_t __stdcall xlive_5265(uint32_t idx, uint32_t priv, uint32_t *pResult) { // XUserCheckPrivilege
    // Deny GFWL online multiplayer / live comms privileges (240..255) cleanly so clicking
    // "Online" in the main menu never enters dead GFWL Live matchmaking & returns gracefully.
    uint32_t allowed = (priv >= 240 && priv <= 255) ? 0 : 1;
    static uint32_t priv_log = 0;
    if (++priv_log <= 12) {
        log_msg("[VT4-Mod] XUserCheckPrivilege(idx=%u priv=%u) -> allowed=%u", idx, priv, allowed);
    }
    if (pResult) *pResult = allowed;
    return 0;
}
uint32_t __stdcall xlive_5267(uint32_t idx, uint32_t dwFlags, void *pInfo) { // XUserGetSigninInfo / XUID
    if (idx != 0 || !pInfo) return 0x80070490;
    *(uint64_t *)pInfo = 0xE000000000000001ULL; // 8-byte XUID only! (Caller buffer is 8 bytes)
    return 0;
}
uint32_t __stdcall xlive_5277(uint32_t a, uint32_t b, uint32_t c) { return 0; } // XUserWriteContext
uint32_t __stdcall xlive_5278(uint32_t a, uint32_t b, void *pOverlapped) { // XUserWriteAchievements
    if (pOverlapped) {
        *(uint32_t *)pOverlapped = 0;
        *((uint32_t *)pOverlapped + 1) = 0;
    }
    return 0;
}
uint32_t __stdcall xlive_5318(uint32_t a, uint32_t b, uint32_t c) { return 0; } // XSessionStart

// ============================================================================
// 4 arguments (ret 16)
// ============================================================================
uint32_t __stdcall xlive_651(uint32_t hNotify, uint32_t dwFilter, uint32_t *pdwId, uint32_t *pParam) { // XNotifyGetNext
    if (!g_signin_notified && pdwId && pParam) {
        g_signin_notified = 1;
        *pdwId = 10;  // XN_SYS_SIGNINCHANGED
        *pParam = 1;  // User 0 signed in
        log_msg("[VT4-Mod] Sent XN_SYS_SIGNINCHANGED for User 0 (LegendsPlayer)");
        return 1;
    }
    return 0;
}
uint32_t __stdcall xlive_5276(uint32_t a, uint32_t b, uint32_t c, uint32_t d) { return 0; } // XUserWriteProperty
uint32_t __stdcall xlive_5314(uint32_t a, uint32_t b, uint32_t c, uint32_t *pRes) {
    if (pRes) *pRes = 0;
    return 0;
}
uint32_t __stdcall xlive_5323(uint32_t a, uint32_t b, uint32_t c, uint32_t d) { return 0; }
uint32_t __stdcall xlive_5325(uint32_t a, uint32_t b, uint32_t c, uint32_t d) { return 0; }
uint32_t __stdcall xlive_5336(uint32_t a, uint32_t b, uint32_t c, uint32_t d) { return 0; }

// ============================================================================
// 5 arguments (ret 20)
// ============================================================================
uint32_t __stdcall xlive_69(uint32_t a, uint32_t b, uint32_t c, uint32_t d, uint32_t e) { return 0; }
uint32_t __stdcall xlive_5034(const void *pIn, uint32_t dwIn, void *pOut, uint32_t *pdwOut, uint32_t h) { // XLiveProtectData
    if (pdwOut) {
        uint32_t avail = *pdwOut;
        *pdwOut = dwIn;
        if (!pOut || avail < dwIn) return 0x8007007A; // ERROR_INSUFFICIENT_BUFFER
    }
    if (pOut && pIn && dwIn) {
        memcpy(pOut, pIn, dwIn);
    }
    log_msg("[VT4-Mod] XLiveProtectData: saved %u bytes (unencrypted)", dwIn);
    return 0;
}
uint32_t __stdcall xlive_5035(const void *pIn, uint32_t dwIn, void *pOut, uint32_t *pdwOut, uint32_t *ph) { // XLiveUnprotectData
    if (ph) *ph = 1;
    if (pdwOut) {
        uint32_t avail = *pdwOut;
        *pdwOut = dwIn;
        if (!pOut || avail < dwIn) return 0x8007007A;
    }
    if (pOut && pIn && dwIn) {
        memcpy(pOut, pIn, dwIn);
    }
    log_msg("[VT4-Mod] XLiveUnprotectData: loaded %u bytes (unencrypted)", dwIn);
    return 0;
}
uint32_t __stdcall xlive_5256(uint32_t hEnum, void *pvBuffer, uint32_t cbBuffer, uint32_t *pcItemsReturned, void *pOverlapped) { // XEnumerate
    static uint32_t enum_calls = 0;
    if (++enum_calls <= 5 || (enum_calls % 120) == 0) {
        log_msg("[VT4-Mod] XEnumerate(hEnum=%u cbBuffer=%u pOver=%p call=%u)", hEnum, cbBuffer, pOverlapped, enum_calls);
    }
    if (pvBuffer && cbBuffer > 0) {
        memset(pvBuffer, 0, cbBuffer);
    }
    if (pcItemsReturned) *pcItemsReturned = 0;
    if (pOverlapped) {
        complete_overlapped(pOverlapped, 0);
        return 997; // ERROR_IO_PENDING
    }
    return 0; // ERROR_SUCCESS
}
uint32_t __stdcall xlive_5312(uint32_t a, uint32_t b, uint32_t c, uint32_t *pcb, uint32_t *ph) {
    log_msg("[VT4-Mod] xlive_5312(XFriendsCreateEnumerator) -> ERROR_NOT_CONNECTED");
    if (pcb) *pcb = 0;
    if (ph) *ph = 0;
    return 0x800704C6;
}
uint32_t __stdcall xlive_5322(uint32_t a, uint32_t b, uint32_t c, uint32_t d, uint32_t e) {
    if (e) complete_overlapped((void *)(uintptr_t)e, 0x800704C6);
    return 0x800704C6;
}
uint32_t __stdcall xlive_5326(uint32_t a, uint32_t b, uint32_t c, uint32_t d, uint32_t e) {
    if (e) complete_overlapped((void *)(uintptr_t)e, 0x800704C6);
    return 0x800704C6;
}
uint32_t __stdcall xlive_5327(uint32_t a, uint32_t b, uint32_t c, uint32_t d, uint32_t e) {
    if (e) complete_overlapped((void *)(uintptr_t)e, 0x800704C6);
    return 0x800704C6;
}

// ============================================================================
// 6 arguments (ret 24)
// ============================================================================
uint32_t __stdcall xlive_20(uint32_t s, char *buf, int len, int flags, struct sockaddr *from, int *fromlen) {
    return recvfrom((SOCKET)s, buf, len, flags, from, fromlen);
}
uint32_t __stdcall xlive_24(uint32_t s, const char *buf, int len, int flags, const struct sockaddr *to, int tolen) {
    return sendto((SOCKET)s, buf, len, flags, to, tolen);
}
uint32_t __stdcall xlive_5273(uint32_t a, uint32_t b, uint32_t c, uint32_t d, uint32_t e, uint32_t f) { return 0; }
uint32_t __stdcall xlive_5317(uint32_t a, uint32_t b, uint32_t c, uint32_t d, uint32_t e, uint32_t f) {
    log_msg("[VT4-Mod] xlive_5317(XSessionWriteStats) -> ERROR_NOT_CONNECTED");
    if (f) complete_overlapped((void *)(uintptr_t)f, 0x800704C6);
    return 0x800704C6;
}
uint32_t __stdcall xlive_5320(uint32_t a, uint32_t b, uint32_t c, uint32_t d, uint32_t e, uint32_t f) {
    log_msg("[VT4-Mod] xlive_5320(XSessionSearchByID) -> ERROR_NOT_CONNECTED");
    if (f) complete_overlapped((void *)(uintptr_t)f, 0x800704C6);
    return 0x800704C6;
}

// ============================================================================
// 7 arguments (ret 28)
// ============================================================================
uint32_t __stdcall xlive_5284(uint32_t a, uint32_t b, uint32_t c, uint32_t d, uint32_t e, uint32_t *pcb, uint32_t *ph) {
    log_msg("[VT4-Mod] xlive_5284(XPresenceCreateEnumerator) -> ERROR_NOT_CONNECTED");
    if (pcb) *pcb = 0;
    if (ph) *ph = 0;
    return 0x800704C6;
}
uint32_t __stdcall xlive_5303(uint32_t a, uint32_t b, uint32_t c, uint32_t d, uint32_t e, uint32_t f, uint32_t g) { return 0; }
uint32_t __stdcall xlive_5333(uint32_t a, uint32_t b, uint32_t c, uint32_t d, uint32_t e, uint32_t f, uint32_t g) {
    log_msg("[VT4-Mod] xlive_5333(XSessionArbitrationRegister) -> ERROR_NOT_CONNECTED");
    if (g) complete_overlapped((void *)(uintptr_t)g, 0x800704C6);
    return 0x800704C6;
}

// ============================================================================
// 8 arguments (ret 32)
// ============================================================================
uint32_t __stdcall xlive_5281(uint32_t a, uint32_t b, uint32_t c, uint32_t d, uint32_t e, uint32_t *pcb, void *pRes, void *pOver) {
    if (pcb) *pcb = 0;
    if (pOver) complete_overlapped(pOver, 0);
    return 0;
}
uint32_t __stdcall xlive_5300(uint32_t a, uint32_t b, uint32_t c, uint32_t d, uint32_t e, uint32_t f, uint32_t g, uint32_t *ph) {
    log_msg("[VT4-Mod] xlive_5300(XSessionCreate) -> ERROR_NOT_CONNECTED");
    if (ph) *ph = 0;
    if (g) complete_overlapped((void *)(uintptr_t)g, 0x800704C6);
    return 0x800704C6;
}

// ============================================================================
// 9 arguments (ret 36)
// ============================================================================
uint32_t __stdcall xlive_5280(uint32_t a, uint32_t b, uint32_t c, uint32_t d, uint32_t cItemInfos, uint32_t f, uint32_t g, uint32_t *pcb, uint32_t *ph) {
    if (pcb) *pcb = 48 * 36; // 1728 bytes required by VT4's 48-entry loop
    if (ph) *ph = 1;
    log_msg("[VT4-Mod] XContentCreateEnumerator called: cItemInfos=%u -> pcb=1728 ph=1", cItemInfos);
    return 0;
}
uint32_t __stdcall xlive_5339(uint32_t a, uint32_t b, uint32_t c, uint32_t d, uint32_t e, uint32_t f, uint32_t *pcb, void *pRes, void *pOver) {
    log_msg("[VT4-Mod] xlive_5339(XUserReadStats) -> ERROR_NOT_CONNECTED");
    if (pcb) *pcb = 0;
    if (pOver) complete_overlapped(pOver, 0x800704C6);
    return 0x800704C6;
}

// ============================================================================
// 10 arguments (ret 40)
// ============================================================================
uint32_t __stdcall xlive_5321(uint32_t a1, uint32_t a2, uint32_t a3, uint32_t a4, uint32_t a5, uint32_t a6, uint32_t a7, uint32_t *pcb, void *pRes, void *pOver) {
    log_msg("[VT4-Mod] xlive_5321(XSessionSearch) -> ERROR_NOT_CONNECTED");
    if (pcb) *pcb = 0;
    if (pOver) complete_overlapped(pOver, 0x800704C6);
    return 0x800704C6;
}

// ============================================================================
// 12 arguments (ret 48)
// ============================================================================
uint32_t __stdcall xlive_70(uint32_t a1, uint32_t a2, uint32_t a3, uint32_t a4, uint32_t a5, uint32_t a6, uint32_t a7, uint32_t a8, uint32_t a9, uint32_t a10, uint32_t a11, uint32_t a12) {
    return 0;
}

static LONG WINAPI CrashHandler(PEXCEPTION_POINTERS ep) {
    DWORD code = ep->ExceptionRecord->ExceptionCode;
    if (code == 0x406D1388 || code == 0x000006BA || code == 0x80000003 || code == 0xE06D7363) {
        return EXCEPTION_CONTINUE_SEARCH;
    }

    log_msg("[VT4-Mod] === EXCEPTION CAUGHT! Code: 0x%08lx at EIP=%p ===",
            (unsigned long)code, (void *)ep->ContextRecord->Eip);
    {
        HMODULE hMod = NULL;
        char mod_name[MAX_PATH] = "Unknown";
        if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                               (LPCSTR)ep->ContextRecord->Eip, &hMod) && hMod) {
            GetModuleFileNameA(hMod, mod_name, sizeof(mod_name));
        }
        log_msg("[VT4-Mod] Exception Module: %s (base=%p)", mod_name, hMod);
    }
    if (code == 0xC0000005) {
        log_msg("[VT4-Mod] Access violation: %s address %p",
                ep->ExceptionRecord->ExceptionInformation[0] ? "writing" : "reading",
                (void *)ep->ExceptionRecord->ExceptionInformation[1]);
    }
    log_msg("[VT4-Mod] Registers: EAX=%08lx EBX=%08lx ECX=%08lx EDX=%08lx ESI=%08lx EDI=%08lx ESP=%08lx EBP=%08lx",
            (unsigned long)ep->ContextRecord->Eax, (unsigned long)ep->ContextRecord->Ebx,
            (unsigned long)ep->ContextRecord->Ecx, (unsigned long)ep->ContextRecord->Edx,
            (unsigned long)ep->ContextRecord->Esi, (unsigned long)ep->ContextRecord->Edi,
            (unsigned long)ep->ContextRecord->Esp, (unsigned long)ep->ContextRecord->Ebp);
    uintptr_t *stack = (uintptr_t *)ep->ContextRecord->Esp;
    log_msg("[VT4-Mod] Stack dump:");
    for (int i = 0; i < 64; i++) {
        uintptr_t val = stack[i];
        const char *extra = "";
        if (val >= 0x00401000 && val < 0x00785a00) extra = " (.text)";
        else if (val >= 0x00788000 && val < 0x0081e600) extra = " (.rdata)";
        else if (val >= 0x0081f000 && val < 0x00836000) extra = " (.data)";
        log_msg("[VT4-Mod]   [ESP+%02x] = 0x%08lx%s", i * 4, (unsigned long)val, extra);
    }

    // Protect fwTree traversal crashes on invalid / freed nodes
    if (code == 0xC0000005) {
        uintptr_t eip = ep->ContextRecord->Eip;
        if ((eip >= 0x0062fa00 && eip <= 0x0062fd00) ||
            (eip >= (uintptr_t)hk_SafeTreeTraverse && eip <= (uintptr_t)hk_SafeTreeTraverse + 0x80) ||
            (eip >= (uintptr_t)hk_SafeTreePreUpdate && eip <= (uintptr_t)hk_SafeTreePreUpdate + 0x80)) {
            log_msg("[VT4-Mod] VEH recovering from invalid TreeTraverse node ecx=%p", (void *)ep->ContextRecord->Ecx);
            // If we pushed a register inside hook, pop it before returning
            ep->ContextRecord->Eip = 0x0062fc52; // clean ret for 0x62fbc0
            return EXCEPTION_CONTINUE_EXECUTION;
        }
    }
    if (!is_valid_code_ptr((void *)ep->ContextRecord->Eip)) {
        if (ep->ContextRecord->Ecx >= 0x00401000 && ep->ContextRecord->Ecx < 0x00788000) {
            log_msg("[VT4-Mod] VEH recovering Eip from ECX=%p", (void *)ep->ContextRecord->Ecx);
            ep->ContextRecord->Eip = ep->ContextRecord->Ecx;
            return EXCEPTION_CONTINUE_EXECUTION;
        }
        for (int i = 0; i < 8; i++) {
            uintptr_t ret_addr = stack[i];
            if (ret_addr >= 0x00401000 && ret_addr < 0x00788000) {
                log_msg("[VT4-Mod] VEH recovering Eip from stack frame %d return address %p", i, (void *)ret_addr);
                ep->ContextRecord->Esp += (i + 1) * sizeof(uintptr_t);
                ep->ContextRecord->Eip = ret_addr;
                return EXCEPTION_CONTINUE_EXECUTION;
            }
        }
    }

    // Automatic crash recovery for bad tree traversal node dereferences
    if (ep->ContextRecord->Eip == 0x0062fbc3 || ep->ContextRecord->Eip == 0x0062fb03 ||
        ep->ContextRecord->Eip == 0x0062fb73 || ep->ContextRecord->Eip == 0x0062fc64) {
        log_msg("[VT4-Mod] VEH recovered from bad node at %p!", (void *)ep->ContextRecord->Eip);
        ep->ContextRecord->Esi = *(uintptr_t *)ep->ContextRecord->Esp;
        ep->ContextRecord->Esp += 4;
        ep->ContextRecord->Eip = *(uintptr_t *)ep->ContextRecord->Esp;
        ep->ContextRecord->Esp += 4;
        return EXCEPTION_CONTINUE_EXECUTION;
    }

    // Automatic crash recovery for write protection violation (e.g. self-modifying code / hooks)
    if (code == 0xC0000005 && ep->ExceptionRecord->ExceptionInformation[0] == 1) {
        void *fault_addr = (void *)ep->ExceptionRecord->ExceptionInformation[1];
        DWORD prot = 0;
        if (VirtualProtect(fault_addr, 4096, PAGE_EXECUTE_READWRITE, &prot)) {
            log_msg("[VT4-Mod] VEH un-protected page for write at %p!", fault_addr);
            return EXCEPTION_CONTINUE_EXECUTION;
        }
    }

    // Automatic crash recovery for fwFormat (0x00628000..0x0062A500)
    if (ep->ContextRecord->Eip >= 0x00628000 && ep->ContextRecord->Eip <= 0x0062A500) {
        log_msg("[VT4-Mod] VEH intercepted unhooked fwFormat crash at %p (ECX=%p)!",
                (void *)ep->ContextRecord->Eip, (void *)ep->ContextRecord->Ecx);
        // If crash happened in fwHashTable::Find (0x006284E0..0x0062853C)
        if (ep->ContextRecord->Eip >= 0x006284E0 && ep->ContextRecord->Eip <= 0x0062853C) {
            uintptr_t *s = (uintptr_t *)ep->ContextRecord->Esp;
            ep->ContextRecord->Edi = s[0];
            ep->ContextRecord->Esi = s[1];
            ep->ContextRecord->Eip = s[2];
            ep->ContextRecord->Esp += 16; // pop edi, esi, ret_addr + 4 (ret 4)
            ep->ContextRecord->Eax = 0;   // return NULL
            log_msg("[VT4-Mod] VEH recovered safely from fwHashTable::Find crash to %p!", (void *)ep->ContextRecord->Eip);
            return EXCEPTION_CONTINUE_EXECUTION;
        }
        // General fwFormat stack unwinding fallback
        uintptr_t *s = (uintptr_t *)ep->ContextRecord->Esp;
        for (int i = 0; i < 16; i++) {
            if (s[i] >= 0x00401000 && (s[i] < 0x00628000 || s[i] > 0x0062A500) && s[i] < 0x00788000) {
                ep->ContextRecord->Eip = s[i];
                ep->ContextRecord->Esp += (i + 1) * sizeof(uintptr_t);
                ep->ContextRecord->Eax = 0;
                log_msg("[VT4-Mod] VEH recovered safely from general fwFormat crash to caller %p!", (void *)ep->ContextRecord->Eip);
                return EXCEPTION_CONTINUE_EXECUTION;
            }
        }
    }

    // Automatic crash recovery for sound/fade notification crash
    if ((ep->ContextRecord->Eip >= 0x0045A8D0 && ep->ContextRecord->Eip <= 0x0045A910) ||
        (ep->ContextRecord->Eip >= 0x0045A920 && ep->ContextRecord->Eip <= 0x0045A983)) {
        log_msg("[VT4-Mod] VEH recovered from sound/fade crash at %p!", (void *)ep->ContextRecord->Eip);
        uintptr_t *s = (uintptr_t *)ep->ContextRecord->Esp;
        for (int i = 0; i < 8; i++) {
            if (s[i] >= 0x00401000 && s[i] < 0x00788000) {
                ep->ContextRecord->Esp += (i + 1) * sizeof(uintptr_t);
                ep->ContextRecord->Eip = s[i];
                return EXCEPTION_CONTINUE_EXECUTION;
            }
        }
    }
    return EXCEPTION_CONTINUE_SEARCH;
}

BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpvReserved) {
    if (fdwReason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(hinstDLL);
        AddVectoredExceptionHandler(1, CrashHandler);
        apply_vt4_patches();
    } else if (fdwReason == DLL_PROCESS_DETACH) {
        netplay_shutdown();
        ngfx_on_reset();
        vp_shutdown();
        perf_shutdown();
        if (g_log) {
            fclose(g_log);
            g_log = NULL;
        }
    }
    return TRUE;
}
