import Link from "next/link";
import { NAV_LINKS, SITE } from "@/lib/constants";
import { Lockup } from "@/components/brand/Logo";

const RESOURCES = [
  { label: "Developer docs", href: "/developers/" },
  { label: "Dashboard", href: "/dashboard/" },
  { label: "Create account", href: "/signup/" },
  { label: "Brand assets", href: "/brand/truebex-mark-grey.svg" },
  { label: "Privacy", href: "/privacy/" },
  { label: "Terms", href: "/terms/" },
] as const;

export function Footer() {
  return (
    <footer className="border-t border-border bg-surface">
      <div className="mx-auto max-w-7xl px-4 py-12 md:px-8">
        <div className="grid gap-10 md:grid-cols-4">
          <div className="md:col-span-1">
            <Lockup className="text-xl" />
            <p className="mt-3 text-sm text-text-secondary">{SITE.tagline}</p>
            <p className="mt-4 max-w-xs text-xs text-text-muted">
              The building design platform where daylight is measured,
              surfaces design themselves and every change is instant.
            </p>
          </div>

          <nav aria-label="Site">
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-muted">
              Product
            </h2>
            <ul className="space-y-2">
              {NAV_LINKS.map((link) => (
                <li key={link.href}>
                  <a
                    href={link.href}
                    className="text-sm text-text-secondary transition-colors hover:text-text-primary"
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>

          <nav aria-label="Resources">
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-muted">
              Resources
            </h2>
            <ul className="space-y-2">
              {RESOURCES.map((link) => (
                <li key={link.href}>
                  <a
                    href={link.href}
                    className="text-sm text-text-secondary transition-colors hover:text-text-primary"
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>

          <div>
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-muted">
              Get in touch
            </h2>
            <ul className="space-y-2 text-sm text-text-secondary">
              <li>
                <a
                  href={`mailto:${SITE.email}`}
                  className="transition-colors hover:text-text-primary"
                >
                  {SITE.email}
                </a>
              </li>
              <li>
                <Link href="/#contact" className="transition-colors hover:text-text-primary">
                  Request a demo
                </Link>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-12 border-t border-border pt-6 text-center text-xs text-text-muted">
          &copy; {new Date().getFullYear()} Truebex. All rights reserved.
        </div>
      </div>
    </footer>
  );
}
