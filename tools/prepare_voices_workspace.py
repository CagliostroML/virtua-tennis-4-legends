#!/usr/bin/env python3
"""
Prepare the turnkey Per-Player Contextual Voice Packs workspace in:
  assets/voices_workspace/

Creates ready-to-drop event & rivalry subfolders for iconic players and generates
assets/voices_workspace/README_VOCES_Y_FRASES_MITICAS.md.
"""
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS_ROOT = os.path.join(REPO_ROOT, "assets", "voices_workspace")

EVENT_DIRS = ("grunt", "serve", "point_win", "point_lose", "protest", "match_win")

# Iconic voice/quote players with exact VT4 roster IDs (00..83) and rivalry subfolders
ICONIC_PLAYERS = [
    ("39_MED", "Daniil Medvedev", ["vs_41_TSI", "vs_40_ZVE", "vs_01_NAD"],
     "«Small cat!», «Man, you better shut your f*** up!», «Look at me when I talk to you!», «Bullshit Russian»"),
    ("31_MCE", "John McEnroe", ["vs_30_BOR", "vs_52_CON"],
     "«You cannot be serious!», «Chalk flew up!», «Answer my question, jerk!»"),
    ("43_KYR", "Nick Kyrgios", ["vs_41_TSI", "vs_02_DJV"],
     "«Bro, what are you doing?!», «Every single time!», quejas al juez de silla y gritos al público"),
    ("26_ALC", "Carlos Alcaraz", ["vs_27_SIN", "vs_02_DJV"],
     "«¡Vamos!», «¡Sí, sí, sí!», «¡Cabeza, corazón y cojones!», grunts intensos de derecha"),
    ("27_SIN", "Jannik Sinner", ["vs_26_ALC"],
     "«Forza!», «Dai!», celebraciones contenidas y grunts secos de saque/revés"),
    ("35_SAB", "Aryna Sabalenka", ["vs_34_SWI", "vs_82_AND"],
     "Grunts potentes característicos, «Come on!», «Let's go!»"),
    ("82_AND", "Mirra Andreeva", ["vs_35_SAB", "vs_34_SWI"],
     "«C'mon!», celebraciones rápidas y grunts secos Next-Gen WTA"),
    ("83_BJK", "Billie Jean King", [],
     "«Come on!», espíritu competitivo clásico de Wimbledon y US Open"),
    ("65_BAD", "Paula Badosa", [],
     "«¡Vamos!», «¡Venga!», grunts competitivos en peloteo"),
    ("33_SER", "Serena Williams", [],
     "«Come on!», grunts de saque y derecha a máxima potencia"),
    ("29_AGA", "Andre Agassi", ["vs_28_SAM"],
     "«Come on!», resoplidos de resto ganador y celebraciones icónicas de los 90"),
    ("30_BOR", "Bjorn Borg", ["vs_31_MCE"],
     "Silencio estoico, «Come on» muy contenido, celebración de rodillas al ganar partido"),
    ("41_TSI", "Stefanos Tsitsipas", ["vs_39_MED", "vs_43_KYR"],
     "«Pame!», «Let's go!», réplicas clásicas en sus duelos contra Medvedev y Kyrgios"),
    ("45_SAF", "Marat Safin", [],
     "Quejas explosivas, «Come on!», reacciones de raqueta"),
    ("54_IVN", "Goran Ivanisevic", [],
     "Reacciones icónicas de Wimbledon 2001, «Ajde!», diálogo consigo mismo"),
    ("56_SEL", "Monica Seles", [],
     "Su inconfundible grunt de doble tono al golpear a dos manos"),
    ("01_NAD", "Rafael Nadal", ["vs_00_FED", "vs_02_DJV"],
     "«¡Vamos!», «¡Venga!», grunt icónico de drive liftado"),
    ("02_DJV", "Novak Djokovic", ["vs_01_NAD", "vs_26_ALC"],
     "«Idemo!», rugido de celebración tras punto largo, «Come on!»"),
]


def build_readme() -> str:
    rows = []
    for folder, name, rivalries, ideas in ICONIC_PLAYERS:
        riv_txt = ", ".join(f"`{r}/`" for r in rivalries) if rivalries else "*(opcional: crea `vs_<id>_<CODE>/`)*"
        rows.append(f"| `{folder}` | {name} | {riv_txt} | {ideas} |")
    table = "\n".join(rows)

    return f"""# 🎙️ Virtua Tennis 4 — Taller de Voces, Grunts y Frases Míticas por Tenista

Esta carpeta te permite añadir **grunts reales, celebraciones, protestas al juez de silla y frases míticas de rivalidad** para cualquiera de los **84 tenistas del juego** (`00_FED`..`83_BJK`).

El motor en C (`src/xlive/voice_packs.h`) **precarga en RAM** únicamente los clips de los 2 tenistas del partido actual (0 lecturas de disco durante el juego, 0 tirones, compatible con PC y Android/Winlator). Si un tenista o evento no tiene clips propios, **suena automáticamente la voz original de SEGA**.

---

## 📁 Cómo organizar tus audios

Dentro de cada carpeta de tenista (ej. `assets/voices_workspace/39_MED/`), deposita archivos **`.wav`** *(o `.mp3` / `.ogg` / `.flac` / `.m4a` si tienes `ffmpeg` instalado)* en cualquiera de estas subcarpetas:

| Subcarpeta | Evento en partido | Ejemplo de uso |
|---|---|---|
| `grunt/` | Golpe normal en peloteo | Grunt real de derecha / revés |
| `serve/` | Saque | Esfuerzo / grunt al sacar |
| `point_win/` | Punto ganado | *«¡Vamos!»*, *«Come on!»*, *«Idemo!»* |
| `point_lose/` | Punto perdido | Resoplido, frustración corta |
| `protest/` | Protesta / meltdown / frase mítica | *«You cannot be serious!»*, *«Small cat!»* |
| `match_win/` | Victoria del partido | Celebración final |
| `vs_<id>_<CODE>/` | **Rivalidad directa** (prioridad 65 %) | Ej. `39_MED/vs_41_TSI/` cuando Medvedev juega contra Tsitsipas |

> **Tip de duración recomendada**:
> - `grunt/` y `serve/`: **0.2 – 0.7 s** (cortos y limpios).
> - `point_win/`, `point_lose/`, `protest/`, `match_win/` y `vs_*`: **0.8 – 3.5 s**.
> - Puedes meter hasta **16 clips por carpeta**; el motor los rota aleatoriamente sin repetir dos veces seguidas.

---

## 🌟 Carpetas pre-creadas ({len(ICONIC_PLAYERS)} tenistas icónicos)

| Carpeta | Tenista | Rivalidades pre-creadas | Ideas de frases / sonidos icónicos |
|---|---|---|---|
{table}

*(¿Quieres añadir a cualquier otro tenista de los 84 del roster, como `34_SWI`, `32_GRA`, `38_WAW`, `73_RIO`? Solo crea su carpeta `<ID>_<CODE>` con las mismas subcarpetas de evento y ejecuta el importador).*

---

## 🔄 Importar y normalizar al juego en 1 comando

El script `tools/import_voice_packs.py` convierte tus clips a **WAV PCM 16-bit mono 44100 Hz**, recorta silencios al inicio/final y normaliza el volumen RMS a **-14 dBFS** (con limitador anticlipping) antes de copiarlos a `game/archive/voices/`:

```powershell
# 1. Vista previa sin escribir nada (comprueba qué clips detecta):
python -u tools/import_voice_packs.py --dry-run

# 2. Importar y normalizar todos los packs de voz al juego:
python -u tools/import_voice_packs.py

# 3. Importar solo un tenista concreto:
python -u tools/import_voice_packs.py --player 39_MED
```
"""


def main() -> None:
    os.makedirs(WS_ROOT, exist_ok=True)
    created_dirs = 0
    for folder, _name, rivalries, _ideas in ICONIC_PLAYERS:
        pdir = os.path.join(WS_ROOT, folder)
        for sub in list(EVENT_DIRS) + list(rivalries):
            full = os.path.join(pdir, sub)
            os.makedirs(full, exist_ok=True)
            created_dirs += 1

    readme_path = os.path.join(WS_ROOT, "README_VOCES_Y_FRASES_MITICAS.md")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(build_readme())

    print(f"Prepared voices workspace at: {WS_ROOT}")
    print(f"  Players: {len(ICONIC_PLAYERS)} | Subfolders ready: {created_dirs}")
    print(f"  Guide  : {readme_path}")


if __name__ == "__main__":
    main()
