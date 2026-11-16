"""Test native OptionMode -> GRAFICOS HD Y LEGENDS submenu and INI persistence."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vt4_test_lib as vt4


def main():
    vt4.kill_vt4()
    vt4.clean_artifacts()
    vt4.write_clean_ini()

    p, hwnd = vt4.launch_vt4()
    try:
        vt4.boot_to_main_menu(hwnd)
        items = vt4.get_carousel_items()
        opt_idx = next((i for i, n in enumerate(items) if "opt" in n.lower()), 7)
        if not vt4.navigate_carousel(hwnd, opt_idx):
            raise RuntimeError("Could not navigate to OptionMode")
        vt4.send_key(hwnd, vt4.VK_RETURN, hold=0.10, post_wait=1.8)
        if not vt4.wait_for_log("Entered OptionMode (Ajustes)", timeout=8.0):
            raise RuntimeError("Did not enter OptionMode")
        vt4.send_key(hwnd, vt4.VK_F10, hold=0.08, post_wait=1.0)

        for _ in range(3):
            vt4.send_key(hwnd, vt4.VK_DOWN, hold=0.09, post_wait=0.3)
        vt4.send_key(hwnd, vt4.VK_RETURN, hold=0.10, post_wait=0.8)
        if not vt4.wait_for_log("Entered native OptionMode submenu -> GRAFICOS HD Y LEGENDS", timeout=5.0):
            raise RuntimeError("Did not enter GRAFICOS HD Y LEGENDS")

        for _ in range(7):
            vt4.send_key(hwnd, vt4.VK_DOWN, hold=0.06, post_wait=0.18)
        vt4.send_key(hwnd, vt4.VK_RIGHT, hold=0.06, post_wait=0.18)  # TVLock=1
        vt4.send_key(hwnd, vt4.VK_DOWN, hold=0.06, post_wait=0.18)   # Speed
        vt4.send_key(hwnd, vt4.VK_RIGHT, hold=0.06, post_wait=0.18)  # 1.20x
        vt4.send_key(hwnd, vt4.VK_DOWN, hold=0.06, post_wait=0.18)   # ExbRules
        vt4.send_key(hwnd, vt4.VK_RIGHT, hold=0.06, post_wait=0.18)
        vt4.send_key(hwnd, vt4.VK_RIGHT, hold=0.06, post_wait=0.18)  # 5 Sets
        vt4.send_key(hwnd, vt4.VK_DOWN, hold=0.06, post_wait=0.18)   # Multiverse
        vt4.send_key(hwnd, vt4.VK_RIGHT, hold=0.06, post_wait=0.18)
        vt4.send_key(hwnd, vt4.VK_RIGHT, hold=0.06, post_wait=0.18)
        vt4.send_key(hwnd, vt4.VK_RIGHT, hold=0.06, post_wait=0.18)  # Chaos Total (3)
        vt4.send_key(hwnd, vt4.VK_RETURN, hold=0.08, post_wait=0.8)
        vt4.send_key(hwnd, vt4.VK_F10, hold=0.08, post_wait=1.2)
    finally:
        if p.poll() is None:
            p.kill()
            p.wait()
        saved_ini = open(vt4.INI_PATH, "r", encoding="utf-8", errors="replace").read()
        vt4.write_clean_ini()

    print("Saved INI snapshot:")
    print(saved_ini.strip())
    for name, ok, info, mode in vt4.verify_pngs():
        print(f"  PNG {'VALID' if ok else 'INVALID'}: {name} {info} {mode}")


if __name__ == "__main__":
    main()
