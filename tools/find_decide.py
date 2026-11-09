import pefile, capstone
pe = pefile.PE('game/VT4.exe')
base = pe.OPTIONAL_HEADER.ImageBase
with open('game/VT4.exe', 'rb') as f:
    data = f.read()

# Let's search for references to 0x7889e0 ("WorldTourMode") or where mode selection happens
# In MainMenu, carousel selection is at [carousel + 0x2c]
# Let's find where [esi + 0xe9c + 0x2c] or [reg + 0x2c] is read in MainMenu functions (0x0043dxxx .. 0x0044xxxx)
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
for s in pe.sections:
    va = base + s.VirtualAddress
    sz = s.SizeOfRawData
    if va <= 0x0043e000 < va + sz:
        code = data[s.PointerToRawData : s.PointerToRawData + sz]
        # search in 0x0043d000 .. 0x00445000
        start_i = 0x0043d000 - va
        end_i = 0x00445000 - va
        subcode = code[start_i:end_i]
        for i in range(len(subcode)-4):
            # cmp dword ptr [reg + 0x2c] or mov reg, [reg + 0x2c]
            chunk = subcode[i:i+4]
            # 8b 40 2c / 8b 41 2c / 8b 42 2c etc.
            if chunk[0] == 0x8b and (chunk[1] & 0xc0) == 0x40 and chunk[2] == 0x2c:
                addr = 0x0043d000 + i
                print(f"mov reg, [reg+0x2c] at 0x{addr:08x}")
