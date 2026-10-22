// Server-only (PF12): the developer API's own description (openapi/v1.json)
// and the MCP tool schema (src/content/tools.json), read at build time for
// the /developers/ reference tables. Never import this from a client
// component: it reads the file system.
import fs from "node:fs";
import path from "node:path";

export interface Schema {
  $ref?: string;
  type?: string | string[];
  items?: Schema;
  anyOf?: Schema[];
  enum?: unknown[];
  const?: unknown;
  properties?: Record<string, Schema>;
  required?: string[];
  additionalProperties?: boolean | Schema;
  description?: string;
  default?: unknown;
  format?: string;
  pattern?: string;
  minimum?: number;
  maximum?: number;
  minLength?: number;
  maxLength?: number;
  minItems?: number;
  maxItems?: number;
}

interface RawParameter {
  name: string;
  in: string;
  required?: boolean;
  schema?: Schema;
  description?: string;
}

interface RawOperation {
  operationId: string;
  summary?: string;
  description?: string;
  parameters?: RawParameter[];
  requestBody?: { content: Record<string, { schema: Schema }> };
  responses: Record<string, { description: string; content?: Record<string, { schema: Schema }> }>;
  "x-truebex-scope"?: string;
  "x-truebex-auth"?: string;
  "x-truebex-contract"?: string;
}

interface Document {
  info: { version: string };
  servers: { url: string }[];
  paths: Record<string, Record<string, RawOperation>>;
  components: { schemas: Record<string, Schema> };
  tags: { name: string; description: string }[];
  "x-truebex-scopes": { scope: string; description: string; default: boolean }[];
  "x-truebex-webhook-events": { type: string; description: string }[];
  "x-truebex-limits": { burst: number; per_minute: number };
  "x-truebex-webhooks": {
    retry_after_s: number[];
    timeout_s: number;
    disable_after_days: number;
    keep_days: number;
    debounce_s: number;
  };
}

export interface Field {
  name: string;
  type: string;
  required: boolean;
  description: string;
  where?: string;
}

export interface Operation {
  id: string;
  group: string;
  method: string;
  path: string;
  description: string;
  scope: string | null;
  optionalKey: boolean;
  contract: string | null;
  params: Field[];
  body: { kind: "json" | "binary" | "multipart" | null; schema: string | null; fields: Field[] };
  response: { status: string; schema: string | null; fields: Field[] };
  errors: { status: string; text: string }[];
}

const ROOT = process.cwd();
const METHOD_ORDER = ["get", "post", "put", "patch", "delete"];

let cached: Document | null = null;

export function apiDocument(): Document {
  cached ??= JSON.parse(fs.readFileSync(path.join(ROOT, "openapi", "v1.json"), "utf8")) as Document;
  return cached;
}

function refName(ref: string): string {
  return ref.slice(ref.lastIndexOf("/") + 1);
}

function resolve(schema: Schema): Schema {
  let s = schema;
  for (let i = 0; s.$ref && i < 10; i++) s = apiDocument().components.schemas[refName(s.$ref)] ?? {};
  return s;
}

/** A schema as a short type: `string`, `int`, `Project`, `string[]`, `"a" | "b"`, `… | null`. */
export function typeOf(schema: Schema | undefined): string {
  if (!schema) return "any";
  if (schema.$ref) return refName(schema.$ref);
  if (schema.anyOf) return [...new Set(schema.anyOf.map(typeOf))].join(" | ");
  if (schema.enum) return schema.enum.map((v) => JSON.stringify(v)).join(" | ");
  if (schema.const !== undefined) return JSON.stringify(schema.const);
  const t = Array.isArray(schema.type) ? schema.type.join(" | ") : schema.type;
  if (t === "array") return `${typeOf(schema.items)}[]`;
  if (t === "integer") return "int";
  if (t === "object") return "object";
  if (t === "string" && schema.format === "binary") return "bytes";
  return t ?? "any";
}

function fieldsOf(schema: Schema | undefined): Field[] {
  if (!schema) return [];
  const s = resolve(schema);
  const required = new Set(s.required ?? []);
  return Object.entries(s.properties ?? {}).map(([name, prop]) => ({
    name,
    type: typeOf(prop),
    required: required.has(name),
    description: prop.description ?? resolve(prop).description ?? "",
  }));
}

function bodyOf(op: RawOperation): Operation["body"] {
  const content = op.requestBody?.content ?? {};
  if (content["application/json"]) {
    const schema = content["application/json"].schema;
    return { kind: "json", schema: schema.$ref ? refName(schema.$ref) : null, fields: fieldsOf(schema) };
  }
  if (content["application/octet-stream"]) return { kind: "binary", schema: null, fields: [] };
  if (content["multipart/form-data"]) {
    const schema = content["multipart/form-data"].schema;
    return { kind: "multipart", schema: schema.$ref ? refName(schema.$ref) : null, fields: fieldsOf(schema) };
  }
  return { kind: null, schema: null, fields: [] };
}

function responseOf(op: RawOperation): Operation["response"] {
  const status = Object.keys(op.responses).sort().find((s) => s.startsWith("2")) ?? "200";
  const schema = op.responses[status]?.content?.["application/json"]?.schema;
  return { status, schema: schema?.$ref ? refName(schema.$ref) : null, fields: fieldsOf(schema) };
}

/** Every operation of the given groups (`projects`, `uploads` …), in path order. */
export function operations(groups?: readonly string[]): Operation[] {
  const out: Operation[] = [];
  for (const [p, item] of Object.entries(apiDocument().paths)) {
    for (const [method, op] of Object.entries(item)) {
      const group = op.operationId.split("_", 1)[0];
      if (groups && !groups.includes(group)) continue;
      out.push({
        id: op.operationId,
        group,
        method: method.toUpperCase(),
        path: p,
        description: (op.description ?? op.summary ?? "").trim(),
        scope: op["x-truebex-scope"] ?? null,
        optionalKey: op["x-truebex-auth"] === "optional",
        contract: op["x-truebex-contract"] ?? null,
        params: (op.parameters ?? []).map((prm) => ({
          name: prm.name,
          type: typeOf(prm.schema),
          required: Boolean(prm.required),
          description: prm.description ?? "",
          where: prm.in,
        })),
        body: bodyOf(op),
        response: responseOf(op),
        errors: Object.entries(op.responses)
          .filter(([s]) => !s.startsWith("2"))
          .map(([status, r]) => ({ status, text: r.description })),
      });
    }
  }
  const order = groups ? [...groups] : [];
  return out.sort(
    (a, b) =>
      order.indexOf(a.group) - order.indexOf(b.group) ||
      a.path.localeCompare(b.path) ||
      METHOD_ORDER.indexOf(a.method.toLowerCase()) - METHOD_ORDER.indexOf(b.method.toLowerCase()),
  );
}

export function groupText(group: string): string {
  return apiDocument().tags.find((t) => t.name === group)?.description ?? "";
}

/** snake_case → camelCase, as the JavaScript SDK names its methods. */
export function camel(name: string): string {
  return name.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
}

// --- the MCP tools ---------------------------------------------------------------------------

// tools.json (schema truebex-tools/1, agent-interface §6.5) as AI1 ships it. The page shows
// `permission`, `logSafe` and what `requires` means in words; `router` and `surfaces` stay
// Truebex's own and are never rendered.
export interface Tool {
  name: string;
  title: string;
  description: string;
  inputSchema: Schema;
  outputSchema?: Schema;
  annotations: { readOnlyHint: boolean; destructiveHint?: boolean; idempotentHint?: boolean; openWorldHint?: boolean };
  _meta: {
    "com.truebex/permission": string;
    "com.truebex/logSafe"?: boolean;
    "com.truebex/requires"?: string;
    "com.truebex/surfaces"?: string[];
  };
}

/** The tools the MCP server lists (agent-interface 1.2.0): those whose surfaces include `mcp`;
 *  no surfaces key means both. The in-app assistant's tools (propose_variants) are never on MCP. */
export function mcpTools(tools: readonly Tool[]): Tool[] {
  return tools.filter((t) => {
    const surfaces = t._meta?.["com.truebex/surfaces"];
    return !Array.isArray(surfaces) || surfaces.includes("mcp");
  });
}

/** src/content/tools.json with only the tools on the mcp surface, in the file's order. */
export function toolsDocument(): { schema: string; version: string; tools: Tool[] } {
  const doc = JSON.parse(fs.readFileSync(path.join(ROOT, "src", "content", "tools.json"), "utf8"));
  return { ...doc, tools: mcpTools(doc.tools) };
}

/** PF12d: page copy with `{tools}` as the number of tools the MCP server lists, so the words follow tools.json. */
export function withToolCount(text: string, tools: readonly Tool[] = toolsDocument().tools): string {
  return text.replace(/\{tools\}/g, String(tools.length));
}

export interface ArgumentRow {
  name: string;
  schema: Schema;
  required: boolean;
}

/** A tool's arguments as the page's rows: one per top-level property (PF12d: a nested field is listed under its
 *  argument's row, see nestedFields). */
export function argumentRows(schema: Schema): ArgumentRow[] {
  const required = new Set(schema.required ?? []);
  return Object.entries(schema.properties ?? {}).map(([name, prop]) => ({ name, schema: prop, required: required.has(name) }));
}

function objectItems(schema: Schema): Schema | null {
  const items = schema.type === "array" ? schema.items : undefined;
  return items?.type === "object" && items.properties ? items : null;
}

function fieldsWithin(schema: Schema, prefix: string): ArgumentRow[] {
  const required = new Set(schema.required ?? []);
  return Object.entries(schema.properties ?? {}).flatMap(([name, prop]) => {
    const row = { name: prefix + name, schema: prop, required: required.has(name) };
    const nested = prop.type === "object" && prop.properties ? fieldsWithin(prop, `${prefix}${name}.`) : [];
    const items = objectItems(prop);
    return [row, ...nested, ...(items ? fieldsWithin(items, `${prefix}${name}[].`) : [])];
  });
}

/** PF12d: the fields listed under an argument's row, in one flat list: an object's own (create_theme's floor,
 *  create_layout's program), or the fields of each item of an array of objects (create_object's parts); deeper, an
 *  object's fields as `a.b` and an array of objects' as `a[].b`. None for any other schema. */
export function nestedFields(schema: Schema): ArgumentRow[] {
  if (schema.type === "object" && schema.properties) return fieldsWithin(schema, "");
  const items = objectItems(schema);
  return items ? fieldsWithin(items, "") : [];
}

/** A tool argument's rules in words: items, range, length, pattern, default. */
export function rulesOf(schema: Schema): string {
  const parts: string[] = [];
  const s = schema.type === "array" && schema.items ? schema.items : schema;
  if (schema.type === "array" && (schema.minItems !== undefined || schema.maxItems !== undefined)) {
    parts.push(
      schema.minItems === schema.maxItems ? `${schema.minItems} items` : `${schema.minItems ?? 0}–${schema.maxItems ?? "∞"} items`,
    );
  }
  if (s.minimum !== undefined || s.maximum !== undefined) parts.push(`${s.minimum ?? "−∞"} to ${s.maximum ?? "∞"}`);
  if (s.minLength !== undefined) parts.push(`≥ ${s.minLength} chars`);
  if (s.maxLength !== undefined) parts.push(`≤ ${s.maxLength} chars`);
  if (s.pattern) parts.push(`pattern ${s.pattern}`);
  if (schema.default !== undefined) parts.push(`default ${JSON.stringify(schema.default)}`);
  return parts.join("; ");
}
