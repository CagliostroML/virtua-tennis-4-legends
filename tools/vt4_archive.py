import os
import sys
import struct

BIN0 = r"c:\Users\acorr\Documents\tenis\game\resource.bin"
BIN1 = r"c:\Users\acorr\Documents\tenis\game\resource.1.bin"
OUT_DIR = r"c:\Users\acorr\Documents\tenis\extracted"

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

def load_directory():
    size1 = os.path.getsize(BIN1)
    with open(BIN1, "rb") as f1:
        f1.seek(size1 - 4)
        dir_pos = struct.unpack(">I", f1.read(4))[0]
        dir_len = (size1 - 4) - dir_pos
        f1.seek(dir_pos)
        comp_dir = f1.read(dir_len)
    raw_dir = lzss_decompress(comp_dir)
    count = struct.unpack(">I", raw_dir[:4])[0]
    pos = 4
    entries = []
    for i in range(count):
        off, csize_raw, usize = struct.unpack(">III", raw_dir[pos:pos+12])
        vol = struct.unpack("b", raw_dir[pos+12:pos+13])[0]
        end = raw_dir.find(b"\x00", pos+13)
        name = raw_dir[pos+13:end].decode("ascii", errors="replace")
        pos = end + 1
        if vol == -1:
            is_comp = False
            csize = csize_raw
            parent_idx = csize_raw
        else:
            is_comp = (csize_raw & 0x80000000) != 0
            csize = csize_raw & 0x7fffffff
            parent_idx = -1
        entries.append({
            "idx": i,
            "name": name,
            "vol": vol,
            "off": off,
            "csize": csize,
            "usize": usize,
            "is_comp": is_comp,
            "parent_idx": parent_idx,
        })
    return entries

def read_entry(entries, entry, f0, f1, cache=None):
    if cache is None:
        cache = {}
    if entry["vol"] == -1:
        p_idx = entry["parent_idx"]
        if p_idx not in cache:
            p_entry = entries[p_idx]
            f = f0 if p_entry["vol"] == 0 else f1
            f.seek(p_entry["off"])
            raw = f.read(p_entry["csize"])
            # Parent containers are LZSS compressed blocks (or raw if not compressed)
            uncomp_header = struct.unpack(">II", raw[:8])
            if uncomp_header[1] + 8 == len(raw):
                cache[p_idx] = lzss_decompress(raw)
            else:
                cache[p_idx] = raw
        parent_data = cache[p_idx]
        return parent_data[entry["off"]:entry["off"] + entry["usize"]]
    else:
        f = f0 if entry["vol"] == 0 else f1
        f.seek(entry["off"])
        raw = f.read(entry["csize"])
        if entry["is_comp"]:
            return lzss_decompress(raw)
        return raw

def main():
    entries = load_directory()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "search"
    query = sys.argv[2].lower() if len(sys.argv) > 2 else ""

    if cmd == "search":
        for e in entries:
            if query in e["name"].lower():
                print(f"[{e['idx']:5d}] vol={e['vol']:2d} comp={int(e['is_comp'])} off=0x{e['off']:08x} csize=0x{e['csize']:08x} usize=0x{e['usize']:08x} {e['name']}")
    elif cmd == "extract":
        cache = {}
        with open(BIN0, "rb") as f0, open(BIN1, "rb") as f1:
            for e in entries:
                if query in e["name"].lower():
                    data = read_entry(entries, e, f0, f1, cache)
                    out_path = os.path.join(OUT_DIR, e["name"].replace("/", os.sep))
                    os.makedirs(os.path.dirname(out_path), exist_ok=True)
                    with open(out_path, "wb") as out_f:
                        out_f.write(data)
                    print(f"Extracted ({len(data)} bytes): {out_path}")

if __name__ == "__main__":
    main()
