#!/usr/bin/env python3
"""
Fix Agassi '91 (29_91) real face + sleeve + racket string holes, and fix
portraits 43, 44, 45, 47, 49, 51 using the cleanest base cutouts on disk.
Packs photo_L, photo_eye, photo_S DDS and writes scratch/fixed_portraits_v3_audit.png.
"""
import os
import shutil
import tempfile
from collections import deque
from PIL import Image, ImageDraw, ImageFilter

from build_legends_roster import PHOTOCRAFT_CLI, _erase_poly, _erase_yellow_green_grass, _run_photocraft_mcp_session
from build_v2_portraits import (
    VR_DIR,
    build_eye_strip,
    build_photo_s,
    frame_portrait_256,
    remove_small_alpha_islands,
    write_bgra_dds,
    write_dxt5_dds,
)
from uv_face_projector import compute_face_affine

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRATCH_DIR = os.path.join(REPO_ROOT, "scratch")


def fill_enclosed_alpha_holes(im: Image.Image, search_box: tuple[int, int, int, int]) -> Image.Image:
    """Fill completely enclosed alpha==0 interior holes inside a cutout (like chest/shirt patterns)
    using blurred adjacent opaque cloth colors."""
    out = im.copy().convert("RGBA")
    w, h = out.size
    a_px = out.getchannel("A").load()

    # BFS from outer boundary over transparent pixels (a < 20)
    visited = bytearray(w * h)
    q = deque()
    for x in range(w):
        for y in (0, h - 1):
            if a_px[x, y] < 20:
                idx = y * w + x
                visited[idx] = 1
                q.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if a_px[x, y] < 20:
                idx = y * w + x
                if not visited[idx]:
                    visited[idx] = 1
                    q.append((x, y))
    while q:
        cx, cy = q.popleft()
        for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
            if 0 <= nx < w and 0 <= ny < h:
                idx = ny * w + nx
                if not visited[idx] and a_px[nx, ny] < 20:
                    visited[idx] = 1
                    q.append((nx, ny))

    # Any unvisited a < 20 inside search_box is a sealed interior hole!
    # Inpaint cleanly with multi-pass blurred RGB from neighboring opaque pixels
    rgb_fill = out.convert("RGB").filter(ImageFilter.GaussianBlur(12))
    rgb_px = rgb_fill.load()
    px = out.load()
    x0, y0, x1, y1 = search_box
    for y in range(max(0, y0), min(h, y1)):
        for x in range(max(0, x0), min(w, x1)):
            if a_px[x, y] < 200 and not visited[y * w + x]:
                r, g, b = rgb_px[x, y]
                px[x, y] = (r, g, b, 255)
    return out


def fix_agassi91_cutout() -> Image.Image:
    """Replace synthetic 29_91 face with real Agassi identity, restore clipped right sleeve,
    and remove gray studio backdrop pockets inside racket oval & throat."""
    orig = Image.open(os.path.join(REPO_ROOT, "assets", "portraits_batch_in", "29_91.jpg")).convert("RGB")
    base = Image.open(os.path.join(REPO_ROOT, "assets", "cutouts_v2", "29_91.png")).convert("RGBA")

    # 1. Restore full sleeve/arm cleanly using exact sleeve outer contour polygon on 29_91.jpg
    # (Sleeve shoulder starts around (255,445) down-left to (162,585) -> cuff (148,700) -> elbow (280,750))
    sleeve_mask = Image.new("L", base.size, 0)
    ImageDraw.Draw(sleeve_mask).polygon(
        [(290, 420), (225, 455), (178, 550), (156, 650), (165, 745), (275, 770), (315, 580)],
        fill=255,
    )
    sleeve_mask = sleeve_mask.filter(ImageFilter.GaussianBlur(1.5))
    sm_px = sleeve_mask.load()
    opx = orig.load()
    bpx = base.load()
    for y in range(415, 775):
        for x in range(150, 320):
            if bpx[x, y][3] < 220 and sm_px[x, y] > 30:
                r, g, b = opx[x, y]
                # Keep subtle feathering along outer contour, avoid external #CE..#D2 gray
                if sm_px[x, y] > 140 or not (abs(r - g) <= 8 and 195 <= b <= 212):
                    bpx[x, y] = (r, g, b, max(bpx[x, y][3], sm_px[x, y]))

    # 2. Align real Agassi landmarks from 29_AG2/ref_3.jpg -> 29_91 pose (896x1200)
    r3 = Image.open(os.path.join(REPO_ROOT, "assets", "face_refs", "29_AG2", "ref_3.jpg")).convert("RGB")
    r3_clean = Image.blend(r3, r3.filter(ImageFilter.GaussianBlur(1.1)), 0.45)

    src_pts = [(378, 594), (658, 560), (540, 882)]
    dst_pts = [(410, 248), (488, 248), (449, 326)]
    mat = compute_face_affine(src_pts, dst_pts)
    warped = r3_clean.transform(base.size, Image.Transform.AFFINE, mat, Image.Resampling.BICUBIC)

    box = (402, 244, 496, 336)
    pb = list(base.convert("RGB").crop(box).getdata())
    ps = list(warped.crop(box).getdata())
    mb = [sum(p[c] for p in pb) / len(pb) for c in range(3)]
    ms = [sum(p[c] for p in ps) / len(ps) for c in range(3)]
    sb = [max(8.0, (sum((p[c] - mb[c]) ** 2 for p in pb) / len(pb)) ** 0.5) for c in range(3)]
    ss = [max(8.0, (sum((p[c] - ms[c]) ** 2 for p in ps) / len(ps)) ** 0.5) for c in range(3)]

    chans = []
    for c in range(3):
        r_gain = 0.78 if c == 0 else 0.90
        chans.append(
            warped.getchannel(c).point(
                lambda v, c=c, g=r_gain: max(0, min(255, int(round((v - ms[c]) * (sb[c] / ss[c]) * g + mb[c]))))
            )
        )
    warped_corr = Image.merge("RGB", chans)

    mask = Image.new("L", base.size, 0)
    ImageDraw.Draw(mask).polygon(
        [(386, 226), (512, 226), (514, 298), (495, 362), (450, 392), (404, 362), (384, 298)],
        fill=255,
    )
    mask = mask.filter(ImageFilter.GaussianBlur(10))
    mpx = mask.load()
    for y in range(228):
        t = max(0.0, (y - 220) / 8.0)
        for x in range(base.width):
            mpx[x, y] = int(mpx[x, y] * t)

    rgb_comp = base.convert("RGB")
    rgb_comp.paste(warped_corr, (0, 0), mask)
    r_c, g_c, b_c = rgb_comp.split()
    out = Image.merge("RGBA", (r_c, g_c, b_c, base.getchannel("A")))

    # 3. Clean gray studio backdrop inside racket oval & V-throat (avoiding white/pink sleeve)
    px = out.load()
    for y in range(375, 598):
        for x in range(590, 825):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            luma = 0.299 * r + 0.587 * g + 0.114 * b
            in_sleeve_zone = (x < 712 and y > 445 and luma > 224) or (r - g > 20)
            in_throat_gap = (625 <= x <= 680 and 540 <= y <= 592)
            if in_throat_gap or not in_sleeve_zone:
                if abs(r - g) <= 12 and abs(g - b) <= 14 and luma >= 186:
                    px[x, y] = (r, g, b, 0)

    out_path = os.path.join(REPO_ROOT, "assets", "cutouts_v2", "29_91_fixed.png")
    out.save(out_path)
    return out


def fix_ferrer_hair_and_racket() -> Image.Image:
    """Restore Ferrer's brown hair & top black hair/visor from 49_ferrer_orig.jpg (exact 1:1 960x1440)."""
    orig = Image.open(os.path.join(REPO_ROOT, "assets", "portraits_page3_src", "49_ferrer_orig.jpg")).convert("RGB")
    cut = Image.open(os.path.join(REPO_ROOT, "assets", "cutouts_v2", "49.png")).convert("RGBA")
    opx = orig.load()
    cpx = cut.load()
    # Ferrer's brown hair lies around x=520..905, y=195..390 against blue US Open backdrop (b > r + 25)
    for y in range(195, 405):
        for x in range(505, 910):
            if cpx[x, y][3] < 200:
                r, g, b = opx[x, y]
                luma = 0.299 * r + 0.587 * g + 0.114 * b
                # Brown hair is warm (r >= b + 4) and dark/mid (luma < 145); wall is cold blue (b > r + 20)
                if r >= b + 2 and luma < 155 and not (r > 200 and g > 200 and b > 200):
                    cpx[x, y] = (r, g, b, 255)
    return cut


def main() -> None:
    cli = os.environ.get("PHOTOCRAFT_CLI") or shutil.which("photocraft-cli") or PHOTOCRAFT_CLI
    if not os.path.isfile(cli):
        raise FileNotFoundError(f"PhotoCraft CLI not found at {cli}")

    # Run PhotoCraft CLI on clean Ferrero wide upper-body crop
    tmp_dir = tempfile.mkdtemp(prefix="vt4_fix_p3_")
    try:
        orig47 = Image.open(os.path.join(REPO_ROOT, "assets", "portraits_page3_src", "47_ferrero_orig.jpg")).convert("RGB")
        w, h = orig47.size
        cr47 = orig47.crop((int(0.22 * w), int(0.01 * h), int(0.76 * w), int(0.48 * h)))
        cw, ch = cr47.size
        sc = 512.0 / max(cw, ch)
        rs47 = cr47.resize((int(cw * sc), int(ch * sc)), Image.Resampling.LANCZOS)
        sq47 = Image.new("RGB", (512, 512), rs47.getpixel((0, 0)))
        sq47.paste(rs47, ((512 - rs47.width) // 2, (512 - rs47.height) // 2))
        in_p = os.path.join(tmp_dir, "47_in.png")
        out_p = os.path.join(tmp_dir, "47_out.png")
        sq47.save(in_p)
        pc_res = _run_photocraft_mcp_session(cli, tmp_dir, [(47, in_p, out_p, [{"id": "layer.removeBackground", "params": {"refine": True}}])])
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    fixed_specs = []

    # 1) 29_91 Agassi '91
    ag91_cut = remove_small_alpha_islands(fix_agassi91_cutout(), 500)
    fixed_specs.append(("29_91", ag91_cut, (85, 45, 845, 920), 0.03, 60))

    # 2) 43 Kyrgios: start from intact 43_kyrgios.png + remove outer signboard slivers & blue strings
    im43 = Image.open(os.path.join(REPO_ROOT, "assets", "portraits_page3_src", "cutouts", "43_kyrgios.png")).convert("RGBA")
    px43 = im43.load()
    for y in range(22, 260):
        for x in range(80, 395):
            r, g, b, a = px43[x, y]
            if a == 0:
                continue
            # Erase bright signboard triangle behind right cheek/neck (x >= 342) or left of arm (x < 210, y < 245)
            if (x >= 342 and y < 195 and b >= r - 2) or (x < 208 and y < 245 and b > r + 14):
                px43[x, y] = (r, g, b, 0)
            # Clean blue sky/wall inside racket strings (x=120..265, y=22..205)
            elif 120 <= x <= 265 and y < 205 and b > r + 24 and b > 105:
                px43[x, y] = (r, g, b, 0)
    im43 = remove_small_alpha_islands(im43, 300)
    fixed_specs.append(("43", im43, (0, 8, 400, 410), 0.03, 66))

    # 3) 44 Hewitt: intact 44_hewitt.png face & white cap + erase ONLY bottom-right dark sleeve fragment (400..512, 320..512)
    im44 = Image.open(os.path.join(REPO_ROOT, "assets", "portraits_page3_src", "cutouts", "44_hewitt.png")).convert("RGBA")
    im44 = _erase_poly(im44, [(400, 320), (512, 320), (512, 512), (415, 512)], blur=1.0)
    im44 = remove_small_alpha_islands(im44, 300)
    fixed_specs.append(("44", im44, (118, 12, 480, 415), 0.03, 52))

    # 4) 45 Safin: intact 45_safin.png full shoulders + deep green foliage cleanup + eye_y=74
    im45 = Image.open(os.path.join(REPO_ROOT, "assets", "portraits_page3_src", "cutouts", "45_safin.png")).convert("RGBA")
    im45 = _erase_yellow_green_grass(im45, 0, 130, 512, 380)
    px45 = im45.load()
    for y in range(135, 360):
        for x in list(range(0, 190)) + list(range(385, 512)):
            r, g, b, a = px45[x, y]
            if a > 0 and g >= r - 6 and g >= b - 2 and (0.299 * r + 0.587 * g + 0.114 * b) < 120:
                px45[x, y] = (r, g, b, 0)
    im45 = remove_small_alpha_islands(im45, 300)
    fixed_specs.append(("45", im45, (12, 20, 498, 495), 0.03, 74))

    # 5) 47 Ferrero: clean upper body PhotoCraft cutout + eye_y=58
    im47 = remove_small_alpha_islands(pc_res[47], 300)
    fixed_specs.append(("47", im47, (35, 10, 470, 475), 0.03, 58))

    # 6) 49 Ferrer: restore brown hair from 49_ferrer_orig.jpg, remove isolated floating racket sliver, tighten upper-body crop
    im49 = fix_ferrer_hair_and_racket()
    im49 = _erase_poly(im49, [(0, 0), (540, 0), (540, 310), (350, 360), (0, 360)], blur=1.0)
    im49 = remove_small_alpha_islands(im49, 450)
    fixed_specs.append(("49", im49, (50, 215, 920, 1060), 0.03, 78))

    # 7) 51 Lendl: erase stray top-left square crowd corner next to temple/hair (x=250..308, y=42..126)
    im51 = Image.open(os.path.join(REPO_ROOT, "assets", "cutouts_v2", "51.png")).convert("RGBA")
    im51 = _erase_poly(im51, [(255, 42), (302, 42), (302, 95), (275, 130), (255, 130)], blur=0.8)
    im51 = remove_small_alpha_islands(im51, 300)
    fixed_specs.append(("51", im51, (105, 42, 650, 560), 0.03, 52))

    # Pack DDS files and assemble audit sheet
    cols, rows = 4, 2
    cw, ch = 260, 326
    sheet = Image.new("RGB", (cols * cw, rows * ch), (28, 30, 38))
    tile = Image.new("RGB", (256, 256))
    tpx = tile.load()
    for y in range(256):
        for x in range(256):
            tpx[x, y] = (62, 66, 78) if ((x // 16) + (y // 16)) % 2 == 0 else (92, 98, 112)
    draw = ImageDraw.Draw(sheet)

    for idx, (k, cutout, cbox, pad_r, eye_y) in enumerate(fixed_specs):
        p256 = frame_portrait_256(cutout, cbox, pad_r)
        eye = build_eye_strip(p256, eye_y)
        ps = build_photo_s(p256)

        write_bgra_dds(p256, os.path.join(REPO_ROOT, VR_DIR, "photo_L", f"{k}.dds"))
        write_bgra_dds(eye, os.path.join(REPO_ROOT, VR_DIR, "photo_eye", f"{k}.dds"))
        write_dxt5_dds(ps, os.path.join(REPO_ROOT, VR_DIR, "photo_S", f"{k}.dds"))
        print(f"Packed fixed ID {k}: photo_L/eye/S updated.")

        r, c = divmod(idx, cols)
        x0, y0 = c * cw + 2, r * ch + 2
        sheet.paste(tile, (x0, y0))
        sheet.paste(p256, (x0, y0), p256)
        sheet.paste(eye.resize((256, 64), Image.Resampling.LANCZOS), (x0, y0 + 258))
        draw.rectangle([x0, y0, x0 + 96, y0 + 18], fill=(15, 18, 25))
        draw.text((x0 + 4, y0 + 3), f"FIXED {k}", fill=(120, 255, 150))

    audit_path = os.path.join(SCRATCH_DIR, "fixed_portraits_v3_audit.png")
    sheet.save(audit_path)
    Image.open(audit_path).verify()
    print("Verified contact sheet:", audit_path)

    for fn in os.listdir(SCRATCH_DIR):
        if fn.startswith(("_grid_", "_dbg_", "test_ag91_", "test_il_surface.", "test_umpire_uv.", "_compare_fix")):
            try:
                os.remove(os.path.join(SCRATCH_DIR, fn))
            except OSError:
                pass


if __name__ == "__main__":
    main()
