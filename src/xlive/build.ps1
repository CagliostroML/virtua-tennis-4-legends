$ErrorActionPreference = 'Stop'
$root = 'c:\Users\acorr\Documents\tenis'
& "$root\tools\zig\zig.exe" cc -target x86-windows-gnu -shared -O2 `
    "$root\src\xlive\xlive.c" "$root\src\xlive\xlive.def" `
    -o "$root\game\xlive.dll" -lws2_32 -lgdi32 -luser32 -lkernel32
if ($LASTEXITCODE -ne 0) { throw "zig cc failed ($LASTEXITCODE)" }
Write-Host "xlive.dll built OK"
