#!/usr/bin/env python3
"""
Curate prime-era reference photos + SEGA 1024x1024 base UV maps into
assets/face_uv_workspace/ so the user can edit faces in AI Studio / PhotoCraft
and pack them with one command: python tools/pack_custom_faces.py
"""
import json
import os
import shutil
import sys
from PIL import Image, ImageDraw

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

from fetch_face_refs import search_commons_photos, download_file

WS_DIR = os.path.join(REPO_ROOT, "assets", "face_uv_workspace")
REFS_DIR = os.path.join(REPO_ROOT, "assets", "face_refs")
PSRC_2 = os.path.join(REPO_ROOT, "assets", "portraits_src")
PSRC_3 = os.path.join(REPO_ROOT, "assets", "portraits_page3_src")
PSRC_4 = os.path.join(REPO_ROOT, "assets", "portraits_page4_src")
BATCH_IN = os.path.join(REPO_ROOT, "assets", "portraits_batch_in")

# Curated good files from existing local assets (excluding elderly, movie, or autograph pics)
CURATED_LOCAL = {
    "26_ALC": [os.path.join(PSRC_2, "26_alcaraz_orig.jpg"), os.path.join(REFS_DIR, "26_ALC", "ref_0.jpg"), os.path.join(REFS_DIR, "26_ALC", "ref_3.jpg")],
    "27_SIN": [os.path.join(PSRC_2, "27_sinner_orig.jpg"), os.path.join(REFS_DIR, "27_SIN", "ref_0.jpg"), os.path.join(REFS_DIR, "27_SIN", "ref_3.jpg")],
    "28_SAM": [os.path.join(PSRC_2, "28_sampras_nb.jpg"), os.path.join(PSRC_2, "28_sampras_orig.jpg"), os.path.join(REFS_DIR, "28_SAM", "ref_0.jpg")],
    "29_91_AGA": [os.path.join(BATCH_IN, "29_91.jpg")],
    "29_AG2": [os.path.join(PSRC_2, "29_agassi_orig.jpg"), os.path.join(REFS_DIR, "29_AG2", "ref_0.jpg"), os.path.join(REFS_DIR, "29_AG2", "ref_3.jpg")],
    "30_BOR": [os.path.join(PSRC_2, "30_borg_nb.jpg"), os.path.join(PSRC_2, "30_borg_orig.jpg")],
    "31_MCE": [os.path.join(PSRC_2, "31_mcenroe_nb.jpg"), os.path.join(PSRC_2, "31_mcenroe_orig.jpg"), os.path.join(REFS_DIR, "31_MCE", "ref_2.jpg")],
    "32_GRA": [os.path.join(PSRC_2, "32_graf_orig.jpg")],
    "33_SER": [os.path.join(PSRC_2, "33_serena_orig.jpg"), os.path.join(REFS_DIR, "33_SER", "ref_0.jpg"), os.path.join(REFS_DIR, "33_SER", "ref_1.jpg")],
    "34_SWI": [os.path.join(PSRC_2, "34_swiatek_orig.jpg"), os.path.join(REFS_DIR, "34_SWI", "ref_0.jpg")],
    "35_SAB": [os.path.join(PSRC_2, "35_sabalenka_orig.jpg"), os.path.join(REFS_DIR, "35_SAB", "ref_0.jpg"), os.path.join(REFS_DIR, "35_SAB", "ref_1.jpg")],
    "36_KUE": [os.path.join(PSRC_2, "36_kuerten_nb.jpg"), os.path.join(PSRC_2, "36_kuerten_orig.jpg")],
    "37_NAV": [os.path.join(BATCH_IN, "37.jpg"), os.path.join(PSRC_2, "37_navratilova_orig.jpg")],
    "38_WAW": [os.path.join(PSRC_3, "38_wawrinka_orig.jpg"), os.path.join(REFS_DIR, "38_WAW", "ref_0.jpg")],
    "39_MED": [os.path.join(PSRC_3, "39_medvedev_orig.jpg"), os.path.join(REFS_DIR, "39_MED", "ref_0.jpg")],
    "40_ZVE": [os.path.join(PSRC_3, "40_zverev_orig.jpg"), os.path.join(REFS_DIR, "40_ZVE", "ref_0.jpg")],
    "41_TSI": [os.path.join(PSRC_3, "41_tsitsipas_orig.jpg"), os.path.join(REFS_DIR, "41_TSI", "ref_0.jpg"), os.path.join(REFS_DIR, "41_TSI", "ref_1.jpg")],
    "42_THI": [os.path.join(PSRC_3, "42_thiem_orig.jpg"), os.path.join(REFS_DIR, "42_THI", "ref_0.jpg")],
    "43_KYR": [os.path.join(PSRC_3, "43_kyrgios_orig.jpg"), os.path.join(REFS_DIR, "43_KYR", "ref_0.jpg")],
    "44_HEW": [os.path.join(PSRC_3, "44_hewitt_orig.jpg"), os.path.join(REFS_DIR, "44_HEW", "ref_0.jpg")],
    "45_SAF": [os.path.join(PSRC_3, "45_safin_orig.jpg"), os.path.join(REFS_DIR, "45_SAF", "ref_0.jpg"), os.path.join(REFS_DIR, "45_SAF", "ref_1.jpg")],
    "46_TSO": [os.path.join(PSRC_3, "46_tsonga_orig.jpg"), os.path.join(REFS_DIR, "46_TSO", "ref_0.jpg")],
    "47_FRR": [os.path.join(PSRC_3, "47_ferrero_orig.jpg"), os.path.join(REFS_DIR, "47_FRR", "ref_0.jpg"), os.path.join(REFS_DIR, "47_FRR", "ref_2.jpg")],
    "48_MOY": [os.path.join(PSRC_3, "48_moya_orig.jpg"), os.path.join(REFS_DIR, "48_MOY", "ref_0.jpg")],
    "49_FER": [os.path.join(PSRC_3, "49_ferrer_orig.jpg"), os.path.join(REFS_DIR, "49_FER", "ref_0.jpg"), os.path.join(REFS_DIR, "49_FER", "ref_2.jpg")],
    "50_NAL": [os.path.join(PSRC_3, "50_nalbandian_orig.jpg"), os.path.join(REFS_DIR, "50_NAL", "ref_0.jpg")],
    "51_LEN": [os.path.join(BATCH_IN, "51.jpg"), os.path.join(PSRC_3, "51_lendl_orig.jpg")],
    "52_CON": [os.path.join(BATCH_IN, "52.jpg"), os.path.join(PSRC_3, "52_connors_orig.jpg")],
    "53_VIL": [os.path.join(PSRC_3, "53_vilas_orig.jpg"), os.path.join(REFS_DIR, "53_VIL", "ref_0.jpg"), os.path.join(REFS_DIR, "53_VIL", "ref_2.jpg")],
    "54_IVN": [os.path.join(PSRC_3, "54_ivanisevic_orig.jpg"), os.path.join(REFS_DIR, "54_IVN", "ref_0.jpg")],
    "55_EVE": [os.path.join(BATCH_IN, "55.jpg"), os.path.join(PSRC_3, "55_evert_orig.jpg")],
    "56_SEL": [os.path.join(PSRC_3, "56_seles_orig.jpg"), os.path.join(REFS_DIR, "56_SEL", "ref_0.jpg"), os.path.join(REFS_DIR, "56_SEL", "ref_2.jpg")],
    "57_HEN": [os.path.join(PSRC_3, "57_henin_orig.jpg"), os.path.join(REFS_DIR, "57_HEN", "ref_1.jpg")],
    "58_MUG": [os.path.join(PSRC_3, "58_muguruza_orig.jpg"), os.path.join(REFS_DIR, "58_MUG", "ref_0.jpg"), os.path.join(REFS_DIR, "58_MUG", "ref_2.jpg")],
    "59_SHE": [os.path.join(PSRC_4, "59_ben_shelton_orig.jpg"), os.path.join(REFS_DIR, "59_SHE", "ref_0.jpg"), os.path.join(REFS_DIR, "59_SHE", "extra_0.jpg")],
    "60_RUB": [os.path.join(PSRC_4, "60_andrey_rublev_orig.jpg"), os.path.join(REFS_DIR, "60_RUB", "ref_3.jpg"), os.path.join(REFS_DIR, "60_RUB", "extra_1.jpg"), os.path.join(REFS_DIR, "60_RUB", "ref_0.jpg")],
    "61_RUU": [os.path.join(PSRC_4, "61_casper_ruud_orig.jpg"), os.path.join(REFS_DIR, "61_RUU", "extra_0.jpg")],
    "62_FRI": [os.path.join(PSRC_4, "62_taylor_fritz_orig.jpg"), os.path.join(REFS_DIR, "62_FRI", "ref_1.jpg"), os.path.join(REFS_DIR, "62_FRI", "ref_2.jpg"), os.path.join(REFS_DIR, "62_FRI", "ref_3.jpg")],
    "63_GAU": [os.path.join(PSRC_4, "63_coco_gauff_orig.jpg"), os.path.join(REFS_DIR, "63_GAU", "extra_0.jpg")],
    "64_RYB": [os.path.join(PSRC_4, "64_elena_rybakina_orig.jpg"), os.path.join(REFS_DIR, "64_RYB", "ref_2.jpg"), os.path.join(REFS_DIR, "64_RYB", "ref_3.jpg")],
    "65_BAD": [os.path.join(PSRC_4, "65_paula_badosa_orig.jpg"), os.path.join(REFS_DIR, "65_BAD", "extra_0.jpg"), os.path.join(REFS_DIR, "65_BAD", "extra_1.jpg")],
    "66_HAL": [os.path.join(PSRC_4, "66_simona_halep_orig.jpg"), os.path.join(REFS_DIR, "66_HAL", "extra_2.jpg"), os.path.join(REFS_DIR, "66_HAL", "extra_3.jpg")],
    "67_COR": [os.path.join(PSRC_4, "67_guillermo_coria_orig.jpg"), os.path.join(REFS_DIR, "67_COR", "extra_5.jpg"), os.path.join(REFS_DIR, "67_COR", "ref_0.jpg")],
    "68_GAS": [os.path.join(PSRC_4, "68_richard_gasquet_orig.jpg"), os.path.join(REFS_DIR, "68_GAS", "ref_3.jpg"), os.path.join(REFS_DIR, "68_GAS", "extra_0.jpg")],
    "69_NIS": [os.path.join(PSRC_4, "69_kei_nishikori_orig.jpg"), os.path.join(REFS_DIR, "69_NIS", "extra_5.jpg"), os.path.join(REFS_DIR, "69_NIS", "extra_6.jpg"), os.path.join(REFS_DIR, "69_NIS", "extra_0.jpg")],
    "70_SOD": [os.path.join(PSRC_4, "70_robin_soderling_orig.jpg"), os.path.join(REFS_DIR, "70_SOD", "ref_1.jpg")],
    "71_BER": [os.path.join(PSRC_4, "71_tomas_berdych_orig.jpg"), os.path.join(REFS_DIR, "71_BER", "ref_1.jpg")],
    "72_CHN": [os.path.join(PSRC_4, "72_michael_chang_orig.jpg")],
    "73_RIO": [os.path.join(PSRC_4, "73_marcelo_rios_orig.jpg"), os.path.join(REFS_DIR, "73_RIO", "extra_0.jpg")],
    "74_MUS": [os.path.join(PSRC_4, "74_thomas_muster_orig.jpg"), os.path.join(REFS_DIR, "74_MUS", "extra_2.jpg"), os.path.join(REFS_DIR, "74_MUS", "extra_0.jpg")],
    "75_BRU": [os.path.join(PSRC_4, "75_sergi_bruguera_orig.jpg")],
    "76_CRT": [os.path.join(PSRC_4, "76_alex_corretja_orig.jpg"), os.path.join(REFS_DIR, "76_CRT", "extra_1.jpg")],
    "77_WLD": [os.path.join(PSRC_4, "77_mats_wilander_orig.jpg"), os.path.join(REFS_DIR, "77_WLD", "extra_1.jpg")],
    "78_LAV": [os.path.join(PSRC_4, "78_rod_laver_orig.jpg"), os.path.join(REFS_DIR, "78_LAV", "extra_2.jpg"), os.path.join(REFS_DIR, "78_LAV", "extra_5.jpg")],
    "79_ASV": [os.path.join(PSRC_4, "79_arantxa_sanchez_vicario_orig.jpg"), os.path.join(REFS_DIR, "79_ASV", "extra_1.jpg")],
    "80_CMT": [os.path.join(PSRC_4, "80_conchita_martinez_orig.jpg"), os.path.join(REFS_DIR, "80_CMT", "ref_2.jpg"), os.path.join(REFS_DIR, "80_CMT", "ref_3.jpg")],
    "81_CLI": [os.path.join(PSRC_4, "81_kim_clijsters_orig.jpg"), os.path.join(REFS_DIR, "81_CLI", "ref_2.jpg")],
}

PRIME_WIKI_QUERIES = {
    "29_91_AGA": "Andre Agassi 199",
    "30_BOR": "Bjorn Borg 1979",
    "32_GRA": "Steffi Graf 199",
    "36_KUE": "Gustavo Kuerten Roland Garros",
    "37_NAV": "Martina Navratilova 198",
    "51_LEN": "Ivan Lendl 198",
    "52_CON": "Jimmy Connors 197",
    "55_EVE": "Chris Evert 197",
}


def main():
    manifest_path = os.path.join(WS_DIR, "manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    summary = {}
    for folder in sorted(manifest.keys()):
        fdir = os.path.join(WS_DIR, folder)
        os.makedirs(fdir, exist_ok=True)
        copied = 0
        for idx, src in enumerate(CURATED_LOCAL.get(folder, []), start=1):
            if not os.path.exists(src):
                continue
            ext = os.path.splitext(src)[1].lower()
            dst = os.path.join(fdir, f"ref_prime_{idx}{ext}")
            shutil.copyfile(src, dst)
            copied += 1

        if folder in PRIME_WIKI_QUERIES:
            try:
                urls = search_commons_photos(PRIME_WIKI_QUERIES[folder], limit=2)
                for j, u in enumerate(urls, start=1):
                    # Skip obvious movie/film refs
                    if "labeouf" in u.lower() or "movie" in u.lower() or "film" in u.lower():
                        continue
                    dst = os.path.join(fdir, f"ref_wiki_{j}.jpg")
                    if download_file(u, dst):
                        copied += 1
            except Exception as ex:
                print(f"[{folder}] wiki search skip: {ex}")

        summary[folder] = copied
        print(f"[{folder:9s}] base UV + {copied} prime ref(s)")

    # Build quick visual audit sheet of all 57 folders (base UV + ref_prime_1)
    cols = 6
    rows = (len(summary) + cols - 1) // cols
    cw, ch = 260, 140
    sheet = Image.new("RGB", (cols * cw, rows * ch), (24, 26, 32))
    draw = ImageDraw.Draw(sheet)
    for idx, folder in enumerate(sorted(summary.keys())):
        r, c = divmod(idx, cols)
        x0, y0 = c * cw, r * ch
        fdir = os.path.join(WS_DIR, folder)
        uv_p = os.path.join(fdir, "00_sega_base_uv.png")
        if os.path.exists(uv_p):
            uv = Image.open(uv_p).convert("RGB").resize((112, 112), Image.Resampling.BILINEAR)
            sheet.paste(uv, (x0 + 6, y0 + 22))
        refs = sorted(x for x in os.listdir(fdir) if x.startswith("ref_"))
        if refs:
            try:
                rf = Image.open(os.path.join(fdir, refs[0])).convert("RGB")
                rf.thumbnail((126, 112), Image.Resampling.BILINEAR)
                sheet.paste(rf, (x0 + 124, y0 + 22))
            except Exception:
                pass
        draw.text((x0 + 6, y0 + 4), f"{folder} ({summary[folder]} refs)", fill=(230, 235, 245))
    sheet.save(os.path.join(WS_DIR, "workspace_audit.png"))
    print("Saved workspace_audit.png")


if __name__ == "__main__":
    main()
