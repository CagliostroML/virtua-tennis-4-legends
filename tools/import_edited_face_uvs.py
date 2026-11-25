#!/usr/bin/env python3
"""
Import manually / AI+PhotoCraft edited 3D face UV textures from:
  assets/face_uv_photocraft_workspace/03_entregar_editados_aqui/
Accepts files named:
  <FOLDER>.png   (e.g. 26_ALC.png, 29_91_AGA.png, 29_AG2.png, 30_BOR.png)
  or bare <ID>.png (e.g. 26.png, 29_91.png, 29.png -> 29_AG2)

Restores SEGA's exact original AO alpha channel on the face texture, syncs
*_B_body_*.dds skin tone to the new neck (unless --no-sync-body), encodes DXT5
with full mipmaps, recompresses game/archive/HIGH/Player/Model/<PLAYER>.sdo,
and writes scratch/imported_face_uvs_audit.png.
"""
import argparse
import json
import math
import os
import random
import re
import sys
from PIL import Image, ImageDraw, ImageFilter

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

from vt4_archive import lzss_decompress
from compress_sega_lzss import lzss_compress_literal
from update_custom_assets import parse_sdo_dds_slots, extract_slot_image, replace_sdo_tex
from pack_custom_faces import _sync_body_skin

WS_PHOTO = os.path.join(REPO_ROOT, "assets", "face_uv_photocraft_workspace")
DROP_DIR = os.path.join(WS_PHOTO, "03_entregar_editados_aqui")
FACE_WS_DIR = os.path.join(REPO_ROOT, "assets", "face_uv_workspace")
MODEL_DIR = os.path.join(REPO_ROOT, "game", "archive", "HIGH", "Player", "Model")
EXTS = (".png", ".webp", ".tga", ".bmp", ".jpg", ".jpeg")


def _build_pid_to_folder(manifest: dict) -> dict[str, str]:
    mapping = {}
    for folder in sorted(manifest.keys()):
        if folder == "29_91_AGA":
            mapping["29_91"] = folder
        else:
            mapping[folder.split("_")[0]] = folder
    return mapping


def _resolve_folder(filename: str, manifest: dict, pid_map: dict[str, str]) -> str | None:
    stem = os.path.splitext(os.path.basename(filename))[0]
    for candidate in (stem, stem.removesuffix("_uv"), stem.removesuffix("_face")):
        if candidate in manifest:
            return candidate
    m = re.match(r"^(29_91|\d{1,3})(?:_|$)", stem)
    if m and m.group(1) in pid_map:
        return pid_map[m.group(1)]
    return None


def _soften_face_ao_alpha(orig_alpha: Image.Image, sdo_name: str = "") -> Image.Image:
    """Preserve deep cavities (eye sockets, nostrils, mouth, ear holes: a < 90)
    while gently softening donor cheek/jaw/hairline AO shadows (a >= 90).
    Also clears baked forehead visor/headband AO shadow bands on P_W_IVA_IT / P_W_KUZ_IT models."""
    lut = [a if a < 90 else int(a * 0.65 + 255 * 0.35) for a in range(256)]
    out = orig_alpha.point(lut)
    if any(k in sdo_name for k in ("P_W_BAD", "P_W_SEL", "P_W_MUG", "P_W_SAB", "P_W_GRA", "P_W_RYB", "P_W_NAV", "P_W_EVE", "P_W_HAL", "P_W_ASV")):
        w, h = out.size
        px = out.load()
        # Forehead region above eyebrows (y in 0.11..0.33, x in 0.20..0.80): remove donor visor/headband alpha-0 band
        for y in range(int(h * 0.11), int(h * 0.33)):
            for x in range(int(w * 0.20), int(w * 0.80)):
                if px[x, y] < 236:
                    px[x, y] = 236
    return out


# Real-life 8-palette eye color enum for Next-Gen 4x-supersampled HD eyes:
#   ice_blue, blue, blue_green, green, hazel_green, hazel, brown, dark_brown
# Each tuple = (outer_iris_rgb, inner_collarette_rgb, limbal_ring_rgb)
EYE_PALETTES = {
    "ice_blue":    ((68, 96, 122),  (112, 138, 158), (22, 34, 48)),
    "blue":        ((42, 68, 98),   (76, 108, 136),  (16, 26, 44)),
    "steel_blue":  ((46, 70, 96),   (82, 108, 132),  (18, 28, 42)),
    "blue_green":  ((42, 74, 78),   (78, 112, 108),  (16, 30, 34)),
    "green":       ((44, 74, 48),   (82, 108, 70),   (18, 32, 20)),
    "hazel_green": ((58, 74, 44),   (98, 96, 52),    (24, 30, 18)),
    "hazel":       ((92, 70, 36),   (134, 102, 48),  (36, 26, 14)),
    "brown":       ((76, 46, 22),   (122, 78, 38),   (30, 18, 10)),
    "warm_brown":  ((76, 46, 22),   (122, 78, 38),   (30, 18, 10)),
    "dark_brown":  ((48, 28, 15),   (86, 50, 24),    (22, 13, 8)),
}

PLAYER_EYE_COLOR = {
    "26_ALC": "dark_brown",  "27_SIN": "blue",        "28_SAM": "dark_brown",
    "29_91_AGA": "brown",    "29_AG2": "brown",       "30_BOR": "blue",
    "31_MCE": "blue",        "32_GRA": "blue_green",  "33_SER": "dark_brown",
    "34_SWI": "hazel",       "35_SAB": "green",       "36_KUE": "brown",
    "37_NAV": "hazel_green", "38_WAW": "brown",       "39_MED": "brown",
    "40_ZVE": "blue_green",  "41_TSI": "hazel_green", "42_THI": "blue_green",
    "43_KYR": "dark_brown",  "44_HEW": "blue",        "45_SAF": "hazel_green",
    "46_TSO": "dark_brown",  "47_FRR": "brown",       "48_MOY": "brown",
    "49_FER": "dark_brown",  "50_NAL": "brown",       "51_LEN": "hazel_green",
    "52_CON": "brown",       "53_VIL": "dark_brown",  "54_IVN": "hazel_green",
    "55_EVE": "hazel_green", "56_SEL": "brown",       "57_HEN": "hazel_green",
    "58_MUG": "dark_brown",  "59_SHE": "dark_brown",  "60_RUB": "hazel_green",
    "61_RUU": "blue",        "62_FRI": "hazel_green", "63_GAU": "dark_brown",
    "64_RYB": "blue",        "65_BAD": "green",       "66_HAL": "hazel_green",
    "67_COR": "dark_brown",  "68_GAS": "hazel_green", "69_NIS": "dark_brown",
    "70_SOD": "blue",        "71_BER": "blue",        "72_CHN": "dark_brown",
    "73_RIO": "dark_brown",  "74_MUS": "hazel_green", "75_BRU": "dark_brown",
    "76_CRT": "brown",       "77_WLD": "blue",        "78_LAV": "blue",
    "79_ASV": "dark_brown",  "80_CMT": "dark_brown",  "81_CLI": "blue_green",
}


def _upgrade_hd_eyes(dec: bytearray, slots: dict, folder: str, eye_color_override: str | None = None) -> int:
    """Synthesize a 4x-supersampled (512x512 -> 128x128 8-mip DXT5) photorealistic iris, limbal ring,
    pupil, and dual corneal catchlight onto *_B_eye_*.dds while preserving exact donor pupil center
    and outer sclera/caruncle shading."""
    pal_name = eye_color_override if (eye_color_override in EYE_PALETTES) else PLAYER_EYE_COLOR.get(folder, "brown")
    outer_rgb, inner_rgb, limbal_rgb = EYE_PALETTES[pal_name]
    updated = 0
    for sname, eslot in slots.items():
        if "_b_eye" not in sname.lower():
            continue
        orig_eye = extract_slot_image(dec, eslot)
        ew, eh = orig_eye.size
        orig_a = orig_eye.getchannel("A")
        opx = orig_eye.load()

        # Detect exact donor pupil centroid in native coordinates (strict true-black pupil < 75 -> zero vertical drift!)
        dark_pts = [(x, y) for y in range(eh) for x in range(ew) if (opx[x, y][0] + opx[x, y][1] + opx[x, y][2]) < 75]
        if len(dark_pts) < 16:
            dark_pts = [(x, y) for y in range(eh) for x in range(ew) if (opx[x, y][0] + opx[x, y][1] + opx[x, y][2]) < 120]
        if dark_pts:
            cx_n = sum(p[0] for p in dark_pts) / len(dark_pts)
            cy_n = sum(p[1] for p in dark_pts) / len(dark_pts)
        else:
            cx_n, cy_n = ew * 0.5, eh * 0.49

        # Render at 4x supersampled resolution (512x512)
        S = 4
        W, H = ew * S, eh * S
        cx, cy = cx_n * S, cy_n * S
        r_iris = 32.5 * S
        r_pupil = 11.2 * S

        hi = orig_eye.convert("RGB").resize((W, H), Image.Resampling.BICUBIC)
        hpx = hi.load()

        for y in range(max(0, int(cy - r_iris - 12)), min(H, int(cy + r_iris + 12))):
            dy = y - cy
            for x in range(max(0, int(cx - r_iris - 12)), min(W, int(cx + r_iris + 12))):
                dx = x - cx
                r = math.hypot(dx, dy)
                if r > r_iris + 6.0:
                    continue
                br, bg, bb = hpx[x, y]

                if r <= r_pupil:
                    # Deep anti-aliased pupil
                    t_pup = max(0.0, min(1.0, (r - (r_pupil - 3.0)) / 3.0))
                    pr, pg, pb = 8, 8, 10
                    ir = int(pr * (1.0 - t_pup) + inner_rgb[0] * 0.55 * t_pup)
                    ig = int(pg * (1.0 - t_pup) + inner_rgb[1] * 0.55 * t_pup)
                    ib = int(pb * (1.0 - t_pup) + inner_rgb[2] * 0.55 * t_pup)
                else:
                    # Normalized radius inside iris [0..1]
                    u = min(1.0, (r - r_pupil) / max(1.0, r_iris - r_pupil))
                    theta = math.atan2(dy, dx)
                    # Multi-frequency radial stroma fibers
                    f1 = math.cos(theta * 22.0 + math.sin(theta * 5.0) * 0.7)
                    f2 = math.sin(theta * 47.0 - u * 4.0)
                    f3 = math.cos(theta * 89.0)
                    fiber = 0.5 + 0.24 * f1 + 0.16 * f2 + 0.10 * f3
                    # Collarette ring peak around u = 0.34
                    coll = math.exp(-((u - 0.34) / 0.18) ** 2)
                    c_mix = min(1.0, coll * 0.75 + (1.0 - u) * 0.35)
                    base_r = outer_rgb[0] * (1.0 - c_mix) + inner_rgb[0] * c_mix
                    base_g = outer_rgb[1] * (1.0 - c_mix) + inner_rgb[1] * c_mix
                    base_b = outer_rgb[2] * (1.0 - c_mix) + inner_rgb[2] * c_mix
                    scale = 0.72 + 0.62 * fiber
                    ir = base_r * scale
                    ig = base_g * scale
                    ib = base_b * scale

                    # Dark limbal ring at outer iris (u in 0.68..1.00 — anchors light irises naturally!)
                    if u > 0.68:
                        lim_t = min(1.0, (u - 0.68) / 0.30)
                        lim_t = lim_t * (1.4 - 0.4 * lim_t)
                        ir = ir * (1.0 - lim_t * 0.85) + limbal_rgb[0] * (lim_t * 0.85)
                        ig = ig * (1.0 - lim_t * 0.85) + limbal_rgb[1] * (lim_t * 0.85)
                        ib = ib * (1.0 - lim_t * 0.85) + limbal_rgb[2] * (lim_t * 0.85)

                # Upper eyelid ambient occlusion shadow across top of iris/pupil
                if dy < -0.15 * r_iris:
                    lid_ao = max(0.52, 1.0 - 0.45 * min(1.0, (-dy - 0.15 * r_iris) / (0.85 * r_iris)))
                    ir *= lid_ao; ig *= lid_ao; ib *= lid_ao

                # Dual corneal catchlight (primary upper-left window + secondary lower-right bounce)
                d_hl1 = math.hypot(dx - (-0.30 * r_iris), dy - (-0.32 * r_iris))
                if d_hl1 < 0.17 * r_iris:
                    ht = max(0.0, 1.0 - (d_hl1 / (0.17 * r_iris)) ** 2)
                    ir += 235 * ht; ig += 240 * ht; ib += 248 * ht
                d_hl2 = math.hypot(dx - (0.24 * r_iris), dy - (0.26 * r_iris))
                if d_hl2 < 0.095 * r_iris:
                    ht2 = max(0.0, 1.0 - (d_hl2 / (0.095 * r_iris)) ** 2) * 0.55
                    ir += 210 * ht2; ig += 215 * ht2; ib += 225 * ht2

                # Smooth feather into donor sclera at r_iris - 4 .. r_iris + 6
                if r > r_iris - 4.0:
                    edge_t = max(0.0, min(1.0, (r - (r_iris - 4.0)) / 10.0))
                    ir = ir * (1.0 - edge_t) + br * edge_t
                    ig = ig * (1.0 - edge_t) + bg * edge_t
                    ib = ib * (1.0 - edge_t) + bb * edge_t

                hpx[x, y] = (max(0, min(255, int(ir))), max(0, min(255, int(ig))), max(0, min(255, int(ib))))

        out_rgb = hi.resize((ew, eh), Image.Resampling.LANCZOS)
        out_rgba = Image.merge("RGBA", (*out_rgb.split(), orig_a))
        replace_sdo_tex(dec, eslot, out_rgba)
        updated += 1
    return updated


def _make_inner_face_mask(w: int, h: int, strength: float = 0.60) -> Image.Image:
    """Smooth feathered elliptical mask covering the inner face (forehead to chin, cheek to cheek),
    leaving ears/neck/outer hair seams untouched."""
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    x0, y0 = int(w * 0.24), int(h * 0.21)
    x1, y1 = int(w * 0.76), int(h * 0.76)
    draw.ellipse((x0, y0, x1, y1), fill=int(round(255 * strength)))
    return mask.filter(ImageFilter.GaussianBlur(radius=max(4, w // 24)))


def _soften_face_normals(dec: bytearray, slots: dict, new_face_rgb: Image.Image) -> int:
    """Synthesize Next-Gen multi-scale facial relief (medium anatomical contour + fine eyebrow/lip/stubble
    detail + subtle organic skin micro-pore normal grain) onto *_N_face_*.dds & *_N_face_sweat_*.dds,
    and neutralize donor *_SS_face_*.dds cheekbone speculars (55% blur-blend), preserving alpha."""
    sobel_med_x = ImageFilter.Kernel((3, 3), (-1, 0, 1, -2, 0, 2, -1, 0, 1), scale=7, offset=128)
    sobel_med_y = ImageFilter.Kernel((3, 3), (-1, -2, -1, 0, 0, 0, 1, 2, 1), scale=7, offset=128)
    sobel_fine_x = ImageFilter.Kernel((3, 3), (-1, 0, 1, -2, 0, 2, -1, 0, 1), scale=11, offset=128)
    sobel_fine_y = ImageFilter.Kernel((3, 3), (-1, -2, -1, 0, 0, 0, 1, 2, 1), scale=11, offset=128)

    # Pre-build a deterministic 512x512 organic skin micro-pore height map once
    if not hasattr(_soften_face_normals, "_pore_cache"):
        rng = random.Random(20261121)
        pore_raw = bytes(rng.randint(100, 156) for _ in range(512 * 512))
        pore_h = Image.frombytes("L", (512, 512), pore_raw).filter(ImageFilter.GaussianBlur(radius=0.65))
        sobel_pore_x = ImageFilter.Kernel((3, 3), (-1, 0, 1, -2, 0, 2, -1, 0, 1), scale=18, offset=128)
        sobel_pore_y = ImageFilter.Kernel((3, 3), (-1, -2, -1, 0, 0, 0, 1, 2, 1), scale=18, offset=128)
        _soften_face_normals._pore_cache = (pore_h.filter(sobel_pore_x), pore_h.filter(sobel_pore_y))
    pore_gx_512, pore_gy_512 = _soften_face_normals._pore_cache

    updated = 0
    for sname, nslot in slots.items():
        low = sname.lower()
        if "_n_face" in low:
            nw, nh = nslot["w"], nslot["h"]
            orig_n = extract_slot_image(dec, nslot)
            orig_r, orig_g, orig_b, orig_a = orig_n.split()
            orig_rgb = Image.merge("RGB", (orig_r, orig_g, orig_b))

            lum_base = new_face_rgb.convert("L").resize((nw, nh), Image.Resampling.LANCZOS)
            lum_med = lum_base.filter(ImageFilter.GaussianBlur(radius=2.0))
            lum_fine = lum_base.filter(ImageFilter.GaussianBlur(radius=0.55))

            gx_m, gy_m = lum_med.filter(sobel_med_x), lum_med.filter(sobel_med_y)
            gx_f, gy_f = lum_fine.filter(sobel_fine_x), lum_fine.filter(sobel_fine_y)
            pgx = pore_gx_512 if (nw, nh) == (512, 512) else pore_gx_512.resize((nw, nh), Image.Resampling.BILINEAR)
            pgy = pore_gy_512 if (nw, nh) == (512, 512) else pore_gy_512.resize((nw, nh), Image.Resampling.BILINEAR)

            # Combine medium relief + fine detail + organic micro-pore grain around neutral 128
            bx_m, by_m = gx_m.tobytes(), gy_m.tobytes()
            bx_f, by_f = gx_f.tobytes(), gy_f.tobytes()
            bx_p, by_p = pgx.tobytes(), pgy.tobytes()
            gx_bytes = bytes(max(0, min(255, 128 + (m - 128) + (f - 128) + (p - 128))) for m, f, p in zip(bx_m, bx_f, bx_p))
            gy_bytes = bytes(max(0, min(255, 128 + (m - 128) + (f - 128) + (p - 128))) for m, f, p in zip(by_m, by_f, by_p))

            gx = Image.frombytes("L", (nw, nh), gx_bytes)
            gy = Image.frombytes("L", (nw, nh), gy_bytes)
            gz = Image.new("L", (nw, nh), 255)
            target_n_rgb = Image.merge("RGB", (gx, gy, gz))

            mask = _make_inner_face_mask(nw, nh, strength=0.84)
            blended_rgb = Image.composite(target_n_rgb, orig_rgb, mask)
            out_n = Image.merge("RGBA", (*blended_rgb.split(), orig_a))
            replace_sdo_tex(dec, nslot, out_n)
            updated += 1
        elif "_ss_face" in low:
            orig_ss = extract_slot_image(dec, nslot)
            sr, sg, sb, sa = orig_ss.split()
            ss_rgb = Image.merge("RGB", (sr, sg, sb))
            soft_ss = ss_rgb.filter(ImageFilter.GaussianBlur(radius=14))
            blended_ss = Image.blend(ss_rgb, soft_ss, 0.55)
            replace_sdo_tex(dec, nslot, Image.merge("RGBA", (*blended_ss.split(), sa)))
            updated += 1
    return updated


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--player", help="Single folder name to import, e.g. 30_BOR")
    ap.add_argument("--no-sync-body", action="store_true", help="Skip *_B_body_*.dds skin-tone sync")
    ap.add_argument("--dry-run", action="store_true", help="Validate files without modifying .sdo archives")
    args = ap.parse_args()

    manifest_path = os.path.join(FACE_WS_DIR, "manifest.json")
    if not os.path.isfile(manifest_path):
        raise FileNotFoundError(f"Missing {manifest_path}")
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    if not os.path.isdir(DROP_DIR):
        print(f"Drop directory not found: {DROP_DIR}")
        return

    pid_map = _build_pid_to_folder(manifest)
    delivered: dict[str, str] = {}
    for fn in sorted(os.listdir(DROP_DIR)):
        if not fn.lower().endswith(EXTS):
            continue
        folder = _resolve_folder(fn, manifest, pid_map)
        if not folder:
            print(f"  [WARN] Unrecognized filename in drop folder: {fn}")
            continue
        if args.player and folder != args.player:
            continue
        delivered[folder] = os.path.join(DROP_DIR, fn)

    if not delivered:
        print(f"No edited face UV images found in {DROP_DIR}. Nothing to import.")
        return

    print(f"Found {len(delivered)} edited face UV(s): {', '.join(sorted(delivered.keys()))}")
    audit_items = []

    for folder in sorted(delivered.keys()):
        src_img = delivered[folder]
        info = manifest[folder]
        sdo_name = info["sdo"]
        face_slot_name = info["face_slot"]
        sdo_path = os.path.join(MODEL_DIR, sdo_name)
        if not os.path.isfile(sdo_path):
            print(f"  [SKIP] {folder}: missing SDO {sdo_path}")
            continue

        raw_im = Image.open(src_img)
        if raw_im.width < 256 or raw_im.height < 256:
            print(f"  [WARN] {folder}: small texture {raw_im.size}, scaling to {info['face_size']}")

        rgb = Image.merge("RGB", raw_im.convert("RGBA").split()[:3])
        dec = bytearray(lzss_decompress(open(sdo_path, "rb").read()))
        slots = {s["name"]: s for s in parse_sdo_dds_slots(dec)}
        if face_slot_name not in slots:
            print(f"  [SKIP] {folder}: slot {face_slot_name} not found in {sdo_name}")
            continue

        slot = slots[face_slot_name]
        orig_face = extract_slot_image(dec, slot)
        new_face_rgb = rgb.resize((slot["w"], slot["h"]), Image.Resampling.LANCZOS)
        new_face = new_face_rgb.convert("RGBA")
        # Preserve deep cavities (a < 90) while gently softening donor AO shadows (a >= 90) and clearing visor bands
        new_face.putalpha(_soften_face_ao_alpha(orig_face.getchannel("A"), sdo_name))

        body_cnt = 0
        norm_cnt = 0
        eye_cnt = 0
        if not args.dry_run:
            replace_sdo_tex(dec, slot, new_face)
            norm_cnt = _soften_face_normals(dec, slots, new_face_rgb)
            eye_cnt = _upgrade_hd_eyes(dec, slots, folder)
            base_uv_path = os.path.join(FACE_WS_DIR, folder, "00_sega_base_uv.png")
            if not args.no_sync_body and os.path.isfile(base_uv_path):
                base_face = Image.open(base_uv_path).convert("RGBA")
                body_cnt = _sync_body_skin(dec, slots, base_face, new_face)
            with open(sdo_path, "wb") as f:
                f.write(lzss_compress_literal(bytes(dec)))
            # Persist copy into face_uv_workspace/<FOLDER>/edited_face_uv.png so full rebuilds retain it
            os.makedirs(os.path.join(FACE_WS_DIR, folder), exist_ok=True)
            new_face_rgb.save(
                os.path.join(FACE_WS_DIR, folder, "edited_face_uv.png")
            )

        audit_items.append((folder, sdo_name, Image.merge("RGB", orig_face.split()[:3]), new_face_rgb))
        print(
            f"  [OK] {folder:9s} -> {sdo_name:14s} (slot={face_slot_name}, src={raw_im.size}, norm={norm_cnt}, eyes={eye_cnt}, body_synced={body_cnt})"
            + (" [dry-run]" if args.dry_run else "")
        )

    if audit_items:
        cols = min(4, len(audit_items))
        rows = (len(audit_items) + cols - 1) // cols
        cw, ch = 420, 224
        sheet = Image.new("RGB", (cols * cw, rows * ch), (20, 22, 28))
        draw = ImageDraw.Draw(sheet)
        for idx, (folder, sdo_name, old_rgb, new_rgb) in enumerate(audit_items):
            r, c = divmod(idx, cols)
            x0, y0 = c * cw + 6, r * ch + 4
            draw.text((x0, y0), f"{folder} ({sdo_name})  ANTES -> NUEVA", fill=(140, 245, 175))
            sheet.paste(old_rgb.resize((196, 196), Image.Resampling.BILINEAR), (x0, y0 + 20))
            sheet.paste(new_rgb.resize((196, 196), Image.Resampling.BILINEAR), (x0 + 202, y0 + 20))
        out_audit = os.path.join(REPO_ROOT, "scratch", "imported_face_uvs_audit.png")
        os.makedirs(os.path.dirname(out_audit), exist_ok=True)
        sheet.save(out_audit)
        Image.open(out_audit).verify()
        print("Audit sheet written:", out_audit)


if __name__ == "__main__":
    main()
