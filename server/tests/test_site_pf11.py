"""PF11 build checks: read out/ after the verify gate's `npm run build`
(skipped when out/ is absent, e.g. a server-only test run)."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
CONSTANTS = ROOT / "src" / "lib" / "constants.ts"

pytestmark = pytest.mark.skipif(
    not (OUT / "index.html").exists(), reason="out/ not built (run npm run build)"
)


def _page(route: str) -> str:
    return (OUT / route / "index.html").read_text("utf-8")


def _noindex(html: str) -> bool:
    return bool(re.search(r'<meta name="robots" content="[^"]*noindex', html))


def _export(name: str) -> str:
    """The source of one `export const NAME = …` block in constants.ts."""
    text = CONSTANTS.read_text("utf-8")
    assert f"export const {name}" in text, name
    return text.split(f"export const {name}", 1)[1].split("export const", 1)[0]


def _title(name: str) -> str:
    match = re.search(r'^\s*title:\s*"([^"]+)"', _export(name), re.M)
    assert match, f"{name}.title"
    return match.group(1)


def _chunks() -> list[str]:
    files = sorted((OUT / "_next").rglob("*.js"))
    assert files, "no JS chunks under out/_next"
    return [f.read_text("utf-8", errors="replace") for f in files]


def test_site_pf11_ai_pages_noindex():
    for route in ("dashboard/cloud", "dashboard/admin/render"):
        assert (OUT / route / "index.html").is_file(), route
        assert _noindex(_page(route)), route


def test_site_pf11_ai_section_and_admin_panel_are_built():
    chunks = _chunks()
    for name in ("CLOUD_AI", "ADMIN_AI"):
        title = _title(name)
        assert any(title in c for c in chunks), f"{name}.title {title!r} not in any chunk"
    # The analysis kinds have labels on the Cloud page and the render admin.
    for label in ("Acoustics study", "Material textures"):
        assert label in _export("CLOUD_AI"), label
        assert any(label in c for c in chunks), label


def test_site_pf11_ai_credits_and_analysis_stay_off_features():
    # The assistant, AI credits and the analysis reports aren't shipped app
    # features yet (brand voice: only shipped features in FEATURES).
    features = _export("FEATURES")
    lowered = features.lower()
    for word in ("credit", "analysis", "acoustic", "assistant"):
        assert word not in lowered, word
    assert not re.search(r"\bAI\b", features)
