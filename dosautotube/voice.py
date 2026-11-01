"""Voice: English narration via ElevenLabs text-to-speech, with character timestamps for sync + captions.

Uses a stock narrator voice (never a clone of a real person). No pitch shifting, ever.
"""
from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path

import requests

DEFAULT_VOICE = os.environ.get("ELEVENLABS_VOICE_ID", "cjVigY5qzO86Huf0OWal")  # premade US-English narrator
MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")


def _headers():
    key = os.environ["ELEVENLABS_API_KEY"]
    h = {"content-type": "application/json", "xi-api-key": key}
    if os.environ.get("ELEVENLABS_AUTH_BEARER"):  # when routed through a key proxy
        h["Authorization"] = f"Bearer {key}"
    return h


def synthesize(text: str, out_mp3: Path, previous_text: str | None = None, next_text: str | None = None,
               voice_id: str = DEFAULT_VOICE, speed: float = 0.97) -> dict:
    """Speak `text` to out_mp3; writes out_mp3.with_suffix('.json') with the character alignment."""
    out_mp3 = Path(out_mp3)
    meta = out_mp3.with_suffix(".json")
    if meta.exists() and out_mp3.exists():
        return json.loads(meta.read_text())
    base = os.environ.get("ELEVENLABS_BASE_URL", "https://api.elevenlabs.io").rstrip("/")
    body = {"text": text, "model_id": MODEL,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.15, "use_speaker_boost": True, "speed": speed}}
    if previous_text:
        body["previous_text"] = previous_text[-300:]
    if next_text:
        body["next_text"] = next_text[:300]
    for attempt in range(10):
        r = requests.post(f"{base}/v1/text-to-speech/{voice_id}/with-timestamps?output_format=mp3_44100_192",
                          headers=_headers(), json=body, timeout=300)
        if r.status_code == 429:
            time.sleep(5 + attempt * 3)
            continue
        r.raise_for_status()
        break
    d = r.json()
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    out_mp3.write_bytes(base64.b64decode(d["audio_base64"]))
    rec = {"text": text, "alignment": d["alignment"]}
    meta.write_text(json.dumps(rec))
    return rec


def narrate_sections(sections: list[dict], folder: Path) -> list[dict]:
    """One TTS call per chapter (natural flow), with neighbouring text for continuity."""
    texts = [" ".join(b["text"] for b in s["beats"]) for s in sections]
    out = []
    for i, s in enumerate(sections):
        rec = synthesize(texts[i], Path(folder) / f"{s['id']}.mp3",
                         texts[i - 1] if i else None, texts[i + 1] if i + 1 < len(texts) else None)
        out.append({"id": s["id"], "audio": str(Path(folder) / f"{s['id']}.mp3"), **rec})
    return out


def music(prompt: str, out: Path, seconds: int = 120) -> Path:
    """Instrumental background bed (ElevenLabs music)."""
    base = os.environ.get("ELEVENLABS_BASE_URL", "https://api.elevenlabs.io").rstrip("/")
    r = requests.post(f"{base}/v1/music?output_format=mp3_44100_192", headers=_headers(),
                      json={"prompt": prompt, "music_length_ms": seconds * 1000, "force_instrumental": True}, timeout=600)
    r.raise_for_status()
    Path(out).write_bytes(r.content)
    return Path(out)
