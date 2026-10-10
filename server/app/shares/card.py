"""The link-preview card of a share (PF5): a 1200 x 630 JPEG composed at
publish from the first panorama, seen in perspective around its start
bearing, with the share's title and the "Designed in Truebex" mark.

Without a panorama the first render is used (cropped to fill); without
either, the brand ground with the drafting grid. Type: Open Sans (OFL,
assets/OpenSans-OFL.txt). A title with characters Open Sans cannot draw is
left off the card rather than drawn as boxes.
"""

import io
import math
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import page

W, H = 1200, 630
ASSETS = Path(__file__).with_name("assets")
PAGE = (0x16, 0x16, 0x16)
TEXT = (0xED, 0xED, 0xED)
FG = (0xCB, 0xCB, 0xCB)
HFOV = 90.0
MAX_PITCH = 30.0


@lru_cache
def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(ASSETS / name), size)


@lru_cache
def _mark(height: int) -> Image.Image:
    mark = Image.open(ASSETS / "mark.png").convert("RGBA")
    return mark.resize((height * mark.width // mark.height, height), Image.LANCZOS)


def _roll(img: Image.Image, shift: int) -> Image.Image:
    """Columns rolled left by `shift` (wrapping), as an equirectangular image turns."""
    shift %= img.width
    if shift == 0:
        return img
    out = Image.new(img.mode, img.size)
    out.paste(img.crop((shift, 0, img.width, img.height)), (0, 0))
    out.paste(img.crop((0, 0, shift, img.height)), (img.width - shift, 0))
    return out


def perspective(pano: Image.Image, *, rel_bearing: float, pitch: float, hfov: float = HFOV, size=(W, H)) -> Image.Image:
    """A pinhole view of an equirectangular image.

    `rel_bearing` is degrees right of the image's middle column. The image is
    rolled so the view looks at the middle, then mapped with a mesh of quads.
    """
    pw, ph = pano.size
    rolled = _roll(pano, round(rel_bearing / 360.0 * pw))
    ow, oh = size
    f = (ow / 2) / math.tan(math.radians(hfov) / 2)
    tp = math.radians(max(-MAX_PITCH, min(MAX_PITCH, pitch)))
    cp, sp = math.cos(tp), math.sin(tp)

    def src(x: float, y: float) -> tuple[float, float]:
        rx, ry, rz = x - ow / 2, -(y - oh / 2), f
        ry, rz = ry * cp + rz * sp, -ry * sp + rz * cp
        lon = math.atan2(rx, rz)
        lat = math.atan2(ry, math.hypot(rx, rz))
        return (lon / (2 * math.pi) + 0.5) * pw, (0.5 - lat / math.pi) * ph

    cols, rows = 40, 21
    mesh = []
    for j in range(rows):
        y0, y1 = oh * j / rows, oh * (j + 1) / rows
        for i in range(cols):
            x0, x1 = ow * i / cols, ow * (i + 1) / cols
            ul, ll, lr, ur = src(x0, y0), src(x0, y1), src(x1, y1), src(x1, y0)
            box = (round(x0), round(y0), round(x1), round(y1))
            mesh.append((box, (*ul, *ll, *lr, *ur)))
    return rolled.transform(size, Image.MESH, mesh, Image.BILINEAR)


def _cover(img: Image.Image) -> Image.Image:
    scale = max(W / img.width, H / img.height)
    img = img.resize((max(W, round(img.width * scale)), max(H, round(img.height * scale))), Image.LANCZOS)
    left, top = (img.width - W) // 2, (img.height - H) // 2
    return img.crop((left, top, left + W, top + H))


def _grid() -> Image.Image:
    img = Image.new("RGB", (W, H), PAGE)
    d = ImageDraw.Draw(img)
    for step, shade in ((24, 0x1C), (120, 0x26)):
        for x in range(0, W, step):
            d.line([(x, 0), (x, H)], fill=(shade,) * 3)
        for y in range(0, H, step):
            d.line([(0, y), (W, y)], fill=(shade,) * 3)
    return img


def _glyph(ch: str, font: ImageFont.FreeTypeFont) -> bytes:
    img = Image.new("L", (int(font.size) * 2, int(font.size) * 2))
    ImageDraw.Draw(img).text((0, 0), ch, font=font, fill=255)
    return img.tobytes()


def drawable(text: str, font: ImageFont.FreeTypeFont) -> bool:
    """False when any character would come out as the font's missing-glyph box."""
    missing = _glyph(chr(0xFFFF), font)
    return all(ch.isspace() or _glyph(ch, font) != missing for ch in set(text))


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int, lines: int) -> list[str]:
    words, out, line = text.split(), [], ""
    for word in words:
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= width:
            line = trial
            continue
        if line:
            out.append(line)
        line = word
        if len(out) == lines:
            break
    if line and len(out) < lines:
        out.append(line)
    consumed = " ".join(out)
    if len(consumed) < len(" ".join(words)) and out:
        last = out[-1]
        while last and draw.textlength(last + "…", font=font) > width:
            last = last[:-1]
        out[-1] = last.rstrip() + "…"
    return out


def compose(background: Image.Image | None, title: str) -> bytes:
    img = (background.convert("RGB") if background is not None else _grid()).copy()
    if img.size != (W, H):
        img = _cover(img)
    # A dark band rising from the bottom so the type reads on any room.
    shade = Image.new("L", (1, H))
    for y in range(H):
        t = max(0.0, (y - H * 0.42) / (H * 0.58))
        shade.putpixel((0, y), int(235 * t**1.4))
    img.paste(Image.new("RGB", (W, H), PAGE), (0, 0), shade.resize((W, H)))

    d = ImageDraw.Draw(img)
    pad = 64
    mark = _mark(30)
    brand = _font("OpenSans-SemiBold.ttf", 28)
    y_brand = H - pad - mark.height
    img.paste(mark, (pad, y_brand), mark)
    d.text((pad + mark.width + 16, y_brand + mark.height / 2), page.DESIGNED_IN, font=brand, fill=FG, anchor="lm")

    head = _font("OpenSans-Bold.ttf", 56)
    if title and drawable(title, head):
        lines = _wrap(d, title, head, W - 2 * pad, 2)
        y = y_brand - 28 - 68 * len(lines)
        for line in lines:
            d.text((pad, y), line, font=head, fill=TEXT)
            y += 68
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=86, optimize=True)
    return out.getvalue()


def background_for(m: dict, pano_image: Image.Image | None, render_image: Image.Image | None) -> Image.Image | None:
    """The card's picture: the start panorama around its start bearing, else a render."""
    from . import manifest

    start = manifest.start_panorama(m)
    if pano_image is not None and start is not None:
        center = float(start.get("center_bearing_deg") or 0)
        bearing = float(start.get("start_bearing_deg", center))
        rel = ((bearing - center + 180) % 360) - 180
        return perspective(pano_image, rel_bearing=rel, pitch=float(start.get("start_pitch_deg") or 0))
    return render_image
