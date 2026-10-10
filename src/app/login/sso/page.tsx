"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { setToken } from "@/lib/api";
import { safeNext } from "@/lib/auth";
import { SSO_CALLBACK } from "@/lib/constants";

// Where single sign-on lands (GET /auth/sso/oidc/callback and the SAML ACS
// redirect here): the session arrives in the URL fragment, which browsers
// never send to a server or write to access logs. Store it, wipe it from the
// address bar and history, and continue to `next`.
export default function SsoReturnPage() {
  const router = useRouter();

  useEffect(() => {
    const fragment = new URLSearchParams(window.location.hash.slice(1));
    const token = fragment.get("token");
    window.history.replaceState(null, "", window.location.pathname);
    if (!token) {
      router.replace("/login/");
      return;
    }
    setToken(token);
    router.replace(safeNext(fragment.get("next")));
  }, [router]);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 px-4 text-center">
      <h1 className="text-xl font-semibold">{SSO_CALLBACK.working}</h1>
      <Link href="/login/" className="text-sm text-text-muted hover:underline">
        {SSO_CALLBACK.retry}
      </Link>
    </main>
  );
}
