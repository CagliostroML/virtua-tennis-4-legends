# Hoja de Ruta: Virtua Tennis 4 - Legends & Next-Gen Edition

Este documento establece la arquitectura técnica y el plan de ejecución por fases para transformar *Virtua Tennis 4* en la edición definitiva: resolución HD nativa, estabilidad total sin GFWL, selector de personajes ampliado, incorporación de leyendas modernas y portabilidad futura.

---

## 1. Estado Actual (Fase 1 Completada)
- [x] **Emulación Games for Windows LIVE (GFWL)**: Integrada al 100% en `xlive.dll` (perfil local automático, guardado de partidas en disco sin registro de Windows).
- [x] **Bypass de vídeos y deadlocks regionales**: Eliminado el bloqueo del selector de idioma europeo/ESRB y el atasco de reproducción de secuencias de vídeo intro.
- [x] **Renderizado HD y Anti-Aliasing (MSAA)**: Soporte completo para 1080p, 2K y 4K con 4x MSAA y filtrado anisotrópico 16x configurable vía `vt4_settings.ini`.
- [x] **Controles y Navegación Universal**: Mapeo completo de teclado (WASD, flechas, Enter, Espacio, Esc) y recuperación de foco al alternar ventanas (Alt+Tab / pantalla completa sin bordes).
- [x] **Estabilidad de Modos Arcade y Exhibición**: Protección contra fallos nulos en `fwFormat` y nodos de jerarquía de interfaz.

---

## 2. Fase 2: Rediseño del Selector de Personajes (Character Select)
El selector original de VT4 soporta una cuadrícula fija de 24 casillas:
1. **Inspección de estructuras de roster**:
   - Estructura `CharacterDef`: ID interno, nombre, modelo 3D (`.mdl`), texturas (`.txp`), estilo de juego (*Strong Backhand*, *Rocket Serve*, etc.), estadísticas y slots de indumentaria.
2. **Ampliación de cuadrícula / Paginación**:
   - Modificación de la matriz de selección para admitir pestañas (`ATP Actuales`, `WTA Actuales`, `Leyendas Históricas`) o scroll de varias páginas.
   - Reemplazo de los retratos 2D en `archive/` o inyección en memoria.
3. **Desbloqueo de personajes ocultos**:
   - King y Duke ya han sido desbloqueados directamente mediante hook del método de validación `FUN_005dfe90`.

---

## 3. Fase 3: Modelado 3D, Texturas e Inyección de Roster (Alcaraz, Sinner, etc.)
1. **Pipeline de Assets (`asset-pipeline`)**:
   - Extracción de geometrías de jugadores base (`.mdl` / `.bin`) con herramientas de decompilación y Blender.
   - Modelado y texturizado de nuevas figuras: Carlos Alcaraz, Jannik Sinner, Novak Djokovic (versión moderna), Rafael Nadal (Prime), Roger Federer (Prime), Aryna Sabalenka, Iga Świątek.
2. **Texturas y Equipamiento**:
   - Raquetas Babolat Pure Aero, Head Speed, Wilson Pro Staff.
   - Ropa con patrocinadores actuales (Nike, Lacoste, Uniqlo).

---

## 4. Fase 4: Físicas, Animaciones y Pistas de Grand Slam
1. **Animaciones de Golpeo**:
   - Ajuste de cinemáticas de derecha (*forehand* con efecto látigo de Alcaraz, revés a dos manos plano de Sinner).
2. **Superficies**:
   - Ajuste del coeficiente de fricción y bote de pelota para diferenciar netamente la tierra batida de Roland Garros, la hierba rápida de Wimbledon y las pistas duras de Melbourne/US Open.

---

## 5. Fase 5: Viabilidad de Portabilidad a Android y Otras Plataformas
¿Es factible recompilar o portar VT4 a Android?

### Ruta A: Port Nativo mediante Decompilación (C++ / SDL2 / Vulkan o GLES)
- **Concepto**: Similar a proyectos como *re3 (GTA)* o *Ship of Harkinian (Zelda)*.
- **Ventaja**: Rendimiento nativo total a 60/120 FPS en cualquier procesador ARM64, consumo mínimo de batería y soporte para controles táctiles en pantalla o mandos Bluetooth (Razer Kishi, Xbox, PS5).

### Ruta B: Recompilación / Wrapper del binario de PS Vita (*Virtua Tennis 4: World Tour Edition*)
- **Dato clave**: VT4 tuvo versión nativa para **PlayStation Vita**, la cual está compilada directamente para arquitectura **ARM (ARMv7)**.
- **Técnica**: La comunidad de emulación y preservación (como los ports de Rinnegatamante y TheFlow para GTA San Andreas, Bully, Max Payne) utiliza cargadores `.so` que toman el ejecutable ARM de Vita y reemplazan las llamadas a la GPU (GXM) y al SO con OpenGL ES/Android NDK. Esto permitiría ejecutar VT4 de forma 100% nativa en Android con un esfuerzo infinitamente menor al de reescribir todo el juego desde cero.

### Ruta C: Capa de Traducción x86/DirectX (Winlator / Box64 / DXVK)
- **Estado actual**: Gracias a las optimizaciones que hemos realizado (eliminación de GFWL, soporte de resolución configurable sin registros de Windows, compatibilidad limpia con Direct3D 9), la versión resultante ya es compatible con emuladores de entorno Windows en Android como **Winlator** o **Mobox** con aceleración por hardware Adreno (Turnip drivers).
