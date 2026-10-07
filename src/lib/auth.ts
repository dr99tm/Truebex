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

export function login(email: string, password: string): Promise<AuthResult> {
  return signIn("/auth/login", { email, password });
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
}

let configPromise: Promise<{ google_client_id: string | null }> | null = null;

/** Server feature flags (e.g. the Google client id). Cached per page load. */
export function fetchPublicConfig(): Promise<{ google_client_id: string | null }> {
  configPromise ??= api<{ google_client_id: string | null }>("/config", {
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
