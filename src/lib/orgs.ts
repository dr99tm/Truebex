"use client";

// Organisations, seats, the audit log and SSO (PF3) as the website uses them.
import { api, API_URL, ApiError, getToken } from "@/lib/api";

export type Role = "owner" | "admin" | "billing" | "member";
export type SeatKind = "named" | "floating" | "none";

export const ROLE_NAMES: Record<Role, string> = {
  owner: "Owner",
  admin: "Admin",
  billing: "Billing",
  member: "Member",
};

export const SEAT_NAMES: Record<SeatKind, string> = {
  named: "Named",
  floating: "Floating",
  none: "No seat",
};

export const isAdmin = (role: Role | undefined | null) => role === "owner" || role === "admin";

export interface OrgSummary {
  id: string;
  name: string;
  slug: string;
  role: Role;
  seat_kind: SeatKind;
}

export interface OrgDetail extends OrgSummary {
  created_at: string;
  members: number;
  sso_required: boolean;
  subscription: {
    plan: string;
    plan_name: string;
    seats: number;
    provider: string;
    current_period_end: string | null;
  } | null;
  seats: { total: number; named: number; floating: number };
  billing_url: string;
}

export interface Member {
  user_id: number;
  email: string;
  name: string | null;
  role: Role;
  seat_kind: SeatKind;
  joined_at: string;
  last_active_at: string | null;
  devices: number;
}

export interface Invite {
  id: string;
  email: string;
  role: Role;
  seat_kind: SeatKind;
  invited_by: string | null;
  created_at: string;
  expires_at: string;
  status: "pending" | "accepted" | "revoked" | "expired";
}

export interface Seats {
  tier: string | null;
  tier_name: string | null;
  total: number;
  named: { total: number; assigned: number };
  floating: {
    total: number;
    in_use: number;
    members: number;
    leases: {
      user: { user_id: number; email: string | null; name: string | null };
      device: { device_id: string; name: string | null };
      since: string;
      expires_at: string;
    }[];
  };
}

export interface MemberUsage {
  user_id: number;
  email: string;
  name: string | null;
  role: Role;
  devices: number;
  last_active_at: string | null;
  api_requests: number;
  floating_hours: number;
  storage_bytes: number | null;
  panoramas: number | null;
  ai_credits: number | null;
}

export interface AuditEvent {
  id: string;
  at: string;
  actor: { user_id: number; email: string | null } | null;
  kind: string;
  target: { kind: string; id: string } | null;
  details: Record<string, unknown>;
}

export interface Domain {
  domain: string;
  txt_record: { name: string; type: "TXT"; value: string };
  verified_at: string | null;
  created_at: string;
}

export interface SsoSettings {
  configured: boolean;
  kind: "oidc" | "saml" | null;
  enabled: boolean;
  required: boolean;
  issuer: string | null;
  client_id: string | null;
  has_client_secret: boolean;
  idp_entity_id: string | null;
  idp_sso_url: string | null;
  idp_cert_sha256: string | null;
  has_break_glass_code: boolean;
  sp: {
    oidc_redirect_uri: string;
    saml_entity_id: string;
    saml_acs_url: string;
    saml_metadata_url: string;
  };
  domains: Domain[];
  break_glass_code?: string;
}

export interface SsoSettingsInput {
  kind: "oidc" | "saml";
  issuer?: string;
  client_id?: string;
  client_secret?: string;
  idp_metadata_xml?: string;
  enabled: boolean;
  required: boolean;
}

export interface InvitePreview {
  org_id: string;
  org_name: string;
  email: string;
  role: Role;
  seat_kind: SeatKind;
  expires_at: string;
  status: Invite["status"];
}

const o = (id: string) => `/orgs/${encodeURIComponent(id)}`;

export const listOrgs = () => api<OrgSummary[]>("/orgs");
export const createOrg = (name: string) =>
  api<{ id: string; slug: string; name: string; role: Role }>("/orgs", { method: "POST", json: { name } });
export const getOrg = (id: string) => api<OrgDetail>(o(id));
export const renameOrg = (id: string, name: string) =>
  api<OrgDetail>(o(id), { method: "PATCH", json: { name } });
export const deleteOrg = (id: string) => api<void>(o(id), { method: "DELETE" });

export const listMembers = (id: string) => api<Member[]>(`${o(id)}/members`);
export const changeRole = (id: string, userId: number, role: Role) =>
  api<Member>(`${o(id)}/members/${userId}`, { method: "PATCH", json: { role } });
export const removeMember = (id: string, userId: number) =>
  api<void>(`${o(id)}/members/${userId}`, { method: "DELETE" });

export const listInvites = (id: string) => api<Invite[]>(`${o(id)}/invites`);
export const createInvite = (id: string, email: string, role: Role, seat: SeatKind) =>
  api<Invite>(`${o(id)}/invites`, { method: "POST", json: { email, role, seat } });
export const resendInvite = (id: string, inviteId: string) =>
  api<Invite>(`${o(id)}/invites/${encodeURIComponent(inviteId)}/resend`, { method: "POST" });
export const revokeInvite = (id: string, inviteId: string) =>
  api<void>(`${o(id)}/invites/${encodeURIComponent(inviteId)}`, { method: "DELETE" });
export const previewInvite = (token: string) =>
  api<InvitePreview>("/invites/preview", { method: "POST", json: { token }, auth: false });
export const acceptInvite = (token: string) =>
  api<{ org_id: string; role: Role; seat_kind: SeatKind }>("/invites/accept", {
    method: "POST",
    json: { token },
  });

export const getSeats = (id: string) => api<Seats>(`${o(id)}/seats`);
export const setFloating = (id: string, floating: number) =>
  api<Seats>(`${o(id)}/seats/settings`, { method: "PUT", json: { floating } });
export const assignSeat = (id: string, userId: number, kind: SeatKind) =>
  api<{ user_id: number; seat_kind: SeatKind }>(`${o(id)}/seats/${userId}`, { method: "PUT", json: { kind } });

export const getUsage = (id: string, month: string) =>
  api<MemberUsage[]>(`${o(id)}/usage?month=${encodeURIComponent(month)}`);

export const getAudit = (id: string, opts: { cursor?: string | null; kind?: string } = {}) => {
  const q = new URLSearchParams();
  if (opts.cursor) q.set("cursor", opts.cursor);
  if (opts.kind) q.set("kind", opts.kind);
  const qs = q.toString();
  return api<{ events: AuditEvent[]; next: string | null }>(`${o(id)}/audit${qs ? `?${qs}` : ""}`);
};

/** The audit log as a CSV file, saved through the browser (the API needs the session). */
export async function downloadAuditCsv(id: string, kind?: string): Promise<void> {
  const q = new URLSearchParams({ format: "csv" });
  if (kind) q.set("kind", kind);
  let res: Response;
  try {
    res = await fetch(`${API_URL}${o(id)}/audit?${q}`, {
      headers: { Authorization: `Bearer ${getToken() ?? ""}` },
    });
  } catch {
    throw new ApiError(0, "Can't reach the Truebex server. Please try again in a moment.");
  }
  if (!res.ok) throw new ApiError(res.status, `Export failed (${res.status}).`);
  const name =
    /filename="([^"]+)"/.exec(res.headers.get("content-disposition") ?? "")?.[1] ?? "truebex-audit.csv";
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export const getSso = (id: string) => api<SsoSettings>(`${o(id)}/sso`);
export const saveSso = (id: string, body: SsoSettingsInput) =>
  api<SsoSettings>(`${o(id)}/sso`, { method: "PUT", json: body });
export const newBreakGlass = (id: string) =>
  api<{ break_glass_code: string }>(`${o(id)}/sso/break-glass`, { method: "POST" });
export const addDomain = (id: string, domain: string) =>
  api<Domain>(`${o(id)}/domains`, { method: "POST", json: { domain } });
export const verifyDomain = (id: string, domain: string) =>
  api<Domain>(`${o(id)}/domains/${encodeURIComponent(domain)}/verify`, { method: "POST" });
export const removeDomain = (id: string, domain: string) =>
  api<void>(`${o(id)}/domains/${encodeURIComponent(domain)}`, { method: "DELETE" });

/** Where "Continue with SSO" sends the browser, or 404 `sso_not_found`. */
export const ssoStart = (email: string, next: string) =>
  api<{ url: string }>(
    `/auth/sso/start?${new URLSearchParams({ email, next, format: "json" })}`,
    { auth: false }
  );

// --- the selected workspace (personal, or one organisation) -------------------------

const ORG_KEY = "truebex_org";

export function readSelectedOrg(): string | null {
  try {
    return window.localStorage.getItem(ORG_KEY);
  } catch {
    return null;
  }
}

export function writeSelectedOrg(id: string | null): void {
  try {
    if (id) window.localStorage.setItem(ORG_KEY, id);
    else window.localStorage.removeItem(ORG_KEY);
  } catch {
    /* private mode: the choice lasts for this page only */
  }
}

/** "2026-10" for the month containing `date` (UTC). */
export function monthOf(date = new Date()): string {
  return date.toISOString().slice(0, 7);
}
