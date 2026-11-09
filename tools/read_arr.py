import pefile
pe = pefile.PE('game/VT4.exe')
base = pe.OPTIONAL_HEADER.ImageBase
with open('game/VT4.exe', 'rb') as f:
    data = f.read()

target = 0x00820654
for s in pe.sections:
    va = base + s.VirtualAddress
    sz = s.SizeOfRawData
    if va <= target < va + sz:
        start_off = s.PointerToRawData + (target - va)
        import struct
        vals = struct.unpack('<10I', data[start_off:start_off+40])
        print("Array at 0x820654:")
        for idx, v in enumerate(vals):
            print(f"[{idx}]: 0x{v:08x}")
