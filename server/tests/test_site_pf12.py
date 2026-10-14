"""PF12 build checks: read out/ after the verify gate's `npm run build`
(skipped when out/ is absent): the developer docs pages, their reference
tables generated from openapi/v1.json and src/content/tools.json, the
dashboard pages, and the site's build config."""

import json
import re
import xml.etree.ElementTree as ET

import pytest

from .pf12_helpers import ROOT, node
from .test_pf12_mcp_package import ASSISTANT_ONLY, Bridge, on_mcp
from .test_pf12_mcp_package import meta as mcp_meta
from .test_site_pf13 import OUT, SITE, Doc, built  # noqa: F401  (built is a fixture)

SUBPAGES = ["projects", "jobs", "shares", "market", "webhooks", "sdks", "mcp"]
MCP_RESOURCES = {"truebex://state/digest", "truebex://project/summary", "truebex://entity/{kind}/{id}"}
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


def _arguments(schema: dict, prefix: str = "") -> dict[str, tuple[dict, bool]]:
    """Every argument the page lists: name -> (schema, required), nested objects as `a.b`."""
    out = {}
    required = set(schema.get("required", []))
    for name, prop in (schema.get("properties") or {}).items():
        out[prefix + name] = (prop, name in required)
        if prop.get("type") == "object" and prop.get("properties"):
            out.update(_arguments(prop, f"{prefix}{name}."))
    return out


def _cells(page: Doc, row: dict) -> list[str]:
    """The text of each cell of one table row."""
    out = []
    for el in page.elements[page.elements.index(row) + 1 :]:
        if el["tag"] == "tr":
            break
        if el["tag"] in ("td", "th"):
            out.append(page.text(el))
    return out


def _num(v) -> str:
    return str(int(v)) if float(v).is_integer() else str(v)


# An argument with no type (TU1's set_tunable value: the portable subset has no type list) shows the page's own
# words for it (DEVELOPER_DOCS.pages.mcp.untypedTypes), else this fallback; never an empty cell or "undefined".
UNTYPED_FALLBACK = "any"


def _untyped_types() -> dict[str, str]:
    block = (ROOT / "src" / "lib" / "constants.ts").read_text(encoding="utf-8").split("untypedTypes: {", 1)[1].split("}", 1)[0]
    return dict(re.findall(r'"([a-z_]+\.[a-z_.]+)": "([^"]+)"', block))


def _expected_cells(prop: dict, untyped: str = UNTYPED_FALLBACK) -> list[str]:
    """What the row must show: the type (enum values), the range, the length, the items, the default."""
    want = []
    s = prop["items"] if prop.get("type") == "array" and isinstance(prop.get("items"), dict) else prop
    if s.get("enum"):
        want += [json.dumps(v) for v in s["enum"]]
    elif "type" not in s:
        want.append(untyped)
    else:
        want.append({"integer": "int"}.get(s.get("type"), s.get("type", "")))
    if prop.get("type") == "array":
        want.append("[]")
    if "minimum" in s or "maximum" in s:
        want.append(f"{_num(s['minimum']) if 'minimum' in s else '−∞'} to {_num(s['maximum']) if 'maximum' in s else '∞'}")
    if "maxLength" in s:
        want.append(f"≤ {s['maxLength']} chars")
    if prop.get("type") == "array" and prop.get("minItems") is not None and prop.get("minItems") == prop.get("maxItems"):
        want.append(f"{prop['minItems']} items")
    if "default" in prop:
        want.append(f"default {json.dumps(prop['default'])}")
    if prop.get("description"):
        want.append(prop["description"])
    return [w for w in want if w]


def test_docs_generated_from_tools_json(built):
    """agent-interface §10: the docs list every tool, class and argument of tools.json (PF12b: the file
    AI1 ships), what a tool that needs an unshipped feature answers, the resources, the switch and
    the prompt, and install notes for the bridge as the app installs it."""
    doc = _tools()
    page = _page("developers/mcp")
    html = page.html
    # agent-interface 1.2.0: the page documents the tools on the mcp surface (absent = both), 13 of the file's 14;
    # the in-app assistant's propose_variants is never on MCP, so its name is nowhere in the page's files.
    listed = on_mcp(doc)
    assert len(listed) == len(doc["tools"]) - len(ASSISTANT_ONLY) == 13
    assert [el["attrs"]["data-tool"] for el in page.all("section", data_tool=True)] == [t["name"] for t in listed]
    for path in (OUT / "developers" / "mcp").rglob("*"):
        if path.is_file():
            for name in ASSISTANT_ONLY:
                assert name.encode() not in path.read_bytes(), (name, path)
    untyped = _untyped_types()
    assert "undefined" not in page.visible_text()
    for tool in listed:
        sections = page.all("section", data_tool=tool["name"])
        assert len(sections) == 1, tool["name"]
        section = sections[0]
        text = page.text(section)
        assert tool["name"] in text and tool["title"] in text and tool["description"] in text, tool["name"]
        klass = tool["_meta"]["com.truebex/permission"]
        assert f"Class: {klass}" in text, tool["name"]
        within = _rows_within(page, section)
        requires = tool["_meta"].get("com.truebex/requires")
        flagged = [el for el in within if el["tag"] == "p" and "data-requires" in el["attrs"]]
        if requires:
            assert len(flagged) == 1 and "feature_absent" in page.text(flagged[0]), tool["name"]
            assert requires not in text, f"{tool['name']}: the plan id {requires} is Truebex's own"
        else:
            assert not flagged, tool["name"]
        rows = {el["attrs"]["data-argument"]: el for el in within if el["tag"] == "tr" and "data-argument" in el["attrs"]}
        want = _arguments(tool["inputSchema"])
        assert set(rows) == set(want), tool["name"]
        for name, (prop, required) in want.items():
            cells = _cells(page, rows[name])
            assert cells[0] == name and cells[2] == ("yes" if required else ""), f"{tool['name']}.{name}: {cells}"
            assert cells[1].strip() and cells[1] != "undefined", f"{tool['name']}.{name}: no type shown"
            row = " | ".join(cells)
            for cell in _expected_cells(prop, untyped.get(f"{tool['name']}.{name}", UNTYPED_FALLBACK)):
                assert cell in row, f"{tool['name']}.{name}: {cell!r} not in {row!r}"
    # TU1's two tools: the untyped value reads as what set_tunable takes, next to its description; get_tunables'
    # limits as the file gives them.
    tunable = {el["attrs"]["data-argument"]: _cells(page, el) for el in _rows_within(page, page.all("section", data_tool="set_tunable")[0]) if el["tag"] == "tr" and "data-argument" in el["attrs"]}
    setter = next(t for t in listed if t["name"] == "set_tunable")["inputSchema"]["properties"]["value"]
    assert tunable["value"][1] == untyped["set_tunable.value"] == "number | boolean | string", tunable["value"]
    assert tunable["value"][4] == setter["description"] and tunable["value"][3] == ""
    reader = {el["attrs"]["data-argument"]: _cells(page, el) for el in _rows_within(page, page.all("section", data_tool="get_tunables")[0]) if el["tag"] == "tr" and "data-argument" in el["attrs"]}
    assert reader["limit"][1] == "int" and "1 to 500" in reader["limit"][3] and "default 200" in reader["limit"][3]
    assert "≤ 40 chars" in reader["feature"][3] and "≤ 80 chars" in reader["query"][3]
    assert "Class: read" in page.text(page.all("section", data_tool="get_tunables")[0])
    assert "Class: edit" in page.text(page.all("section", data_tool="set_tunable")[0])
    # "Also travels in the project log" only where the log takes the tool: a log-safe edit (project-log §6.2), not
    # get_tunables, a read the app's file marks logSafe (PF12c carry-over).
    in_log = [t["name"] for t in listed if "Also travels in the project log" in page.text(page.all("section", data_tool=t["name"])[0])]
    assert in_log == ["place", "move", "resize", "fill", "apply_theme", "set_tunable"], in_log
    # Truebex's own _meta (router, surfaces, requires ids) never reaches the page.
    assert "com.truebex/" not in html and "kernel:" not in html and "registry:" not in html
    for tool in doc["tools"]:
        for symbol in re.findall(r"[A-Za-z]+::[A-Za-z]+", tool["_meta"]["com.truebex/router"]):
            assert symbol not in html, symbol
    text = " ".join(page.visible_text().split())
    for phrase in (
        "Allow AI apps to connect",
        "off by default",
        "read, read + edit, or read + edit + export",
        "for that connection only",
        "Install in Claude Desktop",
        "truebex.mcpb",
        "claude_desktop_config.json",
        r'"args": ["<install>\\MultiWindow\\Tools\\mcp\\truebex-mcp.mjs"]',
        r'claude mcp add --scope user truebex -- node "<install>\MultiWindow\Tools\mcp\truebex-mcp.mjs"',
        "app_not_running",
        f"tools.json {doc['version']}",
    ):
        assert phrase in text, phrase
    assert {el["attrs"]["data-resource"] for el in page.all("tr", data_resource=True)} == MCP_RESOURCES
    constants = (ROOT / "src" / "lib" / "constants.ts").read_text(encoding="utf-8")
    published = re.search(r"mcpPublished: (true|false)", constants.split("export const DEVELOPER_DOCS", 1)[1]).group(1)
    if published == "true":
        assert "claude mcp add --scope user truebex -- npx -y @truebex/mcp" in text
    else:  # the npx form waits until the owner has published @truebex/mcp
        assert "npx" not in html and "Rolling out" in text
    # The app ships node + truebex-mcp.mjs and truebex.mcpb: no executable anywhere in the site.
    for path in OUT.rglob("*"):
        if path.is_file() and path.suffix in {".html", ".js", ".txt", ".json", ".xml"}:
            assert b"truebex-mcp.exe" not in path.read_bytes(), path


def test_docs_resources_match_the_bridge(built, tmp_path):
    """The resources on /developers/mcp/ are the ones the copied bridge lists (they are not in tools.json)."""
    if node() is None:
        pytest.skip("node is not installed")
    bridge = Bridge(tmp_path)
    listed = {r["uri"] for r in bridge.request("resources/list", {"_meta": mcp_meta()})["result"]["resources"]}
    templates = bridge.request("resources/templates/list", {"_meta": mcp_meta()})["result"]["resourceTemplates"]
    listed |= {t["uriTemplate"] for t in templates}
    assert bridge.close()[0] == 0
    assert listed == MCP_RESOURCES
    page = _page("developers/mcp")
    assert {el["attrs"]["data-resource"] for el in page.all("tr", data_resource=True)} == listed


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
