"use client";

import { useEffect, useState } from "react";
import { AUTH_CHANGE_EVENT, fetchMe, getToken, type User } from "@/lib/auth";

/**
 * Tracks whether a token is present. Returns `null` until mounted on the
 * client (avoids SSR/hydration mismatch since the token is in localStorage),
 * then `true`/`false`. Reacts to login/logout in this tab and other tabs.
 */
export function useIsAuthenticated(): boolean | null {
  const [authed, setAuthed] = useState<boolean | null>(null);

  useEffect(() => {
    const sync = () => setAuthed(getToken() !== null);
    sync(); // initial read once we're on the client

    window.addEventListener(AUTH_CHANGE_EVENT, sync); // same-tab login/logout
    window.addEventListener("storage", sync); // other tabs
    return () => {
      window.removeEventListener(AUTH_CHANGE_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  return authed;
}

export interface CurrentUserState {
  user: User | null;
  loading: boolean;
}

/**
 * Fetches the current user from /auth/me and keeps it in sync with login /
 * logout events. `loading` is true until the first fetch resolves.
 */
export function useCurrentUser(): CurrentUserState {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    const load = () => {
      if (!getToken()) {
        setUser(null);
        setLoading(false);
        return;
      }
      setLoading(true);
      fetchMe()
        .then((u) => {
          if (!cancelled) setUser(u);
        })
        .catch(() => {
          if (!cancelled) setUser(null);
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    };

    load();
    window.addEventListener(AUTH_CHANGE_EVENT, load);
    window.addEventListener("storage", load);
    return () => {
      cancelled = true;
      window.removeEventListener(AUTH_CHANGE_EVENT, load);
      window.removeEventListener("storage", load);
    };
  }, []);

  return { user, loading };
}
