import type { Metadata } from "next";
import { Inter } from "next/font/google";
import Image from "next/image";
import "./globals.css";
import { Navbar } from "@/components/layout/Navbar";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL('https://truebex.com'), // or your actual domain 
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
    images: [{ url: "/images/og-image.jpg", width: 1200, height: 630 }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Truebex — True Building Experience",
    description:
      "Design, surf the market, calculate, experience in VR, and make instant changes.",
    images: ["/images/og-image.jpg"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="antialiased overflow-x-hidden">
        <Image
          src="/images/background.jpg"
          alt=""
          fill
          className="fixed inset-0 object-cover opacity-0 pointer-events-none z-0"
          priority
        />
        <div className="relative z-10">
          <Navbar />
          {children}
        </div>
      </body>
    </html>
  );
}
