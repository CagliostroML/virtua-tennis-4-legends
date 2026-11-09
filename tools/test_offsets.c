#include <windows.h>
#include <d3d9.h>
#include <stdio.h>
#include <stddef.h>

#define P(m) printf("%s: %d (0x%x)\n", #m, (int)(offsetof(IDirect3DDevice9Vtbl, m)/4), (int)(offsetof(IDirect3DDevice9Vtbl, m)))

int main() {
    P(Reset);
    P(Present);
    P(GetBackBuffer);
    P(CreateRenderTarget);
    P(CreateDepthStencilSurface);
    P(StretchRect);
    P(SetRenderTarget);
    P(GetRenderTarget);
    P(SetDepthStencilSurface);
    P(GetDepthStencilSurface);
    P(BeginScene);
    P(EndScene);
    P(Clear);
    P(SetTransform);
    P(SetViewport);
    P(GetViewport);
    P(SetRenderState);
    P(CreateStateBlock);
    P(SetTexture);
    P(SetSamplerState);
    P(SetFVF);
    P(DrawPrimitive);
    P(DrawIndexedPrimitive);
    P(DrawPrimitiveUP);
    P(DrawIndexedPrimitiveUP);
    return 0;
}
