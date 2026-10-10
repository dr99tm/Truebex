import { cn } from "@/lib/utils";

/** Requests (or another unit) used vs the plan's monthly allowance. Amber past 80 %. */
export function UsageMeter({
  used,
  limit,
  unit = "requests",
  label = "API requests used this month",
  digits = 0,
}: {
  used: number;
  limit: number;
  /** The counted thing, plural ("requests", "cost units"). */
  unit?: string;
  label?: string;
  /** Decimals shown (cost units have one). */
  digits?: number;
}) {
  const pct = limit > 0 ? Math.min(used / limit, 1) : 0;
  const nf = new Intl.NumberFormat("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-3xl font-semibold tabular-nums text-text-primary">
          {nf.format(used)}
        </p>
        <p className="text-sm text-text-muted tabular-nums">
          of {nf.format(limit)} {unit}
        </p>
      </div>
      <div
        className="mt-3 h-2 overflow-hidden rounded-full bg-surface-elevated"
        role="meter"
        aria-valuemin={0}
        aria-valuemax={limit}
        aria-valuenow={used}
        aria-label={label}
      >
        <div
          className={cn("h-full rounded-full", pct >= 0.8 ? "bg-warn" : "bg-chart")}
          style={{ width: `${Math.max(pct * 100, used > 0 ? 1 : 0)}%` }}
        />
      </div>
      <p className="mt-2 text-xs text-text-muted">
        {Math.round(pct * 100)}% used · {nf.format(Math.max(limit - used, 0))} left this month
      </p>
    </div>
  );
}
