"""Thumbnail: 1280x720, 3-4 bold words, high contrast, brand colours. Text is set in code."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from . import brand
from .visuals import font, gradient_text, paste_logo

W, H = 1280, 720


def make(image: Path, lines: list[str], out: Path, accent: int = -1, logo: bool = True) -> Path:
    """lines: 2-3 short lines (3-4 words total). `accent` line gets the peach->pink->lavender gradient."""
    bg = Image.open(image).convert("RGB")
    s = max(W / bg.width, H / bg.height) * 1.05
    bg = bg.resize((int(bg.width * s), int(bg.height * s)), Image.LANCZOS)
    x0 = bg.width - W  # keep the subject on the right
    bg = bg.crop((x0, (bg.height - H) // 2, x0 + W, (bg.height - H) // 2 + H))
    bg = ImageEnhance.Contrast(ImageEnhance.Color(bg).enhance(1.15)).enhance(1.12)
    # dark wedge on the left for text contrast
    shade = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(shade)
    for x in range(W):
        d.line((x, 0, x, H), fill=int(235 * max(0, 1 - x / (W * 0.62)) ** 1.2))
    img = Image.composite(Image.new("RGB", (W, H), brand.BG), bg, shade)
    # text block
    sizes = [150, 150, 150]
    y = max(40, (H - int(150 * 1.02) * len(lines)) // 2 - 10)
    for i, ln in enumerate(lines):
        f = font("Black", sizes[i])
        while ImageDraw.Draw(img).textlength(ln, font=f) > W * 0.62:
            f = font("Black", f.size - 4)
        # heavy shadow / outline for readability at small sizes
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((62, y + 6), ln, font=f, fill=(0, 0, 0, 230), stroke_width=10, stroke_fill=(0, 0, 0, 230))
        sh = sh.filter(ImageFilter.GaussianBlur(6))
        img.paste(sh, (0, 0), sh)
        if i == (accent if accent >= 0 else len(lines) - 1):
            ImageDraw.Draw(img).text((56, y), ln, font=f, fill=(20, 8, 14), stroke_width=6, stroke_fill=(20, 8, 14))
            gradient_text(img, (56, y), ln, f)
        else:
            ImageDraw.Draw(img).text((56, y), ln, font=f, fill=brand.WHITE, stroke_width=6, stroke_fill=(20, 8, 14))
        y += int(f.size * 1.02)
    if logo:
        paste_logo(img, (W - 92, H - 92), 120)
    img.save(out, quality=92)
    return Path(out)
