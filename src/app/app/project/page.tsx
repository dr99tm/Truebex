import { Suspense } from "react";
import type { Metadata } from "next";
import { ProjectScreen } from "@/components/app/ProjectScreen";
import { APP } from "@/lib/constants";

// A static export has no dynamic segments: the project id is ?id=, read inside Suspense.
export const metadata: Metadata = { title: APP.project.metaTitle, alternates: { canonical: "/app/project/" } };

export default function AppProjectPage() {
  return (
    <Suspense fallback={<p className="p-6 text-sm text-text-secondary">{APP.project.loading}</p>}>
      <ProjectScreen />
    </Suspense>
  );
}
