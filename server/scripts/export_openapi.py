"""Write an OpenAPI document cut from the app's own: `openapi/clients.json` (PF10).

    server\\.venv\\Scripts\\python.exe server\\scripts\\export_openapi.py --clients
    server\\.venv\\Scripts\\python.exe server\\scripts\\export_openapi.py --clients --check   (exit 1 on drift)

`--clients` is the document of the routes the light clients call — the mobile
web client (PF9) and the Android app (PF10) — with the answers they read
(`app/mobile/clients.py`), each operation tagged with the contract it speaks
(`x-truebex-contract`). PF9's TypeScript types and PF10's Dart client are
generated from it (scripts/gen-clients.ps1); tests/test_pf10_clients.py fails
when the file is not current. One script for every exported document: PF12's
developer API document is its `--v1` flag.
"""

import argparse
import copy
import json
import os
import sys
import warnings
from pathlib import Path

SERVER = Path(__file__).resolve().parents[1]
ROOT = SERVER.parent
CLIENTS_OUT = ROOT / "openapi" / "clients.json"
CLIENTS_VERSION = "1.0.0"


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


def _json(schema_ref: str) -> dict:
    return {"content": {"application/json": {"schema": {"$ref": f"#/components/schemas/{schema_ref}"}}}}


def build_clients() -> dict:
    _env()
    from pydantic.json_schema import models_json_schema

    from app.main import app
    from app.mobile import clients

    app.openapi_schema = None
    with warnings.catch_warnings():
        # Other routers' duplicate operation ids: none of them is in this document.
        warnings.simplefilter("ignore", UserWarning)
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
        "servers": [{"url": "https://api.truebex.com"}],
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


DOCUMENTS = {"clients": (CLIENTS_OUT, build_clients)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--clients", action="store_true", help="the light clients' document (PF9, PF10)")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--check", action="store_true", help="exit 1 when the file differs from a fresh export")
    args = ap.parse_args(argv)
    chosen = [name for name in DOCUMENTS if getattr(args, name)]
    if len(chosen) != 1:
        ap.error("pass one of: " + ", ".join(f"--{name}" for name in DOCUMENTS))
    default_out, build = DOCUMENTS[chosen[0]]
    out = args.out or default_out
    text = render(build())
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
