#!/usr/bin/env python3
"""Package VT4 Legends & Next-Gen Edition v1.0.1 release ZIPs safely."""

from __future__ import annotations

import hashlib
import os
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAME_DIR = ROOT / "game"
ANDROID_DIR = ROOT / "dist" / "android" / "VT4_Legends_Android"
OUT_DIR = ROOT / "dist" / "release"

VERSION = "v1.0.1"
PC_ZIP_NAME = f"VT4_Legends-{VERSION}-Windows-x86.zip"
ANDROID_ZIP_NAME = f"VT4_Legends-{VERSION}-Android-Launcher.zip"

FORBIDDEN_EXACT = {
    "vt4.exe",
    "vt4.dll",
    "resource.bin",
    "resource.1.bin",
    "launcher.exe",
    "launcherdll.dll",
    "xaudio2_7.dll",
    "msvcr90.dll",
    "msvcp90.dll",
    "msvcm90.dll",
    "gfwlivesetup.exe",
}
FORBIDDEN_EXTS = {".sdo", ".dds", ".zml", ".apz", ".bin"}

DEFAULT_VT4_SETTINGS_INI = """\
[Graphics]
; Resolucion: 1920x1080 (Full HD), 2560x1440 (2K QHD), 3840x2160 (4K UHD), 1280x720 (HD)
Width=1920
Height=1080
; Modo Ventana: 0 = Pantalla Completa sin bordes (Borderless), 1 = Modo Ventana
Windowed=0
; Direct3D9Ex (reduce latencia y evita flicker en Alt-Tab; 0 = D3D9 estandar para GPUs antiguas/Winlator)
UseD3D9Ex=1
; Suavizado de bordes Anti-Aliasing (MSAA): 0 = Desactivado, 2 = 2x, 4 = 4x, 8 = 8x
AntiAliasing=4
; Sincronizacion Vertical: 1 = Activado (60 FPS estables sin cortes), 0 = Desactivado
VSync=1
; Filtrado Anisotropico para texturas de pista ultra nitidas: 16 = Ultra Nitido, 0 = Normal
AnisotropicFiltering=16
; Nitidez PostFX (EXTRA-6): 0 = Bloom+Blur Original, 1 = Ultra Nitido (Sin Bloom/Blur), 2 = Suave 35%
CleanPostFX=1
; Motor Next-Gen DirectX 9 (CAS Sharpening + ACES Filmic + Micro-Clarity, Tecla F8 en vivo): 1 = ON, 0 = OFF
NextGenFX=1
NextGenSharpen=0.22
NextGenFilmic=1

[Menu]
; Quitar el modo LIVE / Red (servidor GFWL inactivo) del menu principal
RemoveLiveMode=1
; Idioma del juego: auto (SO), en, es, fr, de, it, ja
Locale=auto

[Gameplay]
; Fijar Camara TV Clasica (estilo VT2, desactiva zooms de Super Golpe): 0 = Normal, 1 = Activo
ClassicTVCamera=0
; Velocidad de Fisica en Partido: 0 = Normal (1.00x), 1 = VT2 Arcade Turbo (1.20x), 2 = VT2 Hyper (1.35x), 3 = Simulacion Pro (0.90x), 4 = Ritmo Relajado (0.85x)
MatchSpeedMode=0
; Multiverso Arcade (Fase 3): 0 = Off, 1 = EE-2 Batalla Hielo/Barro, 2 = EE-4 Super Golpes 300%, 3 = Ambos
MultiverseMode=0
; Arma Arcade (EE-3): 0 = Normal, 1 = Raqueta Madera 70s, 2 = Sarten Metalica, 3 = Baguette Gigante
WeaponMode=0
; HUD TV Retransmision (Tecla F7 en partido): 1 = Activo, 0 = Desactivado
BroadcastHUD=1
; Fisicas Pro de Bola: 0 = Estandar VT4, 1 = Simulacion Pro (menos flotante)
ProPhysics=0
; Mando Xbox Tactil en Pantalla (Tecla F6): 0 = Off, 1 = Auto (Android/Wine), 2 = Siempre Visible
TouchXboxHUD=0

[Performance]
; Perfil de rendimiento: 0 = Ultra PC (Default), 1 = Esports (Baja Latencia), 2 = Android/Winlator Low-Spec
PerfProfile=0
; Desbloquear FPS (solo benchmark/turbo; 0 = 60 FPS exactos velocidad 1.00x, 1 = Sin limite)
UnlockFPS=0
TargetFPS=60

[Netplay]
; Online P2P UDP (Crossplay PC <-> Android): Mode 0=OFF, 1=HOST(P1), 2=CLIENT(P2)
Mode=0
PeerIP=127.0.0.1
Port=7777
LocalPort=0
DelayFrames=3
"""


def assert_safe_entry(arcname: str, *, allow_mod_launcher_exe: bool = False) -> None:
    norm = arcname.replace("\\", "/").strip("/")
    base = os.path.basename(norm).lower()
    ext = os.path.splitext(base)[1].lower()
    if base in FORBIDDEN_EXACT:
        raise RuntimeError(f"FORBIDDEN SEGA/runtime binary in archive: {norm}")
    if ext in FORBIDDEN_EXTS:
        raise RuntimeError(f"FORBIDDEN SEGA asset extension in archive: {norm}")
    if ext == ".exe":
        if not (allow_mod_launcher_exe and base == "play_vt4_legends.exe"):
            raise RuntimeError(f"Unexpected .exe inside archive '{norm}' (allow_mod_launcher_exe={allow_mod_launcher_exe})")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build_pc_core_zip(out_path: Path) -> int:
    files: list[tuple[Path, str]] = [
        (GAME_DIR / "xlive.dll", "xlive.dll"),
        (ANDROID_DIR / "dxvk.conf", "dxvk.conf"),
        (GAME_DIR / "ui_arrow_left.png", "ui_arrow_left.png"),
        (GAME_DIR / "ui_arrow_right.png", "ui_arrow_right.png"),
        (GAME_DIR / "archive" / "vt4_legends_crest.png", "archive/vt4_legends_crest.png"),
        (GAME_DIR / "archive" / "opt_btn_sel.png", "archive/opt_btn_sel.png"),
        (GAME_DIR / "archive" / "opt_btn_unsel.png", "archive/opt_btn_unsel.png"),
        (ROOT / "recomplauncher.json", "recomplauncher.json"),
        (ROOT / "tools" / "vt4_recomp_prepare.bat", "vt4_recomp_prepare.bat"),
        (ROOT / "tools" / "launch_linux.sh", "launch_linux.sh"),
        (ROOT / "LINUX_STEAMDECK_GUIDE.md", "LINUX_STEAMDECK_GUIDE.md"),
        (ROOT / "README.md", "README.md"),
        (ROOT / "README.es.md", "README.es.md"),
        (ROOT / "ONLINE_NETPLAY_GUIDE.md", "ONLINE_NETPLAY_GUIDE.md"),
        (ROOT / f"RELEASE_NOTES_{VERSION}.md", f"RELEASE_NOTES_{VERSION}.md"),
    ]

    for subdir in ("netplay", "scoreboards"):
        src_dir = GAME_DIR / "archive" / "hud" / subdir
        if not src_dir.is_dir():
            raise FileNotFoundError(f"Missing HUD asset dir: {src_dir}")
        for p in sorted(src_dir.glob("*.png")):
            files.append((p, f"archive/hud/{subdir}/{p.name}"))

    count = 0
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for src, arc in files:
            if not src.is_file():
                raise FileNotFoundError(f"Missing required release file: {src}")
            assert_safe_entry(arc, allow_mod_launcher_exe=False)
            if arc == "launch_linux.sh":
                info = zipfile.ZipInfo("launch_linux.sh")
                info.create_system = 3
                info.external_attr = 0o100755 << 16
                zf.writestr(info, src.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
            else:
                zf.write(src, arc)
            count += 1

        assert_safe_entry("vt4_settings.ini", allow_mod_launcher_exe=False)
        zf.writestr("vt4_settings.ini", DEFAULT_VT4_SETTINGS_INI.encode("utf-8"))
        count += 1
    return count


def build_android_launcher_zip(out_path: Path) -> int:
    files: list[tuple[Path, str]] = [
        (ANDROID_DIR / "PLAY_VT4_LEGENDS.exe", "PLAY_VT4_LEGENDS.exe"),
        (ANDROID_DIR / "dxvk.conf", "dxvk.conf"),
        (ROOT / "ANDROID_SETUP_GUIDE.md", "ANDROID_SETUP_GUIDE.md"),
        (ROOT / f"RELEASE_NOTES_{VERSION}.md", f"RELEASE_NOTES_{VERSION}.md"),
    ]
    bat = ANDROID_DIR / "LAUNCH_ANDROID.bat"
    if bat.is_file():
        files.append((bat, "LAUNCH_ANDROID.bat"))
    for extra_name in ("vt4_legends_icon.png", "VT4_Legends_Winlator.desktop"):
        extra_p = ANDROID_DIR / extra_name
        if extra_p.is_file():
            files.append((extra_p, extra_name))

    count = 0
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for src, arc in files:
            if not src.is_file():
                raise FileNotFoundError(f"Missing required Android launcher file: {src}")
            assert_safe_entry(arc, allow_mod_launcher_exe=True)
            zf.write(src, arc)
            count += 1
    return count


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old_zip in OUT_DIR.glob(f"VT4_Legends*{VERSION}*.zip"):
        old_zip.unlink()
    pc_zip = OUT_DIR / PC_ZIP_NAME
    and_zip = OUT_DIR / ANDROID_ZIP_NAME
    sums_txt = OUT_DIR / "SHA256SUMS.txt"

    pc_count = build_pc_core_zip(pc_zip)
    and_count = build_android_launcher_zip(and_zip)

    # Final post-write safety verification on ZIP headers
    with zipfile.ZipFile(pc_zip, "r") as zf:
        for info in zf.infolist():
            assert_safe_entry(info.filename, allow_mod_launcher_exe=False)
    with zipfile.ZipFile(and_zip, "r") as zf:
        for info in zf.infolist():
            assert_safe_entry(info.filename, allow_mod_launcher_exe=True)

    pc_sha = sha256_file(pc_zip)
    and_sha = sha256_file(and_zip)
    sums_txt.write_text(f"{pc_sha}  {PC_ZIP_NAME}\n{and_sha}  {ANDROID_ZIP_NAME}\n", encoding="utf-8")

    print(f"Created {pc_zip} ({pc_count} files, {pc_zip.stat().st_size:,} bytes) sha256={pc_sha}")
    print(f"Created {and_zip} ({and_count} files, {and_zip.stat().st_size:,} bytes) sha256={and_sha}")
    print(f"Wrote {sums_txt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
