#!/usr/bin/env python3
"""
Pack user-edited 1024x1024 face UV textures from assets/face_uv_workspace/<PLAYER>/edited_face_uv.png
into game/archive/HIGH/Player/Model/<PLAYER>.sdo with exact DXT5 mipmaps and optional body skin-tone sync.

Usage:
  python tools/pack_custom_faces.py                  # Pack all players that have edited_face_uv.png
  python tools/pack_custom_faces.py --player 30_BOR  # Pack only Borg
  python tools/pack_custom_faces.py --no-sync-body   # Skip automatic *_B_body_*.dds skin tone matching
"""
import argparse
import json
import os
import sys
from PIL import Image

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

from vt4_archive import lzss_decompress
from compress_sega_lzss import lzss_compress_literal
from update_custom_assets import parse_sdo_dds_slots, extract_slot_image, replace_sdo_tex

MODEL_DIR = os.path.join(REPO_ROOT, "game", "archive", "HIGH", "Player", "Model")
FACE_WS_DIR = os.path.join(REPO_ROOT, "assets", "face_uv_workspace")


def _sample_neck_mean(im: Image.Image) -> tuple[float, float, float]:
    rgba = im.convert("RGBA").resize((1024, 1024), Image.Resampling.BILINEAR)
    px = rgba.load()
    sr = sg = sb = cnt = 0
    for y in range(790, 910, 2):
        for x in range(420, 604, 2):
            r, g, b, a = px[x, y]
            if a > 128 and (r + g + b) > 60:
                sr += r
                sg += g
                sb += b
                cnt += 1
    if cnt == 0:
        return (180.0, 140.0, 115.0)
    return (sr / cnt, sg / cnt, sb / cnt)


def _sync_body_skin(dec: bytearray, slots: dict, base_face: Image.Image, new_face: Image.Image) -> int:
    bm = _sample_neck_mean(base_face)
    nm = _sample_neck_mean(new_face)
    ratios = [max(0.65, min(1.45, nm[i] / max(25.0, bm[i]))) for i in range(3)]
    if all(abs(r - 1.0) < 0.03 for r in ratios):
        return 0
    updated = 0
    for sname, slot in slots.items():
        if "_b_body" in sname.lower():
            im_b = extract_slot_image(dec, slot)
            px = im_b.load()
            for y in range(im_b.height):
                for x in range(im_b.width):
                    r, g, b, a = px[x, y]
                    if a == 0:
                        continue
                    px[x, y] = (
                        max(0, min(255, int(r * ratios[0]))),
                        max(0, min(255, int(g * ratios[1]))),
                        max(0, min(255, int(b * ratios[2]))),
                        a,
                    )
            replace_sdo_tex(dec, slot, im_b)
            updated += 1
    return updated


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--player", help="Single folder name, e.g. 30_BOR")
    ap.add_argument("--no-sync-body", action="store_true", help="Do not adjust *_B_body_* skin tone")
    args = ap.parse_args()

    manifest_path = os.path.join(FACE_WS_DIR, "manifest.json")
    if not os.path.exists(manifest_path):
        raise FileNotFoundError("Run python tools/build_all_sdo_models.py first to generate manifest.json")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    targets = [args.player] if args.player else sorted(manifest.keys())
    packed = 0
    for folder in targets:
        if folder not in manifest:
            print(f"[SKIP] Unknown player folder: {folder}")
            continue
        info = manifest[folder]
        ws_dir = os.path.join(FACE_WS_DIR, folder)
        edit_path = os.path.join(ws_dir, "edited_face_uv.png")
        if not os.path.exists(edit_path):
            continue

        sdo_path = os.path.join(MODEL_DIR, info["sdo"])
        if not os.path.exists(sdo_path):
            print(f"[WARN] Missing SDO: {sdo_path}")
            continue

        with open(sdo_path, "rb") as f:
            dec = bytearray(lzss_decompress(f.read()))
        slots = {s["name"]: s for s in parse_sdo_dds_slots(dec)}
        face_slot_name = info["face_slot"]
        if face_slot_name not in slots:
            print(f"[WARN] Face slot {face_slot_name} not found in {info['sdo']}")
            continue

        slot = slots[face_slot_name]
        new_face = Image.open(edit_path).convert("RGBA").resize((slot["w"], slot["h"]), Image.Resampling.LANCZOS)
        orig_face = extract_slot_image(dec, slot)
        new_face.putalpha(orig_face.getchannel("A"))
        replace_sdo_tex(dec, slot, new_face)

        body_cnt = 0
        base_uv_path = os.path.join(ws_dir, "00_sega_base_uv.png")
        if not args.no_sync_body and os.path.exists(base_uv_path):
            base_face = Image.open(base_uv_path).convert("RGBA")
            body_cnt = _sync_body_skin(dec, slots, base_face, new_face)

        with open(sdo_path, "wb") as f:
            f.write(lzss_compress_literal(bytes(dec)))
        packed += 1
        print(f"[PACKED] {folder:9s} -> {info['sdo']} (face={face_slot_name}, body_synced={body_cnt})")

    print(f"Done. Packed {packed} custom face UV(s).")


if __name__ == "__main__":
    main()
