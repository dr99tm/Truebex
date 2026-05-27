import { NAV_LINKS } from "@/lib/constants";

export function Footer() {
  return (
    <footer className="border-t border-border bg-surface">
      <div className="mx-auto max-w-7xl px-4 py-12 md:px-8">
        <div className="grid gap-8 md:grid-cols-3">
          {/* Brand */}
          <div>
            <span className="text-xl font-bold gradient-text">Truebex</span>
            <p className="mt-2 text-sm text-text-secondary">
              True Building Experience
            </p>
            <p className="mt-4 text-xs text-text-muted max-w-xs">
              Design, surf the market, calculate, experience in VR, and make
              instant changes — all in one platform.
            </p>
          </div>

          {/* Links */}
          <div>
            <h4 className="text-sm font-semibold uppercase tracking-wider text-text-muted mb-4">
              Quick Links
            </h4>
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
          </div>

          {/* Contact */}
          <div>
            <h4 className="text-sm font-semibold uppercase tracking-wider text-text-muted mb-4">
              Get in Touch
            </h4>
            <ul className="space-y-2 text-sm text-text-secondary">
              <li>
                <a
                  href="mailto:dr99tm@gmail.com"
                  className="transition-colors hover:text-text-primary"
                >
                  dr99tm@gmail.com
                </a>
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom */}
        <div className="mt-12 border-t border-border pt-6 text-center text-xs text-text-muted">
          &copy; {new Date().getFullYear()} Truebex. All rights reserved.
        </div>
      </div>
    </footer>
  );
}
