// Renders the pricing components to static HTML outside Next.js, so the
// build checks can try other catalogues (TRUEBEX_CATALOGUE_FILE, read by
// src/lib/catalogue-data.ts loadCatalogue) and every interval and currency
// without another `next build`. Used by server/tests/test_site_pf13.py.
//
//   node server/tests/site_render.cjs   ->  JSON on stdout:
//   { catalogue,                       what loadCatalogue() gives the pages
//     cards,                           /pricing/'s TierCards (+ founding banner), as built
//     prices: {"<tier>/<interval>/<currency>": html},    each PriceBlock
//     offers, faq }                    the JSON-LD offers and the pricing FAQ
//
// TypeScript is compiled on require with the project's own `typescript`, and
// "@/..." resolves to src/ as in tsconfig.json. CommonJS on purpose: the
// require hook is what compiles the site's modules (and lets them import
// catalogue.json), so require() is the point here.
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

const React = require(path.join(ROOT, "node_modules", "react"));
const { renderToStaticMarkup } = require(path.join(ROOT, "node_modules", "react-dom", "server"));
const { CURRENCIES, INTERVALS, annualSavingPercent, foundingLive, offersLd } = require("@/lib/catalogue");
const { loadCatalogue } = require("@/lib/catalogue-data");
const { PRICING } = require("@/lib/constants");
const { pricingFaq } = require("@/lib/pricing");
const { PriceBlock, TierCards } = require("@/components/pricing/TierCards");

const catalogue = loadCatalogue();
const cards = renderToStaticMarkup(
  React.createElement(TierCards, {
    tiers: catalogue.tiers,
    copy: PRICING.tiers,
    labels: PRICING.labels,
    saving: annualSavingPercent(catalogue),
    showControls: true,
    founding:
      foundingLive(catalogue) && catalogue.founding ? { offer: catalogue.founding, copy: PRICING.founding } : null,
  })
);
const prices = {};
for (const tier of catalogue.tiers) {
  for (const interval of INTERVALS) {
    for (const currency of CURRENCIES) {
      prices[`${tier.id}/${interval}/${currency}`] = renderToStaticMarkup(
        React.createElement(PriceBlock, { tier, interval, currency, labels: PRICING.labels })
      );
    }
  }
}
const offers = offersLd(catalogue, "https://truebex.com/pricing/");
const faq = pricingFaq(catalogue);
process.stdout.write(JSON.stringify({ catalogue, cards, prices, offers, faq }));
