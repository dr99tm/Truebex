import type { Metadata } from "next";

// The page is a client redirect to /dashboard/ (no metadata of its own):
// never indexed, but its link to the dashboard may be followed (PF13b).
export const metadata: Metadata = {
  robots: { index: false, follow: true },
};

export default function AccountLayout({ children }: { children: React.ReactNode }) {
  return children;
}
