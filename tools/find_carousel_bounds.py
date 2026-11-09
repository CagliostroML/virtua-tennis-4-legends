import pefile, capstone
pe = pefile.PE('game/VT4.exe')
base = pe.OPTIONAL_HEADER.ImageBase
with open('game/VT4.exe', 'rb') as f:
    data = f.read()

# Search for references to [reg+0x6c] or carousel modulo
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
for s in pe.sections:
    va = base + s.VirtualAddress
    sz = s.SizeOfRawData
    if s.Name.decode().strip("\x00") == ".text":
        code = data[s.PointerToRawData : s.PointerToRawData + sz]
        for i in range(len(code)-7):
            # look for cmp reg, 0xa or cmp [reg+6c], 0xa or idiv / div with 10
            # or mov [reg+0x6c], 10
            chunk = code[i:i+7]
            if chunk[:3] == b'\xc7\x46\x6c' and chunk[3] == 0x0a:
                print(f"mov [esi+6c], 10 at 0x{va+i:08x}")
            elif chunk[:3] == b'\x83\xfe\x0a' or chunk[:3] == b'\x83\xf8\x0a':
                print(f"cmp reg, 10 at 0x{va+i:08x}")
