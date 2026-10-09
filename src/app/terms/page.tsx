import type { Metadata } from "next";
import { LegalPage } from "@/components/layout/LegalPage";
import { SITE, TERMS_PAID_PLANS } from "@/lib/constants";

export const metadata: Metadata = {
  title: "Terms of Service",
  description: "The terms for using Truebex, the dashboard, API keys, the API and paid plans.",
  alternates: { canonical: "/terms/" },
};

export default function TermsPage() {
  return (
    <LegalPage title="Terms of Service" updated="October 9, 2026">
      <p>
        These terms apply when you use truebex.com, a Truebex account, the
        dashboard, API keys or the Truebex API (together, &ldquo;the
        service&rdquo;). By creating an account or using the service you agree
        to them.
      </p>

      <h2>Your account</h2>
      <ul>
        <li>You need a valid email address or Google account to sign up.</li>
        <li>Keep your sign-in details and API keys secret. You are responsible for activity under your account and keys.</li>
        <li>Tell us promptly at {SITE.email} if you think your account or a key has been compromised, and revoke the key from your dashboard.</li>
      </ul>

      <h2>The API</h2>
      <ul>
        <li>Each plan includes a monthly number of API requests and active keys, shown on the pricing section and in your dashboard.</li>
        <li>Requests beyond your allowance are refused until the next month or until you upgrade.</li>
        <li>Don&rsquo;t try to get around limits, disrupt the service, access other people&rsquo;s data, or use the service to break the law.</li>
        <li>We may change or add endpoints over time and will try to avoid breaking existing ones.</li>
      </ul>

      <h2>Paid plans</h2>
      <ul>
        {TERMS_PAID_PLANS.map((item) => (
          <li key={item.title}>
            <strong>{item.title}:</strong> {item.text}
          </li>
        ))}
        <li>If something goes wrong with a payment, contact us at {SITE.email} and we will make it right.</li>
      </ul>

      <h2>Your content</h2>
      <p>
        Designs, projects and other content you create with Truebex belong to
        you. You give us only the permissions needed to operate the service for
        you.
      </p>

      <h2>Our service</h2>
      <p>
        Truebex, its software, website, brand and documentation belong to us
        and are protected by law. These terms don&rsquo;t give you any rights
        to our name, logo or brand.
      </p>

      <h2>Availability and warranty</h2>
      <p>
        We work to keep the service available and reliable, but it is provided
        &ldquo;as is&rdquo;, without guarantees of uninterrupted or error-free
        operation. Features marked &ldquo;on the roadmap&rdquo; are plans, not
        commitments.
      </p>

      <h2>Limitation of liability</h2>
      <p>
        To the extent the law allows, Truebex is not liable for indirect or
        consequential losses, and our total liability for any claim is limited
        to the amount you paid us in the three months before it.
      </p>

      <h2>Ending your use</h2>
      <p>
        You can stop using the service and ask us to delete your account at any
        time. We may suspend or close accounts that break these terms, and will
        tell you why when we can.
      </p>

      <h2>Changes</h2>
      <p>
        We may update these terms. We will change the date above and tell
        account holders by email about significant changes before they take
        effect.
      </p>

      <h2>Contact</h2>
      <p>
        <a className="text-accent hover:underline" href={`mailto:${SITE.email}`}>
          {SITE.email}
        </a>
      </p>
    </LegalPage>
  );
}
