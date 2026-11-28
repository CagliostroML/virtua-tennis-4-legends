#!/usr/bin/env python3
"""
Pack the 6 previously B&W portraits (51 Lendl, 52 Connors, 55 Evert, 74 Muster,
75 Bruguera, 77 Wilander) from full-color clean sources into VT4 DDS assets:
  game/archive/HIGH/Frontend/VR/{photo_L,photo_eye,photo_S}/{51,52,55,74,75,77}.dds

Also copies clean RGB bust references for 74_MUS and 55_EVE to
assets/face_uv_photocraft_workspace/01_base_uv_y_referencias/
and builds scratch/bw_colorized_audit.png for visual inspection.
"""
import os
import sys
import cv2
import numpy as np
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
from import_edited_portraits import estimate_eye_y_256

REF_DIR = os.path.join(REPO_ROOT, "assets", "face_uv_photocraft_workspace", "01_base_uv_y_referencias")
MUSTER_SRC = (
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch")
    r"\thomas_muster_portrait_v2_1795629572468.jpg"
)
FLAT_BG_BGR = (72, 64, 60)  # RGB (60, 64, 72) == #3C4048
FLAT_BG_RGB = (60, 64, 72)

PLAYER_NAMES = {
    "51": "Lendl",
    "52": "Connors",
    "55": "Evert",
    "74": "Muster",
    "75": "Bruguera",
    "77": "Wilander",
}


def _keep_main_fg_component(alpha: np.ndarray, anchor_xy: tuple[int, int] | None = None) -> np.ndarray:
    """Keep the main connected opaque component (near anchor if given, else largest)."""
    h, w = alpha.shape
    mask = (alpha > 24).astype(np.uint8)
    num_c, comp = cv2.connectedComponents(mask, connectivity=8)
    if num_c <= 1:
        return alpha
    keep_lbl = 0
    if anchor_xy is not None:
        ax = max(0, min(w - 1, anchor_xy[0]))
        ay = max(0, min(h - 1, anchor_xy[1]))
        lbl = int(comp[ay, ax])
        if lbl > 0:
            keep_lbl = lbl
    if keep_lbl == 0:
        sizes = np.bincount(comp.ravel())
        sizes[0] = 0
        keep_lbl = int(np.argmax(sizes))
    out = alpha.copy()
    out[comp != keep_lbl] = 0
    return out


def cutout_flat_bg(
    bgr: np.ndarray,
    bg_bgr: tuple[int, int, int] | None = None,
    d_lo: float = 16.0,
    d_hi: float = 46.0,
    decontaminate_purple: bool = False,
) -> Image.Image:
    """Cut out portrait over a flat/solid backdrop using border-connected matting."""
    h, w = bgr.shape[:2]
    bgr_f = bgr.astype(np.float32)

    if bg_bgr is None:
        top_strip = bgr_f[:10, :, :].reshape(-1, 3)
        left_strip = bgr_f[: int(h * 0.65), :10, :].reshape(-1, 3)
        right_strip = bgr_f[: int(h * 0.65), -10:, :].reshape(-1, 3)
        samples = np.vstack([top_strip, left_strip, right_strip])
        bg_vec = np.median(samples, axis=0)
    else:
        bg_vec = np.array(bg_bgr, dtype=np.float32)

    dist = np.linalg.norm(bgr_f - bg_vec[None, None, :], axis=2)

    # Pure background pixels connected to top/left/right borders
    cand_bg = (dist <= d_lo).astype(np.uint8)
    _, labels = cv2.connectedComponents(cand_bg, connectivity=4)
    border_labels = set(np.unique(np.concatenate([
        labels[0, :], labels[:, 0], labels[:, -1]
    ]))) - {0}
    bg_core = np.isin(labels, list(border_labels)) if border_labels else (dist <= d_lo)

    # Restrict soft transition strictly to pixels adjacent to border-connected background
    k_trans = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    trans_zone = cv2.dilate(bg_core.astype(np.uint8), k_trans, iterations=1) > 0

    alpha_f = np.ones((h, w), dtype=np.float32)
    alpha_f[bg_core] = 0.0
    ramp = np.clip((dist - d_lo) / max(1.0, d_hi - d_lo), 0.0, 1.0)
    in_ramp = trans_zone & (~bg_core)
    alpha_f[in_ramp] = ramp[in_ramp]

    alpha = np.clip(alpha_f * 255.0, 0, 255).astype(np.uint8)
    alpha = _keep_main_fg_component(alpha, (w // 2, int(h * 0.45)))
    alpha = cv2.GaussianBlur(alpha, (3, 3), 0.6)
    alpha[alpha < 18] = 0
    alpha[alpha > 238] = 255

    # Decontaminate semi-transparent edge pixels against sampled background color
    rgb_f = bgr_f[:, :, ::-1].copy()
    bg_rgb = bg_vec[::-1]
    a_norm = alpha.astype(np.float32) / 255.0
    edge = (alpha > 0) & (alpha < 238)
    if np.any(edge):
        ae = np.maximum(a_norm[edge][:, None], 0.28)
        rgb_f[edge] = (rgb_f[edge] - (1.0 - a_norm[edge][:, None]) * bg_rgb[None, :]) / ae
        if decontaminate_purple:
            # Neutralize faint violet/magenta spill on blonde/brown hair fringe
            r, g, b = rgb_f[edge, 0], rgb_f[edge, 1], rgb_f[edge, 2]
            purple_excess = np.maximum(0.0, b - np.maximum(r, g))
            rgb_f[edge, 2] -= purple_excess * 0.80
            rgb_f[edge, 0] -= purple_excess * 0.15

    rgb = np.clip(rgb_f, 0, 255).astype(np.uint8)
    return Image.fromarray(np.dstack([rgb, alpha]), "RGBA")


def save_clean_flat_ref_512(cutout_rgba: Image.Image, out_path: str) -> None:
    """Save a 512x512 RGB bust over standard #3C4048 backdrop for the UV workspace."""
    bb = cutout_rgba.getbbox()
    cropped = cutout_rgba.crop((bb[0], bb[1], bb[2], cutout_rgba.height)) if bb else cutout_rgba
    cw, ch = cropped.size
    top_pad = 16
    scale = min(480 / max(1, cw), (512 - top_pad) / max(1, ch))
    nw = max(1, int(round(cw * scale)))
    nh = max(1, int(round(ch * scale)))
    resized = cropped.resize((nw, nh), Image.Resampling.LANCZOS)

    canvas = Image.new("RGB", (512, 512), FLAT_BG_RGB)
    canvas.paste(resized, ((512 - nw) // 2, 512 - nh), resized)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    canvas.save(out_path)


def _detect_face_box(gray: np.ndarray) -> tuple[int, int, int, int]:
    cascade_path = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
    clf = cv2.CascadeClassifier(cascade_path)
    h, w = gray.shape
    faces = clf.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=4, minSize=(int(w * 0.16), int(h * 0.16)))
    if len(faces) > 0:
        best = max(faces, key=lambda r: r[2] * r[3])
        return tuple(int(v) for v in best)
    return (int(w * 0.28), int(h * 0.18), int(w * 0.44), int(h * 0.40))


def segment_evert_55(bgr: np.ndarray) -> Image.Image:
    """Segment Chris Evert (55) preserving sunlit blonde hair over dark green bokeh."""
    h, w = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    fx, fy, fw, fh = _detect_face_box(gray)
    cx = fx + fw // 2

    b_c, g_c, r_c = [ch.astype(np.float32) for ch in cv2.split(bgr)]
    max_c = np.maximum(np.maximum(r_c, g_c), b_c)
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    l_ch = lab[:, :, 0].astype(np.float32)

    mask = np.full((h, w), cv2.GC_PR_BGD, dtype=np.uint8)

    # Border-connected dark green bokeh (keep well clear of navy headband & lit hair)
    is_dark_bokeh = ((max_c < 50.0) | ((g_c >= r_c - 2.0) & (max_c < 76.0))).astype(np.uint8)
    _, labels = cv2.connectedComponents(is_dark_bokeh, connectivity=4)
    border_labels = set(np.unique(np.concatenate([
        labels[0, :], labels[:, 0], labels[:, -1]
    ]))) - {0}
    if border_labels:
        mask[np.isin(labels, list(border_labels))] = cv2.GC_BGD

    # Outer upper-left / upper-right corners guaranteed background
    mask[: max(6, int(h * 0.04)), : max(6, int(cx - fw * 0.65))] = cv2.GC_BGD
    mask[: max(6, int(h * 0.04)), min(w - 6, int(cx + fw * 0.65)) :] = cv2.GC_BGD
    mask[: int(h * 0.62), : max(6, int(w * 0.025))] = cv2.GC_BGD
    mask[: int(h * 0.62), min(w - 6, int(w * 0.975)) :] = cv2.GC_BGD

    # Generous probable foreground across head, hair volume, and shoulders
    head_top = max(2, int(fy - fh * 0.95))
    pad_l = max(4, int(cx - fw * 1.15))
    pad_r = min(w - 4, int(cx + fw * 1.15))
    sub = mask[head_top:h, pad_l:pad_r]
    sub[sub != cv2.GC_BGD] = cv2.GC_PR_FGD

    # Keep full width of white striped shirt in lower torso
    shirt_y = min(h - 1, fy + int(fh * 1.18))
    mask[shirt_y:h, 1 : w - 1] = np.where(
        mask[shirt_y:h, 1 : w - 1] == cv2.GC_BGD,
        cv2.GC_BGD,
        cv2.GC_FGD,
    )

    # Protect sunlit blonde hair crown & side locks against dark background erosion
    hair_roi = np.zeros((h, w), dtype=bool)
    cv2.ellipse(
        hair_roi.view(np.uint8),
        (cx, max(10, fy + int(fh * 0.12))),
        (max(16, int(fw * 0.85)), max(16, int(fh * 0.98))),
        0, 0, 360, 1, -1,
    )
    lit_blonde = (l_ch > 105.0) & ((r_c >= g_c - 6.0) | (l_ch > 155.0))
    mask[hair_roi & lit_blonde] = cv2.GC_FGD

    # Definite foreground: face + navy headband + neck + white striped shirt
    cv2.ellipse(
        mask,
        (cx, max(8, fy + int(fh * 0.22))),
        (max(10, int(fw * 0.42)), max(12, int(fh * 0.56))),
        0, 0, 360, int(cv2.GC_FGD), -1,
    )
    cv2.rectangle(
        mask,
        (max(0, cx - int(fw * 0.30)), min(h - 1, fy + int(fh * 0.65))),
        (min(w, cx + int(fw * 0.30)), h - 1),
        int(cv2.GC_FGD), -1,
    )
    shirt_y = min(h - 1, fy + int(fh * 1.18))
    if shirt_y < h - 8:
        shirt_sub = mask[shirt_y:h, max(14, cx - int(fw * 0.90)) : min(w - 14, cx + int(fw * 0.90))]
        shirt_sub[shirt_sub != cv2.GC_BGD] = cv2.GC_FGD

    bg_model = np.zeros((1, 65), np.float64)
    fg_model = np.zeros((1, 65), np.float64)
    cv2.grabCut(bgr, mask, None, bg_model, fg_model, 7, cv2.GC_INIT_WITH_MASK)

    fg = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    fg = _keep_main_fg_component(fg, (cx, min(h - 1, fy + fh // 2)))

    k3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, k3, iterations=1)
    alpha = cv2.GaussianBlur(fg, (3, 3), 0.75)
    alpha[alpha < 20] = 0
    alpha[alpha > 236] = 255

    # Decontaminate dark-green fringe on sunlit hair edges
    rgb_f = bgr[:, :, ::-1].astype(np.float32)
    edge = (alpha > 0) & (alpha < 236)
    if np.any(edge):
        a_norm = (alpha[edge].astype(np.float32) / 255.0)[:, None]
        dark_bg = np.array([16.0, 22.0, 18.0], dtype=np.float32)
        rgb_f[edge] = (rgb_f[edge] - (1.0 - a_norm) * dark_bg[None, :]) / np.maximum(a_norm, 0.32)

    rgb = np.clip(rgb_f, 0, 255).astype(np.uint8)
    return Image.fromarray(np.dstack([rgb, alpha]), "RGBA")


def _soften_flash_highlights(bgr: np.ndarray) -> np.ndarray:
    """Apply gentle roll-off to harsh flash highlights in LAB luminance without shifting hue."""
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    l_ch = lab[:, :, 0]
    over = np.maximum(0.0, l_ch - 188.0)
    # Softly compress highlights above L=188 (max 255 -> ~233)
    lab[:, :, 0] = np.where(l_ch > 188.0, 188.0 + over * 0.67, l_ch)
    # Tiny warmth boost on very bright skin highlights so flash doesn't wash out
    bright_mask = l_ch > 192.0
    lab[bright_mask, 1] = np.clip(lab[bright_mask, 1] + 1.5, 0, 255)
    lab[bright_mask, 2] = np.clip(lab[bright_mask, 2] + 3.0, 0, 255)
    return cv2.cvtColor(np.clip(lab, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)


def segment_connors_52(bgr_full: np.ndarray) -> Image.Image:
    """Segment Jimmy Connors (52) protecting upper-left hair edge and softening flash."""
    H, W = bgr_full.shape[:2]
    # Pre-crop out blurry bystander face at far right edge
    bgr = bgr_full[0 : int(H * 0.99), int(W * 0.02) : int(W * 0.945)].copy()
    bgr = _soften_flash_highlights(bgr)
    h, w = bgr.shape[:2]

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    fx, fy, fw, fh = _detect_face_box(gray)
    cx = fx + fw // 2

    b_c, g_c, r_c = [ch.astype(np.float32) for ch in cv2.split(bgr)]
    max_c = np.maximum(np.maximum(r_c, g_c), b_c)

    mask = np.full((h, w), cv2.GC_PR_BGD, dtype=np.uint8)

    # Only seed pure-black background connected to borders (max < 15) so dark brown hair stays safe
    is_very_dark = (max_c < 15.0).astype(np.uint8)
    _, labels = cv2.connectedComponents(is_very_dark, connectivity=4)
    border_labels = set(np.unique(np.concatenate([
        labels[0, :], labels[:, 0], labels[:, -1]
    ]))) - {0}
    if border_labels:
        mask[np.isin(labels, list(border_labels))] = cv2.GC_BGD

    # Blue-tinted bokeh rail far outside shoulders
    blue_rail = (b_c > r_c + 12.0) & (b_c > 48.0) & (np.arange(h)[:, None] < int(h * 0.76))
    side_out = (np.arange(w)[None, :] < int(w * 0.14)) | (np.arange(w)[None, :] > int(w * 0.84))
    mask[blue_rail & side_out] = cv2.GC_BGD

    # Margins
    m_x = max(6, int(w * 0.02))
    m_y = max(6, int(h * 0.02))
    mask[:, :m_x] = cv2.GC_BGD
    mask[:, w - m_x :] = cv2.GC_BGD
    mask[:m_y, : max(10, cx - int(fw * 0.65))] = cv2.GC_BGD
    mask[:m_y, min(w - 10, cx + int(fw * 0.65)) :] = cv2.GC_BGD

    # Generous head + hair region as probable foreground
    pad_top = max(4, int(fy - fh * 0.75))
    pad_l = max(m_x + 2, int(w * 0.12))
    pad_r = min(w - m_x - 2, int(w * 0.86))
    sub = mask[pad_top:h, pad_l:pad_r]
    sub[sub != cv2.GC_BGD] = cv2.GC_PR_FGD

    # Explicitly protect outer & upper-left brown hair locks (including lit outer strands)
    yy, xx = np.ogrid[:h, :w]
    hair_band = (
        (yy >= int(h * 0.06)) & (yy <= int(h * 0.50)) &
        (xx >= int(w * 0.18)) & (xx <= int(w * 0.80))
    )
    hair_signal = (max_c >= 20.0) & (r_c >= b_c)
    mask[hair_band & hair_signal] = cv2.GC_FGD

    # Definite foreground: crown-to-jaw oval + upper-left hair silhouette + neck + torso
    cv2.ellipse(
        mask,
        (cx, max(10, fy + int(fh * 0.28))),
        (max(12, int(fw * 0.42)), max(14, int(fh * 0.58))),
        0, 0, 360, int(cv2.GC_FGD), -1,
    )
    cv2.ellipse(
        mask,
        (max(16, cx - int(fw * 0.30)), max(16, fy - int(fh * 0.06))),
        (max(10, int(fw * 0.24)), max(10, int(fh * 0.32))),
        0, 0, 360, int(cv2.GC_FGD), -1,
    )
    cv2.rectangle(
        mask,
        (max(0, cx - int(fw * 0.28)), fy + int(fh * 0.72)),
        (min(w, cx + int(fw * 0.28)), h - 1),
        int(cv2.GC_FGD), -1,
    )
    chest_y = min(h - 1, fy + int(fh * 1.24))
    if chest_y < h - 8:
        chest_sub = mask[chest_y:h, max(m_x + 4, cx - int(fw * 0.85)) : min(w - m_x - 4, cx + int(fw * 0.85))]
        chest_sub[chest_sub != cv2.GC_BGD] = cv2.GC_FGD

    bg_model = np.zeros((1, 65), np.float64)
    fg_model = np.zeros((1, 65), np.float64)
    cv2.grabCut(bgr, mask, None, bg_model, fg_model, 7, cv2.GC_INIT_WITH_MASK)

    fg = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    fg = _keep_main_fg_component(fg, (cx, min(h - 1, fy + fh // 2)))

    # Fill any interior dark-shadow hair pockets enclosed within the head/hair silhouette
    k15 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    fg_closed = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, k15, iterations=1)
    fg[0 : int(h * 0.56), :] = np.maximum(fg[0 : int(h * 0.56), :], fg_closed[0 : int(h * 0.56), :])

    k3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, k3, iterations=1)
    alpha = cv2.GaussianBlur(fg, (3, 3), 0.75)
    alpha[alpha < 20] = 0
    alpha[alpha > 236] = 255

    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return Image.fromarray(np.dstack([rgb, alpha]), "RGBA")


def build_cutout_74_muster() -> Image.Image:
    bgr = cv2.imread(MUSTER_SRC, cv2.IMREAD_COLOR)
    assert bgr is not None, f"Missing source: {MUSTER_SRC}"
    cutout = cutout_flat_bg(bgr, bg_bgr=None, d_lo=26.0, d_hi=64.0, decontaminate_purple=True)
    save_clean_flat_ref_512(cutout, os.path.join(REF_DIR, "74_MUS_ref_retrato.png"))
    return cutout


def build_cutout_77_wilander() -> Image.Image:
    src = os.path.join(REF_DIR, "77_WLD_ref_retrato.png")
    bgr = cv2.imread(src, cv2.IMREAD_COLOR)
    assert bgr is not None, f"Missing source: {src}"
    return cutout_flat_bg(bgr, bg_bgr=FLAT_BG_BGR, d_lo=14.0, d_hi=42.0)


def build_cutout_75_bruguera() -> Image.Image:
    src = os.path.join(REF_DIR, "75_BRU_ref_retrato.png")
    bgr = cv2.imread(src, cv2.IMREAD_COLOR)
    assert bgr is not None, f"Missing source: {src}"
    # 1. Crop y: 0..425 to remove the silver trophy plate completely
    bgr = bgr[0:425, 0:512].copy()
    # 2. Paint over the stray white sleeve of another person in lower-left corner
    sleeve_poly = np.array(
        [[0, 290], [108, 294], [144, 320], [165, 342], [176, 365], [189, 425], [0, 425]],
        dtype=np.int32,
    )
    cv2.fillPoly(bgr, [sleeve_poly], FLAT_BG_BGR)
    return cutout_flat_bg(bgr, bg_bgr=FLAT_BG_BGR, d_lo=14.0, d_hi=42.0)


def build_cutout_51_lendl() -> Image.Image:
    src = os.path.join(REF_DIR, "51_LEN_ref_retrato.png")
    bgr = cv2.imread(src, cv2.IMREAD_COLOR)
    assert bgr is not None, f"Missing source: {src}"
    # 1. Paint out blurry ghost silhouette behind Lendl's right shoulder
    ghost_poly = np.array(
        [[55, 22], [186, 22], [186, 178], [155, 196], [112, 212], [55, 244]],
        dtype=np.int32,
    )
    cv2.fillPoly(bgr, [ghost_poly], FLAT_BG_BGR)
    # 2. Crop clean bust removing extended hand/forearm on the right
    bgr = bgr[0:465, 0:340].copy()
    # 3. Gentle bilateral denoise only on foreground pixels (preserve flat bg)
    bg_mask = np.linalg.norm(bgr.astype(np.float32) - np.array(FLAT_BG_BGR, dtype=np.float32), axis=2) <= 10.0
    denoised = cv2.bilateralFilter(bgr, d=5, sigmaColor=24, sigmaSpace=24)
    denoised[bg_mask] = FLAT_BG_BGR
    return cutout_flat_bg(denoised, bg_bgr=FLAT_BG_BGR, d_lo=14.0, d_hi=42.0)


def build_cutout_55_evert() -> Image.Image:
    src = os.path.join(REPO_ROOT, "scratch", "uv_lab", "refs_57", "55_EVE", "ref_03.jpg")
    bgr = cv2.imread(src, cv2.IMREAD_COLOR)
    assert bgr is not None, f"Missing source: {src}"
    cutout = segment_evert_55(bgr)
    save_clean_flat_ref_512(cutout, os.path.join(REF_DIR, "55_EVE_ref_retrato.png"))
    return cutout


def build_cutout_52_connors() -> Image.Image:
    src = os.path.join(REPO_ROOT, "scratch", "uv_lab", "refs_57", "52_CON", "ref_01.jpg")
    bgr = cv2.imread(src, cv2.IMREAD_COLOR)
    assert bgr is not None, f"Missing source: {src}"
    return segment_connors_52(bgr)


JOBS = [
    ("51", build_cutout_51_lendl,    0.03, 85),
    ("52", build_cutout_52_connors,  0.03, 107),
    ("55", build_cutout_55_evert,    0.03, 113),
    ("74", build_cutout_74_muster,   0.03, 99),
    ("75", build_cutout_75_bruguera, 0.03, 75),
    ("77", build_cutout_77_wilander, 0.03, 84),
]


def _color_saturation_score(p256: Image.Image) -> float:
    arr = np.array(p256.convert("RGBA"))
    fg = arr[arr[:, :, 3] > 128, :3].astype(np.float32)
    if len(fg) == 0:
        return 0.0
    chroma = np.max(fg, axis=1) - np.min(fg, axis=1)
    return float(np.mean(chroma))


def main() -> None:
    packed = []
    vr_abs = os.path.join(REPO_ROOT, VR_DIR)

    for pid, builder_fn, top_pad, eye_y_ovr in JOBS:
        cutout = builder_fn()
        cutout = remove_small_alpha_islands(cutout, min_pixels=250)
        p256 = frame_portrait_256(cutout, (0, 0, cutout.width, cutout.height), top_pad)
        eye_y = eye_y_ovr if eye_y_ovr is not None else estimate_eye_y_256(p256)
        eye = build_eye_strip(p256, eye_y)
        ps = build_photo_s(p256)

        pl_path = os.path.join(vr_abs, "photo_L", f"{pid}.dds")
        pe_path = os.path.join(vr_abs, "photo_eye", f"{pid}.dds")
        ps_path = os.path.join(vr_abs, "photo_S", f"{pid}.dds")
        write_bgra_dds(p256, pl_path)
        write_bgra_dds(eye, pe_path)
        write_dxt5_dds(ps, ps_path)

        pl_size = os.path.getsize(pl_path)
        assert pl_size == 262272, f"{pid} photo_L size={pl_size} != 262272"
        c_tl = p256.getpixel((3, 3))[3]
        c_tr = p256.getpixel((252, 3))[3]
        assert c_tl <= 16 and c_tr <= 16, f"{pid} top corners not transparent: {(c_tl, c_tr)}"
        chroma = _color_saturation_score(p256)
        assert chroma > 10.0, f"{pid} looks grayscale (mean chroma={chroma:.2f})"

        packed.append((pid, p256, eye, eye_y, chroma))
        print(
            f"[OK] ID {pid} ({PLAYER_NAMES[pid]}): photo_L={pl_size} B, "
            f"corners=({c_tl},{c_tr}), eye_y={eye_y}, chroma={chroma:.1f}"
        )

    # Render 3x2 audit grid: photo_L on checkerboard + photo_eye below
    cols, rows = 3, 2
    cw, ch = 264, 344
    sheet = Image.new("RGB", (cols * cw, rows * ch), (24, 26, 34))
    tile = Image.new("RGB", (256, 256))
    tpx = tile.load()
    for y in range(256):
        for x in range(256):
            tpx[x, y] = (58, 62, 74) if ((x // 16) + (y // 16)) % 2 == 0 else (90, 94, 108)
    draw = ImageDraw.Draw(sheet)

    for idx, (pid, p256, eye, eye_y, _chroma) in enumerate(packed):
        r, c = divmod(idx, cols)
        x0, y0 = c * cw + 4, r * ch + 4
        sheet.paste(tile, (x0, y0))
        sheet.paste(p256, (x0, y0), p256)
        sheet.paste(eye, (x0, y0 + 258))
        draw.rectangle([x0, y0, x0 + 188, y0 + 18], fill=(14, 16, 22))
        draw.text((x0 + 6, y0 + 3), f"ID {pid} {PLAYER_NAMES[pid]} (eye={eye_y})", fill=(255, 228, 100))

    audit_path = os.path.join(REPO_ROOT, "scratch", "bw_colorized_audit.png")
    os.makedirs(os.path.dirname(audit_path), exist_ok=True)
    sheet.save(audit_path)
    Image.open(audit_path).verify()
    print("Saved audit sheet:", audit_path)


if __name__ == "__main__":
    main()
