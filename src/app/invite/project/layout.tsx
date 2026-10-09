import type { Metadata } from "next";
import { PROJECT_INVITE } from "@/lib/constants";

// An account page reached from an emailed link: never indexed, never in the sitemap.
export const metadata: Metadata = {
  title: PROJECT_INVITE.metaTitle,
  alternates: { canonical: "/invite/project/" },
  robots: { index: false, follow: false },
};

export default function InviteProjectLayout({ children }: { children: React.ReactNode }) {
  return children;
}
