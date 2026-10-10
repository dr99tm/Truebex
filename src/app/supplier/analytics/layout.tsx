import type { Metadata } from "next";
import { SUPPLIER } from "@/lib/constants";

// noindex comes from the supplier layout (src/app/supplier/layout.tsx).
export const metadata: Metadata = { title: SUPPLIER.analytics.title };

export default function SupplierAnalyticsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
