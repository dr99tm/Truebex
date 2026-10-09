"""PF3 build checks (read out/ after the verify gate's build; skipped when
out/ is absent) and the organisation mail templates."""

import re
from pathlib import Path

import pytest

from app import mail

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
built = pytest.mark.skipif(not (OUT / "index.html").is_file(), reason="out/ not built (the verify gate builds it first)")

CONSOLE = ["", "members", "invites", "seats", "usage", "sso", "audit"]


def _html(page: str) -> str:
    return (OUT / page / "index.html").read_text(encoding="utf-8")


def _noindex(html: str) -> bool:
    return bool(re.search(r'<meta name="robots" content="[^"]*noindex', html))


@built
def test_site_pf3_new_pages_noindex():
    assert _noindex(_html("invite"))
    assert _noindex(_html("login/sso"))
    for sub in CONSOLE:
        page = f"dashboard/organisation/{sub}".rstrip("/")
        assert _noindex(_html(page)), page
    # Account pages stay out of the sitemap.
    sitemap = (OUT / "sitemap.xml").read_text(encoding="utf-8")
    for path in ("/invite/", "/login/sso/", "/dashboard/organisation/"):
        assert path not in sitemap


@built
def test_site_pf3_sso_entry_and_no_test_keys():
    login = _html("login")
    chunks = "".join(p.read_text(encoding="utf-8", errors="ignore") for p in (OUT / "_next").rglob("*.js"))
    assert "Continue with SSO" in login or "Continue with SSO" in chunks
    fixtures = Path(__file__).parent / "fixtures" / "sso"
    for key in fixtures.glob("*_key.pem"):
        body = key.read_text(encoding="ascii").splitlines()[1]
        assert body not in chunks


def test_mail_templates_render_and_escape():
    data = {
        "org_invite": {"org_name": "Studio <North>", "inviter": "Ann", "role_name": "Admin", "seat_line": "",
                       "link": "https://truebex.com/invite/?t=abc", "expires": "2026-10-16T09:00:00Z",
                       "email": "a@example.com"},
        "org_seat_assigned": {"org_name": "Studio <North>", "actor": "Ann", "seat_name": "named",
                              "plan_name": "Team", "seat_line": "It is yours alone.", "link": "https://truebex.com/"},
        "org_removed": {"org_name": "Studio <North>", "actor": "Ann", "link": "https://truebex.com/"},
    }
    for name, values in data.items():
        msg = mail.render(name, values)  # PF14's Message
        subject, text, html = msg.subject, msg.text, msg.html
        assert msg.template == name
        assert "$" not in subject + text + html, name
        assert "Studio <North>" in text and "Studio &lt;North&gt;" in html, name
        assert "\n" not in subject
    with pytest.raises(KeyError):
        mail.render("org_removed", {"org_name": "x"})
