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
- [ ] **01. Roger Federer (SUI)** — Diestro (Revés 1M) | *Todoterreno Ofensivo / Volea* (Ajuste a stats Prime)
- [ ] **02. Rafael Nadal (ESP)** — Zurdo (Revés 2M) | *Físico Indestructible / Topspin Extremo* (Ajuste a stats Prime)
- [ ] **03. Novak Djokovic (SRB)** — Diestro (Revés 2M) | *Contragolpeador Elástico / Restador Total* (Ajuste a stats Prime)
- [ ] **04. Andy Murray (GBR)** — Diestro (Revés 2M) | *Táctico Defensivo / Passing Shots*
- [ ] **05. Stan Wawrinka (SUI)** — Diestro (Revés 1M) | *Cañonero de Fondo (Strong Backhand)*
- [ ] **06. Juan Martín del Potro (ARG)** — Diestro (Revés 2M) | *Derecha Demoledora (Hard Hitter)*

### II. La Nueva Era ("Next-Gen" & Actualidad hasta 2026)
- [ ] **07. Carlos Alcaraz (ESP)** — Diestro (Revés 2M) | *Todoterreno Explosivo / Rey de la Dejada*
- [ ] **08. Jannik Sinner (ITA)** — Diestro (Revés 2M) | *Golpeador de Ritmo Frenético*
- [ ] **09. Daniil Medvedev (RUS)** — Diestro (Revés 2M) | *Muro Heterodoxo / Contragolpeador Profundo*
- [ ] **10. Alexander Zverev (GER)** — Diestro (Revés 2M) | *Gran Sacador + Potencia de Revés*
- [ ] **11. Stefanos Tsitsipas (GRE)** — Diestro (Revés 1M) | *Ataque de Derecha y Red*
- [ ] **12. Dominic Thiem (AUT)** — Diestro (Revés 1M) | *Potencia Pesada en Tierra Batida*
- [ ] **13. Nick Kyrgios (AUS)** — Diestro (Revés 2M) | *Impredecible / Gran Sacador / Saque por debajo*
- [ ] **14. Ben Shelton (USA)** — Zurdo (Revés 2M) | *Cañonero Zurdo (Big Server)*

### III. Leyendas de los 2000s y 2010s (La Guardia Clásica)
- [ ] **15. Andy Roddick (USA)** — Diestro (Revés 2M) | *Gran Sacador (249 km/h) + Derecha*
- [ ] **16. Lleyton Hewitt (AUS)** — Diestro (Revés 2M) | *Velocista Incansable / Globos y Passing*
- [ ] **17. Marat Safin (RUS)** — Diestro (Revés 2M) | *Potencia Pura / Revés a dos manos letal*
- [ ] **18. Gustavo "Guga" Kuerten (BRA)** — Diestro (Revés 1M) | *Rey de la Tierra / Revés Liftado 1M*
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
- [ ] **31. Pete Sampras (USA)** — Diestro (Revés 1M) | *Saque y Volea Definitivo + Smash en Salto*
- [ ] **32. Andre Agassi (USA)** — Diestro (Revés 2M) | *El Mejor Restador / Ataque de Fondo*
- [ ] **33. Jim Courier (USA)** — Diestro (Revés 2M) | *Fuerza Bruta desde el Fondo* (Desbloqueado de serie)
- [ ] **34. Boris Becker (GER)** — Diestro (Revés 1M) | *"Boom Boom" (Saque + Volea en Plancha)* (Desbloqueado de serie)
- [ ] **35. Stefan Edberg (SWE)** — Diestro (Revés 1M) | *Saque Kick y Volea Elegante* (Desbloqueado de serie)
- [ ] **36. Goran Ivanišević (CRO)** — Zurdo (Revés 2M) | *Rey del Ace (Saque Zurdo Inalcanzable)*
- [ ] **37. Michael Chang (USA)** — Diestro (Revés 2M) | *Velocidad Extrema y Espíritu de Lucha*
- [ ] **38. Marcelo "Chino" Ríos (CHI)** — Zurdo (Revés 2M) | *Talento Puro / Ángulos y Dejadas*
- [ ] **39. Thomas Muster (AUT)** — Zurdo (Revés 1M) | *La Bestia de la Tierra Batida*
- [ ] **40. Sergi Bruguera / Alex Corretja / Patrick Rafter** — Leyendas de Grand Slam 90s

### V. Los Pioneros (Años 70 y 80) + Jefes SEGA
- [ ] **41. Björn Borg (SWE)** — Diestro (Revés 2M) | *El Hombre de Hielo (Resistencia infinita + Topspin)*
- [ ] **42. John McEnroe (USA)** — Zurdo (Revés 1M) | *Toque Mágico en la Red + Saque de Espaldas*
- [ ] **43. Ivan Lendl (CZE/USA)** — Diestro (Revés 1M) | *Padre del Tenis Moderno de Potencia*
- [ ] **44. Jimmy Connors (USA)** — Zurdo (Revés 2M) | *Golpeo Plano Rasante y Agresividad Total*
- [ ] **45. Mats Wilander (SWE)** — Diestro (Revés 2M) | *Táctico de Acero*
- [ ] **46. Guillermo Vilas (ARG)** — Zurdo (Revés 1M) | *El Gran Willy / Topspin Eterno*
- [ ] **47. Rod Laver (AUS)** — Zurdo (Revés 1M) | *The Rocket (El único doble Grand Slam)*
- [x] **48. King & Duke (SEGA Bosses)** — Jefes finales míticos de *Virtua Tennis* (Desbloqueados de serie vía parche `FUN_005dfe90`)

### VI. Leyendas WTA (Las Grandes Reinas de la Historia)
- [ ] **49. Serena Williams (USA)** — *Potencia y Saque Total*
- [ ] **50. Steffi Graf (GER)** — *Golden Slam (Derecha Invertida + Revés Cortado Letal)*
- [ ] **51. Martina Navratilova (USA)** — *Zurda de Saque y Volea Implacable*
- [ ] **52. Chris Evert (USA)** — *Precisión Milimétrica de Fondo*
- [ ] **53. Monica Seles (YUG/USA)** — *Doble Golpe a Dos Manos Ultra-Agresivo*
- [ ] **54. Arantxa Sánchez Vicario (ESP)** — *Defensa Imposible en Tierra Batida*
- [ ] **55. Conchita Martínez (ESP)** — *Maestra del Efecto y Variedad*
- [ ] **56. Garbiñe Muguruza (ESP)** — *Golpeo Plano y Agresivo*
- [ ] **57. Venus Williams (USA)** — *Gran Sacadora y Envergadura*
- [ ] **58. Maria Sharapova (RUS)** — *Cañonera sin Cuartel*
- [ ] **59. Justine Henin (BEL)** — *El Mejor Revés a Una Mano Femenino*
- [ ] **60. Kim Clijsters (BEL)** — *Elasticidad y Potencia*
- [ ] **61. Caroline Wozniacki / Ana Ivanovic / Svetlana Kuznetsova / Laura Robson** *(Base VT4)*
- [ ] **62. Iga Świątek (POL)** — *Topspin y Dominio Absoluto en Tierra*
- [ ] **63. Aryna Sabalenka (BLR)** — *Potencia Bruta Actual*
- [ ] **64. Paula Badosa / Simona Halep** — *Circuito Moderno WTA*

---

## 🤪 Fase 3: Cinco Easter Eggs Legendarios (Modo Extra "Multiverso Arcade")
- [ ] **EE-1: 🔥 Modo McEnroe Desatado ("¡YOU CANNOT BE SERIOUS!")** — Botón de protesta al juez de silla en bolas cercanas a la línea con minijuego de intimidación arbitral y lanzamiento de raqueta.
- [ ] **EE-2: 🥖 La Batalla de las Superficies Extrema (50% Barro / 50% Hielo)** — Mitad de pista con bote ultra-alto y frenado, mitad con hielo resbaladizo y bote rasante ultrarrápido.
- [ ] **EE-3: 🪵 Modo Raqueta de Madera vs. Sartén de Cocina (Homenaje a Roddick)** — Selector de arma/handicap (raqueta de los 70, sartén metálica, paraguas, baguette gigante) con efectos de sonido e impacto propios.
- [ ] **EE-4: ⚡ Super Golpes DBZ / Mario Power Tennis (Barra VT al 300%)** — Super Shots con físicas extremas (dejada bumerán de Alcaraz que regresa a su campo, Banana Shot de fuego de Nadal, saque supersónico de Roddick/Ivanišević).
- [ ] **EE-5: 🤖 Jefes Secretos Jugables (Juez de Silla motorizado, Recogepelotas Turbo & Matt de Wii Sports)** — Personajes secretos desbloqueables para exhibición.

---

## 🛠️ Fase 4: Funcionalidades Extra (Quality of Life & Motor)
- [ ] **EXTRA-1: Desbloqueo 100% Instantáneo** — Todos los personajes ocultos (Becker, Edberg, Courier, King, Duke), estadios y equipamiento del catálogo SPT desbloqueados desde el inicio.
- [ ] **EXTRA-2: Fijador de Cámara TV Clásica (VT2 Style)** — Desactivar los zooms en primera persona y cambios bruscos de cámara durante los Super Shots.
- [ ] **EXTRA-3: Grand Slams Oficiales & Pista Azul de Madrid** — Nombres y texturas reales para Australian Open, Roland Garros, Wimbledon, US Open y Mutua Madrid Open (Tierra Azul).
- [ ] **EXTRA-4: Selector de Velocidad de Física ("Modo VT2 Arcade Turbo" vs "Simulación")** — Multiplicador configurable de velocidad de bola y desplazamiento.
- [ ] **EXTRA-5: Partidos a 5 Sets Reales de 6 Juegos + Tie-Break / Super Tie-Break** — Desbloqueo de reglas completas de torneo en Exhibición.
- [ ] **EXTRA-6: Parche 4K & Alto Framerate** — Resolución nativa moderna y eliminación de filtros de borrosidad (*bloom/blur* excesivo).
