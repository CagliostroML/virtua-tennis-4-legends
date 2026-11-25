#!/usr/bin/env python3
"""Fetch prime-era reference photos for Page 4 players (IDs 59..81) from Wikipedia / Wikimedia Commons."""
import json
import os
import sys
import time
from PIL import Image, ImageDraw

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

from fetch_face_refs import batch_wiki_leads, search_commons_photos, download_file

PAGE4_PLAYERS = [
    (59, "SHE", "Ben Shelton", "Ben_Shelton", "Ben Shelton tennis"),
    (60, "RUB", "Andrey Rublev", "Andrey_Rublev_(tennis)", "Andrey Rublev tennis"),
    (61, "RUU", "Casper Ruud", "Casper_Ruud", "Casper Ruud tennis"),
    (62, "FRI", "Taylor Fritz", "Taylor_Fritz", "Taylor Fritz tennis"),
    (63, "GAU", "Coco Gauff", "Coco_Gauff", "Coco Gauff tennis"),
    (64, "RYB", "Elena Rybakina", "Elena_Rybakina", "Elena Rybakina tennis"),
    (65, "BAD", "Paula Badosa", "Paula_Badosa", "Paula Badosa tennis"),
    (66, "HAL", "Simona Halep", "Simona_Halep", "Simona Halep tennis"),
    (67, "COR", "Guillermo Coria", "Guillermo_Coria", "Guillermo Coria tennis"),
    (68, "GAS", "Richard Gasquet", "Richard_Gasquet", "Richard Gasquet tennis"),
    (69, "NIS", "Kei Nishikori", "Kei_Nishikori", "Kei Nishikori tennis"),
    (70, "SOD", "Robin Soderling", "Robin_Söderling", "Robin Soderling tennis"),
    (71, "BER", "Tomas Berdych", "Tomáš_Berdych", "Tomas Berdych tennis"),
    (72, "CHN", "Michael Chang", "Michael_Chang", "Michael Chang tennis 199"),
    (73, "RIO", "Marcelo Rios", "Marcelo_Ríos", "Marcelo Rios tennis"),
    (74, "MUS", "Thomas Muster", "Thomas_Muster", "Thomas Muster tennis"),
    (75, "BRU", "Sergi Bruguera", "Sergi_Bruguera", "Sergi Bruguera tennis"),
    (76, "CRT", "Alex Corretja", "Àlex_Corretja", "Alex Corretja tennis"),
    (77, "WLD", "Mats Wilander", "Mats_Wilander", "Mats Wilander tennis 198"),
    (78, "LAV", "Rod Laver", "Rod_Laver", "Rod Laver tennis 196"),
    (79, "ASV", "Arantxa Sanchez Vicario", "Arantxa_Sánchez_Vicario", "Arantxa Sanchez Vicario tennis"),
    (80, "CMT", "Conchita Martinez", "Conchita_Martínez", "Conchita Martinez tennis"),
    (81, "CLI", "Kim Clijsters", "Kim_Clijsters", "Kim Clijsters tennis"),
]

OUT_SRC = os.path.join(REPO_ROOT, "assets", "portraits_page4_src")
OUT_REFS = os.path.join(REPO_ROOT, "assets", "face_refs")


def main():
    os.makedirs(OUT_SRC, exist_ok=True)
    os.makedirs(OUT_REFS, exist_ok=True)

    leads = batch_wiki_leads([p[3] for p in PAGE4_PLAYERS])
    print(f"Fetched {len(leads)} Wikipedia leads")

    manifest = {}
    for pid, code, name, wtitle, query in PAGE4_PLAYERS:
        slug = name.lower().replace(" ", "_")
        orig_dst = os.path.join(OUT_SRC, f"{pid}_{slug}_orig.jpg")
        rdir = os.path.join(OUT_REFS, f"{pid}_{code}")
        os.makedirs(rdir, exist_ok=True)

        urls = []
        if wtitle in leads:
            urls.append(leads[wtitle])
        try:
            for u in search_commons_photos(query, limit=5):
                if u not in urls:
                    urls.append(u)
        except Exception as ex:
            print(f"[{pid}_{code}] commons err: {ex}")

        saved = []
        for idx, u in enumerate(urls[:4]):
            dst = os.path.join(rdir, f"ref_{idx}.jpg")
            if download_file(u, dst):
                saved.append(dst)
            time.sleep(0.25)

        # Pick best active/portrait candidate for portraits_page4_src/<id>_<slug>_orig.jpg
        if saved and not os.path.exists(orig_dst):
            # Prefer ref_0 (Wikipedia lead) or first saved candidate
            import shutil
            shutil.copyfile(saved[0], orig_dst)

        manifest[pid] = {"code": code, "name": name, "orig": orig_dst if os.path.exists(orig_dst) else None, "refs": saved}
        print(f"[{pid}_{code}] {name}: {len(saved)} refs (orig={'OK' if os.path.exists(orig_dst) else 'MISS'})")

    with open(os.path.join(OUT_SRC, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    # Contact sheet for visual inspection
    cols = 6
    rows = (len(PAGE4_PLAYERS) + cols - 1) // cols
    cw, ch = 220, 220
    sheet = Image.new("RGB", (cols * cw, rows * ch), (24, 26, 32))
    draw = ImageDraw.Draw(sheet)
    for i, (pid, code, name, _, _) in enumerate(PAGE4_PLAYERS):
        r, c = divmod(i, cols)
        x0, y0 = c * cw, r * ch
        p = manifest[pid]["orig"]
        if p and os.path.exists(p):
            try:
                im = Image.open(p).convert("RGB")
                im.thumbnail((204, 180), Image.Resampling.BILINEAR)
                sheet.paste(im, (x0 + 8, y0 + 26))
            except Exception:
                pass
        draw.text((x0 + 8, y0 + 6), f"{pid} {code} - {name[:16]}", fill=(235, 240, 250))
    sheet.save(os.path.join(OUT_SRC, "page4_refs_audit.png"))
    print("Saved", os.path.join(OUT_SRC, "page4_refs_audit.png"))


if __name__ == "__main__":
    main()
