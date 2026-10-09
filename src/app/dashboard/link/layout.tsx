import type { Metadata } from "next";

// noindex comes from the dashboard layout (src/app/dashboard/layout.tsx).
export const metadata: Metadata = { title: "Approve a sign-in" };

export default function LinkLayout({ children }: { children: React.ReactNode }) {
  return children;
}
