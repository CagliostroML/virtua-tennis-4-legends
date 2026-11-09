import pefile
pe = pefile.PE('game/VT4.exe')
base = pe.OPTIONAL_HEADER.ImageBase
with open('game/VT4.exe', 'rb') as f:
    data = f.read()

target = 0x00448850
for s in pe.sections:
    va = base + s.VirtualAddress
    sz = s.SizeOfRawData
    if s.Name.decode().strip("\x00") == ".text":
        code = data[s.PointerToRawData : s.PointerToRawData + sz]
        for i in range(len(code)-5):
            if code[i] == 0xe8:
                import struct
                rel = struct.unpack('<i', code[i+1:i+5])[0]
                call_target = va + i + 5 + rel
                if call_target == target:
                    print(f"Call at 0x{va+i:08x}")
