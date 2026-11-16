#!/usr/bin/env python3
"""
Build Fase 2 Roster Expansion assets for Virtua Tennis 4: Legends & Next-Gen Edition.
Generates:
  1. game/archive/Config/Fraw/fwDataDB/fwDataDB_Player.bin (slots 26..37 ALC..NAV)
  2. game/archive/HIGH/Frontend/VR/photo_L/26..37.dds (real photos, soft alpha vignette)
  3. game/archive/HIGH/Player/Model/P_<M/W>_<CODE>_<Author>.sdo (+ _culling/_deformable .zml)
"""
import math
import os
import struct
import sys
from PIL import Image

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

from vt4_archive import BIN0, BIN1, load_directory, read_entry, lzss_decompress
from compress_sega_lzss import lzss_compress_literal
from compile_fwdatadb import compile_fwdatadb, decompile_fwdatadb
from dxt_codec import encode_dds
from make_madrid_blue_clay import recolor_dds_blocks

REAL_PHOTOS_DIR = r"C:\Users\acorr\.gemini\antigravity\brain\22a1c44f-d683-498e-b4f7-f89eb5b5386f\scratch\portraits_real"

# 12 New Legends & Next-Gen Superstars mapped to fwDataDB_Player IDs 26..37
NEW_STARS = [
    {
        "id": 26, "code": "ALC", "short": "C.ALCARAZ", "author": "NG", "man": 1,
        "smin": 112, "smax": 224, "style": "Hard Hit", "type": 1, "h": 183, "w": 74, "bh2": 1, "lefty": 0, "voice": "vo_m_nad",
        "photo": "26_Carlos Alcaraz.jpg", "base": "P_M_NAD_IT",
        "wear_fn": lambda r, g, b: (min(255, int(r * 0.28 + 10)), min(255, int(g * 0.85 + 90)), min(255, int(b * 1.15 + 140))),
        "acc_fn":  lambda r, g, b: (min(255, int(r * 1.15 + 110)), min(255, int(g * 0.55 + 30)), int(b * 0.18)),
        "hair_fn": None,
    },
    {
        "id": 27, "code": "SIN", "short": "J.SINNER", "author": "NG", "man": 1,
        "smin": 114, "smax": 222, "style": "All Round", "type": 1, "h": 191, "w": 77, "bh2": 1, "lefty": 0, "voice": "vo_m_djv",
        "photo": "27_Jannik Sinner.jpg", "base": "P_M_DJV_IT",
        "wear_fn": lambda r, g, b: (min(255, int(r * 0.95 + 65)), min(255, int(g * 0.72 + 45)), min(255, int(b * 0.52 + 25))),
        "acc_fn":  lambda r, g, b: (min(255, r + 50), min(255, g + 45), min(255, b + 45)),
        "hair_fn": lambda r, g, b: (min(255, int(r * 1.35 + 65)), min(255, int(g * 0.72 + 12)), max(0, int(b * 0.25))),
    },
    {
        "id": 28, "code": "SAM", "short": "P.SAMPRAS", "author": "LG", "man": 1,
        "smin": 118, "smax": 226, "style": "Serve & Volley", "type": 1, "h": 185, "w": 77, "bh2": 0, "lefty": 0, "voice": "vo_m_fed",
        "photo": "28_Pete Sampras.jpg", "base": "P_M_FED_SN",
        "wear_fn": lambda r, g, b: (min(255, int(r * 0.88 + 45)), min(255, int(g * 0.90 + 48)), min(255, int(b * 0.96 + 52))),
        "acc_fn":  lambda r, g, b: (int(r * 0.35), int(g * 0.42), min(255, int(b * 0.85 + 35))),
        "hair_fn": lambda r, g, b: (int(r * 0.55), int(g * 0.50), int(b * 0.48)),
    },
    {
        "id": 29, "code": "AGA", "short": "A.AGASSI", "author": "LG", "man": 1,
        "smin": 105, "smax": 208, "style": "Strong Forehand", "type": 1, "h": 180, "w": 80, "bh2": 1, "lefty": 0, "voice": "vo_m_has",
        "photo": "29_Andre Agassi.jpg", "base": "P_M_HAS_IT",
        "wear_fn": lambda r, g, b: (min(255, int(r * 1.25 + 75)), max(0, int(g * 0.28)), min(255, int(b * 0.88 + 45))),
        "acc_fn":  lambda r, g, b: (32, 32, 36),
        "hair_fn": None,
    },
    {
        "id": 30, "code": "BOR", "short": "B.BORG", "author": "LG", "man": 1,
        "smin": 104, "smax": 206, "style": "Solid Defence", "type": 1, "h": 180, "w": 73, "bh2": 1, "lefty": 0, "voice": "vo_m_edb",
        "photo": "30_Björn Borg.jpg", "base": "P_M_EDB_SN",
        "wear_fn": lambda r, g, b: (min(255, int(r * 0.95 + 38)), min(255, int(g * 0.90 + 28)), min(255, int(b * 0.82 + 18))),
        "acc_fn":  lambda r, g, b: (min(255, int(r * 1.25 + 65)), int(g * 0.22), int(b * 0.22)),
        "hair_fn": lambda r, g, b: (min(255, int(r * 1.22 + 30)), min(255, int(g * 1.10 + 18)), int(b * 0.65)),
    },
    {
        "id": 31, "code": "MCE", "short": "J.MCENROE", "author": "LG", "man": 1,
        "smin": 106, "smax": 208, "style": "Aggressive Volley", "type": 1, "h": 180, "w": 75, "bh2": 0, "lefty": 1, "voice": "vo_m_bec",
        "photo": "31_John McEnroe.jpg", "base": "P_M_BEC_SN",
        "wear_fn": lambda r, g, b: (min(255, int(r * 0.45 + 15)), min(255, int(g * 0.55 + 22)), min(255, int(b * 1.15 + 65))),
        "acc_fn":  lambda r, g, b: (min(255, int(r * 1.25 + 80)), int(g * 0.25), int(b * 0.25)),
        "hair_fn": lambda r, g, b: (int(r * 0.65), int(g * 0.55), int(b * 0.48)),
    },
    {
        "id": 32, "code": "GRA", "short": "S.GRAF", "author": "LG", "man": 0,
        "smin": 102, "smax": 202, "style": "Strong Forehand", "type": 1, "h": 176, "w": 64, "bh2": 0, "lefty": 0, "voice": "vo_w_sha",
        "photo": "32_Steffi Graf.jpg", "base": "P_W_SHA_SN",
        "wear_fn": lambda r, g, b: (min(255, r + 45), min(255, g + 45), min(255, b + 48)),
        "acc_fn":  lambda r, g, b: (min(255, int(r * 1.2 + 50)), int(g * 0.22), int(b * 0.22)),
        "hair_fn": lambda r, g, b: (min(255, int(r * 1.12 + 20)), min(255, int(g * 1.04 + 12)), int(b * 0.72)),
    },
    {
        "id": 33, "code": "SER", "short": "S.WILLIAMS", "author": "NG", "man": 0,
        "smin": 110, "smax": 210, "style": "Big Serve", "type": 1, "h": 175, "w": 70, "bh2": 1, "lefty": 0, "voice": "vo_w_wil",
        "photo": "33_Serena Williams.jpg", "base": "P_W_WIL_SN",
        "wear_fn": lambda r, g, b: (min(255, int(r * 0.72 + 45)), int(g * 0.26), min(255, int(b * 1.15 + 75))),
        "acc_fn":  lambda r, g, b: (min(255, int(r * 0.78 + 40)), int(g * 0.24), min(255, int(b * 1.10 + 70))),
        "hair_fn": None,
    },
    {
        "id": 34, "code": "SWI", "short": "I.SWIATEK", "author": "NG", "man": 0,
        "smin": 98, "smax": 194, "style": "Hard Hit", "type": 1, "h": 176, "w": 65, "bh2": 1, "lefty": 0, "voice": "vo_w_woz",
        "photo": "34_Iga Świątek.jpg", "base": "P_W_WOZ_IT",
        "wear_fn": lambda r, g, b: (min(255, int(r * 1.15 + 65)), int(g * 0.26), int(b * 0.34)),
        "acc_fn":  lambda r, g, b: (min(255, r + 40), min(255, g + 35), min(255, b + 35)),
        "hair_fn": lambda r, g, b: (int(r * 0.52), int(g * 0.38), int(b * 0.28)),
    },
    {
        "id": 35, "code": "SAB", "short": "A.SABALENKA", "author": "NG", "man": 0,
        "smin": 108, "smax": 208, "style": "Big Serve", "type": 1, "h": 182, "w": 80, "bh2": 1, "lefty": 0, "voice": "vo_w_sha",
        "photo": "35_Aryna Sabalenka.jpg", "base": "P_W_CHA_IT",
        "wear_fn": lambda r, g, b: (min(255, int(r * 0.85 + 50)), int(g * 0.22), min(255, int(b * 1.05 + 65))),
        "acc_fn":  lambda r, g, b: (min(255, int(r * 1.1 + 50)), int(g * 0.25), min(255, int(b * 0.7 + 30))),
        "hair_fn": lambda r, g, b: (min(255, int(r * 1.1 + 15)), min(255, int(g * 1.02 + 10)), int(b * 0.72)),
    },
    {
        "id": 36, "code": "KUE", "short": "G.KUERTEN", "author": "LG", "man": 1,
        "smin": 108, "smax": 214, "style": "Ground Stroke", "type": 1, "h": 191, "w": 83, "bh2": 0, "lefty": 0, "voice": "vo_m_nad",
        "photo": "36_Gustavo Kuerten.jpg", "base": "P_M_RAF_IT",
        "wear_fn": lambda r, g, b: (int(r * 0.22), min(255, int(g * 0.72 + 55)), min(255, int(b * 1.25 + 95))),
        "acc_fn":  lambda r, g, b: (min(255, int(r * 1.3 + 95)), min(255, int(g * 1.18 + 75)), int(b * 0.15)),
        "hair_fn": lambda r, g, b: (int(r * 0.72), int(g * 0.56), int(b * 0.42)),
    },
    {
        "id": 37, "code": "NAV", "short": "M.NAVRATILOVA", "author": "LG", "man": 0,
        "smin": 100, "smax": 196, "style": "Serve & Volley", "type": 1, "h": 173, "w": 66, "bh2": 0, "lefty": 1, "voice": "vo_w_wil",
        "photo": "37_Martina Navratilova.jpg", "base": "P_W_ROB_IT",
        "wear_fn": lambda r, g, b: (min(255, int(r * 0.78 + 42)), min(255, int(g * 0.82 + 44)), min(255, int(b * 1.05 + 62))),
        "acc_fn":  lambda r, g, b: (min(255, r + 40), min(255, g + 40), min(255, b + 45)),
        "hair_fn": lambda r, g, b: (min(255, int(r * 1.35 + 45)), min(255, int(g * 1.35 + 45)), min(255, int(b * 1.35 + 45))),
    },
]


def update_player_db():
    tpl_txt = os.path.join(REPO_ROOT, "extracted", "Config", "Fraw", "fwDataDB", "fwDataDB_Player.txt")
    bin_path = os.path.join(REPO_ROOT, "game", "archive", "Config", "Fraw", "fwDataDB", "fwDataDB_Player.bin")
    tmp_txt = os.path.join(os.path.dirname(REAL_PHOTOS_DIR), "fwDataDB_Player_expanded.txt")

    lines = decompile_fwdatadb(bin_path, template_path=tpl_txt)
    by_slot_key = {s["id"]: s for s in NEW_STARS}

    # First pass: locate player column order (`row 0..37`)
    slots_orig = [l.split(",")[4] for l in lines[:38]]
    assert len(slots_orig) == 38

    new_lines = []
    for row_idx, line in enumerate(lines):
        parts = line.split(",", 4)
        typ, k1, k2, k3, val = parts
        if row_idx < 646:  # First 17 Player field blocks (each 38 rows)
            slot = row_idx % 38
            if slot in by_slot_key:
                st = by_slot_key[slot]
                if k1 == "Player": val = st["code"]
                elif k1 == "ShortName": val = st["short"]
                elif k1 == "Author": val = st["author"]
                elif k1 == "Man": val = str(st["man"])
                elif k1 == "ServeMin": val = str(st["smin"])
                elif k1 == "ServeMax": val = str(st["smax"])
                elif k1 == "PlayStyle": val = st["style"]
                elif k1 == "Type": val = str(st["type"])
                elif k1 == "Height": val = str(st["h"])
                elif k1 == "Weight": val = str(st["w"])
                elif k1 == "BackHandD": val = str(st["bh2"])
                elif k1 == "Lefty": val = str(st["lefty"])
                elif k1 == "WtDblsPt": val = "3500"
                elif k1 == "WtDblsPtDisp": val = "2"
                elif k1 == "mVoiceSE": val = st["voice"]
        new_lines.append(f"{typ},{k1},{k2},{k3},{val}")

    with open(tmp_txt, "wb") as f:
        f.write(("\n".join(new_lines) + "\n").encode("utf-8"))
    compile_fwdatadb(tmp_txt, bin_path)
    print(f"Updated {bin_path} with 12 Legends & Next-Gen players (IDs 26..37)")


def build_real_portraits():
    out_dir = os.path.join(REPO_ROOT, "game", "archive", "HIGH", "Frontend", "VR", "photo_L")
    os.makedirs(out_dir, exist_ok=True)
    for st in NEW_STARS:
        src = os.path.join(REAL_PHOTOS_DIR, st["photo"])
        im = Image.open(src).convert("RGBA")
        w, h = im.size
        s = min(w, h)
        # Upper-center crop centered on face
        sq = im.crop(((w - s) // 2, 0, (w - s) // 2 + s, s)).resize((256, 256), Image.Resampling.LANCZOS)
        # Apply soft elliptical edge fade so real photos blend cleanly into the silver VT4 panel
        px = bytearray(sq.tobytes())
        for y in range(256):
            dy = (y - 124.0) / 120.0
            for x in range(256):
                dx = (x - 127.5) / 116.0
                r = math.sqrt(dx * dx + dy * dy)
                if r >= 0.98:
                    alpha = 0
                elif r > 0.78:
                    t = (0.98 - r) / 0.20
                    alpha = int(255 * (t * t * (3.0 - 2.0 * t)))
                else:
                    alpha = 255
                px[(y * 256 + x) * 4 + 3] = alpha
        vignetted = Image.frombytes("RGBA", (256, 256), bytes(px))
        dds = encode_dds(vignetted, b"RGBA")
        out_path = os.path.join(out_dir, f"{st['id']}.dds")
        with open(out_path, "wb") as f:
            f.write(dds)
        print(f"Wrote {out_path} ({len(dds)} bytes)")


def build_player_models():
    entries = load_directory()
    cache = {}
    out_dir = os.path.join(REPO_ROOT, "game", "archive", "HIGH", "Player", "Model")
    os.makedirs(out_dir, exist_ok=True)
    raw_cache = {}

    with open(BIN0, "rb") as f0, open(BIN1, "rb") as f1:
        for st in NEW_STARS:
            base = st["base"]
            gender = "M" if st["man"] else "W"
            out_sdo_name = f"P_{gender}_{st['code']}_{st['author']}.sdo"
            out_base_prefix = f"P_{gender}_{st['code']}"
            base_short = base[:7]  # e.g. P_M_NAD

            # Load & cache decompressed base SDO
            if base not in raw_cache:
                e_sdo = next(x for x in entries if x["name"].lower() == f"high/player/model/{base.lower()}.sdo")
                raw_cache[base] = lzss_decompress(read_entry(entries, e_sdo, f0, f1, cache))
            raw = bytearray(raw_cache[base])

            # Customize wear, pants, accessory, hair textures inside SDO
            pos = 0
            tweaks = 0
            while True:
                pos = raw.find(b"DDS ", pos)
                if pos < 0:
                    break
                ctx = bytes(raw[max(0, pos - 48) : pos])
                sz = struct.unpack(">I", raw[pos - 4 : pos])[0]
                fn = None
                if b"_B_wear" in ctx and st["wear_fn"]:
                    fn = st["wear_fn"]
                elif b"_B_pants" in ctx and st["wear_fn"]:
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
            sdo_path = os.path.join(out_dir, out_sdo_name)
            with open(sdo_path, "wb") as f:
                f.write(comp)

            # Copy matching _culling.zml and _deformable.zml
            for suffix in ["_culling.zml", "_deformable.zml"]:
                ez = next(x for x in entries if x["name"].lower() == f"high/player/model/{base_short.lower()}{suffix}")
                zdata = read_entry(entries, ez, f0, f1, cache)
                with open(os.path.join(out_dir, f"{out_base_prefix}{suffix}"), "wb") as f:
                    f.write(zdata)

            print(f"[{st['id']}] Built {out_sdo_name} (from {base}, {tweaks} tex recolored, {len(comp)} bytes)")


def main():
    update_player_db()
    build_real_portraits()
    build_player_models()


if __name__ == "__main__":
    main()
