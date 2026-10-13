# @truebex/mcp — the Truebex MCP server

Lets your own AI app (Claude Desktop, Claude Code or any MCP client that
launches a local stdio server) read and edit the project you have open in
Truebex: find walls, rooms and openings, explain an entity, place, move and
resize, set finishes, export the sheets as a PDF, and undo its own steps.
Eleven tools and three resources, listed even while Truebex is closed.

How it works: your client starts the server and speaks MCP with it over stdio
(one JSON-RPC message per line; logs go to stderr). The server answers
discovery and the tool and resource lists itself, and passes each tool call
and resource read to the running Truebex app over that app's private named
pipe (`\\.\pipe\truebex-agent-<pid>`, reachable by your Windows user only,
with a per-instance token). It never sees a Truebex sign-in, an API key or
your AI account's credentials, and nothing leaves your computer through it.

This package is the same server the Truebex app installs beside itself
(`<install>\MultiWindow\Tools\mcp\truebex-mcp.mjs`). Needs Node 20 or newer.

## Before you start

1. In Truebex: ribbon **Tools > AI > Agent**, then turn on **Allow AI apps to
   connect**. It is off by default and stays on until you turn it off.
2. The first time your AI app calls a tool, Truebex asks what it may do:
   **read**, **read + edit** or **read + edit + export** (or **Deny**), and
   waits up to 30 s for your answer. The answer lasts for that connection only;
   change or revoke it in the Agent panel at any time. Every call is listed
   there, every edit is one undo step (Ctrl+Z), and nothing can quit Truebex,
   delete a project or write outside the project's export folder.

## Claude Desktop

* **The extension:** in the Agent panel click **Install in Claude Desktop**, or
  open `truebex.mcpb` in the Truebex install folder
  (`<install>\MultiWindow\Tools\mcp\`). Claude Desktop shows its install dialog
  and brings its own Node.
* **Or by hand:** Claude Desktop > Settings > Developer > Edit Config, add the
  entry below to `%APPDATA%\Claude\claude_desktop_config.json`, then restart
  Claude Desktop:

```json
{ "mcpServers": { "truebex": { "command": "node", "args": ["<install>\\MultiWindow\\Tools\\mcp\\truebex-mcp.mjs"] } } }
```

  or, from npm: `{ "mcpServers": { "truebex": { "command": "npx", "args": ["-y", "@truebex/mcp"] } } }`.

## Claude Code

```
claude mcp add --scope user truebex -- node "<install>\MultiWindow\Tools\mcp\truebex-mcp.mjs"
```

or, from npm:

```
claude mcp add --scope user truebex -- npx -y @truebex/mcp
```

Then `/mcp` lists `truebex` with its eleven tools. With Truebex open and
connections on, ask "how many walls are on the ground floor?" and allow read
when Truebex asks: it answers through `find`.

## Any other MCP client

A stdio server with the command `node` and the argument
`<install>\MultiWindow\Tools\mcp\truebex-mcp.mjs` (the Agent panel shows the
exact path), or the command `npx -y @truebex/mcp`. MCP revisions 2026-07-28
(`server/discover`, metadata on every request) and the `initialize` handshake
of 2025-11-25 and 2025-06-18; capabilities: tools and resources.

## What it offers

* Tools (`tools.json` is the single source): `read_state`, `find`, `explain`
  (class read); `place`, `move`, `resize`, `fill`, `apply_theme`, `undo`
  (edit); `export_pdf`, `export_panorama` (export). `apply_theme` and
  `export_panorama` answer `feature_absent` until room themes and the panorama
  export arrive in Truebex. Reference: https://truebex.com/developers/mcp/.
* Resources: `truebex://state/digest`, `truebex://project/summary`,
  `truebex://entity/{kind}/{id}` (reading one needs the read class).
* With Truebex closed or connections off, a tool call answers the tool error
  `app_not_running` ("Truebex is not running, or Agent connections are off").

## Several Truebex windows

The server picks the newest running Truebex (a released build before a
development one). To pin one, set `TRUEBEX_AGENT_PIPE` and
`TRUEBEX_AGENT_TOKEN` in the client's server entry;
`%LOCALAPPDATA%\Truebex\agent\instances\<pid>.json` lists every running app's
pipe and token.

## For maintainers

Everything here except this README, `LICENSE` and `package.json` is copied
from the app repository's `Tools/mcp/` (and its wire fixture scripts) by
`scripts\sync-mcp.ps1`, never edited: a fix goes to the app first, then the
script. Run the bridge from a checkout with `node packages\mcp\truebex-mcp.mjs`
(the same file the `truebex-mcp` bin runs). The package tests are
`server/tests/test_pf12_mcp_package.py` (they also run the app's own
`node --test` on `test/`); `truebex.mcpb` is not in this package (it ships with
the app). Publish with `npm publish --access public` from this folder.
