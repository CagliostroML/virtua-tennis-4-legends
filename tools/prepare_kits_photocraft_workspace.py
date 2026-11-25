#!/usr/bin/env python3
"""
Build a turnkey 3D Kit / Shoes / Racket / Accessory UV editing workspace in:
  assets/kits_photocraft_workspace/

Mirrors portraits_photocraft_workspace and face_uv_photocraft_workspace for all
57 custom players (26_ALC..81_CLI, including 29_91_AGA and 29_AG2), complete with
a curated real-world reference catalog (era, outfit, shoes, racket, accessories)
and 1-command reimport via:
  python -u tools/import_edited_kits.py
"""
import json
import os
import sys
from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

from vt4_archive import BIN0, BIN1, load_directory, read_entry, lzss_decompress
from update_custom_assets import parse_sdo_dds_slots, extract_slot_image
from prepare_portraits_workspace import PLAYERS

WS_OUT = os.path.join(REPO_ROOT, "assets", "kits_photocraft_workspace")
FACE_WS_SRC = os.path.join(REPO_ROOT, "assets", "face_uv_workspace")
CUTOUTS_DIR = os.path.join(
    REPO_ROOT, "assets", "portraits_photocraft_workspace", "03_entregar_editados_aqui", "cutouts"
)
MODEL_DIR = os.path.join(REPO_ROOT, "game", "archive", "HIGH", "Player", "Model")

DIR_REF_SEGA = os.path.join(WS_OUT, "00_referencias_oficiales_sega")
DIR_INPUTS = os.path.join(WS_OUT, "01_base_uv_y_referencias")
DIR_CURRENT = os.path.join(WS_OUT, "02_estado_actual_en_juego")
DIR_DROP = os.path.join(WS_OUT, "03_entregar_editados_aqui")

KIT_CATS = ("wear", "pants", "shoes", "racket", "accessory")

OFFICIAL_SEGA_REFS = [
    "P_M_FED_SN.sdo",
    "P_M_NAD_IT.sdo",
    "P_M_DJV_IT.sdo",
    "P_W_SHA_SN.sdo",
    "P_W_WOZ_IT.sdo",
    "P_W_ROB_IT.sdo",
]

SKIP_SLOT_KEYS = (
    "_face",
    "_body",
    "_eye",
    "_eyelash",
    "_mou",
    "_teeth",
    "lodgut",
    "_hair_",
    "_hair0",
    "_hairtop",
    "_head_",
)

# Real-world iconic prime-era reference guide for all 57 custom players
KIT_REFERENCES = {
    "26_ALC": ("2024-25 Roland Garros / Tour", "Camiseta sin mangas o polo técnico blanco/menta con franjas horizontales negras (como el retrato)", "Short técnico negro con ribete blanco/menta", "NikeCourt Vapor Pro 2 blancas/negras", "Babolat Pure Aero 98 amarilla/gris carbono", "Muñequeras blancas con Swoosh negro"),
    "27_SIN": ("2024-25 Australian / US Open", "Polo técnico negro minimalista con detalles naranja/dorado o azul/negro (como el retrato)", "Short negro a juego", "NikeCourt Zoom Zero / GP Challenge negras/naranjas", "Head Speed MP negra/blanca (Auxetic)", "Sin gorra (cabello pelirrojo descubierto) + muñequeras negras"),
    "28_SAM": ("1993-95 Wimbledon", "Polo clásico blanco con cuello y rayas verticales verde bosque/turquesa Nike/Tacchini (como el retrato)", "Short blanco clásico plisado", "Nike Air Oscillate blancas con puntera negra", "Wilson Pro Staff 6.0 85 negra con doble línea roja/amarilla", "Muñequera blanca clásica"),
    "29_91_AGA": ("1990-91 Challenge Court", "Polo blanco Nike Challenge Court con salpicaduras y ribetes neón rosa/azul/amarillo", "Short denim azul lavado con licra rosa neón asomando debajo", "Nike Air Tech Challenge II blanco/rosa Hot Lava", "Donnay Pro One amarilla/azul/naranja años 90", "Cinta de pelo rosa fucsia + muñequera negra/rosa"),
    "29_AG2": ("2005-06 US Open Final", "Camiseta técnica blanca o antracita Adidas/Nike con cuello contrastado blanco/negro", "Short negro clásico con franja blanca lateral", "Adidas Barricade / Nike Air Breathe Free blancas/negras", "Head Liquidmetal / Flexpoint Radical naranja/plata", "Muñequera blanca"),
    "30_BOR": ("1978-80 Wimbledon", "Polo retro Fila crema/blanco con rayas verticales azul marino/burdeos (como el retrato)", "Short azul marino o crema ajustado estilo 70s", "Diadora Borg Elite blancas con detalle dorado", "Donnay Allwood Bjorn Borg de madera marrón/crema", "Cinta de pelo Fila rayas rojo/blanco/azul marino + muñequeras"),
    "31_MCE": ("1981-84 Wimbledon / USO", "Polo clásico Sergio Tacchini blanco con franja horizontal en el pecho azul marino y roja (como el retrato)", "Short azul marino o blanco años 80", "Nike Mac Attack / Challenge Court gris/blanco/rojo", "Dunlop Max 200G negra/verde oliva/dorada", "Cinta de pelo roja + muñequeras rojas/blancas"),
    "32_GRA": ("1993-96 Grand Slam", "Camiseta/vestido blanco Adidas clásico con tres bandas azul marino/negro en hombro y falda blanca", "Falda/short plisado blanco", "Adidas Torsion blancas/marino años 90", "Dunlop Max 200G / Wilson Pro Staff 7.0 Lite", "Muñequera blanca"),
    "33_SER": ("2012-15 Grand Slam", "Vestido atlético blanco o negro Nike con escote limpio (como el retrato)", "Culotte negro/blanco integrado", "Nike Flare / Vapor blancas/negras", "Wilson Blade SW104 negra/verde lima", "Cinta negra/blanca + muñequera doble larga"),
    "34_SWI": ("2023-24 Tour (On Running)", "Camiseta técnica azul eléctrico On con degradado rosa/blanco en manga y cuello azul marino (como el retrato)", "Falda/short blanco o azul marino", "On The Roger Pro blancas/azul marino", "Tecnifibre T-Fight 300 blanca con detalles rojo/azul", "Gorra blanca limpia + muñequera blanca"),
    "35_SAB": ("2024-25 Hard Court", "Vestido/top sin mangas rojo coral/carmesí Nike (como el retrato)", "Short/falda roja coral o negro", "NikeCourt Vapor Pro blancas/carmesí", "Wilson Blade v8/v9 verde esmeralda metálico", "Sin gorra; muñequeras negras/carmesí"),
    "36_KUE": ("2000-01 Roland Garros", "Camiseta técnica blanca o azul/amarillo Brasil Diadora con ribete verde/amarillo (como el retrato)", "Short azul real/marino clásico", "Diadora Protech / Rebound blancas/azules/amarillas", "Head Ti.Radical roja/plata con grip amarillo", "Gorra/cinta azul Brasil"),
    "37_NAV": ("1983-87 Wimbledon / USO", "Polo retro blanco Fila/Puma con cuello azul marino/burdeos (como el retrato)", "Falda blanca clásica plisada años 80", "Adidas/Puma piel blanca vintage", "Yonex R-22 o Prince Comp blanca/azul de aro cuadrado/grande", "Muñequera blanca y gafas clásicas opcionales (NO en UV cara)"),
    "38_WAW": ("2015 Roland Garros / Tour", "Polo blanco Yonex limpio con logo en pecho y detalle azul marino/cuadros (como el retrato)", "Short blanco o azul marino Yonex", "Yonex Power Cushion Eclipsion blancas/azules", "Yonex VCORE Duel G / Percept rojo burdeos o verde oscuro", "Muñequera blanca Yonex (como el retrato)"),
    "39_MED": ("2021 US Open Champion", "Polo blanco Lacoste clásico con cuello verde/azul marino (como el retrato)", "Short blanco o azul marino Lacoste", "Lacoste AG-LT21 Ultra blancas/verdes", "Tecnifibre T-Fight blanco mate con acentos azul/rojo", "Sin gorra; muñequeras blancas Lacoste"),
    "40_ZVE": ("2020-24 Tour (Adidas)", "Camiseta técnica negra o azul oscuro Adidas (como el retrato)", "Short negro Adidas", "Adidas Ubersonic 4 negras/blancas", "Head Gravity MP turquesa/rojo coral o negro mate", "Cinta de pelo negra + muñequeras negras"),
    "41_TSI": ("2021-23 Tour (Adidas)", "Camiseta Adidas estampado multicolor arte pop/azul/naranja/negro (como el retrato)", "Short azul marino o negro Adidas", "Adidas Stycon / Barricade negras/multicolor", "Wilson Blade v8 verde cobrizo metálico", "Cinta azul oscuro/gris Adidas + muñequeras blancas"),
    "42_THI": ("2020 US Open Champion", "Polo azul marino Adidas con cuello blanco/naranja y franjas limpias (como el retrato)", "Short azul marino Adidas", "Adidas SoleCourt Boost azul marino/naranja", "Babolat Pure Strike blanca con acentos naranja fluo", "Sin gorra; muñequeras azul marino"),
    "43_KYR": ("2022 Wimbledon / USO", "Camiseta negra Nike/Jordan limpia con detalle neón/gris oscuro (como el retrato)", "Short negro amplio", "NikeCourt Vapor X / Kyrie negras/lima o blancas", "Yonex EZONE 98 azul profundo/negro", "Gorra negra/muñequeras negras"),
    "44_HEW": ("2001-02 No.1 / Wimbledon", "Polo blanco Nike con cuello marino y detalles amarillo oro/marino Australia (como el retrato)", "Short azul marino o blanco Nike", "Nike Air Oscillate / Implosion blancas/amarillas", "Yonex Super RD Tour / RQiS roja/negra", "Gorra blanca hacia atrás + muñequera blanca"),
    "45_SAF": ("2000 US Open / 2005 AO", "Camiseta blanca Adidas clásica holgada con ribetes gris/azul/negro", "Short azul marino o negro Adidas", "Adidas Barricade II blancas/negras", "Head Prestige Classic / Liquidmetal roja rubí", "Muñequera blanca o azul marino"),
    "46_TSO": ("2008 AO / 2011 Tour", "Camiseta blanca Adidas con bandas azul claro/negro en hombro (como el retrato)", "Short blanco o negro Adidas", "Adidas Barricade V blancas/negras", "Babolat AeroPro Drive GT negra/amarilla", "Muñequeras blancas"),
    "47_FRR": ("2003 Roland Garros", "Camiseta blanca Lotto/Joma con ribetes azul claro y marino en hombros (como el retrato)", "Short azul marino o blanco", "Joma/Lotto blancas/azul cielo", "Head Ti.Radical o Prince Graphite Longbody naranja/negro", "Muñequera blanca"),
    "48_MOY": ("1998 Roland Garros", "Camiseta blanca Nike con ribete azul cobalto diagonal en pecho (como el retrato)", "Short azul cobalto/marino Nike", "Nike Air Oscillate / Zoom blancas/azules", "Babolat Pure Drive azul/blanca clásica", "Cinta de pelo blanca Nike (como el retrato)"),
    "49_FER": ("2012-13 Prime (Lotto)", "Camiseta rojo bermellón Lotto con hombros/detalles blancos y negros (como el retrato)", "Short blanco o negro Lotto", "Lotto Raptor Ultra IV blancas/rojas", "Prince EXO3 Tour negra/naranja", "Cinta de pelo blanca Lotto + muñequera verde lima/blanca"),
    "50_NAL": ("2002-05 Masters Cup / Yonex", "Camiseta blanca con mangas azul cielo y rayas diagonales azul marino Yonex/Topper (como el retrato)", "Short azul marino o blanco", "Yonex SHT-304 blancas/azules", "Yonex RDX 500 roja/negra/plata", "Cinta blanca + muñequera blanca"),
    "51_LEN": ("1984-87 US Open / RG", "Polo clásico blanco Adidas con rombos geométricos verde, rojo y azul en hombro/pecho (como el retrato)", "Short blanco Adidas tres bandas", "Adidas Ivan Lendl Comp blancas/burdeos", "Adidas GTX Pro-T negra/blanca cuello clásico", "Muñequera blanca Adidas"),
    "52_CON": ("1974-82 US Open", "Polo retro blanco con cuello y ribetes finos rojo/azul marino", "Short blanco clásico retro", "Converse Jimmy Connors piel blanca", "Wilson T2000 metálica cromada característica (acero/plata)", "Muñequera blanca/azul"),
    "53_VIL": ("1977 US Open / RG", "Polo blanco retro cuello azul marino con logo circular en pecho (como el retrato)", "Short azul marino años 70", "Adidas Vilas piel blanca/azul", "Head Vilas madera laminada marrón/rojo/oro", "Cinta de pelo azul marino/blanca + muñequeras"),
    "54_IVN": ("2001 Wimbledon Champion", "Camiseta negra o ajedrezado azul/rojo Croacia Diadora/Sergio Tacchini (como el retrato)", "Short negro o blanco clásico", "Diadora blancas/negras", "Head Prestige Classic 600 roja rubí", "Cinta de pelo blanca (como el retrato)"),
    "55_EVE": ("1974-84 Grand Slam", "Vestido/polo blanco puro clásico con ribete fino azul marino o crema (como el retrato)", "Falda blanca clásica plisada", "Converse/Adidas piel blanca limpia", "Wilson Chris Evert madera blanca/negra", "Pulsera/muñequera blanca fina"),
    "56_SEL": ("1991-93 Prime Fila", "Polo/camiseta negra o púrpura con cuello blanco clásico años 90 (como el retrato)", "Falda negra o púrpura plisada", "Fila blancas/púrpura años 90", "Yonex RQ-380 púrpura/negra/blanca", "Muñequera negra/púrpura"),
    "57_HEN": ("2003-07 Roland Garros", "Vestido/top sin mangas blanco Adidas con franjas rojo/negro lateral (como el retrato)", "Falda corta blanca/negra", "Adidas Barricade W blancas/rojas", "Wilson nTour Two roja/naranja y blanca", "Gorra blanca Adidas (como el retrato)"),
    "58_MUG": ("2016 RG / 2017 Wimbledon", "Vestido negro Adidas con detalles esmeralda/blanco (como el retrato)", "Short integrado negro", "Adidas Stella McCartney/Ubersonic negras/blancas", "Babolat Pure Drive azul/negra", "Visera negra con ribete blanco (como el retrato)"),
    "59_SHE": ("2023-25 Tour (On Running)", "Camiseta azul eléctrico limpia con pequeño logo blanco en pecho (como el retrato)", "Short negro o azul marino", "On The Roger Pro azul/blanco", "Yonex EZONE 98 azul turquesa/negro", "Muñequera azul/blanca"),
    "60_RUB": ("2022-24 Tour (Rublo)", "Camiseta azul marino oscuro con finas líneas gris/naranja en pecho (como el retrato)", "Short azul marino oscuro", "NikeCourt Vapor Pro blancas/naranjas", "Head Gravity Pro negra/azul-rojo flip", "Cinta de pelo naranja flúor (como el retrato)"),
    "61_RUU": ("2022-24 Roland Garros (Yonex)", "Polo verde bosque jaspeado Yonex con ribete blanco en cuello (como el retrato)", "Short negro o verde oscuro Yonex", "Yonex Eclipsion blancas/verdes", "Yonex EZONE DR/100 negra/azul/lima", "Cinta de pelo blanca + muñequera blanca (como el retrato)"),
    "62_FRI": ("2022-24 Tour (Nike)", "Camiseta turquesa aguamarina Nike con Swoosh blanco/negro (como el retrato)", "Short negro Nike", "NikeCourt Vapor Pro 2 blancas/turquesa", "Head Radical MP naranja flúor/azul marino", "Cinta de pelo blanca Nike (como el retrato)"),
    "63_GAU": ("2023 US Open Champion (NB)", "Top tirantes blanco New Balance con cuello/ribete azul marino y logo NB (como el retrato)", "Falda/short blanco o azul marino", "New Balance Coco CG1 blancas/marino", "Head Boom MP negra/menta turquesa", "Gorra/muñequeras azul marino NB"),
    "64_RYB": ("2022 Wimbledon / Yonex", "Top sin mangas azul cielo Yonex con detalles amarillo/coral en pecho (como el retrato)", "Falda blanca o azul cielo Yonex", "Adidas Barricade / Yonex blancas/azul", "Yonex VCORE 100 roja/negra", "Gorra blanca limpia Yonex (como el retrato)"),
    "65_BAD": ("2021 Indian Wells (Nike)", "Top blanco tirantes limpio Nike con Swoosh negro (como el retrato)", "Falda blanca Nike", "NikeCourt Air Zoom Vapor blancas/negras", "Wilson Blade 98 verde oscuro/plata", "Visera blanca Nike (como el retrato)"),
    "66_HAL": ("2018-19 RG / Wimbledon (Nike)", "Top negro Nike con detalles blanco/rojo/coral en tira (como el retrato)", "Falda negra o blanca", "Nike Vapor X blancas/negras", "Wilson Blade 98 / Burn negra/naranja-verde", "Muñequera negra/blanca"),
    "67_COR": ("2003-04 Roland Garros", "Camiseta blanca Adidas corte clásico 2004 con tres bandas rojas en hombro derecho (como el retrato)", "Short negro o blanco Adidas", "Adidas Barricade III blancas/rojas/negras", "Prince O3 Tour / Experimental Graphite negra/naranja", "Gorra blanca hacia atrás (como el retrato)"),
    "68_GAS": ("2007-15 Tour (Le Coq Sportif)", "Polo azul Francia Le Coq Sportif limpio con cuello tricolor sutil (como el retrato)", "Short blanco o azul marino", "Asics Gel-Resolution blancas/azules", "Head Extreme / Instinct amarilla/negra o azul", "Muñequeras blancas o azules"),
    "69_NIS": ("2014 US Open Final (Uniqlo)", "Polo blanco Uniqlo con bloque hombro/pecho granate/vino (como el retrato)", "Short azul marino Uniqlo", "Adidas Barricade / Nike Air Zoom blancas/rojas", "Wilson Burn 95 negra/naranja", "Cinta de pelo blanca Uniqlo (como el retrato)"),
    "70_SOD": ("2009-10 Roland Garros (Lotto)", "Polo técnico blanco Lotto con líneas negras geométricas y escudo rojo/azul (como el retrato)", "Short negro Lotto", "Lotto Raptor Ultra II blancas/negras", "Head Radical Tour / Prestige naranja/negra", "Muñequeras blancas"),
    "71_BER": ("2010 Wimbledon Final", "Camiseta blanca limpia de tenis (H&M / Nike) con ribetes sutiles azul/verde (como el retrato)", "Short azul marino o blanco", "Nike Vapor blancas/azules", "Head Instinct azul hielo/plata", "Gorra blanca hacia atrás (como el retrato)"),
    "72_CHN": ("1989 Roland Garros (Reebok)", "Polo blanco años 80-90 con estampado geométrico azul marino/gris en hombro (como el retrato)", "Short blanco clásico Reebok", "Reebok Court Victory Pump blancas/negras/amarillas", "Prince Graphite Longbody verde/negra", "Muñequera blanca"),
    "73_RIO": ("1998 No.1 ATP / Nike", "Polo blanco Nike cuello negro clásico con Swoosh pequeño (como el retrato)", "Short negro Nike", "Nike Air Oscillate blancas/negras", "Yonex RD-7 / Ti-70 púrpura/plata", "Muñequera blanca (y gorra atrás opcional)"),
    "74_MUS": ("1995 Roland Garros (Lotto)", "Polo estampado geométrico multicolor turquesa/morado/blanco años 90 (como el retrato)", "Short azul marino/blanco Lotto", "Lotto años 90 blancas/turquesa", "Head Pro Tour 280 azul cobalto/negro", "Muñequeras blancas"),
    "75_BRU": ("1993-94 Roland Garros", "Polo clásico azul marino y blanco Sergio Tacchini años 90 (como el retrato)", "Short blanco clásico", "Diadora/Reebok piel blanca años 90", "Yonex Super RD Tour / Prince azul-negro", "Muñequera blanca"),
    "76_CRT": ("1998-2001 Masters (Asics)", "Polo azul marino con parte inferior a rayas finas verde lima/blancas (como el retrato)", "Short azul marino o blanco Asics", "Asics gel tenis blancas/azules", "Babolat Pure Drive clásica azul", "Muñequera blanca/azul"),
    "77_WLD": ("1982-88 Grand Slam", "Polo clásico blanco cuello verde esmeralda con ribete azul marino (como el retrato)", "Short blanco clásico años 80", "Adidas Stan Smith / Lendl piel blanca/verde", "Rossignol F200 Carbon gris/verde característico", "Muñequera blanca"),
    "78_LAV": ("1962 & 1969 Grand Slam", "Polo vintage blanco cuello y ribetes azul marino años 60 con corona de laurel (como el retrato)", "Short blanco clásico cintura alta años 60", "Dunlop Volley lona blanca suela verde/goma", "Dunlop Maxply Fort madera natural cuello rojo/negro", "Muñequera blanca discreta"),
    "79_ASV": ("1994 RG / USO (Reebok)", "Chaqueta/polo blanco Reebok con cuello negro y ribetes azul marino (como el retrato)", "Falda blanca o negra Reebok", "Reebok piel blanca clásica años 90", "Yonex RD-7 / R-50 roja/blanca", "Cinta de pelo blanca Reebok + muñequera"),
    "80_CMT": ("1994 Wimbledon Champion", "Polo blanco clásico años 90 con cuello azul marino (como el retrato)", "Falda blanca clásica plisada", "Diadora/Reebok piel blanca limpia", "Wilson Pro Staff Classic 6.1 negra/roja", "Cinta de pelo blanca + muñequera blanca (como el retrato)"),
    "81_CLI": ("2005-11 US Open Champion (Fila)", "Top blanco Fila con bloque verde esmeralda y ribetes azul marino en cuello/borde (como el retrato)", "Falda blanca o negra Fila", "Fila Alfa blancas/verde/marino", "Babolat Pure Drive azul/blanca", "Muñequera blanca Fila"),
}


def strip_alpha_rgb(im: Image.Image) -> Image.Image:
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


def classify_kit_slot(dds_name: str) -> tuple[str, str] | None:
    low = dds_name.lower()
    if "_b_" not in low:
        return None
    if any(sk in low for sk in SKIP_SLOT_KEYS):
        return None
    if "wear" in low:
        return ("wear", "wear")
    if "shoes" in low:
        return ("shoes", "shoes")
    if "racket" in low:
        return ("racket", "racket")
    if "bottom" in low:
        return ("pants", "skirt")
    if "pants" in low or "inner" in low:
        return ("pants", "pants")
    if "hairband" in low:
        return ("accessory", "hairband")
    if "headband" in low:
        return ("accessory", "headband")
    if "cap" in low:
        return ("accessory", "cap")
    if "socks" in low:
        return ("accessory", "socks")
    if "ankle" in low:
        return ("accessory", "ankle")
    if "accessory02" in low:
        return ("accessory", "accessory02")
    return ("accessory", "accessory")


def extract_kit_slots(dec: bytes) -> list[dict]:
    found = []
    used_tags = set()
    for s in parse_sdo_dds_slots(dec):
        res = classify_kit_slot(s["name"])
        if res is None:
            continue
        cat, tag = res
        if tag in used_tags:
            idx = 2
            while f"{tag}_{idx}" in used_tags:
                idx += 1
            tag = f"{tag}_{idx}"
        used_tags.add(tag)
        found.append({
            "dds_name": s["name"],
            "w": s["w"],
            "h": s["h"],
            "fourcc": s["fourcc"].decode("ascii", "replace"),
            "category": cat,
            "tag": tag,
            "slot": s,
        })
    return found


def folder_to_pid(folder: str) -> str:
    return "29_91" if folder == "29_91_AGA" else folder.split("_")[0]


def make_thumb(im: Image.Image | None, size: int = 128) -> Image.Image:
    cell = Image.new("RGB", (size, size), (34, 38, 46))
    if im is None:
        return cell
    tmp = im.copy()
    tmp.thumbnail((size - 4, size - 4), Image.Resampling.BILINEAR)
    cell.paste(tmp, ((size - tmp.width) // 2, (size - tmp.height) // 2))
    return cell


def build_sega_overview(sega_samples: list[tuple[str, dict[str, Image.Image]]], out_path: str) -> None:
    cols = 6  # label + wear + pants + shoes + racket + accessory
    cw, ch = 152, 162
    sheet = Image.new("RGB", (cols * cw, len(sega_samples) * ch), (20, 22, 28))
    draw = ImageDraw.Draw(sheet)
    f_hdr = load_font(15)
    f_sub = load_font(12)
    titles = ("MODELO SEGA", "wear", "pants / inner / skirt", "shoes", "racket", "accessory / cap")

    for r_idx, (sdo_name, by_cat) in enumerate(sega_samples):
        y0 = r_idx * ch + 6
        draw.text((10, y0 + 50), sdo_name.replace(".sdo", ""), fill=(240, 245, 255), font=f_hdr)
        for c_idx, cat in enumerate(KIT_CATS, start=1):
            x0 = c_idx * cw + 6
            lbl = titles[c_idx]
            draw.text((x0 + 4, y0), lbl, fill=(140, 195, 255), font=f_sub)
            sheet.paste(make_thumb(by_cat.get(cat), 132), (x0 + 4, y0 + 18))

    sheet.save(out_path)


def main() -> None:
    for sub_root in (DIR_INPUTS, DIR_CURRENT, DIR_DROP):
        os.makedirs(sub_root, exist_ok=True)
        for cat in KIT_CATS:
            os.makedirs(os.path.join(sub_root, cat), exist_ok=True)
    os.makedirs(DIR_REF_SEGA, exist_ok=True)
    DIR_PORTRAITS_REF = os.path.join(DIR_INPUTS, "retratos_referencia")
    os.makedirs(DIR_PORTRAITS_REF, exist_ok=True)

    manifest_path = os.path.join(FACE_WS_SRC, "manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    id_to_name = {pid: name for pid, _code, name in PLAYERS}

    # 1. Extract 6 representative official SEGA base models from resource.bin
    entries = load_directory()
    by_name = {e["name"].lower(): e for e in entries}
    cache = {}
    base_cache: dict[str, tuple[bytes, dict[str, dict]]] = {}

    sega_overview_data = []
    with open(BIN0, "rb") as f0, open(BIN1, "rb") as f1:
        def load_base_sdo(sdo_name: str):
            if sdo_name not in base_cache:
                e = by_name[f"high/player/model/{sdo_name.lower()}"]
                dec = lzss_decompress(read_entry(entries, e, f0, f1, cache))
                kslots = extract_kit_slots(dec)
                base_cache[sdo_name] = (dec, {ks["dds_name"]: ks for ks in kslots}, kslots)
            return base_cache[sdo_name]

        for sdo_name in OFFICIAL_SEGA_REFS:
            dec, _by_dds, kslots = load_base_sdo(sdo_name)
            by_cat_preview = {}
            stem = sdo_name.replace(".sdo", "")
            for ks in kslots:
                rgb = strip_alpha_rgb(extract_slot_image(dec, ks["slot"]))
                rgb.save(os.path.join(DIR_REF_SEGA, f"{stem}_{ks['tag']}.png"))
                if ks["category"] not in by_cat_preview:
                    by_cat_preview[ks["category"]] = rgb
            sega_overview_data.append((sdo_name, by_cat_preview))
            print(f"[REF-SEGA] {sdo_name}: exported {len(kslots)} UV templates")

        build_sega_overview(sega_overview_data, os.path.join(DIR_REF_SEGA, "PLANTILLAS_OFICIALES_SEGA_KITS.png"))

        # 2. Extract all 57 custom players (clean SEGA base kit UVs + current in-game kit UVs + portrait refs)
        catalog = {}
        sorted_folders = sorted(
            manifest.keys(),
            key=lambda k: (29.5 if k == "29_91_AGA" else (29.8 if k == "29_AG2" else float(folder_to_pid(k)))),
        )

        rows_ropas = []
        rows_zapas = []

        for folder in sorted_folders:
            info = manifest[folder]
            pid = folder_to_pid(folder)
            full_name = id_to_name.get(pid, folder)
            sdo_name = info["sdo"]
            base_sdo = info["base_sega_sdo"]
            gender = "M" if sdo_name.startswith("P_M_") else "W"

            # High-res studio gray portrait reference
            cut_src = os.path.join(CUTOUTS_DIR, f"{pid}.png")
            ref_im = None
            ref_rel = None
            if os.path.isfile(cut_src):
                cut = Image.open(cut_src).convert("RGBA")
                bg = Image.new("RGBA", cut.size, (60, 64, 72, 255))
                ref_im = Image.alpha_composite(bg, cut).convert("RGB")
                ref_rel = f"retratos_referencia/{folder}_retrato.png"
                ref_im.save(os.path.join(DIR_INPUTS, ref_rel))

            # Raw SEGA base SDO & Current Custom SDO
            b_dec, b_by_dds, _ = load_base_sdo(base_sdo)
            cur_sdo_path = os.path.join(MODEL_DIR, sdo_name)
            c_dec = lzss_decompress(open(cur_sdo_path, "rb").read())
            c_kslots = extract_kit_slots(c_dec)

            slot_records = []
            cur_by_cat: dict[str, Image.Image] = {}

            for ks in c_kslots:
                cat = ks["category"]
                tag = ks["tag"]
                dds_name = ks["dds_name"]
                out_name = f"{folder}_{tag}.png"

                # Current in-game pure RGB
                cur_rgb = strip_alpha_rgb(extract_slot_image(c_dec, ks["slot"]))
                cur_rgb.save(os.path.join(DIR_CURRENT, cat, out_name))
                if cat not in cur_by_cat:
                    cur_by_cat[cat] = cur_rgb

                # Base clean SEGA pure RGB (falls back to current if slot added specially)
                b_slot = b_by_dds.get(dds_name)
                base_rgb = strip_alpha_rgb(extract_slot_image(b_dec, b_slot["slot"])) if b_slot else cur_rgb
                base_rgb.save(os.path.join(DIR_INPUTS, cat, out_name))

                slot_records.append({
                    "dds_name": dds_name,
                    "w": ks["w"],
                    "h": ks["h"],
                    "fourcc": ks["fourcc"],
                    "category": cat,
                    "tag": tag,
                    "base_file": f"{cat}/{out_name}",
                    "deliver_path": f"{cat}/{out_name}",
                })

            era, w_ref, p_ref, s_ref, r_ref, a_ref = KIT_REFERENCES[folder]
            catalog[folder] = {
                "folder": folder,
                "pid": pid,
                "name": full_name,
                "gender": gender,
                "sdo": sdo_name,
                "base_sega_sdo": base_sdo,
                "ref_retrato": ref_rel,
                "slots": slot_records,
                "references": {
                    "era": era,
                    "wear_ref": w_ref,
                    "pants_ref": p_ref,
                    "shoes_ref": s_ref,
                    "racket_ref": r_ref,
                    "accessory_ref": a_ref,
                },
            }
            rows_ropas.append((folder, full_name, base_sdo.replace(".sdo", ""), ref_im, cur_by_cat))
            rows_zapas.append((folder, full_name, base_sdo.replace(".sdo", ""), ref_im, cur_by_cat))
            print(f"  [OK] {folder:9s} ({full_name:24s}) slots={len(slot_records)} base={base_sdo}")

    with open(os.path.join(DIR_INPUTS, "CATALOGO_57_EQUIPACIONES.json"), "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)

    # 3. Audit sheets
    f_hdr = load_font(15)
    f_sub = load_font(12)

    def render_audit_sheet(rows_data, cats_to_show, headers, out_png, cols_grid=2):
        cell_w = 18 + (len(cats_to_show) + 1) * 134
        cell_h = 182
        rows_grid = (len(rows_data) + cols_grid - 1) // cols_grid
        sheet = Image.new("RGB", (cols_grid * cell_w, rows_grid * cell_h), (20, 22, 28))
        draw = ImageDraw.Draw(sheet)
        for idx, (folder, name, base_stem, ref_im, cur_by_cat) in enumerate(rows_data):
            r, c = divmod(idx, cols_grid)
            x0, y0 = c * cell_w + 8, r * cell_h + 6
            draw.rectangle([x0 - 3, y0 - 2, x0 + cell_w - 14, y0 + cell_h - 10], outline=(52, 58, 72), width=1)
            draw.text((x0 + 4, y0 + 2), f"{folder} - {name} (Base: {base_stem})", fill=(240, 245, 255), font=f_hdr)
            sheet.paste(make_thumb(ref_im, 128), (x0 + 4, y0 + 36))
            draw.text((x0 + 8, y0 + 20), "retrato", fill=(160, 200, 255), font=f_sub)
            for k_idx, (cat_k, col_lbl) in enumerate(zip(cats_to_show, headers), start=1):
                px = x0 + 4 + k_idx * 134
                draw.text((px + 4, y0 + 20), col_lbl, fill=(140, 235, 175), font=f_sub)
                sheet.paste(make_thumb(cur_by_cat.get(cat_k), 128), (px, y0 + 36))
        sheet.save(out_png)
        print(f"Wrote {out_png} ({sheet.size})")

    render_audit_sheet(
        rows_ropas,
        ("wear", "pants", "accessory"),
        ("wear", "pants/skirt", "accessory"),
        os.path.join(DIR_CURRENT, "AUDITORIA_57_ROPAS_ACTUALES.png"),
        cols_grid=2,
    )
    render_audit_sheet(
        rows_zapas,
        ("shoes", "racket"),
        ("shoes", "racket"),
        os.path.join(DIR_CURRENT, "AUDITORIA_57_ZAPATILLAS_Y_RAQUETAS.png"),
        cols_grid=3,
    )

    # 4. Write complete Spanish README + 57-player Real Gear Substitution Reference Table
    md = [
        "# 🎾 Virtua Tennis 4 — Taller de Equipaciones, Zapatillas y Raquetas UV (PhotoCraft + IA)",
        "",
        "Todo listo para personalizar las **ropas (`wear`, `pants`/`skirt`), zapatillas (`shoes`), raquetas (`racket`) y accesorios (`accessory`/`cap`/`hairband`/`headband`/`socks`)** de los **57 tenistas personalizados** (`26_ALC`..`81_CLI`, más `29_91_AGA` y `29_AG2`).",
        "",
        "---",
        "",
        "## 📁 Estructura de esta carpeta",
        "",
        "1. [`00_referencias_oficiales_sega/`](./00_referencias_oficiales_sega/)",
        "   - Plantillas reales extraídas de 6 modelos oficiales (`P_M_FED_SN`, `P_M_NAD_IT`, `P_M_DJV_IT`, `P_W_SHA_SN`, `P_W_WOZ_IT`, `P_W_ROB_IT`) en **RGB opaco puro** + resumen visual [`PLANTILLAS_OFICIALES_SEGA_KITS.png`](./00_referencias_oficiales_sega/PLANTILLAS_OFICIALES_SEGA_KITS.png).",
        "2. [`01_base_uv_y_referencias/`](./01_base_uv_y_referencias/)",
        "   - Subcarpetas ordenadas por pieza: **`wear/`**, **`pants/`**, **`shoes/`**, **`racket/`**, **`accessory/`** y **`retratos_referencia/`**.",
        "   - Cada plantilla `<CARPETA>_<pieza>.png` es el UV original limpio de SEGA en **RGB opaco puro** *(con pliegues, costuras, suelas y cordaje intactos)*, junto a su busto aprobado en `retratos_referencia/<CARPETA>_retrato.png`.",
        "   - [`CATALOGO_57_EQUIPACIONES.json`](./01_base_uv_y_referencias/CATALOGO_57_EQUIPACIONES.json): mapa completo de slots DDS, resoluciones exactas y referencias de marca/color reales.",
        "3. [`02_estado_actual_en_juego/`](./02_estado_actual_en_juego/)",
        "   - Lo que lleva puesto ahora cada `.sdo` en el juego + 2 hojas de auditoría visual:",
        "     - [`AUDITORIA_57_ROPAS_ACTUALES.png`](./02_estado_actual_en_juego/AUDITORIA_57_ROPAS_ACTUALES.png)",
        "     - [`AUDITORIA_57_ZAPATILLAS_Y_RAQUETAS.png`](./02_estado_actual_en_juego/AUDITORIA_57_ZAPATILLAS_Y_RAQUETAS.png)",
        "4. [`03_entregar_editados_aqui/`](./03_entregar_editados_aqui/)",
        "   - Carpetas listas para depositar cada textura editada (**RGB PNG cuadrado o a su proporción exacta**):",
        "     - `wear/<CARPETA>_wear.png` *(o `<CARPETA>.png`)*",
        "     - `pants/<CARPETA>_pants.png` *(o `<CARPETA>_skirt.png` en `80_CMT` / `81_CLI`)*",
        "     - `shoes/<CARPETA>_shoes.png`",
        "     - `racket/<CARPETA>_racket.png`",
        "     - `accessory/<CARPETA>_accessory.png` *(o `_cap`, `_hairband`, `_headband`, `_socks`, `_ankle`, `_accessory02` según tenga ese modelo)*",
        "",
        "---",
        "",
        "## 🧠 Nota técnica: Alfa automático + Preservación UV 100 %",
        "",
        "- Igual que con las caras, los `.dds` originales usan su canal Alpha para **transparencia de bordes, sombreado/AO de tela o huecos en el cordaje/garganta** (`G_racket_B_*`).",
        "- Entrega tus texturas en **RGB opaco puro** dentro de `03_entregar_editados_aqui/`; al ejecutar [`import_edited_kits.py`](../../tools/import_edited_kits.py), el script **reemplaza cada color manteniendo intacta la máscara Alpha original de SEGA**, reescala a la resolución exacta (`512x512`, `512x256`, `256x256`, `256x128`...) con Lanczos, comprime a DXT1/DXT5 con sus mipmaps exactos y reempaqueta el `.sdo`.",
        "",
        "---",
        "",
        "## 🎯 Plantillas de Prompt para IA + PhotoCraft (sin nombres protegidos)",
        "",
        "Pasa **imagen 1 = la plantilla UV** de `01_base_uv_y_referencias/<pieza>/` + **imagen 2 = `<CARPETA>_retrato.png`** (y la descripción de la tabla inferior):",
        "",
        "### A. Ropa (`wear` y `pants` / `skirt`)",
        "> Edit texture image 1 (an unwrapped 3D tennis shirt/dress/shorts UV texture map) so its colors, stripes, collar trim, geometric pattern, and minimalist athletic logo placement match the tennis outfit seen in reference portrait image 2 (plus: **[DESCRIPCIÓN DE EQUIPACIÓN DE LA TABLA]**).",
        "> CRITICAL RULES: Preserve 100% of the exact UV island shapes, seam coordinates, sleeve/collar bounds, and realistic fabric folds from image 1. Flat, even, diffuse albedo lighting (no hard sun shadows). Do NOT resize or shift any UV islands.",
        "",
        "### B. Zapatillas (`shoes`)",
        "> Repaint tennis shoe UV texture image 1 into **[DESCRIPCIÓN ZAPATILLAS DE LA TABLA]** keeping the exact UV islands for sole, midsole, tongue, laces, heel counter, and side panels aligned pixel-for-pixel with image 1. Clean diffuse game albedo.",
        "",
        "### C. Raqueta (`racket`)",
        "> Repaint tennis racket UV texture image 1 into **[DESCRIPCIÓN RAQUETA DE LA TABLA]**, keeping the frame rim strip, throat decals, grip tape, butt cap, and stringbed grid in the exact same UV coordinates as image 1. Clean flat game texture.",
        "",
        "*(Recuerda evitar nombres comerciales o de famosos si el modelo los censura: describe colores exactos, rayas y materiales, o pasa el logotipo sutil / versión estilizada en PhotoCraft).* ",
        "",
        "---",
        "",
        "## 📋 Lista de Referencias Reales para Sustituir los 57 Jugadores",
        "",
        "| Carpeta | Tenista | Época ref. | Camiseta / Vestido (`wear`) | Pantalón / Falda (`pants`) | Zapatillas (`shoes`) | Raqueta (`racket`) | Accesorios (`accessory`) |",
        "|---|---|---|---|---|---|---|---|",
    ]

    for folder in sorted_folders:
        c = catalog[folder]
        r = c["references"]
        slots_str = ", ".join(s["deliver_path"] for s in c["slots"])
        md.append(
            f"| `{folder}` | {c['name']} | {r['era']} | {r['wear_ref']} | {r['pants_ref']} | {r['shoes_ref']} | {r['racket_ref']} | {r['accessory_ref']} *({slots_str})* |"
        )

    md.extend([
        "",
        "---",
        "",
        "## 🔄 Importar al juego en 1 comando cuando termines",
        "",
        "```powershell",
        "# Importa todo lo que hayas dejado en 03_entregar_editados_aqui/:",
        "python -u tools/import_edited_kits.py",
        "",
        "# O por jugador / categoría:",
        "python -u tools/import_edited_kits.py --player 26_ALC",
        "python -u tools/import_edited_kits.py --category racket",
        "```",
        "",
    ])

    readme_path = os.path.join(WS_OUT, "README_INSTRUCCIONES_PHOTOCRAFT_KITS.md")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"Wrote {readme_path} ({len(sorted_folders)} players documented).")


if __name__ == "__main__":
    main()
