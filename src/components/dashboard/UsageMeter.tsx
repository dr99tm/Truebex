import { cn } from "@/lib/utils";

/** Requests used vs the plan's monthly allowance. Amber past 80 %. */
export function UsageMeter({ used, limit }: { used: number; limit: number }) {
  const pct = limit > 0 ? Math.min(used / limit, 1) : 0;
  const nf = new Intl.NumberFormat("en-US");
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-3xl font-semibold tabular-nums text-text-primary">
          {nf.format(used)}
        </p>
        <p className="text-sm text-text-muted tabular-nums">
          of {nf.format(limit)} requests
        </p>
      </div>
      <div
        className="mt-3 h-2 overflow-hidden rounded-full bg-surface-elevated"
        role="meter"
        aria-valuemin={0}
        aria-valuemax={limit}
        aria-valuenow={used}
        aria-label="API requests used this month"
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
