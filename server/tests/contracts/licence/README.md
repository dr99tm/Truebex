# Licence contract fixtures (licence-api.md v1.0.0, §9)

Made by PF1 on 2026-10-09 with `server/scripts/make_licence_fixtures.py` (deterministic: re-running
reproduces these bytes). From the merge on, the master copy is the app repo's
`Docs/roadmap/fixtures/contracts/licence/`; the platform keeps a copy here, copied, never edited.

| File | Holds |
|---|---|
| `keys.json` | the TEST key pair, kid `test-2026-10`; `private_key` is the 32-byte Ed25519 seed (base64url), worthless outside tests |
| `entitlement-<name>.json` | `{note, stub_now, canonical, envelope}`: `envelope` is the 5.5 `entitlement` exactly as served, `canonical` the RFC 8785 text of `envelope.document`, `stub_now` the clock the stub pins |
| `link-*.json`, `activate-*.json`, `account-pro.json`, `devices.json`, `releases-*.json` | responses as `{http_status, body}`; errors use the shared §7 envelope |
| `installer-stub.bin` | the 4 KiB "installer" whose size and SHA-256 the release manifests state |
| `jcs-cases.json` | hand-written RFC 8785 results for the escapes §6.2 names (both canonicalisers must match) |

Every signature is by the TEST key. `entitlement-tampered.json` was signed as Pro and then edited to
Enterprise, so it must fail; `entitlement-expired.json` expired before `stub_now`. Release notes are
fixture text, never public copy.
