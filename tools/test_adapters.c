#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <d3d9.h>
#include <stdio.h>

int main(void) {
    HMODULE hD3D9 = LoadLibraryA("d3d9.dll");
    typedef IDirect3D9 *(__stdcall *Direct3DCreate9_t)(UINT);
    Direct3DCreate9_t pD3DCreate9 = (Direct3DCreate9_t)GetProcAddress(hD3D9, "Direct3DCreate9");
    IDirect3D9 *d3d = pD3DCreate9(D3D_SDK_VERSION);
    UINT count = d3d->lpVtbl->GetAdapterCount(d3d);
    printf("Adapter count: %u\n", count);

    for (UINT i = 0; i < count; i++) {
        D3DADAPTER_IDENTIFIER9 ident;
        d3d->lpVtbl->GetAdapterIdentifier(d3d, i, 0, &ident);
        printf("[%u] %s (Driver: %s, DeviceName: %s)\n", i, ident.Description, ident.Driver, ident.DeviceName);
        D3DCAPS9 caps;
        HRESULT hr = d3d->lpVtbl->GetDeviceCaps(d3d, i, D3DDEVTYPE_HAL, &caps);
        printf("    GetDeviceCaps(HAL): hr=%08lx\n", (unsigned long)hr);
        hr = d3d->lpVtbl->GetDeviceCaps(d3d, i, D3DDEVTYPE_REF, &caps);
        printf("    GetDeviceCaps(REF): hr=%08lx\n", (unsigned long)hr);
    }
    return 0;
}
