/*
 * perf_opt.h — Performance Telemetry, Fast I/O Cache, Precision Frame Pacer &
 *              Android/Winlator Low-Spec Profiles for VT4 Legends & Next-Gen Edition.
 *
 * Included by src/xlive/xlive.c after basic globals (g_cfg_*, g_game_dir,
 * g_present_calls, g_logic_ticks, log_msg, patch_nops).
 */
#ifndef VT4_PERF_OPT_H
#define VT4_PERF_OPT_H

#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <ctype.h>
#include <windows.h>

/* =========================================================================
 * [Performance] Configuration (loaded from vt4_settings.ini + env overrides)
 * ========================================================================= */
/* PerfProfile:
 *   0 = Ultra / PC Default (full visuals, Fast I/O cache, precision 60Hz pacing, zero 30fps VSync bug)
 *   1 = High-FPS Esports   (VSync OFF, precision pacing / optional UnlockFPS, 1024 shadows, <=2x MSAA, CleanPostFX)
 *   2 = Android / Low-Spec (Winlator/Box64/DXVK/Turnip: 512 shadows, 256x128 bloom, MSAA 0, Aniso 0,
 *                           CleanPostFX=1, Fast I/O cache, low-CPU pacing)
 */
static uint32_t g_cfg_perf_profile = 0;
static uint32_t g_cfg_unlock_fps   = 0; /* 0 = 1.000x physics speed (60Hz paced), 1 = uncapped benchmark/turbo */
static uint32_t g_cfg_target_fps   = 60;
static uint32_t g_cfg_bench_log    = 0; /* 1 when BenchLog=1 or VT4_BENCH=1 */
static uint32_t g_perf_fast_io     = 1; /* 1 = O(1) RAM hash cache (0 GetFileAttributesA syscalls) */
static uint32_t g_perf_pacer_active = 1; /* 1 = precision hybrid QPC pacer + 0x0040553e loop fix */

/* =========================================================================
 * High-Resolution Clock & Precision Hybrid Frame Pacer
 * ========================================================================= */
typedef UINT (WINAPI *TimePeriodFn_t)(UINT);
static TimePeriodFn_t g_perf_timeBeginPeriod = NULL;
static TimePeriodFn_t g_perf_timeEndPeriod   = NULL;
static int            g_perf_timer_1ms_set   = 0;

static LARGE_INTEGER  g_perf_qpc_freq;
static double         g_perf_qpc_to_ms       = 0.0;
static LARGE_INTEGER  g_perf_init_qpc;
static int64_t        g_perf_pacer_next_qpc  = 0;

static void perf_init_clock(void) {
    if (g_perf_qpc_to_ms != 0.0) return;
    QueryPerformanceFrequency(&g_perf_qpc_freq);
    if (g_perf_qpc_freq.QuadPart > 0) {
        g_perf_qpc_to_ms = 1000.0 / (double)g_perf_qpc_freq.QuadPart;
    } else {
        g_perf_qpc_to_ms = 1.0;
    }
    QueryPerformanceCounter(&g_perf_init_qpc);

    if (!g_perf_timer_1ms_set) {
        HMODULE hWinmm = GetModuleHandleA("winmm.dll");
        if (!hWinmm) hWinmm = LoadLibraryA("winmm.dll");
        if (hWinmm) {
            g_perf_timeBeginPeriod = (TimePeriodFn_t)GetProcAddress(hWinmm, "timeBeginPeriod");
            g_perf_timeEndPeriod   = (TimePeriodFn_t)GetProcAddress(hWinmm, "timeEndPeriod");
            if (g_perf_timeBeginPeriod) {
                g_perf_timeBeginPeriod(1);
                g_perf_timer_1ms_set = 1;
            }
        }
    }
}

static void perf_shutdown(void) {
    if (g_perf_timer_1ms_set && g_perf_timeEndPeriod) {
        g_perf_timeEndPeriod(1);
        g_perf_timer_1ms_set = 0;
    }
}

/* Precision Hybrid Sleep + QPC Spin-Wait Frame Pacer
 * Eliminates:
 *   1) VT4's 30.77 FPS VSync double-wait bug (wm_vsync_flag=0 + D3DPRESENT_INTERVAL_ONE)
 *   2) VT4's 100% single-core CPU busy-wait spin in 0x004054cb..0x00405646
 *   3) D3D9 VSync 33-50ms input lag and 60->30 FPS half-refresh drops
 */
static inline void perf_pacer_wait(void) {
    if (!g_perf_pacer_active || g_cfg_unlock_fps) return;
    if (g_perf_qpc_freq.QuadPart <= 0) return;

    int64_t frame_ticks = g_perf_qpc_freq.QuadPart / (int64_t)(g_cfg_target_fps > 0 ? g_cfg_target_fps : 60);
    LARGE_INTEGER now;
    QueryPerformanceCounter(&now);

    if (g_perf_pacer_next_qpc == 0) {
        g_perf_pacer_next_qpc = now.QuadPart + frame_ticks;
        return;
    }

    int64_t rem = g_perf_pacer_next_qpc - now.QuadPart;
    if (rem <= 0) {
        /* Frame ran long (load screen / screenshot / heavy spike): resync cleanly without fast-forward */
        if (-rem > frame_ticks / 2) {
            g_perf_pacer_next_qpc = now.QuadPart + frame_ticks;
        } else {
            g_perf_pacer_next_qpc += frame_ticks;
        }
        return;
    }

    /* Sleep coarsely while > spin_margin_ms remains (wider margin on Android/Low-Spec for thermals) */
    double spin_margin_ms = (g_cfg_perf_profile == 2) ? 2.8 : 2.0;
    int64_t spin_margin_ticks = (int64_t)(spin_margin_ms / g_perf_qpc_to_ms);
    if (rem > spin_margin_ticks) {
        DWORD sleep_ms = (DWORD)((double)(rem - spin_margin_ticks) * g_perf_qpc_to_ms);
        if (sleep_ms >= 1) {
            Sleep(sleep_ms);
        }
    }

    /* Micro spin-wait for sub-0.05ms frame pacing precision */
    for (;;) {
        QueryPerformanceCounter(&now);
        if (now.QuadPart >= g_perf_pacer_next_qpc) break;
        __asm__ __volatile__("pause" ::: "memory");
    }
    g_perf_pacer_next_qpc += frame_ticks;
}

/* =========================================================================
 * Zero-Overhead QPC Telemetry (active ONLY when g_cfg_bench_log != 0)
 * ========================================================================= */
#define PERF_BENCH_MAX_FRAMES 8192

static LARGE_INTEGER g_perf_last_present_qpc;
static int           g_perf_has_last_present = 0;

static float        *g_bench_ft_ms = NULL;
static uint32_t      g_bench_ft_count = 0;
static uint32_t      g_bench_ft_cap = PERF_BENCH_MAX_FRAMES;

static int           g_bench_in_match = 0;
static uint32_t      g_bench_match_frames = 0;
static uint32_t      g_bench_match_logic_ticks = 0;
static uint32_t      g_bench_match_dip_sum = 0;
static uint32_t      g_bench_match_draws_sum = 0;
static uint32_t      g_bench_frame_dip = 0;
static uint32_t      g_bench_frame_draws = 0;
static LARGE_INTEGER g_bench_match_t0;
static int           g_bench_state_logged = 0;

/* I/O Telemetry */
static uint64_t      g_bench_io_calls = 0;
static uint64_t      g_bench_io_hits = 0;
static uint64_t      g_bench_io_syscalls = 0;
static int64_t       g_bench_io_qpc_ticks = 0;

static int perf_cmp_float(const void *a, const void *b) {
    float fa = *(const float *)a;
    float fb = *(const float *)b;
    return (fa > fb) - (fa < fb);
}

static void perf_bench_dump(const char *tag) {
    if (!g_cfg_bench_log || !g_bench_ft_ms || g_bench_ft_count < 10) return;

    uint32_t n = g_bench_ft_count;
    float *sorted = (float *)malloc(sizeof(float) * n);
    if (!sorted) return;
    double sum_ms = 0.0;
    for (uint32_t i = 0; i < n; i++) {
        sorted[i] = g_bench_ft_ms[i];
        sum_ms += (double)g_bench_ft_ms[i];
    }
    qsort(sorted, n, sizeof(float), perf_cmp_float);

    double avg_ms = sum_ms / (double)n;
    double avg_fps = (avg_ms > 0.0001) ? (1000.0 / avg_ms) : 0.0;
    float min_ms = sorted[0];
    float p50_ms = sorted[n / 2];
    float p95_ms = sorted[(uint32_t)((n - 1) * 0.95)];
    float p99_ms = sorted[(uint32_t)((n - 1) * 0.99)];
    float max_ms = sorted[n - 1];

    uint32_t tail_cnt = n / 100;
    if (tail_cnt < 1) tail_cnt = 1;
    double tail_sum = 0.0;
    for (uint32_t i = n - tail_cnt; i < n; i++) {
        tail_sum += (double)sorted[i];
    }
    double one_pct_low_fps = (tail_sum > 0.0001) ? (1000.0 / (tail_sum / (double)tail_cnt)) : 0.0;
    free(sorted);

    double dip_per_frame = (g_bench_match_frames > 0) ? ((double)g_bench_match_dip_sum / (double)g_bench_match_frames) : 0.0;
    double draws_per_frame = (g_bench_match_frames > 0) ? ((double)g_bench_match_draws_sum / (double)g_bench_match_frames) : 0.0;
    double io_ms = (double)g_bench_io_qpc_ticks * g_perf_qpc_to_ms;
    double logic_ratio = (g_bench_match_frames > 0) ? ((double)g_bench_match_logic_ticks / (double)g_bench_match_frames) : 0.0;

    log_msg("[PERF-BENCH] tag=%s profile=%u frames=%u elapsed_ms=%.1f avg_fps=%.2f low1_fps=%.2f "
            "ft_min=%.2f ft_avg=%.2f ft_p50=%.2f ft_p95=%.2f ft_p99=%.2f ft_max=%.2f "
            "dip_pf=%.1f draws_pf=%.1f io_calls=%llu io_hits=%llu io_syscalls=%llu io_ms=%.2f "
            "logic_ticks=%u logic_ratio=%.3f",
            tag, g_cfg_perf_profile, n, sum_ms, avg_fps, one_pct_low_fps,
            min_ms, avg_ms, p50_ms, p95_ms, p99_ms, max_ms,
            dip_per_frame, draws_per_frame,
            (unsigned long long)g_bench_io_calls,
            (unsigned long long)g_bench_io_hits,
            (unsigned long long)g_bench_io_syscalls,
            io_ms, g_bench_match_logic_ticks, logic_ratio);
}

static inline void perf_bench_on_live_match_ready(void) {
    if (!g_cfg_bench_log) return;
    if (!g_bench_in_match) {
        g_bench_in_match = 1;
        g_bench_ft_count = 0;
        g_bench_match_frames = 0;
        g_bench_match_logic_ticks = 0;
        g_bench_match_dip_sum = 0;
        g_bench_match_draws_sum = 0;
        g_perf_has_last_present = 0;
        QueryPerformanceCounter(&g_bench_match_t0);
        if (!g_bench_state_logged) {
            g_bench_state_logged = 1;
            uintptr_t wm = *(uintptr_t *)0x00a75ad0;
            uint32_t wm_vsync = wm ? (uint32_t)(*(uint8_t *)(wm + 0x1c)) : 99u;
            double boot_to_match_ms = (double)(g_bench_match_t0.QuadPart - g_perf_init_qpc.QuadPart) * g_perf_qpc_to_ms;
            log_msg("[PERF-STATE] wm_vsync_flag=%u boot_to_match_ms=%.1f io_calls=%llu io_hits=%llu io_syscalls=%llu io_ms=%.2f",
                    wm_vsync, boot_to_match_ms,
                    (unsigned long long)g_bench_io_calls,
                    (unsigned long long)g_bench_io_hits,
                    (unsigned long long)g_bench_io_syscalls,
                    (double)g_bench_io_qpc_ticks * g_perf_qpc_to_ms);
        }
    }
}

static inline void perf_bench_on_logic_tick(int ticks) {
    if (g_cfg_bench_log && g_bench_in_match) {
        g_bench_match_logic_ticks += (uint32_t)(ticks > 0 ? ticks : 1);
    }
}

static inline void perf_bench_on_dip(void) {
    if (g_cfg_bench_log && g_bench_in_match) {
        g_bench_frame_dip++;
    }
}

static inline void perf_bench_on_draw(void) {
    if (g_cfg_bench_log && g_bench_in_match) {
        g_bench_frame_draws++;
    }
}

static inline void perf_bench_on_present_after(void) {
    if (!g_cfg_bench_log || !g_bench_in_match) return;

    LARGE_INTEGER now;
    QueryPerformanceCounter(&now);
    if (g_perf_has_last_present) {
        float dt_ms = (float)((double)(now.QuadPart - g_perf_last_present_qpc.QuadPart) * g_perf_qpc_to_ms);
        if (g_bench_ft_ms && g_bench_ft_count < g_bench_ft_cap) {
            g_bench_ft_ms[g_bench_ft_count++] = dt_ms;
        }
        g_bench_match_frames++;
        g_bench_match_dip_sum += g_bench_frame_dip;
        g_bench_match_draws_sum += g_bench_frame_draws;

        if (g_bench_match_frames == 120 || g_bench_match_frames == 300 ||
            g_bench_match_frames == 480 || (g_bench_match_frames > 0 && (g_bench_match_frames % 300) == 0)) {
            perf_bench_dump("live_match");
        }
    }
    g_bench_frame_dip = 0;
    g_bench_frame_draws = 0;
    g_perf_last_present_qpc = now;
    g_perf_has_last_present = 1;
}

/* =========================================================================
 * Fast In-Memory I/O Redirect Hash Table (0 disk GetFileAttributesA syscalls!)
 * ========================================================================= */
#define PERF_IO_TABLE_BITS 12
#define PERF_IO_TABLE_SIZE (1u << PERF_IO_TABLE_BITS) /* 4096 slots */
#define PERF_IO_TABLE_MASK (PERF_IO_TABLE_SIZE - 1u)

typedef struct {
    uint32_t hash;
    char    *rel_lower; /* e.g. "high\\player\\model\\p_m_alc_ng.sdo" */
    char    *full_path; /* e.g. "c:\\...\\game\\archive\\HIGH\\Player\\Model\\P_M_ALC_NG.sdo" */
} PerfIoEntry;

static PerfIoEntry g_perf_io_table[PERF_IO_TABLE_SIZE];
static uint32_t    g_perf_io_count = 0;
static int         g_perf_io_ready = 0;

static inline uint32_t perf_fnv1a_lower(const char *s, char *out_lower, size_t out_sz) {
    uint32_t h = 2166136261u;
    size_t i = 0;
    while (*s && i + 1 < out_sz) {
        unsigned char c = (unsigned char)*s++;
        if (c == '/') c = '\\';
        if (c >= 'A' && c <= 'Z') c = (unsigned char)(c + ('a' - 'A'));
        out_lower[i++] = (char)c;
        h ^= (uint32_t)c;
        h *= 16777619u;
    }
    out_lower[i] = '\0';
    return h ? h : 1u;
}

static void perf_io_insert(const char *rel_path, const char *full_path) {
    if (g_perf_io_count >= (PERF_IO_TABLE_SIZE * 3) / 4) return;
    char lower[MAX_PATH];
    uint32_t h = perf_fnv1a_lower(rel_path, lower, sizeof(lower));
    uint32_t idx = h & PERF_IO_TABLE_MASK;
    for (uint32_t probe = 0; probe < PERF_IO_TABLE_SIZE; probe++) {
        PerfIoEntry *e = &g_perf_io_table[idx];
        if (!e->rel_lower) {
            e->hash = h;
            e->rel_lower = _strdup(lower);
            e->full_path = _strdup(full_path);
            g_perf_io_count++;
            return;
        }
        if (e->hash == h && strcmp(e->rel_lower, lower) == 0) {
            /* Keep first-inserted (game/archive/ has priority over game/<subdir>/) */
            return;
        }
        idx = (idx + 1u) & PERF_IO_TABLE_MASK;
    }
}

static void perf_io_scan_dir(const char *disk_dir, const char *rel_prefix) {
    char pattern[MAX_PATH * 2];
    snprintf(pattern, sizeof(pattern), "%s\\*", disk_dir);

    WIN32_FIND_DATAA fd;
    HANDLE hFind = FindFirstFileA(pattern, &fd);
    if (hFind == INVALID_HANDLE_VALUE) return;

    do {
        if (fd.cFileName[0] == '.' &&
            (fd.cFileName[1] == '\0' || (fd.cFileName[1] == '.' && fd.cFileName[2] == '\0'))) {
            continue;
        }
        char full[MAX_PATH * 2];
        char rel[MAX_PATH];
        snprintf(full, sizeof(full), "%s\\%s", disk_dir, fd.cFileName);
        if (rel_prefix && rel_prefix[0]) {
            snprintf(rel, sizeof(rel), "%s\\%s", rel_prefix, fd.cFileName);
        } else {
            snprintf(rel, sizeof(rel), "%s", fd.cFileName);
        }

        if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            perf_io_scan_dir(full, rel);
        } else {
            perf_io_insert(rel, full);
        }
    } while (FindNextFileA(hFind, &fd));

    FindClose(hFind);
}

static void perf_io_init(void) {
    if (g_perf_io_ready || !g_perf_fast_io || !g_game_dir[0]) return;
    LARGE_INTEGER t0, t1;
    QueryPerformanceCounter(&t0);

    /* 1. Index game/archive/ (highest priority) */
    char archive_dir[MAX_PATH * 2];
    snprintf(archive_dir, sizeof(archive_dir), "%s\\archive", g_game_dir);
    perf_io_scan_dir(archive_dir, "");

    /* 2. Index game/<subdir>/ for non-archive, non-save subdirs (matches legacy fallback) */
    char root_pat[MAX_PATH * 2];
    snprintf(root_pat, sizeof(root_pat), "%s\\*", g_game_dir);
    WIN32_FIND_DATAA fd;
    HANDLE hFind = FindFirstFileA(root_pat, &fd);
    if (hFind != INVALID_HANDLE_VALUE) {
        do {
            if (!(fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)) continue;
            if (fd.cFileName[0] == '.') continue;
            if (_stricmp(fd.cFileName, "archive") == 0 || _stricmp(fd.cFileName, "save") == 0) continue;
            char sub_full[MAX_PATH * 2];
            snprintf(sub_full, sizeof(sub_full), "%s\\%s", g_game_dir, fd.cFileName);
            perf_io_scan_dir(sub_full, fd.cFileName);
        } while (FindNextFileA(hFind, &fd));
        FindClose(hFind);
    }

    g_perf_io_ready = 1;
    QueryPerformanceCounter(&t1);
    double scan_ms = (double)(t1.QuadPart - t0.QuadPart) * g_perf_qpc_to_ms;
    log_msg("[VT4-Perf] Fast I/O cache indexed %u files in %.2f ms (0 runtime disk syscalls)",
            g_perf_io_count, scan_ms);
}

static inline int perf_io_lookup(const char *clean_rel, char *out_path, size_t out_size) {
    char lower[MAX_PATH];
    uint32_t h = perf_fnv1a_lower(clean_rel, lower, sizeof(lower));
    uint32_t idx = h & PERF_IO_TABLE_MASK;
    for (uint32_t probe = 0; probe < PERF_IO_TABLE_SIZE; probe++) {
        const PerfIoEntry *e = &g_perf_io_table[idx];
        if (!e->rel_lower) return 0;
        if (e->hash == h && strcmp(e->rel_lower, lower) == 0) {
            if (out_path && out_size > 0) {
                strncpy(out_path, e->full_path, out_size - 1);
                out_path[out_size - 1] = '\0';
            }
            return 1;
        }
        idx = (idx + 1u) & PERF_IO_TABLE_MASK;
    }
    return 0;
}

/* =========================================================================
 * Profile Config Loader & Pipeline Overrides
 * ========================================================================= */
static void perf_load_config(const char *ini_path) {
    perf_init_clock();
    g_cfg_perf_profile = GetPrivateProfileIntA("Performance", "PerfProfile", 0, ini_path);
    if (g_cfg_perf_profile > 2) g_cfg_perf_profile = 0;
    g_cfg_unlock_fps = GetPrivateProfileIntA("Performance", "UnlockFPS", 0, ini_path) ? 1u : 0u;
    g_cfg_target_fps = GetPrivateProfileIntA("Performance", "TargetFPS", 60, ini_path);
    if (g_cfg_target_fps < 30 || g_cfg_target_fps > 360) g_cfg_target_fps = 60;
    g_cfg_bench_log = GetPrivateProfileIntA("Performance", "BenchLog", 0, ini_path) ? 1u : 0u;

    char env_buf[32];
    if (GetEnvironmentVariableA("VT4_BENCH", env_buf, sizeof(env_buf)) > 0 && env_buf[0] == '1') {
        g_cfg_bench_log = 1;
    }
    if (GetEnvironmentVariableA("VT4_PERF_PROFILE", env_buf, sizeof(env_buf)) > 0) {
        uint32_t p = (uint32_t)atoi(env_buf);
        if (p <= 2) g_cfg_perf_profile = p;
    }
    if (GetEnvironmentVariableA("VT4_UNLOCK_FPS", env_buf, sizeof(env_buf)) > 0) {
        g_cfg_unlock_fps = (env_buf[0] == '1') ? 1u : 0u;
    }

    /* Apply profile-level graphics/pipeline overrides cleanly */
    if (g_cfg_perf_profile == 1) {
        /* High-FPS Esports: VSync OFF, CleanPostFX=1, cap MSAA<=2, Aniso<=8 */
        g_cfg_vsync = 0;
        g_cfg_clean_postfx = 1;
        if (g_cfg_antialiasing > 2) g_cfg_antialiasing = 2;
        if (g_cfg_anisotropic > 8)  g_cfg_anisotropic  = 8;
    } else if (g_cfg_perf_profile == 2) {
        /* Android / Low-Spec (Winlator/Box64/DXVK/Turnip): minimal fillrate & zero MSAA resolve */
        g_cfg_vsync = 0;
        g_cfg_antialiasing = 0;
        g_cfg_anisotropic = 0;
        g_cfg_clean_postfx = 1;
    }

    if (g_cfg_bench_log && !g_bench_ft_ms) {
        g_bench_ft_ms = (float *)malloc(sizeof(float) * g_bench_ft_cap);
    }

    perf_io_init();

    log_msg("[VT4-Perf] Config: PerfProfile=%u UnlockFPS=%u TargetFPS=%u BenchLog=%u FastIO=%u Pacer=%u (MSAA=%u Aniso=%u PostFX=%u)",
            g_cfg_perf_profile, g_cfg_unlock_fps, g_cfg_target_fps, g_cfg_bench_log,
            g_perf_fast_io, g_perf_pacer_active, g_cfg_antialiasing, g_cfg_anisotropic, g_cfg_clean_postfx);
}

static inline uint32_t perf_get_shadow_size(void) {
    if (g_cfg_perf_profile == 2) return 512u;
    if (g_cfg_perf_profile == 1) return 1024u;
    return 2048u;
}

static inline uint32_t perf_get_bloom_w(void) {
    if (g_cfg_perf_profile == 2) return 256u;
    if (g_cfg_perf_profile == 1) return 1024u;
    return (g_cfg_width >= 1920) ? 2048u : 1024u;
}

static inline uint32_t perf_get_bloom_h(void) {
    if (g_cfg_perf_profile == 2) return 128u;
    if (g_cfg_perf_profile == 1) return 512u;
    return (g_cfg_height >= 1080) ? 1024u : 512u;
}

static inline void perf_apply_engine_patches(void) {
    if (g_perf_pacer_active) {
        /* Bypass the 0x0040553e (je 0x405626, 6 bytes: 0F 84 E2 00 00 00) QPC busy-spin skip
         * so WinMain enters FrameStep once per frame and our hybrid QPC pacer controls exact
         * 60.000 FPS (1.000x physics speed) with near-0% idle CPU and zero 30 FPS VSync double-wait! */
        const uint8_t *p = (const uint8_t *)0x0040553e;
        if (p[0] == 0x0F && p[1] == 0x84) {
            patch_nops(0x0040553e, 6);
            log_msg("[VT4-Perf] Patched 0x0040553e (6 NOPs): eliminated QPC busy-spin & 30 FPS VSync double-wait");
        }
    }
}

#endif /* VT4_PERF_OPT_H */
