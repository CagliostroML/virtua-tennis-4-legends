#!/usr/bin/env python3
"""
Create descriptive drop-in sample workspaces for future assets:
  1. assets/skins_alt_workspace/ (14 signature [F] alternate skins incl. Sinner Roma Negro & Alcaraz US Open 2026)
  2. assets/voices_workspace/     (ensure 82_AND & 83_BJK + drop-in MUESTRA_QUE_PONER_AQUI.txt notes)
  3. assets/bw_portraits_pending/ (6 B&W portrait candidates + clean paths for Nano Banana colorization)
"""
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)

SKINS_WS = os.path.join(REPO_ROOT, "assets", "skins_alt_workspace")
VOICES_WS = os.path.join(REPO_ROOT, "assets", "voices_workspace")
BW_WS = os.path.join(REPO_ROOT, "assets", "bw_portraits_pending")

SIGNATURE_SKINS = [
    {
        "folder": "26_ALC_USOpen2026",
        "id": 26,
        "player": "Carlos Alcaraz",
        "skin_name": "US Open 2026 Nike Knicks",
        "alt_model": "P_M_AL2_NG.sdo",
        "base_model": "P_M_ALC_NG.sdo",
        "alt_photo_L": "26_alt.dds",
        "palette": "Camiseta sin mangas morado azulado/azul royal (#3B3898), ribetes naranja Knicks (#F56218) y negro, pantalon negro (#16161A), munequeras y cinta a juego",
        "notes": "Requiere UV de uniforme sin mangas + textura corporal de brazos sin manga.",
    },
    {
        "folder": "27_SIN_RomaNegro",
        "id": 27,
        "player": "Jannik Sinner",
        "skin_name": "Roma / Internazionali d'Italia (Negro Entero)",
        "alt_model": "P_M_SI2_NG.sdo",
        "base_model": "P_M_SIN_NG.sdo",
        "alt_photo_L": "27_alt.dds",
        "palette": "Conjunto negro entero (#121215): polo/camiseta Nike negro mate, pantalon negro, calcetines y zapatillas negras con swoosh discreto blanco",
        "notes": "Uniforme iconico de Sinner en el Foro Italico de Roma.",
    },
    {
        "folder": "00_FED_Wimbledon2007",
        "id": 0,
        "player": "Roger Federer",
        "skin_name": "Wimbledon 2007 Blanco y Dorado",
        "alt_model": "P_M_FE2_LG.sdo",
        "base_model": "P_M_FED_SN.sdo (archivo base)",
        "alt_photo_L": "00_alt.dds",
        "palette": "Polo blanco puro (#F8F8FA), detalles dorados (#D4AF37), cinta blanca y pantalon blanco clasico All England",
        "notes": "Skin homenaje a los 5 Wimbledon consecutivos.",
    },
    {
        "folder": "01_NAD_RG2008",
        "id": 1,
        "player": "Rafael Nadal",
        "skin_name": "Roland-Garros 2008 Sin Mangas + Piratas",
        "alt_model": "P_M_NA2_LG.sdo",
        "base_model": "P_M_NAD_IT.sdo (archivo base)",
        "alt_photo_L": "01_alt.dds",
        "palette": "Camiseta Nike sin mangas verde lima (#7ED321), pantalon pirata blanco (#F5F5F5), bandana blanca y munequeras negras/lima",
        "notes": "Opcionalmente usa geometria de piratas largos si se edita el .sdo base.",
    },
    {
        "folder": "02_DJV_AO2019",
        "id": 2,
        "player": "Novak Djokovic",
        "skin_name": "Australian Open 2019 Lacoste",
        "alt_model": "P_M_DJ2_NG.sdo",
        "base_model": "P_M_DJV_IT.sdo (archivo base)",
        "alt_photo_L": "02_alt.dds",
        "palette": "Polo azul cobalto/marino Lacoste (#143878) con banda diagonal blanca/azul cielo y pantalon blanco",
        "notes": "Look clasico de sus finales en Melbourne.",
    },
    {
        "folder": "28_SAM_USOpen95",
        "id": 28,
        "player": "Pete Sampras",
        "skin_name": "US Open 1995 Nike Clasico",
        "alt_model": "P_M_SA2_LG.sdo",
        "base_model": "P_M_SAM_LG.sdo",
        "alt_photo_L": "28_alt.dds",
        "palette": "Polo amplio blanco (#F6F7FA) con cuello gris oscuro y pantalon Nike clasico holgado",
        "notes": "Estetica noventera clasica de Flushing Meadows.",
    },
    {
        "folder": "30_BOR_Wimbledon80",
        "id": 30,
        "player": "Bjorn Borg",
        "skin_name": "Wimbledon 1980 Fila Rayas",
        "alt_model": "P_M_BO2_LG.sdo",
        "base_model": "P_M_BOR_LG.sdo",
        "alt_photo_L": "30_alt.dds",
        "palette": "Polo Fila blanco/marfil (#FAF8F2) con finas rayas azul marino (#1A3058) y rojo (#C82834), cinta Fila a juego",
        "notes": "La final historica contra McEnroe.",
    },
    {
        "folder": "31_MCE_Wimbledon81",
        "id": 31,
        "player": "John McEnroe",
        "skin_name": "Wimbledon 1981 Sergio Tacchini",
        "alt_model": "P_M_MC2_LG.sdo",
        "base_model": "P_M_MCE_LG.sdo",
        "alt_photo_L": "31_alt.dds",
        "palette": "Polo Sergio Tacchini blanco con franja horizontal doble rojo/azul marino en pecho + pantalon corto blanco y cinta roja",
        "notes": "Icono visual de los 80.",
    },
    {
        "folder": "32_GRA_Steffi95",
        "id": 32,
        "player": "Steffi Graf",
        "skin_name": "Adidas 1995 Blanco / Azul-Verde",
        "alt_model": "P_W_GR2_LG.sdo",
        "base_model": "P_W_GRA_LG.sdo",
        "alt_photo_L": "32_alt.dds",
        "palette": "Camiseta y falda Adidas blanco clasico con 3 bandas azul turquesa/verde esmeralda",
        "notes": "Look noventero de Slam.",
    },
    {
        "folder": "33_SER_USOpen2018",
        "id": 33,
        "player": "Serena Williams",
        "skin_name": "US Open 2018 Tutu Negro",
        "alt_model": "P_W_SE2_LG.sdo",
        "base_model": "P_W_SER_NG.sdo",
        "alt_photo_L": "33_alt.dds",
        "palette": "Vestido negro integral (#151518) con medias de compresion negras y detalle plateado Off-White",
        "notes": "Uno de sus conjuntos mas reconocibles en Nueva York.",
    },
    {
        "folder": "34_SWI_RG2024",
        "id": 34,
        "player": "Iga Swiatek",
        "skin_name": "Roland-Garros 2024 On Running",
        "alt_model": "P_W_SW2_NG.sdo",
        "base_model": "P_W_SWI_NG.sdo",
        "alt_photo_L": "34_alt.dds",
        "palette": "Degradado blanco a rosa/tierra batida (#F49AC2 -> #E05860) con falda negra y gorra blanca",
        "notes": "Su uniforme del cuarto titulo en Paris.",
    },
    {
        "folder": "35_SAB_USOpen2024",
        "id": 35,
        "player": "Aryna Sabalenka",
        "skin_name": "US Open 2024 Fucsia Electrico",
        "alt_model": "P_W_SA2_NG.sdo",
        "base_model": "P_W_SAB_NG.sdo",
        "alt_photo_L": "35_alt.dds",
        "palette": "Vestido Nike fucsia/magenta electrico (#D81868) con espalda deportiva abierta y zapatillas a juego",
        "notes": "Conjunto campeona del US Open 2024.",
    },
    {
        "folder": "43_KYR_Wimbledon22",
        "id": 43,
        "player": "Nick Kyrgios",
        "skin_name": "Wimbledon 2022 Blanco + Rojo",
        "alt_model": "P_M_KY2_NG.sdo",
        "base_model": "P_M_KYR_NG.sdo",
        "alt_photo_L": "43_alt.dds",
        "palette": "Camiseta y pantalon blanco estricto Wimbledon (#F7F8FA) con gorra roja hacia atras y zapatillas Nike rojas (#D82028)",
        "notes": "Iconico de su final de Wimbledon 2022.",
    },
    {
        "folder": "82_AND_Tour2026",
        "id": 82,
        "player": "Mirra Andreeva",
        "skin_name": "Tour 2026 Azul Celeste / Blanco",
        "alt_model": "P_W_AN2_NG.sdo",
        "base_model": "P_W_AND_NG.sdo",
        "alt_photo_L": "82_alt.dds",
        "palette": "Vestido Nike azul celeste (#4CA8E8) con paneles laterales blancos y zapatillas blancas/celestes",
        "notes": "Skin Next-Gen para su temporada 2026.",
    },
]

BW_PENDING = [
    ("51", "LEN", "Ivan Lendl", "assets/face_uv_photocraft_workspace/01_base_uv_y_referencias/51_LEN_ref_retrato.png", "Normal"),
    ("52", "CON", "Jimmy Connors", "assets/face_uv_photocraft_workspace/01_base_uv_y_referencias/52_CON_ref_retrato.png", "Normal"),
    ("55", "EVE", "Chris Evert", "assets/face_uv_photocraft_workspace/01_base_uv_y_referencias/55_EVE_ref_retrato.png", "Normal"),
    ("74", "MUS", "Thomas Muster", "assets/face_uv_photocraft_workspace/01_base_uv_y_referencias/74_MUS_ref_retrato.png", "IMPORTANTE: guardar/exportar primero como PNG RGB limpio antes de pasar a Nano Banana (el JPG anterior devolvio HTTP 400 INVALID_ARGUMENT)."),
    ("75", "BRU", "Sergi Bruguera", "assets/face_uv_photocraft_workspace/01_base_uv_y_referencias/75_BRU_ref_retrato.png", "Normal"),
    ("77", "WLD", "Mats Wilander", "assets/face_uv_photocraft_workspace/01_base_uv_y_referencias/77_WLD_ref_retrato.png", "Normal"),
]


def write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def create_skins_workspace() -> None:
    os.makedirs(SKINS_WS, exist_ok=True)
    rows = []
    for s in SIGNATURE_SKINS:
        rows.append(f"| `{s['folder']}` | `{s['id']}` | **{s['player']}** | {s['skin_name']} | `{s['alt_model']}` |")
    readme = f"""# 🎨 Taller de Skins Características Alt (`[F]` en Selección de Personaje)

Esta carpeta deja listas **14 carpetas de muestra descriptivas** con exactamente los archivos necesarios para construir uniformes alternativos conmutables con **`[F]`** (igual que `Agassi '91 / '06`).

> Por tamaño/copyright de binarios SEGA no se sube a GitHub: guarda aquí tus referencias y PNGs editados cuando quieras empujar el paquete `[F]`.

## 📋 Las 14 Skins Planificadas

| Carpeta | ID | Tenista | Skin Propuesta | `.sdo` Destino |
|---|---|---|---|---|
{chr(10).join(rows)}

## 📦 Archivos necesarios dentro de CADA carpeta

| Archivo a aportar | Formato | Para qué sirve |
|---|---|---|
| `ref_kit_front.png` | PNG RGB/RGBA `>= 1024 px` | Referencia real del uniforme (para Nano Banana / PhotoCraft) |
| `body_diffuse_1024.png` | PNG RGBA **`1024x1024`** | Textura UV final de camiseta/pantalón/vestido que se inyecta en `{ '`<alt_model>`' }` |
| `body_spec_mask.png` *(opcional)* | PNG Escala grises `1024x1024` | Brillo/tela en canal Alpha (`DXT5`); si falta se reutiliza el original |
| `shoes_bands_512.png` *(opcional)* | PNG RGBA **`512x512`** | Zapatillas, muñequeras, cinta/gorra del kit alternativo |
| `photo_L_alt.png` | PNG RGBA **`256x256`** | Retrato 2D del uniforme alternativo -> `game/archive/HIGH/Frontend/VR/photo_L/<ID>_alt.dds` |
| `photo_S_alt.png` | PNG RGBA **`128x128`** | Miniatura inferior de CharaSelect (`photo_S/<ID>_alt.dds`) |
| `photo_eye_alt.png` | PNG RGBA **`256x64`** | Tira horizontal del grid (`photo_eye/<ID>_alt.dds`) |
"""
    write_text(os.path.join(SKINS_WS, "README_SKINS_ALT.md"), readme)

    for s in SIGNATURE_SKINS:
        sdir = os.path.join(SKINS_WS, s["folder"])
        os.makedirs(sdir, exist_ok=True)
        write_text(os.path.join(sdir, "kit_spec.json"), json.dumps(s, indent=2, ensure_ascii=False) + "\n")
        guide = f"""SKIN ALTERNATIVA [F]: {s['player']} — {s['skin_name']} (ID {s['id']})
=======================================================================
Modelo base a clonar: {s['base_model']}
Modelo destino [F]:   game/archive/HIGH/Player/Model/{s['alt_model']}
Retrato destino [F]:  game/archive/HIGH/Frontend/VR/photo_L/{s['alt_photo_L']}

PALETA / DISENO OBJETIVO:
  {s['palette']}

NOTAS TECNICAS:
  {s['notes']}

ARCHIVOS A COLOCAR EN ESTA CARPETA (reemplaza los .txt de muestra):
  1. ref_kit_front.png     -> Foto o lamina de referencia del kit real
  2. body_diffuse_1024.png -> Textura UV 1024x1024 RGBA (DTX5/DXT1 en el .sdo)
  3. body_spec_mask.png    -> (Opcional) Canal especular 1024x1024
  4. shoes_bands_512.png   -> (Opcional) Zapatillas y munequeras 512x512 RGBA
  5. photo_L_alt.png       -> Retrato 256x256 RGBA con fondo superior transparente
  6. photo_S_alt.png       -> Miniatura 128x128 RGBA
  7. photo_eye_alt.png     -> Tira de ojos 256x64 RGBA para la rejilla
"""
        write_text(os.path.join(sdir, "LEEME_ARCHIVOS_NECESARIOS.txt"), guide)
        write_text(
            os.path.join(sdir, "PON_AQUI_ref_kit_front.png.txt"),
            f"Deposita aqui 'ref_kit_front.png' (foto real frente del uniforme de {s['player']} - {s['skin_name']}).\n",
        )
        write_text(
            os.path.join(sdir, "PON_AQUI_body_diffuse_1024.png.txt"),
            f"Deposita aqui 'body_diffuse_1024.png' (1024x1024 RGBA con el UV del uniforme para {s['alt_model']}).\n",
        )
        write_text(
            os.path.join(sdir, "PON_AQUI_photo_L_alt.png.txt"),
            f"Deposita aqui 'photo_L_alt.png' (256x256 RGBA transparente arriba -> {s['alt_photo_L']}).\n",
        )
    print(f"Created 14 descriptive skin sample folders in {SKINS_WS}")


def enhance_voices_workspace() -> None:
    subprocess.run(
        [sys.executable, os.path.join(SCRIPT_DIR, "prepare_voices_workspace.py")],
        check=True,
    )
    sample_notes = {
        "grunt": "PON_AQUI_clips_grunt.txt\nColoca aqui 1..16 audios WAV/MP3 cortos (0.2 - 0.6s) de grunts de golpe normal.\nEjemplo: grunt_01.wav, grunt_02.wav\n",
        "serve": "PON_AQUI_clips_saque.txt\nColoca aqui audios cortos (0.3 - 0.8s) de esfuerzo o grunt al sacar.\nEjemplo: serve_01.wav\n",
        "point_win": "PON_AQUI_clips_punto_ganado.txt\nColoca aqui celebraciones al ganar punto (0.8 - 2.5s): Vamos, Come on, Forza, Idemo.\nEjemplo: win_01.wav\n",
        "point_lose": "PON_AQUI_clips_punto_perdido.txt\nColoca aqui resoplidos o quejas breves tras perder un punto (0.8 - 2.5s).\nEjemplo: lose_01.wav\n",
        "protest": "PON_AQUI_clips_protesta.txt\nColoca aqui protestas al juez de silla / frases miticas (1.0 - 3.5s).\nEjemplo: protest_01.wav\n",
        "match_win": "PON_AQUI_clips_victoria.txt\nColoca aqui celebraciones finales al ganar el partido (1.5 - 3.5s).\nEjemplo: match_win_01.wav\n",
    }
    for folder in os.listdir(VOICES_WS):
        pdir = os.path.join(VOICES_WS, folder)
        if not os.path.isdir(pdir):
            continue
        for sub, note in sample_notes.items():
            sdir = os.path.join(pdir, sub)
            if os.path.isdir(sdir):
                fn, body = note.split("\n", 1)
                write_text(os.path.join(sdir, fn), body)
        for sub in os.listdir(pdir):
            if sub.startswith("vs_") and os.path.isdir(os.path.join(pdir, sub)):
                write_text(
                    os.path.join(pdir, sub, "PON_AQUI_frases_rivalidad.txt"),
                    f"Clips especificos cuando {folder} juega contra {sub[3:]}. Tienen prioridad 65% frente a los genericos.\n",
                )
    print(f"Updated voices workspace with MUESTRA files in {VOICES_WS}")


def create_bw_portraits_workspace() -> None:
    os.makedirs(BW_WS, exist_ok=True)
    items = []
    lines = [
        "# 6 Retratos en Blanco y Negro Pendientes de Coloreado con Nano Banana",
        "",
        "Cuando se restablezca la cuota de `image-generator` (Nano Banana), pasa estos 6 archivos",
        "y reempaqueta sus DDS (`photo_L/<ID>.dds`, `photo_eye/<ID>.dds`, `photo_S/<ID>.dds`).",
        "",
    ]
    for pid, code, name, src_rel, note in BW_PENDING:
        src_abs = os.path.join(REPO_ROOT, src_rel.replace("/", os.sep))
        exists = os.path.exists(src_abs)
        items.append({
            "id": int(pid),
            "code": code,
            "player": name,
            "source_path": src_rel,
            "source_exists": exists,
            "target_dds": f"game/archive/HIGH/Frontend/VR/photo_L/{pid}.dds",
            "note": note,
        })
        lines.append(f"- ID {pid} ({code}) {name}")
        lines.append(f"    Origen:  {src_rel} (existe={exists})")
        lines.append(f"    Destino: game/archive/HIGH/Frontend/VR/photo_L/{pid}.dds")
        lines.append(f"    Nota:    {note}")
    write_text(os.path.join(BW_WS, "LEEME_6_RETRATOS_BN.txt"), "\n".join(lines) + "\n")
    write_text(os.path.join(BW_WS, "pending_list.json"), json.dumps(items, indent=2, ensure_ascii=False) + "\n")
    print(f"Created B&W pending portraits workspace in {BW_WS}")


def main() -> None:
    create_skins_workspace()
    enhance_voices_workspace()
    create_bw_portraits_workspace()


if __name__ == "__main__":
    main()
