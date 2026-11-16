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

PORTRAITS_SRC_DIR = os.path.join(REPO_ROOT, "assets", "portraits_src")
PHOTOCRAFT_CLI = r"C:\Program Files\ArtCraft\PhotoCraft\photocraft-cli.exe"

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
    import tempfile
    tmp_txt = os.path.join(tempfile.gettempdir(), "fwDataDB_Player_expanded.txt")

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


def _portrait_pre_crop(src_path, box, round_dims=True, pad_top=0):
    im = Image.open(src_path).convert("RGB")
    w, h = im.size
    cr = im.crop((int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h)))
    cw, ch = cr.size
    sc = 512.0 / max(cw, ch)
    if round_dims:
        nw, nh = int(round(cw * sc)), int(round(ch * sc))
    else:
        nw, nh = int(cw * sc), int(ch * sc)
    rs = cr.resize((nw, nh), Image.Resampling.LANCZOS)
    sq = Image.new("RGB", (512, 512 + pad_top), rs.getpixel((256 if pad_top else 0, 2 if pad_top else 0)))
    sq.paste(rs, ((512 - nw) // 2, 512 - nh + pad_top))
    return sq


def _run_photocraft_mcp_session(cli_path, workdir, jobs):
    import json
    import subprocess

    root = workdir.replace("\\", "/")
    proc = subprocess.Popen(
        [cli_path, "mcp", "--automation-read-root", root, "--automation-write-root", root],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    req_id = 0

    def send_only(obj):
        proc.stdin.write(json.dumps(obj) + "\n")
        proc.stdin.flush()

    def rpc(method, params=None):
        nonlocal req_id
        req_id += 1
        req = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params is not None:
            req["params"] = params
        send_only(req)
        while True:
            line = proc.stdout.readline()
            if not line:
                raise RuntimeError(f"PhotoCraft MCP EOF: {proc.stderr.read()}")
            resp = json.loads(line)
            if resp.get("id") == req_id:
                if "error" in resp:
                    raise RuntimeError(f"PhotoCraft MCP error: {resp}")
                if resp.get("result", {}).get("isError"):
                    raise RuntimeError(f"PhotoCraft MCP tool error: {resp}")
                return resp["result"]

    results = {}
    try:
        rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "vt4-roster", "version": "1.0"}})
        send_only({"jsonrpc": "2.0", "method": "notifications/initialized"})

        for pid, in_path, out_path, steps in jobs:
            rpc("tools/call", {"name": "doc_open", "arguments": {"path": in_path.replace("\\", "/")}})
            res = rpc("tools/call", {"name": "command_batch", "arguments": {"steps": steps}})
            parsed = json.loads(res["content"][0]["text"])
            if parsed.get("failed", 0) > 0:
                raise RuntimeError(f"PhotoCraft MCP batch failed on ID {pid}: {parsed}")
            rpc("tools/call", {"name": "doc_save", "arguments": {"path": out_path.replace("\\", "/")}})
            rpc("tools/call", {"name": "doc_close"})
            results[pid] = Image.open(out_path).convert("RGBA")
    finally:
        proc.stdin.close()
        proc.wait(timeout=10)
    return results


def _erase_poly(im, pts, blur=0.8):
    from PIL import ImageChops, ImageDraw, ImageFilter

    r, g, b, a = im.split()
    m = Image.new("L", im.size, 255)
    ImageDraw.Draw(m).polygon([tuple(p) for p in pts], fill=0)
    if blur > 0:
        m = m.filter(ImageFilter.GaussianBlur(blur))
    a = ImageChops.multiply(a, m)
    return Image.merge("RGBA", (r, g, b, a))


def _erase_rect(im, x0, y0, x1, y1, blur=0.5):
    return _erase_poly(im, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], blur=blur)


def _erase_yellow_green_grass(im, x0, y0, x1, y1):
    from PIL import ImageChops, ImageFilter

    px = im.load()
    m = Image.new("L", im.size, 255)
    mpx = m.load()
    for y in range(max(0, y0), min(im.height, y1)):
        for x in range(max(0, x0), min(im.width, x1)):
            r, g, b, a = px[x, y]
            if a > 0 and g >= r - 6 and (g - b) > 22 and not (r > 185 and b > 155):
                mpx[x, y] = 0
    m = m.filter(ImageFilter.GaussianBlur(0.8))
    r, g, b, a = im.split()
    a = ImageChops.multiply(a, m)
    return Image.merge("RGBA", (r, g, b, a))


def _frame_vt4_portrait(im, box):
    cr = im.crop(box).convert("RGBa")
    rs = cr.resize((256, 256), Image.Resampling.LANCZOS).convert("RGBA")
    r, g, b, a = rs.split()
    a = a.point(lambda v: 0 if v <= 6 else v)
    return Image.merge("RGBA", (r, g, b, a))


def build_real_portraits():
    import json
    import shutil
    import tempfile
    from PIL import ImageChops, ImageEnhance, ImageFilter

    cli = os.environ.get("PHOTOCRAFT_CLI") or shutil.which("photocraft-cli") or PHOTOCRAFT_CLI
    if not os.path.isfile(cli):
        raise FileNotFoundError(f"PhotoCraft CLI not found at {cli}; set PHOTOCRAFT_CLI")

    manifest_path = os.path.join(PORTRAITS_SRC_DIR, "manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        src_by_id = {int(item["id"]): os.path.join(PORTRAITS_SRC_DIR, item["orig_file"]) for item in json.load(f)}

    out_dir = os.path.join(REPO_ROOT, "game", "archive", "HIGH", "Frontend", "VR", "photo_L")
    os.makedirs(out_dir, exist_ok=True)

    # Per-ID pre-crop boxes (from repo assets/portraits_src/) matching VT4 bust framing
    pre_specs = {
        26: ((0.22, 0.30, 0.72, 0.96), True),
        27: ((0.02, 0.00, 0.98, 0.82), True),
        28: ((0.22, 0.14, 0.82, 0.56), True),
        29: ((0.14, 0.03, 0.72, 0.44), True),
        30: ((0.00, 0.04, 1.00, 0.82), True),
        31: ((0.36, 0.21, 0.65, 0.62), True),
        32: ((0.10, 0.04, 0.86, 0.56), False),
        33: ((0.32, 0.11, 0.84, 0.45), False),
        34: ((0.02, 0.00, 0.98, 0.78), True),
        35: ((0.02, 0.01, 0.98, 0.69), True),
        36: ((0.05, 0.12, 0.92, 0.66), True),
        37: ((0.04, 0.06, 0.92, 0.72), True),
    }

    pc_steps = {
        26: [
            {"id": "layer.removeBackground", "params": {"refine": True}},
            {"id": "select.rect", "params": {"x": 0, "y": 115, "width": 106, "height": 397}},
            {"id": "edit.fill", "params": {"contents": "black", "target": "mask"}},
            {"id": "select.deselect"},
            {"id": "layer.layerMask.apply"},
            {"id": "layer.matting.colorDecontaminate", "params": {"amount": 80, "radius": 3}},
            {"id": "layer.matting.defringe", "params": {"width": 1}},
            {"id": "image.adjustments.shadowsHighlights", "params": {"shadowAmount": 12, "highlightAmount": 10}},
        ],
        27: [
            {"id": "layer.removeBackground", "params": {"refine": True}},
            {"id": "paint.stroke", "params": {"target": "mask", "color": "#ffffff", "size": 9, "hardness": 0.9, "points": [[48, 0], [54, 42], [68, 138]]}},
            {"id": "paint.stroke", "params": {"target": "mask", "color": "#ffffff", "size": 8, "hardness": 0.9, "points": [[54, 42], [75, 62], [104, 65], [136, 48], [172, 2]]}},
            {"id": "paint.stroke", "params": {"target": "mask", "color": "#ffffff", "size": 9, "hardness": 0.9, "points": [[136, 48], [105, 92], [76, 138]]}},
            {"id": "select.rect", "params": {"x": 0, "y": 374, "width": 182, "height": 138}},
            {"id": "edit.fill", "params": {"contents": "black", "target": "mask"}},
            {"id": "select.deselect"},
            {"id": "layer.layerMask.apply"},
            {"id": "layer.matting.colorDecontaminate", "params": {"amount": 80, "radius": 3}},
            {"id": "layer.matting.defringe", "params": {"width": 1}},
            {"id": "image.adjustments.shadowsHighlights", "params": {"shadowAmount": 12, "highlightAmount": 8}},
        ],
        28: [
            {"id": "filter.noise.reduceNoise", "params": {"strength": 4, "preserveDetails": 75, "reduceColorNoise": 50, "sharpenDetails": 20, "removeJpegArtifact": True}},
            {"id": "layer.removeBackground", "params": {"refine": True}},
            {"id": "select.rect", "params": {"x": 0, "y": 0, "width": 122, "height": 512}},
            {"id": "edit.fill", "params": {"contents": "black", "target": "mask"}},
            {"id": "select.deselect"},
            {"id": "layer.layerMask.apply"},
            {"id": "layer.matting.colorDecontaminate", "params": {"amount": 80, "radius": 3}},
            {"id": "layer.matting.defringe", "params": {"width": 1}},
            {"id": "image.adjustments.shadowsHighlights", "params": {"shadowAmount": 8, "highlightAmount": 32, "color": 10}},
            {"id": "filter.sharpen.smartSharpen", "params": {"amount": 75, "radius": 1.0, "reduceNoise": 25}},
        ],
        29: [
            {"id": "layer.removeBackground", "params": {"refine": True}},
            {"id": "layer.layerMask.apply"},
            {"id": "layer.matting.colorDecontaminate", "params": {"amount": 80, "radius": 3}},
            {"id": "layer.matting.defringe", "params": {"width": 1}},
            {"id": "image.adjustments.shadowsHighlights", "params": {"shadowAmount": 10, "highlightAmount": 28, "color": 10}},
        ],
        30: [
            {"id": "filter.noise.reduceNoise", "params": {"strength": 4, "preserveDetails": 75, "reduceColorNoise": 0, "sharpenDetails": 20, "removeJpegArtifact": True}},
            {"id": "layer.removeBackground", "params": {"refine": True}},
            {"id": "select.rect", "params": {"x": 486, "y": 0, "width": 26, "height": 512}},
            {"id": "select.rect", "params": {"x": 445, "y": 390, "width": 67, "height": 122, "mode": "add"}},
            {"id": "edit.fill", "params": {"contents": "black", "target": "mask"}},
            {"id": "select.deselect"},
            {"id": "layer.layerMask.apply"},
            {"id": "layer.matting.defringe", "params": {"width": 1}},
            {"id": "image.adjustments.brightnessContrast", "params": {"brightness": 4, "contrast": 14}},
            {"id": "filter.sharpen.smartSharpen", "params": {"amount": 70, "radius": 1.0, "reduceNoise": 30}},
        ],
        31: [
            {"id": "filter.noise.reduceNoise", "params": {"strength": 4, "preserveDetails": 75, "reduceColorNoise": 0, "sharpenDetails": 20, "removeJpegArtifact": True}},
            {"id": "image.autoContrast"},
            {"id": "image.adjustments.shadowsHighlights", "params": {"shadowAmount": 18, "highlightAmount": 12}},
            {"id": "layer.layerMask.hideAll"},
            {"id": "paint.stroke", "params": {"target": "mask", "color": "#ffffff", "size": 3, "hardness": 0.85, "fill": True, "points": [
                [254, 128], [280, 114], [316, 120], [332, 140], [326, 174], [320, 192],
                [350, 210], [390, 242], [428, 266], [462, 266], [486, 212], [512, 210],
                [512, 240], [488, 258], [468, 282], [422, 288], [375, 260], [342, 272],
                [332, 345], [332, 418], [314, 444], [344, 480], [366, 512], [202, 512],
                [218, 476], [192, 456], [194, 428], [206, 360], [206, 276], [174, 284],
                [125, 312], [64, 344], [38, 340], [46, 322], [112, 294], [172, 254],
                [214, 198], [264, 194], [258, 184], [250, 158], [252, 142]
            ]}},
            {"id": "paint.stroke", "params": {"target": "mask", "color": "#ffffff", "size": 9, "hardness": 0.9, "points": [
                [286, 42], [322, 40], [365, 62], [392, 95], [392, 124],
                [358, 132], [312, 110], [282, 72], [286, 42]
            ]}},
            {"id": "paint.stroke", "params": {"target": "mask", "color": "#ffffff", "size": 11, "hardness": 0.9, "points": [[376, 126], [426, 165], [476, 206]]}},
            {"id": "layer.layerMask.apply"},
            {"id": "filter.sharpen.smartSharpen", "params": {"amount": 75, "radius": 1.0, "reduceNoise": 25}},
        ],
        32: [
            {"id": "layer.removeBackground", "params": {"refine": True}},
            {"id": "select.rect", "params": {"x": 388, "y": 182, "width": 124, "height": 106}},
            {"id": "edit.fill", "params": {"contents": "black", "target": "mask"}},
            {"id": "select.deselect"},
            {"id": "paint.stroke", "params": {"target": "mask", "color": "#ffffff", "size": 20, "hardness": 0.9, "points": [[215, 290], [275, 290], [250, 355], [275, 385], [210, 385], [235, 340]]}},
            {"id": "layer.layerMask.apply"},
            {"id": "layer.matting.colorDecontaminate", "params": {"amount": 75, "radius": 3}},
            {"id": "layer.matting.defringe", "params": {"width": 1}},
            {"id": "image.adjustments.shadowsHighlights", "params": {"shadowAmount": 12, "highlightAmount": 18}},
            {"id": "filter.sharpen.smartSharpen", "params": {"amount": 75, "radius": 1.0, "reduceNoise": 25}},
        ],
        33: [
            {"id": "layer.removeBackground", "params": {"refine": True}},
            {"id": "layer.layerMask.apply"},
            {"id": "layer.matting.colorDecontaminate", "params": {"amount": 80, "radius": 3}},
            {"id": "layer.matting.defringe", "params": {"width": 1}},
            {"id": "image.adjustments.shadowsHighlights", "params": {"shadowAmount": 42, "shadowTone": 45, "highlightAmount": 12, "color": 15}},
        ],
        34: [
            {"id": "layer.removeBackground", "params": {"refine": True}},
            {"id": "layer.layerMask.apply"},
            {"id": "layer.matting.colorDecontaminate", "params": {"amount": 80, "radius": 3}},
            {"id": "layer.matting.defringe", "params": {"width": 1}},
            {"id": "image.adjustments.shadowsHighlights", "params": {"shadowAmount": 12, "highlightAmount": 12}},
        ],
        35: [
            {"id": "layer.removeBackground", "params": {"refine": True}},
            {"id": "paint.stroke", "params": {"target": "mask", "color": "#ffffff", "size": 16, "hardness": 0.9, "points": [[138, 86], [185, 78], [234, 86]]}},
            {"id": "paint.stroke", "params": {"target": "mask", "color": "#ffffff", "size": 10, "hardness": 0.9, "points": [[56, 305], [106, 282], [160, 302], [194, 360], [176, 425], [116, 464], [52, 444], [12, 385], [16, 336], [56, 305]]}},
            {"id": "select.rect", "params": {"x": 0, "y": 465, "width": 95, "height": 47}},
            {"id": "edit.fill", "params": {"contents": "black", "target": "mask"}},
            {"id": "select.deselect"},
            {"id": "layer.layerMask.apply"},
            {"id": "layer.matting.colorDecontaminate", "params": {"amount": 80, "radius": 3}},
            {"id": "layer.matting.defringe", "params": {"width": 1}},
            {"id": "image.adjustments.shadowsHighlights", "params": {"shadowAmount": 12, "highlightAmount": 12}},
        ],
        36: [
            {"id": "filter.noise.reduceNoise", "params": {"strength": 4, "preserveDetails": 75, "reduceColorNoise": 50, "sharpenDetails": 20, "removeJpegArtifact": True}},
            {"id": "select.colorRange", "params": {"points": [[45, 50], [390, 65], [450, 200], [50, 420], [95, 304]], "fuzziness": 72, "invert": True}},
            {"id": "select.rect", "params": {"x": 0, "y": 0, "width": 205, "height": 245, "mode": "subtract"}},
            {"id": "select.rect", "params": {"x": 0, "y": 0, "width": 512, "height": 38, "mode": "subtract"}},
            {"id": "select.rect", "params": {"x": 370, "y": 330, "width": 142, "height": 182, "mode": "subtract"}},
            {"id": "layer.layerMask.revealSelection"},
            {"id": "paint.stroke", "params": {"target": "mask", "color": "#ffffff", "size": 16, "hardness": 0.9, "fill": True, "points": [[220, 72], [274, 74], [294, 175], [325, 220], [344, 390], [340, 512], [198, 512], [220, 360], [228, 185]]}},
            {"id": "paint.stroke", "params": {"target": "mask", "color": "#ffffff", "size": 13, "hardness": 0.9, "points": [[8, 95], [22, 165], [32, 245], [50, 272], [105, 294], [155, 292], [228, 282]]}},
            {"id": "paint.stroke", "params": {"target": "mask", "color": "#ffffff", "size": 12, "hardness": 0.9, "points": [[180, 274], [212, 272], [244, 276]]}},
            {"id": "layer.layerMask.apply"},
            {"id": "layer.matting.colorDecontaminate", "params": {"amount": 75, "radius": 3}},
            {"id": "layer.matting.defringe", "params": {"width": 1}},
            {"id": "image.adjustments.shadowsHighlights", "params": {"shadowAmount": 16, "highlightAmount": 22, "color": 12}},
            {"id": "filter.sharpen.smartSharpen", "params": {"amount": 80, "radius": 1.0, "reduceNoise": 25}},
        ],
        37: [
            {"id": "filter.noise.reduceNoise", "params": {"strength": 4, "preserveDetails": 75, "reduceColorNoise": 0, "sharpenDetails": 20, "removeJpegArtifact": True}},
            {"id": "image.autoContrast"},
            {"id": "image.adjustments.shadowsHighlights", "params": {"shadowAmount": 14, "highlightAmount": 12}},
            {"id": "layer.layerMask.hideAll"},
            {"id": "paint.stroke", "params": {"target": "mask", "color": "#ffffff", "size": 3, "hardness": 0.85, "fill": True, "points": [
                [292, 188], [308, 152], [338, 130], [378, 124], [406, 140], [424, 172],
                [432, 214], [424, 248], [408, 266], [404, 286], [436, 322],
                [450, 372], [454, 426], [432, 456], [448, 512], [42, 512],
                [66, 474], [108, 434], [140, 386], [190, 330], [242, 290],
                [276, 264], [296, 236], [288, 206]
            ]}},
            {"id": "paint.stroke", "params": {"target": "mask", "color": "#ffffff", "size": 11, "hardness": 0.9, "points": [[165, 0], [225, 130], [290, 282], [320, 345]]}},
            {"id": "layer.layerMask.apply"},
            {"id": "filter.sharpen.smartSharpen", "params": {"amount": 75, "radius": 1.0, "reduceNoise": 25}},
        ],
    }

    crop_vt4 = {
        26: (80,   0, 384, 304),
        27: (16,   0, 488, 472),
        28: (106, 40, 406, 340),
        29: (14,   8, 422, 416),
        30: (40,  16, 512, 488),
        31: (126, 28, 496, 398),
        32: (104, 92, 412, 400),
        33: (24,  10, 492, 478),
        34: (18,  10, 492, 484),
        35: (32,  40, 456, 464),
        36: (12,  34, 424, 446),
        37: (116, 62, 492, 438),
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        jobs = []
        for st in NEW_STARS:
            pid = int(st["id"])
            box, round_dims = pre_specs[pid]
            pre_img = _portrait_pre_crop(src_by_id[pid], box, round_dims=round_dims)
            in_p = os.path.join(tmpdir, f"in_{pid}.png")
            out_p = os.path.join(tmpdir, f"pc_{pid}.png")
            pre_img.save(in_p)
            jobs.append((pid, in_p, out_p, pc_steps[pid]))

        processed = _run_photocraft_mcp_session(cli, tmpdir, jobs)

        for st in NEW_STARS:
            pid = int(st["id"])
            im = processed[pid]

            if pid == 27:
                im = _erase_poly(im, [(172, 326), (204, 326), (222, 405), (242, 480), (242, 512), (172, 512)], blur=0.8)
                im = _erase_poly(im, [(68, 0), (150, 0), (128, 42), (98, 54), (72, 46)], blur=0.6)
                im = _erase_poly(im, [(75, 70), (118, 62), (82, 112)], blur=0.6)
                im = _erase_rect(im, 0, 352, 184, 512, blur=0.5)
            elif pid == 34:
                im = _erase_rect(im, 202, 0, 236, 22, blur=0.6)
            elif pid == 35:
                px = im.load()
                for y in range(290, 512):
                    for x in range(0, 185):
                        r, g, b, a = px[x, y]
                        if a > 0 and r < 150 and not (r > g + 22 and r > b + 30):
                            if abs(r - g) < 30 and (abs(g - b) < 35 or g >= r):
                                px[x, y] = (r, g, b, 0)
                im = _erase_poly(im, [(394, 278), (409, 326), (428, 386), (450, 448), (464, 475), (512, 475), (512, 278)], blur=0.8)
                im = _erase_rect(im, 0, 428, 42, 512, blur=0.6)
            elif pid == 36:
                im = _erase_poly(im, [(20, 276), (105, 302), (165, 306), (196, 306), (196, 338), (85, 326), (20, 294)], blur=0.8)
                im = _erase_poly(im, [(190, 160), (206, 160), (205, 255), (188, 255)], blur=0.8)
                im = _erase_poly(im, [(286, 85), (314, 85), (314, 170), (294, 170)], blur=0.8)
                im = _erase_yellow_green_grass(im, 20, 260, 210, 340)

            framed = _frame_vt4_portrait(im, crop_vt4[pid])

            if pid == 32:
                # Targeted grass bokeh removal on framed 256x256 without touching skin, hair, ring, or white fabric
                px = framed.load()
                m = Image.new("L", (256, 256), 255)
                mpx = m.load()
                zones = [
                    (22, 98, 72, 208),
                    (22, 195, 58, 240),
                    (184, 88, 246, 154),
                    (184, 152, 248, 202),
                ]
                for x0, y0, x1, y1 in zones:
                    for y in range(y0, y1):
                        for x in range(x0, x1):
                            r, g, b, a = px[x, y]
                            if a == 0:
                                continue
                            if x > 216 and y < 128:
                                mpx[x, y] = 0
                            elif (g >= r - 8) and ((g - b) >= 12) and (r < 205):
                                mpx[x, y] = 0
                m_er = m.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.5))
                m2 = Image.new("L", (256, 256), 255)
                m2px, mpx = m2.load(), m_er.load()
                for x0, y0, x1, y1 in zones:
                    for y in range(y0, y1):
                        for x in range(x0, x1):
                            m2px[x, y] = min(m2px[x, y], mpx[x, y])
                r, g, b, a = framed.split()
                a = ImageChops.multiply(a, m2).point(lambda v: 0 if v <= 6 else v)
                framed = Image.merge("RGBA", (r, g, b, a))

            dds = encode_dds(framed, b"RGBA")
            out_path = os.path.join(out_dir, f"{pid}.dds")
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
