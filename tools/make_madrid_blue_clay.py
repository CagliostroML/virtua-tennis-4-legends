#!/usr/bin/env python3
"""
Generate Madrid Blue Clay (Tierra Azul de Madrid) SDO stage files and official
Grand Slam / Mutua Madrid Open string tables for Virtua Tennis 4.

Touches ONLY loose files inside game/archive/ (reversible, leaves resource*.bin intact).
"""
import os
import struct
import sys
from PIL import Image

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

from vt4_archive import BIN0, BIN1, load_directory, read_entry, lzss_decompress
from compress_sega_lzss import lzss_compress_literal
from dxt_codec import _pack_rgb565, _unpack_rgb565


def _recolor_bc1_block(blk: bytearray, color_fn):
    c0, c1, bits = struct.unpack_from("<HHI", blk, 0)
    r0, g0, b0 = _unpack_rgb565(c0)
    r1, g1, b1 = _unpack_rgb565(c1)
    nr0, ng0, nb0 = color_fn(r0, g0, b0)
    nr1, ng1, nb1 = color_fn(r1, g1, b1)
    nc0 = _pack_rgb565(nr0, ng0, nb0)
    nc1 = _pack_rgb565(nr1, ng1, nb1)
    # Preserve 4-color vs 3-color mode ordering cleanly
    if (c0 > c1) and (nc0 <= nc1):
        if nc0 == nc1:
            if nc0 < 0xFFFF:
                nc0 += 1
            else:
                nc1 -= 1
        else:
            nc0, nc1 = nc1, nc0
            # Flip 2-bit indices 0<->1 and 2<->3
            # In BC1 4-color mode: 00->01, 01->00, 10->11, 11->10 => XOR every pair with 01!
            bits ^= 0x55555555
    elif (c0 <= c1) and (nc0 > nc1):
        nc0, nc1 = nc1, nc0
        # 3-color mode: 0<->1, 2 unchanged, 3 transparent
        new_bits = 0
        for i in range(16):
            idx = (bits >> (i * 2)) & 3
            if idx == 0:
                idx = 1
            elif idx == 1:
                idx = 0
            new_bits |= idx << (i * 2)
        bits = new_bits
    struct.pack_into("<HHI", blk, 0, nc0, nc1, bits)


def recolor_dds_blocks(dds_bytes: bytes, color_fn) -> bytes:
    """Recolor every mip level of a DXT1 or DXT5 DDS while keeping alpha & size identical."""
    fourcc = dds_bytes[84:88]
    if fourcc not in (b"DXT1", b"DXT5"):
        raise ValueError(f"Unsupported fourcc: {fourcc}")
    out = bytearray(dds_bytes)
    pos = 128
    blk_sz = 8 if fourcc == b"DXT1" else 16
    col_off = 0 if fourcc == b"DXT1" else 8
    while pos + blk_sz <= len(out):
        blk = bytearray(out[pos + col_off : pos + col_off + 8])
        _recolor_bc1_block(blk, color_fn)
        out[pos + col_off : pos + col_off + 8] = blk
        pos += blk_sz
    return bytes(out)


def clay_to_madrid_blue(r: int, g: int, b: int):
    luma = 0.299 * r + 0.587 * g + 0.114 * b
    nr = int(max(0, min(255, luma * 0.34)))
    ng = int(max(0, min(255, luma * 0.96)))
    nb = int(max(0, min(255, luma * 1.78)))
    return (nr, ng, nb)


def lightmap_to_cool_blue(r: int, g: int, b: int):
    # Preserve neutral light/whites; swap warm orange bias into cool blue-tint bias
    warmth = max(0, r - b)
    if warmth <= 6:
        return (r, g, b)
    luma = 0.299 * r + 0.587 * g + 0.114 * b
    nb = min(255, r)
    ng = min(255, int(g * 0.94 + warmth * 0.12))
    nr = max(0, int(b * 0.95 - warmth * 0.08 + (luma - b) * 0.12))
    return (nr, ng, nb)


def line_clay_to_madrid_blue(r: int, g: int, b: int):
    # Recolor brown/orange clay scuffs peeking through court lines while keeping white chalk lines pure
    if r > b + 18:
        return clay_to_madrid_blue(r, g, b)
    return (r, g, b)


def patch_sdo_stage(entries, f0, f1, cache, archive_name: str, out_rel_path: str, preview_dir: str | None = None):
    e = next(x for x in entries if x["name"].lower() == archive_name.lower())
    comp_sdo = read_entry(entries, e, f0, f1, cache)
    raw = bytearray(lzss_decompress(comp_sdo))

    # Locate UV_surface, IL_surface, and scuffed line DDS blobs
    patched_count = 0
    pos = 0
    while True:
        pos = raw.find(b"DDS ", pos)
        if pos < 0:
            break
        ctx = bytes(raw[max(0, pos - 64) : pos])
        sz = struct.unpack(">I", raw[pos - 4 : pos])[0]
        if b"UV_surface_OG" in ctx:
            print(f"[{archive_name}] Recoloring UV_surface at 0x{pos:x} (sz=0x{sz:x})...")
            recolored = recolor_dds_blocks(bytes(raw[pos : pos + sz]), clay_to_madrid_blue)
            raw[pos : pos + sz] = recolored
            patched_count += 1
            if preview_dir:
                p_dds = os.path.join(preview_dir, os.path.basename(out_rel_path) + "_uv.dds")
                open(p_dds, "wb").write(recolored)
                im = Image.open(p_dds)
                im.save(p_dds[:-4] + ".png")
        elif b"IL_surface_" in ctx:
            print(f"[{archive_name}] Recoloring IL_surface at 0x{pos:x} (sz=0x{sz:x})...")
            recolored = recolor_dds_blocks(bytes(raw[pos : pos + sz]), lightmap_to_cool_blue)
            raw[pos : pos + sz] = recolored
            patched_count += 1
            if preview_dir:
                p_dds = os.path.join(preview_dir, os.path.basename(out_rel_path) + "_il.dds")
                open(p_dds, "wb").write(recolored)
                im = Image.open(p_dds)
                im.thumbnail((512, 512))
                im.save(p_dds[:-4] + ".png")
        elif b"B_AU_line" in ctx:
            print(f"[{archive_name}] Recoloring scuffed line clay at 0x{pos:x} (sz=0x{sz:x})...")
            recolored = recolor_dds_blocks(bytes(raw[pos : pos + sz]), line_clay_to_madrid_blue)
            raw[pos : pos + sz] = recolored
            patched_count += 1
        pos += 4

    assert patched_count == 4, f"Expected 4 surface/line DDS patches in {archive_name}, got {patched_count}"
    out_path = os.path.join(REPO_ROOT, "game", "archive", out_rel_path.replace("/", os.sep))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    comp_out = lzss_compress_literal(bytes(raw))
    with open(out_path, "wb") as out_f:
        out_f.write(comp_out)
    print(f"Wrote {out_path} ({len(comp_out)} bytes compressed from {len(raw)} bytes)")


def patch_sto_exact(raw_bytes: bytes, replacements: list[tuple[str, str]]) -> bytes:
    """Replace UTF-8 strings inside XML2 .sto keeping EXACT same UTF-8 byte lengths (safe against fixed headers)."""
    buf = bytearray(raw_bytes)
    for old_s, new_s in replacements:
        ob = old_s.encode("utf-8")
        nb = new_s.encode("utf-8")
        if len(nb) < len(ob):
            nb = nb + b" " * (len(ob) - len(nb))
        assert len(ob) == len(nb), f"Byte length mismatch: {old_s!r}({len(ob)}) != {new_s!r}({len(nb)})"
        count = 0
        pos = 0
        while True:
            pos = buf.find(ob + b"\x00", pos)
            if pos < 0:
                break
            buf[pos : pos + len(nb)] = nb
            count += 1
            pos += len(nb)
        print(f"  .sto replace {old_s!r} -> {new_s!r} ({count}x)")
    return bytes(buf)


def build_official_text_overrides(entries, f0, f1, cache):
    spa_map = [
        ("Marbella, Espa\u00f1a", "Madrid Azul, Esp."),            # 17B
        ("Melbourne, Australia", "Melbourne (AO)"),               # 20B
        ("Par\u00eds, Francia", "Par\u00eds (RG)"),               # 15B
        ("Nueva York, EE. UU.", "N. York (US Open)"),             # 19B
        ("Londres, Gran Breta\u00f1a", "Londres (Wimbledon)"),    # 23B
        ("Campeonato mediterr\u00e1neo", "Mutua Madrid Open"),    # 25B
        ("Campeonato de Australia", "Australian Open Oficial"),   # 23B
        ("Campeonato de Francia", "Roland Garros Oficial"),       # 21B
        ("Cl\u00e1sico tenis Inglaterra", "Torneo de Wimbledon"), # 25B
        ("Supertenis EE. UU.", "US Open Oficial"),                # 18B
    ]
    eng_map = [
        ("Marbella, Spain", "Madrid BlueClay"),                   # 15B
        ("Melbourne, Australia", "Melbourne (Aus Open)"),         # 20B
        ("Paris, France", "Paris (RG)"),                          # 13B
        ("New York, USA", "New York (US)"),                       # 13B
        ("London, Great Britain", "London (Wimbledon)"),          # 21B
        ("Mediterranean Championship", "Mutua Madrid Open"),      # 26B
        ("Australia Challenge", "Australian Open"),              # 19B
        ("French Cup", "Rol.Garros"),                             # 10B
        ("England Tennis Classic", "Wimbledon Official"),         # 22B
        ("US Super Tennis", "US Open Finals"),                    # 15B
    ]
    for lang, rep in [("SPA", spa_map), ("ENG", eng_map)]:
        name = f"Frontend/text/{lang}/TR_COMMON.sto"
        e = next(x for x in entries if x["name"].lower() == name.lower())
        comp_outer = read_entry(entries, e, f0, f1, cache)
        # Decompress inner XML2 layer
        inner = lzss_decompress(comp_outer)
        patched_inner = patch_sto_exact(inner, rep)
        comp_out = lzss_compress_literal(patched_inner)
        out_path = os.path.join(REPO_ROOT, "game", "archive", "Frontend", "text", lang, "TR_COMMON.sto")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(comp_out)
        print(f"Wrote {out_path} ({len(comp_out)} bytes)")


def main():
    preview_dir = r"C:\Users\acorr\.gemini\antigravity\brain\22a1c44f-d683-498e-b4f7-f89eb5b5386f\scratch\spa2_tex"
    os.makedirs(preview_dir, exist_ok=True)
    entries = load_directory()
    cache = {}
    with open(BIN0, "rb") as f0, open(BIN1, "rb") as f1:
        patch_sdo_stage(entries, f0, f1, cache, "HIGH/Stage/TA_S_Spa2FS_B_stage_OG.sdo", "HIGH/Stage/TA_S_Spa2FS_B_stage_OG.sdo", preview_dir)
        patch_sdo_stage(entries, f0, f1, cache, "HIGH/Stage/TA_S_Spa2FD_B_stage_OG.sdo", "HIGH/Stage/TA_S_Spa2FD_B_stage_OG.sdo", preview_dir)
        build_official_text_overrides(entries, f0, f1, cache)


if __name__ == "__main__":
    main()
