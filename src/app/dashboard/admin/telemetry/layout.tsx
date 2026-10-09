import type { Metadata } from "next";
import { ADMIN_TELEMETRY } from "@/lib/constants";

// Admin only; never indexed (the dashboard layout says so too).
export const metadata: Metadata = {
  title: ADMIN_TELEMETRY.title,
  robots: { index: false, follow: false },
};

export default function TelemetryAdminLayout({ children }: { children: React.ReactNode }) {
  return children;
}
