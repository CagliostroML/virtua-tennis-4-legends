#!/usr/bin/env python3
"""
Build a turnkey 3D Face UV Texture editing workspace in:
  assets/face_uv_photocraft_workspace/

Mirrors assets/portraits_photocraft_workspace/ so an external PhotoCraft + AI
workflow can edit all 57 custom players' 1024x1024 face UV maps cleanly and
deliver them to 03_entregar_editados_aqui/ for 1-command packing via:
  python -u tools/import_edited_face_uvs.py
"""
import json
import os
import shutil
import sys
from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

from vt4_archive import BIN0, BIN1, load_directory, read_entry, lzss_decompress
from update_custom_assets import parse_sdo_dds_slots, extract_slot_image
from prepare_portraits_workspace import PLAYERS

WS_OUT = os.path.join(REPO_ROOT, "assets", "face_uv_photocraft_workspace")
FACE_WS_SRC = os.path.join(REPO_ROOT, "assets", "face_uv_workspace")
CUTOUTS_DIR = os.path.join(
    REPO_ROOT, "assets", "portraits_photocraft_workspace", "03_entregar_editados_aqui", "cutouts"
)
MODEL_DIR = os.path.join(REPO_ROOT, "game", "archive", "HIGH", "Player", "Model")

DIR_REF_SEGA = os.path.join(WS_OUT, "00_referencias_oficiales_sega")
DIR_INPUTS = os.path.join(WS_OUT, "01_base_uv_y_referencias")
DIR_CURRENT = os.path.join(WS_OUT, "02_estado_actual_en_juego")
DIR_DROP = os.path.join(WS_OUT, "03_entregar_editados_aqui")

OFFICIAL_SEGA_REFS = [
    ("P_M_FED_SN.sdo", "P_FED_B_face_SN.dds"),
    ("P_M_NAD_IT.sdo", "P_NAD_B_face_IT.dds"),
    ("P_M_DJV_IT.sdo", "P_DJV_B_face_IT.dds"),
    ("P_W_SHA_SN.sdo", "P_SHA_B_face_SN.dds"),
    ("P_W_IVA_IT.sdo", "P_IVA_B_face_IT.dds"),
    ("P_W_WIL_SN.sdo", "P_WIL_B_face_SN.dds"),
]

# Per-player hints so the AI/PhotoCraft editor handles base-model artifacts cleanly.
BEARD_BASES = {"P_M_RAF_IT.sdo", "P_M_DEL_SN.sdo", "P_M_FED_SN.sdo", "P_M_NAD_IT.sdo", "P_M_GON_SN.sdo", "P_M_HAS_IT.sdo", "P_M_KOH_IT.sdo"}
PLAYER_NOTES = {
    "26_ALC": "Barba corta muy recortada / sombra de 2 días, cejas pobladas oscuras.",
    "27_SIN": "Afeitado limpio, pecas sutiles y tono claro rojizo/pelirrojo.",
    "28_SAM": "Base P_M_EDB_SN sin barba; sombra leve mediterránea, cejas gruesas oscuras.",
    "29_91_AGA": "Agassi 1991: quitar barba de P_M_NAD_IT (afeitado limpio o sombra juvenil), melena rubia tratada aparte.",
    "29_AG2": "Agassi 2006: cuero cabelludo 100% CALVO y liso arriba/laterales (no pintar pelo), mantener perilla recortada.",
    "30_BOR": "Base P_M_RAF_IT: quitar barba moderna oscura o dejar barba rubia/castaña clara años 70-80, cejas rubias.",
    "31_MCE": "Base P_M_RAF_IT: afeitado limpio (quitar barba de Nadal), cejas castañas expresivas.",
    "32_GRA": "Sin maquillaje pesado, piel clara pecosa/natural años 90.",
    "33_SER": "Base P_W_WIL_SN: tono oscuro cálido, rasgos atléticos naturales.",
    "34_SWI": "Base P_W_WOZ_IT: piel clara natural, cejas definidas.",
    "35_SAB": "Base P_W_KUZ_IT: rasgos marcados y piel clara-media.",
    "36_KUE": "Base P_M_RAF_IT: quitar barba densa (barba mínima o afeitado juvenil), piel bronceada.",
    "37_NAV": "Base P_W_CHA_IT: piel clara años 80, sin maquillaje moderno.",
    "38_WAW": "Barba corta cuidada de Stanislas Wawrinka.",
    "39_MED": "Base P_M_DEL_SN: ajustar barba a barba corta/irregulares fina de Medvedev, piel clara.",
    "40_ZVE": "Base P_M_DEL_SN: quitar barba densa de Del Potro (afeitado limpio o sombra muy fina), piel clara.",
    "41_TSI": "Base P_M_GON_SN: ajustar barba estilizada y cejas pobladas oscuras.",
    "42_THI": "Base P_M_HAS_IT: sombra corta/afeitado limpio, piel clara centroeuropea.",
    "43_KYR": "Base P_M_DEL_SN: barba perfilada oscura y bigote fino de Kyrgios.",
    "44_HEW": "Base P_M_ROD_SN: afeitado limpio juvenil de Lleyton Hewitt, piel clara.",
    "45_SAF": "Base P_M_DEL_SN: afeitado limpio / sombra ligera de Safin.",
    "46_TSO": "Base P_M_MON_SN: ajustar tono más claro que Monfils y rasgos de Tsonga (perilla sutil).",
    "47_FRR": "Base P_M_HAS_IT: afeitado limpio o sombra mínima, piel mediterránea.",
    "48_MOY": "Base P_M_NAD_IT: quitar barba pesada (afeitado limpio / sombra leve), piel bronceada mallorquina.",
    "49_FER": "Base P_M_KOH_IT: afeitado limpio o sombra leve, piel bronceada.",
    "50_NAL": "Base P_M_KOH_IT: sombra leve/afeitado limpio, piel clara-media.",
    "51_LEN": "Base P_M_EDB_SN: afeitado limpio total (años 80), rasgos angulosos de Ivan Lendl.",
    "52_CON": "Base P_M_BEC_SN: afeitado limpio total (años 70-80), piel clara.",
    "53_VIL": "Base P_M_RAF_IT: quitar barba moderna de Nadal, afeitado limpio años 70, piel bronceada.",
    "54_IVN": "Base P_M_DEL_SN: sombra corta o afeitado limpio juvenil años 90-2001.",
    "55_EVE": "Base P_W_CHA_IT: rostro juvenil años 70-80.",
    "56_SEL": "Base P_W_IVA_IT: rostro juvenil años 90.",
    "57_HEN": "Base P_W_WOZ_IT: piel clara natural con pecas ligeras.",
    "58_MUG": "Base P_W_IVA_IT: piel media cálida, cejas definidas.",
    "59_SHE": "Base P_M_MON_SN: tono más claro/dorado afroamericano-americano que Monfils, afeitado limpio.",
    "60_RUB": "Base P_M_FED_SN: afeitado limpio o sombra muy fina pelirroja, cejas pelirrojas claras.",
    "61_RUU": "Base P_M_FED_SN: afeitado limpio nórdico, piel clara.",
    "62_FRI": "Base P_M_DEL_SN: quitar barba de Del Potro (afeitado limpio), piel clara.",
    "63_GAU": "Base P_W_WIL_SN: rostro juvenil de Coco Gauff.",
    "64_RYB": "Base P_W_SHA_SN: piel muy clara porcelana, mirada serena.",
    "65_BAD": "Base P_W_IVA_IT: tono mediterráneo dorado.",
    "66_HAL": "Base P_W_CHA_IT: tono medio europeo.",
    "67_COR": "Base P_M_KOH_IT: afeitado limpio juvenil 2004.",
    "68_GAS": "Base P_M_HAS_IT: barba de 3 días ligera.",
    "69_NIS": "Base P_M_KOH_IT: rasgos asiáticos (ojos rasgados conservando párpado cerrado sin pupilas!), afeitado limpio.",
    "70_SOD": "Base P_M_DEL_SN: quitar barba densa (afeitado limpio nórdico), piel clara.",
    "71_BER": "Base P_M_DEL_SN: quitar barba densa (afeitado limpio o sombra muy clara).",
    "72_CHN": "Base P_M_KOH_IT: rasgos asiáticos juveniles 1989 (párpado cerrado!), afeitado limpio.",
    "73_RIO": "Base P_M_RAF_IT: quitar barba de Nadal (afeitado limpio 1998).",
    "74_MUS": "Base P_M_HAS_IT: afeitado limpio 1995, rostro marcado bronceado.",
    "75_BRU": "Base P_M_EDB_SN: afeitado limpio 1993-94, tono mediterráneo.",
    "76_CRT": "Base P_M_HAS_IT: sombra suave o afeitado limpio 1998-2001.",
    "77_WLD": "Base P_M_FED_SN: quitar barba de Federer (afeitado limpio nórdico años 80).",
    "78_LAV": "Base P_M_BEC_SN: afeitado limpio años 60, piel clara pecosa/pelirroja.",
    "79_ASV": "Base P_W_CHA_IT: tono bronceado mediterráneo años 90.",
    "80_CMT": "Base P_W_ROB_IT: tono mediterráneo años 90.",
    "81_CLI": "Base P_W_ROB_IT: piel clara europea.",
}


def strip_alpha_rgb(im: Image.Image) -> Image.Image:
    """Return raw opaque RGB channels without SEGA's AO alpha channel (avoids white holes)."""
    rgba = im.convert("RGBA")
    r, g, b, _ = rgba.split()
    return Image.merge("RGB", (r, g, b))


def load_font(size: int):
    for candidate in (
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ):
        if os.path.exists(candidate):
            try:
                return ImageFont.truetype(candidate, size)
            except Exception:
                pass
    return ImageFont.load_default()


def build_uv_guide(base_rgb: Image.Image, is_male: bool, out_path: str) -> None:
    """Annotate exact VT4 1024x1024 face UV zones on a pure-RGB base."""
    canvas = base_rgb.convert("RGBA")
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    f_title = load_font(22)
    f_lbl = load_font(17)

    if is_male:
        zones = [
            ((12, 12, 1012, 175), (80, 140, 255), "PELO / CUERO CABELLUDO (superior + patillas)"),
            ((310, 185, 710, 315), (90, 220, 180), "FRENTE / LINEA DEL PELO"),
            ((320, 318, 705, 366), (255, 200, 70), "CEJAS (alinear con la base)"),
            ((345, 368, 680, 422), (255, 70, 70), "PARPADOS CERRADOS: NUNCA PINTAR PUPILAS/IRIS"),
            ((432, 385, 592, 540), (140, 220, 255), "NARIZ / TABIQUE"),
            ((120, 355, 225, 540), (190, 140, 255), "OREJA"),
            ((798, 355, 904, 540), (190, 140, 255), "OREJA"),
            ((405, 570, 620, 650), (255, 120, 190), "LABIOS NEUTROS (NO SONREIR)"),
            ((115, 770, 910, 990), (110, 240, 140), "CUELLO: IGUALAR TONO CON CUERPO"),
        ]
    else:
        zones = [
            ((12, 12, 1012, 130), (80, 140, 255), "PELO / CUERO CABELLUDO"),
            ((290, 135, 730, 260), (90, 220, 180), "FRENTE / LINEA DEL PELO"),
            ((332, 262, 685, 308), (255, 200, 70), "CEJAS (alinear con la base)"),
            ((352, 310, 662, 366), (255, 70, 70), "PARPADOS CERRADOS: NUNCA PINTAR PUPILAS/IRIS"),
            ((440, 325, 580, 470), (140, 220, 255), "NARIZ"),
            ((130, 310, 228, 495), (190, 140, 255), "OREJA"),
            ((792, 310, 890, 495), (190, 140, 255), "OREJA"),
            ((418, 488, 595, 560), (255, 120, 190), "LABIOS NEUTROS"),
            ((80, 710, 944, 1008), (110, 240, 140), "CUELLO Y HOMBROS: EMPLAME CON CUERPO"),
        ]

    for (x0, y0, x1, y1), col, label in zones:
        odraw.rectangle([x0, y0, x1, y1], fill=col + (34,), outline=col + (225,), width=3)
        bbox = odraw.textbbox((0, 0), label, font=f_lbl)
        tw = (bbox[2] - bbox[0]) + 14
        th = (bbox[3] - bbox[1]) + 8
        ly = max(4, y0 - th - 2) if y0 > (th + 8) else y0 + 6
        lx = max(6, min(1018 - tw, (x0 + x1) // 2 - tw // 2))
        odraw.rectangle([lx, ly, lx + tw, ly + th], fill=(12, 14, 20, 232), outline=col + (200,), width=1)
        odraw.text((lx + 7, ly + 3), label, fill=col + (255,), font=f_lbl)

    composed = Image.alpha_composite(canvas, overlay).convert("RGB")
    draw = ImageDraw.Draw(composed)
    header = "GUIA ZONAS UV CARA VT4 (MASCULINO 1024x1024)" if is_male else "GUIA ZONAS UV CARA VT4 (FEMENINO 1024x1024)"
    draw.rectangle([0, 992, 1024, 1024], fill=(14, 16, 22))
    draw.text((16, 996), header, fill=(245, 248, 255), font=f_title)
    composed.save(out_path)


def folder_to_pid(folder: str) -> str:
    if folder == "29_91_AGA":
        return "29_91"
    return folder.split("_")[0]


def find_extra_ref(ws_folder: str) -> str | None:
    fdir = os.path.join(FACE_WS_SRC, ws_folder)
    if not os.path.isdir(fdir):
        return None
    refs = sorted(x for x in os.listdir(fdir) if x.startswith("ref_prime_"))
    if not refs:
        refs = sorted(x for x in os.listdir(fdir) if x.startswith("ref_"))
    if not refs:
        return None
    # Prefer ref_prime_2 or ref_prime_1 if available
    pick = refs[1] if len(refs) >= 2 else refs[0]
    return os.path.join(fdir, pick)


def main() -> None:
    for d in (WS_OUT, DIR_REF_SEGA, DIR_INPUTS, DIR_CURRENT, DIR_DROP):
        os.makedirs(d, exist_ok=True)

    manifest_path = os.path.join(FACE_WS_SRC, "manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Map player ID -> full readable name from PLAYERS
    id_to_name = {pid: name for pid, _code, name in PLAYERS}

    # 1. Extract 6 official SEGA pure-RGB reference UVs + annotated UV guides
    entries = load_directory()
    by_name = {e["name"].lower(): e for e in entries}
    cache = {}
    sega_rgbs = {}
    with open(BIN0, "rb") as f0, open(BIN1, "rb") as f1:
        for sdo_name, slot_name in OFFICIAL_SEGA_REFS:
            e = by_name[f"high/player/model/{sdo_name.lower()}"]
            dec = lzss_decompress(read_entry(entries, e, f0, f1, cache))
            slots = {s["name"]: s for s in parse_sdo_dds_slots(dec)}
            rgba = extract_slot_image(dec, slots[slot_name])
            rgb = strip_alpha_rgb(rgba)
            stem = sdo_name.replace(".sdo", "")
            out_p = os.path.join(DIR_REF_SEGA, f"{stem}_face_RGB.png")
            rgb.save(out_p)
            sega_rgbs[sdo_name] = rgb
            print(f"[REF-SEGA] {out_p} ({rgb.size}, pure RGB)")

    build_uv_guide(sega_rgbs["P_M_DJV_IT.sdo"], True, os.path.join(DIR_REF_SEGA, "GUIA_ZONAS_UV_MASCULINO.png"))
    build_uv_guide(sega_rgbs["P_W_SHA_SN.sdo"], False, os.path.join(DIR_REF_SEGA, "GUIA_ZONAS_UV_FEMENINO.png"))
    print("[REF-SEGA] Generated GUIA_ZONAS_UV_MASCULINO.png & GUIA_ZONAS_UV_FEMENINO.png")

    # 2. Populate 01_base_uv_y_referencias/, 02_estado_actual_en_juego/, and catalog
    catalog = {}
    audit_rows = []
    sorted_folders = sorted(manifest.keys(), key=lambda k: (29.5 if k == "29_91_AGA" else (29.8 if k == "29_AG2" else float(folder_to_pid(k)))))

    for folder in sorted_folders:
        info = manifest[folder]
        pid = folder_to_pid(folder)
        full_name = id_to_name.get(pid, folder)
        sdo_name = info["sdo"]
        base_sdo = info["base_sega_sdo"]
        face_slot = info["face_slot"]
        gender = "M" if sdo_name.startswith("P_M_") else "W"

        # 2a. Base SEGA UV in pure RGB
        src_base_uv = os.path.join(FACE_WS_SRC, folder, "00_sega_base_uv.png")
        base_uv_rgb = strip_alpha_rgb(Image.open(src_base_uv))
        base_uv_out_name = f"{folder}_base_uv.png"
        base_uv_rgb.save(os.path.join(DIR_INPUTS, base_uv_out_name))

        # 2b. High-res approved portrait cutout from Folder 03 on neutral studio gray
        cut_src = os.path.join(CUTOUTS_DIR, f"{pid}.png")
        ref_retrato_name = None
        ref_retrato_im = None
        if os.path.isfile(cut_src):
            cut_im = Image.open(cut_src).convert("RGBA")
            bg = Image.new("RGBA", cut_im.size, (60, 64, 72, 255))
            ref_retrato_im = Image.alpha_composite(bg, cut_im).convert("RGB")
            ref_retrato_name = f"{folder}_ref_retrato.png"
            ref_retrato_im.save(os.path.join(DIR_INPUTS, ref_retrato_name))

        # 2c. Secondary prime-era photo reference
        extra_src = find_extra_ref(folder)
        ref_extra_name = None
        if extra_src and os.path.isfile(extra_src):
            ext = os.path.splitext(extra_src)[1].lower()
            ref_extra_name = f"{folder}_ref_extra{ext}"
            shutil.copyfile(extra_src, os.path.join(DIR_INPUTS, ref_extra_name))

        # 2d. Current in-game face UV from game/archive/HIGH/Player/Model/<sdo>
        sdo_path = os.path.join(MODEL_DIR, sdo_name)
        dec = lzss_decompress(open(sdo_path, "rb").read())
        slots = {s["name"]: s for s in parse_sdo_dds_slots(dec)}
        cur_uv_rgb = strip_alpha_rgb(extract_slot_image(dec, slots[face_slot]))
        cur_uv_rgb.save(os.path.join(DIR_CURRENT, f"{folder}_actual.png"))

        note = PLAYER_NOTES.get(folder, "")
        catalog[folder] = {
            "folder": folder,
            "pid": pid,
            "name": full_name,
            "gender": gender,
            "sdo": sdo_name,
            "base_sega_sdo": base_sdo,
            "face_slot": face_slot,
            "base_uv_file": base_uv_out_name,
            "ref_retrato_file": ref_retrato_name,
            "ref_extra_file": ref_extra_name,
            "deliver_as": f"{folder}.png",
            "notes": note,
        }
        audit_rows.append((folder, full_name, base_sdo.replace(".sdo", ""), cur_uv_rgb, ref_retrato_im))
        print(f"  [OK] {folder:9s} ({full_name:24s}) base={base_sdo:14s} cut={'OK' if ref_retrato_name else 'NO'}")

    cat_path = os.path.join(DIR_INPUTS, "CATALOGO_57_CARAS_UV.json")
    with open(cat_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)

    # 3. Visual contact sheet of all 57 current UV faces vs target new portraits
    cols = 4
    rows = (len(audit_rows) + cols - 1) // cols
    cell_w, cell_h = 460, 238
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), (22, 24, 30))
    draw = ImageDraw.Draw(sheet)
    f_hdr = load_font(15)
    f_sub = load_font(13)

    for idx, (folder, name, base_stem, cur_uv, ref_im) in enumerate(audit_rows):
        r, c = divmod(idx, cols)
        x0, y0 = c * cell_w + 8, r * cell_h + 6
        draw.rectangle([x0 - 2, y0 - 2, x0 + cell_w - 14, y0 + cell_h - 10], outline=(55, 62, 76), width=1)
        draw.text((x0 + 4, y0 + 2), f"{folder} — {name}", fill=(240, 244, 255), font=f_hdr)
        draw.text((x0 + 4, y0 + 21), f"Base: {base_stem}  |  Entrega: {folder}.png", fill=(155, 195, 255), font=f_sub)
        sheet.paste(cur_uv.resize((190, 190), Image.Resampling.BILINEAR), (x0 + 4, y0 + 40))
        if ref_im is not None:
            sheet.paste(ref_im.resize((190, 190), Image.Resampling.BILINEAR), (x0 + 202, y0 + 40))

    audit_path = os.path.join(DIR_CURRENT, "AUDITORIA_57_UVS_ACTUALES.png")
    sheet.save(audit_path)
    print(f"Wrote audit sheet: {audit_path} ({sheet.size})")

    # 4. Write Spanish README_INSTRUCCIONES_PHOTOCRAFT_UV.md
    lines = [
        "# 🎾 Virtua Tennis 4 — Taller de Caras UV 3D (PhotoCraft + IA)",
        "",
        "Esta carpeta contiene **todo preparado** para editar los mapas UV faciales (`1024x1024`) de los **57 tenistas personalizados** (`26_ALC`..`81_CLI`, incluyendo `29_91_AGA` Agassi '91 y `29_AG2` Agassi '06) reutilizando los bustos limpios que ya entregaste.",
        "",
        "---",
        "",
        "## 📁 Estructura de esta carpeta",
        "",
        "1. [`00_referencias_oficiales_sega/`](./00_referencias_oficiales_sega/)",
        "   - 6 caras UV oficiales de SEGA en **RGB puro** (`P_M_FED_SN`, `P_M_NAD_IT`, `P_M_DJV_IT`, `P_W_SHA_SN`, `P_W_IVA_IT`, `P_W_WIL_SN`).",
        "   - **`GUIA_ZONAS_UV_MASCULINO.png`** y **`GUIA_ZONAS_UV_FEMENINO.png`**: diagramas con las zonas exactas (cuero cabelludo, cejas, **párpados cerrados**, nariz, orejas, labios neutros y cuello).",
        "2. [`01_base_uv_y_referencias/`](./01_base_uv_y_referencias/)",
        "   - Para cada uno de los **57 tenistas**, tienes en esta única carpeta:",
        "     - `<CARPETA>_base_uv.png`: Mapa UV facial base `1024x1024` en **RGB puro sin alfa** *(ver nota técnica abajo)*.",
        "     - `<CARPETA>_ref_retrato.png`: Su retrato nuevo aprobado (`03_entregar_editados_aqui/cutouts/`) sobre fondo neutro.",
        "     - `<CARPETA>_ref_extra.jpg`: Segunda foto de referencia de su época en activo.",
        "   - [`CATALOGO_57_CARAS_UV.json`](./01_base_uv_y_referencias/CATALOGO_57_CARAS_UV.json): metadatos, modelo `.sdo`, base SEGA y notas específicas por tenista.",
        "3. [`02_estado_actual_en_juego/`](./02_estado_actual_en_juego/)",
        "   - Los `<CARPETA>_actual.png` (`1024x1024` RGB) que usa actualmente el juego dentro de cada `.sdo` + la hoja [`AUDITORIA_57_UVS_ACTUALES.png`](./02_estado_actual_en_juego/AUDITORIA_57_UVS_ACTUALES.png).",
        "4. [`03_entregar_editados_aqui/`](./03_entregar_editados_aqui/)",
        "   - **Deja aquí cada PNG terminado (`1024x1024` o cuadrado 2K RGB)** nombrado exactamente **`<CARPETA>.png`** (ej. `26_ALC.png`, `29_91_AGA.png`, `29_AG2.png`, `30_BOR.png`, `51_LEN.png`... `81_CLI.png`).",
        "",
        "---",
        "",
        "## 🧠 Por qué los archivos están en RGB puro (sin transparencia)",
        "",
        "- SEGA guarda en los DDS `*_B_face_*.dds` (DXT5) la **oclusión ambiental / cavidades** dentro del canal Alpha (párpados internos, comisuras labiales y fosas nasales tienen alfa bajo). Si se abren tal cual en un editor o generador IA, esos píxeles aparecen como **agujeros blancos o damero**.",
        "- Por eso te entregamos todas las bases en **RGB opaco puro** (`00_` y `01_`).",
        "- Cuando entregues tus PNGs en [`03_entregar_editados_aqui/`](./03_entregar_editados_aqui/), el importador automáticamente:",
        "  1. Reescalará a `1024x1024` (Lanczos) si exportaste en 2K.",
        "  2. **Restaurará intacto el canal Alpha de cavidades original de SEGA** antes de recomprimir a DXT5 con todos sus mipmaps.",
        "  3. **Sincronizará automáticamente el tono de piel del cuerpo (`*_B_body_*.dds`: cuello, brazos y piernas)** para que no haya cortes de color entre cara y cuerpo.",
        "",
        "---",
        "",
        "## 🎯 Las 5 Reglas de Oro para editar la UV facial (Prompt IA + PhotoCraft)",
        "",
        "Sube juntas `<CARPETA>_base_uv.png` (imagen 1 = plantilla UV) y `<CARPETA>_ref_retrato.png` (imagen 2 = identidad facial; opcionalmente también `_ref_extra`) **sin mencionar nombres propios de famosos ni marcas registradas** para evitar bloqueos de filtro:",
        "",
        "1. **Alineación UV 100 % idéntica**: Mantén exactamente en la misma coordenada UV de `<CARPETA>_base_uv.png` la posición de cejas, cuencas oculares, puente/aletas nasales, labios, orejas, línea del pelo y borde inferior del cuello.",
        "2. **PÁRPADOS CERRADOS/NEUTROS — NUNCA PINTAR PUPILAS NI IRIS**: *Virtua Tennis 4* renderiza globos oculares 3D independientes detrás de los párpados. Conserva exactamente la forma neutra de los ojos cerrados/hueco ocular de la base UV (solo adapta pestañas, pliegue y tono alrededor).",
        "3. **Iluminación Albedo plana y uniforme**: Textura mate de videojuego sin sombras duras direccionales, sin brillos de flash ni viñetas.",
        "4. **Identidad facial y vello fieles a la referencia**: Adapta forma de cejas, nariz, pómulos, mandíbula, labios y vello facial para que coincida con `<CARPETA>_ref_retrato.png`. Si la base SEGA hereda barba (ej. `P_M_RAF_IT` o `P_M_DEL_SN`) y el tenista va afeitado en su época activa, **elimínala limpiamente**. Si es `29_AG2` (Agassi '06), mantén el cuero cabelludo **100 % calvo arriba y a los lados** más su perilla.",
        "5. **Labios cerrados / expresión neutra** y tono del borde inferior del cuello fiel al retrato.",
        "",
        "### Plantilla de prompt lista para copiar:",
        "> Edit texture image 1 (a 1024x1024 game character face UV texture map) so the facial identity, eyebrows, nose, cheekbones, lips, skin tone, hairline, and facial hair match the tennis player shown in reference image 2.",
        "> CRITICAL TECHNICAL RULES:",
        "> 1. Preserve 100% of the exact unwrapped UV layout, pixel positions, head silhouette, ear positions, neck border, and outer hair/scalp regions from image 1 — DO NOT crop, zoom, rotate, or turn it into a normal portrait.",
        "> 2. Keep the eyelids CLOSED / hollow in the exact same pixels as image 1 — NEVER draw open eyeballs, irises, sclera, or pupils (the 3D engine renders separate eyeball meshes inside the sockets).",
        "> 3. Remove or adjust any beard/stubble inherited from image 1 so it matches image 2 cleanly; keep lips closed and neutral.",
        "> 4. Use completely flat, even, shadowless diffuse albedo lighting suitable for a 3D game texture. Output 1024x1024 square PNG.",
        "",
        "---",
        "",
        "## 📋 Tabla de los 57 Tenistas, Base SEGA y Notas",
        "",
        "| Archivo a entregar | ID | Tenista | `.sdo` destino | Base SEGA | Notas de edición UV |",
        "|---|---|---|---|---|---|",
    ]
    for folder in sorted_folders:
        c = catalog[folder]
        lines.append(
            f"| `{c['deliver_as']}` | `{c['pid']}` | {c['name']} | `{c['sdo']}` | `{c['base_sega_sdo'].replace('.sdo','')}` | {c['notes']} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 🔄 Reimportar todas las caras UV al juego en 1 comando",
        "",
        "Cuando hayas dejado los PNGs (`26_ALC.png`, etc.) en [`03_entregar_editados_aqui/`](./03_entregar_editados_aqui/), vuelve aquí o ejecuta:",
        "",
        "```powershell",
        "python -u tools/import_edited_face_uvs.py",
        "```",
        "",
        "Opciones útiles:",
        "- `--player 30_BOR` para empaquetar y probar un solo jugador.",
        "- `--no-sync-body` si prefieres mantener intacto el tono original de `*_B_body_*.dds`.",
        "- `--dry-run` para validar nombres y dimensiones antes de modificar ningún `.sdo`.",
        "",
    ])

    readme_path = os.path.join(WS_OUT, "README_INSTRUCCIONES_PHOTOCRAFT_UV.md")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote {readme_path} ({len(sorted_folders)} players ready).")


if __name__ == "__main__":
    main()
