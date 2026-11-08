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
static uint8_t g_keys_down[256] = {0};
static uint32_t g_btn_hold[256] = {0};
static uint32_t g_nav_hold[6] = {0};
static int g_is_fullscreen = 0;
static RECT g_windowed_rect = {0};
static DWORD g_windowed_style = 0;

static inline int is_key_down(int vk) {
    if (vk < 0 || vk >= 256) return 0;
    if (g_game_hwnd) {
        HWND fg = GetForegroundWindow();
        if (fg && fg != g_game_hwnd) return 0;
    }
    return (g_keys_down[vk] != 0) || ((GetAsyncKeyState(vk) & 0x8000) != 0);
}

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
            if (wParam == VK_F11) { // F11 toggle
                toggle_fullscreen(hwnd);
                return 0;
            }
            if (wParam < 256) g_keys_down[wParam] = 1;
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
static uint32_t g_present_calls = 0;
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
    if (vp) {
        if (vp[2] == 0 || vp[3] == 0) {
            uint32_t fix[6] = { vp[0], vp[1], 1280, 720, vp[4], vp[5] };
            static uint32_t last_zero_log = 0;
            if (g_present_calls - last_zero_log >= 60) {
                last_zero_log = g_present_calls;
                log_msg("[VT4-Mod] SetViewport intercepted zero dimensions (%u,%u) at frame %u! Overriding to 1280x720",
                        vp[2], vp[3], g_present_calls);
            }
            return g_real_setviewport(dev, fix);
        }
        if (g_present_calls <= 5 || g_present_calls == 60 || g_present_calls == 240) {
            log_msg("[VT4-Mod] SetViewport frame %u: pos=(%u,%u) size=%ux%u z=(%lu,%lu)",
                    g_present_calls, vp[0], vp[1], vp[2], vp[3], (unsigned long)vp[4], (unsigned long)vp[5]);
        }
    }
    return g_real_setviewport(dev, vp);
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

typedef HRESULT (__stdcall *DrawPrimitiveUP_t)(void *, int, UINT, const void *, UINT);
static DrawPrimitiveUP_t g_real_drawprimitiveup = NULL;
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
static BeginScene_t g_real_beginscene = NULL;
static HRESULT __stdcall hk_BeginScene(void *dev) {
    g_begin_scene_calls++;
    return g_real_beginscene(dev);
}

static HRESULT __stdcall hk_Present(void *dev, const RECT *src, const RECT *dst, HWND dstWnd, const void *dirty) {
    g_present_calls++;
    g_draws_in_cur_frame = 0;

    // StretchRect composite: stretch active offscreen render target to swapchain backbuffer only when offscreen
    void **vtbl = *(void ***)dev;
    typedef HRESULT (__stdcall *GetBackBuffer_t)(void *, UINT, UINT, int, void **);
    GetBackBuffer_t get_bb = (GetBackBuffer_t)vtbl[18];
    void *pBackBuffer = NULL;
    if (get_bb && get_bb(dev, 0, 0, 0, &pBackBuffer) >= 0 && pBackBuffer) {
        typedef HRESULT (__stdcall *StretchRect_t)(void *, void *, const RECT *, void *, const RECT *, int);
        StretchRect_t stretch = (StretchRect_t)vtbl[34];

        // Find offscreen target with the highest draw count this frame
        int best_idx = -1;
        uint32_t best_draws = 0;
        for (int i = 1; i < g_num_tracked_targets; i++) {
            if (g_tracked_targets[i] && g_tracked_targets[i] != pBackBuffer) {
                if (g_target_draw_counts[i] > best_draws) {
                    best_draws = g_target_draw_counts[i];
                    best_idx = i;
                }
            }
        }

        void *srcTarget = (best_idx >= 0 && best_draws > 0) ? g_tracked_targets[best_idx] : NULL;

        // If the engine drew directly onto the swapchain backbuffer (target 0), do NOT overwrite it!
        // Only StretchRect if backbuffer had <= 1 dummy draw and an offscreen target had active draws.
        if (stretch && srcTarget && g_target_draw_counts[0] <= 1 && best_draws > 0) {
            HRESULT sr_hr = stretch(dev, srcTarget, NULL, pBackBuffer, NULL, 2); // 2 = D3DTEXF_LINEAR
            if (g_present_calls <= 5 || g_present_calls == 60 || (g_present_calls % 120) == 0) {
                log_msg("[VT4-Mod] hk_Present frame %u: StretchRect(srcTarget[%d]=%p draws=%u -> BB=%p) hr=0x%08lx",
                        g_present_calls, best_idx, srcTarget, best_draws, pBackBuffer, (unsigned long)sr_hr);
            }
        } else if (g_target_draw_counts[0] > 1) {
            if (g_present_calls <= 5 || g_present_calls == 60 || (g_present_calls % 120) == 0) {
                log_msg("[VT4-Mod] hk_Present frame %u: Direct backbuffer rendering active (T0 draws=%u), skipping StretchRect",
                        g_present_calls, g_target_draw_counts[0]);
            }
        }

        // Reset per-frame draw counts
        memset(g_target_draw_counts, 0, sizeof(g_target_draw_counts));

        void **bb_vtbl = *(void ***)pBackBuffer;
        typedef ULONG (__stdcall *Release_t)(void *);
        Release_t rel = (Release_t)bb_vtbl[2];
        rel(pBackBuffer);
    }

    if (g_present_calls == 1 || (g_present_calls % 300) == 0) {
        log_msg("[VT4-Mod] Present frame %u: clears=%u (last_col=0x%08lx) draws=%u beginScenes=%u caller=%p last_rt=%p",
                g_present_calls, g_clear_calls, (unsigned long)g_last_clear_color, g_draw_calls, g_begin_scene_calls,
                __builtin_return_address(0), g_last_draw_target);
    }
    if (g_present_calls == 1 || g_present_calls == 60) {
        char path[MAX_PATH];
        snprintf(path, sizeof(path), "c:\\Users\\acorr\\Documents\\tenis\\game\\vt4_present_%u.png", g_present_calls);
        capture_d3d9_screenshot(dev, path);
    }
    return g_real_present(dev, src, dst, dstWnd, dirty);
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
        if (pp->BackBufferWidth == 0) pp->BackBufferWidth = 1280;
        if (pp->BackBufferHeight == 0) pp->BackBufferHeight = 720;
        if (!pp->hDeviceWindow) pp->hDeviceWindow = focus;
        pp->Windowed = TRUE;
        pp->FullScreen_RefreshRateInHz = 0;
        pp->MultiSampleType = 0;
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
    for (size_t i = 0; i < sizeof(configs)/sizeof(configs[0]); i++) {
        if (pp) pp->BackBufferFormat = configs[i].fmt;
        DWORD f = configs[i].flags;
        hr = g_real_createdevice(self, adapter, devtype, focus, f, pp, ppdev);
        log_msg("[VT4-Mod] CreateDevice attempt %u (flags=%08x fmt=%u BB=%ux%u) -> hr=%08lx dev=%p",
                (unsigned)i, f, pp ? pp->BackBufferFormat : 0,
                pp ? pp->BackBufferWidth : 0, pp ? pp->BackBufferHeight : 0,
                (unsigned long)hr, ppdev ? *ppdev : NULL);
        if (hr >= 0 && ppdev && *ppdev) {
            log_msg("[VT4-Mod] CreateDevice SUCCESS on attempt %u! Device: %p", (unsigned)i, *ppdev);
            g_d3d_device = *ppdev;
            g_game_hwnd = focus ? focus : pp->hDeviceWindow;

            // Force proper 1280x720 window dimensions & center on screen
            RECT wr = { 0, 0, 1280, 720 };
            DWORD style = WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX | WS_VISIBLE;
            AdjustWindowRect(&wr, style, FALSE);
            int win_w = wr.right - wr.left;
            int win_h = wr.bottom - wr.top;
            int scr_w = GetSystemMetrics(SM_CXSCREEN);
            int scr_h = GetSystemMetrics(SM_CYSCREEN);
            int pos_x = (scr_w > win_w) ? (scr_w - win_w) / 2 : 50;
            int pos_y = (scr_h > win_h) ? (scr_h - win_h) / 2 : 50;

            SetWindowLongA(g_game_hwnd, GWL_STYLE, style);
            SetWindowPos(g_game_hwnd, HWND_TOP, pos_x, pos_y, win_w, win_h, SWP_SHOWWINDOW | SWP_FRAMECHANGED);
            ShowWindow(g_game_hwnd, SW_SHOWNORMAL);
            UpdateWindow(g_game_hwnd);
            SetForegroundWindow(g_game_hwnd);
            log_msg("[VT4-Mod] Fixed window geometry: pos=(%d,%d) size=%dx%d (client 1280x720)", pos_x, pos_y, win_w, win_h);

            uintptr_t wm = *(uintptr_t *)0x00a75ad0;
            if (wm) {
                *(uint32_t *)wm = 1280;
                *(uint32_t *)(wm + 4) = 720;
                *(uint8_t *)(wm + 0xa) = 1;
                *(uint32_t *)(wm + 0x4c) = 1280;
                *(uint32_t *)(wm + 0x50) = 720;
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

                g_real_setrendertarget = (SetRenderTarget_t)dev_vtbl[37];
                void *hk_srt = (void *)hk_SetRenderTarget;
                patch_bytes((uintptr_t)&dev_vtbl[37], &hk_srt, sizeof(hk_srt));

                g_real_beginscene = (BeginScene_t)dev_vtbl[41];
                void *hk_bs = (void *)hk_BeginScene;
                patch_bytes((uintptr_t)&dev_vtbl[41], &hk_bs, sizeof(hk_bs));

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
    static uint32_t last_log = 0;
    static uint32_t last_state = 999;
    uint32_t *pState = (uint32_t *)((char *)self + 0xe98);
    uint32_t subtask = *(uint32_t *)((char *)self + 0xf68);

    if (*pState != last_state) {
        log_msg("[VT4-Mod] MainMenu state transition: %u -> %u (subtask=%d) at frame %u",
                last_state, *pState, (int)subtask, g_present_calls);
        last_state = *pState;
    }

    if (g_present_calls - last_log >= 60) {
        last_log = g_present_calls;
        log_msg("[VT4-Mod] MainMenu::Update frame %u: state=%u subtask=%d", g_present_calls, *pState, (int)subtask);
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
    int active = is_key_down(VK_LEFT) || is_key_down('A');
    if (eval_nav_key(0, active, 14, 4)) {
        log_msg("[VT4-Mod] Menu Left triggered at frame %u (user=%d)", g_present_calls, user);
        return 1;
    }
    return original_menu_input_offset(self, user, 0x08);
}

// 0x004551E0: Menu / Slider Right
static int __thiscall hk_MenuInput_Right(void *self, int user) {
    int active = is_key_down(VK_RIGHT) || is_key_down('D');
    if (eval_nav_key(1, active, 14, 4)) {
        log_msg("[VT4-Mod] Menu Right triggered at frame %u (user=%d)", g_present_calls, user);
        return 1;
    }
    return original_menu_input_offset(self, user, 0x28);
}

// 0x00455240: Menu Up
static int __thiscall hk_MenuInput_Up(void *self, int user) {
    int active = is_key_down(VK_UP) || is_key_down('W');
    if (eval_nav_key(2, active, 18, 6)) {
        log_msg("[VT4-Mod] Menu Up triggered at frame %u (user=%d)", g_present_calls, user);
        return 1;
    }
    return original_menu_input_offset(self, user, 0x48);
}

// 0x004552A0: Menu Down
static int __thiscall hk_MenuInput_Down(void *self, int user) {
    int active = is_key_down(VK_DOWN) || is_key_down('S');
    if (eval_nav_key(3, active, 18, 6)) {
        log_msg("[VT4-Mod] Menu Down triggered at frame %u (user=%d)", g_present_calls, user);
        return 1;
    }
    return original_menu_input_offset(self, user, 0x68);
}

// 0x00455300: Menu Decide / Enter
static MenuInputFn_t g_real_menu_decide = NULL;
static int __thiscall hk_MenuInput_Decide(void *self, int user) {
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

static int __thiscall hk_IsStartPressed(void *self, int user) {
    if (g_present_calls >= 60 && g_present_calls <= 240) {
        log_msg("[VT4-Mod] hk_IsStartPressed auto-trigger at frame %u: user=%d -> 1", g_present_calls, user);
        return 1;
    }
    return g_real_455590(self, user);
}

static int __thiscall hk_CheckInput_455300(void *self, int user) {
    if (g_present_calls >= 60 && g_present_calls <= 240) {
        log_msg("[VT4-Mod] hk_CheckInput_455300 auto-trigger at frame %u: user=%d -> 1", g_present_calls, user);
        return 1;
    }
    return g_real_455300(self, user);
}

static void apply_vt4_patches(void) {
    DWORD old_code_prot = 0;
    VirtualProtect((void *)0x00401000, 0x00400000, PAGE_EXECUTE_READWRITE, &old_code_prot);

    hook_iat(GetModuleHandleA(NULL), "kernel32.dll", "ExitProcess",
             (void *)hk_ExitProcess, (void **)&g_real_exitprocess);
    hook_iat(GetModuleHandleA(NULL), "d3d9.dll", "Direct3DCreate9",
             (void *)hk_Direct3DCreate9, (void **)&g_real_d3dcreate9);

    log_msg("[VT4-Mod] Applying startup patches...");

    // 1. Registry-free save path & Spanish locale (0x0c0a = 3082)
    *(uint32_t *)0x00a75da0 = 1;
    *(wchar_t **)0x00a75bc4 = g_save_path;
    *(uint32_t *)0x00a75bc8 = 0x0c0a;

    // 2. Default resolution 1280x720 in FUN_004025d0 & global resolution variables
    uint32_t w = 1280, h = 720;
    patch_bytes(0x00402694, &w, 4);
    patch_bytes(0x0040269e, &h, 4);
    uint16_t w16 = 1280, h16 = 720;
    patch_bytes(0x008358c8, &w16, 2);
    patch_bytes(0x008358cc, &h16, 2);

    // 3. Force Windowed mode (0) instead of Fullscreen (1) in FUN_004049b0
    uint8_t windowed = 0;
    patch_bytes(0x00404a95, &windowed, 1);

    // 4. Enable loose files in game/archive/ before resource.bin in FUN_0042fe20
    uint8_t loose_flag = 0;
    patch_bytes(0x0042fe3a, &loose_flag, 1);

    // 5. Unlock all legends & hidden characters (King, Duke, Becker, Edberg, Courier...)
    // FUN_005dfe90 returns BOOL (eax = 1): mov eax, 1; ret 4
    const uint8_t unlock_all_patch[8] = { 0xB8, 0x01, 0x00, 0x00, 0x00, 0xC2, 0x04, 0x00 };
    patch_bytes(0x005dfe90, unlock_all_patch, 8);

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

    // 17. Disable FPLoadSaveIcon::Render at 0x005ef5c0 (prevents black background I_CMN_load_save_bg_M & spinner)
    const uint8_t ret_op = 0xC3;
    patch_bytes(0x005ef5c0, &ret_op, 1);
    log_msg("[VT4-Mod] Patched 0x005ef5c0: FPLoadSaveIcon::Render disabled (ret)");

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

    log_msg("[VT4-Mod] Central Menu Navigation & Analog hooks installed (Up, Down, Left, Right, Decide, Cancel)");

    // 26. Action System hooks (0x0062D830, 0x00633A20-0x00633AA0) for Arrow & WASD menu/slider controls
    install_jmp(0x0062D830, (void *)hk_CheckAction_62d830, 10);
    install_jmp(0x00633A20, (void *)hk_ActionUp, 8);
    install_jmp(0x00633A40, (void *)hk_ActionDown, 8);
    install_jmp(0x00633A60, (void *)hk_ActionLeft, 8);
    install_jmp(0x00633A80, (void *)hk_ActionRight, 8);
    install_jmp(0x00633AA0, (void *)hk_ActionDecide, 8);

    // 27. Neutralize focus loss / blanking: force IsWindowFocused (0x00404dc0) to ALWAYS return TRUE
    const uint8_t ret_true3_focus[3] = { 0xB0, 0x01, 0xC3 }; // mov al, 1; ret
    patch_bytes(0x00404dc0, ret_true3_focus, 3);
    log_msg("[VT4-Mod] Window focus protection installed: IsWindowFocused (0x00404dc0) forced to TRUE");

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

    // Automatic crash recovery for invalid EIP execution (EIP == 0 or non-code memory)
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
