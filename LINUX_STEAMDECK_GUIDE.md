# 🐧 Linux & Steam Deck Setup Guide — Virtua Tennis 4: Legends & Next-Gen Edition

This guide covers running **Virtua Tennis 4: Legends & Next-Gen Edition (`v1.0.1+`)** cleanly on **Steam Deck (SteamOS)** and **Linux Desktop** (Proton / GE-Proton / Wine + DXVK).

> [!IMPORTANT]
> Requires a legitimate PC copy of *Virtua Tennis 4* extracted to a local folder (`VT4.exe` PC v1.0 unpacked + `resource.bin` + `resource.1.bin`) plus the contents of `VT4_Legends-v1.0.1-Windows-x86.zip` copied alongside `VT4.exe`.

---

## Method 1 — Steam Deck / SteamOS (Recommended: Non-Steam Game)

No terminal required — Proton + DXVK translates VT4's Direct3D 9 renderer to Vulkan cleanly at a locked **60 FPS**.

1. Switch to **Desktop Mode**, copy the mod files (`xlive.dll`, `archive/`, `vt4_settings.ini`, `dxvk.conf`, PNG overlays) into your VT4 folder next to `VT4.exe`.
   - *(Optional for crisp `1280x800` native Deck fill)* Open `vt4_settings.ini` and set:
     ```ini
     [Graphics]
     Width=1280
     Height=800
     Windowed=0

     [Performance]
     PerfProfile=1
     ```
     *(You can also switch to **`1280x800 (Steam Deck 16:10)`** or `1280x720` right inside **`OPCIONES -> GRÁFICOS HD Y LEGENDS`** in-game.)*
2. Open **Steam** -> **Games** -> **Add a Non-Steam Game to My Library...** -> **Browse...** -> select **`VT4.exe`**.
3. Right-click **`VT4.exe`** in Steam -> **Properties**:
   - **Compatibility** tab: check **Force the use of a specific Steam Play compatibility tool** -> select **Proton Experimental** *(or **GE-Proton**)* .
   - **Shortcut** tab -> **Launch Options**: paste this exact line:
     ```bash
     WINEDLLOVERRIDES="xlive,d3dx9_43=n,b" %command%
     ```
   - **Controller** settings in Steam: select the standard **Gamepad with Joystick Trackpad** layout so Steam Deck controls map natively to XInput (`Q`/`E` page switching maps to **`LB` / `RB`**).
4. Press **Play** (works identically in Gaming Mode!).
   - If you also want native HUD font/PNG overlays (`BroadcastHUD`, `GRÁFICOS HD`, `CharaSelect` eye-strips) and they didn't load from system libraries, either install **`d3dx9_43`** via **Protontricks** or drop your Windows `SysWOW64\d3dx9_43.dll` next to `VT4.exe`. *(Since `v1.0.1`, if `d3dx9_43.dll` is absent, the game still boots safely without crashing.)*

---

## Method 2 — Linux Desktop / Terminal (`launch_linux.sh`, Lutris, Heroic, Bottles, or RecompLauncher)

### Terminal quick launch (`launch_linux.sh`)
`VT4_Legends-v1.0.1-Windows-x86.zip` includes `launch_linux.sh` right next to `VT4.exe`:

```bash
chmod +x launch_linux.sh

# Auto-detect umu-run / Steam Proton / GE-Proton / Wine
./launch_linux.sh

# Or apply Steam Deck 1280x800 defaults cleanly on first run
./launch_linux.sh --deck
```

### Lutris / Heroic / Bottles
- Add `VT4.exe` using Wine/Proton + **DXVK** enabled.
- Add DLL Overrides (`n,b`):
  - `xlive` = `native,builtin`
  - `d3dx9_43` = `native,builtin`
  *(Leave `msvcr90`, `msvcp90`, `msvcm90`, and `xaudio2_7` on Wine/Proton's default SxS / FAudio builtin implementation.)*

### RecompLauncher (Linux / Steam Deck via Proton)
Starting with `v1.0.1`, `recomplauncher.json` defines `prepare` (`vt4_recomp_prepare.bat`) and `start.env` (`WINEDLLOVERRIDES=...`), which RecompLauncher forwards automatically to the configured Proton runtime on Linux/Steam Deck.

---

## Troubleshooting on Linux / Steam Deck

- **Starts without the 84-player mod (vanilla UI / LIVE still visible)**: `xlive.dll` override was not picked up -> double-check Steam Launch Options have `WINEDLLOVERRIDES="xlive,d3dx9_43=n,b" %command%` (let Proton use its built-in SxS `msvcr90` and FAudio `xaudio2_7`). When loaded properly, `xlive_mod.log` appears next to `VT4.exe`, and `xlive.dll` automatically bypasses the Wine/Proton `IGameExplorer` parental-controls check (`0x00404f20`) and `SM_REMOTESESSION` (`0x0040533a`).
- **Unsupported `VT4.exe` popup**: `v1.0.1` includes a PE signature guard. Make sure your `VT4.exe` is the unpacked PC v1.0 executable (`sha256: feae98d9...`, `5,059,400` bytes).
- **26+2 characters instead of 84 (`Safe Core Mode`)**: Copy the custom `.sdo` / `.dds` pack from your build (`tools/export_android_bundle.py` or `tools/` generators) into `archive/`, ensuring exact archive casing (`HIGH/Player/Model/`, `HIGH/Frontend/VR/photo_L/`).
- **Black flicker or device creation error on Mesa/older GPU**: Set `UseD3D9Ex=0` under `[Graphics]` in `vt4_settings.ini`.
- **No sound under Proton**: Verify PulseAudio/PipeWire is running and keep `xaudio2_7` on Proton's builtin FAudio rather than forcing a loose Windows DLL.
