#!/usr/bin/env python3
"""
Import & normalize custom per-player voice packs from:
  assets/voices_workspace/<player_dir>/<event_or_rivalry>/*.{wav,mp3,ogg,flac,m4a}
into:
  game/archive/voices/<player_dir>/<event_or_rivalry>/*.wav

Features:
  - Pure Python stdlib (wave/struct/math) for WAV input (8/16/24/32-bit PCM, mono/stereo,
    any sample rate -> resampled linearly to 44100 Hz 16-bit mono PCM).
  - Optional automatic ffmpeg conversion for .mp3 / .ogg / .flac / .m4a if ffmpeg is on PATH.
  - Trims leading/trailing digital silence (< -45 dBFS) for instant playback latency.
  - Normalizes RMS loudness to -14.0 dBFS (configurable) with -0.5 dBFS peak limiter.
  - Enforces 2 MB max output clip size (matching VP_MAX_WAV_BYTES in src/xlive/voice_packs.h).
"""
import argparse
import math
import os
import re
import shutil
import struct
import subprocess
import tempfile
import wave

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS_ROOT = os.path.join(REPO_ROOT, "assets", "voices_workspace")
GAME_VOICES_ROOT = os.path.join(REPO_ROOT, "game", "archive", "voices")

VALID_EVENTS = {"grunt", "serve", "point_win", "point_lose", "protest", "match_win"}
AUDIO_EXTS = {".wav", ".mp3", ".ogg", ".flac", ".m4a"}
TARGET_RATE = 44100
MAX_OUT_BYTES = 2 * 1024 * 1024

ROSTER_CODES = [
    "FED","NAD","DJV","MRY","DEL","ROD","MON","GON","KOH","SEP",
    "HAS","BEC","RAF","COU","EDB","KIN","DUK","SHA","WIL","KUZ",
    "IVA","CHA","WOZ","ROB","VTM","VTF","ALC","SIN","SAM","AGA",
    "BOR","MCE","GRA","SER","SWI","SAB","KUE","NAV","WAW","MED",
    "ZVE","TSI","THI","KYR","HEW","SAF","TSO","FRR","MOY","FER",
    "NAL","LEN","CON","VIL","IVN","EVE","SEL","HEN","MUG","SHE",
    "RUB","RUU","FRI","GAU","RYB","BAD","HAL","COR","GAS","NIS",
    "SOD","BER","CHN","RIO","MUS","BRU","CRT","WLD","LAV","ASV",
    "CMT","CLI","AND","BJK",
]
VALID_PLAYER_DIRS = {f"{i:02d}_{code}" for i, code in enumerate(ROSTER_CODES)}
VALID_CODES = set(ROSTER_CODES)


def is_valid_subslot(name: str) -> bool:
    if name in VALID_EVENTS:
        return True
    if name.startswith("vs_"):
        rest = name[3:]
        if rest in VALID_PLAYER_DIRS or rest in VALID_CODES:
            return True
    return False


def read_wav_mono_float(path: str) -> tuple[list[float], int]:
    """Read PCM WAV (8/16/24/32-bit, mono/stereo) into normalized float samples [-1, 1]."""
    with wave.open(path, "rb") as wf:
        nch = wf.getnchannels()
        sw = wf.getsampwidth()
        sr = wf.getframerate()
        nframes = wf.getnframes()
        raw = wf.readframes(nframes)

    if nframes == 0:
        return [], sr

    samples = []
    if sw == 1:
        vals = [(b - 128) / 128.0 for b in raw]
    elif sw == 2:
        vals = [v / 32768.0 for v in struct.unpack(f"<{nframes * nch}h", raw)]
    elif sw == 3:
        vals = []
        for i in range(0, len(raw), 3):
            b0, b1, b2 = raw[i], raw[i + 1], raw[i + 2]
            v = b0 | (b1 << 8) | (b2 << 16)
            if v & 0x800000:
                v -= 0x1000000
            vals.append(v / 8388608.0)
    elif sw == 4:
        vals = [v / 2147483648.0 for v in struct.unpack(f"<{nframes * nch}i", raw)]
    else:
        raise ValueError(f"Unsupported WAV sample width: {sw}")

    if nch == 1:
        samples = vals
    else:
        inv = 1.0 / nch
        samples = [sum(vals[i : i + nch]) * inv for i in range(0, len(vals), nch)]
    return samples, sr


def resample_linear(samples: list[float], src_rate: int, dst_rate: int) -> list[float]:
    if src_rate == dst_rate or len(samples) < 2:
        return samples
    ratio = src_rate / float(dst_rate)
    out_len = max(1, int(round(len(samples) / ratio)))
    out = [0.0] * out_len
    n_minus_1 = len(samples) - 1
    for i in range(out_len):
        pos = i * ratio
        idx = int(pos)
        if idx >= n_minus_1:
            out[i] = samples[n_minus_1]
        else:
            frac = pos - idx
            out[i] = samples[idx] * (1.0 - frac) + samples[idx + 1] * frac
    return out


def trim_silence(samples: list[float], thresh_db: float = -45.0, pad_samples: int = 882) -> list[float]:
    if not samples:
        return samples
    thresh = 10.0 ** (thresh_db / 20.0)
    start = 0
    end = len(samples) - 1
    while start < len(samples) and abs(samples[start]) < thresh:
        start += 1
    if start >= len(samples):
        return samples
    while end > start and abs(samples[end]) < thresh:
        end -= 1
    start = max(0, start - pad_samples)
    end = min(len(samples) - 1, end + pad_samples)
    return samples[start : end + 1]


def normalize_rms(samples: list[float], target_dbfs: float = -14.0, peak_limit_dbfs: float = -0.5) -> list[float]:
    if not samples:
        return samples
    mean_sq = sum(s * s for s in samples) / len(samples)
    rms = math.sqrt(mean_sq)
    if rms < 1e-6:
        return samples
    target_rms = 10.0 ** (target_dbfs / 20.0)
    gain = target_rms / rms
    peak = max(abs(s) for s in samples)
    peak_limit = 10.0 ** (peak_limit_dbfs / 20.0)
    if peak * gain > peak_limit:
        gain = peak_limit / peak
    return [max(-1.0, min(1.0, s * gain)) for s in samples]


def write_wav_16bit_mono(path: str, samples: list[float], rate: int = TARGET_RATE) -> int:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    ints = [max(-32768, min(32767, int(round(s * 32767.0)))) for s in samples]
    pcm = struct.pack(f"<{len(ints)}h", *ints)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(pcm)
    return os.path.getsize(path)


def decode_to_wav(src_path: str, tmp_dir: str, ffmpeg_bin: str | None) -> str:
    ext = os.path.splitext(src_path)[1].lower()
    if ext == ".wav":
        return src_path
    if not ffmpeg_bin:
        raise RuntimeError(f"ffmpeg not found on PATH; cannot convert non-WAV file: {src_path}")
    out_wav = os.path.join(tmp_dir, "decoded.wav")
    cmd = [ffmpeg_bin, "-y", "-loglevel", "error", "-i", src_path, "-ac", "1", "-ar", str(TARGET_RATE), "-sample_fmt", "s16", out_wav]
    subprocess.run(cmd, check=True)
    return out_wav


def main() -> None:
    ap = argparse.ArgumentParser(description="Import & normalize custom VT4 voice packs.")
    ap.add_argument("--player", default="", help="Only import a specific player folder (e.g. 39_MED)")
    ap.add_argument("--dry-run", action="store_true", help="Validate & preview without writing files")
    ap.add_argument("--target-dbfs", type=float, default=-14.0, help="Target RMS loudness in dBFS (default -14.0)")
    args = ap.parse_args()

    if not os.path.isdir(WS_ROOT):
        print(f"Workspace not found: {WS_ROOT}. Run tools/prepare_voices_workspace.py first.")
        return

    ffmpeg_bin = shutil.which("ffmpeg")
    print(f"Voice Pack Importer | workspace={WS_ROOT}")
    print(f"  Output root : {GAME_VOICES_ROOT}")
    print(f"  Target spec : {TARGET_RATE} Hz, 16-bit mono PCM, RMS {args.target_dbfs:.1f} dBFS")
    print(f"  ffmpeg      : {ffmpeg_bin if ffmpeg_bin else 'not found (WAV-only pure-Python mode)'}")
    if args.dry_run:
        print("  Mode        : DRY-RUN (no files will be written)")

    found_clips = 0
    imported_clips = 0
    skipped_dirs = []

    with tempfile.TemporaryDirectory() as tmp_dir:
        for pdir in sorted(os.listdir(WS_ROOT)):
            pfull = os.path.join(WS_ROOT, pdir)
            if not os.path.isdir(pfull):
                continue
            if args.player and pdir.lower() != args.player.lower():
                continue
            if pdir not in VALID_PLAYER_DIRS:
                skipped_dirs.append(pdir)
                continue

            for sub in sorted(os.listdir(pfull)):
                sfull = os.path.join(pfull, sub)
                if not os.path.isdir(sfull):
                    continue
                if not is_valid_subslot(sub):
                    print(f"  [WARN] Ignoring unknown subfolder: {pdir}/{sub}")
                    continue

                for fname in sorted(os.listdir(sfull)):
                    ext = os.path.splitext(fname)[1].lower()
                    if ext not in AUDIO_EXTS:
                        continue
                    src = os.path.join(sfull, fname)
                    stem = re.sub(r"[^A-Za-z0-9_\-]+", "_", os.path.splitext(fname)[0]).strip("_") or "clip"
                    dst = os.path.join(GAME_VOICES_ROOT, pdir, sub, f"{stem}.wav")
                    found_clips += 1
                    if args.dry_run:
                        print(f"  [DRY-RUN] {pdir}/{sub}/{fname} -> {os.path.relpath(dst, REPO_ROOT)}")
                        continue

                    wav_src = decode_to_wav(src, tmp_dir, ffmpeg_bin)
                    samples, sr = read_wav_mono_float(wav_src)
                    samples = resample_linear(samples, sr, TARGET_RATE)
                    samples = trim_silence(samples)
                    samples = normalize_rms(samples, target_dbfs=args.target_dbfs)
                    out_bytes = write_wav_16bit_mono(dst, samples, TARGET_RATE)
                    if out_bytes > MAX_OUT_BYTES:
                        os.remove(dst)
                        print(f"  [SKIP >2MB] {pdir}/{sub}/{fname} ({out_bytes} bytes exceeds 2 MB cap)")
                        continue
                    dur = len(samples) / float(TARGET_RATE)
                    print(f"  [OK] {pdir}/{sub}/{stem}.wav ({dur:.2f}s, {out_bytes // 1024} KB)")
                    imported_clips += 1

    if skipped_dirs:
        print(f"  [WARN] Skipped unrecognized player dirs: {', '.join(skipped_dirs)}")
    print(f"\nDone: {found_clips} clip(s) found, {imported_clips} imported.")


if __name__ == "__main__":
    main()
