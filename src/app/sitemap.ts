import type { MetadataRoute } from "next";
import { FEATURE_PAGES, SITE } from "@/lib/constants";
import { HOME_LANGUAGES } from "@/lib/seo";

export const dynamic = "force-static";

// The English home and the Arabic landing page name each other (hreflang),
// with English as the default for every other language.
const homeAlternates = {
  languages: Object.fromEntries(
    Object.entries(HOME_LANGUAGES).map(([lang, path]) => [lang, `${SITE.url}${path}`])
  ),
};

// Public, indexable pages only (the dashboard and auth pages are noindex).
export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  return [
    { url: `${SITE.url}/`, lastModified: now, changeFrequency: "weekly", priority: 1, alternates: homeAlternates },
    { url: `${SITE.url}/ar/`, lastModified: now, changeFrequency: "weekly", priority: 0.9, alternates: homeAlternates },
    { url: `${SITE.url}/pricing/`, lastModified: now, changeFrequency: "weekly", priority: 0.9 },
    ...FEATURE_PAGES.map((p) => ({
      url: `${SITE.url}/features/${p.slug}/`,
      lastModified: now,
      changeFrequency: "monthly" as const,
      priority: p.roadmap ? 0.6 : 0.8,
    })),
    { url: `${SITE.url}/roadmap/`, lastModified: now, changeFrequency: "weekly", priority: 0.7 },
    { url: `${SITE.url}/changelog/`, lastModified: now, changeFrequency: "weekly", priority: 0.7 },
    { url: `${SITE.url}/developers/`, lastModified: now, changeFrequency: "monthly", priority: 0.7 },
    { url: `${SITE.url}/signup/`, lastModified: now, changeFrequency: "yearly", priority: 0.4 },
    { url: `${SITE.url}/privacy/`, lastModified: now, changeFrequency: "yearly", priority: 0.2 },
    { url: `${SITE.url}/terms/`, lastModified: now, changeFrequency: "yearly", priority: 0.2 },
  ];
}
