#include <windows.h>
#include <d3d9.h>
#include <stddef.h>
#include <stdio.h>

int main() {
    printf("DrawPrimitive idx: %d\n", (int)(offsetof(IDirect3DDevice9Vtbl, DrawPrimitive)/4));
    printf("DrawIndexedPrimitive idx: %d\n", (int)(offsetof(IDirect3DDevice9Vtbl, DrawIndexedPrimitive)/4));
    printf("SetRenderTarget idx: %d\n", (int)(offsetof(IDirect3DDevice9Vtbl, SetRenderTarget)/4));
    return 0;
}
