#!/usr/bin/env python3
"""
Generate Fase 3 extra assets for Virtua Tennis 4: Legends & Next-Gen Edition:
  1. game/archive/ee3/*.wav (6 mono 16-bit 44100Hz PCM SFX built from real Wikimedia Commons foley)
  2. game/archive/ee3/umpire_meme.dds (512x512 DXT5 with 10 mipmaps = 349,680 bytes = 0x555f0)
  3. scratch/umpire_meme_preview.png (visual audit preview)
"""
import array
import math
import os
import struct
import subprocess
import sys
import urllib.request
import wave
from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

from vt4_archive import BIN0, BIN1, load_directory, read_entry, lzss_decompress
from dxt_codec import encode_dxt5_payload, make_dds_header

OUT_DIR = os.path.join(REPO_ROOT, "game", "archive", "ee3")
RAW_SFX_DIR = os.path.join(REPO_ROOT, "assets", "sfx_real_raw")
SCRATCH_DIR = os.path.join(REPO_ROOT, "scratch")
SR = 44100

FOLEY_SOURCES = {
    "hollow_crunch.wav": "https://upload.wikimedia.org/wikipedia/commons/8/8e/Hollow_crunch_%28Gravity_Sound%29.wav",
    "crunch.wav": "https://upload.wikimedia.org/wikipedia/commons/a/a6/Crunch_%28Gravity_Sound%29.wav",
    "deep_hit.wav": "https://upload.wikimedia.org/wikipedia/commons/2/2e/Deep_hit_%28Gravity_Sound%29.wav",
    "metal_hit.mp3": "https://upload.wikimedia.org/wikipedia/commons/5/52/Metal_Hit_%28Gravity_Sound%29.mp3",
    "metal_pole_hit_3.wav": "https://upload.wikimedia.org/wikipedia/commons/e/ee/Metal_pole_hit_3_%28Gravity_Sound%29.wav",
    "wood_pole.ogg": "https://upload.wikimedia.org/wikipedia/commons/d/d2/Hitting_wooden_pole.ogg",
    "hit_1.wav": "https://upload.wikimedia.org/wikipedia/commons/3/31/Hit_1_%28Gravity_Sound%29.wav",
    "referee_whistle.wav": "https://upload.wikimedia.org/wikipedia/commons/7/7d/218318_splicesound_referee-whistle-blow-gymnasium.wav",
    "applause.ogg": "https://upload.wikimedia.org/wikipedia/commons/0/09/Applause_ii.ogg",
    "buzzer.wav": "https://upload.wikimedia.org/wikipedia/commons/5/55/Buzzer.wav",
}


def download_foley(filename: str, url: str) -> str:
    os.makedirs(RAW_SFX_DIR, exist_ok=True)
    dst = os.path.join(RAW_SFX_DIR, filename)
    if os.path.isfile(dst) and os.path.getsize(dst) > 512:
        return dst
    req = urllib.request.Request(url, headers={"User-Agent": "VT4ModAudioTool/1.0 (https://example.org)"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = resp.read()
    assert len(data) > 512, f"Downloaded empty/tiny audio for {filename}: {len(data)} bytes"
    with open(dst, "wb") as f:
        f.write(data)
    return dst


def decode_pcm_mono44k(path: str) -> list[float]:
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0 or not proc.stdout:
        raise RuntimeError(f"ffmpeg failed decoding {path}: {proc.stderr.decode('utf-8', 'ignore')}")
    arr = array.array("h")
    arr.frombytes(proc.stdout)
    return [s / 32768.0 for s in arr]


def extract_transient_slice(samples: list[float], dur_sec: float, pre_ms: float = 4.0, fade_out_ms: float = 35.0) -> list[float]:
    """Locate the strongest transient/impact window and normalize cleanly with zero lead silence."""
    if not samples:
        return [0.0] * int(SR * dur_sec)
    n_out = max(1, int(round(SR * dur_sec)))
    # Smooth absolute energy over 15ms sliding windows to pick strongest event (handles multi-hit clips)
    win = max(1, int(SR * 0.015))
    best_idx = 0
    best_e = -1.0
    for i in range(0, len(samples), max(1, win // 3)):
        chunk = samples[i : i + win]
        e = max((abs(v) for v in chunk), default=0.0)
        if e > best_e:
            best_e = e
            best_idx = i

    # Walk backward inside 120ms before best_idx to find where the transient attack begins (>= 8% of peak)
    search_lo = max(0, best_idx - int(SR * 0.12))
    thresh = max(1e-4, best_e * 0.08)
    onset = best_idx
    for j in range(search_lo, best_idx + 1):
        if abs(samples[j]) >= thresh:
            onset = j
            break

    start = max(0, onset - int(SR * (pre_ms / 1000.0)))
    sliced = list(samples[start : start + n_out])
    if len(sliced) < n_out:
        sliced.extend([0.0] * (n_out - len(sliced)))

    # Short fade-in (2ms) and smooth fade-out to avoid DC clicks
    fi = min(len(sliced), max(1, int(SR * 0.002)))
    for k in range(fi):
        sliced[k] *= k / fi
    fo = min(len(sliced), max(1, int(SR * (fade_out_ms / 1000.0))))
    for k in range(fo):
        sliced[len(sliced) - 1 - k] *= k / fo

    pk = max((abs(v) for v in sliced), default=1.0)
    if pk > 1e-6:
        sliced = [v / pk for v in sliced]
    return sliced


def mix_layers(layers: list[tuple[list[float], float]], dur_sec: float) -> list[float]:
    n_out = max(1, int(round(SR * dur_sec)))
    out = [0.0] * n_out
    for buf, gain in layers:
        for i in range(min(n_out, len(buf))):
            out[i] += buf[i] * gain
    fo = min(n_out, int(SR * 0.025))
    for k in range(fo):
        out[n_out - 1 - k] *= k / fo
    return out


def write_wav_mono16(path: str, samples: list[float]) -> dict:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    peak = max((abs(s) for s in samples), default=1.0)
    target_peak = 32767.0 * (10.0 ** (-1.0 / 20.0))  # -1.0 dBFS (~29204)
    scale = target_peak / peak if peak > 1e-6 else 1.0
    pcm = bytearray()
    sq_sum = 0.0
    for s in samples:
        v = max(-32767, min(32767, int(round(s * scale))))
        pcm.extend(struct.pack("<h", v))
        norm = v / 32768.0
        sq_sum += norm * norm
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(bytes(pcm))
    rms = math.sqrt(sq_sum / max(1, len(samples)))
    return {"dur": len(samples) / SR, "rms": rms, "size": os.path.getsize(path)}


def build_real_sfx_suite() -> None:
    raw = {}
    for fn, url in FOLEY_SOURCES.items():
        p = download_foley(fn, url)
        raw[fn] = decode_pcm_mono44k(p)
        print(f"  [FOLEY] {fn:22s} -> {len(raw[fn]) / SR:.2f}s @ {SR}Hz")

    # 1. Giant Baguette: real hollow crunch + crispy crust crunch + deep soft loaf thud
    baguette = mix_layers(
        [
            (extract_transient_slice(raw["hollow_crunch.wav"], 0.28, pre_ms=3.0, fade_out_ms=40.0), 0.72),
            (extract_transient_slice(raw["crunch.wav"], 0.28, pre_ms=2.0, fade_out_ms=40.0), 0.52),
            (extract_transient_slice(raw["deep_hit.wav"], 0.28, pre_ms=3.0, fade_out_ms=50.0), 0.48),
        ],
        0.28,
    )

    # 2. Cast-iron Frying Pan: crisp metal hit transient + metallic pole resonance ring
    pan = mix_layers(
        [
            (extract_transient_slice(raw["metal_hit.mp3"], 0.35, pre_ms=2.0, fade_out_ms=55.0), 0.85),
            (extract_transient_slice(raw["metal_pole_hit_3.wav"], 0.35, pre_ms=2.0, fade_out_ms=70.0), 0.55),
        ],
        0.35,
    )

    # 3. Classic 70s Wood Racket: sharp wooden pole strike + tight ball thwack
    wood70 = mix_layers(
        [
            (extract_transient_slice(raw["wood_pole.ogg"], 0.22, pre_ms=3.0, fade_out_ms=35.0), 0.78),
            (extract_transient_slice(raw["hit_1.wav"], 0.22, pre_ms=2.0, fade_out_ms=35.0), 0.45),
        ],
        0.22,
    )

    # 4. McEnroe QTE Protest / Win / Lose: real referee whistle, applause, buzzer
    protest = extract_transient_slice(raw["referee_whistle.wav"], 0.65, pre_ms=4.0, fade_out_ms=50.0)
    win = extract_transient_slice(raw["applause.ogg"], 1.20, pre_ms=10.0, fade_out_ms=180.0)
    lose = extract_transient_slice(raw["buzzer.wav"], 0.60, pre_ms=4.0, fade_out_ms=60.0)

    outputs = [
        ("hit_wood70.wav", wood70),
        ("hit_pan.wav", pan),
        ("hit_baguette.wav", baguette),
        ("ee1_protest.wav", protest),
        ("ee1_win.wav", win),
        ("ee1_lose.wav", lose),
    ]
    for fn, buf in outputs:
        out_wav = os.path.join(OUT_DIR, fn)
        info = write_wav_mono16(out_wav, buf)
        assert info["rms"] > 0.02, f"Suspiciously silent output {fn}: rms={info['rms']:.4f}"
        print(f"Wrote {out_wav} ({info['size']} B, {info['dur']:.2f}s, 44100Hz 16-bit mono, rms={info['rms']:.3f})")



def extract_umpire_base_image() -> Image.Image:
    entries = load_directory()
    cache = {}
    with open(BIN0, "rb") as f0, open(BIN1, "rb") as f1:
        e = next(x for x in entries if x["name"].lower() == "high/subcharacter/u_up_spa2_tr.sdo")
        raw = lzss_decompress(read_entry(entries, e, f0, f1, cache))
    pos = raw.find(b"DDS ")
    assert pos > 0, "Could not locate DDS inside U_UP_Spa2_TR.sdo"
    sz = struct.unpack(">I", raw[pos - 4 : pos])[0]
    tmp_dds = os.path.join(SCRATCH_DIR, "_umpire_base_tmp.dds")
    os.makedirs(SCRATCH_DIR, exist_ok=True)
    with open(tmp_dds, "wb") as f:
        f.write(raw[pos : pos + sz])
    im = Image.open(tmp_dds).convert("RGBA")
    os.remove(tmp_dds)
    return im


def _apply_referee_stripes(im: Image.Image, box: tuple[int, int, int, int], stripe_w: int = 10) -> None:
    x0, y0, x1, y1 = box
    px = im.load()
    for y in range(y0, y1):
        for x in range(x0, x1):
            r, g, b, a = px[x, y]
            if a < 10:
                continue
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            # Keep fabric fold shading relative to mid-dark jacket
            shade = max(0.55, min(1.35, (lum + 22.0) / 82.0))
            is_white = ((x // stripe_w) % 2) == 0
            if is_white:
                nr = int(min(255, 228 * shade))
                ng = int(min(255, 228 * shade))
                nb = int(min(255, 232 * shade))
            else:
                nr = int(min(255, 22 * shade))
                ng = int(min(255, 22 * shade))
                nb = int(min(255, 26 * shade))
            px[x, y] = (nr, ng, nb, a)


def build_umpire_meme_texture(base: Image.Image) -> Image.Image:
    im = base.copy().convert("RGBA")
    assert im.size == (512, 512)

    # 1. Referee B&W stripes on front/back jacket + sleeves, preserving tie/shirt center (x=62..98, y=0..115)
    _apply_referee_stripes(im, (0, 0, 62, 280), stripe_w=10)
    _apply_referee_stripes(im, (98, 0, 320, 280), stripe_w=10)
    _apply_referee_stripes(im, (62, 125, 98, 280), stripe_w=10)
    _apply_referee_stripes(im, (320, 185, 512, 365), stripe_w=10)

    draw = ImageDraw.Draw(im)

    # 2. Front V-neck bright red tie + VIP gold lapels & cuff buttons
    draw.polygon([(74, 0), (86, 0), (88, 92), (80, 114), (72, 92)], fill=(215, 20, 24, 255))
    draw.line([(72, 16), (88, 28)], fill=(255, 220, 60, 255), width=2)
    draw.line([(72, 46), (88, 58)], fill=(255, 220, 60, 255), width=2)
    draw.line([(73, 76), (87, 88)], fill=(255, 220, 60, 255), width=2)
    # Gold lapel rims + buttons
    draw.line([(56, 2), (76, 116), (98, 2)], fill=(242, 196, 38, 255), width=4)
    draw.ellipse([78, 152, 86, 160], fill=(250, 205, 45, 255), outline=(90, 60, 0, 255))
    draw.ellipse([78, 198, 86, 206], fill=(250, 205, 45, 255), outline=(90, 60, 0, 255))

    # 3. Cash bills ($$$) stuffed inside front breast pocket (x=18..50, y=82..118)
    draw.rectangle([20, 88, 48, 108], fill=(64, 170, 74, 255), outline=(22, 90, 28, 255))
    draw.polygon([(26, 82), (44, 78), (47, 102), (29, 105)], fill=(86, 198, 96, 255), outline=(24, 96, 30, 255))
    draw.rectangle([18, 103, 50, 112], fill=(240, 190, 40, 255))
    try:
        font_sm = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 14)
        font_lg = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 22)
    except Exception:
        font_sm = ImageFont.load_default()
        font_lg = ImageFont.load_default()
    draw.text((23, 84), "$$$", fill=(20, 68, 22, 255), font=font_sm)

    # 4. Back yellow warning sign: "CIEGO" (centered on x=160..320, y=58..118)
    draw.rectangle([192, 62, 288, 112], fill=(252, 212, 20, 255), outline=(12, 12, 12, 255), width=3)
    draw.text((203, 74), "CIEGO", fill=(15, 15, 15, 255), font=font_lg)

    # 5. Face (x=320..512, y=0..180): Pixel "DEAL WITH IT" sunglasses + red clown nose + smirk
    # Glasses bridge + two pixelated frames centered around x=416, y=84
    draw.rectangle([376, 78, 456, 86], fill=(10, 10, 12, 255))
    draw.rectangle([380, 86, 410, 96], fill=(10, 10, 12, 255))
    draw.rectangle([422, 86, 452, 96], fill=(10, 10, 12, 255))
    draw.rectangle([386, 96, 406, 101], fill=(10, 10, 12, 255))
    draw.rectangle([426, 96, 446, 101], fill=(10, 10, 12, 255))
    # Pixel reflections on lenses
    for rx, ry in [(384, 81), (388, 85), (392, 89), (426, 81), (430, 85), (434, 89)]:
        draw.rectangle([rx, ry, rx + 3, ry + 3], fill=(245, 245, 250, 255))
    # Big red clown nose
    draw.ellipse([406, 98, 426, 118], fill=(232, 20, 24, 255), outline=(120, 6, 8, 255), width=2)
    draw.ellipse([410, 101, 416, 107], fill=(255, 185, 185, 255))
    # Mischievous smirk
    draw.arc([402, 116, 430, 134], start=10, end=170, fill=(90, 18, 22, 255), width=3)

    return im


def encode_dxt5_full_mips(im: Image.Image) -> bytes:
    """Encode 512x512 RGBA into DXT5 DDS with all 10 mip levels (0x555f0 = 349,680 bytes)."""
    w, h = im.size
    mips = 10
    hdr = make_dds_header(w, h, b"DXT5", mips=mips)
    payload = bytearray()
    cur = im.convert("RGBA")
    cw, ch = w, h
    for lvl in range(mips):
        payload.extend(encode_dxt5_payload(cur))
        cw = max(1, cw // 2)
        ch = max(1, ch // 2)
        if lvl + 1 < mips:
            cur = cur.resize((cw, ch), Image.Resampling.LANCZOS)
    dds = hdr + bytes(payload)
    assert len(dds) == 0x555F0, f"Unexpected Umpire DDS size: 0x{len(dds):x} != 0x555f0"
    return dds


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(SCRATCH_DIR, exist_ok=True)

    build_real_sfx_suite()

    base_im = extract_umpire_base_image()
    meme_im = build_umpire_meme_texture(base_im)
    prev_path = os.path.join(SCRATCH_DIR, "umpire_meme_preview.png")
    meme_im.save(prev_path)
    print(f"Wrote {prev_path}")

    dds_bytes = encode_dxt5_full_mips(meme_im)
    dds_path = os.path.join(OUT_DIR, "umpire_meme.dds")
    with open(dds_path, "wb") as f:
        f.write(dds_bytes)
    print(f"Wrote {dds_path} ({len(dds_bytes)} B = 0x{len(dds_bytes):x})")

    tmp_dbg = os.path.join(OUT_DIR, "_umpire_base_debug.dds")
    if os.path.exists(tmp_dbg):
        os.remove(tmp_dbg)


if __name__ == "__main__":
    main()
