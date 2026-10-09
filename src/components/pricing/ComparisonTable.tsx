import { Check, Minus } from "lucide-react";
import type { Tier } from "@/lib/catalogue";
import { PRICING } from "@/lib/constants";

type Row = (typeof PRICING.comparison)[number]["rows"][number];

const nf = new Intl.NumberFormat("en-US");
const L = PRICING.labels;

function Yes() {
  return (
    <>
      <Check className="mx-auto h-4 w-4 text-accent" aria-hidden />
      <span className="sr-only">{L.included}</span>
    </>
  );
}

function No() {
  return (
    <>
      <Minus className="mx-auto h-4 w-4 text-text-muted" aria-hidden />
      <span className="sr-only">{L.notIncluded}</span>
    </>
  );
}

function Cell({ tier, row }: { tier: Tier; row: Row }) {
  if (row.kind === "feature") return tier.features.includes(row.key) ? <Yes /> : <No />;
  if (row.kind === "api") return <>{nf.format(tier.api.monthly_requests)}</>;
  const value = tier.limits[row.key];
  if (value === null) return <>{L.unlimited}</>;
  if (value === undefined || value === 0) return <No />;
  return <>{nf.format(value)}</>;
}

/** The entitlement matrix, one row per key, grouped. Rows for work that has
 *  not shipped say "On the roadmap" (brand rule: never present tense). */
export function ComparisonTable({ tiers }: { tiers: Tier[] }) {
  return (
    <div className="overflow-x-auto rounded-[var(--radius-card)] border border-border">
      <table data-comparison="" className="w-full min-w-[720px] border-collapse text-sm">
        <thead>
          <tr className="bg-surface-elevated">
            <th scope="col" className="sticky start-0 bg-surface-elevated px-4 py-3 text-start font-semibold">
              <span className="sr-only">Feature</span>
            </th>
            {tiers.map((t) => (
              <th key={t.id} scope="col" className="px-3 py-3 text-center font-semibold text-text-primary">
                {t.name}
              </th>
            ))}
          </tr>
        </thead>
        {PRICING.comparison.map((group) => (
          <tbody key={group.title}>
            <tr>
              <th
                colSpan={tiers.length + 1}
                scope="colgroup"
                className="border-t border-border bg-surface px-4 pb-2 pt-5 text-start text-xs font-semibold uppercase tracking-wider text-text-muted"
              >
                {group.title}
              </th>
            </tr>
            {group.rows.map((row) => {
              const roadmap = "roadmap" in row && row.roadmap === true;
              return (
                <tr key={row.key} data-feature={row.key} data-roadmap={roadmap ? "true" : "false"} className="border-t border-border">
                  <th scope="row" className="sticky start-0 bg-background px-4 py-3 text-start font-normal text-text-secondary">
                    {row.label}
                    {roadmap && (
                      <span className="ms-2 inline-block whitespace-nowrap rounded-full border border-warn/40 px-2 py-0.5 text-[11px] font-medium text-warn">
                        {L.onTheRoadmap}
                      </span>
                    )}
                  </th>
                  {tiers.map((t) => (
                    <td key={t.id} className="px-3 py-3 text-center tabular-nums text-text-primary">
                      <Cell tier={t} row={row} />
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        ))}
      </table>
    </div>
  );
}
