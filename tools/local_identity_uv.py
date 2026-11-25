#!/usr/bin/env python3
"""
Local Zero-Filter Biometric Identity UV Generator (ArcFace w600k_r50 + HyperSwap 1C 256 + GPEN-BFR-512 ONNX).
100% pure onnxruntime + OpenCV + NumPy (ZERO PyTorch, ZERO insightface Cython, ZERO cache outside scratch/local_faceswap/).
Generalized across ALL Male & Female SEGA VT4 UV layouts (eye_y=144..401, men & women, headbands & caps).
Fast (< 4s/player warm) reusable CLI for transferring real biometric player identity onto any 1024x1024 VT4 face UV!
"""
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SWAP_ROOT = os.path.join(REPO_ROOT, "scratch", "local_faceswap")
MODEL_DIR = os.path.join(SWAP_ROOT, "models")

# Enforce strict zero-trace containment inside scratch/local_faceswap/ BEFORE importing any ML libs!
os.environ["INSIGHTFACE_HOME"] = SWAP_ROOT
os.environ["HF_HOME"] = os.path.join(SWAP_ROOT, "hf_cache")
os.environ["XDG_CACHE_HOME"] = os.path.join(SWAP_ROOT, "xdg_cache")
os.environ["TMP"] = os.path.join(SWAP_ROOT, "tmp")
os.environ["TEMP"] = os.path.join(SWAP_ROOT, "tmp")
os.makedirs(os.environ["TMP"], exist_ok=True)

import argparse
import sys
import time
import cv2
import numpy as np
import onnxruntime as ort
from PIL import Image
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

# Exact InsightFace ArcFace 112x112 5-point canonical template: [L_eye, R_eye, nose, L_mouth, R_mouth]
ARCFACE_112 = np.array([
    [38.2946, 51.6963],
    [73.5318, 51.5014],
    [56.0252, 71.7366],
    [41.5493, 92.3655],
    [70.7299, 92.2041],
], dtype=np.float32)

# Exact InsightFace inswapper_128 alignment template (ratio=1.0, diff_x=+8.0) and HyperSwap 256 (x2.0)
ARCFACE_128 = ARCFACE_112 + np.array([8.0, 0.0], dtype=np.float32)
ARCFACE_256 = ARCFACE_128 * 2.0

# Exact FFHQ 512x512 5-point alignment template for GFPGANv1.4
FFHQ_512 = np.array([
    [192.98138, 239.94708],
    [318.90277, 240.19360],
    [256.63416, 314.01935],
    [201.26117, 371.41043],
    [313.08905, 371.15118],
], dtype=np.float32)

_CACHE = {}


def _get_sessions():
    if "loaded" in _CACHE:
        return _CACHE
    opts = ort.SessionOptions()
    opts.inter_op_num_threads = 1
    opts.intra_op_num_threads = 8
    opts.log_severity_level = 3

    arc_sess = ort.InferenceSession(os.path.join(MODEL_DIR, "arcface_w600k_r50.onnx"), opts, providers=["CPUExecutionProvider"])

    hs_path = os.path.join(MODEL_DIR, "hyperswap_1c_256.onnx")
    insw_path = os.path.join(MODEL_DIR, "inswapper_128_fp16.onnx")
    if os.path.exists(hs_path):
        swap_sess = ort.InferenceSession(hs_path, opts, providers=["CPUExecutionProvider"])
        swap_mode = "hyperswap_256"
        emap = None
    else:
        swap_sess = ort.InferenceSession(insw_path, opts, providers=["CPUExecutionProvider"])
        swap_mode = "inswapper_128"
        emap_cache = os.path.join(MODEL_DIR, "inswapper_emap.npy")
        if os.path.exists(emap_cache):
            emap = np.load(emap_cache).astype(np.float32)
        else:
            import onnx
            from onnx import numpy_helper
            m = onnx.load(insw_path)
            emap = numpy_helper.to_array(m.graph.initializer[-1]).astype(np.float32)
            np.save(emap_cache, emap)

    gpen_path = os.path.join(MODEL_DIR, "gpen_bfr_512.onnx")
    gfp_path = os.path.join(MODEL_DIR, "gfpgan_1.4.onnx")
    if os.path.exists(gpen_path):
        gfp_sess = ort.InferenceSession(gpen_path, opts, providers=["CPUExecutionProvider"])
        enh_mode = "gpen_512"
    else:
        gfp_sess = ort.InferenceSession(gfp_path, opts, providers=["CPUExecutionProvider"])
        enh_mode = "gfpgan_512"

    mp_task = os.path.join(REPO_ROOT, "scratch", "real_alcaraz_3d", "face_landmarker.task")
    det = vision.FaceLandmarker.create_from_options(
        vision.FaceLandmarkerOptions(base_options=mp_python.BaseOptions(model_asset_path=mp_task), num_faces=1)
    )

    _CACHE.update({
        "loaded": True,
        "arc": arc_sess,
        "swap": swap_sess,
        "swap_mode": swap_mode,
        "gfp": gfp_sess,
        "enh_mode": enh_mode,
        "emap": emap,
        "det": det,
    })
    return _CACHE


def _fit_similarity_2d(src_pts: np.ndarray, dst_pts: np.ndarray) -> np.ndarray:
    """Exact 2x3 2D similarity matrix mapping src_pts -> dst_pts (zero OpenCV 5.1 slice issues)."""
    s = np.asarray(src_pts, dtype=np.float64)
    d = np.asarray(dst_pts, dtype=np.float64)
    mu_s = s.mean(axis=0)
    mu_d = d.mean(axis=0)
    cs = s - mu_s
    cd = d - mu_d
    ss = float(np.sum(cs * cs))
    a = float(np.sum(cs[:, 0] * cd[:, 0] + cs[:, 1] * cd[:, 1])) / max(ss, 1e-12)
    b = float(np.sum(cs[:, 0] * cd[:, 1] - cs[:, 1] * cd[:, 0])) / max(ss, 1e-12)
    tx = mu_d[0] - (a * mu_s[0] - b * mu_s[1])
    ty = mu_d[1] - (b * mu_s[0] + a * mu_s[1])
    return np.array([[a, -b, tx], [b, a, ty]], dtype=np.float32)


def _detect_raw_mp(rgb: np.ndarray):
    m = _get_sessions()
    arr = np.ascontiguousarray(rgb, dtype=np.uint8)
    H, W = arr.shape[:2]
    res = m["det"].detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=arr))
    if not res.face_landmarks:
        return None
    lms = np.array([[lm.x * W, lm.y * H] for lm in res.face_landmarks[0]], dtype=np.float32)
    if len(lms) >= 478:
        le = 0.55 * lms[468] + 0.45 * np.mean(lms[[33, 133, 159, 145]], axis=0)
        re = 0.55 * lms[473] + 0.45 * np.mean(lms[[362, 263, 386, 374]], axis=0)
    else:
        le = np.mean(lms[[33, 133, 159, 145]], axis=0)
        re = np.mean(lms[[362, 263, 386, 374]], axis=0)
    kps5 = np.stack([le, re, lms[1], lms[61], lms[291]], axis=0).astype(np.float32)
    return kps5, lms


def detect_kps5_and_lms(rgb: np.ndarray, allow_pad_fallback: bool = True):
    """Detect 478 MediaPipe landmarks and exact 5-point biometric landmarks [L_eye, R_eye, nose, L_mouth, R_mouth].
    Automatically retries with 256px top replicate-padding for tight-top UV layouts (e.g. P_M_DEL_SN eye_y=144!)."""
    out = _detect_raw_mp(rgb)
    if out is not None:
        return out
    if allow_pad_fallback:
        pad_top = 256
        padded = cv2.copyMakeBorder(rgb, pad_top, 64, 64, 64, cv2.BORDER_REPLICATE)
        out2 = _detect_raw_mp(padded)
        if out2 is not None:
            kps5, lms = out2
            kps5 = kps5 - np.array([64.0, float(pad_top)], dtype=np.float32)
            lms = lms - np.array([64.0, float(pad_top)], dtype=np.float32)
            return kps5, lms
    raise RuntimeError("No face detected by MediaPipe")


def extract_arcface_embedding(rgb: np.ndarray) -> np.ndarray:
    """Extract L2-normalized 512-d ArcFace identity vector from an RGB portrait."""
    m = _get_sessions()
    kps5, _ = detect_kps5_and_lms(rgb)
    M = _fit_similarity_2d(kps5, ARCFACE_112)
    crop = cv2.warpAffine(rgb, M, (112, 112), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    inp = ((crop.astype(np.float32) - 127.5) / 127.5).transpose(2, 0, 1)[np.newaxis, ...]
    emb = m["arc"].run(None, {m["arc"].get_inputs()[0].name: inp})[0].flatten().astype(np.float32)
    emb /= (np.linalg.norm(emb) + 1e-8)
    return emb


def extract_eye_socket_cutout_mask(template_uv: np.ndarray, kps5_hint: np.ndarray | None = None) -> tuple[np.ndarray, list]:
    """Dynamically detect exact dark hollow eye-socket cutouts on ANY SEGA VT4 1024x1024 UV layout
    (handles UV_EYE_Y ~ 0.14..0.40, men & women, light & dark skin, dark-red & dark-gray/brown sockets!)."""
    H, W = template_uv.shape[:2]
    if kps5_hint is None:
        kps5_hint, _ = detect_kps5_and_lms(template_uv)
    le, re = kps5_hint[0], kps5_hint[1]
    iod = float(np.linalg.norm(re - le))
    iod = float(np.clip(iod, 110.0, 260.0))

    lab = cv2.cvtColor(template_uv, cv2.COLOR_RGB2LAB).astype(np.float32)
    L = lab[:, :, 0]
    rg = template_uv[:, :, 0].astype(np.float32) - template_uv[:, :, 1].astype(np.float32)

    mask = np.zeros((H, W), dtype=np.uint8)
    centers = []
    for eye_pt in (le, re):
        ex, ey = float(eye_pt[0]), float(eye_pt[1])
        x0 = max(0, int(round(ex - 0.36 * iod)))
        x1 = min(W, int(round(ex + 0.36 * iod)))
        # Keep search ceiling safely below eyebrows (ey - 0.15*iod) and below lower lid (ey + 0.16*iod)
        y0 = max(0, int(round(ey - 0.15 * iod)))
        y1 = min(H, int(round(ey + 0.16 * iod)))

        # Estimate local cheek/under-eye skin luminance right below the eye socket so thresholds adapt to ALL skin tones!
        sy0 = min(H - 1, int(round(ey + 0.18 * iod)))
        sy1 = min(H, int(round(ey + 0.36 * iod)))
        skin_patch = L[sy0:sy1, x0:x1]
        skin_L = float(np.percentile(skin_patch, 65)) if skin_patch.size > 16 else 145.0

        sub_L = L[y0:y1, x0:x1]
        sub_rg = rg[y0:y1, x0:x1]
        # Hollow SEGA eye interior: either dark reddish-brown void or dark neutral/black void relative to local skin
        thresh_red = min(105.0, max(38.0, skin_L * 0.74))
        thresh_dark = min(62.0, max(24.0, skin_L * 0.46))
        cut = ((sub_L < thresh_red) & (sub_rg > 7.0)) | (sub_L < thresh_dark)
        cut_u8 = cv2.morphologyEx(cut.astype(np.uint8) * 255, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        cut_u8 = cv2.morphologyEx(cut_u8, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))

        num_l, labels, stats, cent = cv2.connectedComponentsWithStats(cut_u8)
        best = -1
        best_score = -1.0
        for cid in range(1, num_l):
            area = int(stats[cid, cv2.CC_STAT_AREA])
            cw = int(stats[cid, cv2.CC_STAT_WIDTH])
            ch = int(stats[cid, cv2.CC_STAT_HEIGHT])
            if area < 90 or area > int(0.45 * (x1 - x0) * (y1 - y0)):
                continue
            ccx = x0 + float(cent[cid][0])
            ccy = y0 + float(cent[cid][1])
            dist = float(np.hypot(ccx - ex, (ccy - ey) * 1.8))
            if dist > 0.26 * iod:
                continue
            aspect = cw / max(1.0, float(ch))
            score = area * (1.2 if 1.3 <= aspect <= 5.5 else 0.7) / (1.0 + dist / 20.0)
            if score > best_score:
                best_score = score
                best = cid

        if best > 0:
            best_m = (labels == best).astype(np.uint8) * 255
            mask[y0:y1, x0:x1] = np.maximum(mask[y0:y1, x0:x1], best_m)
            centers.append((
                x0 + float(cent[best][0]),
                y0 + float(cent[best][1]),
                int(stats[best, cv2.CC_STAT_WIDTH]),
                int(stats[best, cv2.CC_STAT_HEIGHT]),
                int(stats[best, cv2.CC_STAT_AREA]),
            ))
        else:
            rx = max(16, int(round(0.16 * iod)))
            ry = max(7, int(round(0.065 * iod)))
            cv2.ellipse(mask, (int(round(ex)), int(round(ey))), (rx, ry), 0, 0, 360, 255, -1)
            centers.append((ex, ey, rx * 2, ry * 2, int(np.pi * rx * ry)))

    # Enforce bilateral symmetry if one eye socket void was missed or significantly smaller than its mirror twin!
    if len(centers) == 2:
        (cx0, cy0, w0, h0, a0), (cx1, cy1, w1, h1, a1) = centers
        if a0 > 1.5 * max(1, a1) or a1 > 1.5 * max(1, a0):
            if a0 >= a1:
                src_cx, src_cy, dst_cx, dst_cy = cx0, cy0, cx1, cy1
                rw, rh = max(w0, 48), max(h0, 26)
            else:
                src_cx, src_cy, dst_cx, dst_cy = cx1, cy1, cx0, cy0
                rw, rh = max(w1, 48), max(h1, 26)
            hx, hy = int(rw * 0.75), int(rh * 0.85)
            sx0, sx1 = max(0, int(src_cx - hx)), min(W, int(src_cx + hx))
            sy0, sy1 = max(0, int(src_cy - hy)), min(H, int(src_cy + hy))
            patch = cv2.flip(mask[sy0:sy1, sx0:sx1], 1)
            ph, pw = patch.shape[:2]
            dx0 = max(0, int(round(dst_cx - pw / 2.0)))
            dy0 = max(0, int(round(dst_cy - ph / 2.0)))
            dx1, dy1 = min(W, dx0 + pw), min(H, dy0 + ph)
            mask[dy0:dy1, dx0:dx1] = np.maximum(mask[dy0:dy1, dx0:dx1], patch[: dy1 - dy0, : dx1 - dx0])
        centers = [(cx0, cy0, w0, h0), (cx1, cy1, w1, h1)]
    else:
        centers = [(c[0], c[1], c[2], c[3]) for c in centers]

    return mask, centers


def synthesize_temp_eyes_on_uv(target_uv: np.ndarray, eye_mask: np.ndarray, centers: list) -> np.ndarray:
    """Step B: Temporarily fill the 2 hollow dark eye-socket voids with realistic neutral open eyes ONLY
    for landmark detection + neural face swapping/restoration (later restored cleanly to dark sockets!)."""
    out = target_uv.copy()
    soft = cv2.GaussianBlur(eye_mask.astype(np.float32) / 255.0, (7, 7), 1.8)
    eye_canvas = out.copy()
    for (cx, cy, w, h) in centers:
        icx, icy = int(round(cx)), int(round(cy))
        rx = max(16, int(round(w * 0.58)))
        ry = max(9, int(round(h * 0.65)))
        cv2.ellipse(eye_canvas, (icx, icy), (rx, ry), 0, 0, 360, (224, 214, 206), -1, cv2.LINE_AA)
        ir = max(8, int(round(ry * 0.88)))
        cv2.circle(eye_canvas, (icx, icy), ir, (46, 30, 22), -1, cv2.LINE_AA)
        cv2.circle(eye_canvas, (icx, icy), max(4, ir // 2), (14, 10, 10), -1, cv2.LINE_AA)
        cv2.circle(eye_canvas, (icx - 3, icy - 3), 2, (235, 232, 228), -1, cv2.LINE_AA)
    out = np.clip(out.astype(np.float32) * (1.0 - soft[:, :, None]) + eye_canvas.astype(np.float32) * soft[:, :, None], 0, 255).astype(np.uint8)
    return out


def color_match_lab_region(src_rgb: np.ndarray, ref_rgb: np.ndarray, mask_f: np.ndarray, strength: float = 0.85) -> np.ndarray:
    """Smooth LAB mean/std color transfer inside mask_f > 0.35 so swapped skin matches target_uv seamlessly."""
    s_lab = cv2.cvtColor(src_rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    r_lab = cv2.cvtColor(ref_rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    valid = mask_f > 0.35
    if not np.any(valid):
        return src_rgb
    out_lab = s_lab.copy()
    for c in range(3):
        sm, ss = float(s_lab[:, :, c][valid].mean()), float(s_lab[:, :, c][valid].std()) + 1e-4
        rm, rs = float(r_lab[:, :, c][valid].mean()), float(r_lab[:, :, c][valid].std()) + 1e-4
        ratio = np.clip(rs / ss, 0.80, 1.20)
        matched = (s_lab[:, :, c] - sm) * ratio + rm
        out_lab[:, :, c] = np.clip(s_lab[:, :, c] * (1.0 - strength) + matched * strength, 0, 255)
    return cv2.cvtColor(out_lab.astype(np.uint8), cv2.COLOR_LAB2RGB)


# MediaPipe inner-mouth & outer-lip landmark loops for Closed-Mouth Lip Guard
_INNER_LIP_IDX = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308, 324, 318, 402, 317, 14, 87, 178, 88, 95]
_OUTER_LIP_IDX = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291, 375, 321, 405, 314, 17, 84, 181, 91, 146]


def _enforce_closed_mouth_lips(rgb: np.ndarray, lms: np.ndarray | None, mode: str = "post") -> np.ndarray:
    """Closed-Mouth Lip Guard: eliminates painted open white teeth & dark mouth-cavity slits inside the lip parting
    while keeping natural closed lip vermilion & a soft natural lip seam (prevents GFPGAN teeth hallucination!)."""
    if lms is None or len(lms) < 420:
        return rgb
    H, W = rgb.shape[:2]
    out = rgb.copy()
    inner_poly = np.round(lms[_INNER_LIP_IDX]).astype(np.int32)
    outer_poly = np.round(lms[_OUTER_LIP_IDX]).astype(np.int32)

    m_in = np.zeros((H, W), dtype=np.uint8)
    m_out = np.zeros((H, W), dtype=np.uint8)
    cv2.fillPoly(m_in, [inner_poly], 255)
    cv2.fillPoly(m_out, [outer_poly], 255)
    # Slightly expand inner mouth slit horizontally/vertically (2px) so teeth edges are completely covered
    m_slit = cv2.dilate(m_in, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 7)))
    m_slit = cv2.bitwise_and(m_slit, m_out)
    m_vermilion = cv2.bitwise_and(m_out, cv2.bitwise_not(m_slit))

    if int(np.count_nonzero(m_slit)) < 12 or int(np.count_nonzero(m_vermilion)) < 25:
        return rgb

    lab = cv2.cvtColor(out, cv2.COLOR_RGB2LAB).astype(np.float32)
    v_pix = lab[m_vermilion > 0]
    lip_L = float(np.median(v_pix[:, 0]))
    lip_a = float(np.median(v_pix[:, 1]))
    lip_b = float(np.median(v_pix[:, 2]))

    L = lab[:, :, 0]
    chroma = np.hypot(lab[:, :, 1] - 128.0, lab[:, :, 2] - 128.0)

    if mode == "pre":
        # Before GFPGAN: softly close any dark mouth gap or pale tooth pixels so GFPGAN renders closed lips!
        bad = (m_slit > 0) & ((L < lip_L - 14.0) | ((L > lip_L + 10.0) & (chroma < 18.0)))
    else:
        # After GFPGAN: strictly suppress white teeth (L > lip_L + 8 & low chroma, or L > 152 & low chroma)
        # AND overly black open-mouth cavities (L < lip_L - 28)!
        is_tooth = ((L > min(155.0, lip_L + 8.0)) & (chroma < 18.0)) | ((L > 168.0) & (chroma < 24.0))
        is_cavity = L < max(38.0, lip_L - 26.0)
        bad = (m_slit > 0) & (is_tooth | is_cavity)

    if not np.any(bad):
        return rgb

    bad_f = cv2.GaussianBlur(bad.astype(np.float32), (7, 7), 1.6)
    # Natural closed-lip vermilion slightly darker at the very center parting line (soft realistic closed seam!)
    ys_s, xs_s = np.where(m_slit > 0)
    cy_lip = float(np.mean(ys_s))
    yy = np.arange(H, dtype=np.float32)[:, None]
    seam_shade = np.exp(-0.5 * ((yy - cy_lip) / 2.2) ** 2) * 14.0  # gentle -14 L closed lip line

    fill_lab = np.empty_like(lab)
    fill_lab[:, :, 0] = np.clip(lip_L - seam_shade, 35.0, 220.0)
    fill_lab[:, :, 1] = lip_a
    fill_lab[:, :, 2] = lip_b
    fill_rgb = cv2.cvtColor(fill_lab.astype(np.uint8), cv2.COLOR_LAB2RGB).astype(np.float32)

    out_f = out.astype(np.float32) * (1.0 - bad_f[:, :, None]) + fill_rgb * bad_f[:, :, None]
    return np.clip(out_f, 0, 255).astype(np.uint8)


def transfer_biometric_identity_uv(
    src_photo_paths: list[str],
    target_uv_path: str,
    template_uv_path: str,
    out_path: str,
    gfpgan_blend: float = 0.68,
    youthful_polish: bool = False,
    headband_safe: bool = False,
) -> dict:
    """Full Eye-Socket-Safe Local Biometric Identity UV Transfer (< 3s warm), generalized for ALL 19 SEGA bases
    with automatic Anisotropic UV Pre-Normalization (EDB/BEC/NAD/IVA/FED) + Closed-Mouth Lip Guard!"""
    t0 = time.perf_counter()
    m = _get_sessions()

    target_uv = np.array(Image.open(target_uv_path).convert("RGB").resize((1024, 1024), Image.Resampling.LANCZOS))
    template_uv = np.array(Image.open(template_uv_path).convert("RGB").resize((1024, 1024), Image.Resampling.LANCZOS))
    H, W = target_uv.shape[:2]

    # Step A: Extract & robustly average 512-d ArcFace identity embedding(s) from real player photo(s)
    embs = []
    used_refs = []
    src_sats = []
    for sp in src_photo_paths:
        try:
            s_rgb = np.array(Image.open(sp).convert("RGB"))
            embs.append(extract_arcface_embedding(s_rgb))
            used_refs.append(sp)
            s_f = s_rgb.astype(np.float32)
            src_sats.append(float(np.mean(np.max(s_f, axis=2) - np.min(s_f, axis=2))))
        except Exception:
            continue
    min_src_sat = min(src_sats) if src_sats else 30.0
    if not embs:
        raise RuntimeError(f"No valid face detected in any source photo: {src_photo_paths}")
    if len(embs) >= 3:
        mat = np.stack(embs, axis=0)
        sims = mat @ mat.T
        med_sim = np.median(sims, axis=1)
        keep = [i for i in range(len(embs)) if med_sim[i] >= 0.32]
        if keep:
            embs = [embs[i] for i in keep]
            used_refs = [used_refs[i] for i in keep]

    avg_emb = np.mean(np.stack(embs, axis=0), axis=0).astype(np.float32)
    avg_emb /= (np.linalg.norm(avg_emb) + 1e-8)
    if m["emap"] is not None:
        latent = (avg_emb.reshape(1, 512) @ m["emap"]).astype(np.float32)
        latent /= (np.linalg.norm(latent) + 1e-8)
    else:
        latent = avg_emb.reshape(1, 512)

    # Step B: Detect layout dynamically from template_uv & temporarily fill hollow dark eye sockets on target UV!
    tmpl_kps5, _ = detect_kps5_and_lms(template_uv)
    eye_cut_mask, eye_centers = extract_eye_socket_cutout_mask(template_uv, kps5_hint=tmpl_kps5)
    uv_with_eyes = synthesize_temp_eyes_on_uv(target_uv, eye_cut_mask, eye_centers)
    try:
        uv_kps5, uv_lms = detect_kps5_and_lms(uv_with_eyes)
    except Exception:
        uv_kps5, uv_lms = tmpl_kps5.copy(), None

    # Step B2 (BUG #1 FIX!): Anisotropic Aspect Pre-Normalization for stretched SEGA UV bases (EDB=0.726, BEC=0.846,
    # NAD=0.892, IVA=1.168, FED=1.165)! Pre-stretch to exact 1:1 canonical ARCFACE aspect BEFORE inswapper + GFPGAN,
    # then cleanly unwarp back to exact (W, H) -> ZERO vertical face squishing or parted-lip distortion!
    arc_iod = float(np.linalg.norm(ARCFACE_112[1] - ARCFACE_112[0]))
    arc_fh = float(0.5 * (ARCFACE_112[3, 1] + ARCFACE_112[4, 1]) - 0.5 * (ARCFACE_112[0, 1] + ARCFACE_112[1, 1]))
    arc_ar = arc_iod / arc_fh  # ~0.866

    uv_iod = float(np.linalg.norm(uv_kps5[1] - uv_kps5[0]))
    uv_fh = float(0.5 * (uv_kps5[3, 1] + uv_kps5[4, 1]) - 0.5 * (uv_kps5[0, 1] + uv_kps5[1, 1]))
    uv_ar = uv_iod / max(uv_fh, 1.0)
    ar_ratio = uv_ar / arc_ar

    sx_iso, sy_iso = 1.0, 1.0
    if abs(ar_ratio - 1.0) > 0.06:
        if ar_ratio < 1.0:
            # Vertically stretched UV (e.g. EDB, BEC, NAD): stretch X wider so aspect becomes 1:1 isotropic!
            sx_iso = float(np.clip(1.0 / ar_ratio, 1.0, 1.55))
        else:
            # Horizontally stretched UV (e.g. IVA, FED): stretch Y taller so aspect becomes 1:1 isotropic!
            sy_iso = float(np.clip(ar_ratio, 1.0, 1.40))

    W_iso = int(round(W * sx_iso))
    H_iso = int(round(H * sy_iso))
    if W_iso != W or H_iso != H:
        iso_eyes = cv2.resize(uv_with_eyes, (W_iso, H_iso), interpolation=cv2.INTER_CUBIC)
        iso_tgt = cv2.resize(target_uv, (W_iso, H_iso), interpolation=cv2.INTER_CUBIC)
        iso_kps5 = uv_kps5.copy()
        iso_kps5[:, 0] *= (W_iso / float(W))
        iso_kps5[:, 1] *= (H_iso / float(H))
    else:
        iso_eyes = uv_with_eyes
        iso_tgt = target_uv
        iso_kps5 = uv_kps5.copy()

    # Pre-close any dark open-mouth slit on iso_eyes before inswapper/GFPGAN
    try:
        _, iso_lms_pre = detect_kps5_and_lms(iso_eyes)
        iso_eyes_clean = _enforce_closed_mouth_lips(iso_eyes, iso_lms_pre, mode="pre")
    except Exception:
        iso_lms_pre = None
        iso_eyes_clean = iso_eyes

    # Step C: Run HyperSwap 1C 256 (or fallback inswapper_128) on isotropic aligned face!
    if m.get("swap_mode") == "hyperswap_256":
        M_swap = _fit_similarity_2d(iso_kps5, ARCFACE_256)
        tgt_256 = cv2.warpAffine(iso_eyes_clean, M_swap, (256, 256), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        swap_in = ((tgt_256.astype(np.float32) / 255.0 - 0.5) / 0.5).transpose(2, 0, 1)[np.newaxis, ...]
        swap_outs = m["swap"].run(None, {"target": swap_in, "source": latent})
        swapped_patch = np.clip((swap_outs[0][0].transpose(1, 2, 0) * 0.5 + 0.5) * 255.0, 0, 255).astype(np.uint8)
        hs_mask = np.clip(swap_outs[1][0, 0], 0.0, 1.0) if len(swap_outs) > 1 else np.ones((256, 256), dtype=np.float32)
        yy256, xx256 = np.mgrid[0:256, 0:256]
        ell256 = np.clip(1.0 - (((xx256 - 128.0) / 100.0) ** 2 + ((yy256 - 140.0) / 110.0) ** 2), 0.0, 1.0)
        ell256 = cv2.GaussianBlur((ell256 > 0.05).astype(np.float32), (31, 31), 9.5)
        m_patch = cv2.GaussianBlur(np.minimum(hs_mask, ell256).astype(np.float32), (15, 15), 4.0)
        # Keep swapper border artifact-free before warping back
        m_patch[:3, :] = 0.0; m_patch[-3:, :] = 0.0; m_patch[:, :4] = 0.0; m_patch[:, -4:] = 0.0
    else:
        M_swap = _fit_similarity_2d(iso_kps5, ARCFACE_128)
        tgt_128 = cv2.warpAffine(iso_eyes_clean, M_swap, (128, 128), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        swap_in = (tgt_128.astype(np.float32) / 255.0).transpose(2, 0, 1)[np.newaxis, ...]
        swap_out = m["swap"].run(None, {"target": swap_in, "source": latent})[0][0]
        swapped_patch = np.clip(swap_out.transpose(1, 2, 0) * 255.0, 0, 255).astype(np.uint8)
        yy128, xx128 = np.mgrid[0:128, 0:128]
        m_patch = np.clip(1.0 - (((xx128 - 64.0) / 50.0) ** 2 + ((yy128 - 70.0) / 55.0) ** 2), 0.0, 1.0)
        m_patch = cv2.GaussianBlur((m_patch > 0.05).astype(np.float32), (21, 21), 6.5)

    swapped_iso = cv2.warpAffine(swapped_patch, M_swap, (W_iso, H_iso), flags=cv2.WARP_INVERSE_MAP | cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    mask_swap_iso = cv2.warpAffine(m_patch, M_swap, (W_iso, H_iso), flags=cv2.WARP_INVERSE_MAP | cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0.0)

    swapped_iso_cm = color_match_lab_region(swapped_iso, iso_eyes_clean, mask_swap_iso, strength=0.80)
    canvas_swapped_iso = np.clip(
        iso_eyes_clean.astype(np.float32) * (1.0 - mask_swap_iso[:, :, None])
        + swapped_iso_cm.astype(np.float32) * mask_swap_iso[:, :, None],
        0,
        255,
    ).astype(np.uint8)
    # Close mouth slit again right before GFPGAN so GFPGAN renders natural closed lips (zero hallucinated teeth!)
    canvas_swapped_iso = _enforce_closed_mouth_lips(canvas_swapped_iso, iso_lms_pre, mode="pre")

    # Step D: Run gfpgan_1.4.onnx (512x512 HD neural face restorer) in exact 1:1 isotropic space!
    M_gfp = _fit_similarity_2d(iso_kps5, FFHQ_512)
    gfp_crop = cv2.warpAffine(canvas_swapped_iso, M_gfp, (512, 512), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    gfp_in = ((gfp_crop.astype(np.float32) / 255.0 - 0.5) / 0.5).transpose(2, 0, 1)[np.newaxis, ...]
    gfp_out = m["gfp"].run(None, {m["gfp"].get_inputs()[0].name: gfp_in})[0][0]
    restored_512 = np.clip((gfp_out.transpose(1, 2, 0) * 0.5 + 0.5) * 255.0, 0, 255).astype(np.uint8)

    restored_iso = cv2.warpAffine(restored_512, M_gfp, (W_iso, H_iso), flags=cv2.WARP_INVERSE_MAP | cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    restored_iso_cm = color_match_lab_region(restored_iso, iso_tgt, mask_swap_iso, strength=0.88)

    hd_iso = np.clip(
        swapped_iso_cm.astype(np.float32) * (1.0 - gfpgan_blend)
        + restored_iso_cm.astype(np.float32) * gfpgan_blend,
        0,
        255,
    ).astype(np.uint8)

    # Post-GFPGAN Closed-Mouth Lip Guard in isotropic space!
    try:
        _, gfp_iso_lms = detect_kps5_and_lms(hd_iso)
        hd_iso = _enforce_closed_mouth_lips(hd_iso, gfp_iso_lms, mode="post")
    except Exception:
        if iso_lms_pre is not None:
            hd_iso = _enforce_closed_mouth_lips(hd_iso, iso_lms_pre, mode="post")

    # B&W-Ref Chromatic Skin Guard: if reference portrait is grayscale (e.g. 1973 BJK / 1995 Muster),
    # lock A/B skin chroma 92% to warm iso_tgt so facial structure transfers WITHOUT bleaching skin!
    if min_src_sat < 14.0:
        hd_lab = cv2.cvtColor(hd_iso, cv2.COLOR_RGB2LAB).astype(np.float32)
        tg_lab = cv2.cvtColor(iso_tgt, cv2.COLOR_RGB2LAB).astype(np.float32)
        v_ch = mask_swap_iso > 0.30
        if np.any(v_ch):
            for c in (1, 2):
                sm, ss = float(hd_lab[:, :, c][v_ch].mean()), float(hd_lab[:, :, c][v_ch].std()) + 1e-4
                rm, rs = float(tg_lab[:, :, c][v_ch].mean()), float(tg_lab[:, :, c][v_ch].std()) + 1e-4
                matched = (hd_lab[:, :, c] - sm) * np.clip(rs / ss, 0.85, 1.15) + rm
                hd_lab[:, :, c] = np.clip(hd_lab[:, :, c] * 0.08 + matched * 0.92, 0, 255)
            hd_iso = cv2.cvtColor(hd_lab.astype(np.uint8), cv2.COLOR_LAB2RGB)

    # Unwarp cleanly back from isotropic space to exact original (W, H) UV aspect ratio!
    if W_iso != W or H_iso != H:
        hd_face = cv2.resize(hd_iso, (W, H), interpolation=cv2.INTER_AREA)
        mask_swap_full = cv2.resize(mask_swap_iso, (W, H), interpolation=cv2.INTER_LINEAR)
    else:
        hd_face = hd_iso
        mask_swap_full = mask_swap_iso

    # Step E: Dynamic anatomical inner-face mask (adapts to ALL 19 male & female UV layouts, preserving hair, headbands, caps, ears & neck!)
    yy, xx = np.mgrid[0:H, 0:W]
    le, re = uv_kps5[0], uv_kps5[1]
    ml, mr = uv_kps5[3], uv_kps5[4]
    cx = 0.5 * (float(le[0]) + float(re[0]))
    eye_y = 0.5 * (float(le[1]) + float(re[1]))
    mouth_y = 0.5 * (float(ml[1]) + float(mr[1]))
    iod = float(np.clip(np.linalg.norm(re - le), 110.0, 250.0))
    face_h = float(np.clip(mouth_y - eye_y, 130.0, 280.0))

    ov_cy = eye_y + 0.50 * face_h
    ov_rx = 1.08 * iod
    ov_ry = 1.04 * face_h
    face_oval = np.clip(1.0 - (((xx - cx) / ov_rx) ** 2 + ((yy - ov_cy) / ov_ry) ** 2), 0.0, 1.0)
    face_oval = np.clip(face_oval * 1.9, 0.0, 1.0)

    # Gate cleanly below hairline/headband/cap (keeps top hair & headbands 100% untouched!)
    hl_factor = 0.40 if headband_safe else 0.52
    hair_y = max(4.0, eye_y - hl_factor * face_h)
    hairline_gate = np.clip((yy - hair_y) / max(18.0, 0.17 * face_h), 0.0, 1.0)
    blend_mask = cv2.GaussianBlur(
        (face_oval * hairline_gate * np.clip(mask_swap_full * 1.35, 0.0, 1.0)).astype(np.float32),
        (41, 41),
        13.0,
    )

    final_uv = np.clip(
        target_uv.astype(np.float32) * (1.0 - blend_mask[:, :, None])
        + hd_face.astype(np.float32) * blend_mask[:, :, None],
        0,
        255,
    ).astype(np.uint8)

    if youthful_polish:
        flab = cv2.cvtColor(final_uv, cv2.COLOR_RGB2LAB).astype(np.float32)
        ck_y0, ck_y1 = max(0, int(eye_y + 0.22 * face_h)), min(H, int(eye_y + 0.58 * face_h))
        ck_x0, ck_x1 = max(0, int(cx - 0.78 * iod)), min(W, int(cx - 0.38 * iod))
        cheek_L_ref = float(np.median(flab[ck_y0:ck_y1, ck_x0:ck_x1, 0])) if (ck_y1 > ck_y0 and ck_x1 > ck_x0) else 150.0
        g_cheek_stubble = np.clip(
            np.exp(-0.5 * (((xx - (cx - 0.76 * iod)) / (0.25 * iod)) ** 2 + ((yy - (eye_y + 0.76 * face_h)) / (0.31 * face_h)) ** 2))
            + np.exp(-0.5 * (((xx - (cx + 0.76 * iod)) / (0.25 * iod)) ** 2 + ((yy - (eye_y + 0.76 * face_h)) / (0.31 * face_h)) ** 2)),
            0.0,
            1.0,
        )
        dip = np.maximum(0.0, (cheek_L_ref - 10.0) - flab[:, :, 0])
        flab[:, :, 0] = np.clip(flab[:, :, 0] + 0.30 * dip * g_cheek_stubble, 0, 255)
        final_uv = cv2.cvtColor(flab.astype(np.uint8), cv2.COLOR_LAB2RGB)

    # Step F (CRITICAL!): Restore EXACT dark hollow inner eye-socket cutouts + tight lower lid rim from template_uv
    # (color-matched at 0.95 to final_uv surrounding eye skin so tanned/dark canvases NEVER show pale halos or black rings!)
    eye_dilate = cv2.dilate(eye_cut_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 15)))
    try:
        _, gfp_lms = detect_kps5_and_lms(hd_face)
        for eye_idx in (
            [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246],
            [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398],
        ):
            poly = np.round(gfp_lms[eye_idx]).astype(np.int32)
            cv2.fillPoly(eye_dilate, [poly], 255)
        eye_dilate = cv2.dilate(eye_dilate, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    except Exception:
        pass
    eye_ring = cv2.dilate(eye_dilate, np.ones((35, 35), np.uint8)).astype(np.float32) / 255.0
    tmpl_eye_cm = color_match_lab_region(template_uv, final_uv, eye_ring, strength=0.95)
    eye_restore_m = cv2.GaussianBlur(eye_dilate.astype(np.float32) / 255.0, (9, 9), 2.4)[:, :, None]
    final_uv = np.clip(
        final_uv.astype(np.float32) * (1.0 - eye_restore_m)
        + tmpl_eye_cm.astype(np.float32) * eye_restore_m,
        0,
        255,
    ).astype(np.uint8)

    # Measure biometric cosine similarity of the final UV (with temp eyes) back to real player ArcFace embedding!
    final_with_eyes = synthesize_temp_eyes_on_uv(final_uv, eye_cut_mask, eye_centers)
    try:
        sim_before = float(np.dot(avg_emb, extract_arcface_embedding(uv_with_eyes)))
    except Exception:
        sim_before = 0.0
    try:
        sim_after = float(np.dot(avg_emb, extract_arcface_embedding(final_with_eyes)))
    except Exception:
        sim_after = 0.0

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    Image.fromarray(final_uv).save(out_path)
    dt = time.perf_counter() - t0
    print(
        f"[Local Identity UV PASS] {os.path.basename(out_path)} | refs={len(used_refs)}/{len(src_photo_paths)} | "
        f"eye_y={eye_y:.0f} | ArcFace_cos_sim: {sim_before:.3f} -> {sim_after:.3f} | elapsed={dt:.2f}s"
    )
    return {
        "out_path": out_path,
        "refs_used": len(used_refs),
        "eye_y": float(eye_y),
        "sim_before": sim_before,
        "sim_after": sim_after,
        "elapsed_s": dt,
    }


def main():
    ap = argparse.ArgumentParser(description="Local Zero-Filter Biometric Identity UV Generator (ArcFace+HyperSwap256+GPEN512 ONNX)")
    ap.add_argument("--src-photos", nargs="+", required=True, help="1+ real player front photo paths")
    ap.add_argument("--target-uv", default=os.path.join(REPO_ROOT, "scratch", "uv_lab", "uv_nanobanana_v2.png"))
    ap.add_argument("--template-uv", default=os.path.join(REPO_ROOT, "scratch", "uv_lab", "uv_template.png"))
    ap.add_argument("--out", default=os.path.join(REPO_ROOT, "scratch", "uv_lab", "uv_local_arcface.png"))
    ap.add_argument("--gfpgan-blend", type=float, default=0.68, help="GPEN-BFR-512/GFPGAN HD restoration blend weight (0..1)")
    ap.add_argument("--youthful-polish", action="store_true", help="Gently soften upper-cheek beard shadow for 22yo freshness")
    ap.add_argument("--headband-safe", action="store_true", help="Keep upper forehead hairline/headband/cap strictly untouched")
    args = ap.parse_args()
    transfer_biometric_identity_uv(
        args.src_photos,
        args.target_uv,
        args.template_uv,
        args.out,
        gfpgan_blend=args.gfpgan_blend,
        youthful_polish=args.youthful_polish,
        headband_safe=args.headband_safe,
    )


if __name__ == "__main__":
    main()
