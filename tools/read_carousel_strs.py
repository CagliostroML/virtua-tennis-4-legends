import pefile
pe = pefile.PE('game/VT4.exe')
base = pe.OPTIONAL_HEADER.ImageBase
strs = [0x7889e0, 0x788e6c, 0x7889f0, 0x7889b4, 0x7889c4, 0x78899c, 0x7889a8, 0x7889d4, 0x788990, 0x78a6dc]
with open('game/VT4.exe', 'rb') as f:
    data = f.read()
for idx, s_va in enumerate(strs):
    for s in pe.sections:
        va = base + s.VirtualAddress
        sz = s.SizeOfRawData
        if va <= s_va < va + sz:
            off = s.PointerToRawData + (s_va - va)
            end = data.find(b'\x00', off)
            st = data[off:end].decode('ascii', errors='ignore')
            print(f'Item {idx} @ 0x{s_va:08x}: "{st}"')
