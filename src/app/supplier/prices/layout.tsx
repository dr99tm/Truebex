import type { Metadata } from "next";
import { SUPPLIER } from "@/lib/constants";

// noindex comes from the supplier layout (src/app/supplier/layout.tsx).
export const metadata: Metadata = { title: SUPPLIER.prices.title };

export default function SupplierPricesLayout({ children }: { children: React.ReactNode }) {
  return children;
}
