import type { Metadata } from "next";
import { SupplierShell } from "@/components/supplier/SupplierShell";
import { SUPPLIER } from "@/lib/constants";

// Every supplier portal page is noindex (00-contract.md P.3: account pages).
export const metadata: Metadata = {
  title: { default: SUPPLIER.meta.title, template: SUPPLIER.meta.template },
  robots: { index: false, follow: false },
};

export default function SupplierLayout({ children }: { children: React.ReactNode }) {
  return <SupplierShell>{children}</SupplierShell>;
}
