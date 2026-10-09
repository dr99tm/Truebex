import Link from "next/link";
import { AR_HOME, FEATURE_PAGES, FOOTER, NAV_LINKS, SITE } from "@/lib/constants";
import { Lockup } from "@/components/brand/Logo";
import { CloudflareAnalytics } from "@/components/analytics/CloudflareAnalytics";
import { LanguageSwitch } from "@/components/layout/LanguageSwitch";
import { socialLinks } from "@/lib/site-config";

const linkClass = "text-sm text-text-secondary transition-colors hover:text-text-primary";

/**
 * The public site's footer. Every public page renders it and no signed-in
 * page does, so it also carries the cookieless analytics beacon.
 */
export function Footer({ locale = "en" }: { locale?: "en" | "ar" }) {
  const ar = locale === "ar";
  const t = ar ? AR_HOME.footer : FOOTER;
  const product = ar ? AR_HOME.nav : NAV_LINKS;
  const resources = ar ? AR_HOME.footer.links : FOOTER.links;

  return (
    <footer className="border-t border-border bg-surface">
      <div className="mx-auto max-w-7xl px-4 py-12 md:px-8">
        <div className="grid gap-10 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6">
          <div className="lg:col-span-1">
            <Lockup className="text-xl" />
            <p className="mt-3 text-sm text-text-secondary">{ar ? AR_HOME.footer.tagline : SITE.tagline}</p>
            <p className="mt-4 max-w-xs text-xs text-text-muted">{t.blurb}</p>
          </div>

          <nav aria-label={t.product}>
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-muted">{t.product}</h2>
            <ul className="space-y-2">
              {product.map((link) => (
                <li key={link.href}>
                  <a href={link.href} className={linkClass}>
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>

          <nav aria-label={t.features}>
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-muted">{t.features}</h2>
            <ul className="space-y-2">
              {FEATURE_PAGES.map((page) => (
                <li key={page.slug}>
                  <a href={`/features/${page.slug}/`} className={linkClass}>
                    {ar
                      ? AR_HOME.footer.featureNames[page.slug as keyof typeof AR_HOME.footer.featureNames]
                      : page.nav}
                  </a>
                </li>
              ))}
            </ul>
          </nav>

          <nav aria-label={t.resources}>
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-muted">{t.resources}</h2>
            <ul className="space-y-2">
              {resources.map((link) => (
                <li key={link.href}>
                  <a href={link.href} className={linkClass}>
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>

          <div>
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-muted">{t.contact}</h2>
            <ul className="space-y-2 text-sm text-text-secondary">
              <li>
                <a href={`mailto:${SITE.email}`} className="transition-colors hover:text-text-primary" dir="ltr">
                  {SITE.email}
                </a>
              </li>
              <li>
                <Link href={ar ? "/ar/#contact" : "/#contact"} className="transition-colors hover:text-text-primary">
                  {t.demo}
                </Link>
              </li>
            </ul>
          </div>

          {socialLinks.length > 0 && (
            <nav aria-label={t.follow}>
              <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-muted">{t.follow}</h2>
              <ul className="space-y-2">
                {socialLinks.map((s) => (
                  <li key={s.id}>
                    <a href={s.url} data-social={s.id} rel="me noopener noreferrer" className={linkClass}>
                      {s.label}
                    </a>
                  </li>
                ))}
              </ul>
            </nav>
          )}
        </div>

        <div className="mt-12 flex flex-col items-center justify-between gap-4 border-t border-border pt-6 text-xs text-text-muted sm:flex-row">
          <p>
            &copy; {new Date().getFullYear()} Truebex. {t.rights}
          </p>
          <LanguageSwitch current={locale} />
        </div>
      </div>
      <CloudflareAnalytics />
    </footer>
  );
}
