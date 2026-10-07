"use client";

import { useEffect, useRef, useState } from "react";
import { fetchPublicConfig, googleLogin } from "@/lib/auth";

// Google Identity Services (https://developers.google.com/identity/gsi/web).
// The client id comes from the API's /config at runtime, so turning Google
// sign-in on or off only needs the server's GOOGLE_CLIENT_ID — no rebuild.
const GSI_SRC = "https://accounts.google.com/gsi/client";

interface GsiButtonOptions {
  theme: "filled_black" | "outline" | "filled_blue";
  size: "large" | "medium";
  text: "continue_with" | "signin_with" | "signup_with";
  shape: "pill" | "rectangular";
  width: number;
  logo_alignment: "left" | "center";
}

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (cfg: {
            client_id: string;
            callback: (res: { credential: string }) => void;
            ux_mode?: "popup" | "redirect";
            auto_select?: boolean;
            itp_support?: boolean;
            use_fedcm_for_prompt?: boolean;
          }) => void;
          renderButton: (el: HTMLElement, opts: GsiButtonOptions) => void;
        };
      };
    };
  }
}

let gsiPromise: Promise<void> | null = null;

function loadGsi(): Promise<void> {
  if (window.google?.accounts?.id) return Promise.resolve();
  gsiPromise ??= new Promise<void>((resolve, reject) => {
    const s = document.createElement("script");
    s.src = GSI_SRC;
    s.async = true;
    s.defer = true;
    s.onload = () => resolve();
    s.onerror = () => {
      gsiPromise = null;
      reject(new Error("Couldn't load Google sign-in."));
    };
    document.head.appendChild(s);
  });
  return gsiPromise;
}

export function GoogleButton({
  mode,
  onSuccess,
  onError,
}: {
  mode: "login" | "signup";
  onSuccess: () => void;
  onError: (message: string) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<"loading" | "ready" | "off">("loading");

  // Keep the latest callbacks without re-initialising GSI on every render.
  const cb = useRef({ onSuccess, onError });
  useEffect(() => {
    cb.current = { onSuccess, onError };
  });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      let clientId: string | null = null;
      try {
        clientId = (await fetchPublicConfig()).google_client_id;
      } catch {
        clientId = null;
      }
      if (!clientId) {
        if (!cancelled) setState("off");
        return;
      }
      try {
        await loadGsi();
      } catch {
        if (!cancelled) setState("off");
        return;
      }
      if (cancelled || !ref.current || !window.google) return;
      window.google.accounts.id.initialize({
        client_id: clientId,
        ux_mode: "popup",
        itp_support: true,
        use_fedcm_for_prompt: true,
        callback: async ({ credential }) => {
          try {
            await googleLogin(credential);
            cb.current.onSuccess();
          } catch (err) {
            cb.current.onError(
              err instanceof Error ? err.message : "Google sign-in failed."
            );
          }
        },
      });
      const width = Math.min(ref.current.offsetWidth || 400, 400);
      window.google.accounts.id.renderButton(ref.current, {
        theme: "filled_black",
        size: "large",
        text: mode === "signup" ? "signup_with" : "continue_with",
        shape: "rectangular",
        width,
        logo_alignment: "center",
      });
      setState("ready");
    })();
    return () => {
      cancelled = true;
    };
  }, [mode]);

  if (state === "off") return null;

  return (
    <div>
      <div
        ref={ref}
        className="flex min-h-[44px] w-full justify-center"
        aria-busy={state === "loading"}
      />
      <div className="my-6 flex items-center gap-3 text-xs uppercase tracking-wider text-text-muted">
        <span className="h-px flex-1 bg-border" />
        or with email
        <span className="h-px flex-1 bg-border" />
      </div>
    </div>
  );
}
