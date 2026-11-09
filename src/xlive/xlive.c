#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <winsock2.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static int g_signin_notified = 0;
static wchar_t g_save_path[MAX_PATH] = L"c:\\Users\\acorr\\Documents\\tenis\\game\\save\\";
static FILE *g_log = NULL;

static void log_msg(const char *fmt, ...) {
    if (!g_log) {
        g_log = fopen("c:\\Users\\acorr\\Documents\\tenis\\game\\xlive_mod.log", "a");
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

static int g_is_fullscreen = 0;
static uint32_t g_present_calls = 0;
static char g_game_dir[MAX_PATH] = { 0 };
static void sync_menu_indices_from_cfg(void);

static void load_vt4_settings(void) {
    char ini_path[MAX_PATH];
    GetModuleFileNameA(NULL, ini_path, sizeof(ini_path));
    char *last_slash = strrchr(ini_path, '\\');
    if (last_slash) *last_slash = '\0';
    strncpy(g_game_dir, ini_path, sizeof(g_game_dir) - 1);
    g_game_dir[sizeof(g_game_dir) - 1] = '\0';
    strncat(ini_path, "\\vt4_settings.ini", sizeof(ini_path) - strlen(ini_path) - 1);

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
                       "; Suavizado de bordes Anti-Aliasing (MSAA): 0 = Desactivado, 2 = 2x, 4 = 4x, 8 = 8x\n"
                       "AntiAliasing=4\n"
                       "; Sincronizacion Vertical: 1 = Activado (60 FPS estables sin cortes), 0 = Desactivado\n"
                       "VSync=1\n"
                       "; Filtrado Anisotropico para texturas de pista ultra nitidas: 16 = Ultra Nitido, 0 = Normal\n"
                       "AnisotropicFiltering=16\n\n"
                       "[Menu]\n"
                       "; Quitar el modo LIVE / Red (servidor GFWL inactivo) del menu principal\n"
                       "RemoveLiveMode=1\n");
            fclose(f);
            log_msg("[VT4-Mod] Created modern settings configuration file: %s", ini_path);
        }
    }

    g_cfg_width = GetPrivateProfileIntA("Graphics", "Width", 1920, ini_path);
    g_cfg_height = GetPrivateProfileIntA("Graphics", "Height", 1080, ini_path);
    g_cfg_windowed = GetPrivateProfileIntA("Graphics", "Windowed", 0, ini_path);
    g_cfg_antialiasing = GetPrivateProfileIntA("Graphics", "AntiAliasing", 4, ini_path);
    g_cfg_vsync = GetPrivateProfileIntA("Graphics", "VSync", 1, ini_path);
    g_cfg_anisotropic = GetPrivateProfileIntA("Graphics", "AnisotropicFiltering", 16, ini_path);
    g_cfg_remove_live = GetPrivateProfileIntA("Menu", "RemoveLiveMode", 1, ini_path);

    if (g_cfg_width <= 0) g_cfg_width = 1920;
    if (g_cfg_height <= 0) g_cfg_height = 1080;

    log_msg("[VT4-Mod] Settings loaded: %ux%u (windowed=%u msaa=%u vsync=%u aniso=%u remove_live=%u)",
            g_cfg_width, g_cfg_height, g_cfg_windowed, g_cfg_antialiasing,
            g_cfg_vsync, g_cfg_anisotropic, g_cfg_remove_live);
    sync_menu_indices_from_cfg();
}

// ============================================================================
// Phase 1B: Settings Menu, Options Integration & Direct3D 9 RenderTarget Scaling
// ============================================================================

#define NUM_SETTINGS_ITEMS 7

typedef struct {
    uint32_t w, h;
    const char *desc;
} ResChoice;

static const ResChoice s_res_choices[] = {
    { 1920, 1080, "1920x1080 (Full HD 1080p)" },
    { 2560, 1440, "2560x1440 (2K QHD 1440p)" },
    { 3840, 2160, "3840x2160 (4K UHD 2160p)" },
    { 1280, 720,  "1280x720 (HD 720p)" }
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
    "Desactivado (Sin limite)",
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

static const char *s_live_choices[] = {
    "Desactivado",
    "Activado (Recomendado)"
};

static int s_idx_res = 0;
static int s_idx_win = 0;
static int s_idx_msaa = 2; // 4x default
static int s_idx_vsync = 1;
static int s_idx_aniso = 3; // 16x default
static int s_idx_live = 1;

static int g_menu_visible = 0;
static int g_menu_selection = 0;
static int g_menu_saved_banner_timer = 0;
static int g_option_mode_active = 0;
static uint32_t g_option_mode_last_frame = 0;

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

    s_idx_live = g_cfg_remove_live ? 1 : 0;
}

static void update_config_txt(void) {
    const wchar_t *config_path = L"c:\\Users\\acorr\\Documents\\tenis\\game\\save\\Config.txt";
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
    snprintf(val, sizeof(val), "%u", g_cfg_remove_live);
    WritePrivateProfileStringA("Menu", "RemoveLiveMode", val, ini_path);

    log_msg("[VT4-Mod] Settings saved to %s", ini_path);
}

static void apply_and_save_menu_settings(void *dev) {
    g_cfg_width = s_res_choices[s_idx_res].w;
    g_cfg_height = s_res_choices[s_idx_res].h;
    g_cfg_windowed = s_idx_win;
    g_cfg_antialiasing = s_msaa_choices[s_idx_msaa].val;
    g_cfg_vsync = s_idx_vsync;
    g_cfg_anisotropic = s_aniso_choices[s_idx_aniso].val;
    g_cfg_remove_live = s_idx_live;

    save_vt4_settings();
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
            int pos_x = (scr_w > win_w) ? (scr_w - win_w) / 2 : 50;
            int pos_y = (scr_h > win_h) ? (scr_h - win_h) / 2 : 50;
            SetWindowLongA(g_game_hwnd, GWL_STYLE, style);
            SetWindowPos(g_game_hwnd, HWND_TOP, pos_x, pos_y, win_w, win_h, SWP_SHOWWINDOW | SWP_FRAMECHANGED);
            g_is_fullscreen = 0;
        }
        UpdateWindow(g_game_hwnd);
    }

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

    g_menu_saved_banner_timer = 180;
    log_msg("[VT4-Mod] Settings applied immediately: %ux%u Win=%u MSAA=%u VSync=%u Aniso=%u Live=%u",
            g_cfg_width, g_cfg_height, g_cfg_windowed, g_cfg_antialiasing,
            g_cfg_vsync, g_cfg_anisotropic, g_cfg_remove_live);
}

static int handle_settings_menu_input(int vk, void *dev) {
    if (!g_menu_visible && !g_option_mode_active) return 0;

    switch (vk) {
        case VK_UP:
        case 'W': {
            g_menu_selection = (g_menu_selection - 1 + NUM_SETTINGS_ITEMS) % NUM_SETTINGS_ITEMS;
            log_msg("[VT4-Mod] Menu Nav: Up -> selection=%d", g_menu_selection);
            return 1;
        }
        case VK_DOWN:
        case 'S': {
            g_menu_selection = (g_menu_selection + 1) % NUM_SETTINGS_ITEMS;
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
                case 5: s_idx_live = !s_idx_live; break;
            }
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
                case 5: s_idx_live = !s_idx_live; break;
            }
            log_msg("[VT4-Mod] Menu Value Right: item %d changed", g_menu_selection);
            return 1;
        }
        case VK_RETURN:
        case VK_SPACE: {
            apply_and_save_menu_settings(dev);
            return 1;
        }
        case VK_ESCAPE: {
            if (g_menu_visible) {
                g_menu_visible = 0;
                log_msg("[VT4-Mod] Menu closed by ESC");
                return 1;
            }
            break;
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
        Apply_t   sb_apply   = (Apply_t)sb_vtbl[4];
        Release_t sb_release = (Release_t)sb_vtbl[2];
        if (sb_apply) sb_apply(g_pOverlaySB);
        if (sb_release) sb_release(g_pOverlaySB);
        g_pOverlaySB = NULL;
    }
    g_in_overlay = 0;
}

static void __attribute__((noinline)) init_menu_fonts(void *dev) {
    if (!dev) dev = g_d3d_device;
    if (!dev || !*(void ***)dev) return;
    if (!g_d3dx_createfont || !g_d3dx_createsprite) {
        HMODULE hD3DX = LoadLibraryA("d3dx9_43.dll");
        if (hD3DX) {
            g_d3dx_createfont = (D3DXCreateFontA_t)GetProcAddress(hD3DX, "D3DXCreateFontA");
            g_d3dx_createsprite = (D3DXCreateSprite_t)GetProcAddress(hD3DX, "D3DXCreateSprite");
        }
    }
    if (g_d3dx_createsprite && !g_pSprite) {
        HRESULT hr_sp = g_d3dx_createsprite(dev, &g_pSprite);
        log_msg("[VT4-Mod] Created D3DXSprite object: %p (hr=0x%08lx)", g_pSprite, (unsigned long)hr_sp);
    }
    if (g_d3dx_createfont) {
        if (!g_pFontTitle) {
            g_d3dx_createfont(dev, 22, 0, FW_BOLD, 1, FALSE, DEFAULT_CHARSET,
                              OUT_DEFAULT_PRECIS, ANTIALIASED_QUALITY,
                              DEFAULT_PITCH | FF_DONTCARE, "Arial", &g_pFontTitle);
        }
        if (!g_pFont) {
            g_d3dx_createfont(dev, 18, 0, FW_NORMAL, 1, FALSE, DEFAULT_CHARSET,
                              OUT_DEFAULT_PRECIS, ANTIALIASED_QUALITY,
                              DEFAULT_PITCH | FF_DONTCARE, "Arial", &g_pFont);
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

static void render_settings_hud(void *dev) {
    if (!dev) return;
    if (!g_menu_visible && !g_option_mode_active) return;

    if (!begin_overlay_state(dev)) return;

    if (g_menu_saved_banner_timer > 0) g_menu_saved_banner_timer--;

    init_menu_fonts(dev);

    void **vtbl = *(void ***)dev;
    typedef HRESULT (__stdcall *SetViewport_t)(void *, const void *);
    SetViewport_t set_vp = (SetViewport_t)vtbl[47];
    uint32_t full_vp[6] = { 0, 0, g_cfg_width, g_cfg_height, 0, 0x3f800000 };
    if (set_vp) set_vp(dev, full_vp);

    float box_w = 820.0f;
    float box_h = 540.0f;
    float box_x = ((float)g_cfg_width - box_w) * 0.5f;
    float box_y = ((float)g_cfg_height - box_h) * 0.5f;

    // 1. Drop shadow
    draw_screen_quad(dev, box_x + 8.0f, box_y + 8.0f, box_x + box_w + 8.0f, box_y + box_h + 8.0f, 0x88000000);

    // 2. Main backdrop panel
    draw_screen_quad(dev, box_x, box_y, box_x + box_w, box_y + box_h, 0xEB0A101C);

    // 3. Header bar
    draw_screen_quad(dev, box_x, box_y, box_x + box_w, box_y + 70.0f, 0xF014223A);

    // 4. Border lines
    draw_screen_quad(dev, box_x, box_y, box_x + box_w, box_y + 2.0f, 0xFF3575D5);
    draw_screen_quad(dev, box_x, box_y + box_h - 2.0f, box_x + box_w, box_y + box_h, 0xFF3575D5);
    draw_screen_quad(dev, box_x, box_y, box_x + 2.0f, box_y + box_h, 0xFF3575D5);
    draw_screen_quad(dev, box_x + box_w - 2.0f, box_y, box_x + box_w, box_y + box_h, 0xFF3575D5);

    // 5. Header separator
    draw_screen_quad(dev, box_x, box_y + 70.0f, box_x + box_w, box_y + 72.0f, 0xFF4585E5);

    // 6. Highlight bar for selected item
    float item_y_start = box_y + 90.0f;
    float item_h = 44.0f;
    float sel_y = item_y_start + (float)g_menu_selection * item_h;

    draw_screen_quad(dev, box_x + 20.0f, sel_y, box_x + box_w - 20.0f, sel_y + item_h - 4.0f, 0xCC1E4B88);
    draw_screen_quad(dev, box_x + 20.0f, sel_y, box_x + 26.0f, sel_y + item_h - 4.0f, 0xFFFFD700);

    // 7. Footer separator
    draw_screen_quad(dev, box_x, box_y + box_h - 55.0f, box_x + box_w, box_y + box_h - 53.0f, 0xFF2A4A7A);

    // 8. Render Text
    if (g_pFont && g_pFontTitle && g_pSprite) {
        void **svtbl = *(void ***)g_pSprite;
        typedef HRESULT (__stdcall *SpriteBegin_t)(void *, DWORD);
        typedef HRESULT (__stdcall *SpriteEnd_t)(void *);
        SpriteBegin_t sp_begin = (SpriteBegin_t)svtbl[8];
        SpriteEnd_t sp_end = (SpriteEnd_t)svtbl[11];
        if (sp_begin) sp_begin(g_pSprite, 0x10);

        RECT r;

        // Title
        r.left = (LONG)(box_x + 30.0f);
        r.top = (LONG)(box_y + 12.0f);
        r.right = (LONG)(box_x + box_w - 30.0f);
        r.bottom = (LONG)(box_y + 40.0f);
        draw_font_text(g_pFontTitle, "VIRTUA TENNIS 4: LEGENDS & NEXT-GEN EDITION", &r, 0xFFFFD700, 1);

        // Subtitle
        r.top = (LONG)(box_y + 42.0f);
        r.bottom = (LONG)(box_y + 66.0f);
        draw_font_text(g_pFont, "AJUSTES GRAFICOS HD Y OPCIONES DEL MOD", &r, 0xFF80D0FF, 1);

        // Render each item
        const char *item_labels[NUM_SETTINGS_ITEMS] = {
            "Resolucion de Pantalla:",
            "Modo de Pantalla:",
            "Anti-Aliasing 3D (MSAA):",
            "Sincronizacion (VSync):",
            "Filtrado Anisotropico:",
            "Ocultar Modo LIVE:",
            "[ GUARDAR Y APLICAR CAMBIOS ]"
        };

        char val_buf[128];
        for (int i = 0; i < NUM_SETTINGS_ITEMS; i++) {
            float cur_y = item_y_start + (float)i * item_h + 8.0f;
            int is_sel = (i == g_menu_selection);
            DWORD lbl_col = is_sel ? 0xFFFFFFFF : 0xFFB0C4DE;
            DWORD val_col = is_sel ? 0xFFFFD700 : 0xFF40E0D0;

            if (i == 6) {
                r.left = (LONG)(box_x + 40.0f);
                r.top = (LONG)cur_y;
                r.right = (LONG)(box_x + box_w - 40.0f);
                r.bottom = (LONG)(cur_y + 30.0f);
                DWORD act_col = is_sel ? 0xFF00FF88 : 0xFF50C070;
                draw_font_text(g_pFontTitle, item_labels[i], &r, act_col, 1);
            } else {
                r.left = (LONG)(box_x + 45.0f);
                r.top = (LONG)cur_y;
                r.right = (LONG)(box_x + 360.0f);
                r.bottom = (LONG)(cur_y + 30.0f);
                draw_font_text(g_pFont, item_labels[i], &r, lbl_col, 0);

                switch (i) {
                    case 0: snprintf(val_buf, sizeof(val_buf), "< %s >", s_res_choices[s_idx_res].desc); break;
                    case 1: snprintf(val_buf, sizeof(val_buf), "< %s >", s_windowed_choices[s_idx_win]); break;
                    case 2: snprintf(val_buf, sizeof(val_buf), "< %s >", s_msaa_choices[s_idx_msaa].desc); break;
                    case 3: snprintf(val_buf, sizeof(val_buf), "< %s >", s_vsync_choices[s_idx_vsync]); break;
                    case 4: snprintf(val_buf, sizeof(val_buf), "< %s >", s_aniso_choices[s_idx_aniso].desc); break;
                    case 5: snprintf(val_buf, sizeof(val_buf), "< %s >", s_live_choices[s_idx_live]); break;
                }

                r.left = (LONG)(box_x + 360.0f);
                r.right = (LONG)(box_x + box_w - 45.0f);
                draw_font_text(g_pFont, val_buf, &r, val_col, 2);
            }
        }

        // Footer navigation controls
        r.left = (LONG)(box_x + 30.0f);
        r.top = (LONG)(box_y + box_h - 45.0f);
        r.right = (LONG)(box_x + box_w - 30.0f);
        r.bottom = (LONG)(box_y + box_h - 10.0f);
        draw_font_text(g_pFont, "[FLECHAS / WASD] Navegar    [ENTER / ESPACIO] Guardar    [ESC / F2] Cerrar",
                       &r, 0xFF9BB0C8, 1);

        // Saved feedback banner
        if (g_menu_saved_banner_timer > 0) {
            float ban_w = 600.0f;
            float ban_h = 45.0f;
            float ban_x = ((float)g_cfg_width - ban_w) * 0.5f;
            float ban_y = box_y + box_h + 15.0f;

            draw_screen_quad(dev, ban_x, ban_y, ban_x + ban_w, ban_y + ban_h, 0xF00A2515);
            draw_screen_quad(dev, ban_x, ban_y, ban_x + ban_w, ban_y + 2.0f, 0xFF00FF7F);
            draw_screen_quad(dev, ban_x, ban_y + ban_h - 2.0f, ban_x + ban_w, ban_y + ban_h, 0xFF00FF7F);

            r.left = (LONG)ban_x;
            r.top = (LONG)(ban_y + 10.0f);
            r.right = (LONG)(ban_x + ban_w);
            r.bottom = (LONG)(ban_y + 35.0f);
            draw_font_text(g_pFontTitle, "AJUSTES GUARDADOS Y APLICADOS CON EXITO", &r, 0xFF00FF88, 1);
        }

        if (sp_end) sp_end(g_pSprite);
    }

    end_overlay_state(dev);
}

static uint8_t g_keys_down[256] = {0};
static uint32_t g_btn_hold[256] = {0};
static uint32_t g_nav_hold[6] = {0};

static inline int is_key_down(int vk) {
    if (vk < 0 || vk >= 256) return 0;
    if (g_keys_down[vk]) return 1;
    if (g_game_hwnd) {
        HWND fg = GetForegroundWindow();
        if (fg && fg != g_game_hwnd) return 0;
    }
    return ((GetAsyncKeyState(vk) & 0x8000) != 0);
}

// ----------------------------------------------------------------------------
// Roster Pagination & Character Selection Grid
// ----------------------------------------------------------------------------
#define NUM_ROSTER_PAGES 2

// Page 0: ATP & WTA World Tour (Vanilla Sega Roster: 8 rows x 3 columns)
static const uint8_t g_roster_page_tour[24] = {
     0,  2,  3,   // Row 0: Federer(0), Djokovic(2), Murray(3)
     1,  5,  4,   // Row 1: Nadal(1), Roddick(5), Del Potro(4)
     6,  7, 10,   // Row 2: Gonzalez(6), Haas(7), Kohlschreiber(10)
     8,  9, 13,   // Row 3: Seppi(8), Monfils(9), Courier(13)
    15, 16, 22,   // Row 4: King(15), Duke(16), Sharapova(22)
    17, 19, 18,   // Row 5: Venus(17), Ivanovic(19), Kuznetsova(18)
    23, 21, 20,   // Row 6: Robson(23), Chakvetadze(21), Wozniacki(20)
    26, 26, 27    // Row 7: CARGAR (26), ACTUAL (26), ALEATORIO (27)
};

// Page 1: Classic Tennis Legends (Becker, Edberg, Rafter + Champions + Intact Slots 21..23)
static const uint8_t g_roster_page_legends[24] = {
    11, 14, 12,   // Row 0: Becker(11), Edberg(14), Rafter(12)
    13, 15, 16,   // Row 1: Courier(13), King(15), Duke(16)
     0,  1,  2,   // Row 2: Federer(0), Nadal(1), Djokovic(2)
     3,  5,  4,   // Row 3: Murray(3), Roddick(5), Del Potro(4)
     6,  7, 10,   // Row 4: Gonzalez(6), Haas(7), Kohlschreiber(10)
     8,  9, 22,   // Row 5: Seppi(8), Monfils(9), Sharapova(22)
    17, 19, 18,   // Row 6: Venus(17), Ivanovic(19), Kuznetsova(18)
    26, 26, 27    // Row 7: CARGAR (26), ACTUAL (26), ALEATORIO (27)
};

static const uint8_t *g_roster_pages[NUM_ROSTER_PAGES] = {
    g_roster_page_tour,
    g_roster_page_legends
};

static const char *g_roster_page_titles[NUM_ROSTER_PAGES] = {
    "PAGINA 1/2: CIRCUITO ATP & WTA WORLD TOUR",
    "PAGINA 2/2: LEYENDAS CLASICAS (BECKER, EDBERG, RAFTER...)"
};

static int g_current_roster_page = 0;
static void *g_pCharaSelect = NULL;
static int g_chara_select_frames = 0;
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
    HMODULE hD3DX = LoadLibraryA("d3dx9_43.dll");
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
    typedef HRESULT (__stdcall *SetVertexShader_t)(void *, void *);
    typedef HRESULT (__stdcall *SetPixelShader_t)(void *, void *);

    SetFVF_t set_fvf = (SetFVF_t)vtbl[89];
    SetRenderState_t set_rs = (SetRenderState_t)vtbl[57];
    SetTexture_t set_tex = (SetTexture_t)vtbl[65];
    SetVertexShader_t set_vs = (SetVertexShader_t)vtbl[92];
    SetPixelShader_t set_ps = (SetPixelShader_t)vtbl[107];

    if (set_vs) set_vs(dev, NULL);
    if (set_ps) set_ps(dev, NULL);

    if (set_rs) {
        set_rs(dev, 27, 1);  // D3DRS_ALPHABLENDENABLE = TRUE
        set_rs(dev, 19, 5);  // D3DRS_SRCBLEND = D3DBLEND_SRCALPHA (5)
        set_rs(dev, 20, 6);  // D3DRS_DESTBLEND = D3DBLEND_INVSRCALPHA (6)
        set_rs(dev, 137, 0); // D3DRS_LIGHTING = FALSE
        set_rs(dev, 22, 1);  // D3DRS_CULLMODE = D3DCULL_NONE (1)
        set_rs(dev, 7, 0);   // D3DRS_ZENABLE = FALSE
    }

    if (set_tex) set_tex(dev, 0, tex);
    if (set_fvf) set_fvf(dev, FVF_TEXTURED_VERTEX);
    if (g_real_drawprimitiveup) {
        g_real_drawprimitiveup(dev, 5, 2, verts, sizeof(TexturedVertex));
    }
    if (set_tex) set_tex(dev, 0, NULL);
}

static void switch_roster_page(int dir) {
    g_current_roster_page = (g_current_roster_page + dir + NUM_ROSTER_PAGES) % NUM_ROSTER_PAGES;
    log_msg("[VT4-Mod] Switching to roster page %d (%s)", g_current_roster_page, g_roster_page_titles[g_current_roster_page]);

    // 1. Copy the 24 slot IDs of the active page to 0x007c5f6c
    memcpy((void *)0x007c5f6c, g_roster_pages[g_current_roster_page], 24);

    // 2. Mark dirty so hk_FPCharaSelect_Update immediately refreshes on next tick
    g_roster_page_dirty = 1;
}

static int check_roster_arrow_click(int mx, int my) {
    if (g_chara_select_frames <= 0) return 0;
    float fx = (float)mx;
    float fy = (float)my;

    if (fx >= g_arr_left_rc[0] && fx <= g_arr_left_rc[2] &&
        fy >= g_arr_left_rc[1] && fy <= g_arr_left_rc[3]) {
        switch_roster_page(-1);
        return 1;
    }
    if (fx >= g_arr_right_rc[0] && fx <= g_arr_right_rc[2] &&
        fy >= g_arr_right_rc[1] && fy <= g_arr_right_rc[3]) {
        switch_roster_page(1);
        return 1;
    }
    return 0;
}

static int s_entry_confirmed = 0;
static int __thiscall hk_FPPlayerEntry_IsReady(void *self) {
    if (!self) return 0;
    if (is_key_down(VK_RETURN) || is_key_down(VK_SPACE) || is_key_down('C')) {
        s_entry_confirmed = 1;
        log_msg("[VT4-Mod] Player confirmed position on court -> advancing to character select!");
    }
    if (s_entry_confirmed) return 1;
    char *esi = *(char **)((char *)self + 0x1c);
    if (esi && (uintptr_t)esi > 0x10000) {
        if (esi[0x18] != 0 && esi[0x10] == 0) return 1;
    }
    return 0;
}

typedef void (__thiscall *FPCharaSelect_Update_t)(void *self);
static FPCharaSelect_Update_t g_real_charaselect_update = (FPCharaSelect_Update_t)0x005e1340;

static void __thiscall hk_FPCharaSelect_Update(void *self) {
    if (!self) return;
    s_entry_confirmed = 0;
    g_pCharaSelect = self;
    g_chara_select_frames = 30;

    static int s_logged_cs = 0;
    if (s_logged_cs++ < 5 || (s_logged_cs % 180) == 0) {
        log_msg("[VT4-Mod] FPCharaSelect_Update frame %u: self=%p", g_present_calls, self);
    }

    void *grid = *(void **)((char *)self + 0x1c);
    if (grid) {
        // Keyboard direct shortcuts [Q] and [E]
        int q_down = is_key_down('Q');
        int e_down = is_key_down('E');
        static int s_prev_q = 0, s_prev_e = 0;
        if (q_down && !s_prev_q) {
            switch_roster_page(-1);
        } else if (e_down && !s_prev_e) {
            switch_roster_page(1);
        }
        s_prev_q = q_down;
        s_prev_e = e_down;

        // Natural Left/Right grid rollover pagination:
        // Grid is 3 columns (col 0, 1, 2) by 8 rows (row 0..7).
        char *p0 = (char *)grid + 0x0c;
        int col0 = *(int *)(p0 + 0x0c);
        int row0 = *(int *)(p0 + 0x10);

        if (row0 < 7) {
            static int s_prev_left = 0;
            static int s_prev_right = 0;
            int left_down = is_key_down(VK_LEFT) || is_key_down('A');
            int right_down = is_key_down(VK_RIGHT) || is_key_down('D');

            if (left_down && !s_prev_left && col0 == 0) {
                switch_roster_page(-1);
                *(int *)(p0 + 0x0c) = 2; // rollover to right column
            } else if (right_down && !s_prev_right && col0 == 2) {
                switch_roster_page(1);
                *(int *)(p0 + 0x0c) = 0; // rollover to left column
            }
            s_prev_left = left_down;
            s_prev_right = right_down;
        }
    }

    if (g_roster_page_dirty && g_pCharaSelect) {
        g_roster_page_dirty = 0;
        if (grid) {
            typedef void (__thiscall *UpdateGridCards_t)(void *self);
            UpdateGridCards_t update_cards = (UpdateGridCards_t)0x005df1b0;
            update_cards(grid);

            typedef void (__thiscall *UpdateDisplay_t)(void *self, int player_idx);
            typedef void (__thiscall *SetPlayerCharacter_t)(void *self, int player_idx);
            UpdateDisplay_t update_disp = (UpdateDisplay_t)0x005df5d0;
            SetPlayerCharacter_t set_player_char = (SetPlayerCharacter_t)0x005e03b0;
            for (int i = 0; i < 4; i++) {
                char *pi = (char *)grid + 0x0c + i * 0x48;
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
    }

    if (g_real_charaselect_update) {
        g_real_charaselect_update(self);
    }
}

static void render_roster_pagination_hud(void *dev) {
    if (!dev) dev = g_d3d_device;
    if (!dev || !*(void ***)dev || g_chara_select_frames <= 0 || g_menu_visible) return;

    if (!begin_overlay_state(dev)) return;

    init_menu_fonts(dev);
    init_arrow_textures(dev);

    void **dev_vtbl = *(void ***)dev;
    typedef HRESULT (__stdcall *SetViewport_t)(void *, const void *);
    SetViewport_t set_vp = (SetViewport_t)dev_vtbl[47];

    uint32_t full_vp[6] = { 0, 0, g_cfg_width, g_cfg_height, 0, 0x3f800000 };
    if (set_vp) set_vp(dev, full_vp);

    typedef HRESULT (__stdcall *BeginScene_t)(void *);
    typedef HRESULT (__stdcall *EndScene_t)(void *);
    BeginScene_t begin_sc = (BeginScene_t)dev_vtbl[41];
    EndScene_t   end_sc   = (EndScene_t)dev_vtbl[42];

    int need_end_scene = 0;
    if (begin_sc && begin_sc(dev) >= 0) {
        need_end_scene = 1;
    }

    if (g_pSprite && g_pFont && g_pFontTitle) {
        void **svtbl = *(void ***)g_pSprite;
        typedef struct { float x, y, z; } D3DVECTOR3_Mod;
        typedef HRESULT (__stdcall *SpriteBegin_t)(void *, DWORD);
        typedef HRESULT (__stdcall *SpriteDraw_t)(void *, void *, const RECT *, const D3DVECTOR3_Mod *, const D3DVECTOR3_Mod *, DWORD);
        typedef HRESULT (__stdcall *SpriteEnd_t)(void *);

        SpriteBegin_t sp_begin = (SpriteBegin_t)svtbl[8];
        SpriteDraw_t  sp_draw  = (SpriteDraw_t)svtbl[9];
        SpriteEnd_t   sp_end   = (SpriteEnd_t)svtbl[11];

        // 0x10 = D3DXSPRITE_ALPHABLEND, 0x01 = D3DXSPRITE_DONOTSAVESTATE
        if (sp_begin && sp_begin(g_pSprite, 0x10 | 0x01) >= 0) {
            float l_x = 810.0f, l_y = 530.0f;
            float r_x = 1530.0f, r_y = 530.0f;

            g_arr_left_rc[0] = l_x; g_arr_left_rc[1] = l_y;
            g_arr_left_rc[2] = l_x + 48.0f; g_arr_left_rc[3] = l_y + 48.0f;

            g_arr_right_rc[0] = r_x; g_arr_right_rc[1] = r_y;
            g_arr_right_rc[2] = r_x + 48.0f; g_arr_right_rc[3] = r_y + 48.0f;

            if (sp_draw) {
                if (g_pTexArrowLeft) {
                    D3DVECTOR3_Mod posL = { l_x, l_y, 0.0f };
                    sp_draw(g_pSprite, g_pTexArrowLeft, NULL, NULL, &posL, 0xFFFFFFFF);
                }
                if (g_pTexArrowRight) {
                    D3DVECTOR3_Mod posR = { r_x, r_y, 0.0f };
                    sp_draw(g_pSprite, g_pTexArrowRight, NULL, NULL, &posR, 0xFFFFFFFF);
                }
            }

            // Key hint under left arrow: [Q / LB]
            RECT r_l = { (LONG)l_x - 20, (LONG)(l_y + 54.0f), (LONG)l_x + 68, (LONG)(l_y + 78.0f) };
            RECT r_lsh = { r_l.left + 1, r_l.top + 1, r_l.right + 1, r_l.bottom + 1 };
            draw_font_text(g_pFont, "[Q / LB]", &r_lsh, 0x90000000, 1);
            draw_font_text(g_pFont, "[Q / LB]", &r_l, 0xFF5090C0, 1);

            // Key hint under right arrow: [E / RB]
            RECT r_r = { (LONG)r_x - 20, (LONG)(r_y + 54.0f), (LONG)r_x + 68, (LONG)(r_y + 78.0f) };
            RECT r_rsh = { r_r.left + 1, r_r.top + 1, r_r.right + 1, r_r.bottom + 1 };
            draw_font_text(g_pFont, "[E / RB]", &r_rsh, 0x90000000, 1);
            draw_font_text(g_pFont, "[E / RB]", &r_r, 0xFF5090C0, 1);

            // Page Subtitle right above character selection grid (x=870..1500, y=275..310)
            RECT r_t = { 870, 275, 1500, 310 };
            const char *title_text = (g_current_roster_page == 0)
                ? "PAGINA 1/2: CIRCUITO ATP / WTA  [LB / RB o Q / E]"
                : "PAGINA 2/2: LEYENDAS CLASICAS (BECKER, EDBERG...)  [LB / RB o Q / E]";

            DWORD col = (g_current_roster_page == 1) ? 0xFF00E5FF : 0xFFFFFFFF;
            RECT r_tsh = { r_t.left + 2, r_t.top + 2, r_t.right + 2, r_t.bottom + 2 };
            draw_font_text(g_pFontTitle, title_text, &r_tsh, 0xDD000000, 1);
            draw_font_text(g_pFontTitle, title_text, &r_t, col, 1);

            if (sp_end) sp_end(g_pSprite);
        }
    }

    if (need_end_scene && end_sc) {
        end_sc(dev);
    }

    end_overlay_state(dev);
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
    settings->bloom_w = (g_cfg_width >= 1920) ? 2048 : 1024;
    settings->bloom_h = (g_cfg_height >= 1080) ? 1024 : 512;
    settings->shadow_w = 2048;
    settings->shadow_h = 2048;

    *(uint32_t *)0x00a75d24 = g_cfg_width;
    *(uint32_t *)0x00a75d28 = g_cfg_height;
    *(uint32_t *)0x00a75d7c = g_cfg_antialiasing;

    log_msg("[VT4-Mod] hk_Renderer_CalcPipelineSettings: 3D=%ux%u MSAA=%u Shadows=%ux%u Bloom=%ux%u",
            settings->width, settings->height, settings->msaa_samples,
            settings->shadow_w, settings->shadow_h, settings->bloom_w, settings->bloom_h);
}

typedef void (__thiscall *OptionMode_Update_t)(void *);
static OptionMode_Update_t g_real_optionmode_update = NULL;

static void __thiscall hk_OptionMode_Update(void *this_ptr) {
    g_option_mode_active = 1;
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
    if (Width == 640 || (Width == 1280 && Height == 720)) {
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
    if (Width == 640 || (Width == 1280 && Height == 720) ||
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
        if (Width == 640 || (Width == 1280 && Height == 720)) {
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
                g_menu_visible = !g_menu_visible;
                log_msg("[VT4-Mod] F2 pressed: g_menu_visible=%d", g_menu_visible);
                return 0;
            }
            if (!g_menu_visible) {
                if (wParam == 'Q' || wParam == 'q' || wParam == VK_OEM_4 || wParam == VK_PRIOR) {
                    switch_roster_page(-1);
                    return 0;
                }
                if (wParam == 'E' || wParam == 'e' || wParam == VK_TAB || wParam == VK_OEM_6 || wParam == VK_NEXT) {
                    switch_roster_page(1);
                    return 0;
                }
            }
            if (g_menu_visible || g_option_mode_active) {
                if (handle_settings_menu_input(wParam, NULL)) {
                    return 0;
                }
            }
            if (wParam < 256) g_keys_down[wParam] = 1;
            break;
        }
        case WM_LBUTTONDOWN: {
            int mx = (short)LOWORD(lParam);
            int my = (short)HIWORD(lParam);
            if (check_roster_arrow_click(mx, my)) {
                return 0;
            }
            break;
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
    if ((g_present_calls >= 59 && g_present_calls <= 62) || g_present_calls == 360) {
        log_msg("[VT4-Mod] Clear #%u at frame %u: caller=%p flags=0x%08lx color=0x%08lx z=%.2f",
                g_clear_calls, g_present_calls, __builtin_return_address(0), (unsigned long)flags, (unsigned long)color, z);
    }
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
        g_current_target = target;
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
    if (g_present_calls >= 59 && g_present_calls <= 62) {
        log_msg("[VT4-Mod] SetRenderTarget at frame %u: index=%lu target=%p", g_present_calls, (unsigned long)index, target);
    }
    return g_real_setrendertarget(dev, index, target);
}

typedef HRESULT (__stdcall *SetViewport_t)(void *, const void *);
static SetViewport_t g_real_setviewport = NULL;
static HRESULT __stdcall hk_SetViewport(void *dev, const uint32_t *vp) {
    if (!dev || !vp) return g_real_setviewport ? g_real_setviewport(dev, vp) : 0;

    void **vtbl = *(void ***)dev;
    typedef HRESULT (__stdcall *GetRenderTarget_t)(void *, DWORD, void **);
    GetRenderTarget_t get_rt = (GetRenderTarget_t)vtbl[38];
    void *pRT = NULL;
    uint32_t rt_w = g_cfg_width, rt_h = g_cfg_height;
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
    } else if (fix[2] == 640 || (fix[2] == 1280 && fix[3] == 720)) {
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

    return g_real_setviewport(dev, fix);
}

static inline void ensure_valid_viewport(void *dev) {
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
                static uint32_t last_log = 0;
                if (g_present_calls - last_log >= 60) {
                    last_log = g_present_calls;
                    log_msg("[VT4-Mod] ensure_valid_viewport: fixed (0,0) -> %ux%u (hr=0x%08lx) at frame %u",
                            w, h, (unsigned long)sv_hr, g_present_calls);
                }
            }
        }
    }
}

static uint32_t g_target_draw_counts[8] = {0};
static inline void record_draw_target(void) {
    if (g_in_overlay) return;
    g_draw_calls++;
    if (g_current_target) {
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

static uint32_t g_draws_in_cur_frame = 0;

typedef HRESULT (__stdcall *DrawIndexedPrimitive_t)(void *, int, INT, UINT, UINT, UINT, UINT);
static DrawIndexedPrimitive_t g_real_drawindexedprimitive = NULL;
static HRESULT __stdcall hk_DrawIndexedPrimitive(void *dev, int type, INT base_vtx, UINT min_idx, UINT num_vtx, UINT start_idx, UINT prim_count) {
    ensure_valid_viewport(dev);
    record_draw_target();
    g_draws_in_cur_frame++;
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

static HRESULT __stdcall hk_EndScene(void *dev) {
    HRESULT hr = g_real_endscene ? g_real_endscene(dev) : 0;
    if (hr != 0) {
        log_msg("[VT4-Mod] EndScene returned 0x%08lx caller=%p", (unsigned long)hr, __builtin_return_address(0));
    }
    return hr;
}

static HRESULT __stdcall hk_BeginScene(void *dev) {
    g_begin_scene_calls++;
    ensure_valid_viewport(dev);

    void **vtbl = *(void ***)dev;

    // Enable Hardware MSAA rasterization & antialiased line rendering on 3D geometry
    typedef HRESULT (__stdcall *SetRenderState_t)(void *, DWORD, DWORD);
    SetRenderState_t set_rs = (SetRenderState_t)vtbl[57];
    if (set_rs && g_cfg_antialiasing > 0) {
        set_rs(dev, 161, 1); // D3DRS_MULTISAMPLEANTIALIAS = TRUE
        set_rs(dev, 176, 1); // D3DRS_ANTIALIASEDLINEENABLE = TRUE
    }

    // Apply Anisotropic Filtering across all 8 texture stages for razor-sharp court lines
    if (g_cfg_anisotropic > 0 && (g_present_calls % 30) == 1) {
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
    HRESULT hr = g_real_beginscene ? g_real_beginscene(dev) : 0;
    if (hr != 0) {
        log_msg("[VT4-Mod] BeginScene returned 0x%08lx caller=%p", (unsigned long)hr, __builtin_return_address(0));
    }
    return hr;
}

static HRESULT __stdcall hk_Present(void *dev, const RECT *src, const RECT *dst, HWND dstWnd, const void *dirty) {
    g_present_calls++;
    g_draws_in_cur_frame = 0;
    if (!g_d3d_device && dev) g_d3d_device = dev;

    if (g_option_mode_active && g_present_calls > g_option_mode_last_frame + 3) {
        g_option_mode_active = 0;
    }

    if (g_present_calls == 1 || (g_present_calls % 300) == 0) {
        log_msg("[VT4-Mod] Present frame %u: clears=%u (last_col=0x%08lx) draws=%u beginScenes=%u caller=%p last_rt=%p",
                g_present_calls, g_clear_calls, (unsigned long)g_last_clear_color, g_draw_calls, g_begin_scene_calls,
                __builtin_return_address(0), g_last_draw_target);
    }

    if (is_key_down(VK_F10)) {
        g_screenshot_requested = 1;
    }

    if (g_present_calls == 1 || g_present_calls == 60 || g_screenshot_requested) {
        g_screenshot_requested = 0;
        char path[MAX_PATH];
        snprintf(path, sizeof(path), "%s\\vt4_present_%u.png", g_game_dir, g_present_calls);
        capture_d3d9_screenshot(dev, path);
    }
    if (g_present_calls <= 5 || g_present_calls == 60 || g_present_calls >= 890 && g_present_calls <= 905) {
        log_msg("[VT4-Mod] hk_Present frame %u: calling real_present", g_present_calls);
    }
    render_roster_pagination_hud(dev);
    render_settings_hud(dev);

    HRESULT pres_hr = g_real_present(dev, src, dst, dstWnd, dirty);
    if (g_present_calls <= 5 || g_present_calls == 60 || (g_present_calls >= 890 && g_present_calls <= 905) || (pres_hr != 0 && pres_hr != (HRESULT)0x08760878)) {
        log_msg("[VT4-Mod] hk_Present frame %u: real_present returned 0x%08lx", g_present_calls, (unsigned long)pres_hr);
    }
    if (pres_hr == (HRESULT)0x08760878) { // S_PRESENT_OCCLUDED: window occluded/background, treat as D3D_OK so render loop never stalls
        pres_hr = 0;
    }
    return pres_hr;
}

static void capture_d3d9_screenshot(void *dev, const char *png_path) {
    if (!dev) return;
    if (!g_d3dx_save) {
        HMODULE hD3DX = LoadLibraryA("d3dx9_43.dll");
        if (hD3DX) g_d3dx_save = (D3DXSaveSurfaceToFileA_t)GetProcAddress(hD3DX, "D3DXSaveSurfaceToFileA");
    }
    if (!g_d3dx_save) {
        log_msg("[VT4-Mod] D3DXSaveSurfaceToFileA not available");
        return;
    }

    void **vtbl = *(void ***)dev;
    typedef HRESULT (__stdcall *GetBackBuffer_t)(void *, UINT, UINT, int, void **);
    GetBackBuffer_t get_bb = (GetBackBuffer_t)vtbl[18];

    void *pSurface = NULL;
    HRESULT hr = get_bb(dev, 0, 0, 0, &pSurface);
    if (hr >= 0 && pSurface) {
        hr = g_d3dx_save(png_path, 3, pSurface, NULL, NULL); // 3 = D3DXIFF_PNG
        char bmp_path[MAX_PATH];
        strncpy(bmp_path, png_path, sizeof(bmp_path));
        char *ext = strrchr(bmp_path, '.');
        if (ext) strcpy(ext, ".bmp");
        g_d3dx_save(bmp_path, 0, pSurface, NULL, NULL); // 0 = D3DXIFF_BMP
        log_msg("[VT4-Mod] D3D9 GPU backbuffer screenshot saved: hr=%08lx -> %s", (unsigned long)hr, png_path);
        void **svtbl = *(void ***)pSurface;
        typedef ULONG (__stdcall *Release_t)(void *);
        Release_t rel = (Release_t)svtbl[2];
        rel(pSurface);
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
            int pos_x = (scr_w > win_w) ? (scr_w - win_w) / 2 : 50;
            int pos_y = (scr_h > win_h) ? (scr_h - win_h) / 2 : 50;

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

        void **dev_vtbl = *(void ***)(*ppdev);
        if (!g_real_present) {
            g_real_present = (Present_t)dev_vtbl[17];
            void *hk_p = (void *)hk_Present;
            patch_bytes((uintptr_t)&dev_vtbl[17], &hk_p, sizeof(hk_p));

            g_real_reset = (Reset_t)dev_vtbl[16];
            void *hk_res = (void *)hk_Reset;
            patch_bytes((uintptr_t)&dev_vtbl[16], &hk_res, sizeof(hk_res));

            g_real_createtexture = (CreateTexture_t)dev_vtbl[23];
            void *hk_ct = (void *)hk_CreateTexture;
            patch_bytes((uintptr_t)&dev_vtbl[23], &hk_ct, sizeof(hk_ct));

            g_real_createrendertarget = (CreateRenderTarget_t)dev_vtbl[28];
            void *hk_crt = (void *)hk_CreateRenderTarget;
            patch_bytes((uintptr_t)&dev_vtbl[28], &hk_crt, sizeof(hk_crt));

            g_real_createdepthstencilsurface = (CreateDepthStencilSurface_t)dev_vtbl[29];
            void *hk_cds = (void *)hk_CreateDepthStencilSurface;
            patch_bytes((uintptr_t)&dev_vtbl[29], &hk_cds, sizeof(hk_cds));

            g_real_setrendertarget = (SetRenderTarget_t)dev_vtbl[37];
            void *hk_srt = (void *)hk_SetRenderTarget;
            patch_bytes((uintptr_t)&dev_vtbl[37], &hk_srt, sizeof(hk_srt));

            g_real_beginscene = (BeginScene_t)dev_vtbl[41];
            void *hk_bs = (void *)hk_BeginScene;
            patch_bytes((uintptr_t)&dev_vtbl[41], &hk_bs, sizeof(hk_bs));

            g_real_endscene = (EndScene_t)dev_vtbl[42];
            void *hk_es = (void *)hk_EndScene;
            patch_bytes((uintptr_t)&dev_vtbl[42], &hk_es, sizeof(hk_es));

            g_real_clear = (Clear_t)dev_vtbl[43];
            void *hk_c = (void *)hk_Clear;
            patch_bytes((uintptr_t)&dev_vtbl[43], &hk_c, sizeof(hk_c));

            g_real_setviewport = (SetViewport_t)dev_vtbl[47];
            void *hk_svp = (void *)hk_SetViewport;
            patch_bytes((uintptr_t)&dev_vtbl[47], &hk_svp, sizeof(hk_svp));

            g_real_drawprimitive = (DrawPrimitive_t)dev_vtbl[81];
            void *hk_dp = (void *)hk_DrawPrimitive;
            patch_bytes((uintptr_t)&dev_vtbl[81], &hk_dp, sizeof(hk_dp));

            g_real_drawindexedprimitive = (DrawIndexedPrimitive_t)dev_vtbl[82];
            void *hk_d = (void *)hk_DrawIndexedPrimitive;
            patch_bytes((uintptr_t)&dev_vtbl[82], &hk_d, sizeof(hk_d));

            g_real_drawprimitiveup = (DrawPrimitiveUP_t)dev_vtbl[83];
            void *hk_dpup = (void *)hk_DrawPrimitiveUP;
            patch_bytes((uintptr_t)&dev_vtbl[83], &hk_dpup, sizeof(hk_dpup));

            g_real_drawindexedprimitiveup = (DrawIndexedPrimitiveUP_t)dev_vtbl[84];
            void *hk_dipup = (void *)hk_DrawIndexedPrimitiveUP;
            patch_bytes((uintptr_t)&dev_vtbl[84], &hk_dipup, sizeof(hk_dipup));

            log_msg("[VT4-Mod] D3D9 device hooks installed (Present, Clear, BeginScene, SetViewport, DrawPrim/Idx/UP)");
        }
        return hr;
    }

    log_msg("[VT4-Mod] CreateDevice FAILED all attempts! Last hr=%08lx", (unsigned long)hr);
    return hr;
}

static void *__stdcall hk_Direct3DCreate9(UINT sdk) {
    void *d3d = NULL;
    if (!g_d3dcreate9ex) {
        HMODULE hD3D9 = GetModuleHandleA("d3d9.dll");
        if (!hD3D9) hD3D9 = LoadLibraryA("d3d9.dll");
        if (hD3D9) g_d3dcreate9ex = (Direct3DCreate9Ex_t)GetProcAddress(hD3D9, "Direct3DCreate9Ex");
    }
    if (g_d3dcreate9ex) {
        HRESULT hr = g_d3dcreate9ex(sdk, &d3d);
        log_msg("[VT4-Mod] Direct3DCreate9Ex(%u) -> hr=%08lx d3d=%p", sdk, (unsigned long)hr, d3d);
    }
    if (!d3d) {
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

static void __attribute__((naked)) hk_SoundPlay(void) {
    __asm__(
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

// 0x006284E0 (fwHashTable::Find - Universal key lookup crash guard)
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
        lpKeyState[0x94] |= 0x80;
        lpKeyState[0x90] |= 0x80;
        lpKeyState[0x8E] |= 0x80;
    }
    // 0x95 = Menu Down, 0x91 = D-pad Down, 0x8F = Analog Down
    if (is_key_down(VK_DOWN) || is_key_down('S')) {
        lpKeyState[0x95] |= 0x80;
        lpKeyState[0x91] |= 0x80;
        lpKeyState[0x8F] |= 0x80;
    }
    // 0x96 = Menu Left, 0x92 = D-pad Left, 0x8C = Analog Left
    if (is_key_down(VK_LEFT) || is_key_down('A')) {
        lpKeyState[0x96] |= 0x80;
        lpKeyState[0x92] |= 0x80;
        lpKeyState[0x8C] |= 0x80;
    }
    // 0x97 = Menu Right, 0x93 = D-pad Right, 0x8D = Analog Right
    if (is_key_down(VK_RIGHT) || is_key_down('D')) {
        lpKeyState[0x97] |= 0x80;
        lpKeyState[0x93] |= 0x80;
        lpKeyState[0x8D] |= 0x80;
    }

    // Confirm / Select / A button: Enter, Space, 'C'
    if (is_key_down(VK_RETURN) || is_key_down(VK_SPACE) || is_key_down('C')) {
        lpKeyState[VK_RETURN] |= 0x80;
        lpKeyState[VK_SPACE] |= 0x80;
        lpKeyState['C'] |= 0x80;
        lpKeyState[0x81] |= 0x80; // Button A
        lpKeyState[0x50] |= 0x80; // Start
    }

    // Cancel / Back / B button: Escape, 'Z', Backspace
    if (is_key_down(VK_ESCAPE) || is_key_down('Z') || is_key_down(VK_BACK)) {
        lpKeyState[VK_ESCAPE] |= 0x80;
        lpKeyState['Z'] |= 0x80;
        lpKeyState[0x80] |= 0x80; // Button B
    }

    // Button X: 'X'
    if (is_key_down('X')) {
        lpKeyState['X'] |= 0x80;
        lpKeyState[0x82] |= 0x80;
    }

    // Button Y: 'V'
    if (is_key_down('V')) {
        lpKeyState['V'] |= 0x80;
        lpKeyState[0x83] |= 0x80;
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
    switch (button) {
        // Directions (Up, Down, Left, Right)
        case 0x94: case 0x90: case 0x8E: // Up
            return is_key_down(VK_UP) || is_key_down('W');
        case 0x95: case 0x91: case 0x8F: // Down
            return is_key_down(VK_DOWN) || is_key_down('S');
        case 0x96: case 0x92: case 0x8C: // Left
            return is_key_down(VK_LEFT) || is_key_down('A');
        case 0x97: case 0x93: case 0x8D: // Right
            return is_key_down(VK_RIGHT) || is_key_down('D');

        // Action Buttons
        case 0x81: // Confirm / A Button / Topspin
            return is_key_down(VK_RETURN) || is_key_down(VK_SPACE) || is_key_down('C');
        case 0x80: // Cancel / Back / B Button / Lob
        case 0x0E: // Virtual Cancel / Escape (used by FPPlayerEntry and Sega AFC)
            return is_key_down(VK_ESCAPE) || is_key_down('Z') || is_key_down(VK_BACK);
        case 0x82: // X Button / Slice
            return is_key_down('X');
        case 0x83: // Y Button / Dropshot
            return is_key_down('V');
        case 0x84: // LB
            return is_key_down('Q');
        case 0x85: // RB
            return is_key_down('E');
        case 0x50: // Start / Pause
            return is_key_down(VK_RETURN) || is_key_down(VK_SPACE) || is_key_down('P');

        // Pass-through for standard VK codes if checked directly
        case VK_RETURN:
            return is_key_down(VK_RETURN);
        case VK_SPACE:
            return is_key_down(VK_SPACE);
        case VK_ESCAPE:
            return is_key_down(VK_ESCAPE);
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
    if (is_mapped_button_down(button)) return 1;
    return original_IsButtonDown(self, button);
}

static int __thiscall hk_IsButtonPressed(void *self, int button) {
    if (g_chara_select_frames > 0 && !g_menu_visible) {
        if (button == 0x84) { // LB
            switch_roster_page(-1);
        } else if (button == 0x85) { // RB
            switch_roster_page(1);
        }
    }
    if (button >= 0 && button < 256) {
        if (is_mapped_button_down(button)) {
            g_btn_hold[button]++;
            if (g_btn_hold[button] == 1) {
                log_msg("[VT4-Mod] IsButtonPressed: button=0x%02x down at frame %u", button, g_present_calls);
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
    int slot = -1;
    if (tag == 0x5570) slot = 0;           // "Up"
    else if (tag == 0x446F776E) slot = 1;  // "Down"
    else if (tag == 0x4C656674) slot = 2;  // "Left"
    else if (tag == 0x52696774) slot = 3;  // "Rigt"
    else if (tag == 0x44656369) slot = 4;  // "Deci"

    if (slot >= 0) {
        if (g_last_action_frame[slot] != g_present_calls) {
            g_last_action_frame[slot] = g_present_calls;
            int active = 0;
            uint32_t *hold = NULL;
            uint32_t delay = 18, rate = 6;
            switch (slot) {
                case 0: // Up
                    active = is_key_down(VK_UP) || is_key_down('W');
                    hold = &g_hold_up;
                    break;
                case 1: // Down
                    active = is_key_down(VK_DOWN) || is_key_down('S');
                    hold = &g_hold_down;
                    break;
                case 2: // Left
                    active = is_key_down(VK_LEFT) || is_key_down('A');
                    hold = &g_hold_left;
                    break;
                case 3: // Right
                    active = is_key_down(VK_RIGHT) || is_key_down('D');
                    hold = &g_hold_right;
                    break;
                case 4: // Deci
                    active = is_key_down(VK_RETURN) || is_key_down(VK_SPACE) || is_key_down('C');
                    hold = &g_hold_deci;
                    delay = 30; rate = 20;
                    break;
            }
            g_action_state[slot] = eval_action_repeat(active, hold, delay, rate);
            if (g_action_state[slot]) {
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
typedef int (__thiscall *MenuInputFn_t)(void *self, int user);

static uint32_t g_nav_last_frame[6] = {0};
static int      g_nav_val[6] = {0};

static inline int eval_nav_key(int slot, int active, uint32_t delay, uint32_t rate) {
    if (g_nav_last_frame[slot] != g_present_calls) {
        g_nav_last_frame[slot] = g_present_calls;
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
    if (g_menu_visible || g_option_mode_active) {
        int active = is_key_down(VK_LEFT) || is_key_down('A');
        if (eval_nav_key(0, active, 14, 4)) {
            handle_settings_menu_input(VK_LEFT, NULL);
            return 1;
        }
        if (original_menu_input_offset(self, user, 0x08)) {
            handle_settings_menu_input(VK_LEFT, NULL);
            return 1;
        }
        return 1;
    }
    int active = is_key_down(VK_LEFT) || is_key_down('A');
    if (eval_nav_key(0, active, 14, 4)) {
        log_msg("[VT4-Mod] Menu Left triggered at frame %u (user=%d)", g_present_calls, user);
        return 1;
    }
    return original_menu_input_offset(self, user, 0x08);
}

// 0x004551E0: Menu / Slider Right
static int __thiscall hk_MenuInput_Right(void *self, int user) {
    if (g_menu_visible || g_option_mode_active) {
        int active = is_key_down(VK_RIGHT) || is_key_down('D');
        if (eval_nav_key(1, active, 14, 4)) {
            handle_settings_menu_input(VK_RIGHT, NULL);
            return 1;
        }
        if (original_menu_input_offset(self, user, 0x28)) {
            handle_settings_menu_input(VK_RIGHT, NULL);
            return 1;
        }
        return 1;
    }
    int active = is_key_down(VK_RIGHT) || is_key_down('D');
    if (eval_nav_key(1, active, 14, 4)) {
        log_msg("[VT4-Mod] Menu Right triggered at frame %u (user=%d)", g_present_calls, user);
        return 1;
    }
    return original_menu_input_offset(self, user, 0x28);
}

// 0x00455240: Menu Up
static int __thiscall hk_MenuInput_Up(void *self, int user) {
    if (g_menu_visible || g_option_mode_active) {
        int active = is_key_down(VK_UP) || is_key_down('W');
        if (eval_nav_key(2, active, 18, 6)) {
            handle_settings_menu_input(VK_UP, NULL);
            return 1;
        }
        if (original_menu_input_offset(self, user, 0x48)) {
            handle_settings_menu_input(VK_UP, NULL);
            return 1;
        }
        return 1;
    }
    int active = is_key_down(VK_UP) || is_key_down('W');
    if (eval_nav_key(2, active, 18, 6)) {
        log_msg("[VT4-Mod] Menu Up triggered at frame %u (user=%d)", g_present_calls, user);
        return 1;
    }
    return original_menu_input_offset(self, user, 0x48);
}

// 0x004552A0: Menu Down
static int __thiscall hk_MenuInput_Down(void *self, int user) {
    if (g_menu_visible || g_option_mode_active) {
        int active = is_key_down(VK_DOWN) || is_key_down('S');
        if (eval_nav_key(3, active, 18, 6)) {
            handle_settings_menu_input(VK_DOWN, NULL);
            return 1;
        }
        if (original_menu_input_offset(self, user, 0x68)) {
            handle_settings_menu_input(VK_DOWN, NULL);
            return 1;
        }
        return 1;
    }
    int active = is_key_down(VK_DOWN) || is_key_down('S');
    if (eval_nav_key(3, active, 18, 6)) {
        log_msg("[VT4-Mod] Menu Down triggered at frame %u (user=%d)", g_present_calls, user);
        return 1;
    }
    return original_menu_input_offset(self, user, 0x68);
}

// 0x0078b6d8: Carousel Navigation Handlers
// Carousel calls vtable[1] (+4) for Prev (moves backwards/up) and vtable[2] (+8) for Next (moves forwards/down)
static int __thiscall hk_Carousel_Prev(void *self) {
    int up = is_key_down(VK_UP) || is_key_down('W');
    int left = is_key_down(VK_LEFT) || is_key_down('A');
    if (eval_nav_key(2, up || left, 18, 6)) {
        log_msg("[VT4-Mod] Carousel Prev triggered (UP/LEFT) at frame %u", g_present_calls);
        return 1;
    }
    return 0;
}

static int __thiscall hk_Carousel_Next(void *self) {
    int down = is_key_down(VK_DOWN) || is_key_down('S');
    int right = is_key_down(VK_RIGHT) || is_key_down('D');
    if (eval_nav_key(3, down || right, 18, 6)) {
        log_msg("[VT4-Mod] Carousel Next triggered (DOWN/RIGHT) at frame %u", g_present_calls);
        return 1;
    }
    return 0;
}

static int s_menu_enter_cooldown = 0;

// 0x00455300: Menu Decide / Enter
static MenuInputFn_t g_real_menu_decide = NULL;
static int __thiscall hk_MenuInput_Decide(void *self, int user) {
    if (s_menu_enter_cooldown > 0) {
        return 0; // Debounce lockout: ignore buffered Enter while transitioning from Title
    }
    if (g_menu_visible || g_option_mode_active) {
        int active = is_key_down(VK_RETURN) || is_key_down(VK_SPACE) || is_key_down('C');
        if (eval_nav_key(4, active, 30, 20)) {
            handle_settings_menu_input(VK_RETURN, NULL);
            return 1;
        }
        if (g_real_menu_decide && g_real_menu_decide(self, user)) {
            handle_settings_menu_input(VK_RETURN, NULL);
            return 1;
        }
        return 1;
    }
    int active = is_key_down(VK_RETURN) || is_key_down(VK_SPACE) || is_key_down('C');
    if (eval_nav_key(4, active, 30, 20)) {
        log_msg("[VT4-Mod] Menu Decide triggered at frame %u (user=%d)", g_present_calls, user);
        return 1;
    }
    if (g_real_menu_decide) {
        return g_real_menu_decide(self, user);
    }
    return 0;
}

// 0x00455440: Menu Cancel / Escape
static MenuInputFn_t g_real_menu_cancel = NULL;
static int __thiscall hk_MenuInput_Cancel(void *self, int user) {
    if (g_menu_visible) {
        int active = is_key_down(VK_ESCAPE) || is_key_down('Z') || is_key_down(VK_BACK);
        if (eval_nav_key(5, active, 30, 20)) {
            g_menu_visible = 0;
            return 1;
        }
        if (g_real_menu_cancel && g_real_menu_cancel(self, user)) {
            g_menu_visible = 0;
            return 1;
        }
        return 1;
    }
    int active = is_key_down(VK_ESCAPE) || is_key_down('Z') || is_key_down(VK_BACK);
    if (eval_nav_key(5, active, 30, 20)) {
        log_msg("[VT4-Mod] Menu Cancel triggered at frame %u (user=%d)", g_present_calls, user);
        return 1;
    }
    if (g_real_menu_cancel) {
        return g_real_menu_cancel(self, user);
    }
    return 0;
}

// 0x00455080 (Analog X) & 0x00454F80 (Analog Y) stick hooks
static float __thiscall hk_AnalogX(void *self, int user) {
    if (is_key_down(VK_LEFT) || is_key_down('A')) return -1.0f;
    if (is_key_down(VK_RIGHT) || is_key_down('D')) return 1.0f;
    return 0.0f;
}

static float __thiscall hk_AnalogY(void *self, int user) {
    if (is_key_down(VK_UP) || is_key_down('W')) return 1.0f;
    if (is_key_down(VK_DOWN) || is_key_down('S')) return -1.0f;
    return 0.0f;
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
    int cur_down = is_key_down(VK_RETURN) || is_key_down(VK_SPACE);
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
    int cur_down = is_key_down(VK_RETURN) || is_key_down(VK_SPACE);
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
    
    // Ignore requests for the archive containers themselves
    if (strstr(rel_path, "resource.bin") != NULL ||
        strstr(rel_path, "resource.1.bin") != NULL) {
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
    
    if (!sub[0]) return 0;
    
    char clean[MAX_PATH];
    strncpy(clean, sub, sizeof(clean) - 1);
    clean[sizeof(clean) - 1] = '\0';
    for (char *p = clean; *p; p++) {
        if (*p == '/') *p = '\\';
    }
    
    char candidate[MAX_PATH * 2];
    
    // 1. Check in game/archive/<clean>
    snprintf(candidate, sizeof(candidate), "%s\\archive\\%s", g_game_dir, clean);
    DWORD attr = GetFileAttributesA(candidate);
    if (attr != INVALID_FILE_ATTRIBUTES && !(attr & FILE_ATTRIBUTE_DIRECTORY)) {
        if (out_path && out_size > 0) {
            strncpy(out_path, candidate, out_size - 1);
            out_path[out_size - 1] = '\0';
        }
        return 1;
    }
    
    // 2. Check in game/<clean> (only for subdirectories, to avoid matching root executables/dlls)
    if (strchr(clean, '\\') != NULL) {
        snprintf(candidate, sizeof(candidate), "%s\\%s", g_game_dir, clean);
        attr = GetFileAttributesA(candidate);
        if (attr != INVALID_FILE_ATTRIBUTES && !(attr & FILE_ATTRIBUTE_DIRECTORY)) {
            if (out_path && out_size > 0) {
                strncpy(out_path, candidate, out_size - 1);
                out_path[out_size - 1] = '\0';
            }
            return 1;
        }
    }
    
    return 0;
}

static int has_loose_txt_replacement(const char *rel_path) {
    if (!rel_path || !rel_path[0]) return 0;
    size_t len = strlen(rel_path);
    if (len < 5) return 0;
    if (_stricmp(rel_path + len - 4, ".bin") != 0) return 0;
    
    char txt_path[MAX_PATH];
    strncpy(txt_path, rel_path, sizeof(txt_path) - 1);
    txt_path[sizeof(txt_path) - 1] = '\0';
    strcpy(txt_path + len - 4, ".txt");
    
    char resolved[MAX_PATH * 2];
    return is_loose_file_override(txt_path, resolved, sizeof(resolved));
}

static uint32_t g_loose_checks = 0;
static int check_loose_file(const char *rel_path) {
    if (g_loose_checks < 20) {
        log_msg("[VT4-Mod] Archive lookup #%u: '%s'", g_loose_checks, rel_path ? rel_path : "NULL");
        g_loose_checks++;
    }
    if (has_loose_txt_replacement(rel_path)) {
        log_msg("[VT4-Mod] [LOOSE] Archive lookup bypassed .bin for loose .txt: %s", rel_path);
        return 1; // Mark as loose so engine falls back to loose file handler
    }
    char resolved[MAX_PATH * 2];
    if (is_loose_file_override(rel_path, resolved, sizeof(resolved))) {
        log_msg("[VT4-Mod] [LOOSE] Archive override detected: %s -> %s", rel_path, resolved);
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
        if (has_loose_txt_replacement(lpFileName)) {
            log_msg("[VT4-Mod] [LOOSE] CreateFileA bypassed .bin for loose .txt: %s", lpFileName);
            SetLastError(ERROR_FILE_NOT_FOUND);
            return INVALID_HANDLE_VALUE;
        }
        char resolved[MAX_PATH * 2];
        if (is_loose_file_override(lpFileName, resolved, sizeof(resolved))) {
            log_msg("[VT4-Mod] [LOOSE] CreateFileA redirected: %s -> %s", lpFileName, resolved);
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
        if (has_loose_txt_replacement(filename)) {
            log_msg("[VT4-Mod] [LOOSE] fopen_s bypassed .bin for loose .txt: %s", filename);
            if (pFile) *pFile = NULL;
            return 2; // ENOENT
        }
        char resolved[MAX_PATH * 2];
        if (is_loose_file_override(filename, resolved, sizeof(resolved))) {
            log_msg("[VT4-Mod] [LOOSE] fopen_s redirected: %s -> %s", filename, resolved);
            return g_real_fopens(pFile, resolved, mode);
        }
    }
    return g_real_fopens(pFile, filename, mode);
}

typedef FILE *(__cdecl *fopen_t)(const char *filename, const char *mode);
static fopen_t g_real_fopen = NULL;

static FILE *__cdecl hk_fopen(const char *filename, const char *mode) {
    if (filename && filename[0]) {
        if (has_loose_txt_replacement(filename)) {
            log_msg("[VT4-Mod] [LOOSE] fopen bypassed .bin for loose .txt: %s", filename);
            return NULL;
        }
        char resolved[MAX_PATH * 2];
        if (is_loose_file_override(filename, resolved, sizeof(resolved))) {
            log_msg("[VT4-Mod] [LOOSE] fopen redirected: %s -> %s", filename, resolved);
            return g_real_fopen(resolved, mode);
        }
    }
    return g_real_fopen(filename, mode);
}

typedef BOOL (WINAPI *PathFileExistsA_t)(LPCSTR pszPath);
static PathFileExistsA_t g_real_pathfileexistsa = NULL;

static BOOL WINAPI hk_PathFileExistsA(LPCSTR pszPath) {
    if (pszPath && pszPath[0]) {
        if (has_loose_txt_replacement(pszPath)) {
            return FALSE;
        }
        char resolved[MAX_PATH * 2];
        if (is_loose_file_override(pszPath, resolved, sizeof(resolved))) {
            log_msg("[VT4-Mod] [LOOSE] PathFileExistsA redirected: %s -> %s", pszPath, resolved);
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

static void apply_vt4_patches(void) {
    DWORD old_code_prot = 0;
    VirtualProtect((void *)0x00401000, 0x00400000, PAGE_EXECUTE_READWRITE, &old_code_prot);

    hook_iat(GetModuleHandleA(NULL), "kernel32.dll", "ExitProcess",
             (void *)hk_ExitProcess, (void **)&g_real_exitprocess);
    hook_iat(GetModuleHandleA(NULL), "d3d9.dll", "Direct3DCreate9",
             (void *)hk_Direct3DCreate9, (void **)&g_real_d3dcreate9);

    log_msg("[VT4-Mod] Applying startup patches...");
    load_vt4_settings();

    // 1. Registry-free save path & Spanish locale (0x0c0a = 3082)
    *(uint32_t *)0x00a75da0 = 1;
    *(wchar_t **)0x00a75bc4 = g_save_path;
    *(uint32_t *)0x00a75bc8 = 0x0c0a;

    // 1b. Cleanly eliminate LIVE Mode from Main Menu carousel (9 items total)
    apply_remove_live_mode_patch();

    // 2. High Definition Resolution configuration
    uint32_t w = g_cfg_width, h = g_cfg_height;
    patch_bytes(0x00402694, &w, 4);
    patch_bytes(0x0040269e, &h, 4);
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
    log_msg("[VT4-Mod] Loose file mod loader active: 0x004079c4 -> hk_Archive_CheckDirectory");

    // 5. Unlock all legends & hidden characters (King, Duke, Becker, Edberg, Courier...)
    // FUN_005dfe90 returns BOOL (eax = 1): mov eax, 1; ret 4
    const uint8_t unlock_all_patch[8] = { 0xB8, 0x01, 0x00, 0x00, 0x00, 0xC2, 0x04, 0x00 };
    patch_bytes(0x005dfe90, unlock_all_patch, 8);

    // 5b. Roster Expansion: Roster Pagination (Page 0 = ATP/WTA, Page 1 = Legends)
    // Initialize base 24-entry grid so Slots 21..23 remain Cargar (26), Actual (26), Aleatorio (27)
    memcpy((void *)0x007c5f6c, g_roster_page_tour, 24);
    log_msg("[VT4-Mod] Character Select Grid: Initialized to Page 0 (Tour: Federer at Slot 0, Slots 21..23 intact)");

    // 5c. Smooth transition from Court Position Select to Character Select:
    // Hook FPPlayerEntry::IsReady (0x005f62d0) so pressing Enter advances immediately
    install_jmp(0x005f62d0, (void *)hk_FPPlayerEntry_IsReady, 6);
    log_msg("[VT4-Mod] FPPlayerEntry::IsReady hooked at 0x005f62d0 (Enter auto-advance active)");

    // Hook FPCharaSelect::Update at vtable 0x007c601c + 8
    void *hk_cs = (void *)hk_FPCharaSelect_Update;
    patch_bytes(0x007c601c + 8, &hk_cs, sizeof(hk_cs));
    log_msg("[VT4-Mod] Hooked FPCharaSelect::Update at 0x007c601c+8 -> hk_FPCharaSelect_Update");

    // 5d. Enable dynamic grid card updating for all 24 slots (Federer -> Becker/Edberg/Rafter)
    // NOP the 10 bytes at 0x005df47c so Sega's card manager unconditionally reads 0x007c5f6c
    const uint8_t nops_10[10] = { 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90 };
    patch_bytes(0x005df47c, nops_10, 10);
    log_msg("[VT4-Mod] Patched 0x005df47c with 10 NOPs: dynamic grid card updating enabled");

    // 5e. Bypass cached card unlock status in FPCharaSelectGrid::UpdateGridCards (0x005df447)
    // Forces dynamic card texture and label reload for all 24 slots on every page flip
    const uint8_t nops_6[6] = { 0x90, 0x90, 0x90, 0x90, 0x90, 0x90 };
    patch_bytes(0x005df447, nops_6, 6);
    log_msg("[VT4-Mod] Patched 0x005df447 with 6 NOPs: dynamic grid card cache bypass enabled");

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

    // 19. Install hooks in Loading and MainMenu vtables
    void *hk_load = (void *)hk_Loading_Update;
    patch_bytes(0x0078a4ac, &hk_load, sizeof(hk_load));
    void *hk_menu = (void *)hk_MainMenu_Update;
    patch_bytes(0x0078a64c, &hk_menu, sizeof(hk_menu));
    log_msg("[VT4-Mod] Installed Loading::Update and MainMenu::Update hooks");

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

    // 25. Analog stick hooks for sliders / smooth movement (0x00454F80 Analog Y, 0x00455080 Analog X)
    install_jmp(0x00454F80, (void *)hk_AnalogY, 6);
    install_jmp(0x00455080, (void *)hk_AnalogX, 6);

    log_msg("[VT4-Mod] Central Menu Navigation & Analog hooks installed (100%% synchronized frame-cached routing)");

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
    if (g_render_calls == 1 || (g_render_calls % 300) == 0) {
        log_msg("[VT4-Mod] XLiveRender frame %u", g_render_calls);
    }

    if (g_chara_select_frames > 0) {
        g_chara_select_frames--;
    }

    if (s_menu_enter_cooldown > 0) {
        s_menu_enter_cooldown--;
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
static void complete_overlapped(void *pOverlapped, DWORD result) {
    if (!pOverlapped) return;
    typedef struct {
        ULONG_PTR InternalLow;
        ULONG_PTR InternalHigh;
        ULONG_PTR InternalContext;
        HANDLE    hEvent;
        PVOID     pCompletionRoutine;
        DWORD_PTR dwCompletionContext;
        DWORD     dwExtendedError;
    } GFWL_OVERLAPPED;
    GFWL_OVERLAPPED *ov = (GFWL_OVERLAPPED *)pOverlapped;
    ov->InternalLow = result;
    ov->InternalHigh = 0;
    ov->dwExtendedError = result;
    if (ov->hEvent) {
        SetEvent(ov->hEvent);
    }
}

uint32_t __stdcall xlive_1082(uint32_t pOverlapped) { return 0; } // XGetOverlappedExtendedError
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
    log_msg("[VT4-Mod] XGetOverlappedResult(pOver=%p bWait=%u)", pOverlapped, bWait);
    if (pOverlapped) complete_overlapped(pOverlapped, 0);
    if (pResult) *pResult = 0;
    return 0;
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
    if (pResult) *pResult = 1;
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
    if (pcb) *pcb = 0;
    if (ph) *ph = 0;
    return 0;
}
uint32_t __stdcall xlive_5322(uint32_t a, uint32_t b, uint32_t c, uint32_t d, uint32_t e) { return 0; }
uint32_t __stdcall xlive_5326(uint32_t a, uint32_t b, uint32_t c, uint32_t d, uint32_t e) { return 0; }
uint32_t __stdcall xlive_5327(uint32_t a, uint32_t b, uint32_t c, uint32_t d, uint32_t e) { return 0; }

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
uint32_t __stdcall xlive_5317(uint32_t a, uint32_t b, uint32_t c, uint32_t d, uint32_t e, uint32_t f) { return 0; }
uint32_t __stdcall xlive_5320(uint32_t a, uint32_t b, uint32_t c, uint32_t d, uint32_t e, uint32_t f) { return 0; }

// ============================================================================
// 7 arguments (ret 28)
// ============================================================================
uint32_t __stdcall xlive_5284(uint32_t a, uint32_t b, uint32_t c, uint32_t d, uint32_t e, uint32_t *pcb, uint32_t *ph) {
    if (pcb) *pcb = 0;
    if (ph) *ph = 0;
    return 0;
}
uint32_t __stdcall xlive_5303(uint32_t a, uint32_t b, uint32_t c, uint32_t d, uint32_t e, uint32_t f, uint32_t g) { return 0; }
uint32_t __stdcall xlive_5333(uint32_t a, uint32_t b, uint32_t c, uint32_t d, uint32_t e, uint32_t f, uint32_t g) { return 0; }

// ============================================================================
// 8 arguments (ret 32)
// ============================================================================
uint32_t __stdcall xlive_5281(uint32_t a, uint32_t b, uint32_t c, uint32_t d, uint32_t e, uint32_t *pcb, void *pRes, void *pOver) {
    if (pcb) *pcb = 0;
    return 0;
}
uint32_t __stdcall xlive_5300(uint32_t a, uint32_t b, uint32_t c, uint32_t d, uint32_t e, uint32_t f, uint32_t g, uint32_t *ph) {
    if (ph) *ph = 1;
    return 0;
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
    if (pcb) *pcb = 0;
    return 0;
}

// ============================================================================
// 10 arguments (ret 40)
// ============================================================================
uint32_t __stdcall xlive_5321(uint32_t a1, uint32_t a2, uint32_t a3, uint32_t a4, uint32_t a5, uint32_t a6, uint32_t a7, uint32_t *pcb, void *pRes, void *pOver) {
    if (pcb) *pcb = 0;
    return 0;
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
        if (g_log) {
            fclose(g_log);
            g_log = NULL;
        }
    }
    return TRUE;
}
