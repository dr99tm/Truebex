# AI-proxy contract fixtures (`contracts/ai-proxy.md` v1.0.0, §9)

Copied, never edited: the app side is authoritative for these files.

On 2026-10-10 the app repository had no `Docs/roadmap/fixtures/contracts/ai-proxy/` folder yet (AI3 creates it),
so PF11 wrote this set to the letter of `ai-proxy.md` §5, §6.2, §7 and §9 with
`server/scripts/make_ai_proxy_fixtures.py` (deterministic) and staged it here. AI3 copies the folder into the app
repo (or replaces it with its own, after which this folder is re-copied).

| File | Holds |
|---|---|
| `models.json`, `balance-studio.json`, `balance-empty.json` | 5.1 and 5.2 answers (Studio, 4388 of 5000 credits left; and empty) |
| `window/01-find.sse`, `window/02-place.sse`, `window/03-end.sse` | "Put a window on the north wall of the study, 1.2 m wide" as three streamed turns: `find`, then `place`, then `end_turn`; each `truebex_credits` event follows from the turn's usage at the 5.1 rates (29, 9, 5 credits: 4388 -> 4345) |
| `refusal.json`, `credits-exhausted.json`, `upstream-busy.json` | a model refusal (non-streamed), the 403, a 503 with `retry_after_s` |

The `.sse` files hold the exact bytes the proxy sends (LF line ends; `.gitattributes` keeps them as written). The
platform's fake provider (`server/tests/fakes/fake_provider.py`) serves them as the upstream without their
`truebex_credits` events, which the proxy inserts itself before `message_stop`.
