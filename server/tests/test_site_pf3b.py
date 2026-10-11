"""PF3b build checks: the Member usage tab drops PF3's "appear here once…"
note, says storage is shown for the current month only, and formats the
three columns (src/lib/memberUsage.ts, run with the project's TypeScript)."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
PAGE = ROOT / "src" / "app" / "dashboard" / "organisation" / "usage" / "page.tsx"
OLD_NOTE = "appear here once those services start counting them"
built = pytest.mark.skipif(not (OUT / "index.html").is_file(), reason="out/ not built (the verify gate builds it first)")


def _chunks() -> str:
    return "".join(p.read_text(encoding="utf-8", errors="ignore") for p in (OUT / "_next").rglob("*.js"))


def test_site_pf3b_usage_page_source_drops_old_note():
    source = PAGE.read_text(encoding="utf-8")
    assert OLD_NOTE not in source and "later(" not in source
    assert "MEMBER_USAGE" in source and "formatStorage" in source


@built
def test_site_pf3b_usage_page_drops_old_note():
    assert (OUT / "dashboard" / "organisation" / "usage" / "index.html").is_file()
    html = (OUT / "dashboard" / "organisation" / "usage" / "index.html").read_text(encoding="utf-8")
    chunks = _chunks()
    assert OLD_NOTE not in html and OLD_NOTE not in chunks
    assert "so it is shown for the current month only" in chunks
    assert "Updates to a panorama that follows the project are not counted again" in chunks


def test_site_pf3b_formats_usage_columns():
    exe = shutil.which("node")
    if exe is None:
        pytest.skip("node not on PATH")
    if not (ROOT / "node_modules" / "typescript").exists():
        pytest.skip("node_modules not installed")
    script = r"""
const fs = require("node:fs");
const ts = require(process.argv[1] + "/node_modules/typescript");
const src = fs.readFileSync(process.argv[1] + "/src/lib/memberUsage.ts", "utf8");
const out = ts.transpileModule(src, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } });
const m = { exports: {} };
new Function("module", "exports", out.outputText)(m, m.exports);
const { formatStorage: s, formatCount: c } = m.exports;
const MIB = 1024 * 1024;
console.log(JSON.stringify({
  seeded: s(256 * MIB), zero: s(0), none: s(null), tiny: s(300), small: s(7.54 * MIB), mb: s(152500000),
  edge: s(1023.7 * MIB), gb: s(1.5 * 1024 * MIB), big: s(12.3 * 1024 * MIB), huge: s(2048 * 1024 * MIB),
  credits: c(1250), many: c(1234567), count: c(2), nothing: c(0), unknown: c(null),
}));
"""
    res = subprocess.run([exe, "-e", script, str(ROOT)], capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert res.returncode == 0, res.stderr
    assert json.loads(res.stdout) == {
        "seeded": "256 MB", "zero": "0 MB", "none": "—", "tiny": "< 0.1 MB", "small": "7.5 MB", "mb": "145 MB",
        "edge": "1 GB", "gb": "1.5 GB", "big": "12 GB", "huge": "2,048 GB",
        "credits": "1,250", "many": "1,234,567", "count": "2", "nothing": "0", "unknown": "—",
    }
