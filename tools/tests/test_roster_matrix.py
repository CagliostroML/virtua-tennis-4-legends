"""Run test_match across a list of P1 IDs and print a summary verification matrix."""
import argparse
import os
import re
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEST_MATCH = os.path.join(REPO_ROOT, "tools", "tests", "test_match.py")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="26,27,28,29,30,31,32,33,34,35,36,37")
    ap.add_argument("--cpu", type=int, default=0)
    ap.add_argument("--mv", type=int, default=3)
    args = ap.parse_args()

    ids = [int(x.strip()) for x in args.ids.split(",") if x.strip()]
    rows = []
    for cid in ids:
        proc = subprocess.run(
            [sys.executable, TEST_MATCH, "--p1", str(cid), "--cpu", str(args.cpu), "--mv", str(args.mv)],
            capture_output=True, text=True
        )
        out = proc.stdout + "\n" + proc.stderr
        loaded = "PNG VALID: vt4_present_" in out and proc.returncode == 0
        ps = re.search(r"PlayStyle asserts:\s*(\d+)", out)
        ex = re.search(r"ExbAdv asserts\s*:\s*(\d+)", out)
        exc_lines = [l for l in out.splitlines() if "EXCEPTION CAUGHT" in l]
        served = out.count("[FASE-3]")
        rows.append((cid, loaded, ps.group(1) if ps else "?", ex.group(1) if ex else "?", len(exc_lines), served))
        print(f"ID {cid:2d}: ok={loaded} ps={rows[-1][2]} ex={rows[-1][3]} exc={len(exc_lines)} served={served}", flush=True)

    print("\n| ID | Loaded | PlayStyle | ExbAdv | Exc | Served([FASE-3]) |")
    print("|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} |")


if __name__ == "__main__":
    main()
