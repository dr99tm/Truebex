"""PF14 build checks: read out/ after the verify gate's `npm run build`
(skipped when out/ is absent, e.g. a server-only test run)."""

from pathlib import Path

import pytest

OUT = Path(__file__).resolve().parents[2] / "out"

pytestmark = pytest.mark.skipif(
    not (OUT / "index.html").exists(), reason="out/ not built (run npm run build)"
)


def _page(route: str) -> str:
    return (OUT / route / "index.html").read_text("utf-8")


def test_site_pf14_admin_telemetry_noindex():
    html = _page("dashboard/admin/telemetry")
    assert 'name="robots"' in html and "noindex" in html
    assert "Telemetry" in html


def test_site_pf14_privacy_mentions_telemetry():
    html = _page("privacy")
    assert "Desktop app: usage events, crash reports and feedback" in html
    # The retention periods of telemetry.md §6.5.
    for period in ("13 months", "180 days", "2 years", "14 days", "30 days"):
        assert period in html, period
    assert "Delete my data" in html
    # The processors PF14 adds, beside PF2's reseller (PF2 removed Wayl:
    # test_site_pf2_no_wayl_in_public_pages).
    for processor in ("Server hosting", "Object storage", "Email delivery", "Uptime monitoring", "Paddle"):
        assert processor in html, processor
