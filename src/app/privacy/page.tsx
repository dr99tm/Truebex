import type { Metadata } from "next";
import { LegalPage } from "@/components/layout/LegalPage";
import { APP_TELEMETRY_PRIVACY, PROCESSORS, SITE, WEBSITE_ANALYTICS_NOTICE } from "@/lib/constants";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "What Truebex collects, why, who processes it, and how to have it deleted.",
  alternates: { canonical: "/privacy/" },
};

export default function PrivacyPage() {
  return (
    <LegalPage title="Privacy Policy" updated="October 9, 2026">
      <p>
        This policy explains what information Truebex (&ldquo;we&rdquo;)
        collects when you use truebex.com, your Truebex account, the
        dashboard, the Truebex API and the desktop app, and what we do with it. We collect only
        what we need to run the service, and we do not sell personal
        information.
      </p>

      <h2>What we collect</h2>
      <ul>
        <li>
          <strong>Account details.</strong> Your email address and, if you sign
          up with a password, a one-way hash of it (never the password itself).
        </li>
        <li>
          <strong>Google sign-in.</strong> If you choose &ldquo;Sign in with
          Google&rdquo;, Google shares your name, email address, profile
          picture and a Google account identifier with us. We use them only to
          create and identify your account. We do not receive access to your
          Google Drive, Gmail, contacts or any other Google data.
        </li>
        <li>
          <strong>API keys and usage.</strong> A one-way hash of each API key,
          its name, and per-day counts of the API endpoints each key called.
          We use this to authenticate requests, enforce plan limits and show
          you your usage.
        </li>
        <li>
          <strong>Devices.</strong> When you sign in to the Truebex app on a
          computer, we record the computer&rsquo;s name, its operating system,
          the app version, when it was activated and last seen, and a
          fingerprint: a one-way hash the app makes from the computer&rsquo;s
          identifiers, never the identifiers themselves. We use them to keep
          the computer signed in, to count your devices against your plan,
          to offer the free trial once per computer, and to show the list in
          your dashboard, where you can remove any of them.
        </li>
        <li>
          <strong>Billing records.</strong> Your plan, billing interval and
          seats, payment amounts and tax, invoices, dates, status, the payment
          provider&rsquo;s reference, and the version and time of the
          cancellation terms you accepted at checkout. Card details are entered
          on the provider&rsquo;s own checkout and never reach our servers.
        </li>
        <li>
          <strong>Demo requests.</strong> The name, email, company and project
          description you send through the &ldquo;Request a Demo&rdquo; form.
        </li>
        <li>
          <strong>Session token.</strong> When you sign in, your browser keeps
          a session token in local storage so you stay signed in. We do not
          use advertising or tracking cookies.
        </li>
      </ul>

      <h2>{WEBSITE_ANALYTICS_NOTICE.title}</h2>
      {WEBSITE_ANALYTICS_NOTICE.paragraphs.map((p) => (
        <p key={p}>{p}</p>
      ))}

      <h2>How we use it</h2>
      <ul>
        <li>To provide your account, dashboard, API keys and the API itself.</li>
        <li>To process subscriptions and show your billing history.</li>
        <li>To answer demo requests and support questions.</li>
        <li>To keep the service secure and prevent abuse.</li>
      </ul>

      <h2>Who processes it for us</h2>
      <p>
        We rely on a small number of providers, each only for its part of the
        service:
      </p>
      <ul>
        {PROCESSORS.map((p) => (
          <li key={p.name}>
            <strong>{p.name}</strong> — {p.role}
          </li>
        ))}
      </ul>
      <p>We share information with others only when the law requires it.</p>

      <h2>{APP_TELEMETRY_PRIVACY.heading}</h2>
      <p>{APP_TELEMETRY_PRIVACY.intro}</p>
      <ul>
        {APP_TELEMETRY_PRIVACY.kinds.map((k) => (
          <li key={k.name}>
            <strong>{k.name}.</strong> {k.consent} {k.holds}
          </li>
        ))}
      </ul>
      <p>{APP_TELEMETRY_PRIVACY.identity}</p>
      <h3>{APP_TELEMETRY_PRIVACY.retentionHeading}</h3>
      <ul>
        {APP_TELEMETRY_PRIVACY.retention.map((r) => (
          <li key={r.data}>
            <strong>{r.data}:</strong> {r.kept}; then {r.then}.
          </li>
        ))}
      </ul>
      <p>{APP_TELEMETRY_PRIVACY.deletion}</p>

      <h2>How long we keep it</h2>
      <p>
        Account, key and billing records are kept while your account exists.
        Usage counts are kept for as long as they are useful for billing and
        your dashboard. Demo requests are kept while we are in conversation
        with you. Billing records may be kept longer where the law requires.
      </p>

      <h2>Your choices and rights</h2>
      <ul>
        <li>Revoke any API key, or remove any signed-in computer, at any time from your dashboard.</li>
        <li>
          Turn the desktop app&rsquo;s usage events and crash reports on or off
          at any time in its privacy settings.
        </li>
        <li>
          Ask us for a copy of your data, to correct it, or to delete your
          account and its data, by emailing{" "}
          <a className="text-accent hover:underline" href={`mailto:${SITE.email}`}>
            {SITE.email}
          </a>
          .
        </li>
        <li>
          Remove Truebex&rsquo;s access to your Google account at any time from{" "}
          <a
            className="text-accent hover:underline"
            href="https://myaccount.google.com/connections"
            rel="noopener noreferrer"
          >
            your Google account settings
          </a>
          .
        </li>
      </ul>

      <h2>Security</h2>
      <p>
        Passwords, API keys and device sign-in tokens are stored only as one-way hashes, all traffic
        uses HTTPS, and plan changes are accepted only from payment events we
        verify with the provider.
      </p>

      <h2>Children</h2>
      <p>Truebex is not directed at children under 16, and we do not knowingly collect their information.</p>

      <h2>Changes</h2>
      <p>
        If we change this policy we will update the date above, and tell
        account holders by email about any significant change.
      </p>

      <h2>Contact</h2>
      <p>
        Questions about privacy:{" "}
        <a className="text-accent hover:underline" href={`mailto:${SITE.email}`}>
          {SITE.email}
        </a>
        .
      </p>
    </LegalPage>
  );
}
