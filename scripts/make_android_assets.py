"""Generate the Android app's brand assets (PF10) from the Truebex brand masters,
with the helpers of scripts/make_web_assets.py.

    py -3.12 scripts/make_android_assets.py              icons, the lockup, the store icon
    py -3.12 scripts/make_android_assets.py --store <captures>
                                                         also the store screenshots (from phone
                                                         captures, PNG) and the feature graphic

Writes (all committed):
    mobile/android/android/app/src/main/res/mipmap-*/ic_launcher.png      48-192 px legacy icons
    mobile/android/android/app/src/main/res/mipmap-*/ic_launcher_foreground.png
                                        adaptive icon foreground (108 dp, the mark in the 66 dp safe zone)
    mobile/android/android/app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml
    mobile/android/android/app/src/main/res/values/ic_launcher_background.xml
    mobile/android/android/app/src/main/res/drawable-*/ic_stat_truebex.png  the notification icon (white mark)
    mobile/android/android/app/src/main/res/raw/keep.xml                    keeps it when resources are shrunk
    mobile/android/assets/brand/lockup.png  the glyph + wordmark for the sign-in screen
    mobile/android/store/icon-512.png       the Play listing icon (full square; Play masks it)
    mobile/android/store/screenshots/*.png  portrait phone screenshots, at most 2:1 (with --store)
    mobile/android/store/feature-graphic-1024x500.png                       (with --store)

The wordmark is never retyped in a font: the lockup image is the brand's own.
"""

import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_web_assets import ACCENT, FG, GROUND, PAGE, UE, font, grid, mark_image, maskable_icon, tile_icon  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "mobile", "android")
RES = os.path.join(APP, "android", "app", "src", "main", "res")
STORE = os.path.join(APP, "store")
DENSITIES = {"mdpi": 1.0, "hdpi": 1.5, "xhdpi": 2.0, "xxhdpi": 3.0, "xxxhdpi": 4.0}


def path(*parts: str) -> str:
    p = os.path.join(*parts)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def adaptive_foreground(size: int) -> Image.Image:
    """108 dp canvas; launchers show the inner 72 dp and keep 66 dp safe: the mark spans 54 %."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    mark = mark_image(int(size * 0.54))
    img.alpha_composite(mark, ((size - mark.width) // 2, (size - mark.height) // 2))
    return img


def launcher_icons() -> None:
    for name, scale in DENSITIES.items():
        legacy = tile_icon(round(48 * scale), 0.18)
        legacy.save(path(RES, f"mipmap-{name}", "ic_launcher.png"))
        adaptive_foreground(round(108 * scale)).save(path(RES, f"mipmap-{name}", "ic_launcher_foreground.png"))
    with open(path(RES, "mipmap-anydpi-v26", "ic_launcher.xml"), "w", encoding="utf-8", newline="\n") as f:
        f.write(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
            '    <background android:drawable="@color/ic_launcher_background" />\n'
            '    <foreground android:drawable="@mipmap/ic_launcher_foreground" />\n'
            '    <monochrome android:drawable="@mipmap/ic_launcher_foreground" />\n'
            "</adaptive-icon>\n"
        )
    with open(path(RES, "values", "ic_launcher_background.xml"), "w", encoding="utf-8", newline="\n") as f:
        f.write(
            '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'
            '    <color name="ic_launcher_background">#232323</color>\n</resources>\n'
        )


def status_icon() -> None:
    """24 dp, white on transparent: Android tints status-bar icons by their alpha only."""
    for name, scale in DENSITIES.items():
        size = round(24 * scale)
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        mark = mark_image(round(22 * scale))
        white = Image.new("RGBA", mark.size, (255, 255, 255, 0))
        white.putalpha(mark.getchannel("A"))
        img.alpha_composite(white, ((size - white.width) // 2, (size - white.height) // 2))
        img.save(path(RES, f"drawable-{name}", "ic_stat_truebex.png"))
    with open(path(RES, "raw", "keep.xml"), "w", encoding="utf-8", newline="\n") as f:
        f.write(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            "<!-- The notification icon is named from Dart only (lib/sync/background.dart). -->\n"
            '<resources xmlns:tools="http://schemas.android.com/tools" tools:keep="@drawable/ic_stat_truebex" />\n'
        )


def lockup() -> None:
    img = Image.open(f"{UE}/Content/Brand/Lockup.png").convert("RGBA")
    w = 720
    img.resize((w, round(img.height * w / img.width)), Image.LANCZOS).save(path(APP, "assets", "brand", "lockup.png"))


def store_icon() -> None:
    maskable_icon(512).convert("RGB").save(path(STORE, "icon-512.png"))


def screenshots(captures: str) -> list[str]:
    """Phone captures (1080 x 2400) to Play's rule of at most 2:1: the status bar and the
    gesture bar are cut, then the frame is cut to 1080 x 2160 from the top."""
    out = []
    names = sorted(n for n in os.listdir(captures) if n.lower().endswith(".png"))
    for i, name in enumerate(names, 1):
        img = Image.open(os.path.join(captures, name)).convert("RGB")
        w, h = img.size
        top = round(h * 0.03)
        img = img.crop((0, top, w, min(h, top + 2 * w)))
        stem = os.path.splitext(name)[0]
        stem = stem.split("-", 1)[1] if stem[:1].isdigit() and "-" in stem else stem  # "1-panorama" -> "panorama"
        target = path(STORE, "screenshots", f"{i:02d}-{stem}.png")
        img.save(target, optimize=True)
        out.append(target)
    return out


def feature_graphic(shots: list[str]) -> None:
    W, H = 1024, 500
    img = Image.new("RGBA", (W, H), PAGE + (255,))
    grid(img, 24, 6)
    grid(img, 120, 14)
    # The panorama screen, in a phone-shaped frame on the right.
    if shots:
        shot = Image.open(shots[0]).convert("RGBA")
        sh = H - 60
        sw = round(shot.width * sh / shot.height)
        shot = shot.resize((sw, sh), Image.LANCZOS)
        frame = Image.new("RGBA", (sw + 16, sh + 16), (0, 0, 0, 0))
        ImageDraw.Draw(frame).rounded_rectangle((0, 0, sw + 15, sh + 15), radius=26, fill=GROUND + (255,))
        mask = Image.new("L", (sw, sh), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, sw - 1, sh - 1), radius=20, fill=255)
        frame.paste(shot, (8, 8), mask)
        img.alpha_composite(frame, (W - sw - 16 - 56, 22))
    lock = Image.open(f"{UE}/Content/Brand/Lockup.png").convert("RGBA")
    lw = 300
    lock = lock.resize((lw, round(lock.height * lw / lock.width)), Image.LANCZOS)
    img.alpha_composite(lock, (56, 70))
    d = ImageDraw.Draw(img)
    d.text((56, 170), "Your projects,", font=font("Segoe UI Bold.ttf", 46), fill=(237, 237, 237))
    d.text((56, 226), "on your phone.", font=font("Segoe UI Bold.ttf", 46), fill=ACCENT)
    d.text(
        (56, 314),
        "Walk the panoramas, change a finish,\nswap a product. Online or not.",
        font=font("Segoe UI.ttf", 24),
        fill=(168, 168, 168),
        spacing=8,
    )
    d.text((56, 420), "truebex.com", font=font("Segoe UI Bold.ttf", 20), fill=FG)
    img.convert("RGB").save(path(STORE, "feature-graphic-1024x500.png"), optimize=True)


if __name__ == "__main__":
    launcher_icons()
    status_icon()
    lockup()
    store_icon()
    if "--store" in sys.argv:
        shots = screenshots(sys.argv[sys.argv.index("--store") + 1])
        feature_graphic(shots)
        print(f"store assets written ({len(shots)} screenshots)")
    print("android assets written")
