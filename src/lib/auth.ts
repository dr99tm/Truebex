"use client";

// Client-side auth helpers that talk to the FastAPI server.
// Set NEXT_PUBLIC_AUTH_URL in .env.local to your cloudflared hostname, e.g.
//   NEXT_PUBLIC_AUTH_URL=https://auth.yourdomain.com
const AUTH_URL = process.env.NEXT_PUBLIC_AUTH_URL ?? "http://127.0.0.1:8000";

const TOKEN_KEY = "truebex_token";

// Fired on the window whenever the token is set or cleared. The native
// `storage` event only fires in *other* tabs, so we dispatch our own so the
// current tab (e.g. the Navbar) can react to login/logout immediately.
export const AUTH_CHANGE_EVENT = "truebex-auth-change";

function emitAuthChange(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(AUTH_CHANGE_EVENT));
  }
}

export interface User {
  id: number;
  email: string;
  created_at: string;
  plan: string;
}

export interface AuthResult {
  access_token: string;
  token_type: string;
  user: User;
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
  emitAuthChange();
}

export function clearToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
  emitAuthChange();
}

/** Throw an Error carrying the server's `detail` message when present. */
async function parseError(res: Response): Promise<never> {
  let detail = `Request failed (${res.status})`;
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") {
      detail = data.detail;
    } else if (Array.isArray(data?.detail) && data.detail[0]?.msg) {
      // FastAPI validation errors come back as a list of {msg, ...}.
      detail = data.detail[0].msg;
    }
  } catch {
    /* response had no JSON body */
  }
  throw new Error(detail);
}

export async function register(
  email: string,
  password: string
): Promise<AuthResult> {
  const res = await fetch(`${AUTH_URL}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) await parseError(res);
  const data: AuthResult = await res.json();
  setToken(data.access_token);
  return data;
}

export async function login(
  email: string,
  password: string
): Promise<AuthResult> {
  const res = await fetch(`${AUTH_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) await parseError(res);
  const data: AuthResult = await res.json();
  setToken(data.access_token);
  return data;
}

export async function fetchMe(): Promise<User | null> {
  const token = getToken();
  if (!token) return null;
  const res = await fetch(`${AUTH_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (res.status === 401) {
    clearToken();
    return null;
  }
  if (!res.ok) await parseError(res);
  return res.json();
}

export function logout(): void {
  clearToken();
}

/**
 * Record a delivered Gammal Tech payment against the current user, activating
 * their plan. Called after the SDK verifies the payment. Requires a token.
 */
export async function activatePlan(
  paymentId: string,
  plan = "pro"
): Promise<User> {
  const token = getToken();
  if (!token) throw new Error("Not signed in.");
  const res = await fetch(`${AUTH_URL}/billing/activate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ payment_id: paymentId, plan }),
  });
  if (!res.ok) await parseError(res);
  return res.json();
}
