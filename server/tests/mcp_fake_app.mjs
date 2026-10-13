// PF12b: runs the app's own fake (packages/mcp/test/fake-app.mjs, copied from
// the app repo's Tools/mcp/test/ by scripts/sync-mcp.ps1, never edited) as a
// process for the pytest package tests: prints one JSON line
// {pipe, token, instances, pid} and keeps the pipe open until stdin closes.
//
//   node server/tests/mcp_fake_app.mjs [--connections-off]

import { startFakeApp } from "../../packages/mcp/test/fake-app.mjs";

const app = await startFakeApp({ connectionsOff: process.argv.includes("--connections-off") });
process.stdout.write(JSON.stringify({ pipe: app.pipe, token: app.token, instances: app.instances, pid: process.pid }) + "\n");

let closing = false;
async function stop() {
  if (closing) return;
  closing = true;
  process.stderr.write(`fake-app: hellos=${app.hellos.length} calls=${app.calls.length} cancels=${app.cancels.length}\n`);
  await app.close();
  process.exit(0);
}
process.stdin.on("end", stop);
process.stdin.on("close", stop);
process.stdin.resume();
