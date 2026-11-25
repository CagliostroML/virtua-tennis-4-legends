#define WIN32_LEAN_AND_MEAN
#include <windows.h>

static int build_dir_from_exe(char *out_dir, DWORD cap) {
    DWORD len = GetModuleFileNameA(NULL, out_dir, cap);
    if (len == 0 || len >= cap) {
        return 0;
    }
    for (DWORD i = len; i > 0; --i) {
        if (out_dir[i - 1] == '\\' || out_dir[i - 1] == '/') {
            out_dir[i - 1] = '\0';
            return 1;
        }
    }
    return 0;
}

int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow) {
    char dir[MAX_PATH];
    char exe_path[MAX_PATH + 32];
    char err_msg[MAX_PATH + 128];
    STARTUPINFOA si;
    PROCESS_INFORMATION pi;
    DWORD exit_code = 0;

    (void)hInstance;
    (void)hPrevInstance;
    (void)lpCmdLine;
    (void)nCmdShow;

    if (!build_dir_from_exe(dir, MAX_PATH)) {
        MessageBoxA(
            NULL,
            "No se pudo determinar la carpeta de PLAY_VT4_LEGENDS.exe.",
            "VT4: Legends & Next-Gen",
            MB_OK | MB_ICONERROR
        );
        return 1;
    }

    SetCurrentDirectoryA(dir);
    SetEnvironmentVariableA("WINEDLLOVERRIDES", "xlive,d3dx9_43,msvcr90,msvcp90,msvcm90=n,b");

    wsprintfA(exe_path, "%s\\VT4.exe", dir);

    ZeroMemory(&si, sizeof(si));
    si.cb = sizeof(si);
    ZeroMemory(&pi, sizeof(pi));

    if (!CreateProcessA(
            exe_path,
            NULL,
            NULL,
            NULL,
            FALSE,
            0,
            NULL,
            dir,
            &si,
            &pi)) {
        DWORD err = GetLastError();
        wsprintfA(
            err_msg,
            "No se pudo iniciar VT4.exe:\n%s\n\nCodigo de error Win32: %lu",
            exe_path,
            (unsigned long)err
        );
        MessageBoxA(NULL, err_msg, "VT4: Legends & Next-Gen", MB_OK | MB_ICONERROR);
        return 1;
    }

    WaitForSingleObject(pi.hProcess, INFINITE);
    if (!GetExitCodeProcess(pi.hProcess, &exit_code)) {
        exit_code = 0;
    }
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    return (int)exit_code;
}
