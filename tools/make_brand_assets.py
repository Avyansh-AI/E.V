"""Generate the E.V. brand assets (logo, icon, tray mark, favicon).

The identity is fully original: a geometric "EV" monogram on a dark
glass-metal tile, built from rounded bars and a chevron. Nothing here is
traced from third-party artwork.

Run from the repository root::

    python tools/make_brand_assets.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
DASHBOARD_STATIC = ROOT / "dashboard" / "static"

# E.V. palette
TILE_TOP = (12, 18, 26, 255)
TILE_BOTTOM = (5, 8, 12, 255)
STROKE = (30, 42, 54, 255)
TEXT = (242, 247, 251, 255)
ACCENT = (79, 209, 255, 255)
ACCENT_2 = (124, 140, 255, 255)

SIZE = 1024


def _vertical_gradient(size: int, top, bottom) -> Image.Image:
    grad = Image.new("RGBA", (1, size))
    for y in range(size):
        t = y / max(1, size - 1)
        grad.putpixel(
            (0, y),
            (
                int(top[0] + (bottom[0] - top[0]) * t),
                int(top[1] + (bottom[1] - top[1]) * t),
                int(top[2] + (bottom[2] - top[2]) * t),
                255,
            ),
        )
    return grad.resize((size, size), Image.NEAREST)


def _rounded_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return mask


def _bar(draw: ImageDraw.ImageDraw, box, radius: int, fill) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def _chevron_mask(size: int, stroke: int) -> Image.Image:
    """Mask of the accent 'V' chevron: one mitered path with rounded caps."""
    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    pts = [(596, 292), (712, 726), (828, 292)]
    md.line(pts, fill=255, width=stroke, joint="curve")
    half = stroke // 2
    for x, y in (pts[0], pts[2]):
        md.ellipse((x - half, y - half, x + half, y + half), fill=255)
    return mask


def _horizontal_gradient(size: int, left, right) -> Image.Image:
    grad = Image.new("RGBA", (size, 1))
    for x in range(size):
        t = x / max(1, size - 1)
        grad.putpixel(
            (0, x) if False else (x, 0),
            (
                int(left[0] + (right[0] - left[0]) * t),
                int(left[1] + (right[1] - left[1]) * t),
                int(left[2] + (right[2] - left[2]) * t),
                255,
            ),
        )
    return grad.resize((size, size), Image.NEAREST)


def build_logo(size: int = SIZE) -> Image.Image:
    scale = size / SIZE
    tile = _vertical_gradient(size, TILE_TOP, TILE_BOTTOM)
    tile.putalpha(_rounded_mask(size, int(220 * scale)))

    # subtle interior light from the top-left corner
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse(
        (-int(size * 0.25), -int(size * 0.35), int(size * 0.85), int(size * 0.7)),
        fill=(72, 132, 178, 46),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(int(90 * scale)))
    tile = Image.alpha_composite(tile, Image.composite(glow, Image.new("RGBA", (size, size), (0, 0, 0, 0)), tile.getchannel("A")))

    def px(v: float) -> int:
        return int(v * scale)

    stroke_w = px(74)
    chevron = _chevron_mask(size, stroke_w)

    # accent bloom behind the chevron
    bloom = chevron.filter(ImageFilter.GaussianBlur(int(30 * scale)))
    bloom_rgba = _horizontal_gradient(size, (79, 209, 255, 120), (124, 140, 255, 120))
    bloom_rgba.putalpha(bloom.point(lambda v: int(v * 0.55)))
    tile = Image.alpha_composite(tile, bloom_rgba)

    draw = ImageDraw.Draw(tile)

    # tile outline + top highlight for the glass-metal feel
    draw.rounded_rectangle(
        (int(6 * scale), int(6 * scale), size - int(6 * scale), size - int(6 * scale)),
        radius=int(214 * scale),
        outline=STROKE,
        width=max(1, int(4 * scale)),
    )
    draw.arc(
        (int(80 * scale), int(40 * scale), size - int(80 * scale), int(360 * scale)),
        start=200, end=340,
        fill=(150, 196, 224, 70),
        width=max(1, int(6 * scale)),
    )

    bar_radius = px(30)
    bar_h = px(74)
    # --- E: three horizontal bars
    _bar(draw, (px(232), px(280), px(560), px(280) + bar_h), bar_radius, TEXT)
    _bar(draw, (px(232), px(474), px(500), px(474) + bar_h), bar_radius, TEXT)
    _bar(draw, (px(232), px(668), px(560), px(668) + bar_h), bar_radius, TEXT)

    # --- V: gradient chevron
    chevron_rgba = _horizontal_gradient(size, ACCENT, ACCENT_2)
    chevron_rgba.putalpha(chevron)
    tile = Image.alpha_composite(tile, chevron_rgba)
    return tile


def build_wordmark(height: int = 256) -> Image.Image:
    """Horizontal 'E.V.' wordmark on a transparent background."""
    width = int(height * 3.6)
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    scale = height / 256
    bar_r = int(14 * scale)
    bar_h = int(30 * scale)
    x0 = int(18 * scale)
    for y in (int(52 * scale), int(113 * scale), int(174 * scale)):
        length = int(96 * scale) if y != int(113 * scale) else int(70 * scale)
        _bar(draw, (x0, y, x0 + length, y + bar_h), bar_r, TEXT)
    dot_r = int(16 * scale)
    draw.ellipse((x0 + int(120 * scale), int(178 * scale), x0 + int(120 * scale) + dot_r * 2, int(178 * scale) + dot_r * 2), fill=ACCENT)
    vx = x0 + int(170 * scale)
    stroke = int(30 * scale)
    draw.line([(vx, int(56 * scale)), (vx + int(52 * scale), int(200 * scale))], fill=ACCENT, width=stroke, joint="curve")
    draw.line([(vx + int(52 * scale), int(200 * scale)), (vx + int(104 * scale), int(56 * scale))], fill=ACCENT_2, width=stroke, joint="curve")
    return img


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    DASHBOARD_STATIC.mkdir(parents=True, exist_ok=True)

    logo = build_logo()
    logo.save(ASSETS / "ev_logo.png")
    build_wordmark().save(ASSETS / "ev_wordmark.png")

    sizes = [16, 24, 32, 48, 64, 128, 256]
    logo.save(ASSETS / "ev_logo.ico", sizes=[(s, s) for s in sizes])
    for s in (32, 64, 256):
        logo.resize((s, s), Image.LANCZOS).save(ASSETS / f"ev_mark_{s}.png")
    logo.resize((512, 512), Image.LANCZOS).save(DASHBOARD_STATIC / "ev-icon.png")
    print("brand assets written to", ASSETS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
