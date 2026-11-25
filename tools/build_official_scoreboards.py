#!/usr/bin/env python3
"""
Generate modular, 4x-supersampled Official TV Broadcast Scoreboard sprites for:
  Virtua Tennis 4: Legends & Next-Gen Edition

Outputs under game/archive/hud/scoreboards/:
  - panel_<theme>.png     (512x168 RGBA) : matte-glass broadcast base with header & 2 rows
  - emblem_<theme>.png    (64x64 RGBA)   : clean geometric tournament emblem
  - point_box_<theme>.png (96x60 RGBA)   : high-contrast active game-point cell
  - serve_dot_<theme>.png (28x28 RGBA)   : glowing optic-yellow service indicator
  - alert_bar_<theme>.png (512x44 RGBA)  : bottom telemetry & Break/Set/Match Point bar
  - flags_ioc.png         (384x160 RGBA) : 6x5 atlas (64x32 cells) for all 26 roster IOC codes + WLD

Also renders scratch/gs_audit/SCOREBOARDS_PREVIEW.png for instant visual QA.
"""
import math
import os
from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(REPO_ROOT, "game", "archive", "hud", "scoreboards")
PREVIEW_PATH = os.path.join(REPO_ROOT, "scratch", "gs_audit", "SCOREBOARDS_PREVIEW.png")


def _font(names, size):
    for p in names:
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


F_BOLD = lambda sz: _font([r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\arialbd.ttf"], sz)
F_REG = lambda sz: _font([r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf"], sz)

# Exact alphabetical index 0..25 matching bhud_lookup_flag_idx in broadcast_hud.h (+ 26 = WLD fallback)
IOC_CODES = [
    "ARG", "AUS", "AUT", "BEL", "BLR", "BRA",
    "CHI", "CRO", "CZE", "DEN", "ESP", "FRA",
    "GBR", "GER", "GRE", "ITA", "JPN", "KAZ",
    "NOR", "POL", "ROU", "RUS", "SRB", "SUI",
    "SWE", "USA", "WLD",
]

THEMES = {
    "ao": {
        "label": "AUSTRALIAN OPEN",
        "bg_top": (10, 26, 62, 232),
        "bg_bot": (6, 16, 40, 238),
        "hdr_top": (0, 134, 206, 246),
        "hdr_bot": (0, 98, 164, 246),
        "accent": (0, 168, 240, 255),
        "accent2": (240, 248, 255, 220),
        "pt_top": (250, 252, 255, 252),
        "pt_bot": (222, 234, 248, 252),
        "pt_ink": (10, 24, 56),
        "pt_border": (0, 168, 240, 255),
        "sample_p1": ("C. ALCARAZ", "ESP", ["6", "7"], "30", True),
        "sample_p2": ("J. SINNER", "ITA", ["4", "5"], "15", False),
    },
    "rg": {
        "label": "ROLAND-GARROS",
        "bg_top": (16, 42, 30, 234),
        "bg_bot": (10, 28, 20, 240),
        "hdr_top": (198, 84, 38, 246),
        "hdr_bot": (158, 60, 24, 246),
        "accent": (218, 96, 44, 255),
        "accent2": (246, 236, 222, 220),
        "pt_top": (252, 250, 246, 252),
        "pt_bot": (232, 226, 218, 252),
        "pt_ink": (18, 44, 32),
        "pt_border": (218, 96, 44, 255),
        "sample_p1": ("I. SWIATEK", "POL", ["6", "3"], "40", True),
        "sample_p2": ("A. SABALENKA", "BLR", ["4", "2"], "30", False),
    },
    "wim": {
        "label": "WIMBLEDON",
        "bg_top": (14, 58, 36, 236),
        "bg_bot": (9, 38, 23, 242),
        "hdr_top": (84, 34, 120, 248),
        "hdr_bot": (58, 20, 88, 248),
        "accent": (216, 180, 88, 255),
        "accent2": (132, 74, 174, 230),
        "pt_top": (94, 38, 134, 252),
        "pt_bot": (66, 24, 100, 252),
        "pt_ink": (255, 255, 255),
        "pt_border": (216, 180, 88, 255),
        "sample_p1": ("R. FEDERER", "SUI", ["7", "6", "4"], "AD", False),
        "sample_p2": ("N. DJOKOVIC", "SRB", ["6", "7", "4"], "40", True),
    },
    "uso": {
        "label": "US OPEN",
        "bg_top": (12, 30, 68, 234),
        "bg_bot": (7, 18, 44, 240),
        "hdr_top": (28, 92, 206, 246),
        "hdr_bot": (18, 62, 152, 246),
        "accent": (242, 210, 56, 255),
        "accent2": (88, 158, 252, 220),
        "pt_top": (248, 218, 68, 254),
        "pt_bot": (228, 188, 36, 254),
        "pt_ink": (12, 24, 52),
        "pt_border": (255, 255, 255, 235),
        "sample_p1": ("B. SHELTON", "USA", ["6", "5"], "15", True),
        "sample_p2": ("J. MCENROE", "USA", ["4", "4"], "0", False),
    },
    "mad": {
        "label": "MUTUA MADRID OPEN",
        "bg_top": (15, 28, 54, 234),
        "bg_bot": (9, 17, 36, 240),
        "hdr_top": (22, 146, 226, 246),
        "hdr_bot": (14, 104, 176, 246),
        "accent": (36, 178, 250, 255),
        "accent2": (220, 234, 248, 220),
        "pt_top": (32, 172, 248, 252),
        "pt_bot": (18, 130, 212, 252),
        "pt_ink": (255, 255, 255),
        "pt_border": (210, 235, 255, 230),
        "sample_p1": ("R. NADAL", "ESP", ["6", "2"], "30", True),
        "sample_p2": ("C. RUUD", "NOR", ["3", "1"], "0", False),
    },
    "tour": {
        "label": "ATP / WTA WORLD TOUR",
        "bg_top": (18, 24, 38, 232),
        "bg_bot": (11, 15, 25, 238),
        "hdr_top": (42, 122, 214, 244),
        "hdr_bot": (26, 86, 166, 244),
        "accent": (52, 158, 246, 255),
        "accent2": (214, 226, 244, 210),
        "pt_top": (248, 250, 254, 252),
        "pt_bot": (224, 232, 244, 252),
        "pt_ink": (16, 22, 34),
        "pt_border": (52, 158, 246, 245),
        "sample_p1": ("N. DJOKOVIC", "SRB", ["6", "4"], "40", True),
        "sample_p2": ("D. MEDVEDEV", "RUS", ["4", "3"], "15", False),
    },
}


def _vgrad_rgba(w: int, h: int, c_top: tuple, c_bot: tuple) -> Image.Image:
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    for y in range(h):
        t = y / max(1, h - 1)
        col = tuple(int(round(c_top[i] * (1.0 - t) + c_bot[i] * t)) for i in range(4))
        dr.line([(0, y), (w, y)], fill=col)
    return im


def _round_mask(w: int, h: int, radius: int) -> Image.Image:
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    return m


def make_panel(t: dict) -> Image.Image:
    # Render 2x -> downsample 512x168
    S = 2
    W, H = 512 * S, 168 * S
    card = _vgrad_rgba(W, H, t["bg_top"], t["bg_bot"])

    # Header strip y: 0..42*S
    hdr_h = 42 * S
    hdr = _vgrad_rgba(W, hdr_h, t["hdr_top"], t["hdr_bot"])
    card.paste(hdr, (0, 0))

    dr = ImageDraw.Draw(card)
    # Row separator & subtle row sheen
    dr.rectangle([0, hdr_h, W, hdr_h + 2 * S], fill=t["accent"])
    dr.rectangle([0, 44 * S, W, 104 * S], fill=(255, 255, 255, 10))
    dr.rectangle([12 * S, 104 * S, W - 10 * S, 105 * S], fill=(255, 255, 255, 42))
    # Left tournament accent stripe
    dr.rectangle([0, 0, 8 * S, H], fill=t["accent"])
    # Subtle outer border
    dr.rounded_rectangle([1, 1, W - 2, H - 2], radius=12 * S, outline=(255, 255, 255, 58), width=2)

    # Mask rounded corners cleanly
    r, g, b, a = card.split()
    mask = _round_mask(W, H, 12 * S)
    from PIL import ImageChops
    a = ImageChops.multiply(a, mask)
    out = Image.merge("RGBA", (r, g, b, a))
    return out.resize((512, 168), Image.Resampling.LANCZOS)


def make_point_box(t: dict) -> Image.Image:
    S = 4
    W, H = 96 * S, 60 * S
    box = _vgrad_rgba(W, H, t["pt_top"], t["pt_bot"])
    dr = ImageDraw.Draw(box)
    dr.rounded_rectangle([2, 2, W - 3, H - 3], radius=8 * S, outline=t["pt_border"], width=2 * S)
    r, g, b, a = box.split()
    from PIL import ImageChops
    a = ImageChops.multiply(a, _round_mask(W, H, 8 * S))
    return Image.merge("RGBA", (r, g, b, a)).resize((96, 60), Image.Resampling.LANCZOS)


def make_alert_bar(t: dict) -> Image.Image:
    S = 2
    W, H = 512 * S, 44 * S
    bar = _vgrad_rgba(W, H, (8, 12, 22, 224), (4, 8, 16, 236))
    dr = ImageDraw.Draw(bar)
    dr.rectangle([0, 0, 8 * S, H], fill=t["accent"])
    dr.rounded_rectangle([1, 1, W - 2, H - 2], radius=8 * S, outline=(255, 255, 255, 48), width=2)
    r, g, b, a = bar.split()
    from PIL import ImageChops
    a = ImageChops.multiply(a, _round_mask(W, H, 8 * S))
    return Image.merge("RGBA", (r, g, b, a)).resize((512, 44), Image.Resampling.LANCZOS)


def make_serve_dot() -> Image.Image:
    S = 4
    W = 28 * S
    im = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx = cy = W // 2
    # Subtle warm glow
    d.ellipse([cx - 46, cy - 46, cx + 46, cy + 46], fill=(238, 255, 80, 68))
    d.ellipse([cx - 34, cy - 34, cx + 34, cy + 34], fill=(224, 246, 56, 255), outline=(255, 255, 255, 240), width=4)
    d.arc([cx - 26, cy - 26, cx + 26, cy + 26], start=30, end=195, fill=(255, 255, 255, 235), width=4)
    return im.resize((28, 28), Image.Resampling.LANCZOS)


def make_emblem(key: str, t: dict) -> Image.Image:
    S = 4
    W = 64 * S  # 256x256
    im = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = W // 2

    if key == "ao":
        # Stylized modernist AO blue/white geometric ribbon + ball
        d.ellipse([18, 18, W - 18, W - 18], fill=(10, 32, 74, 255), outline=(255, 255, 255, 245), width=10)
        d.polygon([(58, 198), (118, 56), (144, 56), (94, 198)], fill=(0, 176, 246, 255))
        d.polygon([(118, 56), (168, 198), (138, 198), (104, 102)], fill=(255, 255, 255, 255))
        d.ellipse([156, 134, 206, 184], fill=(226, 248, 72, 255), outline=(255, 255, 255, 240), width=5)
    elif key == "rg":
        # Parisian clay terracotta seal + crossed rackets
        d.ellipse([14, 14, W - 14, W - 14], fill=(184, 72, 32, 255), outline=(248, 242, 232, 245), width=10)
        d.ellipse([36, 36, W - 36, W - 36], fill=(20, 56, 38, 255), outline=(248, 242, 232, 200), width=5)
        # Crossed rackets in cream white
        d.line([(68, 188), (168, 88)], fill=(248, 244, 236, 245), width=10)
        d.line([(188, 188), (88, 88)], fill=(248, 244, 236, 245), width=10)
        d.ellipse([146, 56, 204, 114], outline=(248, 244, 236, 255), width=8)
        d.ellipse([52, 56, 110, 114], outline=(248, 244, 236, 255), width=8)
        d.ellipse([114, 160, 142, 188], fill=(232, 246, 70, 255))
    elif key == "wim":
        # All England Club green/purple/gold heritage crest + crossed rackets
        d.ellipse([12, 12, W - 12, W - 12], fill=(82, 30, 118, 255), outline=(222, 186, 92, 255), width=10)
        d.ellipse([36, 36, W - 36, W - 36], fill=(14, 68, 38, 255), outline=(255, 255, 255, 225), width=5)
        d.line([(66, 190), (168, 88)], fill=(246, 248, 246, 245), width=10)
        d.line([(190, 190), (88, 88)], fill=(246, 248, 246, 245), width=10)
        d.ellipse([146, 54, 206, 114], outline=(255, 255, 255, 255), width=8)
        d.ellipse([50, 54, 110, 114], outline=(255, 255, 255, 255), width=8)
        d.ellipse([112, 156, 144, 188], fill=(226, 246, 68, 255), outline=(255, 255, 255, 220), width=3)
    elif key == "uso":
        # Electric royal blue shield + flaming US Open yellow ball
        d.rounded_rectangle([16, 16, W - 16, W - 16], radius=48, fill=(18, 62, 152, 255), outline=(242, 210, 56, 255), width=10)
        # Speed flame tails
        d.polygon([(36, 108), (132, 82), (118, 126)], fill=(255, 92, 46, 245))
        d.polygon([(28, 146), (136, 128), (112, 166)], fill=(246, 178, 42, 245))
        d.polygon([(46, 182), (144, 154), (118, 196)], fill=(242, 210, 56, 245))
        d.ellipse([116, 78, 208, 170], fill=(238, 250, 68, 255), outline=(255, 255, 255, 255), width=6)
        d.arc([124, 86, 200, 162], start=35, end=215, fill=(255, 255, 255, 240), width=5)
    elif key == "mad":
        # Madrid Blue Diamond crest
        d.polygon([(c, 16), (W - 16, c), (c, W - 16), (16, c)], fill=(18, 134, 214, 255), outline=(240, 248, 255, 250), width=10)
        d.ellipse([88, 88, 168, 168], fill=(228, 248, 72, 255), outline=(255, 255, 255, 255), width=6)
    else:
        # World Tour shield
        d.ellipse([18, 18, W - 18, W - 18], fill=(32, 102, 188, 255), outline=(235, 244, 255, 245), width=9)
        d.arc([44, 44, W - 44, W - 44], start=-30, end=150, fill=(226, 246, 68, 255), width=10)
        d.ellipse([94, 94, 162, 162], fill=(228, 248, 72, 255), outline=(255, 255, 255, 245), width=5)

    return im.resize((64, 64), Image.Resampling.LANCZOS)


def draw_flag(code: str) -> Image.Image:
    # Draw sharp 4x (256x128) -> downsample to 64x32
    W, H = 256, 128
    im = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    d = ImageDraw.Draw(im)

    if code == "ARG":
        d.rectangle([0, 0, W, H // 3], fill=(116, 172, 223, 255))
        d.rectangle([0, 2 * H // 3, W, H], fill=(116, 172, 223, 255))
        d.ellipse([W // 2 - 14, H // 2 - 14, W // 2 + 14, H // 2 + 14], fill=(246, 180, 14, 255))
    elif code == "AUS":
        d.rectangle([0, 0, W, H], fill=(0, 38, 128, 255))
        # Canton Union Jack simplified
        d.rectangle([0, 0, W // 2, H // 2], fill=(1, 33, 105, 255))
        d.line([(0, 0), (W // 2, H // 2)], fill=(255, 255, 255, 255), width=10)
        d.line([(W // 2, 0), (0, H // 2)], fill=(255, 255, 255, 255), width=10)
        d.rectangle([W // 4 - 8, 0, W // 4 + 8, H // 2], fill=(255, 255, 255, 255))
        d.rectangle([0, H // 4 - 8, W // 2, H // 4 + 8], fill=(255, 255, 255, 255))
        d.rectangle([W // 4 - 5, 0, W // 4 + 5, H // 2], fill=(200, 16, 46, 255))
        d.rectangle([0, H // 4 - 5, W // 2, H // 4 + 5], fill=(200, 16, 46, 255))
        for sx, sy, sr in [(64, 96, 10), (192, 32, 7), (174, 62, 6), (214, 58, 6), (192, 96, 8)]:
            d.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=(255, 255, 255, 255))
    elif code == "AUT":
        d.rectangle([0, 0, W, H // 3], fill=(224, 30, 44, 255))
        d.rectangle([0, 2 * H // 3, W, H], fill=(224, 30, 44, 255))
    elif code == "BEL":
        d.rectangle([0, 0, W // 3, H], fill=(18, 18, 22, 255))
        d.rectangle([W // 3, 0, 2 * W // 3, H], fill=(250, 224, 66, 255))
        d.rectangle([2 * W // 3, 0, W, H], fill=(224, 42, 52, 255))
    elif code == "BLR":
        d.rectangle([0, 0, W, int(H * 0.66)], fill=(210, 38, 48, 255))
        d.rectangle([0, int(H * 0.66), W, H], fill=(0, 134, 68, 255))
        d.rectangle([0, 0, 32, H], fill=(255, 255, 255, 255))
        d.rectangle([8, 12, 24, H - 12], fill=(210, 38, 48, 255))
    elif code == "BRA":
        d.rectangle([0, 0, W, H], fill=(0, 156, 59, 255))
        d.polygon([(W // 2, 16), (W - 28, H // 2), (W // 2, H - 16), (28, H // 2)], fill=(255, 223, 0, 255))
        d.ellipse([W // 2 - 30, H // 2 - 30, W // 2 + 30, H // 2 + 30], fill=(0, 39, 118, 255))
        d.line([(W // 2 - 28, H // 2 - 4), (W // 2 + 28, H // 2 + 10)], fill=(255, 255, 255, 255), width=6)
    elif code == "CHI":
        d.rectangle([0, H // 2, W, H], fill=(213, 43, 30, 255))
        d.rectangle([0, 0, H // 2 + 20, H // 2], fill=(0, 57, 166, 255))
        d.ellipse([26, 18, 58, 50], fill=(255, 255, 255, 255))
    elif code == "CRO":
        d.rectangle([0, 0, W, H // 3], fill=(228, 24, 34, 255))
        d.rectangle([0, 2 * H // 3, W, H], fill=(23, 23, 150, 255))
        d.rectangle([W // 2 - 22, 36, W // 2 + 22, 92], fill=(228, 24, 34, 255), outline=(255, 255, 255, 255), width=4)
    elif code == "CZE":
        d.rectangle([0, H // 2, W, H], fill=(215, 20, 26, 255))
        d.polygon([(0, 0), (W // 2, H // 2), (0, H)], fill=(17, 69, 126, 255))
    elif code == "DEN":
        d.rectangle([0, 0, W, H], fill=(200, 16, 46, 255))
        d.rectangle([72, 0, 96, H], fill=(255, 255, 255, 255))
        d.rectangle([0, H // 2 - 12, W, H // 2 + 12], fill=(255, 255, 255, 255))
    elif code == "ESP":
        d.rectangle([0, 0, W, H // 4], fill=(198, 11, 30, 255))
        d.rectangle([0, H // 4, W, 3 * H // 4], fill=(255, 196, 0, 255))
        d.rectangle([0, 3 * H // 4, W, H], fill=(198, 11, 30, 255))
        d.rectangle([58, 44, 88, 84], fill=(178, 18, 32, 255))
    elif code == "FRA":
        d.rectangle([0, 0, W // 3, H], fill=(0, 85, 164, 255))
        d.rectangle([2 * W // 3, 0, W, H], fill=(239, 65, 53, 255))
    elif code == "GBR":
        d.rectangle([0, 0, W, H], fill=(1, 33, 105, 255))
        d.line([(0, 0), (W, H)], fill=(255, 255, 255, 255), width=22)
        d.line([(W, 0), (0, H)], fill=(255, 255, 255, 255), width=22)
        d.line([(0, 0), (W, H)], fill=(200, 16, 46, 255), width=10)
        d.line([(W, 0), (0, H)], fill=(200, 16, 46, 255), width=10)
        d.rectangle([W // 2 - 20, 0, W // 2 + 20, H], fill=(255, 255, 255, 255))
        d.rectangle([0, H // 2 - 20, W, H // 2 + 20], fill=(255, 255, 255, 255))
        d.rectangle([W // 2 - 12, 0, W // 2 + 12, H], fill=(200, 16, 46, 255))
        d.rectangle([0, H // 2 - 12, W, H // 2 + 12], fill=(200, 16, 46, 255))
    elif code == "GER":
        d.rectangle([0, 0, W, H // 3], fill=(16, 16, 20, 255))
        d.rectangle([0, H // 3, W, 2 * H // 3], fill=(221, 0, 0, 255))
        d.rectangle([0, 2 * H // 3, W, H], fill=(255, 206, 0, 255))
    elif code == "GRE":
        sh = H // 9
        for k in range(9):
            col = (13, 94, 175, 255) if k % 2 == 0 else (255, 255, 255, 255)
            d.rectangle([0, k * sh, W, (k + 1) * sh + 2], fill=col)
        d.rectangle([0, 0, 5 * sh + 10, 5 * sh], fill=(13, 94, 175, 255))
        d.rectangle([(5 * sh + 10) // 2 - 8, 0, (5 * sh + 10) // 2 + 8, 5 * sh], fill=(255, 255, 255, 255))
        d.rectangle([0, 2 * sh, 5 * sh + 10, 3 * sh], fill=(255, 255, 255, 255))
    elif code == "ITA":
        d.rectangle([0, 0, W // 3, H], fill=(0, 146, 70, 255))
        d.rectangle([2 * W // 3, 0, W, H], fill=(206, 43, 55, 255))
    elif code == "JPN":
        d.ellipse([W // 2 - 36, H // 2 - 36, W // 2 + 36, H // 2 + 36], fill=(188, 0, 45, 255))
    elif code == "KAZ":
        d.rectangle([0, 0, W, H], fill=(0, 175, 202, 255))
        d.ellipse([W // 2 - 22, H // 2 - 26, W // 2 + 22, H // 2 + 18], fill=(254, 198, 12, 255))
        d.rectangle([14, 12, 32, H - 12], fill=(254, 198, 12, 255))
    elif code == "NOR":
        d.rectangle([0, 0, W, H], fill=(186, 12, 47, 255))
        d.rectangle([70, 0, 102, H], fill=(255, 255, 255, 255))
        d.rectangle([0, H // 2 - 16, W, H // 2 + 16], fill=(255, 255, 255, 255))
        d.rectangle([78, 0, 94, H], fill=(0, 32, 91, 255))
        d.rectangle([0, H // 2 - 8, W, H // 2 + 8], fill=(0, 32, 91, 255))
    elif code == "POL":
        d.rectangle([0, H // 2, W, H], fill=(220, 20, 60, 255))
    elif code == "ROU":
        d.rectangle([0, 0, W // 3, H], fill=(0, 43, 127, 255))
        d.rectangle([W // 3, 0, 2 * W // 3, H], fill=(252, 209, 22, 255))
        d.rectangle([2 * W // 3, 0, W, H], fill=(206, 17, 38, 255))
    elif code == "RUS":
        d.rectangle([0, H // 3, W, 2 * H // 3], fill=(0, 57, 166, 255))
        d.rectangle([0, 2 * H // 3, W, H], fill=(213, 43, 30, 255))
    elif code == "SRB":
        d.rectangle([0, 0, W, H // 3], fill=(198, 54, 60, 255))
        d.rectangle([0, H // 3, W, 2 * H // 3], fill=(12, 64, 118, 255))
        d.rectangle([62, 34, 98, 92], fill=(255, 255, 255, 240), outline=(218, 178, 62, 255), width=4)
    elif code == "SUI":
        d.rectangle([0, 0, W, H], fill=(218, 24, 34, 255))
        d.rectangle([W // 2 - 14, 24, W // 2 + 14, H - 24], fill=(255, 255, 255, 255))
        d.rectangle([W // 2 - 40, H // 2 - 14, W // 2 + 40, H // 2 + 14], fill=(255, 255, 255, 255))
    elif code == "SWE":
        d.rectangle([0, 0, W, H], fill=(0, 106, 167, 255))
        d.rectangle([72, 0, 98, H], fill=(254, 204, 2, 255))
        d.rectangle([0, H // 2 - 13, W, H // 2 + 13], fill=(254, 204, 2, 255))
    elif code == "USA":
        sh = H / 13.0
        for k in range(13):
            col = (178, 34, 52, 255) if k % 2 == 0 else (255, 255, 255, 255)
            d.rectangle([0, int(k * sh), W, int((k + 1) * sh) + 1], fill=col)
        d.rectangle([0, 0, int(W * 0.44), int(sh * 7)], fill=(60, 59, 110, 255))
        for ry in range(3):
            for rx in range(4):
                sx = 14 + rx * 26
                sy = 12 + ry * 20
                d.ellipse([sx - 3, sy - 3, sx + 3, sy + 3], fill=(255, 255, 255, 255))
    else:  # WLD
        d.rectangle([0, 0, W, H], fill=(24, 88, 178, 255))
        d.ellipse([W // 2 - 38, H // 2 - 38, W // 2 + 38, H // 2 + 38], outline=(255, 255, 255, 240), width=6)
        d.ellipse([W // 2 - 16, H // 2 - 38, W // 2 + 16, H // 2 + 38], outline=(255, 255, 255, 200), width=4)
        d.line([(W // 2 - 38, H // 2), (W // 2 + 38, H // 2)], fill=(255, 255, 255, 200), width=4)

    # Crisp thin border so white-striped flags (JPN/POL/RUS) separate cleanly on dark panels
    d.rectangle([0, 0, W - 1, H - 1], outline=(255, 255, 255, 110), width=4)
    return im.resize((64, 32), Image.Resampling.LANCZOS)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(PREVIEW_PATH), exist_ok=True)

    # 1. Shared IOC flags atlas (6 cols x 5 rows of 64x32 -> 384x160)
    atlas = Image.new("RGBA", (384, 160), (0, 0, 0, 0))
    flag_imgs = {}
    for idx, code in enumerate(IOC_CODES):
        col, row = idx % 6, idx // 6
        fg = draw_flag(code)
        flag_imgs[code] = fg
        atlas.paste(fg, (col * 64, row * 32))
    atlas.save(os.path.join(OUT_DIR, "flags_ioc.png"))

    serve_dot = make_serve_dot()
    sheet_cards = []
    for key, t in THEMES.items():
        panel = make_panel(t)
        emblem = make_emblem(key, t)
        pt_box = make_point_box(t)
        alert = make_alert_bar(t)

        panel.save(os.path.join(OUT_DIR, f"panel_{key}.png"))
        emblem.save(os.path.join(OUT_DIR, f"emblem_{key}.png"))
        pt_box.save(os.path.join(OUT_DIR, f"point_box_{key}.png"))
        serve_dot.save(os.path.join(OUT_DIR, f"serve_dot_{key}.png"))
        alert.save(os.path.join(OUT_DIR, f"alert_bar_{key}.png"))

        # Render realistic preview mock scorebug
        card = Image.new("RGBA", (540, 232), (32, 92, 168, 255))
        card.paste(panel, (14, 10), panel)
        card.paste(emblem.resize((32, 32), Image.Resampling.LANCZOS), (28, 15), emblem.resize((32, 32), Image.Resampling.LANCZOS))
        card.paste(alert, (14, 182), alert)
        dr = ImageDraw.Draw(card)
        dr.text((68, 19), t["label"], font=F_BOLD(18), fill=(255, 255, 255))
        dr.text((462, 20), "01:18", font=F_REG(16), fill=(230, 240, 255))

        for r_i, (pname, ioc, sets, pts, srv) in enumerate([t["sample_p1"], t["sample_p2"]]):
            ry = 56 + r_i * 62
            fl = flag_imgs[ioc].resize((30, 16), Image.Resampling.LANCZOS)
            card.paste(fl, (28, ry + 18), fl)
            dr.text((66, ry + 12), pname, font=F_BOLD(22), fill=(255, 255, 255))
            if srv:
                sd = serve_dot.resize((16, 16), Image.Resampling.LANCZOS)
                card.paste(sd, (316, ry + 18), sd)
            for s_i, sg in enumerate(sets):
                sx = 342 + s_i * 30
                col = (255, 255, 255) if s_i == len(sets) - 1 else (188, 200, 218)
                dr.text((sx, ry + 12), sg, font=F_BOLD(22), fill=col)
            pb = pt_box.resize((72, 48), Image.Resampling.LANCZOS)
            card.paste(pb, (444, ry + 2), pb)
            dr.text((464 if len(pts) == 2 else 474, ry + 12), pts, font=F_BOLD(22), fill=t["pt_ink"])

        dr.text((30, 194), "BREAK POINT  |  BOLA 204 km/h  |  MAX 216  |  RALLY 07", font=F_BOLD(15), fill=(242, 232, 164))
        sheet_cards.append(card)
        print(f"[OK] Generated scoreboard sprite pack: {key}")

    # Compose visual preview sheet (2 cols x 3 rows + flags strip)
    sheet = Image.new("RGB", (1100, 3 * 240 + 180), (18, 22, 30))
    for i, c in enumerate(sheet_cards):
        sheet.paste(c.convert("RGB"), (10 + (i % 2) * 545, 10 + (i // 2) * 240))
    sheet.paste(atlas.convert("RGB"), (10, 3 * 240 + 10))
    sheet.save(PREVIEW_PATH)
    print(f"Saved preview sheet -> {PREVIEW_PATH}")


if __name__ == "__main__":
    main()
