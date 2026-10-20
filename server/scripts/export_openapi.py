"""Write the OpenAPI documents cut from the app's own: `openapi/v1.json` (PF12) and `openapi/clients.json` (PF10).

    server\\.venv\\Scripts\\python.exe server\\scripts\\export_openapi.py --v1
    server\\.venv\\Scripts\\python.exe server\\scripts\\export_openapi.py --v1 --check   (exit 1 on drift)
    server\\.venv\\Scripts\\python.exe server\\scripts\\export_openapi.py --clients
    server\\.venv\\Scripts\\python.exe server\\scripts\\export_openapi.py --clients --check

`--v1` is the developer API: the app's own OpenAPI output cut to what an API
key reaches: `/v1/…`, the marketplace reads (5.1-5.6, a key optional) and the
supplier feeds (5.11-5.13), with only the schemas those name. Each operation
carries `x-truebex-scope` (and `x-truebex-auth: optional` where a key is
optional). The SDKs (scripts/gen-sdks.ps1) and the /developers/ reference
tables are generated from this file; tests/test_pf12_openapi_sdks.py fails when
it is not current. Bump API_VERSION's MINOR when the document grows.

`--clients` is the document of the routes the light clients call — the mobile
web client (PF9) and the Android app (PF10) — with the answers they read
(`app/mobile/clients.py`), each operation tagged with the contract it speaks
(`x-truebex-contract`). PF9's TypeScript types and PF10's Dart client are
generated from it (scripts/gen-clients.ps1); tests/test_pf10_clients.py fails
when the file is not current.
"""

import argparse
import copy
import json
import os
import sys
from pathlib import Path

SERVER = Path(__file__).resolve().parents[1]
ROOT = SERVER.parent
OUT = ROOT / "openapi" / "v1.json"
API_VERSION = "1.1.0"
BASE_URL = "https://api.truebex.com"
CLIENTS_OUT = ROOT / "openapi" / "clients.json"
CLIENTS_VERSION = "1.0.0"

# Routes of PF7 and PF8 that belong to the developer API: (method, path) →
# (operation id, scope, the key optional).
MARKET = {
    ("get", "/market/categories"): ("market_categories", "market:read", True),
    ("get", "/market/regions"): ("market_regions", "market:read", True),
    ("get", "/market/search"): ("market_search", "market:read", True),
    ("get", "/market/products/{product_id}"): ("market_product", "market:read", True),
    ("post", "/market/prices"): ("market_prices", "market:read", True),
    ("get", "/market/suppliers/{supplier_id}"): ("market_supplier", "market:read", True),
    ("post", "/market/feeds"): ("feeds_upload", "supplier:feed", False),
    ("put", "/market/feeds/source"): ("feeds_set_source", "supplier:feed", False),
    ("get", "/market/feeds/{feed_id}"): ("feeds_get", "supplier:feed", False),
}
# The contract each group speaks; the SDKs send it as X-Truebex-Contract
# (tests/test_pf12_openapi_sdks.py checks the routes echo the same).
CONTRACTS = {
    "projects": "project-log/1.2",
    "jobs": "render-jobs/1.1",
    "uploads": "share-bundle/1.1",
    "shares": "share-bundle/1.1",
    "market": "marketplace-api/1.1",
    "feeds": "marketplace-api/1.1",
}
# What each of those operations does (PF7's and PF8's routes carry no docstring).
MARKET_TEXT = {
    "market_categories": "The category tree, rooted on the app's own taxonomy (5.1); ETag, cached a day.",
    "market_regions": "Regions with their currency, tax and delivery rules (5.2).",
    "market_search": "Products by text, category, region, price and availability (5.3); prices in minor units.",
    "market_product": "One product: variants, geometry, the region's price and availability (5.4).",
    "market_prices": "Prices and availability of up to 500 lines for a region, to re-price a project (5.5).",
    "market_supplier": "A verified supplier's profile (5.6).",
    "feeds_upload": "Upload a catalogue feed, CSV or JSON, up to 50 MB (5.11); answers 202 with the run.",
    "feeds_set_source": "Register an https URL the platform pulls daily at 02:00 UTC (5.12).",
    "feeds_get": "A feed run's import report, with up to 200 row errors (5.13).",
}
# Generated component names that would read badly in the SDKs.
RENAME = {"Body_post_feed_market_feeds_post": "FeedUpload", "FeedSourceIn": "FeedSourceRequest"}
TAG_TEXT = {
    "account": "Check a key: its owner, plan, scopes and usage.",
    "projects": "Cloud projects: the operation log, snapshots, versions, members, presence, comments and followed panorama sets (contract project-log).",
    "jobs": "Render jobs and exports (contract render-jobs); `pack` gives the sheet PDF, renders, panoramas and the bill of quantities.",
    "uploads": "Content-addressed uploads in 8 MiB parts, resumable (contract share-bundle §5).",
    "shares": "Share links from a bundle: create, publish, visits, expiry, revoke (contract share-bundle).",
    "market": "The marketplace catalogue: categories, regions, search, products, prices, suppliers. A key is optional and lifts the anonymous limit.",
    "feeds": "A supplier's catalogue feed: upload, a URL pulled daily, the import report (supplier:feed).",
    "webhooks": "Endpoints that receive signed events (Standard Webhooks): deliveries, re-send, secrets.",
}


def _env() -> None:
    # Importing the app reads settings; none of them shape the document.
    os.environ.setdefault("SECRET_KEY", "export-openapi-only-not-a-secret-0123456789")
    sys.path.insert(0, str(SERVER))


def _refs(node, found: set[str]) -> None:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            found.add(ref.rsplit("/", 1)[1])
        for value in node.values():
            _refs(value, found)
    elif isinstance(node, list):
        for value in node:
            _refs(value, found)


def _rewrite_refs(node, mapping: dict[str, str]):
    if isinstance(node, dict):
        out = {}
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str) and value.startswith("#/components/schemas/"):
                name = value.rsplit("/", 1)[1]
                out[key] = "#/components/schemas/" + mapping.get(name, name)
            else:
                out[key] = _rewrite_refs(value, mapping)
        return out
    if isinstance(node, list):
        return [_rewrite_refs(v, mapping) for v in node]
    return node


def build() -> dict:
    _env()
    from pydantic.json_schema import models_json_schema

    from app import scopes
    from app.config import Settings
    from app.main import app
    from app.routers.v1 import models
    from app.webhooks import delivery, events

    app.openapi_schema = None
    full = copy.deepcopy(app.openapi())
    schemas = full["components"]["schemas"]

    # The marketplace answers, documented (PF7/PF8 return plain dicts).
    _, defs = models_json_schema(
        [(m, "validation") for m in [*models.MARKET_RESPONSES.values(), models.ErrorEnvelope]],
        ref_template="#/components/schemas/{model}",
    )
    for name, body in defs.get("$defs", {}).items():
        schemas.setdefault(name, body)

    paths: dict = {}
    for path, item in full["paths"].items():
        for method, op in item.items():
            if path.startswith("/v1/"):
                group = op["operationId"].split("_", 1)[0]
            elif (method, path) in MARKET:
                op_id, scope, optional = MARKET[(method, path)]
                op["operationId"] = op_id
                op["description"] = MARKET_TEXT[op_id]
                op["x-truebex-scope"] = scope
                if optional:
                    op["x-truebex-auth"] = "optional"
                group = op_id.split("_", 1)[0]
                model = models.MARKET_RESPONSES[(method, path)]
                status = "202" if (method, path) == ("post", "/market/feeds") else "200"
                op["responses"][status] = {
                    "description": "Success",
                    "content": {"application/json": {"schema": {"$ref": f"#/components/schemas/{model.__name__}"}}},
                }
                op["responses"]["422"] = {
                    "description": "Validation failed (`validation_failed`).",
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorEnvelope"}}},
                }
                for code, text in (("401", "Invalid or revoked API key."), ("403", "The key lacks the scope."), ("429", "Rate limited (`retry_after_s`).")):
                    op["responses"][code] = {
                        "description": text,
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorEnvelope"}}},
                    }
            else:
                continue
            op["tags"] = [group]
            if group in CONTRACTS:
                op["x-truebex-contract"] = CONTRACTS[group]
            # The key travels as a bearer token or X-API-Key: security schemes, not a parameter.
            op["parameters"] = [p for p in op.get("parameters", []) if p.get("name", "").lower() != "x-api-key"]
            if not op["parameters"]:
                del op["parameters"]
            op["security"] = ([{}] if op.get("x-truebex-auth") == "optional" else []) + [{"bearerKey": []}, {"headerKey": []}]
            paths.setdefault(path, {})[method] = op

    # Only the schemas the kept operations name, transitively.
    keep: set[str] = set()
    _refs(paths, keep)
    while True:
        more: set[str] = set()
        for name in keep:
            _refs(schemas.get(name, {}), more)
        if more <= keep:
            break
        keep |= more
    if "HTTPValidationError" in keep:  # every 422 is the shared envelope here
        keep.discard("HTTPValidationError")
        keep.discard("ValidationError")
        keep.add("ErrorEnvelope")
    mapping = {"HTTPValidationError": "ErrorEnvelope", **{k: v for k, v in RENAME.items() if k in keep}}
    ugly = sorted(n for n in keep if ("__" in n or n.startswith("Body_")) and n not in mapping)
    if ugly:
        raise SystemExit(f"name these schemas in RENAME first: {', '.join(ugly)}")
    components = {mapping.get(n, n): copy.deepcopy(schemas[n]) for n in sorted(keep) if n in schemas}
    for old, new in mapping.items():
        if new in components and "title" in components[new]:
            components[new]["title"] = new

    security = {
        "bearerKey": {"type": "http", "scheme": "bearer", "description": "Authorization: Bearer tbx_live_…"},
        "headerKey": {"type": "apiKey", "in": "header", "name": "X-API-Key"},
    }
    doc = {
        "openapi": full["openapi"],
        "info": {
            "title": "Truebex developer API",
            "version": API_VERSION,
            "description": (
                "Projects, exports, shares, the marketplace, supplier feeds and webhooks, with an API key "
                "from https://truebex.com/dashboard/keys/ sent as `Authorization: Bearer tbx_live_…` or "
                "`X-API-Key`. Each operation names the scope it needs in `x-truebex-scope`. Errors use one "
                "envelope: `{detail, code, status, request_id, retry_after_s, data}`."
            ),
        },
        "servers": [{"url": BASE_URL}],
        "tags": [{"name": name, "description": text} for name, text in TAG_TEXT.items()],
        # What the docs pages and SDK readers need beside the operations.
        "x-truebex-scopes": [
            {"scope": s, "description": scopes.DESCRIPTIONS[s], "default": s in scopes.READ_SCOPES} for s in scopes.SCOPES
        ],
        "x-truebex-limits": {
            "burst": int(Settings.model_fields["api_key_burst"].default),
            "per_minute": int(Settings.model_fields["api_key_per_minute"].default),
        },
        "x-truebex-webhook-events": [{"type": t, "description": events.DESCRIPTIONS[t]} for t in events.EVENT_TYPES],
        "x-truebex-webhooks": {
            "signature": "Standard Webhooks: webhook-id, webhook-timestamp, webhook-signature (v1, HMAC-SHA256)",
            "retry_after_s": list(delivery.SCHEDULE_S),
            "timeout_s": int(Settings.model_fields["webhooks_timeout_s"].default),  # the default, not this machine's .env
            "disable_after_days": delivery.DISABLE_AFTER.days,
            "keep_days": delivery.KEEP.days,
            "debounce_s": int(events.OPS_DEBOUNCE.total_seconds()),
        },
        "paths": _rewrite_refs(paths, mapping),
        "components": {"schemas": _rewrite_refs(components, mapping), "securitySchemes": security},
    }
    return doc


def _json(schema_ref: str) -> dict:
    return {"content": {"application/json": {"schema": {"$ref": f"#/components/schemas/{schema_ref}"}}}}


def build_clients() -> dict:
    _env()
    from pydantic.json_schema import models_json_schema

    from app.main import app
    from app.mobile import clients

    app.openapi_schema = None
    full = copy.deepcopy(app.openapi())
    app.openapi_schema = None
    schemas = full["components"]["schemas"]
    answers = [answer for _, _, answer, _, _ in clients.ROUTES.values()]
    _, defs = models_json_schema(
        [(m, "serialization") for m in [*dict.fromkeys(answers), clients.ErrorEnvelope]],
        ref_template="#/components/schemas/{model}",
    )
    for name, body in defs.get("$defs", {}).items():
        schemas[name] = body
    _, inputs = models_json_schema(
        [(m, "validation") for m in clients.REQUEST_MODELS], ref_template="#/components/schemas/{model}"
    )
    for name, body in inputs.get("$defs", {}).items():
        schemas.setdefault(name, body)

    paths: dict = {}
    for (method, path), (op_id, contract, answer, body, auth) in clients.ROUTES.items():
        op = full["paths"][path][method]
        group = op_id.split("_", 1)[0]
        out = {
            "operationId": op_id,
            "summary": clients.TEXT[op_id],
            "tags": [group],
            "parameters": [
                p for p in op.get("parameters", []) if p.get("in") != "header"
            ],
        }
        if contract:
            out["x-truebex-contract"] = contract
            # Every request names the contract version it speaks (§3).
            out["parameters"].append(
                {
                    "name": "X-Truebex-Contract",
                    "in": "header",
                    "required": False,
                    "schema": {"type": "string", "default": contract},
                    "description": "The contract and version the client speaks; a MAJOR the server does not serve is 400 `contract_version`.",
                }
            )
        if not out["parameters"]:
            del out["parameters"]
        if body is not None:
            out["requestBody"] = {"required": True, **_json(body.__name__)}
        elif "requestBody" in op:
            out["requestBody"] = op["requestBody"]
        status = "201" if "201" in op.get("responses", {}) else "200"
        out["responses"] = {
            status: {"description": "Success", **_json(answer.__name__)},
            "default": {"description": "The shared error envelope (`code` says what failed).", **_json("ErrorEnvelope")},
        }
        if auth == "session":
            out["security"] = [{"session": []}]
        elif auth == "optional":
            out["security"] = [{}, {"session": []}]
        else:
            out["security"] = []
        paths.setdefault(path, {})[method] = out

    # Only the schemas the kept operations name, transitively.
    keep: set[str] = set()
    _refs(paths, keep)
    while True:
        more: set[str] = set()
        for name in keep:
            _refs(schemas.get(name, {}), more)
        if more <= keep:
            break
        keep |= more
    ugly = sorted(n for n in keep if "__" in n or n.startswith("Body_") or n in ("HTTPValidationError", "ValidationError"))
    if ugly:
        raise SystemExit(f"name these schemas first: {', '.join(ugly)}")
    components = {n: copy.deepcopy(schemas[n]) for n in sorted(keep)}

    return {
        "openapi": full["openapi"],
        "info": {
            "title": "Truebex light clients",
            "version": CLIENTS_VERSION,
            "description": (
                "The routes the mobile web client and the Android app call, with the answers they read. "
                "Both clients are generated from this document. A session token from /auth/login or "
                "/auth/google goes in `Authorization: Bearer …`. Errors use one envelope: "
                "`{detail, code, status, request_id, retry_after_s, data}`."
            ),
        },
        "servers": [{"url": BASE_URL}],
        "paths": dict(sorted(paths.items())),
        "components": {
            "schemas": components,
            "securitySchemes": {
                "session": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT", "description": "The 24 h session token."}
            },
        },
    }


def render(doc: dict) -> str:
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


# flag → (default file, builder); each document has its own drift test.
DOCUMENTS = {"v1": (OUT, build), "clients": (CLIENTS_OUT, build_clients)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--v1", action="store_true", help="the developer API document (PF12)")
    ap.add_argument("--clients", action="store_true", help="the light clients' document (PF9, PF10)")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--check", action="store_true", help="exit 1 when the file differs from a fresh export")
    args = ap.parse_args(argv)
    chosen = [name for name in DOCUMENTS if getattr(args, name)]
    if len(chosen) != 1:
        ap.error("pass one of: " + ", ".join(f"--{name}" for name in DOCUMENTS))
    default_out, build_doc = DOCUMENTS[chosen[0]]
    out = args.out or default_out
    text = render(build_doc())
    if args.check:
        current = out.read_text(encoding="utf-8") if out.exists() else ""
        if current != text:
            print(f"{out} is out of date: run scripts/export_openapi.py --{chosen[0]}", file=sys.stderr)
            return 1
        print(f"{out} is current")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {out} ({len(text)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
