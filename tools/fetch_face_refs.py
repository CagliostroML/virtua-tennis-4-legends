#!/usr/bin/env python3
"""Fetch prime-era & multi-angle Wikimedia reference photos for face UV projection + build matching."""
import json
import os
import time
import urllib.parse
import urllib.request
from PIL import Image, ImageDraw

PLAYERS = [
    (26, "ALC", "Carlos_Alcaraz", "Carlos Alcaraz tennis"),
    (27, "SIN", "Jannik_Sinner", "Jannik Sinner tennis"),
    (28, "SAM", "Pete_Sampras", "Pete Sampras tennis"),
    (29, "AG2", "Andre_Agassi", "Andre Agassi tennis"),
    ("29_91", "AGA", "Andre_Agassi", "Andre Agassi tennis 1990s"),
    (30, "BOR", "Björn_Borg", "Bjorn Borg tennis Wimbledon"),
    (31, "MCE", "John_McEnroe", "John McEnroe tennis"),
    (32, "GRA", "Steffi_Graf", "Steffi Graf tennis"),
    (33, "SER", "Serena_Williams", "Serena Williams tennis"),
    (34, "SWI", "Iga_Świątek", "Iga Swiatek tennis"),
    (35, "SAB", "Aryna_Sabalenka", "Aryna Sabalenka tennis"),
    (36, "KUE", "Gustavo_Kuerten", "Gustavo Kuerten tennis"),
    (37, "NAV", "Martina_Navratilova", "Martina Navratilova tennis"),
    (38, "WAW", "Stan_Wawrinka", "Stan Wawrinka tennis"),
    (39, "MED", "Daniil_Medvedev", "Daniil Medvedev tennis"),
    (40, "ZVE", "Alexander_Zverev", "Alexander Zverev tennis"),
    (41, "TSI", "Stefanos_Tsitsipas", "Stefanos Tsitsipas tennis"),
    (42, "THI", "Dominic_Thiem", "Dominic Thiem tennis"),
    (43, "KYR", "Nick_Kyrgios", "Nick Kyrgios tennis"),
    (44, "HEW", "Lleyton_Hewitt", "Lleyton Hewitt tennis"),
    (45, "SAF", "Marat_Safin", "Marat Safin tennis"),
    (46, "TSO", "Jo-Wilfried_Tsonga", "Jo-Wilfried Tsonga tennis"),
    (47, "FRR", "Juan_Carlos_Ferrero", "Juan Carlos Ferrero tennis"),
    (48, "MOY", "Carlos_Moyá", "Carlos Moya tennis"),
    (49, "FER", "David_Ferrer", "David Ferrer tennis"),
    (50, "NAL", "David_Nalbandian", "David Nalbandian tennis"),
    (51, "LEN", "Ivan_Lendl", "Ivan Lendl tennis"),
    (52, "CON", "Jimmy_Connors", "Jimmy Connors tennis"),
    (53, "VIL", "Guillermo_Vilas", "Guillermo Vilas tennis"),
    (54, "IVN", "Goran_Ivanišević", "Goran Ivanisevic tennis"),
    (55, "EVE", "Chris_Evert", "Chris Evert tennis"),
    (56, "SEL", "Monica_Seles", "Monica Seles tennis"),
    (57, "HEN", "Justine_Henin", "Justine Henin tennis"),
    (58, "MUG", "Garbiñe_Muguruza", "Garbine Muguruza tennis"),
]

HDRS = {"User-Agent": "VT4LegendsModBot/1.0 (local-research; python-urllib)"}
OUT_ROOT = os.path.join("assets", "face_refs")


def fetch_json(url: str) -> dict:
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=HDRS)
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read().decode("utf-8", errors="replace"))
        except Exception as ex:
            if "429" in str(ex):
                time.sleep(2.5 * (attempt + 1))
            elif attempt == 2:
                raise
            else:
                time.sleep(0.8)
    return {}


def download_file(url: str, dst: str) -> bool:
    if os.path.exists(dst) and os.path.getsize(dst) > 4096:
        return True
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=HDRS)
            with urllib.request.urlopen(req, timeout=15) as r:
                data = r.read()
            if len(data) < 4096:
                return False
            with open(dst, "wb") as f:
                f.write(data)
            Image.open(dst).verify()
            return True
        except Exception as ex:
            if os.path.exists(dst):
                os.remove(dst)
            if "429" in str(ex):
                time.sleep(2.5 * (attempt + 1))
            else:
                return False
    return False


def batch_wiki_leads(titles: list[str]) -> dict[str, str]:
    res = {}
    joined = "|".join(dict.fromkeys(titles))
    url = (
        "https://en.wikipedia.org/w/api.php?action=query&titles="
        + urllib.parse.quote(joined, safe="|")
        + "&prop=pageimages&pithumbsize=800&format=json"
    )
    d = fetch_json(url)
    for p in (d.get("query") or {}).get("pages", {}).values():
        t = p.get("title", "")
        u = (p.get("thumbnail") or {}).get("source")
        if t and u:
            res[t.replace(" ", "_")] = u
    return res


def search_commons_photos(query: str, limit: int = 4) -> list[str]:
    q = urllib.parse.quote(query)
    api = (
        f"https://commons.wikimedia.org/w/api.php?action=query&generator=search"
        f"&gsrsearch={q}&gsrnamespace=6&gsrlimit=8&prop=imageinfo&iiprop=url|mime|size&iiurlwidth=800&format=json"
    )
    d = fetch_json(api)
    pages = (d.get("query") or {}).get("pages") or {}
    urls = []
    for p in pages.values():
        ii = (p.get("imageinfo") or [{}])[0]
        if ii.get("mime") not in ("image/jpeg", "image/png"):
            continue
        if ii.get("width", 0) < 300 or ii.get("height", 0) < 300:
            continue
        u = ii.get("thumburl") or ii.get("url")
        if u and u not in urls:
            urls.append(u)
        if len(urls) >= limit:
            break
    return urls


def main() -> None:
    os.makedirs(OUT_ROOT, exist_ok=True)
    leads = batch_wiki_leads([p[2] for p in PLAYERS])
    print(f"Batch Wikipedia leads: {len(leads)} players")

    for pid, code, wtitle, query in PLAYERS:
        pdir = os.path.join(OUT_ROOT, f"{pid}_{code}")
        os.makedirs(pdir, exist_ok=True)
        existing = [x for x in os.listdir(pdir) if x.lower().endswith((".jpg", ".jpeg", ".png"))]
        if len(existing) >= 3:
            print(f"[{pid}_{code}] cached ({len(existing)})")
            continue

        urls = []
        lead_u = leads.get(wtitle)
        if lead_u:
            urls.append(lead_u)
        try:
            for u in search_commons_photos(query, limit=4):
                if u not in urls:
                    urls.append(u)
        except Exception as ex:
            print(f"[{pid}_{code}] search err: {ex}")

        saved = len(existing)
        for idx, u in enumerate(urls[:4]):
            dst = os.path.join(pdir, f"ref_{idx}.jpg")
            if os.path.exists(dst):
                continue
            if download_file(u, dst):
                saved += 1
            time.sleep(0.35)
        print(f"[{pid}_{code}] saved total {saved} refs")


if __name__ == "__main__":
    main()
