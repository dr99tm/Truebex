# Truebex for Android — Play listing (English)

Ready to paste into the Play Console (Store presence → Main store listing). Brand rules:
`.claude/skills/truebex-brand-voice` — no other product named, only what the app does. The lengths are
checked by `server/tests/test_pf10_clients.py::test_store_listing_assets`.

| Field | Value |
|---|---|
| App name | Truebex |
| Package | `com.truebex.app` |
| Category | Productivity (the owner may prefer Art & Design) |
| Contact e-mail | the address on https://truebex.com/privacy/ |
| Website | https://truebex.com/ |
| Privacy policy | https://truebex.com/privacy/ |

## Short description

Open your Truebex projects on your phone: walk the panoramas, edit offline.

## Full description

Your Truebex projects, on your phone — with or without a signal.

Walk the panoramas
Open a project you own or one shared with you and look around its cloud panoramas: drag, or tilt the phone, and tap a label to go to the next room. When the project changes, only the new parts of the panorama download.

Rooms and products
See the rooms of each storey with their areas, themes and floor finishes, and the products placed in each room with their prices for the project's region.

Light edits, saved to the project
Change a floor or wall finish, apply a room theme, move a product by 50 or 250 mm, slide a door or a window along its wall, or swap a product for another of the same kind. Each edit is saved to the project's history in the cloud, with your name on it.

Made for site visits
The projects you open stay on the phone: their history, their room list and the panoramas you looked at. Star a project to keep its panoramas ready before you leave the office. Edits made without a signal wait on the phone and go out by themselves when the network returns, even with the app closed.

Nothing changes behind your back
If someone else changed the same wall or product first, you see who it was, and your edit is replaced rather than mixed in. The history lists who changed what, and when; People shows who else has the project open.

Your account, your data
Sign in with your Truebex account or with Google. The session stays in the phone's encrypted storage, the app sends no usage data and shows no ads, and signing out removes your projects and panoramas from the phone.

You need a Truebex account and a project saved to the cloud from the Truebex desktop app.

## Graphics

| Asset | File | Rule |
|---|---|---|
| App icon | `icon-512.png` | 512 × 512, 32-bit PNG, full square (Play applies the mask) |
| Feature graphic | `feature-graphic-1024x500.png` | 1024 × 500 |
| Phone screenshots | `screenshots/01-panorama.png` … `05-projects.png` | 1080 × 2160 (≤ 2:1), portrait, 2–8 |

Made by `py -3.12 scripts/make_android_assets.py --store <captures>` from phone captures
(`adb exec-out screencap -p`).

## Before submitting (owner, GD4)

1. Retake the panorama screenshots and the feature graphic once a real cloud render exists (CL3): the
   captures of 2026-10-11 show the stand-in renderer's test faces.
2. The claims above about the desktop app and cloud panoramas following the phone's edits need the app
   side (CL1 applies `action` operations, CL4 re-renders): submit when those rows are merged.
3. Play Console account, the upload key (`mobile/android/android/key.properties`), the Android OAuth
   client with the release key's SHA-1 in the Google Cloud project of the Web client id, and Play's
   current target API level (GD4).
4. Data safety and content rating: `data-safety.md`, `content-rating.md`.
