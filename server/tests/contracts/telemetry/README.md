# Telemetry contract fixtures (`contracts/telemetry.md` §9)

Copied, never edited: the app side is authoritative for these files.

On 2026-10-09 the app repository had no `Docs/roadmap/fixtures/contracts/telemetry/` folder yet, so PF14
authored this set to the letter of `telemetry.md` v1.0.0 (§5, §6, §9) and staged it here. OP1 copies the
folder into `Docs/roadmap/fixtures/contracts/telemetry/` (or replaces it with its own, after which this
folder is re-copied from there).

| File | Holds |
|---|---|
| `config.json`, `config-off.json` | 5.1 with the allow-list of §6.1; the kill switch on |
| `events-batch.json`, `crash-report.json`, `feedback.json` | valid bodies of 5.2, 5.3's `report`, 5.4's `feedback` |
| `minidump-stub.dmp`, `screenshot.png` | a 44-byte synthetic minidump (header and one unused stream, no memory); a 320 × 200 window capture |
| `log-tail-raw.txt`, `log-tail-scrubbed.txt` | a tail holding a profile path, two project paths and an email, and the scrubber's exact expected output |
| `privacy-violations.json` | payloads the scanner must reject, each with the `data.field` it must name |

`install_id` in the bodies is derived from the install secret
`7d4e1f0a9b3c2d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6`: the first 32 hex of SHA-256 over
the secret's 32 raw bytes (`4a1ffea151643db7fe803e815865e053`).
