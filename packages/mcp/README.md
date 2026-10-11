# @truebex/mcp — the Truebex MCP server

Lets an MCP client (a desktop AI assistant, a coding agent, any client that
launches MCP servers over stdio) read and edit the model open in the Truebex
desktop app: find walls, rooms and products, explain an entity, place, move and
resize, set finishes, apply room themes, export the sheets or a panorama, and
undo its own steps. Eleven tools, listed even while the app is closed.

How it works: the client starts `truebex-mcp` and speaks MCP over stdio (one
JSON-RPC message per line). The server answers `server/discover`, `initialize`
and `tools/list` itself and passes each tool call to the running app over a
per-user named pipe (`\\.\pipe\truebex-agent-<USERNAME>`). The app asks you to
allow each kind of action (read, edit, export) in its Agent panel, runs every
call as one undoable step and lists it. The server never sees a Truebex sign-in
or API key, and nothing leaves your computer through it.

Requires the Truebex app with the Agent panel, and Node 18 or later for `npx`
(the app also installs `truebex-mcp.exe`, which needs no Node).

## Install

### Claude Desktop

Add an entry to `mcpServers` in its config file (Settings → Developer → Edit
Config, `claude_desktop_config.json`), then restart it:

```json
{
  "mcpServers": {
    "truebex": {
      "command": "npx",
      "args": ["-y", "@truebex/mcp"]
    }
  }
}
```

Or point `command` at the installed `truebex-mcp.exe`: the Agent panel in
Truebex shows its full path, ready to paste.

### Claude Code

```bash
claude mcp add --scope user truebex -- npx -y @truebex/mcp
```

Then `/mcp` lists `truebex` with its eleven tools. With the app open, ask
"how many walls are on the ground floor?" and it answers through `find`.

### Any other MCP client

Launch the same command over stdio: `npx -y @truebex/mcp` (or the path of
`truebex-mcp.exe`). Protocol revisions: 2026-07-28 (`server/discover`) and the
`initialize` handshake of 2025-11-25 and 2025-06-18. Capabilities: tools only.

## The tools

`read_state`, `find`, `explain` (read) · `place`, `move`, `resize`, `fill`,
`apply_theme`, `undo` (edit) · `export_pdf`, `export_panorama` (export). Their
schemas are in `tools.json`; the reference is at
https://truebex.com/developers/mcp/.

When the app is not running, a tool call answers `app_not_running`. A call that
needs a permission you have not granted answers `permission_required` while the
app asks you; the client retries after you choose.

## For maintainers

`server.js` and `tools.json` are copied from the app repository's `Tools/mcp/`
at each app release by `scripts/sync-mcp.ps1`, never edited here; a fix goes to
the app first. `test/fake-pipe.mjs` stands in for the app in the package tests
(`server/tests/test_pf12_mcp_package.py`). Publish with `npm publish --access public`
from this folder.
