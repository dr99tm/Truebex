"""PF12e: the platform follows agent-interface 1.4.0 (PL1's set_properties, §5.27: a room's code, name and type, a
storey's code and name, a door's or window's name, 1-200 items as one undo step). set_properties is log-safe, so the
project log takes it as an action (project-log.md §6.2) and ops.LOG_SAFE_TOOLS gains it. The push checks only that
its args.items is a list of 1-200 objects: the replica checks each item, as it checks every other tool's arguments
(place's kind is the one per-tool check the push makes). /developers/mcp/ documents it. The package and tools.json
checks are in test_pf12_mcp_package.py, the page's tables in test_site_pf12.py."""

import json
import subprocess

import pytest

from app.projects import ops

from .licence_helpers import error_of
from .pf12_helpers import PL, ROOT, kh, make_key, node
from .project_helpers import Person, action_op, create, hex32, pull, push, pushed
from .test_pf12d_agent_interface import _creation_op, _never_list
from .test_site_pf13 import OUT, Doc, built  # noqa: F401  (built is a fixture)

PKG = ROOT / "packages" / "mcp"
# A room name in Arabic ("bedroom"), written as code points: the log keeps it as the writer sent it.
ARABIC_NAME = "".join(chr(c) for c in (0x063A, 0x0631, 0x0641, 0x0629, 0x20, 0x0646, 0x0648, 0x0645))
ITEMS_FIELD = "ops[0].action.args.items"


def _tools() -> dict:
    return json.loads((PKG / "tools.json").read_text(encoding="utf-8"))


def _statuses(answer: dict) -> list[str]:
    return [r["status"] for r in answer["results"]]


def properties_op(author: str, items: list | None = None, *, args: dict | None = None, base_seq: int = 0) -> dict:
    """A light client's set_properties as a log `action` (§6.4's shape): `touched` the CL0 ids its targets name
    (project-log §6.2), sorted and unique."""
    args = {"items": items} if args is None else args
    refs = args.get("items") if isinstance(args.get("items"), list) else []
    ids = {i["target"].split("#", 1)[1] for i in refs if isinstance(i, dict) and len(i.get("target", "").split("#", 1)[-1]) == 32}
    op = action_op(author, sorted(ids), tool="set_properties", args=args, base_seq=base_seq)
    op["name"] = "Number rooms"
    return op


def _wire(action: dict) -> bytes:
    return json.dumps(action, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


# --- the project log ------------------------------------------------------------------------------


def test_project_log_accepts_set_properties_action(client):
    """agent-interface 1.4.0 §5.27 makes set_properties log-safe: a person's action with it (a light client's
    session), an agent's (the app's device, author_kind agent) and an API key's (/v1, as an agent) are accepted,
    stored, and pulled back byte-equal, the Arabic name included; touched is the rooms' ids."""
    a = Person(client, "a@example.com")
    pid = create(client, a.dev)["project_id"]
    rooms = [hex32() for _ in range(4)]
    person = properties_op(a.author_id, [{"target": f"room#{rooms[0]}", "props": {"code": "G.01"}}])
    assert person["touched"] == [rooms[0]] and person["action"]["permission"] == "edit"
    answer = pushed(client, a.web, pid, a.replica, [person])
    assert _statuses(answer) == ["accepted"] and answer["results"][0]["server_seq"] == 1
    # An agent's batch (author_kind agent, its session's own author id), from the app's device.
    batch = [
        {"target": f"room#{rooms[1]}", "props": {"code": "G.02", "name": ARABIC_NAME, "type": "bedroom"}},
        {"target": f"room#{rooms[2]}", "props": {"code": "G.03", "name": "Kitchen", "type": "kitchen"}},
    ]
    agent = dict(properties_op(hex32(), batch, base_seq=1), author_kind="agent")
    assert agent["touched"] == sorted(rooms[1:3])
    assert _statuses(pushed(client, a.dev, pid, a.replica, [agent])) == ["accepted"]
    # An API key pushes as an agent with the key's own author id (/v1 mirror of 5.6).
    key = make_key(client, a.session, ["projects:read", "projects:write"])
    keyed = properties_op(a.author_id, [{"target": f"room#{rooms[3]}", "props": {"name": "Store"}}], base_seq=2)
    del keyed["author"], keyed["author_kind"]
    res = client.post(f"/v1/projects/{pid}/ops", json={"replica_id": hex32(), "ops": [keyed]}, headers=kh(key, **PL))
    assert res.status_code == 200, res.text
    assert _statuses(res.json()) == ["accepted"]
    got = pull(client, a.dev, pid)["ops"]
    assert [o["server_seq"] for o in got] == [1, 2, 3]
    assert [o["author_kind"] for o in got] == ["person", "agent", "agent"]
    for sent, op in zip((person, agent, keyed), got):
        assert op["kind"] == "action" and op["action"]["tool"] == "set_properties"
        assert op["touched"] == sent["touched"] and op["name"] == "Number rooms"
        assert _wire(op["action"]) == _wire(sent["action"])  # byte-equal: keys, order and text as written
    assert got[1]["action"]["args"]["items"][0]["props"]["name"] == ARABIC_NAME


def test_project_log_checks_only_set_properties_items(client):
    """The decision (PF12e): the push checks that args.items is a list of 1-200 objects (§5.27's bound), and
    nothing inside an item: a target or prop the kind has no field for is the replica's to refuse (`invalid`, a
    no-op on every replica alike, project-log §6.2), as for any other tool's arguments. A maximal batch, 200 items
    with every string at its longest, fits the log's 64 KiB action."""
    a = Person(client, "a@example.com")
    pid = create(client, a.dev)["project_id"]
    item = {"target": f"room#{hex32()}", "props": {"code": "G.01"}}
    refused = {
        "no items": {},
        "an object, not a list": {"items": item},
        "no item": {"items": []},
        "201 items": {"items": [item] * 201},
        "a ref, not an object": {"items": [f"room#{hex32()}"]},
        "a null item": {"items": [item, None]},
    }
    for why, args in refused.items():
        body = error_of(push(client, a.web, pid, a.replica, [properties_op(a.author_id, args=args)]), 422, "validation_failed")
        field = body["data"]["fields"][0]
        assert field["field"] == ITEMS_FIELD, (why, body)
        assert "1 to 200" in field["message"] and "object" in field["message"], (why, field)
    assert pull(client, a.dev, pid)["head_seq"] == 0
    assert ops.SET_PROPERTIES_MAX_ITEMS == 200

    # Accepted as written: what only the replica can judge.
    loose = [
        {"target": f"storey#{hex32()}", "props": {"type": "bedroom"}},  # a storey has no type
        {"target": f"wall#{hex32()}", "props": {"name": "North"}},  # a wall has no settable property
        {"target": f"room#{hex32()}", "props": {}},  # empty props
        {"target": f"room#{hex32()}", "props": {"colour": "#E8E4DA"}},  # a prop tools.json does not have
        {"target": "selection", "props": {"code": "X"}},
    ]
    seq = 0
    for one in loose:
        answer = pushed(client, a.web, pid, a.replica, [properties_op(a.author_id, [one], base_seq=seq)])
        assert _statuses(answer) == ["accepted"], (one, answer)
        seq += 1
    # 200 rooms, every code, name and type at its maxLength (tools.json 1.4.0): under MAX_ACTION_BYTES, accepted.
    full = [
        {"target": f"room#{hex32()}", "props": {"code": "C" * 64, "name": "N" * 80, "type": "T" * 64}} for _ in range(200)
    ]
    big = properties_op(a.author_id, full, base_seq=seq)
    assert len(big["touched"]) == 200
    assert len(json.dumps(big["action"], separators=(",", ":")).encode()) <= ops.MAX_ACTION_BYTES
    assert _statuses(pushed(client, a.dev, pid, a.replica, [big])) == ["accepted"]
    stored = pull(client, a.dev, pid, after=seq)["ops"]
    assert len(stored) == 1 and stored[0]["action"]["args"]["items"] == full
    # Even with every target at a Ref's 64 characters the batch fits (the log measures the action's JSON).
    longest = dict(big["action"], args={"items": [dict(i, target="room#" + "9" * 59) for i in full]})
    assert len(json.dumps(longest, separators=(",", ":")).encode()) <= ops.MAX_ACTION_BYTES


def test_project_log_set_properties_conflicts_on_its_rooms(client):
    """touched is the rooms a batch names (§6.2): two replicas numbering the same room from the same base
    conflict (the second rejected, the first winning); a batch on other rooms does not."""
    a = Person(client, "a@example.com")
    pid = create(client, a.dev)["project_id"]
    phone, web = hex32(), hex32()
    room, other = hex32(), hex32()
    won = pushed(client, a.web, pid, phone, [properties_op(a.author_id, [{"target": f"room#{room}", "props": {"code": "G.01"}}])])
    lost = pushed(client, a.web, pid, web, [properties_op(a.author_id, [{"target": f"room#{room}", "props": {"code": "1.01"}}])])
    assert _statuses(won) == ["accepted"] and _statuses(lost) == ["rejected"]
    assert [w["op_id"] for w in lost["results"][0]["winning"]] == [won["results"][0]["op_id"]]
    apart = pushed(client, a.web, pid, web, [properties_op(a.author_id, [{"target": f"room#{other}", "props": {"code": "G.02"}}])])
    assert _statuses(apart) == ["accepted"]


def test_project_log_still_refuses_creation_beside_set_properties(client):
    """set_properties opens no door for AI5's tools: create_layout and remove stay refused (PF12d's test), and a
    push holding a set_properties and a remove is refused on the remove's index and stored in no part."""
    a = Person(client, "a@example.com")
    pid = create(client, a.dev)["project_id"]
    numbered = properties_op(a.author_id, [{"target": f"room#{hex32()}", "props": {"code": "G.01"}}])
    for tool in ("create_layout", "remove"):
        body = error_of(push(client, a.web, pid, a.replica, [numbered, _creation_op(a.author_id, tool)]), 422, "validation_failed")
        field = body["data"]["fields"][0]
        assert field["field"] == "ops[1].action.tool" and "set_properties" in field["message"], (tool, field)
    assert pull(client, a.dev, pid)["head_seq"] == 0


def test_log_safe_tools_gain_set_properties():
    """ops.LOG_SAFE_TOOLS gains set_properties after set_tunable (§5's order: 5.27 after 5.18), and the push's item
    bound is tools.json's."""
    assert ops.LOG_SAFE_TOOLS[-2:] == ("set_tunable", "set_properties")
    tool = next(t for t in _tools()["tools"] if t["name"] == "set_properties")
    assert tool["_meta"]["com.truebex/logSafe"] is True and tool["_meta"]["com.truebex/permission"] == "edit"
    items = tool["inputSchema"]["properties"]["items"]
    assert (items["minItems"], items["maxItems"]) == (1, ops.SET_PROPERTIES_MAX_ITEMS)


# --- the package and /developers/mcp/ -------------------------------------------------------------


def test_instructions_name_set_properties():
    """instructions.md 1.4.0 (the server's discover answer) tells an agent to number rooms in one call."""
    text = (PKG / "instructions.md").read_text(encoding="utf-8")
    line = next(ln for ln in text.splitlines() if "set_properties" in ln)
    assert "up to 200 rooms" in line and "one undo step" in line, line


def test_docs_generator_lists_set_properties_items(tmp_path):
    """src/lib/developer-docs.ts (run by node, types stripped): set_properties' rows are its three top-level
    arguments; under items, each item's fields, props' code, name and type as `props.code` … (PF12d's form for an
    array argument: the list reads "Each item:", so `props.code` is items[].props.code)."""
    exe = node()
    if exe is None:
        pytest.skip("node is not installed")
    script = tmp_path / "items.mjs"
    script.write_text(
        "const m = await import(process.argv[2]);\n"
        "const tool = m.toolsDocument().tools.find((t) => t.name === 'set_properties');\n"
        "const s = tool.inputSchema;\n"
        "console.log(JSON.stringify({\n"
        "  rows: m.argumentRows(s).map((r) => [r.name, r.required, m.typeOf(r.schema), m.rulesOf(r.schema)]),\n"
        "  items: m.nestedFields(s.properties.items).map((f) => [f.name, f.required, m.typeOf(f.schema), m.rulesOf(f.schema)]),\n"
        "  last: m.toolsDocument().tools.at(-1).name,\n"
        "}));\n",
        encoding="utf-8",
    )
    entry = (ROOT / "src" / "lib" / "developer-docs.ts").as_uri()
    ran = subprocess.run([exe, "--no-warnings", str(script), entry], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert ran.returncode == 0, ran.stderr
    got = json.loads(ran.stdout.strip().splitlines()[-1])
    assert got["last"] == "set_properties"
    assert got["rows"] == [
        ["items", True, "object[]", "1–200 items"],
        ["dry_run", False, "boolean", ""],
        ["request_id", False, "string", "≤ 32 chars"],
    ]
    assert got["items"] == [
        ["target", True, "string", "≤ 64 chars"],
        ["props", True, "object", ""],
        ["props.code", False, "string", "≤ 64 chars"],
        ["props.name", False, "string", "≤ 80 chars"],
        ["props.type", False, "string", "≤ 64 chars"],
    ]


def test_docs_set_properties_copy(built):
    """Where the page says what an agent may and may never do: set_properties sets the code, name and type of rooms
    (a storey's code and name, a door's or window's name) in batches of up to 200 as one undo step, all or nothing,
    and it is one of the edits that may travel in the project log. Its section says so too."""
    page = Doc((OUT / "developers" / "mcp" / "index.html").read_text(encoding="utf-8"))
    notes = _never_list(page)
    line = next(n for n in notes if "set_properties" in n)
    for phrase in (
        "set_properties sets the code, name and type of rooms",
        "the code and name of storeys, and the name of doors and windows",
        "in batches of up to 200 as one undo step",
        "every item applies, or nothing changes",
        "one of the edits that may also travel in the project log",
    ):
        assert phrase in line, (phrase, line)
    # PF12d's creation lines and the earlier rules stay.
    joined = " ".join(notes)
    assert "The remove tool deletes only what this connection created" in joined and "run console commands" in joined
    section = page.text(page.all("section", data_tool="set_properties")[0])
    assert "Class: edit" in section and "Also travels in the project log" in section
