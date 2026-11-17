"""Deterministic Exhibition match test for any P1/CPU ID, Multiverse, and PostFX setting."""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vt4_test_lib as vt4


def move_grid_cursor(hwnd, cur_row, cur_col, tgt_row, tgt_col):
    while cur_row < tgt_row:
        vt4.send_key(hwnd, vt4.VK_DOWN, hold=0.09, post_wait=0.35)
        cur_row += 1
    while cur_row > tgt_row:
        vt4.send_key(hwnd, vt4.VK_UP, hold=0.09, post_wait=0.35)
        cur_row -= 1
    while cur_col < tgt_col:
        vt4.send_key(hwnd, vt4.VK_RIGHT, hold=0.09, post_wait=0.35)
        cur_col += 1
    while cur_col > tgt_col:
        vt4.send_key(hwnd, vt4.VK_LEFT, hold=0.09, post_wait=0.35)
        cur_col -= 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--p1", type=int, default=26, help="P1 char_id (default 26 Alcaraz)")
    ap.add_argument("--cpu", type=int, default=0, help="CPU char_id (default 0 Federer)")
    ap.add_argument("--mv", type=int, default=0, help="MultiverseMode 0..3")
    ap.add_argument("--postfx", type=int, default=1, help="CleanPostFX 0..2")
    ap.add_argument("--tv", type=int, default=1, help="ClassicTVCamera 0..1")
    ap.add_argument("--speed", type=int, default=0, help="MatchSpeedMode 0..3")
    ap.add_argument("--exbrules", type=int, default=2, help="ExhibitionRules 0..3")
    ap.add_argument("--debug", type=int, default=0, help="DebugLog 0..1")
    ap.add_argument("--rally-wait", type=float, default=2.5, help="Wait after serve before 2nd shot")
    args = ap.parse_args()

    p1_page, p1_row, p1_col = vt4.locate_char(args.p1)
    cpu_page, cpu_row, cpu_col = vt4.locate_char(args.cpu)

    vt4.kill_vt4()
    vt4.clean_artifacts()
    vt4.write_clean_ini(
        clean_postfx=args.postfx,
        tv_cam=args.tv,
        speed=args.speed,
        exb_rules=args.exbrules,
        multiverse=args.mv,
        debug_log=args.debug,
    )

    p, hwnd = vt4.launch_vt4()
    try:
        vt4.boot_to_main_menu(hwnd)
        if not vt4.navigate_carousel(hwnd, 2):
            raise RuntimeError("Failed to select ExhibitionMode")
        vt4.send_key(hwnd, vt4.VK_RETURN, hold=0.10, post_wait=2.5)  # Exhibition Settings
        for _ in range(6):
            vt4.send_key(hwnd, vt4.VK_DOWN, hold=0.11, post_wait=0.75)
        vt4.send_key(hwnd, vt4.VK_RETURN, hold=0.10, post_wait=3.5)

        if not vt4.wait_for_log("FPPlayerEntry::IsReady called", timeout=12.0):
            raise RuntimeError("Did not reach FPPlayerEntry")
        time.sleep(1.0)
        for _ in range(8):
            if "FPCharaSelect_Update frame " in vt4.read_log():
                break
            vt4.send_key(hwnd, vt4.VK_RETURN, hold=0.12, post_wait=1.0)
        if "FPCharaSelect_Update frame " not in vt4.read_log():
            raise RuntimeError("Did not reach FPCharaSelect")
        time.sleep(1.4)

        cur_page = 0
        while cur_page != p1_page:
            step = 1 if p1_page > cur_page else -1
            vt4.send_key(hwnd, vt4.VK_E if step > 0 else vt4.VK_Q, hold=0.10, post_wait=1.2)
            cur_page += step
        move_grid_cursor(hwnd, 0, 0, p1_row, p1_col)
        vt4.send_key(hwnd, vt4.VK_F10, hold=0.08, post_wait=0.8)  # Shot: P1 selected card
        vt4.send_key(hwnd, vt4.VK_RETURN, hold=0.10, post_wait=1.4)  # Confirm P1

        # Pick CPU: P2/CPU selector always starts at (row=0, col=0) on the active page
        while cur_page != cpu_page:
            step = 1 if cpu_page > cur_page else -1
            vt4.send_key(hwnd, vt4.VK_E if step > 0 else vt4.VK_Q, hold=0.10, post_wait=1.2)
            cur_page += step
        move_grid_cursor(hwnd, 0, 0, cpu_row, cpu_col)
        vt4.send_key(hwnd, vt4.VK_RETURN, hold=0.10, post_wait=1.3)  # Confirm CPU
        vt4.send_key(hwnd, vt4.VK_RETURN, hold=0.10, post_wait=1.5)  # Confirm Stage

        if not vt4.wait_for_log("Dismissing loading screen", timeout=25.0):
            raise RuntimeError("Did not dismiss loading screen")
        # Wait up to 8s for LiveMatch ready, pressing Enter once to skip intro flyover
        time.sleep(2.5)
        for _ in range(4):
            if "LiveMatch ready at frame " in vt4.read_log():
                break
            vt4.send_key(hwnd, vt4.VK_RETURN, hold=0.10, post_wait=1.5)
        vt4.wait_for_log("LiveMatch ready at frame ", timeout=6.0)
        time.sleep(3.2)  # Wait for pre-point [1 | 0] badge & ready lock to clear

        # Move slightly left, serve with Z -> wait 0.45s -> Z
        vt4.send_key(hwnd, vt4.VK_A, hold=0.22, post_wait=0.2)
        vt4.send_key(hwnd, vt4.VK_Z, hold=0.12, post_wait=0.45)
        vt4.send_key(hwnd, vt4.VK_Z, hold=0.12, post_wait=0.9)
        vt4.send_key(hwnd, vt4.VK_F10, hold=0.08, post_wait=args.rally_wait)

        # Second serve / rally shot
        vt4.send_key(hwnd, vt4.VK_Z, hold=0.12, post_wait=0.45)
        vt4.send_key(hwnd, vt4.VK_Z, hold=0.12, post_wait=0.9)
        vt4.send_key(hwnd, vt4.VK_F10, hold=0.08, post_wait=1.2)
    finally:
        if p.poll() is None:
            p.kill()
            p.wait()
        vt4.write_clean_ini()

    summary = vt4.summarize_log()
    pngs = vt4.verify_pngs()
    print(f"TEST_MATCH p1={args.p1} cpu={args.cpu} mv={args.mv} postfx={args.postfx}")
    print(f"  PlayStyle asserts: {summary['playstyle_asserts']}")
    print(f"  ExbAdv asserts   : {summary['exbadv_asserts']}")
    print(f"  Exceptions       : {len(summary['exceptions'])}")
    for e in summary["exceptions"][:5]:
        print("   ", e)
    for l in summary["extra6"]:
        print("   ", l)
    for l in summary["fase3"]:
        print("   ", l)
    for l in summary["diag"]:
        print("   ", l)
    for name, ok, info, mode in pngs:
        print(f"  PNG {'VALID' if ok else 'INVALID'}: {name} {info} {mode}")

    if summary["playstyle_asserts"] > 0 or summary["exbadv_asserts"] > 0:
        sys.exit(2)


if __name__ == "__main__":
    main()
