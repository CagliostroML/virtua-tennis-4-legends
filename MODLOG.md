# Virtua Tennis 4 — Modding & Reverse Engineering Log (`MODLOG.md`)

## Session 1 — 2026-11-07
### Goal
Build **Virtua Tennis 4: Legends & Next-Gen Edition** (64-player historical + modern roster up to Alcaraz & Sinner, 5 Arcade Multiverse Easter Eggs, and 6 Engine/QoL features), tracked in [ROADMAP_ROSTER.md](file:///c:/Users/acorr/Documents/tenis/ROADMAP_ROSTER.md).

### Environment & Tooling
- **REA (`rea-agents@6.8.0`)**: Installed locally in `tools/rea` with portable Node `24.22.2` (`tools/node24`), OpenJDK `21.0.13` (`tools/jdk21`), and Ghidra `12.1.4` (`tools/ghidra_12.1.4_PUBLIC`). Wrapper: `tools/rea.cmd`.
- **Universal Modder (`um`)**: Installed locally in `tools/universal-modder/bin/um.cmd`.
- **Source ISO**: `sr-vt4.iso` (2,976,198,656 bytes), mounted on `D:\` and extracting via `msiexec /a` into `c:\Users\acorr\Documents\tenis\game`.
