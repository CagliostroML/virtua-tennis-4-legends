import pefile, capstone
pe = pefile.PE('game/VT4.exe')
base = pe.OPTIONAL_HEADER.ImageBase
with open('game/VT4.exe', 'rb') as f:
    data = f.read()

md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
for s in pe.sections:
    va = base + s.VirtualAddress
    sz = s.SizeOfRawData
    if va <= 0x00448000 < va + sz:
        start_off = s.PointerToRawData + (0x00448000 - va)
        code = data[start_off : start_off + 0x4000]
        for i in md.disasm(code, 0x00448000):
            if '0xc4]' in i.op_str and ('mov' in i.mnemonic):
                print(f'0x{i.address:08x}: {i.mnemonic} {i.op_str}')
