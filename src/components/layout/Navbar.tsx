"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, X } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { AR_HOME, NAV_LINKS, NAV_UI } from "@/lib/constants";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";
import { useCurrentUser } from "@/lib/useAuth";
import { ProfileMenu } from "@/components/auth/ProfileMenu";
import { Lockup } from "@/components/brand/Logo";
import { LanguageSwitch } from "@/components/layout/LanguageSwitch";

// English labels, and the Arabic ones on /ar/ (the Arabic landing page).
const COPY = {
  en: { links: NAV_LINKS, ...NAV_UI },
  ar: { links: AR_HOME.nav, login: AR_HOME.login, demo: AR_HOME.demo, demoHref: "/ar/#contact", dashboard: AR_HOME.dashboard, home: AR_HOME.home, toggle: AR_HOME.toggleMenu },
} as const;

export function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const { user } = useCurrentUser();
  const pathname = usePathname() ?? "/";
  const locale = pathname === "/ar" || pathname.startsWith("/ar/") ? "ar" : "en";
  const t = COPY[locale];

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 50);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Lock body scroll when mobile menu is open
  useEffect(() => {
    if (mobileOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [mobileOpen]);

  return (
    <>
      <header
        className={cn(
          "fixed top-0 left-0 right-0 z-50 transition-all duration-300",
          scrolled
            ? "bg-[var(--color-navbar-scrolled)] backdrop-blur-xl border-b border-border"
            : "bg-[var(--color-navbar)] backdrop-blur-md"
        )}
      >
        <nav className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 md:px-8 md:py-4">
          {/* Logo — links home (works from any route, not just the homepage) */}
          <Link
            href="/"
            className="relative z-50 shrink-0 text-xl transition-opacity hover:opacity-80"
            aria-label={t.home}
          >
            <Lockup />
          </Link>

          {/* Desktop nav — hidden below lg (1024px) since we have 7 links */}
          <ul className="hidden items-center gap-6 lg:flex">
            {t.links.map((link) => (
              <li key={link.href}>
                <a
                  href={link.href}
                  className="text-sm text-text-secondary transition-colors hover:text-text-primary whitespace-nowrap"
                >
                  {link.label}
                </a>
              </li>
            ))}
          </ul>

          {/* Desktop CTA */}
          <div className="hidden lg:flex items-center gap-3 shrink-0">
            <LanguageSwitch current={locale} className="me-1" />
            {user ? (
              <>
                <Button href="/dashboard/" variant="secondary" size="sm">
                  {t.dashboard}
                </Button>
                <ProfileMenu user={user} />
              </>
            ) : (
              <>
                <Button href="/login" variant="secondary" size="sm">
                  {t.login}
                </Button>
                <Button href={t.demoHref} size="sm">
                  {t.demo}
                </Button>
              </>
            )}
          </div>

          {/* Mobile bar controls — Dashboard + avatar when signed in, or a
              direct Log in button when not, alongside the burger toggle. */}
          <div className="flex items-center gap-2 lg:hidden">
            {user ? (
              <>
                <Button href="/dashboard/" variant="secondary" size="sm">
                  {t.dashboard}
                </Button>
                <ProfileMenu user={user} />
              </>
            ) : (
              <Button href="/login" variant="secondary" size="sm">
                {t.login}
              </Button>
            )}
            <button
              className="relative z-50 flex h-10 w-10 items-center justify-center rounded-lg text-text-primary transition-colors hover:bg-white/10"
              onClick={() => setMobileOpen(!mobileOpen)}
              aria-label={t.toggle}
            >
              {mobileOpen ? <X size={22} /> : <Menu size={22} />}
            </button>
          </div>
        </nav>
      </header>

      {/* Mobile menu — fullscreen overlay (outside header for proper stacking) */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-40 bg-background/95 backdrop-blur-xl lg:hidden"
          >
            <div className="flex h-full flex-col items-center justify-center px-6">
              <ul className="flex flex-col items-center gap-5">
                {t.links.map((link, i) => (
                  <motion.li
                    key={link.href}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.05 * i, duration: 0.3 }}
                  >
                    <a
                      href={link.href}
                      className="text-xl font-medium text-text-secondary transition-colors hover:text-text-primary sm:text-2xl"
                      onClick={() => setMobileOpen(false)}
                    >
                      {link.label}
                    </a>
                  </motion.li>
                ))}
                <motion.li
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.05 * t.links.length, duration: 0.3 }}
                >
                  <LanguageSwitch
                    current={locale}
                    className="text-lg"
                    onClick={() => setMobileOpen(false)}
                  />
                </motion.li>
                {/* Signed-in users see Dashboard + profile directly in the
                    navbar bar, so the overlay only carries page links. */}
                {!user && (
                  <>
                    <motion.li
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{
                        delay: 0.05 * (t.links.length + 1),
                        duration: 0.3,
                      }}
                    >
                      <a
                        href="/login"
                        className="text-xl font-medium text-text-secondary transition-colors hover:text-text-primary sm:text-2xl"
                        onClick={() => setMobileOpen(false)}
                      >
                        {t.login}
                      </a>
                    </motion.li>
                    <motion.li
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{
                        delay: 0.05 * (t.links.length + 2),
                        duration: 0.3,
                      }}
                    >
                      <Button
                        href={t.demoHref}
                        size="lg"
                        className="mt-4"
                        onClick={() => setMobileOpen(false)}
                      >
                        {t.demo}
                      </Button>
                    </motion.li>
                  </>
                )}
              </ul>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
