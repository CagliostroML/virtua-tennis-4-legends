#define WIN32_LEAN_AND_MEAN
#include <windows.h>

static void zero_mem(void *ptr, DWORD size) {
    volatile unsigned char *p = (volatile unsigned char *)ptr;
    for (DWORD i = 0; i < size; ++i) {
        p[i] = 0;
    }
}

static DWORD str_len(const char *s) {
    DWORD n = 0;
    while (s && s[n]) ++n;
    return n;
}

static void log_write(HANDLE hLog, const char *msg) {
    if (hLog != INVALID_HANDLE_VALUE && msg) {
        DWORD written = 0;
        WriteFile(hLog, msg, str_len(msg), &written, NULL);
        FlushFileBuffers(hLog);
    }
}

static int build_dir_from_exe(char *out_dir, DWORD cap) {
    DWORD len = GetModuleFileNameA(NULL, out_dir, cap);
    if (len == 0 || len >= cap) return 0;
    for (DWORD i = len; i > 0; --i) {
        if (out_dir[i - 1] == '\\' || out_dir[i - 1] == '/') {
            out_dir[i - 1] = '\0';
            return 1;
        }
    }
    return 0;
}

static void set_env_if_unset(const char *k, const char *v) {
    char tmp[8];
    if (GetEnvironmentVariableA(k, tmp, sizeof(tmp)) == 0) {
        SetEnvironmentVariableA(k, v);
    }
}

/* Satisfy Zig's MinGW COFF linker when linking without CRT startup objects */
int _tls_index = 0;

void WinMainCRTStartup(void) {
    char dir[MAX_PATH];
    char path_buf[MAX_PATH + 64];
    char log_buf[512];
    HANDLE hLog = INVALID_HANDLE_VALUE;
    STARTUPINFOA si;
    PROCESS_INFORMATION pi;
    DWORD exit_code = 0;

    if (!build_dir_from_exe(dir, MAX_PATH)) {
        MessageBoxA(
            NULL,
            "Could not resolve PLAY_VT4_LEGENDS.exe directory.",
            "VT4: Legends & Next-Gen",
            MB_OK | MB_ICONERROR
        );
        ExitProcess(1);
    }

    SetCurrentDirectoryA(dir);
    wsprintfA(path_buf, "%s\\launcher_android.log", dir);
    hLog = CreateFileA(path_buf, GENERIC_WRITE, FILE_SHARE_READ, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);

    wsprintfA(log_buf, "[VT4-Launcher] Started in: %s\r\n", dir);
    log_write(hLog, log_buf);

    /* Pre-flight file check so missing/incomplete copies report clearly instead of failing silently */
    static const char *const k_req[5] = {
        "VT4.exe",
        "vt4.dll",
        "resource.bin",
        "resource.1.bin",
        "xlive.dll"
    };
    for (int i = 0; i < 5; ++i) {
        wsprintfA(path_buf, "%s\\%s", dir, k_req[i]);
        if (GetFileAttributesA(path_buf) == INVALID_FILE_ATTRIBUTES) {
            wsprintfA(log_buf, "[VT4-Launcher] ERROR: Missing required file: %s\r\n", path_buf);
            log_write(hLog, log_buf);
            if (hLog != INVALID_HANDLE_VALUE) CloseHandle(hLog);
            wsprintfA(
                log_buf,
                "Falta un archivo necesario para iniciar:\n%s\n\n"
                "Copia la carpeta completa VT4_Legends_Android (~3.6 GB), no solo el lanzador.",
                path_buf
            );
            MessageBoxA(NULL, log_buf, "VT4: Legends & Next-Gen", MB_OK | MB_ICONERROR);
            ExitProcess(2);
        }
    }

    /* Let Wine/Winlator/Proton use its SxS-safe builtins for msvcr90/p90/m90 and FAudio xaudio2_7 */
    SetEnvironmentVariableA("WINEDLLOVERRIDES", "xlive,d3dx9_43=n,b");
    /* Mobile stability defaults (only if container env didn't override them): */
    set_env_if_unset("PULSE_LATENCY_MSEC", "90");
    set_env_if_unset("DXVK_STATE_CACHE", "1");
    set_env_if_unset("DXVK_STATE_CACHE_PATH", dir);
    log_write(hLog, "[VT4-Launcher] WINEDLLOVERRIDES=xlive,d3dx9_43=n,b PULSE_LATENCY_MSEC=90 DXVK_STATE_CACHE=1\r\n");

    wsprintfA(path_buf, "%s\\VT4.exe", dir);
    zero_mem(&si, sizeof(si));
    si.cb = sizeof(si);
    zero_mem(&pi, sizeof(pi));

    DWORD t0 = GetTickCount();
    if (!CreateProcessA(path_buf, NULL, NULL, NULL, FALSE, 0, NULL, dir, &si, &pi)) {
        DWORD err = GetLastError();
        wsprintfA(log_buf, "[VT4-Launcher] ERROR: CreateProcessA(VT4.exe) failed err=%lu\r\n", (unsigned long)err);
        log_write(hLog, log_buf);
        if (hLog != INVALID_HANDLE_VALUE) CloseHandle(hLog);
        wsprintfA(
            log_buf,
            "No se pudo iniciar VT4.exe:\n%s\n\nCodigo Win32: %lu (revisa launcher_android.log).",
            path_buf,
            (unsigned long)err
        );
        MessageBoxA(NULL, log_buf, "VT4: Legends & Next-Gen", MB_OK | MB_ICONERROR);
        ExitProcess(1);
    }

    wsprintfA(log_buf, "[VT4-Launcher] Launched VT4.exe (pid=%lu), waiting...\r\n", (unsigned long)pi.dwProcessId);
    log_write(hLog, log_buf);

    WaitForSingleObject(pi.hProcess, INFINITE);
    DWORD elapsed_ms = GetTickCount() - t0;
    if (!GetExitCodeProcess(pi.hProcess, &exit_code)) {
        exit_code = 0;
    }
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);

    wsprintfA(log_buf, "[VT4-Launcher] VT4.exe exited: code=0x%08lX (%lu) after %lu ms\r\n",
              (unsigned long)exit_code, (unsigned long)exit_code, (unsigned long)elapsed_ms);
    log_write(hLog, log_buf);
    if (hLog != INVALID_HANDLE_VALUE) CloseHandle(hLog);

    if (exit_code != 0 && elapsed_ms < 5000) {
        wsprintfA(
            log_buf,
            "VT4.exe se cerro enseguida (%lu ms) con codigo 0x%08lX.\n\n"
            "Revisa xlive_mod.log y launcher_android.log en esta misma carpeta.\n"
            "En Winlator, prueba DX Wrapper=DXVK (o WineD3D) y Graphics Driver adecuado para tu GPU.",
            (unsigned long)elapsed_ms,
            (unsigned long)exit_code
        );
        MessageBoxA(NULL, log_buf, "VT4: Legends & Next-Gen", MB_OK | MB_ICONWARNING);
    }

    ExitProcess((UINT)exit_code);
}
