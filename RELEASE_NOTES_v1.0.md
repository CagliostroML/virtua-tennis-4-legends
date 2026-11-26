# Virtua Tennis 4: Legends & Next-Gen Edition — Release `v1.0`

Primer lanzamiento estable (`v1.0`) del mod nativo `xlive.dll` y overhaul completo para **Virtua Tennis 4 (PC & Android)**.

> **Aviso Legal:** El repositorio y el paquete de lanzamiento incluyen exclusivamente código propio del mod, shaders/overlays HUD, herramientas y documentación. **No contienen ni distribuyen archivos, ejecutables ni assets originales de SEGA** (requiere una copia legítima de *Virtua Tennis 4* para PC).

---

## Novedades principales de `v1.0`

- **Roster de 84 tenistas jugables (`IDs 0..83`)** en 4 páginas por épocas (`Era Actual & Next-Gen`, `Era Dorada 2000s-2010s`, `Leyendas 90s & WTA Clásica`, `Pioneros 60s-80s & Jefes SEGA`):
  - **59 modelos `.sdo` personalizados** con cabezas esculpidas en 3D, **caras UV 3D personalizadas**, ojos HD 4x-supersampled, pelo 3D y escalado de huesos.
  - **84/84 retratos 2D a todo color** (`photo_L`, `photo_eye`, `photo_S`), nombres reales en partido y pantalla de carga, y estadísticas individualizadas (`IDs 26..83`).
- **Los 4 Grand Slams Oficiales + Mutua Madrid Open (Tierra Azul)**: `Aus1` (Australian Open), `Fra1` (Roland-Garros), `Eng1` (Wimbledon), `Usa1` (US Open) y `Spa2` (Madrid Blue Clay), con física diferenciada por superficie, `ProPhysics`, Reglas Grand Slam (`5 Sets x 6 Juegos`) y Cámara TV Clásica.
- **Marcadores TV Oficiales en Vivo (`[F7]`)**: 6 temas (`AO`, `RG`, `WIM`, `USO`, `MAD`, `TOUR`), atlas de 27 banderas COI, lectura directa desde RAM de marcador, turno de saque, Break/Set/Match Point, radar `km/h` y `RALLY`.
- **Menú `EN LÍNEA` nativo VT4 + Auto-Descubrimiento LAN (`PC <-> Android`)**: lockstep P2P UDP con escaneo LAN automático y soporte Tailscale.
- **Multiverso Arcade (`EE-1..EE-5`)**: protesta al juez de silla con McEnroe (`[C]` + QTE), pista 50% Hielo / 50% Barro, armas alternativas (`[R]` Madera / Sartén / Baguette), Super Golpes DBZ y jefes finales desbloqueados (`EXTRA-1`).
- **Portabilidad Android 1-Toque & Rendimiento (`PerfProfile=2`)**:
  - Lanzador nativo Win32 **`PLAY_VT4_LEGENDS.exe`** (fija `WINEDLLOVERRIDES` y ejecuta `VT4.exe` de forma síncrona para **GameHub** y **Winlator CMod/Frost**).
  - **Mando Xbox Táctil interactivo (`[F6]`, `TouchXboxHUD=1`)**, fix de resto con teclado y **60.00 FPS constantes** (`1% low 59.92`, `0.06 ms` jitter, `0` syscalls FUSE).

---

## Verificación QA de cierre `v1.0`

- **Roster & Motor (`verify_v1_final_qa.py`)**: comprobación en vivo de los 6 retratos recién coloreados en `CharaSelect` (`51, 52, 55, 74, 75, 77`) + partido en vivo con `BroadcastHUD=1` + `EXTRA-1` + audio nativo XAudio2 (`ps=0 ex=0 exc=0`).
- **Opciones & Persistencia INI (`test_options_ui.py`)**: verificación de `OPCIONES -> GRÁFICOS HD Y LEGENDS` y 4 capturas D3D9 válidas.
- **Bundle Android (`export_android_bundle.py`)**: auditoría case-sensitive (`398` archivos, `0` mismatches) + smoke-test síncrono de `PLAY_VT4_LEGENDS.exe`.
