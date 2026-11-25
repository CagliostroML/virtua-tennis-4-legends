#!/usr/bin/env python3
"""UV face-projection, complexion sync, and SDO bone physique scaler for Virtua Tennis 4."""
import math
import re
import struct
from PIL import Image, ImageChops, ImageDraw, ImageFilter


def _solve_3x3(A, b):
    """Solve 3x3 linear system A*x = b via Gaussian elimination."""
    M = [list(map(float, A[i])) + [float(b[i])] for i in range(3)]
    for col in range(3):
        piv = max(range(col, 3), key=lambda r: abs(M[r][col]))
        M[col], M[piv] = M[piv], M[col]
        denom = M[col][col]
        if abs(denom) < 1e-9:
            raise ValueError("Singular landmark triangle")
        for j in range(col, 4):
            M[col][j] /= denom
        for r in range(3):
            if r == col:
                continue
            fac = M[r][col]
            for j in range(col, 4):
                M[r][j] -= fac * M[col][j]
    return [M[i][3] for i in range(3)]


def compute_face_affine(src_pts, dst_pts, max_aspect_ratio: float = 1.22):
    """Map 3 landmarks (eyeL, eyeR, mouth) from dst -> src for PIL Image.transform(AFFINE).

    Blends constrained aspect-safe affine so rotated/tilted photos align eyes & mouth cleanly.
    """
    (sx1, sy1), (sx2, sy2), (sx3, sy3) = src_pts
    (dx1, dy1), (dx2, dy2), (dx3, dy3) = dst_pts

    # Similarity matrix from dst -> src (preserves exact aspect ratio cleanly).
    vx, vy = sx2 - sx1, sy2 - sy1
    ux, uy = dx2 - dx1, dy2 - dy1
    du2 = ux * ux + uy * uy
    if du2 < 1e-6:
        raise ValueError("Degenerate destination eye distance")
    sa = (ux * vx + uy * vy) / du2
    sb = (ux * vy - uy * vx) / du2
    sc_x = sx1 - (sa * dx1 - sb * dy1)
    sd_y = sy1 - (sb * dx1 + sa * dy1)

    # Full 3-point affine from dst -> src.
    A = [[dx1, dy1, 1.0], [dx2, dy2, 1.0], [dx3, dy3, 1.0]]
    ax, bx, cx = _solve_3x3(A, [sx1, sx2, sx3])
    ay, by, cy = _solve_3x3(A, [sy1, sy2, sy3])

    # Clamp extreme vertical stretch vs horizontal eye scale.
    eye_scale = math.hypot(sa, sb)
    vert_scale = math.hypot(ay, by)
    if vert_scale > 1e-6:
        ratio = vert_scale / max(eye_scale, 1e-6)
        if ratio > max_aspect_ratio or ratio < (1.0 / max_aspect_ratio):
            blend = 0.55
            ax = blend * ax + (1.0 - blend) * sa
            bx = blend * bx + (1.0 - blend) * (-sb)
            cx = blend * cx + (1.0 - blend) * sc_x
            ay = blend * ay + (1.0 - blend) * sb
            by = blend * by + (1.0 - blend) * sa
            cy = blend * cy + (1.0 - blend) * sd_y

    return (ax, bx, cx, ay, by, cy)


def _mean_std_region(im_rgb: Image.Image, box: tuple[int, int, int, int]) -> tuple[list[float], list[float]]:
    crop = im_rgb.crop(box)
    px = list(crop.getdata())
    n = max(1, len(px))
    means = [sum(p[c] for p in px) / n for c in range(3)]
    stds = [max(8.0, math.sqrt(sum((p[c] - means[c]) ** 2 for p in px) / n)) for c in range(3)]
    return means, stds


def project_face_onto_uv(
    base_uv: Image.Image,
    src_photo: Image.Image,
    src_pts: tuple,
    dst_pts: tuple,
    eye_preserve: float = 0.92,
    tone_blend: float = 0.55,
    oval_pad: tuple[float, float] = (1.0, 1.0),
    debug_out: str | None = None,
) -> Image.Image:
    """Warp src_photo facial features onto SEGA 1024x1024 face UV without breaking eye sockets."""
    w, h = base_uv.size
    base_rgba = base_uv.convert("RGBA")
    base_rgb = base_rgba.convert("RGB")

    (dx1, dy1), (dx2, dy2), (dx3, dy3) = dst_pts
    eye_cx = 0.5 * (dx1 + dx2)
    eye_cy = 0.5 * (dy1 + dy2)
    eye_sep = max(60.0, math.hypot(dx2 - dx1, dy2 - dy1))
    face_h = max(90.0, dy3 - eye_cy)

    affine = compute_face_affine(src_pts, dst_pts)
    warped = src_photo.convert("RGB").transform((w, h), Image.Transform.AFFINE, affine, resample=Image.Resampling.BICUBIC)

    # Color & luminance harmonization over central cheek/nose skin box.
    sx0 = int(max(0, eye_cx - 0.60 * eye_sep))
    sx1 = int(min(w, eye_cx + 0.60 * eye_sep))
    sy0 = int(max(0, eye_cy + 0.15 * face_h))
    sy1 = int(min(h, eye_cy + 0.72 * face_h))
    bm, bs = _mean_std_region(base_rgb, (sx0, sy0, sx1, sy1))
    wm, ws = _mean_std_region(warped, (sx0, sy0, sx1, sy1))

    # Shift warped RGB toward target base skin luminance & subtle contrast while retaining natural complexion.
    adj = warped.copy()
    apx = adj.load()
    l_base = 0.299 * bm[0] + 0.587 * bm[1] + 0.114 * bm[2]
    l_warp = 0.299 * wm[0] + 0.587 * wm[1] + 0.114 * wm[2]
    for y in range(max(0, int(eye_cy - 1.3 * face_h)), min(h, int(eye_cy + 2.0 * face_h))):
        for x in range(max(0, int(eye_cx - 1.4 * eye_sep)), min(w, int(eye_cx + 1.4 * eye_sep))):
            r, g, b = apx[x, y]
            # Blend luminance target + partial chromatic target so skin blends smoothly at cheeks & jaw.
            nr = (r - wm[0]) * min(1.15, max(0.75, bs[0] / ws[0])) + (1.0 - tone_blend) * wm[0] + tone_blend * bm[0]
            ng = (g - wm[1]) * min(1.15, max(0.75, bs[1] / ws[1])) + (1.0 - tone_blend) * wm[1] + tone_blend * bm[1]
            nb = (b - wm[2]) * min(1.15, max(0.75, bs[2] / ws[2])) + (1.0 - tone_blend) * wm[2] + tone_blend * bm[2]
            # Keep balanced brightness.
            dl = (l_base - l_warp) * 0.18
            apx[x, y] = (
                int(max(0, min(255, nr + dl))),
                int(max(0, min(255, ng + dl))),
                int(max(0, min(255, nb + dl))),
            )

    # Outer facial projection mask (brows, bridge, cheeks, lips, chin/stubble, stopping before outer hair/bg).
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    rx = 0.84 * eye_sep * oval_pad[0]
    top_y = eye_cy - 0.56 * face_h * oval_pad[1]   # eyebrows + lower forehead cleanly
    bot_y = dy3 + 0.52 * face_h * oval_pad[1]      # chin / goatee / jawline cleanly
    md.ellipse([eye_cx - rx, top_y, eye_cx + rx, bot_y], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=24))

    # Preserve SEGA's 3D eyelid/socket region (mask out open photo irises + sclera while keeping brows above).
    if eye_preserve > 0.0:
        sock = Image.new("L", (w, h), 0)
        sd = ImageDraw.Draw(sock)
        erx = 0.30 * eye_sep
        ery = 0.195 * face_h
        cy_off = 0.075 * face_h
        for ex, ey in ((dx1, dy1), (dx2, dy2)):
            sd.ellipse([ex - erx, ey + cy_off - ery, ex + erx, ey + cy_off + ery], fill=int(255 * eye_preserve))
        sock = sock.filter(ImageFilter.GaussianBlur(radius=9))
        mask = ImageChops.subtract(mask, sock)

    comp = Image.composite(adj, base_rgb, mask).convert("RGBA")
    if debug_out:
        comp.convert("RGB").save(debug_out)
    comp.putalpha(base_rgba.getchannel("A"))
    return comp


def scale_sdo_bones(dec_ba: bytearray, bone_scales: dict[str, tuple[float, float, float]]) -> int:
    """Multiply Parameter Scale (sx, sy, sz) inside Scene_Root nodes of a decompressed SDO."""
    p0 = dec_ba.find(b"Scene_Root\x00")
    if p0 < 0:
        return 0
    changed = 0
    for bone_name, (sx, sy, sz) in bone_scales.items():
        bn = bone_name.encode("ascii")
        # Node path ends with either /<BoneName> followed by byte-prefixed <ShortName>\x00
        # e.g. "\x04Node\x18Scene_Root/Reference/Hip\x03Hip\x00" or "\x04Node...\tReference\x00".
        pat = (
            b"\x04Node.{1,150}?"
            + re.escape(bn)
            + b"\x00.{1,180}?Parameter\x05Scale\x07Variant\x02"
        )
        # Iterate all matches; pick exact leaf match (preceded by "/" or length byte <= 24).
        for m in re.finditer(pat, dec_ba[p0:], re.S):
            blk = dec_ba[p0 + m.start() : p0 + m.end()]
            # Verify this match actually ends with "<len><bone_name>\x00" before "\x03\tParameter"
            idx_name = blk.find(bn + b"\x00")
            if idx_name <= 0:
                continue
            # Check no second "\x04Node" occurred inside this block!
            if b"\x04Node" in blk[5:]:
                continue
            pos = p0 + m.end()
            ox, oy, oz = struct.unpack(">3f", dec_ba[pos : pos + 12])
            struct.pack_into(">3f", dec_ba, pos, ox * sx, oy * sy, oz * sz)
            changed += 1
            break
    return changed
