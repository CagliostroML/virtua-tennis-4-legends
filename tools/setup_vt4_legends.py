#!/usr/bin/env python3
"""Verify retail PC v1.0 files and prepare Virtua Tennis 4: Legends & Next-Gen Edition.

Compatible with standalone CLI usage and RecompLauncher's `prepare` step.

Usage:
  py -u tools/setup_vt4_legends.py --verify-only --game-dir game
  py -u tools/setup_vt4_legends.py --prepare --game-dir "C:\\Games\\VT4" --out-dir "C:\\Games\\VT4_Mods"
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
from pathlib import Path

RETAIL_HASHES: dict[str, tuple[str, int]] = {
    "VT4.exe": ("feae98d9864e2bab6dbdfa5cb55d328974ffc3b555912dccc2cf42db1998ac90", 5059400),
    "vt4.dll": ("6c530e5d84745caa5f62df9a0ed8422fec0896abce13674a375eef1ff02228af", 272200),
    "resource.bin": ("d03cb1b7bd7478770899db780338cdd789291feab1e1c69676e1310257847a64", 2130749198),
    "resource.1.bin": ("9a3a7182c7f0ee591d79f57c219cfe342b1cc164c412a99dfb64150264b8318b", 1062810942),
}

RUNTIME_COPY_FILES = [
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


def emit_progress(fraction: float, label: str) -> None:
    print(f"progress {fraction:.2f} {label}", flush=True)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_retail_dir(game_dir: Path) -> bool:
    if not game_dir.is_dir():
        print(f"ERROR: Game folder does not exist: {game_dir}", file=sys.stderr)
        return False

    all_ok = True
    items = list(RETAIL_HASHES.items())
    for idx, (fname, (exp_sha, exp_size)) in enumerate(items, start=1):
        p = game_dir / fname
        emit_progress(0.10 + 0.45 * (idx / len(items)), f"Checking {fname}")
        if not p.is_file():
            print(f"MISSING: {fname} (not found in {game_dir})", file=sys.stderr)
            all_ok = False
            continue
        actual_size = p.stat().st_size
        actual_sha = sha256_file(p)
        size_ok = actual_size == exp_size
        sha_ok = actual_sha == exp_sha
        status = "OK" if (size_ok and sha_ok) else "MISMATCH"
        print(f"[{status}] {fname}: size={actual_size:,} (expected {exp_size:,}) sha256={actual_sha}")
        if not (size_ok and sha_ok):
            all_ok = False
    return all_ok


def prepare_install(game_dir: Path | None, out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    marker = out_dir / ".vt4_prepared"

    # RecompLauncher keeps_copy support: if source copy wasn't passed again, check existing install
    if game_dir is None:
        if all((out_dir / req).is_file() for req in ("VT4.exe", "vt4.dll", "resource.bin", "resource.1.bin")):
            (out_dir / "save").mkdir(parents=True, exist_ok=True)
            marker.write_text("prepared=1\n", encoding="utf-8")
            emit_progress(1.0, "Already prepared")
            return 0
        print("Missing --game-dir and Virtua Tennis 4 retail files are not present in install folder.", file=sys.stderr)
        return 1

    if marker.is_file():
        marker.unlink()

    for req in ("VT4.exe", "vt4.dll", "resource.bin", "resource.1.bin"):
        if not (game_dir / req).is_file():
            print(f"Missing required retail file '{req}' in {game_dir}. Pick your unpacked VT4 PC folder.", file=sys.stderr)
            return 1

    same_dir = game_dir.resolve() == out_dir.resolve()
    if not same_dir:
        total = len(RUNTIME_COPY_FILES)
        for idx, fname in enumerate(RUNTIME_COPY_FILES, start=1):
            src = game_dir / fname
            dst = out_dir / fname
            if not src.is_file():
                continue
            emit_progress(0.15 + 0.75 * (idx / total), f"Copying {fname}")
            if dst.is_file() and dst.stat().st_size == src.stat().st_size:
                continue
            shutil.copy2(src, dst)

    (out_dir / "save").mkdir(parents=True, exist_ok=True)
    marker.write_text("prepared=1\n", encoding="utf-8")
    emit_progress(1.0, "Virtua Tennis 4 retail files ready")
    print(f"Prepared VT4 Legends install in {out_dir}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify & prepare Virtua Tennis 4: Legends & Next-Gen Edition")
    parser.add_argument("--game-dir", type=Path, default=None, help="Path to user's retail VT4 PC folder")
    parser.add_argument("--out-dir", type=Path, default=None, help="Target mod install folder (defaults to --game-dir)")
    parser.add_argument("--verify-only", action="store_true", help="Verify retail PC v1.0 SHA-256 checksums only")
    parser.add_argument("--prepare", action="store_true", help="Link/copy retail runtime files into --out-dir cleanly")
    args = parser.parse_args()

    if args.verify_only:
        target = args.game_dir or (Path(__file__).resolve().parents[1] / "game")
        ok = verify_retail_dir(target)
        return 0 if ok else 1

    if args.prepare:
        out = args.out_dir or args.game_dir
        if out is None:
            print("ERROR: Specify --out-dir or --game-dir with --prepare", file=sys.stderr)
            return 1
        return prepare_install(args.game_dir, out)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
