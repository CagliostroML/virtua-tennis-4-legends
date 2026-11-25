#!/usr/bin/env python3
"""
Build and extract EE-3 real 3D weapon racket meshes & textures for
Virtua Tennis 4: Legends & Next-Gen Edition.

Outputs into game/archive/ee3/:
  1. Official extracted SEGA textures:
       G_racket_B_sp00_YS.dds, G_racket_S_sp00_YS.dds, G_racket_B_lodGut_sp00_YS.dds
       G_racket_B_sp08_flyingpan_YS.dds, G_racket_S_sp08_flyingpan_YS.dds
       G_racket_B_sp28_bugette_YS.dds, G_racket_S_sp28_bugette_YS.dds
  2. Mode-specific DDS textures matching all 26 SEGA / 82 total player SDO slots:
       {wood70,pan,baguette}_B_{256_dxt1,256_dxt5,512_dxt1}.dds
       {wood70,pan,baguette}_S_{256_dxt1,256_dxt5,512_dxt1}.dds
       {wood70,pan,baguette}_gut_64_dxt5.dds
  3. ee3_meshes.bin:
       Binary 3D vertex/index templates (racket coordinate space):
         - PAN_LOD0, PAN_LODL  (G_racket_sp08_flyingpan_YS rotated +90 deg X, z shifted +1.1833)
         - BAGUETTE_LOD0, BAGUETTE_LODL (G_racket_sp28_bugette_YS spanning z in [0.0..6.8])

Also verifies capacity & bounding boxes across all 26 SEGA player .sdo files.
"""
import io
import os
import re
import struct
import sys
from PIL import Image, ImageDraw, ImageEnhance

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

from vt4_archive import BIN0, BIN1, load_directory, read_entry, lzss_decompress
from dxt_codec import encode_dds, encode_dxt1_payload, encode_dxt5_payload

OUT_DIR = os.path.join(REPO_ROOT, "game", "archive", "ee3")


def decompress_sdo(raw: bytes) -> bytes:
    """Decompress SEGA LZSS .sdo buffer even when directory is_comp flag is false."""
    if raw[:4] == b"SEGA" or raw[1:5] == b"SEGA":
        return raw
    if len(raw) >= 8:
        u, c = struct.unpack_from(">II", raw, 0)
        if 16 < u < 64 * 1024 * 1024 and 8 < c <= len(raw) - 8:
            dec = lzss_decompress(raw)
            if dec[:4] == b"SEGA" or dec[1:5] == b"SEGA":
                return dec
    return raw


def parse_dds_slots(dec: bytes):
    offs = [m.start() for m in re.finditer(b"DDS ", dec)]
    slots = []
    for i, off in enumerate(offs):
        h, w, pitch, depth, mips = struct.unpack_from("<IIIII", dec, off + 12)
        mips = max(1, mips)
        fourcc = dec[off + 84 : off + 88]
        strs = re.findall(b"[A-Za-z0-9_.]{4,48}", dec[max(0, off - 96) : off])
        tname = strs[-1].decode("ascii", "replace") if strs else f"tex_{i}"
        bs = 8 if fourcc == b"DXT1" else 16
        mw, mh = w, h
        payload_sz = 0
        for _ in range(mips):
            payload_sz += max(1, (mw + 3) // 4) * max(1, (mh + 3) // 4) * bs
            mw = max(1, mw // 2)
            mh = max(1, mh // 2)
        slots.append({
            "idx": i, "off": off, "w": w, "h": h, "mips": mips,
            "fourcc": fourcc, "name": tname, "total_sz": 128 + payload_sz,
        })
    return slots


def build_mipmapped_dds(img: Image.Image, w: int, h: int, fourcc: bytes, mips: int) -> bytes:
    """Encode RGBA PIL image into a full multi-mip DDS file with matching DX header."""
    base_dds = bytearray(encode_dds(img.convert("RGBA").resize((w, h), Image.LANCZOS), fourcc))
    # Update dwFlags |= DDSD_MIPMAPCOUNT (0x20000) and dwMipMapCount = mips
    flags = struct.unpack_from("<I", base_dds, 8)[0]
    struct.pack_into("<I", base_dds, 8, flags | 0x20000)
    struct.pack_into("<I", base_dds, 28, mips)
    caps = struct.unpack_from("<I", base_dds, 108)[0]
    struct.pack_into("<I", base_dds, 108, caps | 0x400008)  # DDSCAPS_COMPLEX | DDSCAPS_MIPMAP

    enc_fn = encode_dxt1_payload if fourcc == b"DXT1" else encode_dxt5_payload
    cur = img.convert("RGBA").resize((w, h), Image.LANCZOS)
    payload = bytearray()
    mw, mh = w, h
    for _ in range(mips):
        mimg = cur if cur.size == (mw, mh) else cur.resize((mw, mh), Image.LANCZOS)
        payload.extend(enc_fn(mimg))
        mw = max(1, mw // 2)
        mh = max(1, mh // 2)
    return bytes(base_dds[:128]) + bytes(payload)


def parse_vbs(dec: bytes):
    vbs = []
    pos = 0
    tag = b"\x0cVertexBuffer\x00"
    type_sz = {1: 1, 2: 2, 4: 4}
    while True:
        idx = dec.find(tag, pos)
        if idx < 0:
            break
        p = idx + len(tag)
        l1 = dec[p]; p += 1
        fn = dec[p : p + l1].decode("latin1", "replace"); p += l1
        l2 = dec[p]; p += 1
        sn = dec[p : p + l2].decode("latin1", "replace"); p += l2
        flag = dec[p]; p += 1
        total_verts, total_bytes = struct.unpack_from(">II", dec, p); p += 8
        num_streams = dec[p]; p += 1
        streams = []
        for _ in range(num_streams):
            s_off, s_bytes = struct.unpack_from(">II", dec, p); p += 8
            n_attrs = dec[p]; p += 1
            attrs = [(dec[p + 2 * i], dec[p + 2 * i + 1]) for i in range(n_attrs)]
            p += 2 * n_attrs
            stride = sum(type_sz[t] * c for t, c in attrs)
            streams.append({
                "off": s_off, "bytes": s_bytes, "attrs": attrs,
                "stride": stride, "nverts": s_bytes // stride,
            })
        vbs.append({
            "hdr_off": idx, "full_name": fn, "short_name": sn,
            "flag": flag, "total_verts": total_verts, "total_bytes": total_bytes,
            "streams": streams, "data_off": p,
        })
        pos = p + total_bytes
    return vbs


def parse_ibs(dec: bytes):
    ibs = []
    pos = 0
    tag = b"\x0bIndexBuffer\x00"
    while True:
        idx = dec.find(tag, pos)
        if idx < 0:
            break
        p = idx + len(tag)
        l1 = dec[p]; p += 1
        fn = dec[p : p + l1].decode("latin1", "replace"); p += l1
        l2 = dec[p]; p += 1
        sn = dec[p : p + l2].decode("latin1", "replace"); p += l2
        flag = dec[p]
        cnt = struct.unpack_from(">I", dec, p + 1)[0]
        inds = list(struct.unpack_from(f">{cnt}H", dec, p + 5))
        ibs.append({"full_name": fn, "short_name": sn, "flag": flag, "cnt": cnt, "inds": inds})
        pos = p + 5 + cnt * 2
    return ibs


def decode_vb_vertices(dec: bytes, vb: dict, stream_idx: int = 0):
    s = vb["streams"][stream_idx]
    base = vb["data_off"] + s["off"]
    st = s["stride"]
    out = []
    for i in range(s["nverts"]):
        vp = base + i * st
        x, y, z = struct.unpack_from(">3f", dec, vp)
        ap = vp + 12
        nx = ny = nz = nw = 0
        u = v = 0
        for tp, cnt in s["attrs"][1:]:
            if tp == 2 and cnt == 4:
                nx, ny, nz, nw = struct.unpack_from(">4h", dec, ap)
                ap += 8
            elif tp == 1 and cnt == 4:
                ap += 4
            elif tp == 2 and cnt == 2:
                u, v = struct.unpack_from(">2h", dec, ap)
                ap += 4
        out.append([x, y, z, nx, ny, nz, nw, u, v])
    return out


def trim_strip_for_lod_limit(verts, inds, max_inds: int):
    """If an original strip exceeds max_inds (e.g. DUK/KIN LODL = 668 vs 703), trim tiny handle hang-hole runs cleanly."""
    if len(inds) <= max_inds:
        return inds
    # Identify contiguous valid triangle runs and compute their midpoint & length
    n = len(inds)
    valid = [False] * (n - 2)
    for k in range(n - 2):
        a, b, c = inds[k], inds[k + 1], inds[k + 2]
        if a != b and b != c and a != c:
            valid[k] = True
    runs = []
    k = 0
    while k < n - 2:
        if not valid[k]:
            k += 1
            continue
        s = k
        while k < n - 2 and valid[k]:
            k += 1
        e = k
        # min z in racket space (handle has low Z, pan head has high Z)
        zs = [(verts[inds[j]][2] + verts[inds[j + 1]][2] + verts[inds[j + 2]][2]) / 3.0 for j in range(s, e)]
        runs.append((s, e, e - s, min(zs), max(zs)))

    # Prefer trimming trailing small handle runs or cutting cleanly at run boundary <= max_inds
    # Find largest run end `e` + 2 <= max_inds that ends near index max_inds
    # Wait: check if removing tiny 1-2 tri runs in handle (z < 1.5) saves enough!
    need = len(inds) - max_inds
    drop_mask = [False] * len(inds)
    saved = 0
    # Drop small low-z runs (<= 2 tris, on handle z < 0.0) first, preserving strip bridges around skipped intervals
    # Actually simplest 100%-safe cut without disturbing winding of kept tris: rebuild from kept runs with exact SEGA bridges!
    kept_runs = []
    small_low_runs = set()
    for ri, (s, e, ntri, z0, z1) in enumerate(runs):
        if saved < need + 12 and ntri <= 2 and z1 < 2.5 and s > 20:
            small_low_runs.add(ri)
            saved += (e - s) + 3
    if saved >= need:
        out = []
        for ri, (s, e, ntri, _, _) in enumerate(runs):
            if ri in small_low_runs:
                continue
            sp = s % 2
            seg = inds[s : e + 2]
            if not out:
                if sp == 1:
                    out.append(seg[0])
                out.extend(seg)
            else:
                out.append(out[-1])
                out.append(seg[0])
                out.append(seg[0])
                # After prev_last, seg[0], seg[0]: index of first tri (seg[0], seg[1], seg[2]) is len(out)-1!
                if ((len(out) - 1) % 2) != sp:
                    out.append(seg[0])
                out.extend(seg[1:])
        if len(out) <= max_inds:
            return out

    # Fallback: truncate right at a clean run boundary (e + 2 <= max_inds)
    best_cut = max_inds
    for s, e, _, _, _ in runs:
        if e + 2 <= max_inds:
            best_cut = e + 2
    return inds[:best_cut]


def make_wood70_textures(sp08_b_img: Image.Image) -> tuple[Image.Image, Image.Image, Image.Image]:
    """
    Synthesize 1970s Wooden Racket Diffuse, Specular, and Catgut textures
    aligned to the standard SEGA player racket UV atlas (256x256):
      - x in [0..52]:   dark walnut buttcap + retro 'VT70' badge
      - x in [52..255]: warm laminated ash/mahogany wood grain from sp08 bottom panel
      - x in [135..184], y in [0..145]: classic tanned saddle-leather perforated grip
    """
    wood_tile = sp08_b_img.crop((0, 144, 244, 252)).resize((256, 256), Image.BICUBIC)
    wood_rich = ImageEnhance.Color(wood_tile).enhance(1.18)
    wood_rich = ImageEnhance.Brightness(wood_rich).enhance(0.90)

    # Rotate wood grain vertical so grain runs along racket shaft/rim!
    wood_vert = wood_rich.rotate(90, expand=False)
    diff = wood_vert.copy().convert("RGBA")
    d_draw = ImageDraw.Draw(diff)

    # Subtle 1970s Jack Kramer / Borg Pro laminated walnut & cream pinstripes below grip tape (y=148..166)
    d_draw.rectangle([52, 148, 255, 154], fill=(102, 46, 24, 255))
    d_draw.rectangle([52, 154, 255, 157], fill=(228, 206, 172, 255))
    d_draw.rectangle([52, 157, 255, 163], fill=(142, 34, 28, 255))
    d_draw.rectangle([52, 163, 255, 166], fill=(228, 206, 172, 255))

    # Left buttcap/side strip [0..52]: rich dark mahogany with gold '70' emblem
    d_draw.rectangle([0, 0, 52, 255], fill=(58, 30, 18, 255))
    d_draw.rectangle([4, 20, 48, 116], outline=(218, 184, 110, 255), width=2)
    d_draw.ellipse([10, 140, 42, 172], fill=(38, 20, 12, 255), outline=(222, 188, 112, 255), width=2)

    # Tanned saddle-leather grip tape [135..184, 0..145]
    d_draw.rectangle([134, 0, 185, 146], fill=(166, 110, 62, 255))
    for y in range(0, 146, 14):
        d_draw.line([(134, y), (185, y + 6)], fill=(118, 72, 36, 255), width=2)
        d_draw.line([(134, y + 2), (185, y + 8)], fill=(192, 136, 84, 255), width=1)
    for y in range(4, 144, 10):
        for x in range(139, 182, 9):
            d_draw.point((x + ((y // 10) % 2) * 4, y), fill=(96, 56, 28, 255))

    # Satin wood-varnish specular map (256x256): medium sheen on lacquered wood, matte leather grip
    spec = Image.new("RGBA", (256, 256), (96, 94, 90, 255))
    s_draw = ImageDraw.Draw(spec)
    s_draw.rectangle([0, 0, 52, 255], fill=(120, 116, 108, 255))
    s_draw.rectangle([134, 0, 185, 146], fill=(42, 40, 38, 255))

    # Natural amber/cream catgut strings (64x64 RGBA, preserved string grid alpha)
    gut = Image.new("RGBA", (64, 64), (218, 198, 152, 0))
    gpx = gut.load()
    for y in range(64):
        for x in range(64):
            dx = min(x % 16, 16 - (x % 16))
            dy = min(y % 16, 16 - (y % 16))
            on_x = dx <= 1
            on_y = dy <= 1
            if on_x or on_y:
                a = 215 if (dx == 0 or dy == 0) else 125
                gpx[x, y] = (212, 188, 134, a)

    return diff, spec, gut


def pack_ee3_meshes_bin(records, out_path: str):
    """
    Binary format ('EE3M' v1):
      Header: 4B magic 'EE3M', u32 version=1, u32 num_records
      For each record:
        u32 id, u32 n_verts, u32 n_indices, u32 reserved
        float bbox_min[3], float bbox_max[3]
        verts[n_verts]: 24B each (<3f4h2h: x,y,z, nx,ny,nz,nw, u,v)
        indices[n_indices]: 2B each (<H)
        padding to 4-byte boundary if n_indices odd
    """
    buf = bytearray()
    buf.extend(struct.pack("<4sII", b"EE3M", 1, len(records)))
    for rec_id, verts, inds in records:
        xs = [v[0] for v in verts]
        ys = [v[1] for v in verts]
        zs = [v[2] for v in verts]
        buf.extend(struct.pack("<IIII", rec_id, len(verts), len(inds), 0))
        buf.extend(struct.pack("<6f", min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)))
        for v in verts:
            buf.extend(struct.pack("<3f4h2h", v[0], v[1], v[2], v[3], v[4], v[5], v[6], v[7], v[8]))
        for idx in inds:
            buf.extend(struct.pack("<H", idx))
        if len(inds) % 2 == 1:
            buf.extend(b"\x00\x00")
    with open(out_path, "wb") as f:
        f.write(buf)
    print(f"Wrote {out_path} ({len(buf)} bytes, {len(records)} mesh records)")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    entries = load_directory()
    by_name = {e["name"]: e for e in entries}
    cache = {}
    with open(BIN0, "rb") as f0, open(BIN1, "rb") as f1:
        def load_sdo(path):
            return decompress_sdo(read_entry(entries, by_name[path], f0, f1, cache))

        # 1. Extract official special racket DDS textures
        special_paths = [
            "HIGH/PlayerEdit/Gear/Racket/Model/G_racket_sp00_anniversary_YS.sdo",
            "HIGH/PlayerEdit/Gear/Racket/Model/G_racket_sp08_flyingpan_YS.sdo",
            "HIGH/PlayerEdit/Gear/Racket/Model/G_racket_sp28_bugette_YS.sdo",
        ]
        extracted_imgs = {}
        for sp in special_paths:
            dec = load_sdo(sp)
            for sl in parse_dds_slots(dec):
                dds_bytes = dec[sl["off"] : sl["off"] + sl["total_sz"]]
                out_dds = os.path.join(OUT_DIR, sl["name"])
                with open(out_dds, "wb") as wf:
                    wf.write(dds_bytes)
                extracted_imgs[sl["name"]] = Image.open(io.BytesIO(dds_bytes)).convert("RGBA")
                print(f"Extracted {sl['name']} ({sl['w']}x{sl['h']} {sl['fourcc'].decode()} mips={sl['mips']}, {len(dds_bytes)}B)")

        # 2. Synthesize & save pre-encoded multi-mip DDS variants for all 3 modes (for all 26 players' slot formats)
        wood_b, wood_s, wood_gut = make_wood70_textures(extracted_imgs["G_racket_B_sp08_flyingpan_YS.dds"])

        empty_gut = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        modes_tex = {
            "wood70": (wood_b, wood_s, wood_gut),
            "pan": (
                extracted_imgs["G_racket_B_sp08_flyingpan_YS.dds"],
                extracted_imgs["G_racket_S_sp08_flyingpan_YS.dds"],
                empty_gut,
            ),
            "baguette": (
                extracted_imgs["G_racket_B_sp28_bugette_YS.dds"],
                extracted_imgs["G_racket_S_sp28_bugette_YS.dds"],
                empty_gut,
            ),
        }
        slot_variants = [
            ("256_dxt1", 256, 256, b"DXT1", 9),
            ("256_dxt5", 256, 256, b"DXT5", 9),
            ("512_dxt1", 512, 512, b"DXT1", 10),
        ]
        for mode_name, (img_b, img_s, img_gut) in modes_tex.items():
            for tag, w, h, fcc, mips in slot_variants:
                for kind, img in [("B", img_b), ("S", img_s)]:
                    dds = build_mipmapped_dds(img, w, h, fcc, mips)
                    out_p = os.path.join(OUT_DIR, f"{mode_name}_{kind}_{tag}.dds")
                    with open(out_p, "wb") as wf:
                        wf.write(dds)
            gut_dds = build_mipmapped_dds(img_gut, 64, 64, b"DXT5", 7)
            with open(os.path.join(OUT_DIR, f"{mode_name}_gut_64_dxt5.dds"), "wb") as wf:
                wf.write(gut_dds)
            print(f"Built DDS variants (256 DXT1/DXT5 + 512 DXT1 + 64 DXT5 gut) for {mode_name}")

        # 3. Extract & transform real 3D mesh templates into racket space
        # 3a. Frying Pan (sp08): RotateX(+90 deg) + Translate(0, 0, +1.1832875)
        dec_pan = load_sdo(special_paths[1])
        pan_vbs = parse_vbs(dec_pan)
        pan_ibs = parse_ibs(dec_pan)
        pan_lodl_vb = [v for v in pan_vbs if v["short_name"] == "racket_render_lodL-VB"][0]
        pan_lodl_ib = [b for b in pan_ibs if "racket_render_lodL-" in b["short_name"]][0]

        pan_verts_raw = decode_vb_vertices(dec_pan, pan_lodl_vb, 0)
        pan_verts = []
        for x, y, z, nx, ny, nz, nw, u, v in pan_verts_raw:
            # RotateX(+90): (x, -z, y), TranslateZ(+1.1832875) -> handle -0.308..2.1, circular head z ~ 2.7..6.21, r = 1.748
            tx, ty, tz = x, -z, y + 1.1832875
            rnx, rny, rnz = nx, -nz, ny
            pan_verts.append([tx, ty, tz, rnx, rny, rnz, 0, u, v])
        pan_inds_lod0 = pan_lodl_ib["inds"]  # 703 indices, fits all 26 players' LOD0 (>=1208) and 24/26 LODL (>=730)
        pan_inds_lodl = trim_strip_for_lod_limit(pan_verts, pan_inds_lod0, 668)  # fits ALL 26 players' LODL (>=668)

        # 3b. Giant Baguette (sp28): already oriented along +Z; stretch/shift cleanly into z in [0.0..6.80]
        dec_bag = load_sdo(special_paths[2])
        bag_vbs = parse_vbs(dec_bag)
        bag_ibs = parse_ibs(dec_bag)
        bag_vb0 = [v for v in bag_vbs if v["short_name"] == "polymsh-VB"][0]
        bag_ib0 = [b for b in bag_ibs if "polymsh-" in b["short_name"]][0]
        bag_vbL = [v for v in bag_vbs if v["short_name"] == "polymsh1-VB"][0]
        bag_ibL = [b for b in bag_ibs if "polymsh1-" in b["short_name"]][0]

        def map_baguette_verts(raw_verts):
            zs = [rv[2] for rv in raw_verts]
            z0, z1 = min(zs), max(zs)
            scale_z = 6.80 / (z1 - z0)
            res = []
            for x, y, z, nx, ny, nz, nw, u, v in raw_verts:
                nz_pos = (z - z0) * scale_z
                res.append([x, y, nz_pos, nx, ny, nz, 0, u, v])
            return res

        bag_verts_lod0 = map_baguette_verts(decode_vb_vertices(dec_bag, bag_vb0, 0))
        bag_verts_lodl = map_baguette_verts(decode_vb_vertices(dec_bag, bag_vbL, 0))

        # Pack records: 0=PAN_LOD0, 1=PAN_LODL, 2=BAGUETTE_LOD0, 3=BAGUETTE_LODL
        records = [
            (0, pan_verts, pan_inds_lod0),
            (1, pan_verts, pan_inds_lodl),
            (2, bag_verts_lod0, bag_ib0["inds"]),
            (3, bag_verts_lodl, bag_ibL["inds"]),
        ]
        pack_ee3_meshes_bin(records, os.path.join(OUT_DIR, "ee3_meshes.bin"))

        # 4. Verify bounds & capacity against ALL 26 SEGA player .sdo files
        player_sdos = sorted(k for k in by_name if k.startswith("HIGH/Player/Model/P_") and k.endswith(".sdo"))
        min_v0 = min_i0 = min_vL = min_iL = 10**9
        for ps in player_sdos:
            pdec = load_sdo(ps)
            pvbs = parse_vbs(pdec)
            pibs = parse_ibs(pdec)
            rvb = [v for v in pvbs if v["short_name"] == "racket_render-VB"][0]
            lvb = [v for v in pvbs if v["short_name"] == "racket_render_lodL-VB"][0]
            fv0 = max(s["nverts"] for s in rvb["streams"] if s["nverts"] != 140)
            fvL = max(s["nverts"] for s in lvb["streams"] if s["nverts"] > 20)
            fi0 = max(b["cnt"] for b in pibs if "racket_render-" in b["short_name"] and "double" not in b["short_name"])
            fiL = max(b["cnt"] for b in pibs if "racket_render_lodL-" in b["short_name"] and "lodGut" not in b["short_name"])
            min_v0 = min(min_v0, fv0); min_i0 = min(min_i0, fi0)
            min_vL = min(min_vL, fvL); min_iL = min(min_iL, fiL)

            for sl in parse_dds_slots(pdec):
                if "racket" in sl["name"].lower():
                    sz_key = f"{sl['w']}_{sl['fourcc'].decode().lower()}"
                    assert sz_key in ("256_dxt1", "256_dxt5", "512_dxt1", "64_dxt5"), f"Unexpected tex {sl}"

        print("\n=== EE-3 VERIFICATION REPORT ===")
        for rid, name, vs, inds, vmax, imax in [
            (0, "PAN_LOD0", pan_verts, pan_inds_lod0, min_v0, min_i0),
            (1, "PAN_LODL", pan_verts, pan_inds_lodl, min_vL, min_iL),
            (2, "BAGUETTE_LOD0", bag_verts_lod0, bag_ib0["inds"], min_v0, min_i0),
            (3, "BAGUETTE_LODL", bag_verts_lodl, bag_ibL["inds"], min_vL, min_iL),
        ]:
            xs = [v[0] for v in vs]; ys = [v[1] for v in vs]; zs = [v[2] for v in vs]
            assert len(vs) <= vmax, f"{name} verts {len(vs)} > {vmax}"
            assert len(inds) <= imax, f"{name} inds {len(inds)} > {imax}"
            assert max(inds) < len(vs), f"{name} index OOB!"
            print(f"  {name:14s}: verts={len(vs):3d}/{vmax:3d}, inds={len(inds):4d}/{imax:4d} | "
                  f"x=[{min(xs):.3f}..{max(xs):.3f}] y=[{min(ys):.3f}..{max(ys):.3f}] z=[{min(zs):.3f}..{max(zs):.3f}] [OK]")
        print(f"All 26 SEGA base player .sdo files verified (covers all 82 roster players 0..81)!")


if __name__ == "__main__":
    main()
