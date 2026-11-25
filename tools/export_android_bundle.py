#!/usr/bin/env python3
"""
Turnkey Android (Winlator / GameHub / Mobox) Exporter for Virtua Tennis 4: Legends & Next-Gen Edition.

Builds a clean, standalone runtime bundle in dist/android/VT4_Legends_Android/ containing:
  - Whitelisted core binaries only (no .pdb, .lib, .msi, setup exe, or debug PNG/BMP/log files)
  - Auto-bundled d3dx9_43.dll (x86 SysWOW64) so Wine/DXVK never falls back or misses D3DX9
  - Clean game/archive/ tree (including loose mods, Scoreboard PNGs, EN LINEA UI, Voice Packs, EE-3)
  - Android-tuned vt4_settings.ini (1280x720, PerfProfile=2, MSAA=0, TouchXboxHUD=1 Auto, BroadcastHUD=1)
  - dxvk.conf + LAUNCH_ANDROID.bat + LEEME_ANDROID.txt + empty save/
  - Integrated case-sensitivity audit against resource.bin / resource.1.bin archive entries

Usage:
  python -u tools/export_android_bundle.py
  python -u tools/export_android_bundle.py --patch-only
  python -u tools/export_android_bundle.py --verify-only
"""
import argparse
import os
import shutil
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
GAME_DIR = os.path.join(REPO_ROOT, "game")
DEFAULT_OUT = os.path.join(REPO_ROOT, "dist", "android", "VT4_Legends_Android")
SYSWOW64_D3DX = r"C:\Windows\SysWOW64\d3dx9_43.dll"
ZIG_EXE = os.path.join(REPO_ROOT, "tools", "zig", "zig.exe")
LAUNCHER_SRC = os.path.join(REPO_ROOT, "src", "launcher", "play_vt4_legends.c")

sys.path.insert(0, SCRIPT_DIR)
import vt4_archive  # noqa: E402

CORE_BASE_FILES = [
    "VT4.exe",
    "VT4.exe.cfg",
    "VT4.exe.cat",
    "vt4.dll",
    "resource.bin",
    "resource.1.bin",
]

CORE_MOD_AND_CRT_FILES = [
    "xlive.dll",
    "msvcr90.dll",
    "msvcp90.dll",
    "msvcm90.dll",
]

# Top-level loose dirs inside game/archive/ added purely by xlive.dll mod systems (not in base archive)
MOD_ONLY_ARCHIVE_PREFIXES = (
    "hud/",
    "ee3/",
    "voices/",
    "opt_btn_",
    "vt4_legends_crest.png",
)

SKIP_ARCHIVE_SUFFIXES = (".bak", ".tmp", ".log", ".psd", ".pdb")
SKIP_ARCHIVE_NAMES = {".ds_store", "thumbs.db", "desktop.ini"}

ANDROID_INI_CONTENT = """\
[Graphics]
; Preset optimizado Android / Winlator / GameHub / Mobox (DXVK + Turnip/Vortek)
Width=1280
Height=720
Windowed=1
AntiAliasing=0
VSync=0
AnisotropicFiltering=0
CleanPostFX=1
NextGenFX=0
NextGenSharpen=0.15
NextGenFilmic=0

[Menu]
RemoveLiveMode=1

[Gameplay]
ClassicTVCamera=0
MatchSpeedMode=0
ExhibitionRules=0
MultiverseMode=0
WeaponMode=0
BroadcastHUD=1
ProPhysics=0
; 0=Off, 1=Auto (se activa automaticamente en Android/Wine), 2=Siempre Visible [F6]
TouchXboxHUD=1

[Performance]
; PerfProfile=2: sombras 512x512, bloom 256x128, 0 syscalls FUSE (cache I/O en RAM)
PerfProfile=2
UnlockFPS=0
TargetFPS=60

[Netplay]
; Crossplay P2P UDP PC <-> Android (EN LINEA -> Buscar Sala LAN o PeerIP de Tailscale)
Mode=0
PeerIP=127.0.0.1
Port=7777
LocalPort=0
DelayFrames=3

[Debug]
DebugLog=0
"""

DXVK_CONF_CONTENT = """\
# Virtua Tennis 4: Legends & Next-Gen Edition — Android / DXVK preset
d3d9.samplerAnisotropy = 0
d3d9.maxFrameLatency = 1
d3d9.presentInterval = 0
dxvk.enableAsync = True
dxvk.numCompilerThreads = 2
"""

LAUNCH_BAT_CONTENT = """\
@echo off
cd /d "%~dp0"
set WINEDLLOVERRIDES=xlive,d3dx9_43,msvcr90,msvcp90,msvcm90=n,b
VT4.exe
"""

LEEME_ANDROID_CONTENT = """\
======================================================================
  VIRTUA TENIS 4: LEGENDS & NEXT-GEN EDITION (84 Tenistas) — ANDROID
======================================================================

1. COPIA EN MEMORIA INTERNA
   Copia toda esta carpeta a una ruta corta de tu memoria interna, p.ej.:
   /storage/emulated/0/Download/VT4_Legends_Android/
   (En Winlator / GameHub, copia a C:\\Games\\VT4\\ o usa ruta directa corta).

2. LANZAMIENTO RAPIDO EN 1 TOQUE (PLAY_VT4_LEGENDS.exe)
   Esta carpeta incluye PLAY_VT4_LEGENDS.exe, un lanzador nativo Win32 que
   fija automaticamente WINEDLLOVERRIDES (xlive, d3dx9_43, CRT v90 = Native)
   y ejecuta VT4.exe de forma sincrona para que GameHub/Winlator no cierren
   el contenedor antes de tiempo:
   - En GameHub (GameFusion): Import PC Game -> elige PLAY_VT4_LEGENDS.exe.
     GameHub creara la caratula/icono directo de 1 toque en tu biblioteca
     (y puedes anclar su acceso directo en la pantalla de inicio Android).
   - En Winlator CMod / Frost: abre el contenedor, haz clic derecho sobre
     PLAY_VT4_LEGENDS.exe -> Create Shortcut; luego ve a Shortcuts en la app
     y pulsa el menu (tres puntos) -> Add to Home Screen para tener el icono
     directo de 1 toque en el escritorio de Android.
   - Si prefieres lanzar por script, LAUNCH_ANDROID.bat tambien ejecuta VT4.exe
     de forma sincrona con los mismos overrides.

3. AJUSTES RECOMENDADOS EN WINLATOR / GAMEHUB / MOBOX
   - Resolucion: 1280x720
   - Driver grafico: Turnip (Adreno) o Vortek / VirGL (Mali / Exynos)
   - Wrapper DX: DXVK 2.3+ / 2.4+ (Async)
   - Box64 Preset: Performance
   - Audio: PulseAudio (xaudio2_7=n recomendado)
   - DLL Overrides (automaticos al usar PLAY_VT4_LEGENDS.exe / LAUNCH_ANDROID.bat):
       WINEDLLOVERRIDES=xlive,d3dx9_43,msvcr90,msvcp90,msvcm90=n,b

4. MANDO XBOX TACTIL INTERACTIVO (RECOMP STYLE)
   - Con TouchXboxHUD=1 (Auto, activado por defecto aqui), al detectarse
     Wine/Android aparece automaticamente en pantalla un mando Xbox tactil
     con stick izquierdo analogico + A (Topspin/OK) / B (Globo/Atras) /
     X (Cortado) / Y (Dejada) + LB/RB (cambiar pagina del roster) + START.
   - Si usas mando fisico Bluetooth/USB-C, funciona en paralelo; puedes
     ocultarlo/mostrarlo en directo con [F6] o en OPCIONES -> GRAFICOS HD.

5. ONLINE P2P CROSSPLAY (PC <-> ANDROID)
   - Entra en EN LINEA desde el menu principal:
     * Si jugais en el mismo WiFi: 1 equipo pulsa CREAR SALA (HOST P1) y
       el otro pulsa BUSCAR SALA EN RED LOCAL (LAN) -> CONECTAR.
     * Si jugais por Internet: usad Tailscale (IP 100.x.x.x en IP DEL RIVAL).
   - Luego pulsad ESC y entrad ambos en EXHIBICION con el mismo partido y pista.
"""


def audit_archive_case_sensitivity() -> tuple[int, list[str]]:
    """Audit every loose file in game/archive against exact casing inside resource.bin / resource.1.bin."""
    entries = vt4_archive.load_directory()
    exact_names = {e["name"] for e in entries}
    lower_to_exact = {e["name"].lower(): e["name"] for e in entries}

    archive_root = os.path.join(GAME_DIR, "archive")
    checked = 0
    mismatches = []
    for root, _ds, fs in os.walk(archive_root):
        for fn in fs:
            low_fn = fn.lower()
            if low_fn in SKIP_ARCHIVE_NAMES or any(low_fn.endswith(ext) for ext in SKIP_ARCHIVE_SUFFIXES):
                continue
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, archive_root).replace("\\", "/")
            if any(rel.lower().startswith(p) for p in MOD_ONLY_ARCHIVE_PREFIXES):
                continue
            checked += 1
            if rel in exact_names:
                continue
            exp = lower_to_exact.get(rel.lower())
            if exp and exp != rel:
                mismatches.append(f"CASE MISMATCH: disk='{rel}' archive='{exp}'")
    return checked, mismatches


def should_skip_archive_file(rel_posix: str, fn: str) -> bool:
    low_fn = fn.lower()
    if low_fn in SKIP_ARCHIVE_NAMES or any(low_fn.endswith(s) for s in SKIP_ARCHIVE_SUFFIXES):
        return True
    if "_tmp." in low_fn:
        return True
    return False


def format_size(num_bytes: int) -> str:
    if num_bytes >= 1024 ** 3:
        return f"{num_bytes / (1024 ** 3):.2f} GB"
    if num_bytes >= 1024 ** 2:
        return f"{num_bytes / (1024 ** 2):.2f} MB"
    return f"{num_bytes / 1024.0:.1f} KB"


def build_android_launcher(out_dir: str) -> tuple[str, int]:
    """Compile src/launcher/play_vt4_legends.c into <out_dir>/PLAY_VT4_LEGENDS.exe."""
    if not os.path.isfile(ZIG_EXE):
        raise FileNotFoundError(f"Zig compiler missing: {ZIG_EXE}")
    if not os.path.isfile(LAUNCHER_SRC):
        raise FileNotFoundError(f"Launcher source missing: {LAUNCHER_SRC}")

    dst_exe = os.path.join(out_dir, "PLAY_VT4_LEGENDS.exe")
    cmd = [
        ZIG_EXE,
        "cc",
        "-target",
        "x86-windows-gnu",
        "-O2",
        "-Wl,--subsystem,windows",
        LAUNCHER_SRC,
        "-o",
        dst_exe,
        "-luser32",
        "-lkernel32",
    ]
    res = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    if res.returncode != 0 or not os.path.isfile(dst_exe):
        raise RuntimeError(
            f"Failed to compile PLAY_VT4_LEGENDS.exe (rc={res.returncode}):\n"
            f"{res.stdout}\n{res.stderr}"
        )
    return dst_exe, os.path.getsize(dst_exe)


def export_bundle(out_dir: str, patch_only: bool, allow_missing_d3dx: bool) -> None:
    os.makedirs(out_dir, exist_ok=True)
    total_files = 0
    total_bytes = 0

    def copy_file(src: str, dst: str) -> None:
        nonlocal total_files, total_bytes
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        total_files += 1
        total_bytes += os.path.getsize(dst)

    # 1. Core runtime binaries
    root_list = list(CORE_MOD_AND_CRT_FILES)
    if not patch_only:
        root_list = CORE_BASE_FILES + root_list

    for fn in root_list:
        src = os.path.join(GAME_DIR, fn)
        if not os.path.exists(src):
            raise FileNotFoundError(f"Required runtime file missing: {src}")
        copy_file(src, os.path.join(out_dir, fn))

    # 2. Auto-bundle d3dx9_43.dll from Windows SysWOW64 so Wine/Android always has native D3DX9
    if os.path.exists(SYSWOW64_D3DX):
        copy_file(SYSWOW64_D3DX, os.path.join(out_dir, "d3dx9_43.dll"))
        d3dx_status = "BUNDLED (SysWOW64)"
    elif os.path.exists(os.path.join(GAME_DIR, "d3dx9_43.dll")):
        copy_file(os.path.join(GAME_DIR, "d3dx9_43.dll"), os.path.join(out_dir, "d3dx9_43.dll"))
        d3dx_status = "BUNDLED (game/)"
    else:
        if not allow_missing_d3dx:
            raise FileNotFoundError(f"d3dx9_43.dll not found at {SYSWOW64_D3DX}")
        d3dx_status = "MISSING (warned)"

    # 3. Copy clean game/archive tree
    src_arch = os.path.join(GAME_DIR, "archive")
    dst_arch = os.path.join(out_dir, "archive")
    if os.path.exists(dst_arch):
        shutil.rmtree(dst_arch)
    os.makedirs(dst_arch, exist_ok=True)

    skipped_files = 0
    for root, _ds, fs in os.walk(src_arch):
        for fn in fs:
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, src_arch)
            rel_posix = rel.replace("\\", "/")
            if should_skip_archive_file(rel_posix, fn):
                skipped_files += 1
                continue
            copy_file(full, os.path.join(dst_arch, rel))

    # 4. Native Win32 1-tap launcher (PLAY_VT4_LEGENDS.exe)
    launcher_path, launcher_bytes = build_android_launcher(out_dir)
    total_files += 1
    total_bytes += launcher_bytes

    # 5. Portable empty save directory + Android config / launcher files
    save_dir = os.path.join(out_dir, "save")
    os.makedirs(save_dir, exist_ok=True)

    text_outputs = {
        "vt4_settings.ini": ANDROID_INI_CONTENT,
        "dxvk.conf": DXVK_CONF_CONTENT,
        "LAUNCH_ANDROID.bat": LAUNCH_BAT_CONTENT,
        "LEEME_ANDROID.txt": LEEME_ANDROID_CONTENT,
    }
    for name, body in text_outputs.items():
        p = os.path.join(out_dir, name)
        with open(p, "wb") as f:
            f.write(body.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))
        total_files += 1
        total_bytes += os.path.getsize(p)

    print("=== Android Bundle Export Summary ===")
    print(f"  Output:         {out_dir}")
    print(f"  Mode:           {'patch-only' if patch_only else 'full turnkey standalone'}")
    print(f"  Launcher:       {os.path.basename(launcher_path)} ({format_size(launcher_bytes)})")
    print(f"  d3dx9_43.dll:   {d3dx_status}")
    print(f"  Exported files: {total_files} (skipped junk: {skipped_files})")
    print(f"  Total size:     {format_size(total_bytes)} ({total_bytes:,} bytes)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export clean VT4 Legends Android/Winlator bundle.")
    parser.add_argument("--output", default=DEFAULT_OUT, help="Destination directory for bundle")
    parser.add_argument("--patch-only", action="store_true", help="Skip VT4.exe and resource*.bin")
    parser.add_argument("--verify-only", action="store_true", help="Only run archive case-sensitivity audit")
    parser.add_argument("--allow-missing-d3dx", action="store_true", help="Warn instead of failing if d3dx9_43.dll missing")
    args = parser.parse_args()

    checked, mismatches = audit_archive_case_sensitivity()
    print(f"[Audit] Checked {checked} override files against VT4 archive index -> {len(mismatches)} case mismatches")
    for m in mismatches[:20]:
        print(" ", m)
    if mismatches:
        sys.exit(2)

    if args.verify_only:
        return

    export_bundle(os.path.abspath(args.output), args.patch_only, args.allow_missing_d3dx)


if __name__ == "__main__":
    main()
