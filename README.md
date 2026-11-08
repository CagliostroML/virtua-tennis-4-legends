# Virtua Tennis 4: Legends & Next-Gen Edition 🎾🏆

Proyecto de ingeniería inversa, modernización y modding de **Virtua Tennis 4 (PC)**.

Este repositorio contiene el cargador personalizado C/ASM (`xlive.dll`), scripts de ingeniería inversa, herramientas de descompresión y repaquetado de archivos (`.bin`), y la documentación técnica de parches de motor y Direct3D 9.

---

## 🌟 Logros y Correcciones Implementadas

1. **Bypass Completo de Games for Windows LIVE (GFWL)**:
   - Emulación limpia en espacio de usuario vía wrapper `xlive.dll` (no requiere cliente GFWL, cuenta ni servicios online de Microsoft).
   - Guardado local sin registro de Windows en `./save/`.
   - Soporte automático para idioma español (`0x0C0A` / 3082).
   
2. **Corrección de la Pantalla Negra (D3D9 Viewport Zero-Dimensions Bug)**:
   - En sistemas modernos (Windows 10/11), el motor llamaba a `IDirect3DDevice9::SetViewport` con dimensiones nulas `(0, 0, 0, 0)` en cada frame, causando que Direct3D 9 descartara el 100% de la geometría 3D y elementos 2D de la interfaz.
   - Interceptado a nivel de vtable (`vtbl[47]`) forzando la resolución real del viewport (`1280x720`).

3. **Corrección de Cuellos de Botella y Cuelgues en el Arranque**:
   - Bypass del loop infinito del chequeo de clasificación europea (ESRB/PEGI) en `AdvMode`.
   - Bypass del retardo artificial de 10 segundos (600 frames) en `TitleLogo`.
   - Bypass de chequeos de vídeo de cinemática intro y detección de mandos ausentes.
   - Desbloqueo nativo de todas las leyendas y personajes ocultos (King, Duke, Becker, Edberg, Courier...).

4. **Blindaje de Punteros Nulos en Menú y Navegación**:
   - `0x0045A920` y `0x0045A8D0`: Funciones de sonido y fundido de pantalla protegidas contra desreferenciación nula al pulsar `Enter` / botón de acción.
   - `0x00628E00` y `0x00628E60`: Métodos de formato de interfaz (`fwFormat.cpp`) protegidos contra punteros de nodo nulos.
   - Vectored Exception Handler (VEH) en `xlive.dll` para captura y recuperación automática de accesos inválidos.

---

## 🎮 Controles del Juego

### ⌨️ Teclado (Predeterminado Jugador 1)
| Acción | Tecla Principal | Tecla Alternativa | Mando Xbox Equivalente |
|---|---|---|---|
| **Moverse / Navegar Menús** | Flechas de dirección | — | D-Pad / Stick Izquierdo |
| **Golpe Liftado / Seleccionar / Confirmar** | `Enter` | `Espacio` / `C` | **Botón A** |
| **Golpe Cortado / Atrás / Cancelar** | `Esc` | `X` / `Retroceso` | **Botón B** |
| **Globo (Lob)** | `Z` | — | **Botón X** |
| **Dejada (Drop Shot)** | `V` | — | **Botón Y** |
| **Pausa / Menú de Opciones** | `Esc` | `Enter` | **Botón Start** |

### 🎮 Mandos (Xbox 360 / Xbox One / Xbox Series / PS4 / PS5 / Genéricos)
- El juego soporta nativamente XInput y DirectInput.
- Los mandos de Xbox son detectados automáticamente como Jugador 1 / Jugador 2.
- Los mandos de PlayStation (DualShock 4 / DualSense) son compatibles directamente o mediante emuladores XInput como DS4Windows.

---

## 🛠️ Estructura del Proyecto

```text
├── src/
│   └── xlive/
│       ├── xlive.c          # Wrapper GFWL, hooks D3D9 y parches del motor en C/ASM
│       ├── xlive.def        # Definición de exportaciones de ordinales XLive
│       ├── build.ps1        # Script de compilación rápida con Zig C Compiler
│       └── run_test.ps1     # Script de ejecución y prueba automatizada
├── tools/
│   ├── make_config.py       # Generador de Config.txt (resolución, modo ventana, controles)
│   ├── vt4_archive.py       # Extractor y visor de paquetes resource.bin / CPK
│   ├── test_archive.py      # Pruebas de extracción de texturas y modelos
│   ├── analyze_vt4.py       # Análisis estático de binarios PE
│   └── cap_window.ps1       # Herramienta de captura GPU / ventanas de pruebas
├── ROADMAP_ROSTER.md        # Plan maestro de incorporación de Alcaraz, Sinner y nuevos torneos
├── MODLOG.md                # Registro histórico de cambios y versiones
└── README.md                # Esta guía
```

---

## ⚙️ Compilación de `xlive.dll`

Se utiliza el compilador integrado `zig cc` (o cualquier toolchain MinGW x86):

```powershell
powershell -ExecutionPolicy Bypass -File src/xlive/build.ps1
```

Genera inmediatamente `game/xlive.dll` listo para ser cargado por `VT4.exe`.
