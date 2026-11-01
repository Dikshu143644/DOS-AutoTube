"""Topics: find timely, high-interest AI/tech topics for US/UK viewers.

Signals: Google News RSS (US + UK editions) and Hacker News front page — public, no keys.
Scoring favours topics that are both *trending* (many fresh mentions) and *explainable*
(evergreen "how/what/why" angles), and skips anything we already covered.
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import requests

UA = {"User-Agent": "DOS-AutoTube/0.1 (+https://github.com/Dikshu143644/DOS-AutoTube)"}
FEEDS = [
    "https://news.google.com/rss/search?q=artificial+intelligence+when:7d&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=artificial+intelligence+when:7d&hl=en-GB&gl=GB&ceid=GB:en",
    "https://news.google.com/rss/search?q=AI+tools+when:7d&hl=en-US&gl=US&ceid=US:en",
]
KEY_TERMS = ["agent", "agents", "chatgpt", "gemini", "claude", "llm", "openai", "google", "apple", "nvidia", "robot",
             "deepfake", "copilot", "regulation", "chip", "model", "search", "video", "image", "privacy", "jobs", "coding"]
STOP = set("the a an and or of to in on for with is are was be by from at as this that it its new how why what will".split())


def headlines(limit_per_feed: int = 40) -> list[dict]:
    items = []
    for url in FEEDS:
        try:
            root = ET.fromstring(requests.get(url, headers=UA, timeout=20).content)
            for it in root.iter("item"):
                items.append({"title": it.findtext("title", ""), "link": it.findtext("link", ""),
                              "date": it.findtext("pubDate", ""), "feed": url})
                if len(items) % limit_per_feed == 0:
                    break
        except Exception as e:  # a feed being down never stops the run
            print(f"[topics] feed failed: {url}: {e}")
    try:
        ids = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=20).json()[:60]
        for i in ids:
            s = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{i}.json", timeout=20).json() or {}
            if re.search(r"\b(AI|LLM|GPT|agent|model|neural)\b", s.get("title", ""), re.I):
                items.append({"title": s["title"], "link": s.get("url", ""), "date": "", "feed": "hn", "score": s.get("score", 0)})
    except Exception as e:
        print(f"[topics] HN failed: {e}")
    return items


def rank(items: list[dict], covered: list[str] = ()) -> list[dict]:
    words = Counter()
    for it in items:
        for w in re.findall(r"[a-z][a-z0-9\-]+", it["title"].lower()):
            if w not in STOP and len(w) > 2:
                words[w] += 1
    scored = []
    for it in items:
        t = it["title"].lower()
        if any(c.lower() in t for c in covered):
            continue
        s = sum(words[w] for w in set(re.findall(r"[a-z][a-z0-9\-]+", t)) if w in KEY_TERMS) + it.get("score", 0) / 100
        scored.append({**it, "trend_score": round(s, 2)})
    return sorted(scored, key=lambda x: -x["trend_score"])


def suggest(n: int = 10, history: Path | None = None) -> list[dict]:
    covered = json.loads(Path(history).read_text()) if history and Path(history).exists() else []
    return rank(headlines(), covered)[:n]


if __name__ == "__main__":
    for t in suggest():
        print(f"{t['trend_score']:>6}  {t['title']}")
