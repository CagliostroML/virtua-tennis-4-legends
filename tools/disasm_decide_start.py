import pefile, capstone
pe = pefile.PE('game/VT4.exe')
base = pe.OPTIONAL_HEADER.ImageBase
with open('game/VT4.exe', 'rb') as f:
    data = f.read()

target = 0x005f7660
for s in pe.sections:
    va = base + s.VirtualAddress
    sz = s.SizeOfRawData
    if va <= target < va + sz:
        start_off = s.PointerToRawData + (target - va)
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        print(f"--- Disassembly at 0x{target:08x} ---")
        for i in md.disasm(data[start_off:start_off+0x60], target):
            print(f'0x{i.address:08x}: {i.mnemonic} {i.op_str}')
