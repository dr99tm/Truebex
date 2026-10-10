"""PF5 build checks: the viewer bundle and the dashboard's Shares page in out/
(skipped when out/ is absent; the verify gate builds it first), the share
page's copy kept in step with constants.ts, and the viewer's geometry under
Node (skipped when node is missing)."""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from app.shares import page

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
built = pytest.mark.skipif(not (OUT / "index.html").is_file(), reason="out/ not built (the verify gate builds it first)")
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")


@built
def test_site_pf5_viewer_bundle_built():
    js, css = OUT / "viewer" / "viewer.js", OUT / "viewer" / "viewer.css"
    assert js.is_file() and css.is_file()
    assert js.stat().st_size <= 250 * 1024
    code = js.read_text(encoding="utf-8")
    assert "share-bundle/1.0" in code and page.DESIGNED_IN in code
    # Brand tokens come from globals.css, so the page matches the site.
    styles = css.read_text(encoding="utf-8")
    globals_css = (ROOT / "src" / "app" / "globals.css").read_text(encoding="utf-8")
    accent = re.search(r"--color-accent:\s*([^;]+);", globals_css).group(1).strip()
    assert f"--color-accent:{accent}" in styles
    # PDF.js is copied beside it and loaded only on demand.
    for name in ("pdf.min.mjs", "pdf.worker.min.mjs", "LICENSE"):
        assert (OUT / "viewer" / "pdfjs" / name).is_file(), name
    assert "pdf.min.mjs" in code and "pdf.worker.min.mjs" in code


@built
def test_site_pf5_dashboard_shares_noindex():
    html = (OUT / "dashboard" / "shares" / "index.html").read_text(encoding="utf-8")
    assert re.search(r'<meta name="robots" content="[^"]*noindex', html)
    sitemap = (OUT / "sitemap.xml").read_text(encoding="utf-8")
    assert "/dashboard/" not in sitemap and "/view/" not in sitemap


def test_site_pf5_copy_in_step():
    """The server's share-page strings are the ones in SHARE_PAGE (constants.ts)."""
    text = (ROOT / "src" / "lib" / "constants.ts").read_text(encoding="utf-8")
    block = re.search(r"export const SHARE_PAGE = \{(.*?)\n\} as const;", text, re.S).group(1)

    def value(key: str) -> str:
        m = re.search(rf'\b{key}:\s*"((?:[^"\\]|\\.)*)"', block)
        assert m, key
        return json.loads(f'"{m.group(1)}"')

    assert value("designedIn") == page.DESIGNED_IN
    assert value("getTruebex") == page.GET_TRUEBEX
    assert value("ogTitleSuffix") == page.OG_TITLE_SUFFIX
    assert value("endedTitle") == page.ENDED_TITLE
    assert value("endedText") == page.ENDED_TEXT
    assert value("notFoundTitle") == page.NOT_FOUND_TITLE
    assert value("notFoundText") == page.NOT_FOUND_TEXT
    assert value("downloadPdf") == page.DOWNLOAD_PDF


@needs_node
def test_site_pf5_viewer_geometry():
    """src/viewer/geometry.ts: bearings, hotspot directions, the gyroscope, image choice."""
    script = (
        "import * as g from " + json.dumps((ROOT / "src" / "viewer" / "geometry.ts").as_uri()) + ";"
        "const r = (v) => Math.round(v * 1000) / 1000;"
        "const view = { bearing: 90, pitch: 0 };"
        "const pano = (width, d) => ({ width, height: width / 2, derivatives: d });"
        "const d = { 'pano-4096': { url: 'D4', width: 4096 }, 'pano-1024': { url: 'D1', width: 1024 } };"
        "const out = {"
        " wrap: [g.wrap180(190), g.wrap180(-190), g.wrap180(360), g.wrap180(-180)],"
        " ahead: g.toCamera(90, 0, view).map(r),"
        " right: g.toCamera(180, 0, view).map(r),"
        " up: g.toCamera(90, 30, view).map(r),"
        " upright: g.deviceLook(0, 90, 0, 0),"
        " turnedRight: g.deviceLook(-10, 90, 0, 0),"
        " tiltedBack: g.deviceLook(0, 100, 0, 0),"
        " flat: g.deviceLook(0, 0, 0, 0),"
        " landscape: g.deviceLook(0, 0, -90, 90),"
        " phone: g.pickSources(pano(8192, d), 16384, 'ORIG', { coarse: true, metered: false }),"
        " desktop: g.pickSources(pano(8192, d), 16384, 'ORIG', { coarse: false, metered: false }),"
        " metered: g.pickSources(pano(8192, d), 16384, 'ORIG', { coarse: false, metered: true }),"
        " oldGpu: g.pickSources(pano(8192, d), 4096, 'ORIG', { coarse: false, metered: false }),"
        " tiny: g.pickSources(pano(8192, d), 2048, 'ORIG', { coarse: false, metered: false }),"
        " small: g.pickSources(pano(2048, { 'pano-4096': { url: 'D2', width: 2048 } }), 16384, 'ORIG', { coarse: false, metered: false }),"
        "};"
        "for (const k of ['upright','turnedRight','tiltedBack','flat','landscape']) out[k] = { yaw: r(out[k].yaw), pitch: r(out[k].pitch) };"
        "process.stdout.write(JSON.stringify(out));"
    )
    run = subprocess.run(
        [NODE, "--input-type=module", "-e", script],
        capture_output=True, text=True, timeout=60, cwd=ROOT, env={**os.environ, "NODE_NO_WARNINGS": "1"},
    )
    assert run.returncode == 0, run.stderr
    out = json.loads(run.stdout)
    assert out["wrap"] == [-170, 170, 0, 180]
    # Looking east: east is straight ahead (-z), south is to the right (+x), 30° up is up.
    assert out["ahead"] == [0, 0, -1]
    assert out["right"] == [1, 0, 0]
    assert out["up"][1] == pytest.approx(0.5) and out["up"][2] < 0
    # The phone held upright looks level; turning it clockwise looks right
    # (bearing grows); tilting its top back looks up; lying flat looks down.
    assert out["upright"]["pitch"] == pytest.approx(0, abs=1e-6)
    assert out["turnedRight"]["yaw"] == pytest.approx(out["upright"]["yaw"] + 10)
    assert out["tiltedBack"]["pitch"] == pytest.approx(10)
    assert out["flat"]["pitch"] == pytest.approx(-90)
    # Landscape, top turned left (gamma -90, screen 90°): still level.
    assert out["landscape"]["pitch"] == pytest.approx(0, abs=1e-6)
    # Never the 8k original on a phone, a metered connection or a small GPU.
    assert out["phone"] == {"preview": "D1", "main": "D4"}
    assert out["desktop"] == {"preview": "D1", "main": "ORIG"}
    assert out["metered"]["main"] == "D4" and out["oldGpu"]["main"] == "D4"
    assert out["tiny"]["main"] == "D1"
    assert out["small"]["main"] == "D2"
