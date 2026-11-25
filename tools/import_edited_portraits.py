#!/usr/bin/env python3
"""
Import manually/AI+PhotoCraft edited portraits from:
  assets/portraits_photocraft_workspace/03_entregar_editados_aqui/
    cutouts/<ID>.png      (or <ID>_<CODE>*.png — full-res RGBA transparent bust)
    photo_L/<ID>.png      (optional direct 256x256 RGBA transparent bust)
    photo_eye/<ID>.png    (optional direct 256x64 opaque selector strip)
    photo_S/<ID>.png      (optional direct 128x64 transparent mini bust)

Converts & installs into:
  game/archive/HIGH/Frontend/VR/{photo_L,photo_eye,photo_S}/<ID>.dds
and saves an inspection sheet in scratch/imported_portraits_audit.png.
"""
import argparse
import os
import re
import sys
from PIL import Image, ImageDraw

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

from build_v2_portraits import (
    VR_DIR,
    build_eye_strip,
    build_photo_s,
    frame_portrait_256,
    remove_small_alpha_islands,
    write_bgra_dds,
    write_dxt5_dds,
)

DROP_DIR = os.path.join(REPO_ROOT, "assets", "portraits_photocraft_workspace", "03_entregar_editados_aqui")


def _extract_player_id(filename: str) -> str | None:
    stem = os.path.splitext(os.path.basename(filename))[0]
    m = re.match(r"^(29_91|\d{1,3})(?:_|$)", stem)
    return m.group(1) if m else None


def _scan_dir_by_id(folder: str) -> dict[str, str]:
    found = {}
    if not os.path.isdir(folder):
        return found
    for fn in sorted(os.listdir(folder)):
        if not fn.lower().endswith((".png", ".webp", ".tga", ".bmp", ".jpg", ".jpeg")):
            continue
        pid = _extract_player_id(fn)
        if pid:
            found[pid] = os.path.join(folder, fn)
    return found


def estimate_eye_y_256(p256: Image.Image) -> int:
    """Estimate vertical center of the eyes on a 256x256 bottom-anchored bust portrait.

    On a chest-up bust portrait padded ~8px at top, head height spans ~90-130 px and the
    eyes sit ~24-30% of visible bust height below the top of the head/hairline.
    """
    a = p256.getchannel("A")
    bb = a.getbbox()
    if not bb:
        return 60
    top_y = bb[1]
    bot_y = bb[3]
    vis_h = max(40, bot_y - top_y)
    # Find horizontal head width near top ~45px to gauge face scale (close-up vs waist-up)
    row_widths = []
    for y in range(top_y + 10, min(256, top_y + 70), 4):
        xs = [x for x in range(256) if a.getpixel((x, y)) > 40]
        if xs:
            row_widths.append(xs[-1] - xs[0])
    head_w = max(row_widths) if row_widths else 56
    # Wider heads mean closer bust -> eyes slightly lower relative to top_y
    offset = int(round(max(26.0, min(68.0, head_w * 0.46 + vis_h * 0.06))))
    eye_y = top_y + offset
    return max(26, min(226, eye_y))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Inspect files without writing game DDS files.")
    ap.add_argument("--keep-drops", action="store_true", help="Leave PNGs in 03_entregar_editados_aqui (default keeps them).")
    args = ap.parse_args()

    cutouts = _scan_dir_by_id(os.path.join(DROP_DIR, "cutouts"))
    direct_l = _scan_dir_by_id(os.path.join(DROP_DIR, "photo_L"))
    direct_eye = _scan_dir_by_id(os.path.join(DROP_DIR, "photo_eye"))
    direct_s = _scan_dir_by_id(os.path.join(DROP_DIR, "photo_S"))

    all_ids = sorted(set(cutouts) | set(direct_l) | set(direct_eye) | set(direct_s), key=lambda k: (29.5 if k == "29_91" else float(k)))
    if not all_ids:
        print(f"No edited images found under {DROP_DIR}. Nothing to import.")
        return

    print(f"Found {len(all_ids)} player(s) to import: {', '.join(all_ids)}")
    imported = []

    for pid in all_ids:
        p256 = None
        if pid in direct_l:
            im = Image.open(direct_l[pid]).convert("RGBA")
            if im.size != (256, 256):
                im = frame_portrait_256(im, (0, 0, im.width, im.height), 0.03)
            p256 = im
        elif pid in cutouts:
            raw = Image.open(cutouts[pid]).convert("RGBA")
            raw = remove_small_alpha_islands(raw, min_pixels=250)
            bb = raw.getbbox()
            if not bb:
                print(f"  [SKIP] {pid}: cutout is completely transparent!")
                continue
            p256 = frame_portrait_256(raw, (0, 0, raw.width, raw.height), 0.03)
        else:
            existing_l = os.path.join(REPO_ROOT, VR_DIR, "photo_L", f"{pid}.dds")
            if os.path.isfile(existing_l):
                p256 = Image.open(existing_l).convert("RGBA")

        if p256 is None:
            print(f"  [SKIP] {pid}: no photo_L or cutout found.")
            continue

        if pid in direct_eye:
            eye = Image.open(direct_eye[pid]).convert("RGBA")
            if eye.size != (256, 64):
                eye = eye.resize((256, 64), Image.Resampling.LANCZOS)
            # Ensure opaque alpha channel on photo_eye
            r, g, b, _ = eye.split()
            eye = Image.merge("RGBA", (r, g, b, Image.new("L", (256, 64), 255)))
        else:
            eye_y = estimate_eye_y_256(p256)
            eye = build_eye_strip(p256, eye_y)

        if pid in direct_s:
            ps = Image.open(direct_s[pid]).convert("RGBA")
            if ps.size != (128, 64):
                ps = ps.resize((128, 64), Image.Resampling.LANCZOS)
        else:
            ps = build_photo_s(p256)

        if not args.dry_run:
            write_bgra_dds(p256, os.path.join(REPO_ROOT, VR_DIR, "photo_L", f"{pid}.dds"))
            write_bgra_dds(eye, os.path.join(REPO_ROOT, VR_DIR, "photo_eye", f"{pid}.dds"))
            write_dxt5_dds(ps, os.path.join(REPO_ROOT, VR_DIR, "photo_S", f"{pid}.dds"))
        imported.append((pid, p256, eye))
        print(f"  [OK] {pid}: packed photo_L / photo_eye / photo_S{' (dry-run)' if args.dry_run else ''}")

    if imported:
        cols = min(5, len(imported))
        rows = (len(imported) + cols - 1) // cols
        cw, ch = 260, 326
        sheet = Image.new("RGB", (cols * cw, rows * ch), (24, 26, 34))
        tile = Image.new("RGB", (256, 256))
        tpx = tile.load()
        for y in range(256):
            for x in range(256):
                tpx[x, y] = (58, 62, 72) if ((x // 16) + (y // 16)) % 2 == 0 else (88, 92, 104)
        draw = ImageDraw.Draw(sheet)
        for idx, (pid, p256, eye) in enumerate(imported):
            r, c = divmod(idx, cols)
            x0, y0 = c * cw + 2, r * ch + 2
            sheet.paste(tile, (x0, y0))
            sheet.paste(p256, (x0, y0), p256)
            sheet.paste(eye.resize((256, 64), Image.Resampling.LANCZOS), (x0, y0 + 258))
            draw.rectangle([x0, y0, x0 + 96, y0 + 18], fill=(12, 14, 20))
            draw.text((x0 + 4, y0 + 3), f"NEW {pid}", fill=(120, 255, 160))

        out_sheet = os.path.join(REPO_ROOT, "scratch", "imported_portraits_audit.png")
        os.makedirs(os.path.dirname(out_sheet), exist_ok=True)
        sheet.save(out_sheet)
        Image.open(out_sheet).verify()
        print("Audit sheet written:", out_sheet)


if __name__ == "__main__":
    main()
