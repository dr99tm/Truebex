// Server-only: public site identifiers with build-time overrides, so a local
// build can try the analytics beacon and the verification tags without
// editing constants.ts. None of these values is a secret.
import { ANALYTICS, SOCIAL, VERIFICATION } from "@/lib/constants";

export const analyticsToken =
  process.env.TRUEBEX_ANALYTICS_TOKEN ?? ANALYTICS.cloudflareToken;

export const verification = {
  google: process.env.TRUEBEX_GOOGLE_SITE_VERIFICATION ?? VERIFICATION.google,
  bing: process.env.TRUEBEX_BING_SITE_VERIFICATION ?? VERIFICATION.bing,
};

/** Social accounts that have a URL (the footer's Follow column, `sameAs`). */
export const socialLinks = SOCIAL.filter((s) => s.url);
