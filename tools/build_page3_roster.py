#!/usr/bin/env python3
"""
Build Page 3 Roster Expansion assets (IDs 38..58) for Virtua Tennis 4: Legends & Next-Gen Edition.
Generates:
  1. game/archive/HIGH/Player/Model/P_<M|W>_<CODE>_<Author>.sdo (+ _culling/_deformable .zml)
  2. game/archive/HIGH/Frontend/VR/photo_L/38..58.dds (placeholders or real PhotoCraft cutouts)
"""
import argparse
import os
import struct
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

from vt4_archive import BIN0, BIN1, load_directory, read_entry, lzss_decompress
from compress_sega_lzss import lzss_compress_literal
from dxt_codec import encode_dds
from make_madrid_blue_clay import recolor_dds_blocks
from PIL import Image


def _tint(r_mul, r_add, g_mul, g_add, b_mul, b_add):
    def fn(r, g, b):
        return (
            max(0, min(255, int(r * r_mul + r_add))),
            max(0, min(255, int(g * g_mul + g_add))),
            max(0, min(255, int(b * b_mul + b_add))),
        )
    return fn


def _solid(rgb):
    return lambda r, g, b: rgb


# IDs 38..58 MUST match g_extra_players[21] in src/xlive/xlive.c
PAGE3_STARS = [
    # 38 Wawrinka: crimson & white / Swiss colors
    {"id": 38, "code": "WAW", "name": "Stan Wawrinka", "author": "NG", "man": 1, "base": "P_M_FED_SN", "proxy_id": 0,
     "wear_fn": _tint(1.15, 45, 0.30, 8, 0.34, 10), "acc_fn": _tint(0.95, 40, 0.95, 40, 0.95, 40), "hair_fn": _tint(0.65, 0, 0.55, 0, 0.45, 0)},
    # 39 Medvedev: navy blue & white
    {"id": 39, "code": "MED", "name": "Daniil Medvedev", "author": "NG", "man": 1, "base": "P_M_DJV_IT", "proxy_id": 2,
     "wear_fn": _tint(0.32, 10, 0.48, 22, 1.05, 65), "acc_fn": _tint(0.95, 45, 0.95, 45, 0.95, 45), "hair_fn": _tint(0.75, 0, 0.65, 0, 0.55, 0)},
    # 40 Zverev: teal & black
    {"id": 40, "code": "ZVE", "name": "Alexander Zverev", "author": "NG", "man": 1, "base": "P_M_DJV_IT", "proxy_id": 2,
     "wear_fn": _tint(0.25, 8, 0.95, 48, 0.92, 45), "acc_fn": _solid((28, 30, 34)), "hair_fn": _tint(1.15, 25, 1.05, 15, 0.65, 0)},
    # 41 Tsitsipas: clean white & Hellenic blue headband
    {"id": 41, "code": "TSI", "name": "Stefanos Tsitsipas", "author": "NG", "man": 1, "base": "P_M_FED_SN", "proxy_id": 0,
     "wear_fn": _tint(0.92, 42, 0.94, 44, 0.98, 48), "acc_fn": _tint(0.32, 10, 0.68, 35, 1.15, 75), "hair_fn": _tint(0.78, 0, 0.66, 0, 0.48, 0)},
    # 42 Thiem: vibrant burnt orange & black
    {"id": 42, "code": "THI", "name": "Dominic Thiem", "author": "NG", "man": 1, "base": "P_M_GON_SN", "proxy_id": 7,
     "wear_fn": _tint(1.22, 65, 0.58, 18, 0.22, 5), "acc_fn": _solid((32, 32, 36)), "hair_fn": _tint(0.95, 10, 0.80, 0, 0.55, 0)},
    # 43 Kyrgios: black with electric neon lime trim
    {"id": 43, "code": "KYR", "name": "Nick Kyrgios", "author": "NG", "man": 1, "base": "P_M_ROD_SN", "proxy_id": 5,
     "wear_fn": _tint(0.28, 10, 0.28, 10, 0.30, 12), "acc_fn": _tint(0.75, 45, 1.25, 80, 0.20, 5), "hair_fn": _tint(0.42, 0, 0.38, 0, 0.34, 0)},
    # 44 Hewitt: Aussie gold & dark navy (uses Roddick base w/ cap & light skin)
    {"id": 44, "code": "HEW", "name": "Lleyton Hewitt", "author": "LG", "man": 1, "base": "P_M_ROD_SN", "proxy_id": 5,
     "wear_fn": _tint(1.15, 55, 0.96, 35, 0.22, 5), "acc_fn": _tint(0.28, 8, 0.42, 16, 0.92, 48), "hair_fn": _tint(1.15, 20, 1.02, 10, 0.60, 0)},
    # 45 Safin: dark charcoal & crimson trim
    {"id": 45, "code": "SAF", "name": "Marat Safin", "author": "LG", "man": 1, "base": "P_M_DJV_IT", "proxy_id": 2,
     "wear_fn": _tint(0.45, 12, 0.46, 12, 0.48, 14), "acc_fn": _tint(1.15, 55, 0.26, 8, 0.26, 8), "hair_fn": _tint(0.55, 0, 0.48, 0, 0.42, 0)},
    # 46 Tsonga: French royal blue & red
    {"id": 46, "code": "TSO", "name": "Jo-Wilfried Tsonga", "author": "LG", "man": 1, "base": "P_M_MON_SN", "proxy_id": 6,
     "wear_fn": _tint(0.32, 12, 0.48, 22, 1.18, 70), "acc_fn": _tint(1.18, 60, 0.28, 10, 0.30, 10), "hair_fn": None},
    # 47 Ferrero: Spanish scarlet red & black
    {"id": 47, "code": "FRR", "name": "Juan Carlos Ferrero", "author": "LG", "man": 1, "base": "P_M_HAS_IT", "proxy_id": 10,
     "wear_fn": _tint(1.18, 55, 0.24, 8, 0.24, 8), "acc_fn": _solid((28, 28, 32)), "hair_fn": _tint(0.58, 0, 0.48, 0, 0.38, 0)},
    # 48 Moya: Mallorca crimson/white & headband
    {"id": 48, "code": "MOY", "name": "Carlos Moya", "author": "LG", "man": 1, "base": "P_M_NAD_IT", "proxy_id": 1,
     "wear_fn": _tint(1.12, 50, 0.28, 10, 0.28, 10), "acc_fn": _tint(0.95, 45, 0.95, 45, 0.95, 45), "hair_fn": _tint(0.48, 0, 0.42, 0, 0.36, 0)},
    # 49 Ferrer: deep navy & neon yellow-green
    {"id": 49, "code": "FER", "name": "David Ferrer", "author": "LG", "man": 1, "base": "P_M_SEP_IT", "proxy_id": 9,
     "wear_fn": _tint(0.30, 10, 0.45, 18, 0.98, 55), "acc_fn": _tint(1.05, 50, 1.18, 60, 0.24, 5), "hair_fn": _tint(0.62, 0, 0.50, 0, 0.38, 0)},
    # 50 Nalbandian: Albiceleste sky blue & white
    {"id": 50, "code": "NAL", "name": "David Nalbandian", "author": "LG", "man": 1, "base": "P_M_COU_SN", "proxy_id": 13,
     "wear_fn": _tint(0.42, 24, 0.85, 58, 1.22, 85), "acc_fn": _tint(0.95, 45, 0.95, 45, 0.95, 45), "hair_fn": _tint(0.55, 0, 0.45, 0, 0.38, 0)},
    # 51 Lendl: crisp 80s white & emerald Adidas stripes
    {"id": 51, "code": "LEN", "name": "Ivan Lendl", "author": "LG", "man": 1, "base": "P_M_FED_SN", "proxy_id": 0,
     "wear_fn": _tint(0.95, 45, 0.95, 45, 0.95, 45), "acc_fn": _tint(0.24, 8, 0.88, 36, 0.45, 18), "hair_fn": _tint(1.15, 25, 0.78, 5, 0.42, 0)},
    # 52 Connors: vintage white & brick red trim
    {"id": 52, "code": "CON", "name": "Jimmy Connors", "author": "LG", "man": 1, "base": "P_M_NAD_IT", "proxy_id": 1,
     "wear_fn": _tint(0.92, 42, 0.92, 42, 0.92, 42), "acc_fn": _tint(1.18, 58, 0.28, 10, 0.26, 8), "hair_fn": _tint(0.62, 0, 0.52, 0, 0.42, 0)},
    # 53 Vilas: classic white & Fila navy
    {"id": 53, "code": "VIL", "name": "Guillermo Vilas", "author": "LG", "man": 1, "base": "P_M_EDB_SN", "proxy_id": 14,
     "wear_fn": _tint(0.94, 44, 0.94, 44, 0.94, 44), "acc_fn": _tint(0.28, 8, 0.42, 16, 0.95, 48), "hair_fn": _tint(0.52, 0, 0.44, 0, 0.36, 0)},
    # 54 Ivanisevic: Croatian blue/red
    {"id": 54, "code": "IVN", "name": "Goran Ivanisevic", "author": "LG", "man": 1, "base": "P_M_NAD_IT", "proxy_id": 1,
     "wear_fn": _tint(0.32, 10, 0.55, 24, 1.15, 65), "acc_fn": _tint(1.15, 55, 0.25, 8, 0.28, 8), "hair_fn": _tint(0.75, 0, 0.65, 0, 0.52, 0)},
    # 55 Evert: 70s Wimbledon white & cobalt blue trim
    {"id": 55, "code": "EVE", "name": "Chris Evert", "author": "LG", "man": 0, "base": "P_W_KUZ_IT", "proxy_id": 19,
     "wear_fn": _tint(0.96, 48, 0.96, 48, 0.96, 48), "acc_fn": _tint(0.32, 10, 0.56, 26, 1.15, 70), "hair_fn": _tint(1.18, 25, 1.05, 15, 0.68, 0)},
    # 56 Seles: iconic 90s purple & white
    {"id": 56, "code": "SEL", "name": "Monica Seles", "author": "LG", "man": 0, "base": "P_W_ROB_IT", "proxy_id": 23,
     "wear_fn": _tint(0.85, 45, 0.28, 8, 1.18, 72), "acc_fn": _tint(0.95, 45, 0.95, 45, 0.95, 45), "hair_fn": _tint(0.55, 0, 0.45, 0, 0.38, 0)},
    # 57 Henin: Belgian crimson/gold & black
    {"id": 57, "code": "HEN", "name": "Justine Henin", "author": "LG", "man": 0, "base": "P_W_WOZ_IT", "proxy_id": 22,
     "wear_fn": _tint(1.18, 52, 0.30, 8, 0.30, 8), "acc_fn": _solid((28, 28, 32)), "hair_fn": _tint(0.95, 10, 0.72, 0, 0.42, 0)},
    # 58 Muguruza: mint / emerald & white
    {"id": 58, "code": "MUG", "name": "Garbine Muguruza", "author": "NG", "man": 0, "base": "P_W_SHA_SN", "proxy_id": 17,
     "wear_fn": _tint(0.28, 12, 1.05, 58, 0.85, 42), "acc_fn": _tint(0.95, 45, 0.95, 45, 0.95, 45), "hair_fn": _tint(0.45, 0, 0.38, 0, 0.32, 0)},
]


def build_models():
    entries = load_directory()
    cache = {}
    out_dir = os.path.join(REPO_ROOT, "game", "archive", "HIGH", "Player", "Model")
    os.makedirs(out_dir, exist_ok=True)
    raw_cache = {}

    with open(BIN0, "rb") as f0, open(BIN1, "rb") as f1:
        for st in PAGE3_STARS:
            base = st["base"]
            gender = "M" if st["man"] else "W"
            out_sdo_name = f"P_{gender}_{st['code']}_{st['author']}.sdo"
            out_base_prefix = f"P_{gender}_{st['code']}"
            base_short = base[:7]

            if base not in raw_cache:
                e_sdo = next(x for x in entries if x["name"].lower() == f"high/player/model/{base.lower()}.sdo")
                raw_cache[base] = lzss_decompress(read_entry(entries, e_sdo, f0, f1, cache))
            raw = bytearray(raw_cache[base])

            pos = 0
            tweaks = 0
            while True:
                pos = raw.find(b"DDS ", pos)
                if pos < 0:
                    break
                ctx = bytes(raw[max(0, pos - 48) : pos])
                sz = struct.unpack(">I", raw[pos - 4 : pos])[0]
                fn = None
                if (b"_B_wear" in ctx or b"_B_pants" in ctx) and st["wear_fn"]:
                    fn = st["wear_fn"]
                elif b"_B_accessory" in ctx and st["acc_fn"]:
                    fn = st["acc_fn"]
                elif b"_B_hair" in ctx and st["hair_fn"]:
                    fn = st["hair_fn"]
                if fn is not None:
                    raw[pos : pos + sz] = recolor_dds_blocks(bytes(raw[pos : pos + sz]), fn)
                    tweaks += 1
                pos += 4

            comp = lzss_compress_literal(bytes(raw))
            with open(os.path.join(out_dir, out_sdo_name), "wb") as f:
                f.write(comp)

            for suffix in ["_culling.zml", "_deformable.zml"]:
                ez = next(x for x in entries if x["name"].lower() == f"high/player/model/{base_short.lower()}{suffix}")
                zdata = read_entry(entries, ez, f0, f1, cache)
                with open(os.path.join(out_dir, f"{out_base_prefix}{suffix}"), "wb") as f:
                    f.write(zdata)

            print(f"[{st['id']}] Built {out_sdo_name} (from {base}, {tweaks} tex recolored, {len(comp)} B)")


def build_placeholder_portraits(overwrite=False):
    entries = load_directory()
    cache = {}
    out_dir = os.path.join(REPO_ROOT, "game", "archive", "HIGH", "Frontend", "VR", "photo_L")
    os.makedirs(out_dir, exist_ok=True)
    with open(BIN0, "rb") as f0, open(BIN1, "rb") as f1:
        for st in PAGE3_STARS:
            out_path = os.path.join(out_dir, f"{st['id']}.dds")
            if not overwrite and os.path.exists(out_path):
                continue
            pname = f"high/frontend/vr/photo_l/{st['proxy_id']}.dds"
            ep = next(x for x in entries if x["name"].lower() == pname)
            data = read_entry(entries, ep, f0, f1, cache)
            with open(out_path, "wb") as f:
                f.write(data)
            print(f"[{st['id']}] Wrote placeholder portrait {out_path} (from {st['proxy_id']}.dds)")


def build_portraits_from_cutouts():
    cut_dir = os.path.join(REPO_ROOT, "assets", "portraits_page3_src", "cutouts")
    out_dir = os.path.join(REPO_ROOT, "game", "archive", "HIGH", "Frontend", "VR", "photo_L")
    os.makedirs(out_dir, exist_ok=True)
    for st in PAGE3_STARS:
        slug = st["name"].split()[-1].lower()
        cp = os.path.join(cut_dir, f"{st['id']}_{slug}.png")
        if not os.path.isfile(cp):
            continue
        im = Image.open(cp).convert("RGBA").resize((256, 256), Image.Resampling.LANCZOS)
        r, g, b, a = im.split()
        a = a.point(lambda v: 0 if v <= 6 else v)
        dds = encode_dds(Image.merge("RGBA", (r, g, b, a)), b"RGBA")
        out_path = os.path.join(out_dir, f"{st['id']}.dds")
        with open(out_path, "wb") as f:
            f.write(dds)
        print(f"[{st['id']}] Encoded portrait {out_path} ({len(dds)} B)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", action="store_true", help="Build .sdo/.zml models for 38..58")
    ap.add_argument("--portraits", action="store_true", help="Encode cutouts/*.png to photo_L/38..58.dds")
    ap.add_argument("--placeholders", action="store_true", help="Write missing photo_L/38..58.dds placeholders")
    ap.add_argument("--overwrite-placeholders", action="store_true")
    args = ap.parse_args()
    if not (args.models or args.portraits or args.placeholders or args.overwrite_placeholders):
        args.models = True
        args.portraits = True
    if args.models:
        build_models()
    if args.portraits:
        build_portraits_from_cutouts()
    if args.placeholders or args.overwrite_placeholders:
        build_placeholder_portraits(overwrite=args.overwrite_placeholders)


if __name__ == "__main__":
    main()
