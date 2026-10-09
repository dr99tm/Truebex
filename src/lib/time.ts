import { formatDate, parseServerDate } from "@/lib/api";

const DAY_MS = 86_400_000;

/** Whole days from now until `iso`, rounded up (0 once it has passed). */
export function daysUntil(iso: string): number {
  return Math.max(0, Math.ceil((parseServerDate(iso).getTime() - Date.now()) / DAY_MS));
}

/** "just now", "5 min ago", "3 h ago", then the date. */
export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "—";
  const seconds = (Date.now() - parseServerDate(iso).getTime()) / 1000;
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
  if (seconds < DAY_MS / 1000) return `${Math.floor(seconds / 3600)} h ago`;
  return formatDate(iso);
}
