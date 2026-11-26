# Virtua Tennis 4 — Modding & Reverse Engineering Log (`MODLOG.md`)

## Session 1 — 2026-11-07
### Goal
Build **Virtua Tennis 4: Legends & Next-Gen Edition** (64-player historical + modern roster up to Alcaraz & Sinner, 5 Arcade Multiverse Easter Eggs, and 6 Engine/QoL features), tracked in [ROADMAP_ROSTER.md](file:///c:/Users/acorr/Documents/tenis/ROADMAP_ROSTER.md).

### Environment & Tooling
- **REA (`rea-agents@6.8.0`)**: Installed locally in `tools/rea` with portable Node `24.22.2` (`tools/node24`), OpenJDK `21.0.13` (`tools/jdk21`), and Ghidra `12.1.4` (`tools/ghidra_12.1.4_PUBLIC`). Wrapper: `tools/rea.cmd`.
- **Universal Modder (`um`)**: Installed locally in `tools/universal-modder/bin/um.cmd`.
- **Source ISO**: `sr-vt4.iso` (2,976,198,656 bytes), mounted on `D:\` and extracting via `msiexec /a` into `c:\Users\acorr\Documents\tenis\game`.


## Session 2 — 2026-11-25
### Summary (Grand Slams, 2D Portraits, Broadcast TV HUD, Player Stats/Physics & Full Roster QA)
- **Grand Slam Stages (`tools/build_grand_slam_stages.py`)**: Built and injected all 8 `.sdo` files (Singles + Doubles) for **Australian Open (`Aus1`)**, **Roland Garros (`Fra1`)**, **Wimbledon (`Eng1`)**, and **US Open (`Usa1`)**, plus automatic extraction of `vol=-1` child locator files (`HIGH/Stage/Usa1NS_locator.zml`, `Usa1ND_locator.zml`). Verified all 4 Grand Slams live inside `VT4.exe` (`ps=0 ex=0 exc=0`).
- **2D Portraits (`tools/fix_remaining_portraits_2026.py`)**: Cut out and packed the 7 remaining portraits (`43`, `52`, `58`, `67`, `72`, `82`, `83`) into `photo_L`, `photo_eye`, and `photo_S` (`59/59` `photo_L` with transparent top corners).
- **Modern Broadcast TV HUD, Individualized Stats & Physics (`src/xlive/broadcast_hud.h`, `src/xlive/player_stats.h`, `src/xlive/voice_packs.h`, `src/xlive/xlive.c`, `game/archive/Config/Fraw/fwDataDB/fwDataDB_Stage.txt`)**:
  - Top-left Modern Broadcast TV HUD (`BroadcastHUD`, live `[F7]` toggle + Options HUD item) displaying stadium/surface, matchup, calibrated `km/h` ball radar, and `RALLY` counter.
  - Individualized stats (`player_stats.h`) for all 58 custom players (`IDs 26..83`) and expanded `VP_MAX_ROSTER_IDS = 84` (`"AND"`, `"BJK"`).
  - Surface bounce/speed differentiation in `fwDataDB_Stage.txt` (`Fra1` clay `0.95/0.70`, `Eng1` grass `0.58/0.90`, `Aus1` `0.84/0.83`, `Usa1` `0.86/0.84`, `Spa2` `0.86/0.80`) plus `ProPhysics` trajectory toggle.
- **Full QA Matrix (`tools/tests/test_roster_matrix.py`)**: Verified **20/20** remaining IDs (`60,61,62,64,65,66,67,68,69,70,71,72,74,75,76,77,80,81,82,83`, `cpu=0`, `mv=3`) with `ok=True`, `ps=0`, `ex=0`, `exc=0`, `served>=1`.
- **Loading Names, Keyboard Return-of-Serve, Touch Xbox HUD, Native Online UI & Android Exporter (`src/xlive/xlive.c`, `src/xlive/touch_gamepad.h`, `src/xlive/netplay.h`, `tools/build_netplay_ui_assets.py`, `tools/export_android_bundle.py`, `tools/prepare_future_assets_workspaces.py`)**:
  - Fixed pre-match loading screen wrong names (`0x0043CAC9` -> `hk_Loading_SetPlayerPhoto` restoring ID before `0x006693E9`, plus full bio tables `9..14`).
  - Fixed keyboard return-of-serve (`sample_p1_override_input` inspects `Player+0x248` state `4..9` + 20-tick tap buffer).
  - Added interactive recomp-style Xbox Touch HUD (`TouchXboxHUD=0|1|2`, `[F6]` hotkey, Wine auto-detect, multi-touch + mouse).
  - Replaced `EN LÍNEA` floating pop-up with full-screen pearl/magenta VT4 sprites + LAN UDP auto-discovery (`NP_PKT_DISCOVER`/`NP_PKT_OFFER`) and moved Netplay HUD to top-right.
  - Added `tools/export_android_bundle.py` (turnkey `dist/android/VT4_Legends_Android/` + case-sensitivity audit) and descriptive future sample folders (`assets/skins_alt_workspace/`, `assets/voices_workspace/`, `assets/bw_portraits_pending/`).
- **`v1.0-RC1` Closure — 84/84 Color Portraits & 1-Tap Android Launcher (`tools/pack_colorized_bw_portraits.py`, `src/launcher/play_vt4_legends.c`, `tools/export_android_bundle.py`)**:
  - Recovered and packed all 6 remaining B&W portraits (`51` Lendl, `52` Connors, `55` Evert, `74` Muster, `75` Bruguera, `77` Wilander) in full color (`photo_L` `262,272` B BGRA with transparent top corners, centered `photo_eye`, and `photo_S`; saved clean 512x512 RGB UV references for `74_MUS` and `55_EVE`), visually audited in `scratch/bw_colorized_audit.png` (`84/84` portraits in color).
  - Integrated Win32 native launcher compilation (`src/launcher/play_vt4_legends.c` -> `PLAY_VT4_LEGENDS.exe`, sets `WINEDLLOVERRIDES=xlive,d3dx9_43,msvcr90,msvcp90,msvcm90=n,b` and waits synchronously via `WaitForSingleObject`) and synchronous `LAUNCH_ANDROID.bat` into `tools/export_android_bundle.py`, plus GameHub/Winlator 1-tap Home Screen guides in `LEEME_ANDROID.txt` and `ANDROID_SETUP_GUIDE.md`.
  - Re-exported `dist/android/VT4_Legends_Android/` (`490` files, `3.62 GB`, `0` case mismatches) and verified `PLAY_VT4_LEGENDS.exe` synchronous launch & clean exit via Windows smoke-test (`0` lingering `VT4.exe` processes or logs).

## Session 3 — 2026-11-26 (`v1.0` Release & Closing QA)
- **3D Face UV Audit (`59/59` `.sdo` models)**: Verified across all 59 custom `.sdo` models (`IDs 26..83` + `Agassi '91`) that Phase 5 3DMM head sculpting + biometric UV identity + 4x-supersampled HD eyes (`_upgrade_hd_eyes`) are packed inside `game/archive/HIGH/Player/Model/`, and updated obsolete notes in `ROADMAP_ROSTER.md`.
- **Closing QA Sweep (`scratch/verify_v1_final_qa.py`, `tools/tests/test_options_ui.py`)**: Verified all 6 newly colorized portraits (`51, 52, 55, 74, 75, 77`) in `CharaSelect`, live match (`55 Evert vs 52 Connors`) with `BroadcastHUD=1`, `EXTRA-1: Unlocked 100%`, native `XAudio2` (`SoundPlayCalls=7`), `ps=0 ex=0 exc=0`, and Options HUD INI persistence (`4` valid screenshots in `scratch/qa_v1_final_sheet.png`).
- **Decomp-Style `README.md`, Screenshot Gallery & Release `v1.0`**: Added optimized gallery in `docs/screenshots/`, rewrote `README.md` following decomp/recomp repository conventions, added `RELEASE_NOTES_v1.0.md`, built clean Win32 core release archive `dist/release/VT4_Legends_v1.0_Core_Win32.zip` (zero SEGA assets), and tagged/pushed `v1.0`.
