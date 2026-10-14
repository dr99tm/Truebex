// The share page's project card and download names (PF5b, share-bundle 1.1).
// Pure functions, no DOM: server/app/shares/page.py writes the same card for
// the page's <noscript>, and tests/test_shares_pf5b.py runs both on the same
// inputs under Node.

export interface ProjectFacts {
  units?: string;
  storeys?: unknown;
  rooms?: unknown;
  floor_area_m2?: unknown;
}

export interface ProjectCardLabels {
  storey: string;
  storeys: string;
  room: string;
  rooms: string;
  squareMetres: string;
  squareFeet: string;
}

const SQ_FT_PER_M2 = 10.763910416709722;

/** A positive whole number from the manifest, else null (never shown). */
function count(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) && value >= 1 && Number.isInteger(value) ? value : null;
}

/** At most `places` decimals, half away from zero, with thousands separators. */
function decimals(value: number, places: number): string {
  return new Intl.NumberFormat("en-GB", { maximumFractionDigits: places }).format(value);
}

/**
 * "1 storey · 3 rooms · 72.75 m²": the facts the manifest gives, the area in
 * its units (whole ft² when `imperial`). Null when it gives none (a 1.0
 * manifest), so the page shows no card.
 */
export function projectLine(project: ProjectFacts | null | undefined, labels: ProjectCardLabels): string | null {
  if (!project) return null;
  const parts: string[] = [];
  const storeys = count(project.storeys);
  const rooms = count(project.rooms);
  if (storeys) parts.push(`${decimals(storeys, 0)} ${storeys === 1 ? labels.storey : labels.storeys}`);
  if (rooms) parts.push(`${decimals(rooms, 0)} ${rooms === 1 ? labels.room : labels.rooms}`);
  const area = project.floor_area_m2;
  if (typeof area === "number" && Number.isFinite(area) && area > 0) {
    parts.push(
      project.units === "imperial"
        ? `${decimals(area * SQ_FT_PER_M2, 0)} ${labels.squareFeet}`
        : `${decimals(area, 2)} ${labels.squareMetres}`,
    );
  }
  return parts.length ? parts.join(" · ") : null;
}

/** A file's download name: the last segment of its manifest name (names may hold folders). */
export function downloadName(name: string | null | undefined): string {
  const last = (name ?? "").split("/").filter(Boolean).pop() ?? "";
  const clean = last.replace(/["\\\u0000-\u001f\u007f]/g, "_").trim();
  return clean || "file";
}
