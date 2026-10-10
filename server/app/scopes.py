"""API key scopes (PF12).

A key carries the scopes chosen when it was made (`api_keys.scopes`, a JSON
list). Keys made before scopes existed (NULL) read as every `:read` scope, so
they keep working for what they did before; a supplier key (PF8, bound to a
supplier) holds `supplier:feed` only.

| Scope | Lets a key |
|---|---|
| `projects:read` | open projects, pull operations, read snapshots, versions, members, presence, jobs |
| `projects:write` | create and rename projects, push operations, snapshots, versions, invitations |
| `jobs:write` | submit and cancel render jobs (exports) |
| `shares:write` | upload bundles and publish, list, change and revoke shares |
| `market:read` | catalogue reads with the key's limits instead of the anonymous ones |
| `supplier:feed` | send a supplier's catalogue feed (5.11-5.13) |
| `webhooks:manage` | register webhook endpoints, read deliveries, re-send, rotate secrets |
"""

import json

SCOPES: tuple[str, ...] = (
    "projects:read",
    "projects:write",
    "jobs:write",
    "shares:write",
    "market:read",
    "supplier:feed",
    "webhooks:manage",
)
READ_SCOPES: tuple[str, ...] = tuple(s for s in SCOPES if s.endswith(":read"))
SUPPLIER_SCOPES: tuple[str, ...] = ("supplier:feed",)

DESCRIPTIONS: dict[str, str] = {
    "projects:read": "Open projects and read their operations, snapshots, versions, members, presence and jobs.",
    "projects:write": "Create and rename projects, push operations, register snapshots, name and restore versions, invite.",
    "jobs:write": "Submit and cancel render jobs, the presentation pack among them.",
    "shares:write": "Upload bundles and publish, list, change and revoke shares.",
    "market:read": "Read the catalogue with the key's limits instead of the anonymous ones.",
    "supplier:feed": "Send a supplier's catalogue feed and read its import reports.",
    "webhooks:manage": "Register webhook endpoints, read deliveries, re-send them and rotate secrets.",
}


class ScopeError(ValueError):
    def __init__(self, unknown: list[str]) -> None:
        super().__init__(f"unknown scope(s): {', '.join(unknown)}")
        self.unknown = unknown


def normalise(values: list[str] | None) -> list[str]:
    """The chosen scopes in the catalogue's order; ScopeError for an unknown one."""
    if values is None:
        return list(READ_SCOPES)
    wanted = [str(v).strip() for v in values]
    unknown = [v for v in wanted if v not in SCOPES]
    if unknown:
        raise ScopeError(unknown)
    return [s for s in SCOPES if s in wanted]


def dump(values: list[str]) -> str:
    return json.dumps(values, separators=(",", ":"))


def of_key(key) -> list[str]:
    """What a key may do (an `ApiKey` row)."""
    if getattr(key, "supplier_id", None):
        return list(SUPPLIER_SCOPES)
    raw = getattr(key, "scopes", None)
    if raw is None:
        return list(READ_SCOPES)
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return list(READ_SCOPES)
    return [s for s in SCOPES if isinstance(parsed, list) and s in parsed]


def is_legacy(key) -> bool:
    """Made before scopes: every `:read` scope, and PF8's feed access kept."""
    return getattr(key, "scopes", None) is None and not getattr(key, "supplier_id", None)


def author_for_key(key_id: int) -> str:
    """The 32-hex `author` of operations a key pushes (`author_kind` agent):
    the key's id, zero-padded, so a log names the key that wrote it."""
    return format(int(key_id), "032x")
