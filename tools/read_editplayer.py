import os
import pefile

pe = pefile.PE(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'game', 'VT4.exe'))

rva = 0x00827d60 - 0x400000
data = pe.get_data(rva, 600)
for chunk in data.split(b'\0'):
    if len(chunk) > 3:
        try:
            print(chunk.decode('ascii'))
        except:
            pass
