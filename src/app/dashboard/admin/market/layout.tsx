import type { Metadata } from "next";
import { MARKET } from "@/lib/constants";

// noindex comes from the dashboard layout (src/app/dashboard/layout.tsx).
export const metadata: Metadata = { title: MARKET.admin.title };

export default function AdminMarketLayout({ children }: { children: React.ReactNode }) {
  return children;
}
