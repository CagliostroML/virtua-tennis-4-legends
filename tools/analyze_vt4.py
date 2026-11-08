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

def find_string_and_xrefs(s_bytes):
    for m in re.finditer(re.escape(s_bytes), data):
        roff = m.start()
        va = roff_to_va(roff)
        if not va:
            continue
        start = roff
        while start > 0 and 32 <= data[start-1] < 127:
            start -= 1
        end = data.find(b'\x00', roff)
        full_str = data[start:end].decode('ascii', 'ignore')
        full_va = roff_to_va(start)
        refs = []
        # Notice some strings in VT4 start with 'N=.\src\...' where code references either 'N=...' or '.\src\...'
        for cand_off in range(start, roff + 1):
            cand_va = roff_to_va(cand_off)
            pat = struct.pack('<I', cand_va)
            for r in re.finditer(re.escape(pat), data):
                r_va = roff_to_va(r.start())
                if r_va:
                    refs.append((hex(r_va), hex(cand_va)))
        print(f'String "{full_str}" at VA 0x{full_va:08x} -> refs: {refs}')

for kw in [
    b'CharacterList.cpp',
    b'PlayerManager.cpp',
    b'Player.cpp',
    b'PlayStyleParameter.cpp',
    b'UnlockChecker.cpp',
    b'UnlockManager.cpp',
    b'FPCharaSelect.cpp',
    b'PlayerSelect.cpp',
    b'TourPlayerSelect.cpp',
    b'FPEditBasicPlayerSelect.cpp',
    b'GameSpeedManager.cpp',
    b'CameraList.cpp',
    b'MatchCamera.cpp',
    b'OptionMode.cpp',
]:
    find_string_and_xrefs(kw)

print("\n=== Checking references to 0x00821840..0x008218d0 ===")
text_data = data[0x400:0x400+0x384a00]
for addr in range(0x00821840, 0x008218d0, 4):
    pat = struct.pack('<I', addr)
    for r in re.finditer(re.escape(pat), data):
        r_va = roff_to_va(r.start())
        print(f'Ref to 0x{addr:08x} at VA 0x{r_va:08x} (roff 0x{r.start():06x})')
