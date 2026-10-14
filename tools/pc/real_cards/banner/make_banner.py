#!/usr/bin/env python3
"""Make the Legendary Duelist title banner (1920x1080) from card art and type.

    python tools/pc/real_cards/banner/make_banner.py [out.png] [--size=1920x1080] [--no-footer]

Cards' pictures are YGOPRODeck's cropped art (cached beside this script in art/, not kept in git);
the rest is drawn here: a dark blue sky, a golden glow, the cards' art fading into one another and the
title in gold. Edit TITLE / SUBTITLE / CARDS below and run it again.
"""
import io
import math
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
OUT = Path(ARGS[0]) if ARGS else HERE / "legendary-duelist-banner.png"
W, H = 1920, 1080
for arg in sys.argv[1:]:
    if arg.startswith("--size="):
        W, H = (int(v) for v in arg.split("=")[1].split("x"))
S = min(W / 1920, H / 1080)          # the type's scale: 1 at 1920 x 1080
BRAND = "Yu-Gi-Oh!"
TITLE = ("LEGENDARY", "DUELIST")
SUBTITLE = ""
FOOTER = "PRESS START"
FONT_BOLD = "C:/Windows/Fonts/georgiab.ttf"
FONT_BOLD_FALLBACK = "C:/Windows/Fonts/cambriab.ttf"
# the logo's lettering is custom; these are the closest faces on Windows (swap for a fan font if you have one)
FONT_BRAND = "C:/Windows/Fonts/ROCKEB.TTF"       # Yu-Gi-Oh!: heavy, slab, hand-painted feel
FONT_TITLE = "C:/Windows/Fonts/impact.ttf"       # LEGENDARY DUELIST: like FORBIDDEN MEMORIES on the cover
BRAND_FILL = [(0, (255, 252, 220)), (0.5, (250, 226, 120)), (1, (214, 150, 40))]
TITLE_FILL = [(0, (255, 236, 120)), (0.3, (255, 160, 30)), (0.65, (226, 60, 14)), (1, (120, 14, 6))]
# left to right, each (password, share of the width): the gods behind, the aces in front
CARDS = [(10000000, 1.0), (46986414, 1.2), (89631139, 1.5), (74677422, 1.2), (10000020, 1.0)]
UA = "Mozilla/5.0"


def art(password):
    cache = HERE / "art" / f"{password}.jpg"
    if not cache.exists():
        cache.parent.mkdir(exist_ok=True)
        request = urllib.request.Request(f"https://images.ygoprodeck.com/images/cards_cropped/{password}.jpg", headers={"User-Agent": UA})
        with urllib.request.urlopen(request, timeout=60) as response:
            cache.write_bytes(response.read())
    return Image.open(cache).convert("RGB")


def font(size, *paths):
    for path in paths or (FONT_BOLD, FONT_BOLD_FALLBACK):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def gradient(size, stops):
    """A vertical gradient of (position 0-1, (r, g, b)) stops."""
    w, h = size
    column = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        for (a, ca), (b, cb) in zip(stops, stops[1:]):
            if a <= t <= b:
                k = (t - a) / (b - a) if b > a else 0
                column.putpixel((0, y), tuple(round(ca[i] + (cb[i] - ca[i]) * k) for i in range(3)))
                break
    return column.resize((w, h))


def background():
    sky = gradient((W, H), [(0, (4, 8, 28)), (0.55, (10, 18, 56)), (1, (2, 3, 10))])
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).ellipse((W * 0.2, H * 0.1, W * 0.8, H * 0.95), fill=255)
    glow = glow.filter(ImageFilter.GaussianBlur(220))
    gold = Image.new("RGB", (W, H), (214, 150, 30))
    return Image.composite(gold, sky, glow.point(lambda v: int(v * 0.42)))


def panels(base):
    total = sum(share for _, share in CARDS)
    x = -int(W * 0.04)
    span = W * 1.08
    for index, (password, share) in enumerate(CARDS):
        width = int(span * share / total)
        picture = art(password)
        scale = max(H * 0.92 / picture.height, width * 1.5 / picture.width)
        picture = picture.resize((int(picture.width * scale), int(picture.height * scale)), Image.LANCZOS)
        left = max(0, (picture.width - width * 1.5) // 2)
        picture = picture.crop((left, 0, left + int(width * 1.5), picture.height))
        # fade the sides into the neighbour and the bottom into the dark
        mask = Image.new("L", picture.size, 255)
        draw = ImageDraw.Draw(mask)
        fade = picture.width // 3
        for i in range(fade):
            level = int(255 * (i / fade) ** 1.5)
            draw.line((i, 0, i, picture.height), fill=level)
            draw.line((picture.width - 1 - i, 0, picture.width - 1 - i, picture.height), fill=level)
        vertical = gradient((1, picture.height), [(0, (255,) * 3), (0.55, (230,) * 3), (1, (0,) * 3)]).convert("L").resize(picture.size)
        mask = ImageChops.multiply(mask, vertical)
        strength = 0.78 if index in (1, 2, 3) else 0.5      # the gods stay behind
        mask = mask.point(lambda v: int(v * strength))
        picture = Image.blend(picture, Image.new("RGB", picture.size, (8, 14, 40)), 0.18)
        base.paste(picture, (int(x - (picture.width - width) / 2), int(H * 0.04)), mask)
        x += width
    return base


def vignette(base):
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).ellipse((-W * 0.15, -H * 0.2, W * 1.15, H * 1.2), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(160))
    return Image.composite(base, Image.new("RGB", (W, H), (1, 2, 8)), mask)


def spaced(draw, center, text, face, fill, gap, stroke=0, stroke_fill=None):
    widths = [draw.textlength(ch, font=face) for ch in text]
    total = sum(widths) + gap * (len(text) - 1)
    x = center[0] - total / 2
    for ch, width in zip(text, widths):
        draw.text((x, center[1]), ch, font=face, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
        x += width + gap


def gold_text(base, lines, size=210, top_at=0.40, step=205, gap=14, face_path=None, stops=None, outer=None, backdrop=False):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    mask = Image.new("L", (W, H), 0)
    shadow = Image.new("L", (W, H), 0)
    big = font(int(size * S), face_path) if face_path else font(int(size * S))
    y = int(H * top_at)
    for text in lines:
        md, sd = ImageDraw.Draw(mask), ImageDraw.Draw(shadow)
        spaced(md, (W // 2, y), text, big, 255, int(gap * S))
        spaced(sd, (W // 2, y), text, big, 255, int(gap * S), stroke=max(2, int(size / 15 * S)), stroke_fill=255)
        y += int(step * S)
    # a dark outline and a warm glow behind the gold
    glow = shadow.filter(ImageFilter.GaussianBlur(max(4, int(28 * S)))).point(lambda v: int(v * 0.9))
    base.paste(Image.new("RGB", (W, H), (255, 160, 20)), (0, 0), glow.point(lambda v: int(v * 0.55)))
    base.paste(Image.new("RGB", (W, H), (6, 4, 0)), (0, 0), shadow)
    fill = gradient((W, int(size * 1.15 * S)), stops or [(0, (255, 248, 200)), (0.35, (255, 213, 74)), (0.6, (222, 150, 24)), (1, (120, 70, 6))])
    if backdrop:       # the red splash behind the logo on the cover
        splash = Image.new("L", (W, H), 0)
        bx0, by0, bx1, by1 = mask.getbbox()
        ImageDraw.Draw(splash).ellipse((bx0 - 40 * S, by0 - 30 * S, bx1 + 40 * S, by1 + 30 * S), fill=255)
        splash = splash.filter(ImageFilter.GaussianBlur(int(36 * S)))
        base.paste(Image.new("RGB", (W, H), (200, 24, 14)), (0, 0), splash.point(lambda v: int(v * 0.9)))
    gold = Image.new("RGB", (W, H), (222, 150, 24))
    for line in range(len(lines)):
        gold.paste(fill, (0, int(H * top_at) + int(step * S) * line + int(size * 0.12 * S)))
    base.paste(gold, (0, 0), mask)
    if outer:          # a pale rim outside the dark outline, as on the cover
        rim = shadow.filter(ImageFilter.MaxFilter(9))
        rim = ImageChops.subtract(rim, shadow)
        base.paste(Image.new("RGB", (W, H), outer), (0, 0), rim)
        base.paste(gold, (0, 0), mask)
    # a thin light edge along the top of the letters
    edge = ImageChops.subtract(mask, ImageChops.offset(mask, 0, 5))
    base.paste(Image.new("RGB", (W, H), (255, 252, 225)), (0, 0), edge)
    return base


def ornament(draw, y):
    gold = (222, 170, 50)
    draw.line((W * 0.28, y, W * 0.46, y), fill=gold, width=max(1, int(3 * S)))
    draw.line((W * 0.54, y, W * 0.72, y), fill=gold, width=max(1, int(3 * S)))
    for dx in (-18, 0, 18):
        size = 9 if dx == 0 else 5
        cx = W // 2 + dx * 1.4
        draw.polygon([(cx, y - size), (cx + size, y), (cx, y + size), (cx - size, y)], fill=gold)


def main():
    image = vignette(panels(background()))
    image = gold_text(image, [BRAND], size=118, top_at=0.215, step=0, gap=10, face_path=FONT_BRAND, stops=BRAND_FILL, backdrop=True)
    image = gold_text(image, TITLE, size=200, step=200, gap=10, face_path=FONT_TITLE, stops=TITLE_FILL, outer=(255, 240, 200))
    draw = ImageDraw.Draw(image)
    below = int(H * 0.40) + int(205 * S) * 2
    ornament(draw, below + int(28 * S))
    if SUBTITLE:
        spaced(draw, (W // 2, below + int(55 * S)), SUBTITLE, font(int(46 * S)), (236, 200, 96), int(12 * S), stroke=max(1, int(3 * S)), stroke_fill=(10, 6, 0))
    if "--no-footer" not in sys.argv:
        spaced(draw, (W // 2, int(H * 0.93)), FOOTER, font(int(34 * S)), (225, 225, 235), int(22 * S))
    image.save(OUT, optimize=True)
    print(f"banner -> {OUT}")


if __name__ == "__main__":
    main()
