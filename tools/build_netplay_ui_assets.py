#!/usr/bin/env python3
"""
Generate native VT4-styled pearl/silver/magenta sprites for the EN LINEA (P2P Netplay) screen
into game/archive/hud/netplay/ and save a visual composite at scratch/gs_audit/NETPLAY_UI_PREVIEW.png.
"""
import os
from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(REPO_ROOT, "game", "archive", "hud", "netplay")
AUDIT_DIR = os.path.join(REPO_ROOT, "scratch", "gs_audit")
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(AUDIT_DIR, exist_ok=True)

SS = 2


def lerp_c(c0, c1, t):
    return tuple(int(round(a + (b - a) * t)) for a, b in zip(c0, c1))


def make_netplay_bg():
    W, H = 1280 * SS, 720 * SS
    im = Image.new("RGBA", (W, H), (235, 237, 242, 255))
    dr = ImageDraw.Draw(im)

    # Vertical silver-pearl gradient across left and right panes matching OptionMode style
    for y in range(H):
        t = y / (H - 1)
        left_c = lerp_c((241, 243, 248, 255), (222, 225, 234, 255), t)
        right_c = lerp_c((231, 234, 242, 255), (212, 215, 226, 255), t)
        dr.line([(0, y), (650 * SS, y)], fill=left_c)
        dr.line([(650 * SS, y), (W, y)], fill=right_c)

    # Subtle diagonal court-line geometry in the right panel background
    for offset in (-180, -40, 100, 240):
        x0 = (680 + offset) * SS
        dr.line([(x0, 0), (x0 + 420 * SS, H)], fill=(255, 255, 255, 58), width=4 * SS)
    dr.ellipse([780 * SS, 140 * SS, 1180 * SS, 540 * SS], outline=(132, 22, 222, 24), width=8 * SS)

    # Top sleek header band
    dr.rectangle([0, 0, W, 62 * SS], fill=(246, 248, 252, 245))
    dr.rectangle([0, 62 * SS, W, 66 * SS], fill=(132, 22, 222, 255))

    # Crisp VT4 purple vertical divider (exact OptionMode accent)
    dr.rectangle([650 * SS, 62 * SS, 658 * SS, 656 * SS], fill=(132, 22, 222, 255))

    # Bottom footer band matching OptionMode ("Elegir / Cambiar / Atras")
    dr.rectangle([0, 656 * SS, W, H], fill=(224, 226, 232, 255))
    dr.rectangle([0, 656 * SS, W, 659 * SS], fill=(156, 158, 166, 255))

    out = im.resize((1280, 720), Image.LANCZOS)
    out.save(os.path.join(OUT_DIR, "netplay_bg.png"))
    return out


def make_row_pill(selected: bool):
    W, H = 560 * SS, 54 * SS
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    r = 9 * SS

    if selected:
        # Vibrant VT4 purple/magenta pill
        mask = Image.new("L", (W, H), 0)
        ImageDraw.Draw(mask).rounded_rectangle([2 * SS, 2 * SS, W - 2 * SS, H - 2 * SS], radius=r, fill=255)
        grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        gdr = ImageDraw.Draw(grad)
        for x in range(W):
            t = x / (W - 1)
            c = lerp_c((158, 26, 236, 248), (104, 16, 196, 245), t)
            gdr.line([(x, 0), (x, H)], fill=c)
        im.paste(grad, (0, 0), mask)
        dr = ImageDraw.Draw(im)
        dr.rounded_rectangle([2 * SS, 2 * SS, W - 2 * SS, H - 2 * SS], radius=r, outline=(232, 185, 255, 255), width=2 * SS)
        dr.rounded_rectangle([8 * SS, 8 * SS, 14 * SS, H - 8 * SS], radius=3 * SS, fill=(255, 255, 255, 255))
        dr.line([(16 * SS, H // 2), (W - 14 * SS, H // 2)], fill=(255, 255, 255, 42), width=1 * SS)
    else:
        dr.rounded_rectangle([2 * SS, 2 * SS, W - 2 * SS, H - 2 * SS], radius=r, fill=(247, 248, 252, 242), outline=(162, 166, 178, 235), width=2 * SS)
        dr.rectangle([10 * SS, H // 2, W - 10 * SS, H - 5 * SS], fill=(82, 86, 98, 235))
        dr.rounded_rectangle([10 * SS, H // 2 - 2 * SS, W - 10 * SS, H - 5 * SS], radius=5 * SS, fill=(84, 88, 100, 235))
        # Redraw crisp upper label band cleanly over top half of lower value band
        dr.rectangle([8 * SS, 4 * SS, W - 8 * SS, H // 2], fill=(247, 248, 252, 255))
        dr.rectangle([12 * SS, 10 * SS, 17 * SS, H // 2 - 4 * SS], fill=(132, 22, 222, 210))

    out = im.resize((560, 54), Image.LANCZOS)
    out.save(os.path.join(OUT_DIR, "netplay_row_sel.png" if selected else "netplay_row_unsel.png"))
    return out


def make_action_btn(selected: bool):
    W, H = 560 * SS, 48 * SS
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    r = 10 * SS
    c0 = (26, 154, 88, 250) if selected else (228, 232, 240, 242)
    bd = (130, 255, 184, 255) if selected else (142, 146, 158, 240)
    dr.rounded_rectangle([2 * SS, 2 * SS, W - 2 * SS, H - 2 * SS], radius=r, fill=c0, outline=bd, width=2 * SS)
    if selected:
        dr.rounded_rectangle([6 * SS, 5 * SS, W - 6 * SS, H // 2], radius=r // 2, fill=(255, 255, 255, 36))
    out = im.resize((560, 48), Image.LANCZOS)
    out.save(os.path.join(OUT_DIR, "netplay_btn_sel.png" if selected else "netplay_btn_unsel.png"))
    return out


def make_info_card():
    W, H = 520 * SS, 390 * SS
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.rounded_rectangle([2 * SS, 2 * SS, W - 2 * SS, H - 2 * SS], radius=14 * SS, fill=(250, 251, 255, 242), outline=(165, 168, 184, 240), width=2 * SS)
    dr.rounded_rectangle([12 * SS, 12 * SS, W - 12 * SS, 58 * SS], radius=8 * SS, fill=(132, 22, 222, 240))
    dr.rounded_rectangle([14 * SS, 70 * SS, W - 14 * SS, 134 * SS], radius=8 * SS, fill=(232, 235, 244, 255), outline=(196, 200, 214, 255), width=1 * SS)
    dr.rounded_rectangle([14 * SS, 148 * SS, W - 14 * SS, 310 * SS], radius=8 * SS, fill=(242, 244, 250, 255), outline=(210, 214, 226, 255), width=1 * SS)
    out = im.resize((520, 390), Image.LANCZOS)
    out.save(os.path.join(OUT_DIR, "netplay_card.png"))
    return out


def main():
    bg = make_netplay_bg()
    ru = make_row_pill(False)
    rs = make_row_pill(True)
    bu = make_action_btn(False)
    bs = make_action_btn(True)
    card = make_info_card()

    # Render composite preview for quick visual verification
    prev = bg.copy()
    for i in range(5):
        y = 104 + i * 64
        prev.alpha_composite(rs if i == 1 else ru, (66, y))
    prev.alpha_composite(bs, (66, 444))
    prev.alpha_composite(bu, (66, 504))
    prev.alpha_composite(card, (704, 215))
    prev.save(os.path.join(AUDIT_DIR, "NETPLAY_UI_PREVIEW.png"))
    print("Generated 6 netplay UI sprites in", OUT_DIR)


if __name__ == "__main__":
    main()
