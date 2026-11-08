#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <d3d9.h>
#include <stdio.h>

int main(void) {
    printf("Starting D3D9 test...\n");
    HMODULE hD3D9 = LoadLibraryA("d3d9.dll");
    if (!hD3D9) {
        printf("Failed to load d3d9.dll: %lu\n", GetLastError());
        return 1;
    }

    typedef IDirect3D9 *(__stdcall *Direct3DCreate9_t)(UINT);
    Direct3DCreate9_t pD3DCreate9 = (Direct3DCreate9_t)GetProcAddress(hD3D9, "Direct3DCreate9");
    if (!pD3DCreate9) {
        printf("Failed to get Direct3DCreate9\n");
        return 1;
    }

    IDirect3D9 *d3d = pD3DCreate9(D3D_SDK_VERSION);
    if (!d3d) {
        printf("Direct3DCreate9 failed\n");
        return 1;
    }
    printf("Direct3DCreate9 OK: %p\n", d3d);

    D3DADAPTER_IDENTIFIER9 ident;
    if (SUCCEEDED(d3d->lpVtbl->GetAdapterIdentifier(d3d, D3DADAPTER_DEFAULT, 0, &ident))) {
        printf("Adapter 0: %s (Driver: %s)\n", ident.Description, ident.Driver);
    }

    D3DCAPS9 caps;
    HRESULT hr = d3d->lpVtbl->GetDeviceCaps(d3d, D3DADAPTER_DEFAULT, D3DDEVTYPE_HAL, &caps);
    printf("GetDeviceCaps(HAL): hr=%08lx, DevCaps=%08lx, DevType=%u\n", (unsigned long)hr, (unsigned long)caps.DevCaps, caps.DeviceType);

    D3DDISPLAYMODE mode;
    hr = d3d->lpVtbl->GetAdapterDisplayMode(d3d, D3DADAPTER_DEFAULT, &mode);
    printf("GetAdapterDisplayMode: hr=%08lx %ux%u fmt=%u refresh=%u\n", (unsigned long)hr, mode.Width, mode.Height, mode.Format, mode.RefreshRate);

    // Create a dummy window
    WNDCLASSA wc = {0};
    wc.lpfnWndProc = DefWindowProcA;
    wc.hInstance = GetModuleHandleA(NULL);
    wc.lpszClassName = "VT4TestWnd";
    RegisterClassA(&wc);
    HWND hwnd = CreateWindowA("VT4TestWnd", "Test", WS_OVERLAPPEDWINDOW, 100, 100, 1280, 720, NULL, NULL, wc.hInstance, NULL);
    printf("Created test window: %p\n", hwnd);

    // Test CheckDeviceType
    hr = d3d->lpVtbl->CheckDeviceType(d3d, D3DADAPTER_DEFAULT, D3DDEVTYPE_HAL, mode.Format, D3DFMT_X8R8G8B8, TRUE);
    printf("CheckDeviceType(HAL, disp=%u, bb=X8R8G8B8, win=1): hr=%08lx\n", mode.Format, (unsigned long)hr);

    hr = d3d->lpVtbl->CheckDeviceType(d3d, D3DADAPTER_DEFAULT, D3DDEVTYPE_HAL, mode.Format, D3DFMT_A8R8G8B8, TRUE);
    printf("CheckDeviceType(HAL, disp=%u, bb=A8R8G8B8, win=1): hr=%08lx\n", mode.Format, (unsigned long)hr);

    hr = d3d->lpVtbl->CheckDeviceType(d3d, D3DADAPTER_DEFAULT, D3DDEVTYPE_HAL, mode.Format, D3DFMT_UNKNOWN, TRUE);
    printf("CheckDeviceType(HAL, disp=%u, bb=UNKNOWN, win=1): hr=%08lx\n", mode.Format, (unsigned long)hr);

    // Try CreateDevice combinations
    D3DFORMAT fmts[] = { D3DFMT_UNKNOWN, D3DFMT_X8R8G8B8, D3DFMT_A8R8G8B8 };
    DWORD flags[] = {
        D3DCREATE_HARDWARE_VERTEXPROCESSING,
        D3DCREATE_HARDWARE_VERTEXPROCESSING | D3DCREATE_PUREDEVICE,
        D3DCREATE_SOFTWARE_VERTEXPROCESSING,
        D3DCREATE_MIXED_VERTEXPROCESSING
    };

    for (int f = 0; f < 3; f++) {
        for (int fl = 0; fl < 4; fl++) {
            D3DPRESENT_PARAMETERS pp = {0};
            pp.BackBufferWidth = 1280;
            pp.BackBufferHeight = 720;
            pp.BackBufferFormat = fmts[f];
            pp.BackBufferCount = 1;
            pp.MultiSampleType = D3DMULTISAMPLE_NONE;
            pp.SwapEffect = D3DSWAPEFFECT_DISCARD;
            pp.hDeviceWindow = hwnd;
            pp.Windowed = TRUE;
            pp.EnableAutoDepthStencil = FALSE;
            pp.Flags = 0;
            pp.FullScreen_RefreshRateInHz = 0;
            pp.PresentationInterval = D3DPRESENT_INTERVAL_DEFAULT;

            IDirect3DDevice9 *dev = NULL;
            hr = d3d->lpVtbl->CreateDevice(d3d, D3DADAPTER_DEFAULT, D3DDEVTYPE_HAL, hwnd, flags[fl], &pp, &dev);
            printf("CreateDevice(fmt=%u, flags=%08lx, pp.hDeviceWnd=%p, focus=%p) -> hr=%08lx dev=%p\n",
                   fmts[f], flags[fl], pp.hDeviceWindow, hwnd, (unsigned long)hr, dev);
            if (dev) {
                dev->lpVtbl->Release(dev);
                printf("--> SUCCESS! fmt=%u flags=%08lx\n", fmts[f], flags[fl]);
                DestroyWindow(hwnd);
                d3d->lpVtbl->Release(d3d);
                return 0;
            }
        }
    }

    DestroyWindow(hwnd);
    d3d->lpVtbl->Release(d3d);
    return 0;
}
