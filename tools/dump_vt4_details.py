import struct
import re

with open(r'c:\Users\acorr\Documents\tenis\game\VT4.exe', 'rb') as f:
    data = f.read()

sections = [
    ('.text',  0x00001000, 0x00000400, 0x00384a00),
    ('PSFD00', 0x00386000, 0x00384e00, 0x00001e00),
    ('.rdata', 0x00388000, 0x00386c00, 0x00096600),
    ('.data',  0x0041f000, 0x0041d200, 0x00017000),
]

def roff_to_va(roff):
    for name, vaddr, r_off, r_size in sections:
        if r_off <= roff < r_off + r_size:
            return 0x00400000 + vaddr + (roff - r_off)
    return None

def va_to_roff(va):
    rva = va - 0x00400000
    for name, vaddr, r_off, r_size in sections:
        if vaddr <= rva < vaddr + r_size:
            return r_off + (rva - vaddr)
    return None

for name, center_va, span in [
    ('CharacterList.cpp', 0x007b8a88, 2000),
    ('UnlockChecker.cpp', 0x0078f340, 2500),
    ('FPCharaSelect.cpp', 0x007c5f84, 2500),
    ('OptionMode.cpp',    0x0078ae18, 1500),
]:
    roff = va_to_roff(center_va)
    if not roff:
        continue
    print(f'=== Strings around {name} (0x{center_va:08x}) ===')
    base_off = max(0, roff - 512)
    chunk = data[base_off:roff + span]
    for m in re.finditer(b'[ -~]{3,120}\x00', chunk):
        s_va = roff_to_va(base_off + m.start())
        s_txt = m.group()[:-1].decode('ascii', 'ignore')
        print(f'  0x{s_va:08x}: {s_txt}')
