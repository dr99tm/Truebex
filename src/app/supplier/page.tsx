"use client";

import Link from "next/link";
import { ErrorNote, PageHeader, Panel } from "@/components/dashboard/DashboardShell";
import { useApiData } from "@/components/dashboard/useApiData";
import { Badge, can, productTone, useMember } from "@/components/supplier/SupplierShell";
import { formatDate } from "@/lib/api";
import { SUPPLIER } from "@/lib/constants";
import { countsLine, supplierApi } from "@/lib/supplier";

const O = SUPPLIER.overview;
const nf = new Intl.NumberFormat("en-US");

function Stat({ label, value, href }: { label: string; value: number; href?: string }) {
  const body = (
    <>
      <p className="text-3xl font-bold tabular-nums text-text-primary">{nf.format(value)}</p>
      <p className="mt-1 text-sm text-text-secondary">{label}</p>
    </>
  );
  return (
    <Panel className="p-4 md:p-5">
      {href ? (
        <Link href={href} className="block hover:opacity-90">
          {body}
        </Link>
      ) : (
        body
      )}
    </Panel>
  );
}

// The supplier's home: verification state, open requests and orders, the
// catalogue by state, the last import and this week's numbers.
export default function SupplierOverviewPage() {
  const { me, role } = useMember();
  const { data, error } = useApiData(supplierApi.overview);
  const supplier = me.supplier!;

  return (
    <>
      <PageHeader title={O.title} description={O.description} />
      {supplier.status === "applied" && (
        <div className="mb-6 rounded-[var(--radius-card)] border border-warn/30 bg-warn/5 p-4 text-sm text-warn">
          <strong className="mr-2">{SUPPLIER.status.applied}.</strong>
          {O.underReview}
        </div>
      )}
      {supplier.status === "suspended" && (
        <div className="mb-6">
          <ErrorNote message={O.suspended} />
        </div>
      )}
      {error && <ErrorNote message={error} />}
      {data && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-3 md:gap-4">
            <Stat label={O.openRequests} value={data.open.requests} href={can(role, "orders") ? "/supplier/inbox/" : undefined} />
            <Stat label={O.openOrders} value={data.open.orders} href={can(role, "orders") ? "/supplier/inbox/" : undefined} />
          </div>

          <Panel>
            <div className="flex items-center justify-between gap-2">
              <h2 className="font-semibold">{O.products}</h2>
              <Link href="/supplier/catalogue/" className="text-sm text-accent hover:underline">
                {SUPPLIER.nav.catalogue}
              </Link>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {Object.keys(data.products).length === 0 && <p className="text-sm text-text-muted">{SUPPLIER.catalogue.empty}</p>}
              {Object.entries(data.products).map(([status, n]) => (
                <Badge key={status} tone={productTone(status)}>
                  {SUPPLIER.productStatus[status] ?? status}: {n}
                </Badge>
              ))}
            </div>
          </Panel>

          <Panel>
            <h2 className="font-semibold">{O.week}</h2>
            <dl className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-5">
              {(
                [
                  [O.impressions, data.week.impressions],
                  [O.views, data.week.views],
                  [O.placements, data.week.geometry_downloads],
                  [O.quotes, data.week.quotes],
                  [O.orders, data.week.orders],
                ] as const
              ).map(([label, value]) => (
                <div key={label}>
                  <dt className="text-text-muted">{label}</dt>
                  <dd className="text-lg font-semibold tabular-nums text-text-primary">{nf.format(value)}</dd>
                </div>
              ))}
            </dl>
          </Panel>

          <div className="grid gap-4 md:grid-cols-2">
            <Panel>
              <h2 className="font-semibold">{O.lastImport}</h2>
              {data.last_run ? (
                <div className="mt-2 text-sm text-text-secondary">
                  <p>
                    {SUPPLIER.imports.runStates[data.last_run.state] ?? data.last_run.state} ·{" "}
                    {SUPPLIER.imports.sources[data.last_run.source] ?? data.last_run.source} ·{" "}
                    {formatDate(data.last_run.finished_at ?? data.last_run.created_at)}
                  </p>
                  <p className="mt-1 tabular-nums">{countsLine(SUPPLIER.imports.summary, data.last_run)}</p>
                </div>
              ) : (
                <p className="mt-2 text-sm text-text-muted">{O.noImport}</p>
              )}
            </Panel>
            <Panel>
              <h2 className="font-semibold">{O.feed}</h2>
              {data.feed_source ? (
                <div className="mt-2 text-sm text-text-secondary">
                  <p className="break-all font-mono text-xs">{data.feed_source.url}</p>
                  <p className="mt-1">
                    {SUPPLIER.imports.nextPull}: {formatDate(data.feed_source.next_pull_at)}
                    {data.feed_source.last_status &&
                      ` · ${SUPPLIER.imports.feedStatuses[data.feed_source.last_status] ?? data.feed_source.last_status}`}
                  </p>
                </div>
              ) : (
                <p className="mt-2 text-sm text-text-muted">{O.noFeed}</p>
              )}
            </Panel>
          </div>
        </div>
      )}
    </>
  );
}
