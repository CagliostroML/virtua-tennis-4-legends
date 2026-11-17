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
- [ ] **05. Stan Wawrinka (SUI)** — Diestro (Revés 1M) | *Cañonero de Fondo (Strong Backhand)*
- [x] **06. Juan Martín del Potro (ARG)** — Diestro (Revés 2M) | *Derecha Demoledora (Hard Hitter)* (Stats Prime aplicados en `fwDataDB_Player`)

### II. La Nueva Era ("Next-Gen" & Actualidad hasta 2026)
- [x] **07. Carlos Alcaraz (ESP)** — Diestro (Revés 2M) | *Todoterreno Explosivo / Rey de la Dejada* (`ID 26`, `P_M_ALC_NG.sdo`, retrato `photo_L/26.dds` sin viñeta vía PhotoCraft, jugable y verificado en partido con `0` asserts)
- [x] **08. Jannik Sinner (ITA)** — Diestro (Revés 2M) | *Golpeador de Ritmo Frenético* (`ID 27`, `P_M_SIN_NG.sdo`, retrato `photo_L/27.dds` sin viñeta vía PhotoCraft, jugable y verificado en partido con `0` asserts)
- [ ] **09. Daniil Medvedev (RUS)** — Diestro (Revés 2M) | *Muro Heterodoxo / Contragolpeador Profundo*
- [ ] **10. Alexander Zverev (GER)** — Diestro (Revés 2M) | *Gran Sacador + Potencia de Revés*
- [ ] **11. Stefanos Tsitsipas (GRE)** — Diestro (Revés 1M) | *Ataque de Derecha y Red*
- [ ] **12. Dominic Thiem (AUT)** — Diestro (Revés 1M) | *Potencia Pesada en Tierra Batida*
- [ ] **13. Nick Kyrgios (AUS)** — Diestro (Revés 2M) | *Impredecible / Gran Sacador / Saque por debajo*
- [ ] **14. Ben Shelton (USA)** — Zurdo (Revés 2M) | *Cañonero Zurdo (Big Server)*

### III. Leyendas de los 2000s y 2010s (La Guardia Clásica)
- [x] **15. Andy Roddick (USA)** — Diestro (Revés 2M) | *Gran Sacador (249 km/h) + Derecha* (Stats Prime aplicados en `fwDataDB_Player`)
- [ ] **16. Lleyton Hewitt (AUS)** — Diestro (Revés 2M) | *Velocista Incansable / Globos y Passing*
- [ ] **17. Marat Safin (RUS)** — Diestro (Revés 2M) | *Potencia Pura / Revés a dos manos letal*
- [x] **18. Gustavo "Guga" Kuerten (BRA)** — Diestro (Revés 1M) | *Rey de la Tierra / Revés Liftado 1M* (`ID 36`, foto real `photo_L/36.dds`, modelo `P_M_KUE_LG.sdo` y Página 2)
- [ ] **19. Juan Carlos Ferrero (ESP)** — Diestro (Revés 2M) | *El Mosquito (Velocidad + Derecha Cruzada)*
- [ ] **20. Carlos Moyá (ESP)** — Diestro (Revés 2M) | *Derecha Invertida Demoledora*
- [ ] **21. David Ferrer (ESP)** — Diestro (Revés 2M) | *Muro Físico / Restador Incansable*
- [ ] **22. David Nalbandian (ARG)** — Diestro (Revés 2M) | *Ángulos Imposibles / Revés Cruzado*
- [ ] **23. Guillermo Coria (ARG)** — Diestro (Revés 2M) | *El Mago (Dejadas + Velocidad en Tierra)*
- [ ] **24. Jo-Wilfried Tsonga (FRA)** — Diestro (Revés 2M) | *Tenis Espectáculo (Saque + Derecha + Red)*
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
- [ ] **36. Goran Ivanišević (CRO)** — Zurdo (Revés 2M) | *Rey del Ace (Saque Zurdo Inalcanzable)*
- [ ] **37. Michael Chang (USA)** — Diestro (Revés 2M) | *Velocidad Extrema y Espíritu de Lucha*
- [ ] **38. Marcelo "Chino" Ríos (CHI)** — Zurdo (Revés 2M) | *Talento Puro / Ángulos y Dejadas*
- [ ] **39. Thomas Muster (AUT)** — Zurdo (Revés 1M) | *La Bestia de la Tierra Batida*
- [x] **40. Sergi Bruguera / Alex Corretja / Patrick Rafter** — Leyendas de Grand Slam 90s (*Patrick Rafter*: stats Prime en `fwDataDB_Player` + Página 2 `g_roster_page_legends`; pendientes Bruguera / Corretja)

### V. Los Pioneros (Años 70 y 80) + Jefes SEGA
- [x] **41. Björn Borg (SWE)** — Diestro (Revés 2M) | *El Hombre de Hielo (Resistencia infinita + Topspin)* (`ID 30`, foto real `photo_L/30.dds`, modelo `P_M_BOR_LG.sdo` y Página 2)
- [x] **42. John McEnroe (USA)** — Zurdo (Revés 1M) | *Toque Mágico en la Red + Saque de Espaldas* (`ID 31`, foto real `photo_L/31.dds`, modelo `P_M_MCE_LG.sdo` y Página 2)
- [ ] **43. Ivan Lendl (CZE/USA)** — Diestro (Revés 1M) | *Padre del Tenis Moderno de Potencia*
- [ ] **44. Jimmy Connors (USA)** — Zurdo (Revés 2M) | *Golpeo Plano Rasante y Agresividad Total*
- [ ] **45. Mats Wilander (SWE)** — Diestro (Revés 2M) | *Táctico de Acero*
- [ ] **46. Guillermo Vilas (ARG)** — Zurdo (Revés 1M) | *El Gran Willy / Topspin Eterno*
- [ ] **47. Rod Laver (AUS)** — Zurdo (Revés 1M) | *The Rocket (El único doble Grand Slam)*
- [x] **48. King & Duke (SEGA Bosses)** — Jefes finales míticos de *Virtua Tennis* (Desbloqueados de serie vía parche `FUN_005dfe90`)

### VI. Leyendas WTA (Las Grandes Reinas de la Historia)
- [x] **49. Serena Williams (USA)** — *Potencia y Saque Total* (`ID 33`, foto real `photo_L/33.dds`, modelo `P_W_SER_NG.sdo` y Página 2)
- [x] **50. Steffi Graf (GER)** — *Golden Slam (Derecha Invertida + Revés Cortado Letal)* (`ID 32`, foto real `photo_L/32.dds`, modelo `P_W_GRA_LG.sdo` y Página 2)
- [x] **51. Martina Navratilova (USA)** — *Zurda de Saque y Volea Implacable* (`ID 37`, foto real `photo_L/37.dds`, modelo `P_W_NAV_LG.sdo` y Página 2)
- [ ] **52. Chris Evert (USA)** — *Precisión Milimétrica de Fondo*
- [ ] **53. Monica Seles (YUG/USA)** — *Doble Golpe a Dos Manos Ultra-Agresivo*
- [ ] **54. Arantxa Sánchez Vicario (ESP)** — *Defensa Imposible en Tierra Batida*
- [ ] **55. Conchita Martínez (ESP)** — *Maestra del Efecto y Variedad*
- [ ] **56. Garbiñe Muguruza (ESP)** — *Golpeo Plano y Agresivo*
- [ ] **57. Venus Williams (USA)** — *Gran Sacadora y Envergadura*
- [ ] **58. Maria Sharapova (RUS)** — *Cañonera sin Cuartel*
- [ ] **59. Justine Henin (BEL)** — *El Mejor Revés a Una Mano Femenino*
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
