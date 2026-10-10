// Shared classes for the organisation console's forms and tables.
export const inputClass =
  "min-w-0 rounded-[var(--radius-button)] border border-border bg-background px-3 py-2 text-sm text-text-primary placeholder:text-text-muted outline-none focus:border-accent/50";
export const tableClass = "w-full text-sm";
export const thClass = "py-2 pr-4 font-medium";
export const tdClass = "py-3 pr-4 text-text-secondary";
export const linkButton = "text-accent hover:underline disabled:opacity-50";
export const dangerButton = "text-text-muted hover:text-red-400 disabled:opacity-50";

export function errorText(err: unknown, fallback = "Something went wrong."): string {
  return err instanceof Error ? err.message : fallback;
}
