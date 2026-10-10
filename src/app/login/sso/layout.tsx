import type { Metadata } from "next";
import { SSO_CALLBACK } from "@/lib/constants";

export const metadata: Metadata = {
  title: SSO_CALLBACK.metaTitle,
  robots: { index: false, follow: false },
};

export default function SsoReturnLayout({ children }: { children: React.ReactNode }) {
  return children;
}
