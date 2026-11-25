# 🎨 Guía de Buenas Prácticas — Studio Facemaker 3D de Virtua Tennis 4 (`< 25s/jugador`)

Protocolo técnico estandarizado para convertir **cualquier tenista del roster (`26_ALC`..`81_CLI`)** en un modelo 3D fotorrealista de nivel **9/10+ ("Sobresaliente")** en **1 sola pasada y < 25 segundos por jugador**, manteniendo integridad binaria absoluta y cero regresiones.

---

## 1. Las 8 Reglas de Oro del Facemaker Studio VT4

| # | Regla | Por qué es crítica (fallo real evitado) | Implementación estándar |
|---|---|---|---|
| **1** | **Puerta Estricta de Foto Neutra (`Zero-Smile Gate`)** | Fotos sonriendo de alfombra roja congelan ojos entrecerrados, pómulos subidos, comisuras tensas y dientes entreabiertos sobre la cara en reposo del juego. | • `front_neutral.jpg`: `smile < 0.10`, `squint < 0.25`, ojos bien abiertos, labios cerrados/relajados, `|yaw| <= 0.12`, luz diurna o de estudio uniforme (sin flash duro).<br>• `profile_neutral.jpg`: perfil 90° limpio para frente, puente nasal, punta, oreja, degradado (*fade*) y nuca (si tiene sonrisa, usar un perfil con boca cerrada para calibrar Z de labios/mentón).<br>• Inspeccionar **siempre** cada foto candidata con `read_file` antes de proyectar. |
| **2** | **Delta de Identidad 3D Pura (`3DDFA_V2` ONNX con `alpha_exp = 0`)** | Los 478 landmarks 2D de MediaPipe no capturan el volumen completo de mejillas, arco cigomático, sien ni mandíbula (dejando huecos del molde donante como Djokovic). | • Ejecutar `tools/bfm3d_fit.py` (`onnxruntime` sobre `mb1_120x120.onnx`, `~14 ms`, 0 PyTorch) sobre el render ortográfico base y sobre `front_neutral.jpg`.<br>• Calcular `Delta_BFM = W_shp @ (alpha_shp_target - alpha_shp_base)` fijando **`alpha_exp = 0`** para transferir **solo identidad ósea/carnosa** (~1.20× acotado), sin deformación por sonrisa. |
| **3** | **Ajuste de Silueta por Perfil Dual (`profile_neutral.jpg`)** | El frontal por sí solo deja la profundidad Z del molde donante (nariz aguileña/recta de Djokovic, occipucio alargado, mentón estrecho). | • Extraer la silueta real de perfil de `profile_neutral.jpg` y alinear verticalmente ojo/nariz/labio/mentón/oreja.<br>• Corregir `Face-VB` y `Face_lodL-VB` en Z: puente nasal exacto (recto diagonal vs cóncavo), punta nasal, proyección labial, surco labiomentoniano, mentón, ángulo mandibular (*gonion*), orejas pegadas (`-X`) y occipucio redondeado. |
| **4** | **Pelo 3D Completo + Trampa `World-Space` vs `Head-Local`** | Pintar el pelo sobre un cráneo "huevo" deja silueta plana; y mover `Hair_fix_lodL-VB` en espacio mundo lo desalinea cientos de centímetros a distancia. | • **Regla crítica de coordenadas**: en `.sdo` de VT4, `Hair_fix-VB` está en **espacio mundo** (`Y ≈ 17.4–18.0 dm`), mientras que **`Hair_fix_lodL-VB` está en espacio local del hueso `Head`** (`Y - Head_Y ≈ 1.5–1.9 dm`). Aplicar siempre el delta de altura del hueso `Head` al `lodL`.<br>• Esculpir la bóveda craneal en `Face-VB` + redistribuir las tarjetas 3D de pelo en 4 zonas (flequillo con caída frontal, coronilla volumétrica, sienes/fade, nuca) **ordenadas de capa interior → puntas exteriores** para evitar errores de *alpha-sorting* en DX9. |
| **5** | **Mapa Normal Limpio de Jugador (`(128,128,255)`) — Cero Residuos del Donante** | Suavizar el `*_N_face_*.dds` de SEGA sigue dejando las mejillas hundidas, ojeras y pliegues del donante bajo luz direccional DX9. | • Generar `*_N_face_*.dds` y `*_N_face_sweat_*.dds` desde una base neutra **`(128, 128, 255)`** + relieve multiescala derivado directamente de la foto neutra horneada + grano orgánico de microporos + relieve fino de mechones en el cuero cabelludo. |
| **6** | **Mapa Especular Mate para Pelo (`*_SS_face_*.dds`)** | El especular brillante de piel de SEGA aplicado al pelo pintado produce un efecto "casco de plástico" bajo focos de estadio. | • Fijar reflectividad **mate `~0.02`** en todo el cuero cabelludo, *fade*, cejas y barba incipiente; mantener brillo satinado natural `~0.20` solo en nariz, pómulos y frente. |
| **7** | **Exclusión UV de Orejas + Fade Carbón Anti-Reflejos** | Proyectar el perfil sobre las orejas genera rayas horizontales; desaturar reflejos de flash sobre cabeza rapada crea "canas"/pelo blanco lateral. | • Excluir las islas UV de orejas de la proyección rasante lateral (usar tono de piel equilibrado + AO limpio).<br>• Limitar luminancia `L` en la zona *fade* y mezclar convexamente entre piel bronceada del jugador y negro-carbón (`#1a1715`), eliminando cualquier brillo blanco/gris lateral. |
| **8** | **Invarianza Binaria, Costura `0.0000 mm` y Mipmaps RGB/A Separados** | Desplazar el cuello abre grietas con la camiseta; redimensionar `RGBA` en Pillow premultiplica a negro `(0,0,0)` en los mipmaps `1..10`. | • Bloqueo estricto **`0.0000 mm`** por debajo de `neck_lock_y` (`chin_y - 0.28 dm`).<br>• Trasladar `LeftEye_zero`/`RightEye_zero` + `Eyelash-VB` + cuenca ocular exactamente `±dx` (y `eye_dz`) para cero *clipping* ni fuga de esclerótica.<br>• En `replace_sdo_tex()` (`tools/update_custom_assets.py`), escalar `RGB` y `Alpha` **por separado** en cada mipmap (`mip0_diff < 3.5`, `mip1_diff < 3.5`), conservando el tamaño exacto de chunk DDS y sincronizando `*_B_body_*.dds` con el tono del cuello. |
| **9** | **Regla Anti-Monstruo (`<= 4.5 mm` Max) + Prohibición de Torres de Pelo / RBF Pesado** | El experimento `v8` demostró que empujar el perfil 2D con RBF agresivo (`15–25 mm`) o levantar `Hair_fix-VB` en una torre alta crea narices puntiagudas tipo bruja, cráneos abombados, cabezas-cono y cuencas oculares deformadas — destruyendo el parecido humano aunque el RMSE numérico baje. | • **Límite duro de escultura**: desplazamiento facial total estrictamente **`<= 3.8–4.5 mm`** (`0.0 mm` en cuencas oculares y `0.0000 mm` en costura del cuello `Y <= neck_lock_y`). Si el alineamiento `3DDFA_V2` supera `align_rmse > 9.0 mm`, mantener geometría SEGA limpia (`0.0 mm`) + normales limpias + pelo mate + UV biométrico.<br>• **Cabello natural pegado a la frente**: en vez de levantar torres artificiales, suavizar/bajar la coronilla (`-5 mm`) y drapeado natural del flequillo (`-8` a `-10 mm` sobre la frente), manteniendo `*_N_hair_*.dds` mate (`Alpha 5..11`).<br>• **Test visual humano ("Novia Test")**: validar siempre en hoja offline (`Front / 3-4 / 90° Profile`) que el rostro sea 100% humano e inmediatamente reconocible antes de empaquetar. |

---

## 2. Tabla de Enrutamiento de Moldes Base SEGA (Auditada sobre `resource.bin`)

Cada molde `.sdo` original de SEGA posee una topología de cabeza (`Face-VB`) y tarjetas/mallas de pelo distinta. Elegir el molde correcto evita luchar contra la geometría:

| Molde SEGA Base | Vértices `Face-VB` | Mallas de Pelo 3D (`lod0`) | Accesorios Base | Ideal para Estilos / Tenistas |
|---|---:|---|---|---|
| **`P_M_DJV_IT.sdo`** | 3,208 | `Hair_fix-VB` (808 v) | — | **Rapado / *High-Fade Crop* con flequillo corto** (`26_ALC`, `27_SIN` corto, `69_NIS`, `72_CHN`) |
| **`P_M_MRY_IT.sdo`** | 2,635 | `Hair_Punch_Fix-VB` (1,821 v) | — | **Rizado / ondulado abundante** (`31_MCE` rizado, `59_SHE`, `60_RUB`, `61_RUU`, `46_TSO`) |
| **`P_M_KOH_IT.sdo`** | 3,139 | `Hair_A-VB` (464 v) + `Hair_A1-VB` (464 v) | — | **Copete corto / tupé clásico** (`49_FER`, `50_NAL`, `67_COR`) |
| **`P_M_HAS_IT.sdo`** | 2,709 | `Hair_top-VB` (1,054 v) | — | **Peinado hacia atrás / *swept-top* medio** (`38_WAW`, `42_THI`, `47_FRR`, `68_GAS`, `74_MUS`, `76_CRT`) |
| **`P_M_FED_SN.sdo`** | 2,702 | `Hair_alpha_cloth-VB` (725 v) | — | **Clásico medio con frente despejada** (`77_WLD`, `61_RUU`) |
| **`P_M_DEL_SN.sdo`** | 1,956 | `Hair_alpha_cloth-VB` (384 v) + `Hair_alpha1-VB` (541 v) | — | **Media melena / pelo liso tupido** (`39_MED`, `40_ZVE`, `43_KYR`, `45_SAF`, `54_IVN`, `62_FRI`, `70_SOD`, `71_BER`) |
| **`P_M_RAF_IT.sdo`** | 2,787 | `Hair_osage01-VB` (402 v) | `band-VB` (118 v) | **Melena larga con cinta / *headband*** (`30_BOR`, `36_KUE`, `53_VIL`, `73_RIO`) |
| **`P_M_NAD_IT.sdo`** | 2,242 | `Hair_cloth-VB` (370 v) + `Hair_fix-VB` (176 v) | Cinta / melena | **Melena larga años 90 / 2000** (`29_91_AGA`, `48_MOY`) |
| **`P_M_ROD_SN.sdo`** | 2,054 | *(sin pelo suelto)* | `Cap-VB` (479 v) | **Gorra puesta** (`44_HEW` gorra hacia atrás) |
| **`P_W_IVA_IT.sdo`** | 4,602 | `Hair_Punch_cloth-VB` (316 v) | Visera *(colapsable)* | **Coleta clásica WTA** (`65_BAD`, `56_SEL`, `58_MUG` — colapsar visera si no usa) |
| **`P_W_SHA_SN.sdo`** | 3,052 | `Hair_clothA-VB` (284 v) | — | **Coleta rubia limpia sin visera** (`32_GRA`, `64_RYB`) |
| **`P_W_KUZ_IT.sdo`** | 4,020 | `Hair_alpha_cloth-VB` (644 v) | — | **Coleta con cinta fina** (`35_SAB`) |
| **`P_W_WOZ_IT.sdo`** | 4,612 | `Hair_cloth_01-VB` (635 v) + huesos | `Cap_lodL-VB` | **Coleta con gorra WTA** (`34_SWI`, `57_HEN`) |
| **`P_W_CHA_IT.sdo`** | 4,448 | `Hair_alpha_cloth-VB` (396 v) | — | **Pelo corto / media melena WTA** (`37_NAV`, `55_EVE`, `66_HAL`, `79_ASV`) |
| **`P_W_WIL_SN.sdo`** | 3,076 | `Hair_clothA-VB` (225 v) | `WristBand-VB` | **Trenzas / recogido atlético** (`33_SER`, `63_GAU`) |
| **`P_W_ROB_IT.sdo`** | 4,656 | `Hair_punch_cloth-VB` (322 v) | — | **Coleta limpia WTA** (`80_CMT`, `81_CLI`) |

> **Nota sobre compatibilidad con `xlive.c`**: Al cambiar el molde base de un jugador, mantener siempre sincronizado su `bone_proxy` (en `proxy_bone_base[12]` para IDs `26..37` o `g_extra_players[].bone_proxy` para IDs `38..81`) con el ID original del molde SEGA base elegido.

---

## 3. Flujo Rápido `< 25s / jugador` y Cola por Lotes

### A. Verificación unitaria de referencias y fitter 3DMM (~14 ms)
```powershell
# 1. Validar que BFM3D ONNX detecta 0 NaNs y alpha_shp limpio sobre la foto neutra:
.\scratch\face3d_venv\Scripts\python.exe tools\bfm3d_fit.py scratch\real_alcaraz_3d\refs_neutral\front_neutral.jpg
```

### B. Ejecución Studio Factory para 1 jugador (`< 25s`)
```powershell
# Prueba offline (genera UV horneado + renders Front / 3-4 / Profile para QA visual antes de empaquetar):
.\scratch\face3d_venv\Scripts\python.exe -u tools\studio_face_factory.py `
  --player-id 26_ALC `
  --base-sdo P_M_DJV_IT.sdo `
  --front scratch\real_alcaraz_3d\refs_neutral\front_neutral.jpg `
  --profile scratch\real_alcaraz_3d\refs_neutral\profile_neutral.jpg `
  --hair-style high_fade_crop `
  --offline-only

# Empaquetado final en game/archive/HIGH/Player/Model/ con auditoría automática:
.\scratch\face3d_venv\Scripts\python.exe -u tools\studio_face_factory.py `
  --player-id 26_ALC `
  --base-sdo P_M_DJV_IT.sdo `
  --front scratch\real_alcaraz_3d\refs_neutral\front_neutral.jpg `
  --profile scratch\real_alcaraz_3d\refs_neutral\profile_neutral.jpg `
  --hair-style high_fade_crop `
  --out-sdo game\archive\HIGH\Player\Model\P_M_ALC_NG.sdo
```

### C. Plantilla de Cola por Lotes (Estrellas VIP en paralelo / serie rápida)
Una vez validado el piloto en vivo, basta preparar la pareja `(front_neutral.jpg, profile_neutral.jpg)` por cada tenista y disparar el lote:

```powershell
# Ejemplo de cola VIP (~20-25s por tenista):
# 27_SIN (Sinner)   : --base-sdo P_M_MRY_IT.sdo --hair-style curly_full
# 65_BAD (Badosa)   : --base-sdo P_W_IVA_IT.sdo --hair-style ponytail_no_visor
# 35_SAB (Sabalenka): --base-sdo P_W_KUZ_IT.sdo --hair-style ponytail_headband
# 39_MED (Medvedev) : --base-sdo P_M_DEL_SN.sdo --hair-style high_recede_short
# 34_SWI (Swiatek)  : --base-sdo P_W_WOZ_IT.sdo --hair-style ponytail_cap
```

---

## 4. Checklist Obligatorio de QA antes de `VT4.exe`

1. **Inspección visual de fotos neutras**: 0 sonrisa (`smile < 0.10`), 0 dientes abiertos, 0 sombras duras de flash.
2. **Inspección visual del render offline (Front + 3/4 + Left Profile + UV)**:
   - Ojos centrados, 0 fuga de esclerótica blanca en perfil.
   - Orejas pegadas y sin rayas horizontales.
   - Pelo 3D con volumen en coronilla y flequillo natural, **mate** (sin brillo de plástico) y **sin reflejos grises/blancos** en los laterales.
   - Cuello coincidente en tono con el cuerpo y **`neck_seam == 0.0000 mm`**.
3. **Verificación binaria automática**: `0` NaN/Inf, `mip0_diff < 3.5`, `mip1_diff < 3.5`, tamaño exacto de slots DDS intacto.
4. **Verificación en vivo (`VT4.exe`)**: Captura frontal, 3/4 y perfil sin HUD obstruyendo el rostro, `ps=0 ex=0 exc=0`, audio nativo activo, y limpieza completa de `game/` (`0` `VT4.exe`, `0` PNGs, `0` logs).

---

## 5. Protocolo Definitivo Aprobado (`TEST 2D`): Geometría Zero-Monster + Identidad Biométrica Local (`local_identity_uv.py`) + Canvas Nano Banana / AI Studio (`< 6s/jugador`)

El estándar definitivo aprobado tras el **"Novia Test" (`26_ALC` `TEST 2D`, `ArcFace_cos_sim = 0.505`)** y escalado a los **57/57 tenistas (`tools/batch_studio_57.py`)** combina:

1. **Geometría Zero-Monster (`<= 3.8–4.5 mm`, `0.0 mm` ojos, `0.0000 mm` cuello)**:
   - **PROHIBIDO** aplicar RBF de perfil agresivo (`> 4.5 mm`) ni levantar torres de pelo (`groom_3d_hair` estilo v8).
   - Usar únicamente micro-escultura humana suave (`3DDFA_V2` ONNX `alpha_exp=0` acotado a `<= 3.8–4.5 mm`, o `0.0 mm` si `align_rmse > 9.0 mm`), `0.0 mm` de deformación en párpados/cuencas (solo traslación rígida sincronizada con `LeftEye_zero`/`RightEye_zero`/`Eyelash`), y bloqueo estricto `0.0000 mm` bajo la costura del cuello.
2. **Canvas Base Limpio (`1024x1024`) — Existente o Mejorado con Nano Banana / Google AI Studio**:
   - Aporta el lienzo estructural perfecto (pelo, *high fade*, orejas limpias, cintas/gorras, cuello y tono de piel) anclado 1:1 al UV base de cada molde SEGA (sin nombres de celebridades en archivos temporales).
3. **Transferencia Biométrica Local Sin Filtros (`tools/local_identity_uv.py`, `< 3s` en caliente)**:
   - Motor **100% ONNX local** (`arcface_w600k_r50.onnx` + `inswapper_128_fp16.onnx` + `gfpgan_1.4.onnx`) contenido estrictamente dentro de `scratch/local_faceswap/` (0 PyTorch, 0 `insightface` Cython, 0 archivos en `C:\Users\<user>\.insightface` — borrable sin rastro eliminando esa única carpeta).
   - Promedia los vectores biométricos 512-d ArcFace de 2–3 retratos frontales neutros verificados del tenista real, rellena temporalmente las cuencas oculares oscuras para fijar los 5 landmarks, transfiere la identidad biométrica real con `inswapper_128_fp16`, restaura poros/cejas/labios en 512×512 con `gfpgan_1.4`, iguala color en espacio LAB y **restaura con dilatación (`+4 px`) el recorte oscuro exacto de las cuencas oculares** desde el UV base del propio molde (cero restos de esclerótica blanca pintada, compatible con los 19 moldes SEGA masculinos y femeninos `UV_EYE_Y ~ 0.39` y `~ 0.16`).
4. **Ensamblado Masivo y Materiales DX9 (`tools/batch_studio_57.py`, `< 6s/jugador`)**:
   - Inyecta el UV biométrico en `*_B_face_*.dds`, genera mapas normales limpios `(128,128,255)` (`*_N_face_*` / `*_N_face_sweat_*` con Alpha especular mate en pelo `~5` y satinado en piel `38..62`), actualiza `*_SS_face_*.dds` (SSS cálido en piel + mate `[6,5,4]` en cuero cabelludo/cejas), fuerza `*_N_hair_*.dds` mate (`Alpha 5..11`), sincroniza `*_B_body_*.dds` en LAB, aplica ojos HD 4× (`*_B_eye_*.dds`), guarda copia de seguridad en `scratch/sdo_backups_pre57/` y verifica `mip0_diff < 3.5` y `mip1_diff < 3.5`.
   ```powershell
   # Generar UV biométrico local para 1 tenista (< 3s):
   .\scratch\face3d_venv\Scripts\python.exe tools\local_identity_uv.py --src-photos ref1.jpg ref2.jpg --target-uv canvas.png --template-uv base_uv.png --out out_uv.png

   # Procesar todo el roster 57/57 o re-empaquetar VIPs con canvas Nano Banana en < 6s/jugador:
   .\scratch\face3d_venv\Scripts\python.exe tools\batch_studio_57.py --only 27_SIN,39_MED --canvas-dir scratch\uv_lab\canvas_overrides
   ```

---

## 6. Resultados Verificados del Lote Completo `57/57` (`v2 Full-Polish` + Google AI Studio `Nano Banana 2.1`)

- **Tasa de aprobación**: **`57/57 PASS (100%)`** en los 19 moldes base masculinos y femeninos de SEGA (`UV_EYE_Y = 0.14..0.40`).
- **Salto biométrico (`ArcFace_cos_sim`)**: media global **`0.031 -> 0.376`** (**+12.1×**), con picos en `35_SAB` (`0.512`), `32_GRA` (`0.508`), `26_ALC` (`0.505`), `27_SIN` (`0.487`), `68_GAS` (`0.483`), `36_KUE` (`0.479`), `47_FRR` (`0.479`), `44_HEW` (`0.474`), `43_KYR` (`0.457`), `78_LAV` (`0.457`).
- **Invariantes geométricos y binarios (`57/57`)**:
  - `MAX_NECK_MM = 0.0000 mm` (cero grietas en cuello),
  - `MAX_SCULPT_MM <= 4.50 mm` (`<= 2.67 mm` en los 56 tenistas del lote, `0.0 mm` de distorsión en cuencas oculares, auto-skip seguro a `0.0 mm` cuando `align_rmse > 9.0 mm`),
  - `MAX_MIP0 = 2.61 < 3.5`, `MAX_MIP1 = 2.52 < 3.5`, `0` NaN/Inf.
- **Correcciones universales incorporadas en `tools/local_identity_uv.py` y `tools/batch_studio_57.py`**:
  1. **Pre-normalización anisotrópica de aspecto UV**: estira automáticamente moldes anisotrópicos (`P_M_EDB_SN` `0.726`, `P_M_BEC_SN` `0.846`, `P_M_NAD_IT` `0.892`, `P_W_IVA_IT` `1.168`, `P_M_FED_SN` `1.165`) a proporción facial isotrópica `1:1` (`0.866`) antes de `inswapper_128 + gfpgan_1.4` y deshace el escalado al volver a `1024x1024`.
  2. **Closed-Mouth Lip Guard (pre y post-GFPGAN)**: cierra hendiduras bucales oscuras antes de GFPGAN y suprime dientes blancos pintados / cavidades negras tras GFPGAN, restaurando bermellón labial cerrado natural.
  3. **Base de datos verificada 57/57 (`tools/roster_verified_57.json`) + Ojos HD 4× de 8 paletas naturales**: genera `*_B_eye_*.dds` con colores de iris naturales desaturados y anillo limbal oscuro (`ice_blue`, `blue`, `blue_green`, `green`, `hazel_green`, `hazel`, `brown`, `dark_brown`) centrados sobre la pupila real (`sum(RGB) < 75`).
  4. **Eliminación automática de bandana cian en `P_M_DEL_SN`**: detecta y reemplaza tela cian superior (`Y < 190`) por hebras de cabello mate del color verificado del jugador.
- **Limpieza sin rastro (`Zero-Trace Containment`)**: todos los modelos ONNX (`arcface_w600k_r50.onnx`, `inswapper_128_fp16.onnx`, `gfpgan_1.4.onnx`) y cachés viven exclusivamente dentro de `scratch/local_faceswap/` (`C:\Users\<user>\.insightface` no existe). Al finalizar el proyecto, basta ejecutar `Remove-Item -Recurse -Force scratch\local_faceswap` para eliminar los ~792 MB sin dejar rastro en el sistema.
