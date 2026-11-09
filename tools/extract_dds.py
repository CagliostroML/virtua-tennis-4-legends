import os, struct
from PIL import Image

with open('tools/extracted_mode/I_MNU_mode_MI.afp', 'rb') as f:
    data = f.read()

offsets = [0x99640, 0xda140, 0x11a640, 0x15a6c0, 0x162740, 0x1788c0, 0x198940]
for idx, off in enumerate(offsets):
    # save dds
    # DDS header is 128 bytes
    h, w = struct.unpack('<II', data[off+12:off+20])
    fourcc = data[off+84:off+88]
    # calculate size
    if fourcc == b'DXT1':
        sz = 128 + max(1, ((w + 3) // 4)) * max(1, ((h + 3) // 4)) * 8
    elif fourcc == b'DXT5':
        sz = 128 + max(1, ((w + 3) // 4)) * max(1, ((h + 3) // 4)) * 16
    else:
        sz = 128 + w * h * 4
    dds_data = data[off:off+sz]
    dds_path = f'tools/extracted_mode/tex_{idx}_{w}x{h}_{fourcc.decode("ascii", errors="ignore")}.dds'
    with open(dds_path, 'wb') as df:
        df.write(dds_data)
    print(f'Saved {dds_path} (size={len(dds_data)})')
