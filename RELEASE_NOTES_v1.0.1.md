# Virtua Tennis 4: Legends & Next-Gen Edition — Update `v1.0.1` (`WIP`)

> **Status: Work In Progress (`WIP`)** — This is an actively developed native reverse-engineered Win32 `xlive.dll` mod loader and asset pipeline for *Virtua Tennis 4 (PC)*. Feedback and bug reports are welcome!

> **Legal Notice:** Release archives contain strictly original mod code (`xlive.dll`), original HUD/UI overlays, launch scripts, and documentation. **No SEGA executables, game DLLs, or proprietary assets are included.** You need your own legitimate PC copy of *Virtua Tennis 4*.

> **Safe Core Mode vs. Full 84-Player Roster:** Because zero SEGA/3D assets are bundled in the GitHub download, extracting `VT4_Legends-v1.0.1-Windows-x86.zip` onto your clean PC copy boots in **Safe Core Mode** (`26` original pros + unlocked `King` & `Duke` bosses, with all 60 FPS, NextGenFX, Live TV Scoreboard, ProPhysics, `4:3`/16:10 scaling, LAN Netplay, and Linux/Android compatibility fixes active). Use the Python pipeline in `tools/` on the repository to generate the full 84-player 3D `.sdo`/portrait pack and Grand Slams locally.

---

## Highlights & Fixes in `v1.0.1` (`WIP`)

- **Portable Paths & 1-Second Startup Crash Fix (`P0.1`)**: Removed all hardcoded developer paths from `xlive.dll`. All paths (`save\`, `save\Config.txt`, `xlive_mod.log`, `vt4_settings.ini`) now resolve dynamically relative to `VT4.exe`, auto-creating portable `<game_dir>\save\` and a valid UTF-16LE BOM `Config.txt` if missing.
- **Executable Signature Guard (`P0.2`)**: Verifies `0x00400000` and 5 instruction signatures of the unpacked PC v1.0 `VT4.exe` before patching memory, preventing silent corruption on mismatched/SecuROM builds and logging clearly to `xlive_mod.log`.
- **Safe Core Mode (`P0.3`)**: Clean fallback to `26+2` characters whenever custom `.sdo`/`.dds` packs have not been generated yet into `archive/HIGH/`.
- **OS Locale Auto-Detection, DPI Awareness & D3D9 Fallback (`P0.4`)**: Added `[Menu] Locale=auto` (`auto | en | es | fr | de | it | ja`), `SetProcessDPIAware()`, `[Graphics] UseD3D9Ex=1` with automatic fallback to standard `Direct3DCreate9`, and disabled automatic debug frame-1/60 PNG dumps when `DebugLog=0`.
- **Zero-`.exe` PC Package (`P0.5`)**:
  - `VT4_Legends-v1.0.1-Windows-x86.zip` contains **0 `.exe` files** (fixing Chrome/Defender heuristic warnings) alongside **`SHA256SUMS.txt`**.
  - `VT4_Legends-v1.0.1-Android-Launcher.zip` ships the optional zero-CRT `PLAY_VT4_LEGENDS.exe` launcher (with embedded crest icon), `dxvk.conf`, `vt4_legends_icon.png`, and `VT4_Legends_Winlator.desktop`.
- **Steam Deck & Linux Support (`P1.1`)**: Added `launch_linux.sh` (auto-detects `umu-run`, Proton, or Wine + `--deck` flag), [`LINUX_STEAMDECK_GUIDE.md`](LINUX_STEAMDECK_GUIDE.md), and native **`1280x800 (Steam Deck 16:10)`** resolution preset.
- **4:3 Arcade Cabinet Support (`P1.2`)**: Added **`1024x768 (4:3 Arcade)`**, **`1280x960 (4:3 HD)`**, and **`1600x1200 (4:3 UXGA)`** presets with uniform `1:1` HUD scaling and centered `CharaSelect` overlay alignment.
- **RecompLauncher Integration (`P1.3`)**: Added [`recomplauncher.json`](recomplauncher.json), `vt4_recomp_prepare.bat`, and [`tools/setup_vt4_legends.py`](tools/setup_vt4_legends.py) (`--verify-only`, `prepare`).
- **Wine / Winlator / Proton & Android Vortek+DXVK Fixes (`P1.4`)**:
  - Runtime bypass for `IGameExplorer` Parental Controls (`0x00404f20`, fixing *"Fatal Error! User does not have privileges to access this application"* under Wine/Winlator/Proton) and `SM_REMOTESESSION` (`0x0040533a` -> `0xEB` for Remote Play).
  - Full XInput (`1_4`/`1_3`/`9_1_0`, ports `0..3`) + `winmm.dll!joyGetPosEx` polling, P1 pad slot unlock (`0x00835ee8`), full return-of-serve input fix (`0x008232d1`), gamepad navigation in custom `GRAFICOS HD Y LEGENDS` / `EN LINEA` menus, and right-click/double-tap accidental back guard in menus.
  - Fixed `0xc0000005` underhand-serve crash (`0x00419F42` / `0x004e06f0`) via slot motion bank pre-validation in `hk_GetMotionData`.
  - Fixed loading-screen bio/nationality lookup for all 58 custom players (`hk_Loading_SetBioCard` @ `0x005e5e0e` + isolating `TR_COMMON.sto` country tables `15/16`).
  - Mobile `PerfProfile=2` turbo tuning: removed 2.8 ms Box64 spin-wait, lowered shadows (`256x256`) & bloom (`128x64`), enabled `BackBufferCount=2`, added `Width=0` / `Height=0` Auto container aspect scaling (`<=540p`), scaled `D3DXFont` proportionally, set `TouchXboxHUD=0` default for clean Winlator Virtual Gamepad usage (`[F6]` optional), and configured `PULSE_LATENCY_MSEC=90` + `DXVK_STATE_CACHE=1`.

---

## Quick Install

1. **Windows**: Extract `VT4_Legends-v1.0.1-Windows-x86.zip` next to `VT4.exe` and run `VT4.exe`.
2. **Steam Deck / Linux**: Add `VT4.exe` as a Non-Steam Game with **Proton Experimental** + `WINEDLLOVERRIDES="xlive,d3dx9_43=n,b" %command%`, or run `./launch_linux.sh --deck`.
3. **Android (Winlator / GameHub)**: See [`ANDROID_SETUP_GUIDE.md`](ANDROID_SETUP_GUIDE.md).
