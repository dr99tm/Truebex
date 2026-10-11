# Truebex for Android — Data safety form answers

Play Console → App content → Data safety. The answers describe the app as built (PF10) and match the
privacy policy at https://truebex.com/privacy/ (its "Android app" section).

## Overview

| Question | Answer |
|---|---|
| Does your app collect or share any of the required user data types? | Yes (collects; shares none) |
| Is all of the user data collected by your app encrypted in transit? | Yes: HTTPS only (the release build allows no cleartext except the phone's own loopback address, which never leaves the device) |
| Do you provide a way for users to request that their data is deleted? | Yes: by e-mail to the address in the privacy policy; signing out also deletes everything the app keeps on the phone |

## Data types collected

| Category · type | Collected | Shared | Optional | Purpose | Notes |
|---|---|---|---|---|---|
| Personal info · Email address | Yes | No | No (the account) | Account management | Sign-in with e-mail and password, or with Google |
| Personal info · Name | Yes | No | Yes | Account management | The account's display name, shown to the people on a shared project |
| App activity · Other user-generated content | Yes | No | No | App functionality | The edits the person makes (finish, theme, move, swap) are saved to their project |
| Device or other IDs | Yes | No | No | App functionality | A random id per installation and project (`replica_id`) that orders the phone's edits; not tied to the hardware, not an advertising id |

Not collected: location, contacts, photos or files from the phone, financial info, health, messages,
audio, web history, app interactions or diagnostics. The app has no analytics, no crash reporter, no
advertising and no third-party SDK that collects data.

## Security practices

* Data is encrypted in transit (HTTPS).
* The session token is kept in the phone's encrypted storage, backed by the Android Keystore; the app's
  data is excluded from cloud backups and device transfers.
* Data is not sold and is not shared with third parties; no tracking.
* Deletion: e-mail the address in the privacy policy to delete the account and its data; sign out to
  remove the projects, edits not yet sent and panorama tiles from the phone.
