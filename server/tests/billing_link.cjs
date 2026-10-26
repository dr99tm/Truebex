// PF2f: what /dashboard/billing/ preselects for a link, outside Next.js. The
// tier id is src/lib/billing-link.ts linkedTierId (the page's tierId state);
// the rest is what src/app/dashboard/billing/page.tsx makes of it with the
// API's own catalogue (STATIC_CATALOG, read from server/app/catalogue.json):
// the buyable tier it shows (buyable.find(...) ?? buyable[0]), the interval
// it is sold at, the seats and the unit price. `before` is the same for
// master's reading (params.get("tier") ?? params.get("plan") ?? the default),
// so a test can say a link behaves as it did. Used by
// server/tests/test_pf2f_billing_link_case.py.
//
//   node server/tests/billing_link.cjs <cases.json>   ->  JSON on stdout:
//   cases.json: [{ "query": "<a=b&c=d, as the browser's location.search>", "org": bool }]
//   out:        [{ "id": <tierId>, "tier": <the tier shown>, "interval", "seats",
//                  "unit": <amount_minor> | null, "before": { the same keys } }]
//
// TypeScript is compiled on require with the project's own `typescript`, and
// "@/..." resolves to src/ as in tsconfig.json (as site_render.cjs does).
/* eslint-disable @typescript-eslint/no-require-imports */
"use strict";

const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");

const ROOT = path.resolve(__dirname, "..", "..");
const ts = require(path.join(ROOT, "node_modules", "typescript"));

const resolve = Module._resolveFilename;
Module._resolveFilename = function (request, parent, ...rest) {
  if (request.startsWith("@/")) request = path.join(ROOT, "src", request.slice(2));
  return resolve.call(this, request, parent, ...rest);
};
for (const ext of [".ts", ".tsx"]) {
  Module._extensions[ext] = (module, filename) => {
    const out = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
      fileName: filename,
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2022,
        jsx: ts.JsxEmit.ReactJSX,
        esModuleInterop: true,
        resolveJsonModule: true,
      },
    });
    module._compile(out.outputText, filename);
  };
}

const { linkedTierId } = require("@/lib/billing-link");
const { STATIC_CATALOG } = require("@/lib/billing-catalog");
const { intervalFor } = require("@/lib/catalogue");

// page.tsx's lines after tierId: the interval, currency and seats states and
// the selected tier, interval and unit price (no founding offer before
// /billing/plans answers; a browser without a Eurozone or US locale pays GBP).
function shown(tierId, params) {
  const cat = STATIC_CATALOG;
  const interval = params.get("interval") === "year" ? "year" : "month";
  const currency = params.get("currency")?.toUpperCase() ?? "GBP";
  const seatChoice = Math.min(1000, Math.max(0, Math.floor(Number(params.get("seats")) || 0)));
  const currencies = cat.currencies.length ? cat.currencies : ["GBP", "USD", "EUR"];
  const activeCurrency = currencies.includes(currency) ? currency : currencies[0];
  const buyable = cat.tiers.filter((t) => t.purchasable);
  const tier = buyable.find((t) => t.id === tierId) ?? buyable[0];
  const seats = tier.per_seat ? Math.max(seatChoice || tier.min_seats, tier.min_seats) : 1;
  const sold = intervalFor(tier, interval, activeCurrency);
  const price = tier.prices.find((p) => p.interval === sold && p.currency === activeCurrency);
  return { id: tierId, tier: tier.id, interval: sold, seats, unit: price ? price.amount_minor : null };
}

const cases = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const out = cases.map((c) => {
  const params = new URLSearchParams(c.query);
  const before = params.get("tier") ?? params.get("plan") ?? (c.org ? "team" : "pro");
  return { ...shown(linkedTierId(params, c.org), params), before: shown(before, params) };
});
process.stdout.write(JSON.stringify(out));
