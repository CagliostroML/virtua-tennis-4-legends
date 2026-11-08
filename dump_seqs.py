import pefile
import struct

pe = pefile.PE('c:/Users/acorr/Documents/tenis/game/VT4.exe')
base = pe.OPTIONAL_HEADER.ImageBase
with open('c:/Users/acorr/Documents/tenis/game/VT4.exe', 'rb') as f:
    data = f.read()

off = pe.get_offset_from_rva(0x0081F3D0 - base)
for i in range(30):
    s_ptr = struct.unpack('<I', data[off + i*8 : off + i*8 + 4])[0]
    fn_ptr = struct.unpack('<I', data[off + i*8 + 4 : off + i*8 + 8])[0]
    if s_ptr == 0: break
    try:
        s_off = pe.get_offset_from_rva(s_ptr - base)
        s_name = data[s_off:s_off+30].split(b'\0')[0].decode('latin1', 'ignore')
        print(f'Seq[{i}]: "{s_name}" (str=0x{s_ptr:08X}, ctor=0x{fn_ptr:08X})')
    except Exception as e:
        print(f'Seq[{i}]: str=0x{s_ptr:08X}, ctor=0x{fn_ptr:08X} ({e})')
