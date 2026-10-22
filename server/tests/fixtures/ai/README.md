# The platform's own ai-proxy stand-ins (PF11)

Not the contract's set: that is the app's own (AI3, ai-proxy 1.1.2 §9), copied byte for byte into
`../../contracts/ai-proxy/`. These are the three window turns PF11 wrote on 2026-10-10, when the app had no set yet,
with `server/scripts/make_ai_proxy_fixtures.py` (`--check` compares every file; standard library only). PF11b
(2026-10-22) moved them here when the app's set replaced PF11's; PF11's `models.json`, balances, `refusal.json`, 403
and 503 were superseded by the app's files and dropped. Fixture data, never public copy.

| File | Holds | Read by |
|---|---|---|
| `window/01-find.sse`, `window/02-place.sse`, `window/03-end.sse` | "Put a window on the north wall of the study, 1.2 m wide" as three streamed turns (`find`, `place`, `end_turn`) whose `usage` has cache read and write tokens, and the proxy's whole stream: each `truebex_credits` event (29, 9 and 5 credits from 4388, with `served_by`) is what the proxy itself sends for that usage, so a test compares the whole stream byte for byte | `test_ai_proxy.py`, `test_ai_credits.py` (through `fake.sse(name)` and `fixture_bytes`) |

They stay the platform's own while a test needs §6.2's cache arithmetic or a whole-stream comparison: the app's
turns carry no cache tokens, and their `truebex_credits` are the stub's.
