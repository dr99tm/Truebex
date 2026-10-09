"""The HTML of a share link (PF5): `GET /view/{slug}` writes this share's own
link-preview tags around the static viewer shell, which loads
`${SITE_URL}/viewer/viewer.js` (built from src/viewer/). A crawler never runs
the script, so the tags are what a preview shows; `noindex` keeps the page
out of search while robots.txt lets preview crawlers in.

Rendered with `string.Template`; every value is HTML-escaped.
"""

import html
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


def origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else ""


def csp(site_url: str, files_url: str) -> str:
    """The share page runs only the viewer from the site; files come from storage."""
    site, files = origin(site_url), origin(files_url)
    hosts = " ".join(dict.fromkeys(h for h in (site, files) if h))
    return "; ".join(
        [
            "default-src 'none'",
            f"script-src {site}",
            f"style-src {site} 'unsafe-inline'",
            f"img-src 'self' {hosts} data: blob:",
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
    preload = (
        f'<link rel="preload" as="image" href="{_e(preload_url)}" crossorigin="anonymous" fetchpriority="high">' if preload_url else ""
    )
    noscript = []
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
        image_alt=_e(f"{title}, {DESIGNED_IN.lower()}"),
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
