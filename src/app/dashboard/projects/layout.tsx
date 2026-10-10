import type { Metadata } from "next";
import { PROJECTS } from "@/lib/constants";

// noindex comes from the dashboard layout (src/app/dashboard/layout.tsx).
export const metadata: Metadata = { title: PROJECTS.title };

export default function ProjectsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
