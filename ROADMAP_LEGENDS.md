# Hoja de Ruta: Virtua Tennis 4 - Legends & Next-Gen Edition

Este documento establece la arquitectura técnica y el plan de ejecución por fases para transformar *Virtua Tennis 4* en la edición definitiva: resolución HD nativa en 3D, eliminación total de bordes de sierra, integración del menú de ajustes gráficos in-game, remasterización de texturas con Nano Banana, selector de personajes ampliado, incorporación de leyendas modernas y portabilidad futura.

---

## 1. Estado Actual (Fase 1 Completada)
- [x] **Emulación Games for Windows LIVE (GFWL)**: Integrada al 100% en `xlive.dll` (perfil local automático, guardado de partidas en disco sin registro de Windows ni conexión externa).
- [x] **Bypass de vídeos y deadlocks regionales**: Eliminado el bloqueo del selector de idioma europeo/ESRB y el atasco de reproducción de secuencias de vídeo intro.
- [x] **Pantalla completa sin bordes y menús HD**: 1080p, 2K y 4K con interfaz nítida y ventana sin bordes gestionada en `vt4_settings.ini`.
- [x] **Controles y Navegación Universal**: Mapeo completo de teclado (WASD, flechas, Enter, Espacio, Esc) y recuperación de foco al alternar ventanas (Alt+Tab).
- [x] **Estabilidad de Modos Arcade y Exhibición**: Protección contra fallos nulos en `fwFormat` y nodos de jerarquía de interfaz.

---

## 2. Fase 1B: Remasterización Gráfica HD Total & Menú de Ajustes In-Game (Completada)
- [x] **Escalado del RenderTarget 3D Interno (Full HD / 2K / 4K)**:
  - Intercepción completa en `Renderer::CalcPipelineSettings` (`0x004b09c0`) y métodos Direct3D 9 (`CreateRenderTarget`, `CreateDepthStencilSurface`, `CreateTexture`, `SetViewport`) para computar la escena 3D a resolución nativa (`1920x1080`, `2560x1440`, `3840x2160`), erradicando definitivamente el renderizado interno a 640x512 y el estiramiento borroso.
- [x] **Anti-Aliasing Real en Geometría 3D (MSAA)**:
  - Activado `D3DRS_MULTISAMPLEANTIALIAS` y `D3DRS_ANTIALIASEDLINEENABLE` en `hk_BeginScene` con búferes multitemuestra reales (`D3DMULTISAMPLE_TYPE`), eliminando los dientes de sierra en siluetas de jugadores, pista y red.
- [x] **Sombras de Ultra Alta Resolución (2048x2048)**:
  - Mapas de sombras escalados de 512x512 a **2048x2048** con viewports sincronizados a 2048x2048 para sombras suaves y definidas sin pixelación.
- [x] **Filtrado Anisotrópico 16x Permanente**:
  - Forzado `D3DSAMP_MAXANISOTROPY = 16` y `D3DTEXF_ANISOTROPIC` en todas las etapas de textura (samplers 0 a 7), garantizando líneas de fondo nítidas en ángulos rasantes.
- [x] **Menú de Ajustes Gráficos In-Game & Sincronización Bidireccional**:
  - Interfaz gráfica superpuesta (HUD) Direct3D 9 con renderizado tipográfico anti-aliasing (`ID3DXFont`), cajas translúcidas y navegación con teclado (WASD / Flechas / Enter / Espacio / Esc) y mando:
    - **Resolución**: Selector interactivo (1080p Full HD, 1440p 2K, 4K UHD, 720p HD).
    - **Modo de pantalla**: Pantalla completa sin bordes / Modo ventana con reajuste en caliente.
    - **Anti-Aliasing 3D (MSAA)**: Desactivado / 2x / 4x / 8x Ultra.
    - **Sincronización Vertical (VSync)**: Activado (60 FPS) / Desactivado.
    - **Filtrado Anisotrópico**: Desactivado / 4x / 8x / 16x Ultra.
    - **Ocultar Modo LIVE**: Activado (Recomendado) / Desactivado.
  - Sincronización bidireccional automática: guardado instantáneo en `vt4_settings.ini` y `game/save/Config.txt` con aplicación en tiempo real y banner de confirmación.
  - Accesible desde la opción **Ajustes / Opciones (`OptionMode`)** del juego o pulsando **F2** en cualquier momento.

---

## 3. Fase 2: Rediseño del Selector de Personajes & Activación de Leyendas (Completada)
El selector original de VT4 cuenta con una cuadrícula fija de 24 casillas (`FPCharaSelect`):
- [x] **Desbloqueo Universal de Leyendas y Jefes**:
  - Parcheado el método de validación `FUN_005dfe90` (retorna siempre `TRUE`), desbloqueando de inmediato a King, Duke y todas las figuras bloqueadas.
- [x] **Asignación de Leyendas en Cuadrícula (`0x007c5f6c`)**:
  - Casillas 21, 22 y 23 reasignadas a **Boris Becker (ID 11)**, **Patrick Rafter (ID 12)** y **Stefan Edberg (ID 14)**, reemplazando los slots duplicados `EDIT00`/`EDIT01`.
- [x] **Transición Fluida a Selección de Personajes (`0x005f62e9`)**:
  - Parcheado `FPPlayerEntry::IsReady` (`0x005f62d0`) para avanzar automáticamente tras 30 fotogramas desde Selección de Posición de Pista al Selector de Personajes sin fricción ni bloqueos.
- [x] **Verificación Visual In-Game en 1080p**:
  - Validado el renderizado en tiempo real de los modelos 3D y retratos de Boris Becker (polo Puma blanco clásico), Patrick Rafter (camiseta sin mangas Reebok) y Stefan Edberg (equipación Adidas clásica).

---

## 4. Fase 3: Cargador de Archivos Sueltos (Loose File Loader) & Remasterización con Nano Banana (En Curso)
1. **Cargador Transparente de Archivos Sueltos (`game/archive/`) - Implementado y Verificado**:
   - Intercepción de bajo nivel en `xlive.dll` sin alterar los 3.2 GB originales de `resource.bin` / `resource.1.bin`:
     - `Archive::OpenFile` (`0x004079c4` -> `hk_Archive_CheckDirectory`) y `ArchiveDir::FindIndex` (`0x00407380` -> `hk_ArchiveDir_FindIndex`): detectan reemplazos en `game/archive/` (incluidos archivos dentro de subcontenedores donde `vol == -1`) y redirigen al cargador de disco.
     - Corrección de descompresión en `AsyncLoader` (`0x0040c763` con 7 NOPs y `0x0040c589` limpiando `[esi+0xa9] = 0` en `AsyncLoader::CloseSlot`): evita que archivos sueltos sin comprimir pasen por el descompresor LZSS (`0x0040bc00`) al reutilizar un slot.
     - `CreateFileA` (IAT `0x00788078`): redirección física de lectura de disco hacia `game/archive/`.
     - `fopen_s` / `fopen` (IAT `0x007883c8`, `0x00788414`): redirección de flujos CRT.
     - `PathFileExistsA` (IAT `0x00788464`): detección transparente de archivos modificados.
     - **Compilador y Verificador `fwDataDB` (`tools/compile_fwdatadb.py`)**: compila/decompila `.txt` <-> `.bin` con finales de línea LF y verificación exacta byte-a-byte (`30,128` bytes frente a `fwDataDB_Player.bin`), coexistiendo con el bypass `.bin` -> `.txt` cuando se suministra texto suelto (`fwDataDB_Stage.txt`).
2. **Pipeline de Remasterización de Texturas con Nano Banana (AI Upscaling / Generative Diffusion)**:
   - Extracción masiva de texturas base (`.txp`, `.dds`, `.bin`) de pistas, redes, vestimentas, pieles y raquetas.
   - Procesamiento con **Nano Banana** y modelos generativos de ultra alta resolución para escalar las texturas originales a **2K y 4K**, preservando costuras (*UV seams*), mapas normales y mapas de especularidad.
   - Carga transparente desde la carpeta de archivos sueltos `game/archive/` sin modificar los binarios originales de Sega.
2. **Pipeline de Modelos 3D Next-Gen (`asset-pipeline`)**:
   - Extracción de geometrías de jugadores base (`.mdl` / `.bin`) con herramientas de decompilación y Blender.
   - Modelado y texturizado de nuevas figuras con alta carga poligonal: Carlos Alcaraz, Jannik Sinner, Novak Djokovic (versión moderna), Rafael Nadal (Prime), Roger Federer (Prime), Aryna Sabalenka, Iga Świątek.
3. **Equipamiento Oficial Actual**:
   - Raquetas Babolat Pure Aero, Head Speed, Wilson Pro Staff recreadas en alta resolución.
   - Ropa con patrocinadores actuales (Nike, Lacoste, Uniqlo).

---

## 5. Fase 4: Físicas, Animaciones y Pistas de Grand Slam
1. **Animaciones de Golpeo**:
   - Ajuste de cinemáticas de derecha (*forehand* con efecto látigo de Alcaraz, revés a dos manos plano de Sinner).
2. **Superficies - Implementado (`fwDataDB_Stage.txt`)**:
   - Configuración diferenciada de bote y velocidad (`BoundY` / `BoundXZ`) por superficie (`CLAY`, `GRASS`, `HARD`, `INDOOR`) en `game/archive/Config/Fraw/fwDataDB/fwDataDB_Stage.txt`.
   - Todas las pistas desbloqueadas desde el inicio (`Lock = -1` en los 43 registros, incluidos los 32 estadios principales antes de `MinA`; los 27 slots de la cuadrícula de Exhibición verificados sin candado).

---

## 6. Fase 5: Exportación y Portabilidad a Android (Mejores Prácticas)
El proyecto contempla como requisito oficial que el mod sea **exportable a Android** siguiendo las mejores prácticas vigentes (a contrastar y validar mediante investigación online actualizada antes de la implementación).

### Estrategia Principal (Recomendada): Bundle Portable + Winlator (Bionic/Cmod) / GameNative / APK Contenedor
Gracias a la eliminación completa de GFWL, el guardado local sin registro de Windows y el parcheo limpio de Direct3D 9, nuestra edición de PC (`VT4.exe` + `xlive.dll` + `game/archive/`) es ejecutable directamente en Android mediante capas de traducción modernas sin reescribir el motor:
- **Stack objetivo a validar online**: **Wine (WoW64)** + **Box64 / FEXCore** + **DXVK (D3D9 → Vulkan)** con drivers **Turnip** (Snapdragon/Adreno) y fallback **Vortek/VirGL** (Mali/otros), más audio **ALSA-Reflector** para `XAudio2_7.dll`.
- **Formato tipo app (APK + datos/OBB)**:
  - **Vía rápida y mantenible**: generar un bundle portable limpio (`tools/export_android_bundle.py`) listo para **Winlator Bionic/Cmod** o **GameNative**, usando la exportación nativa de **acceso directo como APK standalone** para abrir el juego directamente desde la pantalla de inicio.
  - **Vía APK + OBB / datos autocontenido**: empaquetar un runtime open-source embebido + datos del juego gestionados conforme a **Android 14/15/16 (Scoped Storage)**, evitando cuello de botella de **FUSE** y bloqueos de `/Android/obb` (almacenamiento privado de la app / `getExternalFilesDir()`, partición `main` + `patch` si se emplea OBB por los ~3,2 GB de `resource.bin` + `resource.1.bin`, y caché de shaders DXVK siempre en ruta escribible).
- **Requisitos técnicos del mod para Android**:
  - Perfil gráfico ligero en `vt4_settings.ini` (`720p`, MSAA desactivado, sombras ajustables, `VSync=1`) y `dxvk.conf` para 60 FPS estables sin estrangulamiento térmico.
  - *DLL overrides* documentados (`xlive=n`, `d3dx9_43=n`, `xaudio2_7=n`) y auditoría de *case-sensitivity* en rutas de `game/archive/`.
  - Soporte plug-and-play para mandos Bluetooth/USB-C (XInput) y perfil de controles táctiles mapeado a acciones de pista y atajos del mod.
  - Distribución responsable: separar el parche/mod de los archivos propietarios originales de SEGA.

### Rutas No Prioritarias / Descartadas a Corto Plazo
- **APK 100% nativo ARM (Decompilación / Recompilación estática de `VT4.exe`)**: Requeriría decompilar o recompilar estáticamente un binario Windows x86 de 5 MB, portar Direct3D 9/XAudio2 a Vulkan/Android NDK y reescribir los hooks de `xlive.c`; queda fuera del alcance práctico a corto/medio plazo.
- **Binario ARM de PS Vita**: Los cargadores de comunidad estilo *Rinnegatamante/TheFlow* cargan `.so` de Android en PS Vita (el sentido inverso); ejecutar VT4 de Vita en Android equivale a usar un emulador como **Vita3K**, que además no incorporaría nuestro mod de PC.
- **Nintendo Wii**: No es posible compilar la versión PC/x86 para Wii (PowerPC 729 MHz, 88 MB RAM, GPU GX sin D3D9). La única alternativa en Wii sería portar parte de los assets/datos como parche **Riivolution** sobre la versión oficial de *Virtua Tennis 4* de Wii (2011).

El desglose de tareas ejecutables y verificables (`ANDROID-1` a `ANDROID-5`) se sigue en `ROADMAP_ROSTER.md` (Fase 5).
