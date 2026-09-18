"""Generate the E.V. application backdrop.

A very dark graphite gradient with a soft accent bloom and a faint technical
grid - enough to give the glass panels depth without competing with content.

Run from the repository root::

    python tools/make_background.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "assets" / "background.png"
WIDTH, HEIGHT = 1920, 1080


def main() -> int:
    base = Image.new("RGB", (WIDTH, HEIGHT), (4, 6, 10))
    px = base.load()
    for y in range(HEIGHT):
        t = y / (HEIGHT - 1)
        for_x = [0] * WIDTH
        # vertical gradient: slightly lighter at the top
        r = int(4 + 7 * (1 - t))
        g = int(6 + 11 * (1 - t))
        b = int(10 + 18 * (1 - t))
        base.paste((r, g, b), (0, y, WIDTH, y + 1))

    glow = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-500, -700, 1100, 620), fill=(12, 46, 66))
    gd.ellipse((1200, 700, 2300, 1600), fill=(10, 18, 52))
    glow = glow.filter(ImageFilter.GaussianBlur(260))
    base = Image.blend(base, Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0)), 0.0)
    base = Image.composite(Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0)), base, Image.new("L", (WIDTH, HEIGHT), 0))
    base = Image.fromarray(
        (
            __import__("numpy").clip(
                __import__("numpy").asarray(base, dtype="int16") + __import__("numpy").asarray(glow, dtype="int16") // 3,
                0,
                255,
            )
        ).astype("uint8")
    )

    grid = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    gdr = ImageDraw.Draw(grid)
    for x in range(0, WIDTH, 96):
        gdr.line((x, 0, x, HEIGHT), fill=(120, 190, 220, 6), width=1)
    for y in range(0, HEIGHT, 96):
        gdr.line((0, y, WIDTH, y), fill=(120, 190, 220, 6), width=1)
    grid = grid.filter(ImageFilter.GaussianBlur(0.6))

    out = Image.alpha_composite(base.convert("RGBA"), grid)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    out.convert("RGB").save(TARGET, optimize=True)
    print("wrote", TARGET)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
