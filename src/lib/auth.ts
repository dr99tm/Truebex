"use client";

// Account calls against the Truebex API. Session tokens live in
// localStorage; see lib/api.ts.
import { api, ApiError, clearToken, getToken, setToken } from "@/lib/api";

export { AUTH_CHANGE_EVENT, getToken } from "@/lib/api";

export interface User {
  id: number;
  email: string;
  created_at: string;
  plan: string;
  name: string | null;
  avatar_url: string | null;
  has_password: boolean;
  google_linked: boolean;
  /** Admins see the Admin group in the dashboard (set by hand on the server). */
  is_admin?: boolean;
}

export interface AuthResult {
  access_token: string;
  token_type: string;
  user: User;
}

async function signIn(path: string, body: unknown): Promise<AuthResult> {
  const data = await api<AuthResult>(path, {
    method: "POST",
    json: body,
    auth: false,
  });
  setToken(data.access_token);
  return data;
}

export function register(email: string, password: string): Promise<AuthResult> {
  return signIn("/auth/register", { email, password });
}

export function login(email: string, password: string, breakGlassCode?: string): Promise<AuthResult> {
  // PF3: an owner's one-time code when their organisation requires SSO.
  return signIn("/auth/login", breakGlassCode ? { email, password, break_glass_code: breakGlassCode } : { email, password });
}

/** Ask for a password reset link. The API answers the same whether or not
 *  the address has an account. */
export async function requestPasswordReset(email: string): Promise<void> {
  await api<{ status: string }>("/auth/password/forgot", { method: "POST", json: { email }, auth: false });
}

/** Set a new password with the token from a reset link, and sign in. */
export function resetPassword(token: string, password: string): Promise<AuthResult> {
  return signIn("/auth/password/reset", { token, password });
}

/** Exchange a Google Identity Services credential for a Truebex session. */
export function googleLogin(credential: string): Promise<AuthResult> {
  return signIn("/auth/google", { credential });
}

export async function fetchMe(): Promise<User | null> {
  if (!getToken()) return null;
  try {
    return await api<User>("/auth/me");
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return null;
    throw err;
  }
}

export function logout(): void {
  clearToken();
  // PF9: the mobile app's offline copy (projects, digests, edits, tiles) goes with the session.
  try {
    // The service worker forgets its tile index too (it may hold it open).
    navigator.serviceWorker?.controller?.postMessage({ type: "clear" });
    indexedDB.deleteDatabase("truebex-app");
    indexedDB.deleteDatabase("truebex-tiles");
    void caches.delete("tiles-v1").catch(() => undefined);
  } catch {
    /* no storage APIs here (private mode): nothing was kept */
  }
}

export interface PublicConfig {
  google_client_id: string | null;
  /** Paddle.js client token for /checkout/ (public by design). */
  paddle_client_token?: string | null;
  paddle_env?: "sandbox" | "production";
}

let configPromise: Promise<PublicConfig> | null = null;

/** Server feature flags (e.g. the Google client id). Cached per page load. */
export function fetchPublicConfig(): Promise<PublicConfig> {
  configPromise ??= api<PublicConfig>("/config", {
    auth: false,
  }).catch((err) => {
    configPromise = null;
    throw err;
  });
  return configPromise;
}

/** Only allow same-site relative redirects after login (no open redirect). */
export function safeNext(next: string | null | undefined): string {
  if (next && next.startsWith("/") && !next.startsWith("//")) return next;
  return "/dashboard";
}
