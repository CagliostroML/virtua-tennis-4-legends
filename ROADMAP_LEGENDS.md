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

## 3. Fase 2: Rediseño del Selector de Personajes (Character Select)
El selector original de VT4 soporta una cuadrícula fija de 24 casillas:
1. **Inspección de estructuras de roster**:
   - Estructura `CharacterDef`: ID interno, nombre, modelo 3D (`.mdl`), texturas (`.txp`), estilo de juego (*Strong Backhand*, *Rocket Serve*, etc.), estadísticas y slots de indumentaria.
2. **Ampliación de cuadrícula / Paginación**:
   - Modificación de la matriz de selección para admitir pestañas (`ATP Actuales`, `WTA Actuales`, `Leyendas Históricas`) o scroll de varias páginas.
   - Reemplazo de los retratos 2D en `archive/` o inyección en memoria.
3. **Desbloqueo de personajes ocultos**:
   - King y Duke ya han sido desbloqueados directamente mediante hook del método de validación `FUN_005dfe90`.

---

## 4. Fase 3: Remasterización de Texturas con Nano Banana & Nuevos Modelos Next-Gen
1. **Pipeline de Remasterización de Texturas con Nano Banana (AI Upscaling / Generative Diffusion)**:
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
2. **Superficies**:
   - Ajuste del coeficiente de fricción y bote de pelota para diferenciar netamente la tierra batida de Roland Garros, la hierba rápida de Wimbledon y las pistas duras de Melbourne/US Open.

---

## 6. Fase 5: Viabilidad de Portabilidad a Android y Otras Plataformas
¿Es factible recompilar o portar VT4 a Android?

### Ruta A: Port Nativo mediante Decompilación (C++ / SDL2 / Vulkan o GLES)
- **Concepto**: Similar a proyectos como *re3 (GTA)* o *Ship of Harkinian (Zelda)*.
- **Ventaja**: Rendimiento nativo total a 60/120 FPS en cualquier procesador ARM64, consumo mínimo de batería y soporte para controles táctiles en pantalla o mandos Bluetooth (Razer Kishi, Xbox, PS5).

### Ruta B: Recompilación / Wrapper del binario de PS Vita (*Virtua Tennis 4: World Tour Edition*)
- **Dato clave**: VT4 tuvo versión nativa para **PlayStation Vita**, la cual está compilada directamente para arquitectura **ARM (ARMv7)**.
- **Técnica**: La comunidad de emulación y preservación (como los ports de Rinnegatamante y TheFlow para GTA San Andreas, Bully, Max Payne) utiliza cargadores `.so` que toman el ejecutable ARM de Vita y reemplazan las llamadas a la GPU (GXM) y al SO con OpenGL ES/Android NDK. Esto permitiría ejecutar VT4 de forma 100% nativa en Android con un esfuerzo infinitamente menor al de reescribir todo el juego desde cero.

### Ruta C: Capa de Traducción x86/DirectX (Winlator / Box64 / DXVK)
- **Estado actual**: Gracias a las optimizaciones que hemos realizado (eliminación de GFWL, soporte de resolución configurable sin registros de Windows, compatibilidad limpia con Direct3D 9), la versión resultante ya es compatible con emuladores de entorno Windows en Android como **Winlator** o **Mobox** con aceleración por hardware Adreno (Turnip drivers).
