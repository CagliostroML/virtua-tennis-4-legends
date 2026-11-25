#!/usr/bin/env python3
"""
Full 3D Hair Grooming Engine for Virtua Tennis 4 (.sdo) Player Models.

Transforms SEGA's flat painted egg-skull & cramped forehead hair strip into full 3D volumetric hair:
  A. Sculpted 3D Scalp Crown Dome on Face-VB & Face_lodL-VB (raises/shapes hair-bearing cranium while
     keeping the shaved side/temple skin-fade tight and preserving 0.0000mm neck-seam lock).
  B. Full 3D Procedural Grooming of ALL hair cards in Hair_fix-VB (world-space, e.g. 68 cards / 808 verts)
     and Hair_fix_lodL-VB (HEAD-LOCAL space offset automatically detected from base mesh!) across 4 anatomical zones:
       - Zone 1: Layered overhanging forehead bangs/fringe (inner + outer alpha-sorted layers!)
       - Zone 2: Full volumetric textured top/crown crop tufts across the entire upper cranium
       - Zone 3: Upper-temple / side-top fade-ridge transition cards
       - Zone 4: Upper-back crown / occiput cards tapering into the back fade
  C. Ultra-Crisp Matte 512x512 Hair Strand Diffuse (*_B_hair_*.dds) & Strand Normal Map (*_N_hair_*.dds)
     + Matte-Hair Specular Masking (*_SS_face_*.dds & *_SS_face_sweat_*.dds) killing plastic scalp gloss!

Supports clean --hair-style presets: high_fade_crop, curly_full, swept_top, buzz.
"""
import math
import os
import struct
import sys
import cv2
import numpy as np
from PIL import Image, ImageFilter

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

from build_ee3_rackets import parse_vbs, parse_ibs
from sculpt_sdo_head import (
    _strip_to_tris,
    _find_ib_for_vb,
    _read_vb_xyz_nrm,
    _write_vb_xyz_nrm,
    _recalc_blended_normals,
)
from update_custom_assets import parse_sdo_dds_slots, extract_slot_image, replace_sdo_tex


HAIR_STYLE_PRESETS = {
    "high_fade_crop": {
        "scalp_top_dy": 0.045,       # Gently rounded athletic crown (NO tall flat-top box!)
        "scalp_front_dz": 0.052,     # Crisp slanted forward-down bangs base above forehead
        "scalp_side_top_dx": -0.018, # Taper upper side corners inward into natural rounded dome!
        "scalp_back_dz": -0.020,     # Smoothly tapered upper-back crown curving into occiput
        "bang_overhang_dz": 0.078,   # Crisp slanted forward-downward French-crop bangs wedge
        "bang_drop_dy": -0.155,      # Hugs upper forehead cleanly
        "crown_loft": 0.038,         # Natural textured 3D crop tufts hugging rounded silhouette
        "card_len_scale": 0.80,
        "card_wid_scale": 1.15,
        "sweep_x": 0.036,            # Subtle organic right-to-left crop sweep
    },
    "curly_full": {
        "scalp_top_dy": 0.210,
        "scalp_front_dz": 0.105,
        "scalp_side_top_dx": 0.095,
        "scalp_back_dz": -0.095,
        "bang_overhang_dz": 0.130,
        "bang_drop_dy": -0.155,
        "crown_loft": 0.135,
        "card_len_scale": 1.10,
        "card_wid_scale": 1.30,
        "sweep_x": 0.030,
    },
    "swept_top": {
        "scalp_top_dy": 0.165,
        "scalp_front_dz": 0.055,
        "scalp_side_top_dx": 0.055,
        "scalp_back_dz": -0.060,
        "bang_overhang_dz": 0.085,
        "bang_drop_dy": -0.055,
        "crown_loft": 0.105,
        "card_len_scale": 0.98,
        "card_wid_scale": 1.18,
        "sweep_x": 0.110,
    },
    "buzz": {
        "scalp_top_dy": 0.030,
        "scalp_front_dz": 0.018,
        "scalp_side_top_dx": 0.010,
        "scalp_back_dz": -0.015,
        "bang_overhang_dz": 0.025,
        "bang_drop_dy": -0.025,
        "crown_loft": 0.022,
        "card_len_scale": 0.60,
        "card_wid_scale": 0.85,
        "sweep_x": 0.0,
    },
}


def _smoothstep(e0: float, e1: float, x: float) -> float:
    if e1 == e0:
        return 1.0 if x >= e1 else 0.0
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


def sculpt_scalp_crown_dome(
    face_xyz: np.ndarray,
    style: str = "high_fade_crop",
    target_top_y_fn=None,
) -> np.ndarray:
    """Step A (v8 Silhouette-Locked): Sculpt naturally rounded 3D hair-bearing crown dome on Face-VB / Face_lodL-VB.
    - Eliminates boxy flat-top corners (smoothly rounds upper |X| sides inward into an athletic dome).
    - When `target_top_y_fn(z)` is provided from the real 90-deg profile silhouette, smoothly conforms the upper
      scalp crown right underneath `target_top_y_fn(z) - 0.035 dm` so the 3D hair cards sit dead-on the real profile!
    - Strictly leaves Y <= 16.90 (and neck Y <= 15.72) 100% untouched (0.0000mm neck seam)."""
    cfg = HAIR_STYLE_PRESETS[style]
    out = face_xyz.copy()

    for i in range(len(out)):
        x, y, z = float(out[i, 0]), float(out[i, 1]), float(out[i, 2])
        if y < 16.92:
            continue

        # Dynamic hairline base height: front forehead hairline ~17.36, temple ~17.32, rear crown ~17.08
        hl_y = 17.36 if z > 0.85 else (17.08 + 0.28 * _smoothstep(-0.25, 0.85, z))
        if y <= hl_y:
            continue

        t_up = _smoothstep(hl_y, hl_y + 0.45, y)
        # Keep sides sleek below the upper fade ridge (Y < 17.44 at |X| > 0.56)
        side_fade_gate = 1.0 - 0.86 * _smoothstep(0.50, 0.74, abs(x)) * (1.0 - _smoothstep(17.42, 17.72, y))

        # Gently rounded athletic dome (strong cosine dome taper across |X| -> ZERO flat-top square corners!)
        t_dome_x = max(0.0, 1.0 - 0.78 * ((abs(x) / 0.76) ** 1.65))
        # Natural forward-sloping front crown (lower over forehead Z>0.9, peaking gently at mid-crown Z~0.25!)
        t_crown_z = math.exp(-0.5 * ((z - 0.22) / 0.62) ** 2)

        if target_top_y_fn is not None and style == "high_fade_crop":
            # Target scalp ceiling sits 5.5mm underneath real outer hair silhouette so 3D cards fill exact silhouette
            # with a natural rounded front dome matching BOTH profile_neutral.jpg & front_neutral.jpg!
            y_sil = float(target_top_y_fn(z))
            dome_side_drop = 0.28 * ((abs(x) / 0.72) ** 2.0)
            y_ceil = y_sil - 0.055 - dome_side_drop
            dy_sil = (y_ceil - y) * _smoothstep(17.44, 17.86, y) * side_fade_gate
            dy = float(np.clip(dy_sil, -0.22, 0.06))
        else:
            dy = cfg["scalp_top_dy"] * t_up * t_dome_x * (0.45 + 0.55 * t_crown_z) * side_fade_gate

        # Round upper-side corners gently INWARD (negative dx on high_fade_crop -> kills boxy top corners!)
        t_corner_y = _smoothstep(17.52, 17.92, y)
        t_corner_x = _smoothstep(0.30, 0.72, abs(x))
        dx = (1.0 if x >= 0 else -1.0) * cfg["scalp_side_top_dx"] * t_corner_y * t_corner_x

        # Slanted forward-downward bangs base right at upper forehead hairline (Y in 17.36..17.64),
        # tapering BACK cleanly higher up (Y > 17.70) to form Alcaraz's real ~35-deg slanted front crop profile!
        t_bang_base = _smoothstep(0.75, 1.28, z) * _smoothstep(17.34, 17.50, y) * (1.0 - _smoothstep(17.56, 17.82, y))
        t_front_tuck = _smoothstep(0.65, 1.20, z) * _smoothstep(17.64, 17.96, y)
        t_back = _smoothstep(0.00, -0.48, z) * _smoothstep(17.16, 17.62, y)
        dz = cfg["scalp_front_dz"] * t_bang_base - 0.085 * t_front_tuck + cfg["scalp_back_dz"] * t_back

        out[i, 0] = x + dx
        out[i, 1] = y + dy
        out[i, 2] = z + dz

    return out


def _extract_hair_cards(dec: bytes, vb: dict, ib: dict):
    """Extract connected hair card components and compute each vertex's normalized (s, t) ribbon coordinates:
      s in [-1..+1] across card width, t in [0..1] from 0=root to 1=feathered tip!"""
    s0 = vb["streams"][0]
    base = vb["data_off"] + s0["off"]
    st = s0["stride"]
    nv = s0["nverts"]
    pts = np.array([struct.unpack_from(">3f", dec, base + i * st) for i in range(nv)], dtype=np.float32)
    uvs = np.array(
        [(u / 65536.0 + 0.5, v / 65536.0 + 0.5) for u, v in (struct.unpack_from(">2h", dec, base + i * st + 20) for i in range(nv))],
        dtype=np.float32,
    )
    tris = _strip_to_tris(ib["inds"])

    parent = list(range(nv))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b, c in tris:
        ra, rb, rc = find(a), find(b), find(c)
        parent[rb] = ra
        parent[rc] = ra

    comp_map = {}
    for i in range(nv):
        comp_map.setdefault(find(i), []).append(i)

    # Sort components by their FIRST triangle appearance in IB (preserves DX9 painter draw order!)
    first_tri_pos = {}
    for ti, (a, b, c) in enumerate(tris):
        r = find(a)
        if r not in first_tri_pos:
            first_tri_pos[r] = ti

    cards = []
    for root in sorted(comp_map.keys(), key=lambda r: first_tri_pos.get(r, 999999)):
        vs = comp_map[root]
        cuv = uvs[vs]
        umin, umax = float(cuv[:, 0].min()), float(cuv[:, 0].max())
        vmin, vmax = float(cuv[:, 1].min()), float(cuv[:, 1].max())
        umean = 0.5 * (umin + umax)
        vmean = 0.5 * (vmin + vmax)
        uspan = max(1e-4, umax - umin)
        vspan = max(1e-4, vmax - vmin)

        st_coords = {}
        for vi in vs:
            u, v = float(uvs[vi, 0]), float(uvs[vi, 1])
            if vmean < 0.41:
                # Top row clumps: root at V_max (~0.36), feathered tips at V_min (~0.0)
                t = (vmax - v) / vspan
                s = 2.0 * (u - umean) / uspan
            elif umean < 0.67:
                # Bottom-left clumps: root at V_min (~0.45), feathered tips at V_max (~0.99)
                t = (v - vmin) / vspan
                s = 2.0 * (u - umean) / uspan
            else:
                # Bottom-right horizontal clumps: root at U_min (~0.68), feathered tips at U_max (~0.99)
                t = (u - umin) / uspan
                s = 2.0 * (v - vmean) / vspan
            st_coords[vi] = (float(np.clip(s, -1.0, 1.0)), float(np.clip(t, 0.0, 1.0)))
        cards.append({"verts": vs, "st": st_coords})
    return pts, uvs, cards


def _surface_point_on_scalp(scalp_pts: np.ndarray, head_center: np.ndarray, direction: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Find the exact 3D anchor point & outward surface normal on the sculpted Face-VB crown dome along `direction`."""
    d = direction / (np.linalg.norm(direction) + 1e-8)
    rel = scalp_pts - head_center[None, :]
    rlen = np.linalg.norm(rel, axis=1) + 1e-8
    dots = (rel @ d) / rlen
    top_k = np.argpartition(dots, -12)[-12:]
    # Weighted average by high alignment power
    w = np.maximum(0.0, dots[top_k] - 0.85) ** 4 + 1e-6
    w /= w.sum()
    anchor = (scalp_pts[top_k] * w[:, None]).sum(axis=0)
    out_n = anchor - head_center
    out_n /= (np.linalg.norm(out_n) + 1e-8)
    return anchor, out_n


def _build_card_layout(n_cards: int, style: str = "high_fade_crop"):
    """Build DX9-alpha-sorted placement specs (inner/lower layers FIRST -> outer/upper silhouette tips LAST!)
    across 4 anatomical zones covering the entire 3D crown, bangs, temples, and upper-back!"""
    cfg = HAIR_STYLE_PRESETS[style]
    # Scale zone counts cleanly for both LOD0 (68 cards) and LODL (40 cards)
    n_bangs = max(8, round(n_cards * 24 / 68))
    n_temples = max(4, round(n_cards * 10 / 68))
    if n_temples % 2 == 1:
        n_temples += 1
    n_back = max(4, round(n_cards * 8 / 68))
    n_crown = max(4, n_cards - n_bangs - n_temples - n_back)

    rng = np.random.default_rng(20260422)
    specs = []

    # Helper to create a structured card spec:
    # (layer_order, zone, dir_vec, grow_dir, width, length, loft_root, loft_mid, loft_tip, cup_depth)
    # layer_order 0 = inner base layer (drawn FIRST), 1 = mid volume, 2 = outer silhouette tips (drawn LAST!)

    # --- LAYER 0 (INNER BASE FOUNDATION — DRAWN FIRST) ---
    n_bang_in = n_bangs // 2
    n_bang_out = n_bangs - n_bang_in
    for k in range(n_bang_in):
        u = -1.0 + 2.0 * (k + 0.5) / n_bang_in
        ang_x = u * 0.52
        edge_taper = 0.78 + 0.22 * (1.0 - abs(u))
        dir_v = np.array([math.sin(ang_x) * 0.68, 0.49 + 0.06 * (1.0 - abs(u)), math.cos(ang_x) * 0.91], dtype=np.float32)
        grow = np.array([cfg["sweep_x"] * 1.4 + 0.04 * u + rng.uniform(-0.05, 0.05), -0.94, 0.38], dtype=np.float32)
        specs.append((0, "bang_in", dir_v, grow, 0.148 * cfg["card_wid_scale"] * edge_taper, 0.30 * cfg["card_len_scale"] * edge_taper, -0.010, 0.030, 0.022, 0.015))

    n_crown_in = n_crown // 2
    n_crown_out = n_crown - n_crown_in
    for k in range(n_crown_in):
        row = k % 4
        col = k // 4
        nrows = max(1, (n_crown_in + 3) // 4)
        fz = -0.34 + 0.96 * (col + 0.5) / nrows + rng.uniform(-0.05, 0.05)
        fx = (-0.54 + 1.08 * (row + 0.5) / 4.0) * (1.0 - 0.22 * abs(fz)) + rng.uniform(-0.04, 0.04)
        fy = math.sqrt(max(0.22, 1.0 - min(0.78, fx * fx + fz * fz * 0.55)))
        dir_v = np.array([fx, fy, fz], dtype=np.float32)
        grow = np.array([cfg["sweep_x"] * 1.4 + rng.uniform(-0.14, 0.14), 0.08, 0.95], dtype=np.float32)
        specs.append((0, "crown_in", dir_v, grow, 0.185 * cfg["card_wid_scale"], 0.26 * cfg["card_len_scale"], -0.010, 0.036, 0.030, 0.018))

    # --- LAYER 1 (MID VOLUME — TEMPLES & BACK CROWN HUGGING ROUNDED DOME) ---
    half_t = n_temples // 2
    for side in (-1.0, 1.0):
        for k in range(half_t):
            tz = 0.06 + 0.68 * (k + 0.5) / half_t
            dir_v = np.array([side * 0.78, 0.60 + 0.10 * (k / max(1, half_t)), tz], dtype=np.float32)
            grow = np.array([side * 0.04, -0.32, 0.92], dtype=np.float32)
            specs.append((1, "temple", dir_v, grow, 0.130 * cfg["card_wid_scale"], 0.21 * cfg["card_len_scale"], -0.012, 0.022, 0.016, 0.012))

    for k in range(n_back):
        u = -0.56 + 1.12 * (k + 0.5) / n_back
        dir_v = np.array([u, 0.62 + 0.14 * (1.0 - abs(u)), -0.70], dtype=np.float32)
        grow = np.array([u * 0.10 + rng.uniform(-0.06, 0.06), -0.92, -0.18], dtype=np.float32)
        specs.append((1, "back", dir_v, grow, 0.175 * cfg["card_wid_scale"], 0.24 * cfg["card_len_scale"], -0.012, 0.026, 0.015, 0.014))

    # --- LAYER 2 (OUTER SILHOUETTE VOLUMETRIC TUFTS & CURVED TEXTURED BANGS — DRAWN LAST!) ---
    for k in range(n_crown_out):
        row = k % 4
        col = k // 4
        nrows = max(1, (n_crown_out + 3) // 4)
        fz = -0.36 + 1.04 * (col + 0.5) / nrows + rng.uniform(-0.06, 0.06)
        fx = (-0.58 + 1.16 * (row + 0.5) / 4.0) * (1.0 - 0.20 * abs(fz)) + rng.uniform(-0.05, 0.05)
        fy = math.sqrt(max(0.20, 1.0 - min(0.80, fx * fx + fz * fz * 0.55)))
        dir_v = np.array([fx, fy, fz], dtype=np.float32)
        grow = np.array([cfg["sweep_x"] * 2.0 + rng.uniform(-0.18, 0.18), 0.14 + rng.uniform(-0.06, 0.10), 0.94], dtype=np.float32)
        loft = cfg["crown_loft"] * (0.85 + 0.28 * rng.random())
        specs.append((2, "crown_out", dir_v, grow, 0.190 * cfg["card_wid_scale"], 0.27 * cfg["card_len_scale"], 0.002, loft * 0.92, loft * 0.72, 0.020))

    for k in range(n_bang_out):
        u = -1.0 + 2.0 * (k + 0.5) / n_bang_out
        ang_x = u * 0.54
        edge_taper = 0.76 + 0.24 * (1.0 - abs(u))
        dir_v = np.array([math.sin(ang_x) * 0.69, 0.55 + 0.06 * (1.0 - abs(u)), math.cos(ang_x) * 0.89], dtype=np.float32)
        overhang = cfg["bang_overhang_dz"] * (0.88 + 0.22 * (1.0 - 0.35 * abs(u))) * edge_taper
        # Natural curved French-crop bangs: arch forward at root/mid then curve DOWNWARD smoothly over forehead!
        grow = np.array([cfg["sweep_x"] * 1.8 + 0.04 * u + rng.uniform(-0.06, 0.06), -0.92, 0.44], dtype=np.float32)
        specs.append((2, "bang_out", dir_v, grow, 0.155 * cfg["card_wid_scale"] * edge_taper, 0.32 * cfg["card_len_scale"] * edge_taper, 0.006, overhang * 0.90, overhang * 0.46, 0.016))

    assert len(specs) == n_cards, f"Spec count mismatch: {len(specs)} vs {n_cards}"
    specs.sort(key=lambda s: s[0])
    return specs


def groom_hair_cards_vb(
    dec_ba: bytearray,
    base_dec: bytes,
    vb_name: str,
    sculpted_face_xyz: np.ndarray,
    style: str = "high_fade_crop",
    head_local_offset: np.ndarray | None = None,
    target_top_y_fn=None,
) -> np.ndarray:
    """Step B (v8 Silhouette-Locked): Redistribute & 3D-sculpt ALL hair cards in Hair_fix-VB or Hair_fix_lodL-VB
    across 4 zones in strict inner->outer DX9 painter order, clamped smoothly to `target_top_y_fn(z)` so the 3D hair
    never bulges into a tall square box and locks cleanly onto the real 90-deg profile & rounded front dome!"""
    base_vbs = {v["short_name"]: v for v in parse_vbs(base_dec)}
    base_ibs = {ib["short_name"]: ib for ib in parse_ibs(base_dec)}
    tgt_vbs = {v["short_name"]: v for v in parse_vbs(dec_ba)}
    tgt_ibs = {ib["short_name"]: ib for ib in parse_ibs(dec_ba)}

    if vb_name not in tgt_vbs:
        return np.zeros((0, 3), dtype=np.float32)

    bvb = base_vbs[vb_name]
    bib = _find_ib_for_vb(base_ibs, vb_name)
    tvb = tgt_vbs[vb_name]
    tib = _find_ib_for_vb(tgt_ibs, vb_name)

    _, _, cards = _extract_hair_cards(base_dec, bvb, bib)
    _, orig_nrm = _read_vb_xyz_nrm(base_dec, bvb)

    # Scalp surface points (upper head Y > 17.00) & head center for spherical projection
    scalp_pts = sculpted_face_xyz[sculpted_face_xyz[:, 1] > 16.95]
    head_center = np.array([0.0, 17.05, 0.38], dtype=np.float32)

    specs = _build_card_layout(len(cards), style=style)
    new_xyz = np.zeros((bvb["streams"][0]["nverts"], 3), dtype=np.float32)
    new_nrm_f = np.zeros((bvb["streams"][0]["nverts"], 3), dtype=np.float32)

    for card, spec in zip(cards, specs):
        _, zone, dir_v, grow_raw, width, length, loft_root, loft_mid, loft_tip, cup_depth = spec
        anchor, out_n = _surface_point_on_scalp(scalp_pts, head_center, dir_v)

        # Build orthonormal frame (side_vec, grow_vec, out_n) tangent to scalp
        grow = grow_raw / (np.linalg.norm(grow_raw) + 1e-8)
        side_v = np.cross(out_n, grow)
        if np.linalg.norm(side_v) < 1e-4:
            side_v = np.cross(out_n, np.array([1.0, 0.0, 0.0], dtype=np.float32))
        side_v /= (np.linalg.norm(side_v) + 1e-8)
        tan_g = np.cross(side_v, out_n)
        tan_g /= (np.linalg.norm(tan_g) + 1e-8)
        if float(np.dot(tan_g, grow)) < 0.0:
            tan_g = -tan_g
            side_v = -side_v

        for vi in card["verts"]:
            s, t = card["st"][vi]
            loft = (1.0 - t) * (1.0 - t) * loft_root + 2.0 * (1.0 - t) * t * loft_mid + t * t * loft_tip
            cup = -cup_depth * (s * s)
            if zone.startswith("bang"):
                # Slanted forward-downward French-crop bangs wedge (natural taper, zero flat vertical wall!)
                p = (
                    anchor
                    + tan_g * (t * length * 0.90)
                    + np.array([0.0, -0.055 * (t * t), 0.036 * math.sin(t * math.pi)], dtype=np.float32)
                    + side_v * (s * width * (0.94 - 0.14 * t))
                    + out_n * (loft + cup)
                )
            else:
                p = (
                    anchor
                    + tan_g * (t * length)
                    + side_v * (s * width * (1.0 - 0.14 * t))
                    + out_n * (loft + cup)
                )

            # Enforce exact profile silhouette ceiling & natural rounded front dome (matches front_neutral.jpg & profile_neutral.jpg!)
            if target_top_y_fn is not None and style == "high_fade_crop":
                y_sil = float(target_top_y_fn(float(p[2])))
                y_max_allowed = y_sil - 0.012 - 0.28 * ((abs(float(p[0])) / 0.72) ** 2.0)
                if p[1] > y_max_allowed:
                    p[1] = y_max_allowed

            if head_local_offset is not None:
                p = p + head_local_offset
            new_xyz[vi] = p
            n_dir = out_n * 0.85 + side_v * (0.28 * s) + tan_g * (0.12 * (t - 0.5))
            n_dir /= (np.linalg.norm(n_dir) + 1e-8)
            new_nrm_f[vi] = n_dir

    xyz_list = [tuple(map(float, r)) for r in new_xyz]
    nrm_list = []
    for i in range(len(new_xyz)):
        nx, ny, nz = new_nrm_f[i]
        nw = orig_nrm[i][3]
        nrm_list.append((int(round(nx * 16384.0)), int(round(ny * 16384.0)), int(round(nz * 16384.0)), int(nw)))
    _write_vb_xyz_nrm(dec_ba, tvb, xyz_list, nrm_list)
    return new_xyz


def synthesize_crisp_hair_textures(
    base_hair_rgba: Image.Image,
    hair_rgb: tuple[int, int, int] = (24, 21, 19),
) -> tuple[Image.Image, Image.Image]:
    """Step C: Paint ultra-crisp matte espresso-black hair strands (512x512 RGBA) + matching tangent-space
    strand normal map (512x512 RGBA), eliminating Djokovic's muddy green/olive DXT blotches!"""
    orig = np.array(base_hair_rgba.convert("RGBA"))
    H, W = orig.shape[:2]
    orig_lum = (0.299 * orig[:, :, 0] + 0.587 * orig[:, :, 1] + 0.114 * orig[:, :, 2]) / 255.0
    orig_a = orig[:, :, 3].astype(np.float32) / 255.0

    # Synthesize crisp directional high-frequency hair strand micro-detail matching each UV clump's orientation:
    # Top row & bottom-left have vertical strands; bottom-right (x > 0.67*W, y > 0.40*H) has horizontal strands!
    # Synthesize crisp multi-frequency espresso hair strands (fine filaments + grouped lock highlights!)
    rng = np.random.default_rng(20261122)
    noise_v = rng.normal(0.0, 1.0, (H // 8, W)).astype(np.float32)
    strand_v = cv2.resize(noise_v, (W, H), interpolation=cv2.INTER_CUBIC)
    strand_v = cv2.GaussianBlur(strand_v, (3, 19), 0.7, 6.0)
    fine_v = cv2.GaussianBlur(rng.normal(0.0, 1.0, (H, W)).astype(np.float32), (1, 15), 0.3, 4.5)

    noise_h = rng.normal(0.0, 1.0, (H, W // 8)).astype(np.float32)
    strand_h = cv2.resize(noise_h, (W, H), interpolation=cv2.INTER_CUBIC)
    strand_h = cv2.GaussianBlur(strand_h, (19, 3), 6.0, 0.7)
    fine_h = cv2.GaussianBlur(rng.normal(0.0, 1.0, (H, W)).astype(np.float32), (15, 1), 4.5, 0.3)

    yy, xx = np.mgrid[0:H, 0:W]
    is_horiz = (xx >= int(W * 0.67)) & (yy >= int(H * 0.40))
    strand = np.where(is_horiz, strand_h * 0.72 + fine_h * 0.48, strand_v * 0.72 + fine_v * 0.48)
    strand = np.clip(strand * 0.78, -0.62, 0.78)

    # Rich readable warm dark espresso-brown strand separation seamlessly matching Nano Banana scalp (zero gray streaks!)
    rel_l = np.clip(orig_lum / 0.16, 0.45, 1.65)
    mod = np.clip(0.62 + 0.45 * rel_l + 0.55 * strand, 0.48, 1.85)
    hr, hg, hb = hair_rgb
    new_rgb = np.stack([
        np.clip(hr * mod, 18, 60),
        np.clip(hg * mod, 15, 52),
        np.clip(hb * mod, 13, 46),
    ], axis=-1).astype(np.uint8)

    # Slightly enrich alpha fullness (+18% mid-alpha density) so 3D crop looks thick & lush without harsh edges!
    new_a = np.clip(np.power(orig_a, 0.82) * 255.0, 0, 255).astype(np.uint8)
    diffuse_pil = Image.fromarray(np.dstack([new_rgb, new_a]), mode="RGBA")

    # Synthesize crisp tangent-space strand normal map from strand height field!
    h_field = (0.65 * orig_a + 0.35 * np.clip(0.5 + strand, 0.0, 1.0)) * 255.0
    gx = cv2.Sobel(h_field.astype(np.float32), cv2.CV_32F, 1, 0, ksize=3) * 0.38
    gy = cv2.Sobel(h_field.astype(np.float32), cv2.CV_32F, 0, 1, ksize=3) * 0.38
    nx = np.clip(128.0 - gx, 40, 216)
    ny = np.clip(128.0 - gy, 40, 216)
    nz = np.full_like(nx, 245.0)
    # IMPORTANT: In VT4 DX9, *_N_hair_*.dds Alpha is SPECULAR INTENSITY (SEGA mean = 7.2 for matte hair)!
    # Setting Alpha=255 would cause mirror-plastic hair cards; keep matte 5..11 modulated subtly by strand density!
    spec_a = np.clip(5.0 + 6.0 * orig_a, 4, 12).astype(np.uint8)
    normal_rgba = np.dstack([nx.astype(np.uint8), ny.astype(np.uint8), nz.astype(np.uint8), spec_a])
    normal_pil = Image.fromarray(normal_rgba, mode="RGBA")
    return diffuse_pil, normal_pil


def build_matte_hair_specular_map(
    orig_ss_rgba: Image.Image,
    baked_face_rgb: np.ndarray,
) -> Image.Image:
    """Build VT4 SS_face subsurface-scattering & matte-hair map (256x256):
    In VT4 DX9, SS_face RGB encodes warm reddish-peach skin subsurface scatter (~[135, 68, 51] on lit skin),
    while scalp/fade/brows must be near-zero matte (~[6, 5, 4]) to kill plastic scalp shine!"""
    w, h = orig_ss_rgba.size
    orig_arr = np.array(orig_ss_rgba.convert("RGBA")).astype(np.float32)
    face_s = cv2.resize(baked_face_rgb, (w, h), interpolation=cv2.INTER_AREA)
    flum = (0.299 * face_s[:, :, 0] + 0.587 * face_s[:, :, 1] + 0.114 * face_s[:, :, 2]) / 255.0

    yy, xx = np.mgrid[0:h, 0:w]
    u = xx / float(w)
    v = yy / float(h)

    # Matte scalp & high-fade mask: top scalp (v < 0.28) + temple/side/back fade (u < 0.29 or u > 0.71, v < 0.62)
    scalp_m = np.clip((0.285 - v) / 0.055, 0.0, 1.0)
    side_fade_m = np.clip((0.295 - np.minimum(u, 1.0 - u)) / 0.065, 0.0, 1.0) * np.clip((0.62 - v) / 0.12, 0.0, 1.0)
    # Exclude ear skin islands (u in 0.12..0.22 or 0.78..0.88, v in 0.35..0.55) from scalp matte
    ear_l = ((u - 0.168) / 0.055) ** 2 + ((v - 0.455) / 0.105) ** 2
    ear_r = ((u - 0.832) / 0.055) ** 2 + ((v - 0.455) / 0.105) ** 2
    is_ear = np.clip(1.2 - np.minimum(ear_l, ear_r), 0.0, 1.0)

    # Dark eyebrow & heavy hair pixels (low luminance inside face) also get matte zero-SSS!
    dark_hair_m = np.clip((0.34 - flum) / 0.14, 0.0, 1.0)
    matte_mask = np.clip(np.maximum(np.maximum(scalp_m, side_fade_m) * (1.0 - is_ear), dark_hair_m), 0.0, 1.0)
    matte_mask = cv2.GaussianBlur(matte_mask.astype(np.float32), (11, 11), 3.0)

    # Healthy warm reddish-peach skin SSS on face/ears/neck (preserves luminous warm skin under DX9 Filmic!)
    skin_r = np.maximum(orig_arr[:, :, 0], 132.0)
    skin_g = np.maximum(orig_arr[:, :, 1], 66.0)
    skin_b = np.maximum(orig_arr[:, :, 2], 50.0)

    out_r = np.clip(skin_r * (1.0 - matte_mask) + 6.0 * matte_mask, 4, 165).astype(np.uint8)
    out_g = np.clip(skin_g * (1.0 - matte_mask) + 5.0 * matte_mask, 4, 95).astype(np.uint8)
    out_b = np.clip(skin_b * (1.0 - matte_mask) + 4.0 * matte_mask, 3, 75).astype(np.uint8)
    orig_a = orig_arr[:, :, 3]
    out_a = np.clip(orig_a * (1.0 - 0.25 * matte_mask) + 185.0 * (0.25 * matte_mask), 120, 245).astype(np.uint8)
    return Image.fromarray(np.dstack([out_r, out_g, out_b, out_a]), mode="RGBA")


def groom_3d_hair(
    target_dec: bytearray,
    base_dec: bytes,
    sculpted_face_xyz: np.ndarray,
    style: str = "high_fade_crop",
    hair_rgb: tuple[int, int, int] = (38, 33, 29),
    inject_textures: bool = True,
    target_top_y_fn=None,
) -> dict:
    """Full end-to-end 3D Hair Groom on target_dec (world-space Hair_fix-VB + head-local Hair_fix_lodL-VB + hair DDS)."""
    base_vbs = {v["short_name"]: v for v in parse_vbs(base_dec)}
    base_slots = {s["name"]: s for s in parse_sdo_dds_slots(base_dec)}
    tgt_slots = {s["name"]: s for s in parse_sdo_dds_slots(target_dec)}

    # Detect exact head-local offset of Hair_fix_lodL-VB automatically!
    lod_offset = None
    if "Hair_fix-VB" in base_vbs and "Hair_fix_lodL-VB" in base_vbs:
        h0_xyz, _ = _read_vb_xyz_nrm(base_dec, base_vbs["Hair_fix-VB"])
        hl_xyz, _ = _read_vb_xyz_nrm(base_dec, base_vbs["Hair_fix_lodL-VB"])
        h0_np = np.array(h0_xyz, dtype=np.float32)
        hl_np = np.array(hl_xyz, dtype=np.float32)
        # If Hair_fix_lodL-VB Y max is < 5.0 while Hair_fix-VB Y max > 12.0, it is in head-local space!
        if hl_np[:, 1].max() < 5.0 and h0_np[:, 1].max() > 12.0:
            lod_offset = np.array([
                0.0,
                float(hl_np[:, 1].max() - h0_np[:, 1].max()),
                float(hl_np[:, 2].max() - h0_np[:, 2].max()),
            ], dtype=np.float32)

    groomed_lod0 = groom_hair_cards_vb(
        target_dec, base_dec, "Hair_fix-VB", sculpted_face_xyz, style=style, head_local_offset=None, target_top_y_fn=target_top_y_fn
    )
    groomed_lodl = groom_hair_cards_vb(
        target_dec, base_dec, "Hair_fix_lodL-VB", sculpted_face_xyz, style=style, head_local_offset=lod_offset, target_top_y_fn=target_top_y_fn
    )

    # Synthesize crisp matte hair diffuse & strand normal maps
    base_hair_name = [k for k in base_slots if "_B_hair_" in k][0]
    base_hair_im = extract_slot_image(base_dec, base_slots[base_hair_name]).convert("RGBA")
    hair_diff_pil, hair_norm_pil = synthesize_crisp_hair_textures(base_hair_im, hair_rgb=hair_rgb)

    if inject_textures:
        for sname, sl in tgt_slots.items():
            if "_B_hair_" in sname:
                replace_sdo_tex(target_dec, sl, hair_diff_pil)
            elif "_N_hair_" in sname:
                replace_sdo_tex(target_dec, sl, hair_norm_pil)

    return {
        "lod0_xyz": groomed_lod0,
        "lodl_xyz": groomed_lodl,
        "lod_offset": lod_offset,
        "hair_diff_pil": hair_diff_pil,
        "hair_norm_pil": hair_norm_pil,
    }


if __name__ == "__main__":
    # Standalone visual smoke-test of Full 3D Hair Groom on Alcaraz v4 base!
    sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))
    import photo_to_vt4_head as p2v

    base_dec = open(os.path.join(REPO_ROOT, "scratch", "real_alcaraz_3d", "P_M_DJV_IT_base_dec.bin"), "rb").read()
    work_dec = bytearray(base_dec)
    vbs = {v["short_name"]: v for v in parse_vbs(work_dec)}
    ibs = {ib["short_name"]: ib for ib in parse_ibs(work_dec)}
    slots = {s["name"]: s for s in parse_sdo_dds_slots(work_dec)}

    fxyz, fnrm, _ = p2v.load_mesh_data(work_dec, vbs["Face-VB"])
    fxyz_crown = sculpt_scalp_crown_dome(fxyz, style="high_fade_crop")
    res = groom_3d_hair(work_dec, base_dec, fxyz_crown, style="high_fade_crop", hair_rgb=(24, 21, 19), inject_textures=False)
    print(f"Groomed LOD0={len(res['lod0_xyz'])} verts, LODL={len(res['lodl_xyz'])} verts, lod_offset={res['lod_offset']}")

    uv_v4 = np.array(Image.open(os.path.join(REPO_ROOT, "scratch", "real_alcaraz_3d", "baked_alcaraz_uv_v4.png")).convert("RGB"))
    eye_tex = np.array(extract_slot_image(work_dec, slots["P_DJV_B_eye_IT.dds"]).convert("RGB"))
    hair_rgba = np.array(res["hair_diff_pil"].convert("RGBA"))
    res["hair_diff_pil"].save(os.path.join(REPO_ROOT, "scratch", "real_alcaraz_3d", "groomed_hair_diffuse_512.png"))

    views = []
    for ang, lbl in [(0.0, "3D Hair Groom: Front"), (38.0, "3D Hair Groom: 3/4"), (90.0, "3D Hair Groom: Left Profile"), (180.0, "3D Hair Groom: Back")]:
        im, _, _ = p2v.render_ortho_head(
            work_dec, vbs, ibs, fxyz_crown, uv_v4, eye_tex, hair_rgba,
            hair_xyz=res["lod0_xyz"], face_nrm_override=fnrm, yaw_deg=ang, shade=True
        )
        cv2.rectangle(im, (0, 0), (1024, 44), (16, 18, 24), -1)
        cv2.putText(im, lbl, (16, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (110, 255, 165), 2)
        views.append(im)
    sheet = np.vstack([np.hstack([views[0], views[1]]), np.hstack([views[2], views[3]])])
    out_p = os.path.join(REPO_ROOT, "scratch", "real_alcaraz_3d", "hair3d_groom_smoke_test.png")
    Image.fromarray(sheet).save(out_p)
    print(f"Saved {out_p}")
