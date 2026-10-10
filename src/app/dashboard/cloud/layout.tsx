import type { Metadata } from "next";
import { CLOUD } from "@/lib/constants";

// noindex comes from the dashboard layout (src/app/dashboard/layout.tsx).
export const metadata: Metadata = { title: CLOUD.title };

export default function CloudLayout({ children }: { children: React.ReactNode }) {
  return children;
}
