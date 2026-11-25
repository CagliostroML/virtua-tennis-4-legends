#!/usr/bin/env python3
"""
Fix remaining 2D portraits in Virtua Tennis 4: Legends & Next-Gen Edition:
  - 82 (Mirra Andreeva): proper transparent studio cutout (was opaque green box)
  - 83 (Billie Jean King): 1975 color portrait cutout (was opaque sepia box)
  - 43 (Nick Kyrgios): clean frontal bust without racket obscuring face
  - 52 (Jimmy Connors): clean frontal bust without racket obscuring face
  - 58 (Garbine Muguruza): frontal studio cutout replacing 90-degree side profile
  - 67 (Guillermo Coria): 3/4-frontal backwards-cap portrait replacing strict side profile
  - 72 (Michael Chang): clean frontal portrait replacing strict side profile

Outputs photo_L/<id>.dds, photo_eye/<id>.dds, photo_S/<id>.dds into
game/archive/HIGH/Frontend/VR/ and writes scratch/portraits_fix_2026.png.
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


# (pid, rel_src_path, pre_crop_norm=(x0,y0,x1,y1), bg_mode, top_pad, eye_y_override)
TARGETS = [
    ("82", "scratch/uv_lab/phase6_refs/82_AND/wiki_main.jpg",        (0.02, 0.01, 0.98, 0.94), "green_wiki82", 0.03,  80),
    ("83", "scratch/uv_lab/refs_57/83_BJK/ref_bjk_1975_nara.jpg",    (0.04, 0.04, 0.74, 0.84), "dark_bg",      0.03,  94),
    ("43", "scratch/uv_lab/refs_57/43_KYR/ref_01.jpg",               (0.08, 0.00, 0.92, 0.99), "blue_sky",     0.03, 120),
    ("52", "scratch/uv_lab/refs_57/52_CON/ref_01.jpg",               (0.06, 0.00, 0.94, 0.98), "dark_bg_hair", 0.03,  90),
    ("58", "scratch/uv_lab/ref_gaps/58_MUG/c0.jpg",                  (0.06, 0.03, 0.94, 0.96), "white_bg",     0.03,  99),
    ("67", "scratch/uv_lab/refs_57/67_COR/ref_01.jpg",               (0.04, 0.03, 0.96, 0.99), "green_court",  0.03, 108),
    ("72", "scratch/uv_lab/refs_57/72_CHN/ref_02.jpg",               (0.02, 0.02, 0.98, 0.99), "white_bg",     0.03, 100),
]


def _detect_face_box(gray: np.ndarray):
    cascade_path = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
    clf = cv2.CascadeClassifier(cascade_path)
    h, w = gray.shape
    faces = clf.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=4, minSize=(int(w * 0.16), int(h * 0.16)))
    if len(faces) > 0:
        best = max(faces, key=lambda r: r[2] * r[3])
        return tuple(int(v) for v in best)
    return (int(w * 0.28), int(h * 0.14), int(w * 0.44), int(h * 0.42))


def segment_portrait(bgr: np.ndarray, bg_mode: str) -> Image.Image:
    h, w = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    fx, fy, fw, fh = _detect_face_box(gray)
    cx = fx + fw // 2

    mask = np.full((h, w), cv2.GC_PR_BGD, dtype=np.uint8)

    # Side margin background seeds; only seed top corners (leaving center crown intact!)
    m_x = max(5, int(w * 0.035))
    m_y = max(5, int(h * 0.025))
    mask[:, :m_x] = cv2.GC_BGD
    mask[:, w - m_x :] = cv2.GC_BGD
    mask[:m_y, : max(10, cx - int(fw * 0.55))] = cv2.GC_BGD
    mask[:m_y, min(w - 10, cx + int(fw * 0.55)) :] = cv2.GC_BGD

    b_c, g_c, r_c = [ch.astype(np.float32) for ch in cv2.split(bgr)]

    if bg_mode == "white_bg":
        maxc = np.maximum(np.maximum(r_c, g_c), b_c)
        minc = np.minimum(np.minimum(r_c, g_c), b_c)
        is_white = ((minc > 224) & ((maxc - minc) < 22)).astype(np.uint8)
        _, labels = cv2.connectedComponents(is_white, connectivity=4)
        border_labels = set(np.unique(np.concatenate([
            labels[0, :], labels[:, 0], labels[:, -1]
        ]))) - {0}
        if border_labels:
            mask[np.isin(labels, list(border_labels))] = cv2.GC_BGD
        mask[: int(h * 0.85), : max(12, int(fx - fw * 0.55))] = cv2.GC_BGD

    elif bg_mode == "green_wiki82":
        # Flood-fill all blurred tennis-court green connected to the borders + any dark green pocket near left neck!
        is_green = ((g_c > r_c + 8.0) & (g_c > b_c + 8.0) & (r_c < 145.0) & (b_c < 145.0)).astype(np.uint8)
        _, labels = cv2.connectedComponents(is_green, connectivity=4)
        border_labels = set(np.unique(np.concatenate([
            labels[0, :], labels[:, 0], labels[:, -1], labels[-1, :max(1, cx - int(fw * 0.7))]
        ]))) - {0}
        if border_labels:
            mask[np.isin(labels, list(border_labels))] = cv2.GC_BGD
        # Clean stray lower-left shoulder/neck court-green pocket
        lower_green = np.zeros((h, w), dtype=bool)
        lower_green[int(fy + fh * 0.65) :, : max(1, cx - int(fw * 0.05))] = True
        mask[lower_green & (g_c > r_c + 6.0) & (g_c > b_c + 8.0)] = cv2.GC_BGD
        # Seed bright white visor interior softly as probable foreground
        is_visor = (r_c > 190) & (g_c > 190) & (b_c > 190)
        visor_roi = np.zeros((h, w), dtype=bool)
        visor_roi[max(0, int(fy - fh * 0.65)) : max(1, int(fy + fh * 0.2)), max(0, cx - fw) : min(w, cx + fw)] = True
        mask[is_visor & visor_roi] = cv2.GC_PR_FGD

    elif bg_mode == "dark_bg_hair":
        # Protect warm bright blonde/brown crown highlights near very top center of head from dark background
        crown_roi = np.zeros((h, w), dtype=bool)
        crown_roi[: max(10, int(fy + fh * 0.25)), max(0, cx - int(fw * 0.55)) : min(w, cx + int(fw * 0.55))] = True
        warm_hair = (r_c > 95.0) & (g_c > 65.0)
        mask[crown_roi & warm_hair] = cv2.GC_FGD

    elif bg_mode == "blue_sky":
        # Flood-fill smooth blue sky connected to left/right/top borders
        is_sky = ((b_c > r_c + 18.0) & (b_c > 90.0)).astype(np.uint8)
        _, labels = cv2.connectedComponents(is_sky, connectivity=4)
        border_labels = set(np.unique(np.concatenate([
            labels[0, :], labels[:, 0], labels[:, -1]
        ]))) - {0}
        if border_labels:
            mask[np.isin(labels, list(border_labels))] = cv2.GC_BGD

    elif bg_mode == "green_court":
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        is_green = ((hsv[:, :, 0] >= 35) & (hsv[:, :, 0] <= 95) & (hsv[:, :, 1] >= 40) & (hsv[:, :, 2] <= 195))
        mask[is_green] = cv2.GC_PR_BGD
        mask[: max(10, int(fy + fh * 0.4)), : max(8, int(fx - fw * 0.45))] = cv2.GC_BGD
        mask[: max(10, int(fy + fh * 0.4)), min(w - 8, int(fx + fw * 1.45)) :] = cv2.GC_BGD

    # Core probable foreground generous vertically so hair crown & visor are never sliced
    pad_top = max(0, int(fy - fh * 0.78))
    pad_l = max(m_x + 2, int(fx - fw * 0.62))
    pad_r = min(w - m_x - 2, int(fx + fw * 1.62))
    mask[pad_top:h, pad_l:pad_r] = np.where(
        mask[pad_top:h, pad_l:pad_r] == cv2.GC_BGD,
        cv2.GC_BGD,
        cv2.GC_PR_FGD,
    )

    # Definite foreground: upper-head / forehead / face oval + neck + inner torso
    cv2.ellipse(
        mask,
        (cx, max(8, fy + int(fh * 0.36))),
        (max(8, int(fw * 0.32)), max(10, int(fh * 0.50))),
        0, 0, 360, int(cv2.GC_FGD), -1
    )
    # Safeguard definite BG pixels if flood-fill touched crown outer halo -> only force GC_FGD inside non-BGD
    neck_top = fy + int(fh * 0.80)
    cv2.rectangle(
        mask,
        (max(0, cx - int(fw * 0.26)), neck_top),
        (min(w, cx + int(fw * 0.26)), h - 1),
        int(cv2.GC_FGD), -1
    )
    chest_y = min(h - 1, fy + int(fh * 1.32))
    if chest_y < h - 8:
        sub = mask[chest_y:h, max(m_x + 4, cx - int(fw * 0.72)) : min(w - m_x - 4, cx + int(fw * 0.72))]
        sub[sub != cv2.GC_BGD] = cv2.GC_FGD

    bg_model = np.zeros((1, 65), np.float64)
    fg_model = np.zeros((1, 65), np.float64)
    cv2.grabCut(bgr, mask, None, bg_model, fg_model, 7, cv2.GC_INIT_WITH_MASK)

    fg = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)

    num_c, comp = cv2.connectedComponents(fg, connectivity=8)
    face_lbl = comp[min(h - 1, fy + fh // 2), min(w - 1, cx)]
    if face_lbl > 0:
        fg = np.where(comp == face_lbl, 255, 0).astype(np.uint8)
    elif num_c > 1:
        sizes = np.bincount(comp.ravel())
        sizes[0] = 0
        fg = np.where(comp == int(np.argmax(sizes)), 255, 0).astype(np.uint8)

    k3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, k3, iterations=1)
    if bg_mode in ("white_bg", "green_court", "green_wiki82"):
        fg = cv2.erode(fg, k3, iterations=1)
    alpha = cv2.GaussianBlur(fg, (3, 3), 0.75)
    alpha[alpha < 22] = 0
    alpha[alpha > 235] = 255

    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float32)
    if bg_mode == "white_bg":
        edge = (alpha > 0) & (alpha < 235)
        rgb[edge] = np.clip(rgb[edge] * 0.88, 0, 255)
    elif bg_mode in ("green_court", "green_wiki82"):
        edge = (alpha > 0) & (alpha < 235)
        g_excess = np.maximum(0.0, rgb[edge, 1] - np.maximum(rgb[edge, 0], rgb[edge, 2]))
        rgb[edge, 1] -= g_excess * 0.7

    rgba = np.dstack([np.clip(rgb, 0, 255).astype(np.uint8), alpha])
    return Image.fromarray(rgba, "RGBA")


def main():
    updated = []
    for pid, rel_src, (nx0, ny0, nx1, ny1), bg_mode, top_pad, eye_y_ovr in TARGETS:
        src_p = os.path.join(REPO_ROOT, rel_src)
        assert os.path.isfile(src_p), f"Missing source for {pid}: {src_p}"
        bgr_full = cv2.imread(src_p, cv2.IMREAD_COLOR)
        H, W = bgr_full.shape[:2]
        x0, y0, x1, y1 = int(W * nx0), int(H * ny0), int(W * nx1), int(H * ny1)
        bgr = bgr_full[y0:y1, x0:x1]

        cutout = segment_portrait(bgr, bg_mode)
        cutout = remove_small_alpha_islands(cutout, min_pixels=250)
        p256 = frame_portrait_256(cutout, (0, 0, cutout.width, cutout.height), top_pad)
        eye_y = eye_y_ovr if eye_y_ovr else estimate_eye_y_256(p256)
        eye = build_eye_strip(p256, eye_y)
        ps = build_photo_s(p256)

        write_bgra_dds(p256, os.path.join(REPO_ROOT, VR_DIR, "photo_L", f"{pid}.dds"))
        write_bgra_dds(eye, os.path.join(REPO_ROOT, VR_DIR, "photo_eye", f"{pid}.dds"))
        write_dxt5_dds(ps, os.path.join(REPO_ROOT, VR_DIR, "photo_S", f"{pid}.dds"))
        updated.append((pid, p256, eye, ps))
        print(f"[OK] {pid}: packed photo_L / photo_eye (eye_y={eye_y}) / photo_S from {os.path.basename(src_p)}")

    cols = 4
    rows = (len(updated) + cols - 1) // cols
    cw, ch = 264, 344
    sheet = Image.new("RGB", (cols * cw, rows * ch), (24, 26, 34))
    tile = Image.new("RGB", (256, 256))
    tpx = tile.load()
    for y in range(256):
        for x in range(256):
            tpx[x, y] = (58, 62, 74) if ((x // 16) + (y // 16)) % 2 == 0 else (90, 94, 108)
    dr = ImageDraw.Draw(sheet)
    for i, (pid, p256, eye, ps) in enumerate(updated):
        x0, y0 = (i % cols) * cw + 4, (i // cols) * ch + 4
        sheet.paste(tile, (x0, y0))
        sheet.paste(p256, (x0, y0), p256)
        sheet.paste(eye, (x0, y0 + 258))
        dr.rectangle([x0, y0, x0 + 76, y0 + 18], fill=(14, 16, 22))
        dr.text((x0 + 6, y0 + 3), f"ID {pid}", fill=(255, 228, 100))

    audit_path = os.path.join(REPO_ROOT, "scratch", "portraits_fix_2026.png")
    sheet.save(audit_path)

    pl_dir = os.path.join(REPO_ROOT, VR_DIR, "photo_L")
    uncut = []
    for fn in sorted(os.listdir(pl_dir)):
        if not fn.endswith(".dds"):
            continue
        im = Image.open(os.path.join(pl_dir, fn)).convert("RGBA")
        corners = [im.getpixel((3, 3))[3], im.getpixel((252, 3))[3]]
        if any(a > 64 for a in corners):
            uncut.append((fn, corners))
    print(f"Audit sheet: {audit_path}")
    print(f"Total photo_L files: {len([f for f in os.listdir(pl_dir) if f.endswith('.dds')])}, opaque_top_corners={uncut}")
    assert len(uncut) == 0, f"Found uncut portraits: {uncut}"


if __name__ == "__main__":
    main()
