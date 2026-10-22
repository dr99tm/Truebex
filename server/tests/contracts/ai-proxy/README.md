# AI-proxy contract fixtures (`contracts/ai-proxy.md` 1.1.2, §9)

The app's own set (AI3), copied, never edited: the app side is authoritative for these files. They come from app
commit a3fd173a0 (T183, AI5 meeting AI3: contract 1.1.1 added `create/`), the folder's last commit on the app's
main; 1.1.2 (T184, AI7's tool-less summaries) is wording only and moved no file. Copied on 2026-10-22 from app main
7fdde1e6f with `scripts\sync-contract-fixtures.ps1 -Contract ai-proxy` (the committed blobs, LF, each blob id
checked); the folder's git tree is 907992a92. `server/tests/test_pf11b_ai_proxy_1_1.py` pins every blob id and the
tree id. This README is the platform's own and is kept by the sync script.

PF11 staged a stand-in set here on 2026-10-10, when the app had none. PF11b (2026-10-22) re-copied the app's over it;
PF11's three window turns, which some tests still read for their cache tokens, moved to `../../fixtures/ai/`.

| File | Holds | Read by |
|---|---|---|
| `models.json` | 5.1: `truebex-assist`, and `truebex-fast` (the stub's alias: the platform serves `truebex-assist` only until GD7) | `test_pf11b` (keys and types per model), `test_ai_proxy.py` |
| `balance-studio.json`, `balance-low.json`, `balance-empty.json` | 5.2 for 4388, 412 and 0 of 5000 credits, with the stub's example `top_up_url` and `usage_url` | `test_pf11b` (keys and types), `test_ai_proxy.py` |
| `count.json` | 5.4 | `test_pf11b` (keys and types) |
| `window/`, `paint/`, `echo/`, `create/` | the four scripted conversations: a `script.json` each (`truebex-ai-proxy-script/1`: the `match` words, then `turns`, each an `sse` file and an optional `capture`) and its `.sse` turns | `test_pf11b` (each played through `POST /ai/messages`), `server/scripts/fake_ai_upstream.py` |
| `refusal.sse` | a streamed `stop_reason: "refusal"` | `test_pf11b` |
| `credits-exhausted.json`, `plan-required.json`, `unauthenticated.json`, `rate-limited.json`, `upstream-busy.json`, `server-error.json`, `too-large.json` | the §7 envelopes the stub's variants answer | `test_pf11b` (code, status, data keys) |

How the platform reads them:

* The `.sse` files are the exact bytes the stub sends. The fake provider (`server/tests/fakes/fake_provider.py`)
  serves them as the upstream without their `truebex_credits` event, which the proxy inserts itself before
  `message_stop`.
* `${wall}` (`window/02-place.sse`) and `${room}` (`paint/02-fill.sse`) sit inside `tool_use` `partial_json`; the
  fake fills them as the stub does, from the `capture` of the earlier turn: the dotted path read from the
  `tool_result` the proxy forwarded. `${remaining}` sits only in `truebex_credits`, which the fake drops.
* Each file's `truebex_credits` is the stub's own ledger. The proxy charges §6.2 from the turn's `usage` at
  `truebex-assist`'s rates: window 22, 23, 24 (the files say 21, 16, 9), paint 21, 23, 23 (24, 19, 11), echo 4 (2),
  create 26, 29 (38, 12), refusal 6 (3).
* `message_start` carries the alias (`truebex-assist`) where a provider names its model; the proxy relays it
  untouched. The files carry no cache token counts.
