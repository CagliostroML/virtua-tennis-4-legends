import pefile
import struct

pe = pefile.PE('c:/Users/acorr/Documents/tenis/game/VT4.exe')
with open('c:/Users/acorr/Documents/tenis/game/VT4.exe', 'rb') as f:
    data = f.read()

off_start = pe.get_offset_from_rva(0x0044DA00 - pe.OPTIONAL_HEADER.ImageBase)
off_end = pe.get_offset_from_rva(0x0044EA00 - pe.OPTIONAL_HEADER.ImageBase)

for i in range(off_start, off_end - 4):
    val = struct.unpack('<I', data[i:i+4])[0]
    if 0x00788000 <= val <= 0x00820000:
        try:
            s_off = pe.get_offset_from_rva(val - pe.OPTIONAL_HEADER.ImageBase)
            s = data[s_off:s_off+40].split(b'\0')[0]
            if len(s) > 2 and all(32 <= b <= 126 for b in s):
                va = pe.get_rva_from_offset(i) + pe.OPTIONAL_HEADER.ImageBase
                print(f'At 0x{va:08X}: string "{s.decode()}"')
        except:
            pass
