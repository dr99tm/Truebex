import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Truebex — True Building Experience",
  description:
    "Design buildings, surf the market for real materials, calculate construction needs, experience spaces in VR, and make instant changes — all in one platform.",
  keywords: [
    "architecture",
    "building design",
    "VR",
    "construction",
    "interior design",
    "3D design platform",
  ],
  openGraph: {
    type: "website",
    locale: "en_US",
    siteName: "Truebex",
    title: "Truebex — True Building Experience",
    description:
      "Design, surf the market, calculate, experience in VR, and make instant changes.",
    images: [{ url: "/images/og-image.png", width: 1200, height: 630 }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Truebex — True Building Experience",
    description:
      "Design, surf the market, calculate, experience in VR, and make instant changes.",
    images: ["/images/og-image.png"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="antialiased overflow-x-hidden">{children}</body>
    </html>
  );
}
