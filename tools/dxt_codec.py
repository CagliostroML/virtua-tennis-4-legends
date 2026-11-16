"""Pure-Python + PIL DXT1 / DXT5 (BC1 / BC3) DDS encoder for VT4 texture modding."""
import struct
from PIL import Image


def _pack_rgb565(r: int, g: int, b: int) -> int:
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def _unpack_rgb565(c: int):
    r = ((c >> 11) & 0x1F) * 255 // 31
    g = ((c >> 5) & 0x3F) * 255 // 63
    b = (c & 0x1F) * 255 // 31
    return (r, g, b)


def _encode_color_block(block_rgb) -> bytes:
    """block_rgb: list of 16 (r, g, b) tuples -> 8-byte BC1/DXT1 block."""
    # Choose endpoints with max/min projection along bounding-box diagonal
    rs = [p[0] for p in block_rgb]
    gs = [p[1] for p in block_rgb]
    bs = [p[2] for p in block_rgb]
    rmin, rmax = min(rs), max(rs)
    gmin, gmax = min(gs), max(gs)
    bmin, bmax = min(bs), max(bs)
    dr, dg, db = rmax - rmin, gmax - gmin, bmax - bmin

    if dr == 0 and dg == 0 and db == 0:
        q = _pack_rgb565(rmin, gmin, bmin)
        if q == 0:
            return struct.pack("<HHI", 1, 0, 0x55555555)
        return struct.pack("<HHI", q, 0, 0)

    best_lo = best_hi = block_rgb[0]
    min_proj = 1 << 30
    max_proj = -(1 << 30)
    for r, g, b in block_rgb:
        p = (r - rmin) * dr + (g - gmin) * dg + (b - bmin) * db
        if p < min_proj:
            min_proj = p
            best_lo = (r, g, b)
        if p > max_proj:
            max_proj = p
            best_hi = (r, g, b)

    q0 = _pack_rgb565(*best_hi)
    q1 = _pack_rgb565(*best_lo)
    if q0 < q1:
        q0, q1 = q1, q0
    if q0 == q1:
        # Force 4-color mode cleanly
        return struct.pack("<HHI", q0, q1, 0)

    p0 = _unpack_rgb565(q0)
    p1 = _unpack_rgb565(q1)
    p2 = ((2 * p0[0] + p1[0]) // 3, (2 * p0[1] + p1[1]) // 3, (2 * p0[2] + p1[2]) // 3)
    p3 = ((p0[0] + 2 * p1[0]) // 3, (p0[1] + 2 * p1[1]) // 3, (p0[2] + 2 * p1[2]) // 3)
    pal = (p0, p1, p2, p3)

    bits = 0
    for i, (r, g, b) in enumerate(block_rgb):
        best_idx = 0
        best_d = 1 << 30
        for idx, (pr, pg, pb) in enumerate(pal):
            d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
            if d < best_d:
                best_d = d
                best_idx = idx
        bits |= (best_idx << (i * 2))
    return struct.pack("<HHI", q0, q1, bits)


def _encode_alpha_block(block_a) -> bytes:
    """block_a: list of 16 uint8 alpha values -> 8-byte BC3 alpha block."""
    a0 = max(block_a)
    a1 = min(block_a)
    if a0 == a1:
        return bytes([a0, a1, 0, 0, 0, 0, 0, 0])

    # a0 > a1 selects 8-level interpolation
    pal = (
        a0,
        a1,
        (6 * a0 + 1 * a1) // 7,
        (5 * a0 + 2 * a1) // 7,
        (4 * a0 + 3 * a1) // 7,
        (3 * a0 + 4 * a1) // 7,
        (2 * a0 + 5 * a1) // 7,
        (1 * a0 + 6 * a1) // 7,
    )
    bits = 0
    for i, val in enumerate(block_a):
        best_idx = 0
        best_d = 999
        for idx, pv in enumerate(pal):
            d = abs(val - pv)
            if d < best_d:
                best_d = d
                best_idx = idx
        bits |= (best_idx << (i * 3))
    return bytes([a0, a1]) + bits.to_bytes(6, "little")


def _iter_blocks(img: Image.Image):
    rgba = img.convert("RGBA")
    w, h = rgba.size
    px = rgba.tobytes()
    bw = max(1, (w + 3) // 4)
    bh = max(1, (h + 3) // 4)
    stride = w * 4
    for by in range(bh):
        y0 = by * 4
        for bx in range(bw):
            x0 = bx * 4
            rgb_blk = []
            a_blk = []
            for dy in range(4):
                yy = min(y0 + dy, h - 1)
                row_off = yy * stride
                for dx in range(4):
                    xx = min(x0 + dx, w - 1)
                    o = row_off + xx * 4
                    rgb_blk.append((px[o], px[o + 1], px[o + 2]))
                    a_blk.append(px[o + 3])
            yield rgb_blk, a_blk


def encode_dxt5_payload(img: Image.Image) -> bytes:
    chunks = bytearray()
    for rgb_blk, a_blk in _iter_blocks(img):
        chunks.extend(_encode_alpha_block(a_blk))
        chunks.extend(_encode_color_block(rgb_blk))
    return bytes(chunks)


def encode_dxt1_payload(img: Image.Image) -> bytes:
    chunks = bytearray()
    for rgb_blk, _ in _iter_blocks(img):
        chunks.extend(_encode_color_block(rgb_blk))
    return bytes(chunks)


def make_dds_header(w: int, h: int, fourcc: bytes, mips: int = 1) -> bytes:
    hdr = bytearray(128)
    hdr[0:4] = b"DDS "
    block_sz = max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * (8 if fourcc == b"DXT1" else 16)
    struct.pack_into("<IIIIIII", hdr, 4, 124, 0x000A1007 if mips > 1 else 0x00081007, h, w, block_sz, 0, mips)
    struct.pack_into("<III", hdr, 76, 32, 0x4, int.from_bytes(fourcc, "little"))
    struct.pack_into("<I", hdr, 108, 0x00401008 if mips > 1 else 0x00001000)
    return bytes(hdr)


def encode_dds(img: Image.Image, fourcc: bytes = b"DXT5") -> bytes:
    w, h = img.size
    if fourcc == b"DXT1":
        return make_dds_header(w, h, b"DXT1", 1) + encode_dxt1_payload(img)
    elif fourcc == b"DXT5":
        return make_dds_header(w, h, b"DXT5", 1) + encode_dxt5_payload(img)
    elif fourcc == b"RGBA":
        px = img.convert("RGBA").tobytes()
        # Swap R/B -> BGRA
        bgra = bytearray(len(px))
        bgra[0::4] = px[2::4]
        bgra[1::4] = px[1::4]
        bgra[2::4] = px[0::4]
        bgra[3::4] = px[3::4]
        hdr = bytearray(128)
        hdr[0:4] = b"DDS "
        struct.pack_into("<IIIIIII", hdr, 4, 124, 0x0000100F, h, w, w * 4, 0, 1)
        struct.pack_into("<IIIIIIII", hdr, 76, 32, 0x41, 0, 32, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)
        struct.pack_into("<I", hdr, 108, 0x00001000)
        return bytes(hdr) + bytes(bgra)
    raise ValueError(f"Unsupported fourcc: {fourcc}")
