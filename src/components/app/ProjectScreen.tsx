"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ChevronDown, ChevronLeft, ChevronUp, Compass, WifiOff } from "lucide-react";
import { HeadsetButton } from "@/components/app/HeadsetButton";
import { PanoramaView } from "@/components/app/PanoramaView";
import { EditPanel, EditsList, PeoplePanel, RoomsPanel, type Selection } from "@/components/app/ProjectPanels";
import { useProject, type EditRequest } from "@/components/app/useProject";
import { FLOOR_FINISHES, finishLabel } from "@/lib/app";
import { fill } from "@/lib/catalogue";
import { APP } from "@/lib/constants";
import type { TileView } from "@/lib/jobs";
import type { ProjectRole } from "@/lib/projects";
import { useIsAuthenticated } from "@/lib/useAuth";
import { cn } from "@/lib/utils";
import { applyTheme, fillFace } from "@/viewer/actions";
import type { CubeHotspot } from "@/viewer/cube";
import { bearingTo, orientationAvailable, requestOrientation, type Look } from "@/viewer/orientation";
import type { XrScene } from "@/viewer/xr";

type Tab = "rooms" | "edit" | "people";
const HEX32 = /^[0-9a-f]{32}$/;

export function ProjectScreen() {
  const params = useSearchParams();
  const pid = (params.get("id") ?? "").toLowerCase();
  const authed = useIsAuthenticated();
  if (authed === null) return <Centered text={APP.project.loading} />;
  if (!authed) return <SignInPrompt next={`/app/project/?id=${pid}`} />;
  if (!HEX32.test(pid)) return <Centered text={APP.project.missing} back />;
  return <ProjectView pid={pid} />;
}

function Centered({ text, back = false }: { text: string; back?: boolean }) {
  return (
    <main className="flex min-h-[100dvh] flex-col items-center justify-center gap-4 px-6 text-center">
      <h1 className="sr-only">{APP.name}</h1>
      <p className="max-w-sm text-text-secondary">{text}</p>
      {back && (
        <Link href="/app/" className="text-accent hover:underline">
          {APP.project.back}
        </Link>
      )}
    </main>
  );
}

export function SignInPrompt({ next }: { next: string }) {
  return (
    <main className="flex min-h-[100dvh] flex-col items-center justify-center px-6 text-center">
      <h1 className="text-2xl font-semibold">{APP.signIn.title}</h1>
      <p className="mt-3 max-w-sm text-sm text-text-secondary">{APP.signIn.text}</p>
      <div className="mt-6 flex gap-3">
        <a href={`/login/?next=${encodeURIComponent(next)}`} className="rounded-[var(--radius-button)] bg-accent px-5 py-2.5 text-sm font-medium text-background">
          {APP.signIn.cta}
        </a>
        <a href={`/signup/?next=${encodeURIComponent(next)}`} className="rounded-[var(--radius-button)] border border-border px-5 py-2.5 text-sm">
          {APP.signIn.create}
        </a>
      </div>
    </main>
  );
}

function ProjectView({ pid }: { pid: string }) {
  const data = useProject(pid);
  const [tab, setTab] = useState<Tab>("rooms");
  const [sheetOpen, setSheetOpen] = useState(false);
  const [selection, setSelection] = useState<Selection>(null);
  const [viewId, setViewId] = useState<string | null>(null);
  const [tilt, setTilt] = useState(false);
  const [motion, setMotion] = useState(false);
  const [notice, setNotice] = useState("");
  const lookRef = useRef<Look>({ yawDeg: 0, pitchDeg: 0 });
  const { digest, set, project, edit: pushEdit } = data;

  const manifest = set?.manifest ?? null;
  const views = useMemo(() => (manifest?.views ?? []) as TileView[], [manifest]);
  const current = views.find((v) => v.view === viewId) ?? views[0] ?? null;
  const digestViews = useMemo(() => new Map((digest?.digest.views ?? []).map((v) => [v.id, v])), [digest]);
  const currentRoomId = current ? (digestViews.get(current.view)?.room ?? null) : null;
  const startYaw = current ? (digestViews.get(current.view)?.yaw_deg ?? 0) : 0;

  const hotspots = useMemo<CubeHotspot[]>(() => {
    if (!current) return [];
    const eye = (v: TileView) => digestViews.get(v.view)?.eye_mm ?? (v as TileView & { eye_mm?: number[] }).eye_mm ?? [0, 0, 0];
    return views
      .filter((v) => v.view !== current.view)
      .map((v) => {
        const look = bearingTo(eye(current), eye(v));
        return { id: v.view, label: digestViews.get(v.view)?.name ?? v.title ?? APP.project.view, ...look };
      });
  }, [views, current, digestViews]);

  const onHotspot = useCallback((id: string) => setViewId(id), []);

  // Presence carries the view: its storey, eye and where the person looks.
  useEffect(() => {
    const viewRef = data.viewRef;
    const dv = current ? digestViews.get(current.view) : undefined;
    const update = () => {
      viewRef.current = current
        ? { storey: dv?.storey ?? null, eye_mm: dv?.eye_mm, yaw_deg: Math.round(lookRef.current.yawDeg) }
        : null;
    };
    update();
    const timer = setInterval(update, 1000);
    return () => clearInterval(timer);
  }, [current, digestViews, data.viewRef]);

  useEffect(() => {
    queueMicrotask(() => setMotion(orientationAvailable() && window.matchMedia?.("(pointer: coarse)").matches === true));
  }, []);

  // Keep the other views' tiles on this device too, so hotspots work offline.
  const prefetched = useRef(new Set<string>());
  useEffect(() => {
    if (!manifest || typeof navigator === "undefined" || !navigator.serviceWorker?.controller) return;
    const need = (window.innerWidth / Math.tan((40 * Math.PI) / 180)) * (window.devicePixelRatio || 1);
    for (const v of manifest.views) {
      const level = v.levels.findIndex((px) => px >= need);
      const l = level === -1 ? v.levels.length - 1 : level;
      for (const face of Object.values(v.faces)) {
        for (const sha of face.tiles[l] ?? []) {
          const url = `${manifest.tiles_base.replace(/\/$/, "")}/${sha}.jpg`;
          if (prefetched.current.has(url)) continue;
          prefetched.current.add(url);
          void fetch(url, { mode: "cors", credentials: "omit" }).catch(() => prefetched.current.delete(url));
        }
      }
    }
  }, [manifest]);

  const canEdit = project ? project.role !== "viewer" : false;
  const pendingIds = useMemo(
    () => new Set(data.entries.filter((e) => e.state === "pending" && e.subject).map((e) => e.subject as string)),
    [data.entries]
  );
  const viewRooms = useMemo(() => new Set([...digestViews.values()].map((v) => v.room).filter(Boolean) as string[]), [digestViews]);

  const edit = useCallback(
    (req: EditRequest) => {
      if (!canEdit) return;
      void pushEdit(req);
    },
    [canEdit, pushEdit]
  );

  const goToRoom = (roomId: string) => {
    const v = [...digestViews.values()].find((d) => d.room === roomId && views.some((m) => m.view === d.id));
    if (v) setViewId(v.id);
    setSheetOpen(false);
  };

  const toggleTilt = async () => {
    if (tilt) {
      setTilt(false);
      return;
    }
    if (await requestOrientation()) setTilt(true);
    else setNotice(APP.project.tiltDenied);
  };

  // The headset's menu: the current room's themes and floor finishes.
  const room = digest?.digest.rooms.find((r) => r.id === currentRoomId) ?? null;
  const onMenu = useCallback(
    (id: string) => {
      if (!room || !digest) return;
      const [kind, value] = id.split(":");
      if (kind === "theme") {
        const t = digest.digest.themes.find((x) => x.id === value);
        if (t) edit({ name: APP.opNames.theme, label: `${APP.edit.theme}: ${t.name}`, subject: room.id, call: applyTheme(room.id, t.id) });
      } else if (kind === "floor") {
        const f = FLOOR_FINISHES.find((x) => x.id === value);
        if (f) {
          edit({ name: APP.opNames.floor, label: `${APP.edit.floor}: ${f.label} (${room.name})`, subject: room.id, call: fillFace(room.id, "floor", f.finish) });
        }
      }
    },
    [room, digest, edit]
  );
  const scene = useMemo<XrScene | null>(() => {
    if (!current || !manifest) return null;
    const floorNow = finishLabel(room?.finishes?.floor, FLOOR_FINISHES);
    return {
      view: current,
      tilesBase: manifest.tiles_base,
      yawDeg: startYaw,
      hotspots,
      menu: {
        title: room?.name ?? digestViews.get(current.view)?.name ?? APP.name,
        groups: room
          ? [
              { title: APP.xr.theme, items: (digest?.digest.themes ?? []).map((t) => ({ id: `theme:${t.id}`, label: t.name, selected: t.id === room.theme })) },
              { title: APP.xr.floor, items: FLOOR_FINISHES.map((f) => ({ id: `floor:${f.id}`, label: f.label, selected: f.label === floorNow })) },
            ]
          : [],
      },
      labels: { menu: APP.xr.menu, close: APP.xr.close },
    };
  }, [current, manifest, startYaw, hotspots, room, digest, digestViews]);

  if (data.status === "loading") return <Centered text={APP.project.loading} />;
  if (data.status === "missing") return <Centered text={APP.project.missing} back />;
  if (data.status === "signedOut") return <SignInPrompt next={`/app/project/?id=${pid}`} />;

  const roles = APP.roles as Record<ProjectRole, string>;
  const panelTitle = { rooms: APP.tabs.rooms, edit: APP.tabs.edit, people: APP.tabs.people };

  return (
    <main className="fixed inset-0 overflow-hidden bg-background">
      {current && manifest ? (
        <PanoramaView
          view={current}
          tilesBase={manifest.tiles_base}
          hotspots={hotspots}
          onHotspot={onHotspot}
          tilt={tilt}
          startYaw={startYaw}
          lookRef={lookRef}
        />
      ) : (
        <div className="absolute inset-0 flex items-center justify-center px-8 text-center text-sm text-text-secondary">
          <p className="max-w-sm">{data.sets.length || set ? APP.project.noManifest : APP.project.noPanorama}</p>
        </div>
      )}

      <header className="absolute inset-x-0 top-0 z-10 bg-gradient-to-b from-background/90 to-transparent px-3 pb-6 pt-[max(0.75rem,env(safe-area-inset-top))]">
        <div className="flex items-center gap-2">
          <Link href="/app/" aria-label={APP.project.back} className="flex h-10 w-10 items-center justify-center rounded-full bg-background/70">
            <ChevronLeft className="h-5 w-5" />
          </Link>
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-base font-semibold">{project?.name}</h1>
            <p className="truncate text-xs text-text-secondary">
              {project && roles[project.role]}
              {set && ` · ${fill(APP.project.updated, { seq: set.at_seq })}`}
              {data.updatedFaces > 0 && ` · ${fill(APP.project.facesUpdated, { n: data.updatedFaces })}`}
            </p>
          </div>
          {motion && current && (
            <button
              type="button"
              onClick={() => void toggleTilt()}
              aria-pressed={tilt}
              className={cn(
                "flex h-10 items-center gap-1.5 rounded-[var(--radius-button)] border px-3 text-sm backdrop-blur",
                tilt ? "border-accent bg-accent-muted" : "border-border bg-background/70"
              )}
            >
              <Compass className="h-4 w-4" aria-hidden="true" />
              {tilt ? APP.project.tiltOn : APP.project.tilt}
            </button>
          )}
          <HeadsetButton
            scene={scene}
            label={APP.project.headset}
            onHotspot={onHotspot}
            onMenu={onMenu}
            onError={(reason) => setNotice(fill(APP.project.headsetFailed, { reason }))}
          />
        </div>
        {views.length > 1 && (
          <label className="mt-2 flex items-center gap-2 text-xs text-text-secondary">
            {APP.project.view}
            <select
              value={current?.view ?? ""}
              onChange={(e) => setViewId(e.target.value)}
              className="rounded-[var(--radius-button)] border border-border bg-background/80 px-2 py-1 text-sm text-text-primary"
            >
              {views.map((v) => (
                <option key={v.view} value={v.view}>
                  {digestViews.get(v.view)?.name ?? v.title ?? APP.project.view}
                </option>
              ))}
            </select>
          </label>
        )}
        {data.offline && (
          <p role="status" className="mt-2 flex items-center gap-2 rounded-[var(--radius-button)] border border-warn/50 bg-background/85 px-3 py-2 text-sm text-warn">
            <WifiOff className="h-4 w-4 shrink-0" aria-hidden="true" />
            {APP.offline}
          </p>
        )}
        {(notice || data.error) && (
          <p role="alert" className="mt-2 rounded-[var(--radius-button)] border border-border bg-background/85 px-3 py-2 text-sm text-text-secondary">
            {notice || data.error}
          </p>
        )}
      </header>

      <section
        aria-label={panelTitle[tab]}
        className={cn(
          "absolute inset-x-0 bottom-0 z-10 flex flex-col rounded-t-[18px] border-t border-border bg-surface/95 backdrop-blur transition-[max-height] duration-300",
          sheetOpen ? "max-h-[70dvh]" : "max-h-[8.5rem]"
        )}
      >
        <button
          type="button"
          onClick={() => setSheetOpen((v) => !v)}
          className="flex w-full items-center justify-center py-1.5 text-text-muted"
          aria-expanded={sheetOpen}
          aria-label={panelTitle[tab]}
        >
          {sheetOpen ? <ChevronDown className="h-5 w-5" /> : <ChevronUp className="h-5 w-5" />}
        </button>
        <div role="tablist" className="flex gap-1 px-3">
          {(["rooms", "edit", "people"] as Tab[]).map((t) => (
            <button
              key={t}
              role="tab"
              type="button"
              aria-selected={tab === t}
              onClick={() => {
                setTab(t);
                setSheetOpen(true);
              }}
              className={cn(
                "flex-1 rounded-[var(--radius-button)] py-2 text-sm",
                tab === t ? "bg-surface-elevated text-text-primary" : "text-text-secondary"
              )}
            >
              {panelTitle[t]}
              {t === "edit" && pendingIds.size > 0 && <span className="ml-1 text-warn">•</span>}
              {t === "people" && data.others.length > 0 && <span className="ml-1 text-accent">{data.others.length}</span>}
            </button>
          ))}
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-[max(1rem,env(safe-area-inset-bottom))] pt-3" role="tabpanel">
          {!sheetOpen && <p className="text-xs text-text-muted">{APP.project.hint}</p>}
          {sheetOpen && tab === "rooms" && (
            <RoomsPanel
              digest={digest}
              prices={data.prices}
              pendingIds={pendingIds}
              viewRooms={viewRooms}
              onGoTo={goToRoom}
              onEdit={(sel) => {
                setSelection(sel);
                setTab("edit");
              }}
            />
          )}
          {sheetOpen && tab === "edit" && (
            <div className="space-y-5">
              <EditPanel digest={digest} selection={selection} canEdit={canEdit} lookRef={lookRef} prices={data.prices} onEdit={edit} />
              <div>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-muted">{APP.edit.recent}</h3>
                <EditsList
                  entries={data.entries}
                  offline={data.offline}
                  meAuthor={data.me?.author_id ?? null}
                  members={project?.members ?? []}
                  onDismiss={(id) => void data.dismiss(id)}
                />
              </div>
            </div>
          )}
          {sheetOpen && tab === "people" && <PeoplePanel others={data.others} members={project?.members ?? []} meId={data.me?.id ?? null} />}
        </div>
      </section>
    </main>
  );
}
