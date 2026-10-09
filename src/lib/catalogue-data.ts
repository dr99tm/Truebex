// Server-only: the plan catalogue at build time. Never import this from a
// client component (it reads the file system for the sample override).
import fs from "node:fs";
import path from "node:path";
import defaultCatalogue from "../../server/app/catalogue.json";
import type { Catalogue } from "@/lib/catalogue";

/**
 * server/app/catalogue.json, or the file named by TRUEBEX_CATALOGUE_FILE
 * (relative to the repo root) for a local build that tries the pricing page
 * with sample prices, e.g. scripts/fixtures/catalogue-sample.json. Releases
 * are built without it.
 */
export function loadCatalogue(): Catalogue {
  const override = process.env.TRUEBEX_CATALOGUE_FILE;
  if (override) {
    const file = path.resolve(process.cwd(), override);
    return JSON.parse(fs.readFileSync(file, "utf8")) as Catalogue;
  }
  return defaultCatalogue as unknown as Catalogue;
}
