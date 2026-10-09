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
CONTENT = ROOT / "src" / "content"
FEEDS = {"stable": CONTENT / "releases.json", "beta": CONTENT / "releases-beta.json"}
built = pytest.mark.skipif(not (OUT / "index.html").is_file(), reason="out/ not built (the verify gate builds it first)")
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")


def _html(page: str) -> str:
    return (OUT / page / "index.html").read_text(encoding="utf-8")


def _feed(channel: str) -> dict:
    return json.loads(FEEDS[channel].read_text(encoding="utf-8"))


def _site_releases() -> list[dict]:
    """Every manifest the build saw (stable and beta feeds, as saved by sync:releases)."""
    seen: dict[str, dict] = {}
    for channel in ("stable", "beta"):
        feed = _feed(channel)
        assert feed["schema"] == "truebex-releases/1" and feed["channel"] == channel
        for entry in feed["releases"]:
            seen.setdefault(entry["manifest"]["version"], entry["manifest"])
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
    latest = _feed("stable")["latest"]
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
    run = subprocess.run(
        [NODE, str(ROOT / "scripts" / "sync-releases.mjs"), "--from", str(LICENCE_FIXTURES), "--out-dir", str(tmp_path)],
        capture_output=True, text=True, timeout=60, cwd=ROOT,
    )
    assert run.returncode == 0, run.stderr
    for channel, name in (("stable", "releases.json"), ("beta", "releases-beta.json")):
        saved = json.loads((tmp_path / name).read_text(encoding="utf-8"))
        fixture = json.loads((LICENCE_FIXTURES / f"releases-{channel}.json").read_text(encoding="utf-8"))["body"]
        assert saved == fixture  # saved exactly as served: manifests and signatures intact
    stable = json.loads((tmp_path / "releases.json").read_text(encoding="utf-8"))
    assert stable["latest"] == "1.1.0" and all("-" not in e["manifest"]["version"] for e in stable["releases"])
    assert json.loads((tmp_path / "releases-beta.json").read_text(encoding="utf-8"))["latest"] == "1.2.0-beta.1"

    # A broken feed changes nothing.
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "releases-stable.json").write_text('{"schema": "nope"}', encoding="utf-8")
    (bad / "releases-beta.json").write_text('{"schema": "nope"}', encoding="utf-8")
    before = (tmp_path / "releases.json").read_bytes()
    run = subprocess.run(
        [NODE, str(ROOT / "scripts" / "sync-releases.mjs"), "--from", str(bad), "--out-dir", str(tmp_path)],
        capture_output=True, text=True, timeout=60, cwd=ROOT,
    )
    assert run.returncode == 1 and (tmp_path / "releases.json").read_bytes() == before


@needs_node
def test_release_notes_renderer_subset():
    """src/lib/releaseNotes.ts parses the contract's subset and never passes HTML through."""
    md = (
        "### What's new\n"
        "* **Bold** and a [link](https://truebex.com/changelog/#1.1.0)\n"
        "* <script>alert(1)</script> & [bad](javascript:void)\n"
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
