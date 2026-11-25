#!/usr/bin/env python3
"""
Official Grand Slam Stages Overhaul for Virtua Tennis 4: Legends & Next-Gen Edition.

Generates authentic, broadcast-grade 2026 court surfaces, sponsor walls, and screen textures
for all 4 Grand Slams (both Singles *S and Doubles *D variants) as loose files under
game/archive/HIGH/Stage/ (leaving resource*.bin untouched and 100% reversible):

  1. Australian Open (Aus1FS / Aus1FD):
     - Melbourne Royal/Sky Blue inner court + Melbourne Navy apron (preserving "Melbourne" text)
     - Modern Kia, Rolex, Emirates, Ralph Lauren, Yonex, AO Melbourne sponsor boards
  2. Roland Garros (Fra1ES / Fra1ED):
     - Enriched Parisian crushed-brick terracotta clay
     - Philippe-Chatrier dark forest green sponsor tarps (BNP Paribas, Rolex, Emirates, Renault,
       Lacoste, Roland-Garros Paris, Perrier, Babolat)
  3. Wimbledon (Eng1FS / Eng1FD):
     - Lush emerald All England Club grass + heritage deep green & royal purple sponsor wall
       (Rolex, IBM, Slazenger, Ralph Lauren, Barclays, evian, Stella Artois, Wimbledon)
  4. US Open (Usa1NS / Usa1ND):
     - Arthur Ashe Stadium US Open Blue court + vibrant US Open Green apron
     - Replaces "US SUPER TENNIS" & "SPT WORLD CHAMPIONSHIPS" on court and walls with modern
       US OPEN branding + Chase, Emirates, Rolex, IBM, Ralph Lauren, Amex, Wilson
"""
import math
import os
import re
import struct
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

from vt4_archive import BIN0, BIN1, load_directory, read_entry, lzss_decompress
from compress_sega_lzss import lzss_compress_literal
from update_custom_assets import parse_sdo_dds_slots, extract_slot_image


# ---------------------------------------------------------------------------
# Fast Vectorized NumPy BC1 (DXT1) & BC3 (DXT5) Encoder
# ---------------------------------------------------------------------------
def _encode_bc1_blocks_np(rgb_u8: np.ndarray) -> bytes:
    """Encode HxWx3 uint8 array (dims padded/multiple of 4) into BC1/DXT1 bytes."""
    h, w, _ = rgb_u8.shape
    bw, bh = max(1, w // 4), max(1, h // 4)
    # Reshape to (bh*bw, 16, 3)
    blk = rgb_u8.reshape(bh, 4, bw, 4, 3).transpose(0, 2, 1, 3, 4).reshape(-1, 16, 3).astype(np.float32)

    rmin = blk.min(axis=1)  # (N, 3)
    rmax = blk.max(axis=1)  # (N, 3)
    diag = rmax - rmin
    # Project onto diagonal for better endpoints than naive bbox corners
    proj = ((blk - rmin[:, None, :]) * diag[:, None, :]).sum(axis=2)  # (N, 16)
    idx_hi = np.argmax(proj, axis=1)
    idx_lo = np.argmin(proj, axis=1)
    n_idx = np.arange(blk.shape[0])
    c_hi = np.clip(np.rint(blk[n_idx, idx_hi]), 0, 255).astype(np.uint16)
    c_lo = np.clip(np.rint(blk[n_idx, idx_lo]), 0, 255).astype(np.uint16)

    def pack565(c):
        return ((c[:, 0] >> 3) << 11) | ((c[:, 1] >> 2) << 5) | (c[:, 2] >> 3)

    def unpack565(q):
        r = (((q >> 11) & 0x1F) * 255 // 31).astype(np.float32)
        g = (((q >> 5) & 0x3F) * 255 // 63).astype(np.float32)
        b = ((q & 0x1F) * 255 // 31).astype(np.float32)
        return np.stack([r, g, b], axis=-1)

    q0 = pack565(c_hi)
    q1 = pack565(c_lo)
    # Ensure 4-color mode cleanly: if q0 < q1 swap; if q0 == q1 leave q0==q1 and bits=0 (c0<=c1, index 0 = color0)
    swap = q0 < q1
    q0_s = np.where(swap, q1, q0)
    q1_s = np.where(swap, q0, q1)
    q0, q1 = q0_s, q1_s

    # Build 4-color palette (N, 4, 3)
    p0 = unpack565(q0)
    p1 = unpack565(q1)
    p2 = np.floor((2.0 * p0 + p1) / 3.0)
    p3 = np.floor((p0 + 2.0 * p1) / 3.0)
    pal = np.stack([p0, p1, p2, p3], axis=1)  # (N, 4, 3)

    # Distance from each pixel (N,16,3) to each palette entry (N,4,3) -> (N, 16, 4)
    diff = blk[:, :, None, :] - pal[:, None, :, :]
    d2 = (diff * diff).sum(axis=3)
    best = np.argmin(d2, axis=2).astype(np.uint32)  # (N, 16)
    # Where q0 == q1, index 0 maps to color0 in 3-color mode
    eq = (q0 == q1)
    if np.any(eq):
        best[eq] = 0

    shifts = (np.arange(16, dtype=np.uint32) * 2)[None, :]
    bits = np.bitwise_or.reduce(best << shifts, axis=1)

    out = np.empty(blk.shape[0], dtype=np.dtype([("q0", "<u2"), ("q1", "<u2"), ("bits", "<u4")]))
    out["q0"] = q0
    out["q1"] = q1
    out["bits"] = bits
    return out.tobytes()


def _encode_bc3_alpha_np(a_u8: np.ndarray) -> np.ndarray:
    """Encode HxW uint8 alpha array into (N, 8) uint8 BC3 alpha blocks."""
    h, w = a_u8.shape
    bw, bh = max(1, w // 4), max(1, h // 4)
    blk = a_u8.reshape(bh, 4, bw, 4).transpose(0, 2, 1, 3).reshape(-1, 16).astype(np.int32)
    a0 = blk.max(axis=1)
    a1 = blk.min(axis=1)
    n = blk.shape[0]
    out = np.zeros((n, 8), dtype=np.uint8)
    out[:, 0] = a0.astype(np.uint8)
    out[:, 1] = a1.astype(np.uint8)

    diff_mask = a0 > a1
    if np.any(diff_mask):
        idx_d = np.where(diff_mask)[0]
        aa0 = a0[idx_d][:, None]
        aa1 = a1[idx_d][:, None]
        pal = np.stack([
            aa0[:, 0],
            aa1[:, 0],
            (6 * aa0[:, 0] + 1 * aa1[:, 0]) // 7,
            (5 * aa0[:, 0] + 2 * aa1[:, 0]) // 7,
            (4 * aa0[:, 0] + 3 * aa1[:, 0]) // 7,
            (3 * aa0[:, 0] + 4 * aa1[:, 0]) // 7,
            (2 * aa0[:, 0] + 5 * aa1[:, 0]) // 7,
            (1 * aa0[:, 0] + 6 * aa1[:, 0]) // 7,
        ], axis=1)  # (M, 8)
        b_d = blk[idx_d]  # (M, 16)
        best = np.argmin(np.abs(b_d[:, :, None] - pal[:, None, :]), axis=2).astype(np.uint64)  # (M, 16)
        shifts = (np.arange(16, dtype=np.uint64) * 3)[None, :]
        packed = np.bitwise_or.reduce(best << shifts, axis=1)  # (M,) uint64
        for byte_i in range(6):
            out[idx_d, 2 + byte_i] = ((packed >> (byte_i * 8)) & 0xFF).astype(np.uint8)
    return out


def encode_rgba_mips_to_sdo(dec_ba: bytearray, slot: dict, img: Image.Image) -> None:
    """Encode Image into exact DDS mipmap chain inside dec_ba[slot], RGB+A resized separately."""
    w, h, mips, fcc = slot["w"], slot["h"], slot["mips"], slot["fourcc"]
    assert fcc in (b"DXT1", b"DXT5"), f"Unsupported fourcc {fcc}"
    rgba = img.convert("RGBA")
    r0, g0, b0, a0 = rgba.split()
    base_rgb = Image.merge("RGB", (r0, g0, b0))
    if base_rgb.size != (w, h):
        base_rgb = base_rgb.resize((w, h), Image.Resampling.LANCZOS)
        base_a = a0.resize((w, h), Image.Resampling.LANCZOS)
    else:
        base_a = a0

    payload = bytearray()
    mw, mh = w, h
    for _ in range(mips):
        if (mw, mh) == (w, h):
            mrgb, ma = base_rgb, base_a
        else:
            mrgb = base_rgb.resize((mw, mh), Image.Resampling.LANCZOS)
            ma = base_a.resize((mw, mh), Image.Resampling.LANCZOS)

        rgb_arr = np.array(mrgb, dtype=np.uint8)
        a_arr = np.array(ma, dtype=np.uint8)
        # Pad <4x4 mips cleanly by edge replication
        pw = ((mw + 3) // 4) * 4
        ph = ((mh + 3) // 4) * 4
        if pw != mw or ph != mh:
            rgb_arr = np.pad(rgb_arr, ((0, ph - mh), (0, pw - mw), (0, 0)), mode="edge")
            a_arr = np.pad(a_arr, ((0, ph - mh), (0, pw - mw)), mode="edge")

        bc1_bytes = _encode_bc1_blocks_np(rgb_arr)
        if fcc == b"DXT1":
            payload.extend(bc1_bytes)
        else:
            a_blk = _encode_bc3_alpha_np(a_arr)  # (N, 8)
            c_blk = np.frombuffer(bc1_bytes, dtype=np.uint8).reshape(-1, 8)
            combined = np.concatenate([a_blk, c_blk], axis=1)  # (N, 16)
            payload.extend(combined.tobytes())

        mw = max(1, mw // 2)
        mh = max(1, mh // 2)

    expected = slot["total_sz"] - 128
    assert len(payload) == expected, f"Size mismatch for {slot['name']}: {len(payload)} != {expected}"
    p_start = slot["off"] + 128
    dec_ba[p_start : p_start + expected] = payload


# ---------------------------------------------------------------------------
# Typography & Vector Badge Helpers
# ---------------------------------------------------------------------------
def _font(names, size: int):
    for n in names:
        p = os.path.join("C:\\Windows\\Fonts", n)
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


F_SANS_BOLD = lambda sz: _font(["arialbd.ttf", "segoeuib.ttf", "calibrib.ttf"], sz)
F_SERIF_BOLD = lambda sz: _font(["georgiab.ttf", "timesbd.ttf", "cambriab.ttf"], sz)
F_IMPACT = lambda sz: _font(["impact.ttf", "ariblk.ttf", "arialbd.ttf"], sz)


def _draw_centered(draw: ImageDraw.ImageDraw, box, text: str, font, fill=(255, 255, 255), stroke_fill=None, stroke_w=0):
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
    draw.text((cx, cy), text, font=font, fill=fill, anchor="mm", stroke_fill=stroke_fill, stroke_width=stroke_w)


def _fabric_noise(img: Image.Image, amp: float = 3.5, seed: int = 42) -> Image.Image:
    rng = np.random.default_rng(seed)
    arr = np.array(img, dtype=np.float32)
    h, w, _ = arr.shape
    noise = rng.normal(0.0, amp, size=(h, w, 1)).astype(np.float32)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def _draw_star(draw: ImageDraw.ImageDraw, cx, cy, r_out, r_in, fill):
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        r = r_out if i % 2 == 0 else r_in
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    draw.polygon(pts, fill=fill)


def _draw_rolex_crown(draw: ImageDraw.ImageDraw, cx, cy, scale, gold=(222, 184, 78)):
    # 5-pronged crown silhouette
    w = 34 * scale
    h = 24 * scale
    base_y = cy + h * 0.45
    draw.ellipse([cx - w * 0.48, base_y - 4 * scale, cx + w * 0.48, base_y + 4 * scale], fill=gold)
    angles = [-0.85, -0.42, 0.0, 0.42, 0.85]
    for idx, a in enumerate(angles):
        tx = cx + math.sin(a) * w * 0.62
        ty = cy - h * (0.48 if idx == 2 else (0.38 if abs(idx - 2) == 1 else 0.22))
        bw = 4.0 * scale
        draw.polygon([(cx + a * w * 0.28 - bw, base_y), (tx, ty), (cx + a * w * 0.28 + bw, base_y)], fill=gold)
        r = 3.4 * scale
        draw.ellipse([tx - r, ty - r, tx + r, ty + r], fill=gold)


# ---------------------------------------------------------------------------
# 1. Australian Open (Aus1FS / Aus1FD)
# ---------------------------------------------------------------------------
def build_aus1_textures(dec: bytearray, slots: dict) -> list[tuple[str, Image.Image]]:
    previews = []
    # A. Surface_s16 / Surface_d16 -> Melbourne Blue (inner rect + dark navy outer + intact "Melbourne" text & Alpha)
    surf_key = next(k for k in slots if re.search(r"surface_[sd]\d+", k, re.I))
    im_surf = extract_slot_image(dec, slots[surf_key])
    arr = np.array(im_surf, dtype=np.float32)
    r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]
    luma = 0.299 * r + 0.587 * g + 0.114 * b

    # Measure normalized greenness / neutral check so white "Melbourne" text and gray shadows stay crisp
    greenness = g - np.maximum(r, b)
    is_paint = np.clip((greenness - 8.0) / 28.0, 0.0, 1.0)

    # Smooth court boundary mask (measured at x=[562..1488], y=[422..1628] on 2048x2048)
    h, w = r.shape
    yy, xx = np.mgrid[0:h, 0:w]
    in_court = ((xx >= 562) & (xx <= 1488) & (yy >= 422) & (yy <= 1628)).astype(np.float32)

    # Original center luma ~115, apron luma ~138. Scale luma subtly for rich broadcast AO blues
    # Inner court: vibrant Melbourne Sky/Royal Blue ~ (40, 118, 198) at luma~115
    t_inner_r = np.clip(luma * 0.34, 0, 255)
    t_inner_g = np.clip(luma * 1.03, 0, 255)
    t_inner_b = np.clip(luma * 1.72, 0, 255)
    # Apron: deep Melbourne Navy ~ (24, 74, 134) at luma~138
    t_apron_r = np.clip(luma * 0.19, 0, 255)
    t_apron_g = np.clip(luma * 0.56, 0, 255)
    t_apron_b = np.clip(luma * 0.99, 0, 255)

    tgt_r = in_court * t_inner_r + (1.0 - in_court) * t_apron_r
    tgt_g = in_court * t_inner_g + (1.0 - in_court) * t_apron_g
    tgt_b = in_court * t_inner_b + (1.0 - in_court) * t_apron_b

    nr = np.clip(r * (1.0 - is_paint) + tgt_r * is_paint, 0, 255)
    ng = np.clip(g * (1.0 - is_paint) + tgt_g * is_paint, 0, 255)
    nb = np.clip(b * (1.0 - is_paint) + tgt_b * is_paint, 0, 255)

    out_surf = Image.fromarray(np.stack([nr, ng, nb, a], axis=-1).astype(np.uint8), "RGBA")
    encode_rgba_mips_to_sdo(dec, slots[surf_key], out_surf)
    previews.append(("AO Surface", out_surf.convert("RGB")))

    # B. SurfaceDetail10 (512x512 DXT1 fine grain overlay) -> slight blue-slate shift so detail enhances blue court cleanly
    det_key = next((k for k in slots if "surfacedetail10" in k.lower()), None)
    if det_key:
        im_d = extract_slot_image(dec, slots[det_key]).convert("RGBA")
        darr = np.array(im_d, dtype=np.float32)
        dlum = 0.299 * darr[:, :, 0] + 0.587 * darr[:, :, 1] + 0.114 * darr[:, :, 2]
        darr[:, :, 0] = np.clip(dlum * 0.95, 0, 255)
        darr[:, :, 1] = np.clip(dlum * 1.00, 0, 255)
        darr[:, :, 2] = np.clip(dlum * 1.08, 0, 255)
        encode_rgba_mips_to_sdo(dec, slots[det_key], Image.fromarray(darr.astype(np.uint8), "RGBA"))

    # C. Sponsors 01 & 02 (render 1024x1024 -> downsample cleanly to 512x512 DXT1)
    sp1 = Image.new("RGB", (1024, 1024), (10, 20, 36))
    d1 = ImageDraw.Draw(sp1)
    # Band 0 (0..256): KIA (modern geometric minimalist on deep navy/black)
    d1.rectangle([0, 0, 1024, 256], fill=(12, 18, 30))
    _draw_centered(d1, (0, 0, 1024, 256), "KIA", F_IMPACT(124), fill=(255, 255, 255))
    # Band 1 (256..512): ROLEX on British green
    d1.rectangle([0, 256, 1024, 512], fill=(0, 96, 57))
    _draw_rolex_crown(d1, 270, 384, 2.0, gold=(230, 192, 82))
    _draw_centered(d1, (340, 256, 880, 512), "ROLEX", F_SERIF_BOLD(102), fill=(248, 248, 244))
    # Band 2 (512..768): Emirates FLY BETTER
    d1.rectangle([0, 512, 1024, 768], fill=(215, 25, 33))
    _draw_centered(d1, (0, 520, 1024, 690), "Emirates", F_SERIF_BOLD(102), fill=(255, 255, 255))
    _draw_centered(d1, (0, 680, 1024, 756), "FLY BETTER", F_SANS_BOLD(34), fill=(255, 236, 236))
    # Band 3 (768..1024): AO AUSTRALIAN OPEN
    d1.rectangle([0, 768, 1024, 1024], fill=(0, 145, 210))
    _draw_centered(d1, (40, 768, 340, 1024), "AO", F_IMPACT(124), fill=(255, 255, 255))
    d1.line([(360, 815), (360, 975)], fill=(180, 232, 255), width=5)
    _draw_centered(d1, (380, 795, 985, 915), "AUSTRALIAN OPEN", F_SANS_BOLD(54), fill=(255, 255, 255))
    _draw_centered(d1, (380, 900, 985, 995), "MELBOURNE", F_SANS_BOLD(36), fill=(220, 245, 255))
    sp1 = _fabric_noise(sp1, 2.5, 101).resize((512, 512), Image.Resampling.LANCZOS)
    encode_rgba_mips_to_sdo(dec, slots[next(k for k in slots if "lo_sponsor01" in k.lower())], sp1)
    previews.append(("AO Sponsor01", sp1))

    sp2 = Image.new("RGB", (1024, 1024), (10, 32, 64))
    d2 = ImageDraw.Draw(sp2)
    # Band 0: RALPH LAUREN
    d2.rectangle([0, 0, 1024, 256], fill=(12, 35, 64))
    _draw_centered(d2, (0, 0, 1024, 256), "RALPH LAUREN", F_SERIF_BOLD(84), fill=(248, 248, 248))
    # Band 1: MELBOURNE AO
    d2.rectangle([0, 256, 1024, 512], fill=(0, 145, 210))
    _draw_centered(d2, (0, 256, 1024, 512), "AO  MELBOURNE", F_SANS_BOLD(88), fill=(255, 255, 255))
    # Band 2: YONEX (authentic split blue/green badge)
    d2.rectangle([0, 512, 1024, 640], fill=(0, 96, 175))
    d2.rectangle([0, 640, 1024, 768], fill=(0, 148, 72))
    d2.ellipse([110, 650, 175, 715], fill=(255, 255, 255))
    d2.polygon([(95, 560), (150, 560), (185, 645), (130, 645)], fill=(255, 255, 255))
    d2.polygon([(195, 560), (250, 560), (215, 645), (160, 645)], fill=(255, 255, 255))
    _draw_centered(d2, (265, 512, 950, 768), "YONEX", F_IMPACT(132), fill=(255, 255, 255))
    # Band 3: ROD LAVER ARENA
    d2.rectangle([0, 768, 1024, 1024], fill=(10, 32, 66))
    d2.rectangle([0, 768, 1024, 782], fill=(0, 155, 222))
    _draw_centered(d2, (0, 795, 1024, 920), "ROD LAVER ARENA", F_SANS_BOLD(74), fill=(255, 255, 255))
    _draw_centered(d2, (0, 915, 1024, 1005), "MELBOURNE PARK", F_SANS_BOLD(34), fill=(110, 212, 255))
    sp2 = _fabric_noise(sp2, 2.5, 102).resize((512, 512), Image.Resampling.LANCZOS)
    encode_rgba_mips_to_sdo(dec, slots[next(k for k in slots if "lo_sponsor02" in k.lower())], sp2)
    previews.append(("AO Sponsor02", sp2))
    return previews


# ---------------------------------------------------------------------------
# 2. Roland Garros (Fra1ES / Fra1ED)
# ---------------------------------------------------------------------------
def build_fra1_textures(dec: bytearray, slots: dict) -> list[tuple[str, Image.Image]]:
    previews = []
    # A. Clay surface (2048x2048 DXT5) -> richer Parisian brick-red terracotta while keeping neutral shadows & Alpha intact
    surf_key = next(k for k in slots if re.search(r"surface_[sd]01", k, re.I))
    im_surf = extract_slot_image(dec, slots[surf_key])
    arr = np.array(im_surf, dtype=np.float32)
    r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]
    # Warmness = pixels where R > B + 20 (true clay vs white chalk/neutral shadows)
    clay_w = np.clip((r - b - 18.0) / 55.0, 0.0, 1.0)
    nr = np.clip(r * (1.0 + 0.10 * clay_w), 0, 255)
    ng = np.clip(g * (1.0 - 0.08 * clay_w), 0, 255)
    nb = np.clip(b * (1.0 - 0.14 * clay_w), 0, 255)
    out_surf = Image.fromarray(np.stack([nr, ng, nb, a], axis=-1).astype(np.uint8), "RGBA")
    encode_rgba_mips_to_sdo(dec, slots[surf_key], out_surf)
    previews.append(("RG Surface", out_surf.convert("RGB")))

    # B. Clay detail (512x512 DXT1) -> slightly warmer crushed-brick modulation
    det_key = next((k for k in slots if "claydetail01" in k.lower()), None)
    if det_key:
        im_d = extract_slot_image(dec, slots[det_key]).convert("RGBA")
        darr = np.array(im_d, dtype=np.float32)
        darr[:, :, 0] = np.clip(darr[:, :, 0] * 1.04, 0, 255)
        darr[:, :, 1] = np.clip(darr[:, :, 1] * 0.96, 0, 255)
        darr[:, :, 2] = np.clip(darr[:, :, 2] * 0.92, 0, 255)
        encode_rgba_mips_to_sdo(dec, slots[det_key], Image.fromarray(darr.astype(np.uint8), "RGBA"))

    # C. Sponsors 01 & 02 -> Dark Philippe-Chatrier Green (#15432E) + Official Roland-Garros Sponsors
    rg_green = (21, 67, 46)
    rg_cream = (244, 240, 230)
    rg_terra = (200, 90, 50)

    sp1 = Image.new("RGB", (1024, 1024), rg_green)
    d1 = ImageDraw.Draw(sp1)
    # Band 0: BNP PARIBAS
    d1.rectangle([180, 74, 275, 182], fill=(0, 145, 90))
    for sx, sy, sr in [(208, 106, 15), (244, 128, 13), (218, 154, 12)]:
        _draw_star(d1, sx, sy, sr, sr * 0.45, (255, 255, 255))
    _draw_centered(d1, (295, 0, 920, 256), "BNP PARIBAS", F_SANS_BOLD(78), fill=rg_cream)
    # Band 1: ROLEX
    _draw_rolex_crown(d1, 260, 384, 2.0, gold=(224, 184, 72))
    _draw_centered(d1, (320, 256, 860, 512), "ROLEX", F_SERIF_BOLD(104), fill=rg_cream)
    # Band 2: Emirates FLY BETTER
    _draw_centered(d1, (0, 524, 1024, 688), "Emirates", F_SERIF_BOLD(98), fill=rg_cream)
    _draw_centered(d1, (0, 680, 1024, 750), "FLY BETTER", F_SANS_BOLD(32), fill=(215, 232, 222))
    # Band 3: RENAULT
    d1.polygon([(210, 896), (255, 818), (300, 896), (255, 974)], outline=rg_cream, width=10)
    _draw_centered(d1, (320, 768, 890, 1024), "RENAULT", F_SANS_BOLD(86), fill=rg_cream)
    sp1 = _fabric_noise(sp1, 4.0, 201).resize((512, 512), Image.Resampling.LANCZOS)
    encode_rgba_mips_to_sdo(dec, slots[next(k for k in slots if "lo_sponsor01" in k.lower())], sp1)
    previews.append(("RG Sponsor01", sp1))

    sp2 = Image.new("RGB", (1024, 1024), rg_green)
    d2 = ImageDraw.Draw(sp2)
    # Band 0: LACOSTE
    _draw_centered(d2, (0, 0, 1024, 256), "LACOSTE", F_SANS_BOLD(102), fill=rg_cream)
    # Band 1: ROLAND-GARROS PARIS with terracotta circular crest
    d2.ellipse([110, 312, 254, 456], fill=rg_terra, outline=rg_cream, width=7)
    _draw_centered(d2, (110, 312, 254, 456), "RG", F_SERIF_BOLD(56), fill=rg_cream)
    _draw_centered(d2, (265, 275, 960, 415), "ROLAND-GARROS", F_SERIF_BOLD(68), fill=rg_cream)
    _draw_centered(d2, (265, 405, 960, 485), "PARIS · PHILIPPE-CHATRIER", F_SANS_BOLD(30), fill=(216, 234, 224))
    # Band 2: PERRIER
    _draw_centered(d2, (0, 512, 1024, 768), "perrier", F_SERIF_BOLD(110), fill=rg_cream)
    # Band 3: BABOLAT
    _draw_centered(d2, (0, 768, 1024, 1024), "Babolat", F_SANS_BOLD(106), fill=rg_cream)
    sp2 = _fabric_noise(sp2, 4.0, 202).resize((512, 512), Image.Resampling.LANCZOS)
    encode_rgba_mips_to_sdo(dec, slots[next(k for k in slots if "lo_sponsor02" in k.lower())], sp2)
    previews.append(("RG Sponsor02", sp2))
    return previews


# ---------------------------------------------------------------------------
# 3. Wimbledon (Eng1FS / Eng1FD)
# ---------------------------------------------------------------------------
def build_eng1_textures(dec: bytearray, slots: dict) -> list[tuple[str, Image.Image]]:
    previews = []
    # A. IL_surface_s_NY / IL_surface_d_NY (2048x2048 DXT5) -> fresh emerald Wimbledon lawn preserving worn clay patches & Alpha
    surf_key = next(k for k in slots if re.search(r"il_surface_[sd]_ny", k, re.I))
    im_surf = extract_slot_image(dec, slots[surf_key])
    arr = np.array(im_surf, dtype=np.float32)
    r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]
    # Grass dominance where G > R + 12 (worn baseline scuffs have R >= G, left untouched!)
    grass_w = np.clip((g - r - 8.0) / 45.0, 0.0, 1.0)
    nr = np.clip(r * (1.0 - 0.16 * grass_w), 0, 255)
    ng = np.clip(g * (1.0 + 0.02 * grass_w), 0, 255)
    nb = np.clip(b * (1.0 - 0.12 * grass_w), 0, 255)
    out_surf = Image.fromarray(np.stack([nr, ng, nb, a], axis=-1).astype(np.uint8), "RGBA")
    encode_rgba_mips_to_sdo(dec, slots[surf_key], out_surf)
    previews.append(("WIM Surface", out_surf.convert("RGB")))

    # B. Blue tarps UV_blue01/02/03 -> Wimbledon heritage dark green (#0C3D26)
    for k in list(slots.keys()):
        if "uv_blue0" in k.lower():
            im_b = extract_slot_image(dec, slots[k]).convert("RGBA")
            barr = np.array(im_b, dtype=np.float32)
            lum = (0.299 * barr[:, :, 0] + 0.587 * barr[:, :, 1] + 0.114 * barr[:, :, 2]) / 255.0
            # Target heritage dark green scaled around texture luminance
            scale = np.clip(lum / 0.25, 0.45, 1.65)
            barr[:, :, 0] = np.clip(12.0 * scale, 0, 255)
            barr[:, :, 1] = np.clip(62.0 * scale, 0, 255)
            barr[:, :, 2] = np.clip(38.0 * scale, 0, 255)
            encode_rgba_mips_to_sdo(dec, slots[k], Image.fromarray(barr.astype(np.uint8), "RGBA"))

    # C. Sponsor wall (1024x512 DXT1, 2 cols x 4 rows) -> Render at 2048x1024 then LANCZOS to 1024x512
    wim_green = (11, 58, 36)
    wim_purple = (84, 46, 113)
    wim_gold = (224, 186, 78)
    sp = Image.new("RGB", (2048, 1024), wim_green)
    dsp = ImageDraw.Draw(sp)
    # Subtle heritage purple accent bar per row band
    for r_i in range(4):
        y0 = r_i * 256
        dsp.line([(0, y0 + 8), (2048, y0 + 8)], fill=wim_purple, width=6)

    cells = [
        # (col, row, brand, sub, style)
        (0, 0, "ROLEX", "", "rolex"),
        (1, 0, "BARCLAYS", "", "sans"),
        (0, 1, "IBM", "", "serif"),
        (1, 1, "evian", "", "serif_sm"),
        (0, 2, "Slazenger", "", "serif"),
        (1, 2, "STELLA ARTOIS", "", "serif_sm"),
        (0, 3, "RALPH LAUREN", "", "serif_sm"),
        (1, 3, "WIMBLEDON", "CENTRE COURT", "wim"),
    ]
    for c, r_i, txt, sub, st in cells:
        bx0, by0 = c * 1024, r_i * 256
        box = (bx0 + 40, by0 + 18, bx0 + 984, by0 + 238)
        if st == "rolex":
            _draw_rolex_crown(dsp, bx0 + 300, by0 + 128, 1.8, gold=wim_gold)
            _draw_centered(dsp, (bx0 + 360, by0 + 18, bx0 + 880, by0 + 238), txt, F_SERIF_BOLD(94), fill=(248, 248, 244))
        elif st == "wim":
            cx, cy = bx0 + 225, by0 + 128
            dsp.ellipse([cx - 66, cy - 66, cx + 66, cy + 66], fill=wim_green, outline=(248, 248, 244), width=6)
            dsp.ellipse([cx - 52, cy - 52, cx + 52, cy + 52], outline=wim_purple, width=7)
            _draw_centered(dsp, (cx - 45, cy - 45, cx + 45, cy + 45), "W", F_SERIF_BOLD(52), fill=(248, 248, 244))
            _draw_centered(dsp, (bx0 + 305, by0 + 35, bx0 + 960, by0 + 150), txt, F_SERIF_BOLD(72), fill=(248, 248, 244))
            _draw_centered(dsp, (bx0 + 305, by0 + 145, bx0 + 960, by0 + 215), sub, F_SANS_BOLD(32), fill=(214, 232, 220))
        elif st == "serif":
            _draw_centered(dsp, box, txt, F_SERIF_BOLD(96), fill=(248, 248, 244))
        elif st == "serif_sm":
            _draw_centered(dsp, box, txt, F_SERIF_BOLD(76), fill=(248, 248, 244))
        else:
            _draw_centered(dsp, box, txt, F_SANS_BOLD(86), fill=(248, 248, 244))

    sp = _fabric_noise(sp, 3.0, 301).resize((1024, 512), Image.Resampling.LANCZOS)
    encode_rgba_mips_to_sdo(dec, slots[next(k for k in slots if "sponsor01a" in k.lower())], sp)
    previews.append(("WIM Sponsors", sp))
    return previews


# ---------------------------------------------------------------------------
# 4. US Open (Usa1NS / Usa1ND)
# ---------------------------------------------------------------------------
def _make_us_open_badge(text_main="US OPEN", text_sub="NEW YORK", w=760, h=220, bg=(26, 98, 70), inverted=False) -> Image.Image:
    im = Image.new("RGBA", (w, h), (*bg, 0))
    d = ImageDraw.Draw(im)
    # Stylised modern flaming tennis ball icon + crisp condensed US OPEN typography
    bx, by = 115, h // 2
    # Flames
    d.polygon([(bx - 88, by - 40), (bx - 22, by - 55), (bx - 52, by - 8)], fill=(255, 198, 42, 235))
    d.polygon([(bx - 98, by), (bx - 24, by - 12), (bx - 24, by + 18)], fill=(245, 120, 28, 235))
    d.polygon([(bx - 82, by + 46), (bx - 16, by + 18), (bx - 42, by + 62)], fill=(215, 48, 38, 235))
    # Ball
    r = 42
    d.ellipse([bx - r, by - r, bx + r, by + r], fill=(225, 245, 70, 245), outline=(255, 255, 255, 255), width=4)
    d.arc([bx - r + 6, by - r + 6, bx + r - 6, by + r - 6], start=35, end=215, fill=(255, 255, 255, 240), width=4)
    _draw_centered(d, (bx + 55, 24, w - 18, h - 68), text_main, F_IMPACT(108), fill=(255, 255, 255, 245))
    _draw_centered(d, (bx + 55, h - 72, w - 18, h - 18), text_sub, F_SANS_BOLD(34), fill=(224, 240, 255, 235))
    if inverted:
        im = im.rotate(180)
    return im


def build_usa1_textures(dec: bytearray, slots: dict) -> list[tuple[str, Image.Image]]:
    previews = []
    # A. Court Surface (2048x2048 DXT5)
    surf_key = next(k for k in slots if "surf_hard_base_" in k.lower())
    im_surf = extract_slot_image(dec, slots[surf_key])
    arr = np.array(im_surf, dtype=np.float32)
    r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]
    luma = 0.299 * r + 0.587 * g + 0.114 * b

    # Erase legacy text regions cleanly across RGB and Alpha (specular/gloss) using local brightness matching
    h, w = r.shape
    clean_patch_r = r[1665:1895, 1220:1440]
    clean_patch_g = g[1665:1895, 1220:1440]
    clean_patch_b = b[1665:1895, 1220:1440]
    clean_patch_a = a[1665:1895, 1220:1440]
    patch_luma_med = float(np.median(0.299 * clean_patch_r + 0.587 * clean_patch_g + 0.114 * clean_patch_b))
    patch_a_med = float(np.median(clean_patch_a))

    def _erase_rect(x0, y0, x1, y1):
        ph, pw = clean_patch_r.shape
        ry = np.tile(clean_patch_r, ((y1 - y0) // ph + 2, (x1 - x0) // pw + 2))[: y1 - y0, : x1 - x0]
        gy = np.tile(clean_patch_g, ((y1 - y0) // ph + 2, (x1 - x0) // pw + 2))[: y1 - y0, : x1 - x0]
        by = np.tile(clean_patch_b, ((y1 - y0) // ph + 2, (x1 - x0) // pw + 2))[: y1 - y0, : x1 - x0]
        ay = np.tile(clean_patch_a, ((y1 - y0) // ph + 2, (x1 - x0) // pw + 2))[: y1 - y0, : x1 - x0]

        ox0, oy0 = max(0, x0 - 6), max(0, y0 - 6)
        ox1, oy1 = min(w, x1 + 6), min(h, y1 + 6)
        ring_mask = np.ones((oy1 - oy0, ox1 - ox0), dtype=bool)
        ring_mask[(y0 - oy0):(y1 - oy0), (x0 - ox0):(x1 - ox0)] = False
        if np.any(ring_mask):
            ring_luma = (0.299 * r[oy0:oy1, ox0:ox1] + 0.587 * g[oy0:oy1, ox0:ox1] + 0.114 * b[oy0:oy1, ox0:ox1])[ring_mask]
            ring_a = a[oy0:oy1, ox0:ox1][ring_mask]
            scale_rgb = float(np.clip(np.median(ring_luma) / max(patch_luma_med, 1.0), 0.80, 1.20))
            scale_a = float(np.clip(np.median(ring_a) / max(patch_a_med, 1.0), 0.80, 1.20))
        else:
            scale_rgb, scale_a = 1.0, 1.0

        ry = np.clip(ry * scale_rgb, 0, 255)
        gy = np.clip(gy * scale_rgb, 0, 255)
        by = np.clip(by * scale_rgb, 0, 255)
        ay = np.clip(ay * scale_a, 0, 255)

        mask = np.ones((y1 - y0, x1 - x0), dtype=np.float32)
        for pad in range(14):
            alpha_p = (pad + 1) / 14.0
            mask[pad, :] = np.minimum(mask[pad, :], alpha_p)
            mask[-1 - pad, :] = np.minimum(mask[-1 - pad, :], alpha_p)
            mask[:, pad] = np.minimum(mask[:, pad], alpha_p)
            mask[:, -1 - pad] = np.minimum(mask[:, -1 - pad], alpha_p)
        r[y0:y1, x0:x1] = r[y0:y1, x0:x1] * (1.0 - mask) + ry * mask
        g[y0:y1, x0:x1] = g[y0:y1, x0:x1] * (1.0 - mask) + gy * mask
        b[y0:y1, x0:x1] = b[y0:y1, x0:x1] * (1.0 - mask) + by * mask
        a[y0:y1, x0:x1] = a[y0:y1, x0:x1] * (1.0 - mask) + ay * mask

    _erase_rect(970, 180, 1715, 400)
    _erase_rect(340, 1648, 1085, 1875)
    _erase_rect(392, 435, 518, 725)
    _erase_rect(1528, 1335, 1665, 1650)

    # Recompute luma after erasing & recolor court/apron to modern Arthur Ashe US Open Blue + Green
    luma = 0.299 * r + 0.587 * g + 0.114 * b
    yy, xx = np.mgrid[0:h, 0:w]
    in_court = ((xx >= 558) & (xx <= 1488) & (yy >= 418) & (yy <= 1628)).astype(np.float32)

    # Colorize only actual painted court area (where B or G exceeds R meaningfully, avoiding neutral gray borders/lines)
    paint_mask = np.clip((np.maximum(g, b) - r - 6.0) / 20.0, 0.0, 1.0)
    # Modern Arthur Ashe US Open Blue ~(32, 92, 168) at orig luma~80; US Open Green ~(26, 108, 76) at orig luma~86
    nr_in = np.clip(luma * 0.42, 0, 255)
    ng_in = np.clip(luma * 1.14, 0, 255)
    nb_in = np.clip(luma * 2.02, 0, 255)
    nr_ap = np.clip(luma * 0.34, 0, 255)
    ng_ap = np.clip(luma * 1.24, 0, 255)
    nb_ap = np.clip(luma * 0.90, 0, 255)

    tr = in_court * nr_in + (1.0 - in_court) * nr_ap
    tg = in_court * ng_in + (1.0 - in_court) * ng_ap
    tb = in_court * nb_in + (1.0 - in_court) * nb_ap
    nr = np.clip(r * (1.0 - paint_mask) + tr * paint_mask, 0, 255)
    ng = np.clip(g * (1.0 - paint_mask) + tg * paint_mask, 0, 255)
    nb = np.clip(b * (1.0 - paint_mask) + tb * paint_mask, 0, 255)

    out_rgb = Image.fromarray(np.stack([nr, ng, nb], axis=-1).astype(np.uint8), "RGB")
    # Stamp crisp US OPEN logos (top inverted + bottom upright + NEW YORK side marks)
    badge_bot = _make_us_open_badge("US OPEN", "ARTHUR ASHE STADIUM", 720, 200, bg=(26, 102, 74), inverted=False)
    badge_top = _make_us_open_badge("US OPEN", "ARTHUR ASHE STADIUM", 720, 200, bg=(26, 102, 74), inverted=True)

    # Vertical "NEW YORK" on left and right sidelines
    side_txt = Image.new("RGBA", (300, 64), (0, 0, 0, 0))
    _draw_centered(ImageDraw.Draw(side_txt), (0, 0, 300, 64), "NEW YORK", F_SANS_BOLD(42), fill=(240, 246, 255, 225))
    s_l = side_txt.rotate(90, expand=True)
    s_r = side_txt.rotate(-90, expand=True)

    decal_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    decal_layer.paste(badge_bot, (425, 1685), badge_bot)
    decal_layer.paste(badge_top, (915, 165), badge_top)
    decal_layer.paste(s_l, (422, 470), s_l)
    decal_layer.paste(s_r, (1552, 1320), s_r)
    out_rgb.paste(decal_layer, (0, 0), decal_layer)

    d_alpha = np.array(decal_layer)[:, :, 3]
    a_out = np.where(d_alpha > 128, np.clip(a + 16.0, 0, 255), a)
    r_f, g_f, b_f = out_rgb.split()
    out_surf = Image.merge("RGBA", (r_f, g_f, b_f, Image.fromarray(a_out.astype(np.uint8), "L")))
    encode_rgba_mips_to_sdo(dec, slots[surf_key], out_surf)
    previews.append(("USO Surface", out_rgb))

    # B. Usa1 Sponsor Atlas (1024x1024 DXT1 — preserve exact UV regions!)
    orig_sp = extract_slot_image(dec, slots[next(k for k in slots if "sponsor01_" in k.lower())]).convert("RGB")
    # Render 2048x2048 then downsample, keeping original USA flag crop sharp
    sp = Image.new("RGB", (2048, 2048), (16, 39, 74))
    dsp = ImageDraw.Draw(sp)

    # Top 2x3 light-gradient strips (y: 0..592): y in [0..196], [196..392], [392..592], x in [0..1024], [1024..2048]
    top_brands = [
        (0, 0, "CHASE", (17, 94, 174), F_SANS_BOLD(92)),
        (1, 0, "Emirates", (200, 24, 34), F_SERIF_BOLD(90)),
        (0, 1, "ROLEX", (0, 96, 57), F_SERIF_BOLD(92)),
        (1, 1, "IBM", (18, 48, 102), F_SERIF_BOLD(96)),
        (0, 2, "RALPH LAUREN", (14, 32, 64), F_SERIF_BOLD(66)),
        (1, 2, "CITIZEN", (18, 24, 36), F_SERIF_BOLD(86)),
    ]
    row_y = [0, 196, 392, 592]
    for col, row, txt, col_txt, fnt in top_brands:
        bx0, bx1 = col * 1024, (col + 1) * 1024
        by0, by1 = row_y[row], row_y[row + 1]
        dsp.rectangle([bx0, by0, bx1, by1], fill=(22, 48, 92))
        dsp.rectangle([bx0 + 130, by0 + 14, bx1 - 130, by1 - 14], fill=(242, 244, 248))
        _draw_centered(dsp, (bx0 + 130, by0 + 14, bx1 - 130, by1 - 14), txt, fnt, fill=col_txt)

    # Middle-top panel (y: 592..1136): dark navy Arthur Ashe stadium panel + USA flag top-right + gold/cyan accent
    dsp.rectangle([0, 592, 2048, 1136], fill=(13, 30, 58))
    usa_flag = orig_sp.crop((768, 296, 1024, 434)).resize((512, 276), Image.Resampling.LANCZOS)
    sp.paste(usa_flag, (1536, 592))
    dsp.rectangle([1636, 868, 2048, 1136], fill=(214, 154, 42))
    _draw_centered(dsp, (1636, 868, 2048, 1136), "NY", F_IMPACT(120), fill=(13, 30, 58))
    badge_mid = _make_us_open_badge("US OPEN", "USTA BILLIE JEAN KING NTC", 880, 220, bg=(13, 30, 58), inverted=False)
    sp.paste(badge_mid, (70, 625), badge_mid)
    _draw_centered(dsp, (760, 865, 1610, 1110), "CHASE", F_SANS_BOLD(116), fill=(255, 255, 255))

    # Row 3 (y: 1136..1536): 4 side wall tiles (x width 512 each)
    dsp.rectangle([0, 1136, 2048, 1536], fill=(16, 42, 82))
    for i, (t, fnt) in enumerate([
        ("CITIZEN", F_SERIF_BOLD(78)),
        ("AMEX", F_SANS_BOLD(92)),
        ("Emirates", F_SERIF_BOLD(86)),
        ("ROLEX", F_SERIF_BOLD(86)),
    ]):
        bx0 = i * 512
        dsp.line([(bx0, 1136), (bx0, 1536)], fill=(8, 20, 42), width=6)
        dsp.line([(bx0, 1170), (bx0 + 512, 1170)], fill=(120, 168, 228), width=4)
        _draw_centered(dsp, (bx0 + 16, 1180, bx0 + 496, 1520), t, fnt, fill=(246, 248, 252))

    # Row 4 (y: 1536..2048): 2 wide front/back wall blocks (x: 0..1024 and 1024..2048)
    dsp.rectangle([0, 1536, 2048, 2048], fill=(14, 38, 76))
    dsp.line([(1024, 1536), (1024, 2048)], fill=(8, 20, 42), width=8)
    dsp.line([(0, 1574), (2048, 1574)], fill=(120, 168, 228), width=5)
    b_l = _make_us_open_badge("US OPEN", "NEW YORK", 460, 180, bg=(14, 38, 76), inverted=False)
    sp.paste(b_l, (30, 1680), b_l)
    dsp.rectangle([540, 1690, 960, 1890], fill=(17, 94, 174), outline=(255, 255, 255), width=4)
    _draw_centered(dsp, (540, 1690, 960, 1890), "CHASE", F_SANS_BOLD(82), fill=(255, 255, 255))

    dsp.rectangle([1070, 1690, 1480, 1890], fill=(205, 32, 39), outline=(255, 255, 255), width=4)
    _draw_centered(dsp, (1070, 1690, 1480, 1890), "Wilson", F_SERIF_BOLD(78), fill=(255, 255, 255))
    b_r = _make_us_open_badge("US OPEN", "NEW YORK", 460, 180, bg=(14, 38, 76), inverted=False)
    sp.paste(b_r, (1550, 1680), b_r)

    sp = _fabric_noise(sp, 2.5, 401).resize((1024, 1024), Image.Resampling.LANCZOS)
    encode_rgba_mips_to_sdo(dec, slots[next(k for k in slots if "sponsor01_" in k.lower())], sp)
    previews.append(("USO Sponsors", sp))

    # C. Giant Jumbotron screen (256x128 DXT1, B_sc_screen01 & IC_sc_screen01)
    scr = Image.new("RGB", (512, 256), (12, 30, 66))
    dscr = ImageDraw.Draw(scr)
    dscr.rectangle([10, 10, 502, 246], outline=(235, 190, 62), width=6)
    b_scr = _make_us_open_badge("US OPEN", "ARTHUR ASHE STADIUM", 470, 170, bg=(12, 30, 66), inverted=False)
    scr.paste(b_scr, (21, 42), b_scr)
    scr_sm = scr.resize((256, 128), Image.Resampling.LANCZOS)
    for k in list(slots.keys()):
        if "sc_screen01" in k.lower():
            encode_rgba_mips_to_sdo(dec, slots[k], scr_sm)
    return previews


# ---------------------------------------------------------------------------
# Runner & Preview Sheet
# ---------------------------------------------------------------------------
STAGE_JOBS = [
    ("HIGH/Stage/TA_S_Aus1FS_B_stage_IW.sdo", build_aus1_textures, True),
    ("HIGH/Stage/TA_S_Aus1FD_B_stage_IW.sdo", build_aus1_textures, False),
    ("HIGH/Stage/TA_S_Fra1ES_B_stage_IW.sdo", build_fra1_textures, True),
    ("HIGH/Stage/TA_S_Fra1ED_B_stage_IW.sdo", build_fra1_textures, False),
    ("HIGH/Stage/TA_S_Eng1FS_B_stage_NY.sdo", build_eng1_textures, True),
    ("HIGH/Stage/TA_S_Eng1FD_B_stage_NY.sdo", build_eng1_textures, False),
    ("HIGH/Stage/TA_S_Usa1NS_B_stage_YE.sdo", build_usa1_textures, True),
    ("HIGH/Stage/TA_S_Usa1ND_B_stage_YE.sdo", build_usa1_textures, False),
]


def main():
    entries = load_directory()
    cache = {}
    all_previews = []

    with open(BIN0, "rb") as f0, open(BIN1, "rb") as f1:
        for arc_path, builder_fn, collect_preview in STAGE_JOBS:
            e = next(x for x in entries if x["name"].lower() == arc_path.lower())
            raw_dec = bytearray(lzss_decompress(read_entry(entries, e, f0, f1, cache)))
            slots = {s["name"]: s for s in parse_sdo_dds_slots(raw_dec)}
            previews = builder_fn(raw_dec, slots)
            if collect_preview:
                all_previews.extend(previews)

            comp_out = lzss_compress_literal(bytes(raw_dec))
            out_path = os.path.join(REPO_ROOT, "game", "archive", arc_path.replace("/", os.sep))
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "wb") as out_f:
                out_f.write(comp_out)
            print(f"[OK] {arc_path}: {len(comp_out):,} B compressed (from {len(raw_dec):,} B)")
            for c in entries:
                if c["vol"] == -1 and c["parent_idx"] == e["idx"]:
                    child_bytes = read_entry(entries, c, f0, f1, cache)
                    child_out = os.path.join(REPO_ROOT, "game", "archive", c["name"].replace("/", os.sep))
                    os.makedirs(os.path.dirname(child_out), exist_ok=True)
                    with open(child_out, "wb") as cf:
                        cf.write(child_bytes)
                    print(f"[OK-CHILD] {c['name']}: {len(child_bytes):,} B")

    # Build combined visual audit sheet
    audit_dir = os.path.join(REPO_ROOT, "scratch", "gs_audit")
    os.makedirs(audit_dir, exist_ok=True)
    cols = 3
    rows = (len(all_previews) + cols - 1) // cols
    tw, th = 380, 380
    sheet = Image.new("RGB", (cols * tw, rows * (th + 32)), (22, 26, 34))
    dr = ImageDraw.Draw(sheet)
    fnt = F_SANS_BOLD(20)
    for i, (label, img) in enumerate(all_previews):
        x0 = (i % cols) * tw
        y0 = (i // cols) * (th + 32)
        thumb = img.copy()
        thumb.thumbnail((tw - 12, th - 12), Image.Resampling.LANCZOS)
        sheet.paste(thumb, (x0 + (tw - thumb.width) // 2, y0 + 28 + (th - thumb.height) // 2))
        dr.text((x0 + 10, y0 + 4), label, font=fnt, fill=(255, 232, 130))

    prev_path = os.path.join(audit_dir, "GRAND_SLAMS_PREVIEW.png")
    sheet.save(prev_path)
    print(f"Saved audit sheet -> {prev_path}")


if __name__ == "__main__":
    main()
