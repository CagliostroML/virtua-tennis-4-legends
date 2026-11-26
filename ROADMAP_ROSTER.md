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
- [x] **07. Carlos Alcaraz (ESP)** — Diestro (Revés 2M) | *Todoterreno Explosivo / Rey de la Dejada* (`ID 26`, `P_M_ALC_NG.sdo`, retrato `photo_L/26.dds` provisional a rehacer con Nano Banana, jugable y verificado en partido con `0` asserts)
- [x] **08. Jannik Sinner (ITA)** — Diestro (Revés 2M) | *Golpeador de Ritmo Frenético* (`ID 27`, `P_M_SIN_NG.sdo`, retrato `photo_L/27.dds` limpiado vía PhotoCraft CLI, jugable y verificado en partido con `0` asserts)
- [x] **09. Daniil Medvedev (RUS)** — Diestro (Revés 2M) | *Muro Heterodoxo / Contragolpeador Profundo* (`ID 39`, `P_M_MED_NG.sdo`, `photo_L/39.dds` vía PhotoCraft, Página 1/4)
- [x] **10. Alexander Zverev (GER)** — Diestro (Revés 2M) | *Gran Sacador + Potencia de Revés* (`ID 40`, `P_M_ZVE_NG.sdo`, `photo_L/40.dds` vía PhotoCraft, Página 1/4)
- [x] **11. Stefanos Tsitsipas (GRE)** — Diestro (Revés 1M) | *Ataque de Derecha y Red* (`ID 41`, `P_M_TSI_NG.sdo`, `photo_L/41.dds` vía PhotoCraft, Página 1/4)
- [x] **12. Dominic Thiem (AUT)** — Diestro (Revés 1M) | *Potencia Pesada en Tierra Batida* (`ID 42`, `P_M_THI_NG.sdo`, `photo_L/42.dds` vía PhotoCraft, Página 1/4)
- [x] **13. Nick Kyrgios (AUS)** — Diestro (Revés 2M) | *Impredecible / Gran Sacador / Saque por debajo* (`ID 43`, `P_M_KYR_NG.sdo`, `photo_L/43.dds` vía PhotoCraft, Página 1/4)
- [x] **14. Ben Shelton (USA)** — Zurdo (Revés 2M) | *Cañonero Zurdo (Big Server)* (`ID 59`, `P_M_SHE_NG.sdo`, `photo_L/59.dds`, Página 1/4, verificado en US Open y `test_roster_matrix`; también verificados en Página 1/4 `60` Rublev, `61` Ruud, `62` Fritz, `63` Coco Gauff, `64` Rybakina y `82` Mirra Andreeva)

### III. Leyendas de los 2000s y 2010s (La Guardia Clásica)
- [x] **15. Andy Roddick (USA)** — Diestro (Revés 2M) | *Gran Sacador (249 km/h) + Derecha* (Stats Prime aplicados en `fwDataDB_Player`, Página 2/4)
- [x] **16. Lleyton Hewitt (AUS)** — Diestro (Revés 2M) | *Velocista Incansable / Globos y Passing* (`ID 44`, `P_M_HEW_LG.sdo`, `photo_L/44.dds` vía PhotoCraft, Página 2/4)
- [x] **17. Marat Safin (RUS)** — Diestro (Revés 2M) | *Potencia Pura / Revés a dos manos letal* (`ID 45`, `P_M_SAF_LG.sdo`, `photo_L/45.dds` vía PhotoCraft, Página 2/4)
- [x] **18. Gustavo "Guga" Kuerten (BRA)** — Diestro (Revés 1M) | *Rey de la Tierra / Revés Liftado 1M* (`ID 36`, foto real `photo_L/36.dds`, modelo `P_M_KUE_LG.sdo` y Página 2/4)
- [x] **19. Juan Carlos Ferrero (ESP)** — Diestro (Revés 2M) | *El Mosquito (Velocidad + Derecha Cruzada)* (`ID 47`, `P_M_FRR_LG.sdo`, `photo_L/47.dds` vía PhotoCraft, Página 2/4)
- [x] **20. Carlos Moyá (ESP)** — Diestro (Revés 2M) | *Derecha Invertida Demoledora* (`ID 48`, `P_M_MOY_LG.sdo`, `photo_L/48.dds` vía PhotoCraft, Página 2/4)
- [x] **21. David Ferrer (ESP)** — Diestro (Revés 2M) | *Muro Físico / Restador Incansable* (`ID 49`, `P_M_FER_LG.sdo`, `photo_L/49.dds` vía PhotoCraft, Página 2/4)
- [x] **22. David Nalbandian (ARG)** — Diestro (Revés 2M) | *Ángulos Imposibles / Revés Cruzado* (`ID 50`, `P_M_NAL_LG.sdo`, `photo_L/50.dds` vía PhotoCraft, Página 2/4)
- [x] **23. Guillermo Coria (ARG)** — Diestro (Revés 2M) | *El Mago (Dejadas + Velocidad en Tierra)* (`ID 67`, `P_M_COR_LG.sdo` y `photo_L/67.dds` recortado; verificado en `test_roster_matrix` con `0` asserts/`2` saques)
- [x] **24. Jo-Wilfried Tsonga (FRA)** — Diestro (Revés 2M) | *Tenis Espectáculo (Saque + Derecha + Red)* (`ID 46`, `P_M_TSO_LG.sdo`, `photo_L/46.dds` vía PhotoCraft, Página 2/4)
- [x] **25. Gaël Monfils (FRA)** — Diestro (Revés 2M) | *Showman Acrobático (Fast Runner)* (Nativo VT4 `ID 6`, desbloqueado en Página 2/4 `g_roster_page_legends`)
- [x] **26. Richard Gasquet (FRA)** — Diestro (Revés 1M) | *Revés a Una Mano Artístico* (`ID 68`, `P_M_GAS_LG.sdo` y `photo_L/68.dds` en Página 2/4; verificado en `test_roster_matrix` con `0` asserts/`2` saques)
- [x] **27. Tommy Haas (GER)** — Diestro (Revés 1M) | *Clásico Completo* (Nativo VT4 `ID 10`, desbloqueado en Página 2/4 `g_roster_page_legends`)
- [x] **28. Fernando González (CHI)** — Diestro (Revés 1M) | *Mano de Piedra (Strong Forehand)* (Nativo VT4 `ID 7`, desbloqueado en Página 2/4 `g_roster_page_legends`)
- [x] **29. Kei Nishikori (JPN)** — Diestro (Revés 2M) | *Golpeo Pronto sobre la Línea* (`ID 69`, `P_M_NIS_LG.sdo` y `photo_L/69.dds` en Página 2/4; verificado en `test_roster_matrix` con `0` asserts/`1` saque)
- [x] **30. Robin Söderling / Tomas Berdych** — Diestro (Revés 2M) | *Cañonero Plano* (`IDs 70/71`, `P_M_SOD_LG.sdo` y `P_M_BER_LG.sdo` + `photo_L/70..71.dds` en Página 2/4; verificados en `test_roster_matrix` con `0` asserts/`2` saques)

### IV. Leyendas de los 90s (Pistas Rápidas vs. Tierra Batida)
- [x] **31. Pete Sampras (USA)** — Diestro (Revés 1M) | *Saque y Volea Definitivo + Smash en Salto* (`ID 28`, foto real `photo_L/28.dds`, modelo `P_M_SAM_LG.sdo` y Página 3/4)
- [x] **32. Andre Agassi (USA)** — Diestro (Revés 2M) | *El Mejor Restador / Ataque de Fondo* (`ID 29`, skin doble `'91` / `'06` con `[F]`, `P_M_AGA_LG.sdo` y `P_M_AG2_LG.sdo`, Página 3/4)
- [x] **33. Jim Courier (USA)** — Diestro (Revés 2M) | *Fuerza Bruta desde el Fondo* (Nativo VT4 en Página 3/4 `g_roster_page_legends2`)
- [x] **34. Boris Becker (GER)** — Diestro (Revés 1M) | *"Boom Boom" (Saque + Volea en Plancha)* (Nativo VT4 en Página 3/4 `g_roster_page_legends2`)
- [x] **35. Stefan Edberg (SWE)** — Diestro (Revés 1M) | *Saque Kick y Volea Elegante* (Nativo VT4 en Página 3/4 `g_roster_page_legends2`)
- [x] **36. Goran Ivanišević (CRO)** — Zurdo (Revés 2M) | *Rey del Ace (Saque Zurdo Inalcanzable)* (`ID 54`, `P_M_IVN_LG.sdo`, `photo_L/54.dds` vía PhotoCraft, Página 3/4)
- [x] **37. Michael Chang (USA)** — Diestro (Revés 2M) | *Velocidad Extrema y Espíritu de Lucha* (`ID 72`, `P_M_CHN_LG.sdo` y `photo_L/72.dds` recortado en Página 4/4; verificado en `test_roster_matrix` con `0` asserts/`2` saques)
- [x] **38. Marcelo "Chino" Ríos (CHI)** — Zurdo (Revés 2M) | *Talento Puro / Ángulos y Dejadas* (`ID 73`, `P_M_RIO_LG.sdo`, `photo_L/73.dds`, Página 4/4, verificado en `test_roster_matrix` con `0` asserts/`2` saques)
- [x] **39. Thomas Muster (AUT)** — Zurdo (Revés 1M) | *La Bestia de la Tierra Batida* (`ID 74`, `P_M_MUS_LG.sdo` y `photo_L/74.dds` a color en Página 4/4; verificado en `test_roster_matrix` con `0` asserts/`2` saques)
- [x] **40. Sergi Bruguera / Álex Corretja / Patrick Rafter** — Leyendas de Grand Slam 90s (*Patrick Rafter* nativo en Página 3/4; *Sergi Bruguera* `ID 75` a color y *Álex Corretja* `ID 76` en Página 4/4 verificados en `test_roster_matrix` con `0` asserts/`1-2` saques)

### V. Los Pioneros (Años 70 y 80) + Jefes SEGA
- [x] **41. Björn Borg (SWE)** — Diestro (Revés 2M) | *El Hombre de Hielo (Resistencia infinita + Topspin)* (`ID 30`, foto real `photo_L/30.dds`, modelo `P_M_BOR_LG.sdo` y Página 4/4)
- [x] **42. John McEnroe (USA)** — Zurdo (Revés 1M) | *Toque Mágico en la Red + Saque de Espaldas* (`ID 31`, hueco gris limpiado en `photo_L/31.dds`, modelo `P_M_MCE_LG.sdo` y Página 4/4)
- [x] **43. Ivan Lendl (CZE/USA)** — Diestro (Revés 1M) | *Padre del Tenis Moderno de Potencia* (`ID 51`, `P_M_LEN_LG.sdo`, `photo_L/51.dds` a color limpio, Página 4/4)
- [x] **44. Jimmy Connors (USA)** — Zurdo (Revés 2M) | *Golpeo Plano Rasante y Agresividad Total* (`ID 52`, `P_M_CON_LG.sdo`, `photo_L/52.dds` a color limpio, Página 4/4)
- [x] **45. Mats Wilander (SWE)** — Diestro (Revés 2M) | *Táctico de Acero* (`ID 77`, `P_M_WLD_LG.sdo` y `photo_L/77.dds` a color en Página 4/4; verificado en `test_roster_matrix` con `0` asserts/`2` saques)
- [x] **46. Guillermo Vilas (ARG)** — Zurdo (Revés 1M) | *El Gran Willy / Topspin Eterno* (`ID 53`, `P_M_VIL_LG.sdo`, `photo_L/53.dds` vía PhotoCraft, Página 4/4)
- [x] **47. Rod Laver (AUS)** — Zurdo (Revés 1M) | *The Rocket (El único doble Grand Slam)* (`ID 78`, `P_M_LAV_LG.sdo`, `photo_L/78.dds`, Página 4/4, verificado en `test_roster_matrix` y en partido EE-1/EE-3)
- [x] **48. King & Duke (SEGA Bosses)** — Jefes finales míticos de *Virtua Tennis* (Desbloqueados de serie vía parche `FUN_005dfe90`)

### VI. Leyendas WTA (Las Grandes Reinas de la Historia)
- [x] **49. Serena Williams (USA)** — *Potencia y Saque Total* (`ID 33`, foto real `photo_L/33.dds`, modelo `P_W_SER_NG.sdo` y Página 2/4)
- [x] **50. Steffi Graf (GER)** — *Golden Slam (Derecha Invertida + Revés Cortado Letal)* (`ID 32`, foto real `photo_L/32.dds`, modelo `P_W_GRA_LG.sdo` y Página 3/4)
- [x] **51. Martina Navratilova (USA)** — *Zurda de Saque y Volea Implacable* (`ID 37`, foto real `photo_L/37.dds`, modelo `P_W_NAV_LG.sdo` y Página 4/4)
- [x] **52. Chris Evert (USA)** — *Precisión Milimétrica de Fondo* (`ID 55`, `P_W_EVE_LG.sdo`, `photo_L/55.dds` a color con cinta Ellesse, Página 4/4)
- [x] **53. Monica Seles (YUG/USA)** — *Doble Golpe a Dos Manos Ultra-Agresivo* (`ID 56`, `P_W_SEL_LG.sdo`, `photo_L/56.dds` vía PhotoCraft, Página 3/4)
- [x] **54. Arantxa Sánchez Vicario (ESP)** — *Defensa Imposible en Tierra Batida* (`ID 79`, `P_W_ASV_LG.sdo`, `photo_L/79.dds`, Página 4/4, verificado en `test_roster_matrix` con `0` asserts/`2` saques)
- [x] **55. Conchita Martínez (ESP)** — *Maestra del Efecto y Variedad* (`ID 80`, `P_W_CMT_LG.sdo` y `photo_L/80.dds` en Página 3/4; verificado en `test_roster_matrix` con `0` asserts/`2` saques; también verificada `83` Billie Jean King en Página 4/4 y Wimbledon)
- [x] **56. Garbiñe Muguruza (ESP)** — *Golpeo Plano y Agresivo* (`ID 58`, `P_W_MUG_NG.sdo`, `photo_L/58.dds` vía PhotoCraft, Página 1/4)
- [x] **57. Venus Williams (USA)** — *Gran Sacadora y Envergadura* (Nativa VT4 `ID 18`, desbloqueada en Página 3/4 `g_roster_page_legends2`)
- [x] **58. Maria Sharapova (RUS)** — *Cañonera sin Cuartel* (Nativa VT4 `ID 17`, desbloqueada en Página 2/4 `g_roster_page_legends`)
- [x] **59. Justine Henin (BEL)** — *El Mejor Revés a Una Mano Femenino* (`ID 57`, `P_W_HEN_LG.sdo`, `photo_L/57.dds` vía PhotoCraft, Página 3/4)
- [x] **60. Kim Clijsters (BEL)** — *Elasticidad y Potencia* (`ID 81`, `P_W_CLI_LG.sdo` y `photo_L/81.dds` en Página 3/4; verificada en `test_roster_matrix` con `0` asserts/`1` saque)
- [x] **61. Caroline Wozniacki / Ana Ivanovic / Svetlana Kuznetsova / Laura Robson** *(Nativas VT4 desbloqueadas y jugables: `Wozniacki` `ID 22` en Página 3/4; `Kuznetsova` `ID 19`, `Ivanovic` `ID 20` y `Robson` `ID 23` en Página 4/4)*
- [x] **62. Iga Świątek (POL)** — *Topspin y Dominio Absoluto en Tierra* (`ID 34`, foto real `photo_L/34.dds`, modelo `P_W_SWI_NG.sdo` y Página 1/4)
- [x] **63. Aryna Sabalenka (BLR)** — *Potencia Bruta Actual* (`ID 35`, foto real `photo_L/35.dds`, modelo `P_W_SAB_NG.sdo` sobre `P_W_KUZ_IT`, Página 1/4)
- [x] **64. Paula Badosa / Simona Halep** — *Circuito Moderno WTA* (`IDs 65/66`, `P_W_BAD_NG.sdo` y `P_W_HAL_NG.sdo` + `photo_L/65..66.dds` en Página 1/4; verificadas en `test_roster_matrix` con `0` asserts/`2` saques)

---

## 🤪 Fase 3: Cinco Easter Eggs Legendarios (Modo Extra "Multiverso Arcade")
- [x] **EE-1: 🔥 Modo McEnroe Desatado ("¡YOU CANNOT BE SERIOUS!")** — Botón de protesta `[C]` al juez de silla en `LiveMatch` con QTE de 2.5 s (`[Z]` / `[ESPACIO]`, zona verde 65-95% -> `+15% FURIA` o `WARNING ARBITRAL`) en `src/xlive/multiverse_modes.h`, verificado en vivo (`06_match_ee1_mcenroe_qte.png`, `fase3=1`).
- [x] **EE-2: 🥖 La Batalla de las Superficies Extrema (50% Barro / 50% Hielo)** — Mitad `-Z` Hielo (`BoundXZ=0.20, BoundY=0.38`, `peak_y=3.33`) y mitad `+Z` Barro (`BoundXZ=1.55, BoundY=1.22`, `peak_y=24.73`) verificadas en trayectoria real vía `MultiverseMode=1/3` (`hk_BallSimulateTrajectory` `0x00478bf3`).
- [x] **EE-3: 🪵 Modo Raqueta de Madera vs. Sartén de Cocina vs. Baguette Gigante** — Selector de arma (`0=Normal`, `1=Raqueta Madera 70s`, `2=Sartén Metálica (Roddick)`, `3=Baguette Gigante`) configurable vía `WeaponMode` en `OPCIONES -> GRÁFICOS HD Y LEGENDS` (fila 11) y tecla `[R]` en `CharaSelect`; inyecta mallas 3D (`game/archive/ee3/ee3_meshes.bin`) y 21 DDS con parche LZSS en RAM (`ee_parse_and_patch_sdo`), verificado en partido con Rod Laver (Sartén) y Ben Shelton (Baguette) sin crashes ni excepciones (`ps=0 ex=0 exc=0`).
- [x] **EE-4: ⚡ Super Golpes DBZ / Mario Power Tennis** — Velocidad de bola `1.55x` y gravedad `k^2` (`0.43`) verificadas en trayectoria real (`bounce_f=23` vs `34`, `v0z=-10.78` vs `-6.70`, `peak_y=11.05`) vía `MultiverseMode=2/3` (`hk_BallSimulateTrajectory` + `hk_BallLaunch_480561`) más estela/halo aditivo (`D3DBLEND_ONE`) en `src/xlive/multiverse_modes.h`.
- [x] **EE-5: 🤖 Jefes Secretos Jugables (King, Duke, T. Tenniel `VTM`, V. Virnie `VTF`)** — Jefes y personajes secretos (`King`, `Duke`, `ID 24 T. Tenniel`, `ID 25 V. Virnie`) jugables directamente en Exhibición (`g_roster_page_legends3` / Páginas de Leyendas).

---

## 🛠️ Fase 4: Funcionalidades Extra (Quality of Life & Motor)
- [x] **EXTRA-1: Desbloqueo 100% Instantáneo** — Leyendas y jefes secretos (`Becker`, `Edberg`, `Courier`, `Rafter`, `King`, `Duke`, `T. Tenniel` ID 24, `V. Virnie` ID 25) jugables vía Página 2/3/4, todos los estadios desbloqueados (`Lock = -1` en `fwDataDB_Stage.txt`) y catálogo SPT/tienda/estilos desbloqueado al 100 % parcheando los 7 getters `UnlockManager` (`0x00463b80`, `0x004638c0`, `0x00463a40`, `0x00463510`, `0x00463230`, `0x00463390`, `0x004640a0` en `src/xlive/xlive.c`, compilado OK; verificación directa de pantalla tienda pendiente).
- [x] **EXTRA-2: Fijador de Cámara TV Clásica (VT2 Style)** — Configurable en `vt4_settings.ini` (`ClassicTVCamera`) y en el HUD de Ajustes: fija `CamType = TV` (`0x0054ca10`) y desactiva los zooms/cortes de `ShotCamera` (`0x00558890`).
- [x] **EXTRA-3: Grand Slams Oficiales & Pista Azul de Madrid** — Generadores reproducibles `tools/make_madrid_blue_clay.py` (Tierra Azul de Madrid en `Spa2FS`/`Spa2FD`) y `tools/build_grand_slam_stages.py` (8 `.sdo` Individuales+Dobles para **Australian Open `Aus1`**, **Roland Garros `Fra1`**, **Wimbledon `Eng1`** y **US Open `Usa1`** + extracción de `Usa1NS_locator.zml`/`Usa1ND_locator.zml`), ajuste de rebote/velocidad por superficie en `fwDataDB_Stage.txt` y localización `TR_COMMON.sto` (`SPA`/`ENG`), verificados los 4 Grand Slams en vivo.
- [x] **EXTRA-4: Selector de Velocidad de Física ("Modo VT2 Arcade Turbo" vs "Simulación")** — Configurable en `vt4_settings.ini` (`MatchSpeedMode`) y en el HUD de Ajustes (`Normal 1.00x`, `VT2 Arcade Turbo 1.20x`, `VT2 Hyper Arcade 1.35x`, `Simulación Pro 0.90x`) escalando el paso de simulación durante el juego en vivo (`0x00482aa1` + `0x0043037b`).
- [x] **EXTRA-5: Partidos a 5 Sets Reales de 6 Juegos + Tie-Break / Super Tie-Break** — Desbloqueados vía `REGLAS EXHIBICION` en `OPCIONES -> GRAFICOS HD Y LEGENDS` (`1/3/5 Sets x 6 Juegos + Tie-Break / Ventaja`, hook `hk_SetMatchRules` `0x0045f480`) y eliminado el Assert NULL de `ExhibitionAdvancedSetting` (`0x004351e1`).
- [x] **EXTRA-6: Parche 4K & Nitidez PostFX** — Resolución configurable en `vt4_settings.ini` y eliminación/reducción de *DOF blur* y *bloom/glare* (`CleanPostFX=0/1/2` en `OPCIONES -> GRAFICOS HD Y LEGENDS`, hook `hk_RenderPostEffects` `0x004a9460`), verificado en comparativa visual y `test_options_ui.py`.

---

## 📱 Fase 5: Exportación y Portabilidad a Android (Mejores Prácticas)
Objetivo: garantizar que *Virtua Tennis 4: Legends & Next-Gen Edition* sea **exportable de forma limpia, reproducible y optimizada a Android**, aplicando las mejores prácticas vigentes del ecosistema (a contrastar y actualizar mediante investigación online antes de ejecutar cada hito).

- [x] **ANDROID-1: Investigación online de mejores prácticas vigentes (Prerrequisito)**
  - Documentadas prácticas Winlator Bionic/Cmod, GameHub, DXVK + Turnip/Vortek, FUSE & Scoped Storage en `ANDROID_SETUP_GUIDE.md`.
- [x] **ANDROID-2: Preparación de compatibilidad en `xlive.dll` y el motor para Wine / Box64 / DXVK**
  - Perfil móvil `PerfProfile=2` (sombras 512x512, bloom 256x128, caché I/O en RAM 0 syscalls), `d3dx9_43.dll` auto-incluido, `dxvk.conf` y auditoría automática case-sensitive de `game/archive/` (`0` mismatches).
- [x] **ANDROID-3: Controles y UX móvil**
  - Soporte plug-and-play XInput + **Display de Mando Xbox Táctil Interactivo** (`src/xlive/touch_gamepad.h`) con stick analógico virtual, botones `A/B/X/Y`, `LB/RB` y `START`, configurable en `OPCIONES -> GRÁFICOS HD Y LEGENDS` (`TouchXboxHUD=0|1|2`, Auto en Android/Wine) o tecla `[F6]`.
- [x] **ANDROID-4: Pipeline automatizado de exportación (`tools/export_android_bundle.py`)**
  - Script reproducible que compila el lanzador nativo Win32 **`PLAY_VT4_LEGENDS.exe`** (`src/launcher/play_vt4_legends.c`, ejecución síncrona con `WINEDLLOVERRIDES` para 1 toque en GameHub/Winlator), genera `LAUNCH_ANDROID.bat` síncrono y exporta el paquete autónomo en `dist/android/VT4_Legends_Android/` (`0` fallos case-sensitive, `--patch-only` y `--verify-only` incluidos), sin basura de compilación/depuración ni subida de binarios SEGA a GitHub.
- [ ] **ANDROID-5: Pruebas en dispositivo real y ajuste térmico/FPS**
  - Validar arranque, 60 FPS estables sin *thermal throttling* ni *micro-stuttering* de shaders, audio sin cortes, guardado local y modos clave (Exhibición con 4 páginas de roster, Madrid Blue Clay, Multiverse EE-1..EE-4 y HUD de Opciones) en Android (priorizando Snapdragon/Adreno con Turnip y documentando compatibilidad en Mali).

---

### Estado verificado de los 12 nuevos IDs (`26..37`, Hito B + Hito D)
- **Matriz jugable (`test_roster_matrix.py --ids 26..37`)**: Los 12 (`26` Alcaraz, `27` Sinner, `28` Sampras, `29` Agassi, `30` Borg, `31` McEnroe, `32` Graf, `33` Serena, `34` Świątek, `35` Sabalenka, `36` Kuerten, `37` Navratilova) cargan en partido, se mueven y sacan (`served=1`, `PlayStyle=0`, `ExbAdv=0`, `Exc=0`) tras mapear `0x0053d6d0` (`0x007baaa8`).
- **Retratos `photo_L/26..37.dds` (Hito D completado)**: 12 originales CC/PD y `manifest.json` en `assets/portraits_src/` (incluyendo `29` Agassi Indian Wells 2006, `30` Borg 1979 en pista y `32` Graf Wimbledon 2009), con restauración/coloreado fiel vía Nano Banana + recorte MCP de **PhotoCraft** en `28` Sampras, `30` Borg, `31` McEnroe y `36` Kuerten (queda pendiente `37` Navratilova al alcanzar el límite horario de `gemini-3.1-flash-image`), exportados desde `tools/build_legends_roster.py` al formato oficial VT4 (`256x256` BGRA 32bpp sin mipmaps, `262,272` bytes, `pf_flags=0x41`, cero viñeta circular) y verificados en `Página 2/2` dentro del juego (`0` asserts, `0` excepciones).

### Estado verificado de Página 3 (`IDs 38..58`, 59 jugadores totales)
- **Motor y `PlayerDB` (`src/xlive/xlive.c`)**: `NUM_ROSTER_PAGES = 3`, `MAX_ROSTER_PLAYERS = 59`, cabecera `PAGINA 3/3: NEXT-GEN & HISTORIA` (con `DT_NOPREFIX`), `g_extra_players[21]` y hooks completos de `PlayerDB` (`0x00533310..0x00533eec`), `ServeMin`/`ServeMax` (`0x00539441`/`0x00539456`), límites `0x3b` (`0x005df6a5`, `0x005b9960`), y guard `hk_GetMotionData` (`0x004e06f0`) frente a retornos `>= 0x7FFE0000u` (`0xFFFFFFE3`/`0xFFFFFFE4`).
- **Modelos y retratos (`tools/build_page3_roster.py`)**: 21 modelos `.sdo` + `.zml` (`P_M_WAW_NG`..`P_W_MUG_NG`), 21 fuentes CC/PD + `assets/portraits_page3_src/manifest.json` y recortes PhotoCraft MCP en `photo_L/38..58.dds` (`262,272` B BGRA 256x256; `51` Lendl, `52` Connors y `55` Evert en B&W limpios a la espera de reseteo de cuota de `gemini-3.1-flash-image`).
- **Matriz jugable (`test_roster_matrix.py --ids 38..58 --mv 3`)**: **21/21** (`38` Wawrinka, `39` Medvedev, `40` Zverev, `41` Tsitsipas, `42` Thiem, `43` Kyrgios, `44` Hewitt, `45` Safin, `46` Tsonga, `47` Ferrero, `48` Moyá, `49` Ferrer, `50` Nalbandian, `51` Lendl, `52` Connors, `53` Vilas, `54` Ivanišević, `55` Evert, `56` Seles, `57` Henin, `58` Muguruza) cargan, muestran su retrato/bandera en `Página 3/3`, juegan y sacan en partido con `PlayStyle=0`, `ExbAdv=0` y `Exceptions=0`.

### Estado verificado de Página 4 (`IDs 59..81`, 82 jugadores en 4 páginas)
- **Motor (`src/xlive/xlive.c`) y modelos (`tools/build_all_sdo_models.py`)**: `NUM_ROSTER_PAGES = 4`, `MAX_ROSTER_PLAYERS = 82` (`IDs 0..81`: 26 base VT4 + 56 personalizados en `g_extra_players`), construidos los **57 modelos `.sdo` + `.zml`** (huesos `14/14` por modelo), 57 carpetas UV en `assets/face_uv_workspace/` y **69 DDS** (`photo_L`, `photo_eye`, `photo_S` para `59..81`).
- **Muestreo jugable en vivo (`test_roster_matrix.py --ids 59,63,73,78,79 --mv 3`)**: **5/5** (`59` Ben Shelton, `63` Coco Gauff, `73` Marcelo Ríos, `78` Rod Laver, `79` Arantxa Sánchez Vicario) cargan, juegan y sacan (`ok=True`, `ps=0`, `ex=0`, `exc=0`, `served=2`). Resto de nuevos IDs `59..81` (`60` Rublev, `61` Ruud, `62` Fritz, `64` Rybakina, `65` Badosa, `66` Halep, `67` Coria, `68` Gasquet, `69` Nishikori, `70` Söderling, `71` Berdych, `72` Chang, `74` Muster, `75` Bruguera, `76` Corretja, `77` Wilander, `80` Conchita Martínez, `81` Clijsters) integrados en DB, UI y `.sdo`/DDS a la espera de barrido individual en pista.

### Estado verificado: Nombres en Partido, Épocas, Miniaturas, Skins y Fase 3 (`TR_COMMON` + `photo_eye` + `EE-1/3/4`)
- **Fix completo de nombres en partido (`0x00668fa0`, `hk_StoLookup`)**: Reemplazo directo del selector `hk_SetFrawTableText` por hook único en `0x00668fa0` (verificando `TR_COMMON.sto` con `table 0, row 0 == "Roger Federer"`). Cubre todas las tablas de nombre (`0..13`, COI y apellidos/iniciales) para todos los IDs personalizados.
- **Agrupación de las 4 páginas por épocas (`src/xlive/xlive.c`)**:
  - `Página 1/4`: *Era Actual & Next-Gen (2015-2026)* (Big 3, Alcaraz, Sinner, Medvedev, Zverev, Tsitsipas, Thiem, Wawrinka, Murray, Del Potro, Kyrgios, Shelton `59`, Rublev `60`, Ruud `61`, Fritz `62`, Świątek, Sabalenka, Gauff `63`, Rybakina `64`, Muguruza, Badosa `65`, Halep `66`).
  - `Página 2/4`: *Era Dorada (2000s - 2010s)* (`Monfils`, `Gasquet 68`, `Nishikori 69`, `González`, `Haas`, `Söderling 70`, `Berdych 71`, `Serena`, `Sharapova`, `Hewitt`, `Safin`, `Kuerten`, `Ferrero`, `Moyá`, `Ferrer`, `Nalbandian`, `Coria 67`, `Tsonga`, `Roddick`, etc.).
  - `Página 3/4`: *Leyendas 90s & WTA Clásica* (`Sampras`, `Agassi`, `Courier`, `Becker`, `Edberg`, `Rafter`, `Ivanišević`, `Conchita 80`, `Venus`, `Wozniacki`, `Clijsters 81`, `Graf`, `Seles`, `Henin`, etc.).
  - `Página 4/4`: *Pioneros 60s-80s & Clásicos VT4* (`Borg`, `McEnroe`, `Lendl`, `Connors`, `Vilas`, `Chang 72`, `Ríos 73`, `Muster 74`, `Bruguera 75`, `Corretja 76`, `Wilander 77`, `Laver 78`, `Navratilova`, `Evert`, `Sánchez Vicario 79`, `Kuznetsova`, `Ivanovic`, `Chakvetadze`, `Robson`, `Kohlschreiber`, `Seppi`, `King`, `Duke`, `T. Tenniel`, `V. Virnie`).
- **Miniaturas de cuadrícula, `[F]` Agassi y `[R]` Arma EE-3 (`src/xlive/xlive.c`, `src/xlive/multiverse_modes.h`)**:
  - Generadas las 82 bandas de ojos (`photo_eye/0..81.dds`), miniaturas `photo_S` y retratos `photo_L` para todas las páginas.
  - Selector `[F]` en `CharaSelect` alternando entre `Agassi '91` (`P_M_AGA_LG.sdo`) y `Agassi '06` (`P_M_AG2_LG.sdo`), más tecla `[R]` y opción fila 11 `ARMA ARCADE (EE-3)` en `OPCIONES -> GRÁFICOS HD Y LEGENDS` (`NUM_SETTINGS_ITEMS = 13`).
  - Botón **`GRÁFICOS HD Y LEGENDS`** en el menú raíz `OPCIONES` integrado con estilo nativo (`opt_btn_unsel.png` / `opt_btn_sel.png`).
  - **EE-1 / EE-2 / EE-3 / EE-4 verificados en vivo**: `verify_full_release.py` + `test_options_ui.py` OK, y `verify_ee2_umpire_agassi91.py` (`ps=0 ex=0 exc=0 fase3=1`) confirmó visualmente en `02_match_ee2_split_court.png` la pista dividida **50% Hielo (`-Z`) / 50% Barro (`+Z`)** en RAM (`ee_patch_stage_ee2_surface`), el audio **WAV** (`ee1_protest`, `pan`, `ee1_lose`), y el retrato reparado de `Agassi '91` (`29_91` en `01_cs_agassi91_fixed.png`). Compilado posteriormente en `xlive.dll` el escape `100%%` de `EXTRA-1` y el filtro amplio `u_ump_b_` para el skin Meme del **Juez de Silla** (`umpire_meme.dds`, pendiente de captura visual final en silla).

### Caras UV 3D (`59/59` modelos `.sdo`), Retratos 2D (`84/84` color) y Talleres de Referencia
- **Modelos `.sdo` con caras UV 3D personalizadas (`59/59` completados en Fase 5)**:
  - Mediante `tools/studio_face_factory.py`, `tools/local_identity_uv.py`, `tools/fix_swapped_faces_v3b.py` y `tools/import_edited_face_uvs.py`, todos los **59 modelos `.sdo` personalizados** (`IDs 26..83` + `Agassi '91`) cuentan con geometría facial 3DMM esculpida, identidad facial transferida al UV 1024x1024, ojos HD 4x-supersampled (`_upgrade_hd_eyes`), pelo volumétrico 3D y escalado físico de huesos empaquetados en `game/archive/HIGH/Player/Model/`.
  - Los workspaces `assets/face_uv_workspace/` y `assets/face_uv_photocraft_workspace/` se conservan como base editable por si en futuras versiones (`v1.1+`) se desea retocar manualmente algún jugador concreto con PhotoCraft.
- **Taller de Retratos 2D (`assets/portraits_photocraft_workspace/`)**:
  - Preparado por `tools/prepare_portraits_workspace.py` con referencias oficiales de SEGA (`00_referencias_oficiales_sega/`), las 57 fotos originales completas (`01_originales_sin_recortar/`), el estado actual + hoja `AUDITORIA_57_ACTUALES.png` (`02_estado_actual_en_juego/`), guía completa `README_INSTRUCCIONES_PHOTOCRAFT.md` y carpetas de entrega `03_entregar_editados_aqui/` para importar con `py -u tools/import_edited_portraits.py`.
- **Retratos `photo_L` corregidos en último pase**: `29_91` Agassi '91, `43` Kyrgios, `44` Hewitt, `45` Safin, `47` Ferrero, `49` Ferrer y los 6 retratos históricos pasados a color (`51` Lendl, `52` Connors, `55` Evert, `74` Muster, `75` Bruguera, `77` Wilander), completando **84/84** retratos a color.

### Estado verificado (2026-11-25): Grand Slams, Retratos 2D, Marcadores TV Oficiales, Online P2P Nativo, Android & Controles
- **Roster completo `84` tenistas (`0..83`, incluye `82` M. Andreeva y `83` B.J. King)**: Verificado al 100% en pista; el barrido `test_roster_matrix.py --ids 60,61,62,64,65,66,67,68,69,70,71,72,74,75,76,77,80,81,82,83 --cpu 0 --mv 3` completó **20/20** (`ok=True`, `ps=0`, `ex=0`, `exc=0`, `served>=1`). Voice packs ampliados a `VP_MAX_ROSTER_IDS=84` (`tools/import_voice_packs.py`, `src/xlive/voice_packs.h`).
- **Estadios de Grand Slam en vivo (`tools/build_grand_slam_stages.py`)**: Generados e inyectados los 8 `.sdo` (S+D) de `Aus1` (Australian Open), `Fra1` (Roland Garros), `Eng1` (Wimbledon) y `Usa1` (US Open + `Usa1NS/D_locator.zml`, eliminada la moqueta fantasma `"O...S"` tanto en RGB como en Alpha especular), verificados los 4 en `VT4.exe` con `ps=0 ex=0 exc=0`.
- **Marcadores TV Oficiales en Vivo (`tools/build_official_scoreboards.py` + `src/xlive/broadcast_hud.h`)**: Temas modulares `ao`, `rg`, `wim`, `uso`, `mad`, `tour` + atlas de 27 banderas IOC + lectura directa de RAM (`Match*` `+0x04 -> TennisStatus*`, sets, juegos, puntos/ventajas, saque, reloj, Break/Set/Match Point, radar `km/h` y rally), verificados en vivo en Wimbledon, US Open y Roland-Garros.
- **Fix pantalla de carga (`0x0043CAC9` + `hk_StoLookup`)**: Interceptado `hk_Loading_SetPlayerPhoto` antes de `0x006693E9` para restaurar el ID real antes del módulo `26` (corregidos casos como `82` Andreeva -> `Del Potro` y `43` Kyrgios -> `Sharapova`), más mapeo completo de tablas bio (`9` revés, `10` nacimiento, `11..14`).
- **Fix resto con teclado (`sample_p1_override_input`)**: Detecta estado del jugador (`Player + 0x248`) para admitir pulsación anticipada/mantenida y buffer de 20 ticks en estados de resto/peloteo `4..9`, manteniendo limpio el timing del saque en estados `2..3`.
- **Display Interactivo Xbox para Android (`src/xlive/touch_gamepad.h`)**: Controles táctiles translúcidos estilo Recomp (`TouchXboxHUD=0|1|2` en `OPCIONES -> GRÁFICOS HD Y LEGENDS` o tecla `[F6]`) con auto-detección de Android/Wine y soporte táctil + ratón.
- **Menú `EN LÍNEA` nativo VT4 + Auto-Descubrimiento LAN (`tools/build_netplay_ui_assets.py` + `src/xlive/netplay.h`)**: Pantalla completa nacarada/púrpura fiel a VT4 con escaneo LAN UDP (`NP_PKT_DISCOVER` / `NP_PKT_OFFER`) y HUD movido a la esquina superior derecha para no chocar con el marcador TV.
- **Retratos 2D (`84/84` a color — cierre `v1.0-RC1`)**:
  - `tools/fix_remaining_portraits_2026.py`: recortados y empaquetados (`photo_L`, `photo_eye`, `photo_S`) los 7 retratos (`43`, `52`, `58`, `67`, `72`, `82`, `83`).
  - `tools/pack_colorized_bw_portraits.py`: recuperados a todo color y empaquetados los últimos 6 retratos (`51` Lendl, `52` Connors, `55` Evert, `74` Muster, `75` Bruguera, `77` Wilander), verificados visualmente en `scratch/bw_colorized_audit.png` (`262,272` B BGRA, esquinas transparentes y `photo_eye` centrado).
- **Lanzador Nativo Android (`src/launcher/play_vt4_legends.c` + `tools/export_android_bundle.py`)**:
  - Integrada compilación directa de `PLAY_VT4_LEGENDS.exe` + `LAUNCH_ANDROID.bat` síncrono + guía de 1 toque para GameHub y Winlator CMod/Frost; bundle reexportado (`3.62 GB`, `490` archivos, `0` fallos case-sensitive) y verificado en Windows con smoke-test síncrono (`0` procesos/logs residuales).
- **Barrido QA de cierre y Release `v1.0` (2026-11-26)**:
  - Verificado en vivo `scratch/verify_v1_final_qa.py` (6 retratos recién coloreados `74, 75, 51, 52, 77, 55` en `CharaSelect` + partido en vivo con `BroadcastHUD=1` + `EXTRA-1: Unlocked 100%` + audio nativo `XAudio2` activo, `ps=0 ex=0 exc=0`) y `tools/tests/test_options_ui.py` (`4` PNG válidos).
  - Auditados **59/59** modelos `.sdo` personalizados con sus caras UV 3D + ojos HD, renovado `README.md` estilo decomp/recomp con galería en `docs/screenshots/`, redactado `RELEASE_NOTES_v1.0.md` y etiquetado **`v1.0`**.

---

## 🎨 Para más tarde: Skins Características `[F]` y Voces

Workspace con muestras descriptivas y listas de archivos generadas por `tools/prepare_future_assets_workspaces.py`:
- **Skins alt `[F]` (`assets/skins_alt_workspace/` — 14 carpetas)**:
  - **Carlos Alcaraz (`26_ALC_USOpen2026`)**: US Open 2026 Nike Knicks sin mangas morado azulado / naranja / negro + pantalón negro (`P_M_AL2_NG.sdo`).
  - **Jannik Sinner (`27_SIN_RomaNegro`)**: Roma / Internazionali d'Italia **negro entero** (`P_M_SI2_NG.sdo`).
  - **Federer (`00` Wimbledon 2007 blanca/dorada)**, **Nadal (`01` RG 2008 sin mangas verde lima + piratas)**, **Djokovic (`02` AO 2019 Lacoste azul marino/blanco)**, **Sampras (`28` US Open '95 blanco)**, **Borg (`30` Wimbledon '80 Fila rayas)**, **McEnroe (`31` Wimbledon '81 Tacchini)**, **Graf (`32` Adidas '95)**, **Serena (`33` US Open 2018 tutú negro)**, **Swiatek (`34` RG 2024 On Running degradado rosa/tierra)**, **Sabalenka (`35` US Open 2024 fucsia)**, **Kyrgios (`43` Wimbledon 2022 blanco + gorra/zapatillas rojas)**, **Andreeva (`82` Tour 2026 azul celeste/blanco)**.
  - *Archivos necesarios por carpeta*: `ref_kit_front.png`, `body_diffuse_1024.png` (1024x1024 RGBA), `body_spec_mask.png` *(opc.)*, `shoes_bands_512.png` *(opc.)*, `photo_L_alt.png` (256x256), `photo_S_alt.png` (128x128), `photo_eye_alt.png` (256x64).
- **6 Retratos B&N (`assets/bw_portraits_pending/`)**: **COMPLETADOS (`84/84` a color en `v1.0-RC1`)** — `51_LEN`, `52_CON`, `55_EVE`, `74_MUS`, `75_BRU`, `77_WLD` empaquetados por `tools/pack_colorized_bw_portraits.py` (ver `assets/bw_portraits_pending/LEEME_6_RETRATOS_BN.txt`).
- **Packs de voces (`assets/voices_workspace/`)**: 18 carpetas icónicas (incluyendo `82_AND` y `83_BJK`) con notas de muestra en cada evento (`grunt/`, `serve/`, `point_win/`, `point_lose/`, `protest/`, `match_win/`, `vs_*/`).
- **HUD TV Moderno (`[F7]`), Estadísticas Individuales (`26..83`) y Físicas/Superficies (`src/xlive/broadcast_hud.h`, `src/xlive/player_stats.h`, `src/xlive/xlive.c`, `game/archive/Config/Fraw/fwDataDB/fwDataDB_Stage.txt`)**:
  - **HUD Broadcast TV** en esquina superior izquierda (`BroadcastHUD`, conmutable con `[F7]` y fila de Opciones): muestra torneo/superficie, emparejamiento, velocidad en vivo (`km/h` calibrado con el radar nativo) y contador de `RALLY`.
  - **Stats individuales** (`player_stats.h`) aplicados en tiempo real para todos los jugadores personalizados `26..83` vía `PlayStyle::LoadInner` + `ServeMax`.
  - **Rebote/velocidad por superficie** diferenciados en `fwDataDB_Stage.txt` (`Fra1` arcilla `0.95/0.70`, `Eng1` hierba `0.58/0.90`, `Aus1` `0.84/0.83`, `Usa1` `0.86/0.84`, `Spa2` `0.86/0.80`) y modo opcional `ProPhysics` (`vt4_settings.ini`) en la simulación de trayectoria de bola.

