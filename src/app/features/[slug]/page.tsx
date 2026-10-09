import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { FeaturePage } from "@/components/features/FeaturePage";
import { FEATURE_PAGES } from "@/lib/constants";
import { breadcrumbLd, faqLd, ldJson, pageMetadata, webPageLd } from "@/lib/seo";
import { downloadCta, featureCapture } from "@/lib/site-routes";

// Static export: exactly these five pages, nothing else under /features/.
export const dynamicParams = false;

export function generateStaticParams() {
  return FEATURE_PAGES.map((p) => ({ slug: p.slug }));
}

function find(slug: string) {
  return FEATURE_PAGES.find((p) => p.slug === slug);
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const page = find((await params).slug);
  if (!page) return {};
  return pageMetadata({ title: page.title, description: page.description, path: `/features/${page.slug}/` });
}

export default async function FeatureRoute({ params }: { params: Promise<{ slug: string }> }) {
  const page = find((await params).slug);
  if (!page) notFound();
  const path = `/features/${page.slug}/`;
  const ld = ldJson([
    webPageLd({ name: page.h1, description: page.description, path }),
    breadcrumbLd([
      { name: "Truebex", path: "/" },
      { name: page.nav, path },
    ]),
    faqLd(page.faq),
  ]);
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: ld }} />
      <FeaturePage
        page={page}
        capture={featureCapture(page.slug, page.capture)}
        download={downloadCta}
        related={FEATURE_PAGES.filter((p) => p.slug !== page.slug)}
      />
    </>
  );
}
