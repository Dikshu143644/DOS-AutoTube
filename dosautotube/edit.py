"""Edit: ffmpeg assembly — Ken Burns stills, animated cards, intro sting, music bed with ducking,
loudness to YouTube's -14 LUFS / -1.5 dBTP, burned-in captions for Shorts."""
from __future__ import annotations

import json
import math
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import brand
from .visuals import font, glow_text, gradient_text

FPS = 30
SR = 48000


def run(cmd: list[str], timeout: int = 1800, log: Path | None = None):
    """Run ffmpeg without capturing pipes (no hangs); output to a log file."""
    lf = open(log, "ab") if log else subprocess.DEVNULL
    p = subprocess.run(["timeout", "-k", "5", str(timeout)] + cmd, stdout=lf, stderr=lf)
    if p.returncode != 0:
        raise RuntimeError(f"command failed ({p.returncode}): {' '.join(cmd[:6])} … see {log}")


def probe_duration(path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, timeout=60).stdout
    return float(out.strip())

# ----------------------------------------------------------------------------- video clips

KB_MODES = ["in", "out", "left", "right", "in2", "up"]


def _cover(img: Image.Image, W: int, H: int) -> Image.Image:
    s = max(W / img.width, H / img.height)
    img = img.resize((math.ceil(img.width * s), math.ceil(img.height * s)), Image.LANCZOS)
    x, y = (img.width - W) // 2, (img.height - H) // 2
    return img.crop((x, y, x + W, y + H))


def kenburns_clip(image: Path, out: Path, dur: float, size=(1920, 1080), mode="in", log=None):
    """Smooth Ken Burns move on a still: render from a 2x canvas so sub-pixel steps don't jitter."""
    W, H = size
    big = Path(out).with_suffix(".src.png")
    _cover(Image.open(image).convert("RGB"), W * 2, H * 2).save(big)
    n = max(2, round(dur * FPS))
    z0, z1, xe, ye = {
        "in": (1.0, 1.12, "(iw-iw/zoom)/2", "(ih-ih/zoom)/2"),
        "in2": (1.04, 1.16, "(iw-iw/zoom)*0.35", "(ih-ih/zoom)/2"),
        "out": (1.14, 1.0, "(iw-iw/zoom)/2", "(ih-ih/zoom)/2"),
        "left": (1.12, 1.12, f"(iw-iw/zoom)*(1-on/{n - 1})", "(ih-ih/zoom)/2"),
        "right": (1.12, 1.12, f"(iw-iw/zoom)*(on/{n - 1})", "(ih-ih/zoom)/2"),
        "up": (1.12, 1.12, "(iw-iw/zoom)/2", f"(ih-ih/zoom)*(1-on/{n - 1})"),
    }[mode]
    z = f"{z0}+({z1}-{z0})*on/{n - 1}"
    vf = (f"zoompan=z='{z}':x='{xe}':y='{ye}':d={n}:s={W}x{H}:fps={FPS},"
          f"format=yuv420p")
    run(["ffmpeg", "-y", "-loop", "1", "-i", str(big), "-vf", vf, "-frames:v", str(n),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-r", str(FPS), str(out)], log=log)
    big.unlink(missing_ok=True)


def card_clip(image: Path, out: Path, dur: float, size=(1920, 1080), log=None):
    """Cards: quick fade-up + gentle push-in so diagrams feel alive."""
    kenburns_clip(image, out, dur, size, mode="in", log=log) if False else None
    W, H = size
    big = Path(out).with_suffix(".src.png")
    _cover(Image.open(image).convert("RGB"), W * 2, H * 2).save(big)
    n = max(2, round(dur * FPS))
    vf = (f"zoompan=z='1.0+0.035*on/{n - 1}':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':d={n}:s={W}x{H}:fps={FPS},"
          f"fade=t=in:st=0:d=0.25,format=yuv420p")
    run(["ffmpeg", "-y", "-loop", "1", "-i", str(big), "-vf", vf, "-frames:v", str(n),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-r", str(FPS), str(out)], log=log)
    big.unlink(missing_ok=True)


def sting_frames(folder: Path, size=(1920, 1080), dur=2.8):
    """Branded intro sting: DOS logo scales up out of a glow, a light sweep crosses it, channel name fades in."""
    W, H = size
    folder.mkdir(parents=True, exist_ok=True)
    n = round(dur * FPS)
    logo = Image.open(brand.LOGO).convert("RGB")
    S = min(W, H) / 1080
    base_sz = int(430 * S)
    name_f = font("ExtraBold", int(64 * S))
    for i in range(n):
        t = i / (n - 1)
        e = 1 - (1 - min(1, t / 0.45)) ** 3  # ease-out
        img = Image.new("RGB", size, brand.BG)
        # glow bloom
        g = Image.new("RGB", size, (0, 0, 0))
        r = int((260 + 220 * e) * S)
        ImageDraw.Draw(g).ellipse((W // 2 - r, H // 2 - r - int(60 * S), W // 2 + r, H // 2 + r - int(60 * S)), fill=(120, 45, 80))
        g = g.filter(ImageFilter.GaussianBlur(int(120 * S)))
        from PIL import ImageChops
        img = ImageChops.add(img, g.point(lambda v: int(v * min(1, t * 2.2))))
        sz = int(base_sz * (0.82 + 0.18 * e))
        lg = logo.resize((sz, sz), Image.LANCZOS)
        m = Image.new("L", (sz, sz), 0)
        ImageDraw.Draw(m).ellipse((0, 0, sz - 1, sz - 1), fill=255)
        m = m.filter(ImageFilter.GaussianBlur(2)).point(lambda v: int(v * min(1, t / 0.25)))
        cx, cy = W // 2, H // 2 - int(60 * S)
        img.paste(lg, (cx - sz // 2, cy - sz // 2), m)
        # light sweep
        sweep_t = (t - 0.35) / 0.4
        if 0 <= sweep_t <= 1:
            sw = Image.new("L", size, 0)
            x = int(cx - sz + 2 * sz * sweep_t)
            ImageDraw.Draw(sw).polygon([(x - 40, cy - sz), (x + 40, cy - sz), (x - 60 + 40, cy + sz), (x - 140, cy + sz)], fill=150)
            sw = sw.filter(ImageFilter.GaussianBlur(18))
            mm = Image.new("L", size, 0)
            mm.paste(m, (cx - sz // 2, cy - sz // 2))
            sw = ImageChops.multiply(sw, mm)
            img = Image.composite(Image.new("RGB", size, (255, 236, 244)), img, sw)
        a = max(0.0, min(1.0, (t - 0.45) / 0.3))
        if a > 0:
            layer = img.copy()
            gradient_text(layer, (W // 2, cy + int(sz * 0.5) + int(70 * S)), brand.CHANNEL_NAME, name_f, anchor="mt")
            img = Image.blend(img, layer, a)
        if t > 0.86:  # fade out
            img = Image.blend(img, Image.new("RGB", size, (0, 0, 0)), (t - 0.86) / 0.14)
        img.save(folder / f"f{i:04d}.png")
    return n


def sting_clip(out: Path, size=(1920, 1080), dur=2.8, log=None):
    folder = Path(out).with_suffix("")
    sting_frames(folder, size, dur)
    run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", str(folder / "f%04d.png"), "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "18", "-pix_fmt", "yuv420p", str(out)], log=log)
    for f in folder.glob("*.png"):
        f.unlink()
    folder.rmdir()


def concat(clips: list[Path], out: Path, log=None):
    lst = Path(out).with_suffix(".txt")
    lst.write_text("".join(f"file '{c}'\n" for c in clips))
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)], log=log)
    lst.unlink()

# ----------------------------------------------------------------------------- audio


def decode(path, sr=SR) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"],
                         capture_output=True, timeout=600).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def write_wav(path, x: np.ndarray, sr=SR):
    x = np.clip(x, -1, 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def place(track: np.ndarray, clip: np.ndarray, at: float, gain=1.0, sr=SR) -> np.ndarray:
    i = int(at * sr)
    need = i + len(clip)
    if need > len(track):
        track = np.concatenate([track, np.zeros(need - len(track), np.float32)])
    track[i:need] += clip * gain
    return track


def _moving_avg(x: np.ndarray, win: int) -> np.ndarray:
    """Centered moving average in O(n) (cumulative sum), same length as x."""
    c = np.concatenate([[0.0], np.cumsum(x, dtype=np.float64)])
    half = win // 2
    idx = np.arange(len(x))
    lo = np.clip(idx - half, 0, len(x))
    hi = np.clip(idx + half, 0, len(x))
    return ((c[hi] - c[lo]) / np.maximum(1, hi - lo)).astype(np.float32)


def music_bed(music: Path, length: float, voice: np.ndarray, sr=SR, bed_db=-23.0, duck_db=-9.0) -> np.ndarray:
    """Loop the music to length, sit it low under the voice, duck further while words are spoken, fade the ends."""
    m = decode(music, sr)
    n = int(length * sr)
    reps = int(np.ceil(n / len(m))) + 1
    xf = int(1.5 * sr)
    out = m.copy()
    for _ in range(reps):  # crossfaded loop
        ramp = np.linspace(0, 1, xf, dtype=np.float32)
        out = np.concatenate([out[:-xf], out[-xf:] * (1 - ramp) + m[:xf] * ramp, m[xf:]])
        if len(out) >= n:
            break
    out = out[:n]
    rms = np.sqrt(np.mean(out ** 2) + 1e-9)
    out = out / rms * (10 ** (bed_db / 20)) * 0.1  # bed level relative to -20 dBFS-ish voice
    # ducking envelope from voice energy
    v = np.zeros(n, np.float32)
    v[:min(n, len(voice))] = np.abs(voice[:n])
    env = _moving_avg(v, int(0.25 * sr))
    speaking = (env > 0.01).astype(np.float32)
    smooth = _moving_avg(speaking, int(0.4 * sr))
    gain = 10 ** ((duck_db * smooth) / 20)
    out = out * gain
    f = int(2.0 * sr)
    out[:f] *= np.linspace(0, 1, f)
    out[-f:] *= np.linspace(1, 0, f)
    return out


def loudnorm(inp: Path, out: Path, I=-14.0, TP=-1.5, LRA=11, log=None):
    """Two-pass EBU R128 loudness normalisation (YouTube target -14 LUFS, true peak <= -1.5 dBTP)."""
    p = subprocess.run(["timeout", "-k", "5", "600", "ffmpeg", "-hide_banner", "-i", str(inp), "-af",
                        f"aformat=channel_layouts=mono,loudnorm=I={I}:TP={TP}:LRA={LRA}:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True)
    txt = p.stderr
    js = json.loads(txt[txt.rindex("{"):txt.rindex("}") + 1])
    af = (f"aformat=channel_layouts=mono,loudnorm=I={I}:TP={TP}:LRA={LRA}:measured_I={js['input_i']}:measured_TP={js['input_tp']}:"
          f"measured_LRA={js['input_lra']}:measured_thresh={js['input_thresh']}:offset={js['target_offset']}:linear=true")
    tmp = Path(out).with_suffix(".pass2.wav")
    run(["ffmpeg", "-y", "-i", str(inp), "-af", af, "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le", str(tmp)], log=log)
    # final trim: hit the target exactly when true-peak headroom allows
    m = measure(tmp)
    g = min(I - m["I"], TP - 0.3 - m["TP"])
    run(["ffmpeg", "-y", "-i", str(tmp), "-af", f"volume={g:.2f}dB", "-c:a", "pcm_s16le", str(out)], log=log)
    tmp.unlink()


def measure(path) -> dict:
    """Integrated loudness (LUFS) and true peak (dBTP) via ffmpeg ebur128."""
    p = subprocess.run(["timeout", "-k", "5", "600", "ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af",
                        "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True)
    s = p.stderr[p.stderr.rindex("Summary:"):]
    import re
    return {"I": float(re.search(r"I:\s+(-?[\d.]+) LUFS", s).group(1)),
            "TP": float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", s).group(1))}


def mux(video: Path, audio: Path, out: Path, crf=20, extra_vf: str | None = None, max_rate: str | None = None, log=None):
    cmd = ["ffmpeg", "-y", "-i", str(video), "-i", str(audio)]
    if extra_vf:
        cmd += ["-vf", extra_vf]
    cmd += ["-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p",
            "-profile:v", "high", "-movflags", "+faststart", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest"]
    if max_rate:
        cmd += ["-maxrate", max_rate, "-bufsize", max_rate]
    run(cmd + [str(out)], log=log)

# ----------------------------------------------------------------------------- captions (Shorts)


def words_from_alignment(alignment: dict, offset: float = 0.0) -> list[tuple[str, float, float]]:
    chars, st, en = alignment["characters"], alignment["character_start_times_seconds"], alignment["character_end_times_seconds"]
    words, cur, s0 = [], "", None
    for c, a, b in zip(chars, st, en):
        if c.isspace():
            if cur:
                words.append((cur, s0 + offset, last + offset))
            cur, s0 = "", None
            continue
        if s0 is None:
            s0 = a
        cur += c
        last = b
    if cur:
        words.append((cur, s0 + offset, last + offset))
    return words


def _ts(t):
    h, rem = divmod(max(0, t), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def ass_captions(words, out: Path, size=(1080, 1920), per=3, font_name="Montserrat ExtraBold", fs=86, y_margin=560):
    """Bold, centered 2-3 word captions with the current word highlighted in brand pink."""
    W, H = size
    hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font_name},{fs},&H00F7F2F7,&H00F7F2F7,&H00140A0E,&H96000000,0,0,0,0,100,100,0,0,1,6,3,2,60,60,{y_margin},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    pink = "&H00A86FFF&"  # BGR of #FF6FA8
    lines = []
    groups, cur = [], []
    for w in words:  # max `per` words per caption, never across a sentence/clause break
        cur.append(w)
        if len(cur) == per or w[0][-1] in ".,:;?!":
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    for gi, g in enumerate(groups):
        g_end = groups[gi + 1][0][1] if gi + 1 < len(groups) else g[-1][2] + 0.4
        for wi, (w, s, e) in enumerate(g):
            end = g[wi + 1][1] if wi + 1 < len(g) else g_end
            txt = " ".join((f"{{\\c{pink}}}{x.upper()}{{\\c&H00F7F2F7&}}" if j == wi else x.upper()) for j, (x, _, _) in enumerate(g))
            lines.append(f"Dialogue: 0,{_ts(s)},{_ts(end)},Cap,,0,0,0,,{txt}")
    Path(out).write_text(hdr + "\n".join(lines) + "\n")
    return out
