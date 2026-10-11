"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { APP_FLUSH_EVENT } from "@/components/app/AppShell";
import { ApiError } from "@/lib/api";
import { APP } from "@/lib/constants";
import {
  getMe,
  getSetState,
  heartbeatWeb,
  latestDigest,
  listPanoramaSets,
  pushOps,
  regionPrices,
  waitForHead,
  type DigestSnapshot,
  type Me,
  type PanoramaSet,
  type PresenceView,
  type PricedItem,
  type SetState,
} from "@/lib/app";
import { getProject, type OpenProject, type Presence } from "@/lib/projects";
import { buildActionOp, hex32, type ToolCall } from "@/viewer/actions";
import { diffTiles, type TileViewLike } from "@/viewer/tilediff";
import { clearAppData, flush, IdbOutbox, kv, type OutboxEntry } from "@/viewer/outbox";

export type Status = "loading" | "ready" | "missing" | "signedOut";

export interface EditRequest {
  /** The undo-step name the desktop shows. */
  name: string;
  /** What the app lists ("Floor finish: Oak boards"). */
  label: string;
  /** The entity it concerns, for its "Pending" badge. */
  subject: string;
  call: ToolCall;
}

export interface ProjectData {
  status: Status;
  offline: boolean;
  me: Me | null;
  project: OpenProject | null;
  digest: DigestSnapshot | null;
  sets: PanoramaSet[];
  set: SetState | null;
  /** Faces the newest manifest changed (0 for the first). */
  updatedFaces: number;
  head: number;
  others: Presence[];
  prices: Record<string, PricedItem>;
  entries: OutboxEntry[];
  error: string;
  edit(req: EditRequest): Promise<void>;
  dismiss(opId: string): Promise<void>;
  /** Where the person looks, for presence (updated by the panorama). */
  viewRef: React.MutableRefObject<PresenceView | null>;
}

const HEARTBEAT_VISIBLE_MS = 10_000;
const HEARTBEAT_HIDDEN_MS = 30_000;
const DIGEST_RECHECK_MS = 30_000;
const SETS_RECHECK_MS = 60_000;
const store = new IdbOutbox();

export const priceKey = (p: { supplier_id: string; sku: string; variant_id: string }) => `${p.supplier_id}|${p.sku}|${p.variant_id}`;

const isNetwork = (err: unknown) => err instanceof ApiError && err.status === 0;
const sleep = (ms: number, signal: AbortSignal) =>
  new Promise<void>((resolve) => {
    const t = setTimeout(resolve, ms);
    signal.addEventListener("abort", () => {
      clearTimeout(t);
      resolve();
    });
  });

/** Faces of every view whose tiles a newer manifest changed. */
function changedFaces(before: SetState, after: SetState): number {
  const old = new Map((before.manifest?.views ?? []).map((v) => [v.view, v as unknown as TileViewLike]));
  return (after.manifest?.views ?? []).reduce(
    (n, v) => n + diffTiles(old.get(v.view) ?? null, v as unknown as TileViewLike).faces.length,
    0
  );
}

/** Backoff 1, 2, 4 … 60 s with ±20 % (contract §8). */
const backoff = (n: number) => Math.min(60_000, 1000 * 2 ** n) * (0.8 + Math.random() * 0.4);

/**
 * Everything the project screen shows, from this device's copy first (so it
 * opens offline) and then the network: the record, the digest, the followed
 * set's newest manifest (long-polled on `rev`), the log's head (long-polled),
 * presence (10 s while visible), regional prices, and the outbox of edits.
 */
export function useProject(pid: string): ProjectData {
  const [status, setStatus] = useState<Status>("loading");
  const [offline, setOffline] = useState(false);
  const [me, setMe] = useState<Me | null>(null);
  const [project, setProject] = useState<OpenProject | null>(null);
  const [digest, setDigest] = useState<DigestSnapshot | null>(null);
  const [sets, setSets] = useState<PanoramaSet[]>([]);
  const [set, setSet] = useState<SetState | null>(null);
  const [updatedFaces, setUpdatedFaces] = useState(0);
  const [head, setHead] = useState(0);
  const [others, setOthers] = useState<Presence[]>([]);
  const [prices, setPrices] = useState<Record<string, PricedItem>>({});
  const [entries, setEntries] = useState<OutboxEntry[]>([]);
  const [error, setError] = useState("");

  const headRef = useRef(0);
  const meRef = useRef<Me | null>(null);
  const replicaRef = useRef<string>("");
  const sessionRef = useRef<string>("");
  const offlineRef = useRef(false);
  const viewRef = useRef<PresenceView | null>(null);
  const digestRef = useRef<DigestSnapshot | null>(null);
  const setIdRef = useRef<string | null>(null);

  const goOffline = useCallback((value: boolean) => {
    offlineRef.current = value;
    setOffline(value);
  }, []);

  const noteHead = useCallback(
    (value: number) => {
      if (value <= headRef.current) return;
      headRef.current = value;
      setHead(value);
      void kv.set(`head:${pid}`, value);
    },
    [pid]
  );

  const refreshEntries = useCallback(async () => {
    const rows = await store.list(pid).catch(() => [] as OutboxEntry[]);
    setEntries(rows.sort((a, b) => b.created - a.created));
  }, [pid]);

  const sync = useCallback(async () => {
    if (!replicaRef.current) return;
    const out = await flush(store, pid, (replica, ops) => pushOps(pid, replica, ops));
    if (out.head !== null) noteHead(out.head);
    if (out.error?.retry && out.error.status === 0) goOffline(true);
    else if (out.head !== null) goOffline(false);
    if (out.error?.status === 401) setStatus("signedOut");
    await refreshEntries();
  }, [pid, noteHead, goOffline, refreshEntries]);

  const loadDigest = useCallback(async () => {
    const fresh = await latestDigest(pid, digestRef.current);
    if (!fresh) return;
    const changed = fresh.sha256 !== digestRef.current?.sha256;
    digestRef.current = fresh;
    setDigest(fresh);
    void kv.set(`digest:${pid}`, fresh);
    const region = fresh.digest.region;
    if (changed && region && fresh.digest.products.length) {
      try {
        const items = await regionPrices(region, fresh.digest.products);
        const byKey = Object.fromEntries(items.map((i) => [priceKey(i), i]));
        setPrices(byKey);
        void kv.set(`prices:${pid}`, byKey);
      } catch {
        /* the marketplace is optional: names show without prices */
      }
    }
  }, [pid]);

  const pickSet = useCallback(
    async (signal: AbortSignal): Promise<string | null> => {
      const found = await listPanoramaSets(pid);
      if (signal.aborted) return null;
      setSets(found.sets);
      const keep = found.sets.find((s) => s.set_id === setIdRef.current) ?? found.sets[0];
      return keep?.set_id ?? null;
    },
    [pid]
  );

  // The first load: this device's copy, then the network.
  useEffect(() => {
    const abort = new AbortController();
    const { signal } = abort;
    sessionRef.current = hex32();
    (async () => {
      const [cachedMe, cachedProject, cachedDigest, cachedSet, cachedHead, cachedPrices, replica] = await Promise.all([
        kv.get<Me>("me"),
        kv.get<OpenProject>(`project:${pid}`),
        kv.get<DigestSnapshot>(`digest:${pid}`),
        kv.get<{ setId: string; state: SetState }>(`set:${pid}`),
        kv.get<number>(`head:${pid}`),
        kv.get<Record<string, PricedItem>>(`prices:${pid}`),
        kv.get<string>(`replica:${pid}`),
      ]);
      if (signal.aborted) return;
      // One replica id per installation and project, kept for good.
      replicaRef.current = replica ?? hex32();
      if (!replica) void kv.set(`replica:${pid}`, replicaRef.current);
      if (cachedMe) {
        meRef.current = cachedMe;
        setMe(cachedMe);
      }
      if (cachedProject) setProject(cachedProject);
      if (cachedDigest) {
        digestRef.current = cachedDigest;
        setDigest(cachedDigest);
      }
      if (cachedSet) {
        setIdRef.current = cachedSet.setId;
        setSet(cachedSet.state);
      }
      if (cachedPrices) setPrices(cachedPrices);
      if (cachedHead) noteHead(cachedHead);
      if (cachedProject) setStatus("ready");
      await refreshEntries();

      try {
        const who = await getMe();
        if (signal.aborted) return;
        if (cachedMe && cachedMe.id !== who.id) {
          // Another account signed in on this device: its copy is not this one's.
          await clearAppData();
          window.location.reload();
          return;
        }
        meRef.current = who;
        setMe(who);
        void kv.set("me", who);
        const opened = await getProject(pid);
        if (signal.aborted) return;
        setProject(opened);
        void kv.set(`project:${pid}`, opened);
        noteHead(opened.head_seq);
        setStatus("ready");
        goOffline(false);
        // Ask the browser not to evict the offline copy under storage pressure.
        void navigator.storage?.persist?.().catch(() => false);
        await Promise.all([loadDigest().catch(() => undefined), sync().catch(() => undefined)]);
        const setId = await pickSet(signal).catch(() => null);
        if (signal.aborted) return;
        if (setId) setIdRef.current = setId;
        if (setId) {
          const state = await getSetState(pid, setId);
          if (signal.aborted) return;
          setSet(state);
          void kv.set(`set:${pid}`, { setId, state });
        }
      } catch (err) {
        if (signal.aborted) return;
        if (isNetwork(err)) {
          goOffline(true);
          if (cachedProject) setStatus("ready");
        } else if (err instanceof ApiError && err.status === 401) setStatus("signedOut");
        else if (err instanceof ApiError && err.status === 404) setStatus("missing");
        else setError(err instanceof Error ? err.message : String(err));
      }
    })();
    return () => abort.abort();
  }, [pid, noteHead, refreshEntries, loadDigest, sync, pickSet, goOffline]);

  // The log's head (5.7, limit 1): new operations, from anyone.
  useEffect(() => {
    if (status !== "ready") return;
    const abort = new AbortController();
    const { signal } = abort;
    (async () => {
      let failures = 0;
      let digestChecked = Date.now();
      while (!signal.aborted) {
        try {
          const page = await waitForHead(pid, headRef.current, 25, signal);
          if (signal.aborted) return;
          const wasOffline = offlineRef.current;
          goOffline(false);
          failures = 0;
          if (page.head_seq > headRef.current) {
            noteHead(page.head_seq);
            if (Date.now() - digestChecked > DIGEST_RECHECK_MS) {
              digestChecked = Date.now();
              void loadDigest().catch(() => undefined);
            }
          }
          if (wasOffline) void sync();
        } catch (err) {
          if (signal.aborted) return;
          if (isNetwork(err)) goOffline(true);
          if (err instanceof ApiError && err.status === 401) {
            setStatus("signedOut");
            return;
          }
          await sleep(backoff(failures++), signal);
        }
      }
    })();
    return () => abort.abort();
  }, [status, pid, noteHead, goOffline, loadDigest, sync]);

  // The followed set: long-poll its rev and take each newer manifest.
  useEffect(() => {
    if (status !== "ready") return;
    const abort = new AbortController();
    const { signal } = abort;
    (async () => {
      let failures = 0;
      let rev = -1;
      let listed = 0;
      let prev: SetState | null = null;
      while (!signal.aborted) {
        try {
          if (!setIdRef.current || Date.now() - listed > SETS_RECHECK_MS) {
            listed = Date.now();
            const id = await pickSet(signal);
            if (id) setIdRef.current = id;
          }
          const id = setIdRef.current;
          if (!id) {
            await sleep(SETS_RECHECK_MS, signal);
            continue;
          }
          const state = await getSetState(pid, id, rev, 25, signal);
          if (signal.aborted) return;
          failures = 0;
          if (state.rev > rev) {
            rev = state.rev;
            setUpdatedFaces(prev ? changedFaces(prev, state) : 0);
            prev = state;
            setSet(state);
            void kv.set(`set:${pid}`, { setId: id, state });
          }
        } catch (err) {
          if (signal.aborted) return;
          if (err instanceof ApiError && err.status === 404) setIdRef.current = null;
          await sleep(backoff(failures++), signal);
        }
      }
    })();
    return () => abort.abort();
  }, [status, pid, pickSet]);

  // Presence: "web" with the view, every 10 s while visible (30 s hidden); leaving on close.
  useEffect(() => {
    if (status !== "ready") return;
    let live = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const beat = async () => {
      if (!replicaRef.current) return;
      try {
        const res = await heartbeatWeb(pid, replicaRef.current, viewRef.current);
        if (live) setOthers(res.others);
      } catch {
        /* the head loop reports being offline */
      }
      if (live) timer = setTimeout(beat, document.visibilityState === "visible" ? HEARTBEAT_VISIBLE_MS : HEARTBEAT_HIDDEN_MS);
    };
    void beat();
    const leave = () => void heartbeatWeb(pid, replicaRef.current, null, true).catch(() => undefined);
    window.addEventListener("pagehide", leave);
    return () => {
      live = false;
      clearTimeout(timer);
      window.removeEventListener("pagehide", leave);
      leave();
    };
  }, [status, pid]);

  // Send the outbox when the device comes back, and when the service worker asks.
  useEffect(() => {
    const go = () => void sync();
    window.addEventListener("online", go);
    window.addEventListener(APP_FLUSH_EVENT, go);
    return () => {
      window.removeEventListener("online", go);
      window.removeEventListener(APP_FLUSH_EVENT, go);
    };
  }, [sync]);

  const edit = useCallback(
    async (req: EditRequest) => {
      const author = meRef.current?.author_id;
      if (!author || !replicaRef.current) {
        setError(APP.errors.session);
        return;
      }
      const op = buildActionOp({
        author,
        replicaId: replicaRef.current,
        baseSeq: headRef.current,
        session: sessionRef.current,
        name: req.name,
        call: req.call,
      });
      await store.put({ op_id: op.op_id, pid, op, state: "pending", label: req.label, subject: req.subject, created: Date.now() });
      await refreshEntries();
      if (offlineRef.current || !navigator.onLine) {
        // Background sync wakes this page when the connection returns (where the browser has it).
        const reg = await navigator.serviceWorker?.ready.catch(() => null);
        await (reg as (ServiceWorkerRegistration & { sync?: { register(tag: string): Promise<void> } }) | null)?.sync
          ?.register("truebex-outbox")
          .catch(() => undefined);
        return;
      }
      await sync();
    },
    [pid, refreshEntries, sync]
  );

  const dismiss = useCallback(
    async (opId: string) => {
      await store.remove(opId);
      await refreshEntries();
    },
    [refreshEntries]
  );

  return { status, offline, me, project, digest, sets, set, updatedFaces, head, others, prices, entries, error, edit, dismiss, viewRef };
}
