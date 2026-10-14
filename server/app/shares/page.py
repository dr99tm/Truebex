"""The HTML of a share link (PF5): `GET /view/{slug}` writes this share's own
link-preview tags around the static viewer shell, which loads
`${SITE_URL}/viewer/viewer.js` (built from src/viewer/). A crawler never runs
the script, so the tags are what a preview shows; `noindex` keeps the page
out of search while robots.txt lets preview crawlers in.

Rendered with `string.Template`; every value is HTML-escaped.
"""

import html
import math
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from string import Template
from urllib.parse import urlsplit

# Copy mirrored from SHARE_PAGE in src/lib/constants.ts (the brand-voice
# source); tests/test_site_pf5.py fails when the two drift.
DESIGNED_IN = "Designed in Truebex"
GET_TRUEBEX = "Get Truebex for Windows"
OG_TITLE_SUFFIX = " — designed in Truebex"
ENDED_TITLE = "This link has ended"
ENDED_TEXT = "The designer ended this share, or it reached its expiry date. Ask them for a new link."
NOT_FOUND_TITLE = "We can't find this share"
NOT_FOUND_TEXT = "Check the link you were sent, or ask the designer for a new one."
DOWNLOAD_PDF = "Download PDF"
# PF5b: the project card's words, mirrored from SHARE_PROJECT_CARD
# (tests/test_shares_pf5b.py fails when the two drift).
PROJECT_CARD = {
    "storey": "storey",
    "storeys": "storeys",
    "room": "room",
    "rooms": "rooms",
    "squareMetres": "m²",
    "squareFeet": "ft²",
}
SQ_FT_PER_M2 = 10.763910416709722

_TEMPLATES = Path(__file__).with_name("templates")
_VIEW = Template((_TEMPLATES / "view.html").read_text(encoding="utf-8"))
_ENDED = Template((_TEMPLATES / "ended.html").read_text(encoding="utf-8"))


def _e(value: object) -> str:
    return html.escape(str(value), quote=True)


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def description(m: dict) -> str:
    """'3 panoramas, 1 render and the drawings.' (at most 160 characters)."""
    parts = []
    panos, renders = len(m.get("panoramas") or []), len(m.get("renders") or [])
    if panos:
        parts.append(_plural(panos, "panorama", "panoramas"))
    if renders:
        parts.append(_plural(renders, "render", "renders"))
    if m.get("sheets"):
        parts.append("the drawings")
    if not parts:
        return DESIGNED_IN + "."
    text = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
    return (text[0].upper() + text[1:] + ".")[:160]


def og_title(title: str) -> str:
    return title + OG_TITLE_SUFFIX


def _count(value: object) -> int | None:
    """A positive whole number from the manifest, else None (never shown)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return int(value) if value >= 1 and value == int(value) else None


def _decimals(value: float, places: int) -> str:
    """At most `places` decimals, rounded half away from zero on the number's
    shortest decimal form (as the viewer's Intl.NumberFormat does: 72.755 ->
    72.76), with thousands separators: 1234.5678 -> '1,234.57'."""
    shortest = Decimal(repr(float(value)))
    text = f"{shortest.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP):,f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def project_line(m: dict) -> str | None:
    """The project card (share-bundle 1.1 `project.storeys`, `rooms`,
    `floor_area_m2`): '1 storey · 3 rooms · 72.75 m²', the area in the
    manifest's units (ft², whole, when `imperial`). None without any of them,
    so a 1.0 manifest renders as before. src/viewer/project.ts writes the same."""
    project = m.get("project") if isinstance(m.get("project"), dict) else {}
    words = PROJECT_CARD
    parts = []
    storeys, rooms = _count(project.get("storeys")), _count(project.get("rooms"))
    if storeys:
        parts.append(f"{storeys:,} {words['storey'] if storeys == 1 else words['storeys']}")
    if rooms:
        parts.append(f"{rooms:,} {words['room'] if rooms == 1 else words['rooms']}")
    area = project.get("floor_area_m2")
    if not isinstance(area, bool) and isinstance(area, (int, float)) and math.isfinite(area) and area > 0:
        if project.get("units") == "imperial":
            parts.append(f"{_decimals(area * SQ_FT_PER_M2, 0)} {words['squareFeet']}")
        else:
            parts.append(f"{_decimals(area, 2)} {words['squareMetres']}")
    return " · ".join(parts) if parts else None


def origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else ""


def csp(site_url: str, files_url: str, tiles_url: str = "") -> str:
    """The share page runs only the viewer from the site; files come from storage
    (and a live panorama's tiles from TILES_BASE_URL, PF6)."""
    site, files = origin(site_url), origin(files_url)
    hosts = " ".join(dict.fromkeys(h for h in (site, files) if h))
    images = " ".join(dict.fromkeys(h for h in (site, files, origin(tiles_url)) if h))
    return "; ".join(
        [
            "default-src 'none'",
            f"script-src {site}",
            f"style-src {site} 'unsafe-inline'",
            f"img-src 'self' {images} data: blob:",
            f"connect-src 'self' {hosts}",
            f"worker-src {site} blob:",
            f"font-src {site} data:",
            "base-uri 'none'",
            "form-action 'none'",
            "frame-ancestors 'none'",
        ]
    )


def render_view(
    *,
    title: str,
    m: dict,
    url: str,
    slug: str,
    api: str,
    site: str,
    card_url: str,
    preload_url: str | None,
    first_render_url: str | None,
    pdf_url: str | None,
) -> str:
    """`card_url` is the cover or PF5's card (with `?v=` after an Update);
    a 1.1 project card adds one line under the title. A 1.0 manifest renders
    exactly as PF5 wrote it."""
    preload = (
        f'<link rel="preload" as="image" href="{_e(preload_url)}" crossorigin="anonymous" fetchpriority="high">' if preload_url else ""
    )
    noscript = []
    if line := project_line(m):
        noscript.append(f'<p class="tbx-project">{_e(line)}</p>')
    if first_render_url:
        noscript.append(f'<img src="{_e(first_render_url)}" alt="{_e(title)}" width="640">')
    if pdf_url:
        noscript.append(f'<p><a href="{_e(pdf_url)}">{_e(DOWNLOAD_PDF)}</a></p>')
    return _VIEW.substitute(
        title=_e(og_title(title)),
        heading=_e(title),
        og_title=_e(og_title(title)),
        description=_e(description(m)),
        url=_e(url),
        image=_e(card_url),
        image_alt=_e(og_title(title)),
        preload=preload,
        site=_e(site),
        slug=_e(slug),
        api=_e(api),
        noscript="\n    ".join(noscript),
        designed_in=_e(DESIGNED_IN),
        get_truebex=_e(GET_TRUEBEX),
    )


def render_ended(*, site: str, gone: bool) -> str:
    heading, text = (ENDED_TITLE, ENDED_TEXT) if gone else (NOT_FOUND_TITLE, NOT_FOUND_TEXT)
    return _ENDED.substitute(
        title=_e(f"{heading} · Truebex"),
        heading=_e(heading),
        text=_e(text),
        site=_e(site),
        designed_in=_e(DESIGNED_IN),
        get_truebex=_e(GET_TRUEBEX),
    )
