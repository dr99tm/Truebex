// The mobile web client's local store and outbox (PF9). IndexedDB
// `truebex-app` holds what the app needs offline — the project list, each
// project's record, digest and replica id, the last manifest of each followed
// set, the last head_seq — and the outbox: edits made as `action` operations
// (actions.ts), kept until the server accepts or rejects them.
//
// The outbox follows project-log §6.3 and §8 for a light client: pending
// operations go out in order, at most 200 a request; accepted (or duplicate)
// ones are done; a rejected one is shown with the operation that won, then
// dropped, and never sent again; the rest of a stopped batch (not_processed)
// stays pending, unchanged, and goes out next. Network errors and 408 / 429 /
// 5xx keep everything pending for the next flush (on reconnect, on start, on
// a background sync); other 4xx fail the batch, never retried as sent.

import type { ActionOp } from "./actions";

export const DB_NAME = "truebex-app";
const DB_VERSION = 1;
export const MAX_BATCH = 200;
/** Accepted edits kept per project for the list of recent edits. */
const KEEP_ACCEPTED = 20;

export type EntryState = "pending" | "accepted" | "rejected" | "failed";

export interface Winner {
  author: string;
  name: string;
  server_seq: number;
}

export interface OutboxEntry {
  op_id: string;
  pid: string;
  op: ActionOp;
  state: EntryState;
  /** What the person did, as the app shows it ("Floor finish: Oak boards"). */
  label: string;
  /** The entity the edit concerns, for its badge. */
  subject?: string;
  created: number;
  seq?: number;
  winner?: Winner | null;
  reason?: string;
}

export interface WireOp {
  op_id: string;
  server_seq: number;
  author: string;
  name: string;
}

export interface PushResult {
  op_id: string;
  status: "accepted" | "duplicate" | "rejected" | "not_processed";
  server_seq?: number;
  reason?: string;
  winning?: WireOp[];
}

export interface PushAnswer {
  head_seq: number;
  results: PushResult[];
}

/** A push that failed as a whole; `retry` says whether sending it again may work. */
export class PushError extends Error {
  readonly retry: boolean;
  readonly status: number;
  readonly code: string;
  constructor(retry: boolean, message: string, status = 0, code = "") {
    super(message);
    this.retry = retry;
    this.status = status;
    this.code = code;
  }
}

/** Contract §8: network errors, 408, 429, 500, 502, 503, 504 and 530 are retried. */
export const retryable = (status: number) => status === 0 || [408, 429, 500, 502, 503, 504, 530].includes(status);

export interface OutboxStore {
  list(pid: string): Promise<OutboxEntry[]>;
  put(entry: OutboxEntry): Promise<void>;
  remove(opId: string): Promise<void>;
}

export type PushFn = (replicaId: string, ops: ActionOp[]) => Promise<PushAnswer>;

export interface FlushOutcome {
  /** The server's head after the last answer, when one came. */
  head: number | null;
  accepted: OutboxEntry[];
  rejected: OutboxEntry[];
  failed: OutboxEntry[];
  /** Still pending: offline, or the server asked to retry later. */
  waiting: number;
  error: PushError | null;
}

/** Apply 5.6's per-operation results to the batch they answer. Pure. */
export function applyResults(batch: OutboxEntry[], answer: PushAnswer): OutboxEntry[] {
  const byId = new Map(answer.results.map((r) => [r.op_id, r]));
  return batch.map((entry) => {
    const r = byId.get(entry.op_id);
    if (!r || r.status === "not_processed") return entry;
    if (r.status === "accepted" || r.status === "duplicate") {
      return { ...entry, state: "accepted" as const, seq: r.server_seq, reason: undefined };
    }
    const w = r.winning?.[0];
    return {
      ...entry,
      state: "rejected" as const,
      reason: r.reason ?? "conflict",
      winner: w ? { author: w.author, name: w.name, server_seq: w.server_seq } : null,
    };
  });
}

let flushing: Promise<FlushOutcome> | null = null;

/** Send every pending operation of `pid`; one flush at a time per page. */
export function flush(store: OutboxStore, pid: string, push: PushFn): Promise<FlushOutcome> {
  flushing ??= run(store, pid, push).finally(() => {
    flushing = null;
  });
  return flushing;
}

async function run(store: OutboxStore, pid: string, push: PushFn): Promise<FlushOutcome> {
  const out: FlushOutcome = { head: null, accepted: [], rejected: [], failed: [], waiting: 0, error: null };
  for (let round = 0; round < 1000; round++) {
    const pending = (await store.list(pid)).filter((e) => e.state === "pending").sort((a, b) => a.created - b.created);
    if (!pending.length) break;
    const replica = pending[0].op.replica_id;
    const batch = pending.filter((e) => e.op.replica_id === replica).slice(0, MAX_BATCH);
    let answer: PushAnswer;
    try {
      answer = await push(replica, batch.map((e) => e.op));
    } catch (err) {
      const error = err instanceof PushError ? err : new PushError(true, err instanceof Error ? err.message : String(err));
      if (error.retry) {
        out.error = error;
        out.waiting = pending.length;
        return out;
      }
      for (const e of batch) {
        const failed = { ...e, state: "failed" as const, reason: error.message };
        await store.put(failed);
        out.failed.push(failed);
      }
      out.error = error;
      continue;
    }
    out.head = answer.head_seq;
    const updated = applyResults(batch, answer);
    let progressed = false;
    for (const e of updated) {
      if (e.state === "pending") continue;
      progressed = true;
      await store.put(e);
      (e.state === "accepted" ? out.accepted : out.rejected).push(e);
    }
    if (!progressed) {
      out.waiting = pending.length;
      break;
    }
  }
  await prune(store, pid);
  return out;
}

async function prune(store: OutboxStore, pid: string): Promise<void> {
  const accepted = (await store.list(pid)).filter((e) => e.state === "accepted").sort((a, b) => b.created - a.created);
  for (const e of accepted.slice(KEEP_ACCEPTED)) await store.remove(e.op_id);
}

/** An in-memory store (the self-test; a browser without IndexedDB). */
export class MemoryOutbox implements OutboxStore {
  private readonly rows = new Map<string, OutboxEntry>();
  async list(pid: string) {
    return [...this.rows.values()].filter((e) => e.pid === pid).map((e) => ({ ...e }));
  }
  async put(entry: OutboxEntry) {
    this.rows.set(entry.op_id, { ...entry });
  }
  async remove(opId: string) {
    this.rows.delete(opId);
  }
}

// --- IndexedDB ------------------------------------------------------------------------------

let dbPromise: Promise<IDBDatabase> | null = null;

function openDb(): Promise<IDBDatabase> {
  dbPromise ??= new Promise<IDBDatabase>((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains("kv")) db.createObjectStore("kv");
      if (!db.objectStoreNames.contains("outbox")) db.createObjectStore("outbox", { keyPath: "op_id" }).createIndex("pid", "pid");
    };
    req.onsuccess = () => {
      req.result.onversionchange = () => {
        req.result.close();
        dbPromise = null;
      };
      resolve(req.result);
    };
    req.onerror = () => reject(req.error);
    req.onblocked = () => reject(new Error("IndexedDB is blocked by another tab"));
  }).catch((err) => {
    dbPromise = null;
    throw err;
  });
  return dbPromise;
}

async function request<T>(store: "kv" | "outbox", mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await openDb();
  return new Promise<T>((resolve, reject) => {
    const tx = db.transaction(store, mode);
    const req = fn(tx.objectStore(store));
    tx.oncomplete = () => resolve(req.result);
    tx.onerror = () => reject(tx.error ?? req.error);
    tx.onabort = () => reject(tx.error ?? new Error("IndexedDB transaction aborted"));
  });
}

export class IdbOutbox implements OutboxStore {
  list(pid: string) {
    return request("outbox", "readonly", (s) => s.index("pid").getAll(pid) as IDBRequest<OutboxEntry[]>);
  }
  async put(entry: OutboxEntry) {
    await request("outbox", "readwrite", (s) => s.put(entry));
  }
  async remove(opId: string) {
    await request("outbox", "readwrite", (s) => s.delete(opId));
  }
}

/** The key-value half of `truebex-app` (records, digests, manifests, ids). */
export const kv = {
  async get<T>(key: string): Promise<T | undefined> {
    try {
      return (await request("kv", "readonly", (s) => s.get(key) as IDBRequest<T | undefined>)) ?? undefined;
    } catch {
      return undefined;
    }
  },
  async set(key: string, value: unknown): Promise<void> {
    try {
      await request("kv", "readwrite", (s) => s.put(value, key));
    } catch {
      /* private mode or storage full: the app still works online */
    }
  },
};

/** Forget everything this browser keeps for the app (sign-out). */
export async function clearAppData(): Promise<void> {
  const db = await dbPromise?.catch(() => null);
  db?.close();
  dbPromise = null;
  await new Promise<void>((resolve) => {
    try {
      const req = indexedDB.deleteDatabase(DB_NAME);
      req.onsuccess = req.onerror = req.onblocked = () => resolve();
    } catch {
      resolve();
    }
  });
}
