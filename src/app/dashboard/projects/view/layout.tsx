import type { Metadata } from "next";
import { PROJECTS } from "@/lib/constants";

// noindex comes from the dashboard layout (src/app/dashboard/layout.tsx).
export const metadata: Metadata = { title: PROJECTS.viewTitle };

export default function ProjectViewLayout({ children }: { children: React.ReactNode }) {
  return children;
}
