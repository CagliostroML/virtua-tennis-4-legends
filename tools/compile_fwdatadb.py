#!/usr/bin/env python3
"""
Compile and inspect Virtua Tennis 4 fwDataDB binary files (.bin <-> .txt).

Binary layout (little-endian, verified byte-for-byte against fwDataDB_Player.bin):
  uint32 row_count
  row_count * (uint32 type_id, uint32 value_or_pool_offset)
    - type_id == 0: int32 signed integer value
    - type_id == 1: float32 IEEE-754 value
    - type_id == 2: uint32 byte offset into null-terminated string pool immediately following the record table
  bytes string_pool
"""

import argparse
import os
import struct
import sys


TYPE_INT = 0
TYPE_FLOAT = 1
TYPE_STRING = 2

TYPE_NAMES = {
    TYPE_INT: "int",
    TYPE_FLOAT: "float",
    TYPE_STRING: "string",
}


def parse_txt_lines(txt_path: str) -> list[tuple[str, str, str, str, str]]:
    with open(txt_path, "rb") as f:
        raw = f.read().decode("utf-8", errors="surrogateescape")

    rows = []
    for line_no, raw_line in enumerate(raw.splitlines(), 1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("#"):
            continue
        parts = stripped.split(",", 4)
        if len(parts) != 5:
            raise ValueError(f"{txt_path}:{line_no}: expected 5 comma-separated fields, got {len(parts)}: {raw_line!r}")
        rows.append((parts[0], parts[1], parts[2], parts[3], parts[4]))
    return rows


def compile_fwdatadb(txt_path: str, bin_path: str) -> bytes:
    rows = parse_txt_lines(txt_path)
    records = bytearray()
    pool = bytearray()

    for idx, (type_str, _, _, _, val_str) in enumerate(rows):
        if type_str == "int":
            records += struct.pack("<Ii", TYPE_INT, int(val_str))
        elif type_str == "float":
            records += struct.pack("<If", TYPE_FLOAT, float(val_str))
        elif type_str == "string":
            offset = len(pool)
            pool += val_str.encode("utf-8", errors="surrogateescape") + b"\x00"
            records += struct.pack("<II", TYPE_STRING, offset)
        else:
            raise ValueError(f"{txt_path}: row {idx}: unsupported field type {type_str!r}")

    data = struct.pack("<I", len(rows)) + bytes(records) + bytes(pool)
    os.makedirs(os.path.dirname(os.path.abspath(bin_path)), exist_ok=True)
    with open(bin_path, "wb") as f:
        f.write(data)
    return data


def read_cstr(pool: bytes, offset: int) -> str:
    if offset < 0 or offset >= len(pool):
        raise ValueError(f"String pool offset {offset} out of range (pool len={len(pool)})")
    end = pool.find(b"\x00", offset)
    if end == -1:
        end = len(pool)
    return pool[offset:end].decode("utf-8", errors="replace")


def decompile_fwdatadb(bin_path: str, txt_path: str | None = None, template_path: str | None = None) -> list[str]:
    with open(bin_path, "rb") as f:
        data = f.read()

    if len(data) < 4:
        raise ValueError(f"{bin_path}: file too small ({len(data)} bytes)")

    count = struct.unpack_from("<I", data, 0)[0]
    table_end = 4 + count * 8
    if len(data) < table_end:
        raise ValueError(f"{bin_path}: truncated record table (need {table_end} bytes, got {len(data)})")

    pool = data[table_end:]
    template_rows = parse_txt_lines(template_path) if template_path else None
    if template_rows is not None and len(template_rows) != count:
        raise ValueError(f"Template row count {len(template_rows)} != binary row count {count}")

    out_lines = []
    for i in range(count):
        type_id, raw_val = struct.unpack_from("<II", data, 4 + i * 8)
        if type_id == TYPE_INT:
            val_s = str(struct.unpack("<i", struct.pack("<I", raw_val))[0])
        elif type_id == TYPE_FLOAT:
            fval = struct.unpack("<f", struct.pack("<I", raw_val))[0]
            val_s = f"{fval:g}"
        elif type_id == TYPE_STRING:
            val_s = read_cstr(pool, raw_val)
        else:
            raise ValueError(f"{bin_path}: row {i}: unknown type_id {type_id}")

        type_name = TYPE_NAMES[type_id]
        if template_rows is not None:
            _, k1, k2, k3, _ = template_rows[i]
            out_lines.append(f"{type_name},{k1},{k2},{k3},{val_s}")
        else:
            out_lines.append(f"{type_name},row_{i:04d},bin,entry,{val_s}")

    content = "\n".join(out_lines) + "\n"
    if txt_path:
        os.makedirs(os.path.dirname(os.path.abspath(txt_path)), exist_ok=True)
        with open(txt_path, "wb") as f:
            f.write(content.encode("utf-8"))
    return out_lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile or decompile VT4 fwDataDB .bin/.txt files.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_comp = sub.add_parser("compile", help="Compile .txt into .bin")
    p_comp.add_argument("input_txt")
    p_comp.add_argument("output_bin")

    p_dec = sub.add_parser("decompile", help="Decompile .bin into .txt")
    p_dec.add_argument("input_bin")
    p_dec.add_argument("output_txt", nargs="?")
    p_dec.add_argument("--template", help="Optional .txt template providing key columns")

    p_ver = sub.add_parser("verify", help="Verify .txt compiles byte-for-byte identical to reference .bin")
    p_ver.add_argument("input_txt")
    p_ver.add_argument("reference_bin")

    args = parser.parse_args()

    if args.cmd == "compile":
        data = compile_fwdatadb(args.input_txt, args.output_bin)
        print(f"Compiled {args.input_txt} -> {args.output_bin} ({len(data)} bytes)")
        return 0

    if args.cmd == "decompile":
        lines = decompile_fwdatadb(args.input_bin, args.output_txt, args.template)
        if args.output_txt:
            print(f"Decompiled {args.input_bin} -> {args.output_txt} ({len(lines)} rows)")
        else:
            for line in lines:
                print(line)
        return 0

    if args.cmd == "verify":
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
        try:
            built = compile_fwdatadb(args.input_txt, tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        with open(args.reference_bin, "rb") as f:
            ref = f.read()
        match = built == ref
        print(f"Verify {args.input_txt} vs {args.reference_bin}: built={len(built)} ref={len(ref)} exact_match={match}")
        return 0 if match else 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
