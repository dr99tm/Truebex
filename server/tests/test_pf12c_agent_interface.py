"""PF12c: the platform follows agent-interface 1.2.0 (TU1's get_tunables and set_tunable, 1.1.0; AI2's
assistant-only propose_variants and the surfaces key, 1.2.0). The project log takes set_tunable as a
log-safe action (project-log.md §6.2 names agent-interface §5's log-safe tools); /developers/mcp/ is
generated from the tools on the mcp surface only, and its never-list follows §6.3's settings exception.
The package and tools.json checks are in test_pf12_mcp_package.py, the page's tables in test_site_pf12.py."""

import json
import subprocess

import pytest

from app.projects import ops

from .licence_helpers import error_of
from .pf12_helpers import ROOT, node
from .project_helpers import Person, action_op, create, hex32, pull, push, pushed
from .test_pf12_mcp_package import ASSISTANT_ONLY, on_mcp, surfaces_of
from .test_site_pf13 import OUT, Doc, built  # noqa: F401  (built is a fixture)

PKG_TOOLS = ROOT / "packages" / "mcp" / "tools.json"
SUN = {"name": "cad.Light.SunIntensity", "value": 7}


def _tools() -> dict:
    return json.loads(PKG_TOOLS.read_text(encoding="utf-8"))


def _statuses(answer: dict) -> list[str]:
    return [r["status"] for r in answer["results"]]


def tunable_op(author: str, args: dict | None = None, *, tool: str = "set_tunable", base_seq: int = 0) -> dict:
    """A light client's set_tunable as a log `action` (§6.4): no entity ref in its arguments, so `touched`
    (the refs in the arguments, project-log §6.2) is empty."""
    op = action_op(author, [], tool=tool, args=dict(SUN if args is None else args), base_seq=base_seq)
    op["name"] = "Set sun intensity"
    return op


# --- the project log ------------------------------------------------------------------------------


def test_project_log_accepts_set_tunable_action(client):
    """agent-interface 1.1.0 §5.18 makes set_tunable log-safe: a light client's action with it is accepted,
    stored and pulled as written."""
    a = Person(client, "a@example.com")
    pid = create(client, a.dev)["project_id"]
    op = tunable_op(a.author_id)
    assert op["action"]["permission"] == "edit" and op["touched"] == []
    answer = pushed(client, a.web, pid, a.replica, [op])  # a light client (session), as PF9 / PF10 push
    assert _statuses(answer) == ["accepted"] and answer["results"][0]["server_seq"] == 1
    got = pull(client, a.dev, pid)["ops"]
    assert [(o["kind"], o["touched"], o["action"]["tool"], o["action"]["args"]) for o in got] == [("action", [], "set_tunable", SUN)]
    # A reset (exactly one of value, reset) is a set_tunable call too.
    reset = tunable_op(a.author_id, {"name": "cad.Light.SunIntensity", "reset": True}, base_seq=1)
    assert _statuses(pushed(client, a.dev, pid, a.replica, [reset])) == ["accepted"]
    assert pull(client, a.dev, pid)["head_seq"] == 2


def test_project_log_refuses_get_tunables_and_propose_variants(client):
    """get_tunables is a read (§5.17) and propose_variants is not log-safe (§5.19, assistant only): the same
    action with either tool is refused 422 on ops[0].action.tool, and nothing is stored."""
    a = Person(client, "a@example.com")
    pid = create(client, a.dev)["project_id"]
    variants = {"variants": [{"name": "Warm", "calls": [{"fill": {"target": hex32(), "finish": {"kind": "paint", "colour": "#E8E4DA"}}}]}]}
    for tool, args in (("get_tunables", {"feature": "Light"}), ("propose_variants", variants), ("get_tunables", SUN)):
        body = error_of(push(client, a.web, pid, a.replica, [tunable_op(a.author_id, args, tool=tool)]), 422, "validation_failed")
        field = body["data"]["fields"][0]
        assert field["field"] == "ops[0].action.tool", body
        assert tool in field["message"] and "set_tunable" in field["message"], field  # the message lists the log-safe tools
    assert pull(client, a.dev, pid)["head_seq"] == 0


def test_project_log_set_tunable_touches_nothing(client):
    """touched comes from the refs in the arguments (§6.2); set_tunable has none, so two replicas that set the
    same knob from the same base never conflict (the platform invents no touched key: PF12c's As-built proposes
    one, `tunable#<name>`, to the owner). A ref-carrying action from the same base still conflicts."""
    a = Person(client, "a@example.com")
    pid = create(client, a.dev)["project_id"]
    phone, web = hex32(), hex32()
    first = pushed(client, a.web, pid, phone, [tunable_op(a.author_id, {"name": "cad.Light.SunIntensity", "value": 7})])
    second = pushed(client, a.web, pid, web, [tunable_op(a.author_id, {"name": "cad.Light.SunIntensity", "value": 3})])
    assert _statuses(first) == _statuses(second) == ["accepted"]
    assert [o["touched"] for o in pull(client, a.dev, pid)["ops"]] == [[], []]
    # The same two replicas moving one wall from base 2: the second is rejected with the first as the winner.
    wall = hex32()
    won = pushed(client, a.web, pid, phone, [action_op(a.author_id, [wall], base_seq=2)])
    lost = pushed(client, a.web, pid, web, [action_op(a.author_id, [wall], base_seq=2)])
    assert _statuses(won) == ["accepted"] and _statuses(lost) == ["rejected"]
    assert [w["op_id"] for w in lost["results"][0]["winning"]] == [won["results"][0]["op_id"]]


def test_log_safe_tools_follow_tools_json():
    """ops.LOG_SAFE_TOOLS is tools.json's log-safe edit tools (the app side is authoritative, C.9), in §5's order;
    a read marked logSafe (get_tunables today) never travels in the log."""
    doc = _tools()
    edits = [t["name"] for t in doc["tools"] if t["_meta"].get("com.truebex/logSafe") and t["_meta"]["com.truebex/permission"] == "edit"]
    assert list(ops.LOG_SAFE_TOOLS) == edits == ["place", "move", "resize", "fill", "apply_theme", "set_tunable"]
    assert not set(ops.LOG_SAFE_TOOLS) & ASSISTANT_ONLY and "get_tunables" not in ops.LOG_SAFE_TOOLS


# --- /developers/mcp/ -----------------------------------------------------------------------------


def test_docs_generator_keeps_the_mcp_surface(tmp_path):
    """src/lib/developer-docs.ts (run by node, types stripped): mcpTools() keeps a tool whose surfaces include
    mcp or that names none (absent = both), drops an assistant-only one; toolsDocument() gives the page the 13
    tools on the mcp surface of src/content/tools.json, in the file's order."""
    exe = node()
    if exe is None:
        pytest.skip("node is not installed")
    script = tmp_path / "surfaces.mjs"
    script.write_text(
        "const m = await import(process.argv[2]);\n"
        "const tool = (name, surfaces) => ({ name, _meta: surfaces ? { 'com.truebex/surfaces': surfaces } : {} });\n"
        "const sample = [tool('both'), tool('mcp', ['mcp']), tool('assistant', ['assistant']), tool('listed', ['mcp', 'assistant']), tool('empty', [])];\n"
        "console.log(JSON.stringify({ sample: m.mcpTools(sample).map((t) => t.name), page: m.toolsDocument().tools.map((t) => t.name) }));\n",
        encoding="utf-8",
    )
    entry = (ROOT / "src" / "lib" / "developer-docs.ts").as_uri()
    ran = subprocess.run(
        [exe, "--no-warnings", str(script), entry], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    assert ran.returncode == 0, ran.stderr
    got = json.loads(ran.stdout.strip().splitlines()[-1])
    # An empty list is not "absent": it names no surface, so the tool is on none (the app refuses such a file).
    assert got["sample"] == ["both", "mcp", "listed"]
    site = json.loads((ROOT / "src" / "content" / "tools.json").read_text(encoding="utf-8"))
    assert got["page"] == [t["name"] for t in on_mcp(site)] and len(got["page"]) == 13
    assert all("mcp" in surfaces_of(t) for t in site["tools"] if t["name"] in got["page"])


def test_docs_never_list_follows_the_contract(built):
    """agent-interface §6.3 (1.1.0): an agent never changes settings, except a tunable through set_tunable,
    which is typed and range-checked, one undo step for a Design tunable, and never a console command."""
    page = Doc((OUT / "developers" / "mcp" / "index.html").read_text(encoding="utf-8"))
    start = next(i for i, el in enumerate(page.elements) if el["tag"] == "h2" and page.text(el) == "What it never does")
    notes = []
    for el in page.elements[start + 1 :]:
        if el["tag"] == "h2":
            break
        if el["tag"] == "li":
            notes.append(page.text(el))
    joined = " ".join(notes)
    assert "run console commands" in joined
    settings = next(n for n in notes if "settings" in n)
    for phrase in (
        "cannot change settings, with one exception: a tunable",
        "set_tunable",
        "typed and range-checked",
        "a Design tunable",
        "one undo step",
        "never a console command",
    ):
        assert phrase in settings, (phrase, settings)
    assert "change settings or drive the interface" not in joined  # PF12b's flat rule, before TU1's exception
