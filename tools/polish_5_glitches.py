#!/usr/bin/env python3
"""
Final Ultra-Tight Polish (tools/polish_5_glitches.py):
  1. Verifies 84/84 unique roster (0..83 each exactly once).
  2. Polishes 6 players (62_FRI, 65_BAD, 29_AG2, 29_91_AGA, 60_RUB, 74_MUS) in ~20s.
  3. Renders scratch/batch_57_audit/POLISH_5_FINAL.png (3x2 grid).
  4. Runs 1 fast live VT4.exe menu check capturing page1_with_andreeva.png & page4_reorganized.png + spotless cleanup!
"""
import glob
import os
import shutil
import subprocess
import sys
import time
import cv2
import numpy as np
from PIL import Image, ImageDraw

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools", "tests"))
sys.path.insert(0, os.path.join(REPO_ROOT, "scratch", "real_alcaraz_3d"))

SWAP_ROOT = os.path.join(REPO_ROOT, "scratch", "local_faceswap")
os.environ["INSIGHTFACE_HOME"] = SWAP_ROOT
os.environ["HF_HOME"] = os.path.join(SWAP_ROOT, "hf_cache")
os.environ["XDG_CACHE_HOME"] = os.path.join(SWAP_ROOT, "xdg_cache")
os.environ["TMP"] = os.path.join(SWAP_ROOT, "tmp")
os.environ["TEMP"] = os.path.join(SWAP_ROOT, "tmp")

from compress_sega_lzss import lzss_compress_literal
from build_ee3_rackets import decompress_sdo
from update_custom_assets import parse_sdo_dds_slots, extract_slot_image, replace_sdo_tex
from hair3d_groom import synthesize_crisp_hair_textures
from local_identity_uv import detect_kps5_and_lms
from batch_studio_57 import MODEL_DIR, FINAL_UV_DIR, AUDIT_DIR
from fix_swapped_faces_v3b import _tint_scalp_hair
from polish_user_feedback_v4 import _render_sdo_preview, paint_white_bandana_uv
from vt4_test_lib import (
    GAME_DIR, LOG_PATH, INI_PATH,
    PAGE_TOUR, PAGE_LEGENDS, PAGE_LEGENDS2, PAGE_LEGENDS3,
    launch_vt4, boot_to_main_menu, send_key, read_log, navigate_carousel, format_ini,
    VK_RETURN, VK_DOWN, VK_Q, VK_F10,
)


def verify_84_unique():
    all_ids = PAGE_TOUR + PAGE_LEGENDS + PAGE_LEGENDS2 + PAGE_LEGENDS3
    assert len(all_ids) == 84, f"Expected 84 slots, got {len(all_ids)}"
    assert sorted(all_ids) == list(range(84)), f"Duplicates/missing in 0..83: {set(range(84)) ^ set(all_ids)}"
    print("[ROSTER ASSERT PASS] 84/84 unique (0..83 each exactly once!)", flush=True)


def polish_6_players():
    # 1. 62_FRI (P_M_FRI_NG.sdo on P_M_FED_SN): crisp bright white bandana on P_FED_B_face_SN + P_FED_B_hair_SN!
    sdo_p = os.path.join(MODEL_DIR, "P_M_FRI_NG.sdo")
    dec = bytearray(decompress_sdo(open(sdo_p, "rb").read()))
    slots = {s["name"]: s for s in parse_sdo_dds_slots(dec)}
    fk = next(k for k in slots if "_b_face" in k.lower())
    f_rgba = np.array(extract_slot_image(dec, slots[fk]).convert("RGBA"))
    kps, _ = detect_kps5_and_lms(f_rgba[:, :, :3])
    # Paint crisp bright white bandana across forehead/temples on face UV
    f_rgb = paint_white_bandana_uv(f_rgba[:, :, :3], kps)
    replace_sdo_tex(dec, slots[fk], Image.fromarray(np.dstack([f_rgb, f_rgba[:, :, 3]]), mode="RGBA"))
    Image.fromarray(f_rgb).save(os.path.join(FINAL_UV_DIR, "62_FRI.png"))
    # Also paint Federer's headband strip on P_FED_B_hair_SN (bottom band region) & any accessory/band crisp white!
    for sn, sl in slots.items():
        sl_l = sn.lower()
        if "_b_hair" in sl_l:
            h_rgba = np.array(extract_slot_image(dec, sl).convert("RGBA"))
            hh, ww = h_rgba.shape[:2]
            # Federer's headband texture occupies the lower band of P_FED_B_hair_SN.dds (y > 0.72*hh)
            band_y0 = int(hh * 0.72)
            lum = (0.3 * h_rgba[band_y0:, :, 0] + 0.59 * h_rgba[band_y0:, :, 1] + 0.11 * h_rgba[band_y0:, :, 2]) / 255.0
            v = np.clip(226.0 + lum * 22.0, 224, 246).astype(np.uint8)
            h_rgba[band_y0:, :, 0] = v
            h_rgba[band_y0:, :, 1] = v
            h_rgba[band_y0:, :, 2] = np.clip(v.astype(np.int32) + 3, 0, 250).astype(np.uint8)
            replace_sdo_tex(dec, sl, Image.fromarray(h_rgba, mode="RGBA"))
    open(sdo_p, "wb").write(lzss_compress_literal(bytes(dec)))
    print("[FIX 1/6] 62_FRI white bandana painted cleanly!", flush=True)

    # 2. 65_BAD (P_W_BAD_NG.sdo): natural warm honey/caramel-brown hair (132,100,64) + smooth left-cheek pale spot!
    sdo_p = os.path.join(MODEL_DIR, "P_W_BAD_NG.sdo")
    dec = bytearray(decompress_sdo(open(sdo_p, "rb").read()))
    slots = {s["name"]: s for s in parse_sdo_dds_slots(dec)}
    fk = next(k for k in slots if "_b_face" in k.lower())
    f_rgba = np.array(extract_slot_image(dec, slots[fk]).convert("RGBA"))
    kps, _ = detect_kps5_and_lms(f_rgba[:, :, :3])
    # Tint ALL scalp/side hair pixels (including bright bleached blonde!) to warm honey/caramel-brown (132,100,64)
    f_rgb = _tint_scalp_hair(f_rgba[:, :, :3], (132, 100, 64), kps, is_muster=True)
    # Smooth out the tiny pale spot on her left cheek (right side of UV image: x in [cx+0.35*iod..cx+0.95*iod], y in [ey+0.25*fh..ey+0.78*fh])
    H, W = f_rgb.shape[:2]
    le, re, ml, mr = kps[0], kps[1], kps[3], kps[4]
    cx = 0.5 * (float(le[0]) + float(re[0]))
    ey = 0.5 * (float(le[1]) + float(re[1]))
    iod = float(np.linalg.norm(re - le))
    fh = float(0.5 * (float(ml[1]) + float(mr[1])) - ey)
    chk_med = np.median(f_rgb[int(ey + 0.30 * fh):int(ey + 0.65 * fh), int(cx - 0.72 * iod):int(cx - 0.28 * iod)].reshape(-1, 3), axis=0).astype(np.float32)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    lchk = np.exp(-(((xx - (cx + 0.52 * iod)) / (0.34 * iod)) ** 2 + ((yy - (ey + 0.52 * fh)) / (0.28 * fh)) ** 2))
    lum_f = (0.299 * f_rgb[:, :, 0] + 0.587 * f_rgb[:, :, 1] + 0.114 * f_rgb[:, :, 2]).astype(np.float32)
    chk_lum = float(0.299 * chk_med[0] + 0.587 * chk_med[1] + 0.114 * chk_med[2])
    pale_spot = np.clip((lum_f - (chk_lum + 10.0)) / 18.0, 0.0, 1.0) * lchk
    pm = cv2.GaussianBlur(pale_spot, (15, 15), 4.0)[:, :, None] * 0.90
    f_rgb = np.clip(f_rgb.astype(np.float32) * (1.0 - pm) + chk_med[None, None, :] * pm, 0, 255).astype(np.uint8)
    replace_sdo_tex(dec, slots[fk], Image.fromarray(np.dstack([f_rgb, f_rgba[:, :, 3]]), mode="RGBA"))
    Image.fromarray(f_rgb).save(os.path.join(FINAL_UV_DIR, "65_BAD.png"))
    for sn, sl in slots.items():
        if "_b_hair" in sn.lower() and "band" not in sn.lower():
            diff, _ = synthesize_crisp_hair_textures(extract_slot_image(dec, sl).convert("RGBA"), hair_rgb=(132, 100, 64))
            replace_sdo_tex(dec, sl, diff)
    open(sdo_p, "wb").write(lzss_compress_literal(bytes(dec)))
    print("[FIX 2/6] 65_BAD caramel-brown hair + left cheek spot smoothed!", flush=True)

    # 3. 29_AG2 (P_M_AG2_LG.sdo): seamless wide-feathered LAB-matched bald scalp (ZERO seam!)
    sdo_p = os.path.join(MODEL_DIR, "P_M_AG2_LG.sdo")
    dec = bytearray(decompress_sdo(open(sdo_p, "rb").read()))
    slots = {s["name"]: s for s in parse_sdo_dds_slots(dec)}
    fk = next(k for k in slots if "_b_face" in k.lower())
    f_rgba = np.array(extract_slot_image(dec, slots[fk]).convert("RGBA"))
    f_rgb = f_rgba[:, :, :3].copy()
    kps, _ = detect_kps5_and_lms(f_rgb)
    H, W = f_rgb.shape[:2]
    le, re, ml, mr = kps[0], kps[1], kps[3], kps[4]
    cx = 0.5 * (float(le[0]) + float(re[0]))
    ey = 0.5 * (float(le[1]) + float(re[1]))
    iod = float(np.linalg.norm(re - le))
    fh = float(0.5 * (float(ml[1]) + float(mr[1])) - ey)
    lab = cv2.cvtColor(f_rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    # Match upper scalp (y < ey - 0.35*fh) directly to true mid-forehead skin LAB with ultra-wide 85px feather!
    fh_lab = np.median(lab[int(ey - 0.30 * fh):int(ey - 0.12 * fh), int(cx - 0.45 * iod):int(cx + 0.45 * iod)].reshape(-1, 3), axis=0)
    sc_lab = np.median(lab[int(max(0, ey - 0.95 * fh)):int(ey - 0.48 * fh), int(cx - 0.55 * iod):int(cx + 0.55 * iod)].reshape(-1, 3), axis=0)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    ear_l = ((xx - 0.17 * W) / (0.068 * W)) ** 2 + ((yy - (ey + 0.25 * fh)) / (0.55 * fh)) ** 2
    ear_r = ((xx - 0.83 * W) / (0.068 * W)) ** 2 + ((yy - (ey + 0.25 * fh)) / (0.55 * fh)) ** 2
    not_ear = np.clip(np.minimum(ear_l, ear_r) - 0.78, 0.0, 1.0)
    top_m = np.clip((ey - 0.26 * fh - yy) / 88.0, 0.0, 1.0) * not_ear
    side_m = np.clip((0.30 * W - np.minimum(xx, W - 1 - xx)) / (0.10 * W), 0.0, 1.0) * np.clip((ey + 0.75 * fh - yy) / (0.30 * fh), 0.0, 1.0) * not_ear
    m = cv2.GaussianBlur(np.maximum(top_m, side_m).astype(np.float32), (61, 61), 18.0)
    for c in range(3):
        lab[:, :, c] = np.clip(lab[:, :, c] + (fh_lab[c] - sc_lab[c]) * m, 0, 255)
    f_rgb = cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2RGB)
    # Also softly blur the transition band right along y = ey - 0.36*fh to erase any residual line
    seam_band = np.exp(-((yy - (ey - 0.36 * fh)) / 24.0) ** 2) * not_ear
    bl = cv2.GaussianBlur(f_rgb, (31, 31), 9.0)
    f_rgb = np.clip(f_rgb.astype(np.float32) * (1.0 - seam_band[:, :, None] * 0.65) + bl.astype(np.float32) * (seam_band[:, :, None] * 0.65), 0, 255).astype(np.uint8)
    replace_sdo_tex(dec, slots[fk], Image.fromarray(np.dstack([f_rgb, f_rgba[:, :, 3]]), mode="RGBA"))
    Image.fromarray(f_rgb).save(os.path.join(FINAL_UV_DIR, "29_AG2.png"))
    open(sdo_p, "wb").write(lzss_compress_literal(bytes(dec)))
    print("[FIX 3/6] 29_AG2 seamless LAB-matched bald scalp!", flush=True)

    # 4. 29_91_AGA (P_M_AGA_LG.sdo): natural warm golden-brown (154,126,76) with darker roots (kill lemon-yellow!)
    sdo_p = os.path.join(MODEL_DIR, "P_M_AGA_LG.sdo")
    dec = bytearray(decompress_sdo(open(sdo_p, "rb").read()))
    slots = {s["name"]: s for s in parse_sdo_dds_slots(dec)}
    fk = next(k for k in slots if "_b_face" in k.lower())
    f_rgba = np.array(extract_slot_image(dec, slots[fk]).convert("RGBA"))
    kps, _ = detect_kps5_and_lms(f_rgba[:, :, :3])
    f_rgb = _tint_scalp_hair(f_rgba[:, :, :3], (154, 126, 76), kps, is_muster=True)
    replace_sdo_tex(dec, slots[fk], Image.fromarray(np.dstack([f_rgb, f_rgba[:, :, 3]]), mode="RGBA"))
    Image.fromarray(f_rgb).save(os.path.join(FINAL_UV_DIR, "29_91_AGA.png"))
    for sn, sl in slots.items():
        if "_b_hair" in sn.lower() and "band" not in sn.lower():
            diff, _ = synthesize_crisp_hair_textures(extract_slot_image(dec, sl).convert("RGBA"), hair_rgb=(154, 126, 76))
            darr = np.array(diff).astype(np.float32)
            yy_h = np.linspace(0.0, 1.0, darr.shape[0])[:, None]
            rb = np.clip(1.0 - yy_h / 0.36, 0.0, 1.0) * 0.58
            root = np.array([72.0, 52.0, 34.0], dtype=np.float32)
            darr[:, :, :3] = darr[:, :, :3] * (1.0 - rb[:, :, None]) + root[None, None, :] * rb[:, :, None]
            replace_sdo_tex(dec, sl, Image.fromarray(np.clip(darr, 0, 255).astype(np.uint8), mode="RGBA"))
    open(sdo_p, "wb").write(lzss_compress_literal(bytes(dec)))
    print("[FIX 4/6] 29_91_AGA natural warm golden-brown mullet!", flush=True)

    # 5 & 6. 60_RUB & 74_MUS (both on P_M_HAS_IT): smooth UV hairline + feather front edge of *_B_hairtop_*!
    for pid, sdo_name, hrgb in [
        ("60_RUB", "P_M_RUB_NG.sdo", (138, 68, 34)),
        ("74_MUS", "P_M_MUS_LG.sdo", (142, 118, 82)),
    ]:
        sdo_p = os.path.join(MODEL_DIR, sdo_name)
        dec = bytearray(decompress_sdo(open(sdo_p, "rb").read()))
        slots = {s["name"]: s for s in parse_sdo_dds_slots(dec)}
        fk = next(k for k in slots if "_b_face" in k.lower())
        f_rgba = np.array(extract_slot_image(dec, slots[fk]).convert("RGBA"))
        f_rgb = f_rgba[:, :, :3].copy()
        kps, _ = detect_kps5_and_lms(f_rgb)
        H, W = f_rgb.shape[:2]
        le, re, ml, mr = kps[0], kps[1], kps[3], kps[4]
        cx = 0.5 * (float(le[0]) + float(re[0]))
        ey = 0.5 * (float(le[1]) + float(re[1]))
        iod = float(np.linalg.norm(re - le))
        fh = float(0.5 * (float(ml[1]) + float(mr[1])) - ey)
        # Keep true skin cleanly up to y = ey - 0.50*fh and smoothly blend into hair above y = ey - 0.56*fh!
        fskin = np.median(f_rgb[int(ey - 0.28 * fh):int(ey - 0.12 * fh), int(cx - 0.45 * iod):int(cx + 0.45 * iod)].reshape(-1, 3), axis=0).astype(np.float32)
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        hl_y = ey - 0.52 * fh
        # Upper scalp hair smoothly tinted to hrgb with soft 28px feather across hairline
        hair_m = np.clip((hl_y - yy) / 28.0, 0.0, 1.0)
        # Clean forehead band right below hl_y (eliminates any harsh orange/beige forehead step!)
        clean_fh = np.clip((yy - (hl_y - 6.0)) / 16.0, 0.0, 1.0) * np.clip(((ey - 0.22 * fh) - yy) / 14.0, 0.0, 1.0)
        clean_fh *= np.clip(1.0 - ((xx - cx) / (1.05 * iod)) ** 2, 0.0, 1.0)
        clean_fh = cv2.GaussianBlur(clean_fh, (17, 17), 5.0)[:, :, None] * 0.78
        f_rgb = np.clip(f_rgb.astype(np.float32) * (1.0 - clean_fh) + fskin[None, None, :] * clean_fh, 0, 255).astype(np.uint8)
        # Match upper scalp smoothly to hrgb
        lum = (0.299 * f_rgb[:, :, 0] + 0.587 * f_rgb[:, :, 1] + 0.114 * f_rgb[:, :, 2]).astype(np.float32) / 255.0
        tgt = np.array(hrgb, dtype=np.float32)
        tinted = np.clip(tgt[None, None, :] * (0.55 + 0.65 * lum)[:, :, None], 15, 225)
        hm = cv2.GaussianBlur(hair_m, (19, 19), 6.0)[:, :, None] * 0.85
        f_rgb = np.clip(f_rgb.astype(np.float32) * (1.0 - hm) + tinted * hm, 0, 255).astype(np.uint8)
        replace_sdo_tex(dec, slots[fk], Image.fromarray(np.dstack([f_rgb, f_rgba[:, :, 3]]), mode="RGBA"))
        Image.fromarray(f_rgb).save(os.path.join(FINAL_UV_DIR, f"{pid}.png"))
        for sn, sl in slots.items():
            if "_b_hair" in sn.lower():
                diff, _ = synthesize_crisp_hair_textures(extract_slot_image(dec, sl).convert("RGBA"), hair_rgb=hrgb)
                darr = np.array(diff)
                if "hairtop" in sn.lower():
                    # Feather bottom/front 18% of hairtop alpha so it melts smoothly into forehead UV!
                    hh = darr.shape[0]
                    fade = np.clip(np.linspace(1.0, 0.15, int(hh * 0.18)), 0.15, 1.0)[:, None]
                    darr[hh - len(fade):, :, 3] = (darr[hh - len(fade):, :, 3].astype(np.float32) * fade).astype(np.uint8)
                replace_sdo_tex(dec, sl, Image.fromarray(darr, mode="RGBA"))
        open(sdo_p, "wb").write(lzss_compress_literal(bytes(dec)))
        print(f"[FIX 5-6/6] {pid} feathered hairtop & smooth forehead hairline!", flush=True)


def render_polish_5_final():
    targets = [
        ("62_FRI", "P_M_FRI_NG.sdo", "P_M_FED_SN"),
        ("65_BAD", "P_W_BAD_NG.sdo", "P_W_IVA_IT"),
        ("29_AG2", "P_M_AG2_LG.sdo", "P_M_DJV_IT"),
        ("29_91_AGA", "P_M_AGA_LG.sdo", "P_M_RAF_IT"),
        ("60_RUB", "P_M_RUB_NG.sdo", "P_M_HAS_IT"),
        ("74_MUS", "P_M_MUS_LG.sdo", "P_M_HAS_IT"),
    ]
    cols, rows = 3, 2
    tw, th = 300, 330
    grid = Image.new("RGB", (cols * tw + 8, rows * th + 8), (18, 20, 26))
    for i, (pid, sdo_name, base_name) in enumerate(targets):
        im_r = _render_sdo_preview(os.path.join(MODEL_DIR, sdo_name), size=300, yaw_deg=-12.0)
        tile = Image.new("RGB", (tw, th), (24, 26, 32))
        tile.paste(im_r.resize((300, 300), Image.Resampling.LANCZOS), (0, 30))
        dr = ImageDraw.Draw(tile)
        dr.rectangle([0, 0, tw, 30], fill=(12, 16, 24))
        dr.text((8, 7), f"{pid}  ({base_name})", fill=(255, 224, 102))
        r, c = divmod(i, cols)
        grid.paste(tile, (c * tw + 4, r * th + 4))
    out_p = os.path.join(AUDIT_DIR, "POLISH_5_FINAL.png")
    grid.save(out_p)
    print(f"[RENDER OK] {out_p}", flush=True)


def capture_page1_and_page4_live():
    def kill_vt4():
        subprocess.run(["taskkill", "/F", "/IM", "VT4.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def latest_png():
        pngs = sorted(glob.glob(os.path.join(GAME_DIR, "vt4_present_*.png")), key=lambda s: int(s.rsplit("_", 1)[1].split(".")[0]))
        return pngs[-1] if pngs else None

    kill_vt4()
    time.sleep(0.5)
    for f in glob.glob(os.path.join(GAME_DIR, "vt4_present_*.png")):
        os.remove(f)
    if os.path.exists(LOG_PATH):
        os.remove(LOG_PATH)

    ini_bak = open(INI_PATH, "r", encoding="utf-8").read() if os.path.exists(INI_PATH) else None
    with open(INI_PATH, "wb") as f:
        f.write(format_ini(width=1280, height=720, windowed=1, remove_live=1))

    proc, hwnd = launch_vt4(timeout=15.0)
    try:
        boot_to_main_menu(hwnd)
        navigate_carousel(hwnd, 2)
        send_key(hwnd, VK_RETURN, hold=0.10, post_wait=2.4)
        for _ in range(6):
            send_key(hwnd, VK_DOWN, hold=0.09, post_wait=0.32)
        send_key(hwnd, VK_RETURN, hold=0.10, post_wait=2.0)  # PREPARADO -> SELECCIONAR POSICIÓN
        send_key(hwnd, VK_RETURN, hold=0.10, post_wait=2.8)  # -> CharaSelect Page 1!

        # Highlight Row 6 Col 0 (82 Mirra Andreeva on Page 1!) and capture page1_with_andreeva.png
        for _ in range(6):
            send_key(hwnd, VK_DOWN, hold=0.08, post_wait=0.18)
        time.sleep(0.6)
        send_key(hwnd, VK_F10, hold=0.10, post_wait=1.2)
        p1 = latest_png()
        if p1:
            shutil.copy2(p1, os.path.join(AUDIT_DIR, "page1_with_andreeva.png"))

        # Press Q -> Page 4, move to Row 3 Col 0 (83 Billie Jean King grouped with pioneers!) -> capture page4_reorganized.png
        send_key(hwnd, VK_Q, hold=0.10, post_wait=1.2)
        for _ in range(3):
            send_key(hwnd, VK_DOWN, hold=0.08, post_wait=0.18)
        time.sleep(0.6)
        send_key(hwnd, VK_F10, hold=0.10, post_wait=1.2)
        p4 = latest_png()
        if p4:
            shutil.copy2(p4, os.path.join(AUDIT_DIR, "page4_reorganized.png"))

        log_txt = read_log()
        exc_cnt = log_txt.count("EXCEPTION") + log_txt.count("CrashHandler")
        print(f"[LIVE PAGES OK] p1={p1 is not None} p4={p4 is not None} exc={exc_cnt} alive={proc.poll() is None}", flush=True)
    finally:
        kill_vt4()
        time.sleep(1.0)
        if ini_bak is not None:
            open(INI_PATH, "w", encoding="utf-8").write(ini_bak)
        for f in glob.glob(os.path.join(GAME_DIR, "vt4_present_*.png")):
            try: os.remove(f)
            except Exception: pass
        if os.path.exists(LOG_PATH):
            try: os.remove(LOG_PATH)
            except Exception: pass

    out = subprocess.check_output(["tasklist", "/FI", "IMAGENAME eq VT4.exe"], text=True)
    print(f"[CLEANUP] VT4={out.count('VT4.exe')} | GAME_PNGS={len(glob.glob(os.path.join(GAME_DIR, 'vt4_present_*.png')))} | GAME_LOG={os.path.exists(LOG_PATH)} | INSIGHTFACE={os.path.exists(os.path.expanduser('~/.insightface'))}", flush=True)


if __name__ == "__main__":
    verify_84_unique()
    polish_6_players()
    render_polish_5_final()
    capture_page1_and_page4_live()
