import os
import struct

BIN0 = r"c:\Users\acorr\Documents\tenis\game\resource.bin"
BIN1 = r"c:\Users\acorr\Documents\tenis\game\resource.1.bin"

def lzss_decompress(comp_bytes):
    uncomp_size, comp_size = struct.unpack(">II", comp_bytes[:8])
    out = bytearray(uncomp_size)
    src = comp_bytes[8:8 + comp_size]
    sp = 0
    dp = 0
    slen = len(src)
    while sp < slen and dp < uncomp_size:
        b = src[sp]
        sp += 1
        if b < 0x80:
            run = b + 1
            out[dp:dp + run] = src[sp:sp + run]
            sp += run
            dp += run
        else:
            b2 = src[sp]
            sp += 1
            length = (b & 0x0f) + 3
            dist = (((b & 0x70) << 4) | b2) + 1
            for _ in range(length):
                out[dp] = out[dp - dist]
                dp += 1
    return bytes(out)

size1 = os.path.getsize(BIN1)
with open(BIN1, "rb") as f1:
    f1.seek(size1 - 4)
    dir_pos = struct.unpack(">I", f1.read(4))[0]
    dir_len = (size1 - 4) - dir_pos
    print(f"Directory offset in resource.1.bin: 0x{dir_pos:x}, compressed length: {dir_len} (0x{dir_len:x})")
    f1.seek(dir_pos)
    comp_dir = f1.read(dir_len)
    uncomp_size, comp_size = struct.unpack(">II", comp_dir[:8])
    print(f"Header: uncomp_size={uncomp_size} (0x{uncomp_size:x}), comp_size={comp_size} (0x{comp_size:x})")
    raw_dir = lzss_decompress(comp_dir)
    print(f"Decompressed directory size: {len(raw_dir)} bytes")
    count = struct.unpack(">I", raw_dir[:4])[0]
    print(f"Total files in archive: {count}")
    pos = 4
    entries = []
    for i in range(count):
        val1, val2, val3 = struct.unpack(">III", raw_dir[pos:pos+12])
        vol = struct.unpack("b", raw_dir[pos+12:pos+13])[0]
        end = raw_dir.find(b"\x00", pos+13)
        name = raw_dir[pos+13:end].decode("ascii", errors="replace")
        pos = end + 1
        entries.append((i, val1, val2, val3, vol, name))

    print("\nFirst 20 files:")
    for e in entries[:20]:
        print(f"  [{e[0]:4d}] vol={e[4]:2d} off=0x{e[1]:08x} csize=0x{e[2]:08x} usize=0x{e[3]:08x} {e[5]}")

    print("\nMatching 'fwdatadb' or 'chara' or 'player' or 'unlock' or 'rafter':")
    for e in entries:
        low = e[5].lower()
        if any(k in low for k in ["fwdatadb", "chara", "unlock", "raf", "option", "select"]):
            print(f"  [{e[0]:4d}] vol={e[4]:2d} off=0x{e[1]:08x} csize=0x{e[2]:08x} usize=0x{e[3]:08x} {e[5]}")
