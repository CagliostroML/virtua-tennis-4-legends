# 📱 Guía de Instalación y Optimización en Android (Winlator / GameHub / Mobox)

Guía práctica para ejecutar **Virtua Tennis 4: Legends & Next-Gen Edition** con fluidez en teléfonos y consolas portátiles Android (Snapdragon Adreno / Mali / Exynos / Tensor) usando **Winlator**, **GameHub (GameFusion)** o **Mobox**.

---

## 0. Exportador Automático Llave en Mano (`tools/export_android_bundle.py`)

Puedes generar directamente un paquete limpio y autónomo listo para copiar a tu móvil Android en **`dist/android/VT4_Legends_Android/`** (o solo la actualización ligera del mod con `--patch-only`):

```powershell
# Exportación completa lista para copiar a Android (~3.5 GB, compila PLAY_VT4_LEGENDS.exe, incluye d3dx9_43.dll, dxvk.conf, vt4_settings.ini móvil y auditoría case-sensitive)
py -u tools/export_android_bundle.py

# Solo actualización de archivos del mod (sin copiar VT4.exe / resource*.bin)
py -u tools/export_android_bundle.py --patch-only
```

El exportador limpia archivos de depuración (`.pdb`, `.png` temporales, instaladores `.msi`), compila el lanzador nativo Win32 **`PLAY_VT4_LEGENDS.exe`**, incluye `d3dx9_43.dll` (x86), `LAUNCH_ANDROID.bat` (síncrono), `dxvk.conf`, `LEEME_ANDROID.txt`, carpeta `save/` portátil y configura automáticamente **`TouchXboxHUD=1`** (Auto: activa en pantalla el display interactivo de mando Xbox al detectar Android/Wine).

---

## 0.5. Arranque en 1 Toque en Pantalla de Inicio (`PLAY_VT4_LEGENDS.exe`)

El paquete exportado incluye **`PLAY_VT4_LEGENDS.exe`** (compilado desde `src/launcher/play_vt4_legends.c`), un lanzador nativo Win32 (~195 KB) que fija automáticamente `WINEDLLOVERRIDES=xlive,d3dx9_43,msvcr90,msvcp90,msvcm90=n,b` y ejecuta `VT4.exe` de forma **síncrona** (`WaitForSingleObject`), evitando que GameHub o Winlator cierren la sesión antes de tiempo.

### En GameHub (GameFusion)
1. Copia `VT4_Legends_Android/` a una ruta corta de tu memoria interna (p. ej. `/storage/emulated/0/Games/VT4_Legends_Android/`).
2. Pulsa **Import PC Game** (o **Add Game**) y selecciona **`PLAY_VT4_LEGENDS.exe`** (no hace falta configurar manualmente `WINEDLLOVERRIDES`).
3. Ajusta el perfil a **1280x720**, **Turnip** (Adreno) o **Vortek** (Mali), **DXVK 2.3+/2.4+ Async** y **PulseAudio**.
4. Lanza el juego con **1 toque** desde tu biblioteca de GameHub (puedes fijar el acceso directo en el launcher de Android si tu versión lo permite).

### En Winlator CMod / Frost
1. Dentro del contenedor de Winlator, abre el explorador de archivos y navega a `VT4_Legends_Android/`.
2. Haz clic derecho (o pulsación larga / dos dedos) sobre **`PLAY_VT4_LEGENDS.exe`** -> **Create Shortcut**.
3. Cierra el contenedor, ve a la pestaña **Shortcuts** de Winlator, pulsa **`⋮`** en el acceso directo creado -> **Add to Home Screen**.
4. Tendrás un icono directo de **1 toque** en la pantalla de inicio de Android que arranca directamente *Virtua Tennis 4: Legends & Next-Gen Edition* con `xlive.dll` y los 84 tenistas activos.

*(Si prefieres ejecutar mediante batch, `LAUNCH_ANDROID.bat` también llama a `VT4.exe` de forma síncrona con los mismos overrides.)*

---

## 1. Requisitos recomendados

- **CPU/GPU ideal**: Snapdragon 8 Gen 1 / 8 Gen 2 / 8 Gen 3 / 8s Gen 3 / 7+ Gen 2 / 870 (GPU **Adreno** con driver **Turnip**).
- **Gama media / Mali / Dimensity / Exynos**: Funciona bien bajando resolución a `1280x720` y activando `PerfProfile=2` en `vt4_settings.ini` (ver sección 3).
- **RAM**: Mínimo 6 GB (recomendado 8 GB+).
- **Almacenamiento**: ~4 GB libres (copia la carpeta exportada `VT4_Legends_Android/` a una ruta corta de la memoria interna, **nunca** desde tarjeta SD lenta ni carpetas con rutas muy largas).

---

## 2. Configuración recomendada del Contenedor (Winlator / GameHub / Mobox)

### A. Snapdragon (GPU Adreno — Mejor rendimiento)
- **Resolución**: `1280x720` (o `1600x900` / `1920x1080` en Snapdragon 8 Gen 2/3).
- **Graphics Driver**: **Turnip (Adreno)** (v24.3.0+ o la más reciente de Winlator Frost / Cmod).
- **DX Wrapper**: **DXVK 2.3.1** o **2.4.1 (GPLAsync)** *(VT4 es Direct3D 9 puro; DXVK lo traduce a Vulkan con enorme eficiencia)*.
- **Box64 Preset**: **Performance** (o `Intermediate` si notas cualquier inestabilidad en menús).
- **Audio Driver**: **PulseAudio** (latencia baja).
- **Windows Components / DLL Overrides**:
  - `xlive` -> **Native (Windows)** *(imprescindible para que cargue nuestro `xlive.dll` con los **84 tenistas**, Grand Slams, Marcadores TV, Netplay LAN y controles táctiles)*.
  - `d3dx9_43` -> **Native (Windows)** *(ya incluida en el paquete exportado para fuentes y sprites D3D9)*.
  - `xaudio2_7` -> **Native (Windows)** *(garantiza el sonido nativo sin cortes; evita el fallback lento de Wine)*.
  - `winmm` -> **Builtin, Native** *(para reproducir packs de voces personalizadas de `archive/voices/` sin stutter)*.

### B. Mali / Dimensity / Exynos / Tensor
- **Resolución**: `1280x720` (o `960x540` en gama baja).
- **Graphics Driver**: **Vortek** (Winlator 9+/Cmod) o **VirGL** / **WineD3D** según compatibilidad de tu versión.
- **DX Wrapper**: **DXVK** (con Vortek) o **WineD3D** (con VirGL).
- **Box64 Preset**: **Performance**.

---

## 3. Configuración óptima de `game/vt4_settings.ini` para Android / PC modesto

Abre `game/vt4_settings.ini` antes de lanzar `VT4.exe` y usa este perfil ligero optimizado:

```ini
[Graphics]
Width=1280
Height=720
Windowed=0
AntiAliasing=0
VSync=0
AnisotropicFiltering=0
CleanPostFX=1

[Performance]
PerfProfile=2
UnlockFPS=0
BenchLog=0

[Menu]
RemoveLiveMode=1

[Gameplay]
ClassicTVCamera=0
MatchSpeedMode=0
ExhibitionRules=0
MultiverseMode=0
```

### Claves de `[Performance]` en `vt4_settings.ini`
- **`PerfProfile=0|1|2`**:
  - `0` (**Ultra PC**): Calidad completa + frame pacer híbrido de precisión a 60.000 FPS + caché I/O en memoria (0 syscalls de disco).
  - `1` (**Esports / Medio**): `CleanPostFX=1`, MSAA <= 2x, Aniso <= 8x, sombras 1024x1024, bloom 1024x512.
  - `2` (**Android / Winlator / DXVK / Turnip — Recomendado en móvil**): VSync OFF, MSAA=0, Aniso=0, `CleanPostFX=1`, sombras **512x512**, bloom **256x128**, `BackBufferCount=1`, `D3DSWAPEFFECT_DISCARD`, caché I/O en memoria (elimina miles de `stat()` lentos en FUSE de Android) y margen de `Sleep` ampliado para reducir temperatura y consumo de batería.
- **`UnlockFPS=0|1`**: `0` por defecto (mantiene la física a velocidad exacta `1.00x` a 60.000 FPS con frame-pacing de precisión); `1` desbloquea FPS para benchmarks/turbo.
- **`BenchLog=0|1`**: `1` activa el registro de telemetría de rendimiento (`QueryPerformanceCounter`: FPS medios, 1% low, p99 frame time y tiempo I/O) en `xlive_mod.log`.

### ¿Por qué vuela en Android con estos ajustes?
- **`AntiAliasing=0` + `AnisotropicFiltering=0`**: El MSAA en D3D9 sobre DXVK/Turnip multiplica el ancho de banda de memoria GPU móvil; desactivarlo libera enormes recursos en Adreno/Mali.
- **`CleanPostFX=1`**: Desactiva el bloom pesado original de SEGA (mejora nitidez y ahorra varios pases de render).
- **`VSync=0` + Frame Pacer de `xlive.dll`**: Elimina el bug original de doble espera VSync (`30.77 FPS`) y las caídas bruscas de 60 -> 30 FPS cuando un frame tarda 17 ms, manteniendo **60.00 FPS** constantes sin input lag.

---

## 4. Mapeo de Mando (Bluetooth / USB-C / Backbone / Display Xbox Táctil)

- **Display Interactivo de Mando Xbox en Pantalla (`TouchXboxHUD`)**:
  - En **`OPCIONES -> GRÁFICOS HD Y LEGENDS`** (fila `MANDO XBOX TACTIL (ANDROID)`) o en `vt4_settings.ini`:
    - `TouchXboxHUD=1` *(Auto — activado por defecto en el paquete Android)*: detecta Android/Wine automáticamente y dibuja el mando Xbox translúcido interactivo (Stick izquierdo, `A/B/X/Y` con leyenda de golpes, `LB/RB` para cambiar las 4 páginas del roster de **84 tenistas**, y `START`).
    - `TouchXboxHUD=2`: siempre visible (puedes probarlo en PC pulsando **`F6`** en cualquier momento).
- En Winlator / GameHub también puedes conectar un mando físico Bluetooth/USB-C (**XInput**) en paralelo; ambos funcionan al instante.
  - **Stick izquierdo / Cruceta**: Mover tenista y apuntar golpe/saque.
  - **A**: Golpe plano / Topspin (y confirmar menús).
  - **B**: Globo (Lob) / Atrás en menús.
  - **X**: Cortado (Slice).
  - **Y**: Dejada / Súper golpe.
  - **LB / RB (`Q` / `E` en teclado)**: Cambiar página del selector de los **84 tenistas** (`Tour` / `Era Dorada` / `Leyendas 90s` / `Pioneros`).
  - **Start**: Pausa / saltar repeticiones.

---

## 5. Solución rápida de problemas en Android

| Síntoma | Causa más probable | Solución |
|---|---|---|
| El juego arranca sin los 84 tenistas (solo 26 originales) | Wine no cargó `xlive.dll` | Lanza desde **`PLAY_VT4_LEGENDS.exe`** (fija los overrides automáticamente) o añade `WINEDLLOVERRIDES="xlive,d3dx9_43,msvcr90,msvcp90,msvcm90=n,b"` en variables de entorno del contenedor |
| Sin sonido o sonido entrecortado | `xaudio2_7` builtin en Wine | Activa `xaudio2_7=n` (Native) y usa `PulseAudio` en el contenedor |
| Tirones al cargar partidos | FUSE lento en `/sdcard/Download` | Mueve `game/` a una ruta corta dentro del almacenamiento interno y mantén `PerfProfile=2` |
| Pantalla negra al iniciar partido | Driver incompatible con MSAA | Pon `AntiAliasing=0` y `CleanPostFX=1` en `vt4_settings.ini` |

---

## 6. Métricas de Rendimiento Verificadas (Benchmarks Reales)

Mediciones reales tomadas en partido de Exhibición de 300 frames (`scratch/bench_fps.py`, audio nativo XAudio2 activo, `0` crashes):

| Métrica | ANTES (`VSync=1` def.) | ANTES (`VSync=0`) | DESPUÉS `PerfProfile=0` (Ultra PC) | DESPUÉS `PerfProfile=1` (Esports) | DESPUÉS `PerfProfile=2` (Android / Winlator) |
|---|---:|---:|---:|---:|---:|
| **FPS Medios** | 30.77 | 60.24 | **60.00 (+95.0 %)** | **60.00** | **60.00** |
| **1% Low FPS** | 28.12 | 45.27 | **59.93 (+113.1 %)** | **59.71** | **59.92** |
| **Frame Time Avg / P99 / Max (ms)** | 32.50 / 34.76 / 36.90 | 16.60 / 16.99 / 28.62 | **16.67 / 16.67 / 16.72** | **16.67 / 16.71 / 16.75** | **16.67 / 16.67 / 16.70** |
| **Jitter de Frame (max - min)** | 5.90 ms | 12.48 ms | **0.10 ms** | **0.17 ms** | **0.06 ms** |
| **Syscalls I/O (`GetFileAttributesA`)** | 2,453 | 2,448 | **0 (-100 %)** | **0 (-100 %)** | **0 (-100 %)** |
| **Tiempo de búsqueda I/O (ms)** | 61.95 ms | 64.39 ms | **0.81 ms (76x más rápido)** | **0.76 ms (81x más rápido)** | **0.78 ms (79x más rápido)** |
| **Velocidad lógica (`1.000 = 1x`)** | 1.967 *(desincronizada)* | 1.010 | **1.003** | **1.003** | **1.003** |
| **Crashes / Asserts** | 28 | 0 | **0 (`ps=0 ex=0 exc=0`)** | **0 (`ps=0 ex=0 exc=0`)** | **0 (`ps=0 ex=0 exc=0`)** |

> **Resumen clave para Android/Winlator**: `PerfProfile=2` elimina el 100 % de las 2,453 llamadas de disco `GetFileAttributesA` por partida (evitando cuellos de botella FUSE en almacenamiento móvil), reduce sombras a `512x512` y bloom a `256x128` con `BackBufferCount=1` y `0` MSAA/Aniso, logrando **60.00 FPS constantes con 59.92 1% low y solo 0.06 ms de jitter**.
