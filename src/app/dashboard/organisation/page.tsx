"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Building2 } from "lucide-react";
import { ErrorNote, PageHeader, Panel, useDashboardUser } from "@/components/dashboard/DashboardShell";
import { useOrgs } from "@/components/dashboard/OrgContext";
import { errorText, inputClass, linkButton } from "@/components/dashboard/orgUi";
import { useApiData } from "@/components/dashboard/useApiData";
import { Button } from "@/components/ui/Button";
import { formatDate } from "@/lib/api";
import {
  createOrg,
  deleteOrg,
  getOrg,
  isAdmin,
  removeMember,
  renameOrg,
  ROLE_NAMES,
  SEAT_NAMES,
  type OrgSummary,
} from "@/lib/orgs";

export default function OrganisationPage() {
  const { current, orgs, loading, error, select } = useOrgs();

  if (loading) return <p className="text-sm text-text-muted" role="status">Loading your organisations…</p>;
  return (
    <>
      {current ? (
        <OrgOverview key={current.id} org={current} />
      ) : (
        <PageHeader
          title="Organisation"
          description="Buy seats once and run them yourself: invite people, give each a named seat or share floating seats, and see who uses what."
        />
      )}
      {error && <ErrorNote message={error} />}
      {!current && orgs.length > 0 && (
        <Panel className="mb-6">
          <h2 className="font-semibold">Your organisations</h2>
          <ul className="mt-4 divide-y divide-border">
            {orgs.map((o) => (
              <li key={o.id} className="flex items-center justify-between gap-4 py-3 text-sm">
                <span>
                  <span className="text-text-primary">{o.name}</span>{" "}
                  <span className="text-text-muted">· {ROLE_NAMES[o.role]}</span>
                </span>
                <button className={linkButton} onClick={() => select(o.id)}>
                  Open
                </button>
              </li>
            ))}
          </ul>
        </Panel>
      )}
      <CreateOrg first={orgs.length === 0} />
    </>
  );
}

function CreateOrg({ first }: { first: boolean }) {
  const { reload, select } = useOrgs();
  const [open, setOpen] = useState(first);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const org = await createOrg(name.trim());
      await reload();
      select(org.id);
      setName("");
      setOpen(false);
    } catch (err) {
      setError(errorText(err, "Couldn't create the organisation."));
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button className={`mt-6 text-sm ${linkButton}`} onClick={() => setOpen(true)}>
        Create another organisation
      </button>
    );
  }
  return (
    <Panel className="mt-6">
      <h2 className="flex items-center gap-2 font-semibold">
        <Building2 size={18} aria-hidden /> Create an organisation
      </h2>
      <p className="mt-1 text-sm text-text-secondary">
        You become its owner. Your own account and plan stay as they are.
      </p>
      <form onSubmit={submit} className="mt-4 flex flex-col gap-3 sm:flex-row">
        <label htmlFor="org-name" className="sr-only">
          Organisation name
        </label>
        <input
          id="org-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={100}
          required
          placeholder="Practice name, e.g. Studio North"
          className={`flex-1 ${inputClass}`}
        />
        <Button type="submit" disabled={busy || !name.trim()}>
          {busy ? "Creating…" : "Create"}
        </Button>
      </form>
      {error && (
        <div className="mt-4">
          <ErrorNote message={error} />
        </div>
      )}
    </Panel>
  );
}

function OrgOverview({ org }: { org: OrgSummary }) {
  const user = useDashboardUser();
  const router = useRouter();
  const { reload, select } = useOrgs();
  const detail = useApiData(() => getOrg(org.id));
  const [name, setName] = useState(org.name);
  const [renaming, setRenaming] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const d = detail.data;
  const admin = isAdmin(org.role);

  async function act(fn: () => Promise<unknown>, after?: () => void) {
    setBusy(true);
    setError("");
    try {
      await fn();
      after?.();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  const rename = (e: React.FormEvent) => {
    e.preventDefault();
    void act(
      () => renameOrg(org.id, name.trim()),
      () => {
        setRenaming(false);
        void reload();
        void detail.reload();
      }
    );
  };

  const leaveOrDelete = (fn: () => Promise<unknown>) =>
    act(fn, () => {
      select(null);
      void reload();
      router.push("/dashboard/");
    });

  return (
    <>
      <PageHeader
        title={org.name}
        description={`Your role: ${ROLE_NAMES[org.role]} · your seat: ${SEAT_NAMES[org.seat_kind]}`}
      />
      {(detail.error || error) && (
        <div className="mb-6">
          <ErrorNote message={error || detail.error || ""} />
        </div>
      )}
      <div className="grid gap-6 lg:grid-cols-3">
        <Panel>
          <h2 className="font-semibold">Plan</h2>
          {d?.subscription ? (
            <>
              <p className="mt-4 text-3xl font-semibold">{d.subscription.plan_name}</p>
              <p className="mt-1 text-sm text-text-secondary">
                {d.subscription.seats} {d.subscription.seats === 1 ? "seat" : "seats"}
                {d.subscription.current_period_end && ` · until ${formatDate(d.subscription.current_period_end)}`}
              </p>
            </>
          ) : (
            <p className="mt-4 text-sm text-text-secondary">
              {detail.loading ? "Loading…" : "No seats yet. Seats are bought on the Billing page."}
            </p>
          )}
          {(org.role === "owner" || org.role === "billing" || org.role === "admin") && d && (
            <a href={`/dashboard/billing/?org=${org.id}`} className="mt-5 inline-flex items-center gap-1 text-sm text-accent hover:underline">
              Billing <ArrowRight size={14} aria-hidden />
            </a>
          )}
        </Panel>
        <Panel>
          <h2 className="font-semibold">Seats</h2>
          {d ? (
            <p className="mt-4 text-sm text-text-secondary">
              {d.seats.total} in total · {d.seats.named} named · {d.seats.floating} floating
            </p>
          ) : (
            <p className="mt-4 text-sm text-text-muted">Loading…</p>
          )}
          {admin && (
            <Link href="/dashboard/organisation/seats/" className="mt-5 inline-flex items-center gap-1 text-sm text-accent hover:underline">
              Manage seats <ArrowRight size={14} aria-hidden />
            </Link>
          )}
        </Panel>
        <Panel>
          <h2 className="font-semibold">People</h2>
          <p className="mt-4 text-3xl font-semibold">{d?.members ?? "…"}</p>
          <p className="mt-1 text-sm text-text-secondary">
            {d?.sso_required ? "Sign-in through your identity provider is required." : "members"}
          </p>
          <Link href="/dashboard/organisation/members/" className="mt-5 inline-flex items-center gap-1 text-sm text-accent hover:underline">
            Members <ArrowRight size={14} aria-hidden />
          </Link>
        </Panel>
      </div>

      <Panel className="mt-6">
        <h2 className="font-semibold">Settings</h2>
        {admin && (
          <div className="mt-4 text-sm">
            {renaming ? (
              <form onSubmit={rename} className="flex flex-col gap-3 sm:flex-row">
                <label htmlFor="rename" className="sr-only">
                  Organisation name
                </label>
                <input id="rename" value={name} onChange={(e) => setName(e.target.value)} maxLength={100} className={`flex-1 ${inputClass}`} />
                <Button type="submit" size="sm" disabled={busy || !name.trim()}>
                  Save
                </Button>
                <Button type="button" size="sm" variant="ghost" onClick={() => setRenaming(false)}>
                  Cancel
                </Button>
              </form>
            ) : (
              <p className="text-text-secondary">
                Name: <span className="text-text-primary">{org.name}</span> · address{" "}
                <span className="font-mono text-text-primary">{org.slug}</span>{" "}
                <button className={linkButton} onClick={() => setRenaming(true)}>
                  Rename
                </button>
              </p>
            )}
          </div>
        )}
        <div className="mt-4 flex flex-wrap gap-6 text-sm">
          <button
            className="text-text-muted hover:text-red-400"
            disabled={busy}
            onClick={() => {
              if (window.confirm(`Leave ${org.name}? Any seat you hold there is released.`)) {
                void leaveOrDelete(() => removeMember(org.id, user.id));
              }
            }}
          >
            Leave {org.name}
          </button>
        </div>
        {org.role === "owner" && (
          <div className="mt-6 border-t border-border pt-4 text-sm">
            <p className="text-text-secondary">
              Delete the organisation: members lose its seats; the audit log is kept. A live subscription must be
              cancelled first. Type the name to confirm.
            </p>
            <div className="mt-3 flex flex-col gap-3 sm:flex-row">
              <label htmlFor="confirm-delete" className="sr-only">
                Type the organisation name
              </label>
              <input
                id="confirm-delete"
                value={confirmDelete}
                onChange={(e) => setConfirmDelete(e.target.value)}
                placeholder={org.name}
                className={`flex-1 ${inputClass}`}
              />
              <Button
                type="button"
                size="sm"
                variant="secondary"
                disabled={busy || confirmDelete !== org.name}
                onClick={() => void leaveOrDelete(() => deleteOrg(org.id))}
              >
                Delete organisation
              </Button>
            </div>
          </div>
        )}
      </Panel>
    </>
  );
}
