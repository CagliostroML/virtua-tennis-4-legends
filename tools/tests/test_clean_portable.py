#!/usr/bin/env python3
"""External clean-directory portability test for VT4 Legends v1.0.1.

Tests outside the git workspace under %LOCALAPPDATA%\\Temp\\VT4_CleanTest:
  - Test A (Safe Core Mode): vanilla base + v1.0.1 PC_Core ZIP contents, NO save/,
    NO vt4_settings.ini, NO custom .sdo/.dds pack. Verifies portable path resolution,
    auto-creation of save\\Config.txt (UTF-16LE BOM), vt4_settings.ini defaults,
    VT4.exe PE signature guard, Safe Core Mode, MainMenu transition, DebugLog=0 PNG
    suppression, and 0 crashes.
  - Test B (Full 84 Mode): links archive\\HIGH via directory junction, removes save/
    & xlive_mod.log, verifies custom roster detection (84 players), MainMenu boot,
    and 0 crashes. Unlinks junction safely before cleanup.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GAME_DIR = ROOT / "game"
PC_ZIP = ROOT / "dist" / "release" / "VT4_Legends-v1.0.1-Windows-x86.zip"
CLEAN_DIR = Path(os.environ.get("LOCALAPPDATA", r"C:\Temp")) / "Temp" / "VT4_CleanTest"

VANILLA_RUNTIME_FILES = [
    "VT4.exe",
    "VT4.exe.cat",
    "VT4.exe.cfg",
    "vt4.dll",
    "resource.bin",
    "resource.1.bin",
    "msvcr90.dll",
    "msvcp90.dll",
    "msvcm90.dll",
    "XAudio2_7.dll",
]


def safe_unlink_junction(p: Path) -> None:
    if p.exists() or p.is_symlink():
        # `cmd /c rmdir` removes a Windows directory junction without deleting target contents
        subprocess.run(["cmd", "/c", "rmdir", str(p)], capture_output=True, check=False)


def clean_temp_dir() -> None:
    subprocess.run(["taskkill", "/F", "/IM", "VT4.exe"], capture_output=True, check=False)
    time.sleep(0.5)
    high_link = CLEAN_DIR / "archive" / "HIGH"
    safe_unlink_junction(high_link)
    if CLEAN_DIR.exists():
        shutil.rmtree(CLEAN_DIR)


def find_hwnd_for_pid(pid: int) -> int:
    user32 = ctypes.windll.user32
    found: list[int] = []
    rect = ctypes.wintypes.RECT()

    @ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    def enum_cb(hwnd: int, _lparam: int) -> int:
        proc_id = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
        if proc_id.value == pid and user32.IsWindowVisible(hwnd):
            if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                if (rect.right - rect.left) >= 320 and (rect.bottom - rect.top) >= 240:
                    found.append(hwnd)
                    return 0
        return 1

    user32.EnumWindows(enum_cb, 0)
    return found[0] if found else 0


def post_enter(pid: int) -> None:
    hwnd = find_hwnd_for_pid(pid)
    if not hwnd:
        return
    user32 = ctypes.windll.user32
    user32.SetCursorPos(10, 10)
    user32.SetForegroundWindow(hwnd)
    vk_return = 0x0D
    wm_keydown = 0x0100
    wm_keyup = 0x0101
    user32.PostMessageA(hwnd, wm_keydown, vk_return, 0)
    time.sleep(0.12)
    user32.PostMessageA(hwnd, wm_keyup, vk_return, 0xC0000000)


def wait_for_boot(proc: subprocess.Popen[bytes], log_path: Path, timeout_s: float = 40.0) -> str:
    deadline = time.time() + timeout_s
    last_enter = 0.0
    text = ""
    while time.time() < deadline:
        if proc.poll() is not None:
            if log_path.is_file():
                text = log_path.read_text(encoding="utf-8", errors="replace")
            raise RuntimeError(f"VT4.exe exited prematurely with code {proc.returncode}.\nLog:\n{text}")
        if log_path.is_file():
            text = log_path.read_text(encoding="utf-8", errors="replace")
            if "MainMenu state transition:" in text:
                time.sleep(1.5)
                return log_path.read_text(encoding="utf-8", errors="replace")
            if "TitleLogo launched successfully!" in text and find_hwnd_for_pid(proc.pid) and (time.time() - last_enter) >= 1.2:
                post_enter(proc.pid)
                last_enter = time.time()
        time.sleep(0.3)
    if log_path.is_file():
        text = log_path.read_text(encoding="utf-8", errors="replace")
    raise TimeoutError(f"Timed out waiting for MainMenu state transition after {timeout_s}s.\nLog:\n{text}")


def terminate_proc(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/F", "/IM", "VT4.exe"], capture_output=True, check=False)
            proc.wait(timeout=5)
    time.sleep(0.6)


def check_no_errors(log_text: str, stage: str) -> None:
    bad_markers = ("CRASH", "EXCEPTION", "[EXC]", "ERROR: Unsupported/packed")
    for line in log_text.splitlines():
        for m in bad_markers:
            if m in line:
                raise AssertionError(f"[{stage}] Error marker '{m}' found in log line: {line}")


def run_test_a_safe_core() -> None:
    print("\n=== Test A: External Clean Portable Safe Core Mode ===")
    assert PC_ZIP.is_file(), f"Missing release package: {PC_ZIP}"
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)

    for fname in VANILLA_RUNTIME_FILES:
        src = GAME_DIR / fname
        if fname.endswith((".cat", ".cfg")) and not src.is_file():
            continue
        assert src.is_file(), f"Missing vanilla file in game/: {src}"
        shutil.copy2(src, CLEAN_DIR / fname)

    with zipfile.ZipFile(PC_ZIP, "r") as zf:
        zf.extractall(CLEAN_DIR)

    # Remove vt4_settings.ini so xlive.dll also verifies auto-creation on first launch
    ini_path = CLEAN_DIR / "vt4_settings.ini"
    if ini_path.is_file():
        ini_path.unlink()

    save_dir = CLEAN_DIR / "save"
    assert not save_dir.exists(), "save/ must not exist before first launch"

    log_path = CLEAN_DIR / "xlive_mod.log"
    proc = subprocess.Popen([str(CLEAN_DIR / "VT4.exe")], cwd=str(CLEAN_DIR))
    try:
        log_text = wait_for_boot(proc, log_path, timeout_s=45.0)
        assert proc.poll() is None, "VT4.exe should remain running cleanly at MainMenu"
    finally:
        terminate_proc(proc)

    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    check_no_errors(log_text, "Test A")

    # Assert local portable paths & auto-created files
    cfg_txt = save_dir / "Config.txt"
    assert cfg_txt.is_file(), "save/Config.txt was not auto-created"
    raw_cfg = cfg_txt.read_bytes()
    assert raw_cfg[:2] == b"\xff\xfe", f"save/Config.txt missing UTF-16LE BOM: {raw_cfg[:4]!r}"
    cfg_lines = raw_cfg.decode("utf-16-le").lstrip("\ufeff").splitlines()
    assert len(cfg_lines) == 35, f"Expected 35 lines in Config.txt, got {len(cfg_lines)}"

    assert ini_path.is_file(), "vt4_settings.ini was not auto-created"
    ini_text = ini_path.read_text(encoding="utf-8", errors="replace")
    assert "UseD3D9Ex=1" in ini_text and "Locale=auto" in ini_text, "vt4_settings.ini missing v1.0.1 keys"

    expected_log_snippets = [
        "VT4.exe signature verified OK",
        "Auto-created default portable Config.txt",
        str(CLEAN_DIR).lower(),
        "Core Mode (custom roster pack not found)",
        "Safe Core Mode active",
        "MainMenu state transition: 1 -> 2",
    ]
    low_log = log_text.lower()
    for snip in expected_log_snippets:
        assert snip.lower() in low_log, f"[Test A] Missing expected log snippet: {snip!r}"

    # Verify hardcoded repo/dev path is absent from xlive_mod.log
    assert str(GAME_DIR).lower() not in low_log, "[Test A] Repo game path leaked into log!"

    # Verify DebugLog=0 suppressed auto frame-1/60 PNG dumps
    stray_pngs = list(CLEAN_DIR.glob("vt4_present_*.png"))
    assert not stray_pngs, f"[Test A] Found unexpected PNG dumps with DebugLog=0: {stray_pngs}"

    print(f"[PASS] Test A passed cleanly in {CLEAN_DIR} (Core Mode, BOM Config.txt, 0 stray PNGs, 0 errors)")


def run_test_b_full_84() -> None:
    print("\n=== Test B: External Clean Portable Full 84 Roster Mode ===")
    high_target = GAME_DIR / "archive" / "HIGH"
    high_link = CLEAN_DIR / "archive" / "HIGH"
    assert high_target.is_dir(), f"Missing source HIGH dir: {high_target}"

    safe_unlink_junction(high_link)
    res = subprocess.run(["cmd", "/c", "mklink", "/J", str(high_link), str(high_target)], capture_output=True, text=True)
    assert res.returncode == 0, f"Failed creating HIGH junction: {res.stdout} {res.stderr}"

    # Clear save/ and log to verify fresh boot in Full 84 mode too
    save_dir = CLEAN_DIR / "save"
    if save_dir.exists():
        shutil.rmtree(save_dir)
    log_path = CLEAN_DIR / "xlive_mod.log"
    if log_path.is_file():
        log_path.unlink()

    proc = subprocess.Popen([str(CLEAN_DIR / "VT4.exe")], cwd=str(CLEAN_DIR))
    try:
        log_text = wait_for_boot(proc, log_path, timeout_s=45.0)
        assert proc.poll() is None, "VT4.exe should remain running cleanly in Full 84 Mode"
    finally:
        terminate_proc(proc)
        safe_unlink_junction(high_link)

    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    check_no_errors(log_text, "Test B")

    expected_log_snippets = [
        "VT4.exe signature verified OK",
        "Auto-created default portable Config.txt",
        "Full Legends Roster Pack detected (84 players enabled)",
        "Fase 2 + Page 3 + Page 4 Roster Expansion active: IDs 26..83 (84 players",
        "MainMenu state transition: 1 -> 2",
    ]
    for snip in expected_log_snippets:
        assert snip in log_text, f"[Test B] Missing expected log snippet: {snip!r}"

    print(f"[PASS] Test B passed cleanly in {CLEAN_DIR} (Full 84 Mode, 0 errors)")


def run_test_c_recomp_prepare() -> None:
    print("\n=== Test C: RecompLauncher Prepare Batch + Manifest ===")
    import json
    src_copy = CLEAN_DIR / "_retail_copy"
    install_dir = CLEAN_DIR / "_recomp_install"
    src_copy.mkdir(parents=True, exist_ok=True)
    install_dir.mkdir(parents=True, exist_ok=True)

    for fname in VANILLA_RUNTIME_FILES:
        src = GAME_DIR / fname
        if src.is_file():
            shutil.copy2(src, src_copy / fname)

    with zipfile.ZipFile(PC_ZIP, "r") as zf:
        zf.extractall(install_dir)

    prep_bat = install_dir / "vt4_recomp_prepare.bat"
    assert prep_bat.is_file(), "vt4_recomp_prepare.bat missing from release ZIP"
    assert (install_dir / "launch_linux.sh").is_file(), "launch_linux.sh missing from release ZIP"
    assert (install_dir / "LINUX_STEAMDECK_GUIDE.md").is_file(), "LINUX_STEAMDECK_GUIDE.md missing from release ZIP"

    manifest = json.loads((install_dir / "recomplauncher.json").read_text(encoding="utf-8"))
    assert manifest.get("format") == 1
    assert manifest.get("start", {}).get("program") == ["VT4.exe"]

    # Run vt4_recomp_prepare.bat with spaces-safe quoting like RecompLauncher does
    res = subprocess.run(
        [str(prep_bat), f"--game={src_copy}", f"--out={install_dir}"],
        cwd=str(install_dir),
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"vt4_recomp_prepare.bat failed (rc={res.returncode}):\n{res.stdout}\n{res.stderr}"
    assert "progress 1.00" in res.stdout, f"Missing final progress line:\n{res.stdout}"
    for req in ("VT4.exe", "vt4.dll", "resource.bin", "resource.1.bin", ".vt4_prepared"):
        assert (install_dir / req).is_file(), f"Prepare missing {req}"
    assert (install_dir / "save").is_dir(), "Prepare missing save/ folder"
    assert (install_dir / "xlive.dll").stat().st_size == (GAME_DIR / "xlive.dll").stat().st_size

    # Verify keeps_copy re-run with omitted --game arg
    res2 = subprocess.run([str(prep_bat), f"--out={install_dir}"], cwd=str(install_dir), capture_output=True, text=True)
    assert res2.returncode == 0, f"keeps_copy re-run failed: {res2.stdout} {res2.stderr}"
    print("[PASS] Test C passed cleanly (vt4_recomp_prepare.bat + recomplauncher.json + Linux files)")


def main() -> int:
    clean_temp_dir()
    try:
        run_test_a_safe_core()
        run_test_b_full_84()
        run_test_c_recomp_prepare()
    finally:
        clean_temp_dir()
    print("\nALL PORTABLE CLEAN TESTS PASSED (0 errors, temp dir cleaned).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
