"""Generate game/save/Config.txt for VT4 (UTF-16LE w/ BOM), layout reversed from FUN_00403900.

Line -> field (offsets from config struct 0x00a75bd0):
 1 str  +0x134     2 str +0x118     3 str +0xe0 (adapter Description, matched vs D3D)
 4 str  +0xfc ("(#N)" adapter suffix)  5 str +0xc4
 6 int  +0x154 width   7 int +0x158 height   8 int +0x150 adapter/refresh
 9 int  +0x1b0 (value&~1)*0.01   10 int +0x1ac   11 bool +0x1b4
12 bool +0x1a8 (shader-model gate for HW vertex processing)   13 bool +0x1b5 (vsync)
14-17 controller slots (FUN_00402fa0) -> 0x00a75bd0 + slot*0x28
18 N device keymap entries, each: GUID line + 16 lines of 19 ints (FUN_00403310)
"""
import os, sys

W, H = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (1280, 720)
KBD = "00000002-0000-0000-0000-000000000000"
NONE = "00000000-0000-0000-0000-000000000000"
lines = [
    "LegendsMod", "LegendsMod", "", "(#0)", "",
    str(W), str(H), "0",
    "0", "0", "0", "1", "1",
    f"{KBD} {KBD} 0 0",
    f"{NONE} {NONE} 0 0",
    f"{NONE} {NONE} 0 0",
    f"{NONE} {NONE} 0 0",
    "0",
]
content = "\r\n".join(lines) + "\r\n"
out = os.path.join(os.path.dirname(__file__), "..", "game", "save", "Config.txt")
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "wb") as f:
    f.write(b"\xff\xfe" + content.encode("utf-16le"))
print("Config.txt ->", os.path.abspath(out), f"{W}x{H}")

