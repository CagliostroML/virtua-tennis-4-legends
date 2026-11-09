import sys
import struct

def lzss_compress_literal(raw: bytes) -> bytes:
    """
    Compresses raw data into a Sega LZSS literal stream.
    Each literal chunk is [len-1] followed by chunk bytes (up to 128 bytes).
    Header is 8 bytes big-endian: (decompressed_size, compressed_size).
    """
    out = bytearray()
    sp = 0
    raw_len = len(raw)
    while sp < raw_len:
        run = min(128, raw_len - sp)
        out.append(run - 1)
        out.extend(raw[sp:sp+run])
        sp += run
    header = struct.pack('>II', raw_len, len(out))
    return header + bytes(out)

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python compress_sega_lzss.py <input_raw> <output_lzss>")
        sys.exit(1)
    with open(sys.argv[1], 'rb') as f:
        data = f.read()
    comp = lzss_compress_literal(data)
    with open(sys.argv[2], 'wb') as f:
        f.write(comp)
    print(f"Compressed {len(data)} -> {len(comp)} bytes to {sys.argv[2]}")
