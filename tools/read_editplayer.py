import pefile

pe = pefile.PE("c:/Users/acorr/Documents/tenis/game/VT4.exe")

rva = 0x00827d60 - 0x400000
data = pe.get_data(rva, 600)
for chunk in data.split(b'\0'):
    if len(chunk) > 3:
        try:
            print(chunk.decode('ascii'))
        except:
            pass
