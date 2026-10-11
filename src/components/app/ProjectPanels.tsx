"use client";

import { useEffect, useState } from "react";
import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp } from "lucide-react";
import type { EditRequest } from "@/components/app/useProject";
import { priceKey } from "@/components/app/useProject";
import { fill } from "@/lib/catalogue";
import { APP } from "@/lib/constants";
import {
  FLOOR_FINISHES,
  WALL_FINISHES,
  finishLabel,
  swapChoices,
  type DigestOpening,
  type DigestProduct,
  type DigestRoom,
  type DigestSnapshot,
  type PricedItem,
  type SwapChoice,
} from "@/lib/app";
import { formatMoney } from "@/lib/market";
import type { Member, Presence, ProjectRole } from "@/lib/projects";
import { timeAgo } from "@/lib/time";
import { cn } from "@/lib/utils";
import { applyTheme, fillFace, moveBy, nudgeVector, slideAlong, swapProduct, type Nudge } from "@/viewer/actions";
import type { Look } from "@/viewer/orientation";
import { conflictLine, type ConflictText, type OutboxEntry } from "@/viewer/outbox";

export type Selection = { kind: "room" | "product" | "opening"; id: string } | null;

const chip =
  "min-h-10 rounded-[var(--radius-button)] border px-3 py-2 text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-50";
const chipIdle = "border-border bg-surface-elevated text-text-primary hover:border-accent/50";
const chipOn = "border-accent bg-accent-muted text-text-primary";

function PendingBadge({ show }: { show: boolean }) {
  if (!show) return null;
  return (
    <span className="ml-2 rounded-full border border-warn/60 px-2 py-0.5 text-[11px] font-medium text-warn">{APP.states.pending}</span>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-4 first:mt-0">
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-muted">{title}</h3>
      {children}
    </section>
  );
}

// --- Rooms ----------------------------------------------------------------------------------------

export function RoomsPanel({
  digest,
  prices,
  pendingIds,
  onEdit,
  onGoTo,
  viewRooms,
}: {
  digest: DigestSnapshot | null;
  prices: Record<string, PricedItem>;
  pendingIds: Set<string>;
  onEdit: (sel: NonNullable<Selection>) => void;
  onGoTo: (roomId: string) => void;
  viewRooms: Set<string>;
}) {
  if (!digest) return <p className="text-sm text-text-secondary">{APP.rooms.none}</p>;
  const d = digest.digest;
  const region = d.region ?? "";
  const storeys = [...d.storeys].sort((a, b) => (a.elevation_mm ?? 0) - (b.elevation_mm ?? 0));
  const known = new Set(storeys.map((s) => s.id));
  const groups = [
    ...storeys.map((s) => ({ id: s.id, name: s.name, rooms: d.rooms.filter((r) => r.storey === s.id) })),
    { id: "", name: "", rooms: d.rooms.filter((r) => !r.storey || !known.has(r.storey)) },
  ].filter((g) => g.rooms.length);
  const themeName = (id: string | null | undefined) => d.themes.find((t) => t.id === id)?.name ?? APP.rooms.noTheme;

  return (
    <div>
      <p className="mb-3 text-xs text-text-muted">{fill(APP.rooms.asOf, { seq: digest.at_seq, when: timeAgo(digest.created_at) })}</p>
      {groups.map((g) => (
        <Section key={g.id || "other"} title={g.name || APP.tabs.rooms}>
          <ul className="space-y-3">
            {g.rooms.map((room) => {
              const products = d.products.filter((p) => p.room === room.id);
              const openings = (d.openings ?? []).filter((o) => o.room === room.id);
              return (
                <li key={room.id} className="rounded-[var(--radius-card)] border border-border bg-surface p-3" data-room={room.id}>
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="font-medium">
                        {room.name}
                        <PendingBadge show={pendingIds.has(room.id)} />
                      </p>
                      <p className="text-xs text-text-secondary">
                        {room.area_m2 != null && fill(APP.rooms.area, { area: room.area_m2.toFixed(1) })}
                        {" · "}
                        {APP.rooms.theme}: {themeName(room.theme)}
                        {" · "}
                        {APP.rooms.floor}: {finishLabel(room.finishes?.floor, FLOOR_FINISHES) ?? APP.rooms.noFinish}
                      </p>
                    </div>
                    <div className="flex shrink-0 gap-2">
                      {viewRooms.has(room.id) && (
                        <button type="button" className={cn(chip, chipIdle)} onClick={() => onGoTo(room.id)}>
                          {APP.rooms.goTo}
                        </button>
                      )}
                      <button type="button" className={cn(chip, chipIdle)} onClick={() => onEdit({ kind: "room", id: room.id })}>
                        {APP.rooms.edit}
                      </button>
                    </div>
                  </div>
                  {products.length > 0 && (
                    <ul className="mt-2 divide-y divide-border-subtle">
                      {products.map((p) => {
                        const priced = prices[priceKey(p.product)]?.price;
                        return (
                          <li key={p.id} className="flex items-center justify-between gap-2 py-2 text-sm">
                            <button type="button" className="text-left hover:text-accent" onClick={() => onEdit({ kind: "product", id: p.id })}>
                              {p.name}
                              <PendingBadge show={pendingIds.has(p.id)} />
                            </button>
                            <span className="shrink-0 text-xs text-text-secondary">
                              {priced ? formatMoney(priced) : region ? fill(APP.rooms.noPrice, { region }) : ""}
                            </span>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                  {openings.length > 0 && (
                    <p className="mt-1 text-xs text-text-secondary">
                      {APP.rooms.openings}:{" "}
                      {openings.map((o, i) => (
                        <span key={o.id}>
                          {i > 0 && ", "}
                          <button type="button" className="hover:text-accent" onClick={() => onEdit({ kind: "opening", id: o.id })}>
                            {o.name}
                          </button>
                          <PendingBadge show={pendingIds.has(o.id)} />
                        </span>
                      ))}
                    </p>
                  )}
                </li>
              );
            })}
          </ul>
        </Section>
      ))}
    </div>
  );
}

// --- Edit -------------------------------------------------------------------------------------------

export function EditPanel({
  digest,
  selection,
  canEdit,
  lookRef,
  prices,
  onEdit,
}: {
  digest: DigestSnapshot | null;
  selection: Selection;
  canEdit: boolean;
  lookRef: React.MutableRefObject<Look>;
  prices: Record<string, PricedItem>;
  onEdit: (req: EditRequest) => void;
}) {
  const d = digest?.digest;
  const room = selection?.kind === "room" ? d?.rooms.find((r) => r.id === selection.id) : undefined;
  const product = selection?.kind === "product" ? d?.products.find((p) => p.id === selection.id) : undefined;
  const opening = selection?.kind === "opening" ? d?.openings?.find((o) => o.id === selection.id) : undefined;
  if (!d || (!room && !product && !opening)) return <p className="text-sm text-text-secondary">{APP.edit.pick}</p>;
  return (
    <div>
      {!canEdit && <p className="mb-3 rounded-[var(--radius-button)] border border-border p-3 text-sm text-text-secondary">{APP.edit.viewerOnly}</p>}
      {room && <RoomEdit key={room.id} room={room} themes={d.themes} canEdit={canEdit} onEdit={onEdit} />}
      {product && (
        <ProductEdit
          key={product.id}
          product={product}
          region={d.region}
          canEdit={canEdit}
          lookRef={lookRef}
          price={prices[priceKey(product.product)]?.price ?? null}
          onEdit={onEdit}
        />
      )}
      {opening && <OpeningEdit opening={opening} canEdit={canEdit} onEdit={onEdit} />}
    </div>
  );
}

function RoomEdit({
  room,
  themes,
  canEdit,
  onEdit,
}: {
  room: DigestRoom;
  themes: { id: string; name: string }[];
  canEdit: boolean;
  onEdit: (req: EditRequest) => void;
}) {
  const walls = room.walls ?? [];
  const [wallId, setWallId] = useState(walls[0]?.id ?? "");
  const wall = walls.find((w) => w.id === wallId) ?? walls[0];
  const floorNow = finishLabel(room.finishes?.floor, FLOOR_FINISHES);
  return (
    <div>
      <h3 className="text-lg font-semibold">{room.name}</h3>
      <Section title={APP.edit.theme}>
        <div className="flex flex-wrap gap-2">
          {themes.map((t) => (
            <button
              key={t.id}
              type="button"
              disabled={!canEdit}
              className={cn(chip, t.id === room.theme ? chipOn : chipIdle)}
              onClick={() =>
                onEdit({ name: APP.opNames.theme, label: `${APP.edit.theme}: ${t.name}`, subject: room.id, call: applyTheme(room.id, t.id) })
              }
            >
              {t.name}
            </button>
          ))}
        </div>
      </Section>
      <Section title={APP.edit.floor}>
        <div className="flex flex-wrap gap-2">
          {FLOOR_FINISHES.map((f) => (
            <button
              key={f.id}
              type="button"
              disabled={!canEdit}
              className={cn(chip, floorNow === f.label ? chipOn : chipIdle)}
              onClick={() =>
                onEdit({
                  name: APP.opNames.floor,
                  label: `${APP.edit.floor}: ${f.label} (${room.name})`,
                  subject: room.id,
                  call: fillFace(room.id, "floor", f.finish),
                })
              }
            >
              {f.label}
            </button>
          ))}
        </div>
      </Section>
      {wall && (
        <Section title={APP.edit.wall}>
          <label className="mb-2 flex items-center gap-2 text-sm text-text-secondary">
            {APP.edit.wallPick}
            <select
              value={wall.id}
              onChange={(e) => setWallId(e.target.value)}
              className="rounded-[var(--radius-button)] border border-border bg-background px-2 py-1.5 text-text-primary"
            >
              {walls.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
            </select>
          </label>
          <div className="flex flex-wrap gap-2">
            {WALL_FINISHES.map((f) => (
              <button
                key={f.id}
                type="button"
                disabled={!canEdit}
                className={cn(chip, chipIdle)}
                onClick={() =>
                  onEdit({
                    name: APP.opNames.wall,
                    label: `${APP.edit.wall}: ${f.label} (${room.name}, ${wall.name})`,
                    subject: room.id,
                    call: fillFace(wall.id, wall.face, f.finish),
                  })
                }
              >
                {f.label}
              </button>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}

const STEPS = [50, 250];

function StepPicker({ step, setStep }: { step: number; setStep: (n: number) => void }) {
  return (
    <div className="mb-2 flex items-center gap-2 text-sm text-text-secondary">
      {APP.edit.step}
      {STEPS.map((n) => (
        <button key={n} type="button" className={cn(chip, n === step ? chipOn : chipIdle)} onClick={() => setStep(n)}>
          {fill(APP.edit.mm, { n })}
        </button>
      ))}
    </div>
  );
}

function ProductEdit({
  product,
  region,
  canEdit,
  lookRef,
  price,
  onEdit,
}: {
  product: DigestProduct;
  region: string | null | undefined;
  canEdit: boolean;
  lookRef: React.MutableRefObject<Look>;
  price: PricedItem["price"];
  onEdit: (req: EditRequest) => void;
}) {
  const [step, setStep] = useState(250);
  const [choices, setChoices] = useState<SwapChoice[] | null>(null);
  const [swapFailed, setSwapFailed] = useState(false);
  useEffect(() => {
    let live = true;
    swapChoices(product, region)
      .then((c) => live && setChoices(c))
      .catch(() => {
        if (!live) return;
        setChoices([]);
        setSwapFailed(true);
      });
    return () => {
      live = false;
    };
  }, [product, region]);

  const nudge = (dir: Nudge, label: string) =>
    onEdit({
      name: fill(APP.opNames.move, { name: product.name }),
      label: `${APP.edit.move} ${product.name}: ${label} ${fill(APP.edit.mm, { n: step })}`,
      subject: product.id,
      call: moveBy([product.id], nudgeVector(lookRef.current.yawDeg, dir, step)),
    });
  const pad: { dir: Nudge; label: string; icon: React.ReactNode; area: string }[] = [
    { dir: "forward", label: APP.edit.forward, icon: <ArrowUp className="h-4 w-4" />, area: "col-start-2" },
    { dir: "left", label: APP.edit.left, icon: <ArrowLeft className="h-4 w-4" />, area: "col-start-1 row-start-2" },
    { dir: "right", label: APP.edit.right, icon: <ArrowRight className="h-4 w-4" />, area: "col-start-3 row-start-2" },
    { dir: "back", label: APP.edit.back, icon: <ArrowDown className="h-4 w-4" />, area: "col-start-2 row-start-3" },
  ];
  return (
    <div>
      <h3 className="text-lg font-semibold">{product.name}</h3>
      {price && <p className="text-sm text-text-secondary">{formatMoney(price)}</p>}
      <Section title={APP.edit.move}>
        <StepPicker step={step} setStep={setStep} />
        <div className="grid w-60 grid-cols-3 grid-rows-3 gap-2">
          {pad.map((b) => (
            <button
              key={b.dir}
              type="button"
              disabled={!canEdit}
              aria-label={`${b.label} ${fill(APP.edit.mm, { n: step })}`}
              className={cn(chip, chipIdle, b.area, "flex items-center justify-center gap-1")}
              onClick={() => nudge(b.dir, b.label)}
            >
              {b.icon}
              <span className="text-xs">{b.label}</span>
            </button>
          ))}
        </div>
        <p className="mt-2 text-xs text-text-muted">{APP.edit.moveHint}</p>
      </Section>
      <Section title={APP.edit.swap}>
        {choices === null && <p className="text-sm text-text-secondary">{APP.edit.swapLoading}</p>}
        {choices?.length === 0 && <p className="text-sm text-text-secondary">{swapFailed ? APP.edit.swapOffline : APP.edit.swapNone}</p>}
        <ul className="space-y-2">
          {choices?.map((c) => (
            <li key={`${c.ref.sku}|${c.ref.variant_id}`}>
              <button
                type="button"
                disabled={!canEdit}
                className={cn(chip, chipIdle, "flex w-full items-center justify-between gap-3 text-left")}
                onClick={() =>
                  onEdit({
                    name: fill(APP.opNames.swap, { name: product.name }),
                    label: `${APP.edit.swap} ${c.name}${c.options ? ` (${c.options})` : ""}`,
                    subject: product.id,
                    call: swapProduct(product.id, c.ref, product.room ?? undefined),
                  })
                }
              >
                <span>
                  {c.name}
                  {c.options && <span className="block text-xs text-text-secondary">{c.options}</span>}
                </span>
                <span className="shrink-0 text-xs text-text-secondary">{c.price ? formatMoney(c.price) : ""}</span>
              </button>
            </li>
          ))}
        </ul>
      </Section>
    </div>
  );
}

function OpeningEdit({ opening, canEdit, onEdit }: { opening: DigestOpening; canEdit: boolean; onEdit: (req: EditRequest) => void }) {
  const [step, setStep] = useState(50);
  const slide = (sign: 1 | -1) =>
    onEdit({
      name: fill(APP.opNames.slide, { name: opening.name }),
      label: `${opening.name}: ${fill(sign > 0 ? APP.edit.slideRight : APP.edit.slideLeft, { step })}`,
      subject: opening.id,
      call: slideAlong(opening.id, sign * step),
    });
  return (
    <div>
      <h3 className="text-lg font-semibold">{opening.name}</h3>
      <Section title={APP.edit.slide}>
        <StepPicker step={step} setStep={setStep} />
        <div className="flex gap-2">
          <button type="button" disabled={!canEdit} className={cn(chip, chipIdle)} onClick={() => slide(-1)}>
            {fill(APP.edit.slideLeft, { step })}
          </button>
          <button type="button" disabled={!canEdit} className={cn(chip, chipIdle)} onClick={() => slide(1)}>
            {fill(APP.edit.slideRight, { step })}
          </button>
        </div>
      </Section>
    </div>
  );
}

// --- Your edits ---------------------------------------------------------------------------------------

export function EditsList({
  entries,
  offline,
  meAuthor,
  members,
  onDismiss,
}: {
  entries: OutboxEntry[];
  offline: boolean;
  meAuthor: string | null;
  members: Member[];
  onDismiss: (opId: string) => void;
}) {
  if (!entries.length) return <p className="text-sm text-text-secondary">{APP.edit.none}</p>;
  const names = new Map(members.flatMap((m) => (m.author_id && m.name ? [[m.author_id, m.name] as const] : [])));
  const text: ConflictText = {
    named: (name) => fill(APP.conflict, { name }),
    self: APP.conflictSelf,
    agent: APP.agentAuthor,
    someone: APP.someone,
  };
  return (
    <ul className="space-y-2" aria-live="polite">
      {entries.map((e) => {
        let state: string;
        let tone = "text-text-secondary";
        if (e.state === "pending") {
          state = offline ? APP.states.waiting : APP.states.pending;
          tone = "text-warn";
        } else if (e.state === "accepted") {
          state = APP.states.saved;
          tone = "text-accent";
        } else if (e.state === "rejected") {
          state = conflictLine(e.winner, meAuthor, names, text);
          tone = "text-warn";
        } else {
          state = fill(APP.states.failed, { reason: e.reason ?? APP.errors.generic });
          tone = "text-warn";
        }
        return (
          <li key={e.op_id} className="flex items-start justify-between gap-3 rounded-[var(--radius-button)] border border-border p-2.5 text-sm" data-state={e.state}>
            <span>
              {e.label}
              <span className={cn("block text-xs", tone)}>{state}</span>
            </span>
            {(e.state === "rejected" || e.state === "failed") && (
              <button type="button" className="shrink-0 text-xs text-text-secondary hover:text-text-primary" onClick={() => onDismiss(e.op_id)}>
                {APP.dismiss}
              </button>
            )}
          </li>
        );
      })}
    </ul>
  );
}

// --- People ---------------------------------------------------------------------------------------------

export function PeoplePanel({ others, members, meId }: { others: Presence[]; members: Member[]; meId: number | null }) {
  const clients = APP.people.clients as Record<string, string>;
  const roles = APP.roles as Record<ProjectRole, string>;
  return (
    <div>
      <Section title={APP.people.here}>
        {others.length === 0 ? (
          <p className="text-sm text-text-secondary">{APP.people.none}</p>
        ) : (
          <ul className="space-y-1.5">
            {others.map((p) => (
              <li key={p.replica_id} className="flex items-center gap-2 text-sm">
                <span className="h-2 w-2 rounded-full bg-accent" aria-hidden="true" />
                {p.name}
                <span className="text-xs text-text-secondary">{clients[p.client] ?? p.client}</span>
              </li>
            ))}
          </ul>
        )}
      </Section>
      <Section title={APP.people.members}>
        <ul className="space-y-1.5">
          {members
            .filter((m) => m.state === "active")
            .map((m) => (
              <li key={`${m.user_id}`} className="flex items-center justify-between text-sm">
                <span>
                  {m.name ?? m.email}
                  {m.user_id === meId && <span className="text-text-muted"> ({APP.people.you})</span>}
                </span>
                <span className="text-xs text-text-secondary">{roles[m.role]}</span>
              </li>
            ))}
        </ul>
      </Section>
    </div>
  );
}
