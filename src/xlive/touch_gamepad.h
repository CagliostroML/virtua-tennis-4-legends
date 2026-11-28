/*
 * Interactive Recomp-Style On-Screen Xbox Controller Overlay for Android / Touch / Demo
 * Supports Win32 Mouse (WM_LBUTTONDOWN/MOUSEMOVE/LBUTTONUP) and Windows 8+ Touch/Pen (WM_POINTER*).
 *
 * Included in src/xlive/xlive.c right after render_settings_hud() and BEFORE xinput_get_p1()
 * so draw_screen_quad, draw_font_text, begin_overlay_state, end_overlay_state,
 * g_real_drawprimitiveup, g_pFont, g_pFontTitle, and g_pSprite are already defined.
 */
#ifndef VT4_TOUCH_GAMEPAD_H
#define VT4_TOUCH_GAMEPAD_H

#include <math.h>
#include <stdint.h>
#include <windows.h>

#ifndef WM_POINTERUPDATE
#define WM_POINTERUPDATE          0x0245
#define WM_POINTERDOWN            0x0246
#define WM_POINTERUP              0x0247
#define WM_POINTERCAPTURECHANGED  0x024C
#endif

#define TG_MAX_POINTERS 8

typedef struct {
    int   active;
    DWORD id;
    float vx; /* virtual 1280x720 X */
    float vy; /* virtual 1280x720 Y */
    int   role; /* 0=none, 1=stick, 2=A, 3=B, 4=X, 5=Y, 6=LB, 7=RB, 8=START */
} TgPointer;

static TgPointer g_tg_ptrs[TG_MAX_POINTERS] = { { 0 } };
static int       g_tg_wine_checked = 0;
static int       g_tg_is_wine = 0;
static uint8_t   g_tg_btn_pulse[9] = { 0 }; /* roles 2..8: A, B, X, Y, LB, RB, START */
static uint8_t   g_tg_stick_pulse_frames = 0;
static float     g_tg_stick_pulse_ax = 0.0f;
static float     g_tg_stick_pulse_ay = 0.0f;
static int       g_tg_auto_hidden_by_xinput = 0;
static int       g_tg_poll_active = 0;
static uint32_t  g_tg_diag_logs = 0;

static inline int touch_gamepad_is_wine(void) {
    if (!g_tg_wine_checked) {
        g_tg_wine_checked = 1;
        HMODULE hNtdll = GetModuleHandleA("ntdll.dll");
        if (hNtdll && GetProcAddress(hNtdll, "wine_get_version") != NULL) {
            g_tg_is_wine = 1;
        }
    }
    return g_tg_is_wine;
}

static inline int touch_gamepad_should_show(uint32_t mode) {
    if (mode == 2u) return 1;
    if (mode == 1u) return touch_gamepad_is_wine() && !g_tg_auto_hidden_by_xinput;
    return 0;
}

static inline void tg_clear_all_pointers(void);

static inline void touch_gamepad_notify_real_xinput(float ax, float ay, WORD btns, uint32_t cfg_mode) {
    if (cfg_mode == 1u && !g_tg_auto_hidden_by_xinput &&
        (btns != 0 || fabsf(ax) > 0.35f || fabsf(ay) > 0.35f)) {
        g_tg_auto_hidden_by_xinput = 1;
        g_tg_poll_active = 0;
        tg_clear_all_pointers();
        memset(g_tg_btn_pulse, 0, sizeof(g_tg_btn_pulse));
        g_tg_stick_pulse_frames = 0;
        log_msg("[VT4-Mod] [TOUCHHUD] Real/Winlator XInput input detected -> auto-hiding software overlay (press F6 to restore)");
    }
}

static void touch_gamepad_reset_autohide(void) {
    g_tg_auto_hidden_by_xinput = 0;
}

/* Virtual 1280x720 geometry constants (symmetric bottom-left stick & bottom-right diamond) */
#define TG_STICK_CX   138.0f
#define TG_STICK_CY   572.0f
#define TG_STICK_R     82.0f
#define TG_KNOB_R      33.0f

#define TG_DIA_CX    1132.0f
#define TG_DIA_CY     568.0f
#define TG_DIA_SPREAD  58.0f
#define TG_BTN_R       29.0f

#define TG_LB_X1       54.0f
#define TG_LB_Y1      444.0f
#define TG_LB_X2      136.0f
#define TG_LB_Y2      476.0f

#define TG_RB_X1     1144.0f
#define TG_RB_Y1      444.0f
#define TG_RB_X2     1226.0f
#define TG_RB_Y2      476.0f

#define TG_ST_X1      582.0f
#define TG_ST_Y1      668.0f
#define TG_ST_X2      698.0f
#define TG_ST_Y2      702.0f

static int tg_hit_test_role(float vx, float vy) {
    float dx_s = vx - TG_STICK_CX;
    float dy_s = vy - TG_STICK_CY;
    if ((dx_s * dx_s + dy_s * dy_s) <= (TG_STICK_R + 28.0f) * (TG_STICK_R + 28.0f)) {
        return 1;
    }

    const float hit_r2 = (TG_BTN_R + 14.0f) * (TG_BTN_R + 14.0f);
    float dxa = vx - TG_DIA_CX,                 dya = vy - (TG_DIA_CY + TG_DIA_SPREAD);
    if (dxa * dxa + dya * dya <= hit_r2) return 2; /* A */
    float dxb = vx - (TG_DIA_CX + TG_DIA_SPREAD), dyb = vy - TG_DIA_CY;
    if (dxb * dxb + dyb * dyb <= hit_r2) return 3; /* B */
    float dxx = vx - (TG_DIA_CX - TG_DIA_SPREAD), dyx = vy - TG_DIA_CY;
    if (dxx * dxx + dyx * dyx <= hit_r2) return 4; /* X */
    float dxy = vx - TG_DIA_CX,                 dyy = vy - (TG_DIA_CY - TG_DIA_SPREAD);
    if (dxy * dxy + dyy * dyy <= hit_r2) return 5; /* Y */

    if (vx >= TG_LB_X1 - 8.0f && vx <= TG_LB_X2 + 8.0f && vy >= TG_LB_Y1 - 6.0f && vy <= TG_LB_Y2 + 6.0f) return 6;
    if (vx >= TG_RB_X1 - 8.0f && vx <= TG_RB_X2 + 8.0f && vy >= TG_RB_Y1 - 6.0f && vy <= TG_RB_Y2 + 6.0f) return 7;
    if (vx >= TG_ST_X1 - 8.0f && vx <= TG_ST_X2 + 8.0f && vy >= TG_ST_Y1 - 6.0f && vy <= TG_ST_Y2 + 6.0f) return 8;
    return 0;
}

static void tg_upsert_pointer(DWORD id, float vx, float vy, int is_down) {
    int slot = -1;
    int free_slot = -1;
    for (int i = 0; i < TG_MAX_POINTERS; i++) {
        if (g_tg_ptrs[i].active && g_tg_ptrs[i].id == id) {
            slot = i;
            break;
        }
        if (!g_tg_ptrs[i].active && free_slot < 0) free_slot = i;
    }
    if (slot < 0) {
        if (!is_down || free_slot < 0) return;
        slot = free_slot;
        g_tg_ptrs[slot].active = 1;
        g_tg_ptrs[slot].id = id;
        g_tg_ptrs[slot].role = tg_hit_test_role(vx, vy);
    } else if (g_tg_ptrs[slot].role != 1) {
        g_tg_ptrs[slot].role = tg_hit_test_role(vx, vy);
    }
    g_tg_ptrs[slot].vx = vx;
    g_tg_ptrs[slot].vy = vy;
    if (is_down) {
        int role = g_tg_ptrs[slot].role;
        if (role >= 2 && role <= 8) {
            g_tg_btn_pulse[role] = 6u;
        } else if (role == 1) {
            float dx = (vx - TG_STICK_CX) / TG_STICK_R;
            float dy = (vy - TG_STICK_CY) / TG_STICK_R;
            float mag = sqrtf(dx * dx + dy * dy);
            if (mag > 1.0f) { dx /= mag; dy /= mag; }
            if (mag > 0.25f) {
                g_tg_stick_pulse_frames = 4u;
                g_tg_stick_pulse_ax = dx;
                g_tg_stick_pulse_ay = dy;
            }
        }
        if (g_tg_diag_logs < 16u) {
            g_tg_diag_logs++;
            log_msg("[VT4-Mod] [TOUCHHUD] press id=%lu role=%d vx=%.1f vy=%.1f",
                    (unsigned long)id, role, vx, vy);
        }
    }
}

static void tg_release_pointer(DWORD id) {
    for (int i = 0; i < TG_MAX_POINTERS; i++) {
        if (g_tg_ptrs[i].active && g_tg_ptrs[i].id == id) {
            g_tg_ptrs[i].active = 0;
            g_tg_ptrs[i].role = 0;
        }
    }
}

static inline void tg_clear_all_pointers(void) {
    memset(g_tg_ptrs, 0, sizeof(g_tg_ptrs));
}

static inline int tg_client_to_virtual(HWND hwnd, int cx, int cy, float *out_vx, float *out_vy) {
    RECT rc;
    if (!hwnd || !GetClientRect(hwnd, &rc)) return 0;
    int cw = rc.right - rc.left;
    int ch = rc.bottom - rc.top;
    if (cw <= 0 || ch <= 0) return 0;
    *out_vx = ((float)cx / (float)cw) * 1280.0f;
    *out_vy = ((float)cy / (float)ch) * 720.0f;
    return 1;
}

static int touch_gamepad_on_wndmsg(HWND hwnd, UINT uMsg, WPARAM wParam, LPARAM lParam, uint32_t cfg_mode) {
    if (!touch_gamepad_should_show(cfg_mode)) return 0;

    if (uMsg == WM_LBUTTONDOWN) {
        float vx = 0.0f, vy = 0.0f;
        int cx = (int)(short)LOWORD(lParam);
        int cy = (int)(short)HIWORD(lParam);
        if (!tg_client_to_virtual(hwnd, cx, cy, &vx, &vy)) return 0;
        if (tg_hit_test_role(vx, vy) == 0) return 0;
        tg_upsert_pointer(0u, vx, vy, 1);
        SetCapture(hwnd);
        return 1;
    }
    if (uMsg == WM_MOUSEMOVE) {
        if (!(wParam & MK_LBUTTON)) return 0;
        for (int i = 0; i < TG_MAX_POINTERS; i++) {
            if (g_tg_ptrs[i].active && g_tg_ptrs[i].id == 0u) {
                float vx = 0.0f, vy = 0.0f;
                int cx = (int)(short)LOWORD(lParam);
                int cy = (int)(short)HIWORD(lParam);
                if (tg_client_to_virtual(hwnd, cx, cy, &vx, &vy)) {
                    tg_upsert_pointer(0u, vx, vy, 0);
                }
                return 1;
            }
        }
        return 0;
    }
    if (uMsg == WM_LBUTTONUP) {
        int had = 0;
        for (int i = 0; i < TG_MAX_POINTERS; i++) {
            if (g_tg_ptrs[i].active && g_tg_ptrs[i].id == 0u) { had = 1; break; }
        }
        tg_release_pointer(0u);
        if (GetCapture() == hwnd) ReleaseCapture();
        return had;
    }
    if (uMsg == WM_CAPTURECHANGED) {
        tg_release_pointer(0u);
        return 0;
    }

    if (uMsg == WM_POINTERDOWN || uMsg == WM_POINTERUPDATE ||
        uMsg == WM_POINTERUP || uMsg == WM_POINTERCAPTURECHANGED) {
        DWORD pid = (DWORD)(LOWORD(wParam) + 1u);
        if (uMsg == WM_POINTERUP || uMsg == WM_POINTERCAPTURECHANGED) {
            int had = 0;
            for (int i = 0; i < TG_MAX_POINTERS; i++) {
                if (g_tg_ptrs[i].active && g_tg_ptrs[i].id == pid) { had = 1; break; }
            }
            tg_release_pointer(pid);
            return had;
        }
        POINT pt = { (LONG)(short)LOWORD(lParam), (LONG)(short)HIWORD(lParam) };
        if (hwnd) ScreenToClient(hwnd, &pt);
        float vx = 0.0f, vy = 0.0f;
        if (!tg_client_to_virtual(hwnd, pt.x, pt.y, &vx, &vy)) return 0;
        if (uMsg == WM_POINTERDOWN && tg_hit_test_role(vx, vy) == 0) return 0;
        if (uMsg == WM_POINTERUPDATE) {
            int found = 0;
            for (int i = 0; i < TG_MAX_POINTERS; i++) {
                if (g_tg_ptrs[i].active && g_tg_ptrs[i].id == pid) { found = 1; break; }
            }
            if (!found) return 0;
        }
        tg_upsert_pointer(pid, vx, vy, (uMsg == WM_POINTERDOWN));
        return 1;
    }
    return 0;
}

static void touch_gamepad_poll_mouse(HWND hwnd, uint32_t cfg_mode) {
    if (!touch_gamepad_should_show(cfg_mode) || !hwnd) {
        if (g_tg_poll_active) {
            g_tg_poll_active = 0;
            tg_release_pointer(0xFFFEu);
        }
        return;
    }
    for (int i = 0; i < TG_MAX_POINTERS; i++) {
        if (g_tg_ptrs[i].active && g_tg_ptrs[i].id == 0u) return;
    }
    SHORT st = GetAsyncKeyState(VK_LBUTTON);
    int held = (st & 0x8000) != 0;
    int tapped = (st & 0x0001) != 0;
    if (held || tapped) {
        POINT pt;
        if (GetCursorPos(&pt) && ScreenToClient(hwnd, &pt)) {
            float vx = 0.0f, vy = 0.0f;
            if (tg_client_to_virtual(hwnd, pt.x, pt.y, &vx, &vy)) {
                int role = tg_hit_test_role(vx, vy);
                if (role != 0 || g_tg_poll_active) {
                    tg_upsert_pointer(0xFFFEu, vx, vy, (!g_tg_poll_active || tapped));
                    g_tg_poll_active = held ? 1 : 0;
                    if (!held) tg_release_pointer(0xFFFEu);
                }
            }
        }
    } else if (g_tg_poll_active) {
        g_tg_poll_active = 0;
        tg_release_pointer(0xFFFEu);
    }
}

static int touch_gamepad_get_p1(float *out_ax, float *out_ay, WORD *out_btns) {
    float ax = 0.0f, ay = 0.0f;
    WORD btns = 0;
    int any = 0;

    static const WORD k_role_masks[9] = {
        0, 0, 0x1000, 0x2000, 0x4000, 0x8000, 0x0100, 0x0200, 0x0010
    };
    for (int r = 2; r <= 8; r++) {
        if (g_tg_btn_pulse[r] > 0) {
            btns |= k_role_masks[r];
            any = 1;
        }
    }
    if (g_tg_stick_pulse_frames > 0) {
        ax = g_tg_stick_pulse_ax;
        ay = g_tg_stick_pulse_ay;
        any = 1;
    }

    for (int i = 0; i < TG_MAX_POINTERS; i++) {
        if (!g_tg_ptrs[i].active) continue;
        any = 1;
        switch (g_tg_ptrs[i].role) {
            case 1: {
                float dx = (g_tg_ptrs[i].vx - TG_STICK_CX) / TG_STICK_R;
                float dy = (g_tg_ptrs[i].vy - TG_STICK_CY) / TG_STICK_R;
                float mag = sqrtf(dx * dx + dy * dy);
                if (mag > 1.0f) { dx /= mag; dy /= mag; }
                if (mag > 0.14f) {
                    ax = dx;
                    ay = dy;
                }
                break;
            }
            case 2: btns |= 0x1000; break; /* A */
            case 3: btns |= 0x2000; break; /* B */
            case 4: btns |= 0x4000; break; /* X */
            case 5: btns |= 0x8000; break; /* Y */
            case 6: btns |= 0x0100; break; /* LB */
            case 7: btns |= 0x0200; break; /* RB */
            case 8: btns |= 0x0010; break; /* START */
            default: break;
        }
    }

    if (out_ax) *out_ax = ax;
    if (out_ay) *out_ay = ay;
    if (out_btns) *out_btns = btns;
    return any;
}

static void tg_setup_flat_rs(void *dev) {
    void **vtbl = *(void ***)dev;
    typedef HRESULT (__stdcall *SetFVF_t)(void *, DWORD);
    typedef HRESULT (__stdcall *SetRenderState_t)(void *, DWORD, DWORD);
    typedef HRESULT (__stdcall *SetTexture_t)(void *, DWORD, void *);
    typedef HRESULT (__stdcall *SetVertexShader_t)(void *, void *);
    typedef HRESULT (__stdcall *SetPixelShader_t)(void *, void *);
    SetFVF_t          set_fvf = (SetFVF_t)vtbl[89];
    SetRenderState_t  set_rs  = (SetRenderState_t)vtbl[57];
    SetTexture_t      set_tex = (SetTexture_t)vtbl[65];
    SetVertexShader_t set_vs  = (SetVertexShader_t)vtbl[92];
    SetPixelShader_t  set_ps  = (SetPixelShader_t)vtbl[107];
    if (set_vs)  set_vs(dev, NULL);
    if (set_ps)  set_ps(dev, NULL);
    if (set_tex) set_tex(dev, 0, NULL);
    if (set_rs) {
        set_rs(dev, 27, 1);  /* D3DRS_ALPHABLENDENABLE = TRUE */
        set_rs(dev, 19, 5);  /* D3DBLEND_SRCALPHA */
        set_rs(dev, 20, 6);  /* D3DBLEND_INVSRCALPHA */
        set_rs(dev, 137, 0); /* D3DRS_LIGHTING = FALSE */
        set_rs(dev, 22, 1);  /* D3DCULL_NONE */
        set_rs(dev, 7, 0);   /* D3DRS_ZENABLE = FALSE */
    }
    if (set_fvf) set_fvf(dev, FVF_SCREEN_VERTEX);
}

static void tg_draw_circle(void *dev, float cx, float cy, float r, DWORD col_center, DWORD col_edge) {
    if (!g_real_drawprimitiveup) return;
    enum { SEGS = 28 };
    ScreenVertex v[SEGS + 2];
    v[0].x = cx; v[0].y = cy; v[0].z = 0.0f; v[0].rhw = 1.0f; v[0].color = col_center;
    for (int i = 0; i <= SEGS; i++) {
        float a = (float)i * (6.2831853f / (float)SEGS);
        v[i + 1].x = cx + cosf(a) * r;
        v[i + 1].y = cy + sinf(a) * r;
        v[i + 1].z = 0.0f;
        v[i + 1].rhw = 1.0f;
        v[i + 1].color = col_edge;
    }
    tg_setup_flat_rs(dev);
    g_real_drawprimitiveup(dev, 6 /* D3DPT_TRIANGLEFAN */, SEGS, v, sizeof(ScreenVertex));
}

static void tg_draw_ring(void *dev, float cx, float cy, float r_in, float r_out, DWORD col_in, DWORD col_out) {
    if (!g_real_drawprimitiveup) return;
    enum { SEGS = 28 };
    ScreenVertex v[(SEGS + 1) * 2];
    for (int i = 0; i <= SEGS; i++) {
        float a = (float)i * (6.2831853f / (float)SEGS);
        float cs = cosf(a), sn = sinf(a);
        v[i * 2 + 0].x = cx + cs * r_in;  v[i * 2 + 0].y = cy + sn * r_in;
        v[i * 2 + 0].z = 0.0f; v[i * 2 + 0].rhw = 1.0f; v[i * 2 + 0].color = col_in;
        v[i * 2 + 1].x = cx + cs * r_out; v[i * 2 + 1].y = cy + sn * r_out;
        v[i * 2 + 1].z = 0.0f; v[i * 2 + 1].rhw = 1.0f; v[i * 2 + 1].color = col_out;
    }
    tg_setup_flat_rs(dev);
    g_real_drawprimitiveup(dev, 5 /* D3DPT_TRIANGLESTRIP */, SEGS * 2, v, sizeof(ScreenVertex));
}

static void tg_draw_pill(void *dev, float x1, float y1, float x2, float y2, DWORD bg, DWORD border) {
    draw_screen_quad(dev, x1, y1, x2, y2, bg);
    draw_screen_quad(dev, x1, y1, x2, y1 + 1.8f, border);
    draw_screen_quad(dev, x1, y2 - 1.8f, x2, y2, border);
    draw_screen_quad(dev, x1, y1, x1 + 1.8f, y2, border);
    draw_screen_quad(dev, x2 - 1.8f, y1, x2, y2, border);
}

static void render_touch_gamepad_hud(void *dev, uint32_t cfg_mode, uint32_t win_w, uint32_t win_h,
                                     int in_match, int in_char_sel, float vis_ax, float vis_ay, WORD vis_btns) {
    if (!touch_gamepad_should_show(cfg_mode)) {
        for (int r = 2; r <= 8; r++) {
            if (g_tg_btn_pulse[r] > 0) g_tg_btn_pulse[r]--;
        }
        if (g_tg_stick_pulse_frames > 0) g_tg_stick_pulse_frames--;
        return;
    }
    if (!dev || !*(void ***)dev) return;
    if (!g_pFont || !g_pFontTitle || !g_pSprite) init_menu_fonts(dev);
    if (!begin_overlay_state(dev)) return;

    void **vtbl = *(void ***)dev;
    typedef HRESULT (__stdcall *SetViewport_t)(void *, const void *);
    SetViewport_t set_vp = (SetViewport_t)vtbl[47];
    uint32_t full_vp[6] = { 0, 0, win_w, win_h, 0, 0x3f800000 };
    if (set_vp) set_vp(dev, full_vp);

    float sx = (float)win_w / 1280.0f;
    float sy = (float)win_h / 720.0f;

    /* Combine live touch state with physical/keyboard mirror so user gets immediate feedback */
    float t_ax = 0.0f, t_ay = 0.0f;
    WORD t_btns = 0;
    touch_gamepad_get_p1(&t_ax, &t_ay, &t_btns);
    float stick_x = (fabsf(t_ax) > 0.05f || fabsf(t_ay) > 0.05f) ? t_ax : vis_ax;
    float stick_y = (fabsf(t_ax) > 0.05f || fabsf(t_ay) > 0.05f) ? t_ay : vis_ay;
    WORD active_btns = vis_btns | t_btns;

    /* 1. Bottom-Left Virtual Xbox Thumbstick */
    float scx = TG_STICK_CX * sx, scy = TG_STICK_CY * sy;
    float sr  = TG_STICK_R * sy,  kr  = TG_KNOB_R * sy;
    int stick_on = (fabsf(stick_x) > 0.08f || fabsf(stick_y) > 0.08f);
    tg_draw_circle(dev, scx, scy, sr, 0x720E1420, 0x54080C14);
    tg_draw_ring(dev, scx, scy, sr - 2.5f * sy, sr,
                 stick_on ? 0xCC70E8FF : 0x78C8D4EA,
                 stick_on ? 0xCC70E8FF : 0x78C8D4EA);
    /* Inner cardinal dots */
    tg_draw_circle(dev, scx, scy - sr * 0.68f, 3.0f * sy, 0x70FFFFFF, 0x70FFFFFF);
    tg_draw_circle(dev, scx, scy + sr * 0.68f, 3.0f * sy, 0x70FFFFFF, 0x70FFFFFF);
    tg_draw_circle(dev, scx - sr * 0.68f, scy, 3.0f * sy, 0x70FFFFFF, 0x70FFFFFF);
    tg_draw_circle(dev, scx + sr * 0.68f, scy, 3.0f * sy, 0x70FFFFFF, 0x70FFFFFF);

    float kx = scx + stick_x * (sr - kr * 0.65f);
    float ky = scy + stick_y * (sr - kr * 0.65f);
    tg_draw_circle(dev, kx, ky, kr, stick_on ? 0xCCF2F6FF : 0xA8C8D2E4, stick_on ? 0xCC8CC8FF : 0x90606A7E);
    tg_draw_ring(dev, kx, ky, kr - 2.0f * sy, kr, 0xD8FFFFFF, 0xD8FFFFFF);

    /* 2. Bottom-Right Xbox ABXY Diamond */
    struct {
        float ox, oy;
        WORD mask;
        DWORD fill_idle, fill_hit, rim;
        const char *letter;
        const char *sub;
    } abxy[4] = {
        {  0.0f,  TG_DIA_SPREAD, 0x1000, 0x941E9E46, 0xE832EA66, 0xD878FF9C, "A", in_match ? "TOPSPIN" : "OK" },
        {  TG_DIA_SPREAD,  0.0f, 0x2000, 0x94B82832, 0xE8FF404E, 0xD8FF8A90, "B", in_match ? "GLOBO"   : "ATRAS" },
        { -TG_DIA_SPREAD,  0.0f, 0x4000, 0x942068C8, 0xE83CA0FF, 0xD88CCCFF, "X", in_match ? "CORTADO" : "CORT." },
        {  0.0f, -TG_DIA_SPREAD, 0x8000, 0x94C49818, 0xE8FFD438, 0xD8FFE888, "Y", in_match ? "DEJADA"  : "SUPER" }
    };
    float br = TG_BTN_R * sy;
    for (int i = 0; i < 4; i++) {
        float bx = (TG_DIA_CX + abxy[i].ox) * sx;
        float by = (TG_DIA_CY + abxy[i].oy) * sy;
        int down = (active_btns & abxy[i].mask) != 0;
        tg_draw_circle(dev, bx, by, br + (down ? 3.0f * sy : 0.0f),
                       down ? abxy[i].fill_hit : abxy[i].fill_idle, 0x8810141C);
        tg_draw_ring(dev, bx, by, br - 2.2f * sy, br, abxy[i].rim, abxy[i].rim);
    }

    /* 3. LB / RB Shoulder Pills (highlighted on CharaSelect or always accessible) */
    int lb_down = (active_btns & 0x0100) != 0;
    int rb_down = (active_btns & 0x0200) != 0;
    int st_down = (active_btns & 0x0010) != 0;
    DWORD lb_bg = lb_down ? 0xD88416DE : (in_char_sel ? 0xA8202638 : 0x72141824);
    DWORD rb_bg = rb_down ? 0xD88416DE : (in_char_sel ? 0xA8202638 : 0x72141824);
    DWORD st_bg = st_down ? 0xD8149850 : 0x88141824;
    tg_draw_pill(dev, TG_LB_X1 * sx, TG_LB_Y1 * sy, TG_LB_X2 * sx, TG_LB_Y2 * sy, lb_bg, lb_down ? 0xFFFFFFFF : 0x98B8C4DC);
    tg_draw_pill(dev, TG_RB_X1 * sx, TG_RB_Y1 * sy, TG_RB_X2 * sx, TG_RB_Y2 * sy, rb_bg, rb_down ? 0xFFFFFFFF : 0x98B8C4DC);
    tg_draw_pill(dev, TG_ST_X1 * sx, TG_ST_Y1 * sy, TG_ST_X2 * sx, TG_ST_Y2 * sy, st_bg, st_down ? 0xFF80FFB8 : 0x98A8B4CC);

    if (g_pFont && g_pFontTitle && g_pSprite) {
        void **svtbl = *(void ***)g_pSprite;
        typedef HRESULT (__stdcall *SpriteBegin_t)(void *, DWORD);
        typedef HRESULT (__stdcall *SpriteEnd_t)(void *);
        SpriteBegin_t sp_begin = (SpriteBegin_t)svtbl[8];
        SpriteEnd_t   sp_end   = (SpriteEnd_t)svtbl[11];
        if (sp_begin && sp_begin(g_pSprite, 0x10) >= 0) {
            RECT r;
            for (int i = 0; i < 4; i++) {
                float bx = (TG_DIA_CX + abxy[i].ox) * sx;
                float by = (TG_DIA_CY + abxy[i].oy) * sy;
                r.left = (LONG)(bx - br); r.top = (LONG)(by - br * 0.72f);
                r.right = (LONG)(bx + br); r.bottom = (LONG)(by + br * 0.25f);
                draw_font_text(g_pFontTitle, abxy[i].letter, &r, 0xFFFFFFFF, 1);
                r.top = (LONG)(by + br * 0.14f); r.bottom = (LONG)(by + br * 0.85f);
                draw_font_text(g_pFont, abxy[i].sub, &r, 0xFFEAEFF8, 1);
            }
            r.left = (LONG)(TG_LB_X1 * sx); r.top = (LONG)(TG_LB_Y1 * sy);
            r.right = (LONG)(TG_LB_X2 * sx); r.bottom = (LONG)(TG_LB_Y2 * sy);
            draw_font_text(g_pFont, in_char_sel ? "< LB PAG" : "LB", &r, 0xFFF0F4FF, 1);

            r.left = (LONG)(TG_RB_X1 * sx); r.top = (LONG)(TG_RB_Y1 * sy);
            r.right = (LONG)(TG_RB_X2 * sx); r.bottom = (LONG)(TG_RB_Y2 * sy);
            draw_font_text(g_pFont, in_char_sel ? "PAG RB >" : "RB", &r, 0xFFF0F4FF, 1);

            r.left = (LONG)(TG_ST_X1 * sx); r.top = (LONG)(TG_ST_Y1 * sy);
            r.right = (LONG)(TG_ST_X2 * sx); r.bottom = (LONG)(TG_ST_Y2 * sy);
            draw_font_text(g_pFont, "START / PAUSA", &r, 0xFFE8EEF8, 1);

            r.left = (LONG)(scx - sr); r.top = (LONG)(scy + sr + 4.0f * sy);
            r.right = (LONG)(scx + sr); r.bottom = (LONG)(scy + sr + 24.0f * sy);
            draw_font_text(g_pFont, "XBOX TACTIL [F6]", &r, 0xB8DDE6F4, 1);

            if (sp_end) sp_end(g_pSprite);
        }
    }

    end_overlay_state(dev);
    ensure_d3d9_device_hooks(dev);

    for (int r = 2; r <= 8; r++) {
        if (g_tg_btn_pulse[r] > 0) g_tg_btn_pulse[r]--;
    }
    if (g_tg_stick_pulse_frames > 0) g_tg_stick_pulse_frames--;
}

#endif /* VT4_TOUCH_GAMEPAD_H */
