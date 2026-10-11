import type { Metadata } from "next";
import { SellPage } from "@/components/suppliers/SellPage";
import { SELL_PAGE } from "@/lib/constants";
import { breadcrumbLd, faqLd, ldJson, pageMetadata, webPageLd } from "@/lib/seo";

// PF13a: the public, indexable page for suppliers. It leads to the supplier
// portal's sign-up; the portal itself (/supplier/) stays noindex.
export const metadata: Metadata = pageMetadata({
  title: SELL_PAGE.title,
  description: SELL_PAGE.description,
  path: SELL_PAGE.path,
  absoluteTitle: true,
});

export default function SuppliersPage() {
  const ld = ldJson([
    webPageLd({ name: SELL_PAGE.h1, description: SELL_PAGE.description, path: SELL_PAGE.path }),
    breadcrumbLd([
      { name: "Truebex", path: "/" },
      { name: SELL_PAGE.nav, path: SELL_PAGE.path },
    ]),
    faqLd(SELL_PAGE.faq),
  ]);
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: ld }} />
      <SellPage />
    </>
  );
}
