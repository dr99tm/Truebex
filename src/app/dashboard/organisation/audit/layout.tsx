import type { Metadata } from "next";

// noindex comes from the dashboard layout (src/app/dashboard/layout.tsx).
export const metadata: Metadata = { title: "Audit log" };

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
