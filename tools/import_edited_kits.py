#!/usr/bin/env python3
"""
Import manually / AI+PhotoCraft edited kit, pants/skirt, shoes, racket, and accessory
UV textures from:
  assets/kits_photocraft_workspace/03_entregar_editados_aqui/

Accepts inside {wear,pants,shoes,racket,accessory}/:
  <FOLDER>_<tag>.png  (e.g. wear/26_ALC_wear.png, pants/80_CMT_skirt.png, accessory/30_BOR_hairband.png)
  or <FOLDER>.png     (maps to primary slot of that category)
  or bare <PID>.png / <PID>_<tag>.png
Also accepts flat files directly in 03_entregar_editados_aqui/ named <FOLDER>_<tag>.png.

Preserves SEGA's exact original Alpha channel, encodes DXT1/DXT5 with full mipmaps,
recompresses game/archive/HIGH/Player/Model/<PLAYER>.sdo, backs up RGB PNGs to
assets/kits_edited_backup/<FOLDER>/<tag>.png, and writes scratch/imported_kits_audit.png.
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from PIL import Image, ImageDraw

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

from vt4_archive import lzss_decompress
from compress_sega_lzss import lzss_compress_literal
from update_custom_assets import parse_sdo_dds_slots, extract_slot_image, replace_sdo_tex

WS_KITS = os.path.join(REPO_ROOT, "assets", "kits_photocraft_workspace")
CATALOG_PATH = os.path.join(WS_KITS, "01_base_uv_y_referencias", "CATALOGO_57_EQUIPACIONES.json")
DROP_DIR = os.path.join(WS_KITS, "03_entregar_editados_aqui")
BACKUP_DIR = os.path.join(REPO_ROOT, "assets", "kits_edited_backup")
MODEL_DIR = os.path.join(REPO_ROOT, "game", "archive", "HIGH", "Player", "Model")
EXTS = (".png", ".webp", ".tga", ".bmp", ".jpg", ".jpeg")
KIT_CATS = ("wear", "pants", "shoes", "racket", "accessory")


def _match_folder_and_tag(stem: str, catalog: dict, pid_to_folder: dict[str, str], cat_filter: str | None) -> tuple[str, str] | None:
    """Resolve filename stem (with optional _<tag>) to (folder, tag_or_empty)."""
    # Exact folder match or folder + "_" + tag (longest folder prefix first)
    for folder in sorted(catalog.keys(), key=len, reverse=True):
        if stem == folder:
            return (folder, "")
        if stem.startswith(folder + "_"):
            return (folder, stem[len(folder) + 1 :])

    # Bare ID match: 29_91 or 26_ALC or 26_wear
    m = re.match(r"^(29_91|\d{1,3})(?:_(.*))?$", stem)
    if m and m.group(1) in pid_to_folder:
        folder = pid_to_folder[m.group(1)]
        rest = m.group(2) or ""
        return (folder, rest)
    return None


def _select_slot_record(entry: dict, cat: str | None, tag_hint: str) -> dict | None:
    candidates = [s for s in entry["slots"] if cat is None or s["category"] == cat]
    if not candidates:
        return None
    if tag_hint:
        low = tag_hint.lower()
        for s in candidates:
            if s["tag"].lower() == low or s["category"].lower() == low:
                return s
    # Primary slot if exact folder/PID stem was given
    if not tag_hint and len(candidates) >= 1 and cat is not None:
        return candidates[0]
    # Root flat file matching category name as tag
    if len(candidates) == 1:
        return candidates[0]
    return None


def collect_deliverables(catalog: dict, player_filter: str | None, cat_filter: str | None) -> dict[str, list[tuple[dict, str]]]:
    pid_to_folder = {v["pid"]: k for k, v in catalog.items()}
    pid_to_folder.setdefault("29", "29_AG2")
    by_player: dict[str, list[tuple[dict, str]]] = defaultdict(list)
    seen_slots: set[tuple[str, str]] = set()

    def scan_folder(scan_dir: str, cat_ctx: str | None):
        if not os.path.isdir(scan_dir):
            return
        for fn in sorted(os.listdir(scan_dir)):
            full_p = os.path.join(scan_dir, fn)
            if not os.path.isfile(full_p) or not fn.lower().endswith(EXTS):
                continue
            stem = os.path.splitext(fn)[0]
            if stem.upper().startswith("AUDITORIA_"):
                continue
            resolved = _match_folder_and_tag(stem, catalog, pid_to_folder, cat_ctx)
            if not resolved:
                print(f"  [WARN] Unrecognized file in drop dir: {os.path.relpath(full_p, DROP_DIR)}")
                continue
            folder, tag_hint = resolved
            if player_filter and folder != player_filter:
                continue
            slot_rec = _select_slot_record(catalog[folder], cat_ctx, tag_hint)
            if not slot_rec:
                print(f"  [WARN] No matching slot for {folder} tag='{tag_hint}' cat={cat_ctx}: {fn}")
                continue
            if cat_filter and slot_rec["category"] != cat_filter:
                continue
            key = (folder, slot_rec["dds_name"])
            if key in seen_slots:
                continue
            seen_slots.add(key)
            by_player[folder].append((slot_rec, full_p))

    for cat in KIT_CATS:
        scan_folder(os.path.join(DROP_DIR, cat), cat)
    scan_folder(DROP_DIR, None)
    return dict(by_player)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--player", help="Single folder name to import, e.g. 26_ALC")
    ap.add_argument("--category", choices=KIT_CATS, help="Limit import to a single kit category")
    ap.add_argument("--dry-run", action="store_true", help="Validate files without modifying .sdo archives")
    args = ap.parse_args()

    if not os.path.isfile(CATALOG_PATH):
        raise FileNotFoundError(f"Missing {CATALOG_PATH}. Run python -u tools/prepare_kits_photocraft_workspace.py first.")
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    if not os.path.isdir(DROP_DIR):
        print(f"Drop directory not found: {DROP_DIR}")
        return

    deliverables = collect_deliverables(catalog, args.player, args.category)
    if not deliverables:
        print(f"No edited kit images found under {DROP_DIR}. Nothing to import.")
        return

    total_tex = sum(len(v) for v in deliverables.values())
    print(f"Found {total_tex} edited kit texture(s) across {len(deliverables)} player(s).")

    audit_items = []
    for folder in sorted(deliverables.keys()):
        entry = catalog[folder]
        sdo_path = os.path.join(MODEL_DIR, entry["sdo"])
        if not os.path.isfile(sdo_path):
            print(f"  [SKIP] {folder}: missing SDO {sdo_path}")
            continue

        dec = bytearray(lzss_decompress(open(sdo_path, "rb").read()))
        slots_by_name = {s["name"]: s for s in parse_sdo_dds_slots(dec)}
        modified = 0

        for slot_rec, img_path in deliverables[folder]:
            dds_name = slot_rec["dds_name"]
            slot = slots_by_name.get(dds_name)
            if not slot:
                print(f"  [WARN] {folder}: slot {dds_name} not present in {entry['sdo']}")
                continue

            raw_im = Image.open(img_path)
            rgb = Image.merge("RGB", raw_im.convert("RGBA").split()[:3])
            orig_im = extract_slot_image(dec, slot)
            resized_rgb = rgb.resize((slot["w"], slot["h"]), Image.Resampling.LANCZOS)
            new_im = resized_rgb.convert("RGBA")
            new_im.putalpha(orig_im.getchannel("A"))

            if not args.dry_run:
                replace_sdo_tex(dec, slot, new_im)
                modified += 1
                bdir = os.path.join(BACKUP_DIR, folder)
                os.makedirs(bdir, exist_ok=True)
                resized_rgb.save(os.path.join(bdir, f"{slot_rec['tag']}.png"))

            old_rgb = Image.merge("RGB", orig_im.split()[:3])
            audit_items.append((folder, slot_rec["tag"], dds_name, old_rgb, resized_rgb))
            print(
                f"  [OK] {folder:9s} [{slot_rec['tag']:11s}] <- {os.path.basename(img_path)} "
                f"({slot['w']}x{slot['h']} {slot_rec['fourcc']})"
                + (" [dry-run]" if args.dry_run else "")
            )

        if modified > 0 and not args.dry_run:
            with open(sdo_path, "wb") as f:
                f.write(lzss_compress_literal(bytes(dec)))

    if audit_items:
        cols = min(4, len(audit_items))
        rows = (len(audit_items) + cols - 1) // cols
        cw, ch = 360, 196
        sheet = Image.new("RGB", (cols * cw, rows * ch), (20, 22, 28))
        draw = ImageDraw.Draw(sheet)
        for idx, (folder, tag, _dds, old_rgb, new_rgb) in enumerate(audit_items):
            r, c = divmod(idx, cols)
            x0, y0 = c * cw + 6, r * ch + 4
            draw.text((x0, y0), f"{folder} [{tag}] ANTES -> NUEVA", fill=(140, 245, 175))
            o = old_rgb.copy()
            o.thumbnail((166, 166), Image.Resampling.BILINEAR)
            n = new_rgb.copy()
            n.thumbnail((166, 166), Image.Resampling.BILINEAR)
            sheet.paste(o, (x0 + (166 - o.width) // 2, y0 + 22 + (166 - o.height) // 2))
            sheet.paste(n, (x0 + 174 + (166 - n.width) // 2, y0 + 22 + (166 - n.height) // 2))
        out_audit = os.path.join(REPO_ROOT, "scratch", "imported_kits_audit.png")
        os.makedirs(os.path.dirname(out_audit), exist_ok=True)
        sheet.save(out_audit)
        Image.open(out_audit).verify()
        print("Audit sheet written:", out_audit)


if __name__ == "__main__":
    main()
