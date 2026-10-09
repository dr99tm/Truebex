// Per-page metadata and JSON-LD builders (the truebex-seo per-page
// checklist): canonical with a trailing slash, the social card, and
// structured data that matches the visible text.
import type { Metadata } from "next";
import { SITE } from "@/lib/constants";

export const OG_IMAGE = {
  url: "/images/og-image.jpg",
  width: 1200,
  height: 630,
  alt: "Truebex — see it before you build it. The building design platform with measured daylight.",
};

// The English home and the Arabic landing page, paired for search engines.
export const HOME_LANGUAGES = { en: "/", ar: "/ar/", "x-default": "/" } as const;

export function absolute(pathname: string): string {
  return `${SITE.url}${pathname}`;
}

export function pageMetadata({
  title,
  description,
  path,
  absoluteTitle,
  languages,
  locale = "en_US",
  types,
}: {
  title: string;
  description: string;
  path: string;
  absoluteTitle?: boolean;
  languages?: Record<string, string>;
  locale?: string;
  types?: Record<string, string>;
}): Metadata {
  const fullTitle = absoluteTitle ? title : `${title} · Truebex`;
  return {
    title: absoluteTitle ? { absolute: title } : title,
    description,
    alternates: {
      canonical: path,
      ...(languages ? { languages } : {}),
      ...(types ? { types } : {}),
    },
    openGraph: {
      type: "website",
      locale,
      url: absolute(path),
      siteName: "Truebex",
      title: fullTitle,
      description,
      images: [OG_IMAGE],
    },
    twitter: {
      card: "summary_large_image",
      title: fullTitle,
      description,
      images: [OG_IMAGE.url],
    },
  };
}

export function breadcrumbLd(items: { name: string; path: string }[]): object {
  return {
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: item.name,
      item: absolute(item.path),
    })),
  };
}

export function webPageLd({
  name,
  description,
  path,
  inLanguage = "en",
}: {
  name: string;
  description: string;
  path: string;
  inLanguage?: string;
}): object {
  return {
    "@type": "WebPage",
    "@id": `${absolute(path)}#webpage`,
    url: absolute(path),
    name,
    description,
    inLanguage,
    isPartOf: { "@id": `${SITE.url}/#website` },
    publisher: { "@id": `${SITE.url}/#organization` },
  };
}

export function faqLd(faq: readonly { q: string; a: string }[]): object {
  return {
    "@type": "FAQPage",
    mainEntity: faq.map((f) => ({
      "@type": "Question",
      name: f.q,
      acceptedAnswer: { "@type": "Answer", text: f.a },
    })),
  };
}

/** A <script type="application/ld+json"> body for a @graph of nodes. */
export function ldJson(nodes: object[]): string {
  return JSON.stringify({ "@context": "https://schema.org", "@graph": nodes });
}
