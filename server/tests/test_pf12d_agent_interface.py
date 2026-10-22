"""PF12d: the platform follows agent-interface 1.3.0 (AI5's six creation skills, §5.20-5.25, and the scoped
remove, §5.26). None of the seven is log-safe, so the project log refuses them as actions (project-log.md §6.2)
and ops.LOG_SAFE_TOOLS does not change; /developers/mcp/ documents them with one row per top-level argument, a
nested object's or an array item's fields listed under its row (create_layout's program), and says what a creation
call does. The package and tools.json checks are in test_pf12_mcp_package.py, the page's tables in
test_site_pf12.py."""

import json
import subprocess

import pytest

from app.projects import ops

from .licence_helpers import error_of
from .pf12_helpers import PL, ROOT, kh, make_key, node
from .project_helpers import Person, action_op, create, hex32, pull, push
from .test_pf12_mcp_package import AI5_TOOLS, CREATION_SKILLS, LAYOUT_BRIEF
from .test_site_pf13 import OUT, Doc, built  # noqa: F401  (built is a fixture)

PKG_TOOLS = ROOT / "packages" / "mcp" / "tools.json"
# One plausible call of each, as an agent would write it (the log refuses the tool, whatever the arguments).
CALLS = {
    "create_layout": {**LAYOUT_BRIEF, "choose": -1},
    "create_theme": {"target": "room#3", "style": "scandinavian", "walls": {"kind": "paint", "colour": "#E8E4DA"}, "choose": -1},
    "create_fills": {"target": "room#3", "ceiling": {"kind": "paint", "colour": "RAL 9010"}, "grid": {"size_mm": [600, 600]}, "choose": -1},
    "create_object": {"name": "desk", "size_mm": [1200, 600, 750], "parts": [{"kind": "box", "at_mm": [0, 0, 0], "size_mm": [1200, 600, 750]}], "place": {"room": "Study"}, "choose": -1},
    "create_material": {"name": "Warm oak", "family": "timber", "colour": "#B07A4A", "roughness": 0.6, "choose": -1},
    "write_sheet_text": {"sheet": "A-101", "blocks": [{"title": "Notes", "lines": ["Bedrooms: {count:bedrooms}"]}], "choose": -1},
    "remove": {"refs": ["wall#12", "room#3"]},
}
LOG_SAFE = ("place", "move", "resize", "fill", "apply_theme", "set_tunable")


def _tools() -> dict:
    return json.loads(PKG_TOOLS.read_text(encoding="utf-8"))


def _creation_op(author: str, tool: str, *, base_seq: int = 0) -> dict:
    """A light client's action carrying an AI5 tool (§6.4's shape); `touched` the refs a remove names, as a writer
    would derive it (§6.2)."""
    refs = [hex32() for _ in CALLS[tool].get("refs", [])]
    op = action_op(author, refs, tool=tool, args=dict(CALLS[tool]), base_seq=base_seq)
    op["name"] = f"Agent: {tool}"
    return op


# --- the project log ------------------------------------------------------------------------------


def test_project_log_refuses_creation_tools(client):
    """create_layout and remove, and the other five AI5 tools, are class edit but not log-safe (tools.json 1.3.0):
    an action with any of them is refused 422 on ops[0].action.tool, from a session, a device and an API key,
    and nothing is stored. ops.LOG_SAFE_TOOLS is unchanged."""
    by_name = {t["name"]: t for t in _tools()["tools"]}
    for tool in AI5_TOOLS:
        meta = by_name[tool]["_meta"]
        assert meta["com.truebex/permission"] == "edit" and meta["com.truebex/logSafe"] is False, tool
    assert set(CALLS) == set(AI5_TOOLS)
    assert ops.LOG_SAFE_TOOLS == LOG_SAFE

    a = Person(client, "a@example.com")
    pid = create(client, a.dev)["project_id"]
    for tool in AI5_TOOLS:
        for headers in (a.web, a.dev):  # a light client's session (PF9 / PF10), the app's device
            body = error_of(push(client, headers, pid, a.replica, [_creation_op(a.author_id, tool)]), 422, "validation_failed")
            field = body["data"]["fields"][0]
            assert field["field"] == "ops[0].action.tool", (tool, body)
            assert repr(tool) in field["message"] and all(name in field["message"] for name in LOG_SAFE), field
    # The /v1 mirror (an API key pushes as an agent) refuses them the same way.
    key = make_key(client, a.session, ["projects:read", "projects:write"])
    for tool in ("create_layout", "remove"):
        op = _creation_op(a.author_id, tool)
        del op["author"], op["author_kind"]
        res = client.post(f"/v1/projects/{pid}/ops", json={"replica_id": hex32(), "ops": [op]}, headers=kh(key, **PL))
        body = error_of(res, 422, "validation_failed")
        assert body["data"]["fields"][0]["field"] == "ops[0].action.tool", (tool, body)
    # A push is all or nothing: a log-safe move beside a create_layout is not stored either, and the field names the
    # creation call's index.
    move = action_op(a.author_id, [hex32()])
    body = error_of(push(client, a.web, pid, a.replica, [move, _creation_op(a.author_id, "create_layout")]), 422, "validation_failed")
    assert body["data"]["fields"][0]["field"] == "ops[1].action.tool", body
    assert pull(client, a.dev, pid)["head_seq"] == 0


# --- /developers/mcp/ -----------------------------------------------------------------------------


def test_docs_generator_lists_nested_fields(tmp_path):
    """src/lib/developer-docs.ts (run by node, types stripped): argumentRows() gives one row per top-level argument;
    nestedFields() gives an object's fields or an array's object items' fields in one flat list (deeper: `a.b` for an
    object, `a[].b` for an array of objects), and nothing for any other schema."""
    exe = node()
    if exe is None:
        pytest.skip("node is not installed")
    script = tmp_path / "nested.mjs"
    script.write_text(
        "const m = await import(process.argv[2]);\n"
        "const doc = m.toolsDocument();\n"
        "const schema = (name) => doc.tools.find((t) => t.name === name).inputSchema;\n"
        "const flat = (fields) => fields.map((f) => [f.name, f.required, m.typeOf(f.schema)]);\n"
        "const sample = { type: 'array', items: { type: 'object', required: ['a'], properties: { a: { type: 'string' },"
        " b: { type: 'object', properties: { c: { type: 'number' } } }, d: { type: 'array', items: { type: 'object', properties: { e: { type: 'boolean' } } } } } } };\n"
        "console.log(JSON.stringify({\n"
        "  rows: m.argumentRows(schema('create_layout')).map((r) => r.name),\n"
        "  program: flat(m.nestedFields(schema('create_layout').properties.program)),\n"
        "  parts: flat(m.nestedFields(schema('create_object').properties.parts)).map((f) => f[0]),\n"
        "  sample: flat(m.nestedFields(sample)),\n"
        "  none: [m.nestedFields({ type: 'array', items: { type: 'number' } }), m.nestedFields({ type: 'object' }), m.nestedFields({ type: 'string' })],\n"
        "  counted: m.withToolCount('{tools} tools, {tools} again'), total: doc.tools.length,\n"
        "}));\n",
        encoding="utf-8",
    )
    entry = (ROOT / "src" / "lib" / "developer-docs.ts").as_uri()
    ran = subprocess.run([exe, "--no-warnings", str(script), entry], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert ran.returncode == 0, ran.stderr
    got = json.loads(ran.stdout.strip().splitlines()[-1])
    layout = json.loads(PKG_TOOLS.read_text(encoding="utf-8"))
    layout = next(t for t in layout["tools"] if t["name"] == "create_layout")["inputSchema"]
    assert got["rows"] == list(layout["properties"])  # top-level only: no `program.rooms` row
    assert got["program"] == [
        ["rooms", True, "object[]"],
        ["rooms[].type", True, '"living" | "kitchen" | "dining" | "bedroom" | "bathroom" | "wc" | "hall" | "study" | "utility" | "store"'],
        ["rooms[].name", False, "string"],
        ["rooms[].area_m2", True, "number"],
        ["rooms[].adjacent", False, "int[]"],
        ["rooms[].exterior", False, "boolean"],
        ["corridor_mm", False, "number"],
        ["wall_mm", False, "number"],
        ["ext_wall_mm", False, "number"],
    ]
    assert got["parts"] == ["name", "kind", "at_mm", "size_mm", "plane", "profile_mm", "depth_mm", "material"]
    assert got["sample"] == [["a", True, "string"], ["b", False, "object"], ["b.c", False, "number"], ["d", False, "object[]"], ["d[].e", False, "boolean"]]
    assert got["none"] == [[], [], []]
    total = got["total"]
    assert got["counted"] == f"{total} tools, {total} again"


def _never_list(page: Doc) -> list[str]:
    start = next(i for i, el in enumerate(page.elements) if el["tag"] == "h2" and page.text(el) == "What it never does")
    notes = []
    for el in page.elements[start + 1 :]:
        if el["tag"] == "h2":
            break
        if el["tag"] == "li":
            notes.append(page.text(el))
    return notes


def test_docs_creation_copy_follows_the_contract(built):
    """agent-interface 1.3.0 §5.20-5.26 and instructions.md, where the page says what an agent may and may never do:
    without choose a creation call changes nothing and returns checked candidates; with choose one candidate is
    applied as one undo step; the checks are sanity rules, never a building-code check, and no result claims
    compliance; remove deletes only what this connection created."""
    page = Doc((OUT / "developers" / "mcp" / "index.html").read_text(encoding="utf-8"))
    notes = _never_list(page)
    creation = next(n for n in notes if "create_layout" in n)
    for name in CREATION_SKILLS:
        assert name in creation, (name, creation)
    for phrase in (
        "Called without choose, a creation tool changes nothing and returns checked candidates",
        "with choose (-1 for the best), it applies one of them as one undo step",
    ):
        assert phrase in creation, (phrase, creation)
    checks = next(n for n in notes if "sanity rules" in n)
    for phrase in ("sanity rules", "never a building-code check", "no result claims compliance", "at most 3 times"):
        assert phrase in checks, (phrase, checks)
    remove = next(n for n in notes if "remove tool" in n)
    assert "The remove tool deletes only what this connection created" in remove and "nothing is removed" in remove, remove
    # The never-list keeps its earlier rules (PF12b, PF12c).
    joined = " ".join(notes)
    assert "run console commands" in joined and "cannot change settings, with one exception: a tunable" in joined
    # The refusal codes say what a creation call answers (§5.20-5.26, §7).
    errors = {el["attrs"]["data-error"]: " ".join(page.text(el).split()) for el in page.all("tr", data_error=True)}
    assert "candidates" in errors["invalid"] and "report" in errors["invalid"], errors["invalid"]
    assert "remove" in errors["refused"] and "3 failed repairs" in errors["refused"], errors["refused"]
    # Never a compliance claim anywhere on the page (brand voice: only claim what is true).
    text = " ".join(page.visible_text().split()).lower()
    for claim in ("compliant", "complies", "code-compliant", "meets building code", "building regulations approved"):
        assert claim not in text, claim
