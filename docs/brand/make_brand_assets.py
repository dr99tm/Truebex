"""Render every social-media image from this folder's brand sources.

    py -3.12 docs/brand/make_brand_assets.py           (write export/)
    py -3.12 docs/brand/make_brand_assets.py --check   (does the website still match?)

Sources (edit these to change the brand):
    brand.json                 name, slogan, colours, fonts, logo spacing
    logo/truebex-mark.svg      the T/J glyph (any fill; the colour comes from brand.json)
    logo/truebex-wordmark.svg  the "Truebex" wordmark
    images/daylight-doorway.png  the clean in-app capture used on banners
    fonts/                     Open Sans (fallback when Segoe UI is not installed)

Writes export/ (all committed; upload from there):
    svg/truebex-{mark,wordmark,lockup}-{grey,white,dark}.svg
    avatar.png                 1080 x 1080, every platform's profile picture
    facebook-cover.png         1640 x 624
    linkedin-cover.png         1128 x 191
    x-header.png               1500 x 500
    youtube-banner.png         2560 x 1440 (text inside the 1546 x 423 safe area)
    reddit-banner.png          1920 x 384
    youtube-watermark.png      150 x 150, transparent
    lockup-dark.png            2000 x 1066, the lockup on the ground (as the Figma master)
    lockup-grey.png, lockup-white.png  2000 px wide, transparent
    mark-dark.png              800 x 800, the mark on the ground (as the Figma master)

Paths are drawn by this script (no cairo needed): M L H V C Z, absolute only,
which is all the Figma exports use. Segoe UI is only rendered into images; it
is never copied into this folder.
"""

import json
import os
import re
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BRAND = json.load(open(os.path.join(HERE, "brand.json"), encoding="utf-8"))
COLORS = BRAND["colors"]
SS = 4  # supersampling for the logo shapes


def rgb(name: str) -> tuple[int, int, int]:
    h = COLORS[name].lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def out(*parts: str) -> str:
    path = os.path.join(HERE, "export", *parts)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


# ---------------------------------------------------------------- logo shapes


def read_svg(rel: str) -> tuple[float, float, list[str]]:
    text = open(os.path.join(HERE, rel), encoding="utf-8").read()
    _, _, w, h = (float(v) for v in re.search(r'viewBox="([^"]+)"', text).group(1).split())
    return w, h, re.findall(r'<path d="([^"]+)"', text)


MARK = read_svg(BRAND["logo"]["mark"])
WORD = read_svg(BRAND["logo"]["wordmark"])


def subpaths(d: str) -> list[list[tuple[float, float]]]:
    """Flatten one path into closed polygons (cubics at 16 steps)."""
    tokens = re.findall(r"[MLHVCZ]|-?\d*\.?\d+(?:e-?\d+)?", d)
    polys, cur, x, y, cmd, i = [], [], 0.0, 0.0, "", 0
    while i < len(tokens):
        if tokens[i] in "MLHVCZ":
            cmd = tokens[i]
            i += 1
            if cmd == "Z":
                if cur:
                    polys.append(cur)
                cur = []
                continue
        n = lambda k: float(tokens[i + k])  # noqa: E731
        if cmd == "M":
            if cur:
                polys.append(cur)
            x, y = n(0), n(1)
            cur = [(x, y)]
            i += 2
            cmd = "L"
        elif cmd == "L":
            x, y = n(0), n(1)
            cur.append((x, y))
            i += 2
        elif cmd == "H":
            x = n(0)
            cur.append((x, y))
            i += 1
        elif cmd == "V":
            y = n(0)
            cur.append((x, y))
            i += 1
        elif cmd == "C":
            x1, y1, x2, y2, x3, y3 = (n(k) for k in range(6))
            for s in range(1, 17):
                t = s / 16
                u = 1 - t
                cur.append(
                    (
                        u**3 * x + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t**3 * x3,
                        u**3 * y + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t**3 * y3,
                    )
                )
            x, y = x3, y3
            i += 6
        else:
            raise ValueError(f"unsupported path command {cmd!r}")
    if cur:
        polys.append(cur)
    return polys


def lockup_parts() -> tuple[float, float, list[tuple[list[str], float, float]]]:
    """(width, height, [(paths, dx, dy)]) in SVG units: the mark sits on the
    wordmark's baseline (the T's foot), as in the Figma lockup."""
    mw, mh, mark = MARK
    ww, wh, word = WORD
    gap = BRAND["logo"]["lockup_gap"]
    baseline = 17.7656  # foot of the wordmark's T
    return mw + gap + ww, wh, [(mark, 0.0, baseline - mh), (word, mw + gap, 0.0)]


def shape(kind: str) -> tuple[float, float, list[tuple[list[str], float, float]]]:
    if kind == "mark":
        return MARK[0], MARK[1], [(MARK[2], 0.0, 0.0)]
    if kind == "wordmark":
        return WORD[0], WORD[1], [(WORD[2], 0.0, 0.0)]
    return lockup_parts()


def logo(kind: str, width: int, color: tuple[int, int, int]) -> Image.Image:
    """The mark, wordmark or lockup `width` px wide, RGBA on transparent."""
    w, h, parts = shape(kind)
    scale = width * SS / w
    size = (width * SS, max(1, round(h * scale)))
    mask = Image.new("L", size, 0)
    for paths, dx, dy in parts:
        for d in paths:
            for poly in subpaths(d):  # even-odd: each ring flips coverage
                ring = Image.new("L", size, 0)
                ImageDraw.Draw(ring).polygon([((px + dx) * scale, (py + dy) * scale) for px, py in poly], fill=255)
                mask = ImageChops.logical_xor(mask.convert("1"), ring.convert("1")).convert("L")
    mask = mask.resize((width, max(1, round(size[1] / SS))), Image.LANCZOS)
    img = Image.new("RGBA", mask.size, color + (255,))
    img.putalpha(mask)
    return img


def write_svgs() -> None:
    for kind in ("mark", "wordmark", "lockup"):
        w, h, parts = shape(kind)
        for tag, fill in (("grey", COLORS["logo"]), ("white", "#FFFFFF"), ("dark", COLORS["ground"])):
            body = ""
            for paths, dx, dy in parts:
                group = "".join(f'<path d="{d}" fill="{fill}"/>' for d in paths)
                body += f'<g transform="translate({dx:g} {dy:g})">{group}</g>' if (dx or dy) else group
            with open(out("svg", f"truebex-{kind}-{tag}.svg"), "w", encoding="utf-8", newline="\n") as f:
                f.write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:g} {h:g}">{body}</svg>\n')


# ---------------------------------------------------------------- text


def font(bold: bool, size: int) -> ImageFont.FreeTypeFont:
    primary = BRAND["fonts"]["primary"]
    path = primary["bold" if bold else "regular"]
    if os.path.exists(path):
        return ImageFont.truetype(path, size)
    f = ImageFont.truetype(os.path.join(HERE, BRAND["fonts"]["fallback"]["file"]), size)
    f.set_variation_by_axes([100, 700 if bold else 400])  # wdth, wght
    return f


# ---------------------------------------------------------------- images


def ground(size: tuple[int, int], unit: float) -> Image.Image:
    """The ground with the drafting grid (24 / 120 px at the site's scale)."""
    img = Image.new("RGBA", size, rgb("ground") + (255,))
    for step, alpha in ((24 * unit, 6), (120 * unit, 14)):
        layer = Image.new("RGBA", size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        x = 0.0
        while x < size[0]:
            d.line([(round(x), 0), (round(x), size[1])], fill=(255, 255, 255, alpha))
            x += step
        y = 0.0
        while y < size[1]:
            d.line([(0, round(y)), (size[0], round(y))], fill=(255, 255, 255, alpha))
            y += step
        img.alpha_composite(layer)
    return img


def capture_into(img: Image.Image, left: int) -> None:
    """Cover the canvas right of `left` with the capture, fading in from the left."""
    W, H = img.size
    bw = W - left
    shot = Image.open(os.path.join(HERE, BRAND["capture"])).convert("RGBA")
    s = max(bw / shot.width, H / shot.height)
    shot = shot.resize((round(shot.width * s), round(shot.height * s)), Image.LANCZOS)
    ox, oy = (shot.width - bw) // 2, round((shot.height - H) * 0.45)
    shot = shot.crop((ox, oy, ox + bw, oy + H))
    fade = Image.new("L", shot.size, 255)
    fd = ImageDraw.Draw(fade)
    ramp = max(1, round(bw * 0.45))
    for x in range(ramp):
        fd.line([(x, 0), (x, H)], fill=int(255 * (x / ramp) ** 1.6))
    shot.putalpha(fade.point(lambda a: int(a * 0.9)))
    img.alpha_composite(shot, (left, 0))


def banner(name: str, size: tuple[int, int], safe: tuple[int, int, int, int], one_line: bool = False) -> None:
    """The lockup over the slogan in the left half of the safe area, the
    capture on the right. `safe` is what every device shows (x0, y0, x1, y1)."""
    W, H = size
    x0, y0, x1, y1 = safe
    sw, sh = x1 - x0, y1 - y0
    img = ground(size, sh / 360)
    capture_into(img, x0 + round(sw * 0.5))

    first, second = BRAND["slogan"]
    lines = [first + " " + second] if one_line else [first, second]
    max_w, max_h = sw * (0.62 if one_line else 0.46), sh * 0.8
    fs = round(sh * 0.3)
    while True:
        f = font(True, fs)
        lock_h = 0.62 * fs
        block_h = lock_h + 0.55 * fs + len(lines) * 1.18 * fs
        if (max(f.getlength(t) for t in lines) <= max_w and block_h <= max_h) or fs <= 8:
            break
        fs -= 1

    top = y0 + (sh - block_h) / 2
    lock = logo("lockup", round(lock_h * lockup_parts()[0] / lockup_parts()[1]), rgb("logo"))
    img.alpha_composite(lock, (x0, round(top)))
    d = ImageDraw.Draw(img)
    y = top + lock_h + 0.55 * fs
    if one_line:
        d.text((x0, y), first, font=f, fill=rgb("text_primary"))
        d.text((x0 + f.getlength(first + " "), y), second, font=f, fill=rgb("accent"))
    else:
        d.text((x0, y), first, font=f, fill=rgb("text_primary"))
        d.text((x0, y + 1.18 * fs), second, font=f, fill=rgb("accent"))
    img.convert("RGB").save(out(name), optimize=True)


def centred(name: str, size: tuple[int, int], kind: str, width: int, color, bg) -> None:
    img = Image.new("RGBA", size, bg)
    mark = logo(kind, width, color)
    img.alpha_composite(mark, ((size[0] - mark.width) // 2, (size[1] - mark.height) // 2))
    (img if bg[3] < 255 else img.convert("RGB")).save(out(name), optimize=True)


def write_images() -> None:
    g = rgb("ground") + (255,)
    clear = (0, 0, 0, 0)
    share = BRAND["logo"]["avatar_mark_width"]
    centred("avatar.png", (1080, 1080), "mark", round(1080 * share), rgb("logo"), g)
    centred("mark-dark.png", (800, 800), "mark", round(800 * share), rgb("logo"), g)
    centred("lockup-dark.png", (2000, 1066), "lockup", 1051, rgb("logo"), g)
    centred("youtube-watermark.png", (150, 150), "mark", 136, rgb("logo"), clear)
    for tag, color in (("grey", rgb("logo")), ("white", (255, 255, 255))):
        logo("lockup", 2000, color).save(out(f"lockup-{tag}.png"), optimize=True)

    banner("youtube-banner.png", (2560, 1440), (507, 508, 2053, 931))
    banner("facebook-cover.png", (1640, 624), (180, 96, 1460, 528))
    banner("x-header.png", (1500, 500), (300, 80, 1440, 420))
    banner("linkedin-cover.png", (1128, 191), (240, 24, 1100, 167), one_line=True)
    banner("reddit-banner.png", (1920, 384), (320, 64, 1800, 320), one_line=True)


# ---------------------------------------------------------------- website check


def check() -> int:
    """List where the website no longer matches this folder."""
    drift = []
    css = open(os.path.join(ROOT, "src", "app", "globals.css"), encoding="utf-8").read().lower()
    for token, var in (
        ("ground", "--color-brand-ground"),
        ("logo", "--color-brand-fg"),
        ("accent", "--color-accent"),
        ("accent_strong", "--color-accent-strong"),
        ("warn", "--color-warn"),
        ("page", "--color-background"),
        ("text_primary", "--color-text-primary"),
        ("text_secondary", "--color-text-secondary"),
    ):
        m = re.search(rf"{var}:\s*(#[0-9a-f]+)", css)
        if not m or m.group(1) != COLORS[token].lower():
            drift.append(f"src/app/globals.css {var}: {m and m.group(1)} (brand.json {token}: {COLORS[token]})")
    for kind, src in (("mark", MARK), ("wordmark", WORD)):
        site = open(os.path.join(ROOT, "public", "brand", f"truebex-{kind}-grey.svg"), encoding="utf-8").read()
        if re.findall(r'<path d="([^"]+)"', site) != src[2]:
            drift.append(f"public/brand/truebex-{kind}-*.svg and src/components/brand/Logo.tsx: {kind} paths differ")
    consts = open(os.path.join(ROOT, "src", "lib", "constants.ts"), encoding="utf-8").read()
    if f'slogan: "{" ".join(BRAND["slogan"])}"' not in consts:
        drift.append("src/lib/constants.ts SITE.slogan differs from brand.json slogan")
    for line in drift:
        print("drift:", line)
    print("website matches docs/brand" if not drift else f"{len(drift)} difference(s)")
    return 1 if drift else 0


if __name__ == "__main__":
    if "--check" in sys.argv:
        sys.exit(check())
    write_svgs()
    write_images()
    print("export/ written")
