import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Check } from "lucide-react";
import { Footer } from "@/components/layout/Footer";
import { DownloadPanel } from "@/components/releases/DownloadPanel";
import { Button } from "@/components/ui/Button";
import { DOWNLOAD, SITE } from "@/lib/constants";
import { latestRelease } from "@/lib/releases";

export const metadata: Metadata = {
  title: DOWNLOAD.metaTitle,
  description: DOWNLOAD.description,
  alternates: { canonical: "/download/" },
  openGraph: {
    title: `${DOWNLOAD.metaTitle} · Truebex`,
    description: DOWNLOAD.description,
    url: `${SITE.url}/download/`,
  },
};

export default function DownloadPage() {
  const latest = latestRelease("stable");
  const ld = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "Truebex",
    url: SITE.url,
    applicationCategory: "DesignApplication",
    operatingSystem: "Windows 10, Windows 11",
    downloadUrl: `${SITE.url}/download/`,
    publisher: { "@id": `${SITE.url}/#organization` },
    ...(latest
      ? {
          softwareVersion: latest.version,
          datePublished: latest.published_at.slice(0, 10),
          fileSize: `${Math.round(latest.installer.bytes / 1_000_000)}MB`,
          releaseNotes: latest.notes_url,
        }
      : {}),
  };

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(ld) }} />
      <main className="mx-auto max-w-3xl px-4 pb-24 pt-28 md:px-8">
        <p className="text-sm font-medium uppercase tracking-wider text-accent">{DOWNLOAD.eyebrow}</p>
        <h1 className="mt-3 text-3xl font-bold tracking-tight sm:text-5xl">{DOWNLOAD.h1}</h1>
        <p className="mt-5 text-lg text-text-secondary">{DOWNLOAD.intro}</p>

        <section className="mt-10 rounded-[var(--radius-card)] border border-border bg-surface p-6 md:p-8">
          <DownloadPanel initial={latest} />
          {latest && (
            <Link
              href={`/changelog/#${latest.version}`}
              className="mt-5 inline-flex items-center gap-1 text-sm text-accent hover:underline"
            >
              {DOWNLOAD.changelogCta}
              <ArrowRight size={14} aria-hidden />
            </Link>
          )}
        </section>

        <section className="mt-12">
          <h2 className="text-2xl font-semibold tracking-tight">{DOWNLOAD.requirementsTitle}</h2>
          <ul className="mt-4 space-y-3">
            {DOWNLOAD.requirements.map((r) => (
              <li key={r} className="flex gap-3 text-text-secondary">
                <Check size={18} className="mt-0.5 shrink-0 text-accent" aria-hidden />
                {r}
              </li>
            ))}
          </ul>
        </section>

        <section className="mt-12">
          <h2 className="text-2xl font-semibold tracking-tight">{DOWNLOAD.accountTitle}</h2>
          <p className="mt-3 text-text-secondary">{DOWNLOAD.accountText}</p>
          <div className="mt-6">
            <Button href="/signup/">{DOWNLOAD.accountCta}</Button>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
