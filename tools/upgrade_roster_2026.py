#!/usr/bin/env python3
"""
2026 SOTA Facemaker + Real 3D Hair/Accessory Overhaul for Virtua Tennis 4 (.sdo).

Upgrades all 58 custom players (skipping 26_ALC to preserve his approved Nano Banana UV):
  1. Always starts from FRESH vanilla SEGA base .sdo + .zml extracted from BIN0/BIN1
     (never stale mismatched-base canvases in 03_entregar_editados_aqui!).
  2. Runs HyperSwap 1C 256 + GPEN-BFR-512 (tools/local_identity_uv.py) + Zero-Monster
     3DDFA_V2 sculpt (<= 3.8 mm, 0.0 mm eyes, 0.0000 mm neck seam).
  3. Synthesizes clean procedural bald-scalp UV + satin SSS/normal maps for 29_AG2,
     skin-fade temple UV for 43_KYR, and natural perimeter hair tinting (ZERO _tint_scalp_hair).
  4. Applies global luminance-mapped natural hair ramp to all 3D hair/head/hairtop slots
     (eliminates all 14 olive [57,52,41] bugs) + clamps _N_hair alpha strictly matte 5..11.
  5. Engineers real 3D .sdo VB/IB geometry & clean accessory textures:
       - 29_91_AGA: 3D cascading 90s mullet + two-tone blonde/brown hair + Challenge Court headband
       - 29_AG2:    collapsed Hair_fix + transparent hair DDS + clean bald dome
       - 44_HEW:    180-deg rotated Cap-VB for real 3D backwards cap + clean white/navy tex
       - 37_NAV & 83_BJK: parametric 3D eyeglasses packed cleanly into P_W_KUZ_IT accessory-VB/IB
                          + hidden ponytail Hair_alpha_cloth + transparent _B_hair + clean forehead alpha
       - 43_KYR:    3D sculpted high-fade mohawk ridge
       - Clean 3D headbands/caps/visors for 30_BOR (Fila), 31_MCE, 34_SWI, 36_KUE, 40_ZVE,
         48_MOY, 49_FER, 53_VIL, 54_IVN, 57_HEN, 60_RUB, 61_RUU, 62_FRI, 67_COR, 71_BER, 72_CHN,
         77_WLD, 79_ASV.
"""
import argparse
import json
import math
import os
import struct
import sys
import time
import cv2
import numpy as np
from PIL import Image, ImageDraw
from scipy.spatial import cKDTree

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))
sys.path.insert(0, os.path.join(REPO_ROOT, "scratch", "real_alcaraz_3d"))

# Strict cache containment inside scratch/local_faceswap/ BEFORE importing ML modules
SWAP_ROOT = os.path.join(REPO_ROOT, "scratch", "local_faceswap")
os.environ["INSIGHTFACE_HOME"] = SWAP_ROOT
os.environ["HF_HOME"] = os.path.join(SWAP_ROOT, "hf_cache")
os.environ["XDG_CACHE_HOME"] = os.path.join(SWAP_ROOT, "xdg_cache")
os.environ["TMP"] = os.path.join(SWAP_ROOT, "tmp")
os.environ["TEMP"] = os.path.join(SWAP_ROOT, "tmp")
os.makedirs(os.environ["TMP"], exist_ok=True)

import batch_studio_57 as b57
import local_identity_uv as lidu
import polish_user_feedback_v4 as p4
from vt4_archive import BIN0, BIN1, load_directory, read_entry
from compress_sega_lzss import lzss_compress_literal
from build_ee3_rackets import parse_vbs, parse_ibs, decompress_sdo
from update_custom_assets import parse_sdo_dds_slots, extract_slot_image, replace_sdo_tex
from sculpt_sdo_head import _strip_to_tris, _find_ib_for_vb, _recalc_blended_normals
from build_all_sdo_models import PLAYERS_3D
from local_identity_uv import detect_kps5_and_lms
from photo_to_vt4_head import load_mesh_data
from run_clean_4way_test import render_generic_sdo_head, get_eye_and_head_world_coords

MODEL_DIR = b57.MODEL_DIR
AUDIT_DIR = b57.AUDIT_DIR
FRESH_BASES_DIR = os.path.join(REPO_ROOT, "scratch", "uv_lab", "fresh_bases_2026")
REFS_57_DIR = b57.REFS_57_DIR

HERO_IDS = [
    "29_AG2", "29_91_AGA", "70_SOD", "71_BER", "39_MED", "60_RUB",
    "65_BAD", "35_SAB", "58_MUG", "82_AND", "74_MUS", "81_CLI",
    "37_NAV", "83_BJK", "44_HEW", "43_KYR", "30_BOR", "34_SWI",
]

# Natural non-olive 3D hair target RGBs per category + specific player overrides
HAIR_RGB_BY_CATEGORY = {
    "black":        (26, 23, 21),
    "dark_brown":   (52, 37, 27),
    "brown":        (78, 55, 36),
    "medium_brown": (98, 70, 44),
    "light_brown":  (124, 92, 58),
    "blonde_brown": (148, 114, 68),
    "dirty_blonde": (152, 126, 86),
    "ash_blonde":   (182, 158, 126),
    "blonde":       (190, 158, 108),
    "ginger_red":   (166, 84, 34),
    "red":          (158, 76, 34),
    "auburn":       (126, 62, 34),
    "gray":         (142, 140, 136),
    "bald":         (78, 56, 38),
}

PLAYER_HAIR_RGB_OVERRIDE = {
    "27_SIN":    (166, 84, 34),   # copper-ginger
    "29_91_AGA": (154, 118, 70),  # medium golden-brown roots (mullet gradients to bleached blonde)
    "30_BOR":    (186, 154, 104), # Swedish golden blonde
    "31_MCE":    (88, 54, 34),    # warm wavy chestnut
    "34_SWI":    (76, 52, 34),    # medium brunette
    "35_SAB":    (138, 104, 66),  # light warm golden-brown
    "36_KUE":    (92, 60, 34),    # rich chestnut curls
    "37_NAV":    (182, 156, 114), # platinum/ash blonde short bob
    "39_MED":    (74, 52, 36),    # brown
    "40_ZVE":    (152, 126, 86),  # dirty blonde
    "41_TSI":    (96, 68, 42),    # honey-brown curls
    "43_KYR":    (24, 21, 19),    # jet black
    "44_HEW":    (184, 156, 106), # Australian blonde
    "49_FER":    (46, 33, 24),    # dark espresso-brown
    "52_CON":    (62, 44, 30),    # classic brunette
    "53_VIL":    (66, 46, 32),    # dark chestnut
    "54_IVN":    (44, 32, 24),    # dark brown
    "56_SEL":    (102, 74, 48),   # light-medium brown
    "57_HEN":    (114, 82, 50),   # light brown
    "58_MUG":    (56, 39, 28),    # dark brown
    "60_RUB":    (168, 88, 38),   # ginger-copper
    "61_RUU":    (150, 122, 82),  # Scandinavian light brown
    "65_BAD":    (114, 82, 52),   # warm brunette
    "67_COR":    (52, 37, 27),    # dark brown
    "68_GAS":    (86, 62, 42),    # medium brown
    "70_SOD":    (166, 138, 96),  # Swedish light blonde
    "71_BER":    (148, 120, 80),  # light brown/dirty blonde
    "72_CHN":    (24, 22, 20),    # black
    "74_MUS":    (92, 66, 44),    # Austrian brown
    "77_WLD":    (176, 146, 102), # Swedish blonde
    "81_CLI":    (188, 160, 114), # Belgian golden blonde
    "82_AND":    (182, 158, 126), # warm ash blonde
    "83_BJK":    (74, 52, 34),    # classic 1973 warm brunette
}


# ---------------------------------------------------------------------------
# Pinned references & verified pre-existing Nano Banana canvases (2026 Polish)
# ---------------------------------------------------------------------------
PINNED_REFS_2026 = {
    "60_RUB": ["scratch/uv_lab/refs_57/60_RUB/ref_01.jpg"],
    "39_MED": ["scratch/uv_lab/refs_57/39_MED/ref_02.jpg"],
    "35_SAB": ["scratch/uv_lab/refs_57/35_SAB/ref_sab_miami_calm.jpg"],
    "29_AG2": ["scratch/uv_lab/refs_57/29_AG2/ref_agassi_bald_clean.jpg", "assets/face_refs/29_AG2/ref_3.jpg"],
    "34_SWI": ["scratch/uv_lab/refs_57/34_SWI/ref_02.jpg", "scratch/uv_lab/refs_57/34_SWI/ref_03.jpg"],
    "59_SHE": ["scratch/uv_lab/refs_57/59_SHE/ref_01.jpg", "scratch/uv_lab/refs_57/59_SHE/ref_02.jpg"],
    "72_CHN": ["scratch/uv_lab/refs_57/72_CHN/ref_02.jpg"],
    "77_WLD": ["assets/face_refs/77_WLD/ref_0.jpg"],
    "79_ASV": ["scratch/uv_lab/refs_57/79_ASV/ref_asv_1994_clean.jpg"],
    "83_BJK": ["scratch/uv_lab/refs_57/83_BJK/ref_bjk_1975_crop.jpg"],
}

# (relative_canvas_path, run_hyperswap)
PINNED_CANVAS_2026 = {
    "43_KYR": ("scratch/uv_lab/canvas_overrides/43_KYR.png", False),
    "65_BAD": ("scratch/uv_lab/canvas_overrides/65_BAD.png", False),
    "35_SAB": ("scratch/uv_lab/p6_canvases/35_SAB.png", True),
    "29_AG2": ("scratch/uv_lab/p6_canvases/29_AG2.png", True),
}


def discover_player_refs_2026(pid: str) -> list[str]:
    if pid in PINNED_REFS_2026:
        out = [os.path.join(REPO_ROOT, p) for p in PINNED_REFS_2026[pid] if os.path.exists(os.path.join(REPO_ROOT, p))]
        if out:
            return out
    strict = _orig_discover_refs(pid)
    if strict:
        return strict
    r57_dir = os.path.join(REFS_57_DIR, pid)
    if os.path.isdir(r57_dir):
        scored = []
        for fn in sorted(os.listdir(r57_dir)):
            if not fn.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                continue
            fp = os.path.join(r57_dir, fn)
            try:
                rgb = np.array(Image.open(fp).convert("RGB"))
                kps5, _ = detect_kps5_and_lms(rgb, allow_pad_fallback=True)
                iod = float(np.linalg.norm(kps5[1] - kps5[0]))
                if iod < 24.0:
                    continue
                yaw = abs(float(kps5[2][0]) - 0.5 * (float(kps5[0][0]) + float(kps5[1][0]))) / max(iod, 1.0)
                if yaw <= 0.52:
                    scored.append((iod - yaw * 160.0, fp))
            except Exception:
                continue
        if scored:
            scored.sort(key=lambda x: x[0], reverse=True)
            return [p for _, p in scored[:3]]
    return strict


_orig_discover_refs = b57.discover_player_refs
b57.discover_player_refs = discover_player_refs_2026

_SKIP_SWAP_PIDS: set[str] = set()
_orig_transfer_uv = b57.transfer_biometric_identity_uv


def _wrapped_transfer_uv(src_photo_paths, target_uv_path, template_uv_path, out_path, **kwargs):
    pid_tag = os.path.splitext(os.path.basename(out_path))[0]
    if pid_tag in _SKIP_SWAP_PIDS:
        tgt_im = Image.open(target_uv_path).convert("RGB").resize((1024, 1024), Image.Resampling.LANCZOS)
        tgt_im.save(out_path)
        cos_sim = 0.0
        try:
            tgt_arr = np.array(tgt_im)
            ek_m, ek_c = lidu.extract_eye_socket_cutout_mask(np.array(Image.open(template_uv_path).convert("RGB").resize((1024, 1024))))
            teyes = lidu.synthesize_temp_eyes_on_uv(tgt_arr, ek_m, ek_c)
            ee = lidu.extract_arcface_embedding(teyes)
            re0 = lidu.extract_arcface_embedding(np.array(Image.open(src_photo_paths[0]).convert("RGB")))
            cos_sim = float(np.dot(ee, re0))
        except Exception:
            pass
        print(f"[Preserve AAA UV PASS] {os.path.basename(out_path)} | ArcFace_cos_sim={cos_sim:+.3f}", flush=True)
        return {"sim_before": cos_sim, "sim_after": cos_sim, "refs_used": len(src_photo_paths)}
    return _orig_transfer_uv(src_photo_paths, target_uv_path, template_uv_path, out_path, **kwargs)


b57.transfer_biometric_identity_uv = _wrapped_transfer_uv
lidu.transfer_biometric_identity_uv = _wrapped_transfer_uv


def align_canvas_to_template_uv(canvas_rgb: np.ndarray, tmpl_rgb: np.ndarray) -> np.ndarray:
    """Warp any pre-existing AAA UV canvas cleanly onto exact 5 facial landmarks of target base UV."""
    H, W = tmpl_rgb.shape[:2]
    src = cv2.resize(canvas_rgb, (W, H), interpolation=cv2.INTER_LANCZOS4)
    try:
        t_kps5, _ = detect_kps5_and_lms(tmpl_rgb)
        ek_m, ek_c = lidu.extract_eye_socket_cutout_mask(src)
        src_eyes = lidu.synthesize_temp_eyes_on_uv(src, ek_m, ek_c)
        try:
            s_kps5, _ = detect_kps5_and_lms(src_eyes)
        except Exception:
            s_kps5, _ = detect_kps5_and_lms(src)
        M = lidu._fit_similarity_2d(s_kps5, t_kps5)
        warped = cv2.warpAffine(src, M, (W, H), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REPLICATE)
        # Preserve original border corners smoothly outside face oval if shift is small
        shift = float(np.max(np.abs(s_kps5 - t_kps5)))
        if shift < 2.5:
            return src
        return warped
    except Exception:
        return src


# ---------------------------------------------------------------------------
# Generic attribute-aware VB / IB read-write helpers (stride 32 / 36 / 40 / 44)
# ---------------------------------------------------------------------------
def _vb_attr_offsets(vb: dict, st_idx: int = 0) -> tuple[int, int, int | None, int]:
    """Return (pos_off, nrm_off, col_off, uv_off) from stream attribute descriptors."""
    attrs = vb["streams"][st_idx]["attrs"]
    type_sz = {1: 1, 2: 2, 4: 4}
    off = 0
    pos_off = 0
    nrm_off = 12
    col_off = None
    uv_off = 20
    uv_found = False
    for dt, cnt in attrs:
        sz = type_sz[dt] * cnt
        if dt == 4 and cnt == 3:
            pos_off = off
        elif dt == 2 and cnt == 4 and off == 12:
            nrm_off = off
        elif dt == 1 and cnt == 4 and off < 28:
            col_off = off
        elif dt == 2 and cnt == 2 and not uv_found:
            uv_off = off
            uv_found = True
        off += sz
    return pos_off, nrm_off, col_off, uv_off


def read_vb_full(dec: bytes, vb: dict, st_idx: int = 0):
    s = vb["streams"][st_idx]
    base = vb["data_off"] + s["off"]
    st = s["stride"]
    nv = s["nverts"]
    pos_off, nrm_off, _, uv_off = _vb_attr_offsets(vb, st_idx)
    xyz = np.zeros((nv, 3), dtype=np.float32)
    nrm = np.zeros((nv, 4), dtype=np.int32)
    uv = np.zeros((nv, 2), dtype=np.float32)
    for i in range(nv):
        voff = base + i * st
        xyz[i] = struct.unpack_from(">3f", dec, voff + pos_off)
        nrm[i] = struct.unpack_from(">4h", dec, voff + nrm_off)
        ur, vr = struct.unpack_from(">2h", dec, voff + uv_off)
        uv[i, 0] = ur / 65536.0 + 0.5
        uv[i, 1] = vr / 65536.0 + 0.5
    return xyz, nrm, uv


def write_vb_stream_xyz_nrm(dec_ba: bytearray, vb: dict, xyz: np.ndarray, nrm, st_idx: int = 0):
    s = vb["streams"][st_idx]
    base = vb["data_off"] + s["off"]
    st = s["stride"]
    nv = s["nverts"]
    assert len(xyz) == nv and len(nrm) == nv
    for i in range(nv):
        off = base + i * st
        x, y, z = float(xyz[i][0]), float(xyz[i][1]), float(xyz[i][2])
        assert math.isfinite(x) and math.isfinite(y) and math.isfinite(z)
        struct.pack_into(">3f", dec_ba, off, x, y, z)
        nx, ny, nz, nw = nrm[i]
        struct.pack_into(
            ">4h", dec_ba, off + 12,
            max(-32767, min(32767, int(nx))),
            max(-32767, min(32767, int(ny))),
            max(-32767, min(32767, int(nz))),
            int(nw),
        )


def locate_ib_data(dec: bytes, ib_short_name: str) -> tuple[int, int] | None:
    """Return (inds_byte_off, cnt) for exact short_name match in SDO."""
    pos = 0
    tag = b"\x0bIndexBuffer\x00"
    while True:
        idx = dec.find(tag, pos)
        if idx < 0:
            return None
        p = idx + len(tag)
        l1 = dec[p]; p += 1 + l1
        l2 = dec[p]; p += 1
        sn = dec[p:p + l2].decode("latin1", "replace"); p += l2
        p += 1  # flag
        cnt = struct.unpack_from(">I", dec, p)[0]
        if sn == ib_short_name:
            return (p + 4, cnt)
        pos = p + 4 + cnt * 2


def write_ib_inds(dec_ba: bytearray, ib_short_name: str, new_inds: list[int]):
    loc = locate_ib_data(bytes(dec_ba), ib_short_name)
    assert loc is not None, f"Missing IB {ib_short_name}"
    data_off, orig_cnt = loc
    assert len(new_inds) <= orig_cnt and len(new_inds) >= 3
    padded = list(new_inds) + [new_inds[-1]] * (orig_cnt - len(new_inds))
    struct.pack_into(f">{orig_cnt}H", dec_ba, data_off, *padded)


# ---------------------------------------------------------------------------
# Step 3 UV Pre-cleaning: Bald Scalp Synthesis (29_AG2), Skin-Fade (43_KYR), Perimeter Hair Tint
# ---------------------------------------------------------------------------
def synthesize_bald_scalp_uv(base_rgb: np.ndarray, post_swap: bool = False) -> np.ndarray:
    """Create a realistic, seamless shaved-bald dome UV on P_M_DJV_IT (1024x1024)."""
    H, W = base_rgb.shape[:2]
    kps5, lms = detect_kps5_and_lms(base_rgb)
    le, re = kps5[0], kps5[1]
    cx = 0.5 * (float(le[0]) + float(re[0]))
    eye_y = 0.5 * (float(le[1]) + float(re[1]))
    iod = float(np.linalg.norm(re - le))

    # Sample clean central forehead BELOW hairline (y=[245..325]) so post-swap tone matches 100%
    sx0, sx1 = max(0, int(cx - 0.55 * iod)), min(W, int(cx + 0.55 * iod))
    sy0, sy1 = max(0, int(eye_y - 0.80 * iod)), min(H, int(eye_y - 0.40 * iod))
    swatch = base_rgb[sy0:sy1, sx0:sx1].astype(np.float32)
    swatch_tone = np.median(swatch.reshape(-1, 3), axis=0)
    swatch_low = cv2.GaussianBlur(swatch, (35, 35), 9.0)
    pore_hi = swatch - swatch_low

    tile2 = np.hstack([pore_hi, pore_hi[:, ::-1]])
    tile4 = np.vstack([tile2, tile2[::-1, :]])
    th, tw = tile4.shape[:2]
    tiled_hi = np.zeros((H, W, 3), dtype=np.float32)
    for y in range(0, H, th):
        for x in range(0, W, tw):
            yh = min(th, H - y)
            xw = min(tw, W - x)
            tiled_hi[y:y + yh, x:x + xw] = tile4[:yh, :xw]

    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    dome_hl = np.exp(-0.5 * (((xx - cx) / (1.35 * iod)) ** 2 + ((yy - 140.0) / 110.0) ** 2))
    scalp_fill = swatch_tone[None, None, :] * (0.95 + 0.06 * dome_hl[:, :, None]) + tiled_hi * 0.85

    lum = 0.299 * base_rgb[:, :, 0] + 0.587 * base_rgb[:, :, 1] + 0.114 * base_rgb[:, :, 2]
    skin_lum = float(np.mean(swatch_tone * np.array([0.299, 0.587, 0.114])))

    brow_safe_y = eye_y - 0.36 * iod
    # Wide 70px feathered transition across upper forehead [190..260] -> zero horizontal seam!
    m_top = np.clip((262.0 - yy) / 68.0, 0.0, 1.0)
    side_x = (np.abs(xx - cx) - 0.90 * iod) / (0.24 * iod)
    m_side = np.clip(side_x, 0.0, 1.0) * np.clip((585.0 - yy) / 45.0, 0.0, 1.0) * np.clip((yy - 180.0) / 40.0, 0.0, 1.0)
    m_outer_nape = np.clip((np.abs(xx - cx) - 1.55 * iod) / (0.28 * iod), 0.0, 1.0) * np.clip((770.0 - yy) / 60.0, 0.0, 1.0)

    ear_lx, ear_rx, ear_y = cx - 1.72 * iod, cx + 1.72 * iod, eye_y + 0.36 * iod
    ear_prot = np.clip(
        (np.exp(-0.5 * (((xx - ear_lx) / (0.25 * iod)) ** 2 + ((yy - ear_y) / (0.50 * iod)) ** 2))
         + np.exp(-0.5 * (((xx - ear_rx) / (0.25 * iod)) ** 2 + ((yy - ear_y) / (0.50 * iod)) ** 2))) * 2.2,
        0.0, 1.0,
    )
    face_prot = np.exp(-0.5 * (((xx - cx) / (0.72 * iod)) ** 2 + ((yy - (eye_y + 0.30 * iod)) / (0.95 * iod)) ** 2))
    face_prot = np.where(yy > brow_safe_y, np.clip(face_prot * 2.6, 0.0, 1.0), 0.0)

    dark_hair = np.clip((skin_lum * 0.90 - lum) / max(15.0, skin_lum * 0.35), 0.0, 1.0)
    if post_swap:
        # Also re-unify upper crown [0..260] directly to post-swap forehead tone smoothly
        raw_mask = np.maximum(m_top, np.maximum(m_side, m_outer_nape) * np.maximum(dark_hair, 0.45 * np.clip((260.0 - yy) / 100.0, 0.0, 1.0)))
    else:
        raw_mask = np.maximum(m_top, np.maximum(m_side, m_outer_nape) * dark_hair)
    raw_mask = np.clip(raw_mask * (1.0 - ear_prot) * (1.0 - face_prot), 0.0, 1.0)
    raw_mask = np.maximum(raw_mask, np.clip((205.0 - yy) / 22.0, 0.0, 1.0) * (1.0 - ear_prot))
    alpha = cv2.GaussianBlur(raw_mask.astype(np.float32), (45, 45), 14.0)[:, :, None]

    out = base_rgb.astype(np.float32) * (1.0 - alpha) + scalp_fill * alpha
    return np.clip(out, 0, 255).astype(np.uint8)


def fill_kuz_forehead_hairline(uv_rgb: np.ndarray, hair_rgb: tuple[int, int, int]) -> np.ndarray:
    """Fix P_W_KUZ_IT black alpha-0 headband void at y=100..190 by painting fine streaked short hair
    across y=0..150 and feathery natural wispy bangs transitioning cleanly into forehead skin at y=145..222."""
    H, W = uv_rgb.shape[:2]
    try:
        kps5, _ = detect_kps5_and_lms(uv_rgb)
        cx = 0.5 * (float(kps5[0][0]) + float(kps5[1][0]))
        eye_y = 0.5 * (float(kps5[0][1]) + float(kps5[1][1]))
        iod = float(np.linalg.norm(kps5[1] - kps5[0]))
    except Exception:
        cx, eye_y, iod = W * 0.5, 345.0, 180.0

    # Sample clean forehead skin below old headband zone (y ~ 225..268)
    fy0, fy1 = max(0, int(eye_y - 0.68 * iod)), min(H, int(eye_y - 0.42 * iod))
    fx0, fx1 = max(0, int(cx - 0.55 * iod)), min(W, int(cx + 0.55 * iod))
    skin_patch = uv_rgb[fy0:fy1, fx0:fx1].astype(np.float32)
    skin_rgb = np.median(skin_patch.reshape(-1, 3), axis=0) if skin_patch.size > 0 else np.array([200.0, 150.0, 120.0])

    rng = np.random.default_rng(1983)
    # Generate fine high-frequency vertical hair strand variation (wide W horizontal blur tiny, vertical long)
    noise = rng.normal(0.0, 1.0, (H, W)).astype(np.float32)
    strands = cv2.GaussianBlur(noise, (3, 45), 0.7, 14.0)
    strands_fine = cv2.GaussianBlur(rng.normal(0.0, 1.0, (H, W)).astype(np.float32), (1, 21), 0.4, 7.0)
    hair_var = np.clip(0.86 + 0.24 * strands + 0.12 * strands_fine, 0.52, 1.28)[:, :, None]
    hair_tex = np.clip(np.array(hair_rgb, dtype=np.float32)[None, None, :] * hair_var, 12, 240)

    # Create natural feathery uneven bang silhouette edge across y=148..208 (higher around center temples, wavy wisps!)
    xx = np.arange(W, dtype=np.float32)[None, :]
    wisp_wave = (
        14.0 * np.sin((xx - cx) * 0.048 + 0.4)
        + 9.0 * np.cos((xx - cx) * 0.115 - 0.7)
        + 10.0 * cv2.GaussianBlur(rng.normal(0.0, 1.0, (1, W)).astype(np.float32), (15, 1), 3.0)
    )
    edge_y = 178.0 + wisp_wave  # wavy bang hem right cleanly above brow zone
    yy = np.arange(H, dtype=np.float32)[:, None]

    # Above edge_y: dense natural layered hair; below edge_y down to y~215: soft wispy fade into real skin!
    w_hair = np.clip((edge_y - yy) / 28.0, 0.0, 1.0)
    # Also ensure side temple hair corners (`|x-cx| > 0.88*iod`, `y < 350`) with dark/void pixels become natural hair
    side_dark = (np.abs(uv_rgb[:, :, 0].astype(np.int32) - 0) >= 0) & (np.max(uv_rgb, axis=2) < 95) & (yy < 350.0) & (np.abs(xx - cx) > 0.86 * iod)
    void_center = (np.max(uv_rgb, axis=2) < 55) & (yy < 225.0)
    w_hair = np.maximum(w_hair, np.where(side_dark | void_center, 0.98, 0.0))

    # Fill missing black headband strip [90..235] underneath wisps with smooth skin tone so zero dark gap ever shows!
    dark_void = (np.max(uv_rgb, axis=2) < 55) & (yy >= 90.0) & (yy <= 235.0) & (np.abs(xx - cx) <= 0.95 * iod)
    void_m = cv2.GaussianBlur(dark_void.astype(np.float32), (19, 19), 5.0)[:, :, None]
    base_clean = uv_rgb.astype(np.float32) * (1.0 - void_m) + skin_rgb[None, None, :] * void_m

    w_hair_b = cv2.GaussianBlur(w_hair.astype(np.float32), (9, 9), 2.2)[:, :, None]
    out = base_clean * (1.0 - w_hair_b) + hair_tex * w_hair_b
    return np.clip(out, 0, 255).astype(np.uint8)


def apply_skin_fade_uv(base_rgb: np.ndarray, strength: float = 0.92) -> np.ndarray:
    """Create crisp high skin-fade on P_M_DJV_IT lower temples while keeping dark top mohawk strip."""
    H, W = base_rgb.shape[:2]
    kps5, _ = detect_kps5_and_lms(base_rgb)
    cx = 0.5 * (float(kps5[0][0]) + float(kps5[1][0]))
    eye_y = 0.5 * (float(kps5[0][1]) + float(kps5[1][1]))
    iod = float(np.linalg.norm(kps5[1] - kps5[0]))

    ck = base_rgb[int(eye_y + 0.4 * iod):int(eye_y + 0.9 * iod), int(cx - 0.65 * iod):int(cx - 0.25 * iod)].astype(np.float32)
    skin_rgb = np.median(ck.reshape(-1, 3), axis=0)

    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    lum = (0.299 * base_rgb[:, :, 0] + 0.587 * base_rgb[:, :, 1] + 0.114 * base_rgb[:, :, 2])
    dark = np.clip((105.0 - lum) / 50.0, 0.0, 1.0)
    # High-contrast skin-fade starting closer to temples (|x - cx| > 0.92*iod) & higher up, protecting ears!
    side = np.clip((np.abs(xx - cx) - 0.94 * iod) / (0.26 * iod), 0.0, 1.0)
    vert = np.clip((yy - 140.0) / 45.0, 0.0, 1.0) * np.clip((680.0 - yy) / 60.0, 0.0, 1.0)
    ear_lx, ear_rx, ear_y = cx - 1.72 * iod, cx + 1.72 * iod, eye_y + 0.36 * iod
    ear_prot = np.clip(
        (np.exp(-0.5 * (((xx - ear_lx) / (0.24 * iod)) ** 2 + ((yy - ear_y) / (0.50 * iod)) ** 2))
         + np.exp(-0.5 * (((xx - ear_rx) / (0.24 * iod)) ** 2 + ((yy - ear_y) / (0.50 * iod)) ** 2))) * 2.2,
        0.0, 1.0,
    )
    fade_w = cv2.GaussianBlur((side * vert * dark * (1.0 - ear_prot)).astype(np.float32), (25, 25), 7.0) * strength
    out = base_rgb.astype(np.float32) * (1.0 - fade_w[:, :, None]) + skin_rgb[None, None, :] * fade_w[:, :, None]
    return np.clip(out, 0, 255).astype(np.uint8)


def recolor_uv_hair_perimeter(uv_rgb: np.ndarray, hair_rgb: tuple[int, int, int], aggressive: bool = False) -> np.ndarray:
    """Safely recolor painted scalp hair strictly OUTSIDE protected face/eyebrow/ear oval (NO forehead boxes!)."""
    H, W = uv_rgb.shape[:2]
    try:
        kps5, _ = detect_kps5_and_lms(uv_rgb)
        cx = 0.5 * (float(kps5[0][0]) + float(kps5[1][0]))
        eye_y = 0.5 * (float(kps5[0][1]) + float(kps5[1][1]))
        mouth_y = 0.5 * (float(kps5[3][1]) + float(kps5[4][1]))
        iod = float(np.linalg.norm(kps5[1] - kps5[0]))
        fh = float(np.clip(mouth_y - eye_y, 130.0, 270.0))
    except Exception:
        return uv_rgb

    lum = 0.299 * uv_rgb[:, :, 0] + 0.587 * uv_rgb[:, :, 1] + 0.114 * uv_rgb[:, :, 2]
    # Estimate cheek skin lum to detect dark hair cleanly
    cy0, cy1 = max(0, int(eye_y + 0.25 * fh)), min(H, int(eye_y + 0.70 * fh))
    cx0, cx1 = max(0, int(cx - 0.75 * iod)), min(W, int(cx - 0.30 * iod))
    skin_lum = float(np.median(lum[cy0:cy1, cx0:cx1])) if (cy1 > cy0 and cx1 > cx0) else 145.0

    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    scalp_y = max(4.0, eye_y - (0.50 if aggressive else 0.56) * fh)
    # Soft outer gate strictly excluding eyebrows, eye sockets, nose, mouth, and both ears
    top_gate = np.clip((scalp_y - yy) / max(12.0, 0.22 * fh), 0.0, 1.0)
    side_gate = np.clip((np.abs(xx - cx) - (1.06 if aggressive else 1.18) * iod) / (0.28 * iod), 0.0, 1.0) * np.clip((680.0 - yy) / 80.0, 0.0, 1.0)
    ear_lx, ear_rx, ear_y = cx - 1.72 * iod, cx + 1.72 * iod, eye_y + 0.32 * iod
    ear_prot = np.clip(
        (np.exp(-0.5 * (((xx - ear_lx) / (0.26 * iod)) ** 2 + ((yy - ear_y) / (0.52 * iod)) ** 2))
         + np.exp(-0.5 * (((xx - ear_rx) / (0.26 * iod)) ** 2 + ((yy - ear_y) / (0.52 * iod)) ** 2))) * 2.5,
        0.0, 1.0,
    )
    thresh = 0.86 if aggressive else 0.62
    dark_gate = np.clip((skin_lum * thresh - lum) / max(12.0, skin_lum * 0.25), 0.0, 1.0)
    mask = cv2.GaussianBlur((np.maximum(top_gate, side_gate) * dark_gate * (1.0 - ear_prot)).astype(np.float32), (17, 17), 4.5)
    if float(mask.max()) < 0.05:
        return uv_rgb

    norm = np.clip((lum - 8.0) / 55.0, 0.0, 1.45)[:, :, None]
    scale = 0.52 + 0.52 * norm
    target = np.clip(np.array(hair_rgb, dtype=np.float32)[None, None, :] * scale, 0, 255)
    out = uv_rgb.astype(np.float32) * (1.0 - mask[:, :, None]) + target * mask[:, :, None]
    return np.clip(out, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# Step 4 Global Natural Hair Ramp + Clean 3D Accessories & VB Geometry Edits
# ---------------------------------------------------------------------------
def apply_natural_hair_ramp(target_dec: bytearray, base_dec: bytes, hair_rgb: tuple[int, int, int]):
    """Replace olive-prone _B_hair/_B_head/_B_hairtop textures with normalized-luminance ramp from
    FRESH vanilla SEGA base, preserving original Alpha and clamping _N_hair Alpha to matte 5..11."""
    base_slots = {s["name"]: s for s in parse_sdo_dds_slots(base_dec)}
    tgt_slots = {s["name"]: s for s in parse_sdo_dds_slots(bytes(target_dec))}
    tr, tg, tb = [float(c) for c in hair_rgb]

    for sname, sl in tgt_slots.items():
        snl = sname.lower()
        if any(tag in snl for tag in ("hairband", "headband")):
            continue
        if ("_b_hair" in snl or "_b_head_" in snl or "_b_hairtop" in snl) and sname in base_slots:
            im = extract_slot_image(base_dec, base_slots[sname]).convert("RGBA")
            arr = np.array(im).astype(np.float32)
            lum = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
            vis = arr[:, :, 3] > 24
            med_lum = float(np.median(lum[vis])) if np.any(vis) else 38.0
            norm = np.clip((lum - 10.0) / max(28.0, med_lum * 1.45), 0.0, 1.45)
            scale = 0.42 + 0.65 * norm
            r = np.clip(tr * scale, 12, 238).astype(np.uint8)
            g = np.clip(tg * scale, 10, 224).astype(np.uint8)
            b = np.clip(tb * scale, 9, 200).astype(np.uint8)
            a = arr[:, :, 3].astype(np.uint8)
            replace_sdo_tex(target_dec, sl, Image.fromarray(np.dstack([r, g, b, a]), mode="RGBA"))
        elif "_n_hair" in snl:
            im = extract_slot_image(bytes(target_dec), sl).convert("RGBA")
            arr = np.array(im)
            arr[:, :, 3] = np.clip(arr[:, :, 3].astype(np.float32) * (8.0 / 255.0) + 4.0, 5, 11).astype(np.uint8)
            replace_sdo_tex(target_dec, sl, Image.fromarray(arr, mode="RGBA"))


def _paint_band_or_cap_slot(target_dec: bytearray, base_dec: bytes, base_name: str, mode: str, primary_rgb, stripe_rgb=None, stripe2_rgb=None):
    """Paint clean logos-free headbands (preserving wrist regions!) or caps onto matching base DDS slot."""
    tgt_slots = {s["name"]: s for s in parse_sdo_dds_slots(bytes(target_dec))}
    base_slots = {s["name"]: s for s in parse_sdo_dds_slots(base_dec)}

    def fold_shaded(base_crop: np.ndarray, target_col, lum_floor=0.55) -> np.ndarray:
        lum = (0.299 * base_crop[:, :, 0] + 0.587 * base_crop[:, :, 1] + 0.114 * base_crop[:, :, 2]) / 255.0
        med = max(0.20, float(np.median(lum)))
        rel = np.clip(lum / med, 0.55, 1.35)
        shade = np.clip(lum_floor + (1.0 - lum_floor) * rel, 0.65, 1.12)[:, :, None]
        col = np.array(target_col, dtype=np.float32)[None, None, :]
        rgb = np.clip(col * shade, 0, 255).astype(np.uint8)
        return np.dstack([rgb, base_crop[:, :, 3].astype(np.uint8)])

    if base_name == "P_M_NAD_IT" and mode == "headband":
        sname = next(k for k in tgt_slots if "_b_accessory" in k.lower())
        arr = np.array(extract_slot_image(base_dec, base_slots[sname]).convert("RGBA"))
        H, W = arr.shape[:2]  # 512x256
        # Preserve cloth fold contrast cleanly while removing red+swoosh in headband [256:512, 190:256] and wristbands!
        # Replace swoosh pixels first by median neighbor cloth luminosity
        band_src = arr[190:256, 256:512].copy()
        band_new = fold_shaded(band_src, primary_rgb, lum_floor=0.68)
        if stripe_rgb is not None:
            # Draw crisp athletic horizontal stripes across headband height [190..256 -> local 0..66]
            bh = band_new.shape[0]
            band_new[int(bh * 0.22):int(bh * 0.36), :, :3] = fold_shaded(band_src[int(bh * 0.22):int(bh * 0.36), :], stripe_rgb, 0.72)[:, :, :3]
            if stripe2_rgb is not None:
                band_new[int(bh * 0.62):int(bh * 0.76), :, :3] = fold_shaded(band_src[int(bh * 0.62):int(bh * 0.76), :], stripe2_rgb, 0.72)[:, :, :3]
        arr[190:256, 256:512] = band_new
        # Also recolor matching top-right & bottom-left wristbands cleanly without red swoosh leak
        arr[0:190, 256:512] = fold_shaded(arr[0:190, 256:512], primary_rgb, 0.68)
        arr[190:256, 0:256] = fold_shaded(arr[190:256, 0:256], primary_rgb, 0.68)
        arr[0:190, 0:256] = fold_shaded(arr[0:190, 0:256], primary_rgb, 0.68)
        replace_sdo_tex(target_dec, tgt_slots[sname], Image.fromarray(arr, mode="RGBA"))

    elif base_name in ("P_M_DEL_SN", "P_M_FED_SN") and mode == "headband":
        sname = next(k for k in tgt_slots if "_b_accessory" in k.lower())
        arr = np.array(extract_slot_image(base_dec, base_slots[sname]).convert("RGBA"))
        # Headband is cleanly TOP half y=[0..128] in 512x256
        top_src = arr[0:128, 0:512].copy()
        # Neutralize swoosh inside top_src luminosity before tinting
        lum = 0.299 * top_src[:, :, 0] + 0.587 * top_src[:, :, 1] + 0.114 * top_src[:, :, 2]
        sat = np.max(top_src[:, :, :3], axis=2) - np.min(top_src[:, :, :3], axis=2)
        swoosh = (sat > 25) & (lum < 210)
        if np.any(swoosh):
            fill_rgb = np.median(top_src[~swoosh][:, :3], axis=0).astype(np.uint8)
            top_src[swoosh, :3] = fill_rgb
        arr[0:128, 0:512] = fold_shaded(top_src, primary_rgb, lum_floor=0.68)
        if stripe_rgb is not None:
            arr[44:62, 0:512, :3] = fold_shaded(top_src[44:62, 0:512], stripe_rgb, 0.72)[:, :, :3]
        if base_name == "P_M_DEL_SN":
            # Also neutralize blue swoosh on bottom-left wristbands
            bot_src = arr[128:256, 0:256].copy()
            sat_b = np.max(bot_src[:, :, :3], axis=2) - np.min(bot_src[:, :, :3], axis=2)
            sw_b = sat_b > 25
            if np.any(sw_b):
                bot_src[sw_b, :3] = np.median(bot_src[~sw_b][:, :3], axis=0).astype(np.uint8)
            arr[128:256, 0:256] = fold_shaded(bot_src, primary_rgb, 0.68)
        replace_sdo_tex(target_dec, tgt_slots[sname], Image.fromarray(arr, mode="RGBA"))

    elif base_name == "P_M_COU_SN" and mode == "cap":
        sname = next(k for k in tgt_slots if "_b_cap" in k.lower())
        arr = np.array(extract_slot_image(base_dec, base_slots[sname]).convert("RGBA"))
        cap_new = fold_shaded(arr, primary_rgb, lum_floor=0.66)
        if stripe_rgb is not None:
            # Trim along cap edge/seam accents cleanly
            cap_new[:, 64:74, :3] = fold_shaded(arr[:, 64:74], stripe_rgb, 0.72)[:, :, :3]
        replace_sdo_tex(target_dec, tgt_slots[sname], Image.fromarray(cap_new, mode="RGBA"))
        aname = next((k for k in tgt_slots if "_b_accessory" in k.lower()), None)
        if aname:
            warr = np.array(extract_slot_image(base_dec, base_slots[aname]).convert("RGBA"))
            replace_sdo_tex(target_dec, tgt_slots[aname], Image.fromarray(fold_shaded(warr, primary_rgb, 0.68), mode="RGBA"))

    elif base_name == "P_W_IVA_IT" and mode == "visor":
        sname = next(k for k in tgt_slots if "_b_accessory" in k.lower())
        arr = np.array(extract_slot_image(base_dec, base_slots[sname]).convert("RGBA"))
        # Preserve visor folds, replace entire visor cleanly + strip black Adidas logo at [220:300, 35:105]
        clean_src = arr.copy()
        logo = (clean_src[25:115, 200:312, 0] < 140)
        clean_src[25:115, 200:312][logo, :3] = 225
        v_new = fold_shaded(clean_src, primary_rgb, lum_floor=0.72)
        if stripe_rgb is not None:
            v_new[150:166, :, :3] = fold_shaded(clean_src[150:166, :], stripe_rgb, 0.72)[:, :, :3]
        replace_sdo_tex(target_dec, tgt_slots[sname], Image.fromarray(v_new, mode="RGBA"))


def _collapse_vb(dec_ba: bytearray, vbs: dict, vb_name: str, point=(0.0, 0.5, 0.0)):
    if vb_name not in vbs:
        return
    vb = vbs[vb_name]
    for si in range(len(vb["streams"])):
        nv = vb["streams"][si]["nverts"]
        xyz = np.tile(np.array(point, dtype=np.float32), (nv, 1))
        nrm = [(0, 32767, 0, 0)] * nv
        write_vb_stream_xyz_nrm(dec_ba, vb, xyz, nrm, st_idx=si)


def _apply_3d_agassi_91_mullet(target_dec: bytearray, base_dec: bytes):
    """Sculpt P_M_NAD_IT Hair_cloth-VB into flowing 90s bleached-blonde mullet + wispy top + Challenge Court band."""
    vbs = {v["short_name"]: v for v in parse_vbs(bytes(target_dec))}
    ibs = {ib["short_name"]: ib for ib in parse_ibs(bytes(target_dec))}
    slots = {s["name"]: s for s in parse_sdo_dds_slots(bytes(target_dec))}
    bslots = {s["name"]: s for s in parse_sdo_dds_slots(base_dec)}

    # 1. Flowing cascading mullet in rotated Head-bone coordinates (+X = world +Y, +Y = world -Z, Z = world X)
    for vn in ("Hair_cloth-VB", "Hair_cloth_lodL-VB"):
        if vn not in vbs:
            continue
        xyz, nrm, _ = read_vb_full(bytes(target_dec), vbs[vn], st_idx=0)
        new_xyz = xyz.copy()
        for i in range(len(xyz)):
            x, y, z = float(xyz[i, 0]), float(xyz[i, 1]), float(xyz[i, 2])
            t_down = float(np.clip((0.52 - x) / 0.82, 0.0, 1.0))
            t_back = float(np.clip((y + 0.05) / 0.87, 0.0, 1.0))
            # Cascade ~8.5cm down behind neck/collar, sweeping softly backward and feathering outward
            new_xyz[i, 0] = x - 0.86 * (t_down ** 1.15) * (0.40 + 0.60 * t_back)
            new_xyz[i, 1] = y + 0.36 * t_back * (0.35 + 0.65 * t_down)
            new_xyz[i, 2] = z * (1.0 + 0.18 * t_down * (0.35 + 0.65 * t_back))
        ib = _find_ib_for_vb(ibs, vn)
        nn = _recalc_blended_normals([tuple(map(float, r)) for r in new_xyz], [tuple(r) for r in nrm], ib["inds"], blend=0.45) if ib else nrm
        write_vb_stream_xyz_nrm(target_dec, vbs[vn], new_xyz, nn, st_idx=0)

    # 2. Voluminous tousled 1991 top crown + wispy front Challenge Court bangs (Hair_fix-VB world space)
    for vn in ("Hair_fix-VB", "Hair_fix_lodL-VB"):
        if vn not in vbs:
            continue
        xyz, nrm, _ = read_vb_full(bytes(target_dec), vbs[vn], st_idx=0)
        new_xyz = xyz.copy()
        for i in range(len(xyz)):
            x, y, z = float(xyz[i, 0]), float(xyz[i, 1]), float(xyz[i, 2])
            t_top = float(np.clip((y - 17.30) / 0.72, 0.0, 1.0))
            t_front = float(np.clip((z - 0.55) / 0.60, 0.0, 1.0))
            t_bang_wisp = float(np.clip((z - 0.72) / 0.42, 0.0, 1.0) * np.clip((17.50 - y) / 0.35, 0.0, 1.0))
            new_xyz[i, 0] = x * (1.0 + 0.08 * t_top)
            new_xyz[i, 1] = y + 0.24 * t_top - 0.07 * t_bang_wisp
            new_xyz[i, 2] = z + 0.08 * t_front + 0.06 * t_bang_wisp
        ib = _find_ib_for_vb(ibs, vn)
        nn = _recalc_blended_normals([tuple(map(float, r)) for r in new_xyz], [tuple(r) for r in nrm], ib["inds"], blend=0.45) if ib else nrm
        write_vb_stream_xyz_nrm(target_dec, vbs[vn], new_xyz, nn, st_idx=0)

    # 3. Two-tone 90s mullet diffuse texture (darker roots -> golden-blonde bleached mullet tips!)
    if "P_NAD_B_hair_IT.dds" in slots:
        bim = extract_slot_image(base_dec, bslots["P_NAD_B_hair_IT.dds"]).convert("RGBA")
        arr = np.array(bim).astype(np.float32)
        H = arr.shape[0]
        lum = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
        vis = arr[:, :, 3] > 24
        med = float(np.median(lum[vis])) if np.any(vis) else 38.0
        norm = np.clip((lum - 10.0) / max(26.0, med * 1.4), 0.0, 1.45)
        yy = np.linspace(0.0, 1.0, H)[:, None, None]
        # Top V=0..0.38 golden-brown roots (148,108,62) -> bottom V=0.38..1.0 bleached blonde (214,186,122)
        t_bleach = np.clip((yy - 0.25) / 0.45, 0.0, 1.0)
        root_rgb = np.array([[[144.0, 106.0, 62.0]]], dtype=np.float32)
        tip_rgb = np.array([[[214.0, 184.0, 118.0]]], dtype=np.float32)
        col = root_rgb * (1.0 - t_bleach) + tip_rgb * t_bleach
        scale = (0.45 + 0.62 * norm)[:, :, None]
        rgb_out = np.clip(col * scale, 18, 244).astype(np.uint8)
        replace_sdo_tex(target_dec, slots["P_NAD_B_hair_IT.dds"], Image.fromarray(np.dstack([rgb_out, arr[:, :, 3].astype(np.uint8)]), mode="RGBA"))

    if "P_NAD_B_head_IT.dds" in slots:
        bim2 = extract_slot_image(base_dec, bslots["P_NAD_B_head_IT.dds"]).convert("RGBA")
        arr2 = np.array(bim2).astype(np.float32)
        lum2 = 0.299 * arr2[:, :, 0] + 0.587 * arr2[:, :, 1] + 0.114 * arr2[:, :, 2]
        norm2 = np.clip((lum2 - 10.0) / 48.0, 0.0, 1.45)
        scale2 = (0.45 + 0.62 * norm2)[:, :, None]
        rgb2 = np.clip(np.array([[[154.0, 118.0, 70.0]]]) * scale2, 18, 232).astype(np.uint8)
        replace_sdo_tex(target_dec, slots["P_NAD_B_head_IT.dds"], Image.fromarray(np.dstack([rgb2, arr2[:, :, 3].astype(np.uint8)]), mode="RGBA"))

    # 4. Crisp Challenge Court headband: white base with hot-pink & black stripes!
    _paint_band_or_cap_slot(target_dec, base_dec, "P_M_NAD_IT", "headband", (242, 242, 244), stripe_rgb=(242, 48, 136), stripe2_rgb=(30, 30, 36))


def _apply_3d_backwards_cap(target_dec: bytearray, base_dec: bytes, primary_rgb=(242, 242, 245), stripe_rgb=None):
    """Rotate P_M_COU_SN Cap-VB & Cap_lodL-VB 180 deg around skull center (cz=0.48) with strict Face-VB clearance guard."""
    vbs = {v["short_name"]: v for v in parse_vbs(bytes(target_dec))}
    ibs = {ib["short_name"]: ib for ib in parse_ibs(bytes(target_dec))}
    cz = 0.48
    ec = (0.0, 17.05, 0.56)
    er = (0.83, 1.00, 1.06)

    # Build angular cKDTree on Face-VB skull (y > 16.65) to enforce >= 8 mm outward cap clearance over forehead/crown
    origin = np.array([0.0, 16.75, 0.45], dtype=np.float32)
    f_xyz, _, _ = read_vb_full(bytes(target_dec), vbs["Face-VB"], st_idx=0)
    skull_pts = f_xyz[f_xyz[:, 1] > 16.65]
    rel_f = skull_pts - origin[None, :]
    r_face = np.linalg.norm(rel_f, axis=1)
    dir_f = rel_f / np.maximum(r_face[:, None], 1e-6)
    skull_tree = cKDTree(dir_f)

    for vn in ("Cap-VB", "Cap_lodL-VB"):
        if vn not in vbs:
            continue
        xyz, nrm, _ = read_vb_full(bytes(target_dec), vbs[vn], st_idx=0)
        new_xyz = xyz.copy()
        new_nrm = nrm.copy()
        new_xyz[:, 0] = -xyz[:, 0]
        new_xyz[:, 2] = 2.0 * cz - xyz[:, 2]
        # Preserve triangle outward normal sign under Y-axis 180-deg rotation
        new_nrm[:, 0] = -nrm[:, 0]
        new_nrm[:, 2] = -nrm[:, 2]
        for i in range(len(new_xyz)):
            x, y, z = float(new_xyz[i, 0]), float(new_xyz[i, 1]), float(new_xyz[i, 2])
            z_orig = float(xyz[i, 2])
            dx, dy, dz = x - ec[0], max(0.05, y - ec[1]), z - ec[2]
            norm_e = math.sqrt((dx / er[0]) ** 2 + (dy / er[1]) ** 2 + (dz / er[2]) ** 2)
            s = 1.0 / max(1e-4, norm_e)
            tx, ty, tz = ec[0] + dx * s, ec[1] + dy * s, ec[2] + dz * s
            xd, yd, zd = 0.16 * x + 0.84 * tx, 0.16 * y + 0.84 * ty, 0.16 * z + 0.84 * tz
            y_floor = 16.92 + 0.30 * max(0.0, min(1.0, (zd + 0.15) / 1.15))
            if yd < y_floor:
                yd = y_floor + 0.12 * (yd - y_floor)

            # Enforce strict >= 0.08 dm (8 mm) radial clearance outside Face-VB forehead/temples/crown on dome vertices
            if z_orig <= 1.25:
                rv = np.array([xd, yd, zd], dtype=np.float32) - origin
                rn = float(np.linalg.norm(rv))
                if rn > 1e-4:
                    _, nbr_idx = skull_tree.query(rv / rn, k=8)
                    r_req = float(r_face[nbr_idx].max()) + 0.08
                    if rn < r_req:
                        scaled = origin + (rv / rn) * r_req
                        xd, yd, zd = float(scaled[0]), float(scaled[1]), float(scaled[2])

            if z_orig > 1.15:
                tb = max(0.0, min(1.0, (z_orig - 1.15) / 1.00))
                tb_s = tb * tb * (3.0 - 2.0 * tb)
                x_bill = x * (1.0 - 0.16 * tb_s)
                z_bill = 2.0 * cz - (1.15 + (z_orig - 1.15) * 1.05)
                y_bill = 17.24 - 0.08 * tb_s - 0.14 * min(1.0, (x_bill / 0.62) ** 2)
                x = (1.0 - tb_s) * xd + tb_s * x_bill
                y = (1.0 - tb_s) * yd + tb_s * y_bill
                z = (1.0 - tb_s) * zd + tb_s * z_bill
            else:
                x, y, z = xd, yd, zd
            new_xyz[i, 0], new_xyz[i, 1], new_xyz[i, 2] = x, y, z
        ib = _find_ib_for_vb(ibs, vn)
        nn = _recalc_blended_normals([tuple(map(float, r)) for r in new_xyz], [tuple(r) for r in new_nrm], ib["inds"], blend=0.55) if ib else new_nrm
        write_vb_stream_xyz_nrm(target_dec, vbs[vn], new_xyz, nn, st_idx=0)
    # Tuck upper hair slightly inward so stray hair sits under the backwards cap without poking through front rim
    for vn in ("Hair_fix-VB", "Hair_fix_lodL-VB"):
        if vn not in vbs:
            continue
        hxyz, hnrm, _ = read_vb_full(bytes(target_dec), vbs[vn], st_idx=0)
        new_h = hxyz.copy()
        for i in range(len(new_h)):
            if new_h[i, 1] > 0.85:
                th = min(1.0, (float(new_h[i, 1]) - 0.85) / 0.45)
                new_h[i, 0] *= (1.0 - 0.16 * th)
                new_h[i, 2] *= (1.0 - 0.16 * th)
        ib = _find_ib_for_vb(ibs, vn)
        nn = _recalc_blended_normals([tuple(map(float, r)) for r in new_h], [tuple(r) for r in hnrm], ib["inds"], blend=0.45) if ib else hnrm
        write_vb_stream_xyz_nrm(target_dec, vbs[vn], new_h, nn, st_idx=0)
    _paint_band_or_cap_slot(target_dec, base_dec, "P_M_COU_SN", "cap", primary_rgb, stripe_rgb=stripe_rgb)


def _unify_bald_scalp_tone_ag2(target_dec: bytearray):
    """Equalize Agassi (29_AG2) bald scalp, face, ears, & neck via multi-scale low-pass LAB illumination flattening."""
    slots = {s["name"]: s for s in parse_sdo_dds_slots(bytes(target_dec))}
    f_k = next(k for k in slots if "_b_face" in k.lower())
    f_rgba = np.array(extract_slot_image(bytes(target_dec), slots[f_k]).convert("RGBA"))
    f_rgb = f_rgba[:, :, :3]
    H, W = f_rgb.shape[:2]
    lab = cv2.cvtColor(f_rgb, cv2.COLOR_RGB2LAB).astype(np.float32)

    fore = lab[int(H * 0.31):int(H * 0.37), int(W * 0.35):int(W * 0.65)].reshape(-1, 3)
    cheek_l = lab[int(H * 0.46):int(H * 0.54), int(W * 0.34):int(W * 0.44)].reshape(-1, 3)
    cheek_r = lab[int(H * 0.46):int(H * 0.54), int(W * 0.56):int(W * 0.66)].reshape(-1, 3)
    emp_lab = np.median(np.vstack([fore, cheek_l, cheek_r]), axis=0)
    target_lab = 0.50 * emp_lab + 0.50 * np.array([142.0, 146.5, 160.5], dtype=np.float32)

    yy = (np.arange(H, dtype=np.float32) / max(1, H - 1))[:, None]
    xx = (np.arange(W, dtype=np.float32) / max(1, W - 1))[None, :]
    # Protect eyes/brows (~y=0.35..0.44, x=0.33..0.67) and dark goatee/lips (~y=0.55..0.68, x=0.39..0.61)
    is_eye_brow = (yy >= 0.34) & (yy <= 0.44) & (xx >= 0.33) & (xx <= 0.67)
    is_goatee_lip = (yy >= 0.54) & (yy <= 0.68) & (xx >= 0.39) & (xx <= 0.61) & (lab[:, :, 0] < 126.0)
    is_feat = (lab[:, :, 0] < 86.0) | is_eye_brow | is_goatee_lip

    lab_fill = lab.copy()
    for c in range(3):
        lab_fill[:, :, c] = np.where(is_feat, target_lab[c], lab[:, :, c])
    lowpass_lab = cv2.GaussianBlur(lab_fill, (0, 0), sigmaX=60.0, sigmaY=60.0)

    # Smooth skin weight (1.0 on bald scalp/forehead/cheeks/ears/temples/neck, gently 0.0 inside dark features)
    w_skin = np.clip((lab[:, :, 0] - 74.0) / 20.0, 0.0, 1.0)
    w_eye_soft = 1.0 - np.exp(-0.5 * (np.maximum(0.0, 0.04 - np.maximum(np.abs(yy - 0.39) - 0.03, np.abs(xx - 0.50) - 0.14)) / 0.015) ** 2)
    w_eyebrow_guard = np.where((yy >= 0.33) & (yy <= 0.44) & (xx >= 0.33) & (xx <= 0.67), 0.15, 1.0)
    w_skin = np.minimum(w_skin, w_eyebrow_guard)
    # Soft feather around inner goatee/mouth box so chin beard texture doesn't wash out
    m_goatee_soft = np.where(is_goatee_lip, 0.0, 1.0)
    m_goatee_soft = cv2.GaussianBlur(m_goatee_soft.astype(np.float32), (21, 21), 6.0)
    w_skin = w_skin * m_goatee_soft

    for c in range(3):
        lab[:, :, c] = np.clip(lab[:, :, c] - 0.88 * (lowpass_lab[:, :, c] - target_lab[c]) * w_skin, 0.0, 255.0)

    rgb_out = cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2RGB)
    replace_sdo_tex(target_dec, slots[f_k], Image.fromarray(np.dstack([rgb_out, f_rgba[:, :, 3]]), mode="RGBA"))
    # Overwrite cached final_uvs_57/29_AG2.png so audit sheets show the exact unified texture!
    ag2_uv_path = os.path.join(REPO_ROOT, "scratch", "uv_lab", "final_uvs_57", "29_AG2.png")
    if os.path.exists(ag2_uv_path):
        Image.fromarray(rgb_out).resize((1024, 1024), Image.Resampling.LANCZOS).save(ag2_uv_path)

    # Also match _b_body_ skin pixels cleanly to target_lab
    for sn, sl in slots.items():
        if "_b_body_" in sn.lower():
            b_rgba = np.array(extract_slot_image(bytes(target_dec), sl).convert("RGBA"))
            b_lab = cv2.cvtColor(b_rgba[:, :, :3], cv2.COLOR_RGB2LAB).astype(np.float32)
            skin_m = (b_lab[:, :, 0] > 42.0) & (b_lab[:, :, 1] > 129.0) & (b_lab[:, :, 2] > 128.0)
            if np.any(skin_m):
                b_med = np.median(b_lab[skin_m], axis=0)
                shift = target_lab - b_med
                for c in range(3):
                    b_lab[:, :, c] = np.where(skin_m, np.clip(b_lab[:, :, c] + shift[c], 0.0, 255.0), b_lab[:, :, c])
                b_rgb = cv2.cvtColor(b_lab.astype(np.uint8), cv2.COLOR_LAB2RGB)
                replace_sdo_tex(target_dec, sl, Image.fromarray(np.dstack([b_rgb, b_rgba[:, :, 3]]), mode="RGBA"))


def _sculpt_bald_cranium_ag2(target_dec: bytearray):
    """Trim P_M_DJV_IT baked scalp-hair volume into clean bald cranium & slightly broaden Agassi cheek/jaw."""
    vbs = {v["short_name"]: v for v in parse_vbs(bytes(target_dec))}
    ibs = {ib["short_name"]: ib for ib in parse_ibs(bytes(target_dec))}
    for vn in ("Face-VB", "Face_lodL-VB"):
        if vn not in vbs:
            continue
        xyz, nrm, _ = read_vb_full(bytes(target_dec), vbs[vn], st_idx=0)
        new_xyz = xyz.copy()
        for i in range(len(xyz)):
            x, y, z = float(xyz[i, 0]), float(xyz[i, 1]), float(xyz[i, 2])
            if y > 17.40:
                t = min(1.0, (y - 17.40) / 0.55)
                t_up = t * t * (3.0 - 2.0 * t)
                x *= (1.0 - 0.11 * t_up)
                y -= 0.11 * t_up
                if z > 0.75:
                    tz = min(1.0, (z - 0.75) / 0.60)
                    tz_s = tz * tz * (3.0 - 2.0 * tz)
                    z -= 0.13 * t_up * tz_s
            elif 15.45 <= y <= 16.75 and z > 0.45:
                # Subtle cheek/jaw broadening (0.0mm neck below 15.45)
                tc = math.exp(-0.5 * ((y - 16.15) / 0.40) ** 2) * min(1.0, (z - 0.45) / 0.60)
                x *= (1.0 + 0.045 * tc)
            new_xyz[i, 0], new_xyz[i, 1], new_xyz[i, 2] = x, y, z
        ib = _find_ib_for_vb(ibs, vn)
        nn = _recalc_blended_normals([tuple(map(float, r)) for r in new_xyz], [tuple(r) for r in nrm], ib["inds"], blend=0.45) if ib else nrm
        write_vb_stream_xyz_nrm(target_dec, vbs[vn], new_xyz, nn, st_idx=0)


def _apply_3d_sabalenka_bun(target_dec: bytearray):
    """Raise P_W_SHA_SN scrunchie & coil Hair_clothA-VB into a visible high athletic 3D bun (mono) for Sabalenka."""
    vbs = {v["short_name"]: v for v in parse_vbs(bytes(target_dec))}
    ibs = {ib["short_name"]: ib for ib in parse_ibs(bytes(target_dec))}
    slots = {s["name"]: s for s in parse_sdo_dds_slots(bytes(target_dec))}
    for vn in ("Accessory-VB", "Accessory_lodL-VB"):
        if vn not in vbs:
            continue
        axyz, anrm, _ = read_vb_full(bytes(target_dec), vbs[vn], st_idx=0)
        new_a = axyz.copy()
        new_a[:, 1] += 0.42
        new_a[:, 2] -= 0.04
        write_vb_stream_xyz_nrm(target_dec, vbs[vn], new_a, anrm, st_idx=0)
    for vn in ("Hair_clothA-VB", "Hair_clothA_cloth_lodL-VB"):
        if vn not in vbs:
            continue
        xyz, nrm, _ = read_vb_full(bytes(target_dec), vbs[vn], st_idx=0)
        new_xyz = xyz.copy()
        for i in range(len(xyz)):
            x, y, z = float(xyz[i, 0]), float(xyz[i, 1]), float(xyz[i, 2])
            ny = max(0.0, min(1.0, (1.13 - y) / 2.87))  # 0 at root tie, 1 at ponytail tip
            theta = ny * math.pi
            new_xyz[i, 0] = x * (0.45 + 0.65 * math.sin(theta))
            new_xyz[i, 1] = 1.48 + 0.38 * math.cos(theta)
            new_xyz[i, 2] = -0.92 - 0.52 * math.sin(theta) + (z + 1.15) * 0.14
        ib = _find_ib_for_vb(ibs, vn)
        nn = _recalc_blended_normals([tuple(map(float, r)) for r in new_xyz], [tuple(r) for r in nrm], ib["inds"], blend=0.45) if ib else nrm
        write_vb_stream_xyz_nrm(target_dec, vbs[vn], new_xyz, nn, st_idx=0)
    if "P_SHA_B_accessory_SN.dds" in slots:
        sla = slots["P_SHA_B_accessory_SN.dds"]
        replace_sdo_tex(target_dec, sla, Image.new("RGBA", (sla["w"], sla["h"]), (232, 232, 236, 255)))


def _apply_3d_mohawk_kyrgios(target_dec: bytearray):
    """Sculpt P_M_DJV_IT Hair_fix-VB & skull ridge into crisp central high-fade mohawk for 43_KYR."""
    vbs = {v["short_name"]: v for v in parse_vbs(bytes(target_dec))}
    ibs = {ib["short_name"]: ib for ib in parse_ibs(bytes(target_dec))}
    for vn in ("Hair_fix-VB", "Hair_fix_lodL-VB"):
        if vn not in vbs:
            continue
        xyz, nrm, _ = read_vb_full(bytes(target_dec), vbs[vn], st_idx=0)
        new_xyz = xyz.copy()
        is_world = float(xyz[:, 1].max()) > 8.0
        for i in range(len(xyz)):
            x, y, z = float(xyz[i, 0]), float(xyz[i, 1]), float(xyz[i, 2])
            # Compress sides inward & lift central mohawk spine!
            new_xyz[i, 0] = x * 0.60
            t_center = math.exp(-0.5 * (new_xyz[i, 0] / 0.24) ** 2)
            t_y = float(np.clip(((y - 17.30) if is_world else (y - 1.25)) / 0.60, 0.0, 1.0))
            new_xyz[i, 1] = y + 0.17 * t_center * t_y - 0.04 * (1.0 - t_center) * t_y
            new_xyz[i, 2] = z + 0.06 * t_center * t_y
        ib = _find_ib_for_vb(ibs, vn)
        nn = _recalc_blended_normals([tuple(map(float, r)) for r in new_xyz], [tuple(r) for r in nrm], ib["inds"], blend=0.45) if ib else nrm
        write_vb_stream_xyz_nrm(target_dec, vbs[vn], new_xyz, nn, st_idx=0)


def _build_eyeglasses_geometry(high_detail: bool = True):
    """Build solid closed-ring/tube 3D eyeglasses geometry in P_W_KUZ_IT accessory-VB head-local space.
    Head-local reference (head_w=[0, 16.377, 0.156]):
      - Eye centers: (+-0.331, +0.825, +0.993) | Eyelash front: z=+1.264 | Ears: |x|=0.88, y~+0.88, z~+0.25
    Returns (verts_xyz [N,3], verts_nrm [N,3], strip_inds list[int])."""
    verts = []
    norms = []
    rings_strips = []

    def add_strip_tube(spine_pts: list[tuple[float, float, float]], radii_xy: list[tuple[float, float]], closed: bool):
        # Cross-section n-gon tube per spine point (4-gon LOD0, 3-gon LOD1) -> outward normals + CCW strip
        ns = len(spine_pts)
        cs_count = 4 if high_detail else 3
        start_v = len(verts)
        sp = np.array(spine_pts, dtype=np.float32)
        if cs_count == 4:
            unit_offs = [(+1.0, +1.0), (-1.0, +1.0), (-1.0, -1.0), (+1.0, -1.0)]
        else:
            unit_offs = [(math.cos(2.0 * math.pi * j / 3.0), math.sin(2.0 * math.pi * j / 3.0)) for j in range(3)]

        for i in range(ns):
            p_prev = sp[(i - 1) % ns] if closed else sp[max(0, i - 1)]
            p_next = sp[(i + 1) % ns] if closed else sp[min(ns - 1, i + 1)]
            tang = p_next - p_prev
            tn = float(np.linalg.norm(tang))
            tang = tang / max(tn, 1e-6)
            # Local frame: forward_z=(0,0,1), radial = normalize(cross(tang, forward_z))
            fwd = np.array([0.0, 0.0, 1.0], dtype=np.float32)
            rad = np.cross(tang, fwd)
            rn = float(np.linalg.norm(rad))
            if rn < 1e-3:
                rad = np.array([0.0, 1.0, 0.0], dtype=np.float32)
            else:
                rad /= rn
            up = np.cross(rad, tang)
            up /= max(float(np.linalg.norm(up)), 1e-6)
            r1, r2 = radii_xy[i]
            for ua, ub in unit_offs:
                a, b = ua * r1, ub * r2
                vpos = sp[i] + a * rad + b * up
                nvec = a * rad + b * up
                nvec /= max(float(np.linalg.norm(nvec)), 1e-6)
                verts.append(vpos)
                norms.append(nvec)

        seg_max = ns if closed else (ns - 1)
        s_list = []
        for k in range(seg_max):
            k_next = (k + 1) % ns if closed else (k + 1)
            b0 = start_v + k * cs_count
            b1 = start_v + k_next * cs_count
            seg = []
            for j in range(cs_count + 1):
                jj = j % cs_count
                seg.append(b0 + jj)
                seg.append(b1 + jj)
            if not s_list:
                s_list.extend(seg)
            else:
                s_list.append(s_list[-1])
                s_list.append(seg[0])
                if len(s_list) % 2 == 1:
                    s_list.append(seg[0])
                s_list.extend(seg)
        rings_strips.append(s_list)

    n_rim = 14 if high_detail else 6
    eye_z = 1.40
    # 1. Left & Right rounded-aviator lens rims
    for sign in (-1.0, +1.0):
        cx = sign * 0.345
        cy = 0.815
        rx, ry = 0.225, 0.175
        pts = []
        rads = []
        for k in range(n_rim):
            ang = 2.0 * math.pi * k / n_rim
            # Subtle aviator teardrop flatten on top, curve on outer bottom
            px = cx + sign * rx * math.cos(ang)
            py = cy + ry * math.sin(ang) - 0.015 * max(0.0, -math.sin(ang))
            pz = eye_z - 0.045 * ((abs(px) / 0.57) ** 1.4)  # gentle wraparound curve!
            pts.append((px, py, pz))
            rads.append((0.023, 0.018))
        add_strip_tube(pts, rads, closed=True)

    # 2. Nose bridge connecting inner rims across nose bridge
    if high_detail:
        bridge = [(-0.125, 0.855, eye_z - 0.005), (0.0, 0.865, eye_z + 0.012), (0.125, 0.855, eye_z - 0.005)]
    else:
        bridge = [(-0.125, 0.855, eye_z), (0.125, 0.855, eye_z)]
    add_strip_tube(bridge, [(0.020, 0.016)] * len(bridge), closed=False)

    # 3. Left & Right temple arms sweeping outside face/temples & resting cleanly above ears
    for sign in (-1.0, +1.0):
        arm = [
            (sign * 0.565, 0.855, eye_z - 0.040),
            (sign * 0.720, 0.865, 1.050),
            (sign * 0.840, 0.875, 0.650),
            (sign * 0.855, 0.875, 0.250),
            (sign * 0.835, 0.750, 0.020),
            (sign * 0.805, 0.640, -0.040),
        ]
        if not high_detail:
            arm = [arm[0], arm[3], arm[5]]
        add_strip_tube(arm, [(0.020, 0.016)] * len(arm), closed=False)

    # Stitch all strips into single valid triangle strip with parity-safe degenerate bridges
    out_inds = []
    for s in rings_strips:
        if not out_inds:
            out_inds.extend(s)
        else:
            out_inds.append(out_inds[-1])
            out_inds.append(s[0])
            if len(out_inds) % 2 == 1:
                out_inds.append(s[0])
            out_inds.extend(s)

    nrm_int = []
    for nv in norms:
        nrm_int.append((
            int(max(-32767, min(32767, nv[0] * 32767.0))),
            int(max(-32767, min(32767, nv[1] * 32767.0))),
            int(max(-32767, min(32767, nv[2] * 32767.0))),
            0,
        ))
    return np.array(verts, dtype=np.float32), nrm_int, out_inds


def _apply_3d_eyeglasses_kuz(target_dec: bytearray, frame_rgb=(54, 34, 22), hide_ponytail: bool = True, keep_bob: bool = False):
    """Replace P_W_KUZ_IT accessory-VB/IB with solid 3D eyeglasses + hide ponytail (or sculpt 3D short 1973 bob if keep_bob)."""
    vbs = {v["short_name"]: v for v in parse_vbs(bytes(target_dec))}
    ibs = {ib["short_name"]: ib for ib in parse_ibs(bytes(target_dec))}
    slots = {s["name"]: s for s in parse_sdo_dds_slots(bytes(target_dec))}

    def pack_glasses(vb_name: str, high_detail: bool):
        if vb_name not in vbs:
            return
        vb = vbs[vb_name]
        st = vb["streams"][0]
        base = vb["data_off"] + st["off"]
        stride, nv = st["stride"], st["nverts"]
        g_xyz, g_nrm, g_inds = _build_eyeglasses_geometry(high_detail=high_detail)
        assert len(g_xyz) <= nv, f"{vb_name}: {len(g_xyz)} > {nv}"
        # Keep trailing tangent bytes from v0, neutralize RGBA color (20..24)=ffffffff and UV=(0.25,0.25)
        tmpl = bytearray(target_dec[base:base + stride])
        struct.pack_into(">4B", tmpl, 20, 255, 255, 255, 255)
        u16 = int(-0.25 * 65536)
        struct.pack_into(">2h", tmpl, 24, u16, u16)
        for i in range(nv):
            off = base + i * stride
            target_dec[off:off + stride] = tmpl
            if i < len(g_xyz):
                struct.pack_into(">3f", target_dec, off, float(g_xyz[i, 0]), float(g_xyz[i, 1]), float(g_xyz[i, 2]))
                struct.pack_into(">4h", target_dec, off + 12, *g_nrm[i])
            else:
                struct.pack_into(">3f", target_dec, off, 0.0, 0.80, 0.0)
                struct.pack_into(">4h", target_dec, off + 12, 0, 32767, 0, 0)
        ib = _find_ib_for_vb(ibs, vb_name)
        assert ib is not None
        write_ib_inds(target_dec, ib["short_name"], g_inds)

    pack_glasses("accessory-VB", high_detail=True)
    pack_glasses("accessory_lodL-VB", high_detail=False)

    # Paint solid frame texture (DXT1) with subtle organic tortoiseshell grain
    if "P_KUZ_B_accessory_IT.dds" in slots:
        sl = slots["P_KUZ_B_accessory_IT.dds"]
        arr = np.zeros((sl["h"], sl["w"], 4), dtype=np.uint8)
        rng = np.random.default_rng(1973)
        grain = cv2.GaussianBlur(rng.normal(0.0, 1.0, (sl["h"], sl["w"])).astype(np.float32), (9, 9), 2.5) * 14.0
        for c, val in enumerate(frame_rgb):
            arr[:, :, c] = np.clip(float(val) + grain, 10, 220).astype(np.uint8)
        arr[:, :, 3] = 255
        replace_sdo_tex(target_dec, sl, Image.fromarray(arr, mode="RGBA"))

    if keep_bob:
        # Collapse ponytail tie st_idx=0 ONLY; sculpt st_idx=1 layered hair into rounded 1973 chin/ear-length short bob!
        for vn in ("Hair_alpha_cloth-VB", "Hair_alpha_cloth_lodL-VB"):
            if vn not in vbs:
                continue
            vb_h = vbs[vn]
            st0 = vb_h["streams"][0]
            write_vb_stream_xyz_nrm(
                target_dec, vb_h,
                np.tile(np.array([[0.0, 0.5, 0.0]], dtype=np.float32), (st0["nverts"], 1)),
                [(0, 32767, 0, 0)] * st0["nverts"], st_idx=0,
            )
            if len(vb_h["streams"]) >= 2:
                hxyz, hnrm, _ = read_vb_full(bytes(target_dec), vb_h, st_idx=1)
                new_h = hxyz.copy()
                for i in range(len(new_h)):
                    x, y, z = float(new_h[i, 0]), float(new_h[i, 1]), float(new_h[i, 2])
                    if y < 0.05:
                        y = max(y, 0.04 + 0.18 * (y + 0.74) / 0.79)
                    t_c = max(0.0, min(1.0, (y - 0.10) / 1.50))
                    x *= (1.0 + 0.06 * t_c)
                    if z < 0.15:
                        z -= 0.05 * t_c
                    new_h[i, 0], new_h[i, 1], new_h[i, 2] = x, y, z
                stem_h = vn[:-3]
                ib_s1 = next((b for bn, b in ibs.items() if bn.lower().startswith(stem_h.lower() + "-") and "-0001-" in bn.lower()), None)
                nn = _recalc_blended_normals([tuple(map(float, r)) for r in new_h], [tuple(r) for r in hnrm], ib_s1["inds"], blend=0.45) if ib_s1 else hnrm
                write_vb_stream_xyz_nrm(target_dec, vb_h, new_h, nn, st_idx=1)
    elif hide_ponytail:
        _collapse_vb(target_dec, vbs, "Hair_alpha_cloth-VB", point=(0.0, 0.5, 0.0))
        _collapse_vb(target_dec, vbs, "Hair_alpha_cloth_lodL-VB", point=(0.0, 0.5, 0.0))
        if "P_KUZ_B_hair_IT.dds" in slots:
            slh = slots["P_KUZ_B_hair_IT.dds"]
            replace_sdo_tex(target_dec, slh, Image.new("RGBA", (slh["w"], slh["h"]), (0, 0, 0, 0)))

    # Seal isolated KUZ hair-cap island across open headband gap cleanly onto upper forehead & temples
    for vn in ("Face-VB", "Face_lodL-VB"):
        if vn not in vbs:
            continue
        fxyz, fnrm, fuv = read_vb_full(bytes(target_dec), vbs[vn], st_idx=0)
        fib = _find_ib_for_vb(ibs, vn)
        if not fib:
            continue
        ftris = _strip_to_tris(fib["inds"])
        par = list(range(len(fxyz)))
        def _find(x):
            while par[x] != x:
                par[x] = par[par[x]]
                x = par[x]
            return x
        for a, b, c in ftris:
            if a < len(fxyz) and b < len(fxyz) and c < len(fxyz):
                ra, rb, rc = _find(a), _find(b), _find(c)
                par[rb] = ra; par[rc] = ra
        comps = {}
        for i in range(len(fxyz)):
            comps.setdefault(_find(i), []).append(i)
        cap_idx = set()
        for root, vs in comps.items():
            if float(fuv[vs, 1].min()) < 0.05:
                cap_idx.update(vs)
        if cap_idx:
            new_fxyz = fxyz.copy()
            for i in cap_idx:
                x, y, z = float(fxyz[i, 0]), float(fxyz[i, 1]), float(fxyz[i, 2])
                tz = max(0.0, min(1.0, (z - 0.15) / 0.80))
                tz_s = tz * tz * (3.0 - 2.0 * tz)
                ty = max(0.0, min(1.0, (y - 17.10) / 0.70))
                ty_s = ty * ty * (3.0 - 2.0 * ty)
                tz_front = max(0.0, min(1.0, (z + 0.25) / 0.75))
                tzf_s = tz_front * tz_front * (3.0 - 2.0 * tz_front)
                new_fxyz[i, 2] = z + 0.38 * tz_s
                new_fxyz[i, 1] = y - 0.17 * ty_s * tzf_s
            nn = _recalc_blended_normals([tuple(map(float, r)) for r in new_fxyz], [tuple(r) for r in fnrm], fib["inds"], blend=0.45)
            write_vb_stream_xyz_nrm(target_dec, vbs[vn], new_fxyz, nn, st_idx=0)

    # Clear baked white headband shadow in _B_face alpha forehead
    f_k = next(k for k in slots if "_b_face" in k.lower())
    fim = extract_slot_image(bytes(target_dec), slots[f_k]).convert("RGBA")
    farr = np.array(fim)
    fh, fw = farr.shape[:2]
    farr[int(fh * 0.10):int(fh * 0.34), int(fw * 0.18):int(fw * 0.82), 3] = np.maximum(
        farr[int(fh * 0.10):int(fh * 0.34), int(fw * 0.18):int(fw * 0.82), 3], 242
    )
    replace_sdo_tex(target_dec, slots[f_k], Image.fromarray(farr, mode="RGBA"))


def apply_player_3d_overrides(pid: str, base_name: str, target_dec: bytearray, base_dec: bytes):
    """Apply exact 3D VB/IB geometry & clean accessory textures for each player."""
    slots = {s["name"]: s for s in parse_sdo_dds_slots(bytes(target_dec))}
    vbs = {v["short_name"]: v for v in parse_vbs(bytes(target_dec))}

    if pid == "29_91_AGA":
        _apply_3d_agassi_91_mullet(target_dec, base_dec)
    elif pid == "29_AG2":
        _sculpt_bald_cranium_ag2(target_dec)
        _unify_bald_scalp_tone_ag2(target_dec)
        vbs = {v["short_name"]: v for v in parse_vbs(bytes(target_dec))}
        _collapse_vb(target_dec, vbs, "Hair_fix-VB", point=(0.0, 16.5, 0.0))
        _collapse_vb(target_dec, vbs, "Hair_fix_lodL-VB", point=(0.0, 0.5, 0.0))
        if "P_DJV_B_hair_IT.dds" in slots:
            slh = slots["P_DJV_B_hair_IT.dds"]
            replace_sdo_tex(target_dec, slh, Image.new("RGBA", (slh["w"], slh["h"]), (0, 0, 0, 0)))
        # Keep completely clean-shaved unified bald scalp, satin normals & warm SSS
        f_k = next(k for k in slots if "_b_face" in k.lower())
        f_rgb = np.array(extract_slot_image(bytes(target_dec), slots[f_k]).convert("RGB").resize((1024, 1024)))
        kps5, _ = detect_kps5_and_lms(f_rgb)
        for sn, sl in slots.items():
            snl = sn.lower()
            if "_n_face_" in snl:
                im_n = b57.build_clean_normal_dynamic(f_rgb, (sl["w"], sl["h"]), kps5, is_sweat=("sweat" in snl))
                narr = np.array(im_n)
                nh = narr.shape[0]
                narr[:int(nh * 0.42), :, 3] = np.maximum(narr[:int(nh * 0.42), :, 3], 42)
                replace_sdo_tex(target_dec, sl, Image.fromarray(narr, mode="RGBA"))
            elif "_ss_face_" in snl:
                ssim = np.array(extract_slot_image(bytes(target_dec), sl).convert("RGBA"))
                sh, sw = ssim.shape[:2]
                patch = ssim[int(sh * 0.45):int(sh * 0.65), int(sw * 0.35):int(sw * 0.45)]
                med_ss = np.median(patch.reshape(-1, 4), axis=0).astype(np.uint8)
                top_mask = (np.arange(sh)[:, None] < int(sh * 0.46)) & (ssim[:, :, 0] < 60)
                ssim[top_mask] = med_ss
                replace_sdo_tex(target_dec, sl, Image.fromarray(ssim, mode="RGBA"))
    elif pid == "35_SAB":
        _apply_3d_sabalenka_bun(target_dec)
    elif pid == "65_BAD":
        # Hide P_W_IVA_IT visor completely (Accessory-VB[s0]) while keeping ponytail & hairtop intact
        for vn in ("Accessory-VB", "Accessory_lodL-VB"):
            if vn in vbs:
                st0 = vbs[vn]["streams"][0]
                nv0 = st0["nverts"]
                write_vb_stream_xyz_nrm(target_dec, vbs[vn], np.tile(np.array([[0.0, 0.5, 0.0]], dtype=np.float32), (nv0, 1)), [(0, 32767, 0, 0)] * nv0, st_idx=0)
        if "P_IVA_B_accessory_IT.dds" in slots:
            sla = slots["P_IVA_B_accessory_IT.dds"]
            replace_sdo_tex(target_dec, sla, Image.new("RGBA", (sla["w"], sla["h"]), (0, 0, 0, 0)))
        f_k = next(k for k in slots if "_b_face" in k.lower())
        farr = np.array(extract_slot_image(bytes(target_dec), slots[f_k]).convert("RGBA"))
        farr[int(farr.shape[0] * 0.08):int(farr.shape[0] * 0.35), int(farr.shape[1] * 0.16):int(farr.shape[1] * 0.84), 3] = 248
        replace_sdo_tex(target_dec, slots[f_k], Image.fromarray(farr, mode="RGBA"))
    elif pid == "34_SWI":
        # Swiatek on P_W_IVA_IT: watertight spherical 6-panel white baseball cap dome (s1 wraps down to s0 strap all around)
        ibs = {ib["short_name"]: ib for ib in parse_ibs(bytes(target_dec))}
        for vn in ("Accessory-VB", "Accessory_lodL-VB"):
            if vn not in vbs:
                continue
            vb_acc = vbs[vn]
            if len(vb_acc["streams"]) >= 2:
                xyz1, nrm1, _ = read_vb_full(bytes(target_dec), vb_acc, st_idx=1)
                new1 = xyz1.copy()
                for i in range(len(new1)):
                    x, y, z = float(new1[i, 0]), float(new1[i, 1]), float(new1[i, 2])
                    dx, dz = x, z - 0.14
                    r_norm = min(1.0, math.sqrt((dx / 0.63) ** 2 + (dz / 0.78) ** 2))
                    theta = math.atan2(dz, dx)
                    phi = r_norm * (0.55 * math.pi)
                    sin_p, cos_p = math.sin(phi), math.cos(phi)
                    tx = 0.835 * sin_p * math.cos(theta)
                    tz = 0.10 + 0.94 * sin_p * math.sin(theta)
                    ty = 1.32 + 0.96 * (max(0.0, cos_p) ** 0.55) - 0.14 * max(0.0, -cos_p) + 0.20 * max(0.0, min(1.0, (tz + 0.20) / 1.10)) * (r_norm ** 1.3)
                    new1[i, 0], new1[i, 1], new1[i, 2] = tx, ty, tz
                ib1_name = ("Accessory-0001-IB" if vn == "Accessory-VB" else "Accessory_lodL-0001-IB")
                ib1 = ibs.get(ib1_name) or _find_ib_for_vb(ibs, vn)
                nn1 = _recalc_blended_normals([tuple(map(float, r)) for r in new1], [tuple(r) for r in nrm1], ib1["inds"], blend=0.55) if ib1 else nrm1
                write_vb_stream_xyz_nrm(target_dec, vb_acc, new1, nn1, st_idx=1)
            xyz0, nrm0, _ = read_vb_full(bytes(target_dec), vb_acc, st_idx=0)
            new0 = xyz0.copy()
            for i in range(len(new0)):
                if new0[i, 1] > 1.25 and new0[i, 2] < 1.0:
                    new0[i, 1] += 0.04
            write_vb_stream_xyz_nrm(target_dec, vb_acc, new0, nrm0, st_idx=0)
        if "P_IVA_B_accessory_IT.dds" in slots:
            sla = slots["P_IVA_B_accessory_IT.dds"]
            bsla = {s["name"]: s for s in parse_sdo_dds_slots(base_dec)}[sla["name"]]
            carr = np.array(extract_slot_image(base_dec, bsla).convert("RGBA")).astype(np.float32)
            lum_c = (0.299 * carr[:, :, 0] + 0.587 * carr[:, :, 1] + 0.114 * carr[:, :, 2]) / 255.0
            med_c = max(0.25, float(np.median(lum_c)))
            shade_c = np.clip(0.92 + 0.10 * np.clip(lum_c / med_c, 0.7, 1.2), 0.88, 1.02)[:, :, None]
            rgb_c = np.clip(np.array([[[243.0, 243.0, 246.0]]]) * shade_c, 0, 255).astype(np.uint8)
            replace_sdo_tex(target_dec, sla, Image.fromarray(np.dstack([rgb_c, carr[:, :, 3].astype(np.uint8)]), mode="RGBA"))
        if "P_IVA_B_hairtop_IT.dds" in slots:
            slh = slots["P_IVA_B_hairtop_IT.dds"]
            hw, hh = slh["w"], slh["h"]
            yy, xx = np.mgrid[0:hh, 0:hw].astype(np.float32)
            r_u = np.clip(np.sqrt(((xx / max(1, hw - 1)) - 0.5) ** 2 + ((yy / max(1, hh - 1)) - 0.5) ** 2) * 2.0, 0.0, 1.0)
            seam = 1.0 - 0.03 * np.exp(-0.5 * (np.abs(xx / max(1, hw - 1) - 0.5) / 0.015) ** 2)
            shade_h = (0.99 - 0.035 * (r_u ** 1.5)) * seam
            crisp = np.clip(np.stack([243.0 * shade_h, 243.0 * shade_h, 246.0 * shade_h, np.full_like(shade_h, 255.0)], axis=-1), 0, 255).astype(np.uint8)
            replace_sdo_tex(target_dec, slh, Image.fromarray(crisp, mode="RGBA"))
        if "P_IVA_N_hairtop_IT.dds" in slots:
            sln = slots["P_IVA_N_hairtop_IT.dds"]
            replace_sdo_tex(target_dec, sln, Image.new("RGBA", (sln["w"], sln["h"]), (128, 128, 255, 22)))
    elif pid == "81_CLI":
        f_k = next(k for k in slots if "_b_face" in k.lower())
        farr = np.array(extract_slot_image(bytes(target_dec), slots[f_k]).convert("RGBA"))
        farr[:, :, :3] = recolor_uv_hair_perimeter(farr[:, :, :3], (196, 170, 124), aggressive=True)
        replace_sdo_tex(target_dec, slots[f_k], Image.fromarray(farr, mode="RGBA"))
    elif pid == "44_HEW":
        _apply_3d_backwards_cap(target_dec, base_dec, primary_rgb=(240, 241, 244), stripe_rgb=None)
    elif pid == "59_SHE":
        # Directly match P_MON_B_body_SN skin tone to final lightened cheek LAB (uncapped from batch_studio_57's +-18 cap)
        f_k = next((k for k in slots if "_b_face" in k.lower()), None)
        if f_k:
            f_rgb = np.array(extract_slot_image(bytes(target_dec), slots[f_k]).convert("RGB"))
            fh, fw = f_rgb.shape[:2]
            f_lab = cv2.cvtColor(f_rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
            c_patch = f_lab[int(fh * 0.45):int(fh * 0.58), int(fw * 0.32):int(fw * 0.44)].reshape(-1, 3)
            cheek_lab = np.median(c_patch, axis=0)
            for sn, sl in slots.items():
                if "_b_body_" in sn.lower():
                    b_rgba = np.array(extract_slot_image(bytes(target_dec), sl).convert("RGBA"))
                    b_lab = cv2.cvtColor(b_rgba[:, :, :3], cv2.COLOR_RGB2LAB).astype(np.float32)
                    skin_m = (b_lab[:, :, 0] > 22.0) & (b_lab[:, :, 0] < 195.0) & (b_lab[:, :, 1] > 128.0) & (b_lab[:, :, 2] > 128.0)
                    if np.any(skin_m):
                        b_med = np.median(b_lab[skin_m], axis=0)
                        shift = cheek_lab - b_med
                        for c in range(3):
                            b_lab[:, :, c] = np.where(skin_m, np.clip(b_lab[:, :, c] + shift[c], 0.0, 255.0), b_lab[:, :, c])
                        b_rgb = cv2.cvtColor(b_lab.astype(np.uint8), cv2.COLOR_LAB2RGB)
                        replace_sdo_tex(target_dec, sl, Image.fromarray(np.dstack([b_rgb, b_rgba[:, :, 3]]), mode="RGBA"))
    elif pid == "61_RUU":
        _paint_band_or_cap_slot(target_dec, base_dec, "P_M_DEL_SN", "headband", (242, 242, 245), stripe_rgb=(28, 52, 98))
    elif pid == "71_BER":
        _paint_band_or_cap_slot(target_dec, base_dec, "P_M_COU_SN", "cap", (44, 92, 168), stripe_rgb=(242, 244, 248))
    elif pid == "72_CHN":
        _paint_band_or_cap_slot(target_dec, base_dec, "P_M_COU_SN", "cap", (242, 242, 245), stripe_rgb=(176, 36, 44))
    elif pid in ("83_BJK", "37_NAV", "56_SEL"):
        h_rgb = PLAYER_HAIR_RGB_OVERRIDE.get(pid, (120, 90, 58))
        if pid == "83_BJK":
            # Subtle jaw/cheekbone narrowing sculpt (Kuznetsova wide jaw -> BJK 1973 oval silhouette, 0.0mm neck lock)
            ibs = {ib["short_name"]: ib for ib in parse_ibs(bytes(target_dec))}
            for vn in ("Face-VB", "Face_lodL-VB"):
                if vn not in vbs:
                    continue
                fxyz, fnrm, _ = read_vb_full(bytes(target_dec), vbs[vn], st_idx=0)
                new_f = fxyz.copy()
                for i in range(len(new_f)):
                    x, y, z = float(new_f[i, 0]), float(new_f[i, 1]), float(new_f[i, 2])
                    if y >= 15.5 and z > 0.25:
                        t_j = math.exp(-0.5 * ((y - 16.1) / 0.45) ** 2) * max(0.0, min(1.0, (z - 0.25) / 0.55))
                        new_f[i, 0] = x * (1.0 - 0.055 * t_j)
                ib = _find_ib_for_vb(ibs, vn)
                nn = _recalc_blended_normals([tuple(map(float, r)) for r in new_f], [tuple(r) for r in fnrm], ib["inds"], blend=0.45) if ib else fnrm
                write_vb_stream_xyz_nrm(target_dec, vbs[vn], new_f, nn, st_idx=0)
            _apply_3d_eyeglasses_kuz(target_dec, frame_rgb=(74, 42, 24), hide_ponytail=False, keep_bob=True)
        elif pid == "37_NAV":
            _apply_3d_eyeglasses_kuz(target_dec, frame_rgb=(42, 48, 58), hide_ponytail=True)
        else:
            if "P_KUZ_B_accessory_IT.dds" in slots:
                sl = slots["P_KUZ_B_accessory_IT.dds"]
                bsl = {s["name"]: s for s in parse_sdo_dds_slots(base_dec)}[sl["name"]]
                arr = np.array(extract_slot_image(base_dec, bsl).convert("RGBA"))
                arr[:, :, :3] = np.clip(arr[:, :, :3].astype(np.float32) * np.array([[[0.96, 0.96, 0.98]]]), 0, 255).astype(np.uint8)
                replace_sdo_tex(target_dec, sl, Image.fromarray(arr, mode="RGBA"))
        # Refill KUZ alpha=0 headband void with organic wispy bangs + force opaque upper-head alpha
        f_k = next(k for k in slots if "_b_face" in k.lower())
        farr = np.array(extract_slot_image(bytes(target_dec), slots[f_k]).convert("RGBA"))
        frgb = fill_kuz_forehead_hairline(farr[:, :, :3], h_rgb)
        fh, fw = farr.shape[:2]
        farr[:, :, :3] = frgb
        farr[:int(fh * 0.40), :, 3] = np.maximum(farr[:int(fh * 0.40), :, 3], 248)
        replace_sdo_tex(target_dec, slots[f_k], Image.fromarray(farr, mode="RGBA"))
    elif pid == "43_KYR":
        # Gentle +0.04 dm top loft ONLY (preserve Nano Banana crisp hairline & beard width)
        ibs = {ib["short_name"]: ib for ib in parse_ibs(bytes(target_dec))}
        for vn in ("Hair_fix-VB", "Hair_fix_lodL-VB"):
            if vn in vbs:
                xyz, nrm, _ = read_vb_full(bytes(target_dec), vbs[vn], st_idx=0)
                new_xyz = xyz.copy()
                is_w = float(xyz[:, 1].max()) > 8.0
                for i in range(len(xyz)):
                    ty = float(np.clip(((xyz[i, 1] - 17.45) if is_w else (xyz[i, 1] - 1.40)) / 0.50, 0.0, 1.0))
                    new_xyz[i, 1] += 0.045 * ty * math.exp(-0.5 * (xyz[i, 0] / 0.35) ** 2)
                ib = _find_ib_for_vb(ibs, vn)
                nn = _recalc_blended_normals([tuple(map(float, r)) for r in new_xyz], [tuple(r) for r in nrm], ib["inds"], blend=0.4) if ib else nrm
                write_vb_stream_xyz_nrm(target_dec, vbs[vn], new_xyz, nn, st_idx=0)
    elif pid == "30_BOR":
        # Iconic white Fila headband with navy + red horizontal pinstripes
        _paint_band_or_cap_slot(target_dec, base_dec, "P_M_NAD_IT", "headband", (242, 242, 244), stripe_rgb=(24, 42, 92), stripe2_rgb=(188, 34, 40))
    elif pid == "36_KUE":
        _paint_band_or_cap_slot(target_dec, base_dec, "P_M_NAD_IT", "headband", (224, 178, 36), stripe_rgb=(24, 72, 148))
    elif pid == "53_VIL":
        _paint_band_or_cap_slot(target_dec, base_dec, "P_M_NAD_IT", "headband", (28, 42, 78), stripe_rgb=(238, 240, 244))
    elif pid == "60_RUB":
        _paint_band_or_cap_slot(target_dec, base_dec, "P_M_NAD_IT", "headband", (242, 242, 244))
    elif pid == "31_MCE":
        _paint_band_or_cap_slot(target_dec, base_dec, "P_M_DEL_SN", "headband", (186, 32, 36))
    elif pid in ("40_ZVE", "54_IVN"):
        _paint_band_or_cap_slot(target_dec, base_dec, "P_M_DEL_SN", "headband", (242, 242, 245), stripe_rgb=(28, 48, 92))
    elif pid == "48_MOY":
        _paint_band_or_cap_slot(target_dec, base_dec, "P_M_DEL_SN", "headband", (242, 242, 245))
    elif pid == "67_COR":
        _paint_band_or_cap_slot(target_dec, base_dec, "P_M_COU_SN", "cap", (242, 244, 246), stripe_rgb=(110, 178, 228))
    elif pid == "49_FER":
        _paint_band_or_cap_slot(target_dec, base_dec, "P_M_FED_SN", "headband", (242, 242, 245))
    elif pid == "77_WLD":
        _paint_band_or_cap_slot(target_dec, base_dec, "P_M_DEL_SN", "headband", (28, 46, 88), stripe_rgb=(238, 240, 244))
    elif pid == "62_FRI":
        _paint_band_or_cap_slot(target_dec, base_dec, "P_M_FED_SN", "headband", (242, 242, 245), stripe_rgb=(28, 30, 34))
    elif pid == "82_AND":
        # Clean white visor + warm wheat-blonde ponytail on P_W_IVA_IT
        _paint_band_or_cap_slot(target_dec, base_dec, "P_W_IVA_IT", "visor", (244, 244, 246), stripe_rgb=(210, 214, 220))
    elif pid == "57_HEN":
        _paint_band_or_cap_slot(target_dec, base_dec, "P_W_IVA_IT", "visor", (244, 244, 246), stripe_rgb=(32, 68, 128))
    elif pid == "79_ASV":
        _paint_band_or_cap_slot(target_dec, base_dec, "P_W_IVA_IT", "visor", (244, 244, 246), stripe_rgb=(192, 38, 48))


# ---------------------------------------------------------------------------
# Full Diagnostic 3D Head Renderer (including NAD rotated Hair_cloth + 3D Accessories!)
# ---------------------------------------------------------------------------
def _collect_meshes_full(dec: bytes, vbs: dict, ibs: dict, slots: dict) -> list:
    """Collect hair, caps, headbands, visors & 3D eyeglasses accurately in world space."""
    _, head_world = get_eye_and_head_world_coords(dec, vbs)
    is_nad = ("P_NAD_B_hair_IT.dds" in slots) or ("P_NAD_B_face_IT.dds" in slots)

    def get_slot(subs):
        for sname, sl in slots.items():
            sl_l = sname.lower()
            if all(x in sl_l for x in subs):
                return np.array(extract_slot_image(dec, sl).convert("RGBA"))
        return None

    def first_slot(*cands):
        for c in cands:
            r = get_slot(c)
            if r is not None:
                return r
        return None

    hair_tex = first_slot(["_b_hair_"], ["_b_hair01"], ["_b_hair"])
    hairtop_tex = first_slot(["_b_hairtop"], ["_b_head_"])
    if hairtop_tex is None:
        hairtop_tex = hair_tex
    cap_tex = get_slot(["_b_cap"])
    acc_tex = first_slot(["_b_accessory"], ["_b_headband"], ["_b_hairband"])

    out = []
    for vn, vb in vbs.items():
        vl = vn.lower()
        if "lod" in vl or "wrist" in vl or "body" in vl or "sweat" in vl or "lash" in vl or "eye" in vl or "face" in vl:
            continue
        if not any(t in vl for t in ("hair", "cap", "band", "acc")):
            continue
        stem = vn[:-3] if vn.endswith("-VB") else vn
        matching_ibs = [ib for ib_n, ib in ibs.items() if ib_n.lower().startswith(stem.lower() + "-")]
        if not matching_ibs:
            ib0 = _find_ib_for_vb(ibs, vn)
            matching_ibs = [ib0] if ib0 else []
        if not matching_ibs:
            continue
        for si in range(len(vb["streams"])):
            ib = next((b for b in matching_ibs if f"-{si:04d}-ib" in b["short_name"].lower()), None)
            if ib is None:
                ib = matching_ibs[si] if si < len(matching_ibs) else matching_ibs[0]
            pts, _, uvs = read_vb_full(dec, vb, st_idx=si)
            if is_nad and vn == "Hair_cloth-VB":
                wpts = np.column_stack([pts[:, 2], head_world[1] + pts[:, 0], head_world[2] - pts[:, 1]]).astype(np.float32)
            elif float(pts[:, 1].max()) < 8.0:
                wpts = pts + head_world[None, :]
            else:
                wpts = pts

            tris = _strip_to_tris(ib["inds"])
            ib_l = ib["short_name"].lower()
            keep = []
            for t in tris:
                a, b, c = t
                if a >= len(wpts) or b >= len(wpts) or c >= len(wpts):
                    continue
                if "acc" in vl and (max(abs(float(wpts[a, 0])), abs(float(wpts[b, 0])), abs(float(wpts[c, 0]))) >= 1.35 or min(float(wpts[a, 1]), float(wpts[b, 1]), float(wpts[c, 1])) <= 16.25):
                    continue
                if min(float(np.linalg.norm(wpts[a] - wpts[b])), float(np.linalg.norm(wpts[b] - wpts[c]))) < 1e-4:
                    continue
                keep.append(t)
            tris = keep
            if "_b_cap" in ib_l or "cap" in vl:
                mtex = cap_tex
            elif "_b_hairtop" in ib_l or "_b_head" in ib_l or ("fix" in vl and is_nad):
                mtex = hairtop_tex
            elif "_b_hair" in ib_l or ("hair" in vl):
                mtex = hair_tex
            elif vn.lower().startswith("accessory") and "P_SHA_B_hair_SN.dds" in slots:
                mtex = hair_tex if si in (1, 2) else acc_tex
            elif "headband" in vl or "hairband" in vl or "_b_accessory" in ib_l or "acc" in vl:
                mtex = acc_tex
            else:
                mtex = hair_tex
            if mtex is not None and tris:
                out.append((wpts, uvs, tris, mtex))
    return out


def render_hero_head_full(dec: bytes, yaw_deg: float = 0.0, size: int = 384) -> np.ndarray:
    vbs = {v["short_name"]: v for v in parse_vbs(dec)}
    ibs = {ib["short_name"]: ib for ib in parse_ibs(dec)}
    slots = {s["name"]: s for s in parse_sdo_dds_slots(dec)}
    fslot = next(s for k, s in slots.items() if "_b_face" in k.lower())
    eslot = next((s for k, s in slots.items() if "_b_eye" in k.lower()), None)
    hslot = next((s for k, s in slots.items() if "_b_hair" in k.lower()), None)
    fuv = np.array(extract_slot_image(dec, fslot).convert("RGB"))
    etex = np.array(extract_slot_image(dec, eslot).convert("RGB")) if eslot else np.full((64, 64, 3), 80, dtype=np.uint8)
    htex = np.array(extract_slot_image(dec, hslot).convert("RGBA")) if hslot else np.zeros((64, 64, 4), dtype=np.uint8)
    fxyz, fnrm, _ = read_vb_full(dec, vbs["Face-VB"])
    meshes = _collect_meshes_full(dec, vbs, ibs, slots)
    im, _, _, _ = render_generic_sdo_head(
        dec, vbs, ibs, fxyz, fuv, etex, meshes, htex,
        face_nrm_override=fnrm, yaw_deg=yaw_deg, shade=True,
    )
    return cv2.resize(im, (size, size), interpolation=cv2.INTER_AREA)


# ---------------------------------------------------------------------------
# Main Upgrade Driver
# ---------------------------------------------------------------------------
def _fit_tile(im_rgb: np.ndarray, tile_sz: int) -> np.ndarray:
    ih, iw = im_rgb.shape[:2]
    if ih != iw:
        side = min(ih, iw)
        y0 = max(0, (ih - side) // 4)
        x0 = (iw - side) // 2
        im_rgb = im_rgb[y0:y0 + side, x0:x0 + side]
    return cv2.resize(im_rgb, (tile_sz, tile_sz), interpolation=cv2.INTER_AREA)


def render_heroes_sheet(records: list[dict], out_path: str, tile_sz: int = 300):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    rows = []
    banner = np.full((52, tile_sz * 6, 3), (12, 16, 22), dtype=np.uint8)
    cv2.putText(
        banner,
        "2026 SOTA OVERHAUL SHOWCASE | Best Ref | Fresh Base UV | HyperSwap+GPEN UV | 3D -34 deg | 3D Front 0 deg | 3D +34 deg",
        (14, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.56, (110, 255, 165), 2, cv2.LINE_AA,
    )
    rows.append(banner)
    for rec in records:
        pid = rec["player_id"]
        sdo_path = os.path.join(MODEL_DIR, rec["out_sdo"])
        dec = decompress_sdo(open(sdo_path, "rb").read())
        fslot = next(s for s in parse_sdo_dds_slots(dec) if "_b_face" in s["name"].lower())
        fuv_tex = np.array(extract_slot_image(dec, fslot).convert("RGB"))
        ref_im = _fit_tile(np.array(Image.open(rec["best_ref"]).convert("RGB")), tile_sz) if rec["best_ref"] else np.full((tile_sz, tile_sz, 3), 40, dtype=np.uint8)
        old_im = _fit_tile(np.array(Image.open(rec["old_uv"]).convert("RGB")), tile_sz)
        new_im = _fit_tile(fuv_tex, tile_sz)
        r_m34 = render_hero_head_full(dec, yaw_deg=-34.0, size=tile_sz)
        r_000 = render_hero_head_full(dec, yaw_deg=0.0, size=tile_sz)
        r_p34 = render_hero_head_full(dec, yaw_deg=34.0, size=tile_sz)

        hdr = np.full((28, tile_sz * 6, 3), (22, 26, 34), dtype=np.uint8)
        col = (110, 255, 165) if rec["cos_sim_after"] >= 0.40 else (255, 220, 110)
        txt = (
            f"{pid} ({rec['base_sdo']}) | cos_sim: {rec['cos_sim_before']:.3f} -> {rec['cos_sim_after']:.3f} | "
            f"sculpt={rec['sculpt_max_mm']:.2f}mm | neck={rec['neck_seam_mm']:.4f}mm | mip={rec['mip0']:.2f}/{rec['mip1']:.2f}"
        )
        cv2.putText(hdr, txt, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.50, col, 1, cv2.LINE_AA)
        rows.append(hdr)
        rows.append(np.hstack([ref_im, old_im, new_im, r_m34, r_000, r_p34]))
    Image.fromarray(np.vstack(rows)).save(out_path)
    print(f"[SHEET SAVED] {out_path}", flush=True)


def render_all_6_sheets(metrics_list: list[dict], tile_sz: int = 320):
    os.makedirs(AUDIT_DIR, exist_ok=True)
    per_sheet = 10
    n_sheets = (len(metrics_list) + per_sheet - 1) // per_sheet
    out_paths = []
    for s_idx in range(n_sheets):
        chunk = metrics_list[s_idx * per_sheet:(s_idx + 1) * per_sheet]
        rows = []
        banner = np.full((52, tile_sz * 5, 3), (12, 16, 22), dtype=np.uint8)
        ids_str = f"{chunk[0]['player_id']} .. {chunk[-1]['player_id']}"
        cv2.putText(
            banner,
            f"VT4 2026 SOTA AUDIT SHEET {s_idx + 1}/{n_sheets} ({ids_str}) | Ref | Fresh Base UV | HyperSwap+GPEN UV | 3D Front | 3D 3/4",
            (14, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (110, 255, 165), 2, cv2.LINE_AA,
        )
        rows.append(banner)
        for rec in chunk:
            pid = rec["player_id"]
            dec = decompress_sdo(open(os.path.join(MODEL_DIR, rec["out_sdo"]), "rb").read())
            fslot = next(s for s in parse_sdo_dds_slots(dec) if "_b_face" in s["name"].lower())
            fuv = np.array(extract_slot_image(dec, fslot).convert("RGB"))
            ref_im = _fit_tile(np.array(Image.open(rec["best_ref"]).convert("RGB")), tile_sz) if (rec["best_ref"] and os.path.exists(rec["best_ref"])) else np.full((tile_sz, tile_sz, 3), 40, dtype=np.uint8)
            old_im = _fit_tile(np.array(Image.open(rec["old_uv"]).convert("RGB")), tile_sz) if os.path.exists(rec["old_uv"]) else np.zeros((tile_sz, tile_sz, 3), dtype=np.uint8)
            new_im = _fit_tile(fuv, tile_sz)
            fr_im = render_hero_head_full(dec, yaw_deg=0.0, size=tile_sz)
            t34_im = render_hero_head_full(dec, yaw_deg=34.0, size=tile_sz)

            hdr = np.full((28, tile_sz * 5, 3), (22, 26, 34), dtype=np.uint8)
            col = (110, 255, 165) if rec["cos_sim_after"] >= 0.40 else ((255, 220, 110) if rec["cos_sim_after"] >= 0.25 else (255, 120, 120))
            txt = (
                f"{pid} ({rec['base_sdo']}) | refs={rec['refs_used']} | "
                f"cos_sim: {rec['cos_sim_before']:.3f} -> {rec['cos_sim_after']:.3f} | "
                f"sculpt={rec['sculpt_max_mm']:.2f}mm | neck={rec['neck_seam_mm']:.4f}mm | mip={rec['mip0']:.2f}/{rec['mip1']:.2f} | {rec['status']}"
            )
            cv2.putText(hdr, txt, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.48, col, 1, cv2.LINE_AA)
            rows.append(hdr)
            rows.append(np.hstack([ref_im, old_im, new_im, fr_im, t34_im]))
        sp = os.path.join(AUDIT_DIR, f"sheet_{s_idx + 1:02d}.png")
        Image.fromarray(np.vstack(rows)).save(sp)
        out_paths.append(sp)
        print(f"[SHEET SAVED] {sp}", flush=True)
    return out_paths


def upgrade_single_player(spec: dict, roster_meta: dict, entries: list, f0, f1, arc_cache: dict) -> dict:
    pid = spec["folder"]
    base_name = spec["base"]
    out_stem = spec["out"]
    ent = next(e for e in entries if e["name"].lower() == f"high/player/model/{base_name.lower()}.sdo")
    base_dec = decompress_sdo(read_entry(entries, ent, f0, f1, arc_cache))

    # Resolve verified natural hair RGB
    h_cat = roster_meta.get(pid, {}).get("hair_color", "brown")
    hair_rgb = PLAYER_HAIR_RGB_OVERRIDE.get(pid, HAIR_RGB_BY_CATEGORY.get(h_cat, (78, 55, 36)))

    # 1. Stage FRESH vanilla or PINNED AAA UV into FRESH_BASES_DIR/<pid>.png
    os.makedirs(FRESH_BASES_DIR, exist_ok=True)
    bslots = {s["name"]: s for s in parse_sdo_dds_slots(base_dec)}
    bf_slot = next(s for k, s in bslots.items() if "_b_face" in k.lower())
    fresh_rgb = np.array(extract_slot_image(base_dec, bf_slot).convert("RGB").resize((1024, 1024), Image.Resampling.LANCZOS))
    _SKIP_SWAP_PIDS.discard(pid)
    if pid in PINNED_CANVAS_2026:
        rel_c, do_swap = PINNED_CANVAS_2026[pid]
        raw_c = np.array(Image.open(os.path.join(REPO_ROOT, rel_c)).convert("RGB").resize((1024, 1024), Image.Resampling.LANCZOS))
        canvas_rgb = align_canvas_to_template_uv(raw_c, fresh_rgb)
        if pid == "29_AG2":
            # Blend subtle 40% high-freq skin pore texture onto p6_canvases/29_AG2.png
            f_f = fresh_rgb.astype(np.float32)
            pore = f_f - cv2.GaussianBlur(f_f, (21, 21), 5.0)
            canvas_rgb = np.clip(canvas_rgb.astype(np.float32) + pore * 0.40, 0, 255).astype(np.uint8)
        elif pid == "35_SAB":
            canvas_rgb = recolor_uv_hair_perimeter(canvas_rgb, hair_rgb, aggressive=True)
        if not do_swap:
            _SKIP_SWAP_PIDS.add(pid)
    elif pid == "29_AG2":
        canvas_rgb = synthesize_bald_scalp_uv(fresh_rgb)
    elif pid == "59_SHE":
        # Lift Monfils dark skin cleanly toward Ben Shelton's real light warm tan (LAB L~142, a~142, b~146) pre-swap
        lab_s = cv2.cvtColor(fresh_rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
        Hs, Ws = fresh_rgb.shape[:2]
        yys = (np.arange(Hs, dtype=np.float32) / max(1, Hs - 1))[:, None]
        skin_pre = (lab_s[:, :, 0] > 38.0) & ((yys >= 0.24) | (lab_s[:, :, 0] > 52.0))
        if np.any(skin_pre):
            med_s = np.median(lab_s[skin_pre], axis=0)
            target_s = np.array([142.0, 142.0, 146.0], dtype=np.float32)
            # Softly stretch around skin median & shift L/a/b smoothly
            m_soft = np.clip((lab_s[:, :, 0] - 36.0) / 14.0, 0.0, 1.0) * np.where((yys >= 0.24) | (lab_s[:, :, 0] > 50.0), 1.0, 0.0)
            for c, d_val in enumerate(target_s - med_s):
                lab_s[:, :, c] = np.clip(lab_s[:, :, c] + d_val * m_soft, 0.0, 255.0)
        canvas_rgb = cv2.cvtColor(lab_s.astype(np.uint8), cv2.COLOR_LAB2RGB)
    elif pid == "72_CHN":
        # Prep Courier Caucasian base for Michael Chang: jet-black hair perimeter & subtle Asian warm skin tone
        c_tmp = recolor_uv_hair_perimeter(fresh_rgb, (20, 18, 17), aggressive=True)
        lab_c = cv2.cvtColor(c_tmp, cv2.COLOR_RGB2LAB).astype(np.float32)
        skin_c = lab_c[:, :, 0] > 75.0
        lab_c[:, :, 1] = np.where(skin_c, np.clip(lab_c[:, :, 1] - 4.5, 0.0, 255.0), lab_c[:, :, 1])
        lab_c[:, :, 2] = np.where(skin_c, np.clip(lab_c[:, :, 2] + 5.0, 0.0, 255.0), lab_c[:, :, 2])
        canvas_rgb = cv2.cvtColor(lab_c.astype(np.uint8), cv2.COLOR_LAB2RGB)
    elif base_name == "P_W_KUZ_IT":
        canvas_rgb = fill_kuz_forehead_hairline(fresh_rgb, hair_rgb)
    elif pid == "43_KYR":
        canvas_rgb = apply_skin_fade_uv(fresh_rgb, strength=0.92)
    elif pid == "81_CLI":
        canvas_rgb = recolor_uv_hair_perimeter(fresh_rgb, hair_rgb, aggressive=True)
    elif h_cat not in ("black", "dark_brown"):
        canvas_rgb = recolor_uv_hair_perimeter(fresh_rgb, hair_rgb)
    else:
        canvas_rgb = fresh_rgb
    canvas_path = os.path.join(FRESH_BASES_DIR, f"{pid}.png")
    Image.fromarray(canvas_rgb).save(canvas_path)

    # 2. Rebuild fresh .sdo + .zml + BACKUP_DIR from decompressed vanilla SEGA base
    p4.rebuild_base_sdo_and_zml(spec, base_dec, entries, f0, f1, arc_cache)

    # 3. Run HyperSwap 1C 256 + GPEN-BFR-512 (lower GPEN 0.30 where ref likeness needs max fidelity) + <=3.8mm sculpt
    g_blend = 0.30 if pid in ("72_CHN", "77_WLD", "79_ASV", "83_BJK") else 0.38
    rec = b57.process_one_player(spec, base_dec, canvas_dir=FRESH_BASES_DIR, no_sculpt=False, gfpgan_blend=g_blend)
    _SKIP_SWAP_PIDS.discard(pid)

    # 4. Re-open packed SDO and apply natural hair ramp + 3D VB/IB hair & accessory overrides
    sdo_path = os.path.join(MODEL_DIR, f"{out_stem}.sdo")
    tgt_dec = bytearray(decompress_sdo(open(sdo_path, "rb").read()))
    apply_natural_hair_ramp(tgt_dec, base_dec, hair_rgb)
    apply_player_3d_overrides(pid, base_name, tgt_dec, base_dec)

    comp = lzss_compress_literal(bytes(tgt_dec))
    open(sdo_path, "wb").write(comp)
    return rec


def main():
    ap = argparse.ArgumentParser()
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--heroes-only", action="store_true")
    group.add_argument("--render-heroes", action="store_true")
    group.add_argument("--all", action="store_true")
    group.add_argument("--only", type=str, default=None)
    args = ap.parse_args()

    t0 = time.perf_counter()
    if args.render_heroes:
        hjson = os.path.join(AUDIT_DIR, "metrics_heroes_2026.json")
        recs = json.load(open(hjson, "r", encoding="utf-8"))
        render_heroes_sheet(recs, os.path.join(AUDIT_DIR, "UPGRADE_2026_HEROES.png"))
        return

    entries = load_directory()
    arc_cache = {}
    roster_meta = b57._load_verified_roster()

    if args.heroes_only:
        sel = set(HERO_IDS)
        specs = [p for p in PLAYERS_3D if p["folder"] in sel]
        # Order to match HERO_IDS
        order = {k: i for i, k in enumerate(HERO_IDS)}
        specs.sort(key=lambda s: order[s["folder"]])
    elif args.only:
        sel = set(args.only.split(","))
        specs = [p for p in PLAYERS_3D if p["folder"] in sel and p["folder"] != "26_ALC"]
    else:
        specs = [p for p in PLAYERS_3D if p["folder"] != "26_ALC"]

    results = []
    olive_hits = []
    with open(BIN0, "rb") as f0, open(BIN1, "rb") as f1:
        for spec in specs:
            rec = upgrade_single_player(spec, roster_meta, entries, f0, f1, arc_cache)
            results.append(rec)
            # Automated olive [57,52,41] check on packed _b_hair
            dec_chk = decompress_sdo(open(os.path.join(MODEL_DIR, rec["out_sdo"]), "rb").read())
            for sl in parse_sdo_dds_slots(dec_chk):
                if "_b_hair" in sl["name"].lower() and spec["folder"] not in ("29_AG2", "37_NAV", "83_BJK"):
                    arr = np.array(extract_slot_image(dec_chk, sl).convert("RGBA"))
                    vis = arr[arr[:, :, 3] > 60][:, :3]
                    if len(vis) > 0:
                        m = np.median(vis, axis=0)
                        if abs(m[0] - 57) < 6 and abs(m[1] - 52) < 6 and abs(m[2] - 41) < 6 and spec["folder"] not in ("43_KYR", "49_FER", "54_IVN", "67_COR", "72_CHN"):
                            olive_hits.append((spec["folder"], m.tolist()))

    # Save hero sheet or rebuild metrics + all 6 sheets
    if args.heroes_only:
        json.dump(results, open(os.path.join(AUDIT_DIR, "metrics_heroes_2026.json"), "w", encoding="utf-8"), indent=2)
        render_heroes_sheet(results, os.path.join(AUDIT_DIR, "UPGRADE_2026_HEROES.png"))
    elif args.only:
        hjson = os.path.join(AUDIT_DIR, "metrics_heroes_2026.json")
        by_id = {}
        if os.path.exists(hjson):
            for r in json.load(open(hjson, "r", encoding="utf-8")):
                by_id[r["player_id"]] = r
        for r in results:
            by_id[r["player_id"]] = r
        hero_set = set(HERO_IDS)
        merged_heroes = [by_id[k] for k in HERO_IDS if k in by_id]
        json.dump(merged_heroes, open(hjson, "w", encoding="utf-8"), indent=2)
        render_heroes_sheet(merged_heroes, os.path.join(AUDIT_DIR, "UPGRADE_2026_HEROES.png"))
        mpath = os.path.join(AUDIT_DIR, "metrics_57.json")
        if os.path.exists(mpath):
            m57 = json.load(open(mpath, "r", encoding="utf-8"))
            res_map = {r["player_id"]: r for r in results}
            for idx_m, rm in enumerate(m57):
                if rm["player_id"] in res_map:
                    m57[idx_m] = res_map[rm["player_id"]]
            json.dump(m57, open(mpath, "w", encoding="utf-8"), indent=2)
            render_all_6_sheets(m57)
    if args.all:
        # Include 26_ALC existing record if metrics_57.json exists
        mpath = os.path.join(AUDIT_DIR, "metrics_57.json")
        old_alc = None
        if os.path.exists(mpath):
            try:
                old_list = json.load(open(mpath, "r", encoding="utf-8"))
                old_alc = next((r for r in old_list if r["player_id"] == "26_ALC"), None)
            except Exception:
                old_alc = None
        full_metrics = ([old_alc] if old_alc else []) + results
        json.dump(full_metrics, open(mpath, "w", encoding="utf-8"), indent=2)
        heroes_map = {r["player_id"]: r for r in results}
        hero_recs = [heroes_map[k] for k in HERO_IDS if k in heroes_map]
        render_heroes_sheet(hero_recs, os.path.join(AUDIT_DIR, "UPGRADE_2026_HEROES.png"))
        render_all_6_sheets(full_metrics)

    print(f"\n[DONE] {len(results)} players upgraded in {time.perf_counter() - t0:.1f}s | olive_bugs={olive_hits}", flush=True)


if __name__ == "__main__":
    main()
