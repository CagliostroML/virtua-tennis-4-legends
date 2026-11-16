"""Shared test utilities for automated VT4 Legends & Next-Gen verification."""
import ctypes
import glob
import os
import re
import subprocess
import time
from PIL import Image

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GAME_DIR = os.path.join(REPO_ROOT, "game")
LOG_PATH = os.path.join(GAME_DIR, "xlive_mod.log")
INI_PATH = os.path.join(GAME_DIR, "vt4_settings.ini")

user32 = ctypes.windll.user32
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101

VK_BACK = 0x08
VK_RETURN = 0x0D
VK_ESCAPE = 0x1B
VK_SPACE = 0x20
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
VK_A = 0x41
VK_D = 0x44
VK_E = 0x45
VK_J = 0x4A
VK_Q = 0x51
VK_S = 0x53
VK_W = 0x57
VK_X = 0x58
VK_Z = 0x5A
VK_F10 = 0x79

PAGE_TOUR = [
    0, 2, 3,
    1, 5, 4,
    6, 7, 10,
    8, 9, 13,
    15, 16, 22,
    17, 19, 18,
    23, 21, 20,
]

PAGE_LEGENDS = [
    11, 14, 12,
    13, 26, 27,
    28, 29, 30,
    31, 32, 33,
    34, 35, 36,
    37, 15, 16,
    24, 25, 23,
]


def format_ini(
    width=1920,
    height=1080,
    windowed=1,
    aa=4,
    vsync=1,
    aniso=16,
    clean_postfx=1,
    remove_live=1,
    tv_cam=0,
    speed=0,
    exb_rules=0,
    multiverse=0,
    debug_log=0,
):
    lines = [
        "[Graphics]",
        f"Width={width}",
        f"Height={height}",
        f"Windowed={windowed}",
        f"AntiAliasing={aa}",
        f"VSync={vsync}",
        f"AnisotropicFiltering={aniso}",
        f"CleanPostFX={clean_postfx}",
        "[Menu]",
        f"RemoveLiveMode={remove_live}",
        "[Gameplay]",
        f"ClassicTVCamera={tv_cam}",
        f"MatchSpeedMode={speed}",
        f"ExhibitionRules={exb_rules}",
        f"MultiverseMode={multiverse}",
    ]
    if debug_log:
        lines.extend(["[Debug]", f"DebugLog={debug_log}"])
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


def write_clean_ini(**overrides):
    with open(INI_PATH, "wb") as f:
        f.write(format_ini(**overrides))


def kill_vt4():
    os.system("taskkill /F /IM VT4.exe >nul 2>&1")
    time.sleep(0.4)


def clean_artifacts():
    if os.path.exists(LOG_PATH):
        os.remove(LOG_PATH)
    for png in glob.glob(os.path.join(GAME_DIR, "vt4_present_*.png")):
        os.remove(png)


def find_hwnd(pid):
    result = []
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def cb(hwnd, lparam):
        if user32.IsWindowVisible(hwnd):
            wpid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
            if wpid.value == pid:
                result.append(hwnd)
                return False
        return True

    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return result[0] if result else None


def launch_vt4(timeout=12.0):
    p = subprocess.Popen([os.path.join(GAME_DIR, "VT4.exe")], cwd=GAME_DIR)
    deadline = time.time() + timeout
    hwnd = None
    while time.time() < deadline:
        time.sleep(0.25)
        hwnd = find_hwnd(p.pid)
        if hwnd:
            break
    if not hwnd:
        p.kill()
        p.wait()
        raise RuntimeError("Failed to find VT4.exe window")
    user32.SetCursorPos(10, 10)
    return p, hwnd


def send_key(hwnd, vk, hold=0.10, post_wait=0.45):
    user32.SetCursorPos(10, 10)
    user32.SetForegroundWindow(hwnd)
    user32.PostMessageA(hwnd, WM_KEYDOWN, vk, 0)
    time.sleep(hold)
    user32.PostMessageA(hwnd, WM_KEYUP, vk, 0xC0000000)
    time.sleep(post_wait)


def read_log():
    if not os.path.exists(LOG_PATH):
        return ""
    with open(LOG_PATH, "r", errors="replace") as f:
        return f.read()


def wait_for_log(substr, timeout=20.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if substr in read_log():
            return True
        time.sleep(0.2)
    return False


def get_carousel_sel():
    matches = re.findall(r"Carousel selection changed: -?\d+ -> (-?\d+)", read_log())
    return int(matches[-1]) if matches else None


def get_carousel_items():
    lines = read_log().splitlines()
    cleaned = []
    for i, line in enumerate(lines):
        m = re.search(r"Carousel::AddItem: name='([^']*)'", line)
        if m:
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if "BLOCKED Live item" not in nxt:
                cleaned.append(m.group(1))
    return cleaned


def navigate_carousel(hwnd, target_idx, max_steps=14):
    for _ in range(max_steps):
        sel = get_carousel_sel()
        if sel == target_idx:
            return True
        vk = VK_DOWN if (sel is None or sel < target_idx) else VK_UP
        send_key(hwnd, vk, hold=0.10, post_wait=0.85)
    return get_carousel_sel() == target_idx


def boot_to_main_menu(hwnd):
    time.sleep(4.2)
    send_key(hwnd, VK_RETURN, hold=0.10, post_wait=1.0)
    if not wait_for_log("MainMenu state transition: 1 -> 2", timeout=14.0):
        raise RuntimeError("Did not reach MainMenu state 2")
    time.sleep(1.5)


def locate_char(char_id):
    if char_id in PAGE_LEGENDS:
        idx = PAGE_LEGENDS.index(char_id)
        return 1, idx // 3, idx % 3
    if char_id in PAGE_TOUR:
        idx = PAGE_TOUR.index(char_id)
        return 0, idx // 3, idx % 3
    raise ValueError(f"char_id {char_id} is not on PAGE_TOUR or PAGE_LEGENDS")


def verify_pngs():
    results = []
    pngs = sorted(
        glob.glob(os.path.join(GAME_DIR, "vt4_present_*.png")),
        key=lambda s: int(s.rsplit("_", 1)[1].split(".")[0]),
    )
    for png in pngs:
        try:
            with Image.open(png) as im:
                im.verify()
            with Image.open(png) as im:
                results.append((os.path.basename(png), True, im.size, im.mode))
        except Exception as e:
            results.append((os.path.basename(png), False, str(e), ""))
    return results


def summarize_log():
    txt = read_log()
    playstyle_asserts = txt.count("PlayStyleParameter.cpp (137)")
    exbadv_asserts = txt.count("ExhibitionAdvancedSetting.cpp (72)")
    # Exclude normal startup TreeTraverse VEH lines only if needed, report all EXCEPTION CAUGHT lines
    exc_lines = [l for l in txt.splitlines() if "EXCEPTION CAUGHT" in l]
    # Filter out normal startup TreeTraverse VEH recoveries
    real_exc = []
    lines = txt.splitlines()
    for idx, l in enumerate(lines):
        if "EXCEPTION CAUGHT" in l:
            block = "\n".join(lines[idx:idx+80])
            if "VEH recovering from invalid TreeTraverse node" not in block:
                real_exc.append(l)
    exc_lines = real_exc
    fase3_lines = [l for l in txt.splitlines() if "[FASE-3]" in l]
    extra6_lines = [l for l in txt.splitlines() if "[EXTRA-6]" in l]
    diag_lines = [l for l in txt.splitlines() if "[DIAG-" in l]
    return {
        "playstyle_asserts": playstyle_asserts,
        "exbadv_asserts": exbadv_asserts,
        "exceptions": exc_lines,
        "fase3": fase3_lines,
        "extra6": extra6_lines,
        "diag": diag_lines,
    }
