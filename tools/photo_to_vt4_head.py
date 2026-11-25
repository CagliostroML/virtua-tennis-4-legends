#!/usr/bin/env python3
"""
Studio-Grade Dual-View Photo-to-3D Facemaker Pipeline for Virtua Tennis 4 (.sdo) Player Models.
Pilot target: Carlos Alcaraz (26_ALC, P_M_ALC_NG.sdo from P_M_DJV_IT.sdo base).

v3 Studio Polish (incorporating all 5 Hydrogen QA audit fixes):
  1. Eye-socket & Eyeball Z-alignment:
     - True anatomical LeftEye_zero/RightEye_zero Z depth (no white sclera poking out in Left Profile or 3/4!).
     - Tightly wrapped outer orbital rim / lateral canthus around the shifted (+3.2mm/eye) eyeball.
  2. Clean Closer-Set Ears (Zero Horizontal Stripes, Zero Double-Ear Ghost):
     - Smoothly tucks outer/upper Djokovic ear helix inward by -3.8mm toward skull to match Alcaraz's ears.
     - Excludes ear UV islands from grazing side projection, preserving crisp UV-aligned 3D ear detail color-matched to Alcaraz's skin.
  3. Cool Charcoal-Black Barbershop High Skin-Fade + Seamless Forehead-to-Temple Blend:
     - Preserves cool neutral charcoal-ash stubble chroma (#1e1d1c -> rosy-tan skin) on the shaved fade above/behind the ear
       (zero warm orange-brown fade tint!) and eliminates the diagonal temple hairline notch.
  4. Mouth Seam, Nostril Pinch & Nasolabial Cleanup:
     - Cleanly paints out the pale horizontal lip-parting seam with natural lip color + subtle crease,
       softens nostril pinch dots, and relaxes smiling nasolabial creases for a composed athletic expression.
  5. Healthy Rosier Mediterranean Skin Tone + Thicker Dark Brows + Lower Textured Hair_fix Fringe + +2mm Lip/Chin Z-Projection.
"""
import argparse
import io
import os
import struct
import sys
import cv2
import numpy as np
from PIL import Image
from scipy.interpolate import RBFInterpolator
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

from vt4_archive import BIN0, BIN1, load_directory, read_entry
from compress_sega_lzss import lzss_compress_literal
from build_ee3_rackets import parse_vbs, parse_ibs, decompress_sdo
from sculpt_sdo_head import (
    _strip_to_tris,
    _find_ib_for_vb,
    _read_vb_xyz_nrm,
    _write_vb_xyz_nrm,
    _recalc_blended_normals,
    _shift_eye_bones,
)
from update_custom_assets import parse_sdo_dds_slots, extract_slot_image, replace_sdo_tex
from import_edited_face_uvs import (
    _soften_face_ao_alpha,
    _upgrade_hd_eyes,
    _soften_face_normals,
)


def load_mesh_data(dec: bytes, vb: dict):
    s = vb["streams"][0]
    base = vb["data_off"] + s["off"]
    st = s["stride"]
    n = s["nverts"]
    xyz = np.zeros((n, 3), dtype=np.float32)
    nrm = np.zeros((n, 4), dtype=np.int32)
    uv = np.zeros((n, 2), dtype=np.float32)
    for i in range(n):
        off = base + i * st
        xyz[i] = struct.unpack_from(">3f", dec, off)
        nrm[i] = struct.unpack_from(">4h", dec, off + 12)
        u_raw, v_raw = struct.unpack_from(">2h", dec, off + 20)
        uv[i, 0] = u_raw / 65536.0 + 0.5
        uv[i, 1] = v_raw / 65536.0 + 0.5
    if n > 0 and float(uv[:, 0].max()) < 0.55 and float(uv[:, 1].max()) < 0.55:
        uv = np.clip(uv * 2.0, 0.0, 1.0)
    return xyz, nrm, uv


def detect_478(det, rgb_img: np.ndarray) -> np.ndarray:
    H, W = rgb_img.shape[:2]
    mp_im = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_img)
    res = det.detect(mp_im)
    if not res.face_landmarks:
        raise RuntimeError("MediaPipe failed to detect face landmarks")
    lms = res.face_landmarks[0]
    out = np.zeros((len(lms), 3), dtype=np.float32)
    for k, lm in enumerate(lms):
        out[k, 0] = lm.x * W
        out[k, 1] = lm.y * H
        out[k, 2] = lm.z * W
    return out


def extract_profile_silhouette(prof_rgb: np.ndarray):
    """Extract sub-pixel front face profile & rear cranium silhouette mask from studio profile_best.jpg."""
    H, W = prof_rgb.shape[:2]
    bg = np.median(prof_rgb[220:750, 20:140].reshape(-1, 3), axis=0)
    r_minus_b = prof_rgb[:, :, 0].astype(np.float32) - prof_rgb[:, :, 2].astype(np.float32)
    dist_bg = np.linalg.norm(prof_rgb.astype(np.float32) - bg[None, None, :], axis=2)
    fg = ((r_minus_b > 18.0) | (dist_bg > 32.0)).astype(np.uint8) * 255
    gray = cv2.cvtColor(prof_rgb, cv2.COLOR_RGB2GRAY)
    is_white_bg = (gray > 180) & (r_minus_b < 16.0)
    fg[is_white_bg] = 0
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    num_l, labels, stats, _ = cv2.connectedComponentsWithStats(fg)
    best_l = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    head_mask = (labels == best_l).astype(np.uint8)
    yy, xx = np.mgrid[0:H, 0:W]
    collar_line = 920.0 - 0.56 * np.maximum(0.0, xx - 450.0)
    head_mask[yy > collar_line] = 0
    head_mask[yy > 810] = 0
    return head_mask


def render_ortho_head(
    dec: bytes,
    vbs: dict,
    ibs: dict,
    face_xyz: np.ndarray,
    face_tex: np.ndarray,
    eye_tex: np.ndarray,
    hair_tex_rgba: np.ndarray,
    eye_dx: float = 0.0,
    eye_dy: float = 0.0,
    eye_dz: float = 0.0,
    hair_xyz: np.ndarray | None = None,
    face_nrm_override: np.ndarray | None = None,
    yaw_deg: float = 0.0,
    shade: bool = False,
    y_mid: float = 16.65,
    scale: float = 370.0,
):
    """Orthographic 3D head renderer with smooth per-vertex normals, true LeftEye_zero/RightEye_zero depth,
    and proper RGBA alpha-blending for Hair_fix-VB."""
    W = H = 1024
    img = np.full((H, W, 3), 48, dtype=np.uint8)
    zbuf = np.full((H, W), -1e9, dtype=np.float32)
    xyz_buf = np.zeros((H, W, 3), dtype=np.float32)
    valid_buf = np.zeros((H, W), dtype=bool)
    cx = 512.0
    cy = 512.0
    z_mid = 0.42

    rad = np.deg2rad(yaw_deg)
    ca, sa = float(np.cos(rad)), float(np.sin(rad))
    light_dir = np.array([0.22, 0.35, 0.91], dtype=np.float32)
    light_dir /= np.linalg.norm(light_dir)

    def project_pt(p):
        px = p[0]
        py = p[1] - y_mid
        pz = p[2] - z_mid
        rx = px * ca - pz * sa
        rz = px * sa + pz * ca
        return cx + rx * scale, cy - py * scale, rz

    def rast(pts, tris, uvs, tex, z_bias=0.0, record_xyz=True, alpha_blend=False, vnrm=None, eye_darken=False):
        th, tw = tex.shape[:2]
        has_alpha = (tex.shape[2] == 4)
        for a, b, c in tris:
            pa, pb, pc = pts[a], pts[b], pts[c]
            xa, ya, za = project_pt(pa)
            xb, yb, zb = project_pt(pb)
            xc, yc, zc = project_pt(pc)
            det = (yb - yc) * (xa - xc) + (xc - xb) * (ya - yc)
            if abs(det) < 1e-4:
                continue
            x0 = max(0, int(min(xa, xb, xc)))
            x1 = min(W - 1, int(max(xa, xb, xc)) + 1)
            y0 = max(0, int(min(ya, yb, yc)))
            y1 = min(H - 1, int(max(ya, yb, yc)) + 1)
            if x0 > x1 or y0 > y1:
                continue
            yy, xx = np.mgrid[y0 : y1 + 1, x0 : x1 + 1]
            w0 = ((yb - yc) * (xx - xc) + (xc - xb) * (yy - yc)) / det
            w1 = ((yc - ya) * (xx - xc) + (xa - xc) * (yy - yc)) / det
            w2 = 1.0 - w0 - w1
            m = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4)
            if not np.any(m):
                continue
            zz = w0 * za + w1 * zb + w2 * zc
            m = m & ((zz + z_bias) > zbuf[y0 : y1 + 1, x0 : x1 + 1])
            if not np.any(m):
                continue
            uu = (w0 * uvs[a, 0] + w1 * uvs[b, 0] + w2 * uvs[c, 0])[m]
            vv = (w0 * uvs[a, 1] + w1 * uvs[b, 1] + w2 * uvs[c, 1])[m]
            tx = np.clip((uu * tw).astype(np.int32), 0, tw - 1)
            ty = np.clip((vv * th).astype(np.int32), 0, th - 1)
            if alpha_blend and has_alpha:
                rgba = tex[ty, tx]
                al = rgba[:, 3].astype(np.float32) / 255.0
                vis = al > 0.08
                if not np.any(vis):
                    continue
                dst = img[y0 : y1 + 1, x0 : x1 + 1][m].astype(np.float32)
                src = rgba[:, :3].astype(np.float32)
                if shade and vnrm is not None:
                    na = vnrm[a, :3].astype(np.float32)
                    nb = vnrm[b, :3].astype(np.float32)
                    nc = vnrm[c, :3].astype(np.float32)
                    nx = (w0 * na[0] + w1 * nb[0] + w2 * nc[0])[m]
                    ny = (w0 * na[1] + w1 * nb[1] + w2 * nc[1])[m]
                    nz = (w0 * na[2] + w1 * nb[2] + w2 * nc[2])[m]
                    nlen = np.sqrt(nx * nx + ny * ny + nz * nz) + 1e-6
                    nx /= nlen; ny /= nlen; nz /= nlen
                    rnx = nx * ca - nz * sa
                    rny = ny
                    rnz = nx * sa + nz * ca
                    ndotl = np.clip(rnx * light_dir[0] + rny * light_dir[1] + rnz * light_dir[2], 0.0, 1.0)
                    src = src * (0.76 + 0.44 * ndotl)[:, None]
                blended = dst * (1.0 - al[:, None]) + src * al[:, None]
                img[y0 : y1 + 1, x0 : x1 + 1][m] = np.clip(blended, 0, 255).astype(np.uint8)
                opaque_m = m.copy()
                opaque_m[m] = al > 0.65
                zbuf[y0 : y1 + 1, x0 : x1 + 1][opaque_m] = (zz + z_bias)[opaque_m]
            else:
                zbuf[y0 : y1 + 1, x0 : x1 + 1][m] = (zz + z_bias)[m]
                if record_xyz:
                    xyz_buf[y0 : y1 + 1, x0 : x1 + 1, 0][m] = (w0 * pa[0] + w1 * pb[0] + w2 * pc[0])[m]
                    xyz_buf[y0 : y1 + 1, x0 : x1 + 1, 1][m] = (w0 * pa[1] + w1 * pb[1] + w2 * pc[1])[m]
                    xyz_buf[y0 : y1 + 1, x0 : x1 + 1, 2][m] = (w0 * pa[2] + w1 * pb[2] + w2 * pc[2])[m]
                    valid_buf[y0 : y1 + 1, x0 : x1 + 1][m] = True
                if shade and vnrm is not None:
                    na = vnrm[a, :3].astype(np.float32)
                    nb = vnrm[b, :3].astype(np.float32)
                    nc = vnrm[c, :3].astype(np.float32)
                    nx = (w0 * na[0] + w1 * nb[0] + w2 * nc[0])[m]
                    ny = (w0 * na[1] + w1 * nb[1] + w2 * nc[1])[m]
                    nz = (w0 * na[2] + w1 * nb[2] + w2 * nc[2])[m]
                    nlen = np.sqrt(nx * nx + ny * ny + nz * nz) + 1e-6
                    nx /= nlen; ny /= nlen; nz /= nlen
                    rnx = nx * ca - nz * sa
                    rny = ny
                    rnz = nx * sa + nz * ca
                    ndotl = np.clip(rnx * light_dir[0] + rny * light_dir[1] + rnz * light_dir[2], 0.0, 1.0)
                    sh = (0.72 + 0.31 * ndotl)[:, None]
                else:
                    sh = 1.0
                col = tex[ty, tx, :3].astype(np.float32) * sh
                if eye_darken and abs(yaw_deg) > 25.0:
                    # Realistic brow/eyelid socket ambient occlusion in side & 3/4 views
                    col *= (0.68 if abs(yaw_deg) > 65.0 else 0.86)
                img[y0 : y1 + 1, x0 : x1 + 1][m] = np.clip(col, 0, 255).astype(np.uint8)

    # 1. Left & Right eyeballs positioned at true LeftEye_zero / RightEye_zero anatomical Z (1.095 + eye_dz!)
    for eye_name, ex_sign in (("LeftEye-VB", -1.0), ("RightEye-VB", 1.0)):
        evb = vbs[eye_name]
        eib = _find_ib_for_vb(ibs, eye_name)
        es = evb["streams"][0]
        ebase = evb["data_off"] + es["off"]
        est = es["stride"]
        epts = np.array([struct.unpack_from(">3f", dec, ebase + i * est) for i in range(es["nverts"])], dtype=np.float32)
        epts[:, 0] += ex_sign * (0.2592 + eye_dx)
        epts[:, 1] += 16.9738 + eye_dy
        epts[:, 2] += 1.096 + eye_dz
        euvs = np.array([((u + 32768) / 32768.0, (v + 32768) / 32768.0) for u, v in (struct.unpack_from(">2h", dec, ebase + i * est + 24) for i in range(es["nverts"]))], dtype=np.float32)
        # Render eyeball strictly behind Face-VB socket rims (z_bias = -0.025 in profile so outer orbital rim occludes sclera cleanly!)
        ebias = -0.025 if abs(yaw_deg) > 45.0 else -0.08
        rast(epts, _strip_to_tris(eib["inds"]), euvs, eye_tex, z_bias=ebias, record_xyz=True, alpha_blend=False, eye_darken=True)

    # 2. Face-VB
    fvb = vbs["Face-VB"]
    fib = _find_ib_for_vb(ibs, "Face-VB")
    _, fnrm_b, fuvs = load_mesh_data(dec, fvb)
    vnrm_use = face_nrm_override if face_nrm_override is not None else fnrm_b
    rast(face_xyz, _strip_to_tris(fib["inds"]), fuvs, face_tex, z_bias=0.0, record_xyz=True, alpha_blend=False, vnrm=vnrm_use)

    # 3. Hair_fix-VB with proper RGBA alpha blending & outward-normal crown shading
    hvb = vbs["Hair_fix-VB"]
    hib = _find_ib_for_vb(ibs, "Hair_fix-VB")
    hxyz, hnrm, huvs = load_mesh_data(dec, hvb)
    if hair_xyz is not None:
        hxyz = hair_xyz
        # Compute clean outward spherical normals from head center for smooth 3D crown form shading
        hc = np.array([0.0, 17.05, 0.38], dtype=np.float32)
        hvec = hxyz - hc[None, :]
        hlen = np.linalg.norm(hvec, axis=1, keepdims=True) + 1e-6
        hnrm = np.hstack([((hvec / hlen) * 16384.0).astype(np.int32), np.zeros((len(hxyz), 1), dtype=np.int32)])
    rast(hxyz, _strip_to_tris(hib["inds"]), huvs, hair_tex_rgba, z_bias=0.015, record_xyz=False, alpha_blend=True, vnrm=hnrm)

    return img, xyz_buf, valid_buf


def delight_front_photo(front_rgb: np.ndarray, lms_photo: np.ndarray, base_face_rgb: np.ndarray):
    """Delight front_best.jpg into Carlos Alcaraz's healthier, slightly rosier Mediterranean tan
    (away from Djokovic's sallow yellow-olive!), with thick dark eyebrows and relaxed smile creases."""
    H, W = front_rgb.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W]

    lab = cv2.cvtColor(front_rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    L, A, B = lab[:, :, 0], lab[:, :, 1], lab[:, :, 2]

    cheek_idx = [50, 101, 118, 119, 120, 47, 126, 209, 49, 131, 134, 51, 5, 281, 363, 360, 279, 429, 355, 277, 349, 348, 347, 330, 280, 425, 266, 371, 352, 345, 372, 340, 108, 151, 337]
    c_pts = lms_photo[cheek_idx, :2].astype(np.int32)
    p_skin_samples = lab[np.clip(c_pts[:, 1], 0, H - 1), np.clip(c_pts[:, 0], 0, W - 1)]
    med_L, pA_med, pB_med = np.median(p_skin_samples, axis=0)

    # Thick dark Alcaraz eyebrows (expanded slightly vertically & toward inner brow!)
    brow_L_idx = [70, 63, 105, 66, 107, 55, 65, 52, 53, 46]
    brow_R_idx = [336, 296, 334, 293, 300, 285, 295, 282, 283, 276]
    brow_mask = np.zeros((H, W), dtype=np.float32)
    for b_idx in (brow_L_idx, brow_R_idx):
        b_pts = lms_photo[b_idx, :2].copy()
        b_pts[:5, 1] -= 11.5
        b_pts[5:, 1] += 4.0
        cv2.fillPoly(brow_mask, [b_pts.astype(np.int32)], 1.0)
    brow_mask = cv2.GaussianBlur(brow_mask, (17, 17), 4.5)

    lip_idx = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291, 375, 321, 405, 314, 17, 84, 181, 91, 146]
    lip_mask = np.zeros((H, W), dtype=np.float32)
    cv2.fillPoly(lip_mask, [lms_photo[lip_idx, :2].astype(np.int32)], 1.0)
    lip_mask = cv2.GaussianBlur(lip_mask, (15, 15), 4.0)

    w_skin = np.clip((L - (med_L - 62.0)) / 34.0, 0.0, 1.0) * (1.0 - brow_mask)

    # Restrict brow_mask strictly to dark brow hair pixels (never desaturate lit skin above the brow!)
    brow_hair_w = np.clip(((med_L - 10.0) - L) / 32.0, 0.0, 1.0)
    brow_mask = brow_mask * brow_hair_w

    # Gently delight reddish dark under-brow shadow right above upper eyelids
    eL = lms_photo[468, :2]
    eR = lms_photo[473, :2]
    g_underbrow = (
        np.exp(-0.5 * (((xx - eL[0]) / 68.0) ** 2 + ((yy - (eL[1] - 15.0)) / 18.0) ** 2))
        + np.exp(-0.5 * (((xx - eR[0]) / 68.0) ** 2 + ((yy - (eR[1] - 15.0)) / 18.0) ** 2))
    )
    g_underbrow = np.clip(g_underbrow * (1.0 - brow_mask), 0.0, 1.0)
    ub_dip = np.maximum(0.0, (med_L - 10.0) - L)
    L = L + 0.56 * ub_dip * g_underbrow

    # Deepen & enrich Alcaraz's thick dark eyebrows (+26% darker contrast on actual brow hairs)
    L = L * (1.0 - 0.26 * brow_mask)

    L_blur = cv2.GaussianBlur(L, (75, 75), 25.0)
    flash_diff = L_blur - med_L
    corr = np.where(flash_diff > 0, -0.65 * flash_diff, -0.20 * flash_diff * w_skin)
    L_delit = L + corr * w_skin
    over = np.maximum(0.0, L_delit - (med_L + 12.0))
    L_delit = L_delit - 0.65 * over * w_skin

    # Soften smiling nasolabial creases & under-lip groove so resting 3D face looks composed (not mid-grin!)
    mc_L = lms_photo[61, :2]
    mc_R = lms_photo[291, :2]
    al_L = lms_photo[129, :2]
    al_R = lms_photo[358, :2]
    lm_18 = lms_photo[18, :2]
    lm_2 = lms_photo[2, :2]

    nl_L = 0.42 * al_L + 0.58 * (mc_L + np.array([-16.0, -6.0]))
    nl_R = 0.42 * al_R + 0.58 * (mc_R + np.array([+16.0, -6.0]))
    g_nasolab_L = np.exp(-0.5 * (((xx - nl_L[0]) / 28.0) ** 2 + ((yy - nl_L[1]) / 52.0) ** 2))
    g_nasolab_R = np.exp(-0.5 * (((xx - nl_R[0]) / 28.0) ** 2 + ((yy - nl_R[1]) / 52.0) ** 2))
    g_under_lip = np.exp(-0.5 * (((xx - lm_18[0]) / 30.0) ** 2 + ((yy - (lm_18[1] + 3.0)) / 16.0) ** 2))
    g_under_nose = np.exp(-0.5 * (((xx - lm_2[0]) / 24.0) ** 2 + ((yy - (lm_2[1] + 6.0)) / 14.0) ** 2))

    g_crease = np.clip(
        (0.86 * (g_nasolab_L + g_nasolab_R) + 0.80 * g_under_lip + 0.68 * g_under_nose) * (1.0 - lip_mask),
        0.0,
        1.0,
    )
    L_bright_local = cv2.GaussianBlur(L_delit, (55, 55), 18.0) + 3.0
    shadow_dip = np.maximum(0.0, L_bright_local - L_delit)
    L_delit = L_delit + 0.82 * shadow_dip * g_crease

    # HEALTHIER, SLIGHTLY ROSIER MEDITERRANEAN SKIN TONE (away from Djokovic's sallow yellow-olive!)
    base_lab = cv2.cvtColor(base_face_rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    bL_med = float(np.median(base_lab[520:640, 350:440, 0]))
    bA_med = float(np.median(base_lab[520:640, 350:440, 1]))
    bB_med = float(np.median(base_lab[520:640, 350:440, 2]))

    # Blend closer to Alcaraz's real warm-rosy photo complexion (+6.5 L, +3.2 A, -4.2 B vs Djokovic's yellow base!)
    tgt_L = bL_med + 6.8
    tgt_A = bA_med + 3.2
    tgt_B = bB_med - 4.2
    target_skin_lab = np.array([tgt_L, tgt_A, tgt_B], dtype=np.float32)

    L_out = np.clip(L_delit + (tgt_L - med_L) * (1.0 - 0.88 * brow_mask), 0, 255)

    A_smooth = cv2.GaussianBlur(A, (75, 75), 25.0) - pA_med
    B_smooth = cv2.GaussianBlur(B, (75, 75), 25.0) - pB_med
    A_skin = tgt_A + np.clip(0.20 * A_smooth, -1.8, 2.4)
    B_skin = tgt_B + np.clip(0.20 * B_smooth, -1.8, 2.2)

    A_lip = tgt_A + np.clip((A - pA_med) * 0.50 + 5.2, 3.0, 11.5)
    B_lip = tgt_B - 1.5

    # Neutral dark charcoal-espresso eyebrows (not brown-yellow!)
    A_brow = 129.5
    B_brow = 131.5

    A_out = A_skin * (1.0 - lip_mask) + A_lip * lip_mask
    B_out = B_skin * (1.0 - lip_mask) + B_lip * lip_mask
    A_out = A_out * (1.0 - 0.78 * brow_mask) + A_brow * (0.78 * brow_mask)
    B_out = B_out * (1.0 - 0.78 * brow_mask) + B_brow * (0.78 * brow_mask)

    out_lab = np.stack([np.clip(L_out, 0, 255), np.clip(A_out, 0, 255), np.clip(B_out, 0, 255)], axis=-1).astype(np.uint8)
    return cv2.cvtColor(out_lab, cv2.COLOR_LAB2RGB), target_skin_lab


def delight_profile_photo(prof_rgb: np.ndarray, target_skin_lab: np.ndarray) -> np.ndarray:
    """Color-match profile_best.jpg side skin to exact healthy rosy-tan target_skin_lab and suppress
    studio-flash white/silver glare on the shaved high-fade so every fade pixel is a pure convex blend
    of dark black-brown hair (#1a1715) and warm tanned scalp skin (ZERO white/gray 'canas'!)."""
    H, W = prof_rgb.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W]
    lab = cv2.cvtColor(prof_rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    L, A, B = lab[:, :, 0], lab[:, :, 1], lab[:, :, 2]

    cheek_patch = lab[470:590, 460:580].reshape(-1, 3)
    pL_med, pA_med, pB_med = np.median(cheek_patch, axis=0)

    tgt_L, tgt_A, tgt_B = target_skin_lab

    # Fade/scalp zone: above ear top (y < 465) and behind ear (x > 735)
    in_fade_zone = np.clip(((465.0 - yy) / 85.0) + ((xx - 730.0) / 70.0), 0.0, 1.0)
    in_fade_zone = cv2.GaussianBlur(in_fade_zone.astype(np.float32), (25, 25), 8.0)

    # Suppress bright white studio-flash specular reflection on the shaved fade/scalp (L > pL_med - 15 in fade zone!)
    # Pulling bright glare on buzzed hair down smoothly kills any silvery/white 'canas' glare!
    L_blur = cv2.GaussianBlur(L, (81, 81), 28.0)
    L_delit = L - 0.35 * np.maximum(0.0, L_blur - pL_med)
    # In the fade zone, compress any bright specular glare > (pL_med - 24) sharply so buzzed fade never flashes white!
    fade_glare = np.maximum(0.0, L_delit - (pL_med - 24.0)) * in_fade_zone
    L_delit = L_delit - 0.58 * fade_glare

    # Subtle jawline/gonion contour contrast boost along y in [610..700], x in [460..630]
    g_jaw_contour = np.exp(-0.5 * (((xx - 545.0) / 95.0) ** 2 + ((yy - 650.0) / 48.0) ** 2))
    L_delit = L_delit - 3.5 * g_jaw_contour * np.clip((pL_med - L_delit) / 28.0, 0.0, 1.0)

    # Pure skin fraction t_skin: 0.0 on dark black-brown hair (L <= 46), 1.0 on bare tanned skin (L >= pL_med - 14)
    # Every fade pixel smoothly blends between dark black-brown hair (#1a1715 -> LAB ~ 22, 130.5, 132.5)
    # and warm tanned scalp skin (tgt_L, tgt_A, tgt_B) -> mathematically IMPOSSIBLE to produce white/gray hair!
    t_skin = np.clip((L_delit - 44.0) / max(30.0, (pL_med - 16.0) - 44.0), 0.0, 1.0)

    # Shift skin luminance cleanly toward tgt_L, keeping dark hair deep black-brown
    L_out = L_delit + (tgt_L - pL_med) * t_skin
    # Extra gentle clamp in fade zone so buzzed scalp never exceeds healthy tanned skin luminance (tgt_L - 6)
    L_fade_cap = tgt_L - 6.0
    L_out = L_out - np.maximum(0.0, L_out - L_fade_cap) * 0.75 * in_fade_zone

    A_hair, B_hair = 130.2, 132.5  # Deep natural black-brown (#1a1715), NEVER bluish-silver!
    A_skin = tgt_A + np.clip(0.20 * (A - pA_med), -2.5, 3.5)
    B_skin = tgt_B + np.clip(0.20 * (B - pB_med), -2.5, 2.5)

    # In the fade zone, blend warm tanned scalp skin chroma cleanly by t_skin^0.85 (no monochrome gray!)
    t_chr = np.power(t_skin, 0.85)
    A_out = A_hair * (1.0 - t_chr) + A_skin * t_chr
    B_out = B_hair * (1.0 - t_chr) + B_skin * t_chr

    out_lab = np.stack([np.clip(L_out, 0, 255), np.clip(A_out, 0, 255), np.clip(B_out, 0, 255)], axis=-1).astype(np.uint8)
    return cv2.cvtColor(out_lab, cv2.COLOR_LAB2RGB)


def fit_dual_view_3d_morph(
    face_xyz: np.ndarray,
    face_uv: np.ndarray,
    lms_base_2d: np.ndarray,
    lms_photo_2d: np.ndarray,
    xyz_buf: np.ndarray,
    valid_buf: np.ndarray,
    prof_mask: np.ndarray,
):
    """Stage 2 (v3): Dual-View 3D TPS/RBF Head Morph with:
      - Exact real side-profile silhouette + extra +2mm upper lip & chin Z-projection
      - Compacted rear occiput (+21mm forward)
      - Closer-set tucked ears (-3.8mm inward helix)
      - Tightly wrapped outer orbital rim / lateral canthus (zero white sclera poke in profile!)
      - Strict 0.0000mm neck lock below Y=15.72."""
    H, W = valid_buf.shape
    scale = 370.0

    B_3D = np.zeros((468, 3), dtype=np.float32)
    for k in range(468):
        px = int(np.clip(round(lms_base_2d[k, 0]), 0, W - 1))
        py = int(np.clip(round(lms_base_2d[k, 1]), 0, H - 1))
        if valid_buf[py, px]:
            B_3D[k] = xyz_buf[py, px]
        else:
            B_3D[k, 0] = (lms_base_2d[k, 0] - 512.0) / scale
            B_3D[k, 1] = 16.65 - (lms_base_2d[k, 1] - 512.0) / scale
            B_3D[k, 2] = 1.15

    p_eyeL = np.mean(lms_photo_2d[[33, 133, 159, 145], :2], axis=0)
    p_eyeR = np.mean(lms_photo_2d[[362, 263, 386, 374], :2], axis=0)
    roll = np.arctan2(p_eyeR[1] - p_eyeL[1], p_eyeR[0] - p_eyeL[0])
    cos_r, sin_r = np.cos(-roll), np.sin(-roll)
    p_mid = 0.5 * (p_eyeL + p_eyeR)

    P_rot = np.zeros((468, 3), dtype=np.float32)
    for k in range(468):
        dx = lms_photo_2d[k, 0] - p_mid[0]
        dy = lms_photo_2d[k, 1] - p_mid[1]
        P_rot[k, 0] = dx * cos_r - dy * sin_r
        P_rot[k, 1] = dx * sin_r + dy * cos_r
        P_rot[k, 2] = lms_photo_2d[k, 2]

    mid_idx = [168, 6, 197, 195, 5, 4, 1, 2, 164, 0, 17, 152]
    P_rot[:, 0] -= np.median(P_rot[mid_idx, 0])

    b_eye_y = 0.5 * (np.mean(B_3D[[33, 133, 159, 145], 1]) + np.mean(B_3D[[362, 263, 386, 374], 1]))
    b_chin_y = B_3D[152, 1]
    b_h = b_eye_y - b_chin_y
    p_chin_y = P_rot[152, 1]
    s_3d = b_h / max(1.0, p_chin_y)

    mouth_set = set([61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 185, 40, 39, 37, 0, 267, 269, 270, 409, 78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308, 191, 80, 81, 82, 13, 312, 311, 310, 415])

    T_3D = B_3D.copy()
    for k in range(468):
        tx = P_rot[k, 0] * s_3d
        ty = b_eye_y - P_rot[k, 1] * s_3d
        wx = 0.44 if k in mouth_set else 0.36
        wy = 0.28
        T_3D[k, 0] = B_3D[k, 0] + wx * (tx - B_3D[k, 0])
        T_3D[k, 1] = B_3D[k, 1] + wy * (ty - B_3D[k, 1])

    # Extract true Z_target(Y) directly from prof_mask (profile_best.jpg) + +2.0mm upper lip & chin Z boost!
    py_eye = 434.0
    scale_prof = 280.2
    px_ref_brow = 256.0
    z_ref_brow = 1.430

    prof_target_curve = []
    prof_ctrl_pts = []
    prof_ctrl_disp = []

    for y3d in np.linspace(17.44, 15.94, 31):
        m_b = (np.abs(face_xyz[:, 0]) < 0.045) & (np.abs(face_xyz[:, 1] - y3d) < 0.045) & (face_xyz[:, 2] > 0.85)
        if not np.any(m_b):
            continue
        zb = float(face_xyz[m_b, 2].max())
        py = py_eye + (16.974 - y3d) * scale_prof
        if y3d < 16.36:
            py += 24.0 * min(1.0, (16.36 - y3d) / 0.09)
        py_i = int(np.clip(round(py), 0, prof_mask.shape[0] - 1))
        xs = np.where(prof_mask[py_i] > 0)[0]
        if len(xs) < 20:
            continue
        za = z_ref_brow + (px_ref_brow - float(xs[0])) / scale_prof
        # Straighten Alcaraz's nasal dorsum (mid-bridge Y in 16.72..16.92): push +4.8mm forward so bridge
        # forms Alcaraz's real clean straight diagonal nose bridge (NOT an overly scooped ski-slope curve!)
        dorsum_fill = 0.048 * float(np.exp(-0.5 * ((y3d - 16.82) / 0.095) ** 2))
        # Extra +2.0mm forward Z projection on upper lip (Y~16.40) and chin apex (Y~15.98..16.06)
        lip_boost = 0.020 * float(np.exp(-0.5 * ((y3d - 16.38) / 0.09) ** 2))
        chin_boost = 0.022 * float(np.exp(-0.5 * ((y3d - 16.01) / 0.10) ** 2))
        za += dorsum_fill + lip_boost + chin_boost
        dz_prof = float(np.clip(za - zb, -0.145, 0.115))
        dy_prof = 0.044 * float(np.exp(-0.5 * ((y3d - 16.61) / 0.09) ** 2))
        prof_target_curve.append((float(y3d), zb, zb + dz_prof))
        for x_c in (-0.05, 0.0, 0.05):
            falloff = 0.88 if abs(x_c) > 0 else 1.0
            prof_ctrl_pts.append([x_c, float(y3d), zb])
            prof_ctrl_disp.append([0.0, dy_prof * falloff, dz_prof * falloff])

    d_3d = T_3D - B_3D
    for k in range(468):
        x, y, z = B_3D[k]
        alar_g = np.exp(-0.5 * (((abs(x) - 0.16) / 0.10) ** 2 + ((y - 16.62) / 0.11) ** 2 + ((z - 1.36) / 0.15) ** 2))
        cheek_g = np.exp(-0.5 * (((abs(x) - 0.54) / 0.22) ** 2 + ((y - 16.72) / 0.26) ** 2 + ((z - 1.05) / 0.35) ** 2))
        gonion_g = np.exp(-0.5 * (((abs(x) - 0.54) / 0.22) ** 2 + ((y - 16.24) / 0.22) ** 2 + ((z - 0.72) / 0.38) ** 2))
        if abs(x) < 0.26 and y >= 15.92 and y <= 17.45:
            nearest = min(prof_target_curve, key=lambda t: abs(t[0] - y))
            w_mid = float(np.exp(-0.5 * (x / 0.16) ** 2))
            d_3d[k, 2] += (nearest[2] - nearest[1]) * w_mid
            d_3d[k, 1] += 0.052 * float(np.exp(-0.5 * ((y - 16.61) / 0.09) ** 2)) * w_mid
        d_3d[k, 0] += (0.042 if x >= 0 else -0.042) * cheek_g + (0.052 if x >= 0 else -0.052) * gonion_g + (0.024 if x >= 0 else -0.024) * alar_g
        d_3d[k, 2] += 0.028 * cheek_g + 0.024 * gonion_g

    B_mir = B_3D.copy()
    B_mir[:, 0] = -B_mir[:, 0]
    d_mir = d_3d.copy()
    d_mir[:, 0] = -d_mir[:, 0]

    anchors = []
    anchor_d = []
    for x, y, z in face_xyz[::4]:
        if y <= 15.74:
            anchors.append([x, y, z])
            anchor_d.append([0.0, 0.0, 0.0])
        elif z < 0.22 and y > 15.95:
            t_back = min(1.0, max(0.0, (0.22 - z) / 0.88))
            t_y = min(1.0, max(0.0, (y - 15.95) / 0.45))
            t_top = min(1.0, max(0.0, (y - 17.45) / 0.65))
            dz_occ = 0.215 * (t_back ** 1.15) * t_y
            dy_occ = -0.068 * t_top
            dx_occ = -x * 0.030 * t_top
            anchors.append([x, y, z])
            anchor_d.append([dx_occ, dy_occ, dz_occ])
        elif y >= 17.48 and z >= 0.22:
            t_top = min(1.0, max(0.0, (y - 17.48) / 0.65))
            anchors.append([x, y, z])
            anchor_d.append([-x * 0.025 * t_top, -0.062 * t_top, 0.015 * t_top])

    # Strong angular jaw gonion controls on left & right sides
    for sx in (-1.0, 1.0):
        for gy, gz, gdx, gdy, gdz in [
            (16.16, 0.52, 0.055, -0.025, 0.038),
            (16.25, 0.72, 0.050, -0.015, 0.044),
            (16.05, 0.95, 0.042, -0.010, 0.060),
        ]:
            anchors.append([sx * 0.56, gy, gz])
            anchor_d.append([sx * gdx, gdy, gdz])

    ctrl_pts = np.vstack([B_3D, B_mir, np.array(prof_ctrl_pts, dtype=np.float32), np.array(anchors, dtype=np.float32)])
    ctrl_disp = np.vstack([d_3d, d_mir, np.array(prof_ctrl_disp, dtype=np.float32), np.array(anchor_d, dtype=np.float32)])

    rbf_3d = RBFInterpolator(ctrl_pts, ctrl_disp, kernel="thin_plate_spline", smoothing=0.06)
    # Slight deep-set eye_dz = -0.012 (-1.2mm) so eyeball tucks cleanly beneath Alcaraz's strong brow ridge & outer canthus!
    return rbf_3d, (0.032, 0.0, -0.012), prof_target_curve


def apply_rbf_to_xyz(xyz: np.ndarray, rbf_3d: RBFInterpolator, eye_dx: float = 0.032, eye_dy: float = 0.0, eye_dz: float = -0.012):
    raw_disp = rbf_3d(xyz)
    neck_lock_y = 15.720
    new_xyz = xyz.copy()
    max_front_disp_mm = 0.0
    max_occ_disp_mm = 0.0
    neck_seam_mm = 0.0

    for i in range(len(xyz)):
        x, y, z = xyz[i]
        if y <= neck_lock_y:
            continue
        t_neck = min(1.0, max(0.0, (y - neck_lock_y) / 0.18))
        neck_gate = t_neck * t_neck * (3.0 - 2.0 * t_neck)

        dx, dy, dz = raw_disp[i] * neck_gate

        # Strict rigid eye socket lock around (±0.265, 16.974, 1.195)
        g_eyeL = np.exp(-0.5 * (((x + 0.265) / 0.18) ** 2 + ((y - 16.974) / 0.11) ** 2 + ((z - 1.195) / 0.20) ** 2))
        g_eyeR = np.exp(-0.5 * (((x - 0.265) / 0.18) ** 2 + ((y - 16.974) / 0.11) ** 2 + ((z - 1.195) / 0.20) ** 2))
        w_eye = min(1.0, (g_eyeL + g_eyeR) * 1.45)
        rig_dx = (eye_dx if x >= 0 else -eye_dx) * neck_gate
        rig_dz = eye_dz * neck_gate
        dx = dx * (1.0 - w_eye) + rig_dx * w_eye
        dy = dy * (1.0 - w_eye) + eye_dy * w_eye
        dz = dz * (1.0 - w_eye) + rig_dz * w_eye

        # Wrap lateral canthus / outer orbital rim slightly forward (+2.2mm Z) so outer eyelid hugs eyeball cleanly in side profile!
        g_canthus = np.exp(-0.5 * (((abs(x) - 0.42) / 0.09) ** 2 + ((y - 16.97) / 0.08) ** 2 + ((z - 1.14) / 0.12) ** 2))
        dz += 0.022 * g_canthus * neck_gate

        # Tuck Djokovic's protruding outer/upper ear helix inward toward the skull (-4.2mm X) to match Alcaraz's closer-set ears!
        if abs(x) > 0.60 and 16.44 < y < 17.10 and 0.18 < z < 0.60:
            t_ear = min(1.0, max(0.0, (abs(x) - 0.60) / 0.18))
            t_ear_y = 0.55 + 0.45 * min(1.0, max(0.0, (y - 16.50) / 0.45))
            tuck = 0.044 * (t_ear ** 1.15) * t_ear_y
            dx += (-tuck if x > 0 else tuck)

        # Mouth contact seal at Y = 16.355
        g_lip_seam = np.exp(-0.5 * ((x / 0.28) ** 2 + ((y - 16.355) / 0.042) ** 2 + ((z - 1.36) / 0.14) ** 2))
        dy *= (1.0 - 0.82 * g_lip_seam)

        limit = 0.220 if z < 0.05 else 0.150
        mag = float(np.sqrt(dx * dx + dy * dy + dz * dz))
        if mag > limit:
            s = limit / mag
            dx *= s
            dy *= s
            dz *= s
            mag = limit

        if z < 0.05:
            max_occ_disp_mm = max(max_occ_disp_mm, mag * 100.0)
        else:
            max_front_disp_mm = max(max_front_disp_mm, mag * 100.0)
        if y <= neck_lock_y:
            neck_seam_mm = max(neck_seam_mm, mag * 100.0)

        new_xyz[i] = [x + dx, y + dy, z + dz]

    return new_xyz, max_front_disp_mm, max_occ_disp_mm, neck_seam_mm


def sculpt_alcaraz_hair_fix(hxyz: np.ndarray) -> np.ndarray:
    """Bring Hair_fix-VB front fringe slightly lower & textured to hug Alcaraz's natural crop hairline
    (killing Djokovic's flat high shelf!) while staying snugly conformed to the compacted cranium."""
    out = hxyz.copy()
    ymin = float(hxyz[:, 1].min())
    ymax = float(hxyz[:, 1].max())
    yspan = max(0.2, ymax - ymin)
    for i in range(len(out)):
        x, y, z = out[i]
        t = min(1.0, max(0.0, (y - ymin) / yspan))
        front_t = min(1.0, max(0.0, (z - 0.92) / 0.48))
        # Subtle organic fringe wave across X so hairline looks naturally textured rather than a straight ruler shelf
        wave = 0.012 * float(np.sin(x * 7.5 + 0.6)) * front_t * (1.0 - t)
        dy = -0.050 * (1.0 - t) * front_t - 0.072 * (t ** 1.1) - 0.018 + wave
        dx = -x * 0.060 * min(1.0, abs(x) / 0.45)
        dz = -0.018 * t - 0.010 * front_t
        out[i] = [x + dx, y + dy, z + dz]
    return out


def bake_dual_view_projective_uv(
    morphed_xyz: np.ndarray,
    morphed_nrm: np.ndarray,
    face_uv: np.ndarray,
    face_tris: list,
    lms_morphed_2d: np.ndarray,
    lms_photo_2d: np.ndarray,
    front_rgb_delit: np.ndarray,
    prof_rgb_delit: np.ndarray,
    prof_mask: np.ndarray,
    base_face_rgba: np.ndarray,
    target_skin_lab: np.ndarray,
):
    """Stage 3 (v3): Dual-View Projective Baking with:
      - Clean UV-aligned color-matched ears (zero horizontal stripes, zero double-ear ghost!)
      - Cool charcoal-black barbershop high skin-fade (zero orange-brown fade tint!)
      - Zero diagonal forehead-to-temple hairline notch
      - Clean lip parting seam (zero pale line) & softened nostril bases."""
    H = W = 1024
    scale = 370.0
    cx = 512.0
    cy = 512.0
    y_mid = 16.65

    # --- A. FRONT VIEW VERTEX-TO-PHOTO MAPPING ---
    v_ortho_front = np.zeros((len(morphed_xyz), 2), dtype=np.float32)
    v_ortho_front[:, 0] = cx + morphed_xyz[:, 0] * scale
    v_ortho_front[:, 1] = cy - (morphed_xyz[:, 1] - y_mid) * scale

    src_pts = np.ascontiguousarray(lms_morphed_2d[:468, :2], dtype=np.float32)
    dst_pts = np.ascontiguousarray(lms_photo_2d[:468, :2], dtype=np.float32).copy()

    # Slightly thicker & lower inner/mid eyebrows matching Alcaraz's intense low brow line
    all_brow_idx = [70, 63, 105, 66, 107, 55, 65, 52, 53, 46, 336, 296, 334, 293, 300, 285, 295, 282, 283, 276]
    top_brow_idx = [70, 63, 105, 66, 107, 336, 296, 334, 293, 300]
    inner_brow_idx = [107, 66, 55, 65, 336, 296, 285, 295]
    dst_pts[all_brow_idx, 1] += 2.2
    dst_pts[top_brow_idx, 1] -= 7.8
    dst_pts[inner_brow_idx, 1] -= 2.2

    m_center_x = 0.5 * (dst_pts[61, 0] + dst_pts[291, 0])
    mouth_all = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 185, 40, 39, 37, 0, 267, 269, 270, 409, 78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308, 191, 80, 81, 82, 13, 312, 311, 310, 415]
    for mi in mouth_all:
        dx_m = dst_pts[mi, 0] - m_center_x
        t_corner = min(1.0, abs(dx_m) / 55.0)
        dst_pts[mi, 0] = m_center_x + dx_m * 0.96
        dst_pts[mi, 1] -= 4.2 * (t_corner ** 1.5)

    mu_s = np.mean(src_pts, axis=0)
    mu_d = np.mean(dst_pts, axis=0)
    cs = src_pts - mu_s
    cd = dst_pts - mu_d
    ss = float(np.sum(cs * cs))
    a_sim = float(np.sum(cs[:, 0] * cd[:, 0] + cs[:, 1] * cd[:, 1])) / ss
    b_sim = float(np.sum(cs[:, 0] * cd[:, 1] - cs[:, 1] * cd[:, 0])) / ss
    R_sim = np.array([[a_sim, -b_sim], [b_sim, a_sim]], dtype=np.float32)
    t_sim = mu_d - (mu_s @ R_sim.T)
    M_sim = np.hstack([R_sim, t_sim[:, None]])

    angles = np.linspace(0, 2 * np.pi, 36, endpoint=False)
    ring_src = []
    for rad in (360.0, 460.0):
        for ang in angles:
            ring_src.append([512.0 + rad * np.cos(ang), 512.0 + rad * np.sin(ang)])
    ring_src = np.array(ring_src, dtype=np.float32)
    ring_dst = (ring_src @ M_sim[:, :2].T) + M_sim[:, 2]

    rbf_front = RBFInterpolator(np.vstack([src_pts, ring_src]), np.vstack([dst_pts, ring_dst]), kernel="thin_plate_spline", smoothing=26.0)
    v_photo_front = rbf_front(v_ortho_front)

    # --- B. SIDE PROFILE VIEW VERTEX-TO-PHOTO MAPPING ---
    ear_m = (face_uv[:, 0] > 0.12) & (face_uv[:, 0] < 0.22) & (face_uv[:, 1] > 0.35) & (face_uv[:, 1] < 0.55) & (morphed_xyz[:, 0] < -0.5)
    ep = morphed_xyz[ear_m]
    e_ymin, e_ymax = float(ep[:, 1].min()), float(ep[:, 1].max())
    e_zmin, e_zmax = float(ep[:, 2].min()), float(ep[:, 2].max())
    e_ymid, e_zmid = float(ep[:, 1].mean()), float(ep[:, 2].mean())
    occ_z = float(morphed_xyz[(morphed_xyz[:, 1] > 16.9) & (morphed_xyz[:, 1] < 17.5), 2].min())
    crown_y = float(morphed_xyz[:, 1].max())
    nose_z = float(morphed_xyz[(np.abs(morphed_xyz[:, 0]) < 0.06) & (morphed_xyz[:, 1] > 16.58) & (morphed_xyz[:, 1] < 16.76), 2].max())

    side_src = np.array([
        [1.18, 16.97],
        [nose_z, 16.67],
        [1.36, 17.34],
        [0.42, crown_y],
        [occ_z, 17.32],
        [occ_z + 0.12, 16.50],
        [e_zmid, e_ymax],
        [e_zmax, e_ymid],
        [e_zmin, e_ymid],
        [e_zmid + 0.04, e_ymin],
        [0.65, 16.20],
        [1.36, 16.01],
        [0.85, 17.34],
    ], dtype=np.float32)

    side_dst = np.array([
        [435.0, 442.0],
        [227.0, 526.0],
        [285.0, 295.0],
        [615.0, 82.0],
        [902.0, 295.0],
        [818.0, 535.0],
        [744.0, 396.0],
        [688.0, 480.0],
        [778.0, 468.0],
        [684.0, 558.0],
        [585.0, 692.0],
        [284.0, 742.0],
        [502.0, 326.0],
    ], dtype=np.float32)

    rbf_side = RBFInterpolator(side_src, side_dst, kernel="thin_plate_spline", smoothing=0.015)
    v_photo_side = rbf_side(morphed_xyz[:, [2, 1]])

    # --- C. COLOR-MATCHED BASE UV CANVAS (HEALTHY ROSIER MEDITERRANEAN TAN + COOL CHARCOAL SCALP HAIR) ---
    base_rgb = base_face_rgba[:, :, :3].copy()
    base_lab = cv2.cvtColor(base_rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    b_patch = base_lab[520:660, 350:674].reshape(-1, 3)
    b_mean = np.median(b_patch, axis=0)

    base_lum = (0.299 * base_rgb[:, :, 0] + 0.587 * base_rgb[:, :, 1] + 0.114 * base_rgb[:, :, 2]) / 255.0
    rg_diff = base_rgb[:, :, 0].astype(np.float32) - base_rgb[:, :, 1].astype(np.float32)
    yy, xx = np.mgrid[0:H, 0:W]
    w_lum_hair = np.clip((0.35 - base_lum) / 0.12, 0.0, 1.0)
    w_chr_hair = np.clip((26.0 - rg_diff) / 14.0, 0.0, 1.0)
    w_y_hair = np.clip((620.0 - yy) / 80.0, 0.0, 1.0)
    in_face_center = ((xx >= 330) & (xx <= 694) & (yy >= 245)).astype(np.float32)
    hair_mask = w_lum_hair * w_chr_hair * w_y_hair * (1.0 - in_face_center)
    hair_mask = cv2.GaussianBlur(hair_mask.astype(np.float32), (21, 21), 6.0)

    skin_weight = 1.0 - hair_mask
    lab_shift = (target_skin_lab - b_mean) * np.array([0.92, 0.96, 0.96], dtype=np.float32)
    base_lab_shifted = base_lab.copy()
    base_lab_shifted[:, :, 0] = np.clip(base_lab[:, :, 0] + lab_shift[0] * skin_weight, 0, 255)
    base_lab_shifted[:, :, 1] = np.clip(base_lab[:, :, 1] + lab_shift[1] * skin_weight, 0, 255)
    base_lab_shifted[:, :, 2] = np.clip(base_lab[:, :, 2] + lab_shift[2] * skin_weight, 0, 255)
    canvas_rgb = cv2.cvtColor(base_lab_shifted.astype(np.uint8), cv2.COLOR_LAB2RGB)

    # Cool neutral charcoal-black scalp hair (zero warm orange/brown cast!)
    rel_lum = np.clip(base_lum / 0.16, 0.35, 1.85)
    dark_hair = np.stack([
        np.clip(27.0 * (0.42 + 0.58 * rel_lum), 9, 54),
        np.clip(26.0 * (0.42 + 0.58 * rel_lum), 9, 52),
        np.clip(26.0 * (0.42 + 0.58 * rel_lum), 9, 52),
    ], axis=-1).astype(np.uint8)
    canvas_rgb = (canvas_rgb * (1.0 - hair_mask[:, :, None]) + dark_hair * hair_mask[:, :, None]).astype(np.uint8)

    # --- D. VALID PHOTO MASKS ---
    oval_idx = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]
    oval_pts = lms_photo_2d[oval_idx, :2].copy()
    center_xy = np.mean(oval_pts, axis=0)
    for i_pt in range(len(oval_pts)):
        if oval_pts[i_pt, 1] > lms_photo_2d[13, 1]:
            vec = oval_pts[i_pt] - center_xy
            oval_pts[i_pt] = center_xy + vec * 0.96

    p_lab = cv2.cvtColor(front_rgb_delit, cv2.COLOR_RGB2LAB).astype(np.float32)
    front_valid_mask = np.zeros((H, W), dtype=np.float32)
    cv2.fillPoly(front_valid_mask, [oval_pts.astype(np.int32)], 1.0)
    brow_top_y = float(np.min(lms_photo_2d[[70, 63, 105, 66, 107, 336, 296, 334, 293, 300], 1])) - 14.0
    upper_hair_in_photo = (yy < brow_top_y) & (p_lab[:, :, 0] < (target_skin_lab[0] - 28.0))
    front_valid_mask[upper_hair_in_photo] = 0.0
    front_valid_mask = cv2.GaussianBlur(front_valid_mask, (45, 45), 14.0)

    # Side profile valid mask: strictly excludes front face/mouth (x < 440), front bangs wedge (x < 535 & y < 365),
    # dark sub-jaw collar (y > 678), and lower earlobe/neck shadow pocket (x > 645 & y > 565)!
    side_valid_mask = cv2.erode(prof_mask, np.ones((21, 21), np.uint8)).astype(np.float32)
    side_valid_mask[:, :440] = 0.0
    side_valid_mask[:365, :535] = 0.0
    side_valid_mask[678:, :720] = 0.0
    side_valid_mask[565:, 645:] = 0.0
    side_valid_mask = cv2.GaussianBlur(side_valid_mask, (55, 55), 18.0)

    # --- E. RASTERIZE FACE-VB TRIANGLES INTO 1024x1024 UV SPACE ---
    f_map_x = np.full((H, W), -1.0, dtype=np.float32)
    f_map_y = np.full((H, W), -1.0, dtype=np.float32)
    f_weight = np.zeros((H, W), dtype=np.float32)

    s_map_x = np.full((H, W), -1.0, dtype=np.float32)
    s_map_y = np.full((H, W), -1.0, dtype=np.float32)
    s_weight = np.zeros((H, W), dtype=np.float32)

    vnx = np.abs(morphed_nrm[:, 0].astype(np.float32)) / 16384.0
    vnz = morphed_nrm[:, 2].astype(np.float32) / 16384.0
    vy_3d = morphed_xyz[:, 1]
    vz_3d = morphed_xyz[:, 2]

    v_vis_front = (
        np.clip((vnz - 0.18) / 0.52, 0.0, 1.0)
        * np.clip((vy_3d - 15.80) / 0.16, 0.0, 1.0)
        * np.clip((17.32 - vy_3d) / 0.16, 0.0, 1.0)
    )
    v_vis_side = (
        np.clip((vnx - 0.25) / 0.50, 0.0, 1.0)
        * np.clip((vy_3d - 16.06) / 0.20, 0.0, 1.0)
        * np.clip((17.75 - vy_3d) / 0.25, 0.0, 1.0)
        * np.clip((1.02 - vz_3d) / 0.30, 0.0, 1.0)
    )

    uv_px = face_uv * 1024.0
    for a, b, c in face_tris:
        if (v_vis_front[a] <= 0.01 and v_vis_front[b] <= 0.01 and v_vis_front[c] <= 0.01) and (
            v_vis_side[a] <= 0.01 and v_vis_side[b] <= 0.01 and v_vis_side[c] <= 0.01
        ):
            continue
        ua, va = uv_px[a]
        ub, vb = uv_px[b]
        uc, vc = uv_px[c]
        if max(abs(ua - ub), abs(ub - uc), abs(ua - uc)) > 300.0:
            continue
        det = (vb - vc) * (ua - uc) + (uc - ub) * (va - vc)
        if abs(det) < 1e-4:
            continue
        x0 = max(0, int(min(ua, ub, uc)))
        x1 = min(W - 1, int(max(ua, ub, uc)) + 1)
        y0 = max(0, int(min(va, vb, vc)))
        y1 = min(H - 1, int(max(va, vb, vc)) + 1)
        if x0 > x1 or y0 > y1:
            continue
        yy_t, xx_t = np.mgrid[y0 : y1 + 1, x0 : x1 + 1]
        w0 = ((vb - vc) * (xx_t - uc) + (uc - ub) * (yy_t - vc)) / det
        w1 = ((vc - va) * (xx_t - uc) + (ua - uc) * (yy_t - vc)) / det
        w2 = 1.0 - w0 - w1
        m = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4)
        if not np.any(m):
            continue

        f_map_x[y0 : y1 + 1, x0 : x1 + 1][m] = (w0 * v_photo_front[a, 0] + w1 * v_photo_front[b, 0] + w2 * v_photo_front[c, 0])[m]
        f_map_y[y0 : y1 + 1, x0 : x1 + 1][m] = (w0 * v_photo_front[a, 1] + w1 * v_photo_front[b, 1] + w2 * v_photo_front[c, 1])[m]
        f_weight[y0 : y1 + 1, x0 : x1 + 1][m] = (w0 * v_vis_front[a] + w1 * v_vis_front[b] + w2 * v_vis_front[c])[m]

        s_map_x[y0 : y1 + 1, x0 : x1 + 1][m] = (w0 * v_photo_side[a, 0] + w1 * v_photo_side[b, 0] + w2 * v_photo_side[c, 0])[m]
        s_map_y[y0 : y1 + 1, x0 : x1 + 1][m] = (w0 * v_photo_side[a, 1] + w1 * v_photo_side[b, 1] + w2 * v_photo_side[c, 1])[m]
        s_weight[y0 : y1 + 1, x0 : x1 + 1][m] = (w0 * v_vis_side[a] + w1 * v_vis_side[b] + w2 * v_vis_side[c])[m]

    sampled_front = cv2.remap(front_rgb_delit, f_map_x, f_map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
    valid_front = cv2.remap(front_valid_mask, f_map_x, f_map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0.0)
    wf = f_weight * valid_front

    mirror_front = sampled_front[:, ::-1, :]
    mirror_wf = wf[:, ::-1]
    u_grid = np.linspace(0.0, 1023.0, W)[None, :]
    mirror_alpha = np.where(u_grid < 430.0, np.clip(0.26 + 0.48 * (430.0 - u_grid) / 110.0, 0.26, 0.74), 0.26)[:, :, None]
    both_valid = (wf > 0.05) & (mirror_wf > 0.05)
    harm_front = sampled_front.copy()
    harm_front[both_valid] = (
        sampled_front[both_valid] * (1.0 - mirror_alpha.repeat(H, axis=0)[both_valid])
        + mirror_front[both_valid] * mirror_alpha.repeat(H, axis=0)[both_valid]
    ).astype(np.uint8)
    wf = np.maximum(wf, 0.80 * mirror_wf)

    # Protect closed-eyelid UV slit
    eye_slit_L = ((xx - 421.0) / 48.0) ** 2 + ((yy - 397.5) / 17.5) ** 2
    eye_slit_R = ((xx - 603.0) / 48.0) ** 2 + ((yy - 397.5) / 17.5) ** 2
    eye_slit_mask = np.clip(1.0 - np.minimum(eye_slit_L, eye_slit_R), 0.0, 1.0)
    eye_slit_mask = cv2.GaussianBlur(eye_slit_mask.astype(np.float32), (15, 15), 4.0)
    wf = wf * (1.0 - 0.95 * eye_slit_mask)
    wf = np.clip(cv2.GaussianBlur(wf.astype(np.float32), (35, 35), 10.0), 0.0, 1.0)

    # Exclude UV EAR ISLANDS cleanly from side projection -> ZERO horizontal stripes on front/3-4 ears AND ZERO double-ear ghost in profile!
    # SEGA's base UV ears (already color-matched to Alcaraz's healthy rosy-tan skin on canvas_rgb!) align 1:1 to Face-VB's 3D ear ridges!
    ear_L = ((xx - 168.0) / 56.0) ** 2 + ((yy - 455.0) / 104.0) ** 2
    ear_R = ((xx - 856.0) / 56.0) ** 2 + ((yy - 455.0) / 104.0) ** 2
    ear_protect = np.clip(1.25 - np.minimum(ear_L, ear_R), 0.0, 1.0)
    ear_protect = cv2.GaussianBlur(ear_protect.astype(np.float32), (25, 25), 7.0)

    sampled_side = cv2.remap(prof_rgb_delit, s_map_x, s_map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
    valid_side = cv2.remap(side_valid_mask, s_map_x, s_map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0.0)
    ws = s_weight * valid_side * (1.0 - ear_protect)
    ws = ws * np.clip(1.0 - wf * 1.15, 0.0, 1.0)
    ws = np.clip(cv2.GaussianBlur(ws.astype(np.float32), (35, 35), 11.0), 0.0, 1.0)

    # Multi-band blend: Side Profile (high skin-fade + jaw stubble) onto canvas_rgb
    side_f = sampled_side.astype(np.float32)
    canvas_f = canvas_rgb.astype(np.float32)
    side_low = cv2.GaussianBlur(side_f, (41, 41), 12.0)
    canvas_low = cv2.GaussianBlur(canvas_f, (41, 41), 12.0)
    ws_low = cv2.GaussianBlur(ws, (55, 55), 18.0)[:, :, None]
    ws_high = ws[:, :, None]
    with_side_f = (canvas_low * (1.0 - ws_low) + side_low * ws_low) + ((canvas_f - canvas_low) * (1.0 - ws_high) + (side_f - side_low) * ws_high)
    with_side_f = np.clip(with_side_f, 0, 255)

    # Multi-band blend: Front View onto with_side_f
    front_f = harm_front.astype(np.float32)
    front_low = cv2.GaussianBlur(front_f, (45, 45), 14.0)
    ws_base_low = cv2.GaussianBlur(with_side_f, (45, 45), 14.0)
    wf_low = cv2.GaussianBlur(wf, (65, 65), 22.0)[:, :, None]
    wf_high = wf[:, :, None]
    baked_rgb = np.clip(
        (ws_base_low * (1.0 - wf_low) + front_low * wf_low)
        + ((with_side_f - ws_base_low) * (1.0 - wf_high) + (front_f - front_low) * wf_high),
        0,
        255,
    ).astype(np.uint8)

    # --- F. TARGETED UV POLISH: MOUTH SEAM PALE LINE, NOSTRIL PINCH DOTS, CORNER SHADOWS & TEMPLE BLEND ---
    # 1. Cleanly feather out the pale horizontal strip along the closed lip parting (v in 600..626, u in 416..608)!
    seam_y0, seam_y1 = 600, 627
    seam_x0, seam_x1 = 416, 608
    upper_row = cv2.GaussianBlur(baked_rgb[588:599, seam_x0:seam_x1], (15, 5), 4.0).mean(axis=0)
    lower_row = cv2.GaussianBlur(baked_rgb[627:637, seam_x0:seam_x1], (15, 5), 4.0).mean(axis=0)
    ux = np.linspace(-1.0, 1.0, seam_x1 - seam_x0)
    w_x = np.clip((1.0 - ux * ux) * 1.6, 0.0, 1.0)
    for y_s in range(seam_y0, seam_y1):
        ty = (y_s - seam_y0) / float(seam_y1 - seam_y0 - 1)
        # Flat plateau w_y = 1.0 across the pale strip (v in 607..620), smoothly feathered over 7px top/bottom!
        if y_s < 607:
            w_y = (y_s - seam_y0) / 7.0
        elif y_s > 620:
            w_y = (seam_y1 - 1 - y_s) / 6.0
        else:
            w_y = 1.0
        w_seam = (w_y * w_x)[:, None]
        lip_interp = upper_row * (1.0 - ty) + lower_row * ty
        # Subtle soft closed-lip crease shadow right along the center parting line
        crease_darken = 1.0 - 0.14 * float(np.exp(-0.5 * ((ty - 0.52) / 0.14) ** 2))
        lip_interp = lip_interp * crease_darken
        baked_rgb[y_s, seam_x0:seam_x1] = np.clip(
            baked_rgb[y_s, seam_x0:seam_x1].astype(np.float32) * (1.0 - w_seam) + lip_interp * w_seam,
            0,
            255,
        ).astype(np.uint8)

    # 2. Soften tiny nostril pinch dots around (468, 512) and (556, 512)
    nostril_soft = cv2.medianBlur(baked_rgb, 9)
    g_nostril = np.clip(
        np.exp(-0.5 * (((xx - 468.0) / 14.0) ** 2 + ((yy - 512.0) / 11.0) ** 2))
        + np.exp(-0.5 * (((xx - 556.0) / 14.0) ** 2 + ((yy - 512.0) / 11.0) ** 2)),
        0.0,
        1.0,
    )[:, :, None]
    baked_rgb = (baked_rgb * (1.0 - 0.75 * g_nostril) + nostril_soft * (0.75 * g_nostril)).astype(np.uint8)

    # 3. Soften outer mouth corner pockets & under-lip dip in LAB L
    uv_lab = cv2.cvtColor(baked_rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    uL = uv_lab[:, :, 0]
    uL_ref = cv2.GaussianBlur(cv2.dilate(uL, np.ones((19, 19), np.uint8)), (41, 41), 13.0) - 3.0
    g_uv_clean = np.clip(
        np.exp(-0.5 * (((xx - 421.0) / 22.0) ** 2 + ((yy - 590.0) / 18.0) ** 2))
        + np.exp(-0.5 * (((xx - 603.0) / 22.0) ** 2 + ((yy - 590.0) / 18.0) ** 2))
        + 0.70 * np.exp(-0.5 * (((xx - 512.0) / 24.0) ** 2 + ((yy - 630.0) / 13.0) ** 2)),
        0.0,
        1.0,
    )
    uv_dip = np.maximum(0.0, uL_ref - uL)
    uv_lab[:, :, 0] = np.clip(uL + 0.74 * uv_dip * g_uv_clean, 0, 255)
    baked_rgb = cv2.cvtColor(uv_lab.astype(np.uint8), cv2.COLOR_LAB2RGB)

    # 4. Wide smooth forehead-to-temple corner feather (eliminates any diagonal hairline seam/notch!)
    g_temple_seam = np.clip(
        np.exp(-0.5 * (((xx - 308.0) / 34.0) ** 2 + ((yy - 270.0) / 42.0) ** 2))
        + np.exp(-0.5 * (((xx - 716.0) / 34.0) ** 2 + ((yy - 270.0) / 42.0) ** 2)),
        0.0,
        1.0,
    )[:, :, None]
    temple_blur = cv2.GaussianBlur(baked_rgb, (45, 45), 14.0)
    baked_rgb = (baked_rgb * (1.0 - 0.72 * g_temple_seam) + temple_blur * (0.72 * g_temple_seam)).astype(np.uint8)

    out_rgba = np.dstack([baked_rgb, base_face_rgba[:, :, 3]])
    return out_rgba, lab_shift


def build_silhouette_overlay(morphed_side_img: np.ndarray, prof_target_curve: list) -> np.ndarray:
    """Overlay Alcaraz's exact real extracted profile curve (green) vs Base DJV curve (red) onto morphed side render."""
    vis = morphed_side_img.copy()
    scale = 370.0
    cx = 512.0
    cy = 512.0
    y_mid = 16.65
    z_mid = 0.42

    pts_base = []
    pts_alc = []
    for y3d, zb, za in prof_target_curve:
        py = int(round(cy - (y3d - y_mid) * scale))
        px_b = int(round(cx - (zb - z_mid) * scale))
        px_a = int(round(cx - (za - z_mid) * scale))
        pts_base.append((px_b, py))
        pts_alc.append((px_a, py))

    for i in range(len(pts_base) - 1):
        cv2.line(vis, pts_base[i], pts_base[i + 1], (255, 70, 70), 3)
        cv2.line(vis, pts_alc[i], pts_alc[i + 1], (70, 255, 130), 3)

    cv2.putText(vis, "RED = Base DJV Profile", (24, 78), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 90, 90), 2)
    cv2.putText(vis, "GREEN = Real Alcaraz Target", (24, 108), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (80, 255, 140), 2)
    return vis


def main():
    ap = argparse.ArgumentParser(description="Studio-Grade Dual-View Photo-to-3D Facemaker Pipeline for VT4 (v3)")
    ap.add_argument("--player-id", default="26_ALC", help="Player workspace/eye-color ID (e.g. 26_ALC, 27_SIN)")
    ap.add_argument("--base-sdo", default="HIGH/Player/Model/P_M_DJV_IT.sdo", help="SEGA base .sdo path inside resource.bin")
    ap.add_argument("--front", default=os.path.join(REPO_ROOT, "scratch", "real_alcaraz_3d", "refs", "front_best.jpg"))
    ap.add_argument("--profile", default=os.path.join(REPO_ROOT, "scratch", "real_alcaraz_3d", "refs", "profile_best.jpg"))
    ap.add_argument("--out-sdo", default=os.path.join(REPO_ROOT, "game", "archive", "HIGH", "Player", "Model", "P_M_ALC_NG.sdo"))
    ap.add_argument("--hair-style", choices=("fade_crop", "medium_curly", "keep_base"), default="fade_crop")
    ap.add_argument("--tag", default="v3", help="Output filename tag (e.g. v3)")
    ap.add_argument("--offline-only", action="store_true", help="Render comparison & UV only without overwriting out-sdo")
    args = ap.parse_args()

    out_dir = os.path.join(REPO_ROOT, "scratch", "real_alcaraz_3d")
    os.makedirs(out_dir, exist_ok=True)

    base_stem = os.path.splitext(os.path.basename(args.base_sdo))[0]
    base_cache_path = os.path.join(out_dir, f"{base_stem}_base_dec.bin")
    if os.path.exists(base_cache_path):
        base_dec = bytearray(open(base_cache_path, "rb").read())
    else:
        entries = load_directory()
        by_name = {e["name"]: e for e in entries}
        with open(BIN0, "rb") as f0, open(BIN1, "rb") as f1:
            base_dec = bytearray(decompress_sdo(read_entry(entries, by_name[args.base_sdo], f0, f1)))
        open(base_cache_path, "wb").write(base_dec)

    base_vbs = {v["short_name"]: v for v in parse_vbs(base_dec)}
    base_ibs = {ib["short_name"]: ib for ib in parse_ibs(base_dec)}
    base_slots = {s["name"]: s for s in parse_sdo_dds_slots(base_dec)}

    _upgrade_hd_eyes(base_dec, base_slots, "26_ALC")

    base_face_pil = extract_slot_image(base_dec, base_slots["P_DJV_B_face_IT.dds"])
    base_face_rgba = np.array(base_face_pil.convert("RGBA"))
    base_face_rgb = base_face_rgba[:, :, :3].copy()
    eye_tex = np.array(extract_slot_image(base_dec, base_slots["P_DJV_B_eye_IT.dds"]).convert("RGB"))
    hair_tex_rgba = np.array(extract_slot_image(base_dec, base_slots["P_DJV_B_hair_IT.dds"]).convert("RGBA"))

    face_xyz, face_nrm, face_uv = load_mesh_data(base_dec, base_vbs["Face-VB"])
    face_ib = _find_ib_for_vb(base_ibs, "Face-VB")
    face_tris = _strip_to_tris(face_ib["inds"])

    base_render, xyz_buf, valid_buf = render_ortho_head(base_dec, base_vbs, base_ibs, face_xyz, base_face_rgb, eye_tex, hair_tex_rgba, yaw_deg=0.0)

    opts = vision.FaceLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=os.path.join(out_dir, "face_landmarker.task")),
        num_faces=1,
    )
    det = vision.FaceLandmarker.create_from_options(opts)

    front_rgb = np.array(Image.open(args.front).convert("RGB"))
    profile_rgb = np.array(Image.open(args.profile).convert("RGB"))
    lms_base_2d = detect_478(det, base_render)
    lms_photo_2d = detect_478(det, front_rgb)
    prof_mask = extract_profile_silhouette(profile_rgb)

    # Stage 2: Dual-View 3D RBF Head Morph (Front 468 + Real Side Profile + Tucked Ears + Wrapped Orbital Rim!)
    rbf_3d, (eye_dx, eye_dy, eye_dz), prof_target_curve = fit_dual_view_3d_morph(
        face_xyz, face_uv, lms_base_2d, lms_photo_2d, xyz_buf, valid_buf, prof_mask
    )
    morphed_xyz, max_front_mm, max_occ_mm, neck_seam_mm = apply_rbf_to_xyz(face_xyz, rbf_3d, eye_dx, eye_dy, eye_dz)
    morphed_nrm_list = _recalc_blended_normals(
        [tuple(map(float, r)) for r in morphed_xyz],
        [tuple(map(int, r)) for r in face_nrm],
        face_ib["inds"],
        blend=0.55,
    )
    morphed_nrm = np.array(morphed_nrm_list, dtype=np.int32)

    hxyz, _, _ = load_mesh_data(base_dec, base_vbs["Hair_fix-VB"])
    morphed_hair = sculpt_alcaraz_hair_fix(hxyz)

    morphed_geom_render, _, _ = render_ortho_head(
        base_dec, base_vbs, base_ibs, morphed_xyz, base_face_rgb, eye_tex, hair_tex_rgba,
        eye_dx=eye_dx, eye_dy=eye_dy, eye_dz=eye_dz, hair_xyz=morphed_hair, face_nrm_override=morphed_nrm, yaw_deg=0.0
    )
    lms_morphed_2d = detect_478(det, morphed_geom_render)

    # Stage 3: Dual-View Projective Baking (front_best.jpg + profile_best.jpg!)
    front_delit, target_skin_lab = delight_front_photo(front_rgb, lms_photo_2d, base_face_rgb)
    prof_delit = delight_profile_photo(profile_rgb, target_skin_lab)
    baked_uv_rgba, lab_shift = bake_dual_view_projective_uv(
        morphed_xyz, morphed_nrm, face_uv, face_tris,
        lms_morphed_2d, lms_photo_2d, front_delit, prof_delit, prof_mask, base_face_rgba, target_skin_lab
    )

    baked_rgb_pil = Image.fromarray(baked_uv_rgba[:, :, :3])
    uv_out_path = os.path.join(out_dir, f"baked_alcaraz_uv_{args.tag}.png")
    baked_rgb_pil.save(uv_out_path)

    # Cool neutral charcoal-black Hair_fix-VB texture preserving feathered alpha tips!
    hair_lum = (0.299 * hair_tex_rgba[:, :, 0] + 0.587 * hair_tex_rgba[:, :, 1] + 0.114 * hair_tex_rgba[:, :, 2]) / 255.0
    rel_hlum = np.clip(hair_lum / 0.16, 0.35, 1.85)
    alc_hair_rgb = np.stack([
        np.clip(26.0 * (0.42 + 0.58 * rel_hlum), 8, 52),
        np.clip(25.0 * (0.42 + 0.58 * rel_hlum), 8, 50),
        np.clip(25.0 * (0.42 + 0.58 * rel_hlum), 8, 50),
    ], axis=-1).astype(np.uint8)
    alc_hair_rgba = np.dstack([alc_hair_rgb, hair_tex_rgba[:, :, 3]])

    morphed_front, _, _ = render_ortho_head(
        base_dec, base_vbs, base_ibs, morphed_xyz, baked_uv_rgba[:, :, :3], eye_tex, alc_hair_rgba,
        eye_dx=eye_dx, eye_dy=eye_dy, eye_dz=eye_dz, hair_xyz=morphed_hair, face_nrm_override=morphed_nrm, yaw_deg=0.0, shade=True
    )
    morphed_34, _, _ = render_ortho_head(
        base_dec, base_vbs, base_ibs, morphed_xyz, baked_uv_rgba[:, :, :3], eye_tex, alc_hair_rgba,
        eye_dx=eye_dx, eye_dy=eye_dy, eye_dz=eye_dz, hair_xyz=morphed_hair, face_nrm_override=morphed_nrm, yaw_deg=38.0, shade=True
    )
    morphed_side, _, _ = render_ortho_head(
        base_dec, base_vbs, base_ibs, morphed_xyz, baked_uv_rgba[:, :, :3], eye_tex, alc_hair_rgba,
        eye_dx=eye_dx, eye_dy=eye_dy, eye_dz=eye_dz, hair_xyz=morphed_hair, face_nrm_override=morphed_nrm, yaw_deg=90.0, shade=True
    )
    sil_overlay = build_silhouette_overlay(morphed_side, prof_target_curve)

    def label_tile(im_arr, text):
        out = im_arr.copy()
        cv2.rectangle(out, (0, 0), (out.shape[1], 44), (16, 18, 24), -1)
        cv2.putText(out, text, (16, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.78, (110, 255, 165), 2)
        return out

    row1 = np.hstack([
        label_tile(front_rgb, "REAL PHOTO: Carlos Alcaraz (Front)"),
        label_tile(morphed_front, f"NEW 3D ALCARAZ {args.tag}: Front (Rosier Tan + Tucked Ears + Clean Lips)"),
        label_tile(morphed_34, f"NEW 3D ALCARAZ {args.tag}: 3/4 Angle (38 deg, Charcoal Fade)"),
    ])
    row2 = np.hstack([
        label_tile(profile_rgb, "REAL PHOTO: Carlos Alcaraz (Left Profile)"),
        label_tile(morphed_side, f"NEW 3D ALCARAZ {args.tag}: Left Profile (Clean Eye Socket + Fade)"),
        label_tile(sil_overlay, "SILHOUETTE CHECK: Red=DJV Base vs Green=Real Alcaraz"),
    ])
    comp_path = os.path.join(out_dir, f"step2_3_ortho_comparison_{args.tag}.png")
    Image.fromarray(np.vstack([row1, row2])).save(comp_path)
    print(
        f"Rendered {comp_path} | front_max_disp={max_front_mm:.2f}mm | "
        f"occiput_max_disp={max_occ_mm:.2f}mm | neck_seam={neck_seam_mm:.4f}mm"
    )

    if args.offline_only:
        return

    # Pack into game/archive/HIGH/Player/Model/P_M_ALC_NG.sdo + verify NaN/inf, neck seam, and mip-0/mip-1!
    prev_sdo_path = os.path.join(out_dir, "P_M_ALC_NG_prev.sdo")
    target_dec = bytearray(decompress_sdo(open(prev_sdo_path, "rb").read()))
    target_vbs = {v["short_name"]: v for v in parse_vbs(target_dec)}
    target_ibs = {ib["short_name"]: ib for ib in parse_ibs(target_dec)}

    for vb_name in ("Face-VB", "Face_lodL-VB"):
        b_xyz, b_nrm = _read_vb_xyz_nrm(base_dec, base_vbs[vb_name])
        m_xyz_np, _, _, _ = apply_rbf_to_xyz(np.array(b_xyz, dtype=np.float32), rbf_3d, eye_dx, eye_dy, eye_dz)
        assert np.all(np.isfinite(m_xyz_np)), f"Non-finite vertex in {vb_name}"
        m_xyz_list = [tuple(map(float, r)) for r in m_xyz_np]
        ib = _find_ib_for_vb(target_ibs, vb_name)
        m_nrm_list = _recalc_blended_normals(m_xyz_list, b_nrm, ib["inds"], blend=0.55) if ib else b_nrm
        _write_vb_xyz_nrm(target_dec, target_vbs[vb_name], m_xyz_list, m_nrm_list)

    for h_name in ("Hair_fix-VB", "Hair_fix_lodL-VB"):
        bh_xyz, bh_nrm = _read_vb_xyz_nrm(base_dec, base_vbs[h_name])
        mh_np = sculpt_alcaraz_hair_fix(np.array(bh_xyz, dtype=np.float32))
        assert np.all(np.isfinite(mh_np)), f"Non-finite vertex in {h_name}"
        mh_list = [tuple(map(float, r)) for r in mh_np]
        hib = _find_ib_for_vb(target_ibs, h_name)
        mh_nrm = _recalc_blended_normals(mh_list, bh_nrm, hib["inds"], blend=0.35) if hib else bh_nrm
        _write_vb_xyz_nrm(target_dec, target_vbs[h_name], mh_list, mh_nrm)

    for lash_name in ("Eyelash-VB", "Eyelash_lodL-VB"):
        bl_xyz, bl_nrm = _read_vb_xyz_nrm(base_dec, base_vbs[lash_name])
        ml_xyz = [(x + (eye_dx if x >= 0 else -eye_dx), y + eye_dy, z + eye_dz) for (x, y, z) in bl_xyz]
        _write_vb_xyz_nrm(target_dec, target_vbs[lash_name], ml_xyz, bl_nrm)

    # Reset LeftEye_zero & RightEye_zero from base_dec exact translations + apply (eye_dx, eye_dy, eye_dz)!
    import re as _re
    p0_b = base_dec.find(b"Scene_Root\x00")
    p0_t = target_dec.find(b"Scene_Root\x00")
    for bone, sx in ((b"LeftEye_zero", -1.0), (b"RightEye_zero", +1.0)):
        ib_idx = base_dec.find(bone + b"\x00", p0_b)
        it_idx = target_dec.find(bone + b"\x00", p0_t)
        mb = _re.search(b"Parameter.Translation\x07Variant\x02", base_dec[ib_idx : ib_idx + 400])
        mt = _re.search(b"Parameter.Translation\x07Variant\x02", target_dec[it_idx : it_idx + 400])
        if mb and mt:
            tx, ty, tz = struct.unpack_from(">3f", base_dec, ib_idx + mb.end())
            # Head-local: tx=world +Y, ty=world -Z, tz=world +X
            struct.pack_into(">3f", target_dec, it_idx + mt.end(), tx + eye_dy, ty - eye_dz, tz + sx * eye_dx)

    soft_alpha = _soften_face_ao_alpha(base_face_pil.convert("RGBA").split()[3], "P_M_ALC_NG.sdo")
    final_face_pil = Image.merge("RGBA", (*baked_rgb_pil.split(), soft_alpha))

    ws_uv_path = os.path.join(REPO_ROOT, "assets", "face_uv_workspace", "26_ALC", "edited_face_uv.png")
    if os.path.exists(os.path.dirname(ws_uv_path)):
        baked_rgb_pil.save(ws_uv_path)

    target_slots = {s["name"]: s for s in parse_sdo_dds_slots(target_dec)}
    face_slot_name = [k for k in target_slots if "_B_face_" in k][0]
    replace_sdo_tex(target_dec, target_slots[face_slot_name], final_face_pil)
    _upgrade_hd_eyes(target_dec, target_slots, "26_ALC")
    _soften_face_normals(target_dec, target_slots, final_face_pil)

    for sname, sl in target_slots.items():
        if "_B_hair_" in sname:
            orig_hair_pil = extract_slot_image(target_dec, sl).convert("RGBA")
            h_rgba = np.dstack([alc_hair_rgb, np.array(orig_hair_pil)[:, :, 3]])
            replace_sdo_tex(target_dec, sl, Image.fromarray(h_rgba, mode="RGBA"))

    for sname, sl in target_slots.items():
        if "_B_body_" in sname:
            body_pil = extract_slot_image(base_dec, base_slots["P_DJV_B_body_IT.dds"]).convert("RGBA")
            b_arr = np.array(body_pil)
            b_lab = cv2.cvtColor(b_arr[:, :, :3], cv2.COLOR_RGB2LAB).astype(np.float32)
            b_lab[:, :, 0] = np.clip(b_lab[:, :, 0] + lab_shift[0], 0, 255)
            b_lab[:, :, 1] = np.clip(b_lab[:, :, 1] + lab_shift[1], 0, 255)
            b_lab[:, :, 2] = np.clip(b_lab[:, :, 2] + lab_shift[2], 0, 255)
            b_rgb_new = cv2.cvtColor(b_lab.astype(np.uint8), cv2.COLOR_LAB2RGB)
            replace_sdo_tex(target_dec, sl, Image.fromarray(np.dstack([b_rgb_new, b_arr[:, :, 3]]), mode="RGBA"))

    # Round-trip verify mip-0 & mip-1 RGB integrity on P_ALC_B_face_NG.dds!
    comp_bytes = lzss_compress_literal(bytes(target_dec))
    open(args.out_sdo, "wb").write(comp_bytes)

    rt_dec = decompress_sdo(open(args.out_sdo, "rb").read())
    rt_slots = {s["name"]: s for s in parse_sdo_dds_slots(rt_dec)}
    fslot = rt_slots[face_slot_name]
    rt_m0 = np.array(extract_slot_image(rt_dec, fslot).convert("RGB"), dtype=np.float32)
    mip0_sz = (fslot["w"] // 4) * (fslot["h"] // 4) * 16
    mip1_sz = (fslot["w"] // 8) * (fslot["h"] // 8) * 16
    hdr = bytearray(rt_dec[fslot["off"] : fslot["off"] + 128])
    struct.pack_into("<IIIII", hdr, 12, fslot["h"] // 2, fslot["w"] // 2, mip1_sz, 0, 1)
    m1_bytes = bytes(hdr) + rt_dec[fslot["off"] + 128 + mip0_sz : fslot["off"] + 128 + mip0_sz + mip1_sz]
    rt_m1 = np.array(Image.open(io.BytesIO(m1_bytes)).convert("RGB"), dtype=np.float32)
    ref_m0 = np.array(baked_rgb_pil.convert("RGB"), dtype=np.float32)
    ref_m1 = np.array(baked_rgb_pil.convert("RGB").resize((512, 512), Image.Resampling.LANCZOS), dtype=np.float32)
    diff_m0 = float(np.mean(np.abs(rt_m0 - ref_m0)))
    diff_m1 = float(np.mean(np.abs(rt_m1 - ref_m1)))
    assert diff_m0 < 3.5 and diff_m1 < 3.5, f"Mip diff too high: m0={diff_m0}, m1={diff_m1}"
    print(
        f"Packed & verified {args.out_sdo} ({len(comp_bytes):,} bytes) | "
        f"neck_seam={neck_seam_mm:.4f}mm | NaN/inf=0 | mip0_diff={diff_m0:.2f} | mip1_diff={diff_m1:.2f}"
    )


if __name__ == "__main__":
    main()
