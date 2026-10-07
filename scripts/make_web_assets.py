"""Generate the website's brand assets from the Truebex brand masters.

    py -3.12 scripts/make_web_assets.py

Sources (the Unreal project owns the brand; this script only reads it):
    T:/unreal5_7_4_projects/truebex_compact/Brand/Truebex/logo/figma_original/*.svg
    T:/unreal5_7_4_projects/truebex_compact/Content/Brand/{Logo,Lockup}.png
    T:/unreal5_7_4_projects/truebex_compact/Content/Fonts/Segoe/*.ttf   (raster text only)
    T:/unreal5_7_4_projects/MultiWindow/Saved/CadTool/*.png             (in-app captures)

Writes (all committed):
    public/brand/*.svg                  mark / wordmark in brand grey and white (media kit)
    src/app/icon.svg                    favicon (dark tile + mark)
    src/app/apple-icon.png              180 px home-screen icon
    src/app/favicon.ico                 16/32/48 px
    public/icon-192.png, icon-512.png   web app manifest icons
    public/images/og-image.jpg          1200x630 social card
    public/images/product/*.jpg         cropped in-app captures (debug HUD removed)

Segoe UI is only rendered into images here; it is never shipped as a web font.
"""

import os
import re

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UE = "T:/unreal5_7_4_projects/truebex_compact"
SVG_SRC = f"{UE}/Brand/Truebex/logo/figma_original"
FONT_DIR = f"{UE}/Content/Fonts/Segoe"
SHOTS = "T:/unreal5_7_4_projects/MultiWindow/Saved/CadTool"

GROUND = (0x23, 0x23, 0x23)
PAGE = (0x16, 0x16, 0x16)
FG = (0xCB, 0xCB, 0xCB)
ACCENT = (0xA0, 0xCE, 0xFF)


def out(*parts: str) -> str:
    path = os.path.join(ROOT, *parts)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def svg_paths(name: str) -> tuple[str, list[str]]:
    text = open(os.path.join(SVG_SRC, name), encoding="utf-8").read()
    view_box = re.search(r'viewBox="([^"]+)"', text).group(1)
    return view_box, re.findall(r'<path d="([^"]+)"', text)


def write_svg(path: str, view_box: str, paths: list[str], fill: str) -> None:
    body = "".join(f'<path d="{d}" fill="{fill}"/>' for d in paths)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view_box}">{body}</svg>\n')


def media_kit() -> None:
    mark_vb, mark = svg_paths("Truebex_logo_v1.svg")
    word_vb, word = svg_paths("Truebex_name_v1.svg")
    for fill, tag in (("#CBCBCB", "grey"), ("#FFFFFF", "white"), ("#232323", "dark")):
        write_svg(out("public", "brand", f"truebex-mark-{tag}.svg"), mark_vb, mark, fill)
        write_svg(out("public", "brand", f"truebex-wordmark-{tag}.svg"), word_vb, word, fill)

    # Favicon: the app icon's look (dark rounded tile, grey mark), as SVG.
    body = "".join(f'<path d="{d}" fill="#CBCBCB"/>' for d in mark)
    with open(out("src", "app", "icon.svg"), "w", encoding="utf-8", newline="\n") as f:
        f.write(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
            '<rect width="64" height="64" rx="14" fill="#232323"/>'
            f'<g transform="translate(9 20.5) scale(1.3529)">{body}</g></svg>\n'
        )


def mark_image(width: int) -> Image.Image:
    """The grey glyph (Logo.png, 2:1) scaled to `width`, RGBA."""
    logo = Image.open(f"{UE}/Content/Brand/Logo.png").convert("RGBA")
    return logo.resize((width, width // 2), Image.LANCZOS)


def tile_icon(size: int, radius_ratio: float = 0.0) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    r = int(size * radius_ratio)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=r, fill=GROUND + (255,))
    mark = mark_image(int(size * 0.66))
    img.alpha_composite(mark, ((size - mark.width) // 2, (size - mark.height) // 2))
    return img


def icons() -> None:
    tile_icon(180).convert("RGB").save(out("src", "app", "apple-icon.png"))
    for s in (192, 512):
        tile_icon(s).convert("RGB").save(out("public", f"icon-{s}.png"))
    ico = tile_icon(256, 0.22)
    ico.save(out("src", "app", "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)])


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)


def grid(img: Image.Image, step: int, alpha: int) -> None:
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for x in range(0, img.width, step):
        d.line([(x, 0), (x, img.height)], fill=(255, 255, 255, alpha))
    for y in range(0, img.height, step):
        d.line([(0, y), (img.width, y)], fill=(255, 255, 255, alpha))
    img.alpha_composite(layer)


def crop_hud(path: str, top: int = 96) -> Image.Image:
    """Drop the debug HUD rows (FPS / status text) along the top edge."""
    im = Image.open(path).convert("RGB")
    return im.crop((0, top, im.width, im.height))


def product_shots() -> dict[str, Image.Image]:
    shots = {
        "rooms-area-labels": crop_hud(f"{SHOTS}/roomsdemo3d_living.png", 90),
        "first-person-walkthrough": crop_hud(f"{SHOTS}/face8F.png", 50),
        "wall-face-panels": crop_hud(f"{SHOTS}/island3d_reveal.png", 110),
    }
    for name, im in shots.items():
        w = 1200
        im.resize((w, round(im.height * w / im.width)), Image.LANCZOS).save(
            out("public", "images", "product", f"{name}.jpg"), quality=84, optimize=True, progressive=True
        )
    return shots


def og_image(shots: dict[str, Image.Image]) -> None:
    W, H = 1200, 630
    img = Image.new("RGBA", (W, H), PAGE + (255,))
    grid(img, 24, 6)
    grid(img, 120, 14)

    # Product capture on the right, fading into the page on its left edge.
    shot = shots["first-person-walkthrough"]
    sh = H
    sw = round(shot.width * sh / shot.height)
    shot = shot.resize((sw, sh), Image.LANCZOS).convert("RGBA")
    fade = Image.new("L", (sw, sh), 255)
    fd = ImageDraw.Draw(fade)
    ramp = 260
    for x in range(ramp):
        fd.line([(x, 0), (x, sh)], fill=int(255 * (x / ramp) ** 1.6))
    shot.putalpha(fade.point(lambda a: int(a * 0.9)))
    img.alpha_composite(shot, (W - sw + 140, 0))

    # Lockup, headline, sub-line on the left.
    lockup = Image.open(f"{UE}/Content/Brand/Lockup.png").convert("RGBA")
    lw = 420
    lockup = lockup.resize((lw, round(lockup.height * lw / lockup.width)), Image.LANCZOS)
    img.alpha_composite(lockup, (72, 92))

    d = ImageDraw.Draw(img)
    d.text((72, 210), "See it before", font=font("Segoe UI Bold.ttf", 66), fill=(237, 237, 237))
    d.text((72, 286), "you build it.", font=font("Segoe UI Bold.ttf", 66), fill=ACCENT)
    d.text(
        (72, 392),
        "Real-time 2D + 3D building design.\nLumen light, first-person walkthroughs,\nand live areas on Unreal Engine 5.7.",
        font=font("Segoe UI.ttf", 28),
        fill=(168, 168, 168),
        spacing=10,
    )
    d.text((72, 556), "truebex.com", font=font("Segoe UI Bold.ttf", 24), fill=FG)
    img.convert("RGB").save(out("public", "images", "og-image.jpg"), quality=88, optimize=True)


if __name__ == "__main__":
    media_kit()
    icons()
    og_image(product_shots())
    print("brand assets written")
