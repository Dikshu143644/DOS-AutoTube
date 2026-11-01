"""Metadata: title (<60 chars, curiosity), description with chapters + sources, tags, hashtags."""
from __future__ import annotations

from pathlib import Path

from . import brand


def ts(sec: float) -> str:
    sec = int(round(sec))
    return f"{sec // 60}:{sec % 60:02d}" if sec < 3600 else f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def chapters_from_timeline(segments: list[dict], chapter_titles: list[tuple[str, int]]) -> list[tuple[float, str]]:
    """chapter_titles: [(title, first_segment_index)]. YouTube needs the first at 0:00 and each >= 10 s."""
    out = [(0.0 if i == 0 else segments[idx]["start"], title) for i, (title, idx) in enumerate(chapter_titles)]
    return out


def description(summary: str, chapters: list[tuple[float, str]], sources: list[dict], hashtags: list[str],
                extra_links: list[str] = ()) -> str:
    lines = [summary.strip(), ""]
    if chapters:
        lines.append("Chapters")
        lines += [f"{ts(t)} {name}" for t, name in chapters]
        lines.append("")
    if sources:
        lines.append("Sources")
        lines += [f"- {s['name']}: {s['url']}" for s in sources]
        lines.append("")
    lines.append(f"Subscribe for one big AI idea, explained simply, every week: {brand.CHANNEL_URL}?sub_confirmation=1")
    lines += list(extra_links)
    lines.append("")
    lines.append("Narration uses an AI voice and the visuals are AI-generated 3D art and code-made diagrams; "
                 "the research, script and fact-checking are by DOS AI Explained.")
    lines.append("")
    lines.append(" ".join(hashtags))
    text = "\n".join(lines)
    assert len(text) <= 5000, "YouTube description limit is 5000 characters"
    return text


def check_title(title: str) -> str:
    assert len(title) < 60, f"title is {len(title)} chars"
    return title


def check_tags(tags: list[str]) -> list[str]:
    assert sum(len(t) + 2 for t in tags) <= 500, "YouTube tag limit is 500 characters"
    return tags


def write(folder: Path, **meta) -> Path:
    import json
    p = Path(folder) / "metadata.json"
    p.write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    return p
