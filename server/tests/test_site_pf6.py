"""PF6 build checks: read out/ after the verify gate's `npm run build`
(skipped when out/ is absent, e.g. a server-only test run)."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"

pytestmark = pytest.mark.skipif(
    not (OUT / "index.html").exists(), reason="out/ not built (run npm run build)"
)


def _page(route: str) -> str:
    return (OUT / route / "index.html").read_text("utf-8")


def _noindex(html: str) -> bool:
    return bool(re.search(r'<meta name="robots" content="[^"]*noindex', html))


def test_site_pf6_cloud_pages_noindex():
    for route in ("dashboard/cloud", "dashboard/admin/render"):
        assert (OUT / route / "index.html").is_file(), route
        assert _noindex(_page(route)), route


def test_site_pf6_pages_not_in_sitemap_and_nav_has_cloud():
    sitemap = (OUT / "sitemap.xml").read_text("utf-8")
    assert "/dashboard/cloud" not in sitemap and "/dashboard/admin" not in sitemap
    shell = (ROOT / "src" / "components" / "dashboard" / "DashboardShell.tsx").read_text("utf-8")
    assert '"/dashboard/cloud/"' in shell and '"/dashboard/admin/render/"' in shell


def test_site_pf6_cloud_panoramas_stay_on_the_roadmap():
    # Cloud panoramas ship with the app's headless render (CL3, CL4): the
    # public copy keeps them on the roadmap (brand voice: only shipped
    # features in FEATURES).
    constants = (ROOT / "src" / "lib" / "constants.ts").read_text("utf-8")
    features = constants.split("export const FEATURES", 1)[1].split("export const", 1)[0]
    assert "cloud" not in features.lower() and "panorama" not in features.lower()


def test_site_pf6_viewer_modules_are_framework_free():
    for name in ("cube.ts", "live.ts"):
        text = (ROOT / "src" / "viewer" / name).read_text("utf-8")
        assert "from \"react\"" not in text and "@/" not in text, name
