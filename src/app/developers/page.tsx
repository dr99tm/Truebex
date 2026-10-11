import Link from "next/link";
import { DevPage, OperationReference, devPath } from "@/components/developers/DevDocs";
import { Button } from "@/components/ui/Button";
import { loadCatalogue } from "@/lib/catalogue-data";
import { DEVELOPER_DOCS as D } from "@/lib/constants";
import { apiDocument, operations } from "@/lib/developer-docs";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata({
  title: D.overview.title,
  description: D.overview.description,
  path: "/developers/",
});

// Allowances per plan, from the plan catalogue (the pricing page's source).
const nf = new Intl.NumberFormat("en-US");
const LIMITS = loadCatalogue().tiers.map((t) => ({
  plan: t.name,
  requests: nf.format(t.api.monthly_requests),
  keys: nf.format(t.api.max_api_keys),
}));

function fill(text: string, values: Record<string, string | number>): string {
  return text.replace(/\{(\w+)\}/g, (_, k: string) => String(values[k] ?? ""));
}

export default function DevelopersPage() {
  const O = D.overview;
  const doc = apiDocument();
  const limits = doc["x-truebex-limits"];
  const sections = D.nav.filter((n) => n.slug);
  return (
    <DevPage
      slug=""
      eyebrow={O.eyebrow}
      h1={O.h1}
      intro={O.intro}
      description={O.description}
      actions={
        <>
          <Button href="/signup/?next=%2Fdashboard%2Fkeys%2F">{O.cta}</Button>
          <Button href="/dashboard/usage/" variant="secondary">
            {O.ctaSecondary}
          </Button>
        </>
      }
    >
      <h2 id="quick-start">{O.quickStartTitle}</h2>
      <ol className="my-4 list-decimal space-y-2 pl-6 text-text-secondary">
        {O.quickStart.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ol>
      <pre>
        <code>{`curl ${D.apiBase}/v1/ping \\
  -H "Authorization: Bearer tbx_live_your_key"`}</code>
      </pre>

      <h2 id="what">{O.groupsTitle}</h2>
      <ul>
        {sections.map((s) => {
          const page = D.pages[s.slug as keyof typeof D.pages];
          return (
            <li key={s.slug}>
              <Link className="text-accent hover:underline" href={devPath(s.slug)}>
                {page.h1}
              </Link>
              {` — ${page.intro.split(". ")[0].replace(/\.$/, "")}.`}
            </li>
          );
        })}
      </ul>

      <h2 id="authentication">{O.authTitle}</h2>
      <p>{O.authText}</p>
      <pre>
        <code>{`Authorization: Bearer tbx_live_…
# or
X-API-Key: tbx_live_…`}</code>
      </pre>
      <ul>
        {O.keyRules.map((r) => (
          <li key={r}>{r}</li>
        ))}
      </ul>

      <h2 id="scopes">{O.scopesTitle}</h2>
      <p>{O.scopesIntro}</p>
      <table>
        <thead>
          <tr>
            <th>{O.scopeColumn}</th>
            <th>{O.allowsColumn}</th>
          </tr>
        </thead>
        <tbody>
          {doc["x-truebex-scopes"].map((s) => (
            <tr key={s.scope} data-scope={s.scope}>
              <td>
                <code>{s.scope}</code>
                {s.default ? <span className="mt-1 block text-xs text-text-muted">{O.defaultScope}</span> : null}
              </td>
              <td>{s.description}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2 id="base-url">{O.baseUrlTitle}</h2>
      <pre>
        <code>{D.apiBase}</code>
      </pre>

      <h2 id="limits">{O.limitsTitle}</h2>
      <p>{O.limitsText}</p>
      <pre>
        <code>{`X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 958`}</code>
      </pre>
      <table>
        <thead>
          <tr>
            <th>{O.limitsPlan}</th>
            <th>{O.limitsRequests}</th>
            <th>{O.limitsKeys}</th>
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
      <p>{fill(O.burstText, { burst: limits.burst, perMinute: limits.per_minute })}</p>

      <h2 id="errors">{O.errorsTitle}</h2>
      <p>{O.errorsIntro}</p>
      <pre>
        <code>{`HTTP/1.1 403 Forbidden
{
  "detail": "This API key does not have the projects:write scope.",
  "code": "forbidden",
  "status": 403,
  "request_id": "5c1e0f…",
  "retry_after_s": null,
  "data": { "needed": "projects:write", "scopes": ["projects:read"] }
}`}</code>
      </pre>
      <table>
        <thead>
          <tr>
            <th>{O.errorStatus}</th>
            <th>{O.errorCode}</th>
            <th>{O.errorMeaning}</th>
          </tr>
        </thead>
        <tbody>
          {O.errors.map((e) => (
            <tr key={e.code}>
              <td>
                <code>{e.status}</code>
              </td>
              <td>
                <code>{e.code}</code>
              </td>
              <td>{e.meaning}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2 id="versions">{O.contractsTitle}</h2>
      <p>{O.contractsText}</p>

      <OperationReference ops={operations(["account"])} />
    </DevPage>
  );
}
