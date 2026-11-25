#!/usr/bin/env python3
"""
Unified 3D SDO Model Builder for Virtua Tennis 4: Legends & Next-Gen Edition.

Rebuilds ALL 57 custom .sdo + _culling.zml + _deformable.zml models (IDs 26..81 + 29_91/29_06)
with:
  1. Optimal SEGA base .sdo skeleton/mesh/hair/headband/cap per player.
  2. Calibrated 3D bone physique scaling (height, shoulders, chest, arms, thighs, calves).
  3. Iconic prime-era kits, headbands, caps, and hair recoloring.
  4. Exports each player's exact 1024x1024 SEGA base face UV to
     assets/face_uv_workspace/<folder>/00_sega_base_uv.png, and automatically injects
     edited_face_uv.png if present.
"""
import io
import json
import os
import random
import re
import struct
import sys
from PIL import Image, ImageFilter

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

from vt4_archive import BIN0, BIN1, load_directory, read_entry, lzss_decompress
from compress_sega_lzss import lzss_compress_literal
from make_madrid_blue_clay import recolor_dds_blocks
from update_custom_assets import parse_sdo_dds_slots, extract_slot_image, replace_sdo_tex
from uv_face_projector import scale_sdo_bones

MODEL_OUT_DIR = os.path.join(REPO_ROOT, "game", "archive", "HIGH", "Player", "Model")
FACE_WS_DIR = os.path.join(REPO_ROOT, "assets", "face_uv_workspace")


def _tint(r_mul, r_add, g_mul, g_add, b_mul, b_add):
    def fn(r, g, b):
        return (
            max(0, min(255, int(r * r_mul + r_add))),
            max(0, min(255, int(g * g_mul + g_add))),
            max(0, min(255, int(b * b_mul + b_add))),
        )
    return fn


def _solid(rgb):
    return lambda r, g, b: rgb


def _hair_to_rgb(target_rgb, base_lum=0.15, contrast=0.55):
    """Luminance-mapped hair recolorer: lifts dark SEGA hair cleanly to natural blonde/light-brown
    (or darkens blonde bases to natural brunette) without clipping or neon saturation."""
    tr, tg, tb = target_rgb
    inv_base = 1.0 / max(0.05, base_lum)

    def fn(r, g, b):
        lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
        rel = min(1.85, lum * inv_base)
        scale = (1.0 - contrast) + contrast * rel
        return (
            max(0, min(255, int(tr * scale))),
            max(0, min(255, int(tg * scale))),
            max(0, min(255, int(tb * scale))),
        )

    return fn


def physique(h=1.0, chest=1.0, sh=1.0, arm=1.0, thigh=1.0, calf=1.0):
    return {
        "Reference": (h, h, h),
        "Spine": (1.0, chest, chest),
        "Spine1": (1.0, chest * 1.02, chest * 1.02),
        "Spine2": (1.0, chest * 1.04, chest * 1.04),
        "LeftShoulder": (sh, chest, chest),
        "RightShoulder": (sh, chest, chest),
        "LeftArm": (1.0, arm, arm),
        "RightArm": (1.0, arm, arm),
        "LeftForeArm": (1.0, arm * 0.96, arm * 0.96),
        "RightForeArm": (1.0, arm * 0.96, arm * 0.96),
        "LeftUpLeg": (1.0, thigh, thigh),
        "RightUpLeg": (1.0, thigh, thigh),
        "LeftLeg": (1.0, calf, calf),
        "RightLeg": (1.0, calf, calf),
    }


def _apply_agassi_91_special(dec, slots):
    """Agassi '91 (on P_M_RAF_IT): blonde-brown 90s mullet + hot-pink/black Challenge Court headband + neon/denim."""
    for tname, sl in slots.items():
        tl = tname.lower()
        if ("_b_hair_" in tl or "_b_head_" in tl) and "band" not in tl:
            im = extract_slot_image(dec, sl)
            px = im.load()
            w, h = im.size
            for y in range(h):
                t = y / max(1, h - 1)
                for x in range(w):
                    r, g, b, a = px[x, y]
                    if a < 8 and "_b_hair_" in tl:
                        continue
                    lum = (r * 0.3 + g * 0.59 + b * 0.11) / 255.0
                    scale = 0.60 + lum * 1.40
                    px[x, y] = (
                        min(255, int((184 + 36 * t) * scale)),
                        min(255, int((150 + 36 * t) * scale)),
                        min(255, int((84 + 28 * t) * scale)),
                        a,
                    )
            replace_sdo_tex(dec, sl, im)
        elif "_b_accessory_" in tl or "_b_hairband_" in tl or "_b_headband_" in tl:
            im_acc = extract_slot_image(dec, sl)
            apx = im_acc.load()
            for y in range(im_acc.height):
                for x in range(im_acc.width):
                    r, g, b, a = apx[x, y]
                    lum = (r * 0.3 + g * 0.59 + b * 0.11) / 255.0
                    if y % 64 < 18:
                        apx[x, y] = (int(28 + 30 * lum), int(28 + 30 * lum), int(34 + 30 * lum), a)
                    else:
                        apx[x, y] = (min(255, int(190 + 65 * lum)), min(255, int(35 + 45 * lum)), min(255, int(115 + 55 * lum)), a)
            replace_sdo_tex(dec, sl, im_acc)
        elif "_b_wear" in tl:
            im_w = extract_slot_image(dec, sl)
            wpx = im_w.load()
            for y in range(im_w.height):
                for x in range(im_w.width):
                    r, g, b, a = wpx[x, y]
                    lum = (r * 0.3 + g * 0.59 + b * 0.11) / 255.0
                    sat = max(r, g, b) - min(r, g, b)
                    if sat > 45:
                        v = min(255, int(210 + lum * 45))
                        wpx[x, y] = (v, v, v, a)
                    elif lum > 0.72:
                        wpx[x, y] = (235, 38, 128, a)
                    else:
                        wpx[x, y] = (32, 34, 38, a)
            replace_sdo_tex(dec, sl, im_w)
        elif "_b_pants" in tl:
            im_p = extract_slot_image(dec, sl)
            ppx = im_p.load()
            for y in range(im_p.height):
                for x in range(im_p.width):
                    r, g, b, a = ppx[x, y]
                    lum = (r * 0.3 + g * 0.59 + b * 0.11) / 255.0
                    if lum < 0.25:
                        ppx[x, y] = (26, 26, 30, a)
                    else:
                        ppx[x, y] = (min(255, int(68 + lum * 88)), min(255, int(102 + lum * 96)), min(255, int(156 + lum * 82)), a)
            replace_sdo_tex(dec, sl, im_p)


def _apply_agassi_06_special(dec, slots):
    """Agassi '06: smooth bald head (no hair mesh) + flat scalp normal + sleek black/white kit."""
    im_h = Image.new("RGBA", (slots["P_DJV_B_hair_IT.dds"]["w"], slots["P_DJV_B_hair_IT.dds"]["h"]), (0, 0, 0, 0))
    replace_sdo_tex(dec, slots["P_DJV_B_hair_IT.dds"], im_h)

    # If user hasn't supplied a custom AI Studio face UV yet, strip hair from DJV face & add goatee
    im_face = extract_slot_image(dec, slots["P_DJV_B_face_IT.dds"])
    fw, fh = im_face.size
    fpx = im_face.load()
    sr = sg = sb = cnt = 0
    for y in range(280, 330):
        for x in range(430, 590):
            r, g, b, _ = fpx[x, y]
            sr += r; sg += g; sb += b; cnt += 1
    skin_r, skin_g, skin_b = sr // cnt, sg // cnt, sb // cnt
    rng = random.Random(2006)
    for y in range(fh):
        for x in range(fw):
            r, g, b, a = fpx[x, y]
            if ((x - 178) / 48.0) ** 2 + ((y - 455) / 86.0) ** 2 < 1.0 or ((x - 846) / 48.0) ** 2 + ((y - 455) / 86.0) ** 2 < 1.0:
                continue
            is_scalp_top = y < 276
            is_side_hair = (x < 342 or x > 682) and y < 745
            lum = r * 0.3 + g * 0.59 + b * 0.11
            local_k = 1.02 - 0.10 * min(1.0, abs(x - 512) / 512.0) - 0.07 * (1.0 - min(1.0, y / 276.0))
            if (is_scalp_top or is_side_hair) and lum < 142:
                n = rng.randint(-3, 3)
                fpx[x, y] = (
                    max(0, min(255, int(skin_r * local_k + n))),
                    max(0, min(255, int(skin_g * local_k + n))),
                    max(0, min(255, int(skin_b * local_k + n))),
                    a,
                )
            elif is_scalp_top and y > 220:
                blend = min(1.0, (y - 220) / 56.0)
                fpx[x, y] = (
                    int(skin_r * local_k * (1 - blend) + r * blend),
                    int(skin_g * local_k * (1 - blend) + g * blend),
                    int(skin_b * local_k * (1 - blend) + b * blend),
                    a,
                )
            dx_g, dy_g = (x - 512) / 68.0, (y - 682) / 48.0
            if dx_g * dx_g + dy_g * dy_g < 1.0 and y > 628 and rng.random() < 0.72:
                strength = max(0.0, (1.0 - (dx_g * dx_g + dy_g * dy_g) ** 0.5) * 0.55)
                fpx[x, y] = (
                    int(r * (1 - strength) + 54 * strength),
                    int(g * (1 - strength) + 42 * strength),
                    int(b * (1 - strength) + 34 * strength),
                    a,
                )
    im_face.paste(im_face.crop((0, 0, fw, 300)).filter(ImageFilter.GaussianBlur(radius=3.0)), (0, 0))
    replace_sdo_tex(dec, slots["P_DJV_B_face_IT.dds"], im_face)

    im_nface = extract_slot_image(dec, slots["P_DJV_N_face_IT.dds"])
    nfpx = im_nface.load()
    for y in range(int(im_nface.height * 0.26)):
        for x in range(im_nface.width):
            nfpx[x, y] = (128, 128, 255, nfpx[x, y][3])
    replace_sdo_tex(dec, slots["P_DJV_N_face_IT.dds"], im_nface)

    # Charcoal black & white collar kit
    im_w = extract_slot_image(dec, slots["P_DJV_B_wear01_IT.dds"])
    wpx = im_w.load()
    for y in range(im_w.height):
        for x in range(im_w.width):
            r, g, b, a = wpx[x, y]
            lum = (r * 0.3 + g * 0.59 + b * 0.11) / 255.0
            if y < int(im_w.height * 0.12) and int(im_w.width * 0.18) < x < int(im_w.width * 0.32):
                wpx[x, y] = (230, 232, 235, a)
            else:
                v = int(28 + lum * 28)
                wpx[x, y] = (v, v + 1, v + 3, a)
    replace_sdo_tex(dec, slots["P_DJV_B_wear01_IT.dds"], im_w)

    im_p = extract_slot_image(dec, slots["P_DJV_B_pants01_IT.dds"])
    ppx = im_p.load()
    for y in range(im_p.height):
        for x in range(im_p.width):
            r, g, b, a = ppx[x, y]
            lum = (r * 0.3 + g * 0.59 + b * 0.11) / 255.0
            v = int(26 + lum * 26)
            ppx[x, y] = (v, v + 1, v + 3, a)
    replace_sdo_tex(dec, slots["P_DJV_B_pants01_IT.dds"], im_p)

    im_acc = extract_slot_image(dec, slots["P_DJV_B_accessory01_IT.dds"])
    apx = im_acc.load()
    for y in range(im_acc.height):
        for x in range(im_acc.width):
            r, g, b, a = apx[x, y]
            lum = (r * 0.3 + g * 0.59 + b * 0.11) / 255.0
            v = min(255, int(195 + lum * 55))
            apx[x, y] = (v, v, v, a)
    replace_sdo_tex(dec, slots["P_DJV_B_accessory01_IT.dds"], im_acc)


def _apply_sabalenka_special(dec, slots):
    """Sabalenka: crimson Nike dress + dark crimson shorts + honey-brunette ponytail on P_W_KUZ_IT."""
    im_w = extract_slot_image(dec, slots["P_KUZ_B_wear01_IT.dds"])
    wp = im_w.load()
    for y in range(im_w.height):
        for x in range(im_w.width):
            r, g, b, a = wp[x, y]
            lum = int(0.299 * r + 0.587 * g + 0.114 * b)
            if r > g + 45 and r > b + 45:
                wp[x, y] = (max(20, int(r * 0.35)), max(12, int(g * 0.25)), max(12, int(b * 0.25)), a)
            else:
                wp[x, y] = (min(255, int(lum * 0.95 + 48)), max(10, int(lum * 0.18)), max(10, int(lum * 0.18)), a)
    replace_sdo_tex(dec, slots["P_KUZ_B_wear01_IT.dds"], im_w)

    im_p = extract_slot_image(dec, slots["P_KUZ_B_pants_IT.dds"])
    pp = im_p.load()
    for y in range(im_p.height):
        for x in range(im_p.width):
            r, g, b, a = pp[x, y]
            lum = int(0.299 * r + 0.587 * g + 0.114 * b)
            pp[x, y] = (min(255, lum + 95), max(10, lum // 3), max(10, lum // 3), a)
    replace_sdo_tex(dec, slots["P_KUZ_B_pants_IT.dds"], im_p)

    im_acc = extract_slot_image(dec, slots["P_KUZ_B_accessory_IT.dds"])
    ap = im_acc.load()
    for y in range(im_acc.height):
        for x in range(im_acc.width):
            r, g, b, a = ap[x, y]
            if r > 170 and g > 170 and b > 170:
                ap[x, y] = (28, 28, 34, a)
    replace_sdo_tex(dec, slots["P_KUZ_B_accessory_IT.dds"], im_acc)

    im_h = extract_slot_image(dec, slots["P_KUZ_B_hair_IT.dds"])
    hp = im_h.load()
    for y in range(im_h.height):
        for x in range(im_h.width):
            r, g, b, a = hp[x, y]
            hp[x, y] = (min(255, int(r * 1.12)), min(255, int(g * 1.02)), max(0, int(b * 0.85)), a)
    replace_sdo_tex(dec, slots["P_KUZ_B_hair_IT.dds"], im_h)


def _apply_borg_fila_headband(dec, slots):
    """Borg: iconic striped red/white/navy Fila headband on accessory/hairband."""
    for tname, sl in slots.items():
        tl = tname.lower()
        if "_b_hairband_" in tl or "_b_accessory" in tl:
            im_hb = extract_slot_image(dec, sl)
            px = im_hb.load()
            for y in range(im_hb.height):
                band = (y * 5) // im_hb.height
                for x in range(im_hb.width):
                    r, g, b, a = px[x, y]
                    lum = (r * 0.3 + g * 0.59 + b * 0.11) / 255.0
                    k = 0.75 + 0.35 * lum
                    if band in (0, 4):
                        px[x, y] = (min(255, int(225 * k)), min(255, int(225 * k)), min(255, int(230 * k)), a)
                    elif band in (1, 3):
                        px[x, y] = (min(255, int(28 * k)), min(255, int(48 * k)), min(255, int(135 * k)), a)
                    else:
                        px[x, y] = (min(255, int(205 * k)), min(255, int(28 * k)), min(255, int(36 * k)), a)
            replace_sdo_tex(dec, sl, im_hb)


def _apply_navratilova_short_hair(dec, slots):
    """Short 70s/80s bob cut: hide long ponytail slot on KUZ/CHA bases so zero ponytail renders."""
    for tname, sl in slots.items():
        if "_b_hair" in tname.lower() and "band" not in tname.lower():
            replace_sdo_tex(dec, sl, Image.new("RGBA", (sl["w"], sl["h"]), (0, 0, 0, 0)))


# Complete 57-player specification: exact SDO output name, optimal SEGA base, bone physique, and prime kit
PLAYERS_3D = [
    # --- IDs 26..37 + 29_91 ---
    {"folder": "26_ALC", "out": "P_M_ALC_NG", "base": "P_M_DJV_IT",
     "bones": physique(h=0.995, chest=1.06, sh=1.04, arm=1.12, thigh=1.08, calf=1.06),
     "wear_fn": _tint(0.28, 12, 0.85, 85, 1.18, 140), "pants_fn": _solid((26, 32, 48)),
     "acc_fn": _tint(1.15, 110, 0.55, 30, 0.18, 0), "hair_fn": _tint(0.65, 0, 0.62, 0, 0.60, 0)},

    {"folder": "27_SIN", "out": "P_M_SIN_NG", "base": "P_M_MRY_IT",
     "bones": physique(h=1.040, chest=0.90, sh=0.96, arm=0.89, thigh=0.90, calf=0.90),
     "wear_fn": _tint(0.95, 65, 0.72, 45, 0.52, 25), "pants_fn": _tint(0.95, 55, 0.95, 55, 0.96, 58),
     "acc_fn": _tint(1.0, 50, 1.0, 45, 1.0, 45), "hair_fn": _hair_to_rgb((152, 74, 34), base_lum=0.16)},

    {"folder": "28_SAM", "out": "P_M_SAM_LG", "base": "P_M_EDB_SN",
     "bones": physique(h=1.000, chest=1.00, sh=1.02, arm=1.02, thigh=1.00, calf=0.99),
     "wear_fn": _tint(0.92, 55, 0.94, 58, 0.98, 62), "pants_fn": _tint(0.92, 55, 0.94, 58, 0.98, 62),
     "acc_fn": _tint(0.32, 10, 0.42, 15, 0.88, 40), "hair_fn": _tint(0.38, 0, 0.32, 0, 0.28, 0)},

    {"folder": "29_91_AGA", "out": "P_M_AGA_LG", "base": "P_M_NAD_IT",
     "bones": physique(h=0.985, chest=1.06, sh=1.03, arm=1.05, thigh=1.06, calf=1.04),
     "special": _apply_agassi_91_special},

    {"folder": "29_AG2", "out": "P_M_AG2_LG", "base": "P_M_DJV_IT",
     "bones": physique(h=0.985, chest=1.07, sh=1.03, arm=1.06, thigh=1.07, calf=1.05),
     "special": _apply_agassi_06_special},

    {"folder": "30_BOR", "out": "P_M_BOR_LG", "base": "P_M_NAD_IT",
     "bones": physique(h=0.985, chest=0.98, sh=1.00, arm=0.98, thigh=1.00, calf=0.98),
     "wear_fn": _tint(0.96, 48, 0.92, 38, 0.84, 24), "pants_fn": _tint(0.26, 8, 0.36, 14, 0.88, 38),
     "acc_fn": _tint(0.95, 45, 0.92, 35, 0.85, 22), "hair_fn": _hair_to_rgb((172, 140, 76), base_lum=0.145),
     "special": _apply_borg_fila_headband},

    {"folder": "31_MCE", "out": "P_M_MCE_LG", "base": "P_M_DEL_SN",
     "bones": physique(h=0.985, chest=0.97, sh=0.99, arm=0.97, thigh=0.97, calf=0.97),
     "wear_fn": _tint(0.94, 50, 0.95, 52, 0.98, 56), "pants_fn": _tint(0.32, 10, 0.44, 18, 0.98, 48),
     "acc_fn": _tint(1.25, 80, 0.22, 0, 0.22, 0), "hair_fn": _hair_to_rgb((72, 48, 30), base_lum=0.145)},

    {"folder": "32_GRA", "out": "P_W_GRA_LG", "base": "P_W_SHA_SN",
     "bones": physique(h=0.936, chest=0.94, sh=0.97, arm=0.95, thigh=0.96, calf=0.95),
     "wear_fn": _tint(1.0, 52, 1.0, 52, 1.0, 56), "pants_fn": _tint(0.95, 48, 0.95, 48, 0.98, 52),
     "acc_fn": _tint(1.20, 50, 0.22, 0, 0.22, 0), "hair_fn": _tint(1.16, 22, 1.06, 14, 0.68, 0)},

    {"folder": "33_SER", "out": "P_W_SER_NG", "base": "P_W_WIL_SN",
     "bones": physique(h=0.965, chest=1.08, sh=1.05, arm=1.10, thigh=1.12, calf=1.08),
     "wear_fn": _tint(0.72, 45, 0.26, 0, 1.15, 75), "pants_fn": _tint(0.72, 45, 0.26, 0, 1.15, 75),
     "acc_fn": _tint(0.78, 40, 0.24, 0, 1.10, 70), "hair_fn": None},

    {"folder": "34_SWI", "out": "P_W_SWI_NG", "base": "P_W_IVA_IT",
     "bones": physique(h=1.015, chest=1.00, sh=1.00, arm=1.00, thigh=1.02, calf=1.00),
     "wear_fn": _tint(1.15, 65, 0.26, 0, 0.34, 0), "pants_fn": _tint(0.28, 10, 0.36, 14, 0.85, 36),
     "cap_fn": _solid((244, 244, 246)), "acc_fn": _solid((242, 244, 247)), "hair_fn": _hair_to_rgb((92, 54, 28), base_lum=0.145)},

    {"folder": "35_SAB", "out": "P_W_SAB_NG", "base": "P_W_SHA_SN",
     "bones": physique(h=0.985, chest=1.08, sh=1.03, arm=1.10, thigh=1.08, calf=1.05),
     "wear_fn": _tint(1.22, 58, 0.22, 6, 0.24, 8), "pants_fn": _solid((118, 20, 26)),
     "acc_fn": _solid((28, 28, 34)), "hair_fn": _hair_to_rgb((118, 86, 52), base_lum=0.338)},

    {"folder": "36_KUE", "out": "P_M_KUE_LG", "base": "P_M_NAD_IT",
     "bones": physique(h=1.045, chest=0.95, sh=0.98, arm=0.94, thigh=0.95, calf=0.94),
     "wear_fn": _tint(0.22, 0, 0.72, 55, 1.25, 95), "pants_fn": _tint(1.25, 80, 1.12, 65, 0.16, 0),
     "acc_fn": _tint(1.30, 95, 1.18, 75, 0.15, 0), "hair_fn": _hair_to_rgb((78, 54, 34), base_lum=0.145)},

    {"folder": "37_NAV", "out": "P_W_NAV_LG", "base": "P_W_KUZ_IT",
     "bones": physique(h=1.000, chest=1.02, sh=1.02, arm=1.04, thigh=1.02, calf=1.00),
     "wear_fn": _tint(0.92, 48, 0.94, 50, 1.02, 58), "pants_fn": _tint(0.32, 10, 0.48, 20, 0.96, 48),
     "hair_fn": _hair_to_rgb((176, 146, 86), base_lum=0.22), "special": _apply_navratilova_short_hair},

    # --- Page 3 IDs 38..58 ---
    {"folder": "38_WAW", "out": "P_M_WAW_NG", "base": "P_M_HAS_IT",
     "bones": physique(h=0.995, chest=1.10, sh=1.04, arm=1.08, thigh=1.08, calf=1.06),
     "wear_fn": _tint(1.18, 52, 0.26, 6, 0.28, 8), "pants_fn": _tint(0.95, 45, 0.95, 45, 0.96, 48),
     "acc_fn": _tint(0.95, 45, 0.95, 45, 0.95, 45), "hair_fn": _tint(0.58, 0, 0.48, 0, 0.38, 0)},

    {"folder": "39_MED", "out": "P_M_MED_NG", "base": "P_M_EDB_SN",
     "bones": physique(h=1.015, chest=0.88, sh=0.96, arm=0.88, thigh=0.88, calf=0.88),
     "wear_fn": _tint(0.94, 48, 0.95, 50, 0.98, 55), "pants_fn": _tint(0.28, 10, 0.40, 18, 0.92, 45),
     "acc_fn": _tint(0.95, 45, 0.95, 45, 0.95, 45), "hair_fn": _hair_to_rgb((66, 46, 30), base_lum=0.145)},

    {"folder": "40_ZVE", "out": "P_M_ZVE_NG", "base": "P_M_DEL_SN",
     "bones": physique(h=1.015, chest=1.00, sh=1.02, arm=0.98, thigh=0.98, calf=0.96),
     "wear_fn": _tint(0.24, 8, 0.92, 46, 0.90, 44), "pants_fn": _solid((26, 28, 32)),
     "acc_fn": _solid((26, 28, 32)), "hair_fn": _hair_to_rgb((152, 124, 72), base_lum=0.16)},

    {"folder": "41_TSI", "out": "P_M_TSI_NG", "base": "P_M_NAD_IT",
     "bones": physique(h=1.045, chest=1.00, sh=1.02, arm=0.98, thigh=0.98, calf=0.97),
     "wear_fn": _tint(0.94, 46, 0.95, 48, 0.99, 54), "pants_fn": _tint(0.30, 10, 0.52, 24, 1.05, 60),
     "acc_fn": _tint(0.95, 48, 0.96, 50, 0.98, 52), "hair_fn": _hair_to_rgb((138, 102, 62), base_lum=0.145)},

    {"folder": "42_THI", "out": "P_M_THI_NG", "base": "P_M_HAS_IT",
     "bones": physique(h=1.005, chest=1.07, sh=1.02, arm=1.05, thigh=1.10, calf=1.08),
     "wear_fn": _tint(1.22, 65, 0.58, 18, 0.22, 5), "pants_fn": _solid((30, 30, 34)),
     "acc_fn": _solid((30, 30, 34)), "hair_fn": _tint(0.88, 8, 0.72, 0, 0.50, 0)},

    {"folder": "43_KYR", "out": "P_M_KYR_NG", "base": "P_M_DJV_IT",
     "bones": physique(h=0.990, chest=1.00, sh=1.01, arm=1.00, thigh=0.96, calf=0.94),
     "wear_fn": _tint(0.28, 10, 0.28, 10, 0.30, 12), "pants_fn": _tint(0.26, 8, 0.26, 8, 0.28, 10),
     "acc_fn": _tint(0.75, 45, 1.25, 80, 0.20, 5), "hair_fn": _hair_to_rgb((28, 24, 21), base_lum=0.145)},

    {"folder": "44_HEW", "out": "P_M_HEW_LG", "base": "P_M_COU_SN",
     "bones": physique(h=0.947, chest=0.97, sh=0.98, arm=0.97, thigh=0.98, calf=0.98),
     "wear_fn": _tint(1.15, 55, 0.96, 35, 0.22, 5), "pants_fn": _tint(0.28, 8, 0.36, 14, 0.85, 36),
     "acc_fn": _solid((240, 240, 244)), "cap_fn": _solid((240, 240, 244)), "hair_fn": _hair_to_rgb((152, 122, 68), base_lum=0.16)},

    {"folder": "45_SAF", "out": "P_M_SAF_LG", "base": "P_M_MRY_IT",
     "bones": physique(h=0.990, chest=1.05, sh=1.03, arm=1.04, thigh=1.03, calf=1.02),
     "wear_fn": _tint(0.42, 12, 0.44, 12, 0.46, 14), "pants_fn": _solid((28, 28, 32)),
     "acc_fn": _tint(1.15, 55, 0.26, 8, 0.26, 8), "hair_fn": _hair_to_rgb((52, 38, 28), base_lum=0.16)},

    {"folder": "46_TSO", "out": "P_M_TSO_LG", "base": "P_M_DJV_IT",
     "bones": physique(h=0.974, chest=1.10, sh=1.05, arm=1.12, thigh=1.10, calf=1.08),
     "wear_fn": _tint(0.32, 12, 0.48, 22, 1.18, 70), "pants_fn": _tint(0.92, 44, 0.92, 44, 0.96, 48),
     "acc_fn": _tint(1.18, 60, 0.28, 10, 0.30, 10), "hair_fn": _hair_to_rgb((24, 21, 19), base_lum=0.145)},

    {"folder": "47_FRR", "out": "P_M_FRR_LG", "base": "P_M_HAS_IT",
     "bones": physique(h=0.995, chest=0.93, sh=0.97, arm=0.92, thigh=0.94, calf=0.93),
     "wear_fn": _tint(1.18, 55, 0.24, 8, 0.24, 8), "pants_fn": _solid((26, 26, 30)),
     "acc_fn": _solid((28, 28, 32)), "hair_fn": _tint(0.52, 0, 0.44, 0, 0.35, 0)},

    {"folder": "48_MOY", "out": "P_M_MOY_LG", "base": "P_M_DEL_SN",
     "bones": physique(h=1.035, chest=1.02, sh=1.02, arm=1.06, thigh=1.02, calf=1.00),
     "wear_fn": _tint(1.12, 50, 0.28, 10, 0.28, 10), "pants_fn": _tint(0.95, 45, 0.95, 45, 0.96, 48),
     "acc_fn": _solid((240, 240, 244)), "hair_fn": _hair_to_rgb((48, 34, 24), base_lum=0.145)},

    {"folder": "49_FER", "out": "P_M_FER_LG", "base": "P_M_FED_SN",
     "bones": physique(h=0.985, chest=1.00, sh=1.00, arm=1.00, thigh=1.02, calf=1.02),
     "wear_fn": _tint(0.30, 10, 0.45, 18, 0.98, 55), "pants_fn": _solid((26, 32, 48)),
     "acc_fn": _solid((238, 238, 242)), "hair_fn": _hair_to_rgb((52, 36, 24), base_lum=0.16)},

    {"folder": "50_NAL", "out": "P_M_NAL_LG", "base": "P_M_KOH_IT",
     "bones": physique(h=1.010, chest=1.10, sh=1.03, arm=1.06, thigh=1.08, calf=1.06),
     "wear_fn": _tint(0.42, 24, 0.85, 58, 1.22, 85), "pants_fn": _tint(0.94, 46, 0.94, 46, 0.96, 48),
     "acc_fn": _tint(0.95, 45, 0.95, 45, 0.95, 45), "hair_fn": _tint(0.55, 0, 0.45, 0, 0.38, 0)},

    {"folder": "51_LEN", "out": "P_M_LEN_LG", "base": "P_M_EDB_SN",
     "bones": physique(h=1.025, chest=0.97, sh=1.00, arm=0.97, thigh=0.98, calf=0.97),
     "wear_fn": _tint(0.96, 48, 0.96, 48, 0.96, 48), "pants_fn": _tint(0.96, 48, 0.96, 48, 0.96, 48),
     "acc_fn": _tint(0.24, 8, 0.88, 36, 0.45, 18), "hair_fn": _hair_to_rgb((96, 62, 36), base_lum=0.334)},

    {"folder": "52_CON", "out": "P_M_CON_LG", "base": "P_M_GON_SN",
     "bones": physique(h=0.937, chest=0.93, sh=0.96, arm=0.93, thigh=0.94, calf=0.93),
     "wear_fn": _tint(0.94, 46, 0.94, 46, 0.94, 46), "pants_fn": _tint(0.94, 46, 0.94, 46, 0.94, 46),
     "acc_fn": _tint(1.18, 58, 0.28, 10, 0.26, 8), "hair_fn": _hair_to_rgb((96, 68, 44), base_lum=0.16)},

    {"folder": "53_VIL", "out": "P_M_VIL_LG", "base": "P_M_NAD_IT",
     "bones": physique(h=0.985, chest=1.04, sh=1.01, arm=1.05, thigh=1.04, calf=1.02),
     "wear_fn": _tint(0.95, 46, 0.95, 46, 0.96, 48), "pants_fn": _tint(0.28, 8, 0.42, 16, 0.95, 48),
     "acc_fn": _solid((26, 48, 112)), "hair_fn": _hair_to_rgb((38, 28, 22), base_lum=0.145)},

    {"folder": "54_IVN", "out": "P_M_IVN_LG", "base": "P_M_DEL_SN",
     "bones": physique(h=0.990, chest=0.94, sh=0.98, arm=0.94, thigh=0.94, calf=0.93),
     "wear_fn": _tint(0.32, 10, 0.55, 24, 1.15, 65), "pants_fn": _tint(0.94, 46, 0.94, 46, 0.96, 48),
     "acc_fn": _solid((238, 238, 242)), "hair_fn": _hair_to_rgb((66, 48, 32), base_lum=0.16)},

    {"folder": "55_EVE", "out": "P_W_EVE_LG", "base": "P_W_CHA_IT",
     "bones": physique(h=0.970, chest=0.94, sh=0.96, arm=0.94, thigh=0.95, calf=0.94),
     "wear_fn": _tint(0.96, 48, 0.96, 48, 0.98, 52), "pants_fn": _tint(0.32, 10, 0.56, 26, 1.15, 70),
     "hair_fn": _tint(1.18, 25, 1.05, 15, 0.68, 0)},

    {"folder": "56_SEL", "out": "P_W_SEL_LG", "base": "P_W_KUZ_IT",
     "bones": physique(h=0.990, chest=0.97, sh=0.98, arm=0.97, thigh=0.98, calf=0.97),
     "wear_fn": _tint(0.85, 45, 0.28, 8, 1.18, 72), "pants_fn": _tint(0.95, 46, 0.95, 46, 0.96, 48),
     "acc_fn": _solid((238, 238, 242)), "hair_fn": _hair_to_rgb((62, 42, 26), base_lum=0.145)},

    {"folder": "57_HEN", "out": "P_W_HEN_LG", "base": "P_W_IVA_IT",
     "bones": physique(h=0.960, chest=0.95, sh=0.97, arm=0.96, thigh=0.96, calf=0.95),
     "wear_fn": _tint(1.18, 52, 0.30, 8, 0.30, 8), "pants_fn": _solid((28, 28, 32)),
     "acc_fn": _solid((242, 244, 247)), "hair_fn": _hair_to_rgb((124, 88, 48), base_lum=0.145)},

    {"folder": "58_MUG", "out": "P_W_MUG_NG", "base": "P_W_ROB_IT",
     "bones": physique(h=0.978, chest=1.04, sh=1.02, arm=1.03, thigh=1.04, calf=1.03),
     "wear_fn": _tint(0.28, 12, 1.05, 58, 0.85, 42), "pants_fn": _tint(0.95, 46, 0.95, 46, 0.96, 48),
     "acc_fn": _solid((240, 240, 244)), "hair_fn": _hair_to_rgb((36, 26, 20), base_lum=0.145)},

    # --- Page 4 IDs 59..81 ---
    {"folder": "59_SHE", "out": "P_M_SHE_NG", "base": "P_M_MON_SN",
     "bones": physique(h=1.000, chest=1.04, sh=1.03, arm=1.06, thigh=1.04, calf=1.03),
     "wear_fn": _tint(0.26, 10, 0.56, 30, 1.22, 85), "pants_fn": _solid((24, 30, 48)),
     "hair_fn": None},

    {"folder": "60_RUB", "out": "P_M_RUB_NG", "base": "P_M_NAD_IT",
     "bones": physique(h=1.015, chest=0.92, sh=0.98, arm=0.93, thigh=0.93, calf=0.92),
     "wear_fn": _tint(0.30, 12, 0.34, 14, 0.48, 22), "pants_fn": _solid((28, 30, 36)),
     "acc_fn": _solid((238, 238, 242)), "hair_fn": _hair_to_rgb((152, 74, 34), base_lum=0.145)},

    {"folder": "61_RUU", "out": "P_M_RUU_NG", "base": "P_M_DEL_SN",
     "bones": physique(h=0.990, chest=1.02, sh=1.01, arm=1.02, thigh=1.02, calf=1.01),
     "wear_fn": _tint(0.24, 8, 0.92, 44, 0.82, 40), "pants_fn": _solid((24, 34, 58)),
     "acc_fn": _solid((240, 240, 244)), "hair_fn": _hair_to_rgb((134, 106, 62), base_lum=0.161)},

    {"folder": "62_FRI", "out": "P_M_FRI_NG", "base": "P_M_FED_SN",
     "bones": physique(h=1.030, chest=1.02, sh=1.03, arm=1.02, thigh=1.01, calf=1.00),
     "wear_fn": _tint(0.95, 48, 0.96, 48, 0.98, 52), "pants_fn": _solid((24, 34, 58)),
     "acc_fn": _solid((242, 242, 245)), "hair_fn": _hair_to_rgb((54, 38, 26), base_lum=0.161)},

    {"folder": "63_GAU", "out": "P_W_GAU_NG", "base": "P_W_WIL_SN",
     "bones": physique(h=0.965, chest=1.00, sh=1.01, arm=1.02, thigh=1.03, calf=1.01),
     "wear_fn": _tint(1.26, 75, 0.44, 16, 0.42, 16), "pants_fn": _solid((26, 30, 44)),
     "acc_fn": _tint(1.22, 65, 0.50, 18, 0.48, 18), "hair_fn": None},

    {"folder": "64_RYB", "out": "P_W_RYB_NG", "base": "P_W_SHA_SN",
     "bones": physique(h=0.990, chest=0.94, sh=0.97, arm=0.94, thigh=0.94, calf=0.93),
     "wear_fn": _tint(0.84, 42, 1.02, 58, 1.12, 68), "pants_fn": _tint(0.45, 22, 0.95, 52, 1.15, 72),
     "acc_fn": _tint(0.96, 48, 0.96, 48, 0.98, 52), "hair_fn": _hair_to_rgb((62, 40, 24), base_lum=0.338)},

    {"folder": "65_BAD", "out": "P_W_BAD_NG", "base": "P_W_IVA_IT",
     "bones": physique(h=0.990, chest=1.02, sh=1.01, arm=1.02, thigh=1.03, calf=1.01),
     "wear_fn": _tint(1.20, 56, 0.24, 6, 0.28, 8), "pants_fn": _solid((26, 26, 30)),
     "acc_fn": _solid((30, 30, 34)), "hair_fn": _hair_to_rgb((118, 86, 50), base_lum=0.22)},

    {"folder": "66_HAL", "out": "P_W_HAL_NG", "base": "P_W_CHA_IT",
     "bones": physique(h=0.970, chest=0.96, sh=0.97, arm=0.96, thigh=0.98, calf=0.98),
     "wear_fn": _tint(1.20, 58, 0.24, 6, 0.26, 8), "pants_fn": _tint(0.96, 48, 0.96, 48, 0.98, 52),
     "hair_fn": _tint(0.50, 0, 0.42, 0, 0.34, 0)},

    {"folder": "67_COR", "out": "P_M_COR_LG", "base": "P_M_COU_SN",
     "bones": physique(h=0.985, chest=0.95, sh=0.97, arm=0.95, thigh=0.97, calf=0.97),
     "wear_fn": _tint(0.38, 20, 0.82, 55, 1.22, 85), "pants_fn": _solid((24, 34, 58)),
     "acc_fn": _solid((238, 238, 242)), "cap_fn": _solid((242, 242, 246)), "hair_fn": _hair_to_rgb((46, 32, 22), base_lum=0.145)},

    {"folder": "68_GAS", "out": "P_M_GAS_LG", "base": "P_M_VTM_AN",
     "bones": physique(h=0.985, chest=1.00, sh=1.00, arm=1.00, thigh=1.01, calf=1.00),
     "wear_fn": _tint(0.28, 10, 0.48, 22, 1.18, 72), "pants_fn": _tint(0.95, 48, 0.95, 48, 0.98, 52),
     "acc_fn": _tint(1.18, 58, 0.26, 8, 0.28, 8), "hair_fn": _hair_to_rgb((48, 34, 24), base_lum=0.145)},

    {"folder": "69_NIS", "out": "P_M_NIS_LG", "base": "P_M_KOH_IT",
     "bones": physique(h=0.990, chest=0.95, sh=0.97, arm=0.95, thigh=0.96, calf=0.96),
     "wear_fn": _tint(1.20, 56, 0.24, 6, 0.26, 8), "pants_fn": _tint(0.96, 48, 0.96, 48, 0.98, 52),
     "acc_fn": _tint(0.96, 46, 0.96, 46, 0.96, 46), "hair_fn": _tint(0.32, 0, 0.30, 0, 0.30, 0)},

    {"folder": "70_SOD", "out": "P_M_SOD_LG", "base": "P_M_BEC_SN",
     "bones": physique(h=0.990, chest=1.08, sh=1.06, arm=1.06, thigh=1.06, calf=1.04),
     "wear_fn": _tint(0.96, 48, 0.96, 48, 0.98, 52), "pants_fn": _tint(0.28, 10, 0.44, 18, 1.12, 65),
     "acc_fn": _tint(1.18, 55, 1.05, 42, 0.22, 5), "hair_fn": _hair_to_rgb((152, 126, 78), base_lum=0.145)},

    {"folder": "71_BER", "out": "P_M_BER_LG", "base": "P_M_COU_SN",
     "bones": physique(h=1.005, chest=1.05, sh=1.04, arm=1.04, thigh=1.03, calf=1.01),
     "wear_fn": _tint(0.26, 8, 0.38, 16, 0.92, 46), "pants_fn": _tint(0.95, 46, 0.95, 46, 0.97, 50),
     "acc_fn": _solid((240, 240, 244)), "cap_fn": _solid((32, 54, 112)), "hair_fn": _hair_to_rgb((128, 98, 58), base_lum=0.145)},

    {"folder": "72_CHN", "out": "P_M_CHN_LG", "base": "P_M_COU_SN",
     "bones": physique(h=0.980, chest=0.96, sh=0.98, arm=0.96, thigh=1.00, calf=1.02),
     "wear_fn": _tint(0.96, 48, 0.96, 48, 0.98, 52), "pants_fn": _tint(0.22, 8, 0.72, 36, 0.85, 44),
     "acc_fn": _solid((242, 242, 246)), "cap_fn": _solid((244, 244, 248)), "hair_fn": _hair_to_rgb((24, 21, 19), base_lum=0.145)},

    {"folder": "73_RIO", "out": "P_M_RIO_LG", "base": "P_M_RAF_IT",
     "bones": physique(h=0.970, chest=0.95, sh=0.97, arm=0.95, thigh=0.97, calf=0.97),
     "wear_fn": _tint(0.94, 46, 0.94, 46, 0.96, 48), "pants_fn": _solid((28, 28, 34)),
     "acc_fn": _tint(1.18, 56, 0.26, 8, 0.28, 8), "hair_fn": _tint(0.40, 0, 0.34, 0, 0.30, 0)},

    {"folder": "74_MUS", "out": "P_M_MUS_LG", "base": "P_M_HAS_IT",
     "bones": physique(h=0.975, chest=1.08, sh=1.04, arm=1.08, thigh=1.09, calf=1.12),
     "wear_fn": _tint(0.85, 50, 1.25, 80, 0.20, 5), "pants_fn": _tint(0.95, 48, 0.95, 48, 0.98, 52),
     "acc_fn": _tint(0.95, 45, 0.95, 45, 0.95, 45), "hair_fn": _hair_to_rgb((118, 88, 54), base_lum=0.16)},

    {"folder": "75_BRU", "out": "P_M_BRU_LG", "base": "P_M_EDB_SN",
     "bones": physique(h=1.010, chest=0.94, sh=0.98, arm=0.94, thigh=0.94, calf=0.94),
     "wear_fn": _tint(0.95, 48, 0.97, 50, 0.95, 48), "pants_fn": _solid((24, 34, 62)),
     "acc_fn": _tint(0.24, 8, 0.92, 42, 0.46, 18), "hair_fn": _tint(0.48, 0, 0.40, 0, 0.34, 0)},

    {"folder": "76_CRT", "out": "P_M_CRT_LG", "base": "P_M_HAS_IT",
     "bones": physique(h=0.980, chest=1.01, sh=1.00, arm=1.00, thigh=1.01, calf=1.00),
     "wear_fn": _tint(0.26, 8, 0.40, 16, 0.95, 48), "pants_fn": _tint(0.95, 48, 0.95, 48, 0.97, 50),
     "acc_fn": _tint(0.95, 46, 0.95, 46, 0.95, 46), "hair_fn": _tint(0.45, 0, 0.38, 0, 0.32, 0)},

    {"folder": "77_WLD", "out": "P_M_WLD_LG", "base": "P_M_DEL_SN",
     "bones": physique(h=0.990, chest=0.94, sh=0.98, arm=0.94, thigh=0.95, calf=0.95),
     "wear_fn": _tint(0.96, 48, 0.96, 48, 0.98, 52), "pants_fn": _tint(0.26, 8, 0.38, 16, 0.92, 46),
     "acc_fn": _solid((26, 48, 112)), "hair_fn": _hair_to_rgb((136, 108, 62), base_lum=0.145)},

    {"folder": "78_LAV", "out": "P_M_LAV_LG", "base": "P_M_BEC_SN",
     "bones": physique(h=0.910, chest=0.94, sh=0.97, arm=0.96, thigh=0.95, calf=0.95),
     "wear_fn": _tint(0.98, 52, 0.98, 52, 0.98, 52), "pants_fn": _tint(0.98, 52, 0.98, 52, 0.98, 52),
     "acc_fn": _tint(0.96, 48, 0.96, 48, 0.96, 48), "hair_fn": _hair_to_rgb((138, 66, 36), base_lum=0.504)},

    {"folder": "79_ASV", "out": "P_W_ASV_LG", "base": "P_W_IVA_IT",
     "bones": physique(h=0.975, chest=0.98, sh=0.98, arm=0.98, thigh=1.00, calf=1.00),
     "wear_fn": _tint(1.22, 58, 0.26, 6, 0.22, 4), "pants_fn": _tint(0.96, 48, 0.96, 48, 0.98, 50),
     "acc_fn": _solid((242, 244, 247)), "hair_fn": _hair_to_rgb((56, 36, 22), base_lum=0.145)},

    {"folder": "80_CMT", "out": "P_W_CMT_LG", "base": "P_W_ROB_IT",
     "bones": physique(h=0.965, chest=0.98, sh=0.98, arm=0.98, thigh=0.99, calf=0.99),
     "wear_fn": _tint(0.96, 48, 0.96, 48, 0.98, 52), "pants_fn": _solid((26, 36, 68)),
     "acc_fn": _tint(0.96, 48, 0.96, 48, 0.96, 48), "hair_fn": _tint(0.45, 0, 0.38, 0, 0.32, 0)},

    {"folder": "81_CLI", "out": "P_W_CLI_LG", "base": "P_W_ROB_IT",
     "bones": physique(h=0.980, chest=1.03, sh=1.02, arm=1.03, thigh=1.04, calf=1.02),
     "wear_fn": _tint(1.20, 56, 0.24, 6, 0.28, 8), "pants_fn": _solid((26, 26, 30)),
     "acc_fn": _tint(1.22, 55, 1.02, 40, 0.22, 5), "hair_fn": _hair_to_rgb((174, 142, 82), base_lum=0.208)},

    {"folder": "82_AND", "out": "P_W_AND_NG", "base": "P_W_IVA_IT",
     "bones": physique(h=0.985, chest=0.95, sh=0.97, arm=0.95, thigh=0.96, calf=0.96),
     "wear_fn": _tint(0.84, 48, 1.08, 62, 0.98, 56), "pants_fn": _tint(0.94, 48, 0.96, 50, 0.96, 50),
     "acc_fn": _solid((244, 244, 246)), "hair_fn": _hair_to_rgb((184, 160, 126), base_lum=0.32)},

    {"folder": "83_BJK", "out": "P_W_BJK_LG", "base": "P_W_KUZ_IT",
     "bones": physique(h=0.955, chest=0.97, sh=0.98, arm=0.98, thigh=0.98, calf=0.98),
     "wear_fn": _tint(0.96, 50, 0.96, 50, 0.98, 54), "pants_fn": _solid((28, 42, 78)),
     "hair_fn": _hair_to_rgb((82, 56, 36), base_lum=0.22), "special": _apply_navratilova_short_hair},
]


def _find_face_slot(slots):
    for name, sl in slots.items():
        if "_b_face" in name.lower():
            return sl
    return None


def main():
    os.makedirs(MODEL_OUT_DIR, exist_ok=True)
    os.makedirs(FACE_WS_DIR, exist_ok=True)

    # Seed Sabalenka's already-tested UV prototype into 35_SAB/edited_face_uv.png if not yet present
    sab_proto = os.path.join(REPO_ROOT, "scratch", "sab_face_uv_test.png")
    sab_ws_edit = os.path.join(FACE_WS_DIR, "35_SAB", "edited_face_uv.png")
    if os.path.exists(sab_proto) and not os.path.exists(sab_ws_edit):
        os.makedirs(os.path.dirname(sab_ws_edit), exist_ok=True)
        Image.open(sab_proto).convert("RGBA").save(sab_ws_edit)

    entries = load_directory()
    cache = {}
    raw_cache = {}
    manifest = {}

    with open(BIN0, "rb") as f0, open(BIN1, "rb") as f1:
        for spec in PLAYERS_3D:
            base = spec["base"]
            out_stem = spec["out"]
            zml_out_prefix = out_stem[:7]  # e.g. P_M_ALC
            base_zml_prefix = base[:7]

            if base not in raw_cache:
                e_sdo = next(x for x in entries if x["name"].lower() == f"high/player/model/{base.lower()}.sdo")
                raw_cache[base] = lzss_decompress(read_entry(entries, e_sdo, f0, f1, cache))

            dec = bytearray(raw_cache[base])
            slots = {s["name"]: s for s in parse_sdo_dds_slots(dec)}

            # Export exact 1024x1024 base SEGA face UV for the user's face workspace
            ws_dir = os.path.join(FACE_WS_DIR, spec["folder"])
            os.makedirs(ws_dir, exist_ok=True)
            face_slot = _find_face_slot(slots)
            if face_slot:
                base_face_im = extract_slot_image(dec, face_slot)
                base_face_im.save(os.path.join(ws_dir, "00_sega_base_uv.png"))

            # Apply kit / hair / headband recolors first, then any special pixel/UV painters
            tweaks = 0
            pos = 0
            while True:
                pos = dec.find(b"DDS ", pos)
                if pos < 0:
                    break
                ctx = bytes(dec[max(0, pos - 48) : pos]).lower()
                sz = struct.unpack(">I", dec[pos - 4 : pos])[0]
                fn = None
                if b"_b_wear" in ctx and spec.get("wear_fn"):
                    fn = spec["wear_fn"]
                elif (b"_b_pants" in ctx or b"_b_inner" in ctx or b"_b_bottom" in ctx) and spec.get("pants_fn"):
                    fn = spec["pants_fn"]
                elif (b"_b_accessory" in ctx or b"_b_headband" in ctx or b"_b_hairband" in ctx or b"_b_band" in ctx) and spec.get("acc_fn"):
                    fn = spec["acc_fn"]
                elif b"_b_cap" in ctx and spec.get("cap_fn"):
                    fn = spec["cap_fn"]
                elif (b"_b_hair" in ctx or b"_b_hairtop" in ctx or b"_b_head" in ctx) and b"hairband" not in ctx and b"headband" not in ctx and spec.get("hair_fn"):
                    fn = spec["hair_fn"]
                if fn is not None:
                    dec[pos : pos + sz] = recolor_dds_blocks(bytes(dec[pos : pos + sz]), fn)
                    tweaks += 1
                pos += 4

            if "special" in spec:
                spec["special"](dec, slots)
                tweaks += 1

            # Inject edited_face_uv.png if user already generated one for this player
            custom_face_path = os.path.join(ws_dir, "edited_face_uv.png")
            has_custom_face = False
            if face_slot and os.path.exists(custom_face_path):
                cf = Image.open(custom_face_path).convert("RGBA").resize((face_slot["w"], face_slot["h"]), Image.Resampling.LANCZOS)
                # Preserve SEGA's exact original alpha channel on the face UV
                orig_a = extract_slot_image(dec, face_slot).getchannel("A")
                cf.putalpha(orig_a)
                replace_sdo_tex(dec, face_slot, cf)
                has_custom_face = True

            # Apply 3D physique bone scaling
            scaled = scale_sdo_bones(dec, spec["bones"])

            # Compress and write .sdo + .zml
            comp = lzss_compress_literal(bytes(dec))
            with open(os.path.join(MODEL_OUT_DIR, f"{out_stem}.sdo"), "wb") as f:
                f.write(comp)
            for suffix in ("_culling.zml", "_deformable.zml"):
                ez = next(x for x in entries if x["name"].lower() == f"high/player/model/{base_zml_prefix.lower()}{suffix}")
                with open(os.path.join(MODEL_OUT_DIR, f"{zml_out_prefix}{suffix}"), "wb") as f:
                    f.write(read_entry(entries, ez, f0, f1, cache))

            manifest[spec["folder"]] = {
                "sdo": f"{out_stem}.sdo",
                "base_sega_sdo": f"{base}.sdo",
                "face_slot": face_slot["name"] if face_slot else None,
                "face_size": [face_slot["w"], face_slot["h"]] if face_slot else None,
                "has_edited_face": has_custom_face,
                "bones_scaled": scaled,
                "height_scale": spec["bones"]["Reference"][0],
            }
            print(f"[{spec['folder']:9s}] {out_stem}.sdo <- {base} | bones={scaled}/14 | tex={tweaks} | face={'CUSTOM' if has_custom_face else 'base'}")

    with open(os.path.join(FACE_WS_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"\nBuilt all {len(PLAYERS_3D)} SDO models and exported UV workspace manifest!")


if __name__ == "__main__":
    main()
