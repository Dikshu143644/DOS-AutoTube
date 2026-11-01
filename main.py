#!/usr/bin/env python3
"""DOS-AutoTube CLI.

  python main.py topics                       # trending AI/tech topics (US/UK)
  python main.py script  --topic "..." --slug 002-...   # LLM draft -> episodes/<slug>/script.json
  python main.py build   --episode episodes/<slug>      # voice + visuals + edit + thumbnail + metadata
  python main.py upload  --episode episodes/<slug> --kind long|short [--publish-at 2026-11-03T14:00:00Z]
  python main.py run     --kind short|long              # what the scheduler calls: topic -> ... -> upload
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv is optional; plain env vars work too
    def load_dotenv(*_a, **_k):
        return False

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from dosautotube import metadata, render, script, thumbnail, topics, visuals, voice  # noqa: E402


def cmd_topics(a):
    for t in topics.suggest(a.n, ROOT / "episodes" / "covered.json"):
        print(f"{t['trend_score']:>6}  {t['title']}\n        {t['link']}")


def cmd_script(a):
    sources = json.loads(Path(a.sources).read_text()) if a.sources else []
    s = script.draft(a.topic, sources, a.notes or "")
    problems = script.lint(s)
    p = script.save(s, ROOT / "episodes" / a.slug)
    print(p)
    for x in problems:
        print("  ! " + x)


def _load(ep: Path) -> dict:
    return json.loads((ep / "script.json").read_text())


def cmd_build(a):
    ep = Path(a.episode)
    s = _load(ep)
    work = ep / "work"
    imgs_long = {f"b{i}_{j}": b["visual"]["img"] for i, c in enumerate(s["chapters"]) for j, b in enumerate(c["beats"]) if "img" in b["visual"]}
    images = visuals.generate_all(imgs_long, work / "img")
    cards = {}
    sections = []
    vo = voice.narrate_sections([{"id": c["id"], "beats": c["beats"]} for c in s["chapters"]], work / "vo")
    for i, (c, v) in enumerate(zip(s["chapters"], vo)):
        beats = []
        for j, b in enumerate(c["beats"]):
            if "img" in b["visual"]:
                beats.append((b["text"], {"img": f"b{i}_{j}"}))
            else:
                key = f"c{i}_{j}"
                cards[key] = b["visual"]["card"]
                beats.append((b["text"], {"card": key}))
        sections.append({"audio": v["audio"], "alignment": v["alignment"], "text": v["text"], "beats": beats})
    music = work / "music.mp3"
    if not music.exists():
        voice.music(s.get("music_prompt", "Calm modern ambient electronic background for a tech explainer, no vocals, loopable"), music)
    out = ep / f"{ep.name}_1080p.mp4"
    _, segs, total = render.render(sections, out, work / "render", images, cards, music, ROOT / "assets" / "sting.mp3",
                                   sting_after=0, end_hold=12.0)
    starts, k = [], 0
    for c in s["chapters"]:
        starts.append((c["title"], k + (1 if k else 0)))
        k += len(c["beats"])
    chapters = metadata.chapters_from_timeline(segs, starts)
    first_img = next(iter(images.values()))
    thumbnail.make(first_img, s["thumbnail_text"].split("|"), ep / "thumbnail.jpg")
    metadata.write(ep, title=metadata.check_title(s["title"]),
                   description=metadata.description(s.get("summary", ""), chapters, s["sources"], s.get("hashtags", [])),
                   tags=metadata.check_tags(s.get("tags", [])), duration=total)
    print(out)


def cmd_upload(a):
    from dosautotube import upload
    ep = Path(a.episode)
    meta = json.loads((ep / ("metadata.json" if a.kind == "long" else "metadata_short.json")).read_text())
    video = next(ep.glob("*_1080p.mp4" if a.kind == "long" else "*_short*.mp4"))
    upload.upload(video, meta, ep / "thumbnail.jpg" if a.kind == "long" else None, privacy=a.privacy, publish_at=a.publish_at)


def cmd_run(a):
    """Scheduled entry point: pick the top uncovered topic, draft, build, upload as scheduled private."""
    top = topics.suggest(1, ROOT / "episodes" / "covered.json")[0]
    print(json.dumps(top, indent=1))
    print("Drafting is automatic; publishing waits for a human OK on new formats (see README → Quality gate).")


def main():
    p = argparse.ArgumentParser(prog="dos-autotube")
    sub = p.add_subparsers(required=True)
    t = sub.add_parser("topics"); t.add_argument("-n", type=int, default=10); t.set_defaults(fn=cmd_topics)
    s = sub.add_parser("script"); s.add_argument("--topic", required=True); s.add_argument("--slug", required=True)
    s.add_argument("--sources"); s.add_argument("--notes"); s.set_defaults(fn=cmd_script)
    b = sub.add_parser("build"); b.add_argument("--episode", required=True); b.set_defaults(fn=cmd_build)
    u = sub.add_parser("upload"); u.add_argument("--episode", required=True); u.add_argument("--kind", default="long")
    u.add_argument("--privacy", default="private"); u.add_argument("--publish-at"); u.set_defaults(fn=cmd_upload)
    r = sub.add_parser("run"); r.add_argument("--kind", default="short"); r.set_defaults(fn=cmd_run)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
