import type { Metadata, Viewport } from "next";
import { Open_Sans } from "next/font/google";
import "./globals.css";
import { Navbar } from "@/components/layout/Navbar";
import { SITE } from "@/lib/constants";
import { socialLinks, verification } from "@/lib/site-config";

// Fallback for Segoe UI (see globals.css): same designer, open licence.
const openSans = Open_Sans({
  subsets: ["latin"],
  variable: "--font-open-sans",
  display: "swap",
});

export const viewport: Viewport = {
  themeColor: "#161616",
  colorScheme: "dark",
};

export const metadata: Metadata = {
  metadataBase: new URL(SITE.url),
  title: {
    default: SITE.title,
    template: "%s · Truebex",
  },
  description: SITE.description,
  applicationName: "Truebex",
  keywords: [
    "Truebex",
    "building design platform",
    "architectural design software",
    "daylight design",
    "daylight simulation for architects",
    "parametric wall panels",
    "interior design software",
    "3D building design",
    "architecture app",
  ],
  authors: [{ name: "Truebex" }],
  creator: "Truebex",
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    locale: "en_US",
    url: SITE.url,
    siteName: "Truebex",
    title: SITE.title,
    description: SITE.description,
    images: [
      {
        url: "/images/og-image.jpg",
        width: 1200,
        height: 630,
        alt: "Truebex — see it before you build it. The building design platform with measured daylight.",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: SITE.title,
    description: SITE.description,
    images: ["/images/og-image.jpg"],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true, "max-image-preview": "large" },
  },
  category: "technology",
  // Search Console and Bing Webmaster Tools (public tokens; empty = no tag).
  verification: {
    ...(verification.google ? { google: verification.google } : {}),
    ...(verification.bing ? { other: { "msvalidate.01": verification.bing } } : {}),
  },
};

const organizationLd = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      "@id": `${SITE.url}/#organization`,
      name: "Truebex",
      url: SITE.url,
      logo: `${SITE.url}/icon-512.png`,
      email: SITE.email,
      slogan: SITE.tagline,
      ...(socialLinks.length ? { sameAs: socialLinks.map((s) => s.url) } : {}),
    },
    {
      "@type": "WebSite",
      "@id": `${SITE.url}/#website`,
      url: SITE.url,
      name: "Truebex",
      publisher: { "@id": `${SITE.url}/#organization` },
    },
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    // lang/dir are rewritten to ar/rtl in out/ar/index.html after the build
    // (scripts/postbuild-lang.mjs), so the client must not fight them.
    <html lang="en" className={openSans.variable} suppressHydrationWarning>
      <body className="antialiased overflow-x-hidden">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(organizationLd) }}
        />
        <div className="relative z-10">
          <Navbar />
          {children}
        </div>
      </body>
    </html>
  );
}
