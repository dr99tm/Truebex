// PF7e: renders the dashboard's orders list (src/components/market/OrderList.tsx)
// to static HTML outside Next.js, the way /dashboard/orders/ shows it for a
// link (?order=<id>, an order's `web_url`), so the build checks can try a link
// to a listed order, to one past the first page (fetched with 5.9), to an
// unknown or another account's order and to a malformed id without a browser.
// Used by server/tests/test_site_pf7.py.
//
//   node server/tests/orders_render.cjs <cases.json>   ->  JSON on stdout:
//   cases.json: [{ "orders": [5.8's orders], "link": "<?order= value>" | null,
//                  "fetched": <5.9's order> | null (404 / 403) | absent (not asked) }]
//   out:        [{ "fetch": <id the page asks 5.9 for> | null,
//                  "ids": [order ids as shown], "focused": <id> | null, "note": bool,
//                  "html": <the rendered list> }]
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

const React = require(path.join(ROOT, "node_modules", "react"));
const { renderToStaticMarkup } = require(path.join(ROOT, "node_modules", "react-dom", "server"));
const { linkedOrderToFetch, orderLinkView } = require("@/lib/order-link");
const { OrderList } = require("@/components/market/OrderList");

const cases = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const out = cases.map((c) => {
  const view = orderLinkView(c.orders, c.link, c.fetched);
  const html = renderToStaticMarkup(
    React.createElement(OrderList, { view, busy: null, onAct: () => {} })
  );
  return {
    fetch: linkedOrderToFetch(c.orders, c.link),
    ids: view.orders.map((o) => o.order_id),
    focused: view.focused,
    note: view.note,
    html,
  };
});
process.stdout.write(JSON.stringify(out));
