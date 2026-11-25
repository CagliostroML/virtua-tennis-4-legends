# 🚀 Plan de Implementación e Informe de Buenas Prácticas — Actualización Integral Next-Gen (`Virtua Tennis 4: Legends & Next-Gen Edition`)

Documento técnico de arquitectura, estándares de seguridad binaria/gráfica y criterios de validación para el salto visual **All-In-One Next-Gen** sobre los **57 tenistas personalizados** (`26_ALC`..`81_CLI`, incluyendo `29_91_AGA` y `29_AG2`) y el motor **DirectX 9 (`xlive.dll`)**.

---

## 1. Arquitectura del Salto Next-Gen (Los 3 Pilares Simultáneos)

| Pilar | Componente / Archivo | Objetivo Técnico y Visual |
|---|---|---|
| **Pilar 1: Rostros, Ojos HD, Microporos y Geometría 3D** | `tools/build_all_sdo_models.py`<br>`tools/import_edited_face_uvs.py`<br>`tools/sculpt_sdo_head.py`<br>`game/archive/HIGH/Player/Model/*.sdo` | • **Ojos e iris fotorrealistas (`*_B_eye_*.dds`)**: Sustitución de los ojos planos de 2011 por iris supersampled con fibras radiales, anillo limbal oscuro, pupila nítida, sombreado escleral y reflejo corneal (*catchlight*) adaptado al color real de ojos de cada tenista (marrón oscuro en Alcaraz/Badosa/Nadal/Medvedev; avellana/verde-azul en Sinner/Sabalenka/Borg/Graf/Rybakina/Świątek/Zverev).<br>• **Normales multiescala con microporos (`*_N_face_*.dds` y `*_N_face_sweat_*.dds`)**: Síntesis de relieve facial multiescala a partir del UV 1024×1024 editado (cejas, párpados, pliegue nasal, labios, barba incipiente) + grano orgánico de microporos cutáneos y suavizado de `*_SS_face_*.dds` para eliminar el brillo plástico.<br>• **Eliminación de accesorios heredados erróneos**: Ocultación/colapso limpio de viseras o gorras del molde SEGA donante cuando no corresponden al look real (ej. eliminación de la visera oscura heredada de Ivanovic en **`65_BAD` Paula Badosa**).<br>• **Esculpido 3D anatómico + `eye_spacing`**: Morfología 3D por tenista con separación ocular simétrica (`LeftEye_zero`/`RightEye_zero` + pestañas + cuencas + glabela) y bloqueo estricto de costura de cuello (`0.0000 mm`). |
| **Pilar 2: Post-Procesado DirectX 9 Nativo (`NextGenFX`)** | `src/xlive/nextgen_fx.h`<br>`src/xlive/xlive.c`<br>`game/xlive.dll` | • **Shader `ps_3_0` integrado en `xlive.dll`** (sin depender de DLLs externas de ReShade): captura el backbuffer antes de `Present` (`GetBackBuffer` → `StretchRect` a textura `D3DUSAGE_RENDERTARGET`) y dibuja un quad a pantalla completa.<br>• **Nitidez Adaptativa (estilo AMD FidelityFX CAS)**: Recupera microdetalle en poros, pelo, equipaciones y textura de pista sin halos ni artefactos.<br>• **Tone-Mapping Fílmico ACES + Colorimetría de Piel Natural**: Elimina el velo amarillento/lavado de 2011, profundiza sombras y mantiene blancos puros y colores de pista vivos.<br>• **Micro-contraste Local / Claridad Sutil**: Realza el volumen 3D en nariz, pómulos, mandíbula y pliegues de ropa manteniendo el HUD/texto 100 % nítido.<br>• **Control en vivo (`F8`) y `vt4_settings.ini`**: Claves `NextGenFX=1`, `NextGenSharpen=0.65`, `NextGenFilmic=1` bajo `[Graphics]`, con conmutación instantánea en partido mediante la tecla **`F8`**. |
| **Pilar 3: Perfiles Multiplataforma (PC Ultra / Esports / Android)** | `src/xlive/perf_opt.h`<br>`game/vt4_settings.ini`<br>`ANDROID_SETUP_GUIDE.md` | • **`PerfProfile=0` (Ultra PC)** y **`PerfProfile=1` (Esports)**: `NextGenFX=1` activo por defecto a **60.00 FPS** clavados con frame pacer híbrido QPC + caché I/O en memoria (`0` syscalls de disco en partido).<br>• **`PerfProfile=2` (Android / Winlator / DXVK / Turnip)**: Auto-desactiva `NextGenFX` por defecto (salvo que se fuerce explícitamente) para proteger el ancho de banda de memoria GPU móvil, la batería y la temperatura, manteniendo **60.00 FPS** estables con sombras 512×512 y bloom 256×128. |

---

## 2. Informe de Buenas Prácticas Técnicas y Reglas de Seguridad

### 2.1. Integridad Binaria y Topológica de Modelos `.sdo`
1. **Invarianza de tamaño de chunks DDS y mipmaps**:
   - Todo reemplazo de texturas dentro de un `.sdo` (`*_B_face_*`, `*_N_face_*`, `*_N_face_sweat_*`, `*_SS_face_*`, `*_B_eye_*`, `*_B_hair_*`) mantiene exactamente las dimensiones, formato FourCC (`DXT1`/`DXT5`), número de mipmaps y tamaño en bytes del slot original, evitando desalinear las tablas internas de offsets del `.sdo`.
2. **Escalado independiente de canales RGB y Alpha en mipmaps (`replace_sdo_tex`)**:
   - **Prohibido** redimensionar imágenes `RGBA` directamente en Pillow (la premultiplicación por `Alpha=0` en máscaras de oclusión ambiental tiñe de negro `RGB(0,0,0)` los mipmaps `1..10`, creando bandas negras en frente y cuello).
   - Siempre separar `r, g, b, a = cur.split()`, redimensionar `RGB` y `A` por separado con `Image.LANCZOS` y recombinar en cada nivel de mipmap (`max_diff < 3.5` en mip-0 y mip-1).
3. **Bloqueo estricto de costura de cuello (`0.0000 mm`)**:
   - Todo desplazamiento de vértices en `Face-VB` y `Face_lodL-VB` aplica peso `0.0` por debajo de `neck_lock_y` (`chin_y - 0.28 dm`), con rampa suave C1 hacia la mandíbula. Garantiza **0 huecos o grietas** entre cabeza y torso en cualquier animación.
4. **Preservación de rigging ocular, parpadeo y boca**:
   - El ajuste `eye_spacing` traslada rígidamente los huesos `LeftEye_zero` y `RightEye_zero` junto con `Eyelash-VB`, `Eyelash_lodL-VB` y los vértices de la cuenca ocular en `Face-VB`/`Face_lodL-VB` en la misma magnitud exacta `±dx`, preservando el pivote de rotación del globo ocular y evitando cualquier *clipping* al parpadear.
5. **Colapso limpio de accesorios no deseados (viseras/gorras)**:
   - Cuando un modelo base incluye geometría de visera/gorra que no corresponde al tenista real (ej. `65_BAD`), se neutraliza limpiamente sin eliminar buffers del `.sdo` ni alterar el orden de `VertexBuffer`/`IndexBuffer` que espera el ejecutable.

---

### 2.2. Seguridad DirectX 9 y Compatibilidad Wine / Winlator (`src/xlive/nextgen_fx.h`)
1. **Aislamiento completo de estado D3D9 (`IDirect3DStateBlock9`)**:
   - Antes de dibujar el pase fullscreen de `NextGenFX`, se captura el estado completo del dispositivo (`D3DSBT_ALL` o bloque explícito de RenderStates, SamplerStates, Vertex/Pixel Shaders, VertexDeclaration y StreamSource) y se restaura inmediatamente después, evitando parpadeos o corrupción en la UI/HUD de SEGA.
2. **Gestión segura de `IDirect3DDevice9::Reset` (`hk_Reset`)**:
   - Toda textura `D3DPOOL_DEFAULT` (`D3DUSAGE_RENDERTARGET`), superficie (`IDirect3DSurface9`) y `IDirect3DStateBlock9` creada por `NextGenFX` **debe liberarse (`Release()`) obligatoriamente antes de invocar al `Reset` real** y recrearse bajo demanda en el siguiente `Present`. Esto evita cuelgues al cambiar resolución o hacer `Alt+Tab`.
3. **Fallback sin fallos (Zero-Crash Shader Loading)**:
   - Preferir bytecode `ps_3_0` precompilado embebido en `nextgen_fx.h` (o carga dinámica opcional de `d3dcompiler_43.dll` / `d3dx9_43.dll` con `LoadLibraryA`). Si el hardware o contenedor Android/Wine no soporta el pase, `NextGenFX` se desactiva limpiamente sin afectar al juego.

---

### 2.3. Pipeline 100 % Reproducible desde Scripts

Cualquier cambio en modelos, caras, cabellos, ojos, normales o esculpido 3D se regenera de extremo a extremo con 3 comandos deterministas:

```powershell
# Paso 1: Reconstruir los 57 .sdo base (físico 3D, equipaciones, color de pelo por luminancia y limpieza de viseras)
python -u tools/build_all_sdo_models.py

# Paso 2: Inyectar las 57 caras UV editadas (mipmaps RGB/A separados + ojos HD + normales microporo + suavizado especular/AO)
python -u tools/import_edited_face_uvs.py

# Paso 3: Aplicar esculpido craneal/facial 3D + eye_spacing simétrico + auditoría automática 57/57
python -u tools/sculpt_sdo_head.py --all
```

Para recompilar el motor `xlive.dll` (con `perf_opt.h`, `voice_packs.h` y `nextgen_fx.h`):

```powershell
powershell -ExecutionPolicy Bypass -File src\xlive\build.ps1
```

---

### 2.4. Matriz de Verificación y Control de Calidad (QA Checklist)

| Categoría | Criterio de Aceptación Obligatorio | Método de Verificación |
|---|---|---|
| **Integridad 3D (57/57 `.sdo`)** | • `max_neck_seam_disp == 0.0000 mm`<br>• `0` vértices `NaN`/`Inf`<br>• `max_disp <= 15.0 mm`<br>• `max_eye_clearance_error <= 0.15 mm` | Auditoría automática al finalizar `python -u tools/sculpt_sdo_head.py --all` |
| **Calidad de Texturas y Mipmaps** | • `mip0_diff < 3.5` y `mip1_diff < 3.5` en los 57 `.sdo`<br>• Ojos HD centrados al píxel en el iris original<br>• `65_BAD` sin visera negra heredada de Ivanovic | Verificación programática + lámina `scratch/nextgen_faces/hd_eyes_and_normals_proof.png` |
| **Compilación `xlive.dll`** | • `0` errores y `0` warnings con `zig cc -target x86-windows-gnu -O2` | `powershell -ExecutionPolicy Bypass -File src\xlive\build.ps1` |
| **Estabilidad y FPS en Vivo (`VT4.exe`)** | • **60.00 FPS** medios / **~59.9 FPS** 1% low<br>• `ps=0 ex=0 exc=0` (0 asserts, 0 excepciones)<br>• Audio nativo XAudio2 activo (`SoundPlayCalls > 0`)<br>• Conmutación en vivo `NextGenFX=0` vs `NextGenFX=1` (`F8`) sin artefactos | Partido real en `VT4.exe` + comparativa `scratch/nextgen_showcase/fx_off_vs_on.png` y galería close-up de primeros planos |
| **Higiene del Directorio `game/`** | • `0` procesos `VT4.exe` residuales<br>• `0` capturas `game/vt4_present_*.png`<br>• `0` `game/xlive_mod.log` temporales<br>• `game/vt4_settings.ini` restaurado (`PerfProfile=0`, `NextGenFX=1`) | Comprobación automática post-captura en `finally:` |
