"""PF12 build checks: read out/ after the verify gate's `npm run build`
(skipped when out/ is absent): the developer docs pages, their reference
tables generated from openapi/v1.json and src/content/tools.json, the
dashboard pages, and the site's build config."""

import json
import re
import xml.etree.ElementTree as ET

from .pf12_helpers import ROOT
from .test_site_pf13 import OUT, SITE, Doc, built  # noqa: F401  (built is a fixture)

SUBPAGES = ["projects", "jobs", "shares", "market", "webhooks", "sdks", "mcp"]
GROUP_PAGES = {
    "projects": ["projects"],
    "jobs": ["jobs"],
    "shares": ["uploads", "shares"],
    "market": ["market", "feeds"],
    "webhooks": ["webhooks"],
    "": ["account"],
}


def _page(rel: str) -> Doc:
    return Doc((OUT / rel / "index.html").read_text(encoding="utf-8"))


def _doc() -> dict:
    return json.loads((ROOT / "openapi" / "v1.json").read_text(encoding="utf-8"))


def _tools() -> dict:
    return json.loads((ROOT / "src" / "content" / "tools.json").read_text(encoding="utf-8"))


def test_docs_generated_from_tools_json(built):
    """agent-interface §10: the docs list every tool, class and argument of tools.json."""
    page = _page("developers/mcp")
    for tool in _tools()["tools"]:
        sections = page.all("section", data_tool=tool["name"])
        assert len(sections) == 1, tool["name"]
        section = sections[0]
        text = page.text(section)
        assert tool["name"] in text and tool["title"] in text and tool["description"] in text
        klass = tool["_meta"]["com.truebex/permission"]
        assert klass in text
        args = {el["attrs"]["data-argument"] for el in page.all("tr", data_argument=True) if el in _rows_within(page, section)}
        want = set()
        for name, prop in tool["inputSchema"]["properties"].items():
            want.add(name)
            for sub in (prop.get("properties") or {}):
                want.add(f"{name}.{sub}")
        assert args == want, tool["name"]
    text = page.visible_text()
    assert "claude mcp add --scope user truebex -- npx -y @truebex/mcp" in text
    assert '"args": ["-y", "@truebex/mcp"]' in text


def _rows_within(page: Doc, section: dict) -> list[dict]:
    start = page.elements.index(section)
    out = []
    for el in page.elements[start + 1 :]:
        if el["tag"] == "section":
            break
        out.append(el)
    return out


def test_site_pf12_developer_pages(built):
    sitemap = ET.parse(OUT / "sitemap.xml").getroot()
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = {u.find("s:loc", ns).text for u in sitemap.findall("s:url", ns)}
    files = sorted((OUT / "developers").rglob("index.html"))
    assert {f.parent.name for f in files} == {"developers", *SUBPAGES}
    for f in files:
        rel = f.parent.relative_to(OUT).as_posix()
        page = Doc(f.read_text(encoding="utf-8"))
        assert len(page.all("h1")) == 1, rel
        assert page.canonical() == f"{SITE}/{rel}/", rel
        assert {"TechArticle", "BreadcrumbList"} <= page.ld_types(), rel
        description = page.meta("description") or ""
        assert 120 <= len(description) <= 160, (rel, len(description))
        assert page.title().endswith("· Truebex"), rel
        assert f"{SITE}/{rel}/" in urls, rel
        # Every page links to every other through the docs nav.
        for sub in SUBPAGES:
            assert page.all("a", href=f"/developers/{sub}/"), (rel, sub)
        assert "noindex" not in (page.meta("robots") or "")


def test_site_pf12_reference_matches_openapi(built):
    """Every operation of the document is on its page, generated, with its scope."""
    doc = _doc()
    by_group: dict[str, list[tuple[str, str, dict]]] = {}
    for path, item in doc["paths"].items():
        for method, op in item.items():
            by_group.setdefault(op["operationId"].split("_")[0], []).append((method.upper(), path, op))
    for rel, groups in GROUP_PAGES.items():
        page = _page(f"developers/{rel}".rstrip("/"))
        listed = {el["attrs"]["data-operation"] for el in page.all("section", data_operation=True)}
        want = {op["operationId"] for g in groups for _, _, op in by_group[g]}
        assert listed == want, rel
        for g in groups:
            for method, path, op in by_group[g]:
                section = page.all("section", data_operation=op["operationId"])[0]
                text = page.text(section)
                assert method in text and path in text, op["operationId"]
                if op.get("x-truebex-scope"):
                    assert op["x-truebex-scope"] in text, op["operationId"]
    # The SDK page has a row per operation.
    sdks = _page("developers/sdks")
    rows = {el["attrs"]["data-operation"] for el in sdks.all("tr", data_operation=True)}
    assert rows == {op["operationId"] for ops in by_group.values() for _, _, op in ops}
    # The overview's scope table and the webhooks page's events come from the document too.
    overview = _page("developers")
    assert {el["attrs"]["data-scope"] for el in overview.all("tr", data_scope=True)} == {
        s["scope"] for s in doc["x-truebex-scopes"]
    }
    hooks = _page("developers/webhooks")
    assert {el["attrs"]["data-event"] for el in hooks.all("tr", data_event=True)} == {
        e["type"] for e in doc["x-truebex-webhook-events"]
    }
    limits = doc["x-truebex-limits"]
    assert f"{limits['burst']} calls at once" in overview.visible_text()


def test_site_pf12_roadmap_work_is_labelled(built):
    """Projects in the app, cloud rendering and the Agent panel are not shipped:
    their pages say so (brand voice: only claim what ships)."""
    for rel in ("developers/projects", "developers/jobs", "developers/mcp", "developers/market"):
        assert "On the roadmap." in _page(rel).visible_text(), rel
    constants = (ROOT / "src" / "lib" / "constants.ts").read_text(encoding="utf-8")
    block = constants.split("export const DEVELOPER_DOCS", 1)[1]
    published = re.search(r"sdksPublished: (true|false)", block).group(1)
    if published == "false":
        assert "Rolling out." in _page("developers/sdks").visible_text()
    features = constants.split("export const FEATURES", 1)[1].split("export const", 1)[0].lower()
    assert "webhook" not in features and "mcp" not in features and " sdk" not in features


def test_site_pf12_dashboard_pages(built):
    for rel in ("dashboard/webhooks", "dashboard/keys"):
        page = _page(rel)
        assert re.search(r'<meta name="robots" content="[^"]*noindex', page.html), rel
    sitemap = (OUT / "sitemap.xml").read_text(encoding="utf-8")
    assert "/dashboard/webhooks" not in sitemap
    shell = (ROOT / "src" / "components" / "dashboard" / "DashboardShell.tsx").read_text(encoding="utf-8")
    assert '"/dashboard/webhooks/"' in shell
    keys = (ROOT / "src" / "app" / "dashboard" / "keys" / "page.tsx").read_text(encoding="utf-8")
    assert "listScopes" in keys and "T.scopesLabel" in keys
    # The OpenAPI document never ships to the browser: only server code reads it.
    for chunk in (OUT / "_next").rglob("*.js"):
        text = chunk.read_text(encoding="utf-8", errors="ignore")
        assert "x-truebex-scope" not in text, chunk.name


def test_site_pf12_build_excludes_packages():
    tsconfig = json.loads((ROOT / "tsconfig.json").read_text(encoding="utf-8"))
    assert {"sdks", "packages"} <= set(tsconfig["exclude"])
    eslint = (ROOT / "eslint.config.mjs").read_text(encoding="utf-8")
    assert '"sdks/**"' in eslint and '"packages/**"' in eslint
