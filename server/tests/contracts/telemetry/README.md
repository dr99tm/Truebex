# Telemetry contract fixtures (`contracts/telemetry.md` §9)

Copied, never edited: the app side is authoritative for these files (C.9).

This set is OP1's, from the app repository's `Docs/roadmap/fixtures/contracts/telemetry/` on `main` at
`90799860` (2026-10-13, Autopilot T158; `telemetry.md` 1.0.1). It replaced the set PF14 authored here on
2026-10-09 (PF14d). Re-copy after the app changes the folder:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\sync-contract-fixtures.ps1 -Contract telemetry
```

The script reads the files as committed on the app's `main` (`git archive`; the app checkout on the owner's PC
has `core.autocrlf=true`, so its working tree holds CRLF copies of these LF files), checks every copy against
the app's git blob id, and keeps this README. `.gitattributes` keeps the folder `-text`.

| File | Holds |
|---|---|
| `config.json`, `config-off.json` | 5.1 with the allow-list of §6.1; the kill switch on and off |
| `events-batch.json`, `crash-report.json`, `feedback.json` | valid bodies of 5.2, 5.3's `report`, 5.4's `feedback` |
| `minidump-stub.dmp`, `screenshot.png` | a 746-byte synthetic minidump (4 streams, no memory); a 64 × 36 window capture |
| `log-tail-raw.txt`, `log-tail-scrubbed.txt` | a tail holding a profile path, project paths, an email, the machine and the user, and the scrubber's exact output |
| `scrub-context.json` | the profile folder, user, machine and project folders `log-tail-raw.txt` was written with |
| `privacy-violations.json` | `{"cases": [{name, endpoint, field, payload}]}`: payloads the scanner must refuse, each with the `data.field` it must name |

The bodies name the installation `3f2a9c1e7b4d4e0f8a6b5c4d3e2f1a0b`, not derived from a secret here; the 5.5
tests use their own secret and derive its id as the app does (SHA-256 over the 64 hex characters).
