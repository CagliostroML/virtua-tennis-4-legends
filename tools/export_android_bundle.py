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
import zipfile

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
]

# Wine/Winlator handles SxS VC90 CRT and FAudio xaudio2_7 natively via its builtins;
# loose copies without a WinSxS activation context trigger R6034 or COM init hangs under Wine.
STALE_WINE_INCOMPAT_DLLS = (
    "msvcr90.dll",
    "msvcp90.dll",
    "msvcm90.dll",
    "XAudio2_7.dll",
)

OPTIONAL_RUNTIME_FILES = [
    "ui_arrow_left.png",
    "ui_arrow_right.png",
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
; Preset optimizado Android / Winlator / GameHub / Mobox (Vortek & Turnip + DXVK)
; 0=Auto: detecta la pantalla del contenedor y escala hasta 540p en PerfProfile=2 (ahorra ~44% GPU vs 720p)
Width=0
Height=0
Windowed=0
UseD3D9Ex=1
AntiAliasing=0
VSync=0
AnisotropicFiltering=0
CleanPostFX=1
NextGenFX=0
NextGenSharpen=0.15
NextGenFilmic=0

[Menu]
RemoveLiveMode=1
Locale=auto

[Gameplay]
ClassicTVCamera=0
MatchSpeedMode=0
ExhibitionRules=0
MultiverseMode=0
WeaponMode=0
BroadcastHUD=1
ProPhysics=0
; 0=Off (usa Virtual Gamepad nativo de Winlator), 1=Auto, 2=Siempre Visible [F6]
TouchXboxHUD=0

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
# Virtua Tennis 4: Legends & Next-Gen Edition — Android / DXVK (Vortek & Turnip) preset
d3d9.samplerAnisotropy = 0
d3d9.maxFrameLatency = 2
d3d9.presentInterval = 0
d3d9.deferSurfaceCreation = True
d3d9.supportDFFormats = False
dxvk.enableAsync = True
dxvk.enableGraphicsPipelineLibrary = True
dxvk.numCompilerThreads = 2
"""

LAUNCH_BAT_CONTENT = """\
@echo off
cd /d "%~dp0"
set WINEDLLOVERRIDES=xlive,d3dx9_43=n,b
VT4.exe
if errorlevel 1 (
    echo.
    echo [VT4-Android] VT4.exe exited with error code %errorlevel%.
    echo Check xlive_mod.log in this folder for details.
    pause
)
"""

LEEME_ANDROID_CONTENT = """\
======================================================================
  VIRTUA TENIS 4: LEGENDS & NEXT-GEN EDITION (84 Tenistas) — ANDROID
======================================================================

--- INICIO RAPIDO EN 3 PASOS ---
1) Copia esta carpeta entera (~3.6 GB) a una ruta corta de tu memoria interna:
   /storage/emulated/0/Games/VT4_Legends_Android/
2) En GameHub / Winlator, selecciona PLAY_VT4_LEGENDS.exe
   (compilado Win32 puro sin UCRT; fija xlive,d3dx9_43=n,b y deja a Wine
    usar su propio msvcr90/xaudio2_7 estable, ademas de generar launcher_android.log).
3) Pulsa Play: en Winlator abre Menu lateral -> Input Controls -> Virtual Gamepad
   (o usa mando Bluetooth/USB-C) para multitactil real con la pantalla limpia.
   El rendimiento movil PerfProfile=2 y pantalla completa se activan solos.

NOTA SOBRE .APK: No existe APK nativo ARM64 porque VT4.exe es un binario
x86 Win32 de SEGA parcheado en memoria por xlive.dll. Winlator / GameHub
lo ejecuta a 60 FPS gracias a Turnip + DXVK Async.

1. COPIA EN MEMORIA INTERNA
   Copia toda esta carpeta a una ruta corta de tu memoria interna, p.ej.:
   /storage/emulated/0/Games/VT4_Legends_Android/
   (En Winlator / GameHub, copia a C:\\Games\\VT4\\ o usa ruta directa corta).

2. LANZAMIENTO RAPIDO EN 1 TOQUE (PLAY_VT4_LEGENDS.exe)
   Esta carpeta incluye PLAY_VT4_LEGENDS.exe, un lanzador nativo Win32 que
   fija automaticamente WINEDLLOVERRIDES=xlive,d3dx9_43=n,b
   y ejecuta VT4.exe de forma sincrona para que GameHub/Winlator no cierren
   el contenedor antes de tiempo:
   - En GameHub (GameFusion): Import PC Game -> elige PLAY_VT4_LEGENDS.exe.
     GameHub creara la caratula/icono directo de 1 toque en tu biblioteca
     (y puedes anclar su acceso directo en la pantalla de inicio Android).
   - En Winlator (Oficial / CMod / Frost): abre el contenedor, haz clic derecho
     (toque con DOS DEDOS a la vez) sobre PLAY_VT4_LEGENDS.exe (lleva el icono
     escudo incrustado) -> Create Shortcut.
     * En Winlator Oficial lanzas en 1 toque desde Menu -> Shortcuts (el oficial
       solo muestra Settings/Copy/Cut/Remove, sin Add to Home Screen).
     * En Winlator CMod puedes pulsar tres puntos -> Add to Home Screen para
       anclarlo en tu escritorio de Android.
     * En Shortcuts -> tres puntos -> Settings puedes fijar Virtual Gamepad,
       resolucion 960x540 y Audio ALSA solo para este acceso directo.
     Tambien incluimos vt4_legends_icon.png y VT4_Legends_Winlator.desktop.
   - Si algo falla al abrir, revisa launcher_android.log y xlive_mod.log
     en esta carpeta (LAUNCH_ANDROID.bat tambien hara pause si falla).

3. AJUSTES RECOMENDADOS EN WINLATOR / GAMEHUB / MOBOX
   - Resolucion del contenedor: 960x540 (16:9) o 1280x576 (20:9 pantalla completa);
     vt4_settings.ini usa Width=0 / Height=0 (Auto) + PerfProfile=2.
   - Driver grafico: Turnip (Adreno) o Vortek (MediaTek / Mali / universal)
   - Wrapper DX: DXVK 1.10.3 o 2.x Async (PLAY_VT4_LEGENDS.exe activa
     DXVK_STATE_CACHE=1 para eliminar tirones al compilar shaders en el segundo partido)
   - Audio Driver: ALSA (recomendado en MediaTek/Mali) o PulseAudio (con
     PULSE_LATENCY_MSEC=90 automatico para evitar chasquidos)
   - Box64 Preset: Performance o Stability/Intermediate si notas tirones en Mali;
     marca solo los nucleos CPU grandes en CPU Affinity si tu movil tiene nucleos MIX.
   - DLL Overrides (automaticos al usar PLAY_VT4_LEGENDS.exe / LAUNCH_ANDROID.bat):
       WINEDLLOVERRIDES=xlive,d3dx9_43=n,b

4. CONTROLES EN PANTALLA EN WINLATOR / ANDROID
   - OPCION PRINCIPAL — VIRTUAL GAMEPAD NATIVO DE WINLATOR (RECOMENDADO):
     * Desliza desde el borde izquierdo (o pulsa Atras en Android) para abrir el
       menu lateral de Winlator -> Input Controls -> selecciona Virtual Gamepad.
     * Soporta multitactil real (mover con stick y pulsar A/B/X/Y a la vez).
     * Por defecto TouchXboxHUD=0 para dejar la pantalla limpia sin duplicar botones.
     * La proteccion anti-click-derecho/doble-toque evita que toques accidentales
       retrocedan en los menus.
   - OPCION ALTERNATIVA — OVERLAY XBOX INTEGRADO (TouchXboxHUD=0|1|2, tecla [F6]):
     * Si en alguna sesion prefieres probar nuestro overlay integrado, pulsa [F6]
       en cualquier momento o cambialo en OPCIONES -> GRAFICOS HD Y LEGENDS.

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


def _compile_launcher_icon_res(res_tmp_dir: str) -> str | None:
    """Build multi-size ICO + Win32 .res from vt4_legends_crest.png if Pillow + zig rc succeed."""
    crest_png = os.path.join(GAME_DIR, "archive", "vt4_legends_crest.png")
    if not os.path.isfile(crest_png):
        return None
    try:
        from PIL import Image
    except Exception:
        return None

    os.makedirs(res_tmp_dir, exist_ok=True)
    ico_path = os.path.join(res_tmp_dir, "vt4_legends.ico")
    rc_path = os.path.join(res_tmp_dir, "icon.rc")
    res_path = os.path.join(res_tmp_dir, "icon.res")
    try:
        with Image.open(crest_png) as img:
            rgba = img.convert("RGBA")
            rgba.save(
                ico_path,
                format="ICO",
                sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
            )
        with open(rc_path, "w", encoding="ascii") as f:
            f.write('1 ICON "vt4_legends.ico"\n')
        rc_cmd = [ZIG_EXE, "rc", "/fo", res_path, rc_path]
        r = subprocess.run(rc_cmd, cwd=res_tmp_dir, capture_output=True, text=True)
        if r.returncode == 0 and os.path.isfile(res_path):
            return res_path
    except Exception:
        return None
    return None


def _write_winlator_icon_and_desktop(out_dir: str) -> list[tuple[str, int]]:
    """Export 256x256 PNG crest icon and Winlator .desktop template into <out_dir>."""
    written: list[tuple[str, int]] = []
    crest_png = os.path.join(GAME_DIR, "archive", "vt4_legends_crest.png")
    icon_png_path = os.path.join(out_dir, "vt4_legends_icon.png")
    if os.path.isfile(crest_png):
        try:
            from PIL import Image

            with Image.open(crest_png) as img:
                img.convert("RGBA").resize((256, 256), Image.Resampling.LANCZOS).save(
                    icon_png_path, format="PNG", optimize=True
                )
        except Exception:
            shutil.copy2(crest_png, icon_png_path)
        written.append((icon_png_path, os.path.getsize(icon_png_path)))

    desktop_body = (
        "[Desktop Entry]\n"
        "Name=VT4 Legends & Next-Gen\n"
        "Exec=env WINEDLLOVERRIDES=\"xlive,d3dx9_43=n,b\" "
        "PULSE_LATENCY_MSEC=90 DXVK_STATE_CACHE=1 "
        "wine D:\\\\VT4_Legends_Android\\\\PLAY_VT4_LEGENDS.exe\n"
        "Path=D:\\\\VT4_Legends_Android\n"
        "Type=Application\n"
        "StartupNotify=true\n"
        "Icon=vt4_legends_icon\n"
    )
    desktop_path = os.path.join(out_dir, "VT4_Legends_Winlator.desktop")
    with open(desktop_path, "wb") as f:
        f.write(desktop_body.encode("utf-8"))
    written.append((desktop_path, os.path.getsize(desktop_path)))
    return written


def build_android_launcher(out_dir: str) -> tuple[str, int]:
    """Compile src/launcher/play_vt4_legends.c into <out_dir>/PLAY_VT4_LEGENDS.exe."""
    if not os.path.isfile(ZIG_EXE):
        raise FileNotFoundError(f"Zig compiler missing: {ZIG_EXE}")
    if not os.path.isfile(LAUNCHER_SRC):
        raise FileNotFoundError(f"Launcher source missing: {LAUNCHER_SRC}")

    dst_exe = os.path.join(out_dir, "PLAY_VT4_LEGENDS.exe")
    obj_path = os.path.join(out_dir, "play_vt4_legends.obj")
    res_tmp_dir = os.path.join(out_dir, "_icon_res_tmp")
    res_path = _compile_launcher_icon_res(res_tmp_dir)
    cmd_compile = [
        ZIG_EXE,
        "cc",
        "-target",
        "x86-windows-gnu",
        "-Os",
        "-fno-stack-protector",
        "-mno-stack-arg-probe",
        "-c",
        LAUNCHER_SRC,
        "-o",
        obj_path,
    ]
    res1 = subprocess.run(cmd_compile, cwd=REPO_ROOT, capture_output=True, text=True)
    if res1.returncode != 0 or not os.path.isfile(obj_path):
        shutil.rmtree(res_tmp_dir, ignore_errors=True)
        raise RuntimeError(
            f"Failed to compile play_vt4_legends.obj (rc={res1.returncode}):\n"
            f"{res1.stdout}\n{res1.stderr}"
        )

    link_inputs = [obj_path] + ([res_path] if res_path else [])
    cmd_link = [
        ZIG_EXE,
        "cc",
        "-target",
        "x86-windows-gnu",
        "-nostdlib",
        "-Wl,--subsystem,windows",
        "-Wl,-e,WinMainCRTStartup",
        *link_inputs,
        "-o",
        dst_exe,
        "-lkernel32",
        "-luser32",
    ]
    res2 = subprocess.run(cmd_link, cwd=REPO_ROOT, capture_output=True, text=True)
    if os.path.isfile(obj_path):
        os.remove(obj_path)
    shutil.rmtree(res_tmp_dir, ignore_errors=True)
    if res2.returncode != 0 or not os.path.isfile(dst_exe):
        raise RuntimeError(
            f"Failed to link PLAY_VT4_LEGENDS.exe (rc={res2.returncode}):\n"
            f"{res2.stdout}\n{res2.stderr}"
        )
    pdb_path = os.path.join(out_dir, "PLAY_VT4_LEGENDS.pdb")
    if os.path.isfile(pdb_path):
        os.remove(pdb_path)
    return dst_exe, os.path.getsize(dst_exe)


def create_android_zip(out_dir: str, patch_only: bool) -> str:
    parent = os.path.dirname(os.path.abspath(out_dir))
    suffix = "PatchOnly" if patch_only else "Full"
    zip_path = os.path.join(parent, f"VT4_Legends_Android_{suffix}.zip")
    stored_exts = {".bin", ".sdo", ".dds", ".png", ".zml", ".apz", ".ogg", ".mp3", ".wav"}
    skip_base = {x.lower() for x in CORE_BASE_FILES} if patch_only else set()
    root_name = os.path.basename(os.path.abspath(out_dir))
    with zipfile.ZipFile(zip_path, "w") as zf:
        for root, _ds, fs in os.walk(out_dir):
            for fn in sorted(fs):
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, out_dir).replace("\\", "/")
                if rel.lower() in skip_base:
                    continue
                arc = f"{root_name}/{rel}"
                ext = os.path.splitext(fn)[1].lower()
                if ext in stored_exts:
                    zf.write(full, arc, compress_type=zipfile.ZIP_STORED)
                else:
                    zf.write(full, arc, compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
    return zip_path


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

    # Remove stale loose VC90 CRT / XAudio2 DLLs if left over from an older export
    for stale in STALE_WINE_INCOMPAT_DLLS:
        stale_path = os.path.join(out_dir, stale)
        if os.path.isfile(stale_path):
            os.remove(stale_path)

    # 1. Core runtime binaries
    root_list = list(CORE_MOD_AND_CRT_FILES)
    if not patch_only:
        root_list = CORE_BASE_FILES + root_list

    for fn in root_list:
        src = os.path.join(GAME_DIR, fn)
        if not os.path.exists(src):
            raise FileNotFoundError(f"Required runtime file missing: {src}")
        copy_file(src, os.path.join(out_dir, fn))

    for fn in OPTIONAL_RUNTIME_FILES:
        src = os.path.join(GAME_DIR, fn)
        if os.path.isfile(src):
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

    # 4. Native Win32 1-tap launcher (PLAY_VT4_LEGENDS.exe with embedded crest icon) + shortcut assets
    launcher_path, launcher_bytes = build_android_launcher(out_dir)
    total_files += 1
    total_bytes += launcher_bytes
    for _extra_p, extra_sz in _write_winlator_icon_and_desktop(out_dir):
        total_files += 1
        total_bytes += extra_sz

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
    parser.add_argument("--zip", action="store_true", help="Also build a single transferable ZIP next to output dir")
    args = parser.parse_args()

    checked, mismatches = audit_archive_case_sensitivity()
    print(f"[Audit] Checked {checked} override files against VT4 archive index -> {len(mismatches)} case mismatches")
    for m in mismatches[:20]:
        print(" ", m)
    if mismatches:
        sys.exit(2)

    if args.verify_only:
        return

    abs_out = os.path.abspath(args.output)
    export_bundle(abs_out, args.patch_only, args.allow_missing_d3dx)
    if args.zip:
        zp = create_android_zip(abs_out, args.patch_only)
        print(f"  Transfer ZIP:   {zp} ({format_size(os.path.getsize(zp))})")


if __name__ == "__main__":
    main()
