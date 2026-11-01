"""Script: turn a topic + sources into an original, fact-checked episode script (JSON).

The LLM drafts; the rules below keep it original and honest. A human-readable episode file
(episodes/<slug>/script.json) is the single source of truth for voice, visuals and metadata.
Supports Gemini (GEMINI_API_KEY) or any OpenAI-compatible endpoint (OPENAI_API_KEY / OPENAI_BASE_URL).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import requests

RULES = """You write scripts for DOS AI Explained, a YouTube channel that explains AI and tech simply
for curious beginners, students, creators and professionals in the US and UK.
Rules:
- Original explanation in your own words, with one concrete worked example. No filler, no hype.
- Hook in the first sentence (a contrast, a surprise or a question). Spoken, friendly, plain English.
- Every number or claim must come from the SOURCES given; attribute it in the sentence ("Gartner predicts ...").
  If a fact is not in the sources, leave it out.
- Long video: 6-8 minutes (~900-1100 words) in 5-7 chapters, ending with a recap + subscribe line.
- Short: 30-50 seconds (~75-110 words): hook -> one insight -> CTA.
- Each chapter is a list of beats (1-2 sentences each). For each beat give a visual: either
  {"img": "<one-line 3D scene description, no text in image>"} or {"card": {...}} where the card shows
  ONLY words that are spoken in that beat (types: statement, list, loop, compare, stat, quote, code, flow, two).
Return JSON: {"title":..., "chapters":[{"id":..,"title":..,"beats":[{"text":..,"visual":{..}}]}],
"short":{"beats":[...]}, "sources":[{"name":..,"url":..}], "thumbnail_text":"3-4 WORDS"}"""


def _gemini(prompt: str) -> str:
    key = os.environ["GEMINI_API_KEY"]
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                      headers={"x-goog-api-key": key},
                      json={"contents": [{"parts": [{"text": prompt}]}],
                            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.7}},
                      timeout=300)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def _openai(prompt: str) -> str:
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com").rstrip("/")
    r = requests.post(f"{base}/v1/chat/completions", headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                      json={"model": os.environ.get("SCRIPT_MODEL", "gpt-4.1"), "response_format": {"type": "json_object"},
                            "messages": [{"role": "user", "content": prompt}]}, timeout=300)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def draft(topic: str, sources: list[dict], notes: str = "") -> dict:
    src = "\n".join(f"- {s['name']}: {s['url']}\n  {s.get('excerpt', '')[:1500]}" for s in sources)
    prompt = f"{RULES}\n\nTOPIC: {topic}\nNOTES: {notes}\nSOURCES:\n{src}"
    raw = _gemini(prompt) if os.environ.get("GEMINI_API_KEY") else _openai(prompt)
    return json.loads(re.sub(r"^```json|```$", "", raw.strip()))


def lint(script: dict) -> list[str]:
    """Cheap guards before we spend on voice/visuals."""
    problems = []
    words = sum(len(b["text"].split()) for c in script["chapters"] for b in c["beats"])
    if not 800 <= words <= 1300:
        problems.append(f"long video is {words} words (want ~900-1100)")
    sw = sum(len(b["text"].split()) for b in script["short"]["beats"])
    if not 70 <= sw <= 125:
        problems.append(f"short is {sw} words (want ~75-110)")
    spoken = " ".join(b["text"] for c in script["chapters"] for b in c["beats"]).lower()
    for c in script["chapters"]:
        for b in c["beats"]:
            for n in re.findall(r"\d+(?:\.\d+)?%?", json.dumps(b.get("visual", {}))):
                if n.rstrip("%") not in spoken:
                    problems.append(f"on-screen number {n} is not spoken")
    if not script.get("sources"):
        problems.append("no sources")
    return problems


def save(script: dict, folder: Path) -> Path:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / "script.json"
    p.write_text(json.dumps(script, indent=2, ensure_ascii=False))
    return p
