import type { Metadata } from "next";
import { INVITE_PAGE } from "@/lib/constants";

export const metadata: Metadata = {
  title: INVITE_PAGE.metaTitle,
  robots: { index: false, follow: false },
};

export default function InviteLayout({ children }: { children: React.ReactNode }) {
  return children;
}
