"""Render an episode: narration sections + beats -> timed visuals -> final MP4 (YouTube-ready)."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from . import edit as E
from .visuals import card

FPS = E.FPS


def beat_starts(alignment: dict, text: str, beats: list[str]) -> list[float]:
    """Find when each beat's first word is spoken, from the TTS character alignment."""
    starts = alignment["character_start_times_seconds"]
    off, out = 0, []
    for b in beats:
        idx = text.index(b[: min(20, len(b))], off)
        out.append(starts[idx] if out else 0.0)
        off = idx + len(b)
    return out


def build_timeline(sections, sting_after: int | None = 0, sting_dur=2.8, gap=0.7, end_hold=0.0, lead_in=0.15):
    """sections: [{"audio": path, "alignment": dict, "text": str, "beats": [(text, visual_spec), ...]}].
    Returns (segments, audio_events, total). Segment: {"start","end","visual"}; event: (path, at)."""
    segs, events, t = [], [], lead_in
    for i, s in enumerate(sections):
        dur = E.probe_duration(s["audio"])
        bts = beat_starts(s["alignment"], s["text"], [b[0] for b in s["beats"]])
        events.append((s["audio"], t))
        sec_end = t + dur + (gap if i < len(sections) - 1 else 0)
        for j, (txt, vis) in enumerate(s["beats"]):
            st = (t + bts[j]) if segs else 0.0
            en = t + bts[j + 1] if j + 1 < len(s["beats"]) else sec_end
            segs.append({"start": st, "end": en, "visual": vis, "text": txt})
        t = sec_end
        if sting_after is not None and i == sting_after:
            segs.append({"start": t, "end": t + sting_dur, "visual": {"sting": True}})
            events.append(("STING", t))
            t += sting_dur
    segs[-1]["end"] += end_hold
    return segs, events, segs[-1]["end"]


def render(sections, out: Path, work: Path, images: dict, cards: dict, music: Path | None, sting_audio: Path | None,
           size=(1920, 1080), sting_after=0, end_hold=0.0, captions: dict | None = None, workers=6,
           max_rate: str | None = None, log: Path | None = None):
    work = Path(work)
    (work / "clips").mkdir(parents=True, exist_ok=True)
    (work / "cards").mkdir(parents=True, exist_ok=True)
    segs, events, total = build_timeline(sections, sting_after=sting_after, end_hold=end_hold)
    # absolute frame boundaries -> no drift
    jobs, clips = [], []
    kb_cycle = E.KB_MODES
    for k, sg in enumerate(segs):
        f0, f1 = round(sg["start"] * FPS), round(sg["end"] * FPS)
        dur = (f1 - f0) / FPS
        clip = work / "clips" / f"c{k:03d}.mp4"
        clips.append(clip)
        vis = sg["visual"]
        if clip.exists() and clip.stat().st_size > 0:  # resume: reuse clips already rendered for this timeline
            continue
        if vis.get("sting"):
            jobs.append((E.sting_clip, (clip, size, dur), {"log": log}))
        elif "card" in vis:
            cp = work / "cards" / f"{vis['card']}.png"
            if not cp.exists():
                spec = cards[vis["card"]]
                card(spec, size, images.get(spec.get("bg"))).save(cp)
            jobs.append((E.card_clip, (cp, clip, dur, size), {"log": log}))
        else:
            mode = vis.get("kb", kb_cycle[k % len(kb_cycle)])
            jobs.append((E.kenburns_clip, (images[vis["img"]], clip, dur, size, mode), {"log": log}))
    with ThreadPoolExecutor(workers) as ex:
        for f in [ex.submit(fn, *a, **kw) for fn, a, kw in jobs]:
            f.result()
    silent = work / "video_silent.mp4"
    E.concat(clips, silent, log=log)
    # audio
    voice = np.zeros(int((total + 1) * E.SR), np.float32)
    fx = np.zeros_like(voice)
    for path, at in events:
        if path == "STING":
            if sting_audio:
                fx = E.place(fx, E.decode(sting_audio), at, gain=0.5)
        else:
            voice = E.place(voice, E.decode(path), at)
    n = int(total * E.SR)
    voice, fx = voice[:n], fx[:n]
    mix = voice + fx
    if music:
        mix = mix + E.music_bed(music, total, voice)
    raw = work / "mix_raw.wav"
    E.write_wav(raw, mix / max(1.0, float(np.max(np.abs(mix)))))
    norm = work / "mix.wav"
    E.loudnorm(raw, norm, log=log)
    vf = None
    if captions:
        ass = work / "captions.ass"
        E.ass_captions(captions["words"], ass, size=size, **captions.get("style", {}))
        vf = f"subtitles={ass}:fontsdir={captions['fontsdir']}"
    E.mux(silent, norm, out, extra_vf=vf, max_rate=max_rate, log=log)
    json.dump({"segments": segs, "events": [(str(p), a) for p, a in events], "total": total},
              open(work / "timeline.json", "w"), indent=1, default=str)
    return out, segs, total
