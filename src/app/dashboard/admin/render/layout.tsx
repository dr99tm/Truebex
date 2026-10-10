import type { Metadata } from "next";
import { ADMIN_RENDER } from "@/lib/constants";

// Admin only; never indexed (the dashboard layout says so too).
export const metadata: Metadata = {
  title: ADMIN_RENDER.title,
  robots: { index: false, follow: false },
};

export default function RenderAdminLayout({ children }: { children: React.ReactNode }) {
  return children;
}
