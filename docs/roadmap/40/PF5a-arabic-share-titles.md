# PF5a — Share pages: Arabic titles drawn on the link-preview card and laid out right to left (launch priority 1)

**Needs merged:** PF5, PF13 (both on `master` at 6ef7928). **Unblocks:** none (closes PF5's carry-over "PF13 (Arabic)"). **Contract:** none (the share-bundle shapes are unchanged).

## Status

**Built 2026-10-12** (Autopilot T57, `ap/t57-pf5a-share-pages-arabic-titles-d`): Arabic, Persian and Urdu titles are joined and drawn right to left on the card, and the designer's names on the share page read in their own direction; see As-built. Before this task (master 6ef7928, verified on 2026-10-12):

| Area | Where (master 6ef7928) | Before |
|---|---|---|
| The card's title | `server/app/shares/card.py` `compose()`, `drawable()`, `_wrap()` | drawn in OpenSans-Bold only when every character has a glyph: "شقة الكرادة" was left off the 1200 × 630 card (`GET /s/{slug}/card.jpg`, `og:image`). Open Sans has Hebrew, so a Hebrew title was drawn in logical order, its letters reversed |
| Text layout | Pillow 12.3.0 (`server/requirements.txt`) | `PIL.features.check("raqm")` is False on this PC: the wheel's libraqm loads FriBiDi at runtime and none is installed. The API image (`server/Dockerfile`, python:3.12-slim-bookworm) has no apt step either |
| The share page | `src/viewer/main.ts:134` (title), `:287` (room chips), `gallery.ts:28` (render captions), `pdf.ts:56` (sheet names), `pano.ts:324` and `cube.ts:179` (hotspot labels) | no `dir`: Arabic names sat on the left, and a mixed Arabic and number name could reorder |
| The ended page | `server/app/shares/templates/ended.html` | does not show the share's title (only "This link has ended"), so nothing to change |
| `scripts/serve-out.py` | `ThreadingHTTPServer` | listen backlog 5: a dashboard's burst of about 100 requests got random `ERR_CONNECTION_REFUSED` in headless self-tests and human tests (PF5 deviation 13; PF8's and PF2d's As-built; the T47 merge) |

## Goal

A designer in Baghdad names a share "شقة الكرادة — مراجعة العميل" and sends the link on WhatsApp. The preview card shows that title, joined and reading right to left at the right edge, above the "Designed in Truebex" mark, and the share page shows the title, the room names, the render captions and the sheet names in their own direction. English titles look exactly as before.

## Read first

* `docs/roadmap/40/00-contract.md`; `PF5-share-pages.md` (Design: the card and the page; As-built deviations 2, 4, 12 and 13; Risks); the As-built of `PF13-website-pricing-features-roadmap-arabic-changelog-analytics.md` (Noto Sans Arabic for `/ar/`).
* Unicode: UAX #9 (the Bidirectional Algorithm), `ArabicShaping.txt`, `BidiBrackets.txt`, `BidiMirroring.txt`, and the conformance files `BidiTest.txt` and `BidiCharacterTest.txt` (version 15.0.0, the version of Python 3.12's `unicodedata`).
* `.claude/skills/truebex-brand-voice` (this feature adds no public copy: the card's mark and the page's words are unchanged).

## Scope

**In:**

1. **Card.** Titles in Arabic script (Arabic, and the Persian and Urdu letters that have presentation forms) drawn with Noto Sans Arabic Bold (OFL, committed with its licence beside Open Sans in `server/app/shares/assets/`): joined letter forms and lam-alef ligatures; right to left by the Unicode Bidirectional Algorithm, so digits and Latin words inside keep their order; right-aligned at the same size (56 px), line pitch (68 px) and baseline band as a Latin title; two lines at most with an ellipsis, as `_wrap` does. The mark stays where it is. Latin titles render exactly as before; a title in a script neither font covers (CJK) is still left off.
2. **Shaping route** that works on this PC and in the API image with no system package: shaping into presentation forms and the bidi algorithm in pure Python (`server/app/shares/rtl.py`). If a title cannot be shaped (a letter with no presentation forms) or a character is in neither font, the title is left off: never boxes, never disconnected or reversed letters.
3. **Page.** `dir="auto"` on the share's title, room chips, render captions, sheet names and hotspot labels, and on the `<noscript>` title of `view.html`; CSS so each aligns to its own start, and a row of Arabic room chips starts at the right. `<html lang="en">` stays: the page's own words are English.
4. **`scripts/serve-out.py`**: a server subclass with `request_queue_size = 128`, and a test.
5. **`server/scripts/demo_share.py`** for the human test: `--title` makes a share of its own (its own bundle id), `--rooms` names the panoramas.
6. Tests: `server/tests/test_shares_pf5a.py`; `server/scripts/bidi_conformance.py` to re-check the bidi algorithm against Unicode's files.

**Out (and where it goes):**

* Harakat (vowel marks, shadda) on the card: left off, the letters stay joined. Placing marks needs a real shaper (HarfBuzz through libraqm and FriBiDi, or uharfbuzz with an outline rasteriser): a later task if designers put marks in titles.
* Arabic letters with no presentation forms in Unicode (most of Arabic Supplement and Extended-A, for example Kurdish ڵ, ێ, ڕ and Uyghur ە): the title is left off the card, as today. Same route as above.
* Explicit bidi controls in a title (LRE, RLE, LRO, RLO, PDF, LRI, RLI, FSI, PDI): dropped before the card's layout (X1-X8 are not run).
* Redrawing the card when a share is renamed (`PATCH /shares/{id}`): the card is made at publish, as in PF5. Owner's call whether to add it (PF5 follow-up).
* An Arabic share page (the page's own words in Arabic): waits for the site's Arabic pages after LO1 and a native speaker's review (GD6).
* A web font for Arabic on the share page: none, as in PF5 (system fonts: Segoe UI on Windows and Noto on Android have Arabic).

## Design

**API, data, jobs:** none changed. The card is still composed once, at publish, by `card.compose()` (now `render()` to an image, then JPEG).

**The card** (`server/app/shares/card.py`):

* A title with no right-to-left letters and no Arabic digits (`rtl.needs_bidi`) takes PF5's path unchanged: the same drawable check, the same `_wrap` (now given a width function), the same drawing. A test compares it pixel for pixel with PF5's code.
* Any other title goes through `title_lines()`: `rtl.clean()` (NFC; combining marks and explicit bidi controls dropped), the paragraph direction from its first strong letter (P2-P3, the rule `dir="auto"` uses on the page), wrapping in logical order with `_wrap` (a line's width = its shaped, reordered runs), and per line: `rtl.shape()` → a font per character → `rtl.display()` (reordered and mirrored) → runs of one font. Each line is drawn right-aligned at `W − 64 − width` (left-aligned at 64 when the title starts with a Latin letter), its baseline where Open Sans's would be (the line top plus Open Sans's ascent).
* Fonts: Arabic-block characters in Noto Sans Arabic Bold; other letters (Latin, Greek, Cyrillic, Hebrew) in Open Sans Bold; digits, spaces and punctuation in the font of the nearest letter before them (else after) when that font has them, else the other one (Noto has digits and a few marks; the em dash, ellipsis and brackets come from Open Sans). Both are loaded with `ImageFont.Layout.BASIC`, so a machine that does have libraqm never reorders the already-ordered text again. A character neither font has leaves the title off.

**`rtl.py`** (pure Python on `unicodedata`; no dependency, no system package):

* Shaping: the presentation forms (isolated, final, initial, medial) and the four lam-alef ligatures are read from the compatibility decompositions of U+FB50–U+FDFF and U+FE70–U+FEFF; a letter's joining type is derived from the forms that exist, with ArabicShaping.txt's three exceptions in a table (noon ghunna is dual-joining, U with hamza above is right-joining, the prepended number signs are non-joining). Transparent marks are skipped, tatweel and ZWJ cause joining, ZWNJ breaks it. A letter with no forms, or a joined use of a form Unicode lacks, answers None.
* Bidi: UAX #9 for one paragraph without explicit embeddings: P2-P3, W1-W7, N0 (bracket pairs, BidiBrackets.txt's 64 pairs), N1-N2, I1-I2, L1, L2, and L4 mirroring for the brackets and `<> «» ‹› ≤≥`. Each card line is resolved as a paragraph with the title's direction.

**Rejected routes:**

* Pillow with libraqm: needs FriBiDi at runtime. The image could `apt-get install libfribidi0`, but the tests and the human test run on Windows, where there is none.
* `arabic-reshaper` (MIT) with `python-bidi` (LGPL-3.0): python-bidi 0.6's Rust `get_display` does not mirror brackets ("(شقة)" came back as ")ﺔﻘﺷ("), its Python fallback is the pre-6.3 algorithm (no bracket pairs), and neither returns the levels that reordering each wrapped line needs.
* uharfbuzz (Apache-2.0): real shaping, but Pillow cannot draw glyph ids, so it would need its own outline rasteriser.

**The page** (`src/viewer/`): `el()` in `main.ts` takes `dir`; the title (`h1.tbx-title`) and room chips get `dir="auto"`, as do render captions (`gallery.ts`), the sheet-name line (`pdf.ts`; each name wrapped in FSI…PDI so an Arabic and an English name never swap words across the " · ") and hotspot labels (`pano.ts`, `cube.ts`). `viewer.css`: `text-align: start` on the title and the sheet names; `.tbx-rooms:has(> .tbx-chip:first-child:dir(rtl)) { direction: rtl }`, so a row of Arabic rooms starts at the right and scrolls from there. `view.html`'s `<noscript>` title gets `dir="auto"`; `<html lang="en">` is unchanged.

**Security and privacy:** nothing new is stored or sent. Explicit bidi controls in a title cannot reorder the card (they are dropped); on the page the browser's own algorithm applies, isolated per element by `dir="auto"`.

## Deliverables

- [x] `server/app/shares/rtl.py` (shaping and bidi), `server/app/shares/card.py` (`render`, `title_lines`, font runs)
- [x] `server/app/shares/assets/NotoSansArabic-Bold.ttf` (Noto Sans Arabic 2.013) and `NotoSansArabic-OFL.txt`
- [x] `server/app/shares/templates/view.html` (`<h1 dir="auto">` in `<noscript>`)
- [x] `src/viewer/main.ts`, `gallery.ts`, `pdf.ts`, `pano.ts`, `cube.ts`, `viewer.css`
- [x] `scripts/serve-out.py` (`Server`, `make_server`, backlog 128)
- [x] `server/scripts/demo_share.py` (`--title` with its own bundle id, `--rooms`), `server/scripts/bidi_conformance.py`
- [x] `server/tests/test_shares_pf5a.py` (10 tests)
- [x] this doc, the tracker row, PF5's carry-over marked done, a README section

## Tests

| Name | Kind | Asserts |
|---|---|---|
| `test_pf5a_arabic_title_drawn_right_aligned` | pytest | on the grid and on the house's living room, "شقة الكرادة" changes the card only in the title band above the mark, its ink starts right of the middle and ends at the right margin (between 1128 and 1140 px); a Latin title still starts at 64 px |
| `test_pf5a_arabic_title_shaped` | pytest | the presentation forms: شقة → FEB7 FED8 FE94; لا → FEFB; سلام and للإهمال with the final lam-alef forms; Persian پدری, Urdu گھر, ZWNJ in خانه‌ی; harakat dropped. The card's joined word has no gap in its ink and is narrower than its letters drawn apart, which have gaps |
| `test_pf5a_long_arabic_title_wraps_with_ellipsis` | pytest | a 20-word title: two lines, each within 1072 px, the ellipsis (Open Sans) at the left end of line two and nowhere on line one; two bands of ink above the mark |
| `test_pf5a_number_keeps_bidi_order` | pytest | "شقة 2" is drawn "2 ﺔﻘﺷ" (the number left of the word), on the card too; "شقة 12" keeps "12"; "فيلا 3 – Villa 12B" shows "Villa 12B – 3 " first; "(شقة)" has mirrored brackets; "Villa 12 — شقة الكرادة" reads left to right from the left margin |
| `test_pf5a_latin_title_pixels_unchanged` | pytest | four Latin, Greek and Cyrillic titles (one wrapping with an ellipsis) on both backgrounds have exactly the pixels of PF5's title code (kept in the test as the oracle), and the stored JPEG bytes are equal |
| `test_pf5a_cjk_title_still_left_off` | pytest | "設計図", "设计图 شقة", "شقة ★" and "ماڵ" (a letter with no joined forms) leave the card as without a title; Hebrew "שלום עולם" is drawn right to left, right-aligned |
| `test_pf5a_publish_arabic_title_card_drawn` | pytest | through `POST /shares`, the uploads and `POST /shares/{id}/publish`: the stored card differs from the same room without a title only in the band, strongly in its right half; `/s/{slug}/card.jpg` serves it; `/view/{slug}` keeps `<html lang="en">` and has `<h1 dir="auto">` with the title |
| `test_pf5a_viewer_names_dir_auto` | build check | `out/viewer/viewer.js` ≤ 250 KB; the title is made by `el("h1","tbx-title",…,"auto")` and `el()` sets `.dir`; the room chips too; captions, sheet names and hotspot labels set `dir="auto"`; `viewer.css` has `text-align:start` on `.tbx-title` and the `:dir(rtl)` rooms rule |
| `test_pf5a_serve_out_backlog` | pytest | `serve-out.py`'s `Server.request_queue_size` ≥ 128; 100 connections queue before the server accepts any; then a file is served with `Access-Control-Allow-Origin: *` and `text/javascript` |
| `test_pf5a_demo_share_title` | pytest | `demo_share.py --title` publishes a share of its own with that title (5 parts, then 0 parts and the same url); `--rooms` names the panoramas and their hotspots |
| `scripts/bidi_conformance.py` | manual | 0 failures on Unicode's BidiTest.txt and BidiCharacterTest.txt for the cases `rtl.py` implements (needs the files; see As-built) |
| `test_shares.py`, `test_site_pf5.py`, `npm run lint`, `npm run build` | pytest, build check | still green |

## Human test

Set-up, in the worktree, PowerShell (two windows):

* **API.** `cd server`; if there is no `server\.env`, `Copy-Item .env.example .env`. Run `.venv\Scripts\python.exe scripts\make_signing_key.py --kind lic` and paste the `LICENCE_SIGNING_KEY=` and `LICENCE_KEY_ID=` lines it prints over the empty ones in `server\.env`. In `server\.env` also set `API_URL=http://127.0.0.1:8000` and `SITE_URL=http://127.0.0.1:3157`, and add `,http://127.0.0.1:3157` to the end of `CORS_ORIGINS`. Start the API with `server\run.bat`.
* **Site.** `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1` → `serving … on http://127.0.0.1:3157/`. If it names another port, use that port in `SITE_URL` and `CORS_ORIGINS` and restart `run.bat`. (The share page is served by the API and loads `viewer.js` from this address; no rebuild is needed.)

1. In a third window, in `server\`, make an account and publish the Arabic share (paste the Arabic; if the console shows boxes, that is only its font):

   ```powershell
   Invoke-RestMethod -Method Post http://127.0.0.1:8000/auth/register -ContentType 'application/json' -Body '{"email":"arabic@example.com","password":"password123"}'
   .venv\Scripts\python.exe scripts\demo_share.py --email arabic@example.com --password password123 --fixture tests\contracts\share-bundle\manifest-house.json --api http://127.0.0.1:8000 --title "شقة الكرادة — مراجعة العميل" --rooms "غرفة المعيشة, المطبخ 2, الممر"
   ```

   → "5 parts sent", "state live …" and `url http://127.0.0.1:8000/view/<slug>`.
2. Open that url in Edge on the PC (optionally F12 → device toolbar → 412 px wide, or a phone through PF5's LAN steps) → the title "شقة الكرادة — مراجعة العميل" sits at the right edge of the dark header and reads right to left; the room chips at the bottom start at the right ("غرفة المعيشة" highlighted, then "المطبخ 2" with the 2 on its left, then "الممر"); the hotspot labels in the room are Arabic. Renders tab → the caption under the picture is "Street view" (the fixture's). The tabs, "Drag to look around" and the footer stay in English, left to right; nothing scrolls sideways.
3. Open `http://127.0.0.1:8000/s/<slug>/card.jpg` → the living room; above "Designed in Truebex" (bottom left) the title in joined Arabic letters, right-aligned at the right margin, with the em dash between the two parts; no boxes, no separated letters.
4. Repeat with an English title on a second account:

   ```powershell
   Invoke-RestMethod -Method Post http://127.0.0.1:8000/auth/register -ContentType 'application/json' -Body '{"email":"english@example.com","password":"password123"}'
   .venv\Scripts\python.exe scripts\demo_share.py --email english@example.com --password password123 --fixture tests\contracts\share-bundle\manifest-house.json --api http://127.0.0.1:8000 --title "House — client review"
   ```

   → its page shows "House — client review" at the left of the header with "Living room", "Kitchen", "Hall" chips from the left, and its `card.jpg` shows the title at the left above the mark, as before PF5a.
5. Optional, a mixed title on a third account: `--title "فيلا المنصور (الطابق 2) – Villa 12B"` → the card and the page show it right to left, "(الطابق 2)" with its brackets the right way round and "Villa 12B" at the left end.

## Risks / traps

* `rtl.py` reads Unicode data from the running Python's `unicodedata` (15.0.0 on Python 3.12); its bracket and mirroring tables are Unicode 15.0's. When the server moves to a new Python, run `scripts/bidi_conformance.py` against that version's conformance files.
* The right-to-left path loads its fonts with `Layout.BASIC` on purpose. PF5's Latin path still uses Pillow's default engine, so on a machine with libraqm and FriBiDi a Latin card could differ slightly from this PC's, as it already could before PF5a.
* The rooms row's right-to-left start uses `:has()` and `:dir()` (Chrome and Edge 120+, Safari 16.4+, Firefox 121+). Older browsers keep the row left to right; each chip still reads in its own direction.
* Every plan allows one live share for now (GD7 placeholders): the human test uses one account per share.
* Windows PowerShell 5.1's console may show Arabic as boxes; the argument still reaches Python intact (checked: the stored title is exact).

## As-built

* **Date, branch, commits:** 2026-10-12, `ap/t57-pf5a-share-pages-arabic-titles-d` from `master` 6ef7928 (Claude Autopilot T57): `14abd4e` the card (`rtl.py`, `card.py`, Noto Sans Arabic), the page (`dir="auto"`, CSS), `serve-out.py`, `bidi_conformance.py` and the tests; `ff7275c` `demo_share.py --rooms`; then this documentation.
* **Counts:** pytest 622 → 632 collected (10 new in `test_shares_pf5a.py`). The verify gate's result is below. `viewer.js` 28.4 KB, `viewer.css` 10.0 KB (budget 250 KB). Noto Sans Arabic Bold adds 255 KB to the API image.
* **Self-tests:**
  * `scripts/bidi_conformance.py` on Unicode 15.0.0's files: BidiTest.txt 92,898 cases, BidiCharacterTest.txt 91,605 cases (every case without explicit embeddings, isolates or paragraph separators), 0 failures. Joining types derived for the 248 Arabic-block letters and marks with forms agree with ArabicShaping.txt (after the three exceptions in the table); 193 letters with no presentation forms answer None.
  * Card pixels: 16 cards composed by PF5's code before any change (8 titles × the grid and the living room: English, a wrapping one, HTML-like, Greek and Cyrillic, empty, CJK, Arabic, Hebrew) and again after: the 12 non-Arabic, non-Hebrew cards are byte-identical JPEGs; the Arabic and Hebrew ones now carry their titles.
  * End to end: the API under uvicorn on a scratch SQLite database (port 18057), four shares through `demo_share.py` from PowerShell (the Arabic review title, the same with Arabic rooms, a mixed Arabic/Latin title, the English one), `out/` built against that API and served by `scripts/autopilot-serve.ps1` on 3157. Headless Edge over CDP at 412 px: every `/view/{slug}` loads with no console errors and no sideways scroll; the Arabic titles' text ends at the header's right edge (x 396 of 412, `direction: rtl`, `text-align: start`), the English one starts at x 16; Arabic chips run from the right (`direction: rtl` on the row), the Arabic caption and hotspots are `rtl`; `<html lang="en">`. The four `card.jpg` files were opened and looked at: joined Arabic, right-aligned above the mark; the English card as before.
  * `serve-out.py`: with backlog 5, 95 of 100 queued connections were refused (192 s of SYN retries); with 128, all 100 connected in 0.2 s.
* **Deviations from the task text and why:**
  1. *No new dependency and no system package:* the shaping and the bidi algorithm are written here on the standard library's Unicode data (see Design, Rejected routes). `requirements.txt` and `server/Dockerfile` are unchanged, so the image needs nothing new (no Docker on this PC: the image build is checked at deploy as usual; only the font file under `app/` is new). "If shaping is unavailable at runtime" therefore means a title the shaper or the fonts cannot handle, which is left off.
  2. *Harakat are dropped on the card* (letters stay joined); placing marks needs GPOS (Out).
  3. *Letters without presentation forms leave the title off* (Kurdish, Uyghur, some African orthographies), rather than drawing them unjoined.
  4. *Hebrew titles are now drawn right to left* in Open Sans (they were drawn reversed before); the "same pixels" promise holds for titles with no right-to-left letters.
  5. *A title that starts with a Latin letter reads left to right* and starts at the left margin ("Villa 12 — شقة الكرادة"), the rule `dir="auto"` applies on the page, so card and page agree.
  6. *Mixed fonts on one line:* digits and spaces next to Arabic come from Noto (it has them), the em dash, ellipsis, brackets and Latin letters from Open Sans.
  7. *Each card line is resolved as its own paragraph* with the title's direction (UAX #9 resolves the whole paragraph, then reorders lines); they differ only for neutral characters at a line's edge.
  8. *Hotspot labels* (`pano.ts`, `cube.ts`) also get `dir="auto"`, and the sheet names are isolated one by one (FSI…PDI) in their line.
  9. *The ended page shows no title*, so `ended.html` is unchanged; `view.html`'s `<noscript>` title got `dir="auto"`.
  10. *`demo_share.py`:* `--title` now gives the share its own bundle id (running it again with the same title returns the same share), and `--rooms` names the panoramas, so the human test can show Arabic chips with the contract's fixtures left untouched.
  11. *`card.render()`* returns the image and `compose()` encodes it, so tests compare pixels before JPEG.
* **Licences:** Noto Sans Arabic 2.013 (`NotoSansArabic-Bold.ttf`, hinted, from notofonts.github.io), SIL Open Font License 1.1, `assets/NotoSansArabic-OFL.txt`. Unicode data from Python's `unicodedata`; the 64 bracket pairs in `rtl.py` are from BidiBrackets.txt (Unicode License v3). No new Python package.
* **Contract:** none; nothing to record in the Unreal repo's `contracts/`.
* **Carry-over → which feature:** HarfBuzz shaping (harakat, letters without presentation forms) → a later task if designers need it (the image would then add FriBiDi for libraqm, or uharfbuzz). Redrawing a share's card when it is renamed → owner (PF5 follow-up). PF5's "PF13 (Arabic)" carry-over is done.
