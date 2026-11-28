# 📱 Guía de Instalación y Optimización en Android (Winlator / GameHub / Mobox)

Guía práctica para ejecutar **Virtua Tennis 4: Legends & Next-Gen Edition** con fluidez en teléfonos y consolas portátiles Android (Snapdragon Adreno / Mali / Exynos / Tensor) usando **Winlator**, **GameHub (GameFusion)** o **Mobox**.

---

## ⚡ Inicio Rápido en 3 Pasos (El camino más simple)

> **¿Por qué no hay archivo `.apk`?** `VT4.exe` es un binario nativo de Windows x86 (32 bits) con Direct3D 9 parcheado en memoria por `xlive.dll`. Compilarlo a un `.apk` nativo ARM64 requeriría decompilar todo el juego desde cero; en **GameHub** o **Winlator** ya corre a **60 FPS** con DXVK + Turnip usando nuestro lanzador directo de 1 toque.

1. **Prepara la carpeta lista en tu PC (o con un solo `.zip`)**:
   - Ejecuta `py -u tools/export_android_bundle.py --zip` (genera `dist/android/VT4_Legends_Android/` **y** un único archivo `dist/android/VT4_Legends_Android_Full.zip` listo para pasar por cable USB).
   - Copia o descomprime la carpeta en una **ruta corta de la memoria interna** del móvil, por ejemplo `/storage/emulated/0/Games/VT4_Legends_Android/` *(nunca desde tarjeta SD)*.
2. **Importa `PLAY_VT4_LEGENDS.exe`**:
   - **En GameHub**: `Import PC Game` -> elige `PLAY_VT4_LEGENDS.exe` -> selecciona **1280x720**, **Turnip** (Adreno) o **Vortek** (Mali) y **DXVK Async**.
   - **En Winlator CMod / Frost**: abre el contenedor -> clic derecho / pulsación larga en `PLAY_VT4_LEGENDS.exe` -> `Create Shortcut` -> desde la pestaña *Shortcuts*, `Add to Home Screen`.
3. **¡A jugar en 1 toque!**: `PLAY_VT4_LEGENDS.exe` (Win32 puro sin UCRT) activa automáticamente `xlive,d3dx9_43=n,b` (dejando a Wine usar su `msvcr90` y `xaudio2_7` estables), omite el fallo de `IGameExplorer` / Control Parental en Wine (`0x00404f20`), activa el perfil ligero **`PerfProfile=2`** (`UseD3D9Ex=1` con fallback automático a D3D9) y deja **`TouchXboxHUD=0`** para usar limpio el **Virtual Gamepad** multitáctil de Winlator (o mando físico).

---

## 0. Exportador Automático Llave en Mano (`tools/export_android_bundle.py`)

Puedes generar directamente un paquete limpio y autónomo listo para copiar a tu móvil Android en **`dist/android/VT4_Legends_Android/`** (o empaquetado en un único `.zip` con `--zip`, o solo la actualización ligera del mod con `--patch-only`):

```powershell
# Exportación completa + ZIP único listo para pasar al móvil (~3.6 GB, compila PLAY_VT4_LEGENDS.exe, incluye d3dx9_43.dll, dxvk.conf, vt4_settings.ini móvil y auditoría case-sensitive)
py -u tools/export_android_bundle.py --zip

# Solo actualización ligera de archivos del mod (sin copiar VT4.exe / resource*.bin)
py -u tools/export_android_bundle.py --patch-only --zip
```

El exportador limpia archivos de depuración (`.pdb`, `.png` temporales, instaladores `.msi`), compila el lanzador nativo Win32 puro **`PLAY_VT4_LEGENDS.exe`** con **icono escudo incrustado** (log `launcher_android.log`, `PULSE_LATENCY_MSEC=90`, `DXVK_STATE_CACHE=1`), incluye `d3dx9_43.dll` (x86), `LAUNCH_ANDROID.bat`, `dxvk.conf`, `vt4_legends_icon.png`, `VT4_Legends_Winlator.desktop`, `LEEME_ANDROID.txt`, carpeta `save/` portátil y configura **`TouchXboxHUD=0`**, **`Width=0` / `Height=0` (Auto <= 540p)** y **`Windowed=0`** para aprovechar todo el ancho sin botones duplicados.

---

## 0.5. Arranque en 1 Toque en Pantalla de Inicio (`PLAY_VT4_LEGENDS.exe`)

El paquete exportado incluye **`PLAY_VT4_LEGENDS.exe`** (compilado desde `src/launcher/play_vt4_legends.c`, Win32 puro sin dependencias UCRT y con icono oficial embebido) que fija automáticamente `WINEDLLOVERRIDES=xlive,d3dx9_43=n,b`, `PULSE_LATENCY_MSEC=90` y `DXVK_STATE_CACHE=1` dentro de la propia carpeta, escribe `launcher_android.log` y ejecuta `VT4.exe` de forma **síncrona** (`WaitForSingleObject`), evitando que GameHub o Winlator cierren la sesión antes de tiempo.

### En GameHub (GameFusion)
1. Copia `VT4_Legends_Android/` a una ruta corta de tu memoria interna (p. ej. `/storage/emulated/0/Games/VT4_Legends_Android/`).
2. Pulsa **Import PC Game** (o **Add Game**) y selecciona **`PLAY_VT4_LEGENDS.exe`** (no hace falta configurar manualmente `WINEDLLOVERRIDES`).
3. Ajusta el perfil a **1280x720**, **Turnip** (Adreno) o **Vortek** (Mali), **DXVK 2.3+/2.4+ Async** y **PulseAudio**.
4. Lanza el juego con **1 toque** desde tu biblioteca de GameHub (puedes fijar el acceso directo en el launcher de Android si tu versión lo permite).

### En Winlator (Oficial / CMod / Frost)
1. Dentro del contenedor de Winlator, abre el explorador de archivos y navega a `VT4_Legends_Android/` (desactiva un momento *Virtual Gamepad* si quieres usar toque directo).
2. Toca con **dos dedos a la vez** *(clic derecho)* sobre **`PLAY_VT4_LEGENDS.exe`** -> **Create Shortcut**.
3. Sal del contenedor y abre la pestaña **`☰ -> Shortcuts`** de Winlator:
   - En **Winlator Oficial**, ya puedes lanzar en 1 toque desde esa pestaña (no incluye *Add to Home Screen*; en `⋮ -> Settings` puedes dejar fijos **Input Controls -> Virtual Gamepad**, `960x540` y Audio **ALSA**).
   - En **Winlator CMod** (fork compatible), pulsa **`⋮ -> Add to Home Screen`** para crear el icono directo del escudo en tu escritorio de Android.

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
  - `xaudio2_7` / `msvcr90` -> **Builtin (Wine)** *(Winlator ya incluye FAudio y VC90 SxS nativos; evitar copias sueltas evita errores `R6034` y bloqueos de audio)*.

### B. Mali / Dimensity / Exynos / Tensor (Vortek + DXVK — Redmi Note / Poco / Realme)
- **Resolución del Contenedor**: `960x540` (16:9) o `1280x576` (20:9 pantalla completa). En `vt4_settings.ini`, **`Width=0` y `Height=0` (Auto)** adaptan el juego exactamente al aspecto del contenedor sin recortar el marcador ni desperdigar fill-rate.
- **Graphics Driver**: **Vortek (Universal / Vulkan Mali)** (en Winlator 9+ / CMod / Frost).
- **DX Wrapper**: **DXVK 1.10.3** o **DXVK 2.x Async** *(nuestro `dxvk.conf` activa `enableAsync`, `enableGraphicsPipelineLibrary`, `maxFrameLatency = 2`, `deferSurfaceCreation = True` y `supportDFFormats = False`)*.
- **Audio Driver**: **ALSA** *(menor latencia en MediaTek/Mali)* o **PulseAudio** (`PLAY_VT4_LEGENDS.exe` fija automáticamente `PULSE_LATENCY_MSEC=90`).
- **Box64 Preset & CPU**: **Performance** (o **Intermediate / Stability** si notas micro-tirones al acumular shaders); si tu procesador tiene núcleos grandes + pequeños, activa solo los núcleos rápidos en *Processor Affinity*.

---

## 3. Configuración óptima de `game/vt4_settings.ini` para Android / PC modesto

Abre `vt4_settings.ini` (en `VT4_Legends_Android/` ya viene preconfigurado así):

```ini
[Graphics]
Width=0
Height=0
Windowed=0
UseD3D9Ex=1
AntiAliasing=0
VSync=0
AnisotropicFiltering=0
CleanPostFX=1
```

### Claves de `[Performance]` en `vt4_settings.ini`
- **`PerfProfile=0|1|2`**:
  - `0` (**Ultra PC**): Calidad completa + frame pacer híbrido de precisión a 60.000 FPS + caché I/O en memoria (0 syscalls de disco).
  - `1` (**Esports / Medio**): `CleanPostFX=1`, MSAA <= 2x, Aniso <= 8x, sombras 1024x1024, bloom 1024x512.
  - `2` (**Android / Winlator / Vortek & Turnip — Recomendado en móvil**): VSync OFF, MSAA=0, Aniso=0, `CleanPostFX=1`, sombras **256x256**, bloom **128x64**, `BackBufferCount=2` (triple buffering), `D3DSWAPEFFECT_DISCARD`, caché I/O en memoria (0 syscalls FUSE), fuentes D3DX escaladas a la altura real y frame pacer con `Sleep` limpio **sin bucle spin-wait en Box64**.
- **`UnlockFPS=0|1`**: `0` por defecto (mantiene la física a velocidad exacta `1.00x` a 60.000 FPS con frame-pacing de precisión); `1` desbloquea FPS para benchmarks/turbo.
- **`BenchLog=0|1`**: `1` activa el registro de telemetría de rendimiento (`QueryPerformanceCounter`: FPS medios, 1% low, p99 frame time y tiempo I/O) en `xlive_mod.log`.

### ¿Por qué vuela en Android con estos ajustes?
- **`AntiAliasing=0` + `AnisotropicFiltering=0`**: El MSAA en D3D9 sobre DXVK/Turnip multiplica el ancho de banda de memoria GPU móvil; desactivarlo libera enormes recursos en Adreno/Mali.
- **`CleanPostFX=1`**: Desactiva el bloom pesado original de SEGA (mejora nitidez y ahorra varios pases de render).
- **`VSync=0` + Frame Pacer de `xlive.dll`**: Elimina el bug original de doble espera VSync (`30.77 FPS`) y las caídas bruscas de 60 -> 30 FPS cuando un frame tarda 17 ms, manteniendo **60.00 FPS** constantes sin input lag.

---

## 4. Mapeo de Mando y Controles en Winlator

- **Virtual Gamepad nativo de Winlator o mando físico Bluetooth/USB-C (Recomendado y por defecto, `TouchXboxHUD=0`)**:
  1. Abre el menú lateral de Winlator (desliza desde el borde izquierdo o pulsa Atrás en Android) -> **Input Controls** -> elige **Virtual Gamepad** (mando XInput virtual con soporte multitáctil real para moverte y golpear a la vez).
  2. La pantalla queda limpia sin botones duplicados, con lectura completa en menús, partidos (incluido resto de saque) y menú personalizado (`OPCIONES` vía `F2` o toque), además de protección anti-click-derecho/doble-toque para evitar retrocesos accidentales en menús.
- **Overlay integrado opcional (`[F6]`)**:
  - Si alguna vez quieres probar nuestro overlay en pantalla, pulsa **`F6`** (o activa `TouchXboxHUD=1|2` en **`OPCIONES -> GRÁFICOS HD Y LEGENDS`**). Con `1` (Auto) se oculta al detectar cualquier pulsación de Virtual Gamepad o mando físico.
- Mapeo XInput / Táctil:
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
| El juego arranca sin los 84 tenistas (solo 26 originales) | Wine no cargó `xlive.dll` | Lanza desde **`PLAY_VT4_LEGENDS.exe`** (fija los overrides automáticamente) o añade `WINEDLLOVERRIDES="xlive,d3dx9_43=n,b"` en variables de entorno del contenedor |
| Sin sonido o bloqueos al iniciar | `xaudio2_7` / `msvcr90` sueltos | Usa **PulseAudio** y deja `xaudio2_7` / `msvcr90` en **Builtin (Wine)** (`export_android_bundle.py` ya lo deja limpio así) |
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
