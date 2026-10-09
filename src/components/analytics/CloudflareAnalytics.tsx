import Script from "next/script";
import { analyticsToken } from "@/lib/site-config";

const BEACON = "https://static.cloudflareinsights.com/beacon.min.js";

/**
 * Cloudflare Web Analytics: cookieless page views, no cross-site profile.
 * Rendered by the public site's Footer only, so it never loads on the
 * dashboard, account or sign-in pages. `spa: false` stops the beacon from
 * following a client-side navigation into a signed-in area. No token, no
 * script.
 */
export function CloudflareAnalytics() {
  if (!analyticsToken) return null;
  return (
    <Script
      id="cf-web-analytics"
      src={BEACON}
      strategy="afterInteractive"
      data-cf-beacon={JSON.stringify({ token: analyticsToken, spa: false })}
    />
  );
}
