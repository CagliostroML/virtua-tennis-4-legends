#!/usr/bin/env python3
"""
Update custom portraits, eye-strips, photo_S, and upgraded 3D models (.sdo + .zml)
for Virtua Tennis 4: Legends & Next-Gen Edition.

Generates:
  1. Fixed Wawrinka portrait notch (game/archive/HIGH/Frontend/VR/photo_L/38.dds)
  2. Grid mini eye-strips for ALL 59 roster IDs 0..58 (game/archive/HIGH/Frontend/VR/photo_eye/{0..58}.dds)
  3. Match HUD small portraits 26..58 (game/archive/HIGH/Frontend/VR/photo_S/{26..58}.dds)
  4. Upgraded 3D player models:
     - P_M_AGA_LG.sdo (Agassi '91: blonde mullet + hot-pink headband + 90s Challenge Court denim/neon kit on P_M_NAD_IT)
     - P_M_AG2_LG.sdo (+ _culling/_deformable.zml) (Agassi '06: bald head + goatee + sleek black/white kit on P_M_DJV_IT)
     - P_W_SAB_NG.sdo (+ _culling/_deformable.zml) (Sabalenka: crimson red tank dress + honey-brown high ponytail on P_W_SHA_SN)
"""
import io
import os
import random
import re
import struct
import sys
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

from vt4_archive import BIN0, BIN1, load_directory, read_entry, lzss_decompress
from compress_sega_lzss import lzss_compress_literal
from dxt_codec import encode_dds, encode_dxt1_payload, encode_dxt5_payload

PHOTO_L_DIR = os.path.join(REPO_ROOT, "game", "archive", "HIGH", "Frontend", "VR", "photo_L")
PHOTO_S_DIR = os.path.join(REPO_ROOT, "game", "archive", "HIGH", "Frontend", "VR", "photo_S")
PHOTO_EYE_DIR = os.path.join(REPO_ROOT, "game", "archive", "HIGH", "Frontend", "VR", "photo_eye")
MODEL_DIR = os.path.join(REPO_ROOT, "game", "archive", "HIGH", "Player", "Model")
SCRATCH_DIR = r"C:\Users\acorr\.gemini\antigravity\brain\b7dada32-9382-44f8-87e7-4bcc74c92a1c\scratch"


def fix_wawrinka_portrait():
    """Patch tiny diagonal forehead cutout notch on left side of Wawrinka's hair/temple."""
    p38 = os.path.join(PHOTO_L_DIR, "38.dds")
    im = Image.open(p38).convert("RGBA")
    w, h = im.size
    px = im.load()

    # Scan inward from center (x=140) leftwards so stray cutout specks on forehead don't break edge
    fixed = 0
    for y in range(15, 56):
        x_left = 140
        while x_left > 82 and px[x_left - 1, y][3] > 180:
            x_left -= 1
        target_left = max(86, int(93 + (y - 36) ** 2 * 0.032 - (y - 32) * 0.22))
        if y < 22:
            target_left = 97 + (22 - y)
        if x_left > target_left:
            for x in range(target_left, x_left + 1):
                sx = min(w - 1, x_left + 5)
                sy = min(h - 1, y + 3)
                sr, sg, sb, _ = px[sx, sy]
                if y < 38:
                    sr = int(sr * 0.45 + 64 * 0.55)
                    sg = int(sg * 0.45 + 46 * 0.55)
                    sb = int(sb * 0.45 + 34 * 0.55)
                dist = x - target_left
                alpha = 255 if dist >= 2 else (195 if dist == 1 else 105)
                px[x, y] = (sr, sg, sb, alpha)
                fixed += 1
    if fixed > 0:
        open(p38, "wb").write(encode_dds(im, b"RGBA"))
        print(f"Fixed Wawrinka 38.dds forehead notch ({fixed} px filled)")
    else:
        print("Wawrinka 38.dds already clean")


def make_eyestrip(im: Image.Image) -> Image.Image:
    """Create a 256x64 dark-contrast eye-strip thumbnail centered on the player's eyes."""
    rgba = im.convert("RGBA")
    w, h = rgba.size
    px = rgba.load()

    # Find true head crown top: first row where contiguous opaque span >= 26 px (skips raised racket/cap tip)
    y_head_top = None
    row_spans = []
    for y in range(h):
        xs = [x for x in range(w) if px[x, y][3] > 90]
        span = (max(xs) - min(xs) + 1) if len(xs) >= 20 else 0
        row_spans.append((xs, span))
        if y_head_top is None and span >= 28:
            y_head_top = y
    if y_head_top is None:
        y_head_top = 8

    ey1 = max(0, y_head_top + 18)
    ey2 = min(h, y_head_top + 60)
    xs_head = []
    for y in range(ey1, ey2):
        xs, _ = row_spans[y]
        if xs:
            xs_head.append((min(xs) + max(xs)) * 0.5)
    cx = int(sum(xs_head) / len(xs_head)) if xs_head else w // 2
    head_w = max([row_spans[y][1] for y in range(ey1, ey2)] or [72])

    # Crop tight 3.6:1 eye-band centered on eyes (38..58 px below crown)
    crop_w = max(92, min(w, int(head_w * 1.95)))
    crop_h = max(24, int(crop_w * 64 / 256))
    cy = y_head_top + int(max(36, min(58, head_w * 0.60)))
    x1 = max(0, min(w - crop_w, cx - crop_w // 2))
    y1 = max(0, min(h - crop_h, cy - crop_h // 2))
    band = rgba.crop((x1, y1, x1 + crop_w, y1 + crop_h)).resize((256, 64), Image.LANCZOS)

    bg = Image.new("RGBA", (256, 64), (36, 40, 48, 255))
    comp = Image.alpha_composite(bg, band)
    comp = ImageEnhance.Brightness(comp).enhance(0.68)
    comp = ImageEnhance.Contrast(comp).enhance(1.12)
    cpx = comp.load()
    for x in range(44):
        k = 0.52 + 0.48 * (x / 44.0)
        for y in range(64):
            r, g, b, _ = cpx[x, y]
            cpx[x, y] = (int(r * k), int(g * k), int(b * k), 255)
    return comp


def build_portraits_and_eyestrips(entries, f0, f1, cache):
    os.makedirs(PHOTO_EYE_DIR, exist_ok=True)
    os.makedirs(PHOTO_S_DIR, exist_ok=True)

    for cid in range(59):
        disk_pL = os.path.join(PHOTO_L_DIR, f"{cid}.dds")
        if os.path.exists(disk_pL):
            im = Image.open(disk_pL)
        else:
            e = [x for x in entries if x["name"] == f"HIGH/Frontend/VR/photo_L/{cid}.dds"][0]
            raw = read_entry(entries, e, f0, f1, cache)
            im = Image.open(io.BytesIO(raw))

        # Write 256x64 BGRA eye-strip for ALL 0..58
        eye = make_eyestrip(im)
        open(os.path.join(PHOTO_EYE_DIR, f"{cid}.dds"), "wb").write(encode_dds(eye, b"RGBA"))

        # Write 128x64 DXT5 photo_S for custom players 26..58 (replaces SEGA World Tour NPC faces in Match HUD/Brackets)
        if cid >= 26:
            # Square/wide crop upper chest & face into 128x64 DXT5 with grey/transparent corners
            rgba = im.convert("RGBA")
            w, h = rgba.size
            px = rgba.load()
            ys = [y for y in range(h) if any(px[x, y][3] > 60 for x in range(w))]
            y_top = ys[0] if ys else 0
            crop_h = min(h - y_top, max(96, int((h - y_top) * 0.58)))
            sub = rgba.crop((0, y_top, w, y_top + crop_h)).resize((128, 64), Image.LANCZOS)
            bg = Image.new("RGBA", (128, 64), (176, 178, 182, 255))
            s_comp = Image.alpha_composite(bg, sub)
            # Rounded corner alpha matching SEGA photo_S
            spx = s_comp.load()
            for y in range(64):
                for x in range(128):
                    a = 255
                    if x < 4 or x > 123:
                        dy = abs(y - 31.5)
                        if dy > 22:
                            a = 0
                    spx[x, y] = (spx[x, y][0], spx[x, y][1], spx[x, y][2], a)
            open(os.path.join(PHOTO_S_DIR, f"{cid}.dds"), "wb").write(encode_dds(s_comp, b"DXT5"))

    print("Generated 59 eye-strips in photo_eye/ (0..58) and 33 Match portraits in photo_S/ (26..58)")


def parse_sdo_dds_slots(dec: bytes):
    offs = [m.start() for m in re.finditer(b"DDS ", dec)]
    slots = []
    for i, off in enumerate(offs):
        h, w, pitch, depth, mips = struct.unpack_from("<IIIII", dec, off + 12)
        mips = max(1, mips)
        fourcc = dec[off + 84 : off + 88]
        strs = re.findall(b"[A-Za-z0-9_.]{4,40}", dec[max(0, off - 96) : off])
        tname = strs[-1].decode("ascii", "replace") if strs else f"tex_{i}"
        # compute exact payload size across mips
        bs = 8 if fourcc == b"DXT1" else 16
        mw, mh = w, h
        payload_sz = 0
        for _ in range(mips):
            payload_sz += max(1, (mw + 3) // 4) * max(1, (mh + 3) // 4) * bs
            mw = max(1, mw // 2)
            mh = max(1, mh // 2)
        slots.append({
            "idx": i, "off": off, "w": w, "h": h, "mips": mips,
            "fourcc": fourcc, "name": tname, "total_sz": 128 + payload_sz
        })
    return slots


def replace_sdo_tex(dec_ba: bytearray, slot: dict, img: Image.Image):
    """Replace DDS payload inside decompressed .sdo while preserving EXACT byte size and mipmap count.
    Resizes RGB and Alpha channels independently so PIL's premultiplied RGBA resize never zeros RGB
    to black (or creates Lanczos ringing) where SEGA's AO/cavity alpha channel is 0.
    """
    w, h, mips, fcc = slot["w"], slot["h"], slot["mips"], slot["fourcc"]
    assert fcc in (b"DXT1", b"DXT5"), f"Unsupported fourcc {fcc}"
    enc_fn = encode_dxt1_payload if fcc == b"DXT1" else encode_dxt5_payload
    rgba = img.convert("RGBA")
    r0, g0, b0, a0 = rgba.split()
    base_rgb = Image.merge("RGB", (r0, g0, b0))
    if base_rgb.size != (w, h):
        base_rgb = base_rgb.resize((w, h), Image.LANCZOS)
        base_a = a0.resize((w, h), Image.LANCZOS)
    else:
        base_a = a0
    payload = bytearray()
    mw, mh = w, h
    for _ in range(mips):
        if (mw, mh) == (w, h):
            mrgb, ma = base_rgb, base_a
        else:
            mrgb = base_rgb.resize((mw, mh), Image.LANCZOS)
            ma = base_a.resize((mw, mh), Image.LANCZOS)
        mimg = Image.merge("RGBA", (*mrgb.split(), ma))
        payload.extend(enc_fn(mimg))
        mw = max(1, mw // 2)
        mh = max(1, mh // 2)
    expected = slot["total_sz"] - 128
    assert len(payload) == expected, f"Size mismatch for {slot['name']}: {len(payload)} != {expected}"
    p_start = slot["off"] + 128
    dec_ba[p_start : p_start + expected] = payload


def extract_slot_image(dec: bytes, slot: dict) -> Image.Image:
    return Image.open(io.BytesIO(dec[slot["off"] : slot["off"] + slot["total_sz"]])).convert("RGBA")


def build_agassi_91_sdo(entries, f0, f1, cache):
    """Agassi '91 (Melena rubia + cinta + Challenge Court neon/denim) on P_M_NAD_IT."""
    e = [x for x in entries if x["name"] == "HIGH/Player/Model/P_M_NAD_IT.sdo"][0]
    dec = bytearray(lzss_decompress(read_entry(entries, e, f0, f1, cache)))
    slots = {s["name"]: s for s in parse_sdo_dds_slots(dec)}

    # 1. Hair + Scalp -> sun-bleached 90s golden blonde with subtle root depth
    for tname in ["P_NAD_B_hair_IT.dds", "P_NAD_B_head_IT.dds"]:
        im = extract_slot_image(dec, slots[tname])
        px = im.load()
        w, h = im.size
        for y in range(h):
            # darker warm-gold near roots (top), bright bleached blonde toward tips (bottom)
            t = y / max(1, h - 1)
            for x in range(w):
                r, g, b, a = px[x, y]
                if a < 8 and tname == "P_NAD_B_hair_IT.dds":
                    continue
                lum = (r * 0.3 + g * 0.59 + b * 0.11) / 255.0
                scale = 0.55 + lum * 1.45
                nr = min(255, int((195 + 45 * t) * scale))
                ng = min(255, int((162 + 44 * t) * scale))
                nb = min(255, int((90 + 36 * t) * scale))
                px[x, y] = (nr, ng, nb, a)
        replace_sdo_tex(dec, slots[tname], im)

    # 2. Face hairline + lighten eyebrows/stubble toward blonde/warm-brown
    im_face = extract_slot_image(dec, slots["P_NAD_B_face_IT.dds"])
    fpx = im_face.load()
    fw, fh = im_face.size
    for y in range(fh):
        for x in range(fw):
            r, g, b, a = fpx[x, y]
            # dark hair pixels near hairline/temples (top & outer sides, avoiding eyes/mouth/nose)
            is_crown = y < int(fh * 0.24)
            is_temple = (x < int(fw * 0.26) or x > int(fw * 0.74)) and y < int(fh * 0.56)
            if (is_crown or is_temple) and r < 95 and g < 85 and b < 78:
                lum = (r + g + b) / (3.0 * 95.0)
                nr = min(240, int(175 + lum * 55))
                ng = min(215, int(145 + lum * 50))
                nb = min(150, int(85 + lum * 35))
                fpx[x, y] = (nr, ng, nb, a)
    replace_sdo_tex(dec, slots["P_NAD_B_face_IT.dds"], im_face)

    # 3. Accessory (wide headband & wristbands) -> 90s hot pink / black stripe Challenge Court
    im_acc = extract_slot_image(dec, slots["P_NAD_B_accessory_IT.dds"])
    apx = im_acc.load()
    aw, ah = im_acc.size
    for y in range(ah):
        for x in range(aw):
            r, g, b, a = apx[x, y]
            lum = (r * 0.3 + g * 0.59 + b * 0.11) / 255.0
            # hot magenta/pink with high-contrast shading
            if y % 64 < 18:
                apx[x, y] = (int(28 + 30 * lum), int(28 + 30 * lum), int(34 + 30 * lum), a)
            else:
                apx[x, y] = (min(255, int(190 + 65 * lum)), min(255, int(35 + 45 * lum)), min(255, int(115 + 55 * lum)), a)
    replace_sdo_tex(dec, slots["P_NAD_B_accessory_IT.dds"], im_acc)

    # 4. Shirt (wearN01) -> Crisp 90s white base with hot pink / acid lime / black Challenge Court stripes
    im_w = extract_slot_image(dec, slots["P_NAD_B_wearN01_IT.dds"])
    wpx = im_w.load()
    ww, wh = im_w.size
    for y in range(wh):
        for x in range(ww):
            r, g, b, a = wpx[x, y]
            lum = (r * 0.3 + g * 0.59 + b * 0.11) / 255.0
            # Notice Nadal shirt already has horizontal stripes in its UV! Keep contrast on stripes as hot pink / black
            sat = max(r, g, b) - min(r, g, b)
            if sat > 45:
                # shirt body fabric -> clean white / charcoal Challenge Court
                v = min(255, int(210 + lum * 45))
                wpx[x, y] = (v, v, v, a)
            elif lum > 0.72:
                # bright stripe bands -> electric hot pink!
                wpx[x, y] = (235, 38, 128, a)
            else:
                # collar/dark stripe -> matte black
                wpx[x, y] = (32, 34, 38, a)
    replace_sdo_tex(dec, slots["P_NAD_B_wearN01_IT.dds"], im_w)

    # 5. Shorts (pantsN01) -> 90s blue stonewash denim with black inner cycling layer
    im_p = extract_slot_image(dec, slots["P_NAD_B_pantsN01_IT.dds"])
    ppx = im_p.load()
    pw, ph = im_p.size
    for y in range(ph):
        for x in range(pw):
            r, g, b, a = ppx[x, y]
            lum = (r * 0.3 + g * 0.59 + b * 0.11) / 255.0
            if lum < 0.25:
                ppx[x, y] = (26, 26, 30, a)
            else:
                # faded stonewash denim blue
                ppx[x, y] = (min(255, int(68 + lum * 88)), min(255, int(102 + lum * 96)), min(255, int(156 + lum * 82)), a)
    replace_sdo_tex(dec, slots["P_NAD_B_pantsN01_IT.dds"], im_p)

    # Copy base .zml metadata from P_M_NAD_IT
    for zext in ["_culling.zml", "_deformable.zml"]:
        ze = [x for x in entries if x["name"] == f"HIGH/Player/Model/P_M_NAD{zext}"][0]
        open(os.path.join(MODEL_DIR, f"P_M_AGA{zext}"), "wb").write(read_entry(entries, ze, f0, f1, cache))

    out_sdo = os.path.join(MODEL_DIR, "P_M_AGA_LG.sdo")
    open(out_sdo, "wb").write(lzss_compress_literal(bytes(dec)))
    print(f"Built {out_sdo} (Agassi '91 blonde mullet + Challenge Court kit)")


def build_agassi_06_sdo(entries, f0, f1, cache):
    """Agassi '06 (Calvo + perilla + kit negro/blanco) on P_M_DJV_IT."""
    e = [x for x in entries if x["name"] == "HIGH/Player/Model/P_M_DJV_IT.sdo"][0]
    dec = bytearray(lzss_decompress(read_entry(entries, e, f0, f1, cache)))
    slots = {s["name"]: s for s in parse_sdo_dds_slots(dec)}

    # 1. Hair -> completely transparent (alpha=0) so head contour is pure smooth skull!
    im_h = Image.new("RGBA", (slots["P_DJV_B_hair_IT.dds"]["w"], slots["P_DJV_B_hair_IT.dds"]["h"]), (0, 0, 0, 0))
    replace_sdo_tex(dec, slots["P_DJV_B_hair_IT.dds"], im_h)

    # 2. Face -> replace painted hair on crown, temples, sideburns, nape with natural forehead skin + Agassi goatee!
    im_face = extract_slot_image(dec, slots["P_DJV_B_face_IT.dds"])
    im_face.thumbnail((512, 512)) # temporary check not needed, work at full 1024x1024!
    im_face = extract_slot_image(dec, slots["P_DJV_B_face_IT.dds"])
    fw, fh = im_face.size
    fpx = im_face.load()

    # Sample average forehead skin tone (center x=430..590, y=280..330 in 1024x1024)
    sr_sum = sg_sum = sb_sum = cnt = 0
    for y in range(280, 330):
        for x in range(430, 590):
            r, g, b, _ = fpx[x, y]
            sr_sum += r; sg_sum += g; sb_sum += b; cnt += 1
    skin_r, skin_g, skin_b = sr_sum // cnt, sg_sum // cnt, sb_sum // cnt
    rng = random.Random(2006)

    # Smooth scalp mask over crown (y < 272, avoiding eyebrows y>=335), plus outer hair halo & behind ears
    for y in range(fh):
        for x in range(fw):
            r, g, b, a = fpx[x, y]
            # Keep ONLY ear cartilage itself (exclude surrounding dark hair halo behind ear)
            in_left_ear = ((x - 178) / 48.0) ** 2 + ((y - 455) / 86.0) ** 2 < 1.0
            in_right_ear = ((x - 846) / 48.0) ** 2 + ((y - 455) / 86.0) ** 2 < 1.0
            if in_left_ear or in_right_ear:
                continue

            is_scalp_top = y < 276
            is_side_hair = (x < 342 or x > 682) and y < 745
            lum = (r * 0.3 + g * 0.59 + b * 0.11)
            # Sample local skin brightness smoothly instead of flat constant box
            local_k = 1.02 - 0.10 * min(1.0, abs(x - 512) / 512.0) - 0.07 * (1.0 - min(1.0, y / 276.0))
            if (is_scalp_top or is_side_hair) and lum < 142:
                n = rng.randint(-3, 3)
                nr = max(0, min(255, int(skin_r * local_k + n)))
                ng = max(0, min(255, int(skin_g * local_k + n)))
                nb = max(0, min(255, int(skin_b * local_k + n)))
                fpx[x, y] = (nr, ng, nb, a)
            elif is_scalp_top and y > 220:
                blend = min(1.0, (y - 220) / 56.0)
                fpx[x, y] = (
                    int(skin_r * local_k * (1 - blend) + r * blend),
                    int(skin_g * local_k * (1 - blend) + g * blend),
                    int(skin_b * local_k * (1 - blend) + b * blend),
                    a,
                )

            # Soften seam along vertical sideburn boundaries (x=330..360 and x=664..694, y=260..735)
            if 260 <= y < 735 and (328 <= x <= 362 or 662 <= x <= 696):
                dx_b = abs(x - 345) / 18.0 if x < 512 else abs(x - 679) / 18.0
                edge_b = max(0.0, 1.0 - dx_b) * 0.5
                fpx[x, y] = (
                    int(fpx[x, y][0] * (1 - edge_b) + skin_r * edge_b),
                    int(fpx[x, y][1] * (1 - edge_b) + skin_g * edge_b),
                    int(fpx[x, y][2] * (1 - edge_b) + skin_b * edge_b),
                    a,
                )

            # Add iconic trimmed brown/salt-pepper chin goatee (mouth around y=585, chin y=640..725, x=440..584)
            dx_g = (x - 512) / 68.0
            dy_g = (y - 682) / 48.0
            if dx_g * dx_g + dy_g * dy_g < 1.0 and y > 628:
                dist = (dx_g * dx_g + dy_g * dy_g) ** 0.5
                strength = max(0.0, (1.0 - dist) * 0.55)
                if rng.random() < 0.72:
                    fpx[x, y] = (
                        int(r * (1 - strength) + 54 * strength),
                        int(g * (1 - strength) + 42 * strength),
                        int(b * (1 - strength) + 34 * strength),
                        a,
                    )

    # Soften hairline seam cleanly with a larger blur across crown & ear-surround before blending
    scalp_crop = im_face.crop((0, 0, fw, 300)).filter(ImageFilter.GaussianBlur(radius=3.0))
    im_face.paste(scalp_crop, (0, 0))
    replace_sdo_tex(dec, slots["P_DJV_B_face_IT.dds"], im_face)

    # Save debug PNG of bald face texture so we can visually inspect it!
    dbg_face = im_face.copy()
    dbg_face.thumbnail((512, 512))
    dbg_face.save(os.path.join(SCRATCH_DIR, "agassi_06_bald_face.png"))

    # 3. Flatten hair bump in P_DJV_N_face_IT so smooth bald head doesn't reflect hair strands!
    im_nface = extract_slot_image(dec, slots["P_DJV_N_face_IT.dds"])
    nfw, nfh = im_nface.size
    nfpx = im_nface.load()
    for y in range(int(nfh * 0.26)):
        for x in range(nfw):
            nfpx[x, y] = (128, 128, 255, nfpx[x, y][3])
    replace_sdo_tex(dec, slots["P_DJV_N_face_IT.dds"], im_nface)

    # 4. Outfit -> Iconic Agassi 2006 late-career sleek black / dark charcoal & white trim kit
    im_w = extract_slot_image(dec, slots["P_DJV_B_wear01_IT.dds"])
    wpx = im_w.load()
    ww, wh = im_w.size
    for y in range(wh):
        for x in range(ww):
            r, g, b, a = wpx[x, y]
            # Convert yellow shirt -> sleek charcoal black (#24262A), suppress wing graphics
            lum = (r * 0.3 + g * 0.59 + b * 0.11) / 255.0
            # Keep collar white trim
            if y < int(wh * 0.12) and int(ww * 0.18) < x < int(ww * 0.32):
                wpx[x, y] = (230, 232, 235, a)
            else:
                v = int(28 + lum * 28)
                wpx[x, y] = (v, v + 1, v + 3, a)
    replace_sdo_tex(dec, slots["P_DJV_B_wear01_IT.dds"], im_w)

    im_p = extract_slot_image(dec, slots["P_DJV_B_pants01_IT.dds"])
    ppx = im_p.load()
    for y in range(im_p.size[1]):
        for x in range(im_p.size[0]):
            r, g, b, a = ppx[x, y]
            lum = (r * 0.3 + g * 0.59 + b * 0.11) / 255.0
            v = int(26 + lum * 26)
            ppx[x, y] = (v, v + 1, v + 3, a)
    replace_sdo_tex(dec, slots["P_DJV_B_pants01_IT.dds"], im_p)

    # White wristbands
    im_acc = extract_slot_image(dec, slots["P_DJV_B_accessory01_IT.dds"])
    apx = im_acc.load()
    for y in range(im_acc.size[1]):
        for x in range(im_acc.size[0]):
            r, g, b, a = apx[x, y]
            lum = (r * 0.3 + g * 0.59 + b * 0.11) / 255.0
            v = min(255, int(195 + lum * 55))
            apx[x, y] = (v, v, v, a)
    replace_sdo_tex(dec, slots["P_DJV_B_accessory01_IT.dds"], im_acc)

    for zext in ["_culling.zml", "_deformable.zml"]:
        ze = [x for x in entries if x["name"] == f"HIGH/Player/Model/P_M_DJV{zext}"][0]
        open(os.path.join(MODEL_DIR, f"P_M_AG2{zext}"), "wb").write(read_entry(entries, ze, f0, f1, cache))

    out_sdo = os.path.join(MODEL_DIR, "P_M_AG2_LG.sdo")
    open(out_sdo, "wb").write(lzss_compress_literal(bytes(dec)))
    print(f"Built {out_sdo} (Agassi '06 BALD skull + goatee + black kit)")


def build_sabalenka_sdo(entries, f0, f1, cache):
    """Sabalenka (sleek ponytail + crimson-red Nike tank dress + warm brunette hair) on P_W_SHA_SN."""
    e = [x for x in entries if x["name"] == "HIGH/Player/Model/P_W_SHA_SN.sdo"][0]
    dec = bytearray(lzss_decompress(read_entry(entries, e, f0, f1, cache)))
    slots = {s["name"]: s for s in parse_sdo_dds_slots(dec)}

    # 1. Wear -> Rich Crimson Red tournament dress (matching photo_L/35.dds!) with crisp white Swoosh/trim
    im_w = extract_slot_image(dec, slots["P_SHA_B_wear_SN.dds"])
    wpx = im_w.load()
    ww, wh = im_w.size
    for y in range(wh):
        for x in range(ww):
            r, g, b, a = wpx[x, y]
            lum = (r * 0.3 + g * 0.59 + b * 0.11) / 255.0
            # Sharapova dress has pale top + teal skirt; turn WHOLE dress cohesive crimson-coral red!
            # Keep narrow yellow trim strip/swoosh crisp white/dark
            if y < int(wh * 0.08) and int(ww * 0.40) < x < int(ww * 0.60):
                # tag/trim -> crisp white
                wpx[x, y] = (240, 240, 240, a)
            elif g > r + 25 and b > r + 15 and lum > 0.72:
                # logo accent -> clean white/black
                wpx[x, y] = (245, 245, 245, a)
            else:
                nr = min(255, int(148 + lum * 96))
                ng = min(255, int(18 + lum * 36))
                nb = min(255, int(24 + lum * 42))
                wpx[x, y] = (nr, ng, nb, a)
    replace_sdo_tex(dec, slots["P_SHA_B_wear_SN.dds"], im_w)

    # 2. Inner / shorts -> dark crimson-black
    im_i = extract_slot_image(dec, slots["P_SHA_B_inner_SN.dds"])
    ipx = im_i.load()
    for y in range(im_i.size[1]):
        for x in range(im_i.size[0]):
            r, g, b, a = ipx[x, y]
            lum = (r * 0.3 + g * 0.59 + b * 0.11) / 255.0
            ipx[x, y] = (int(90 * lum + 25), int(16 * lum + 8), int(18 * lum + 10), a)
    replace_sdo_tex(dec, slots["P_SHA_B_inner_SN.dds"], im_i)

    # 3. Hair -> Sabalenka honey-chestnut / warm brunette ponytail
    im_h = extract_slot_image(dec, slots["P_SHA_B_hair_SN.dds"])
    hpx = im_h.load()
    for y in range(im_h.size[1]):
        for x in range(im_h.size[0]):
            r, g, b, a = hpx[x, y]
            hpx[x, y] = (int(r * 0.74), int(g * 0.66), int(b * 0.54), a)
    replace_sdo_tex(dec, slots["P_SHA_B_hair_SN.dds"], im_h)

    # 4. Accessory -> white/red wristbands
    im_a = extract_slot_image(dec, slots["P_SHA_B_accessory_SN.dds"])
    apx = im_a.load()
    for y in range(im_a.size[1]):
        for x in range(im_a.size[0]):
            r, g, b, a = apx[x, y]
            lum = (r * 0.3 + g * 0.59 + b * 0.11) / 255.0
            apx[x, y] = (min(255, int(200 + lum * 55)), min(255, int(45 + lum * 45)), min(255, int(48 + lum * 45)), a)
    replace_sdo_tex(dec, slots["P_SHA_B_accessory_SN.dds"], im_a)

    for zext in ["_culling.zml", "_deformable.zml"]:
        ze = [x for x in entries if x["name"] == f"HIGH/Player/Model/P_W_SHA{zext}"][0]
        open(os.path.join(MODEL_DIR, f"P_W_SAB{zext}"), "wb").write(read_entry(entries, ze, f0, f1, cache))

    out_sdo = os.path.join(MODEL_DIR, "P_W_SAB_NG.sdo")
    open(out_sdo, "wb").write(lzss_compress_literal(bytes(dec)))
    print(f"Built {out_sdo} (Sabalenka crimson tank dress + sporty brunette ponytail)")


def main():
    os.makedirs(SCRATCH_DIR, exist_ok=True)
    only_portraits = "--portraits" in sys.argv
    fix_wawrinka_portrait()
    entries = load_directory()
    with open(BIN0, "rb") as f0, open(BIN1, "rb") as f1:
        cache = {}
        build_portraits_and_eyestrips(entries, f0, f1, cache)
        if not only_portraits:
            build_agassi_91_sdo(entries, f0, f1, cache)
            build_agassi_06_sdo(entries, f0, f1, cache)
            build_sabalenka_sdo(entries, f0, f1, cache)

    # Export validation PNGs of eye-strip sample & Wawrinka fix
    for pid in [0, 26, 29, 35, 38, 51]:
        im = Image.open(os.path.join(PHOTO_EYE_DIR, f"{pid}.dds"))
        out = os.path.join(SCRATCH_DIR, f"eye_{pid}.png")
        im.save(out)
    im38 = Image.open(os.path.join(PHOTO_L_DIR, "38.dds"))
    im38.save(os.path.join(SCRATCH_DIR, "waw38_fixed.png"))
    print("Asset update complete!")


if __name__ == "__main__":
    main()
