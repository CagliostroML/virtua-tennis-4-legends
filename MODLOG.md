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
