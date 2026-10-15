// The light client's edits as project-log `action` operations (PF9; contract
// project-log §6.2, the action of agent-interface §6.4). The web client never
// writes a delta: each edit names one log-safe tool with its arguments, and
// every kernel replica applies it through the same tool at its server_seq.
//
// Entities in the arguments are `Ref`s, `<kind>#<id>` (agent-interface §6.2;
// PF4a), exactly as the app's own action-move.json writes them: a kernel
// replica turns `wall#<32 hex>` into its own row and looks a bare id up as
// nothing. A pick always knows its kind from the digest section it came from
// (`DIGEST_KINDS`); the builder refuses a bare id rather than send one.
// `touched` is the sorted, unique set of the refs' ids (§6.2);
// `name` is the undo-step name the desktop shows. Framework-free: the project
// page, the outbox and the self-test (checked against the contract fixture
// action-move.json) all use it.

export type P3 = [number, number, number];
export type Face = "left" | "right" | "both" | "floor" | "ceiling" | "all";

export interface Finish {
  kind: "paint" | "wallpaper" | "pattern3d" | "none";
  colour?: string;
  roughness?: number;
  texture?: string;
  pattern?: "tile" | "brick" | "slat" | "coffer";
  tile_mm?: [number, number];
}

/** `FCadProductRef` on the wire (marketplace-api §6.3). */
export interface ProductRef {
  supplier_id: string;
  sku: string;
  variant_id: string;
}

export type MoveArgs = { refs: string[]; by_mm?: P3; to_mm?: P3; along_mm?: number; rotate_deg?: number };
export type FillArgs = { target: string; face?: Face; finish: Finish };
export type ThemeArgs = { theme: string; target: string; keep_products?: boolean };
/** `place` of a product; `replace` (a placed product's ref) is PF9's MINOR proposal for agent-interface §5.7. */
export type PlaceArgs = { kind: "product"; product: ProductRef; replace?: string; room?: string; at_mm?: P3 };

export type ToolCall =
  | { tool: "move"; args: MoveArgs }
  | { tool: "fill"; args: FillArgs }
  | { tool: "apply_theme"; args: ThemeArgs }
  | { tool: "place"; args: PlaceArgs };

export interface ActionOp {
  op_id: string;
  author: string;
  author_kind: "person";
  at: string;
  replica_id: string;
  base_seq: number;
  kind: "action";
  name: string;
  touched: string[];
  action: { tool: ToolCall["tool"]; args: ToolCall["args"]; permission: "edit"; session: string; request_id: string };
}

export interface BuildInput {
  /** The person's author id (`/auth/me`). */
  author: string;
  /** One per browser installation and project. */
  replicaId: string;
  /** The highest server_seq the client had seen when the person made the edit. */
  baseSeq: number;
  /** This app session (agent-interface §6.3: the author of its undo steps). */
  session: string;
  name: string;
  call: ToolCall;
  opId?: string;
  requestId?: string;
  at?: Date | string;
}

const HEX32 = /^[0-9a-f]{32}$/;
const COLOUR = /^#[0-9A-Fa-f]{6}$/;
const REF_KEYS = ["refs", "target", "host", "room", "replace"] as const;
const MAX_MM = 1_000_000;
export const NAME_MAX = 80;

/** agent-interface §6.2: the kinds of `Cad3DFastEyeView.h`, door / window (aliases of opening), storey, stair, sheet, layer. */
export const REF_KINDS = [
  "wall",
  "opening",
  "room",
  "slab",
  "object",
  "extrusion",
  "model",
  "sweep",
  "dim",
  "refplane",
  "line",
  "curve",
  "door",
  "window",
  "storey",
  "stair",
  "sheet",
  "layer",
] as const;
export type RefKind = (typeof REF_KINDS)[number];

/** The kind of what a digest section lists: a placed product is an `object` row, as in the app's own selection. */
export const DIGEST_KINDS = { room: "room", wall: "wall", product: "object", opening: "opening" } as const satisfies Record<string, RefKind>;

const REF = new RegExp(`^(${REF_KINDS.join("|")})#([0-9a-f]{32})$`);

export const isHex32 = (value: unknown): value is string => typeof value === "string" && HEX32.test(value);

/** A `Ref` (agent-interface §6.2): `<kind>#<id>`, the id CL0's 32-hex entity id (`wall#dc64…6b30d`). */
export const ref = (kind: RefKind, id: string): string => `${kind}#${id.toLowerCase()}`;

/** The entity id a ref names, or null for anything else (a bare id, a name, an unknown kind). */
export function refId(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const m = REF.exec(value.toLowerCase());
  return m ? m[2] : null;
}

export const isRef = (value: unknown): value is string => refId(value) !== null;

/** 32 lowercase hex from the platform's random source (op ids, replica ids). */
export function hex32(): string {
  const bytes = new Uint8Array(16);
  globalThis.crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

/** RFC 3339 UTC with milliseconds and `Z` (2026-10-09T12:00:00.000Z). */
export function rfc3339ms(at: Date): string {
  return at.toISOString();
}

/** The ids of every entity ref in a tool's arguments, sorted and unique: the operation's `touched` (bare ids). */
export function touchedOf(args: object): string[] {
  const ids = new Set<string>();
  const record = args as Record<string, unknown>;
  for (const key of REF_KEYS) {
    const value = record[key];
    for (const v of Array.isArray(value) ? value : [value]) {
      const id = refId(v);
      if (id) ids.add(id);
    }
  }
  return [...ids].sort();
}

function fail(message: string): never {
  throw new Error(`action: ${message}`);
}

const finiteMm = (v: unknown) => typeof v === "number" && Number.isFinite(v) && Math.abs(v) <= MAX_MM;
const isP3 = (v: unknown): v is P3 => Array.isArray(v) && v.length === 3 && v.every(finiteMm);

/** The checks of agent-interface §5.7–5.11 a light client can make without the model. */
export function validateCall(call: ToolCall): void {
  const refsOk = (refs: unknown) => Array.isArray(refs) && refs.length >= 1 && refs.length <= 100 && refs.every(isRef);
  switch (call.tool) {
    case "move": {
      const a = call.args;
      if (!refsOk(a.refs)) fail("move.refs: 1 to 100 refs <kind>#<id>");
      const given = (["by_mm", "to_mm", "along_mm", "rotate_deg"] as const).filter((k) => a[k] !== undefined);
      if (given.length !== 1) fail("move: exactly one of by_mm, to_mm, along_mm, rotate_deg");
      if (a.by_mm !== undefined && !isP3(a.by_mm)) fail("move.by_mm: three numbers (mm)");
      if (a.to_mm !== undefined && (!isP3(a.to_mm) || a.refs.length !== 1)) fail("move.to_mm: one ref, three numbers");
      if (a.along_mm !== undefined && !finiteMm(a.along_mm)) fail("move.along_mm: a number (mm)");
      if (a.rotate_deg !== undefined && !(Math.abs(a.rotate_deg) <= 360)) fail("move.rotate_deg: -360 to 360");
      return;
    }
    case "fill": {
      const a = call.args;
      if (!isRef(a.target)) fail("fill.target: a ref <kind>#<id>");
      const f = a.finish;
      if (!f || !["paint", "wallpaper", "pattern3d", "none"].includes(f.kind)) fail("fill.finish.kind");
      if (f.colour !== undefined && !COLOUR.test(f.colour)) fail("fill.finish.colour: #RRGGBB");
      if (f.roughness !== undefined && !(f.roughness >= 0 && f.roughness <= 1)) fail("fill.finish.roughness: 0 to 1");
      if (f.texture !== undefined && f.texture.length > 120) fail("fill.finish.texture: at most 120 characters");
      return;
    }
    case "apply_theme": {
      const a = call.args;
      if (!isRef(a.target)) fail("apply_theme.target: a ref <kind>#<id>");
      if (!a.theme || a.theme.length > 120) fail("apply_theme.theme: 1 to 120 characters");
      return;
    }
    case "place": {
      const a = call.args;
      if (a.kind !== "product") fail("place: only products travel in the log from a light client");
      const p = a.product;
      if (!p || !isHex32(p.supplier_id) || !p.sku || p.sku.length > 64 || !p.variant_id || p.variant_id.length > 64) {
        fail("place.product: supplier_id, sku, variant_id");
      }
      if (a.replace !== undefined && !isRef(a.replace)) fail("place.replace: a ref <kind>#<id>");
      if (a.room !== undefined && !isRef(a.room)) fail("place.room: a ref <kind>#<id>");
      if (a.room === undefined && a.at_mm === undefined && a.replace === undefined) fail("place: room, at_mm or replace");
      return;
    }
    default:
      fail("not a log-safe tool");
  }
}

/** One `action` operation, ready for 5.6 (`POST /projects/{pid}/ops`). */
export function buildActionOp(input: BuildInput): ActionOp {
  const author = input.author.toLowerCase();
  const replica = input.replicaId.toLowerCase();
  const session = input.session.toLowerCase();
  if (!isHex32(author)) fail("author: 32 hex (the person's author_id)");
  if (!isHex32(replica)) fail("replica_id: 32 hex");
  if (!isHex32(session)) fail("session: 32 hex");
  if (!Number.isInteger(input.baseSeq) || input.baseSeq < 0) fail("base_seq: 0 or more");
  validateCall(input.call);
  const opId = (input.opId ?? hex32()).toLowerCase();
  const requestId = (input.requestId ?? hex32()).toLowerCase();
  if (!isHex32(opId) || !isHex32(requestId)) fail("op_id, request_id: 32 hex");
  const at = typeof input.at === "string" ? input.at : rfc3339ms(input.at ?? new Date());
  return {
    op_id: opId,
    author,
    author_kind: "person",
    at,
    replica_id: replica,
    base_seq: input.baseSeq,
    kind: "action",
    name: Array.from(input.name.trim()).slice(0, NAME_MAX).join(""),
    touched: touchedOf(input.call.args),
    action: { tool: input.call.tool, args: input.call.args, permission: "edit", session, request_id: requestId },
  };
}

// --- the light edits ---------------------------------------------------------------------

export type Nudge = "left" | "right" | "forward" | "back";

/**
 * A step in doc millimetres relative to where the person looks (`bearingDeg`,
 * compass: 0 = north = doc +Y, 90 = east = doc +X), rounded to whole mm.
 */
export function nudgeVector(bearingDeg: number, dir: Nudge, stepMm: number): P3 {
  const b = (bearingDeg * Math.PI) / 180;
  const forward = [Math.sin(b), Math.cos(b)];
  const right = [Math.cos(b), -Math.sin(b)];
  const [x, y] =
    dir === "forward" ? forward : dir === "back" ? [-forward[0], -forward[1]] : dir === "right" ? right : [-right[0], -right[1]];
  const mm = (v: number) => Math.round(v * stepMm) + 0; // + 0: no -0 on the wire
  return [mm(x), mm(y), 0];
}

// Every entity argument below is a ref, `ref(kind, id)` (§6.2).
export const moveBy = (refs: string[], by: P3): ToolCall => ({ tool: "move", args: { refs, by_mm: by } });
export const slideAlong = (ref: string, along: number): ToolCall => ({ tool: "move", args: { refs: [ref], along_mm: along } });
export const fillFace = (target: string, face: Face, finish: Finish): ToolCall => ({ tool: "fill", args: { target, face, finish } });
export const applyTheme = (room: string, theme: string): ToolCall => ({
  tool: "apply_theme",
  args: { theme, target: room, keep_products: true },
});
export const swapProduct = (replace: string, product: ProductRef, room?: string): ToolCall => ({
  tool: "place",
  args: room ? { kind: "product", product, replace, room } : { kind: "product", product, replace },
});
