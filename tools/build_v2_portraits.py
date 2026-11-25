#!/usr/bin/env python3
"""Frame and pack PhotoCraft v2 cutouts into photo_L, photo_eye, and photo_S DDS."""
import os
import struct
from collections import deque
from PIL import Image, ImageDraw

from dxt_codec import encode_dds

VR_DIR = os.path.join("game", "archive", "HIGH", "Frontend", "VR")

# (crop_box=(x0,y0,x1,y1) in cutout coords, top_pad_ratio, eye_y_center_in_256)
FRAMING = {
    "29_91": ((85, 45, 835, 1020), 0.03, 54),
    "37":    ((165, 25, 800, 880), 0.02, 100),
    "38":    ((35, 20, 835, 960),  0.03, 46),
    "40":    ((0, 0, 850, 980),    0.03, 62),
    "43":    ((10, 15, 620, 585),  0.03, 50),
    "44":    ((0, 0, 430, 560),    0.03, 64),
    "45":    ((55, 35, 390, 610),  0.03, 52),
    "47":    ((0, 5, 380, 470),    0.03, 50),
    "49":    ((345, 340, 845, 1000), 0.02, 64),
    "51":    ((65, 10, 655, 580),  0.03, 66),
    "52":    ((310, 5, 1264, 848), 0.03, 130),
    "55":    ((0, 25, 465, 725),   0.03, 50),
    "56":    ((85, 30, 865, 1070), 0.03, 96),
}


def remove_small_alpha_islands(im: Image.Image, min_pixels: int = 350) -> Image.Image:
    """Keep major connected opaque components and strip isolated floating specks."""
    rgba = im.convert("RGBA")
    w, h = rgba.size
    a_bytes = bytearray(rgba.getchannel("A").tobytes())
    visited = bytearray(w * h)
    keep = bytearray(w * h)

    for idx in range(w * h):
        if a_bytes[idx] <= 20 or visited[idx]:
            continue
        q = deque([idx])
        visited[idx] = 1
        comp = []
        while q:
            c = q.popleft()
            comp.append(c)
            cy, cx = divmod(c, w)
            if cy > 0:
                n = c - w
                if a_bytes[n] > 20 and not visited[n]:
                    visited[n] = 1
                    q.append(n)
            if cy + 1 < h:
                n = c + w
                if a_bytes[n] > 20 and not visited[n]:
                    visited[n] = 1
                    q.append(n)
            if cx > 0:
                n = c - 1
                if a_bytes[n] > 20 and not visited[n]:
                    visited[n] = 1
                    q.append(n)
            if cx + 1 < w:
                n = c + 1
                if a_bytes[n] > 20 and not visited[n]:
                    visited[n] = 1
                    q.append(n)
        if len(comp) >= min_pixels:
            for c in comp:
                keep[c] = 1

    for i in range(w * h):
        if not keep[i] or a_bytes[i] < 18:
            a_bytes[i] = 0

    new_a = Image.frombytes("L", (w, h), bytes(a_bytes))
    rgba.putalpha(new_a)
    return rgba


def write_bgra_dds(im: Image.Image, path: str) -> None:
    """Write uncompressed 32-bit BGRA DDS (matching SEGA VT4 photo_L/photo_eye)."""
    rgba = im.convert("RGBA")
    w, h = rgba.size
    bgra = rgba.tobytes("raw", "BGRA")

    hdr = bytearray(128)
    hdr[0:4] = b"DDS "
    struct.pack_into(
        "<7I",
        hdr,
        4,
        124,
        0x0002100F,
        h,
        w,
        w * 4,
        0,
        1,
    )
    struct.pack_into(
        "<8I",
        hdr,
        76,
        32,
        0x00000041,
        0,
        32,
        0x00FF0000,
        0x0000FF00,
        0x000000FF,
        0xFF000000,
    )
    struct.pack_into("<I", hdr, 108, 0x00001000)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(hdr)
        f.write(bgra)


def write_dxt5_dds(im: Image.Image, path: str) -> None:
    """Write 1-mip DXT5 DDS via dxt_codec (matching SEGA VT4 photo_S)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(encode_dds(im.convert("RGBA"), b"DXT5"))


def frame_portrait_256(cutout: Image.Image, crop_box: tuple, top_pad_ratio: float) -> Image.Image:
    """Crop portrait box, keep bottom anchored, and fit onto 256x256 transparent canvas."""
    x0, y0, x1, y1 = crop_box
    w, h = cutout.size
    crop = cutout.crop((max(0, x0), max(0, y0), min(w, x1), min(h, y1)))
    bb = crop.getbbox()
    if bb:
        cw, ch = crop.size
        crop = crop.crop((bb[0], bb[1], bb[2], ch))

    cw, ch = crop.size
    top_pad = int(round(256 * top_pad_ratio))
    avail_h = 256 - top_pad
    avail_w = 244
    scale = min(avail_w / max(1, cw), avail_h / max(1, ch))
    nw = max(1, int(round(cw * scale)))
    nh = max(1, int(round(ch * scale)))
    resized = crop.resize((nw, nh), Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    px = (256 - nw) // 2
    py = 256 - nh
    canvas.paste(resized, (px, py), resized)
    return canvas


def build_eye_strip(portrait_256: Image.Image, eye_y: int) -> Image.Image:
    """Build 256x64 opaque studio eye-strip matching VT4 photo_eye style."""
    bg = Image.new("RGBA", (256, 64), (24, 28, 36, 255))
    draw = ImageDraw.Draw(bg)
    for x in range(256):
        v = int(20 + 16 * (x / 255.0))
        draw.line([(x, 0), (x, 63)], fill=(v, v + 3, v + 8, 255))

    bb = portrait_256.crop((0, max(0, eye_y - 24), 256, min(256, eye_y + 24))).getbbox()
    cx = (bb[0] + bb[2]) // 2 if bb else 128
    half_w = 96
    half_h = 24
    x0 = max(0, min(256 - 2 * half_w, cx - half_w))
    y0 = max(0, min(256 - 2 * half_h, eye_y - half_h))
    face_band = portrait_256.crop((x0, y0, x0 + 2 * half_w, y0 + 2 * half_h))
    zoomed = face_band.resize((256, 64), Image.Resampling.LANCZOS)
    bg.paste(zoomed, (0, 0), zoomed)
    return bg


def build_photo_s(portrait_256: Image.Image) -> Image.Image:
    """Build 128x64 photo_S upper-body card over transparent background."""
    crop = portrait_256.crop((0, 0, 256, 152)).resize((104, 64), Image.Resampling.LANCZOS)
    card = Image.new("RGBA", (128, 64), (0, 0, 0, 0))
    card.paste(crop, (12, 0), crop)
    return card


def main() -> None:
    updated_keys = []
    for k, (crop_box, pad_r, eye_y) in FRAMING.items():
        src = os.path.join("assets", "cutouts_v2", f"{k}.png")
        im = Image.open(src).convert("RGBA")
        im = remove_small_alpha_islands(im, min_pixels=350)
        p256 = frame_portrait_256(im, crop_box, pad_r)
        eye = build_eye_strip(p256, eye_y)
        ps = build_photo_s(p256)

        write_bgra_dds(p256, os.path.join(VR_DIR, "photo_L", f"{k}.dds"))
        write_bgra_dds(eye, os.path.join(VR_DIR, "photo_eye", f"{k}.dds"))
        write_dxt5_dds(ps, os.path.join(VR_DIR, "photo_S", f"{k}.dds"))
        updated_keys.append(k)
        print(f"Packed {k}: photo_L/eye/S updated.")

    cols, rows = 5, 3
    cw, ch = 260, 326
    sheet = Image.new("RGB", (cols * cw, rows * ch), (28, 30, 38))
    tile = Image.new("RGB", (256, 256))
    px = tile.load()
    for y in range(256):
        for x in range(256):
            px[x, y] = (62, 66, 78) if ((x // 16) + (y // 16)) % 2 == 0 else (92, 98, 112)

    draw = ImageDraw.Draw(sheet)
    for idx, k in enumerate(updated_keys):
        r, c = divmod(idx, cols)
        x0, y0 = c * cw + 2, r * ch + 2
        sheet.paste(tile, (x0, y0))
        pl = Image.open(os.path.join(VR_DIR, "photo_L", f"{k}.dds")).convert("RGBA")
        pe = Image.open(os.path.join(VR_DIR, "photo_eye", f"{k}.dds")).convert("RGBA")
        sheet.paste(pl, (x0, y0), pl)
        sheet.paste(pe.resize((256, 64), Image.Resampling.LANCZOS), (x0, y0 + 258))
        draw.rectangle([x0, y0, x0 + 96, y0 + 18], fill=(15, 18, 25))
        draw.text((x0 + 4, y0 + 3), f"ID {k}", fill=(255, 225, 90))

    out = os.path.join("scratch", "portraits_audit_v2.png")
    sheet.save(out)
    Image.open(out).verify()
    print("Verified contact sheet:", out)


if __name__ == "__main__":
    main()
