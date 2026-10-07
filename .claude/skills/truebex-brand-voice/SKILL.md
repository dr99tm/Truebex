---
name: truebex-brand-voice
description: Truebex brand identity, voice and content rules for truebex.com. Use BEFORE writing or editing any website copy, headline, feature text, FAQ, meta description, social post, email, or visual (colors, logo, type) for Truebex — including src/lib/constants.ts, landing sections, the developer docs, and OG images.
---

# Truebex brand voice

Truebex — **True Building Experience**. A real-time 2D + 3D building design
tool (Revit-style CAD) built on Unreal Engine 5.7. The brand promise is in the
name: *what you see is true.* Every word on the site has to keep that promise.

## The one rule: only claim what ships

Copy describes the desktop app as it exists today. Before writing a capability,
confirm it in the product docs:

- `T:\unreal5_7_4_projects\truebex_compact\Docs\cad\implemented\README.md` — every shipped plan (01–38)
- `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\README.md` — what's in progress

Shipped (safe to claim): walls, rooms/regions, doors/windows (openings), slabs,
stairs, arcs/ellipses, groups, reference planes, dimension locks, constraints;
live room areas; wall-face panels, nested regions, dynamic fills, face-as-asset
library; sweeps; Lumen GI, sun/sky, measured opening light, hardware ray
tracing, path tracing, DLSS 4.5; first-person walk mode with collision; section
cuts, storey navigator, view cube; `.tbxp` projects / `.tbxa` assets; edits in
milliseconds (drag 240 ms → 4.3 ms benchmark).

**Not shipped — roadmap only** (label "On the roadmap", never present tense):
real-product marketplace, quantity take-off & cost estimates, VR headsets,
project/asset API. Content lives in `ROADMAP` in `src/lib/constants.ts`;
never move an item into `FEATURES` until the product docs show it shipped.

Payments: say "rolling out" for Stripe and Wayl until `/billing/plans` on the
API lists them as enabled.

## Voice

| Be | Not |
|---|---|
| Precise — numbers, units, named features ("20.36 m²", "4.3 ms") | Vague superlatives ("revolutionary", "next-gen", "seamless") |
| Calm and confident — short declarative sentences | Hype, exclamation marks, ALL CAPS |
| Architect-literate — walls, openings, slabs, sections, daylight | Gamer/engine jargon in headlines (shaders, cvars, PPV) |
| Visual — what you *see* and *feel* in the space | Abstract platform-speak ("unified ecosystem", "single source of truth") |
| Honest about limits | Implying features we don't have |

Signature lines (reuse, don't dilute): **"See it before you build it."** ·
"What you draw is what you see." · "Draw it, light it, measure it, walk through it."

Headline pattern: concrete promise + payoff. ("Real light, in real time." /
"Walk through it.") Keep H2s ≤ 6 words, subtitles one sentence.

Vocabulary: say *design, draw, model, light, walk through, room, wall, opening,
daylight, area*. Avoid *metaverse, AI-powered* (unless true), *synergy,
platform* as a noun on its own, *VR* (unless roadmap).

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

1. Every capability claim is in the "shipped" list above (or labelled roadmap).
2. Numbers have units; no orphan superlatives.
3. Headline ≤ 8 words, includes a concrete noun.
4. Alt text describes what the image shows *and* the feature it proves.
5. Update the matching JSON-LD (`app/page.tsx` FAQ/SoftwareApplication) when FAQ or features change.
6. Then run the `truebex-seo` checklist.
