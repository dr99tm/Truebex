"use client";

// Shared client for the Truebex API (server/). The site is a static export,
// so NEXT_PUBLIC_AUTH_URL is baked in at build time.
export const API_URL =
  process.env.NEXT_PUBLIC_AUTH_URL ?? "http://127.0.0.1:8000";

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

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
  emitAuthChange();
}

export function clearToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
  emitAuthChange();
}

export class ApiError extends Error {
  readonly status: number;
  /** Contract routes send a `code` (e.g. "device_limit"); others read as http_<status>. */
  readonly code: string;
  constructor(status: number, message: string, code?: string) {
    super(message);
    this.status = status;
    this.code = code ?? `http_${status}`;
    this.name = "ApiError";
  }
}

/** Throw an ApiError carrying the server's `detail` message when present. */
async function toError(res: Response): Promise<ApiError> {
  let detail = `Request failed (${res.status})`;
  let code: string | undefined;
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") {
      detail = data.detail;
    } else if (Array.isArray(data?.detail) && data.detail[0]?.msg) {
      // FastAPI validation errors come back as a list of {msg, ...}.
      detail = data.detail[0].msg;
    }
    if (typeof data?.code === "string") code = data.code;
  } catch {
    /* response had no JSON body */
  }
  return new ApiError(res.status, detail, code);
}

/**
 * fetch() against the API. Sends the session token when present, parses
 * JSON, and turns non-2xx responses into ApiError. A 401 on an authed call
 * clears the stored token (it expired or was revoked).
 */
export async function api<T>(
  path: string,
  init: RequestInit & { json?: unknown; auth?: boolean } = {}
): Promise<T> {
  const { json, auth = true, headers, ...rest } = init;
  const h = new Headers(headers);
  if (json !== undefined) h.set("Content-Type", "application/json");
  const token = auth ? getToken() : null;
  if (token) h.set("Authorization", `Bearer ${token}`);

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...rest,
      headers: h,
      body: json !== undefined ? JSON.stringify(json) : rest.body,
    });
  } catch {
    throw new ApiError(0, "Can't reach the Truebex server. Please try again in a moment.");
  }
  if (!res.ok) {
    if (res.status === 401 && token) clearToken();
    throw await toError(res);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

/** The API stores UTC without an offset; read it as UTC. */
export function parseServerDate(value: string): Date {
  return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  return parseServerDate(value).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}
