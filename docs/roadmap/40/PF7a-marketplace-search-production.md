# PF7a — Marketplace search on the production stack: Postgres full-text and picture-search model files on the VM (launch priority 2)

**Needs merged:** PF7, PF14 (both on `master` at 842768e). **Unblocks:** marketplace search after the cutover (`infra/CUTOVER.md`); picture search on the VM. **Contract:** `T:\unreal5_7_4_projects\truebex_compact\Docs\roadmap\40\contracts\marketplace-api.md` (1.1.0): no change, 5.3 answers keep their shape.

## Status

**Built on branch `ap/t41-pf7a-marketplace-search-on-the-p` (2026-10-11); see As-built.** Before this task, on `master` 842768e (verified with Grep and Read on 2026-10-11):

| Area | Where (master 842768e) | Before |
|---|---|---|
| Adapter choice | `server/app/market/search.py:117-121` (`index_for`) | FTS5 on SQLite, otherwise `LikeIndex` |
| `LikeIndex` | `server/app/market/search.py:91-114` | `ILIKE` on name, description, brand and SKU only; relevance is a word count. A search by material, variant option, category label, supplier, GTIN or classification code misses on Postgres what `document()` (`:124-143`) finds on SQLite: `test_market.py::test_search_filters_and_region_prices` (`q=linen`) fails with the app on Postgres |
| Index table | `server/app/market/models.py:508-524` | `market_search_fts` (FTS5) created and dropped by DDL events, `execute_if(dialect="sqlite")`; nothing for Postgres |
| The copy | `server/scripts/sqlite_to_postgres.py` | copies the mapped tables; the FTS5 table is not mapped, so nothing indexed the products on the target |
| Model files on the VM | `infra/host/compose.yaml` (api, worker), `server/Dockerfile`, `server/app/config.py:199-200` | no volume; `EMBEDDING_DIR` defaults to `./models`, not in the image; the deploy skill's Marketplace row: picture search off on the VM |
| Embedding existing products | `server/app/market/jobs.py:36-38`, `server/app/market/embeddings.py` (`embed_pending`) | the `market.embeddings` job (60 s) embeds every approved product with no vector for the model, 50 a run |

PF7's As-built carry-over handed "a Postgres full-text `SearchIndex` adapter … and the worker" to PF14, and the T28 merge "picture-search weights on the VM, since `EMBEDDING_DIR` is not a volume yet"; PF14 merged without either.

## Goal

Marketplace search works the same on the production stack (Postgres on the VM) as on SQLite: the same words find the same products, with the name counting more than the rest. Picture search can be switched on on the VM with three one-off steps the deploy skill lists.

## Read first

* `docs/roadmap/40/00-contract.md` P.2 to P.4; the As-built of `PF7-…md`, `PF8-…md` and `PF14-…md`.
* `server/app/market/search.py`, `models.py` (DDL at the end), `embeddings.py`, `jobs.py`; `server/scripts/sqlite_to_postgres.py`, `fetch_models.py`, `seed_market.py`.
* `infra/README.md` (Postgres tests), `infra/CUTOVER.md` (step 3), `infra/host/compose.yaml`, `server/Dockerfile`.
* `.claude/skills/truebex-deploy/SKILL.md` (*API*, *Secrets and switches*) and `server/tests/test_deploy_skill.py`.
* `server/tests/conftest.py` (`TEST_DATABASE_URL`, `TEST_APP_DATABASE_URL`).

## Scope

**In:**

1. `PgIndex` behind the `SearchIndex` protocol, picked by `index_for` on `postgresql`. Its own table: `product_id` key, `name`, `body`, and a tsvector weighting the name above the body, with a GIN index. DDL events create and drop it on Postgres only, as FTS5's do on SQLite. `match` keeps FTS5's behaviour: every word must match, prefix matching, name above body, case-insensitive. The `simple` configuration (multilingual catalogues, GB and AE). Accent-insensitive without a superuser extension. `LikeIndex` stays the fallback for other databases.
2. `scripts/sqlite_to_postgres.py`: the index is derived data, not copied; the copy rebuilds it with `market.search.rebuild`; the every-feature-table rule names it as derived.
3. Picture-search model files on the VM: one named volume in `api` and `worker` at the path `EMBEDDING_DIR` names (set in Compose's `environment`). The deploy skill's one-off steps: fetch the files into the volume with `scripts/fetch_models.py --dir <that path>` inside the image; `EMBEDDING_MODEL=clip-vit-b32` in `server.sops.env` and a restart; embeddings for existing products. `test_deploy_skill.py` names the steps.
4. No contract change: 5.3 answers keep their shape.

**Out (and where it goes):** a vector index (`ProductEmbedding` rows are enough at today's catalogue size; a later feature when the catalogue grows past about 50 000 products); `s3` media URLs (the media route already redirects for a non-local store); fixing the Postgres failures outside `server/app/market/` (listed in the As-built for the next plan review).

## Design

**API:** none added or changed. `GET /market/search` (5.3) and `POST /market/search/image` answer as before; `POST /admin/market/search/rebuild` (PF7) rebuilds whichever index the database has.

**Data:**

| Table | Database | Columns | Made by |
|---|---|---|---|
| `market_search_fts` | SQLite | FTS5: `product_id UNINDEXED, name, body`, `unicode61 remove_diacritics 2` | PF7, unchanged |
| `market_search_tsv` | Postgres | `product_id VARCHAR(32) PRIMARY KEY`, `name TEXT`, `body TEXT`, `tsv TSVECTOR GENERATED ALWAYS AS (setweight(to_tsvector('simple', name), 'A') \|\| setweight(to_tsvector('simple', body), 'B')) STORED`; GIN index `ix_market_search_tsv_tsv` on `tsv` | DDL events `after_create` / `before_drop` on `Base.metadata`, `execute_if(dialect="postgresql")` |

* `name` and `body` hold the **folded words** of `document()`'s two parts, not the original text: lower case, accents removed (`fold`: NFKD, combining marks dropped, NFC), split into `\w+` words exactly as `tokens()` splits a query, joined by spaces. So Postgres's parser sees the same words FTS5 sees ("2.5 L" is `2 5 l`, an e-mail or host is its parts), and accent folding needs no `unaccent` extension. Postgres keeps the tsvector itself.
* **Query:** `tokens(fold(q))` (at most 10 words; a word with no letter or digit, such as `___`, is dropped), each as a prefix, all required: `w1:* & w2:*` through `to_tsquery('simple', …)`. A word Postgres splits (`pr_40_50`) becomes a phrase, as in FTS5.
* **Rank:** `ts_rank('{0, 0, 0.1, 1}', tsv, q) × 20`: a name hit counts ten body hits (FTS5's bm25 column weights 10 : 1) and scores about 12, above 5.3's availability and rating boosts (at most 1.5), so text relevance leads on both databases.
* **Derived data:** `scripts/sqlite_to_postgres.py` names `DERIVED = ("market_search_fts", "market_search_tsv")` (FTS5's shadow tables carry its name); after the copy it runs `market.search.rebuild` on the target and prints `search index rebuilt: <n> products` before `ALL TABLES MATCH`.
* **Empty index at start:** `database.init_db` ends with `market.search.fill_if_empty(bind)`: an index that is empty while products exist is rebuilt (the VM's first start with PF7a, a restore). It runs after the migrations and the category seed; an index with rows is left alone. `rebuild` goes in key order, so the API's two processes and the worker starting together take the rows' locks in the same order.

**Infrastructure:**

* `infra/host/compose.yaml`: `api` and `worker` get `EMBEDDING_DIR: /app/models` in `environment` and `models:/app/models` in `volumes`; `models` is a top-level named volume. `/app/models` is the image's `./models` (config's default) and `fetch_models.py`'s default `--dir` in the image.
* `server/Dockerfile`: `mkdir -p /app/models && chown truebex:truebex /app/models` before `USER truebex`. Docker gives a new, empty named volume the owner of the folder it mounts on, so the non-root user can fetch into it. `server/.dockerignore` ignores a local `models` folder.

**Jobs:** none new. Switching the model on embeds the existing products: `market.embeddings` (worker, every 60 s) embeds every approved product without a vector for the model, 50 a run; `python -m app.worker --run market.embeddings` runs it at once.

**Deploy skill** (*API*): "Picture search, once per VM (PF7a)": (1) `docker compose exec api python scripts/fetch_models.py --dir /app/models`; (2) `sops infra\secrets\server.sops.env` → `EMBEDDING_MODEL=clip-vit-b32`, `infra\deploy.ps1`; (3) no command needed for existing products, `docker compose exec worker python -m app.worker --run market.embeddings` for the next 50 at once, and the check. "Marketplace search index (PF7a)": derived, no step; how it is filled and rebuilt. *Secrets and switches*: `EMBEDDING_DIR` is set by Compose; `EMBEDDING_MODEL` once the files are in the volume.

**Security and privacy:** no new data. The index holds catalogue text that 5.3 already serves publicly. Query words are bound as one parameter and hold no tsquery operator (`\w+` only). The model files come from Hugging Face over HTTPS into a volume only the two containers mount; no secret is involved.

## Deliverables

- [x] `server/app/market/search.py`: `PgIndex`, `fold`, `index_for` on `postgresql`, `fill_if_empty`, `rebuild` in key order
- [x] `server/app/market/models.py`: `PG_TABLE` and its DDL events (Postgres only)
- [x] `server/app/database.py`: one block at the end of `init_db` (`fill_if_empty`)
- [x] `server/scripts/sqlite_to_postgres.py`: `DERIVED`, the rebuild after the copy, `Report.indexed`
- [x] `infra/host/compose.yaml`: the `models` volume and `EMBEDDING_DIR` in `api` and `worker`; `server/Dockerfile`, `server/.dockerignore`
- [x] `.claude/skills/truebex-deploy/SKILL.md`: picture search once per VM, the search index, `EMBEDDING_DIR`
- [x] `infra/CUTOVER.md` (the rebuild line), `infra/README.md` (Postgres tests, the volume), `infra/secrets/server.env.example` (a comment)
- [x] `server/tests/test_market_production.py` (17 tests, 10 `postgres`-marked); `server/tests/test_deploy_skill.py` (+1)
- [x] `README.md`: section "Marketplace search on Postgres (PF7a)"; this doc; the PF7a row in `docs/roadmap/40/README.md`

## Tests

| Name | Kind | Asserts |
|---|---|---|
| `test_index_for_picks_fts5_on_sqlite_and_pg_index_on_postgresql` | pytest | `Fts5Index` on SQLite, `PgIndex` on a `postgresql+psycopg` engine (no server needed), `LikeIndex` on any other dialect |
| `test_fold_drops_case_and_accents` | pytest | Latin accents and case; Arabic hamza and short vowels |
| `test_sqlite_has_only_the_fts5_index` | pytest | `market_search_fts` on SQLite, no `market_search_tsv` |
| `test_pg_index_table_created_and_dropped_on_postgresql_only` | pytest, postgres | `init_db` twice; columns, primary key, a GIN index on `tsv`, no FTS5 table; `drop_all` drops it |
| `test_pg_index_finds_the_fixture_by_its_whole_document` | pytest, postgres | the fixture catalogue by a material (`linen`, `ash`), category labels (`seating`, `coffee tables`, `decoration`), variant options, a GTIN, a classification code, the supplier's name (renamed, so not the brand) |
| `test_pg_index_prefix_case_and_accents` | pytest, postgres | `lin`, `LINEN`, `coff tab`, `pr_40_5`, `línen`; `Café crème` found by `cafe creme` and `CAFÉ`; punctuation-only queries match nothing |
| `test_pg_index_needs_every_word` | pytest, postgres | `oak linen` → the sofa; `oak ash` → none |
| `test_pg_index_ranks_a_name_hit_above_a_body_hit` | pytest, postgres | `oslo`, `chalk`: the name hit scores above the theme's body hit; 5.3 lists the sofa first in GB and AE |
| `test_pg_index_reindex_after_a_text_change_and_remove` | pytest, postgres | after a rename, the old description no longer matches and the new name does; `remove`; `rebuild` |
| `test_search_answers_alike_on_sqlite_and_postgres` | pytest, postgres | 11 queries through `search.search` on both databases: same keys, same product sets, same facets |
| `test_empty_index_filled_at_start_on_sqlite` / `_on_postgres` | pytest (+ postgres) | an emptied index is refilled by the next `init_db`; an index with rows is left alone; drafts are indexed too |
| `test_sqlite_to_postgres_copies_or_derives_every_table` / `test_postgres_tables_are_copied_or_derived` | pytest (+ postgres) | every table `init_db` makes is copied (`_models()`) or in `DERIVED` |
| `test_sqlite_to_postgres_rebuilds_the_search_index` / `_on_postgres` | pytest (+ postgres) | the fixture catalogue copied: `report.indexed == 6`, the line before `ALL TABLES MATCH`, the target finds `linen` |
| `test_compose_mounts_one_model_volume_at_embedding_dir` | pytest | parsed YAML: `api` and `worker` mount the same named volume at their `EMBEDDING_DIR`; the local trial keeps it; the Dockerfile makes and chowns that folder before `USER` |
| `test_deploy_skill_picture_search_steps` | pytest | the skill's *API*: `fetch_models.py --dir` at Compose's `EMBEDDING_DIR`, `server.sops.env … EMBEDDING_MODEL=clip-vit-b32`, `--run market.embeddings` (a registered job), in that order; `market_search_tsv` and the rebuild route named |

## Human test

Window 1, in the worktree: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\autopilot-serve.ps1` serves `out/`; no page changed in this feature, so the steps below use the local API.

1. A disposable Postgres (this PC has Postgres 17), in PowerShell window 2:
   `$pg='C:\Program Files\PostgreSQL\17\bin'; $d="$env:TEMP\pf7a-pg"; Set-Content "$env:TEMP\pf7a-pw.txt" 'pf7a-local'`
   `& "$pg\initdb.exe" -D $d -U truebex --pwfile="$env:TEMP\pf7a-pw.txt" -A scram-sha-256 -E UTF8 --locale=C`
   `Add-Content "$d\postgresql.conf" "port = 55470"; & "$pg\pg_ctl.exe" -D $d -l "$d\log.txt" -w start`
   `$env:PGPASSWORD='pf7a-local'; & "$pg\createdb.exe" -h 127.0.0.1 -p 55470 -U truebex pf7a_test; & "$pg\createdb.exe" -h 127.0.0.1 -p 55470 -U truebex pf7a_api` → "server started".
2. Same window, `cd server`: `$env:TEST_DATABASE_URL='postgresql+psycopg://truebex:pf7a-local@127.0.0.1:55470/pf7a_test'; .venv\Scripts\python.exe -m pytest -q -m postgres -k market` → `10 passed` (and the rest deselected).
3. An API on that Postgres: `$env:DATABASE_URL='postgresql+psycopg://truebex:pf7a-local@127.0.0.1:55470/pf7a_api'; $env:STORAGE_DIR='./pf7a-try-storage'; .venv\Scripts\python.exe scripts\seed_market.py` → `supplier Nord Living (f8afe1ba…): verified`, a feed line `6 rows, 2 created, …`, six products `approved` and the Bergen lounge chair `pending_review` (not searchable until an admin approves it). Then `Start-Process -WorkingDirectory $PWD .venv\Scripts\python.exe '-m uvicorn app.main:app --port 8000'` and `curl.exe -s "http://127.0.0.1:8000/market/search?q=linen&region=GB"` → one result, `"name":"Oslo 3-seater sofa"`, a GBP price. `q=seating`, `q=9501101530003` and `q=lin` give the same sofa; `q=coff%20tab` gives the two coffee tables.
4. Close the API window. The same against SQLite: `$env:DATABASE_URL='sqlite:///./pf7a-try.db'; .venv\Scripts\python.exe scripts\seed_market.py`, start the API again as in 3, and the same `curl.exe` lines → the same products. Close the API window.
5. On a PC with Docker, in the worktree: `docker compose --env-file infra/host/local/compose.trial -f infra/host/compose.yaml -f infra/host/compose.local.yaml config` → no error; under `api` and `worker`: `EMBEDDING_DIR: /app/models` and a volume `source: models`, `target: /app/models`; `models` under the top-level `volumes`. (The production file alone needs the VM's `secrets/` files and `API_IMAGE`; the trial overlay supplies local ones.)
6. Clean up: `& "$pg\pg_ctl.exe" -D $d -m fast stop; Remove-Item -Recurse -Force $d, server\pf7a-try.db, server\pf7a-try-storage`.

## Risks / traps

* **Ranking is close, not identical.** FTS5's bm25 weighs rare words and short documents; `ts_rank` (normalisation 0) does neither. The same query finds the same products on both databases and a name hit leads on both, but products that match equally may come in a different order (`nord living` in the self-test).
* **The words in the index are folded.** `market_search_tsv.name` / `body` are lower-case and accent-free word lists, not the product's text; read the products for display, never the index.
* **A new column on `products`, `product_variants`, `suppliers` or `market_categories`** must reach `_ADDED_COLUMNS` as usual: `fill_if_empty` reads them through the ORM after `_migrate`, so it runs after the migrations by design.
* **Postgres's own parser would split differently** ("2.5", hosts, e-mails as single tokens); that is why the words are split in Python first. Do not feed raw text to `to_tsvector` in a later change.
* **The `models` volume's owner** comes from the image's `/app/models` only when the volume is first created. A volume made before this image (for example by hand as root) needs `docker compose exec -u root api chown truebex:truebex /app/models` once.
* **`EMBEDDING_MODEL=clip-vit-b32` before the files exist**: the process logs a warning and keeps picture search off until it restarts (the embedder is cached per process). Fetch first, then switch on and deploy, as the skill orders it.
* No Docker on this PC: `docker compose config` and the image's folder ownership are exercised by the owner's Docker PC or the VM; the YAML shape is checked by pytest.

## As-built

* **Date, branch, commits:** 2026-10-11, `ap/t41-pf7a-marketplace-search-on-the-p` from `master` 0e3b88a (842768e + the autopilot setup fix). `ad934d2` (PgIndex, DDL, `fill_if_empty`, the copy script, Compose volume, Dockerfile, tests), then the commit with the skill, infra docs, README, this doc and the tracker row.
* **Counts:**
  * pytest collected 549 → 567 (`test_market_production.py` 17, of which 10 `postgres`-marked; `test_deploy_skill.py` +1). On SQLite (the verify gate) the 10 skip.
  * With `TEST_DATABASE_URL` on a local Postgres 17.10: `pytest -m postgres -k market` → 10 passed.
  * The whole suite with the app on Postgres 17.10 (`TEST_APP_DATABASE_URL` + `TEST_DATABASE_URL`, session time zone Asia/Baghdad on purpose, three groups in parallel on separate databases): **503 passed, 3 failed, 61 skipped** of 567. The skips are the site tests (`out/` not built for this run; they read no database) and the SQLite-only parameter of `test_usage_record_upsert_sqlite_and_postgres`. Every market and supplier test passed except `test_feed_source_daily_pull` (below). The existing market tests went through `PgIndex`.
  * Baseline: the same market and supplier files on Postgres with master's `LikeIndex` forced back in → `test_market.py::test_search_filters_and_region_prices` fails (`q=linen` finds nothing); with `PgIndex` it passes.
* **Postgres failures outside `server/app/market/`, for the next plan review (not fixed here):** all three pass with `PGTZ=UTC` (the VM's Postgres runs in UTC) and fail only when the session's time zone is not UTC. Each test reads a `timestamptz` that Postgres returns in the session's zone, then relabels it as UTC with `.replace(tzinfo=timezone.utc)` or formats it in that zone:
  * `tests/test_billing.py::test_wayl_checkout_and_verified_webhook` (the known one, T36 fixes it);
  * `tests/test_billing_pf2b.py::test_eu_withdrawal_flow` (expects `15:06` where the e-mail correctly says `12:06 UTC`);
  * `tests/test_supplier_feeds.py::test_feed_source_daily_pull` (`row.next_pull_at.replace(tzinfo=timezone.utc)`: 05:00+03:00 read as 05:00 UTC; the stored value is right).
* **Self-tests beyond pytest:** two real API processes (uvicorn) seeded with `seed_market.py`, one on Postgres 17 and one on SQLite, asked `GET /market/search?region=GB` with `linen`, `seating`, `9501101530003`, `coff tab`, `nord living`, `oslo`, `línen`, `LINEN` and `Pr_40_50`: the same products from both every time (the six products for `nord living`, in a different order; the sofa before the theme for `oslo`), `X-Truebex-Contract: marketplace-api/1.1`. No Docker here: `docker compose config` was not run (pytest parses the YAML).
* **Deviations and why:**
  1. *An empty index is filled at start* (`search.fill_if_empty`, one block at the end of `database.init_db`). The VM may already hold products when PF7a is first deployed (the staging rehearsal of the cutover), and a restore brings products without an index; without it Postgres search would find nothing until someone rebuilt the index. It runs after the migrations and the category seed (the rebuild reads products and labels through the ORM), so it is not a DDL event.
  2. *Accents folded in Python, not by `unaccent`.* `unaccent` is a trusted extension from Postgres 13, but it still has to be created in each database and its function cannot sit in a generated column. Folding in Python (`fold`) needs no extension, no superuser, and is the same on the index and the query side. It also folds Arabic hamza and short vowels.
  3. *Words split in Python before Postgres sees them* (Design, Data): Postgres's parser keeps "2.5", host names and e-mail addresses as single tokens, where FTS5 and `tokens()` split them, so a GB search for `5` or `example` would have differed.
  4. *Rank scale.* `ts_rank` × 20 with weights A 1, B 0.1: Scope said "name weighted above body"; the scale keeps text relevance ahead of 5.3's availability and rating boosts, as on SQLite.
  5. *Existing products' embeddings need no new command.* `market.embeddings` already embeds every approved product without a vector for the model (50 a minute); `test_market_admin.py::test_market_image_search_stub` shows it for the stub model. The skill names the job and `--run` for doing the next 50 at once.
  6. *The volume path* is `/app/models`, the config default `./models` in the image's working directory and `fetch_models.py`'s default `--dir` there, so a command without `--dir` lands in the volume too. The Dockerfile makes that folder for `truebex`, so the volume is writable by the non-root user (Docker copies the owner to a new volume).
  7. *Supplier-name test.* The fixture's brand equals its supplier's name, so the test renames the supplier to prove the supplier's name is indexed on its own.
* **Contract:** none changed; no §11 row is added (no endpoint). 5.3's keys, product sets and facets are equal on both databases (`test_search_answers_alike_on_sqlite_and_postgres`).
* **Carry-over → which feature:**
  * The owner, once per VM after deploying this: the three picture-search steps in the deploy skill (*API*), when picture search should go live.
  * The next plan review: the three time-zone test failures above.
  * Later, when the catalogue grows past about 50 000 products: a vector index for picture search (pgvector or similar) and a look at `ts_rank_cd` / normalisation for long descriptions.
