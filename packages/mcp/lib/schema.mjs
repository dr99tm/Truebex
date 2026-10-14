// Truebex MCP server (roadmap 40 / AI1): tools.json (schema truebex-tools/1) and
// the PORTABLE JSON Schema subset every tool schema keeps to, so one file passes
// MCP (JSON Schema 2020-12) and every model provider adapter of AI2 / AI3
// unchanged (contract agent-interface.md 6.5). The app validates each call
// against the same subset (TruebexAgent's AgentToolsFile.cpp); this copy serves
// the tests and the bundled fallback list.

import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';

export const TOOLS_SCHEMA = 'truebex-tools/1';

/** The keywords a schema may use. No $ref, oneOf, anyOf, allOf, if/then/else, pattern. */
export const PORTABLE_KEYWORDS = new Set([
  'type', 'description', 'properties', 'required', 'additionalProperties', 'enum', 'const',
  'minimum', 'maximum', 'minLength', 'maxLength', 'items', 'minItems', 'maxItems', 'default',
]);

export const PERMISSIONS = ['read', 'edit', 'export'];

/** _meta keys that stay inside Truebex (stripped before tools/list). */
export const INTERNAL_META = ['com.truebex/router', 'com.truebex/requires', 'com.truebex/surfaces', 'com.truebex/logSafe'];

/** The hash the app and the server compare: SHA-1 of the file with CR removed. */
export function toolsHash(text) {
  return createHash('sha1').update(String(text).replace(/\r/g, ''), 'utf8').digest('hex');
}

export function loadToolsFile(path) {
  const text = readFileSync(path, 'utf8');
  const doc = JSON.parse(text);
  return { doc, hash: toolsHash(text), text };
}

/** Problems with one schema node against the portable subset ([] = fine). */
export function portableProblems(schema, where = 'inputSchema') {
  const out = [];
  if (!schema || typeof schema !== 'object' || Array.isArray(schema)) {
    out.push(`${where}: not an object`);
    return out;
  }
  for (const key of Object.keys(schema)) {
    if (!PORTABLE_KEYWORDS.has(key)) { out.push(`${where}: keyword ${key} is outside the portable subset`); }
  }
  if (schema.properties) {
    for (const [name, sub] of Object.entries(schema.properties)) {
      out.push(...portableProblems(sub, `${where}.${name}`));
    }
  }
  if (schema.items) { out.push(...portableProblems(schema.items, `${where}[]`)); }
  if (schema.additionalProperties !== undefined && typeof schema.additionalProperties !== 'boolean') {
    out.push(`${where}: additionalProperties must be a boolean`);
  }
  return out;
}

function typeOf(v) {
  if (v === null) { return 'null'; }
  if (Array.isArray(v)) { return 'array'; }
  if (typeof v === 'number') { return Number.isInteger(v) ? 'integer' : 'number'; }
  return typeof v;
}

function typeMatches(want, v) {
  const got = typeOf(v);
  if (want === 'number') { return got === 'number' || got === 'integer'; }
  return want === got;
}

/** Validate a value against a portable schema: null when valid, else the first
 *  problem naming the field ("width_mm: must be >= 100"). */
export function validate(schema, value, path = '') {
  const at = path || 'arguments';
  if (schema.type && !typeMatches(schema.type, value)) { return `${at}: must be ${schema.type}`; }
  if (schema.const !== undefined && value !== schema.const) { return `${at}: must be ${JSON.stringify(schema.const)}`; }
  if (schema.enum && !schema.enum.includes(value)) { return `${at}: must be one of ${schema.enum.join(', ')}`; }
  if (typeof value === 'number') {
    if (schema.minimum !== undefined && value < schema.minimum) { return `${at}: must be >= ${schema.minimum}`; }
    if (schema.maximum !== undefined && value > schema.maximum) { return `${at}: must be <= ${schema.maximum}`; }
  }
  if (typeof value === 'string') {
    if (schema.minLength !== undefined && value.length < schema.minLength) { return `${at}: shorter than ${schema.minLength}`; }
    if (schema.maxLength !== undefined && value.length > schema.maxLength) { return `${at}: longer than ${schema.maxLength}`; }
  }
  if (Array.isArray(value)) {
    if (schema.minItems !== undefined && value.length < schema.minItems) { return `${at}: needs at least ${schema.minItems} items`; }
    if (schema.maxItems !== undefined && value.length > schema.maxItems) { return `${at}: takes at most ${schema.maxItems} items`; }
    if (schema.items) {
      for (let i = 0; i < value.length; i++) {
        const e = validate(schema.items, value[i], `${at}[${i}]`);
        if (e) { return e; }
      }
    }
  }
  if (typeOf(value) === 'object') {
    for (const req of schema.required || []) {
      if (!(req in value)) { return `${path ? path + '.' : ''}${req}: required`; }
    }
    const props = schema.properties || {};
    for (const [k, v] of Object.entries(value)) {
      if (props[k]) {
        const e = validate(props[k], v, path ? `${path}.${k}` : k);
        if (e) { return e; }
      } else if (schema.additionalProperties === false) {
        return `${path ? path + '.' : ''}${k}: unknown argument`;
      }
    }
  }
  return null;
}

/** The surfaces a tool is offered on (default both); AI2's propose_variants is
 *  assistant-only, so MCP never lists it. */
export const SURFACES = ['mcp', 'assistant'];
export function surfacesOf(t) {
  const s = t && t._meta && t._meta['com.truebex/surfaces'];
  return Array.isArray(s) ? s : SURFACES;
}

/** The tools as MCP serves them: the mcp surface only, internal _meta keys
 *  removed, order kept. */
export function publicTools(doc) {
  return (doc.tools || []).filter((t) => surfacesOf(t).includes('mcp')).map((t) => {
    const copy = JSON.parse(JSON.stringify(t));
    if (copy._meta) {
      for (const k of INTERNAL_META) { delete copy._meta[k]; }
      if (!Object.keys(copy._meta).length) { delete copy._meta; }
    }
    return copy;
  });
}

/** Every problem with a tools.json document ([] = valid). */
export function toolsFileProblems(doc) {
  const out = [];
  if (doc.schema !== TOOLS_SCHEMA) { out.push(`schema must be ${TOOLS_SCHEMA}`); }
  if (!/^\d+\.\d+\.\d+$/.test(doc.version || '')) { out.push('version must be MAJOR.MINOR.PATCH'); }
  const seen = new Set();
  for (const t of doc.tools || []) {
    const name = t.name || '?';
    if (!/^[a-z][a-z0-9_]{0,63}$/.test(name)) { out.push(`${name}: bad name`); }
    if (seen.has(name)) { out.push(`${name}: duplicate`); }
    seen.add(name);
    if (!t.description) { out.push(`${name}: no description`); }
    const perm = t._meta && t._meta['com.truebex/permission'];
    if (!PERMISSIONS.includes(perm)) { out.push(`${name}: permission ${perm} not in ${PERMISSIONS.join('/')}`); }
    if (!t._meta || !t._meta['com.truebex/router']) { out.push(`${name}: no router`); }
    const surfaces = surfacesOf(t);
    if (!surfaces.length || surfaces.some((s) => !SURFACES.includes(s))) { out.push(`${name}: surfaces must be a non-empty subset of ${SURFACES.join('/')}`); }
    if (!t.inputSchema || t.inputSchema.type !== 'object') { out.push(`${name}: inputSchema must be an object schema`); }
    if (t.inputSchema && t.inputSchema.additionalProperties !== false) { out.push(`${name}: inputSchema must set additionalProperties false`); }
    out.push(...portableProblems(t.inputSchema, `${name}.inputSchema`));
    if (t.outputSchema) { out.push(...portableProblems(t.outputSchema, `${name}.outputSchema`)); }
    const a = t.annotations || {};
    if (a.openWorldHint !== false) { out.push(`${name}: openWorldHint must be false`); }
    if (perm === 'read' && a.readOnlyHint !== true) { out.push(`${name}: a read tool must be readOnly`); }
  }
  return out;
}
