# Truebex brand folder (v1)

Everything the Truebex brand is made of, in one place: the words, the logo, the colours, the fonts and every
social-media image. To change the brand, change this folder, run the script, then update the accounts.

| Path | What it is |
|---|---|
| `social-media.md` | **v1 social media**: every profile's text, category (Software Company), links, images, mailboxes and the tracker |
| `messaging-brief.md` | the owner's messaging brief: what Truebex says and which claims ship |
| `brand.json` | name, slogan, website, handle, category, colours, fonts, logo spacing |
| `logo/truebex-mark.svg`, `logo/truebex-wordmark.svg` | the logo sources (vector) |
| `logo/figma/` | the Figma masters as exported (reference only) |
| `fonts/` | Open Sans (SIL OFL, `OFL.txt`): the website's web font and the images' fallback |
| `images/daylight-doorway.png` | the one clean in-app capture the banners use |
| `make_brand_assets.py` | renders everything in `export/` from the sources above |
| `export/` | **upload from here**: avatar, covers, banners, watermark, lockups, SVG logo set |

## The brand at a glance

| | |
|---|---|
| Name | Truebex (True Building Experience) |
| Slogan | Imagine More. Build Better. (Arabic: «تخيّل أكثر. ابنِ أفضل.») |
| Category | Software Company |
| Handle | truebex (fallback truebexapp) |
| Ground | `#232323` |
| Logo grey | `#CBCBCB` |
| Accent | `#A0CEFF` (on light backgrounds `#1762C9`) |
| Roadmap amber | `#E2A75C` |
| Website page | `#161616` |
| Type | Segoe UI (the app's font) → Open Sans fallback |

**Fonts.** Segoe UI is licensed with Windows: it may be rendered into images (the script reads it from
`C:/Windows/Fonts`) but is never copied into this folder or served on the website. On a machine without it,
the script falls back to the bundled Open Sans, as the website does.

**Logo rules.** Grey `#CBCBCB` on dark, `#232323` on light. Clear space at least the mark's stem width. No
gradients, outlines, rotation or effects; never retype the wordmark in a font. The lockup is always left to
right, Arabic included.

## Change the brand

1. Edit the source: `brand.json` (colours, slogan, fonts, spacing), `logo/*.svg` (new logo),
   `images/daylight-doorway.png` (a new clean capture), or the wording in `social-media.md`.
2. Render the images:

   ```
   py -3.12 docs/brand/make_brand_assets.py
   ```

3. Upload the changed files from `export/` and paste the changed text from `social-media.md` into each account;
   tick them in its tracker (§13).
4. Bring the website in line. List what differs:

   ```
   py -3.12 docs/brand/make_brand_assets.py --check
   ```

   It compares `brand.json` and `logo/` with the website's copies:

   | Brand item | Website file |
   |---|---|
   | colours | `src/app/globals.css` (`@theme` tokens) |
   | mark / wordmark | `public/brand/*.svg`, `src/components/brand/Logo.tsx`; icons and the OG card from `scripts/make_web_assets.py` |
   | slogan | `src/lib/constants.ts` (`SITE.slogan`, `HERO`) |
   | voice and rules | `.claude/skills/truebex-brand-voice/SKILL.md` |

   Then deploy the site (the `truebex-deploy` skill).
