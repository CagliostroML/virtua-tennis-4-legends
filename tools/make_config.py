"""Generate game/save/Config.txt for VT4 (UTF-16LE w/ BOM), layout reversed from FUN_00403900.

Line -> field (offsets from config struct 0x00a75bd0):
 1 str  +0x134 AudioDeviceName
 2 str  +0x118 AudioDeviceId
 3 str  +0xe0  mGraphicsDeviceName
 4 str  +0xfc  mGraphicsDeviceId
 5 str  +0xc4  mGraphicsDisplayId
 6 int  +0x154 width
 7 int  +0x158 height
 8 int  +0x150 adapter/refresh
 9 int  +0x1b0 Option3d
10 int  +0x1ac AntiAliasQuality
11 bool +0x1b4 EnablePostProcess
12 bool +0x1a8 mSM30 (HW vertex processing)
13 bool +0x1b5 VSync
14-17 controller slots (FUN_00402fa0) -> Type PadNumber Layout Vibrate
18 N device keymap entries (mGuidList.Count)
For each entry:
  GUID line
  16 lines of 19 space-separated ints (4 players x 4 layouts):
    Buttons[10] UpDownType UpDownIdx LeftRightType LeftRightIdx DigitalType DigitalIdx[4]
"""
import os, sys

W, H = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (1280, 720)
NONE = "00000000-0000-0000-0000-000000000000"
KBD  = "00000001-0000-0000-0000-000000000000"
XBOX = "00000002-0000-0000-0000-000000000000"

# Default Keyboard Config line (19 values):
# Buttons: 90 ('Z'/Lob), 88 ('X'/Slice), 67 ('C'/TopSpin/Confirm), 86 ('V'/DropShot),
#          100 (Num4), 102 (Num6), 103 (Num7), 105 (Num9), 83 ('S'/Select), 32 (Space/Start)
# AnalogueUpDown: Type=0, Idx=255
# AnalogueLeftRight: Type=0, Idx=255
# DigitalAxis: Type=2 (Keyboard arrows), Idx = 38 (Up), 40 (Down), 37 (Left), 39 (Right)
KBD_MAP_LINE = "90 88 67 86 100 102 103 105 83 32 0 255 0 255 2 38 40 37 39"

lines = [
    "LegendsMod", "LegendsMod", "", "(#0)", "",
    str(W), str(H), "0",
    "0", "0", "0", "1", "1",
    f"{KBD} {KBD} 0 0",    # Player 1: Keyboard
    f"{XBOX} {XBOX} 0 0",  # Player 2: Xbox Gamepad
    f"{NONE} {NONE} 0 0",  # Player 3: None
    f"{NONE} {NONE} 0 0",  # Player 4: None
    "1",                   # 1 custom device mapped in mGuidList
    KBD,                   # Device GUID: Keyboard
]
# 16 lines for Player 1..4 x Layout 1..4
for _ in range(16):
    lines.append(KBD_MAP_LINE)

content = "\r\n".join(lines) + "\r\n"
out = os.path.join(os.path.dirname(__file__), "..", "game", "save", "Config.txt")
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "wb") as f:
    f.write(b"\xff\xfe" + content.encode("utf-16le"))
print("Config.txt ->", os.path.abspath(out), f"{W}x{H} (Keyboard mapping enabled: 1 device, 16 layout lines)")
