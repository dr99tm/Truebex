---
name: truebex-brand-voice
description: Truebex brand identity, voice and content rules for truebex.com. Use BEFORE writing or editing any website copy, headline, feature text, FAQ, meta description, social post, email, or visual (colors, logo, type) for Truebex — including src/lib/constants.ts, landing sections, the developer docs, and OG images.
---

# Truebex brand voice

Truebex — **True Building Experience**. A building design platform where
daylight is measured, surfaces design themselves, and one change updates the
whole project. The brand promise is in the name: *what you see is true.* Every
word on the site has to keep that promise.

## Positioning rules (from the owner, 2026-10-07)

1. **Truebex stands alone.** Never name, compare to, or position against any
   other software, engine or vendor in public copy: no "built on <engine>",
   no "<tool> alternative", no "<tool>-style", no engine feature names
   (render tech, upscalers) and no engine trademarks. Describe what Truebex
   does in its own words. (Internal docs and code may name the stack.)
2. **Lead with what's distinctive.** Don't market table-stakes features every
   design tool has (room areas, walking around the model, basic modelling).
   The headline features are: measured daylight through every opening,
   self-arranging surface fills, assets that update everywhere, design
   intent that holds (constraints/references), instant edits at any size,
   projects that remember their light and view.
3. **One image, clean.** Only show captures with no HUD, labels or debug
   overlays. Today the site uses exactly one: daylight through a doorway
   (`public/images/product/daylight-doorway*.jpg`). Add others only when they
   are equally clean and beautiful.

## The one rule: only claim what ships

Copy describes the desktop app as it exists today. Before writing a capability,
confirm it in the product docs:

- `T:\unreal5_7_4_projects\truebex_compact\Docs\cad\implemented\README.md` — every shipped plan (01–38)
- `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\AS-BUILT\release-notes.md` — roadmap 39 (release 1.0.0, 2026-10-07): what it added
- `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\README.md` — roadmap 40, what's in progress (a row is shipped only when ticked AND merged to `main`)

Shipped — the internal fact list. These are engineering names; translate them
into Truebex's own words before they reach public copy (rule 1), and only
headline the distinctive ones (rule 2):
walls, rooms/regions, doors/windows (openings), slabs, stairs, arcs/ellipses,
groups, reference planes, dimension locks, constraints; wall-face panels,
nested regions, dynamic fills ("fill tree"), face-as-asset library + asset
workbench (edit an asset, every instance updates); sweeps; global
illumination, sun/sky, measured opening light (interior doors pass light on),
ray tracing, path tracing; lighting profiles and the view saved in the
project, lighting on the undo stack; section cuts, storey navigator;
`.tbxp` projects / `.tbxa` assets; edits in milliseconds (drag 240 ms →
4.3 ms benchmark). Since roadmap 39 (2026-10-07): sheets auto-created with
our own vector PDF (selectable text, fillable forms) and DXF writers;
dimension styles, auto dimensions, relevance and pins; paint, wallpaper and
3D pattern finishes; panels on any face (floors, ceilings, slabs, models);
mouldings at door jambs and along curved walls; the Scale command; walls from
curves with smooth curved meshes; models with a feature list; sweeps that face
the viewer; control points; references to anything; dynamic doors, windows,
cabinets and custom objects; stairs from a run; category prototypes; the asset
registry with embedded / linked saves and placeholders; the asset browser;
texture import (BC1–BC7, mips) and mesh import (glTF, GLB, OBJ, FBX) with the
Object Composer; one UI kit with a live theme; 445 MB install, 4.6 s cold
start. Also shipped but *not* marketed (table stakes): live room areas,
first-person walk mode, the self-driving test harness (FastEye).

**Not shipped — roadmap only** (label "On the roadmap", never present tense):
IFC and DWG exchange, several people on one model (cloud projects, history),
the marketplace with live regional prices and the live cost model, cloud
panoramas on phones and headsets, daylight / energy / sound / wind reports,
building services (MEP), the assistant that edits the model, Arabic UI.
Content lives in `src/content/roadmap.json` (words by hand; `status` from
`scripts/sync-roadmap.mjs`, which reads both roadmap trackers); never move an
item into `FEATURES` until the roadmap 40 tracker shows its row merged. The
pricing page's comparison rows for unshipped work carry "On the roadmap"
(`roadmap: true` in `PRICING.comparison`), and `/features/marketplace/` is
written in the future tense.

Payments: say "rolling out" for Stripe and Wayl until `/billing/plans` on the
API lists them as enabled.

## Voice

| Be | Not |
|---|---|
| Precise — numbers, units, named features ("4.3 ms", "30 days") | Vague superlatives ("revolutionary", "next-gen", "seamless") |
| Calm and confident — short declarative sentences | Hype, exclamation marks, ALL CAPS |
| Architect-literate — walls, openings, slabs, sections, daylight | Engine/render jargon or any third-party product name |
| Visual — what you *see* and *feel* in the space | Abstract platform-speak ("unified ecosystem", "single source of truth") |
| Honest about limits | Implying features we don't have |

Signature lines (reuse, don't dilute): **"See it before you build it."** ·
"What you draw is what you see." · "Daylight, measured — not painted." ·
"Make it once, update everywhere."

Headline pattern: concrete promise + payoff. ("Daylight, measured — not
painted." / "Make it once, update everywhere.") Keep H2s ≤ 6 words, subtitles
one sentence.

Vocabulary: say *design, draw, shape, light, daylight, room, wall, opening,
surface, asset, platform*. Avoid *metaverse, AI-powered* (unless true),
*synergy*, *VR*, *walkthrough*, *area calculation*, and any other product's
or engine's name.

## Visual identity (source of truth: the app)

| Token | Value | Source |
|---|---|---|
| Ground | `#232323` | `MwBrand.cpp` (window background) |
| Foreground / logo | `#CBCBCB` | `MwBrand.cpp` |
| Accent (UI, links, text) | `#A0CEFF` | `MwTheme.cpp` dark accent |
| Accent strong (light bg) | `#1762C9` | `MwTheme.cpp` light accent |
| Warn / roadmap | `#E2A75C` | `MwTheme.cpp` amber |
| Chart fill | `#4A8DF0` | dataviz-validated brand blue on `#1d1d1d` |
| Page | `#161616` | site only (one step below ground) |

All tokens are in `src/app/globals.css` `@theme`. Never hard-code hex in
components; use the Tailwind token (`text-accent`, `bg-surface`, `fill-chart`).

- **Logo**: the T/J glyph + "Truebex" wordmark, from the Figma masters in
  `truebex_compact/Brand/Truebex/logo/figma_original`. Use
  `src/components/brand/Logo.tsx` (`Lockup`, `LogoMark`, `Wordmark`); never
  retype the wordmark in a font. Grey `#CBCBCB` on dark; `#232323` on light.
  Clear space ≥ the glyph's stem width. Don't recolor with gradients, outline,
  rotate, or add effects.
- **Type**: Segoe UI (the app's font) → Open Sans fallback (same designer,
  Steve Matteson). Segoe UI is licensed — never self-host it as a web font; it
  may be rendered into raster images (OG cards) only.
- **Imagery**: real in-app captures over illustrations. Crop away debug HUD
  text. Regenerate with `py -3.12 scripts/make_web_assets.py`. Caption every
  capture with what it proves ("Rooms label their own areas").
- **Texture**: the drafting grid (`.blueprint-grid`) — 24 px minor / 120 px
  major lines — is the brand's background motif.

## Checklist before shipping copy

1. Every capability claim is in the "shipped" list above (or labelled roadmap), and no other software or engine is named.
2. Numbers have units; no orphan superlatives.
3. Headline ≤ 8 words, includes a concrete noun.
4. Alt text describes what the image shows *and* the feature it proves.
5. Update the matching JSON-LD (`app/page.tsx` FAQ/SoftwareApplication) when FAQ or features change. Prices never go in copy: they come from `server/app/catalogue.json`, and a tier without one says "Price at launch".
6. Arabic copy (`AR_HOME`) follows the same rules and is reviewed by a native speaker before launch.
7. Then run the `truebex-seo` checklist.
