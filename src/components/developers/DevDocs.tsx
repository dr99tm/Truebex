// The /developers/ pages (PF12): one layout with the section nav, the status
// note for work still on the roadmap, and the reference tables generated from
// openapi/v1.json at build time. Server components only.
import Link from "next/link";
import { Footer } from "@/components/layout/Footer";
import { DEVELOPER_DOCS as D } from "@/lib/constants";
import type { Field, Operation } from "@/lib/developer-docs";
import { breadcrumbLd, ldJson } from "@/lib/seo";

export function devPath(slug: string): string {
  return slug ? `/developers/${slug}/` : "/developers/";
}

export function DevPage({
  slug,
  eyebrow = D.breadcrumb,
  h1,
  intro,
  description,
  status,
  statusLabel = D.onRoadmap,
  actions,
  children,
}: {
  slug: string;
  eyebrow?: string;
  h1: string;
  intro: string;
  description: string;
  status?: string;
  statusLabel?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
}) {
  const path = devPath(slug);
  const label = D.nav.find((n) => n.slug === slug)?.label ?? h1;
  const crumbs = [
    { name: "Truebex", path: "/" },
    { name: D.breadcrumb, path: "/developers/" },
    ...(slug ? [{ name: label, path }] : []),
  ];
  const ld = ldJson([
    {
      "@type": "TechArticle",
      headline: h1,
      description,
      url: `https://truebex.com${path}`,
      inLanguage: "en",
      publisher: { "@id": "https://truebex.com/#organization" },
    },
    breadcrumbLd(crumbs),
  ]);
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: ld }} />
      <main className="mx-auto max-w-6xl px-4 pb-24 pt-28 md:px-8">
        <nav aria-label="Breadcrumb" className="text-sm text-text-muted">
          <ol className="flex flex-wrap gap-1">
            {crumbs.map((c, i) => (
              <li key={c.path} className="flex gap-1">
                {i > 0 && <span aria-hidden>/</span>}
                {i < crumbs.length - 1 ? (
                  <Link className="hover:text-text-primary" href={c.path}>
                    {c.name}
                  </Link>
                ) : (
                  <span aria-current="page">{c.name}</span>
                )}
              </li>
            ))}
          </ol>
        </nav>
        <div className="mt-6 grid gap-10 lg:grid-cols-[13rem_minmax(0,1fr)]">
          <aside>
            <nav aria-label="Developer docs" className="lg:sticky lg:top-24">
              <ul className="flex flex-wrap gap-2 lg:flex-col lg:gap-1">
                {D.nav.map((n) => (
                  <li key={n.slug}>
                    <Link
                      href={devPath(n.slug)}
                      aria-current={n.slug === slug ? "page" : undefined}
                      className={
                        n.slug === slug
                          ? "block rounded-[var(--radius-button)] bg-accent/10 px-3 py-1.5 text-sm text-accent"
                          : "block rounded-[var(--radius-button)] px-3 py-1.5 text-sm text-text-secondary hover:text-text-primary"
                      }
                    >
                      {n.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
          </aside>
          <div className="min-w-0">
            <p className="text-sm font-medium uppercase tracking-wider text-accent">{eyebrow}</p>
            <h1 className="mt-3 text-3xl font-bold tracking-tight sm:text-5xl">{h1}</h1>
            <p className="mt-5 max-w-3xl text-lg text-text-secondary">{intro}</p>
            {status ? <StatusNote label={statusLabel} text={status} /> : null}
            {actions ? <div className="mt-8 flex flex-wrap gap-3">{actions}</div> : null}
            <article className="prose-doc mt-8 max-w-3xl">{children}</article>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}

export function StatusNote({ label, text }: { label: string; text: string }) {
  return (
    <p className="mt-6 max-w-3xl rounded-[var(--radius-card)] border border-warn/40 bg-warn/5 px-4 py-3 text-sm text-text-secondary">
      <span className="mr-1 font-semibold text-warn">{`${label}.`}</span> {text}
    </p>
  );
}

export function Notes({ title, notes }: { title: string; notes: readonly string[] }) {
  return (
    <>
      <h2>{title}</h2>
      <ul>
        {notes.map((n) => (
          <li key={n}>{n}</li>
        ))}
      </ul>
    </>
  );
}

function FieldTable({ fields, withWhere = false }: { fields: Field[]; withWhere?: boolean }) {
  const R = D.reference;
  return (
    <div className="overflow-x-auto">
      <table>
        <thead>
          <tr>
            <th>{R.field}</th>
            {withWhere && <th>{R.where}</th>}
            <th>{R.type}</th>
            <th>{R.required}</th>
          </tr>
        </thead>
        <tbody>
          {fields.map((f) => (
            <tr key={`${f.where ?? ""}${f.name}`}>
              <td>
                <code>{f.name}</code>
                {f.description ? <span className="mt-1 block text-xs text-text-muted">{f.description}</span> : null}
              </td>
              {withWhere && <td>{f.where}</td>}
              <td>
                <code className="break-all">{f.type}</code>
              </td>
              <td>{f.required ? R.yes : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** One section per operation, generated from openapi/v1.json. */
export function OperationReference({ ops }: { ops: Operation[] }) {
  const R = D.reference;
  return (
    <>
      <h2 id="reference">{R.title}</h2>
      {ops.map((op) => (
        <section key={op.id} id={op.id} data-operation={op.id} className="mt-10 border-t border-border pt-6">
          <h3 className="!mt-0 flex flex-wrap items-baseline gap-2">
            <code className="text-accent">{op.method}</code>
            <code className="break-all">{op.path}</code>
          </h3>
          <p>{op.description}</p>
          <p className="text-sm">
            {R.scope}:{" "}
            {op.scope ? <code>{op.scope}</code> : <span>{R.anyKey}</span>}
            {op.optionalKey ? <span> ({R.optionalKey})</span> : null}
          </p>
          {op.params.length > 0 && (
            <>
              <h4 className="mt-4 text-sm font-semibold text-text-primary">{R.params}</h4>
              <FieldTable fields={op.params} withWhere />
            </>
          )}
          {op.body.kind && (
            <>
              <h4 className="mt-4 text-sm font-semibold text-text-primary">
                {R.body}
                {op.body.schema ? (
                  <>
                    {" "}
                    · <code>{op.body.schema}</code>
                  </>
                ) : null}
              </h4>
              {op.body.kind === "binary" ? <p>{R.binaryBody}</p> : null}
              {op.body.kind === "multipart" ? <p>{R.multipartBody}</p> : null}
              {op.body.fields.length > 0 && <FieldTable fields={op.body.fields} />}
            </>
          )}
          <h4 className="mt-4 text-sm font-semibold text-text-primary">
            {R.response} {op.response.status}
            {op.response.schema ? (
              <>
                {" "}
                · <code>{op.response.schema}</code>
              </>
            ) : null}
          </h4>
          {op.response.status === "204" ? <p>{R.empty}</p> : null}
          {op.response.fields.length > 0 && <FieldTable fields={op.response.fields} />}
          {op.errors.length > 0 && (
            <p className="text-sm">
              {R.errors}: {op.errors.map((e) => e.status).join(", ")}
            </p>
          )}
        </section>
      ))}
    </>
  );
}
