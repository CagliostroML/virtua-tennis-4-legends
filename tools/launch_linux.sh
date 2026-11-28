#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GAME_DIR=""
WINE_BIN=""
PROTON_BIN=""
DECK_PRESET=0

usage() {
    cat <<'EOF'
Virtua Tennis 4: Legends & Next-Gen Edition — Linux & Steam Deck Launcher

Usage:
  ./launch_linux.sh [options]

Options:
  --game-dir <dir>   Folder containing VT4.exe and xlive.dll (auto-detected if omitted)
  --deck             Apply Steam Deck 1280x800 16:10 + PerfProfile=1 preset if not customized
  --proton <path>    Path to Proton binary (e.g. ~/.local/share/Steam/steamapps/common/Proton - Experimental/proton)
  --wine <path>      Path to Wine binary
  -h, --help         Show this help
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --game-dir)
            GAME_DIR="${2:-}"
            shift 2
            ;;
        --deck)
            DECK_PRESET=1
            shift
            ;;
        --proton)
            PROTON_BIN="${2:-}"
            shift 2
            ;;
        --wine)
            WINE_BIN="${2:-}"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

if [[ -z "$GAME_DIR" ]]; then
    if [[ -f "$SCRIPT_DIR/VT4.exe" ]]; then
        GAME_DIR="$SCRIPT_DIR"
    elif [[ -f "$SCRIPT_DIR/../game/VT4.exe" ]]; then
        GAME_DIR="$(cd "$SCRIPT_DIR/../game" && pwd)"
    elif [[ -f "$PWD/VT4.exe" ]]; then
        GAME_DIR="$PWD"
    else
        echo "ERROR: Could not locate VT4.exe. Pass --game-dir <path> or place launch_linux.sh next to VT4.exe." >&2
        exit 1
    fi
fi

if [[ ! -f "$GAME_DIR/VT4.exe" ]]; then
    echo "ERROR: VT4.exe not found in $GAME_DIR" >&2
    exit 1
fi
if [[ ! -f "$GAME_DIR/xlive.dll" ]]; then
    echo "ERROR: xlive.dll not found in $GAME_DIR. Extract VT4_Legends-v1.0.1-Windows-x86.zip there first." >&2
    exit 1
fi

# Auto-detect Steam Deck hardware or honor --deck flag for 1280x800 16:10 defaults
if [[ "$DECK_PRESET" -eq 0 ]] && [[ -r /sys/class/dmi/id/product_name ]]; then
    PROD_NAME="$(cat /sys/class/dmi/id/product_name 2>/dev/null || true)"
    if [[ "$PROD_NAME" == *"Jupiter"* || "$PROD_NAME" == *"Galileo"* ]]; then
        DECK_PRESET=1
    fi
fi

if [[ "$DECK_PRESET" -eq 1 ]] && [[ ! -f "$GAME_DIR/vt4_settings.ini" ]]; then
    cat >"$GAME_DIR/vt4_settings.ini" <<'EOF'
[Graphics]
Width=1280
Height=800
Windowed=0
UseD3D9Ex=1
AntiAliasing=2
VSync=1
AnisotropicFiltering=8
CleanPostFX=1
NextGenFX=1
NextGenSharpen=0.20
NextGenFilmic=1

[Menu]
RemoveLiveMode=1
Locale=auto

[Gameplay]
ClassicTVCamera=0
MatchSpeedMode=0
MultiverseMode=0
WeaponMode=0
BroadcastHUD=1
ProPhysics=0
TouchXboxHUD=0

[Performance]
PerfProfile=1
UnlockFPS=0
TargetFPS=60
EOF
    echo "[VT4-Linux] Created Steam Deck preset vt4_settings.ini (1280x800, PerfProfile=1)"
fi

export WINEDLLOVERRIDES="xlive,d3dx9_43=n,b"
export WINEPREFIX="${WINEPREFIX:-$HOME/.local/share/vt4-legends-prefix}"
export STEAM_COMPAT_CLIENT_INSTALL_PATH="${STEAM_COMPAT_CLIENT_INSTALL_PATH:-$HOME/.local/share/Steam}"
export STEAM_COMPAT_DATA_PATH="${STEAM_COMPAT_DATA_PATH:-$HOME/.local/share/vt4-legends-compatdata}"

cd "$GAME_DIR"
echo "[VT4-Linux] Game dir: $GAME_DIR"
echo "[VT4-Linux] WINEDLLOVERRIDES=$WINEDLLOVERRIDES"

if [[ -n "$PROTON_BIN" ]]; then
    mkdir -p "$STEAM_COMPAT_DATA_PATH"
    exec "$PROTON_BIN" run "$GAME_DIR/VT4.exe"
fi

if [[ -n "$WINE_BIN" ]]; then
    exec "$WINE_BIN" "$GAME_DIR/VT4.exe"
fi

if command -v umu-run >/dev/null 2>&1; then
    mkdir -p "$STEAM_COMPAT_DATA_PATH"
    exec umu-run "$GAME_DIR/VT4.exe"
fi

# Search Steam Proton Experimental / Proton 9 / GE-Proton
for cand in \
    "$HOME/.local/share/Steam/steamapps/common/Proton - Experimental/proton" \
    "$HOME/.local/share/Steam/steamapps/common/Proton 9.0 (Beta)/proton" \
    "$HOME/.local/share/Steam/steamapps/common/Proton 8.0/proton" \
    "$HOME/.steam/root/compatibilitytools.d"/GE-Proton*/proton; do
    if [[ -x "$cand" ]]; then
        mkdir -p "$STEAM_COMPAT_DATA_PATH"
        echo "[VT4-Linux] Launching via Proton: $cand"
        exec "$cand" run "$GAME_DIR/VT4.exe"
    fi
done

if command -v wine >/dev/null 2>&1; then
    echo "[VT4-Linux] Launching via Wine: $(command -v wine)"
    exec wine "$GAME_DIR/VT4.exe"
fi

echo "ERROR: Neither umu-run, Steam Proton, nor wine was found in PATH." >&2
echo "On Steam Deck, add VT4.exe as a Non-Steam Game with Proton Experimental and set Launch Options to:" >&2
echo '  WINEDLLOVERRIDES="xlive,d3dx9_43=n,b" %command%' >&2
exit 1
