import type { Metadata } from "next";
import Link from "next/link";
import { Footer } from "@/components/layout/Footer";
import { Button } from "@/components/ui/Button";
import { loadCatalogue } from "@/lib/catalogue-data";

const API = "https://api.truebex.com";

export const metadata: Metadata = {
  title: "Developer API",
  description:
    "Build on Truebex. Create API keys in your dashboard, authenticate with a bearer token, and track usage against your plan's monthly allowance.",
  alternates: { canonical: "/developers/" },
  openGraph: {
    title: "Truebex Developer API",
    description:
      "API keys, bearer authentication, usage metering and rate limits for the Truebex API.",
    url: "https://truebex.com/developers/",
  },
};

const ENDPOINTS = [
  { method: "GET", path: "/v1/ping", desc: "Check that a key works. Returns the server time." },
  { method: "GET", path: "/v1/account", desc: "The key's owner, plan and this month's usage." },
];

// Allowances per plan, from the plan catalogue (the pricing page's source).
const nf = new Intl.NumberFormat("en-US");
const LIMITS = loadCatalogue().tiers.map((t) => ({
  plan: t.name,
  requests: nf.format(t.api.monthly_requests),
  keys: nf.format(t.api.max_api_keys),
}));

const ERRORS = [
  { code: "401", meaning: "Missing, malformed, invalid or revoked API key." },
  { code: "429", meaning: "Monthly request allowance used up. Resets on the 1st (UTC), or upgrade." },
  { code: "5xx", meaning: "Server problem. Retry with exponential backoff." },
];

const techArticleLd = {
  "@context": "https://schema.org",
  "@type": "TechArticle",
  headline: "Truebex Developer API",
  description:
    "How to authenticate with the Truebex API using API keys, call endpoints, and stay within usage limits.",
  url: "https://truebex.com/developers/",
  publisher: { "@id": "https://truebex.com/#organization" },
};

export default function DevelopersPage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(techArticleLd) }}
      />
      <main className="mx-auto max-w-3xl px-4 pb-24 pt-28 md:px-8">
        <p className="text-sm font-medium uppercase tracking-wider text-accent">Developers</p>
        <h1 className="mt-3 text-3xl font-bold tracking-tight sm:text-5xl">The Truebex API</h1>
        <p className="mt-5 text-lg text-text-secondary">
          Authenticate with an API key, call the API over HTTPS, and watch your
          usage in the dashboard. Every plan includes a monthly request
          allowance.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Button href="/signup/?next=%2Fdashboard%2Fkeys%2F">Get an API key</Button>
          <Button href="/dashboard/usage/" variant="secondary">
            View usage
          </Button>
        </div>

        <article className="prose-doc mt-8">
          <h2 id="quick-start">Quick start</h2>
          <ol className="my-4 list-decimal space-y-2 pl-6 text-text-secondary">
            <li>
              <Link className="text-accent hover:underline" href="/signup/">
                Create a free account
              </Link>{" "}
              (Google or email).
            </li>
            <li>
              Open{" "}
              <Link className="text-accent hover:underline" href="/dashboard/keys/">
                Dashboard → API keys
              </Link>{" "}
              and create a key. Copy it — it is shown once.
            </li>
            <li>Call the API:</li>
          </ol>
          <pre>
            <code>{`curl ${API}/v1/ping \\
  -H "Authorization: Bearer tbx_live_your_key"`}</code>
          </pre>

          <h2 id="authentication">Authentication</h2>
          <p>
            Send your key on every request, either as a bearer token or in the{" "}
            <code>X-API-Key</code> header. Keys start with <code>tbx_live_</code>.
          </p>
          <pre>
            <code>{`Authorization: Bearer tbx_live_…
# or
X-API-Key: tbx_live_…`}</code>
          </pre>
          <ul>
            <li>Keep keys on your server. Never ship them in browser or app code.</li>
            <li>Use one key per environment, and revoke a key the moment it leaks.</li>
            <li>We store only a hash of each key, so a lost key can&apos;t be recovered — create a new one.</li>
          </ul>

          <h2 id="base-url">Base URL</h2>
          <pre>
            <code>{API}</code>
          </pre>

          <h2 id="endpoints">Endpoints</h2>
          <table>
            <thead>
              <tr>
                <th>Method</th>
                <th>Path</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              {ENDPOINTS.map((e) => (
                <tr key={e.path}>
                  <td>
                    <code>{e.method}</code>
                  </td>
                  <td>
                    <code>{e.path}</code>
                  </td>
                  <td>{e.desc}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p>
            Project and asset endpoints are on the roadmap and will be added
            under <code>/v1</code> without breaking these.
          </p>

          <h3>Example response</h3>
          <pre>
            <code>{`GET /v1/account

{
  "email": "you@example.com",
  "plan": "free",
  "key": { "id": 1, "name": "Production", "prefix": "tbx_live_Ab12Cd" },
  "usage": { "used": 42, "limit": 1000, "remaining": 958 }
}`}</code>
          </pre>

          <h2 id="limits">Usage and limits</h2>
          <p>
            Every call to <code>/v1</code> counts toward your monthly allowance,
            across all your keys. Allowances reset on the 1st of each month
            (UTC). Each response carries your current numbers:
          </p>
          <pre>
            <code>{`X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 958`}</code>
          </pre>
          <table>
            <thead>
              <tr>
                <th>Plan</th>
                <th>Requests / month</th>
                <th>Active keys</th>
              </tr>
            </thead>
            <tbody>
              {LIMITS.map((l) => (
                <tr key={l.plan}>
                  <td>{l.plan}</td>
                  <td>{l.requests}</td>
                  <td>{l.keys}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h2 id="errors">Errors</h2>
          <p>
            Errors return JSON with a human-readable <code>detail</code>:
          </p>
          <pre>
            <code>{`HTTP/1.1 429 Too Many Requests
{ "detail": "Monthly limit of 1000 requests reached for the Free plan." }`}</code>
          </pre>
          <table>
            <thead>
              <tr>
                <th>Status</th>
                <th>Meaning</th>
              </tr>
            </thead>
            <tbody>
              {ERRORS.map((e) => (
                <tr key={e.code}>
                  <td>
                    <code>{e.code}</code>
                  </td>
                  <td>{e.meaning}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h2 id="examples">Examples</h2>
          <h3>JavaScript (Node 18+)</h3>
          <pre>
            <code>{`const res = await fetch("${API}/v1/account", {
  headers: { Authorization: \`Bearer \${process.env.TRUEBEX_API_KEY}\` },
});
if (!res.ok) throw new Error((await res.json()).detail);
console.log(await res.json());`}</code>
          </pre>
          <h3>Python</h3>
          <pre>
            <code>{`import os, requests

r = requests.get(
    "${API}/v1/account",
    headers={"Authorization": f"Bearer {os.environ['TRUEBEX_API_KEY']}"},
    timeout=10,
)
r.raise_for_status()
print(r.json())`}</code>
          </pre>
        </article>
      </main>
      <Footer />
    </>
  );
}
