"""Visuals: generated 3D stills (OpenAI-compatible image API) + code-drawn cards and diagrams.

Every on-screen word is drawn in code (crisp, never AI-lettered) and comes from the narration.
"""
from __future__ import annotations

import base64
import math
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter

from . import brand
from .brand import BG, BG2, LAVENDER, MUTED, PEACH, PINK, WHITE, font

# ----------------------------------------------------------------------------- image generation

def generate_image(prompt: str, out: Path, size: str = "1536x1024", quality: str = "high") -> Path:
    """Generate one still via an OpenAI-compatible images endpoint (OPENAI_BASE_URL / OPENAI_API_KEY)."""
    out = Path(out)
    if out.exists():
        return out
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com").rstrip("/")
    model = os.environ.get("IMAGE_MODEL", "gpt-image-1")
    r = requests.post(
        f"{base}/v1/images/generations",
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
        json={"model": model, "prompt": f"{prompt} {brand.IMAGE_STYLE}", "size": size, "quality": quality},
        timeout=400,
    )
    r.raise_for_status()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base64.b64decode(r.json()["data"][0]["b64_json"]))
    return out


def generate_all(prompts: dict[str, str], folder: Path, size: str = "1536x1024", workers: int = 8) -> dict[str, Path]:
    """Generate every still in parallel (one wait, not N)."""
    folder = Path(folder)
    with ThreadPoolExecutor(workers) as ex:
        futs = {k: ex.submit(generate_image, p, folder / f"{k}.png", size) for k, p in prompts.items()}
        return {k: f.result() for k, f in futs.items()}

# ----------------------------------------------------------------------------- drawing helpers

def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def gradient_color(t: float):
    """Peach -> pink -> lavender at t in [0,1]."""
    t = max(0.0, min(1.0, t))
    return _lerp(PEACH, PINK, t * 2) if t < 0.5 else _lerp(PINK, LAVENDER, (t - 0.5) * 2)


def gradient_text(img: Image.Image, xy, text: str, fnt, anchor="la"):
    """Draw text filled with the brand gradient (left->right)."""
    d = ImageDraw.Draw(img)
    box = d.textbbox(xy, text, font=fnt, anchor=anchor)
    w, h = box[2] - box[0], box[3] - box[1]
    if w <= 0 or h <= 0:
        return box
    grad = Image.new("RGB", (w, 1))
    for x in range(w):
        grad.putpixel((x, 0), gradient_color(x / max(1, w - 1)))
    grad = grad.resize((w, h))
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).text(xy, text, font=fnt, fill=255, anchor=anchor)
    layer = Image.new("RGB", img.size)
    layer.paste(grad, (box[0], box[1]))
    img.paste(layer, (0, 0), mask)
    return box


def glow_text(img: Image.Image, xy, text: str, fnt, fill=WHITE, glow=PINK, radius=18, anchor="la", strength=0.55):
    g = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(g).text(xy, text, font=fnt, fill=glow + (int(255 * strength),), anchor=anchor)
    g = g.filter(ImageFilter.GaussianBlur(radius))
    img.paste(g, (0, 0), g)
    ImageDraw.Draw(img).text(xy, text, font=fnt, fill=fill, anchor=anchor)


def wrap(text: str, fnt, max_w: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=fnt) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def rounded_panel(img, box, radius=36, fill=(30, 20, 30, 200), outline=True, width=3):
    """Glassy panel with a gradient border."""
    x0, y0, x1, y1 = box
    panel = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(panel).rounded_rectangle(box, radius, fill=fill)
    img.paste(panel, (0, 0), panel)
    if outline:
        border = Image.new("RGB", img.size)
        bw = x1 - x0
        grad = Image.new("RGB", (bw, 1))
        for x in range(bw):
            grad.putpixel((x, 0), gradient_color(x / max(1, bw - 1)))
        border.paste(grad.resize((bw, y1 - y0)), (x0, y0))
        m = Image.new("L", img.size, 0)
        ImageDraw.Draw(m).rounded_rectangle(box, radius, outline=255, width=width)
        img.paste(border, (0, 0), m)


def backdrop(size, image: Path | None = None, dim: float = 0.28, blur: int = 22) -> Image.Image:
    """Dark brand backdrop: blurred, dimmed still (if given) + warm vignette + soft neon glows."""
    W, H = size
    base = Image.new("RGB", size, BG)
    if image and Path(image).exists():
        src = Image.open(image).convert("RGB")
        s = max(W / src.width, H / src.height)
        src = src.resize((int(src.width * s) + 1, int(src.height * s) + 1), Image.LANCZOS)
        src = src.crop(((src.width - W) // 2, (src.height - H) // 2, (src.width - W) // 2 + W, (src.height - H) // 2 + H))
        src = src.filter(ImageFilter.GaussianBlur(blur))
        base = Image.blend(base, src, dim)
    glow = Image.new("RGB", size, (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    r = int(min(W, H) * 0.55)
    gd.ellipse((-r // 2, H - r, r, H + r // 2), fill=(90, 40, 30))
    gd.ellipse((W - r, -r // 2, W + r // 2, r), fill=(60, 40, 95))
    glow = glow.filter(ImageFilter.GaussianBlur(r // 3))
    base = Image.composite(base, base, Image.new("L", size, 255))
    from PIL import ImageChops
    base = ImageChops.add(base, glow)
    # vignette
    vig = Image.new("L", size, 0)
    ImageDraw.Draw(vig).ellipse((-W * 0.15, -H * 0.25, W * 1.15, H * 1.25), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(min(W, H) // 5))
    return Image.composite(base, Image.new("RGB", size, (6, 4, 6)), vig)


def paste_logo(img, center, size):
    logo = Image.open(brand.LOGO).convert("RGB").resize((size, size), Image.LANCZOS)
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).ellipse((0, 0, size - 1, size - 1), fill=255)
    m = m.filter(ImageFilter.GaussianBlur(1))
    ring = Image.new("RGBA", img.size, (0, 0, 0, 0))
    cx, cy = center
    ImageDraw.Draw(ring).ellipse((cx - size // 2 - 14, cy - size // 2 - 14, cx + size // 2 + 14, cy + size // 2 + 14), fill=PINK + (150,))
    ring = ring.filter(ImageFilter.GaussianBlur(22))
    img.paste(ring, (0, 0), ring)
    img.paste(logo, (cx - size // 2, cy - size // 2), m)

# ----------------------------------------------------------------------------- cards

def _kicker(img, text, x, y, fnt):
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((x, y, x + 10, y + fnt.size), 4, fill=PINK)
    d.text((x + 28, y + fnt.size // 2), text.upper(), font=fnt, fill=MUTED, anchor="lm")


def card(spec: dict, size=(1920, 1080), bg_image: Path | None = None) -> Image.Image:
    """Render one card from a spec. Types: title, statement, quote, code, flow, list, loop, compare, stat, two, endscreen."""
    W, H = size
    v = H > W  # vertical (Shorts)
    S = W / 1920 if not v else W / 1080
    img = backdrop(size, bg_image)
    d = ImageDraw.Draw(img)
    t = spec["type"]
    pad = int(140 * S)
    maxw = W - 2 * pad

    if spec.get("kicker"):
        _kicker(img, spec["kicker"], pad, int((120 if not v else 260) * S), font("SemiBold", int(34 * S)))

    if t in ("title", "statement"):
        big = font("Black" if t == "title" else "ExtraBold", int(spec.get("size", 112 if t == "title" else 100) * S))
        lines = wrap(spec["text"], big, maxw)
        lh = int(big.size * 1.12)
        sub = font("Medium", int(54 * S)) if spec.get("sub") else None
        sub_lines = wrap(spec["sub"], sub, maxw) if sub else []
        total = lh * len(lines) + (int(40 * S) + int(sub.size * 1.3) * len(sub_lines) if sub else 0)
        y = (H - total) // 2
        for i, ln in enumerate(lines):
            if spec.get("gradient_line") == i:
                gradient_text(img, (W // 2, y), ln, big, anchor="mt")
            else:
                glow_text(img, (W // 2, y), ln, big, anchor="mt")
            y += lh
        if sub:
            y += int(40 * S)
            for ln in sub_lines:
                d.text((W // 2, y), ln, font=sub, fill=MUTED, anchor="mt")
                y += int(sub.size * 1.3)

    elif t == "quote":
        q = font("Bold", int(64 * S))
        lines = wrap("\u201c" + spec["text"] + "\u201d", q, maxw - int(80 * S))
        lh = int(q.size * 1.25)
        y = (H - lh * len(lines)) // 2 - int(30 * S)
        rounded_panel(img, (pad - int(40 * S), y - int(70 * S), W - pad + int(40 * S), y + lh * len(lines) + int(130 * S)))
        for ln in lines:
            d.text((W // 2, y), ln, font=q, fill=WHITE, anchor="mt")
            y += lh
        gradient_text(img, (W // 2, y + int(30 * S)), "\u2014 " + spec["by"], font("SemiBold", int(38 * S)), anchor="mt")

    elif t == "code":
        mono = font("SemiBold", int(54 * S))
        box = (pad, H // 2 - int(110 * S), W - pad, H // 2 + int(110 * S))
        rounded_panel(img, box, fill=(18, 12, 18, 235))
        gradient_text(img, (box[0] + int(60 * S), H // 2), spec["fn"] + "(", mono, anchor="lm")
        x = box[0] + int(60 * S) + int(d.textlength(spec["fn"] + "(", font=mono))
        arg = spec["arg"]
        af = mono
        while d.textlength(arg + ")", font=af) > box[2] - x - int(50 * S):
            af = font("SemiBold", af.size - 2)
        d.text((x, H // 2), arg, font=af, fill=WHITE, anchor="lm")
        d.text((x + d.textlength(arg, font=af), H // 2), ")", font=mono, fill=LAVENDER, anchor="lm")
        if spec.get("caption"):
            d.text((W // 2, box[3] + int(70 * S)), spec["caption"], font=font("Medium", int(44 * S)), fill=MUTED, anchor="mt")

    elif t == "flow":
        steps = spec["steps"]
        n = len(steps)
        f = font("Bold", int(50 * S))
        bw, bh, gap = int(470 * S), int(230 * S), int(110 * S)
        total = n * bw + (n - 1) * gap
        x = (W - total) // 2
        y = H // 2 - bh // 2
        for i, s in enumerate(steps):
            hi = i == spec.get("highlight", -1)
            rounded_panel(img, (x, y, x + bw, y + bh), fill=(40, 22, 36, 235) if hi else (24, 16, 24, 220), outline=True, width=5 if hi else 2)
            for j, ln in enumerate(wrap(s, f, bw - int(40 * S))):
                d.text((x + bw // 2, y + bh // 2 + (j - (len(wrap(s, f, bw - int(40 * S))) - 1) / 2) * f.size * 1.2), ln, font=f, fill=WHITE, anchor="mm")
            if i < n - 1:
                ax = x + bw + int(18 * S)
                d.line((ax, H // 2, ax + gap - int(36 * S), H // 2), fill=PINK, width=int(6 * S))
                d.polygon([(ax + gap - int(36 * S), H // 2 - int(14 * S)), (ax + gap - int(14 * S), H // 2), (ax + gap - int(36 * S), H // 2 + int(14 * S))], fill=PINK)
            x += bw + gap
        if spec.get("caption"):
            d.text((W // 2, y + bh + int(90 * S)), spec["caption"], font=font("Medium", int(46 * S)), fill=MUTED, anchor="mt")

    elif t == "list":
        items = spec["items"]
        hl = spec.get("highlight")
        hl = set(hl if isinstance(hl, (list, tuple)) else ([hl] if hl is not None else []))
        title_f = font("ExtraBold", int(70 * S))
        y = int((230 if not v else 420) * S)
        if spec.get("title"):
            glow_text(img, (pad, y), spec["title"], title_f)
            y += int(140 * S)
        f = font("Bold", int(54 * S))
        num_f = font("Black", int(54 * S))
        rowh = int((118 if not v else 150) * S)
        for i, it in enumerate(items):
            on = not hl or i in hl
            col = WHITE if on else (110, 98, 112)
            if on and hl:
                rounded_panel(img, (pad - int(30 * S), y - int(14 * S), W - pad, y + rowh - int(26 * S)), radius=int(26 * S), fill=(44, 24, 40, 220), width=3)
            if on:
                gradient_text(img, (pad, y + int(10 * S)), f"{i + 1:02d}", num_f)
            else:
                d.text((pad, y + int(10 * S)), f"{i + 1:02d}", font=num_f, fill=col)
            d.text((pad + int(130 * S), y + int(10 * S)), it, font=f, fill=col)
            y += rowh

    elif t == "loop":
        nodes = spec.get("nodes", ["Think", "Act", "Observe"])
        hl = spec.get("highlight", -1)
        cx, cy = W // 2, int(H * (0.47 if not v else 0.42))
        R = int((300 if not v else 330) * S)
        ring = Image.new("RGBA", img.size, (0, 0, 0, 0))
        rd = ImageDraw.Draw(ring)
        for k in range(360):
            a0 = math.radians(k - 90)
            c = gradient_color(k / 359)
            rd.arc((cx - R, cy - R, cx + R, cy + R), k - 90, k - 89 + 1, fill=c + (255,), width=int(10 * S))
        gl = ring.filter(ImageFilter.GaussianBlur(int(16 * S)))
        img.paste(gl, (0, 0), gl)
        img.paste(ring, (0, 0), ring)
        f = font("ExtraBold", int(48 * S))
        nr = int(135 * S)
        for i, name in enumerate(nodes):
            a = math.radians(-90 + i * 360 / len(nodes))
            x, y = cx + R * math.cos(a), cy + R * math.sin(a)
            on = hl in (i, "all")
            col = (gradient_color(i / max(1, len(nodes) - 1)) if on else (36, 24, 34))
            node = Image.new("RGBA", img.size, (0, 0, 0, 0))
            nd = ImageDraw.Draw(node)
            if on:
                nd.ellipse((x - nr - 20, y - nr - 20, x + nr + 20, y + nr + 20), fill=col + (170,))
                node = node.filter(ImageFilter.GaussianBlur(int(24 * S)))
                img.paste(node, (0, 0), node)
            dd = ImageDraw.Draw(img)
            dd.ellipse((x - nr, y - nr, x + nr, y + nr), fill=(20, 12, 18) if not on else (34, 18, 30), outline=col if on else (90, 70, 90), width=int(6 * S))
            dd.text((x, y), name, font=f, fill=WHITE if on or hl == -1 else (150, 135, 150), anchor="mm")
        center = spec.get("center", "Repeat")
        if center:
            gradient_text(img, (cx, cy), center, font("Black", int(58 * S)), anchor="mm")
        if spec.get("caption"):
            cf_ = font("SemiBold", int(48 * S))
            yy = cy + int(R * 0.5) + nr + int(70 * S)
            for ln in wrap(spec["caption"], cf_, maxw):
                glow_text(img, (W // 2, yy), ln, cf_, anchor="mt", radius=10, strength=0.35)
                yy += int(cf_.size * 1.3)

    elif t == "compare":
        hl = spec.get("highlight")
        f_h = font("ExtraBold", int(76 * S))
        f_i = font("SemiBold", int(52 * S))
        colw = (W - 2 * pad - int(60 * S)) // 2
        for i, col in enumerate(spec["cols"]):
            x0 = pad + i * (colw + int(60 * S))
            on = hl is None or hl == i
            rounded_panel(img, (x0, int(200 * S), x0 + colw, H - int(170 * S)), fill=(40, 22, 36, 230) if on else (20, 14, 20, 200), width=5 if on else 2)
            if on:
                gradient_text(img, (x0 + colw // 2, int(270 * S)), col["title"], f_h, anchor="mt")
            else:
                d.text((x0 + colw // 2, int(270 * S)), col["title"], font=f_h, fill=(120, 105, 120), anchor="mt")
            y = int(420 * S)
            for it in col["items"]:
                for j, ln in enumerate(wrap(it, f_i, colw - int(120 * S))):
                    if j == 0:
                        d.ellipse((x0 + int(50 * S), y + int(14 * S), x0 + int(66 * S), y + int(30 * S)), fill=PINK if on else (90, 70, 90))
                    d.text((x0 + int(90 * S), y), ln, font=f_i, fill=WHITE if on else (125, 112, 125))
                    y += int(f_i.size * 1.3)
                y += int(30 * S)

    elif t == "stat":
        big = font("Black", int(250 * S))
        y = int(H * 0.40)
        g = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(g).text((W // 2, y), spec["value"], font=big, fill=PINK + (150,), anchor="mm")
        g = g.filter(ImageFilter.GaussianBlur(int(30 * S)))
        img.paste(g, (0, 0), g)
        gradient_text(img, (W // 2, y), spec["value"], big, anchor="mm")
        lf = font("Bold", int(56 * S))
        yy = y + int(170 * S)
        for ln in wrap(spec["label"], lf, maxw):
            d.text((W // 2, yy), ln, font=lf, fill=WHITE, anchor="mt")
            yy += int(lf.size * 1.25)
        if spec.get("source"):
            d.text((W // 2, H - int(110 * S)), "Source: " + spec["source"], font=font("Medium", int(32 * S)), fill=MUTED, anchor="mm")

    elif t == "two":
        f = font("ExtraBold", int(60 * S))
        y = int(H * 0.22) if not v else int(H * 0.25)
        if spec.get("title"):
            d.text((W // 2, y), spec["title"], font=font("SemiBold", int(46 * S)), fill=MUTED, anchor="mt")
            y += int(120 * S)
        for i, q in enumerate(spec["items"]):
            lines = wrap(q, f, maxw - int(200 * S))
            hgt = int(f.size * 1.25) * len(lines) + int(80 * S)
            rounded_panel(img, (pad, y, W - pad, y + hgt), fill=(36, 20, 34, 225))
            gradient_text(img, (pad + int(50 * S), y + hgt // 2), f"{i + 1}", font("Black", int(80 * S)), anchor="lm")
            yy = y + int(40 * S)
            for ln in lines:
                d.text((pad + int(150 * S), yy), ln, font=f, fill=WHITE)
                yy += int(f.size * 1.25)
            y += hgt + int(50 * S)

    elif t == "brand":
        ly = int(H * (0.36 if not v else 0.38))
        paste_logo(img, (W // 2, ly), int((330 if not v else 420) * S))
        f1 = font("Black", int(spec.get("size", 84) * S))
        yy = ly + int((230 if not v else 290) * S)
        for i, ln in enumerate(wrap(spec["text"], f1, maxw)):
            glow_text(img, (W // 2, yy), ln, f1, anchor="mt")
            yy += int(f1.size * 1.15)
        if spec.get("sub"):
            gradient_text(img, (W // 2, yy + int(30 * S)), spec["sub"], font("Bold", int(56 * S)), anchor="mt")
    elif t == "endscreen":
        # Leaves the right half free for YouTube end-screen elements (video + subscribe).
        lx = int(W * 0.27) if not v else W // 2
        ly = int(H * 0.40)
        paste_logo(img, (lx, ly), int(300 * S))
        f1 = font("ExtraBold", int(60 * S))
        glow_text(img, (lx, ly + int(230 * S)), spec.get("text", "Subscribe"), f1, anchor="mt")
        gradient_text(img, (lx, ly + int(320 * S)), brand.CHANNEL_NAME, font("Bold", int(48 * S)), anchor="mt")
        if spec.get("sub"):
            sf = font("Medium", int(36 * S))
            yy = ly + int(400 * S)
            for ln in wrap(spec["sub"], sf, int(W * 0.42) if not v else maxw):
                d.text((lx, yy), ln, font=sf, fill=MUTED, anchor="mt")
                yy += int(sf.size * 1.35)
        if not v:
            for bx in [(int(W * 0.52), int(H * 0.22), int(W * 0.93), int(H * 0.62))]:
                rounded_panel(img, bx, radius=24, fill=(255, 255, 255, 10), width=2)
    else:
        raise ValueError(f"unknown card type {t}")
    return img


def render_cards(specs: dict[str, dict], folder: Path, size=(1920, 1080), bg_images: dict | None = None) -> dict[str, Path]:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    out = {}
    for k, spec in specs.items():
        p = folder / f"{k}.png"
        bgi = (bg_images or {}).get(spec.get("bg"))
        card(spec, size, bgi).save(p)
        out[k] = p
    return out
