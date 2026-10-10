"use client";

import { useState } from "react";
import { ShieldAlert } from "lucide-react";
import { ErrorNote, PageHeader, Panel } from "@/components/dashboard/DashboardShell";
import { OrgGate } from "@/components/dashboard/OrgContext";
import { dangerButton, errorText, inputClass, linkButton } from "@/components/dashboard/orgUi";
import { useApiData } from "@/components/dashboard/useApiData";
import { Button } from "@/components/ui/Button";
import { formatDate } from "@/lib/api";
import {
  addDomain,
  getSso,
  newBreakGlass,
  removeDomain,
  saveSso,
  verifyDomain,
  type OrgSummary,
  type SsoSettings,
} from "@/lib/orgs";

export default function SsoPage() {
  return <OrgGate level="owner">{(org) => <SsoView key={org.id} org={org} />}</OrgGate>;
}

function Copyable({ label, value }: { label: string; value: string }) {
  return (
    <div className="text-sm">
      <p className="text-text-muted">{label}</p>
      <code className="mt-1 block break-all rounded-[var(--radius-button)] border border-border bg-background px-3 py-2 font-mono text-xs text-text-primary">
        {value}
      </code>
    </div>
  );
}

function SsoView({ org }: { org: OrgSummary }) {
  const sso = useApiData(() => getSso(org.id));
  const s = sso.data;
  return (
    <>
      <PageHeader
        title="Single sign-on"
        description={`Let everyone at ${org.name} sign in through your identity provider (OpenID Connect or SAML 2.0). People with an address in a verified domain join as members the first time they sign in.`}
      />
      {sso.error && (
        <div className="mb-6">
          <ErrorNote message={sso.error} />
        </div>
      )}
      {sso.loading && !s && <p className="text-sm text-text-muted">Loading…</p>}
      {s && (
        <>
          <Domains org={org} sso={s} reload={sso.reload} />
          <Connection org={org} sso={s} onSaved={(next) => sso.setData(next)} />
        </>
      )}
    </>
  );
}

function Domains({ org, sso, reload }: { org: OrgSummary; sso: SsoSettings; reload: () => Promise<void> }) {
  const [domain, setDomain] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await fn();
      await reload();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel className="mb-6">
      <h2 className="font-semibold">1 · Verified e-mail domains</h2>
      <p className="mt-1 text-sm text-text-secondary">
        Add each domain your people sign in with, publish the TXT record at your DNS host, then press Verify.
      </p>
      <form
        className="mt-4 flex flex-col gap-3 sm:flex-row"
        onSubmit={(e) => {
          e.preventDefault();
          void act(async () => {
            await addDomain(org.id, domain.trim());
            setDomain("");
          });
        }}
      >
        <label htmlFor="domain" className="sr-only">
          Domain
        </label>
        <input
          id="domain"
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          placeholder="practice.com"
          className={`flex-1 ${inputClass}`}
        />
        <Button type="submit" size="sm" disabled={busy || !domain.trim()}>
          Add domain
        </Button>
      </form>
      {error && (
        <div className="mt-4">
          <ErrorNote message={error} />
        </div>
      )}
      <ul className="mt-4 divide-y divide-border">
        {sso.domains.map((d) => (
          <li key={d.domain} className="py-4 text-sm" data-domain={d.domain}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span className="font-medium text-text-primary">
                {d.domain}{" "}
                {d.verified_at ? (
                  <span className="ml-2 text-emerald-400">verified {formatDate(d.verified_at)}</span>
                ) : (
                  <span className="ml-2 text-warn">not verified yet</span>
                )}
              </span>
              <span className="inline-flex gap-4">
                {!d.verified_at && (
                  <button className={linkButton} disabled={busy} onClick={() => act(() => verifyDomain(org.id, d.domain))}>
                    Verify
                  </button>
                )}
                <button
                  className={dangerButton}
                  disabled={busy}
                  onClick={() => window.confirm(`Remove ${d.domain}?`) && act(() => removeDomain(org.id, d.domain))}
                >
                  Remove
                </button>
              </span>
            </div>
            {!d.verified_at && (
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <Copyable label="TXT record name" value={d.txt_record.name} />
                <Copyable label="TXT record value" value={d.txt_record.value} />
              </div>
            )}
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function Connection({ org, sso, onSaved }: { org: OrgSummary; sso: SsoSettings; onSaved: (s: SsoSettings) => void }) {
  const [kind, setKind] = useState<"oidc" | "saml">(sso.kind ?? "oidc");
  const [issuer, setIssuer] = useState(sso.issuer ?? "");
  const [clientId, setClientId] = useState(sso.client_id ?? "");
  const [secret, setSecret] = useState("");
  const [metadata, setMetadata] = useState("");
  const [enabled, setEnabled] = useState(sso.configured ? sso.enabled : true);
  const [required, setRequired] = useState(sso.required);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [code, setCode] = useState<string | null>(null);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      const out = await saveSso(org.id, {
        kind,
        enabled,
        required,
        ...(kind === "oidc"
          ? { issuer: issuer.trim(), client_id: clientId.trim(), client_secret: secret || undefined }
          : { idp_metadata_xml: metadata.trim() || undefined }),
      });
      if (out.break_glass_code) setCode(out.break_glass_code);
      setSecret("");
      setMetadata("");
      setSaved(true);
      onSaved(out);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function regenerate() {
    if (!window.confirm("Make a new break-glass code? The current one stops working.")) return;
    try {
      setCode((await newBreakGlass(org.id)).break_glass_code);
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <Panel>
      <h2 className="font-semibold">2 · Identity provider</h2>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <Copyable label="OIDC redirect URI" value={sso.sp.oidc_redirect_uri} />
        <Copyable label="SAML metadata URL" value={sso.sp.saml_metadata_url} />
        <Copyable label="SAML entity id (audience)" value={sso.sp.saml_entity_id} />
        <Copyable label="SAML ACS URL" value={sso.sp.saml_acs_url} />
      </div>

      <form onSubmit={save} className="mt-6 space-y-4 text-sm">
        <fieldset className="flex gap-6">
          <legend className="mb-2 text-text-muted">Protocol</legend>
          {(["oidc", "saml"] as const).map((k) => (
            <label key={k} className="flex items-center gap-2">
              <input type="radio" name="kind" value={k} checked={kind === k} onChange={() => setKind(k)} />
              {k === "oidc" ? "OpenID Connect" : "SAML 2.0"}
            </label>
          ))}
        </fieldset>

        {kind === "oidc" ? (
          <div className="grid gap-3 md:grid-cols-3">
            <label className="flex flex-col gap-1">
              <span className="text-text-muted">Issuer URL</span>
              <input value={issuer} onChange={(e) => setIssuer(e.target.value)} placeholder="https://login.practice.com" className={inputClass} />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-text-muted">Client id</span>
              <input value={clientId} onChange={(e) => setClientId(e.target.value)} className={inputClass} />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-text-muted">Client secret</span>
              <input
                type="password"
                value={secret}
                onChange={(e) => setSecret(e.target.value)}
                autoComplete="off"
                placeholder={sso.has_client_secret ? "Saved · leave empty to keep" : ""}
                className={inputClass}
              />
            </label>
          </div>
        ) : (
          <label className="flex flex-col gap-1">
            <span className="text-text-muted">
              Identity provider metadata (XML)
              {sso.idp_entity_id && ` · saved: ${sso.idp_entity_id}`}
            </span>
            <textarea
              value={metadata}
              onChange={(e) => setMetadata(e.target.value)}
              rows={6}
              placeholder={sso.idp_entity_id ? "Leave empty to keep the saved metadata" : "<md:EntityDescriptor …>"}
              className={`font-mono text-xs ${inputClass}`}
            />
            {sso.idp_cert_sha256 && <span className="text-xs text-text-muted">Signing certificate SHA-256 {sso.idp_cert_sha256}</span>}
          </label>
        )}

        <label className="flex items-center gap-2">
          <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
          Enabled
        </label>
        <label className="flex items-start gap-2">
          <input type="checkbox" checked={required} onChange={(e) => setRequired(e.target.checked)} className="mt-1" />
          <span>
            Require SSO for verified domains
            <span className="block text-text-muted">
              Password and Google sign-in stop working for those addresses. Owners get a one-time break-glass code.
            </span>
          </span>
        </label>
        <Button type="submit" disabled={busy}>
          {busy ? "Saving…" : "Save"}
        </Button>
        {saved && (
          <p role="status" className="text-emerald-400">
            Saved.
          </p>
        )}
        {error && <ErrorNote message={error} />}
      </form>

      {code && (
        <div className="mt-6 rounded-[var(--radius-button)] border border-warn/30 bg-warn/5 p-4 text-sm">
          <p className="flex items-center gap-2 font-semibold text-text-primary">
            <ShieldAlert size={16} className="text-warn" aria-hidden /> Break-glass code (shown once)
          </p>
          <p className="mt-2 font-mono text-lg tracking-widest text-text-primary">{code}</p>
          <p className="mt-2 text-text-secondary">
            Store it somewhere safe. If your identity provider is down, an owner signs in with their password plus this
            code. It works once.
          </p>
        </div>
      )}
      {sso.required && (
        <button className={`mt-4 text-sm ${linkButton}`} onClick={regenerate}>
          Make a new break-glass code
        </button>
      )}
    </Panel>
  );
}
