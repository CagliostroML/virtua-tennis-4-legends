<div align="center">

# 🎾 Virtua Tennis 4: Legends & Next-Gen Edition

**Ingeniería inversa, motor nativo `xlive.dll` y overhaul visual/jugable de Virtua Tennis 4 (PC)**

![Roster 84 Jugadores](https://img.shields.io/badge/Roster-84%20Tenistas%20(ATP%2FWTA%2FLeyendas)-1e88e5?style=for-the-badge)
![Grand Slams](https://img.shields.io/badge/Estadios-4%20Grand%20Slams%20%2B%20Madrid%20Azul-2e7d32?style=for-the-badge)
![Motor](https://img.shields.io/badge/Motor-D3D9%20%2B%20NextGenFX%20%2B%20GFWL--Free-6a1b9a?style=for-the-badge)
![Netplay & Android](https://img.shields.io/badge/Modos-P2P%20Netplay%20%26%20Android-ef6c00?style=for-the-badge)

</div>

---

## ✨ Novedades Principales

### 🏆 1. Roster Histórico & Next-Gen de **84 Tenistas** (4 Páginas por Épocas)
- **Paginación nativa en `CharaSelect`** (`Q` / `E` o `LB` / `RB`) ampliada de 26 a **84 jugadores jugables (`IDs 0..83`)** sin sustituir ni romper personajes originales:
  - **Página 1/4 — Era Actual & Next-Gen (2015–2026)**: Alcaraz, Sinner, Djokovic, Nadal, Federer, Medvedev, Zverev, Tsitsipas, Rublev, Ruud, Fritz, Shelton, Kyrgios, Świątek, Sabalenka, Gauff, Rybakina, Badosa, Andreeva, Muguruza, Halep.
  - **Página 2/4 — Era Dorada (2000s–2010s)**: Del Potro, Murray, Roddick, Wawrinka, Hewitt, Safin, Ferrer, Ferrero, Moyá, Nalbandian, Coria, Tsonga, Monfils, Gasquet, Haas, González, Nishikori, Söderling, Berdych, Kuerten, Serena Williams.
  - **Página 3/4 — Leyendas 90s & WTA Clásica**: Sampras, Agassi (`[F]` skin doble `'91` / `'06`), Courier, Becker, Edberg, Ivanišević, Rafter, Graf, Seles, Henin, Conchita Martínez, Venus Williams, Wozniacki, Clijsters, Sharapova.
  - **Página 4/4 — Pioneros 60s–80s & Jefes SEGA**: Borg, McEnroe, Lendl, Connors, Vilas, Chang, Ríos, Muster, Bruguera, Corretja, Wilander, Laver, Navratilova, Evert, Billie Jean King, Arantxa Sánchez Vicario + **King, Duke, T. Tenniel y V. Virnie** desbloqueados de serie.
- **Nombres reales en marcador/partido y pantalla de carga** (`hk_StoLookup` + `hk_Loading_SetPlayerPhoto`), **84/84 retratos 2D a todo color** (`photo_L`, `photo_eye`, `photo_S`), **estadísticas individualizadas** (`src/xlive/player_stats.h` para los 58 custom `IDs 26..83`) y `voice_packs.h` ampliado a 84 IDs.

### 🏟️ 2. Los 4 Grand Slams Oficiales + Mutua Madrid Open (Tierra Azul)
- **Australian Open (`Aus1`)**: Pista azul Melbourne + bordes *Melbourne Navy* y patrocinadores modernos (Kia, Rolex, Emirates, Ralph Lauren, Yonex).
- **Roland Garros (`Fra1`)**: Tierra batida parisina enriquecida + fondos verdes de Philippe-Chatrier (BNP Paribas, Rolex, Renault, Lacoste, Emirates, Babolat).
- **Wimbledon (`Eng1`)**: Hierba esmeralda del All England Club con desgaste natural + lonas verde/púrpura oficiales (Rolex, IBM, Slazenger, Ralph Lauren, Barclays, evian).
- **US Open (`Usa1`)**: Pista azul Arthur Ashe Stadium + bordes verdes US Open y vallas Chase, Wilson, Rolex, IBM, Emirates, Citizen (limpiado de marcas heredadas tanto en RGB como en canal especular alfa + extracción de `Usa1NS_locator.zml` / `Usa1ND_locator.zml`).
- **Mutua Madrid Open (`Spa2`)**: Generador de pista de **Tierra Azul** ([make_madrid_blue_clay.py](file:///c:/Users/acorr/Documents/tenis/tools/make_madrid_blue_clay.py)) con marcas y sponsors dedicados.

### 📺 3. Jugabilidad, Marcadores TV Oficiales, Físicas por Superficie y NextGenFX
- **Física diferenciada por superficie** ([fwDataDB_Stage.txt](file:///c:/Users/acorr/Documents/tenis/game/archive/Config/Fraw/fwDataDB/fwDataDB_Stage.txt)): Rebote alto y bola frenada en **Tierra Batida** (`Fra1`: `BoundY=0.95`, `BoundXZ=0.70`), bote bajo y rápido en **Hierba** (`Eng1`: `0.58 / 0.90`) y equilibrio medio-alto en **Dura** (`Aus1`, `Usa1`).
- **Marcadores TV Oficiales en Vivo (`[F7]`)** ([broadcast_hud.h](file:///c:/Users/acorr/Documents/tenis/src/xlive/broadcast_hud.h), [build_official_scoreboards.py](file:///c:/Users/acorr/Documents/tenis/tools/build_official_scoreboards.py)): 6 temas oficiales (`AO`, `RG`, `WIM`, `USO`, `MAD`, `TOUR`) + atlas de 27 banderas COI, lectura directa en RAM de sets, juegos, puntos/ventajas, turno de saque, Break/Set/Match Point, radar de bola en `km/h` y contador de `RALLY`.
- **`ProPhysics`, Resto con Teclado y Selector de Velocidad**: Modo realista de trayectoria (`ProPhysics=1`), fix del resto con teclado en estados `4..9` (buffer de pulsación de 20 ticks) y velocidades VT2 Arcade Turbo (`1.20x` / `1.35x`) o Simulación (`0.90x`).
- **Reglas Grand Slam (5 Sets x 6 Juegos)** + Cámara TV Clásica fija (`ClassicTVCamera`) configurables desde **Opciones -> Gráficos HD y Legends (`[F2]`)**.
- **NextGenFX (`src/xlive/nextgen_fx.h`)**: Corrección de viewport D3D9 en Windows 10/11, limpieza de *DOF blur/bloom* (`CleanPostFX`), nitidez adaptativa (`NextGenSharpen`) y gradación fílmica (`NextGenFilmic`).

### 🤪 4. Multiverso Arcade (EE-1..EE-5), Online P2P Nativo y Exportación Android 1-Toque
- **EE-1**: Protesta al juez de silla con McEnroe (`[C]` + QTE).
- **EE-2**: *Batalla de las Superficies* — pista partida en RAM **50% Hielo / 50% Barro** (`MultiverseMode=1/3`).
- **EE-3**: Armería alternativa (`[R]`) — **Raqueta de Madera 70s**, **Sartén Metálica** o **Baguette Gigante**.
- **EE-4**: Super Golpes Arcade estilo DBZ / Power Tennis con estela aditiva.
- **EE-5**: Jefes finales (`King`, `Duke`, `T. Tenniel`, `V. Virnie`) 100% jugables.
- **Menú `EN LÍNEA` Nativo VT4 + Auto-Descubrimiento LAN** ([netplay.h](file:///c:/Users/acorr/Documents/tenis/src/xlive/netplay.h), [build_netplay_ui_assets.py](file:///c:/Users/acorr/Documents/tenis/tools/build_netplay_ui_assets.py)): Pantalla completa nacarada/púrpura fiel a VT4 con escaneo LAN UDP (`Crear Sala` / `Buscar Sala LAN` / IP Tailscale) para crossplay PC <-> Android.
- **Display Interactivo de Mando Xbox Táctil (`[F6]`)** ([touch_gamepad.h](file:///c:/Users/acorr/Documents/tenis/src/xlive/touch_gamepad.h)): Controles táctiles translúcidos estilo Recomp (`TouchXboxHUD=0|1|2`, Auto en Android/Wine) con stick izquierdo, `A/B/X/Y`, `LB/RB` y `START`.
- **Exportación Android Llave en Mano + `PLAY_VT4_LEGENDS.exe`** ([export_android_bundle.py](file:///c:/Users/acorr/Documents/tenis/tools/export_android_bundle.py), [play_vt4_legends.c](file:///c:/Users/acorr/Documents/tenis/src/launcher/play_vt4_legends.c)): Paquete autónomo (`PerfProfile=2`, `d3dx9_43.dll`, auditoría case-sensitive) con lanzador nativo Win32 de 1 toque para **GameHub** y **Winlator CMod/Frost**. Ver [ONLINE_NETPLAY_GUIDE.md](file:///c:/Users/acorr/Documents/tenis/ONLINE_NETPLAY_GUIDE.md) y [ANDROID_SETUP_GUIDE.md](file:///c:/Users/acorr/Documents/tenis/ANDROID_SETUP_GUIDE.md).

---

## 🎮 Controles y Atajos del Mod

| Contexto | Tecla / Botón | Función |
|---|---|---|
| Global / En juego | `F2` | Abrir menú **Gráficos HD y Legends** |
| Global / En juego | `F6` | Mostrar / ocultar **Mando Xbox Táctil (`TouchXboxHUD`)** |
| En partido | `F7` | Activar / ocultar **Marcadores TV Oficiales (`BroadcastHUD`)** |
| En partido | `F10` | Captura limpia de backbuffer D3D9 (`vt4_present_*.png`) |
| `CharaSelect` | `Q` / `E` (`LB` / `RB`) | Cambiar entre las **4 páginas de roster** |
| `CharaSelect` | `F` | Alternar skin **Agassi '91 / '06** |
| `CharaSelect` | `R` | Cambiar arma arcade **EE-3** (Normal / Madera / Sartén / Baguette) |
| En partido (`EE-1`) | `C` | Protestar al juez de silla (QTE con `Z` / `Espacio`) |
| Tenis (P1 teclado) | Flechas + `Enter` / `Esc` / `Z` / `V` | Moverse + Topspin / Slice / Globo / Dejada (soporte nativo XInput / DirectInput) |

---

## 🛠️ Estructura del Proyecto

```text
├── src/
│   ├── launcher/
│   │   └── play_vt4_legends.c          # Lanzador nativo Win32 1-toque (WINEDLLOVERRIDES + WaitForSingleObject)
│   └── xlive/
│       ├── xlive.c                     # Mod Loader nativo (GFWL bypass, D3D9, PlayerDB, hooks motor)
│       ├── broadcast_hud.h             # Marcadores TV oficiales [F7] + radar km/h y contador de rally
│       ├── touch_gamepad.h             # Display Xbox táctil interactivo para Android/Wine [F6]
│       ├── player_stats.h              # Estadísticas individualizadas (IDs 26..83)
│       ├── voice_packs.h               # Tabla de packs de voz (84 IDs)
│       ├── multiverse_modes.h          # Easter Eggs EE-1..EE-5 (Ice/Mud, armas 3D, estelas)
│       ├── nextgen_fx.h / perf_opt.h   # Shaders NextGenFX y perfilado de rendimiento (PerfProfile=0..2)
│       ├── netplay.h                   # Sincronización P2P Lockstep + Auto-descubrimiento LAN UDP
│       └── xlive.def / build.ps1       # Exportaciones XLive y compilación Zig x86 -> game/xlive.dll
├── tools/
│   ├── build_grand_slam_stages.py      # Generador BC1/BC3 + LZSS de AO, RG, Wimbledon y US Open
│   ├── build_official_scoreboards.py   # Generador de overlays de Marcadores TV y atlas de banderas
│   ├── build_netplay_ui_assets.py      # Generador de sprites nativos del menú EN LÍNEA
│   ├── make_madrid_blue_clay.py        # Generador de Tierra Azul de Madrid (Spa2FS/D)
│   ├── build_all_sdo_models.py         # Pipeline de modelos 3D .sdo / .zml y UV faciales
│   ├── fix_remaining_portraits_2026.py # Recorte GrabCut y empaquetado DDS (photo_L/eye/S)
│   ├── pack_colorized_bw_portraits.py  # Empaquetado a color de los 6 retratos históricos (84/84)
│   ├── export_android_bundle.py        # Exportador Android llave en mano + PLAY_VT4_LEGENDS.exe
│   ├── vt4_archive.py / compress_sega_lzss.py # Extractor y compresor SEGA LZSS
│   └── tests/
│       ├── vt4_test_lib.py             # Automatización de menús y lectura de asserts VEH
│       └── test_roster_matrix.py       # Barrido QA automatizado jugador a jugador
├── ROADMAP_ROSTER.md                   # Registro maestro del roster (84/84) y fases 1-5
├── MODLOG.md                           # Historial técnico de sesiones y verificaciones
├── ONLINE_NETPLAY_GUIDE.md             # Guía de juego online P2P y LAN
└── ANDROID_SETUP_GUIDE.md              # Guía de portabilidad Android (GameHub / Winlator + DXVK)
```

---

## ⚙️ Compilación, Generación y QA

1. **Compilar `game/xlive.dll`** (con `zig cc` x86):
   ```powershell
   powershell -ExecutionPolicy Bypass -File src/xlive/build.ps1
   ```
2. **Regenerar los 4 estadios de Grand Slam** en `game/archive/HIGH/Stage/`:
   ```powershell
   py -u tools/build_grand_slam_stages.py
   ```
3. **Exportar paquete Android completo (`dist/android/VT4_Legends_Android/` + `PLAY_VT4_LEGENDS.exe`)**:
   ```powershell
   py -u tools/export_android_bundle.py
   ```
4. **Ejecutar matriz QA automatizada** (verifica carga, `PlayStyle=0`, `ExbAdv=0`, `Exceptions=0` y saques reales):
   ```powershell
   py -u tools/tests/test_roster_matrix.py --ids 60,61,62,64,65,66,67,68,69,70,71,72,74,75,76,77,80,81,82,83 --cpu 0 --mv 3
   ```

---

## ⚖️ Aviso Legal

Este repositorio contiene exclusivamente código fuente propio del mod (`src/xlive/`), scripts de herramientas (`tools/`) y documentación. **No incluye ni distribuye archivos originales ni binarios protegidos de SEGA** (`VT4.exe`, `resource*.bin`, texturas o modelos originales). Requiere una copia legítima de *Virtua Tennis 4* para PC.
