// The organisation console's Member usage columns (PF3b): cloud storage,
// panoramas and AI credits as the table shows them. No imports, so the build
// checks can run these on their own (server/tests/test_site_pf3b.py).

const MIB = 1024 * 1024;
const whole = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 0 });
const tenths = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 1 });

/** 268 435 456 → "256 MB", 1.5 GiB → "1.5 GB", 0 → "0 MB": 1 024-based as on the
 * Projects page, MB below 1 GB, one decimal under 10, thousands separators;
 * null (an earlier month) → "—". */
export function formatStorage(bytes: number | null | undefined): string {
  if (bytes == null) return "—";
  const mb = bytes / MIB;
  if (mb > 0 && mb < 0.05) return "< 0.1 MB";
  const [value, unit] = mb < 1023.5 ? [mb, "MB"] : [mb / 1024, "GB"];
  return `${(value < 10 ? tenths : whole).format(value)} ${unit}`;
}

/** 1250 → "1,250"; null → "—". Panoramas and AI credits. */
export function formatCount(value: number | null | undefined): string {
  return value == null ? "—" : whole.format(value);
}
