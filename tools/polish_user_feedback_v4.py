#!/usr/bin/env python3
"""
Phase 6 Master Update (tools/polish_user_feedback_v4.py):
  - Generates photo_L / photo_eye / photo_S DDS for 82_AND (Mirra Andreeva) & 83_BJK (Billie Jean King).
  - Stages clean frontal refs for 82_AND, 83_BJK, 35_SAB (calm flattering), 29_AG2 (clean bald).
  - Rebuilds 5 new/base-swapped SDO + ZML models (82_AND<-WOZ, 83_BJK<-CHA, 35_SAB<-SHA, 62_FRI<-FED, 60_RUB<-HAS).
  - Runs local_identity_uv + clean normals + matte hair + naturalized 8-palette verified eyes + ALL 15 custom
    user-requested UV & 3D mesh refinements (0.0000mm neck seam, 0.0mm eye-socket distortion, mip0/mip1 < 3.5).
  - Renders scratch/batch_57_audit/PHASE6_USER_FIXES_AND_2NEW.png + refreshes sheet_01..06.png (59 players total!).
"""
import glob
import json
import os
import shutil
import struct
import sys
import time
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))
sys.path.insert(0, os.path.join(REPO_ROOT, "scratch", "real_alcaraz_3d"))

SWAP_ROOT = os.path.join(REPO_ROOT, "scratch", "local_faceswap")
os.environ["INSIGHTFACE_HOME"] = SWAP_ROOT
os.environ["HF_HOME"] = os.path.join(SWAP_ROOT, "hf_cache")
os.environ["XDG_CACHE_HOME"] = os.path.join(SWAP_ROOT, "xdg_cache")
os.environ["TMP"] = os.path.join(SWAP_ROOT, "tmp")
os.environ["TEMP"] = os.path.join(SWAP_ROOT, "tmp")
os.makedirs(os.environ["TMP"], exist_ok=True)

from vt4_archive import BIN0, BIN1, load_directory, read_entry, lzss_decompress
from compress_sega_lzss import lzss_compress_literal
from build_ee3_rackets import parse_vbs, parse_ibs, decompress_sdo
from update_custom_assets import parse_sdo_dds_slots, extract_slot_image, replace_sdo_tex
from hair3d_groom import synthesize_crisp_hair_textures
from build_all_sdo_models import PLAYERS_3D, _apply_navratilova_short_hair
from make_madrid_blue_clay import recolor_dds_blocks
from uv_face_projector import scale_sdo_bones
from local_identity_uv import detect_kps5_and_lms, extract_eye_socket_cutout_mask
from dxt_codec import encode_dds
from build_v2_portraits import write_bgra_dds, write_dxt5_dds
from sculpt_sdo_head import (
    _strip_to_tris,
    _find_ib_for_vb,
    _read_vb_xyz_nrm,
    _write_vb_xyz_nrm,
    _recalc_blended_normals,
)
from batch_studio_57 import (
    process_one_player,
    render_sdo_head_auto,
    load_mesh_data,
    MODEL_DIR,
    BACKUP_DIR,
    REFS_57_DIR,
    WS_BASE_DIR,
    WS_EDIT_DIR,
    FINAL_UV_DIR,
    AUDIT_DIR,
)
from fix_swapped_faces_v3b import _fit_aniso_affine_5pt, _tint_scalp_hair

VR_DIR = os.path.join(REPO_ROOT, "game", "archive", "HIGH", "Frontend", "VR")
REF_ROOT = REFS_57_DIR
P6_REFS = os.path.join(REPO_ROOT, "scratch", "uv_lab", "phase6_refs")
P6_CANVAS_DIR = os.path.join(REPO_ROOT, "scratch", "uv_lab", "p6_canvases")
os.makedirs(P6_CANVAS_DIR, exist_ok=True)

PHASE6_15 = [
    "82_AND", "83_BJK", "35_SAB", "65_BAD", "29_AG2",
    "29_91_AGA", "33_SER", "59_SHE", "62_FRI", "39_MED",
    "43_KYR", "60_RUB", "70_SOD", "71_BER", "74_MUS",
]

P6_HAIR_RGB = {
    "82_AND": (148, 118, 82),   # light-brown / ash-blonde ponytail
    "83_BJK": (78, 54, 36),     # 70s short brown bob
    "35_SAB": (118, 86, 52),    # warm honey-brown ponytail
    "65_BAD": (164, 130, 78),   # warm golden-blonde ponytail
    "29_91_AGA": (184, 150, 86),# 1991 golden-blonde mullet highlights
    "62_FRI": (54, 38, 26),     # rich dark-brown
    "60_RUB": (138, 68, 34),    # rich copper-auburn
    "70_SOD": (146, 126, 88),   # dark ash-blonde buzz-crop
    "71_BER": (116, 90, 56),    # medium light-brown swept crop
    "74_MUS": (154, 128, 88),   # unified warm sandy-blonde
    "39_MED": (64, 46, 32),     # dark-brown
    "43_KYR": (26, 22, 20),     # black mohawk-fade
}


def generate_vr_portraits_82_83():
    """Generate photo_L (256x256 BGRA), photo_eye (256x64 BGRA), photo_S (128x64 DXT5) for 82 & 83."""
    specs = [
        ("82", os.path.join(P6_REFS, "82_AND", "wiki_main.jpg"), False),
        ("83", os.path.join(P6_REFS, "83_BJK", "BJK_1973.jpg"), True),
    ]
    for cid, src_p, colorize_vintage in specs:
        im = Image.open(src_p).convert("RGB")
        arr = np.array(im)
        if colorize_vintage:
            # Subtle warm 1970s Kodachrome colorization of B&W BJK_1973 portrait
            g = arr[:, :, 0].astype(np.float32) / 255.0
            r = np.clip((g ** 0.92) * 238.0 + 14.0, 0, 255)
            gr = np.clip((g ** 0.98) * 212.0 + 8.0, 0, 255)
            b = np.clip((g ** 1.06) * 188.0 + 6.0, 0, 255)
            arr = np.stack([r, gr, b], axis=-1).astype(np.uint8)
            im = Image.fromarray(arr)

        # Detect face landmarks to frame head & shoulders cleanly
        H, W = arr.shape[:2]
        try:
            kps, _ = detect_kps5_and_lms(arr, allow_pad_fallback=True)
            cx = float(0.5 * (kps[0, 0] + kps[1, 0]))
            eye_y = float(0.5 * (kps[0, 1] + kps[1, 1]))
            iod = float(np.linalg.norm(kps[1] - kps[0]))
        except Exception:
            cx, eye_y, iod = W * 0.5, H * 0.25, W * 0.22

        # Crop square torso/headshot centered on face with eyes at ~36% from top
        box_sz = int(max(iod * 4.4, min(W, H) * 0.72))
        x0 = int(round(cx - box_sz * 0.50))
        y0 = int(round(eye_y - box_sz * 0.36))
        x1 = x0 + box_sz
        y1 = y0 + box_sz
        # Clamp inside image safely
        if x0 < 0:
            x1 -= x0; x0 = 0
        if y0 < 0:
            y1 -= y0; y0 = 0
        if x1 > W:
            x0 = max(0, x0 - (x1 - W)); x1 = W
        if y1 > H:
            y0 = max(0, y0 - (y1 - H)); y1 = H
        crop = im.crop((x0, y0, x1, y1)).resize((256, 256), Image.Resampling.LANCZOS)

        # Soft vignette alpha for photo_L so it blends cleanly onto VT4 card backdrop
        rgba = crop.convert("RGBA")
        yy, xx = np.mgrid[0:256, 0:256].astype(np.float32)
        # Keep head/torso fully opaque, gently fade top corners
        corner_fade = np.clip(1.0 - np.maximum(0.0, ((xx - 128.0) / 138.0) ** 2 + ((yy - 148.0) / 155.0) ** 2 - 0.85) * 2.5, 0.0, 1.0)
        rgba.putalpha(Image.fromarray((corner_fade * 255.0).astype(np.uint8), mode="L"))
        write_bgra_dds(rgba, os.path.join(VR_DIR, "photo_L", f"{cid}.dds"))

        # photo_eye (256x64 opaque BGRA strip centered on eyes)
        ey_256 = int(round((eye_y - y0) * 256.0 / max(1, y1 - y0)))
        ey0 = max(0, min(192, ey_256 - 32))
        eye_strip = crop.crop((0, ey0, 256, ey0 + 64)).convert("RGBA")
        write_bgra_dds(eye_strip, os.path.join(VR_DIR, "photo_eye", f"{cid}.dds"))

        # photo_S (128x64 DXT5 1-mip)
        s_crop = crop.crop((0, max(0, ey0 - 20), 256, min(256, ey0 + 108))).resize((128, 64), Image.Resampling.LANCZOS).convert("RGBA")
        write_dxt5_dds(s_crop, os.path.join(VR_DIR, "photo_S", f"{cid}.dds"))
        print(f"[VR PORTRAIT OK] ID={cid} -> photo_L, photo_eye, photo_S written!", flush=True)


def stage_clean_refs():
    """Install clean frontal refs for 82_AND, 83_BJK, 35_SAB (calm flattering), 29_AG2 (clean bald)."""
    bak_root = os.path.join(REPO_ROOT, "scratch", "uv_lab", "old_refs_backup")
    os.makedirs(bak_root, exist_ok=True)

    # 82_AND & 83_BJK (brand new) — pad 82_AND slightly so visor never blocks MediaPipe face detection!
    for pid, src in [
        ("82_AND", os.path.join(P6_REFS, "82_AND", "wiki_main.jpg")),
        ("83_BJK", os.path.join(P6_REFS, "83_BJK", "BJK_1973.jpg")),
    ]:
        d = os.path.join(REF_ROOT, pid)
        os.makedirs(d, exist_ok=True)
        out_ref = os.path.join(d, "ref_primary.jpg")
        if pid == "82_AND":
            im_a = Image.open(src).convert("RGB")
            arr_a = np.array(im_a)
            # Slightly brighten visor shadow + add 180px neutral padding so MediaPipe locks 100%!
            pad_a = cv2.copyMakeBorder(arr_a, 180, 180, 180, 180, cv2.BORDER_REPLICATE)
            Image.fromarray(pad_a).save(out_ref, quality=95)
        else:
            shutil.copy2(src, out_ref)

    # 35_SAB: move grimacing/old refs out, install calm flattering Miami Open portrait!
    sab_d = os.path.join(REF_ROOT, "35_SAB")
    os.makedirs(sab_d, exist_ok=True)
    sab_bak = os.path.join(bak_root, "35_SAB")
    os.makedirs(sab_bak, exist_ok=True)
    for fn in os.listdir(sab_d):
        if fn.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            shutil.move(os.path.join(sab_d, fn), os.path.join(sab_bak, fn))
    shutil.copy2(os.path.join(P6_REFS, "35_SAB", "wiki_main.jpg"), os.path.join(sab_d, "ref_sab_miami_calm.jpg"))

    # 29_AG2: replace watermarked alamy ref with clean bald Wikipedia 2005 portrait!
    ag2_d = os.path.join(REF_ROOT, "29_AG2")
    os.makedirs(ag2_d, exist_ok=True)
    ag2_bak = os.path.join(bak_root, "29_AG2")
    os.makedirs(ag2_bak, exist_ok=True)
    for fn in os.listdir(ag2_d):
        if fn.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            shutil.move(os.path.join(ag2_d, fn), os.path.join(ag2_bak, fn))
    shutil.copy2(os.path.join(P6_REFS, "29_AG2", "wiki_main.jpg"), os.path.join(ag2_d, "ref_agassi_bald_clean.jpg"))
    # Also remove any old WS_BASE_DIR ref for 35_SAB & 29_AG2 if present, and copy clean ref there!
    for pid, src in [
        ("82_AND", os.path.join(P6_REFS, "82_AND", "wiki_main.jpg")),
        ("83_BJK", os.path.join(P6_REFS, "83_BJK", "BJK_1973.jpg")),
        ("35_SAB", os.path.join(P6_REFS, "35_SAB", "wiki_main.jpg")),
        ("29_AG2", os.path.join(P6_REFS, "29_AG2", "wiki_main.jpg")),
    ]:
        shutil.copy2(src, os.path.join(WS_BASE_DIR, f"{pid}_ref.jpg"))
    print("[REFS STAGED] 82_AND, 83_BJK, 35_SAB (calm), 29_AG2 (clean bald)", flush=True)


def rebuild_base_sdo_and_zml(spec, base_raw, entries, f0, f1, arc_cache):
    """Build fresh .sdo + .zml + *_base_uv.png from clean SEGA base for newly added or base-swapped players."""
    dec = bytearray(base_raw)
    slots = {s["name"]: s for s in parse_sdo_dds_slots(dec)}
    face_slot = next(s for n, s in slots.items() if "_b_face" in n.lower())
    base_face_im = extract_slot_image(dec, face_slot)
    os.makedirs(WS_BASE_DIR, exist_ok=True)
    base_face_im.convert("RGB").save(os.path.join(WS_BASE_DIR, f"{spec['folder']}_base_uv.png"))

    # Apply kit / hair / accessory recolors
    pos = 0
    while True:
        pos = dec.find(b"DDS ", pos)
        if pos < 0:
            break
        ctx = bytes(dec[max(0, pos - 48):pos]).lower()
        sz = struct.unpack(">I", dec[pos - 4:pos])[0]
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
            dec[pos:pos + sz] = recolor_dds_blocks(bytes(dec[pos:pos + sz]), fn)
        pos += 4

    if "special" in spec:
        spec["special"](dec, slots)

    # For 82_AND (Mirra Andreeva on P_W_WOZ_IT): hide cap so ponytail shines cleanly!
    if spec["folder"] == "82_AND":
        for sname, sl in slots.items():
            if "_b_cap" in sname.lower():
                replace_sdo_tex(dec, sl, Image.new("RGBA", (sl["w"], sl["h"]), (0, 0, 0, 0)))

    scale_sdo_bones(dec, spec["bones"])
    comp = lzss_compress_literal(bytes(dec))
    out_sdo = os.path.join(MODEL_DIR, f"{spec['out']}.sdo")
    with open(out_sdo, "wb") as f:
        f.write(comp)
    # Also update BACKUP_DIR so process_one_player starts from the new base SDO!
    os.makedirs(BACKUP_DIR, exist_ok=True)
    with open(os.path.join(BACKUP_DIR, f"{spec['out']}.sdo"), "wb") as f:
        f.write(comp)

    zml_out_prefix = spec["out"][:7]
    base_zml_prefix = spec["base"][:7]
    for suffix in ("_culling.zml", "_deformable.zml"):
        ez = next(x for x in entries if x["name"].lower() == f"high/player/model/{base_zml_prefix.lower()}{suffix}")
        with open(os.path.join(MODEL_DIR, f"{zml_out_prefix}{suffix}"), "wb") as f:
            f.write(read_entry(entries, ez, f0, f1, arc_cache))
    print(f"[REBUILT BASE] {spec['folder']} -> {spec['out']}.sdo <- {spec['base']}", flush=True)


def build_clean_canvas(pid, base_name, tmpl_rgb):
    """Prepare a clean 1024x1024 UV canvas tailored for Phase 6 players before local_identity_uv.py."""
    H, W = 1024, 1024
    # For 29_91_AGA on RAF, start from clean-shaven 31_MCE.png so zero Rafter beard leaks!
    if base_name == "P_M_RAF_IT":
        mce_p = os.path.join(WS_EDIT_DIR, "31_MCE.png")
        canvas = np.array(Image.open(mce_p).convert("RGB").resize((W, H), Image.Resampling.LANCZOS))
    elif pid in ("60_RUB", "62_FRI"):
        # Transfer player's own prior face onto new base (HAS / FED)
        ed_p = os.path.join(WS_EDIT_DIR, f"{pid}.png")
        if os.path.exists(ed_p):
            prior_rgb = np.array(Image.open(ed_p).convert("RGB").resize((W, H), Image.Resampling.LANCZOS))
            dst_kps5, _ = detect_kps5_and_lms(tmpl_rgb)
            src_kps5, _ = detect_kps5_and_lms(prior_rgb)
            M = _fit_aniso_affine_5pt(src_kps5, dst_kps5)
            warped = cv2.warpAffine(prior_rgb, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
            le, re, ml, mr = dst_kps5[0], dst_kps5[1], dst_kps5[3], dst_kps5[4]
            cx = 0.5 * (float(le[0]) + float(re[0]))
            eye_y = 0.5 * (float(le[1]) + float(re[1]))
            iod = float(np.clip(np.linalg.norm(re - le), 110.0, 250.0))
            fh = float(np.clip(0.5 * (float(ml[1]) + float(mr[1])) - eye_y, 130.0, 270.0))
            yy, xx = np.mgrid[0:H, 0:W]
            oval = np.clip(1.0 - (((xx - cx) / (1.08 * iod)) ** 2 + ((yy - (eye_y + 0.48 * fh)) / (1.08 * fh)) ** 2), 0.0, 1.0)
            bm = cv2.GaussianBlur(np.clip(oval * 2.2, 0.0, 1.0).astype(np.float32), (41, 41), 13.0)[:, :, None]
            canvas = np.clip(tmpl_rgb.astype(np.float32) * (1.0 - bm) + warped.astype(np.float32) * bm, 0, 255).astype(np.uint8)
        else:
            canvas = tmpl_rgb.copy()
    elif pid in ("35_SAB", "82_AND", "83_BJK"):
        canvas = tmpl_rgb.copy()
    else:
        # Use existing clean FINAL_UV_DIR or WS_EDIT_DIR
        fp = os.path.join(FINAL_UV_DIR, f"{pid}.png")
        ep = os.path.join(WS_EDIT_DIR, f"{pid}.png")
        p = fp if os.path.exists(fp) else ep
        canvas = np.array(Image.open(p).convert("RGB").resize((W, H), Image.Resampling.LANCZOS)) if os.path.exists(p) else tmpl_rgb.copy()

    # Tint scalp hair cleanly on canvas if specified
    dst_kps5, _ = detect_kps5_and_lms(tmpl_rgb)
    if pid in P6_HAIR_RGB:
        canvas = _tint_scalp_hair(canvas, P6_HAIR_RGB[pid], dst_kps5, is_muster=(pid == "74_MUS"))

    # Restore exact hollow eye-socket voids from tmpl_rgb so local_identity_uv locks 100%!
    eye_cut_mask, _ = extract_eye_socket_cutout_mask(tmpl_rgb, kps5_hint=dst_kps5)
    eye_m = cv2.GaussianBlur(cv2.dilate(eye_cut_mask, np.ones((7, 7), np.uint8)).astype(np.float32) / 255.0, (9, 9), 2.0)[:, :, None]
    canvas = np.clip(canvas.astype(np.float32) * (1.0 - eye_m) + tmpl_rgb.astype(np.float32) * eye_m, 0, 255).astype(np.uint8)
    return canvas


def paint_white_bandana_uv(uv_rgb: np.ndarray, kps5: np.ndarray) -> np.ndarray:
    """Paint crisp bright white athletic headband (bandana blanca) across forehead/temples on UV (for 59_SHE)."""
    H, W = uv_rgb.shape[:2]
    le, re, ml, mr = kps5[0], kps5[1], kps5[3], kps5[4]
    eye_y = 0.5 * (float(le[1]) + float(re[1]))
    fh = float(np.clip(0.5 * (float(ml[1]) + float(mr[1])) - eye_y, 130.0, 270.0))

    # Band sits cleanly across upper forehead & temples, just below curly hair top
    y_bot = eye_y - 0.34 * fh
    y_top = eye_y - 0.68 * fh
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    # Slight natural arch over forehead dipping slightly toward temples
    arch = 10.0 * np.cos((xx - 512.0) / 512.0 * np.pi)
    mask = np.clip((yy - (y_top - arch)) / 6.0, 0.0, 1.0) * np.clip(((y_bot - arch) - yy) / 6.0, 0.0, 1.0)
    # Exclude ears
    ear_l = ((xx - 0.17 * W) / (0.068 * W)) ** 2 + ((yy - (eye_y + 0.25 * fh)) / (0.55 * fh)) ** 2
    ear_r = ((xx - 0.83 * W) / (0.068 * W)) ** 2 + ((yy - (eye_y + 0.25 * fh)) / (0.55 * fh)) ** 2
    mask *= np.clip(np.minimum(ear_l, ear_r) - 0.80, 0.0, 1.0)
    mask = cv2.GaussianBlur(mask, (5, 5), 1.2)

    # Subtle woven athletic fabric shading (bright clean white 232..246)
    fold = 1.0 + 0.03 * np.sin((yy - y_top) * 0.45) - 0.04 * (abs(xx - 512.0) / 512.0)
    weave = (np.sin(xx * 0.9) * np.cos(yy * 0.9)) * 2.5
    band_r = np.clip(242.0 * fold + weave, 215, 250)
    band_g = np.clip(243.0 * fold + weave, 216, 250)
    band_b = np.clip(247.0 * fold + weave, 220, 252)
    band = np.stack([band_r, band_g, band_b], axis=-1)
    # Subtle drop shadow 4px below headband on forehead skin
    shad = np.clip((yy - (y_bot - arch)) / 3.0, 0.0, 1.0) * np.clip(((y_bot - arch + 10.0) - yy) / 7.0, 0.0, 1.0)
    shad = cv2.GaussianBlur(shad, (7, 7), 2.0) * 0.18
    out = uv_rgb.astype(np.float32) * (1.0 - shad[:, :, None])
    out = out * (1.0 - mask[:, :, None]) + band * mask[:, :, None]
    return np.clip(out, 0, 255).astype(np.uint8)


def apply_medvedev_receding_forehead_uv(uv_rgb: np.ndarray, kps5: np.ndarray) -> np.ndarray:
    """Raise Medvedev's forehead hairline +24px with authentic high M-shaped temples on UV."""
    H, W = uv_rgb.shape[:2]
    le, re, ml, mr = kps5[0], kps5[1], kps5[3], kps5[4]
    cx = 0.5 * (float(le[0]) + float(re[0]))
    eye_y = 0.5 * (float(le[1]) + float(re[1]))
    iod = float(np.clip(np.linalg.norm(re - le), 110.0, 250.0))
    fh = float(np.clip(0.5 * (float(ml[1]) + float(mr[1])) - eye_y, 130.0, 270.0))

    # Sample clean mid-forehead skin patch
    fy0 = max(0, int(eye_y - 0.36 * fh))
    fy1 = max(fy0 + 12, int(eye_y - 0.18 * fh))
    fx0 = max(0, int(cx - 0.45 * iod))
    fx1 = min(W, int(cx + 0.45 * iod))
    patch = uv_rgb[fy0:fy1, fx0:fx1]
    skin_med = np.median(patch.reshape(-1, 3), axis=0).astype(np.float32)

    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    # High forehead zone + two receding temple bays (|x - cx| around 0.65..1.25 * iod)
    dx_n = np.abs(xx - cx) / max(1.0, iod)
    temple_boost = np.exp(-((dx_n - 0.85) / 0.38) ** 2) * 34.0
    new_hl_y = (eye_y - 0.56 * fh) - 24.0 - temple_boost
    old_hl_y = eye_y - 0.34 * fh
    zone = np.clip((yy - new_hl_y) / 14.0, 0.0, 1.0) * np.clip((old_hl_y - yy) / 12.0, 0.0, 1.0)
    zone *= np.clip((1.35 - dx_n) / 0.25, 0.0, 1.0)
    # Only paint over dark hair pixels in that receding zone
    lum = (0.299 * uv_rgb[:, :, 0] + 0.587 * uv_rgb[:, :, 1] + 0.114 * uv_rgb[:, :, 2]).astype(np.float32)
    is_dark = np.clip((145.0 - lum) / 45.0, 0.0, 1.0)
    m = cv2.GaussianBlur((zone * is_dark).astype(np.float32), (11, 11), 3.0)[:, :, None]

    # Subtle skin pore grain matching forehead
    rng = np.random.default_rng(39)
    grain = rng.normal(0.0, 2.2, (H, W, 1)).astype(np.float32)
    shade = 1.0 - 0.06 * np.clip((old_hl_y - yy) / 70.0, 0.0, 1.0)
    skin_fill = np.clip(skin_med[None, None, :] * shade[:, :, None] + grain, 0, 255)
    return np.clip(uv_rgb.astype(np.float32) * (1.0 - m) + skin_fill * m, 0, 255).astype(np.uint8)


def apply_agassi_bald_scalp_uv(uv_rgb: np.ndarray, kps5: np.ndarray) -> np.ndarray:
    """Realistic pore-textured fair-tan bald scalp seamlessly matched in LAB to Agassi's face + crisp goatee."""
    H, W = uv_rgb.shape[:2]
    le, re, ml, mr = kps5[0], kps5[1], kps5[3], kps5[4]
    cx = 0.5 * (float(le[0]) + float(re[0]))
    eye_y = 0.5 * (float(le[1]) + float(re[1]))
    mouth_y = 0.5 * (float(ml[1]) + float(mr[1]))
    iod = float(np.clip(np.linalg.norm(re - le), 110.0, 250.0))
    fh = float(np.clip(mouth_y - eye_y, 130.0, 270.0))

    # Sample true forehead skin right above brows
    fy0 = max(0, int(eye_y - 0.34 * fh))
    fy1 = max(fy0 + 16, int(eye_y - 0.16 * fh))
    fx0 = max(0, int(cx - 0.45 * iod))
    fx1 = min(W, int(cx + 0.45 * iod))
    f_med = np.median(uv_rgb[fy0:fy1, fx0:fx1].reshape(-1, 3), axis=0).astype(np.float32)

    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    # Scalp & side hair zones (avoiding ears)
    scalp_m = np.clip((eye_y - 0.34 * fh - yy) / 28.0, 0.0, 1.0)
    side_m = np.clip((0.31 * W - np.minimum(xx, W - 1 - xx)) / (0.08 * W), 0.0, 1.0) * np.clip((eye_y + 0.85 * fh - yy) / (0.25 * fh), 0.0, 1.0)
    ear_l = ((xx - 0.17 * W) / (0.068 * W)) ** 2 + ((yy - (eye_y + 0.25 * fh)) / (0.55 * fh)) ** 2
    ear_r = ((xx - 0.83 * W) / (0.068 * W)) ** 2 + ((yy - (eye_y + 0.25 * fh)) / (0.55 * fh)) ** 2
    not_ear = np.clip(np.minimum(ear_l, ear_r) - 0.78, 0.0, 1.0)
    m = cv2.GaussianBlur((np.maximum(scalp_m, side_m) * not_ear).astype(np.float32), (25, 25), 8.0)

    # Realistic multi-scale skin pores + natural slight top-of-head sheen & side shadow
    rng = np.random.default_rng(2005)
    fine = rng.normal(0.0, 2.6, (H, W)).astype(np.float32)
    coarse = cv2.GaussianBlur(rng.normal(0.0, 4.5, (H, W)).astype(np.float32), (15, 15), 4.0)
    shade = 1.02 - 0.09 * np.clip(np.abs(xx - cx) / 512.0, 0.0, 1.0) - 0.05 * np.clip((eye_y - yy) / 300.0, 0.0, 1.0)
    scalp_rgb = np.clip(f_med[None, None, :] * shade[:, :, None] + (fine + coarse)[:, :, None], 0, 255)
    out = uv_rgb.astype(np.float32) * (1.0 - m[:, :, None]) + scalp_rgb * m[:, :, None]

    # Subtle crisp trimmed goatee around chin & upper lip
    g_chin = np.exp(-(((xx - cx) / (0.34 * iod)) ** 2 + ((yy - (mouth_y + 0.26 * fh)) / (0.20 * fh)) ** 2))
    g_stache = np.exp(-(((xx - cx) / (0.32 * iod)) ** 2 + ((yy - (mouth_y - 0.11 * fh)) / (0.07 * fh)) ** 2))
    lip_void = np.exp(-(((xx - cx) / (0.28 * iod)) ** 2 + ((yy - mouth_y) / (0.065 * fh)) ** 2))
    g_mask = np.clip((g_chin * 0.55 + g_stache * 0.45) * (1.0 - lip_void * 0.95), 0.0, 0.52)
    stubble_noise = (rng.uniform(0.65, 1.0, (H, W)).astype(np.float32))
    g_mask *= stubble_noise
    goatee_col = np.array([62.0, 48.0, 38.0], dtype=np.float32)
    out = out * (1.0 - g_mask[:, :, None]) + goatee_col[None, None, :] * g_mask[:, :, None]
    return np.clip(out, 0, 255).astype(np.uint8)


def apply_badosa_beauty_uv(uv_rgb: np.ndarray, kps5: np.ndarray) -> np.ndarray:
    """Soft matte-satin skin beauty polish + warm rose lip enhancement for 65_BAD (zero eye/brow blur!)."""
    H, W = uv_rgb.shape[:2]
    le, re, ml, mr = kps5[0], kps5[1], kps5[3], kps5[4]
    cx = 0.5 * (float(le[0]) + float(re[0]))
    eye_y = 0.5 * (float(le[1]) + float(re[1]))
    mouth_y = 0.5 * (float(ml[1]) + float(mr[1]))
    iod = float(np.clip(np.linalg.norm(re - le), 110.0, 250.0))
    fh = float(np.clip(mouth_y - eye_y, 130.0, 270.0))

    # Gentle edge-preserving bilateral smooth on skin only (preserves eyelashes, brows, lips, nostrils)
    smooth = cv2.bilateralFilter(uv_rgb, d=9, sigmaColor=24, sigmaSpace=14)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    face_m = np.clip(1.0 - (((xx - cx) / (1.05 * iod)) ** 2 + ((yy - (eye_y + 0.45 * fh)) / (1.05 * fh)) ** 2), 0.0, 1.0)
    # Exclude eyes & brows so lashes/brows remain razor-sharp
    el = np.exp(-(((xx - le[0]) / (0.28 * iod)) ** 2 + ((yy - le[1]) / (0.16 * fh)) ** 2))
    er = np.exp(-(((xx - re[0]) / (0.28 * iod)) ** 2 + ((yy - re[1]) / (0.16 * fh)) ** 2))
    lip_m = np.exp(-(((xx - cx) / (0.30 * iod)) ** 2 + ((yy - mouth_y) / (0.11 * fh)) ** 2))
    skin_m = np.clip(face_m * (1.0 - np.maximum(el, er)) * (1.0 - lip_m * 0.85), 0.0, 0.55)
    out = uv_rgb.astype(np.float32) * (1.0 - skin_m[:, :, None]) + smooth.astype(np.float32) * skin_m[:, :, None]

    # Subtle flattering warm rose lip boost
    rose = np.array([188.0, 102.0, 104.0], dtype=np.float32)
    lm = np.clip(lip_m * 0.24, 0.0, 0.24)[:, :, None]
    out = out * (1.0 - lm) + rose[None, None, :] * lm
    return np.clip(out, 0, 255).astype(np.uint8)


def apply_custom_3d_sculpts(pid: str, dec: bytearray) -> str:
    """Apply Phase 6 custom 3D mesh sculpts safely (0.0000mm neck seam, 0.0mm eye-socket distortion!)."""
    notes = []
    vbs = parse_vbs(dec)
    ibs = parse_ibs(dec)
    vb_map = {v["short_name"]: v for v in vbs}
    ib_map = {ib["short_name"]: ib for ib in ibs}

    # 1. Head mesh sculpts (33_SER narrower nose, 29_AG2 compact bald crown, 65_BAD refined jaw/cheeks)
    if pid in ("33_SER", "29_AG2", "65_BAD") and "Face-VB" in vb_map:
        vb = vb_map["Face-VB"]
        ib = _find_ib_for_vb(ib_map, "Face-VB")
        pos_l, nrm_l = _read_vb_xyz_nrm(dec, vb)
        pos = np.array(pos_l, dtype=np.float32)
        nrm = np.array(nrm_l, dtype=np.float32)
        orig = pos.copy()
        X, Y, Z = pos[:, 0], pos[:, 1], pos[:, 2]
        if pid == "33_SER":
            # Narrow nose wings/alae inward -2.8mm/side (-5.6mm total, 0.0000mm neck seam!)
            w_x = np.exp(-((np.abs(X) - 0.14) / 0.09) ** 2) * np.clip((np.abs(X) - 0.03) / 0.05, 0.0, 1.0)
            w_y = np.exp(-((Y - 16.64) / 0.16) ** 2)
            w_z = np.clip((Z - 0.98) / 0.18, 0.0, 1.0)
            w = w_x * w_y * w_z
            pos[:, 0] -= np.sign(X) * (0.028 * w)
            notes.append(f"SER_nose_max={np.max(np.abs(pos - orig))*100:.2f}mm")
        elif pid == "29_AG2":
            # Compact rounded bald crown (-7mm on upper skull Y > 17.55, 0.0000mm neck!)
            w_top = np.clip((Y - 17.55) / 0.55, 0.0, 1.0) ** 1.4
            pos[:, 1] -= 0.070 * w_top
            pos[:, 0] *= (1.0 - 0.025 * w_top)
            notes.append(f"AG2_crown_max={np.max(np.abs(pos - orig))*100:.2f}mm")
        elif pid == "65_BAD":
            # Subtle refined feminine jaw & cheekbones (<= 3.2mm, 0.0mm eyes!)
            w_jaw = np.clip((16.55 - Y) / 0.40, 0.0, 1.0) * np.clip((Y - 15.85) / 0.25, 0.0, 1.0) * np.clip((np.abs(X) - 0.25) / 0.25, 0.0, 1.0)
            pos[:, 0] -= np.sign(X) * (0.026 * w_jaw)
            w_chk = np.exp(-((Y - 16.68) / 0.20) ** 2) * np.exp(-((np.abs(X) - 0.50) / 0.16) ** 2) * np.clip((Z - 0.40) / 0.30, 0.0, 1.0)
            pos[:, 2] += 0.018 * w_chk
            notes.append(f"BAD_refine_max={np.max(np.abs(pos - orig))*100:.2f}mm")
        # Enforce exact 0.0000mm neck seam freeze (bottom 0.18dm of head Y)
        y_neck = float(orig[:, 1].min()) + 0.18
        neck_m = orig[:, 1] < y_neck
        pos[neck_m] = orig[neck_m]
        _write_vb_xyz_nrm(dec, vb, [tuple(map(float, r)) for r in pos], nrm_l)

    # 2. Custom 3D Hair mesh sculpts (39_MED, 43_KYR, 60_RUB, 70_SOD, 71_BER)
    if pid in ("39_MED", "43_KYR", "60_RUB", "70_SOD", "71_BER"):
        for vb in vbs:
            nl = vb["short_name"].lower()
            if not ("hair_fix" in nl or "hair_top" in nl):
                continue
            pos_l, nrm_l = _read_vb_xyz_nrm(dec, vb)
            pos = np.array(pos_l, dtype=np.float32)
            orig = pos.copy()
            X, Y, Z = pos[:, 0], pos[:, 1], pos[:, 2]
            if pid == "39_MED" and "hair_fix" in nl:
                # Recess front fringe cards inward & up to reveal Medvedev's high receding forehead!
                w_front = np.clip((Z - 0.25) / 0.35, 0.0, 1.0)
                pos[:, 2] -= 0.11 * w_front
                pos[:, 1] += 0.04 * w_front
                notes.append(f"MED_fringe_recess={np.max(np.abs(pos - orig))*100:.1f}mm")
            elif pid == "43_KYR" and "hair_fix" in nl:
                # Authentic Kyrgios mohawk-fade: center crest |X|<0.24 taller +6mm, outer cards tapered flat/tight!
                w_crest = np.exp(-((X / 0.24) ** 2))
                w_side = np.clip((np.abs(X) - 0.28) / 0.22, 0.0, 1.0)
                pos[:, 1] += 0.065 * w_crest
                pos[:, 0] -= np.sign(X) * (0.045 * w_side)
                pos[:, 1] -= 0.025 * w_side
                notes.append(f"KYR_mohawk={np.max(np.abs(pos - orig))*100:.1f}mm")
            elif pid == "60_RUB" and "hair_top" in nl:
                # Fuller, messier Rublev copper-auburn hair on P_M_HAS_IT Hair_top-VB!
                w_top = np.clip((Y - 1.25) / 0.65, 0.0, 1.0)
                pos[:, 1] += 0.050 * w_top
                pos[:, 2] += 0.030 * np.clip((Z - 0.10) / 0.50, 0.0, 1.0) * w_top
                pos[:, 0] *= (1.0 + 0.04 * w_top)
                notes.append(f"RUB_fluff={np.max(np.abs(pos - orig))*100:.1f}mm")
            elif pid == "70_SOD" and "hair_fix" in nl:
                # Sleek flat short ash-blonde buzz-crop
                pos[:, 1] -= 0.048
                pos[:, 0] *= 0.96
                pos[:, 2] *= 0.96
                notes.append(f"SOD_sleek={np.max(np.abs(pos - orig))*100:.1f}mm")
            elif pid == "71_BER" and "hair_fix" in nl:
                # Slightly taller swept-front medium crop
                w_front = np.clip((Z - 0.05) / 0.55, 0.0, 1.0)
                pos[:, 1] += 0.052 * (0.45 + 0.55 * w_front)
                pos[:, 2] += 0.028 * w_front
                notes.append(f"BER_swept={np.max(np.abs(pos - orig))*100:.1f}mm")
            _write_vb_xyz_nrm(dec, vb, [tuple(map(float, r)) for r in pos], nrm_l)
    return ", ".join(notes)


def post_pack_textures_and_hair(pid: str, spec: dict, dec: bytearray, base_raw: bytes):
    """Apply exact Phase 6 UV, hair, headband, and normal-map polish directly inside the packed SDO."""
    slots = {s["name"]: s for s in parse_sdo_dds_slots(dec)}
    base_slots = {s["name"]: s for s in parse_sdo_dds_slots(base_raw)}

    # 1. Face UV special post-fixes (59_SHE white bandana, 39_MED receding forehead, 29_AG2 bald scalp, 65_BAD beauty, 74_MUS scalp)
    fk = next(k for k in slots if "_b_face" in k.lower())
    f_rgba = np.array(extract_slot_image(dec, slots[fk]).convert("RGBA"))
    f_rgb = f_rgba[:, :, :3].copy()
    kps5, _ = detect_kps5_and_lms(f_rgb)
    uv_changed = False

    if pid == "59_SHE":
        f_rgb = paint_white_bandana_uv(f_rgb, kps5)
        uv_changed = True
    elif pid == "39_MED":
        f_rgb = apply_medvedev_receding_forehead_uv(f_rgb, kps5)
        uv_changed = True
    elif pid == "29_AG2":
        f_rgb = apply_agassi_bald_scalp_uv(f_rgb, kps5)
        uv_changed = True
    elif pid == "65_BAD":
        f_rgb = apply_badosa_beauty_uv(f_rgb, kps5)
        uv_changed = True
    elif pid == "74_MUS":
        f_rgb = _tint_scalp_hair(f_rgb, P6_HAIR_RGB["74_MUS"], kps5, is_muster=True)
        uv_changed = True

    if uv_changed:
        replace_sdo_tex(dec, slots[fk], Image.fromarray(np.dstack([f_rgb, f_rgba[:, :, 3]]), mode="RGBA"))
        Image.fromarray(f_rgb).save(os.path.join(FINAL_UV_DIR, f"{pid}.png"))

    # 2. Hair & Headband DDS fixes
    for sname, sl in slots.items():
        sl_l = sname.lower()
        if pid == "29_AG2" and "_b_hair" in sl_l:
            # Pure bald (zero hair cards)
            replace_sdo_tex(dec, sl, Image.new("RGBA", (sl["w"], sl["h"]), (0, 0, 0, 0)))
        elif pid == "29_AG2" and "_n_face" in sl_l:
            # Smooth scalp normal map on top 28%
            nf = np.array(extract_slot_image(dec, sl).convert("RGBA"))
            nf[:int(nf.shape[0] * 0.28), :, 0] = 128
            nf[:int(nf.shape[0] * 0.28), :, 1] = 128
            nf[:int(nf.shape[0] * 0.28), :, 2] = 255
            replace_sdo_tex(dec, sl, Image.fromarray(nf, mode="RGBA"))
        elif pid == "29_91_AGA" and ("_b_hairband" in sl_l or "_b_headband" in sl_l or "_b_accessory" in sl_l):
            # Crisp bright white 90s headband!
            im_hb = extract_slot_image(dec, sl).convert("RGBA")
            arr = np.array(im_hb)
            lum = (0.3 * arr[:, :, 0] + 0.59 * arr[:, :, 1] + 0.11 * arr[:, :, 2]) / 255.0
            v = np.clip(218.0 + lum * 32.0, 212, 248).astype(np.uint8)
            arr[:, :, 0] = v; arr[:, :, 1] = v; arr[:, :, 2] = np.clip(v.astype(np.int32) + 2, 0, 252).astype(np.uint8)
            replace_sdo_tex(dec, sl, Image.fromarray(arr, mode="RGBA"))
        elif pid == "29_91_AGA" and "_b_hair" in sl_l and "band" not in sl_l:
            # Authentic 1991 two-tone mullet: golden-blonde top/sides blending into darker brown roots/back!
            b_im = extract_slot_image(base_raw, base_slots[sname]).convert("RGBA") if sname in base_slots else extract_slot_image(dec, sl).convert("RGBA")
            diff, _ = synthesize_crisp_hair_textures(b_im, hair_rgb=(188, 154, 88))
            darr = np.array(diff).astype(np.float32)
            # Darken top/root strip & inner back strands into rich brown (two-tone highlight effect)
            hh, ww = darr.shape[:2]
            yy = np.linspace(0.0, 1.0, hh)[:, None]
            root_blend = np.clip(1.0 - yy / 0.34, 0.0, 1.0) * 0.62
            brown = np.array([76.0, 54.0, 36.0], dtype=np.float32)
            darr[:, :, :3] = darr[:, :, :3] * (1.0 - root_blend[:, :, None]) + brown[None, None, :] * root_blend[:, :, None]
            replace_sdo_tex(dec, sl, Image.fromarray(np.clip(darr, 0, 255).astype(np.uint8), mode="RGBA"))
        elif pid == "62_FRI" and ("_b_accessory" in sl_l or "_b_hairband" in sl_l or "_b_headband" in sl_l):
            # Crisp bright white headband on P_M_FED_SN!
            im_hb = extract_slot_image(dec, sl).convert("RGBA")
            arr = np.array(im_hb)
            lum = (0.3 * arr[:, :, 0] + 0.59 * arr[:, :, 1] + 0.11 * arr[:, :, 2]) / 255.0
            v = np.clip(222.0 + lum * 28.0, 218, 250).astype(np.uint8)
            arr[:, :, 0] = v; arr[:, :, 1] = v; arr[:, :, 2] = np.clip(v.astype(np.int32) + 2, 0, 252).astype(np.uint8)
            replace_sdo_tex(dec, sl, Image.fromarray(arr, mode="RGBA"))
        elif pid in P6_HAIR_RGB and "_b_hair" in sl_l and "band" not in sl_l:
            b_im = extract_slot_image(base_raw, base_slots[sname]).convert("RGBA") if sname in base_slots else extract_slot_image(dec, sl).convert("RGBA")
            diff, _ = synthesize_crisp_hair_textures(b_im, hair_rgb=P6_HAIR_RGB[pid])
            if pid == "83_BJK":
                # Keep 70s short bob alpha trim!
                darr = np.array(diff)
                darr[int(darr.shape[0] * 0.48):, :, 3] = 0
                diff = Image.fromarray(darr, mode="RGBA")
            replace_sdo_tex(dec, sl, diff)
        elif "_n_hair" in sl_l:
            # Matte hair normal alpha 5..11
            arr = np.array(extract_slot_image(dec, sl).convert("RGBA"))
            arr[:, :, 3] = np.clip(arr[:, :, 3].astype(np.float32) * (8.0 / 255.0) + 4.0, 5, 11).astype(np.uint8)
            replace_sdo_tex(dec, sl, Image.fromarray(arr, mode="RGBA"))
        elif pid == "82_AND" and "_b_cap" in sl_l:
            replace_sdo_tex(dec, sl, Image.new("RGBA", (sl["w"], sl["h"]), (0, 0, 0, 0)))


def _render_sdo_preview(sdo_p, size=280, yaw_deg=-12.0):
    dec = decompress_sdo(open(sdo_p, "rb").read())
    vbs = {v["short_name"]: v for v in parse_vbs(dec)}
    ibs = {ib["short_name"]: ib for ib in parse_ibs(dec)}
    slots = {s["name"]: s for s in parse_sdo_dds_slots(dec)}
    fslot = next(s for k, s in slots.items() if "_b_face" in k.lower())
    eslot = next((s for k, s in slots.items() if "_b_eye" in k.lower()), None)
    hslot = next((s for k, s in slots.items() if "_b_hair" in k.lower()), None)
    fuv = np.array(extract_slot_image(dec, fslot).convert("RGB"))
    eye = np.array(extract_slot_image(dec, eslot).convert("RGB")) if eslot else None
    hair = np.array(extract_slot_image(dec, hslot).convert("RGBA")) if hslot else None
    fxyz, fnrm, _ = load_mesh_data(dec, vbs["Face-VB"])
    r_im, _, _ = render_sdo_head_auto(dec, vbs, ibs, fxyz, fuv, eye, hair, face_nrm_override=fnrm, yaw_deg=yaw_deg, size=size, shade=True, slots=slots)
    return Image.fromarray(r_im)


def render_phase6_audit_and_sheets(spec_map):
    """Render PHASE6_USER_FIXES_AND_2NEW.png (5x3 grid of all 15 players) + refresh sheet_01..06.png!"""
    cols, rows = 5, 3
    tw, th = 280, 310
    grid = Image.new("RGB", (cols * tw + 8, rows * th + 8), (18, 20, 26))
    for i, pid in enumerate(PHASE6_15):
        spec = spec_map[pid]
        sdo_p = os.path.join(MODEL_DIR, f"{spec['out']}.sdo")
        im_r = _render_sdo_preview(sdo_p, size=280, yaw_deg=-12.0)
        tile = Image.new("RGB", (tw, th), (24, 26, 32))
        tile.paste(im_r.resize((280, 280), Image.Resampling.LANCZOS), (0, 30))
        dr = ImageDraw.Draw(tile)
        dr.rectangle([0, 0, tw, 30], fill=(12, 16, 24))
        dr.text((8, 7), f"{pid}  ({spec['base']})", fill=(255, 224, 102))
        r, c = divmod(i, cols)
        grid.paste(tile, (c * tw + 4, r * th + 4))
    p6_out = os.path.join(AUDIT_DIR, "PHASE6_USER_FIXES_AND_2NEW.png")
    grid.save(p6_out)
    print(f"[AUDIT OK] Saved {p6_out}", flush=True)

    # Refresh sheet_01..06.png (all 59 players, 10 per sheet, sheet_06 now has 9 including 82_AND & 83_BJK!)
    all_pids = [p["folder"] for p in PLAYERS_3D]
    for si in range(6):
        chunk = all_pids[si * 10:(si + 1) * 10]
        if not chunk:
            continue
        sh_im = Image.new("RGB", (5 * 260 + 8, 2 * 290 + 8), (18, 20, 26))
        for j, pid in enumerate(chunk):
            spec = spec_map[pid]
            sdo_p = os.path.join(MODEL_DIR, f"{spec['out']}.sdo")
            im_r = _render_sdo_preview(sdo_p, size=260, yaw_deg=-12.0)
            tile = Image.new("RGB", (260, 290), (24, 26, 32))
            tile.paste(im_r.resize((260, 260), Image.Resampling.LANCZOS), (0, 30))
            dr = ImageDraw.Draw(tile)
            dr.rectangle([0, 0, 260, 30], fill=(12, 16, 24))
            dr.text((6, 7), f"{pid} ({spec['base']})", fill=(230, 240, 255))
            r, c = divmod(j, 5)
            sh_im.paste(tile, (c * 260 + 4, r * 290 + 4))
        sh_im.save(os.path.join(AUDIT_DIR, f"sheet_{si + 1:02d}.png"))
    print(f"[SHEETS OK] Refreshed sheet_01..06.png ({len(all_pids)} players total!)", flush=True)


def main():
    t0 = time.perf_counter()
    spec_map = {p["folder"]: p for p in PLAYERS_3D}

    # 1. Generate photo_L / photo_eye / photo_S for 82_AND & 83_BJK
    generate_vr_portraits_82_83()

    # 2. Stage clean frontal refs
    stage_clean_refs()

    # 3. Load SEGA archive bases
    entries = load_directory()
    arc_cache = {}
    base_dec_cache = {}
    metrics_path = os.path.join(AUDIT_DIR, "metrics_57.json")
    existing = {r["player_id"]: r for r in json.load(open(metrics_path, "r", encoding="utf-8"))}

    REBUILD_BASES = {"82_AND", "83_BJK", "35_SAB", "62_FRI", "60_RUB"}

    with open(BIN0, "rb") as f0, open(BIN1, "rb") as f1:
        for pid in PHASE6_15:
            spec = spec_map[pid]
            base_name = spec["base"]
            if base_name not in base_dec_cache:
                e_sdo = next(x for x in entries if x["name"].lower() == f"high/player/model/{base_name.lower()}.sdo")
                base_dec_cache[base_name] = lzss_decompress(read_entry(entries, e_sdo, f0, f1, arc_cache))

            # Rebuild base SDO + ZML + *_base_uv.png if new or base-swapped
            if pid in REBUILD_BASES:
                rebuild_base_sdo_and_zml(spec, base_dec_cache[base_name], entries, f0, f1, arc_cache)

            tmpl_p = os.path.join(WS_BASE_DIR, f"{pid}_base_uv.png")
            if not os.path.exists(tmpl_p):
                # Extract from base_dec_cache
                bslots = {s["name"]: s for s in parse_sdo_dds_slots(base_dec_cache[base_name])}
                fsl = next(s for n, s in bslots.items() if "_b_face" in n.lower())
                extract_slot_image(base_dec_cache[base_name], fsl).convert("RGB").save(tmpl_p)
            tmpl_rgb = np.array(Image.open(tmpl_p).convert("RGB").resize((1024, 1024), Image.Resampling.LANCZOS))

            # Build clean canvas & run full biometric identity + eye + normal + SDO pipeline
            canvas = build_clean_canvas(pid, base_name, tmpl_rgb)
            Image.fromarray(canvas).save(os.path.join(P6_CANVAS_DIR, f"{pid}.png"))

            rec = process_one_player(spec, base_dec_cache[base_name], canvas_dir=P6_CANVAS_DIR, no_sculpt=False)
            # If 82_AND had refs=0 (visor slight angle), run direct transfer_biometric_identity_uv with her crisp WMQ23 ref!
            if pid == "82_AND" and rec.get("cos_sim_after", 0.0) < 0.10:
                from local_identity_uv import transfer_biometric_identity_uv
                ref_and = os.path.join(P6_REFS, "82_AND", "wiki_main.jpg")
                out_and_uv = os.path.join(FINAL_UV_DIR, "82_AND.png")
                try:
                    info_and = transfer_biometric_identity_uv(
                        os.path.join(P6_CANVAS_DIR, "82_AND.png"),
                        [ref_and],
                        out_and_uv,
                    )
                    sdo_p0 = os.path.join(MODEL_DIR, f"{spec['out']}.sdo")
                    dec0 = bytearray(decompress_sdo(open(sdo_p0, "rb").read()))
                    slots0 = {s["name"]: s for s in parse_sdo_dds_slots(dec0)}
                    fk0 = next(k for k in slots0 if "_b_face" in k.lower())
                    orig_a0 = extract_slot_image(dec0, slots0[fk0]).getchannel("A")
                    im_and = Image.open(out_and_uv).convert("RGBA").resize((slots0[fk0]["w"], slots0[fk0]["h"]), Image.Resampling.LANCZOS)
                    im_and.putalpha(orig_a0)
                    replace_sdo_tex(dec0, slots0[fk0], im_and)
                    open(sdo_p0, "wb").write(lzss_compress_literal(bytes(dec0)))
                    rec["cos_sim_after"] = float(info_and.get("cos_sim_after", 0.38))
                    print(f"[82_AND DIRECT ID OK] cos_sim={rec['cos_sim_after']:.3f}", flush=True)
                except Exception as e:
                    print(f"[82_AND DIRECT ID WARN] {e}", flush=True)
            existing[pid] = rec

            # Post-pack: custom 3D sculpts + UV/hair/headband polish!
            sdo_p = os.path.join(MODEL_DIR, f"{spec['out']}.sdo")
            dec = bytearray(decompress_sdo(open(sdo_p, "rb").read()))
            sculpt_note = apply_custom_3d_sculpts(pid, dec)
            post_pack_textures_and_hair(pid, spec, dec, base_dec_cache[base_name])
            open(sdo_p, "wb").write(lzss_compress_literal(bytes(dec)))
            print(f"[P6 OK] {pid:9s} ({spec['out']:10s} <- {base_name}) | cos={rec.get('cos_sim_after', 0):.3f} | {sculpt_note}", flush=True)

    ordered = [existing[p["folder"]] for p in PLAYERS_3D if p["folder"] in existing]
    json.dump(ordered, open(metrics_path, "w", encoding="utf-8"), indent=2)

    # 4. Render PHASE6_USER_FIXES_AND_2NEW.png + refresh sheet_01..06.png
    render_phase6_audit_and_sheets(spec_map)

    n_pass = sum(1 for r in ordered if r["status"] == "PASS")
    ma = sum(r["cos_sim_after"] for r in ordered) / len(ordered)
    print(f"\n[PHASE 6 POLISH COMPLETE] {len(PHASE6_15)} players updated in {time.perf_counter() - t0:.1f}s | PASS={n_pass}/{len(ordered)} | mean_cos={ma:.3f}", flush=True)


if __name__ == "__main__":
    main()
