import pefile, capstone
pe = pefile.PE('game/VT4.exe')
base = pe.OPTIONAL_HEADER.ImageBase
with open('game/VT4.exe', 'rb') as f:
    data = f.read()
# Search backwards from 0x0043eb00 for 55 8b ec (push ebp; mov ebp, esp) or 83 ec (sub esp)
for s in pe.sections:
    va = base + s.VirtualAddress
    sz = s.SizeOfRawData
    if va <= 0x0043eb00 < va + sz:
        start_off = s.PointerToRawData + (0x0043ea80 - va)
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        for i in md.disasm(data[start_off:start_off+0x80], 0x0043ea80):
            print(f'0x{i.address:08x}: {i.mnemonic} {i.op_str}')
