"""The light clients' API document (PF10): the routes the mobile web client
(PF9, TypeScript) and the Android app (PF10, Dart) both call, and the shapes
they read, as one OpenAPI document (`openapi/clients.json`).

PF4's and PF6's routes return plain dicts, so FastAPI's own schema says
nothing about their answers, and 5.6 reads its body as a stream. The models
below describe those answers (contract project-log §5, §6.2, §6.5; render-jobs
§6.2; marketplace-api 5.3–5.5) and `server/scripts/export_openapi.py --clients`
puts them into FastAPI's schema of the same routes. Both clients are generated
from that file (`scripts/gen-clients.ps1`); `tests/test_pf10_clients.py` checks
the file is current and that the real routes answer exactly these shapes, so
neither client drifts from the server.

Every model allows keys it does not name (contract §3: readers ignore keys
they do not know), so a MINOR addition never breaks a generated client.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..market.schemas import PricesRequest
from ..projects.ops import PushIn
from ..projects.presence import PresenceIn
from ..schemas import GoogleLogin, Token, UserLogin, UserOut

LOG = "project-log/1.1"
MARKET = "marketplace-api/1.1"


class _Open(BaseModel):
    model_config = ConfigDict(extra="allow")


# --- errors (every contract file §7) ---------------------------------------------------------


class ErrorEnvelope(_Open):
    """The shared error body; clients branch on `code` (`http_<status>` when absent)."""

    detail: str
    code: str | None = None
    status: int | None = None
    request_id: str | None = None
    retry_after_s: int | None = None
    data: dict[str, Any] | None = None


# --- projects (5.2, 5.3, 5.13) ---------------------------------------------------------------


class ProjectOwner(_Open):
    user_id: int
    name: str | None


class SnapshotSummary(_Open):
    snapshot_id: str
    at_seq: int
    doc_version: int
    created_at: str


class ProjectRecord(_Open):
    """5.1–5.4's record; `members` counts the active people."""

    project_id: str
    name: str
    role: Literal["owner", "editor", "viewer"]
    owner: ProjectOwner | None
    org_id: str | None
    created_at: str
    updated_at: str
    head_seq: int
    latest_snapshot: SnapshotSummary | None
    doc_version: int
    members: int
    bytes: int


class ProjectList(_Open):
    projects: list[ProjectRecord]
    next_cursor: str | None


class Member(_Open):
    """5.13; `author_id` names who wrote an operation (project-log 1.1.0): set for
    every active member, null for an invitation."""

    user_id: int | None
    invite_id: str | None
    email: str
    name: str | None
    role: str
    state: Literal["active", "invited"]
    invited_at: str | None
    accepted_at: str | None
    author_id: str | None


class MemberList(_Open):
    members: list[Member]


class ProjectQuota(_Open):
    bytes: int | None
    bytes_used: int


class OpenProject(_Open):
    """5.3: the record with the members listed and the owner's quota."""

    project_id: str
    name: str
    role: Literal["owner", "editor", "viewer"]
    owner: ProjectOwner | None
    org_id: str | None
    created_at: str
    updated_at: str
    head_seq: int
    latest_snapshot: SnapshotSummary | None
    doc_version: int
    members: list[Member]
    bytes: int
    quota: ProjectQuota


# --- snapshots (5.9; `digest` is PF9's MINOR proposal for §6.4) --------------------------------


class SnapshotFile(_Open):
    """A signed URL, valid 15 minutes; fetched without the session."""

    sha256: str
    bytes: int | None
    url: str
    url_expires_at: str


class SnapshotFiles(_Open):
    tbxp: SnapshotFile | None
    tbxpack: SnapshotFile | None
    digest: SnapshotFile | None = None


class Snapshot(_Open):
    snapshot_id: str
    at_seq: int
    doc_version: int
    created_by: int | None
    created_at: str
    files: SnapshotFiles


# --- the log (5.6, 5.7, §6.2, §6.3) ------------------------------------------------------------


class OperationAction(_Open):
    """`FTruebexAgentAction` (agent-interface §6.4): a log-safe tool and its arguments.
    `session` and `request_id` come with a live call; the desktop's own log actions
    may carry neither (PF4a). Refs in `args` are `<kind>#<id>` (§6.2)."""

    tool: str
    args: dict[str, Any]
    permission: str
    session: str | None = None
    request_id: str | None = None


class Operation(_Open):
    """§6.2 as the server stores it. Light clients never decode `delta`."""

    op_id: str
    server_seq: int
    replica_id: str
    author: str
    author_kind: Literal["person", "agent"]
    at: str
    kind: Literal["delta", "action", "restore"]
    name: str
    base_seq: int
    touched: list[str]
    delta_format: str | None
    delta: str | None
    action: OperationAction | None
    restore: dict[str, Any] | None


class PushResult(_Open):
    """One operation's fate (§6.3): `winning` and `more` come with `rejected`."""

    op_id: str
    status: Literal["accepted", "duplicate", "rejected", "not_processed"]
    server_seq: int | None = None
    reason: str | None = None
    winning: list[Operation] | None = None
    more: bool | None = None


class PushAnswer(_Open):
    head_seq: int
    results: list[PushResult]


class PullPage(_Open):
    ops: list[Operation]
    head_seq: int
    more: bool


# --- presence (5.17, 5.18, §6.5) ----------------------------------------------------------------


class PresenceView(_Open):
    storey: str | None = None
    eye_mm: list[float] | None = None
    yaw_deg: float | None = None


class Presence(_Open):
    """`client` is desktop, web, android, headset or worker."""

    user_id: int
    name: str | None
    replica_id: str
    client: str
    seen_at: str
    view: PresenceView | None
    selection: list[str]
    editing: list[str]


class PresenceAnswer(_Open):
    ttl_s: int
    others: list[Presence]


class PresenceList(_Open):
    present: list[Presence]


# --- panoramas (PF9's members' read of followed sets; render-jobs §6.2 manifests) ---------------


class PanoramaSet(_Open):
    set_id: str
    rev: int
    at_seq: int
    views: list[str]
    following: bool
    mine: bool
    updated_at: str


class PanoramaSets(_Open):
    sets: list[PanoramaSet]


class TileFace(_Open):
    """`tiles[level]` lists the face's tile hashes row by row (`<tiles_base>/<sha256>.jpg`)."""

    rendered: bool | None = None
    reason: str | None = None
    tiles: list[list[str]]


class TileFaces(_Open):
    n: TileFace
    e: TileFace
    s: TileFace
    w: TileFace
    u: TileFace
    d: TileFace


class TileView(_Open):
    view: str
    title: str | None = None
    eye_mm: list[float] | None = None
    face_px: int
    tile_px: int
    levels: list[int]
    faces: TileFaces


class TileManifest(_Open):
    """`truebex-tiles/1`; a client refuses a MAJOR it does not know ("Update needed")."""

    schema_: str = Field(alias="schema")
    job_id: str
    project_id: str | None = None
    at_seq: int
    tiles_base: str
    views: list[TileView]
    faces_rendered: int | None = None
    faces_reused: int | None = None


class SetState(_Open):
    rev: int
    job_id: str | None
    follow_job_id: str
    at_seq: int
    following: bool
    manifest: TileManifest | None


# --- the marketplace (5.3–5.5; only what the clients read is named) -----------------------------


class Price(_Open):
    """Minor units: `amount` / 10^`exponent` in `currency`."""

    amount: int
    currency: str
    exponent: int
    region: str
    includes_tax: bool
    tax_rate_bp: int
    at: str | None


class Availability(_Open):
    state: str


class PricedItem(_Open):
    supplier_id: str
    sku: str
    variant_id: str
    qty: int | None = None
    status: str | None = None
    price: Price | None
    availability: Availability | None
    substitutes: list[dict[str, Any]]


class PricesAnswer(_Open):
    items: list[PricedItem]


class SearchHit(_Open):
    product_id: str
    supplier_id: str
    name: str
    category: str | None
    variant_id: str | None
    price: Price | None


class SearchAnswer(_Open):
    results: list[SearchHit]
    next_cursor: str | None = None


class ProductVariant(_Open):
    variant_id: str
    options: dict[str, Any] | None = None
    price: Price | None = None
    availability: Availability | None = None


class ProductAnswer(_Open):
    product_id: str
    supplier_id: str
    sku: str
    name: str
    category: str | None
    variants: list[ProductVariant]


# --- the routes -------------------------------------------------------------------------------

# (method, path) -> (operation id, contract header, the success answer, a request
# body the route reads itself, the session it needs: "session", "optional" or None).
ROUTES: dict[tuple[str, str], tuple[str, str | None, type[BaseModel] | None, type[BaseModel] | None, str | None]] = {
    ("post", "/auth/login"): ("auth_login", None, Token, None, None),
    ("post", "/auth/google"): ("auth_google", None, Token, None, None),
    ("get", "/auth/me"): ("auth_me", None, UserOut, None, "session"),
    ("get", "/projects"): ("projects_list", LOG, ProjectList, None, "session"),
    ("get", "/projects/{project_id}"): ("projects_open", LOG, OpenProject, None, "session"),
    ("get", "/projects/{project_id}/snapshots/latest"): ("snapshots_latest", LOG, Snapshot, None, "session"),
    ("get", "/projects/{project_id}/ops"): ("ops_pull", LOG, PullPage, None, "session"),
    ("post", "/projects/{project_id}/ops"): ("ops_push", LOG, PushAnswer, PushIn, "session"),
    ("put", "/projects/{project_id}/presence"): ("presence_put", LOG, PresenceAnswer, None, "session"),
    ("get", "/projects/{project_id}/presence"): ("presence_get", LOG, PresenceList, None, "session"),
    ("get", "/projects/{project_id}/members"): ("members_list", LOG, MemberList, None, "session"),
    ("get", "/projects/{project_id}/panoramas"): ("panoramas_list", LOG, PanoramaSets, None, "session"),
    ("get", "/projects/{project_id}/panoramas/{set_id}"): ("panoramas_get", LOG, SetState, None, "session"),
    ("post", "/market/prices"): ("market_prices", MARKET, PricesAnswer, None, "optional"),
    ("get", "/market/search"): ("market_search", MARKET, SearchAnswer, None, "optional"),
    ("get", "/market/products/{product_id}"): ("market_product", MARKET, ProductAnswer, None, "optional"),
}

# What each operation is for (shown in both generated clients).
TEXT = {
    "auth_login": "Sign in with e-mail and password; the answer's token is the session (24 h).",
    "auth_google": "Sign in with a Google ID token minted for the Web client id (the Android app's server client id).",
    "auth_me": "The signed-in person, with the author_id every operation they write carries.",
    "projects_list": "Projects I own or that are shared with me (5.2), newest activity first.",
    "projects_open": "Open a project (5.3): the record, its head, members and quota.",
    "snapshots_latest": "The newest snapshot (5.9) with signed URLs, or the one `id` names (a restore's); `files.digest` is the project digest.",
    "ops_pull": "Operations after a sequence number (5.7); long-polls up to wait_s (≤ 25).",
    "ops_push": "Push operations (5.6), at most 200; each answers accepted, duplicate, rejected or not_processed (§6.3).",
    "presence_put": "Heartbeat (5.17) with the client kind and view; `leaving` removes it.",
    "presence_get": "Who is in the project (5.18).",
    "members_list": "Members and invitations (5.13).",
    "panoramas_list": "The project's followed panorama sets (members' read).",
    "panoramas_get": "One set's newest tile manifest; with `rev` and `wait_s`, held until it moves past `rev`.",
    "market_prices": "Prices and availability of the placed products for a region (5.5).",
    "market_search": "Products by category and region (5.3), for a swap.",
    "market_product": "One product with its variants and the region's prices (5.4).",
}

# Schemas FastAPI already names for these routes' bodies, kept as they are.
REQUEST_MODELS: tuple[type[BaseModel], ...] = (UserLogin, GoogleLogin, PresenceIn, PricesRequest, PushIn)
