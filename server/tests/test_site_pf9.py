"""PF9 build checks: read out/ after the verify gate's `npm run build`
(skipped when out/ is absent, e.g. a server-only test run)."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"

pytestmark = pytest.mark.skipif(
    not (OUT / "index.html").exists(), reason="out/ not built (run npm run build)"
)

APP_PAGES = ("app", "app/project")
# API paths the service worker must never name (it caches none of them).
API_PATHS = ("/projects", "/auth/", "/jobs", "/market", "/licence", "/uploads", "/files/", "/presence", "/ops")


def _page(route: str) -> str:
    return (OUT / route / "index.html").read_text("utf-8")


def _noindex(html: str) -> bool:
    return bool(re.search(r'<meta name="robots" content="[^"]*noindex', html))


def test_site_pf9_manifest_installable():
    manifest = json.loads((OUT / "manifest.webmanifest").read_text("utf-8"))
    assert manifest["id"] == "/app/" and manifest["start_url"] == "/app/"
    assert manifest["scope"] == "/" and manifest["display"] == "standalone"
    maskable = [i for i in manifest["icons"] if "maskable" in i.get("purpose", "")]
    assert maskable and maskable[0]["sizes"] == "512x512"
    icon = OUT / maskable[0]["src"].lstrip("/")
    assert icon.is_file() and icon.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert any(i["sizes"] == "192x192" for i in manifest["icons"])
    # Every page links it; iOS home-screen metadata is on the app pages.
    html = _page("app")
    assert 'rel="manifest"' in html
    assert 'name="apple-mobile-web-app-title" content="Truebex"' in html
    assert re.search(r'name="(apple-)?mobile-web-app-capable" content="yes"', html)


def test_site_pf9_service_worker_built():
    sw = OUT / "sw.js"
    assert sw.is_file()
    text = sw.read_text("utf-8")
    assert len(text.encode()) <= 30 * 1024
    assert "tiles-v1" in text and "shell-v1" in text
    for path in API_PATHS:
        assert path not in text, path
    # The precache list names this build's app pages and the hashed files they load.
    precache = json.loads(re.search(r'(\["/app/","/app/project/"[^\]]*\])', text).group(1))
    assert all(p == "/app/" or p == "/app/project/" or p.startswith("/_next/static/") or p.endswith((".png", ".webmanifest"))
               for p in precache)
    scripts = re.findall(r'src="(/_next/static/[^"]+\.js)"', _page("app/project"))
    assert scripts and set(scripts) <= set(precache)


def test_site_pf9_app_pages_noindex():
    for route in APP_PAGES:
        assert (OUT / route / "index.html").is_file(), route
        html = _page(route)
        assert _noindex(html), route
        assert html.count("<h1") <= 1, route
    sitemap = (OUT / "sitemap.xml").read_text("utf-8")
    assert "/app/" not in sitemap


def test_site_pf9_js_selftests():
    node = shutil.which("node")
    assert node, "node is needed for the PF9 self-tests"
    script = OUT / "viewer" / "selftest.mjs"
    assert script.is_file()
    run = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "checks passed" in run.stdout


def test_site_pf9_headset_library_loads_on_demand():
    # The 3D library is in a chunk of its own, loaded when the headset view starts.
    chunks = list((OUT / "_next" / "static").rglob("*.js"))
    three = [c for c in chunks if "isWebGLRenderer" in c.read_text("utf-8", errors="ignore")]
    assert three, "no chunk carries the 3D library"
    page_scripts = set(re.findall(r'src="(/_next/static/[^"]+\.js)"', _page("app/project")))
    for chunk in three:
        assert "/" + chunk.relative_to(OUT).as_posix() not in page_scripts


def test_site_pf9_copy_and_modules():
    constants = (ROOT / "src" / "lib" / "constants.ts").read_text("utf-8")
    app = constants.split("export const APP = {", 1)[1].split("} as const;", 1)[0]
    assert "First mobile version" in app
    assert "changed this first — your edit was replaced" in app
    # Brand voice: no "VR" and no engine or library names in public copy.
    assert not re.search(r"\bVR\b|WebXR|three\.js|Unreal", app)
    # Shipped-only: FEATURES does not claim the mobile client before its row merges.
    features = constants.split("export const FEATURES", 1)[1].split("export const", 1)[0].lower()
    assert "headset" not in features and "mobile web" not in features
    for name in ("actions.ts", "outbox.ts", "tilediff.ts", "cachepolicy.ts", "orientation.ts", "xr.ts"):
        text = (ROOT / "src" / "viewer" / name).read_text("utf-8")
        assert 'from "react"' not in text and '"@/' not in text, name
