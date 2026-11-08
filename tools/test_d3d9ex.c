#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <d3d9.h>
#include <stdio.h>

typedef HRESULT (__stdcall *Direct3DCreate9Ex_t)(UINT, IDirect3D9Ex **);

int main(void) {
    HMODULE hD3D9 = LoadLibraryA("d3d9.dll");
    Direct3DCreate9Ex_t pCreateEx = (Direct3DCreate9Ex_t)GetProcAddress(hD3D9, "Direct3DCreate9Ex");
    IDirect3D9Ex *d3dex = NULL;
    HRESULT hr = pCreateEx(D3D_SDK_VERSION, &d3dex);
    printf("Direct3DCreate9Ex: hr=%08lx d3dex=%p\n", (unsigned long)hr, d3dex);

    WNDCLASSA wc = {0};
    wc.lpfnWndProc = DefWindowProcA;
    wc.hInstance = GetModuleHandleA(NULL);
    wc.lpszClassName = "ExWnd";
    RegisterClassA(&wc);
    HWND hwnd = CreateWindowA("ExWnd", "ExTest", WS_OVERLAPPEDWINDOW, 100, 100, 1280, 720, NULL, NULL, wc.hInstance, NULL);

    D3DPRESENT_PARAMETERS pp = {0};
    pp.BackBufferWidth = 1280;
    pp.BackBufferHeight = 720;
    pp.BackBufferFormat = D3DFMT_X8R8G8B8;
    pp.BackBufferCount = 1;
    pp.SwapEffect = D3DSWAPEFFECT_DISCARD;
    pp.hDeviceWindow = hwnd;
    pp.Windowed = TRUE;
    pp.PresentationInterval = D3DPRESENT_INTERVAL_DEFAULT;

    IDirect3DDevice9 *dev = NULL;
    hr = d3dex->lpVtbl->CreateDevice(d3dex, D3DADAPTER_DEFAULT, D3DDEVTYPE_HAL, hwnd, D3DCREATE_HARDWARE_VERTEXPROCESSING, &pp, &dev);
    printf("d3dex->CreateDevice: hr=%08lx dev=%p\n", (unsigned long)hr, dev);

    if (dev) {
        printf("--> DEVICE CREATED SUCCESSFULLY WITH D3D9Ex!\n");
        dev->lpVtbl->Release(dev);
    }
    DestroyWindow(hwnd);
    d3dex->lpVtbl->Release(d3dex);
    return 0;
}
