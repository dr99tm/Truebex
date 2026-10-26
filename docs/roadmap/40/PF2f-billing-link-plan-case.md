# PF2f — The billing page reads a link's `?plan=` and `?tier=` without case (launch priority 2)

**Needs merged:** PF2 (the billing page and its `?tier=` links), PF14f (the audit that found this, and `server/app/enums.py` `canonical` as the rule to follow); both on `master` 4859428. **Unblocks:** the app's "See plans" from a packaged build preselects the plan it names; PF14f's carry-over "The site (whoever next touches the billing page)". **Contract:** none. This is a web page, not a contract route, so no contract file moves. PF14f's PATCH line D (the app writes its upgrade link from a literal) stays with the app half.

## Status

**Built (2026-10-26, branch `ap/t100-pf2f-the-billing-page-reads-a-li`, Autopilot T100); see As-built.** Checked on `master` 4859428 before the work began:

| # | Where (master 4859428) | Before |
|---|---|---|
| 1 | `src/app/dashboard/billing/page.tsx:380-382` | `tierId` = `params.get("tier") ?? params.get("plan") ?? (org ? "team" : "pro")`, the value taken exactly |
| 2 | `page.tsx:438` | `buyable.find((t) => t.id === tierId) ?? buyable[0]`: `Team` matches no id, so the page shows Pro (the first buyable tier) |
| 3 | An empty value | `?plan=` gives `""`, which `??` keeps, so the page shows Pro, even for an organisation (whose default is Team); `?tier=&plan=Team` shows Pro too |
| 4 | The app (`main` a913df53a, read-only; `CadEntitlement.cpp` unchanged since bc06615c6) | `Plugins/CADTOOL/Source/CadCore/Private/CadEntitlement.cpp:829-832` `UpgradeUrl(FName Plan)` writes `https://truebex.com/dashboard/billing/?plan=%s` from `Plan.ToString()` (declared at `CadCore/Public/CadEntitlement.h:270-271`). It is opened by "See plans" (`TruebexLicence/Private/LicenceUpgradeUi.cpp:194`) and logged by `CadBuiltinCommands_LC3.cpp:41`. In a Shipping or Game build `team` comes out as `Team` (`Engine/Source/Runtime/Core/Public/UObject/UnrealNames.inl:190`). The app's own checks run on editor binaries and see `?plan=pro` only (`CadSelfTest_LC3.cpp:673`, FastEye's `FastEyeTest_LC3.cpp:197`). |

## Goal

Someone using a packaged build of the app hits a Team feature and clicks "See plans". Their browser opens truebex.com's billing page with Team already chosen: the annual price, the minimum of 2 seats and the total, exactly as the lower-case link shows it. This holds when they are not signed in to the site yet: the sign-in page keeps the link and brings them back to it. Today such a link shows Pro. Every link that already worked keeps working unchanged.

## Read first

* `docs/roadmap/40/00-contract.md` (P.2-P.4); `PF14f-fname-case.md` (Goal, the audit's "Outside the API", Carry-over "The site"); `PF2-billing-through-the-uk-company.md`.
* `src/app/dashboard/billing/page.tsx` (`BillingManager`), `src/lib/billing-catalog.ts` (`STATIC_CATALOG`), `server/app/catalogue.json`, `src/components/pricing/TierCards.tsx:320` (the pricing page's `?tier=` links), `src/components/dashboard/DashboardShell.tsx:105-106` and `src/components/auth/AuthForm.tsx:22` (sign-in keeps the link).
* `server/app/enums.py` (`canonical`: ASCII only); `server/tests/orders_render.cjs` (how a test runs the site's TypeScript in Node).

## Scope

**In:**

1. `src/lib/billing-link.ts` `linkedTierId(params, org)`: the tier id a billing link asks for. It reads `?tier=` first, then `?plan=`. A value that is all ASCII is lower-cased; any other value is passed through untouched, so it matches no tier, as today. With neither parameter it answers the default (`team` for an organisation, `pro` for a person). An empty value is kept, as today.
2. `page.tsx`'s `tierId` initial state calls the helper (one import, the `tierId` lines). Nothing else on the page moves. Team's rules (annual only, its minimum seats) apply to the preselected tier as they do for a lower-case link.
3. No other parameter changes: `?interval=` stays exact, `?currency=` keeps its `toUpperCase`, and `?code=`, `?seats=`, `?org=` and `?checkout=` are untouched. The As-built records the grep of the app's links (its `UpgradeUrl` is the only producer of a mixed-case value).

**Out (and where it goes):**

* The app's own fix (`UpgradeUrl` writing a lower-case literal): the app half, PF14f's PATCH line D (repeated in As-built).
* A link naming a tier that is not for sale (free, enterprise): unchanged, so the page shows the first buyable tier. Whether enterprise should open the contact form instead is the owner's call (As-built, Carry-over).
* Deploying the site: the owner, at the next release.
* Website copy: none changes.

## Design

**API, data, jobs:** none.

**UI.** One helper and one call:

```ts
export function linkedTierId(params: Pick<URLSearchParams, "get">, org: boolean): string {
  const value = params.get("tier") ?? params.get("plan");
  if (value === null) return org ? "team" : "pro";
  return isAscii(value) ? value.toLowerCase() : value;
}
// page.tsx
const [tierId, setTierId] = useState<string>(linkedTierId(params, org !== null));
```

| Link | `tierId` | The page shows (en-GB browser) |
|---|---|---|
| `?plan=Team`, `TEAM`, `tEaM`, `team` | `team` | Team: £99.17 / month, billed annually (£1,190.00 / year), 2 seats, total £2,380.00 / year |
| `?plan=Pro`, `pro`; no parameter (a person) | `pro` | Pro: £24.00 / month, 1 seat |
| no parameter (an organisation) | `team` | Team, as above |
| `?tier=Studio` | `studio` | Studio: £79.00 / month |
| `?tier=team&plan=Pro` | `team` | Team (`?tier=` wins) |
| `?tier=TEAM&interval=year&currency=usd&seats=5` | `team` | Team: US$1,788.00 / year a seat, 5 seats, total US$8,940.00 / year |
| `?plan=Teams`, `enterprise`, `Free`, `?plan=` (empty), `?tier=&plan=Team` | `teams`, `enterprise`, `free`, `""`, `""` | Pro (the first buyable tier), as before |
| a value with a non-ASCII letter (for example `TEAM` + U+212A, the Kelvin sign) | the value as given | Pro, as before |

The ASCII rule is PF14f's: JavaScript's `toLowerCase` also folds some non-ASCII letters (the Kelvin sign becomes `k`), so only an all-ASCII value is lower-cased. The catalogue's ids are lower-case ASCII (`free`, `pro`, `studio`, `team`, `enterprise`), so the lower-cased value is the id.

**Security and privacy:** no new input. The value only picks one of the catalogue's tiers; checkout still sends the tier's own id and the API checks it.

## Deliverables

- [x] `src/lib/billing-link.ts` (`linkedTierId`)
- [x] `src/app/dashboard/billing/page.tsx`: one import, the `tierId` state
- [x] `server/tests/billing_link.cjs` and `server/tests/test_pf2f_billing_link_case.py`
- [x] This doc, the tracker row, README's section, PF14f's carry-over line

## Tests

| Name | Kind | Asserts |
|---|---|---|
| `test_pf2f_plan_in_any_case_preselects_its_tier` | pytest (Node) | `?plan=Team`, `TEAM`, `tEaM` give `team` and the same tier, interval, seats and unit price as `?plan=team` (Team, year, 2, 119000); `?plan=Pro` as `?plan=pro`; master's reading showed Pro for each |
| `test_pf2f_tier_in_any_case_and_tier_before_plan` | pytest (Node) | `?tier=Studio` gives `studio`; `?tier=team&plan=Pro` and `?tier=Team&plan=pro` give Team; `?tier=TEAM&interval=month&currency=usd&seats=5` gives what the lower-case link gives (Team, annual, 5 seats); `?tier=Studio&interval=year&currency=EUR` too |
| `test_pf2f_lower_case_links_unchanged` | pytest (Node) | the pricing page's 18 links (every buyable tier × interval × currency), `?plan=pro` and no parameter (person and organisation) answer exactly what master answered; the catalogue's ids are lower-case ASCII |
| `test_pf2f_not_a_buyable_tier_as_before` | pytest (Node) | `Teams`, `enterprise`, `Enterprise`, `free`, `Free`, an empty `?plan=` (person and organisation), `?tier=&plan=Team` and `?tier=+team` (a leading space) show Pro, as master did; the empty value stays `""` |
| `test_pf2f_non_ascii_value_passed_through` | pytest (Node) | `TEAM` + Kelvin sign, `T` + Greek capital epsilon + `AM` and `Stud` + Kelvin + `io` (built with `chr()`) come back unchanged and show Pro |
| `test_pf2f_page_reads_the_tier_through_the_helper` | source check | `page.tsx` has no `params.get("plan")` / `params.get("tier")`, imports `linkedTierId` and calls it in the `tierId` state; the interval, currency, seats, code and checkout reads and the `buyable.find` line are unchanged |

`server/tests/billing_link.cjs` compiles `src/` with the project's own `typescript` (`@/` resolved, `catalogue.json` required), as `orders_render.cjs` does. For each link it answers `linkedTierId`'s id and what the page makes of it (the tier shown, the interval it is sold at, the seats, the unit price, with `page.tsx`'s own lines after `tierId`), beside the same for master's exact reading (`before`).

## Human test

**About 3 minutes, no provider keys.** Use Windows PowerShell in the worktree. The verify gate leaves an `out/` that talks to the production API, so the site is rebuilt against a local one first.

1. **The local API.** PowerShell window 1, in the worktree's `server\` folder; leave it running:
   ```
   $env:DATABASE_URL="sqlite:///./pf2f-test.db"; $env:SECRET_KEY="pf2f-local-test-0123456789abcdef0123456789"; $env:CORS_ORIGINS="http://127.0.0.1:3200,http://127.0.0.1:3100"
   .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```
   It prints `Uvicorn running on http://127.0.0.1:8000`.
2. **The site against it.** PowerShell window 2, in the worktree:
   ```
   Remove-Item -Recurse -Force out
   $env:NEXT_PUBLIC_AUTH_URL="http://127.0.0.1:8000"; powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1
   ```
   It builds (about a minute), then prints `serving …\out on http://127.0.0.1:<port>/`: port 3200 from Autopilot's Try it, 3100 otherwise. Use that port below.
3. Open `http://127.0.0.1:<port>/signup/` and create an account (any `@example.com` address, a password of 8 characters or more). You land on the dashboard.
4. Open `http://127.0.0.1:<port>/dashboard/billing/?plan=Team`. Under "Choose a plan" the **Team** card has the accent outline and the check mark. It reads "£99.17 / month, billed annually", "£1,190.00 / year" and "per seat · Minimum 2". Seats shows 2, and "Total before tax: £2,380.00 / year" is followed by "Team is billed annually." (A browser with a US locale shows US$149.00, US$1,788.00 and US$3,576.00; a eurozone one shows EUR.)
5. Change the address to `?plan=team`: the same. Change it to `?plan=Teams`: **Pro** is selected (£24.00 / month), as before.
6. Sign out: click your initial at the top right, then **Log out**. Open `http://127.0.0.1:<port>/dashboard/billing/?plan=Team` again. The login page opens, its address ending `?next=%2Fdashboard%2Fbilling%2F%3Fplan%3DTeam`. Sign in with the same account: you come back to the billing page with **Team** selected, as in step 4.
7. Stop both windows with Ctrl+C. Delete `server\pf2f-test.db` if you like.
8. *(Optional, the owner's, after the next deploy.)* In the app's Shipping release, open a Team feature on a plan below Team and click "See plans". truebex.com's billing page opens with Team selected.

## Risks / traps

* **Static export:** the page reads its query on the client (`useSearchParams` inside `Suspense`), so the build cannot check the selection. The Node test runs the helper and the page's own selection rules, and the headless run checks the built page.
* **Headless Edge moves its own `navigator.language`** from en-GB to en-US part way through a run (its profile's languages settle), which moves the page's default currency from GBP to USD between two visits. The self-test pins the locale over CDP (`Network.setUserAgentOverride` `acceptLanguage`, `Emulation.setLocaleOverride`); it is not the page's doing.
* **Ports:** another program on this PC listened on 127.0.0.1:18100 (18000 + the task number); the self-test used 28100 and 23200.
* **A self-test `out/`** must not stay inside the worktree before the gate (ESLint lints a moved build): it was built, then moved to the session's scratchpad outside the worktree.

## As-built

* **Date, branch, commits:** 2026-10-26, `ap/t100-pf2f-the-billing-page-reads-a-li` (base `master` 4859428): `ebfb8f1` (the tests, all six failing on master), `f460f44` (the helper and the page), then the docs commit (this doc, the tracker row, README's section, PF14f's carry-over line).
* **Counts:** pytest 972 → 978 collected (6 new in `test_pf2f_billing_link_case.py`). On master 4859428 all six fail: the five Node tests with `Cannot find module …\src\lib\billing-link`, the source check on `params.get("plan")`. With a stand-in `billing-link.ts` holding master's exact reading, three fail on their assertions (`'Team' == 'team'` in the first two, and the source check) and three pass, the ones that pin what stays. With a naive `toLowerCase` stand-in, the non-ASCII test fails (`'teamk' == 'TEAM\u212a'`). No existing assertion moved. The suites the task names (`test_billing`, `test_billing_pf2`, `test_billing_pf2b`, `test_billing_orgs`, `test_pf2c_billing_tidy`, `test_pf2d_billing_followups`, `test_site_pf2`, `test_site_pf13`) plus this one: 103 passed, 25 skipped (site checks without `out/`) in 28 s. The verify gate runs them with `out/` built (last bullet).
* **The helper:** `src/lib/billing-link.ts` (22 lines), `linkedTierId(params, org)` with an `isAscii` loop over char codes (no regular-expression escapes). `page.tsx` changed in 4 lines: the import at `:19` and the `tierId` state at `:380-382` (its comment names PF2f). `linkedTierId(params, org !== null)` matches master's `org ? …`: `BillingManager`'s `org` is `OrgDetail | null` (`:1099`, `:1105`).
* **The empty value (checked):** on master `?plan=` selects Pro for a person and for an organisation, because `""` is not null and wins over the default; `?tier=&plan=Team` selects Pro too. The helper keeps both (`""` is all ASCII and lower-cases to itself).
* **Headless check** (Edge over CDP, Node 24, no npm package; scratchpad `selftest.sh` + `cdp_pf2f.mjs`): uvicorn on a scratch SQLite database (port 28100, `CORS_ORIGINS` = the served origin), `out/` built with `NEXT_PUBLIC_AUTH_URL=http://127.0.0.1:28100` and moved to the scratchpad, served by `scripts/serve-out.py` on 23200, `localStorage.truebex_token` from `POST /auth/register` (`pf2f-…@example.com`), the locale pinned to en-GB. GET `/billing/plans` answered provider null, founding off, Team year-only at GBP 119000 / USD 178800, minimum 2. **This branch: 33 of 33 checks**, no browser errors. What each showed (selected card | seats | total):
  * `?plan=Team`: `Team | £99.17 / month, billed annually | £1,190.00 / year | per seat · Minimum 2`, seats 2, `Total before tax: £2,380.00 / year | Team is billed annually.`
  * `?plan=team`, `?plan=TEAM`, `?plan=tEaM`: exactly the same as `?plan=Team`.
  * `?plan=Pro` and `?plan=pro`: `Pro | £24.00 / month | 1 seat`, no seats box, `Total before tax: £24.00 / month`.
  * `?plan=Teams`, `?plan=Enterprise`, no parameter: the same as `?plan=pro` (Pro).
  * `?tier=Studio`: `Studio | £79.00 / month | 1 seat`.
  * `?tier=TEAM&interval=year&currency=usd&seats=5` and `?tier=team&interval=year&currency=USD&seats=5`: `Team | US$1,788.00 / year | per seat · Minimum 2`, seats 5, `Total before tax: US$8,940.00 / year`, both the same.
  * `?tier=team&plan=Pro`: Team.
  * Signed out, `?plan=Team`: sent to `http://127.0.0.1:23200/login/?next=%2Fdashboard%2Fbilling%2F%3Fplan%3DTeam`. After signing in with the e-mail and password form: back on `/dashboard/billing/?plan=Team` with Team selected, the same card, seats and total as signed in.
  * **Master's build** (`page.tsx` from 4859428, the same driver and API): **24 of 33**. `?plan=Team`, `TEAM`, `tEaM` and `?tier=Studio` showed `Pro | £24.00 / month | 1 seat`; `?tier=TEAM&…&seats=5` showed Pro at `US$290.00 / year`; after signing in, `?plan=Team` showed Pro. The lower-case links, `?plan=Teams`, `?plan=Enterprise`, no parameter, the redirect to the login page and the way back passed there too.
  * The first run on this branch passed 32 of 33. The miss was a currency, not a tier: headless Edge's `navigator.language` moved from en-GB (`en-GB,en,en-US`) to en-US (`en-US,en,ar`) part way through the run, so the page's default currency moved to USD (Risks). With the locale pinned, every page read en-GB.
* **The app's links (Scope 3):** a grep of the app's `Plugins/` (`main` a913df53a, `*.cpp` and `*.h`, test and self-test code left out) for `truebex.com` links built with a value finds three. (1) `CadCore/Private/CadEntitlement.cpp:831`, `?plan=` from `FName::ToString()`: the only mixed-case producer. (2) `TruebexMarket/Private/CadMarket_PR2.cpp:206`, `market/basket?region=%s&items=%s` from `FCadMarketClient::Region()` (an `FString`, `CadMarketClient.h:101`) and the basket lines (`FString`s, URL-encoded), as PF14f found. (3) `TruebexMarket/Private/CadOrders.cpp:1360`, the fallback `https://truebex.com/market/orders/` + `OrderId` (an `FString` path, used only when 5.7's `web_url` is empty). `TruebexLicence/Private/TruebexLicence.cpp:584` opens `/dashboard/billing/` with no value (Manage). `TruebexUpdateTestKit.h:91`'s `changelog/#%s` is a test kit. The other browser openers (`LicenceUi.cpp:58`, `TelemetryUi.cpp:92`, `Cad3DShare.cpp:1422`, `CadOrdersPanel.cpp:1072`, `TruebexUpdateUi.cpp:196`, `MwMarkdown.cpp:204`) open URLs the API or the document gave them, or the privacy page.
* **Deviations from the task and why:**
  1. *The Node helper says what the page shows, not only the id.* `billing_link.cjs` also runs `page.tsx`'s lines after `tierId` (the selected tier, `intervalFor`, seats, the unit price, `STATIC_CATALOG`), so the tests can say "the same interval, seats and price" and "as master" in one place. The page itself is not rendered in Node (it needs the dashboard shell and the API); the headless run covers the built page.
  2. *Master's build was clicked through as well* (24 of 33), to show the fault on the real page.
* **Contract:** no contract file moves. PATCH line for the app half, repeating PF14f's line D: `UpgradeUrl` (`CadEntitlement.cpp:831`) writes the plan from a lower-case string literal (or lower-cases `Plan.ToString()`), as the other FName-written values should. With PF2f the site accepts either spelling, so the app's fix is no longer urgent.
* **Carry-over:**
  * **PF14f's "The site (whoever next touches the billing page)":** met here (PF14f's doc points at this one).
  * **The app half:** PF14f's PATCH line D, the upgrade link included (above).
  * **The owner:** whether `?plan=enterprise` (or the app's upgrade to Enterprise, if it ever sends one) should open the contact form rather than show Pro. Today it shows the first buyable tier, as before. Deploy at the next release; Human test step 8 on a Shipping build afterwards.
* **Cut:** nothing.
* **Verify gate:** `scripts/autopilot-verify.ps1` (absolute `-File` path) green on the docs commit's tree: lint, build (compiled in 13.0 s), pytest 959 passed + 19 skipped (978 collected; the six new tests ran, node and node_modules present) in 697 s, `out/index.html` checked; 761 s in all. The self-test builds were moved out of the worktree first (no `out/` under `.sdk-tools/scratch/`).
