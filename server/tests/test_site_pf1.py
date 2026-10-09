"""PF1 build checks: read the static export in out/ after the verify gate's
`npm run build` (skipped when out/ is absent), plus the site scripts run
under Node (skipped when node is missing)."""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from .conftest import LICENCE_FIXTURES, REL_SEED, TEST_KEY

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
RELEASES = ROOT / "src" / "content" / "releases.json"
built = pytest.mark.skipif(not (OUT / "index.html").is_file(), reason="out/ not built (the verify gate builds it first)")
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")


def _html(page: str) -> str:
    return (OUT / page / "index.html").read_text(encoding="utf-8")


def _site_releases() -> list[dict]:
    data = json.loads(RELEASES.read_text(encoding="utf-8"))
    seen: dict[str, dict] = {}
    for channel in ("stable", "beta"):
        for r in data[channel]["releases"]:
            seen.setdefault(r["version"], r)
    return list(seen.values())


def _canonical(html: str) -> str | None:
    m = re.search(r'<link rel="canonical" href="([^"]+)"', html)
    return m.group(1) if m else None


@built
def test_site_pf1_download_page():
    html = _html("download")
    assert len(re.findall(r"<h1[\s>]", html)) == 1
    assert "Download Truebex for Windows" in html
    assert _canonical(html) == "https://truebex.com/download/"
    assert 'href="/signup/' in html  # the licence: a free account
    latest = json.loads(RELEASES.read_text(encoding="utf-8"))["stable"]["latest"]
    if latest:
        assert f'data-release="{latest}"' in html and latest in html
    else:
        assert 'data-release="none"' in html


@built
def test_site_pf1_changelog_anchors():
    html = _html("changelog")
    assert len(re.findall(r"<h1[\s>]", html)) == 1
    assert _canonical(html) == "https://truebex.com/changelog/"
    for release in _site_releases():
        assert f'id="{release["version"]}"' in html, release["version"]
        assert release["notes_url"].endswith(f"#{release['version']}")
    # The fixture feeds' notes_url anchors are the versions (what the page uses as ids).
    beta = json.loads((LICENCE_FIXTURES / "releases-beta.json").read_text(encoding="utf-8"))["body"]
    for entry in beta["releases"]:
        assert entry["manifest"]["notes_url"] == f"https://truebex.com/changelog/#{entry['manifest']['version']}"


@built
def test_site_pf1_link_page_noindex():
    html = _html("dashboard/link")
    assert re.search(r'<meta name="robots" content="[^"]*noindex', html)


@built
def test_site_pf1_sitemap_and_no_secrets():
    sitemap = (OUT / "sitemap.xml").read_text(encoding="utf-8")
    assert "https://truebex.com/download/" in sitemap and "https://truebex.com/changelog/" in sitemap
    secrets = [TEST_KEY["private_key"], REL_SEED, "PRIVATE KEY", "private_key"]
    env = ROOT / "server" / ".env"
    if env.is_file():
        for line in env.read_text(encoding="utf-8", errors="ignore").splitlines():
            name, _, value = line.partition("=")
            if name.strip() in ("LICENCE_SIGNING_KEY", "SECRET_KEY", "STORAGE_URL_SECRET") and len(value.strip()) >= 16:
                secrets.append(value.strip())
    for path in OUT.rglob("*"):
        if path.is_file() and path.suffix in {".html", ".js", ".txt", ".json", ".xml", ".css", ".webmanifest"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for secret in secrets:
                assert secret not in text, f"{path.relative_to(OUT)} holds a secret-shaped string"


@needs_node
def test_sync_releases_from_fixture_feed(tmp_path):
    out = tmp_path / "releases.json"
    run = subprocess.run(
        [NODE, str(ROOT / "scripts" / "sync-releases.mjs"), "--from", str(LICENCE_FIXTURES), "--out", str(out)],
        capture_output=True, text=True, timeout=60, cwd=ROOT,
    )
    assert run.returncode == 0, run.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["schema"] == "truebex-site-releases/1"
    assert data["stable"]["latest"] == "1.1.0" and data["beta"]["latest"] == "1.2.0-beta.1"
    fixture_versions = {
        e["manifest"]["version"]
        for e in json.loads((LICENCE_FIXTURES / "releases-beta.json").read_text(encoding="utf-8"))["body"]["releases"]
    }
    assert {r["version"] for r in data["beta"]["releases"]} == fixture_versions
    assert all(not re.search(r"-", r["version"]) for r in data["stable"]["releases"])
    first = data["stable"]["releases"][0]
    assert set(first) >= {"version", "channel", "published_at", "notes_md", "notes_url", "installer"}
    assert first["installer"]["bytes"] == 4096


@needs_node
def test_release_notes_renderer_subset():
    """src/lib/releaseNotes.ts parses the contract's subset and never passes HTML through."""
    md = (
        "### What's new\n"
        "* **Bold** and a [link](https://truebex.com/changelog/#1.1.0)\n"
        "* <script>alert(1)</script> & [bad](javascript:alert(1))\n"
        "\n"
        "Plain paragraph.\n"
    )
    script = (
        "import { parseNotes } from " + json.dumps((ROOT / "src" / "lib" / "releaseNotes.ts").as_uri()) + ";"
        "process.stdout.write(JSON.stringify(parseNotes(process.env.NOTES)));"
    )
    run = subprocess.run(
        [NODE, "--input-type=module", "-e", script],
        capture_output=True, text=True, timeout=60, cwd=ROOT, env={**os.environ, "NOTES": md},
    )
    assert run.returncode == 0, run.stderr
    blocks = json.loads(run.stdout)
    assert blocks[0] == {"type": "heading", "level": 3, "inline": [{"type": "text", "text": "What's new"}]}
    items = blocks[1]["items"]
    assert blocks[1]["type"] == "list" and len(items) == 2
    assert items[0][0] == {"type": "bold", "children": [{"type": "text", "text": "Bold"}]}
    assert {"type": "link", "href": "https://truebex.com/changelog/#1.1.0", "children": [{"type": "text", "text": "link"}]} in items[0]
    # Raw HTML stays text (React escapes it when rendering); an unsafe link
    # keeps only its label.
    assert '"type": "link"' not in json.dumps(items[1])
    assert items[1] == [{"type": "text", "text": "<script>alert(1)</script> & bad"}]
    assert blocks[2] == {"type": "paragraph", "inline": [{"type": "text", "text": "Plain paragraph."}]}
