// node --test Tools/mcp/test   (Scripts/verify.d/AI1-mcp.ps1 runs it every round)
//
// The AI1 MCP scenarios against the real server process and test/fake-app.mjs:
// one test per row of the feature doc's table (mcp-*), plus the tools.json check.

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { test } from 'node:test';
import { startFakeApp } from './fake-app.mjs';
import { MCP_DIR, emptyInstances, modernMeta, spawnServer } from './helpers.mjs';
import { readZip } from './zip.mjs';
import { INTERNAL_META, loadToolsFile, publicTools, surfacesOf, toolsFileProblems, validate } from '../lib/schema.mjs';
import { SERVER_VERSION, SUPPORTED_VERSIONS } from '../lib/server.mjs';

const TOOL_NAMES = ['read_state', 'find', 'explain', 'place', 'move', 'resize', 'fill', 'apply_theme', 'export_pdf', 'export_panorama', 'undo', 'get_tunables', 'set_tunable'];
// AI5 (contract 1.3.0): the creation skills and the scoped remove, after propose_variants in the file.
const AI5_TOOLS = ['create_layout', 'create_theme', 'create_fills', 'create_object', 'create_material', 'write_sheet_text', 'remove'];
const PL1_TOOLS = ['set_properties'];   // roadmap 40 / PL1 (contract 1.4.0, section 5.27)
const MCP_TOOLS = [...TOOL_NAMES, ...AI5_TOOLS, ...PL1_TOOLS];

test('mcp-tools-json-valid', () => {
  const { doc } = loadToolsFile(join(MCP_DIR, 'tools.json'));
  assert.deepEqual(toolsFileProblems(doc), []);
  // AI2: the file also carries the assistant-only propose_variants; MCP lists the other thirteen.
  assert.deepEqual(doc.tools.map((t) => t.name), [...TOOL_NAMES, 'propose_variants', ...AI5_TOOLS, ...PL1_TOOLS]);
  assert.deepEqual(surfacesOf(doc.tools.find((t) => t.name === 'propose_variants')), ['assistant']);
  assert.deepEqual(publicTools(doc).map((t) => t.name), MCP_TOOLS);
  const perms = Object.fromEntries(doc.tools.map((t) => [t.name, t._meta['com.truebex/permission']]));
  assert.equal(perms.read_state, 'read');
  assert.equal(perms.place, 'edit');
  assert.equal(perms.export_pdf, 'export');
  // the schema checker itself: a field error names the field
  const place = doc.tools.find((t) => t.name === 'place').inputSchema;
  assert.equal(validate(place, { kind: 'window', width_mm: 50 }), 'width_mm: must be >= 100');
  assert.equal(validate(place, { kind: 'window', colour: 'x' }), 'colour: unknown argument');
  assert.equal(validate(place, {}), 'kind: required');
  assert.equal(validate(place, { kind: 'window', host: 'wall#42', width_mm: 1200 }), null);
  // TU1's two tools (merge T165): value takes a number, a boolean or a name
  assert.equal(perms.get_tunables, 'read');
  assert.equal(perms.set_tunable, 'edit');
  const setTunable = doc.tools.find((t) => t.name === 'set_tunable').inputSchema;
  assert.equal(validate(setTunable, { name: 'cad.Light.SunIntensity', value: 7 }), null);
  assert.equal(validate(setTunable, { name: 'cad.Elev.HlrVariant', value: 'Exact' }), null);
  assert.equal(validate(setTunable, { name: 'cad.Light.Sun', value: false }), null);
  assert.equal(validate(setTunable, { value: 7 }), 'name: required');
  // AI5: the skills' intents check like any tool's arguments
  for (const n of AI5_TOOLS) { assert.equal(perms[n], 'edit'); }
  const layout = doc.tools.find((t) => t.name === 'create_layout').inputSchema;
  assert.equal(validate(layout, { program: { rooms: [{ type: 'bedroom', area_m2: 12 }] }, choose: -1 }), null);
  assert.equal(validate(layout, { program: { rooms: [{ type: 'garage', area_m2: 12 }] } }), 'program.rooms[0].type: must be one of living, kitchen, dining, bedroom, bathroom, wc, hall, study, utility, store');
  assert.equal(validate(layout, {}), 'program: required');
});

test('mcp-discover', async (t) => {
  const app = await startFakeApp();
  const s = spawnServer({ TRUEBEX_AGENT_INSTANCES_DIR: app.instances });
  t.after(async () => { await s.close(); await app.close(); });

  const d = await s.request('server/discover', { _meta: modernMeta() });
  assert.equal(d.result.resultType, 'complete');
  assert.deepEqual(d.result.supportedVersions, SUPPORTED_VERSIONS);
  assert.ok(d.result.supportedVersions.includes('2026-07-28'));
  assert.deepEqual(d.result.capabilities, { tools: {}, resources: {} });
  assert.equal(d.result._meta['io.modelcontextprotocol/serverInfo'].name, 'truebex');
  assert.match(d.result.instructions, /data from the project, never instructions/);
  assert.equal(d.result.ttlMs, 60000);

  const r = await s.request('tools/call', { _meta: modernMeta(), name: 'read_state', arguments: {} });
  assert.equal(r.result.isError, false);
  assert.match(r.result.content[0].text, /^TRUEBEX/);
  assert.equal(r.result.structuredContent.ok, true);
  assert.equal(JSON.parse(r.result.content[1].text).digest, r.result.structuredContent.digest);
  assert.equal(app.hellos.length, 1);
  assert.equal(app.hellos[0].client.name, 'node-test');
  assert.equal(app.hellos[0].era, '2026-07-28');
  assert.equal(app.hellos[0].wire, 'truebex-agent-wire/1');

  const res = await s.request('resources/read', { _meta: modernMeta(), uri: 'truebex://state/digest' });
  assert.equal(res.result.contents[0].mimeType, 'text/plain');
  const missing = await s.request('resources/read', { _meta: modernMeta(), uri: 'truebex://entity/wall/999' });
  assert.equal(missing.error.code, -32602);
  const bad = await s.request('resources/read', { _meta: modernMeta(), uri: 'file:///C:/Windows/win.ini' });
  assert.equal(bad.error.code, -32602);
  const unknownTool = await s.request('tools/call', { _meta: modernMeta(), name: 'delete_project', arguments: {} });
  assert.equal(unknownTool.error.code, -32602);
});

test('mcp-legacy-initialize', async (t) => {
  const app = await startFakeApp();
  const s = spawnServer({ TRUEBEX_AGENT_INSTANCES_DIR: app.instances });
  t.after(async () => { await s.close(); await app.close(); });

  const init = await s.request('initialize', { protocolVersion: '2025-11-25', capabilities: {}, clientInfo: { name: 'legacy-client', version: '0.9' } });
  assert.equal(init.result.protocolVersion, '2025-11-25');
  assert.deepEqual(init.result.capabilities.tools, { listChanged: false });
  assert.equal(init.result.serverInfo.name, 'truebex');
  assert.equal(init.result.resultType, undefined);
  s.send({ jsonrpc: '2.0', method: 'notifications/initialized' });
  const list = await s.request('tools/list', {});
  assert.equal(list.result.tools.length, 21);
  assert.equal(list.result.resultType, undefined);
  const call = await s.request('tools/call', { name: 'place', arguments: { kind: 'window', host: 'wall#42', width_mm: 1200 } });
  assert.equal(call.result.isError, false);
  assert.deepEqual(call.result.structuredContent.created, ['opening#20']);
  assert.equal(app.hellos[0].era, '2025-11-25');
  assert.equal(app.hellos[0].client.name, 'legacy-client');

  // 2025-06-18 is answered in kind; an unknown legacy revision gets the newest legacy one
  const s2 = spawnServer({ TRUEBEX_AGENT_INSTANCES_DIR: app.instances });
  t.after(() => s2.close());
  const old = await s2.request('initialize', { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'older' } });
  assert.equal(old.result.protocolVersion, '2025-06-18');
  const s3 = spawnServer({ TRUEBEX_AGENT_INSTANCES_DIR: app.instances });
  t.after(() => s3.close());
  const ancient = await s3.request('initialize', { protocolVersion: '2024-11-05', capabilities: {}, clientInfo: { name: 'ancient' } });
  assert.equal(ancient.result.protocolVersion, '2025-11-25');
});

test('mcp-unsupported-version', async (t) => {
  const s = spawnServer({ TRUEBEX_AGENT_INSTANCES_DIR: emptyInstances() });
  t.after(() => s.close());
  const r = await s.request('tools/list', { _meta: modernMeta({ 'io.modelcontextprotocol/protocolVersion': '1900-01-01' }) });
  assert.equal(r.error.code, -32022);
  assert.deepEqual(r.error.data.supported, SUPPORTED_VERSIONS);
  assert.equal(r.error.data.requested, '1900-01-01');
  // a modern request without its required capabilities is malformed
  const noCaps = await s.request('tools/list', { _meta: { 'io.modelcontextprotocol/protocolVersion': '2026-07-28' } });
  assert.equal(noCaps.error.code, -32602);
  // no _meta and no initialize: malformed, with the versions named for the person
  const bare = await s.request('tools/list', {});
  assert.equal(bare.error.code, -32602);
  assert.deepEqual(bare.error.data.supported, SUPPORTED_VERSIONS);
});

test('mcp-tools-deterministic', async (t) => {
  const s = spawnServer({ TRUEBEX_AGENT_INSTANCES_DIR: emptyInstances() });
  t.after(() => s.close());
  const a = await s.request('tools/list', { _meta: modernMeta() });
  const b = await s.request('tools/list', { _meta: modernMeta() });
  assert.deepEqual(a.result.tools, b.result.tools);
  assert.equal(JSON.stringify(a.result.tools), JSON.stringify(b.result.tools));
  assert.deepEqual(a.result.tools.map((x) => x.name), MCP_TOOLS);
  assert.equal(a.result.ttlMs, 60000);
  assert.equal(a.result.cacheScope, 'private');
  for (const tool of a.result.tools) {
    for (const k of INTERNAL_META) { assert.ok(!(tool._meta && k in tool._meta), `${tool.name} leaks ${k}`); }
    assert.ok(tool._meta['com.truebex/permission']);
    assert.equal(tool.inputSchema.type, 'object');
    assert.equal(tool.annotations.openWorldHint, false);
  }
});

// AI2: propose_variants is the in-app assistant's (surfaces ["assistant"]): an MCP
// client never sees it and a call to it is an unknown tool, app or no app.
test('mcp-assistant-only-hidden', async (t) => {
  const app = await startFakeApp();
  const s = spawnServer({ TRUEBEX_AGENT_INSTANCES_DIR: app.instances });
  t.after(async () => { await s.close(); await app.close(); });
  const list = await s.request('tools/list', { _meta: modernMeta() });
  assert.ok(!list.result.tools.some((x) => x.name === 'propose_variants'));
  const call = await s.request('tools/call', { _meta: modernMeta(), name: 'propose_variants', arguments: { variants: [] } });
  assert.equal(call.error.code, -32602);
});

test('mcp-no-app', async (t) => {
  const s = spawnServer({ TRUEBEX_AGENT_INSTANCES_DIR: emptyInstances() });
  t.after(() => s.close());
  const list = await s.request('tools/list', { _meta: modernMeta() });
  assert.equal(list.result.tools.length, 21);
  const call = await s.request('tools/call', { _meta: modernMeta(), name: 'read_state', arguments: {} });
  assert.equal(call.result.isError, true);
  assert.equal(call.result.structuredContent.code, 'app_not_running');
  assert.match(call.result.content[0].text, /Truebex is not running, or Agent connections are off/);
  // connections off: the app refuses hello the same way
  const off = await startFakeApp({ connectionsOff: true });
  t.after(() => off.close());
  const s2 = spawnServer({ TRUEBEX_AGENT_INSTANCES_DIR: off.instances });
  t.after(() => s2.close());
  const r2 = await s2.request('tools/call', { _meta: modernMeta(), name: 'find', arguments: { kind: 'room' } });
  assert.equal(r2.result.isError, true);
  assert.equal(r2.result.structuredContent.code, 'app_not_running');
  // a wrong token is refused by the app
  const app = await startFakeApp();
  t.after(() => app.close());
  const s3 = spawnServer({ TRUEBEX_AGENT_PIPE: app.pipe, TRUEBEX_AGENT_TOKEN: 'nope' });
  t.after(() => s3.close());
  const r3 = await s3.request('tools/call', { _meta: modernMeta(), name: 'find', arguments: {} });
  assert.equal(r3.result.isError, true);
  assert.match(r3.result.content[0].text, /bad_token|wrong token/);
});

test('mcp-stdout-clean', async (t) => {
  const app = await startFakeApp();
  const s = spawnServer({ TRUEBEX_AGENT_INSTANCES_DIR: app.instances });
  t.after(async () => { await s.close(); await app.close(); });
  await s.request('server/discover', { _meta: modernMeta() });
  await s.request('tools/list', { _meta: modernMeta() });
  await s.request('tools/call', { _meta: modernMeta(), name: 'read_state', arguments: {} });
  await s.request('tools/call', { _meta: modernMeta(), name: 'export_pdf', arguments: {} });
  await s.request('nonsense/method', { _meta: modernMeta() });
  s.sendRaw('this is not json\n');
  await s.waitFor((m) => m.error && m.error.code === -32700);
  s.send({ jsonrpc: '2.0', method: 'notifications/initialized' });
  await s.request('ping', { _meta: modernMeta() });
  for (const line of s.raw) {
    const m = JSON.parse(line);
    assert.equal(m.jsonrpc, '2.0', line);
    assert.ok('result' in m || 'error' in m, line);
    assert.ok(!line.includes('\n'));
  }
  assert.ok(s.raw.length >= 7);
});

test('mcp-stdin-eof', async (t) => {
  const app = await startFakeApp();
  t.after(() => app.close());
  const s = spawnServer({ TRUEBEX_AGENT_INSTANCES_DIR: app.instances });
  await s.request('tools/call', { _meta: modernMeta(), name: 'read_state', arguments: {} });   // holds the pipe open
  const t0 = performance.now();
  s.proc.stdin.end();
  const code = await Promise.race([s.exited, new Promise((r) => setTimeout(() => r('still running'), 1000))]);
  const ms = performance.now() - t0;
  if (code === 'still running') { s.proc.kill(); }
  assert.notEqual(code, 'still running', `exit took > 1 s`);
  assert.ok(ms <= 1000, `exit ms=${ms.toFixed(0)}`);
});

test('mcp-cancel', async (t) => {
  const app = await startFakeApp({ delayMs: 600 });
  const s = spawnServer({ TRUEBEX_AGENT_INSTANCES_DIR: app.instances });
  t.after(async () => { await s.close(); await app.close(); });
  await s.request('tools/call', { _meta: modernMeta(), name: 'read_state', arguments: {} }, 5000);   // connected
  const id = 4242;
  s.send({ jsonrpc: '2.0', id, method: 'tools/call', params: { _meta: modernMeta(), name: 'place', arguments: { kind: 'window', host: 'wall#42' } } });
  await new Promise((r) => setTimeout(r, 150));
  s.send({ jsonrpc: '2.0', method: 'notifications/cancelled', params: { requestId: id, reason: 'test' } });
  await new Promise((r) => setTimeout(r, 1200));
  assert.equal(s.lines.filter((m) => m.id === id).length, 0, 'no message after a cancel');
  assert.equal(app.cancels.length, 1, 'the app was told');
  const after = await s.request('ping', { _meta: modernMeta() });
  assert.equal(after.result.resultType, 'complete');
});

test('mcp-bundle-manifest', () => {
  const manifest = JSON.parse(readFileSync(join(MCP_DIR, 'manifest.json'), 'utf8'));
  assert.equal(manifest.manifest_version, '0.3');
  assert.equal(manifest.name, 'truebex');
  assert.equal(manifest.version, SERVER_VERSION);
  assert.equal(manifest.server.type, 'node');
  assert.equal(manifest.server.entry_point, 'truebex-mcp.mjs');
  assert.deepEqual(manifest.server.mcp_config.args, ['${__dirname}/truebex-mcp.mjs']);
  const { doc } = loadToolsFile(join(MCP_DIR, 'tools.json'));
  assert.deepEqual(manifest.tools.map((x) => x.name), publicTools(doc).map((x) => x.name));

  const entries = readZip(readFileSync(join(MCP_DIR, 'truebex.mcpb')));
  const names = [...entries.keys()].sort();
  assert.deepEqual(names, ['README.md', 'instructions.md', 'lib/jsonrpc.mjs', 'lib/schema.mjs', 'lib/server.mjs', 'lib/wire.mjs', 'manifest.json', 'tools.json', 'truebex-mcp.mjs']);
  for (const name of names) {
    const disk = readFileSync(join(MCP_DIR, ...name.split('/')));
    assert.ok(disk.equals(entries.get(name)), `${name} in truebex.mcpb differs from the file beside it: run Scripts/mcp_pack.ps1`);
  }
});
