#!/usr/bin/env python3
"""
Prepare a turnkey portrait-editing workspace in:
  assets/portraits_photocraft_workspace/

Creates:
  00_referencias_oficiales_sega/  (Federer, Nadal, Sharapova photo_L/eye/S PNGs)
  01_originales_sin_recortar/     (all 57 raw source images + NB restores cleanly named)
  02_estado_actual_en_juego/      (57 current in-game photo_L & photo_eye PNGs + AUDITORIA_57_ACTUALES.png)
  03_entregar_editados_aqui/      (cutouts/, photo_L/, photo_eye/, photo_S/ drop folders)
  README_INSTRUCCIONES_PHOTOCRAFT.md
"""
import os
import shutil
import struct
import sys
import tempfile
from PIL import Image, ImageDraw

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

from vt4_archive import BIN0, BIN1, load_directory, read_entry, lzss_decompress

WS_DIR = os.path.join(REPO_ROOT, "assets", "portraits_photocraft_workspace")
VR_DIR = os.path.join(REPO_ROOT, "game", "archive", "HIGH", "Frontend", "VR")

PLAYERS = [
    ("26", "ALC", "Carlos_Alcaraz"),
    ("27", "SIN", "Jannik_Sinner"),
    ("28", "SAM", "Pete_Sampras"),
    ("29", "AGA", "Andre_Agassi_2006"),
    ("29_91", "AGA", "Andre_Agassi_1991"),
    ("30", "BOR", "Bjorn_Borg"),
    ("31", "MCE", "John_McEnroe"),
    ("32", "GRA", "Steffi_Graf"),
    ("33", "SER", "Serena_Williams"),
    ("34", "SWI", "Iga_Swiatek"),
    ("35", "SAB", "Aryna_Sabalenka"),
    ("36", "KUE", "Gustavo_Kuerten"),
    ("37", "NAV", "Martina_Navratilova"),
    ("38", "WAW", "Stan_Wawrinka"),
    ("39", "MED", "Daniil_Medvedev"),
    ("40", "ZVE", "Alexander_Zverev"),
    ("41", "TSI", "Stefanos_Tsitsipas"),
    ("42", "THI", "Dominic_Thiem"),
    ("43", "KYR", "Nick_Kyrgios"),
    ("44", "HEW", "Lleyton_Hewitt"),
    ("45", "SAF", "Marat_Safin"),
    ("46", "TSO", "Jo_Wilfried_Tsonga"),
    ("47", "FRR", "Juan_Carlos_Ferrero"),
    ("48", "MOY", "Carlos_Moya"),
    ("49", "FER", "David_Ferrer"),
    ("50", "NAL", "David_Nalbandian"),
    ("51", "LEN", "Ivan_Lendl"),
    ("52", "CON", "Jimmy_Connors"),
    ("53", "VIL", "Guillermo_Vilas"),
    ("54", "IVN", "Goran_Ivanisevic"),
    ("55", "EVE", "Chris_Evert"),
    ("56", "SEL", "Monica_Seles"),
    ("57", "HEN", "Justine_Henin"),
    ("58", "MUG", "Garbine_Muguruza"),
    ("59", "SHE", "Ben_Shelton"),
    ("60", "RUB", "Andrey_Rublev"),
    ("61", "RUU", "Casper_Ruud"),
    ("62", "FRI", "Taylor_Fritz"),
    ("63", "GAU", "Coco_Gauff"),
    ("64", "RYB", "Elena_Rybakina"),
    ("65", "BAD", "Paula_Badosa"),
    ("66", "HAL", "Simona_Halep"),
    ("67", "COR", "Guillermo_Coria"),
    ("68", "GAS", "Richard_Gasquet"),
    ("69", "NIS", "Kei_Nishikori"),
    ("70", "SOD", "Robin_Soderling"),
    ("71", "BER", "Tomas_Berdych"),
    ("72", "CHN", "Michael_Chang"),
    ("73", "RIO", "Marcelo_Rios"),
    ("74", "MUS", "Thomas_Muster"),
    ("75", "BRU", "Sergi_Bruguera"),
    ("76", "CRT", "Alex_Corretja"),
    ("77", "WLD", "Mats_Wilander"),
    ("78", "LAV", "Rod_Laver"),
    ("79", "ASV", "Arantxa_Sanchez_Vicario"),
    ("80", "CMT", "Conchita_Martinez"),
    ("81", "CLI", "Kim_Clijsters"),
]


def _find_orig_file(pid: str) -> list[tuple[str, str]]:
    """Return [(dest_suffix, src_path)] for a given player ID."""
    if pid == "29_91":
        res = []
        p_pose = os.path.join(REPO_ROOT, "assets", "portraits_batch_in", "29_91.jpg")
        p_face = os.path.join(REPO_ROOT, "assets", "face_refs", "29_AG2", "ref_3.jpg")
        if os.path.isfile(p_pose):
            res.append(("_pose_challenge_court", p_pose))
        if os.path.isfile(p_face):
            res.append(("_cara_real_agassi", p_face))
        return res

    num = int(pid)
    res = []
    if 26 <= num <= 37:
        folder = os.path.join(REPO_ROOT, "assets", "portraits_src")
    elif 38 <= num <= 58:
        folder = os.path.join(REPO_ROOT, "assets", "portraits_page3_src")
    else:
        folder = os.path.join(REPO_ROOT, "assets", "portraits_page4_src")

    prefix = f"{pid}_"
    for fn in sorted(os.listdir(folder)):
        if fn.startswith(prefix) and fn.lower().endswith((".jpg", ".jpeg", ".png")):
            full = os.path.join(folder, fn)
            if "_nb." in fn.lower():
                res.append(("_nano_banana", full))
            elif "_orig." in fn.lower():
                res.append(("", full))
    return res


def export_sega_references(out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    entries = load_directory()
    cache = {}
    sega_refs = [("0", "FED"), ("1", "NAD"), ("17", "SHA")]
    tmp_dir = tempfile.mkdtemp(prefix="vt4_sega_ref_")
    try:
        with open(BIN0, "rb") as f0, open(BIN1, "rb") as f1:
            for sid, code in sega_refs:
                for kind in ("photo_L", "photo_S"):
                    target = f"HIGH/Frontend/VR/{kind}/{sid}.dds"
                    e = next(x for x in entries if x["name"].lower() == target.lower())
                    blob = read_entry(entries, e, f0, f1, cache)
                    raw = blob if blob[:4] == b"DDS " else lzss_decompress(blob)
                    tmp = os.path.join(tmp_dir, f"{sid}_{kind}.dds")
                    with open(tmp, "wb") as tf:
                        tf.write(raw)
                    Image.open(tmp).convert("RGBA").save(os.path.join(out_dir, f"{int(sid):02d}_{code}_{kind}.png"))

                # photo_eye from loose custom_assets generation (SEGA uses FR/VT frontend sheet or generated 256x64)
                eye_dds = os.path.join(VR_DIR, "photo_eye", f"{sid}.dds")
                if os.path.isfile(eye_dds):
                    Image.open(eye_dds).convert("RGBA").save(os.path.join(out_dir, f"{int(sid):02d}_{code}_photo_eye.png"))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def write_readme(path: str) -> None:
    content = """# 🎾 Virtua Tennis 4: Legends & Next-Gen — Taller de Retratos (PhotoCraft + IA)

Esta carpeta contiene **todo listo** para editar con máxima calidad los **57 retratos seleccionables** (`IDs 26..81` + skin alternativo `29_91` de Agassi '91) junto con **la tira horizontal de los ojos ("la carita del selector")**.

---

## 📁 Estructura de esta carpeta

1. [`00_referencias_oficiales_sega/`](./00_referencias_oficiales_sega/)
   - Plantillas reales extraídas de SEGA (`Federer 00`, `Nadal 01`, `Sharapova 17`) en formato `.png` para `photo_L` (`256x256`), `photo_eye` (`256x64`) y `photo_S` (`128x64`).
2. [`01_originales_sin_recortar/`](./01_originales_sin_recortar/)
   - Las fotos originales completas (sin recortar ni comprimir) de los **57** tenistas (`26..81` + `29_91`), nombradas como `<ID>_<CODE>_<Nombre>.jpg`.
   - En los casos donde ya existía versión restaurada previa (`_nano_banana.jpg`), se incluyen ambas.
3. [`02_estado_actual_en_juego/`](./02_estado_actual_en_juego/)
   - Los `photo_L` (`256x256`) y `photo_eye` (`256x64`) que usa ahora mismo el juego, más la hoja visual [`AUDITORIA_57_ACTUALES.png`](./02_estado_actual_en_juego/AUDITORIA_57_ACTUALES.png) para detectar de un vistazo cuáles están mal recortados, en blanco y negro o con mala foto.
4. [`03_entregar_editados_aqui/`](./03_entregar_editados_aqui/)
   - **`cutouts/`** *(RECOMENDADO)*: Deja aquí el busto recortado en `.png` RGBA **con fondo 100 % transparente** a resolución alta (`512x512` o `1024x1024`), nombrado **`<ID>.png`** (ej. `26.png`, `29_91.png`, `51.png`) o `<ID>_<CODE>.png`.
   - **`photo_L/`** *(opcional)*: Si ya exportaste directamente el retrato final a `256x256` RGBA transparente (`<ID>.png`).
   - **`photo_eye/`** *(opcional)*: Si editaste manualmente la carita del selector (`256x64` RGBA opaca, `<ID>.png`). Si no la pones aquí, el importador la genera automáticamente centrada sobre los ojos de tu `cutouts/<ID>.png`.
   - **`photo_S/`** *(opcional)*: Miniatura `128x64` RGBA transparente (si no se entrega, el importador la genera automáticamente desde `photo_L`).

---

## 🎯 Especificaciones exactas para IA + PhotoCraft (qué pedirle a la otra conversación)

### Regla general de identidad y época
- **ÉPOCA EN ACTIVO SIEMPRE**: Cada tenista debe lucir **joven / en su época en activo como tenista profesional** con equipación deportiva icónica de su carrera (NUNCA fotos de veterano retirado con traje ni actores de películas).
- **Evitar bloqueos de filtros**: No envíes nombres propios de famosos ni marcas registradas a modelos de imagen que censuren celebridades; pasa la imagen original como referencia visual pidiendo edición fotorrealista de iluminación/color/recorte sin cambiar la identidad de la persona de la foto.

### 1. Retrato grande de selección — `photo_L` (`256x256` PNG RGBA transparente)
- **Encuadre**: Plano medio/busto (desde el pecho o cintura alta hasta ~8 píxeles por encima de la coronilla/gorra/cinta), con los hombros llegando con naturalidad sin cortes verticales abruptos en mitad del lienzo y la base **apoyada al borde inferior** (`y = 256`).
- **Fondo**: **100 % transparente** (`alpha = 0`), sin viñeta circular ni halos blancos/azules alrededor del pelo. Limpiar por completo los huecos interiores (entre brazos y torso, garganta de la raqueta y entre el cordaje de la raqueta).
- **Estilo**: Iluminación limpia de estudio / foto deportiva nítida, contrastada y a todo color (colorear las fotos antiguas en Blanco y Negro conservando exactamente sus rasgos y uniforme).

### 2. "La carita del selector" — `photo_eye` (`256x64` PNG RGBA opaco)
Es la banda rectangular (`4:1`) que aparece en las **21 casillas de cada página del selector**. Para que quede idéntica al estilo oficial de *Virtua Tennis 4*:
1. **Fondo degradado oscuro de SEGA**: Lienzo opaco de **`256x64`** (`alpha = 255` en toda la tira) con gradiente horizontal lineal de izquierda (`RGB(20, 23, 28)`) a derecha (`RGB(36, 39, 44)`).
2. **Encuadre facial 4:1 centrado en los ojos**: Toma del busto (`photo_L` o del recorte original) un rectángulo horizontal con relación de aspecto `4:1` (por ejemplo, `192x48 px` sobre un `photo_L` de `256x256`), **centrado verticalmente exactamente entre los ojos y el puente de la nariz** (de modo que se vean claramente la frente/cinta/visera arriba, ambos ojos en el centro y la parte superior de la nariz/pómulos abajo, sin cortar los ojos).
3. Reescalar ese recorte `4:1` a `256x64` con Lanczos y pegarlo sobre el fondo oscuro usando su máscara alfa transparente (como en `00_referencias_oficiales_sega/00_FED_photo_eye.png`).

### 3. Miniatura — `photo_S` (`128x64` PNG RGBA transparente)
- Recortar la mitad superior de `photo_L` (`0, 0, 256, 152`), reescalar a `104x64` (Lanczos) y pegarla centrada (`x=12, y=0`) sobre un lienzo transparente de `128x64`.

---

## 📋 Prioridades por tenista (de más urgente a ya terminado)

### 🔴 Grupo 1 — Prioridad Máxima (Rehacer / Colorear B&W)
- `26_ALC` (**Carlos Alcaraz**): Retrato actual provisional con cortes raros en torso/cuello; rehacer limpio desde `26_ALC_Carlos_Alcaraz.jpg`.
- `29_91_AGA` (**Andre Agassi 1991**): Combinar la cara **real** de Andre Agassi (`29_91_AGA_Andre_Agassi_1991_cara_real_agassi.jpg` / `29_AGA`) con su look icónico de 1991 (melena rubia larga + cinta rosa + polo Challenge Court en `29_91_AGA_Andre_Agassi_1991_pose_challenge_court.jpg`) y cordaje/garganta transparentes.
- **6 Leyendas en Blanco y Negro por colorear a todo color realista**:
  - `51_LEN` (**Ivan Lendl**) — *polo blanco + rombos verdes/azules/rojos de los 80*
  - `52_CON` (**Jimmy Connors**) — *polo retro blanco con ribetes rojo/azul marino*
  - `55_EVE` (**Chris Evert**) — *falda/polo blanco clásico años 70-80*
  - `74_MUS` (**Thomas Muster**) — *equipación colorida principios de los 90*
  - `75_BRU` (**Sergi Bruguera**) — *camiseta años 90 Roland Garros*
  - `77_WLD` (**Mats Wilander**) — *polo blanco/verde/azul clásico años 80*

### 🟠 Grupo 2 — Buscar o regenerar foto joven de mayor calidad (fuente débil)
- `46_TSO` (Jo-Wilfried Tsonga, resolución baja)
- `67_COR` (Guillermo Coria)
- `72_CHN` (Michael Chang)
- `73_RIO` (Marcelo Ríos)
- `80_CMT` (Conchita Martínez)

### 🟡 Grupo 3 — Recortes de acción mejorables (pulir bordes, sombras, raquetas o reencuadrar mejor)
- `39_MED`, `41_TSI`, `42_THI`, `43_KYR`, `44_HEW`, `45_SAF`, `47_FRR`, `48_MOY`, `49_FER`, `50_NAL`, `53_VIL`, `54_IVN`, `57_HEN`, `58_MUG` y repaso de Página 4 (`59_SHE`..`81_CLI` salvo `74/75/77`).

### 🟢 Grupo 4 — Ya están muy bien (no tocar salvo que quieras homogeneizar estilo)
- `27_SIN`, `28_SAM`, `29_AGA` ('06), `30_BOR`, `31_MCE`, `32_GRA`, `33_SER`, `34_SWI`, `35_SAB`, `36_KUE`, `37_NAV`, `38_WAW`, `40_ZVE`, `56_SEL`.

---

## 🔄 Cómo reimportarlos al juego en 1 comando cuando termines

Cuando hayas colocado los PNG editados dentro de [`03_entregar_editados_aqui/`](./03_entregar_editados_aqui/), vuelve a esta conversación o ejecuta directamente desde la raíz del repositorio:

```powershell
python -u tools/import_edited_portraits.py
```

El script convertirá cada tenista automáticamente a los DDS oficiales del juego (`photo_L`, `photo_eye` y `photo_S` dentro de `game/archive/HIGH/Frontend/VR/`) sin tocar nada del motor y generará una hoja de verificación visual.
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def main() -> None:
    ref_dir = os.path.join(WS_DIR, "00_referencias_oficiales_sega")
    orig_dir = os.path.join(WS_DIR, "01_originales_sin_recortar")
    cur_dir = os.path.join(WS_DIR, "02_estado_actual_en_juego")
    drop_dir = os.path.join(WS_DIR, "03_entregar_editados_aqui")

    for d in (ref_dir, orig_dir, cur_dir, drop_dir):
        os.makedirs(d, exist_ok=True)
    for sub in ("cutouts", "photo_L", "photo_eye", "photo_S"):
        os.makedirs(os.path.join(drop_dir, sub), exist_ok=True)

    # Clear stale generated copies cleanly inside 01_originales and 02_estado_actual
    for d in (orig_dir, cur_dir):
        for fn in os.listdir(d):
            if fn.endswith((".jpg", ".jpeg", ".png")):
                os.remove(os.path.join(d, fn))

    export_sega_references(ref_dir)
    print("Exported SEGA reference PNGs (Federer, Nadal, Sharapova).")

    # Copy all 57 originals & export current in-game PNGs + master audit sheet
    cols, rows = 8, 8
    cw, ch = 260, 326
    sheet = Image.new("RGB", (cols * cw, rows * ch), (24, 26, 34))
    tile = Image.new("RGB", (256, 256))
    tpx = tile.load()
    for y in range(256):
        for x in range(256):
            tpx[x, y] = (58, 62, 72) if ((x // 16) + (y // 16)) % 2 == 0 else (88, 92, 104)
    draw = ImageDraw.Draw(sheet)

    copied_orig = 0
    exported_cur = 0
    missing_orig = []
    for idx, (pid, code, pname) in enumerate(PLAYERS):
        orig_matches = _find_orig_file(pid)
        if not orig_matches:
            missing_orig.append(pid)
        for suf, spath in orig_matches:
            ext = os.path.splitext(spath)[1].lower()
            dst_name = f"{pid}_{code}_{pname}{suf}{ext}"
            shutil.copyfile(spath, os.path.join(orig_dir, dst_name))
            copied_orig += 1

        pl_dds = os.path.join(VR_DIR, "photo_L", f"{pid}.dds")
        pe_dds = os.path.join(VR_DIR, "photo_eye", f"{pid}.dds")
        pl_im = Image.open(pl_dds).convert("RGBA")
        pe_im = Image.open(pe_dds).convert("RGBA")
        pl_im.save(os.path.join(cur_dir, f"{pid}_{code}_photo_L.png"))
        pe_im.save(os.path.join(cur_dir, f"{pid}_{code}_photo_eye.png"))
        exported_cur += 1

        r, c = divmod(idx, cols)
        x0, y0 = c * cw + 2, r * ch + 2
        sheet.paste(tile, (x0, y0))
        sheet.paste(pl_im, (x0, y0), pl_im)
        sheet.paste(pe_im.resize((256, 64), Image.Resampling.LANCZOS), (x0, y0 + 258))
        draw.rectangle([x0, y0, x0 + 132, y0 + 18], fill=(12, 14, 20))
        draw.text((x0 + 4, y0 + 3), f"{pid} {code}", fill=(255, 225, 90))

    audit_path = os.path.join(cur_dir, "AUDITORIA_57_ACTUALES.png")
    sheet.save(audit_path)
    Image.open(audit_path).verify()

    readme_path = os.path.join(WS_DIR, "README_INSTRUCCIONES_PHOTOCRAFT.md")
    write_readme(readme_path)

    print(f"Workspace ready: {WS_DIR}")
    print(f"  Originals copied : {copied_orig} files (missing IDs: {missing_orig})")
    print(f"  Current exported : {exported_cur} players -> {audit_path}")
    print(f"  Guide written    : {readme_path}")


if __name__ == "__main__":
    main()
