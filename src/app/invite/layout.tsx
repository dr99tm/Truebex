import type { Metadata } from "next";
import { INVITE_PAGE } from "@/lib/constants";

// The template passes the site's on to /invite/project/ (PF4); a plain title would end it here.
export const metadata: Metadata = {
  title: { default: INVITE_PAGE.metaTitle, template: "%s · Truebex" },
  robots: { index: false, follow: false },
};

export default function InviteLayout({ children }: { children: React.ReactNode }) {
  return children;
}
