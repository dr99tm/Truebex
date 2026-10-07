"use client";

import { useMemo, useRef, useState } from "react";

// Daily API requests this month: one series, magnitude over time -> columns.
// Single series, so no legend box; the panel title names it. Bars use the
// validated chart token (--color-chart), 4 px rounded tops anchored to the
// baseline, 2 px gaps, a per-bar tooltip on hover AND keyboard focus, and a
// table view so no value is hover-only.

interface Point {
  day: string; // YYYY-MM-DD
  count: number;
}

const H = 180;
const PAD_TOP = 12;
const PAD_BOTTOM = 22;

function niceMax(v: number): number {
  if (v <= 4) return 4;
  const pow = 10 ** Math.floor(Math.log10(v));
  const step = [1, 2, 2.5, 5, 10].find((s) => s * pow * 4 >= v) ?? 10;
  return step * pow * 4;
}

const nf = new Intl.NumberFormat("en-US");

function label(day: string): string {
  return new Date(`${day}T00:00:00Z`).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

export function UsageChart({ data }: { data: Point[] }) {
  const [active, setActive] = useState<number | null>(null);
  const [showTable, setShowTable] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);

  const max = useMemo(() => niceMax(Math.max(0, ...data.map((d) => d.count))), [data]);
  const n = Math.max(data.length, 1);
  const plotH = H - PAD_TOP - PAD_BOTTOM;
  const ticks = [0, max / 2, max];

  const total = data.reduce((s, d) => s + d.count, 0);

  return (
    <div>
      <div ref={wrap} className="relative">
        <svg
          viewBox={`0 0 ${n * 10} ${H}`}
          preserveAspectRatio="none"
          className="h-[180px] w-full overflow-visible"
          role="img"
          aria-label={`Daily API requests this month: ${nf.format(total)} in total over ${data.length} days.`}
        >
          {/* recessive grid */}
          {ticks.map((t) => {
            const y = PAD_TOP + plotH - (t / max) * plotH;
            return (
              <line
                key={t}
                x1={0}
                x2={n * 10}
                y1={y}
                y2={y}
                stroke="currentColor"
                className="text-border"
                strokeWidth={1}
                vectorEffect="non-scaling-stroke"
              />
            );
          })}
          {data.map((d, i) => {
            const h = (d.count / max) * plotH;
            const x = i * 10 + 1; // 2-unit gap between bars
            const y = PAD_TOP + plotH - h;
            return (
              <g key={d.day}>
                {d.count > 0 && (
                  <rect
                    x={x}
                    y={y}
                    width={8}
                    height={h}
                    rx={Math.min(1.2, h / 2)}
                    className={active === i ? "fill-chart-hover" : "fill-chart"}
                  />
                )}
                {/* hit target: the whole column, bigger than the mark */}
                <rect
                  x={i * 10}
                  y={0}
                  width={10}
                  height={H}
                  fill="transparent"
                  tabIndex={0}
                  role="button"
                  aria-label={`${label(d.day)}: ${nf.format(d.count)} requests`}
                  onPointerEnter={() => setActive(i)}
                  onPointerLeave={() => setActive(null)}
                  onFocus={() => setActive(i)}
                  onBlur={() => setActive(null)}
                  className="cursor-default outline-none"
                />
              </g>
            );
          })}
        </svg>

        {/* y-axis values (HTML so text isn't stretched by the viewBox) */}
        <div className="pointer-events-none absolute inset-y-0 left-0 text-[10px] text-text-muted tabular-nums">
          {ticks.map((t) => (
            <span
              key={t}
              className="absolute -translate-y-1/2 bg-surface pr-1"
              style={{ top: `${((PAD_TOP + plotH - (t / max) * plotH) / H) * 100}%` }}
            >
              {nf.format(t)}
            </span>
          ))}
        </div>
        <div className="pointer-events-none absolute bottom-0 left-0 right-0 flex justify-between text-[10px] text-text-muted">
          <span>{data[0] ? label(data[0].day) : ""}</span>
          <span>{data.length > 1 ? label(data[data.length - 1].day) : ""}</span>
        </div>

        {active !== null && data[active] && (
          <div
            className="pointer-events-none absolute top-0 z-10 -translate-x-1/2 -translate-y-full rounded-md border border-border bg-surface-elevated px-3 py-2 text-xs shadow-lg"
            style={{ left: `${((active + 0.5) / n) * 100}%` }}
            role="status"
          >
            <p className="font-semibold tabular-nums text-text-primary">
              {nf.format(data[active].count)} requests
            </p>
            <p className="text-text-muted">{label(data[active].day)}</p>
          </div>
        )}
      </div>

      <button
        type="button"
        onClick={() => setShowTable((v) => !v)}
        className="mt-4 text-xs text-accent hover:underline"
        aria-expanded={showTable}
      >
        {showTable ? "Hide table" : "View as table"}
      </button>
      {showTable && (
        <div className="mt-3 max-h-64 overflow-auto rounded-md border border-border">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-surface-elevated text-left text-text-muted">
              <tr>
                <th className="px-3 py-2 font-medium">Day</th>
                <th className="px-3 py-2 text-right font-medium">Requests</th>
              </tr>
            </thead>
            <tbody>
              {data.map((d) => (
                <tr key={d.day} className="border-t border-border">
                  <td className="px-3 py-1.5 text-text-secondary">{label(d.day)}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-text-primary">
                    {nf.format(d.count)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
