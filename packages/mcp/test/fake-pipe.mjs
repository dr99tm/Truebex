// The app's side of the pipe, faked from a fixture script (agent-interface §9):
// PF12's package tests replay each script through the bridge and this answers
// the lines the bridge relays (tools/call of a known tool, cancellations) in
// order, with the script's expected answer. A relayed line that differs from
// the script's request is answered with a JSON-RPC error, so the test fails.
//
//   node test/fake-pipe.mjs --pipe \\.\pipe\truebex-agent-test-1 --script test/fixtures/permissions.jsonl
//
// Prints "ready" on stdout once it listens; writes what it received to --log.
import fs from "node:fs";
import net from "node:net";
import path from "node:path";
import readline from "node:readline";
import { fileURLToPath } from "node:url";

const args = Object.fromEntries(
  process.argv.slice(2).reduce((pairs, arg, i, all) => (arg.startsWith("--") ? [...pairs, [arg.slice(2), all[i + 1]]] : pairs), []),
);
const here = path.dirname(fileURLToPath(import.meta.url));
const tools = JSON.parse(fs.readFileSync(path.join(here, "..", "tools.json"), "utf8")).tools.map((t) => t.name);
const lines = fs
  .readFileSync(args.script, "utf8")
  .split(/\r?\n/)
  .filter((l) => l.trim())
  .map((l) => JSON.parse(l));
const relayed = lines.filter(
  ({ request }) =>
    (request.method === "tools/call" && tools.includes(request.params?.name)) || request.method === "notifications/cancelled",
);
const received = [];
let next = 0;

function same(a, b) {
  return JSON.stringify(a) === JSON.stringify(b);
}

const server = net.createServer((socket) => {
  socket.setEncoding("utf8");
  readline.createInterface({ input: socket, crlfDelay: Infinity }).on("line", (line) => {
    if (!line.trim()) return;
    const message = JSON.parse(line);
    received.push(message);
    if (args.log) fs.writeFileSync(args.log, JSON.stringify(received));
    const entry = relayed[next++];
    if (!entry || !same(message, entry.request)) {
      if (message.id !== undefined) {
        socket.write(
          JSON.stringify({
            jsonrpc: "2.0",
            id: message.id,
            error: { code: -32603, message: "fake pipe: not the script's next request", data: { expected: entry?.request ?? null, got: message } },
          }) + "\n",
        );
      }
      return;
    }
    if (entry.answer) socket.write(JSON.stringify(entry.answer) + "\n");
  });
});
server.listen(args.pipe, () => process.stdout.write("ready\n"));
process.stdin.on("end", () => server.close(() => process.exit(0)));
process.stdin.resume();
