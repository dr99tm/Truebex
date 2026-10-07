import type { MetadataRoute } from "next";
import { SITE } from "@/lib/constants";

export const dynamic = "force-static";

// Public, indexable pages only (the dashboard and auth pages are noindex).
export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  return [
    { url: `${SITE.url}/`, lastModified: now, changeFrequency: "weekly", priority: 1 },
    { url: `${SITE.url}/developers/`, lastModified: now, changeFrequency: "monthly", priority: 0.7 },
    { url: `${SITE.url}/signup/`, lastModified: now, changeFrequency: "yearly", priority: 0.4 },
  ];
}
