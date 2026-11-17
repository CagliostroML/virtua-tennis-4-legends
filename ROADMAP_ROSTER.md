# 🎾 Virtua Tennis 4: Legends & Next-Gen Edition — Hoja de Ruta y Registro Maestro

Este documento es nuestra hoja de ruta viva. Iremos marcando con `[x]` cada elemento a medida que lo implementemos y verifiquemos en el juego.

---

## 📦 Fase 1: Preparación, Reconocimiento e Ingeniería Inversa Base
- [x] Extraer contenido de `sr-vt4.iso` e instalar el cliente base en el entorno de laboratorio (`game/`).
- [x] Aplicar ejecutable desempaquetado (`VT4.exe`) y emulador de `xlive.dll` (GFWL-free) y verificar que el juego arranca en modo ventana (1280x720 windowed, D3D9Ex).
- [x] Escanear la instalación y crear herramientas de modding (`tools/vt4_archive.py`, `tools/make_config.py`).
- [x] Analizar `VT4.exe` con **REA + Ghidra 12.1.4** (`binary_overview`, `search_strings`, `list_procedures`, `decompile`) para localizar:
  - [x] Tabla/estructura en memoria de los tenistas del roster (`PlayerStruct` / IDs / Estadísticas / Estilos) y bases de datos `fwDataDB`.
  - [x] Flags de desbloqueo de leyendas ocultas (`King`, `Duke` desbloqueados de serie vía parche `FUN_005dfe90`).
  - [x] Sistema de carga de archivos y contenedores (`resource.bin`, `resource.1.bin` y soporte de carpetas sueltas `game/archive/`).
- [x] Construir herramienta en Python para desempaquetar y reempaquetar los contenedores de datos de VT4 (probado con 94 archivos extraídos).
- [x] Construir nuestra DLL de inyección (`xlive.dll` Mod Loader nativo compilado con Zig x86) para interceptar D3D9Ex, saltar GFWL, perfiles locales, saves sin registro y opciones en tiempo real.
- [x] Corregir el fallo de viewport nulo `(0,0)` en D3D9Ex interceptando `SetViewport` (`vtbl[47]`), restaurando al 100% la visibilidad de la Escena de Título y el Menú Principal completo (Arcade, Exhibición, World Tour, Opciones). Menú 100% jugable e interactivo a 60 FPS estables.

---

## 🏆 Fase 2: El Roster Definitivo (64 Tenistas: 48 ATP + 16 WTA)

### I. El "Big 3" + Era Dorada Moderna
- [x] **01. Roger Federer (SUI)** — Diestro (Revés 1M) | *Todoterreno Ofensivo / Volea* (Stats Prime aplicados en `fwDataDB_Player`)
- [x] **02. Rafael Nadal (ESP)** — Zurdo (Revés 2M) | *Físico Indestructible / Topspin Extremo* (Stats Prime aplicados en `fwDataDB_Player`)
- [x] **03. Novak Djokovic (SRB)** — Diestro (Revés 2M) | *Contragolpeador Elástico / Restador Total* (Stats Prime aplicados en `fwDataDB_Player`)
- [x] **04. Andy Murray (GBR)** — Diestro (Revés 2M) | *Táctico Defensivo / Passing Shots* (Stats Prime aplicados en `fwDataDB_Player`)
- [x] **05. Stan Wawrinka (SUI)** — Diestro (Revés 1M) | *Cañonero de Fondo (Strong Backhand)* (`ID 38`, `P_M_WAW_NG.sdo`, `photo_L/38.dds` vía PhotoCraft, Página 3)
- [x] **06. Juan Martín del Potro (ARG)** — Diestro (Revés 2M) | *Derecha Demoledora (Hard Hitter)* (Stats Prime aplicados en `fwDataDB_Player`)

### II. La Nueva Era ("Next-Gen" & Actualidad hasta 2026)
- [x] **07. Carlos Alcaraz (ESP)** — Diestro (Revés 2M) | *Todoterreno Explosivo / Rey de la Dejada* (`ID 26`, `P_M_ALC_NG.sdo`, retrato `photo_L/26.dds` sin viñeta vía PhotoCraft, jugable y verificado en partido con `0` asserts)
- [x] **08. Jannik Sinner (ITA)** — Diestro (Revés 2M) | *Golpeador de Ritmo Frenético* (`ID 27`, `P_M_SIN_NG.sdo`, retrato `photo_L/27.dds` sin viñeta vía PhotoCraft, jugable y verificado en partido con `0` asserts)
- [x] **09. Daniil Medvedev (RUS)** — Diestro (Revés 2M) | *Muro Heterodoxo / Contragolpeador Profundo* (`ID 39`, `P_M_MED_NG.sdo`, `photo_L/39.dds` vía PhotoCraft, Página 3)
- [x] **10. Alexander Zverev (GER)** — Diestro (Revés 2M) | *Gran Sacador + Potencia de Revés* (`ID 40`, `P_M_ZVE_NG.sdo`, `photo_L/40.dds` vía PhotoCraft, Página 3)
- [x] **11. Stefanos Tsitsipas (GRE)** — Diestro (Revés 1M) | *Ataque de Derecha y Red* (`ID 41`, `P_M_TSI_NG.sdo`, `photo_L/41.dds` vía PhotoCraft, Página 3)
- [x] **12. Dominic Thiem (AUT)** — Diestro (Revés 1M) | *Potencia Pesada en Tierra Batida* (`ID 42`, `P_M_THI_NG.sdo`, `photo_L/42.dds` vía PhotoCraft, Página 3)
- [x] **13. Nick Kyrgios (AUS)** — Diestro (Revés 2M) | *Impredecible / Gran Sacador / Saque por debajo* (`ID 43`, `P_M_KYR_NG.sdo`, `photo_L/43.dds` vía PhotoCraft, Página 3)
- [ ] **14. Ben Shelton (USA)** — Zurdo (Revés 2M) | *Cañonero Zurdo (Big Server)*

### III. Leyendas de los 2000s y 2010s (La Guardia Clásica)
- [x] **15. Andy Roddick (USA)** — Diestro (Revés 2M) | *Gran Sacador (249 km/h) + Derecha* (Stats Prime aplicados en `fwDataDB_Player`)
- [x] **16. Lleyton Hewitt (AUS)** — Diestro (Revés 2M) | *Velocista Incansable / Globos y Passing* (`ID 44`, `P_M_HEW_LG.sdo`, `photo_L/44.dds` vía PhotoCraft, Página 3)
- [x] **17. Marat Safin (RUS)** — Diestro (Revés 2M) | *Potencia Pura / Revés a dos manos letal* (`ID 45`, `P_M_SAF_LG.sdo`, `photo_L/45.dds` vía PhotoCraft, Página 3)
- [x] **18. Gustavo "Guga" Kuerten (BRA)** — Diestro (Revés 1M) | *Rey de la Tierra / Revés Liftado 1M* (`ID 36`, foto real `photo_L/36.dds`, modelo `P_M_KUE_LG.sdo` y Página 2)
- [x] **19. Juan Carlos Ferrero (ESP)** — Diestro (Revés 2M) | *El Mosquito (Velocidad + Derecha Cruzada)* (`ID 47`, `P_M_FRR_LG.sdo`, `photo_L/47.dds` vía PhotoCraft, Página 3)
- [x] **20. Carlos Moyá (ESP)** — Diestro (Revés 2M) | *Derecha Invertida Demoledora* (`ID 48`, `P_M_MOY_LG.sdo`, `photo_L/48.dds` vía PhotoCraft, Página 3)
- [x] **21. David Ferrer (ESP)** — Diestro (Revés 2M) | *Muro Físico / Restador Incansable* (`ID 49`, `P_M_FER_LG.sdo`, `photo_L/49.dds` vía PhotoCraft, Página 3)
- [x] **22. David Nalbandian (ARG)** — Diestro (Revés 2M) | *Ángulos Imposibles / Revés Cruzado* (`ID 50`, `P_M_NAL_LG.sdo`, `photo_L/50.dds` vía PhotoCraft, Página 3)
- [ ] **23. Guillermo Coria (ARG)** — Diestro (Revés 2M) | *El Mago (Dejadas + Velocidad en Tierra)*
- [x] **24. Jo-Wilfried Tsonga (FRA)** — Diestro (Revés 2M) | *Tenis Espectáculo (Saque + Derecha + Red)* (`ID 46`, `P_M_TSO_LG.sdo`, `photo_L/46.dds` vía PhotoCraft, Página 3)
- [ ] **25. Gaël Monfils (FRA)** — Diestro (Revés 2M) | *Showman Acrobático (Fast Runner)*
- [ ] **26. Richard Gasquet (FRA)** — Diestro (Revés 1M) | *Revés a Una Mano Artístico*
- [ ] **27. Tommy Haas (GER)** — Diestro (Revés 1M) | *Clásico Completo*
- [ ] **28. Fernando González (CHI)** — Diestro (Revés 1M) | *Mano de Piedra (Strong Forehand)*
- [ ] **29. Kei Nishikori (JPN)** — Diestro (Revés 2M) | *Golpeo Pronto sobre la Línea*
- [ ] **30. Robin Söderling / Tomas Berdych** — Diestro (Revés 2M) | *Cañonero Plano*

### IV. Leyendas de los 90s (Pistas Rápidas vs. Tierra Batida)
- [x] **31. Pete Sampras (USA)** — Diestro (Revés 1M) | *Saque y Volea Definitivo + Smash en Salto* (`ID 28`, foto real `photo_L/28.dds`, modelo `P_M_SAM_LG.sdo` y Página 2)
- [x] **32. Andre Agassi (USA)** — Diestro (Revés 2M) | *El Mejor Restador / Ataque de Fondo* (`ID 29`, foto real `photo_L/29.dds`, modelo `P_M_AGA_LG.sdo` y Página 2)
- [x] **33. Jim Courier (USA)** — Diestro (Revés 2M) | *Fuerza Bruta desde el Fondo* (Stats Prime y Página 2 `g_roster_page_legends`)
- [x] **34. Boris Becker (GER)** — Diestro (Revés 1M) | *"Boom Boom" (Saque + Volea en Plancha)* (Stats Prime y Página 2 `g_roster_page_legends`)
- [x] **35. Stefan Edberg (SWE)** — Diestro (Revés 1M) | *Saque Kick y Volea Elegante* (Stats Prime y Página 2 `g_roster_page_legends`)
- [x] **36. Goran Ivanišević (CRO)** — Zurdo (Revés 2M) | *Rey del Ace (Saque Zurdo Inalcanzable)* (`ID 54`, `P_M_IVN_LG.sdo`, `photo_L/54.dds` vía PhotoCraft, Página 3)
- [ ] **37. Michael Chang (USA)** — Diestro (Revés 2M) | *Velocidad Extrema y Espíritu de Lucha*
- [ ] **38. Marcelo "Chino" Ríos (CHI)** — Zurdo (Revés 2M) | *Talento Puro / Ángulos y Dejadas*
- [ ] **39. Thomas Muster (AUT)** — Zurdo (Revés 1M) | *La Bestia de la Tierra Batida*
- [x] **40. Sergi Bruguera / Alex Corretja / Patrick Rafter** — Leyendas de Grand Slam 90s (*Patrick Rafter*: stats Prime en `fwDataDB_Player` + Página 2 `g_roster_page_legends`; pendientes Bruguera / Corretja)

### V. Los Pioneros (Años 70 y 80) + Jefes SEGA
- [x] **41. Björn Borg (SWE)** — Diestro (Revés 2M) | *El Hombre de Hielo (Resistencia infinita + Topspin)* (`ID 30`, foto real `photo_L/30.dds`, modelo `P_M_BOR_LG.sdo` y Página 2)
- [x] **42. John McEnroe (USA)** — Zurdo (Revés 1M) | *Toque Mágico en la Red + Saque de Espaldas* (`ID 31`, foto real `photo_L/31.dds`, modelo `P_M_MCE_LG.sdo` y Página 2)
- [x] **43. Ivan Lendl (CZE/USA)** — Diestro (Revés 1M) | *Padre del Tenis Moderno de Potencia* (`ID 51`, `P_M_LEN_LG.sdo`, `photo_L/51.dds` recorte PhotoCraft B&W 1982, Página 3)
- [x] **44. Jimmy Connors (USA)** — Zurdo (Revés 2M) | *Golpeo Plano Rasante y Agresividad Total* (`ID 52`, `P_M_CON_LG.sdo`, `photo_L/52.dds` recorte PhotoCraft B&W 1978, Página 3)
- [ ] **45. Mats Wilander (SWE)** — Diestro (Revés 2M) | *Táctico de Acero*
- [x] **46. Guillermo Vilas (ARG)** — Zurdo (Revés 1M) | *El Gran Willy / Topspin Eterno* (`ID 53`, `P_M_VIL_LG.sdo`, `photo_L/53.dds` vía PhotoCraft, Página 3)
- [ ] **47. Rod Laver (AUS)** — Zurdo (Revés 1M) | *The Rocket (El único doble Grand Slam)*
- [x] **48. King & Duke (SEGA Bosses)** — Jefes finales míticos de *Virtua Tennis* (Desbloqueados de serie vía parche `FUN_005dfe90`)

### VI. Leyendas WTA (Las Grandes Reinas de la Historia)
- [x] **49. Serena Williams (USA)** — *Potencia y Saque Total* (`ID 33`, foto real `photo_L/33.dds`, modelo `P_W_SER_NG.sdo` y Página 2)
- [x] **50. Steffi Graf (GER)** — *Golden Slam (Derecha Invertida + Revés Cortado Letal)* (`ID 32`, foto real `photo_L/32.dds`, modelo `P_W_GRA_LG.sdo` y Página 2)
- [x] **51. Martina Navratilova (USA)** — *Zurda de Saque y Volea Implacable* (`ID 37`, foto real `photo_L/37.dds`, modelo `P_W_NAV_LG.sdo` y Página 2)
- [x] **52. Chris Evert (USA)** — *Precisión Milimétrica de Fondo* (`ID 55`, `P_W_EVE_LG.sdo`, `photo_L/55.dds` recorte PhotoCraft B&W, Página 3)
- [x] **53. Monica Seles (YUG/USA)** — *Doble Golpe a Dos Manos Ultra-Agresivo* (`ID 56`, `P_W_SEL_LG.sdo`, `photo_L/56.dds` vía PhotoCraft, Página 3)
- [ ] **54. Arantxa Sánchez Vicario (ESP)** — *Defensa Imposible en Tierra Batida*
- [ ] **55. Conchita Martínez (ESP)** — *Maestra del Efecto y Variedad*
- [x] **56. Garbiñe Muguruza (ESP)** — *Golpeo Plano y Agresivo* (`ID 58`, `P_W_MUG_NG.sdo`, `photo_L/58.dds` vía PhotoCraft, Página 3)
- [ ] **57. Venus Williams (USA)** — *Gran Sacadora y Envergadura*
- [ ] **58. Maria Sharapova (RUS)** — *Cañonera sin Cuartel*
- [x] **59. Justine Henin (BEL)** — *El Mejor Revés a Una Mano Femenino* (`ID 57`, `P_W_HEN_LG.sdo`, `photo_L/57.dds` vía PhotoCraft, Página 3)
- [ ] **60. Kim Clijsters (BEL)** — *Elasticidad y Potencia*
- [ ] **61. Caroline Wozniacki / Ana Ivanovic / Svetlana Kuznetsova / Laura Robson** *(Laura Robson desbloqueada en Página 2 `g_roster_page_legends`; pendientes Wozniacki/Ivanovic/Kuznetsova)*
- [x] **62. Iga Świątek (POL)** — *Topspin y Dominio Absoluto en Tierra* (`ID 34`, foto real `photo_L/34.dds`, modelo `P_W_SWI_NG.sdo` y Página 2)
- [x] **63. Aryna Sabalenka (BLR)** — *Potencia Bruta Actual* (`ID 35`, foto real `photo_L/35.dds`, modelo `P_W_SAB_NG.sdo` y Página 2)
- [ ] **64. Paula Badosa / Simona Halep** — *Circuito Moderno WTA*

---

## 🤪 Fase 3: Cinco Easter Eggs Legendarios (Modo Extra "Multiverso Arcade")
- [ ] **EE-1: 🔥 Modo McEnroe Desatado ("¡YOU CANNOT BE SERIOUS!")** — Botón de protesta al juez de silla en bolas cercanas a la línea con minijuego de intimidación arbitral y lanzamiento de raqueta.
- [x] **EE-2: 🥖 La Batalla de las Superficies Extrema (50% Barro / 50% Hielo)** — Mitad `-Z` Hielo (`BoundXZ=0.20, BoundY=0.38`, `peak_y=3.33`) y mitad `+Z` Barro (`BoundXZ=1.55, BoundY=1.22`, `peak_y=24.73`) verificadas en trayectoria real vía `MultiverseMode=1/3` (`hk_BallSimulateTrajectory` `0x00478bf3`).
- [ ] **EE-3: 🪵 Modo Raqueta de Madera vs. Sartén de Cocina (Homenaje a Roddick)** — Selector de arma/handicap (raqueta de los 70, sartén metálica, paraguas, baguette gigante) con efectos de sonido e impacto propios.
- [x] **EE-4: ⚡ Super Golpes DBZ / Mario Power Tennis** — Velocidad de bola `1.55x` y gravedad `k^2` (`0.43`) verificadas en trayectoria real (`bounce_f=23` vs `34`, `v0z=-10.78` vs `-6.70`, `peak_y=11.05`) vía `MultiverseMode=2/3` (`hk_BallSimulateTrajectory` + `hk_BallLaunch_480561`); golpes temáticos extra pendientes.
- [x] **EE-5: 🤖 Jefes Secretos Jugables (King, Duke, T. Tenniel `VTM`, V. Virnie `VTF` en Página 2 `g_roster_page_legends`; futuros skins Juez de Silla motorizado, Recogepelotas Turbo & Matt)** — Jefes y personajes secretos (`King`, `Duke`, `ID 24 T. Tenniel`, `ID 25 V. Virnie`) jugables directamente en Exhibición.

---

## 🛠️ Fase 4: Funcionalidades Extra (Quality of Life & Motor)
- [x] **EXTRA-1: Desbloqueo 100% Instantáneo** — Leyendas y jefes secretos (`Becker`, `Edberg`, `Courier`, `Rafter`, `King`, `Duke`, `T. Tenniel` ID 24, `V. Virnie` ID 25) jugables vía Página 2 (`g_roster_page_legends`) y todos los estadios desbloqueados (`Lock = -1` en `fwDataDB_Stage.txt`; equipamiento del catálogo SPT pendiente).
- [x] **EXTRA-2: Fijador de Cámara TV Clásica (VT2 Style)** — Configurable en `vt4_settings.ini` (`ClassicTVCamera`) y en el HUD de Ajustes: fija `CamType = TV` (`0x0054ca10`) y desactiva los zooms/cortes de `ShotCamera` (`0x00558890`).
- [x] **EXTRA-3: Grand Slams Oficiales & Pista Azul de Madrid** — Generador reproducible `tools/make_madrid_blue_clay.py` que transforma `Spa2FS`/`Spa2FD` (`UV_surface`, `IL_surface` y marcas en líneas `B_AU_line*`) en **Tierra Azul de Madrid** (`BoundY=0.88, BoundXZ=0.78` en `fwDataDB_Stage.txt`) y localiza `TR_COMMON.sto` (`SPA`/`ENG`) para Australian Open, Roland Garros, Wimbledon, US Open y Mutua Madrid Open.
- [x] **EXTRA-4: Selector de Velocidad de Física ("Modo VT2 Arcade Turbo" vs "Simulación")** — Configurable en `vt4_settings.ini` (`MatchSpeedMode`) y en el HUD de Ajustes (`Normal 1.00x`, `VT2 Arcade Turbo 1.20x`, `VT2 Hyper Arcade 1.35x`, `Simulación Pro 0.90x`) escalando el paso de simulación durante el juego en vivo (`0x00482aa1` + `0x0043037b`).
- [x] **EXTRA-5: Partidos a 5 Sets Reales de 6 Juegos + Tie-Break / Super Tie-Break** — Desbloqueados vía `REGLAS EXHIBICION` en `OPCIONES -> GRAFICOS HD Y LEGENDS` (`1/3/5 Sets x 6 Juegos + Tie-Break / Ventaja`, hook `hk_SetMatchRules` `0x0045f480`) y eliminado el Assert NULL de `ExhibitionAdvancedSetting` (`0x004351e1`).
- [x] **EXTRA-6: Parche 4K & Nitidez PostFX** — Resolución configurable en `vt4_settings.ini` y eliminación/reducción de *DOF blur* y *bloom/glare* (`CleanPostFX=0/1/2` en `OPCIONES -> GRAFICOS HD Y LEGENDS`, hook `hk_RenderPostEffects` `0x004a9460`), verificado en comparativa visual y `test_options_ui.py`.

---

### Estado verificado de los 12 nuevos IDs (`26..37`, Hito B + Hito D)
- **Matriz jugable (`test_roster_matrix.py --ids 26..37`)**: Los 12 (`26` Alcaraz, `27` Sinner, `28` Sampras, `29` Agassi, `30` Borg, `31` McEnroe, `32` Graf, `33` Serena, `34` Świątek, `35` Sabalenka, `36` Kuerten, `37` Navratilova) cargan en partido, se mueven y sacan (`served=1`, `PlayStyle=0`, `ExbAdv=0`, `Exc=0`) tras mapear `0x0053d6d0` (`0x007baaa8`).
- **Retratos `photo_L/26..37.dds` (Hito D completado)**: 12 originales CC/PD y `manifest.json` en `assets/portraits_src/` (incluyendo `29` Agassi Indian Wells 2006, `30` Borg 1979 en pista y `32` Graf Wimbledon 2009), con restauración/coloreado fiel vía Nano Banana + recorte MCP de **PhotoCraft** en `28` Sampras, `30` Borg, `31` McEnroe y `36` Kuerten (queda pendiente `37` Navratilova al alcanzar el límite horario de `gemini-3.1-flash-image`), exportados desde `tools/build_legends_roster.py` al formato oficial VT4 (`256x256` BGRA 32bpp sin mipmaps, `262,272` bytes, `pf_flags=0x41`, cero viñeta circular) y verificados en `Página 2/2` dentro del juego (`0` asserts, `0` excepciones).

### Estado verificado de Página 3 (`IDs 38..58`, 59 jugadores totales)
- **Motor y `PlayerDB` (`src/xlive/xlive.c`)**: `NUM_ROSTER_PAGES = 3`, `MAX_ROSTER_PLAYERS = 59`, cabecera `PAGINA 3/3: NEXT-GEN & HISTORIA` (con `DT_NOPREFIX`), `g_extra_players[21]` y hooks completos de `PlayerDB` (`0x00533310..0x00533eec`), `ServeMin`/`ServeMax` (`0x00539441`/`0x00539456`), límites `0x3b` (`0x005df6a5`, `0x005b9960`), y guard `hk_GetMotionData` (`0x004e06f0`) frente a retornos `>= 0x7FFE0000u` (`0xFFFFFFE3`/`0xFFFFFFE4`).
- **Modelos y retratos (`tools/build_page3_roster.py`)**: 21 modelos `.sdo` + `.zml` (`P_M_WAW_NG`..`P_W_MUG_NG`), 21 fuentes CC/PD + `assets/portraits_page3_src/manifest.json` y recortes PhotoCraft MCP en `photo_L/38..58.dds` (`262,272` B BGRA 256x256; `51` Lendl, `52` Connors y `55` Evert en B&W limpios a la espera de reseteo de cuota de `gemini-3.1-flash-image`).
- **Matriz jugable (`test_roster_matrix.py --ids 38..58 --mv 3`)**: **21/21** (`38` Wawrinka, `39` Medvedev, `40` Zverev, `41` Tsitsipas, `42` Thiem, `43` Kyrgios, `44` Hewitt, `45` Safin, `46` Tsonga, `47` Ferrero, `48` Moyá, `49` Ferrer, `50` Nalbandian, `51` Lendl, `52` Connors, `53` Vilas, `54` Ivanišević, `55` Evert, `56` Seles, `57` Henin, `58` Muguruza) cargan, muestran su retrato/bandera en `Página 3/3`, juegan y sacan en partido con `PlayStyle=0`, `ExbAdv=0` y `Exceptions=0`.

### Estado verificado: Nombres en Partido, Épocas, Miniaturas y Skins (`TR_COMMON` + `photo_eye` + Agassi/Sabalenka)
- **Fix completo de nombres en partido (`0x00668fa0`, `hk_StoLookup`)**: Reemplazo directo del selector `hk_SetFrawTableText` por hook único en `0x00668fa0` (verificando `TR_COMMON.sto` con `table 0, row 0 == "Roger Federer"`). Cubre todas las tablas de nombre (`0` completo, `1` Apellido Nombre, `2` tarjeta, `3` nombre pila, `4` banner `I. Apellido`, `5` mayúsculas marcador `I.APELLIDO`, `6` código COI `ESP`/`BLR`/`SUI`, más `7/8/10/11/13`) para los **33 IDs nuevos (`26..58`)**, corrigiendo nombres NPC de relleno como *"Dries Nothomb"* en **Sabalenka (`35`)**.
- **Agrupación de las 3 páginas por épocas (`src/xlive/xlive.c`, `tools/tests/vt4_test_lib.py`)**:
  - `Página 1/3`: *Actual & Next-Gen (2010-2026)* (Big 3, Alcaraz, Sinner, Medvedev, Zverev, Tsitsipas, Thiem, Wawrinka, Murray, Del Potro, Kyrgios, Monfils, Świątek, Sabalenka, Serena, Sharapova, Muguruza, Wozniacki, Venus).
  - `Página 2/3`: *Era Dorada (1990s - 2000s)* (Sampras, Agassi, Courier, Edberg, Becker, Rafter, Ivanišević, Kuerten, Hewitt, Safin, Ferrero, Moyá, Ferrer, Nalbandian, Tsonga, Roddick, González, Haas, Seles, Henin, Graf).
  - `Página 3/3`: *Pioneros 70s-80s & Clásicos VT4* (Borg, McEnroe, Lendl, Connors, Vilas, Navratilova, Evert, Kuznetsova, Ivanovic, Chakvetadze, Robson, Kohlschreiber, Seppi, King, Duke, Tenniel, Virnie + destacados).
- **Miniaturas de cuadrícula y UI (`tools/update_custom_assets.py`, `render_roster_pagination_hud`)**: Generadas las 59 bandas de ojos (`game/archive/HIGH/Frontend/VR/photo_eye/0..58.dds`, BGRA 256×64), miniaturas `photo_S/26..58.dds` (128×64 DXT5), corrección del borde izquierdo de `photo_L/38.dds` (Wawrinka) y renderizado UTF-8 (`TextOutW`) sobre los 21 recuadros de cada página.
- **Skins alternativas de Agassi (`[F]`) y mejora de modelos (`update_custom_assets.py`)**:
  - Selector `[F]` en `CharaSelect` (tecla `F` o clic en la barra inferior) alternando en tiempo real entre `P_M_AGA_LG.sdo` (**Agassi '91**: melena rubia + cinta + conjunto Challenge Court sobre malla `P_M_NAD_IT`) y `P_M_AG2_LG.sdo` (**Agassi '06**: cabeza calva real sin malla de pelo + perilla + conjunto negro/blanco sobre malla `P_M_DJV_IT`), plus `P_W_SAB_NG.sdo` (vestido rojo + coleta alta sobre `P_W_SHA_SN`).
  - Verificado con `test_options_ui.py` (válido), capturas visuales en partida (`01`–`08`) y `test_roster_matrix.py --ids 26,27,34,35,29,38,51 --cpu 0 --mv 3` (**7/7** `ok=True`, `PlayStyle=0`, `ExbAdv=0`, `Exc=0`, `served>=1`).
