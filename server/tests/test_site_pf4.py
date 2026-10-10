"""PF4 build checks: read out/ after the verify gate's `npm run build`
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


def test_site_pf4_project_pages_noindex():
    for route in ("dashboard/projects", "dashboard/projects/view", "invite/project"):
        assert (OUT / route / "index.html").is_file(), route
        assert _noindex(_page(route)), route


def test_site_pf4_invite_page_static_text_and_one_h1():
    html = _page("invite/project")
    assert len(re.findall(r"<h1[\s>]", html)) == 1
    assert "Join a shared project" in html
    assert "The link works once" in html


def test_site_pf4_invite_titles_keep_the_site_suffix():
    # /invite/project/ sits under PF3's /invite/ layout: that layout must pass
    # the root "%s · Truebex" template on, not end it with a plain title.
    for route, title in (("invite", "Join an organisation"), ("invite/project", "Join a shared project")):
        assert f"<title>{title} · Truebex</title>" in _page(route), route


def test_site_pf4_pages_not_in_sitemap_and_nav_has_projects():
    sitemap = (OUT / "sitemap.xml").read_text("utf-8")
    assert "/dashboard/projects" not in sitemap and "/invite/" not in sitemap
    shell = (ROOT / "src" / "components" / "dashboard" / "DashboardShell.tsx").read_text("utf-8")
    assert '"/dashboard/projects/"' in shell


def test_site_pf4_cloud_projects_stay_on_the_roadmap():
    # Cloud projects ship in the app with CL1: the public copy keeps them on
    # the roadmap (brand voice: only shipped features in FEATURES).
    constants = (ROOT / "src" / "lib" / "constants.ts").read_text("utf-8")
    features = constants.split("export const FEATURES", 1)[1].split("export const", 1)[0]
    assert "cloud project" not in features.lower() and "several people" not in features.lower()
