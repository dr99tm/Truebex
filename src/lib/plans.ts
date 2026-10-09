// Plan names and limits for any component, client or server: imported at
// build time straight from the server's own catalogue
// (server/app/catalogue.json), so a plan is never named twice.
import catalogue from "../../server/app/catalogue.json";

export interface PlanTier {
  id: string;
  name: string;
  rank: number;
  purchasable: boolean;
  features: string[];
  limits: Record<string, number | null>;
  api: { monthly_requests: number; max_api_keys: number };
}

const TIERS: PlanTier[] = [...(catalogue.tiers as unknown as PlanTier[])].sort((a, b) => a.rank - b.rank);

export function tier(id: string | null | undefined): PlanTier {
  return TIERS.find((t) => t.id === id) ?? TIERS[0];
}

/** The display name of a plan id: Free, Pro, Studio, Team, Enterprise. */
export function planName(id: string | null | undefined): string {
  return tier(id).name;
}
