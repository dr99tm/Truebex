import type { Metadata } from "next";
import { AppShell } from "@/components/app/AppShell";
import { APP } from "@/lib/constants";

// The mobile web client (PF9): app pages, not search pages.
export const metadata: Metadata = {
  title: { absolute: APP.metaTitle, template: `%s · ${APP.name}` },
  description: APP.metaDescription,
  robots: { index: false, follow: false },
  alternates: { canonical: "/app/" },
};

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
