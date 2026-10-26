// PF2f: the tier a /dashboard/billing/ link asks for. The pricing page links
// with ?tier=<id>; the app's "See plans" opens ?plan=<plan>, written from an
// FName, which a packaged build of the app does not keep in its case (`team`
// comes out as `Team`). So the value is read without ASCII case, as the API
// reads the app's enum values (PF14f, server/app/enums.py canonical): only an
// all-ASCII value is lower-cased (toLowerCase would also fold letters such as
// the Kelvin sign into ASCII), anything else is kept as given and names no tier.

function isAscii(value: string): boolean {
  for (let i = 0; i < value.length; i++) if (value.charCodeAt(i) > 127) return false;
  return true;
}

/** The tier id a billing link preselects: ?tier= first, then ?plan= (an
 *  empty value included, as before), else Team for an organisation and Pro
 *  for a person. The page shows its first buyable tier for an id it does not
 *  sell (a misspelling, free, enterprise). */
export function linkedTierId(params: Pick<URLSearchParams, "get">, org: boolean): string {
  const value = params.get("tier") ?? params.get("plan");
  if (value === null) return org ? "team" : "pro";
  return isAscii(value) ? value.toLowerCase() : value;
}
