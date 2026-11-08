import pefile

pe = pefile.PE("c:/Users/acorr/Documents/tenis/game/VT4.exe")
for section in pe.sections:
    data = section.get_data()
    for needle in [b"PlayerCreate", b"CharacterCreate", b"WorldTour", b"DiffSelect", b"Difficulty", b"SPT_Edit", b"EditPlayer"]:
        pos = 0
        while True:
            pos = data.find(needle, pos)
            if pos == -1: break
            va = 0x400000 + section.VirtualAddress + pos
            print(f"Found {needle.decode()} at VA 0x{va:08x} in {section.Name.decode().strip(chr(0))}")
            pos += len(needle)
