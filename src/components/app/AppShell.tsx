"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

/** The install prompt a browser offers (Chromium's beforeinstallprompt). */
interface InstallPromptEvent extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

interface AppState {
  /** The browser offered an install prompt (Android, desktop Chromium). */
  canInstall: boolean;
  install(): Promise<void>;
  /** iOS Safari, not yet on the home screen: show the Share → Add to Home Screen hint. */
  iosHint: boolean;
  installed: boolean;
  online: boolean;
}

const AppContext = createContext<AppState>({
  canInstall: false,
  install: async () => undefined,
  iosHint: false,
  installed: false,
  online: true,
});

export const useApp = () => useContext(AppContext);

/** Fired on the window when the service worker asks the page to send its outbox (background sync). */
export const APP_FLUSH_EVENT = "truebex-app-flush";

/**
 * The /app/ shell (PF9): registers the service worker (scope "/", out/sw.js),
 * keeps the browser's install prompt for the Install button, and tracks
 * whether the device is online. Feature detection only, never the user agent.
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const [prompt, setPrompt] = useState<InstallPromptEvent | null>(null);
  const [installed, setInstalled] = useState(false);
  const [iosHint, setIosHint] = useState(false);
  const [online, setOnline] = useState(true);

  useEffect(() => {
    const standalone =
      window.matchMedia?.("(display-mode: standalone)").matches ||
      (navigator as Navigator & { standalone?: boolean }).standalone === true;
    const onPrompt = (e: Event) => {
      e.preventDefault();
      setPrompt(e as InstallPromptEvent);
    };
    const onInstalled = () => {
      setInstalled(true);
      setPrompt(null);
    };
    const onOnline = () => setOnline(true);
    const onOffline = () => setOnline(false);
    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    // Read once on the client (the export renders without a window).
    queueMicrotask(() => {
      setInstalled(standalone);
      setOnline(navigator.onLine);
      // `navigator.standalone` exists only in iOS Safari, where there is no install prompt.
      setIosHint(!standalone && "standalone" in navigator);
    });

    const onMessage = (e: MessageEvent) => {
      if ((e.data as { type?: string } | null)?.type === "flush") window.dispatchEvent(new Event(APP_FLUSH_EVENT));
    };
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => undefined);
      navigator.serviceWorker.addEventListener("message", onMessage);
    }
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt);
      window.removeEventListener("appinstalled", onInstalled);
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
      if ("serviceWorker" in navigator) navigator.serviceWorker.removeEventListener("message", onMessage);
    };
  }, []);

  const install = useCallback(async () => {
    if (!prompt) return;
    await prompt.prompt();
    const choice = await prompt.userChoice.catch(() => null);
    if (choice?.outcome === "accepted") setInstalled(true);
    setPrompt(null);
  }, [prompt]);

  return (
    <AppContext.Provider value={{ canInstall: prompt !== null && !installed, install, iosHint: iosHint && !installed, installed, online }}>
      <div className="min-h-[100dvh] bg-background text-text-primary">{children}</div>
    </AppContext.Provider>
  );
}
