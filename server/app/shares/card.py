"""The link-preview card of a share (PF5): a 1200 x 630 JPEG composed at
publish from the first panorama, seen in perspective around its start
bearing, with the share's title and the "Designed in Truebex" mark.

Without a panorama the first render is used (cropped to fill); without
either, the brand ground with the drafting grid. Type: Open Sans (OFL,
assets/OpenSans-OFL.txt). A title with characters Open Sans cannot draw is
left off the card rather than drawn as boxes.

PF5a: a title with right-to-left letters (Arabic, Persian, Urdu, Hebrew) is
joined and ordered by rtl.py and drawn right-aligned in the same band, its
Arabic letters in Noto Sans Arabic (OFL, assets/NotoSansArabic-OFL.txt) and
its other letters, digits and marks in Open Sans. If any letter cannot be
joined or neither font has a character, the title is left off as before:
never boxes, never unjoined or reversed letters.

PF5b: a share-bundle 1.1 manifest's `cover` (a JPEG the app made for link
previews) is the card instead (`from_cover`); without one, the card above.
"""

import io
import math
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import page, rtl

W, H = 1200, 630
ASSETS = Path(__file__).with_name("assets")
PAGE = (0x16, 0x16, 0x16)
TEXT = (0xED, 0xED, 0xED)
FG = (0xCB, 0xCB, 0xCB)
HFOV = 90.0
MAX_PITCH = 30.0
PAD = 64
LATIN = "OpenSans-Bold.ttf"
ARABIC = "NotoSansArabic-Bold.ttf"
TITLE_SIZE = 56
LINE_PITCH = 68
ELLIPSIS = chr(0x2026)


@lru_cache
def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(ASSETS / name), size)


@lru_cache
def _basic(name: str, size: int) -> ImageFont.FreeTypeFont:
    """Glyphs set one after another, left to right, on every machine: rtl.py has
    already joined and ordered the text, so libraqm (where installed) must not
    reorder it again."""
    return ImageFont.truetype(str(ASSETS / name), size, layout_engine=ImageFont.Layout.BASIC)


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


@lru_cache(maxsize=4096)
def _has(ch: str, name: str) -> bool:
    return drawable(ch, _basic(name, TITLE_SIZE))


def _wrap(text: str, width: float, lines: int, measure) -> list[str]:
    """Up to `lines` lines of whole words no wider than `width` (as `measure`
    finds them); words left over end the last line with an ellipsis."""
    words, out, line = text.split(), [], ""
    for word in words:
        trial = f"{line} {word}".strip()
        if measure(trial) <= width:
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
        while last and measure(last + ELLIPSIS) > width:
            last = last[:-1]
        out[-1] = last.rstrip() + ELLIPSIS
    return out


def _fonts(text: str) -> list[str] | None:
    """The font of each character of a shaped line: Arabic in Noto Sans Arabic,
    other letters in Open Sans; digits, spaces and marks in the font of the
    nearest letter before them (else after) when it has them, else the other.
    None when neither font has a character."""
    strong = [rtl.bidi_class(ch) in ("L", "R", "AL") and not rtl.invisible(ch) for ch in text]
    out = []
    for i, ch in enumerate(text):
        if rtl.invisible(ch):  # a mark like RLM steers the order and is never drawn
            out.append(LATIN)
            continue
        if rtl.arabic(ch):
            order: tuple[str, ...] = (ARABIC,)
        elif strong[i]:
            order = (LATIN,)
        else:
            near = next((text[j] for j in range(i - 1, -1, -1) if strong[j]), None)
            near = near or next((text[j] for j in range(i + 1, len(text)) if strong[j]), None)
            order = (ARABIC, LATIN) if near and rtl.arabic(near) else (LATIN, ARABIC)
        name = next((n for n in order if _has(ch, n)), None)
        if name is None:
            return None
        out.append(name)
    return out


def _runs(line: str, rtl_paragraph: bool) -> list[tuple[str, str]] | None:
    """One line as drawn left to right: (text, font) runs, joined, in bidi order
    and mirrored; None when a letter cannot be joined or drawn."""
    shaped = rtl.shape(line)
    fonts = _fonts(shaped) if shaped is not None else None
    if fonts is None:
        return None
    runs: list[list[str]] = []
    for i, ch in rtl.display(shaped, rtl_paragraph):
        if runs and runs[-1][1] == fonts[i]:
            runs[-1][0] += ch
        else:
            runs.append([ch, fonts[i]])
    return [(text, name) for text, name in runs]


def _width(runs: list[tuple[str, str]]) -> float:
    return sum(_basic(name, TITLE_SIZE).getlength(text) for text, name in runs)


def title_lines(title: str) -> tuple[bool, list[list[tuple[str, str]]]] | None:
    """A title with right-to-left letters, laid out for the card: whether it reads
    right to left (its first letter, as `dir="auto"` decides on the page) and up
    to two lines of (text, font) runs left to right. None when it cannot be drawn."""
    text = " ".join(rtl.clean(title).split())
    rtl_paragraph = rtl.base_rtl(text)
    laid: dict[str, list[tuple[str, str]] | None] = {}

    def runs(line: str) -> list[tuple[str, str]] | None:
        if line not in laid:
            laid[line] = _runs(line, rtl_paragraph)
        return laid[line]

    if not text or runs(text) is None:
        return None
    def measure(line: str) -> float:
        laid_out = runs(line)
        return math.inf if laid_out is None else _width(laid_out)

    lines = [runs(line) for line in _wrap(text, W - 2 * PAD, 2, measure)]
    if not lines or any(line is None for line in lines):
        return None
    return rtl_paragraph, lines


def render(background: Image.Image | None, title: str) -> Image.Image:
    """The card as an image: the picture, the shade, the mark and the title."""
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
    pad = PAD
    mark = _mark(30)
    brand = _font("OpenSans-SemiBold.ttf", 28)
    y_brand = H - pad - mark.height
    img.paste(mark, (pad, y_brand), mark)
    d.text((pad + mark.width + 16, y_brand + mark.height / 2), page.DESIGNED_IN, font=brand, fill=FG, anchor="lm")

    head = _font(LATIN, TITLE_SIZE)
    if title and not rtl.needs_bidi(title):
        if drawable(title, head):
            lines = _wrap(title, W - 2 * pad, 2, lambda s: d.textlength(s, font=head))
            y = y_brand - 28 - LINE_PITCH * len(lines)
            for line in lines:
                d.text((pad, y), line, font=head, fill=TEXT)
                y += LINE_PITCH
    elif title and (laid := title_lines(title)):
        # The same band and baseline as a Latin title; right-aligned when the
        # title reads right to left.
        rtl_paragraph, lines = laid
        y = y_brand - 28 - LINE_PITCH * len(lines)
        baseline = head.getmetrics()[0]
        for runs in lines:
            x = W - pad - _width(runs) if rtl_paragraph else pad
            for text, name in runs:
                font = _basic(name, TITLE_SIZE)
                d.text((x, y + baseline), text, font=font, fill=TEXT, anchor="ls")
                x += font.getlength(text)
            y += LINE_PITCH
    return img


def compose(background: Image.Image | None, title: str) -> bytes:
    """The card as the JPEG stored at publish (shares/{share_id}/card.jpg)."""
    out = io.BytesIO()
    render(background, title).save(out, format="JPEG", quality=86, optimize=True)
    return out.getvalue()


def from_cover(data: bytes) -> bytes:
    """PF5b (share-bundle 1.1): the app's `cover` as the link-preview card. A
    1200 x 630 JPEG is served as it is, byte for byte (the app made it for
    previews, with its watermark when the plan has one); any other size is
    cropped to fill 1200 x 630, never stretched, and nothing is drawn on it."""
    with Image.open(io.BytesIO(data)) as img:
        if img.format == "JPEG" and img.size == (W, H):
            return data
        fitted = _cover(img.convert("RGB"))
    out = io.BytesIO()
    fitted.save(out, format="JPEG", quality=86, optimize=True)
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
