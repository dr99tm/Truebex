"""The MCP package (PF12; agent-interface.md §10's platform tests): the bridge
of §6.6 started with node, alone, against a fake app pipe that answers the
fixture scripts of §9."""

import json
import os
import queue
import subprocess
import threading
import uuid
from pathlib import Path

import pytest

from .pf12_helpers import ROOT, node

PKG = ROOT / "packages" / "mcp"
FIXTURES = PKG / "test" / "fixtures"
MASK = "<masked>"
SUPPORTED = ["2026-07-28", "2025-11-25", "2025-06-18"]
CONTRACT_ORDER = [
    "read_state", "find", "explain", "place", "move", "resize", "fill", "apply_theme", "export_pdf", "export_panorama", "undo",
]
ALLOWED_KEYWORDS = {
    "type", "properties", "required", "additionalProperties", "enum", "const", "minimum", "maximum", "minLength",
    "maxLength", "pattern", "items", "minItems", "maxItems", "description", "default",
}

pytestmark = pytest.mark.skipif(node() is None, reason="node is not installed")


def _pipe_name() -> str:
    if os.name == "nt":
        return rf"\\.\pipe\truebex-agent-test-{uuid.uuid4().hex}"
    return str(Path(os.environ.get("TMPDIR", "/tmp")) / f"truebex-agent-test-{uuid.uuid4().hex}.sock")


class Bridge:
    """`node bin/truebex-mcp.js` with its stdout read line by line."""

    def __init__(self, pipe: str) -> None:
        env = {**os.environ, "TRUEBEX_AGENT_PIPE": pipe}
        self.proc = subprocess.Popen(
            [node(), str(PKG / "bin" / "truebex-mcp.js")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, cwd=PKG,
        )
        self.lines: queue.Queue = queue.Queue()
        self.raw = bytearray()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        for line in self.proc.stdout:
            self.raw += line
            self.lines.put(line)
        self.lines.put(None)

    def send(self, message) -> None:
        data = message if isinstance(message, bytes) else (json.dumps(message) + "\n").encode()
        self.proc.stdin.write(data)
        self.proc.stdin.flush()

    def answer(self, timeout: float = 10) -> dict:
        line = self.lines.get(timeout=timeout)
        assert line is not None, "the bridge closed stdout"
        assert line.endswith(b"\n") and line.count(b"\n") == 1
        return json.loads(line)

    def close(self, timeout: float = 10) -> int:
        self.proc.stdin.close()
        return self.proc.wait(timeout=timeout)


class FakePipe:
    def __init__(self, script: Path) -> None:
        self.name = _pipe_name()
        self.proc = subprocess.Popen(
            [node(), str(PKG / "test" / "fake-pipe.mjs"), "--pipe", self.name, "--script", str(script)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=PKG,
        )
        ready = self.proc.stdout.readline()
        assert ready.strip() == b"ready", self.proc.stderr.read()

    def stop(self) -> None:
        self.proc.stdin.close()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def matches(expected, actual, where: str = "") -> None:
    """`expected` with "<masked>" for volatile values; dicts must have the same keys."""
    if expected == MASK:
        return
    if isinstance(expected, dict):
        assert isinstance(actual, dict), where
        assert set(expected) <= set(actual), f"{where}: missing {set(expected) - set(actual)}"
        for k, v in expected.items():
            matches(v, actual[k], f"{where}.{k}")
    else:
        assert expected == actual, f"{where}: {expected!r} != {actual!r}"


def _tools() -> dict:
    return json.loads((PKG / "tools.json").read_text(encoding="utf-8"))


# --- §10 platform tests ------------------------------------------------------------------------


def test_mcp_package_stdio_framing():
    bridge = Bridge(_pipe_name())
    bridge.send({"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert bridge.answer() == {"jsonrpc": "2.0", "id": 1, "result": {}}
    # A pretty-printed request is not a line: a parse error, and the stream goes on.
    bridge.send(b'{"jsonrpc": "2.0",\n"id": 2, "method": "ping"}\n')
    first = bridge.answer()
    assert first["error"]["code"] == -32700 and first["id"] is None
    bridge.answer()  # the second half of it
    # Batches are not JSON-RPC in these revisions; one object per line.
    bridge.send([{"jsonrpc": "2.0", "id": 3, "method": "ping"}])
    assert bridge.answer()["error"]["code"] == -32600
    bridge.send({"jsonrpc": "2.0", "id": 4, "method": "tools/list"})
    big = bridge.answer()
    assert len(big["result"]["tools"]) == 11  # a long answer is still one line
    bridge.send({"jsonrpc": "2.0", "id": 5, "method": "resources/list"})
    assert bridge.answer()["error"]["code"] == -32601  # tools only
    # Exits when stdin closes; stdout held nothing but those messages, logs went to stderr.
    assert bridge.close() == 0
    lines = bridge.raw.decode("utf-8").splitlines()
    assert len(lines) == 6 and all(json.loads(l)["jsonrpc"] == "2.0" for l in lines)
    assert b"truebex-mcp" in bridge.proc.stderr.read()


def test_mcp_package_discover_and_legacy_initialize():
    bridge = Bridge(_pipe_name())
    meta = {
        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
        "io.modelcontextprotocol/clientCapabilities": {},
        "io.modelcontextprotocol/clientInfo": {"name": "pytest", "version": "1"},
    }
    bridge.send({"jsonrpc": "2.0", "id": 1, "method": "server/discover", "params": {"_meta": meta}})
    found = bridge.answer()["result"]
    assert found["resultType"] == "complete" and found["supportedVersions"] == SUPPORTED
    assert found["capabilities"] == {"tools": {"listChanged": False}} and found["serverInfo"]["name"] == "truebex"
    for version in ("2025-11-25", "2025-06-18"):
        bridge.send({"jsonrpc": "2.0", "id": version, "method": "initialize",
                     "params": {"protocolVersion": version, "capabilities": {}, "clientInfo": {"name": "c", "version": "1"}}})
        got = bridge.answer()
        assert got["id"] == version and got["result"]["protocolVersion"] == version
        assert got["result"]["capabilities"] == {"tools": {"listChanged": False}}
    # An unknown legacy revision gets the newest legacy one; an unserved modern one is -32022.
    bridge.send({"jsonrpc": "2.0", "id": 9, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}}})
    assert bridge.answer()["result"]["protocolVersion"] == "2025-11-25"
    bridge.send({"jsonrpc": "2.0", "id": 10, "method": "tools/list",
                 "params": {"_meta": {**meta, "io.modelcontextprotocol/protocolVersion": "2099-01-01"}}})
    err = bridge.answer()["error"]
    assert err["code"] == -32022 and err["data"]["supported"] == SUPPORTED
    assert bridge.close() == 0


def test_mcp_package_tools_list_and_replay():
    # tools/list is tools.json, with the app closed.
    bridge = Bridge(_pipe_name())
    bridge.send({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    listed = bridge.answer()["result"]
    assert listed["tools"] == _tools()["tools"]
    assert listed["ttlMs"] == 3600000 and listed["cacheScope"] == "private"
    # app_not_running with no pipe; an unknown tool never reaches the app.
    bridge.send({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "find", "arguments": {}}})
    res = bridge.answer()["result"]
    assert res["isError"] is True and res["structuredContent"]["code"] == "app_not_running"
    bridge.send({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "quit_app", "arguments": {}}})
    assert bridge.answer()["error"]["code"] == -32602
    assert bridge.close() == 0

    # Every fixture script replays: requests in, the expected answers out.
    scripts = sorted(FIXTURES.glob("*.jsonl"))
    names = {s.stem for s in scripts}
    assert {"window-north-study", "permissions", "fence", "legacy-initialize", "app-not-running"} <= names
    for script in scripts:
        rows = [json.loads(l) for l in script.read_text(encoding="utf-8").splitlines() if l.strip()]
        fake = None if script.stem == "app-not-running" else FakePipe(script)
        bridge = Bridge(fake.name if fake else _pipe_name())
        try:
            for i, row in enumerate(rows):
                bridge.send(row["request"])
                if row.get("answer") is not None:
                    matches(row["answer"], bridge.answer(), f"{script.stem}[{i}]")
            assert bridge.close() == 0, script.stem
            assert bridge.lines.get(timeout=5) is None, f"{script.stem}: an answer nobody asked for"
        finally:
            if fake:
                fake.stop()


# --- tools.json ---------------------------------------------------------------------------------


def _walk(schema: dict, where: str, inside_input: bool) -> None:
    unknown = set(schema) - ALLOWED_KEYWORDS
    assert not unknown, f"{where}: {unknown} (agent-interface §6.5)"
    if schema.get("type") == "object" and inside_input:
        assert schema.get("additionalProperties") is False, where
    for name, sub in (schema.get("properties") or {}).items():
        _walk(sub, f"{where}.{name}", inside_input)
    if isinstance(schema.get("items"), dict):
        _walk(schema["items"], f"{where}[]", inside_input)


def test_tools_json_follows_the_contract():
    doc = _tools()
    assert doc["version"] == "1.0.0"
    assert [t["name"] for t in doc["tools"]] == CONTRACT_ORDER
    classes = {t["name"]: t["_meta"]["com.truebex/permission"] for t in doc["tools"]}
    assert {n for n, c in classes.items() if c == "read"} == {"read_state", "find", "explain"}
    assert {n for n, c in classes.items() if c == "export"} == {"export_pdf", "export_panorama"}
    log_safe = {t["name"] for t in doc["tools"] if t["_meta"]["com.truebex/logSafe"]}
    assert log_safe == {"place", "move", "resize", "fill", "apply_theme"}  # project-log §6.2
    for t in doc["tools"]:
        assert t["title"] and t["description"] and t["annotations"]["destructiveHint"] is False
        assert t["annotations"]["readOnlyHint"] == (classes[t["name"]] == "read")
        _walk(t["inputSchema"], f"{t['name']}.inputSchema", True)
        _walk(t["outputSchema"], f"{t['name']}.outputSchema", False)
        if classes[t["name"]] != "read":
            assert t["inputSchema"]["properties"]["request_id"] == {"type": "string", "pattern": "^[0-9a-f]{32}$"}, t["name"]


def test_site_copy_of_tools_json_is_the_package_one():
    """src/content/tools.json (the /developers/mcp/ page reads it) is a copy, never edited."""
    site = (ROOT / "src" / "content" / "tools.json").read_text(encoding="utf-8")
    assert json.loads(site) == _tools()


def test_mcp_package_install_notes():
    pkg = json.loads((PKG / "package.json").read_text(encoding="utf-8"))
    assert pkg["name"] == "@truebex/mcp" and pkg["bin"] == {"truebex-mcp": "bin/truebex-mcp.js"}
    assert set(pkg["files"]) >= {"bin", "server.js", "tools.json"} and not pkg.get("dependencies")
    readme = (PKG / "README.md").read_text(encoding="utf-8")
    for line in (
        '"truebex": {',
        '"command": "npx"',
        '"args": ["-y", "@truebex/mcp"]',
        "claude mcp add --scope user truebex -- npx -y @truebex/mcp",
        "truebex-mcp.exe",
    ):
        assert line in readme, line
    sync = (ROOT / "scripts" / "sync-mcp.ps1").read_text(encoding="utf-8")
    assert "Tools\\mcp" in sync and "src\\content\\tools.json" in sync
