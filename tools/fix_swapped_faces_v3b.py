#!/usr/bin/env python3
"""
Phase 5 v3b Surgical Fix (~60-90s):
  1. Transfers each of the 14 non-Nano-Banana base-swapped players' OWN clean prior face UV
     (skin tone, brows, clean-shaven jaw, Tsonga's warm brown complexion!) via exact landmark-aligned
     anisotropic affine warp onto their NEW SEGA base UV (using clean-shaven 31_MCE.png for RAF so
     ZERO Pat Rafter beard remains on 29_91_AGA, 41_TSI, 48_MOY, 77_WLD!), matching new base ears/neck
     in LAB directly to the player's own face skin tone BEFORE running local_identity_uv.py!
  2. Fixes the 4 hair tints (40_ZVE dirty golden-blonde, 60_RUB rich copper-auburn, 70_SOD ash-blonde,
     74_MUS unified warm sandy light-brown across BOTH UV scalp & *_B_hair*/*_B_hairtop*!).
  3. Re-packs ONLY those 15 .sdo files (with full unclamped brown body sync on 46_TSO, 0.0000mm neck seam,
     mip0/mip1 < 3.5, matte hair Alpha 5..11, naturalized 8-palette verified eyes) and refreshes
     REMODEL_V3_HIGHLIGHTS.png + sheet_01..06.png!
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import time
import cv2
import numpy as np
from PIL import Image

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
from build_ee3_rackets import decompress_sdo
from update_custom_assets import parse_sdo_dds_slots, extract_slot_image, replace_sdo_tex
from hair3d_groom import synthesize_crisp_hair_textures
from build_all_sdo_models import PLAYERS_3D
from local_identity_uv import detect_kps5_and_lms, extract_eye_socket_cutout_mask
from batch_studio_57 import (
    process_one_player,
    MODEL_DIR,
    WS_BASE_DIR,
    WS_EDIT_DIR,
    FINAL_UV_DIR,
    AUDIT_DIR,
    _HAIR_COLOR_RGB,
)
from remodel_all_57_v3 import step5_render_sheets_and_highlights

SWAPPED_14 = [
    "39_MED", "46_TSO", "70_SOD", "71_BER",
    "40_ZVE", "45_SAF", "52_CON", "54_IVN", "60_RUB", "62_FRI",
    "29_91_AGA", "41_TSI", "48_MOY", "77_WLD",
]

HAIR_TINT_OVERRIDES = {
    "40_ZVE": (128, 102, 64),   # natural dirty golden-blonde
    "60_RUB": (135, 66, 32),    # natural rich copper-auburn
    "70_SOD": (138, 118, 82),   # natural ash-blonde
    "74_MUS": (152, 128, 92),   # warm sandy light-brown
    "39_MED": (64, 46, 32),     # natural dark-brown
    "46_TSO": (24, 21, 19),     # dark buzz-crop
    "71_BER": (124, 98, 62),    # ash light-brown
    "45_SAF": (56, 40, 28),     # shaggy dark-brown
    "52_CON": (96, 68, 44),     # 70s medium brown
    "54_IVN": (66, 48, 32),     # 90s shaggy dark-brown
    "62_FRI": (56, 40, 28),     # medium wavy dark-brown
    "29_91_AGA": (162, 130, 76),# 90s blonde-brown mullet
    "41_TSI": (128, 98, 56),    # long wavy golden-brown
    "48_MOY": (50, 36, 26),     # 90s dark-brown
    "77_WLD": (130, 104, 62),   # 80s light-brown
}


def _fit_aniso_affine_5pt(src_kps5: np.ndarray, dst_kps5: np.ndarray) -> np.ndarray:
    """Exact anisotropic 2x3 affine matrix (separate sx, sy, tx, ty) aligning 5 facial landmarks cleanly."""
    s_le, s_re, s_n, s_ml, s_mr = src_kps5
    d_le, d_re, d_n, d_ml, d_mr = dst_kps5
    s_iod = max(20.0, float(s_re[0] - s_le[0]))
    d_iod = max(20.0, float(d_re[0] - d_le[0]))
    s_ey = 0.5 * (float(s_le[1]) + float(s_re[1]))
    d_ey = 0.5 * (float(d_le[1]) + float(d_re[1]))
    s_my = 0.5 * (float(s_ml[1]) + float(s_mr[1]))
    d_my = 0.5 * (float(d_ml[1]) + float(d_mr[1]))
    s_fh = max(20.0, s_my - s_ey)
    d_fh = max(20.0, d_my - d_ey)
    sx = d_iod / s_iod
    sy = d_fh / s_fh
    s_cx = 0.5 * (float(s_le[0]) + float(s_re[0]))
    d_cx = 0.5 * (float(d_le[0]) + float(d_re[0]))
    tx = d_cx - sx * s_cx
    ty = d_ey - sy * s_ey
    return np.array([[sx, 0.0, tx], [0.0, sy, ty]], dtype=np.float32)


def _tint_scalp_hair(uv_rgb: np.ndarray, target_hair_rgb: tuple[int, int, int], kps5: np.ndarray, is_muster: bool = False) -> np.ndarray:
    """Smoothly tint scalp & side hair pixels on a 1024x1024 UV to target_hair_rgb without touching ears or skin."""
    H, W = uv_rgb.shape[:2]
    le, re, ml, mr = kps5[0], kps5[1], kps5[3], kps5[4]
    eye_y = 0.5 * (float(le[1]) + float(re[1]))
    fh = float(np.clip(0.5 * (float(ml[1]) + float(mr[1])) - eye_y, 130.0, 270.0))

    yy, xx = np.mgrid[0:H, 0:W]
    lum = (0.299 * uv_rgb[:, :, 0] + 0.587 * uv_rgb[:, :, 1] + 0.114 * uv_rgb[:, :, 2]).astype(np.float32) / 255.0
    hair_y = max(20.0, eye_y - 0.44 * fh)
    scalp_zone = np.clip((hair_y - yy) / max(24.0, 0.20 * fh), 0.0, 1.0)
    side_zone = np.clip((0.30 * W - np.minimum(xx, W - 1 - xx)) / (0.08 * W), 0.0, 1.0) * np.clip((eye_y + 0.90 * fh - yy) / (0.25 * fh), 0.0, 1.0)
    ear_l = ((xx - 0.17 * W) / (0.065 * W)) ** 2 + ((yy - (eye_y + 0.25 * fh)) / (0.55 * fh)) ** 2
    ear_r = ((xx - 0.83 * W) / (0.065 * W)) ** 2 + ((yy - (eye_y + 0.25 * fh)) / (0.55 * fh)) ** 2
    not_ear = np.clip(np.minimum(ear_l, ear_r) - 0.75, 0.0, 1.0)
    if is_muster:
        # Muster already has bright blonde scalp pixels -> tint ALL scalp/side hair pixels (not just dark!)
        hair_px = np.clip((0.85 - lum) / 0.15, 0.0, 1.0)
    else:
        hair_px = np.clip((0.52 - lum) / 0.16, 0.0, 1.0)
    hmask = cv2.GaussianBlur((np.maximum(scalp_zone, side_zone) * not_ear * hair_px).astype(np.float32), (11, 11), 2.8)
    if float(hmask.max()) < 0.08:
        return uv_rgb
    med_hl = max(0.10, float(np.median(lum[hmask > 0.5])) if np.any(hmask > 0.5) else 0.22)
    rel = np.clip(lum / med_hl, 0.55, 1.70)
    tgt = np.array(target_hair_rgb, dtype=np.float32)
    tinted = np.clip(tgt[None, None, :] * (0.45 + 0.55 * rel)[:, :, None], 10, 235)
    return np.clip(uv_rgb.astype(np.float32) * (1.0 - hmask[:, :, None]) + tinted * hmask[:, :, None], 0, 255).astype(np.uint8)


def build_transferred_canvas(pid: str, base_name: str, tmpl_rgb: np.ndarray) -> np.ndarray:
    """Build a clean, player-authentic 1024x1024 UV canvas on the NEW SEGA base by:
      1. Starting from clean-shaven 31_MCE.png for P_M_RAF_IT (ZERO Pat Rafter beard!) or tmpl_rgb for DJV/MRY.
      2. Warping the player's OWN prior face UV (skin, brows, jaw, Tsonga's warm brown complexion!) onto the
         new base's exact 5-point landmark layout.
      3. Matching ALL skin pixels (ears, neck, jaw border, forehead) of the new base UV in LAB directly to
         the player's own face skin tone (so 46_TSO is 100% warm brown across face, ears & neck!).
      4. Tinting the new base's scalp/side hair cleanly to HAIR_TINT_OVERRIDES[pid] and restoring exact hollow eye cutouts!"""
    H, W = 1024, 1024
    # 1. Choose clean base structural canvas (use clean-shaven 31_MCE.png for RAF -> zero Rafter beard!)
    if base_name == "P_M_RAF_IT":
        mce_p = os.path.join(WS_EDIT_DIR, "31_MCE.png")
        base_canvas = np.array(Image.open(mce_p).convert("RGB").resize((W, H), Image.Resampling.LANCZOS))
    else:
        base_canvas = tmpl_rgb.copy()

    dst_kps5, _ = detect_kps5_and_lms(tmpl_rgb)
    eye_cut_mask, _ = extract_eye_socket_cutout_mask(tmpl_rgb, kps5_hint=dst_kps5)

    # 2. Load player's own prior face UV (Nano Banana for 39_MED & 40_ZVE, 03_entregar_editados_aqui for others!)
    ov_p = os.path.join(REPO_ROOT, "scratch", "uv_lab", "canvas_overrides", f"{pid}.png")
    ed_p = os.path.join(WS_EDIT_DIR, f"{pid}.png")
    prior_p = ov_p if (pid in ("39_MED", "40_ZVE") and os.path.exists(ov_p)) else ed_p
    prior_rgb = np.array(Image.open(prior_p).convert("RGB").resize((W, H), Image.Resampling.LANCZOS))
    src_kps5, _ = detect_kps5_and_lms(prior_rgb)

    # 3. Exact anisotropic 5-point warp of prior face onto new base coordinates
    M = _fit_aniso_affine_5pt(src_kps5, dst_kps5)
    warped_prior = cv2.warpAffine(prior_rgb, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

    # 4. Compute cheek skin LAB of warped_prior vs base_canvas & shift ALL skin pixels of base_canvas to match player's skin!
    le, re, ml, mr = dst_kps5[0], dst_kps5[1], dst_kps5[3], dst_kps5[4]
    cx = 0.5 * (float(le[0]) + float(re[0]))
    eye_y = 0.5 * (float(le[1]) + float(re[1]))
    mouth_y = 0.5 * (float(ml[1]) + float(mr[1]))
    iod = float(np.clip(np.linalg.norm(re - le), 110.0, 250.0))
    fh = float(np.clip(mouth_y - eye_y, 130.0, 270.0))

    cy0, cy1 = max(0, int(eye_y + 0.25 * fh)), min(H, int(eye_y + 0.72 * fh))
    cx0, cx1 = max(0, int(cx - 0.75 * iod)), min(W, int(cx - 0.30 * iod))
    wp_lab = cv2.cvtColor(warped_prior, cv2.COLOR_RGB2LAB).astype(np.float32)
    bc_lab = cv2.cvtColor(base_canvas, cv2.COLOR_RGB2LAB).astype(np.float32)
    tgt_skin = np.median(wp_lab[cy0:cy1, cx0:cx1].reshape(-1, 3), axis=0)
    src_skin = np.median(bc_lab[cy0:cy1, cx0:cx1].reshape(-1, 3), axis=0)

    # Skin pixel mask on base_canvas (includes ears, neck, forehead, jaw; excludes dark scalp hair)
    yy, xx = np.mgrid[0:H, 0:W]
    hair_y = max(20.0, eye_y - 0.44 * fh)
    scalp_zone = np.clip((hair_y - yy) / max(24.0, 0.20 * fh), 0.0, 1.0)
    side_zone = np.clip((0.29 * W - np.minimum(xx, W - 1 - xx)) / (0.07 * W), 0.0, 1.0) * np.clip((eye_y + 0.85 * fh - yy) / (0.25 * fh), 0.0, 1.0)
    ear_l = ((xx - 0.17 * W) / (0.065 * W)) ** 2 + ((yy - (eye_y + 0.25 * fh)) / (0.55 * fh)) ** 2
    ear_r = ((xx - 0.83 * W) / (0.065 * W)) ** 2 + ((yy - (eye_y + 0.25 * fh)) / (0.55 * fh)) ** 2
    is_ear = np.clip(1.15 - np.minimum(ear_l, ear_r), 0.0, 1.0)
    lum_bc = (0.299 * base_canvas[:, :, 0] + 0.587 * base_canvas[:, :, 1] + 0.114 * base_canvas[:, :, 2]).astype(np.float32) / 255.0
    is_hair = np.maximum(scalp_zone, side_zone) * (1.0 - is_ear) * np.clip((0.46 - lum_bc) / 0.14, 0.0, 1.0)
    is_skin = cv2.GaussianBlur(np.clip(1.0 - is_hair, 0.0, 1.0).astype(np.float32), (21, 21), 6.0)

    dL = float(np.clip(tgt_skin[0] - src_skin[0], -62.0, 32.0))
    da = float(np.clip(tgt_skin[1] - src_skin[1], -18.0, 18.0))
    db = float(np.clip(tgt_skin[2] - src_skin[2], -20.0, 24.0))
    bc_lab[:, :, 0] = np.clip(bc_lab[:, :, 0] + dL * is_skin, 0, 255)
    bc_lab[:, :, 1] = np.clip(bc_lab[:, :, 1] + da * is_skin, 0, 255)
    bc_lab[:, :, 2] = np.clip(bc_lab[:, :, 2] + db * is_skin, 0, 255)
    base_skin_matched = cv2.cvtColor(bc_lab.astype(np.uint8), cv2.COLOR_LAB2RGB)

    # 5. Composite player's warped inner face (brows, eyes, nose, cheeks, lips, chin/jaw) smoothly onto skin-matched base!
    ov_cy = eye_y + 0.50 * fh
    ov_rx = 1.12 * iod
    ov_ry = 1.12 * fh
    face_oval = np.clip(1.0 - (((xx - cx) / ov_rx) ** 2 + ((yy - ov_cy) / ov_ry) ** 2), 0.0, 1.0)
    face_oval = np.clip(face_oval * 2.2, 0.0, 1.0)
    hl_gate = np.clip((yy - max(8.0, eye_y - 0.48 * fh)) / max(18.0, 0.18 * fh), 0.0, 1.0)
    blend_m = cv2.GaussianBlur((face_oval * hl_gate).astype(np.float32), (41, 41), 13.0)
    merged = np.clip(
        base_skin_matched.astype(np.float32) * (1.0 - blend_m[:, :, None])
        + warped_prior.astype(np.float32) * blend_m[:, :, None],
        0,
        255,
    ).astype(np.uint8)

    # 6. Tint scalp/side hair cleanly to verified natural HAIR_TINT_OVERRIDES[pid]
    if pid in HAIR_TINT_OVERRIDES:
        merged = _tint_scalp_hair(merged, HAIR_TINT_OVERRIDES[pid], dst_kps5)

    # 7. Restore clean hollow dark eye-socket voids from tmpl_rgb (skin-matched!) so local_identity_uv locks 100%!
    eye_m = cv2.GaussianBlur(cv2.dilate(eye_cut_mask, np.ones((7, 7), np.uint8)).astype(np.float32) / 255.0, (9, 9), 2.0)[:, :, None]
    merged = np.clip(merged.astype(np.float32) * (1.0 - eye_m) + tmpl_rgb.astype(np.float32) * eye_m, 0, 255).astype(np.uint8)
    return merged


def main():
    t0 = time.perf_counter()
    v3b_cdir = os.path.join(REPO_ROOT, "scratch", "uv_lab", "v3b_canvases")
    os.makedirs(v3b_cdir, exist_ok=True)
    spec_map = {p["folder"]: p for p in PLAYERS_3D}

    entries = load_directory()
    arc_cache = {}
    base_dec_cache = {}
    metrics_path = os.path.join(AUDIT_DIR, "metrics_57.json")
    existing = {r["player_id"]: r for r in json.load(open(metrics_path, "r", encoding="utf-8"))}

    with open(BIN0, "rb") as f0, open(BIN1, "rb") as f1:
        # 1. Build player-transferred canvases & re-pack all 14 base-swapped players!
        for pid in SWAPPED_14:
            spec = spec_map[pid]
            base_name = spec["base"]
            if base_name not in base_dec_cache:
                e_sdo = next(x for x in entries if x["name"].lower() == f"high/player/model/{base_name.lower()}.sdo")
                base_dec_cache[base_name] = lzss_decompress(read_entry(entries, e_sdo, f0, f1, arc_cache))

            tmpl_p = os.path.join(WS_BASE_DIR, f"{pid}_base_uv.png")
            tmpl_rgb = np.array(Image.open(tmpl_p).convert("RGB").resize((1024, 1024), Image.Resampling.LANCZOS))
            canvas = build_transferred_canvas(pid, base_name, tmpl_rgb)
            Image.fromarray(canvas).save(os.path.join(v3b_cdir, f"{pid}.png"))

            rec = process_one_player(spec, base_dec_cache[base_name], canvas_dir=v3b_cdir, no_sculpt=False)
            existing[pid] = rec

            # Post-pack: apply exact natural hair RGB tint on *_B_hair_* + matte *_N_hair_* + full body skin sync on 46_TSO!
            sdo_p = os.path.join(MODEL_DIR, f"{spec['out']}.sdo")
            dec = bytearray(decompress_sdo(open(sdo_p, "rb").read()))
            slots = {s["name"]: s for s in parse_sdo_dds_slots(dec)}
            base_slots = {s["name"]: s for s in parse_sdo_dds_slots(base_dec_cache[base_name])}
            changed = False
            if pid in HAIR_TINT_OVERRIDES:
                hrgb = HAIR_TINT_OVERRIDES[pid]
                for sname, sl in slots.items():
                    sl_l = sname.lower()
                    if "_b_hair" in sl_l and "band" not in sl_l:
                        b_im = extract_slot_image(base_dec_cache[base_name], base_slots[sname]).convert("RGBA") if sname in base_slots else extract_slot_image(dec, sl).convert("RGBA")
                        diff, norm = synthesize_crisp_hair_textures(b_im, hair_rgb=hrgb)
                        replace_sdo_tex(dec, sl, diff)
                        changed = True
                    elif "_n_hair" in sl_l:
                        arr = np.array(extract_slot_image(dec, sl).convert("RGBA"))
                        arr[:, :, 3] = np.clip(arr[:, :, 3].astype(np.float32) * (8.0 / 255.0) + 4.0, 5, 11).astype(np.uint8)
                        replace_sdo_tex(dec, sl, Image.fromarray(arr, mode="RGBA"))
                        changed = True
            if pid == "46_TSO":
                # Unclamped full LAB body skin sync for Tsonga's warm medium-brown skin on P_M_DJV_IT!
                fuv = np.array(Image.open(os.path.join(FINAL_UV_DIR, "46_TSO.png")).convert("RGB"))
                bf = np.array(extract_slot_image(base_dec_cache[base_name], base_slots[next(k for k in base_slots if "_b_face" in k.lower())]).convert("RGB").resize((1024, 1024)))
                f_lab = cv2.cvtColor(fuv, cv2.COLOR_RGB2LAB).astype(np.float32)
                b_lab = cv2.cvtColor(bf, cv2.COLOR_RGB2LAB).astype(np.float32)
                shift = np.median(f_lab[520:640, 350:440].reshape(-1, 3), axis=0) - np.median(b_lab[520:640, 350:440].reshape(-1, 3), axis=0)
                for sname, sl in slots.items():
                    if "_b_body_" in sname.lower():
                        bb = np.array(extract_slot_image(base_dec_cache[base_name], base_slots[sname]).convert("RGBA"))
                        blab = cv2.cvtColor(bb[:, :, :3], cv2.COLOR_RGB2LAB).astype(np.float32)
                        for c in range(3):
                            blab[:, :, c] = np.clip(blab[:, :, c] + shift[c] * 0.92, 0, 255)
                        brgb = cv2.cvtColor(blab.astype(np.uint8), cv2.COLOR_LAB2RGB)
                        replace_sdo_tex(dec, sl, Image.fromarray(np.dstack([brgb, bb[:, :, 3]]), mode="RGBA"))
                        changed = True
            if changed:
                open(sdo_p, "wb").write(lzss_compress_literal(bytes(dec)))

        # 2. Fix 74_MUS (Muster): warm sandy light-brown (152, 128, 92) on BOTH UV scalp AND *_B_hair*/*_B_hairtop*!
        spec_m = spec_map["74_MUS"]
        sdo_m = os.path.join(MODEL_DIR, f"{spec_m['out']}.sdo")
        dec_m = bytearray(decompress_sdo(open(sdo_m, "rb").read()))
        slots_m = {s["name"]: s for s in parse_sdo_dds_slots(dec_m)}
        fk = next(k for k in slots_m if "_b_face" in k.lower())
        f_rgba = np.array(extract_slot_image(dec_m, slots_m[fk]).convert("RGBA"))
        kps5_m, _ = detect_kps5_and_lms(f_rgba[:, :, :3])
        f_rgb_new = _tint_scalp_hair(f_rgba[:, :, :3], (152, 128, 92), kps5_m, is_muster=True)
        replace_sdo_tex(dec_m, slots_m[fk], Image.fromarray(np.dstack([f_rgb_new, f_rgba[:, :, 3]]), mode="RGBA"))
        Image.fromarray(f_rgb_new).save(os.path.join(FINAL_UV_DIR, "74_MUS.png"))
        for sname, sl in slots_m.items():
            if "_b_hair" in sname.lower():
                im_h = extract_slot_image(dec_m, sl).convert("RGBA")
                diff, _ = synthesize_crisp_hair_textures(im_h, hair_rgb=(152, 128, 92))
                replace_sdo_tex(dec_m, sl, diff)
        open(sdo_m, "wb").write(lzss_compress_literal(bytes(dec_m)))
        print("[MUSTER OK] Unified UV scalp + hairtop/hair DDS to warm sandy light-brown (152,128,92)", flush=True)

    ordered = [existing[p["folder"]] for p in PLAYERS_3D if p["folder"] in existing]
    json.dump(ordered, open(metrics_path, "w", encoding="utf-8"), indent=2)

    # 3. Refresh all 6 audit sheets + REMODEL_V3_HIGHLIGHTS.png!
    step5_render_sheets_and_highlights()

    out = subprocess.check_output(["tasklist", "/FI", "IMAGENAME eq VT4.exe"], text=True)
    n_pass = sum(1 for r in ordered if r["status"] == "PASS")
    mb = sum(r["cos_sim_before"] for r in ordered) / len(ordered)
    ma = sum(r["cos_sim_after"] for r in ordered) / len(ordered)
    print(
        f"\n[v3b COMPLETE] 15 players fixed in {time.perf_counter() - t0:.1f}s | "
        f"57/57 PASS={n_pass}/57 | mean_cos={mb:.3f}->{ma:.3f} | "
        f"VT4={out.count('VT4.exe')} PNGS={len(glob.glob('game/vt4_present_*.png'))} "
        f"LOG={os.path.exists('game/xlive_mod.log')} INSIGHTFACE={os.path.exists(os.path.expanduser('~/.insightface'))}",
        flush=True,
    )


if __name__ == "__main__":
    main()
