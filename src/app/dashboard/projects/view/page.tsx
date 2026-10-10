"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, History, Trash2, UserPlus, Users } from "lucide-react";
import {
  ErrorNote,
  PageHeader,
  Panel,
  useDashboardUser,
} from "@/components/dashboard/DashboardShell";
import { Button } from "@/components/ui/Button";
import { ApiError, formatDate } from "@/lib/api";
import { fill } from "@/lib/catalogue";
import { PROJECTS } from "@/lib/constants";
import {
  changeRole,
  deleteProject,
  formatBytes,
  getProject,
  heartbeat,
  hex32,
  inviteMember,
  listVersions,
  memberRef,
  nameVersion,
  projectError,
  removeMember,
  renameProject,
  restoreVersion,
  type Member,
  type OpenProject,
  type Presence,
  type Version,
} from "@/lib/projects";
import { timeAgo } from "@/lib/time";

const inputClass =
  "min-w-0 rounded-[var(--radius-button)] border border-border bg-background px-4 py-2.5 text-text-primary placeholder:text-text-muted outline-none focus:border-accent/50";
const HEARTBEAT_MS = 10_000;

type Role = "editor" | "viewer";

function ProjectView({ pid }: { pid: string }) {
  const me = useDashboardUser();
  const router = useRouter();
  const [project, setProject] = useState<OpenProject | null>(null);
  const [versions, setVersions] = useState<Version[]>([]);
  const [others, setOthers] = useState<Presence[]>([]);
  const [missing, setMissing] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [p, v] = await Promise.all([getProject(pid), listVersions(pid)]);
      setProject(p);
      setVersions(v.versions);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) setMissing(true);
      else setError(projectError(err));
    }
  }, [pid]);

  useEffect(() => {
    void load();
  }, [load]);

  // Presence: this tab is one "web" replica while the page is open.
  const replica = useRef<string>("");
  useEffect(() => {
    if (missing) return;
    if (!replica.current) replica.current = hex32();
    let live = true;
    const beat = () =>
      heartbeat(pid, replica.current)
        .then((res) => live && setOthers(res.others))
        .catch(() => undefined);
    void beat();
    const timer = window.setInterval(beat, HEARTBEAT_MS);
    const leave = () => void heartbeat(pid, replica.current, true).catch(() => undefined);
    window.addEventListener("pagehide", leave);
    return () => {
      live = false;
      window.clearInterval(timer);
      window.removeEventListener("pagehide", leave);
      leave();
    };
  }, [pid, missing]);

  async function run(key: string, action: () => Promise<void>) {
    setBusy(key);
    setError("");
    setNotice("");
    try {
      await action();
    } catch (err) {
      setError(projectError(err));
    } finally {
      setBusy(null);
    }
  }

  if (missing) {
    return (
      <>
        <BackLink />
        <Panel>
          <p className="text-text-primary">{PROJECTS.notFound}</p>
        </Panel>
      </>
    );
  }
  if (!project) {
    return (
      <>
        <BackLink />
        {error ? <ErrorNote message={error} /> : <p className="text-sm text-text-muted" role="status">{PROJECTS.loading}</p>}
      </>
    );
  }

  const isOwner = project.role === "owner";
  const canEdit = project.role !== "viewer";

  return (
    <>
      <BackLink />
      <PageHeader
        title={project.name}
        description={
          isOwner
            ? PROJECTS.roles.owner
            : `${PROJECTS.roles[project.role]} · ${fill(PROJECTS.summary.sharedBy, { name: project.owner?.name ?? "—" })}`
        }
      />
      {error && (
        <div className="mb-6">
          <ErrorNote message={error} />
        </div>
      )}
      {notice && (
        <p role="status" className="mb-6 rounded-[var(--radius-button)] border border-accent/30 bg-accent/5 px-4 py-3 text-sm text-text-primary">
          {notice}
        </p>
      )}

      <Panel className="mb-6">
        <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
          <Stat label={PROJECTS.summary.operations} value={String(project.head_seq)} />
          <Stat label={PROJECTS.summary.stored} value={formatBytes(project.bytes)} />
          <Stat
            label={PROJECTS.summary.snapshot}
            value={
              project.latest_snapshot
                ? fill(PROJECTS.summary.snapshotAt, { seq: project.latest_snapshot.at_seq })
                : PROJECTS.summary.noSnapshot
            }
            hint={project.latest_snapshot ? timeAgo(project.latest_snapshot.created_at) : undefined}
          />
          {isOwner && (
            <Stat
              label={PROJECTS.summary.storage}
              value={
                project.quota.bytes == null
                  ? fill(PROJECTS.summary.unlimited, { used: formatBytes(project.quota.bytes_used) })
                  : fill(PROJECTS.summary.storageOf, {
                      used: formatBytes(project.quota.bytes_used),
                      limit: formatBytes(project.quota.bytes),
                    })
              }
            />
          )}
        </dl>
        {isOwner && (
          <RenameForm
            key={project.name}
            name={project.name}
            busy={busy === "rename"}
            onRename={(name) =>
              run("rename", async () => {
                await renameProject(pid, name);
                await load();
              })
            }
          />
        )}
      </Panel>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel>
          <h2 className="flex items-center gap-2 font-semibold">
            <Users size={16} aria-hidden /> {PROJECTS.members.title}
          </h2>
          <ul className="mt-4 divide-y divide-border text-sm">
            {project.members.map((m) => (
              <MemberRow
                key={memberRef(m)}
                member={m}
                isMe={m.user_id === me.id}
                isOwner={isOwner}
                busy={busy === memberRef(m)}
                onRole={(role) =>
                  run(memberRef(m), async () => {
                    await changeRole(pid, memberRef(m), role);
                    await load();
                  })
                }
                onRemove={() =>
                  run(memberRef(m), async () => {
                    await removeMember(pid, memberRef(m));
                    if (m.user_id === me.id) router.push("/dashboard/projects/");
                    else await load();
                  })
                }
              />
            ))}
          </ul>
          {isOwner && (
            <InviteForm
              busy={busy === "invite"}
              onInvite={(email, role) =>
                run("invite", async () => {
                  const member = await inviteMember(pid, email, role);
                  setNotice(fill(PROJECTS.members.sent, { email: member.email }));
                  await load();
                })
              }
            />
          )}
          <p className="mt-4 text-xs text-text-muted">{PROJECTS.members.roleHelp}</p>
        </Panel>

        <Panel>
          <h2 className="flex items-center gap-2 font-semibold">
            <History size={16} aria-hidden /> {PROJECTS.versions.title}
          </h2>
          {versions.length === 0 ? (
            <p className="mt-4 text-sm text-text-muted">{PROJECTS.versions.empty}</p>
          ) : (
            <ul className="mt-4 divide-y divide-border text-sm">
              {versions.map((v) => (
                <VersionRow
                  key={v.version_id}
                  version={v}
                  canRestore={canEdit}
                  busy={busy === v.version_id}
                  onRestore={() =>
                    run(v.version_id, async () => {
                      const res = await restoreVersion(pid, v.version_id);
                      setNotice(fill(PROJECTS.versions.restored, { seq: res.op.server_seq }));
                      await load();
                    })
                  }
                />
              ))}
            </ul>
          )}
          {canEdit &&
            (project.latest_snapshot ? (
              <VersionForm
                busy={busy === "version"}
                atSeq={project.latest_snapshot.at_seq}
                onCreate={(name, note) =>
                  run("version", async () => {
                    const snap = project.latest_snapshot!;
                    await nameVersion(pid, { name, note, at_seq: snap.at_seq, snapshot_id: snap.snapshot_id });
                    await load();
                  })
                }
              />
            ) : (
              <p className="mt-4 text-xs text-text-muted">{PROJECTS.versions.needSnapshot}</p>
            ))}
        </Panel>
      </div>

      <Panel className="mt-6">
        <h2 className="font-semibold">{PROJECTS.presence.title}</h2>
        {others.length === 0 ? (
          <p className="mt-3 text-sm text-text-muted">{PROJECTS.presence.empty}</p>
        ) : (
          <ul className="mt-3 flex flex-wrap gap-2 text-sm" data-presence={others.length}>
            {others.map((o) => (
              <li key={o.replica_id} className="rounded-full border border-border px-3 py-1 text-text-secondary">
                <span className="text-text-primary">{o.name}</span> · {PROJECTS.presence.clients[o.client]}
                {o.editing.length > 0 && <> · {fill(PROJECTS.presence.editing, { n: o.editing.length })}</>}
              </li>
            ))}
          </ul>
        )}
      </Panel>

      {isOwner && (
        <DeletePanel
          name={project.name}
          busy={busy === "delete"}
          onDelete={() =>
            run("delete", async () => {
              await deleteProject(pid);
              router.push("/dashboard/projects/");
            })
          }
        />
      )}
    </>
  );
}

function BackLink() {
  return (
    <Link href="/dashboard/projects/" className="mb-4 inline-flex items-center gap-1 text-sm text-text-muted hover:text-accent">
      <ArrowLeft size={14} aria-hidden /> {PROJECTS.back}
    </Link>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div>
      <dt className="text-text-muted">{label}</dt>
      <dd className="mt-1 text-lg font-semibold tabular-nums text-text-primary">{value}</dd>
      {hint && <dd className="text-xs text-text-muted">{hint}</dd>}
    </div>
  );
}

function RenameForm({ name, busy, onRename }: { name: string; busy: boolean; onRename: (name: string) => void }) {
  const [value, setValue] = useState(name);
  return (
    <form
      className="mt-6 flex flex-col gap-3 border-t border-border pt-6 sm:flex-row"
      onSubmit={(e) => {
        e.preventDefault();
        if (value.trim() && value.trim() !== name) onRename(value.trim());
      }}
    >
      <label htmlFor="rename" className="sr-only">
        {PROJECTS.rename.label}
      </label>
      <input id="rename" value={value} maxLength={120} onChange={(e) => setValue(e.target.value)} className={`${inputClass} flex-1`} />
      <Button type="submit" variant="secondary" disabled={busy || !value.trim() || value.trim() === name}>
        {busy ? PROJECTS.rename.busy : PROJECTS.rename.submit}
      </Button>
    </form>
  );
}

function MemberRow({
  member,
  isMe,
  isOwner,
  busy,
  onRole,
  onRemove,
}: {
  member: Member;
  isMe: boolean;
  isOwner: boolean;
  busy: boolean;
  onRole: (role: Role) => void;
  onRemove: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const removable = member.role !== "owner" && (isOwner || isMe);
  const label = member.state === "invited" ? PROJECTS.members.withdraw : isMe ? PROJECTS.members.leave : PROJECTS.members.remove;
  return (
    <li className="flex flex-wrap items-center gap-3 py-3" data-member={member.email}>
      <div className="min-w-0 flex-1">
        <p className="truncate text-text-primary">
          {member.name ?? member.email}
          {isMe && <span className="text-text-muted"> ({PROJECTS.members.you})</span>}
        </p>
        <p className="truncate text-xs text-text-muted">
          {member.name ? member.email : null}
          {member.state === "invited" && <>{member.name ? " · " : ""}{PROJECTS.members.invited} {formatDate(member.invited_at)}</>}
        </p>
      </div>
      {isOwner && member.role !== "owner" ? (
        <select
          aria-label={PROJECTS.members.roleLabel}
          value={member.role}
          disabled={busy}
          onChange={(e) => onRole(e.target.value as Role)}
          className="rounded-[var(--radius-button)] border border-border bg-background px-2 py-1.5 text-text-primary"
        >
          <option value="editor">{PROJECTS.roles.editor}</option>
          <option value="viewer">{PROJECTS.roles.viewer}</option>
        </select>
      ) : (
        <span className="text-text-secondary">{PROJECTS.roles[member.role]}</span>
      )}
      {removable &&
        (confirming ? (
          <span className="inline-flex gap-3">
            <button type="button" className="text-red-400 hover:underline" disabled={busy} onClick={onRemove}>
              {PROJECTS.members.confirm}
            </button>
            <button type="button" className="text-text-muted hover:underline" onClick={() => setConfirming(false)}>
              {PROJECTS.members.cancel}
            </button>
          </span>
        ) : (
          <button type="button" className="text-text-muted hover:text-red-400" onClick={() => setConfirming(true)}>
            {label}
          </button>
        ))}
    </li>
  );
}

function InviteForm({ busy, onInvite }: { busy: boolean; onInvite: (email: string, role: Role) => void }) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("editor");
  return (
    <form
      className="mt-4 flex flex-col gap-3 border-t border-border pt-4 sm:flex-row"
      onSubmit={(e) => {
        e.preventDefault();
        if (!email.trim()) return;
        onInvite(email.trim(), role);
        setEmail("");
      }}
    >
      <label htmlFor="invite-email" className="sr-only">
        {PROJECTS.members.emailLabel}
      </label>
      <input
        id="invite-email"
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder={PROJECTS.members.emailPlaceholder}
        className={`${inputClass} flex-1`}
      />
      <select
        aria-label={PROJECTS.members.roleLabel}
        value={role}
        onChange={(e) => setRole(e.target.value as Role)}
        className="rounded-[var(--radius-button)] border border-border bg-background px-3 py-2.5 text-text-primary"
      >
        <option value="editor">{PROJECTS.roles.editor}</option>
        <option value="viewer">{PROJECTS.roles.viewer}</option>
      </select>
      <Button type="submit" disabled={busy || !email.trim()}>
        <UserPlus size={16} aria-hidden />
        <span className="ml-2">{busy ? PROJECTS.members.inviting : PROJECTS.members.invite}</span>
      </Button>
      <p className="sr-only">{PROJECTS.members.pending}</p>
    </form>
  );
}

function VersionRow({
  version,
  canRestore,
  busy,
  onRestore,
}: {
  version: Version;
  canRestore: boolean;
  busy: boolean;
  onRestore: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  return (
    <li className="py-3" data-version={version.name}>
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-text-primary">{version.name}</p>
          <p className="text-xs text-text-muted">
            {fill(PROJECTS.versions.at, { seq: version.at_seq })} · {formatDate(version.created_at)}
          </p>
        </div>
        {canRestore && !confirming && (
          <Button variant="secondary" size="sm" onClick={() => setConfirming(true)} disabled={busy}>
            {busy ? PROJECTS.versions.restoring : PROJECTS.versions.restore}
          </Button>
        )}
      </div>
      {version.note && <p className="mt-1 text-xs text-text-secondary">{version.note}</p>}
      {confirming && (
        <div className="mt-3 rounded-[var(--radius-button)] border border-warn/30 bg-warn/5 p-3 text-xs text-text-primary">
          <p>{fill(PROJECTS.versions.confirmRestore, { name: version.name })}</p>
          <div className="mt-3 flex gap-3">
            <Button
              size="sm"
              onClick={() => {
                setConfirming(false);
                onRestore();
              }}
            >
              {PROJECTS.versions.restore}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setConfirming(false)}>
              {PROJECTS.members.cancel}
            </Button>
          </div>
        </div>
      )}
    </li>
  );
}

function VersionForm({ busy, atSeq, onCreate }: { busy: boolean; atSeq: number; onCreate: (name: string, note: string) => void }) {
  const [name, setName] = useState("");
  const [note, setNote] = useState("");
  return (
    <form
      className="mt-4 space-y-3 border-t border-border pt-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (!name.trim()) return;
        onCreate(name.trim(), note.trim());
        setName("");
        setNote("");
      }}
    >
      <label htmlFor="version-name" className="sr-only">
        {PROJECTS.versions.nameLabel}
      </label>
      <input
        id="version-name"
        value={name}
        maxLength={120}
        onChange={(e) => setName(e.target.value)}
        placeholder={PROJECTS.versions.namePlaceholder}
        className={`${inputClass} w-full`}
      />
      <label htmlFor="version-note" className="sr-only">
        {PROJECTS.versions.noteLabel}
      </label>
      <input
        id="version-note"
        value={note}
        maxLength={2000}
        onChange={(e) => setNote(e.target.value)}
        placeholder={PROJECTS.versions.noteLabel}
        className={`${inputClass} w-full`}
      />
      <Button type="submit" variant="secondary" disabled={busy || !name.trim()}>
        {busy ? PROJECTS.versions.creating : PROJECTS.versions.create}
      </Button>
      <span className="ml-3 text-xs text-text-muted">{fill(PROJECTS.versions.at, { seq: atSeq })}</span>
    </form>
  );
}

function DeletePanel({ name, busy, onDelete }: { name: string; busy: boolean; onDelete: () => void }) {
  const [typed, setTyped] = useState("");
  const label = fill(PROJECTS.danger.confirmLabel, { name });
  return (
    <Panel className="mt-6 border-red-500/30">
      <h2 className="flex items-center gap-2 font-semibold text-red-300">
        <Trash2 size={16} aria-hidden /> {PROJECTS.danger.title}
      </h2>
      <p className="mt-2 text-sm text-text-secondary">{PROJECTS.danger.text}</p>
      <form
        className="mt-4 flex flex-col gap-3 sm:flex-row"
        onSubmit={(e) => {
          e.preventDefault();
          if (typed === name) onDelete();
        }}
      >
        <label htmlFor="delete-confirm" className="sr-only">
          {label}
        </label>
        <input
          id="delete-confirm"
          value={typed}
          onChange={(e) => setTyped(e.target.value)}
          placeholder={label}
          autoComplete="off"
          className={`${inputClass} flex-1`}
        />
        <button
          type="submit"
          disabled={busy || typed !== name}
          className="inline-flex h-10 items-center justify-center rounded-[var(--radius-button)] border border-red-500/60 px-6 text-sm font-medium text-red-300 transition-colors hover:bg-red-500/10 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {busy ? PROJECTS.danger.busy : PROJECTS.danger.submit}
        </button>
      </form>
    </Panel>
  );
}

function ViewInner() {
  const params = useSearchParams();
  const pid = (params.get("id") ?? "").toLowerCase();
  if (!/^[0-9a-f]{32}$/.test(pid)) {
    return (
      <>
        <BackLink />
        <Panel>
          <p className="text-text-primary">{PROJECTS.missingId}</p>
        </Panel>
      </>
    );
  }
  return <ProjectView key={pid} pid={pid} />;
}

export default function ProjectViewPage() {
  return (
    <Suspense fallback={null}>
      <ViewInner />
    </Suspense>
  );
}
