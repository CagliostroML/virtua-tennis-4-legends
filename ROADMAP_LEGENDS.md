# Hoja de Ruta: Virtua Tennis 4 - Legends & Next-Gen Edition

Este documento establece la arquitectura técnica y el plan de ejecución por fases para transformar *Virtua Tennis 4* en la edición definitiva: resolución HD nativa en 3D, eliminación total de bordes de sierra, estabilidad total sin GFWL, selector de personajes ampliado, incorporación de leyendas modernas y portabilidad futura.

---

## 1. Estado Actual (Fase 1 Completada)
- [x] **Emulación Games for Windows LIVE (GFWL)**: Integrada al 100% en `xlive.dll` (perfil local automático, guardado de partidas en disco sin registro de Windows ni conexión externa).
- [x] **Bypass de vídeos y deadlocks regionales**: Eliminado el bloqueo del selector de idioma europeo/ESRB y el atasco de reproducción de secuencias de vídeo intro.
- [x] **Pantalla completa sin bordes y menús HD**: 1080p, 2K y 4K con interfaz nítida y ventana sin bordes gestionada en `vt4_settings.ini`.
- [x] **Controles y Navegación Universal**: Mapeo completo de teclado (WASD, flechas, Enter, Espacio, Esc) y recuperación de foco al alternar ventanas (Alt+Tab).
- [x] **Estabilidad de Modos Arcade y Exhibición**: Protección contra fallos nulos en `fwFormat` y nodos de jerarquía de interfaz.

---

## 2. Fase 1B: Remasterización Gráfica HD Total (3D Nativo & Anti-Aliasing)
A raíz de las pruebas en pista, se ha identificado por qué los modelos 3D y las pistas conservan bordes de sierra ("dientes de sierra") mientras que el HUD ya es HD:

```
[VT4-Mod] SetViewport frame 4: pos=(0,0) size=640x512
[VT4-Mod] StretchRect(srcTarget[2]=05DB9280 draws=13 -> BB=05DB98C0)
```

1. **Escalado del RenderTarget 3D Interno (Full HD / 4K)**:
   - El motor de VT4 dibuja la interfaz directamente al BackBuffer (a 1920x1080), pero la partida 3D (jugadores, pista, sombras) la renderiza en un RenderTarget interno de resolución reducida (640x512 / 720p) y luego la estira con `StretchRect`.
   - **Acción**: Interceptar `CreateRenderTarget` y `CreateTexture` (con flag `D3DUSAGE_RENDERTARGET`) para forzar que los buffers de color y profundidad de la escena 3D se creen a la resolución completa de la pantalla (`1920x1080` / `2560x1440` / `3840x2160`).
2. **Anti-Aliasing Real en Geometría 3D (MSAA / SMAA)**:
   - Activar el estado `D3DRS_MULTISAMPLEANTIALIAS` en los pases de dibujo 3D e implementar un pase de anti-aliasing de bordes (SMAA o FXAA) para erradicar las aristas dentadas en las siluetas de los tenistas y la red.
3. **Sombras de Alta Resolución**:
   - Actualmente, el mapa de sombras (*shadow map*) se genera a 512x512, lo que provoca que las sombras de los tenistas sobre la pista verde se proyecten pixeladas.
   - **Acción**: Escalar los buffers de sombras a 2048x2048 o 4096x4096 para obtener sombras nítidas y suaves.
4. **Filtrado Anisotrópico 16x Permanente**:
   - Forzar `D3DSAMP_MAXANISOTROPY = 16` y `D3DTEXF_ANISOTROPIC` en cada cambio de textura para que las líneas de fondo y la textura de la pista se mantengan nítidas en perspectiva rasante.

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

## 4. Fase 3: Modelado 3D, Texturas e Inyección de Roster (Alcaraz, Sinner, etc.)
1. **Remasterización de Texturas (HD / 4K Textures)**:
   - Sustitución de texturas de 512x512 originales por versiones en alta resolución (2048x2048) de piel, caras, ropa y raquetas usando el cargador de archivos sueltos `game/archive/`.
2. **Pipeline de Modelos 3D (`asset-pipeline`)**:
   - Extracción de geometrías de jugadores base (`.mdl` / `.bin`) con herramientas de decompilación y Blender.
   - Modelado y texturizado de nuevas figuras: Carlos Alcaraz, Jannik Sinner, Novak Djokovic (versión moderna), Rafael Nadal (Prime), Roger Federer (Prime), Aryna Sabalenka, Iga Świątek.
3. **Equipamiento Oficial Actual**:
   - Raquetas Babolat Pure Aero, Head Speed, Wilson Pro Staff.
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
