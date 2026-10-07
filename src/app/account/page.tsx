"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

// The old account page moved to /dashboard/. Kept so existing links work.
export default function AccountRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/dashboard/");
  }, [router]);
  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <p className="text-text-secondary">
        Moved to <a className="text-accent hover:underline" href="/dashboard/">your dashboard</a>…
      </p>
    </main>
  );
}
