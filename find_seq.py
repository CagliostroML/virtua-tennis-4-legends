import pefile
import struct

pe = pefile.PE('c:/Users/acorr/Documents/tenis/game/VT4.exe')
base = pe.OPTIONAL_HEADER.ImageBase
with open('c:/Users/acorr/Documents/tenis/game/VT4.exe', 'rb') as f:
    data = f.read()

target = 0x00635610

for section in pe.sections:
    if section.Name.startswith(b'.text'):
        start_rva = section.VirtualAddress
        raw_start = section.PointerToRawData
        raw_end = raw_start + section.SizeOfRawData
        text_data = data[raw_start:raw_end]
        
        for i in range(5, len(text_data) - 4):
            if text_data[i] == 0xE8:
                rel = struct.unpack('<i', text_data[i+1:i+5])[0]
                call_va = base + start_rva + i
                if call_va + 5 + rel == target:
                    s_name = 'unknown'
                    if text_data[i-5] == 0x68:
                        str_va = struct.unpack('<I', text_data[i-4:i])[0]
                        try:
                            s_off = pe.get_offset_from_rva(str_va - base)
                            s_name = data[s_off:s_off+40].split(b'\0')[0].decode('latin1', 'ignore')
                        except:
                            s_name = hex(str_va)
                    print(f'Call to ChangeSeq at 0x{call_va:08X} with arg: "{s_name}"')
