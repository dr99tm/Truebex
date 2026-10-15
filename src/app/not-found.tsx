import type { Metadata } from "next";
import { Button } from "@/components/ui/Button";
import { NOT_FOUND } from "@/lib/constants";

// PF13c: the site's own not-found page. Next exports it as out/404.html (what
// GitHub Pages answers a missing path with, status 404), out/404/ and
// out/_not-found/. Its `robots` replaces the root layout's whole object, so
// the layout's `index, follow` and googlebot tags are gone; Next writes its
// own `noindex` beside this one. No canonical (PF13b), not in the sitemap.
export const metadata: Metadata = {
  title: NOT_FOUND.title,
  robots: { index: false },
};

export default function NotFound() {
  return (
    <main className="relative isolate flex min-h-svh items-center overflow-hidden px-4 pb-24 pt-28 md:px-8">
      <div
        aria-hidden
        className="blueprint-grid absolute inset-0 -z-10 [mask-image:radial-gradient(ellipse_at_center,black_20%,transparent_70%)]"
      />
      <div className="mx-auto max-w-2xl text-center">
        <p className="text-sm font-medium uppercase tracking-wider text-accent">{NOT_FOUND.eyebrow}</p>
        <h1 className="mt-3 text-balance text-3xl font-bold tracking-tight sm:text-5xl">{NOT_FOUND.heading}</h1>
        <p className="mt-5 text-pretty text-lg text-text-secondary">{NOT_FOUND.intro}</p>
        <div className="mt-10 flex flex-col items-stretch justify-center gap-3 sm:flex-row sm:items-center">
          <Button href="/">{NOT_FOUND.home}</Button>
          {NOT_FOUND.links.map((link) => (
            <Button key={link.href} href={link.href} variant="secondary">
              {link.label}
            </Button>
          ))}
        </div>
      </div>
    </main>
  );
}
