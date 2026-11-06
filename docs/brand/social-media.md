# Truebex — social media v1

**Version:** v1, 2026-10-22. The profile text, categories, images and mailboxes for every Truebex account.
Everything it points to lives in this folder (`docs/brand/`): see `README.md` for the folder and how to change the
brand.

The one place that holds what every Truebex profile says. Fill each platform by hand from here.

**To change anything later:** edit this file (and, for colours, logo or slogan, `brand.json` / `logo/`, then run
`py -3.12 docs/brand/make_brand_assets.py`) first, then copy the change to the platform, then tick it in
the tracker (§13). When a profile goes live, put its URL in `SOCIAL` in `src/lib/constants.ts` (the footer's
Follow column and the Organization `sameAs` show only the set ones) and deploy.

**Source of the wording:** the owner's v2 profiles (2026-10-20), built on the messaging brief
(`docs/brand/messaging-brief.md`). Two texts were shortened to fit their platform's limit (Facebook intro,
Reddit); each says so where it appears.

**Never put passwords, recovery codes or 2FA secrets in this file** — it is in git. Keep them in a password
manager.

Character limits were read from memory: check them on the form when you fill it in. Every text below fits
its limit (counts in brackets).

---

## 1. The brand on every profile

| Field | Value |
|---|---|
| Name | **Truebex** |
| Slogan | **Imagine More. Build Better.** (Arabic: «تخيّل أكثر. ابنِ أفضل.») |
| Meaning | True Building Experience |
| Core idea | Give designers and owners the freedom to explore alternatives, refine designs together, and make better-informed decisions before construction. |
| Voice | Clear, confident, professional, creative and human. Better decisions and better spaces — not a list of software features. |
| Handle | **truebex** everywhere; if one is taken, **truebexapp** everywhere |
| Website | https://truebex.com/ |
| Category | **Software Company** everywhere; where the list has no such entry, the nearest: "Software" (Instagram), "Software Development" (LinkedIn industry) |
| Location | United Kingdom — *confirm: it must match the company documents you gave Wayl and Companies House* |
| Legal name | *(once the company exists — e.g. "Truebex Ltd", company number, registered office)* |
| Contact / Support / Sales | contact@truebex.com · support@truebex.com · sales@truebex.com (§12) |
| WhatsApp | *(the business number — see §10)* |
| Avatar | the T/J mark, grey `#CBCBCB` on the dark ground `#232323` — `export/avatar.png` (§14) |
| Banner | the lockup and slogan beside the daylight-through-a-doorway capture — one file per platform in `export/` (§14) |
| Fonts | Segoe UI (the app's font, in images only) → Open Sans (the website's web font, `fonts/`) |
| Colours | ground `#232323`, logo `#CBCBCB`, accent `#A0CEFF` |

### Consistency checklist

- **Imagine More. Build Better.** is the primary slogan on every profile.
- The brand name is **Truebex**; every profile links to **https://truebex.com/**.
- Emphasise exploration, iteration, shared understanding and better decisions before construction.
- Short bios stay short; the About sections carry the fuller explanation.
- Never present an unshipped capability as available (headsets, product marketplace, cost estimates, several
  people in one model are on the roadmap). Update feature-specific wording when the product and website are
  ready.
- Once the new website is deployed, review all social links and profile wording together.

### Links with tracking (for each platform's "website" field)

They open https://truebex.com/ and tell the site's analytics which profile sent the visitor. Inside a
description, the plain https://truebex.com/ is fine.

| Platform | Link |
|---|---|
| YouTube | `https://truebex.com/?utm_source=youtube&utm_medium=social&utm_campaign=profile` |
| Facebook | `https://truebex.com/?utm_source=facebook&utm_medium=social&utm_campaign=profile` |
| Instagram | `https://truebex.com/?utm_source=instagram&utm_medium=social&utm_campaign=profile` |
| LinkedIn | `https://truebex.com/?utm_source=linkedin&utm_medium=social&utm_campaign=profile` |
| X | `https://truebex.com/?utm_source=x&utm_medium=social&utm_campaign=profile` |
| TikTok | `https://truebex.com/?utm_source=tiktok&utm_medium=social&utm_campaign=profile` |
| Threads | `https://truebex.com/?utm_source=threads&utm_medium=social&utm_campaign=profile` |
| Pinterest | `https://truebex.com/?utm_source=pinterest&utm_medium=social&utm_campaign=profile` |
| Reddit | `https://truebex.com/?utm_source=reddit&utm_medium=social&utm_campaign=profile` |
| WhatsApp | `https://truebex.com/?utm_source=whatsapp&utm_medium=social&utm_campaign=profile` |

---

## 2. Instagram

Make it a **professional account → Business**, and link it to the Facebook Page (Meta Business Suite).

**Bio** [111 / 150]

```
Architectural design, reimagined.
Explore ideas. Refine spaces before construction.
Imagine More. Build Better.
```

| Field | Limit | Value |
|---|---|---|
| Username | 30 | truebex |
| Name | 64 | Truebex |
| Category | — | Software Company *(if the list only offers "Software", pick that)*; show category on profile: on |
| Links | 5 | 1. Website — the Instagram link (§1); 2. `https://truebex.com/download/`, title "Download for Windows"; 3. `https://truebex.com/ar/`, title "بالعربية" |
| Contact options | — | Email: contact@truebex.com; WhatsApp: the business number (§10) |
| Profile picture | 320 × 320 (upload 1080 × 1080) | `export/avatar.png` |
| Highlights (later) | — | Explore · Compare · Experience · Releases |

Hashtags for posts (3–5 per post): `#architecture #interiordesign #buildingdesign #designsoftware #realestate`

---

## 3. Facebook (Page)

Create from your personal account: Menu → Pages → Create new Page. The Page is public; your personal account
stays private behind it.

**Short description / intro** [96 / 101] — *your v2 text (152) is over Facebook's 101; shortened, same idea:*

```
A connected design platform for exploring ideas and making better decisions before construction.
```

*Alternative [97]:* `Explore ideas and make better-informed decisions before construction. Imagine More. Build Better.`

**About** [340]

```
Truebex helps architects, interior designers, property developers, and owners explore possibilities and refine spaces before construction begins.

Bring design ideas into context, compare alternatives, and make decisions with a clearer understanding of the space you are creating.

Imagine More. Build Better.

Website: https://truebex.com/
```

| Field | Limit | Value |
|---|---|---|
| Page name | 75 | Truebex |
| Category (up to 3) | — | **Software Company** (first) · Architectural Designer · Interior Design Studio *(if "Software Company" isn't offered, type "Software" and take the closest; last resort: Science, Technology & Engineering)* |
| Username | 50 | TruebexOfficial → facebook.com/TruebexOfficial (facebook.com/truebex was not available) |
| Website | — | the Facebook link (§1) |
| Email | — | contact@truebex.com |
| Phone / WhatsApp | — | the WhatsApp business number (§10), if you want it public |
| Location / address | — | leave off unless it is the company's registered office (never a home address) |
| Action button | — | **Send WhatsApp message** (once §10 exists), else **Send email** → contact@truebex.com |
| Profile picture | 720 × 720 (shows as a circle) | `export/avatar.png` |
| Cover | 1640 × 624 (keep text in the middle 1640 × 360) | `export/facebook-cover.png` |
| Link to Instagram | — | Settings → Linked accounts, once Instagram exists |

---

## 4. LinkedIn (Company Page)

Needs a personal LinkedIn account (at least a day old, more than one connection). Me → Create a company page →
Company.

**Tagline** [76 / 120]

```
Imagine More. Build Better. Design with greater clarity before construction.
```

**About** [594 / 2,000]

```
Truebex is a building design platform for architects, interior designers, property developers, and building professionals.

We believe better spaces begin with the freedom to explore options, evaluate alternatives, and make informed decisions before construction. Truebex brings the design process closer together, helping designers and owners develop a shared understanding of the space they want to create.

Our goal is simple: make it easier to move from ideas to better design decisions—and from better decisions to better spaces.

Imagine More. Build Better.

Website: https://truebex.com/
```

| Field | Limit | Value |
|---|---|---|
| Name | 100 | Truebex |
| Public URL | — | linkedin.com/company/truebex |
| Website | — | the LinkedIn link (§1) |
| Industry | — | Software Development |
| Organisation size | — | 0–1 employees *(change as you grow)* |
| Organisation type | — | Self-employed now; **Privately held** once the company is formed |
| Specialties (up to 20) | — | Building design software · Architectural design · Interior design · Design visualisation · Real estate design |
| Founded | — | the year the company was formed |
| Button | — | **Visit website** → the LinkedIn link (§1) |
| Logo | 400 × 400 | `export/avatar.png` |
| Cover | 1128 × 191 | `export/linkedin-cover.png` |
| Your own profile | — | Experience → "Founder, Truebex" linked to the Page, so the Page shows a real person behind it |

---

## 5. X

**Bio** [101 / 160]

```
Explore ideas. Refine designs. Make better decisions before construction. Imagine More. Build Better.
```

| Field | Limit | Value |
|---|---|---|
| Name | 50 | Truebex |
| Handle | 4–15 | @truebex |
| Location | 30 | United Kingdom *(as §1)* |
| Website | — | the X link (§1) |
| Profile picture | 400 × 400 | `export/avatar.png` |
| Header | 1500 × 500 | `export/x-header.png` |
| Account type | — | Professional → category "Software Company" *(or nearest)* |

---

## 6. TikTok

Make it a **business account**.

**Bio** [56 / 80]

```
Explore more. Design better. Imagine More. Build Better.
```

| Field | Limit | Value |
|---|---|---|
| Name | 30 | Truebex |
| Username | 24 | @truebex |
| Website | — | the TikTok link (§1) *(a link may need a verified business account or more followers)* |
| Email | — | contact@truebex.com |
| Profile photo | 200 × 200 (upload 1080 × 1080) | `export/avatar.png` |

Every post that shows Truebex turns on the content disclosure setting "Your brand".

---

## 7. YouTube

Created 2026-10-16 (tracker, §13). Customization → Profile.

**Description** [529 / 1,000]

```
Welcome to Truebex — a building design platform built around exploring possibilities and making better design decisions before construction.

Discover product demonstrations, design workflows, feature walkthroughs, and ideas for architects, interior designers, property developers, and everyone shaping the built environment.

Truebex helps bring design ideas into context so teams and clients can better understand, evaluate, and refine the spaces they want to create.

Imagine More. Build Better.

Website: https://truebex.com/
```

| Field | Limit | Value |
|---|---|---|
| Channel name | 100 | Truebex |
| Handle | 3–30 | @Truebex |
| Links | 14 | title **truebex.com** → the YouTube link (§1); **Download for Windows** → `https://truebex.com/download/`; then each other profile as it goes live |
| Contact email | — | contact@truebex.com |
| Profile picture | 800 × 800 | `export/avatar.png` |
| Banner | 2560 × 1440, safe area 1546 × 423 in the centre | `export/youtube-banner.png` |
| Video watermark | 150 × 150 | `export/youtube-watermark.png` |

---

## 8. Threads

Threads uses your Instagram account: sign in with the **truebex** Instagram, so the name and photo come from
there.

**Bio** [130 / 150]

```
Better spaces begin with better decisions. Explore, refine, and shape your design before construction. Imagine More. Build Better.
```

| Field | Limit | Value |
|---|---|---|
| Link | — | the Threads link (§1) |
| Profile | — | public |

---

## 9. Pinterest

Make it a **business account** and claim the website (Settings → Claimed accounts → truebex.com; it gives a
meta tag or file to add to the site — ask and it goes into `VERIFICATION` like Google's and Bing's).

**Profile description** [181 / 500]

```
Ideas for better spaces start here. Explore architectural design, interior concepts, materials, and ways to refine a space before construction. Truebex — Imagine More. Build Better.
```

| Field | Limit | Value |
|---|---|---|
| Name | 65 | Truebex |
| Username | 30 | truebex |
| Website | — | the Pinterest link (§1) |
| Profile picture | 165 × 165 (upload 1080 × 1080) | `export/avatar.png` |
| First boards (later) | — | Interior concepts · Materials and finishes · Spaces designed in Truebex |

---

## 10. WhatsApp Business

Install the **WhatsApp Business** app with a number used only for Truebex (not your personal WhatsApp). The
link to share is `https://wa.me/<number in international format, no + or spaces>`.

**Business description** [153 / 512]

```
Truebex is a building design platform for architects, interior designers, and property developers. Contact us to learn more.

Imagine More. Build Better.
```

| Field | Limit | Value |
|---|---|---|
| Business name | — | Truebex *(cannot be changed often — get it right first time)* |
| Category | — | Software Company *(or the list's nearest: "Software" / "IT services")* |
| About | 139 | Imagine More. Build Better. [27] |
| Address | — | leave empty (no home address) |
| Email | — | contact@truebex.com |
| Websites (2) | — | the WhatsApp link (§1); `https://truebex.com/download/` |
| Profile photo | 640 × 640 | `export/avatar.png` |
| Catalogue | — | leave empty until prices are final |

**Greeting message** (sent to a new chat; English, then Arabic — check the Arabic before use)

> Hello, and thanks for contacting Truebex. Tell us how we can help — the app, your licence, a demo or plans
> for your team — and we'll reply as soon as we can.
>
> مرحبًا، وشكرًا لتواصلك مع Truebex. أخبرنا كيف يمكننا مساعدتك — التطبيق، أو ترخيصك، أو عرض توضيحي، أو خطط
> لفريقك — وسنرد عليك في أقرب وقت.

**Away message**

> Thanks for your message. We're away right now and will reply in our next working hours. For support you
> can also write to support@truebex.com.
>
> شكرًا لرسالتك. نحن خارج أوقات العمل الآن وسنرد في أقرب وقت. للدعم يمكنك أيضًا مراسلتنا على
> support@truebex.com.

**Quick replies**

| Shortcut | Message |
|---|---|
| `/download` | Download Truebex for Windows: https://truebex.com/download/ |
| `/pricing` | Plans and what each includes: https://truebex.com/pricing/ |
| `/support` | For help with the app or your licence, write to support@truebex.com with what you were doing and a screenshot. |
| `/demo` | We'd be glad to show you Truebex. Which days and times suit you, and what kind of projects do you design? |

---

## 11. Reddit

Create a profile for the brand (u/truebex). Post as a maker taking part in communities, never as an
advertiser; read each community's rules before the first post.

**Profile description** [193 / 200] — *your v2 text (223 without the website line) is over Reddit's 200;
shortened, same words:*

```
We’re building Truebex, a design platform for architects, interior designers and property developers: explore alternatives, refine spaces and make better-informed decisions before construction.
```

| Field | Limit | Value |
|---|---|---|
| Display name | 30 | Truebex |
| Social links | 5 | Website → the Reddit link (§1) *(the website goes here, not in the description)* |
| Avatar / banner | — | `export/avatar.png`, `export/reddit-banner.png` |

---

## 12. Company mailboxes

| Address | What it is for | Where it is shown |
|---|---|---|
| **contact@truebex.com** | general questions, press, partners, payment providers (Wayl, Paddle), Companies House's registered email | website contact section and footer, every profile, Wayl, store listings |
| **support@truebex.com** | people who use the app: install, licence, account, bugs | download page, in-app feedback replies, WhatsApp |
| **sales@truebex.com** | demos, plans, teams and organisations, Enterprise, suppliers | "Request a demo", pricing page (Team / Enterprise), LinkedIn |

### How the addresses work

Mail in: Cloudflare Email Routing sends contact@ and support@ to the `truebex-support` Worker (the Desk), and a
catch-all sends every other address to the same Worker, which forwards non-support mail to Gmail.

Mail out: Amazon SES in Frankfurt (eu-central-1), with production access. The truebex.com domain is verified, DKIM
is on, `bounce.truebex.com` is the MAIL FROM domain, and bounces and complaints go to the `truebex-ses-alerts`
topic.

The website shows `SITE.email` (contact@) and `SITE.supportEmail` (support@) from `src/lib/constants.ts`.

Still open: the API server's mail settings use **hello@truebex.com** (`MAIL_FROM`, `SUPPORT_EMAIL`, `ALERT_EMAIL` in
`infra/secrets/server.env.example`). Mail to hello@ reaches the catch-all, so it isn't lost, but customers see a
third address. Decide whether to move `SUPPORT_EMAIL` to support@truebex.com.

### Signatures

```
Truebex — Imagine More. Build Better.
truebex.com · contact@truebex.com
```

support@ and sales@ use the same with their own address. Add the legal name, company number and registered
office once the company exists (UK trading disclosures).

### Auto-replies

**support@**

> Thanks for writing to Truebex support. We've got your message and will answer within one working day.
> While you wait: the download page (https://truebex.com/download/) lists the latest release and what your
> computer needs.

**sales@**

> Thanks for your interest in Truebex. We'll reply within one working day to arrange a demo or answer your
> questions about plans and teams.

**contact@** — none (a person reads it).

*"Within one working day" is a promise: change it to what you can keep.*

---

## 13. The tracker

Update this table as each one is done. Login email = the address the account is registered with (not the
password).

| Platform | Handle | URL | Created | v2 text in | Login email | 2FA on | In `SOCIAL` |
|---|---|---|---|---|---|---|---|
| YouTube | @Truebex | https://www.youtube.com/@Truebex (ID: https://www.youtube.com/channel/UCDcvENr5BAZOJlmAa0B7q-Q) | 2026-10-16 | | | | yes |
| Facebook | TruebexOfficial | https://www.facebook.com/TruebexOfficial | | | | | yes |
| Instagram | truebex | https://www.instagram.com/truebex/ | | | | | yes |
| LinkedIn | truebex | Not confirmed: linkedin.com/company/truebex does not exist, and the Facebook page links a personal profile, /in/truebex | | | | | |
| X | @truebex | Taken by an unrelated account since 2014; the Facebook page links to it by mistake | | | | | |
| TikTok | @truebex | Taken by an unrelated account | | | | | |
| Threads | @truebex | | | | | | n/a (not in `SOCIAL` yet) |
| Pinterest | truebex | | | | | | n/a (not in `SOCIAL` yet) |
| Reddit | u/truebex | | | | | | n/a (not in `SOCIAL` yet) |
| WhatsApp Business | — | | | | | | n/a |
| contact@truebex.com | — | — | | — | — | | `SITE.email` |
| support@truebex.com | — | — | | — | — | | `SITE.supportEmail`; server `SUPPORT_EMAIL` is still hello@ |
| sales@truebex.com | — | — | | — | — | | |

`SOCIAL` lists LinkedIn, Instagram, YouTube, Facebook, TikTok and X, and the website shows the ones with a URL.
Threads, Pinterest, Reddit and WhatsApp need an entry before their links can show on the website.

---

## 14. Images (ready in `export/`)

Made by `make_brand_assets.py` from `brand.json`, `logo/`, `fonts/` and `images/`. Never edit an export by hand:
change the source and run the script again.

| File | Size | Use |
|---|---|---|
| `export/avatar.png` | 1080 × 1080 | every profile picture and logo (platforms downscale; the mark is 56 % of the width, so a circle crop keeps it whole) |
| `export/facebook-cover.png` | 1640 × 624 | Facebook cover |
| `export/linkedin-cover.png` | 1128 × 191 | LinkedIn cover |
| `export/x-header.png` | 1500 × 500 | X header |
| `export/youtube-banner.png` | 2560 × 1440 | YouTube banner (text inside the 1546 × 423 safe area) |
| `export/reddit-banner.png` | 1920 × 384 | Reddit banner |
| `export/youtube-watermark.png` | 150 × 150, transparent | YouTube video watermark |
| `export/lockup-dark.png` | 2000 × 1066 | the lockup on the ground: press, partner pages, listings |
| `export/lockup-grey.png`, `lockup-white.png` | 2000 px wide, transparent | the lockup over video or photos |
| `export/mark-dark.png` | 800 × 800 | the mark on the ground |
| `export/svg/` | vector | mark, wordmark and lockup in grey, white and dark |

TikTok, Threads, Pinterest and WhatsApp take only the avatar. Banners use only the one clean capture: no panels,
labels, cursor or debug text.
