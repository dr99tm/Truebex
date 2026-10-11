"""Shapes the developer API documents (PF12): `openapi/v1.json`, the SDKs'
types and the reference tables on /developers/ come from these.

Response models are documentation only (`responses=` on each route, never
`response_model`): the mirror returns exactly what the contract routes return,
so a field the contracts add later reaches callers before this file names it.
Request models subclass the contract routers' own, so validation is theirs.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.json_schema import SkipJsonSchema

from .. import projects as _projects
from .. import shares as _shares
from .. import uploads as _uploads
from ...projects import presence as _presence


class _Doc(BaseModel):
    model_config = ConfigDict(extra="allow")


# --- errors -------------------------------------------------------------------------------


class ErrorEnvelope(_Doc):
    """The shared error envelope of every contract (`code` is what to branch on)."""

    detail: str
    code: str = Field(description="e.g. forbidden, not_found, validation_failed, rate_limited, session_required")
    status: int
    request_id: str
    retry_after_s: int | None = None
    data: dict[str, Any] | None = None


# --- account ------------------------------------------------------------------------------


class Ping(_Doc):
    ok: bool
    time: str


class AccountKey(_Doc):
    id: int
    name: str
    prefix: str
    scopes: list[str]
    author: str = Field(description="The 32-hex author id of operations this key pushes (author_kind agent).")


class AccountUsage(_Doc):
    used: int
    limit: int
    remaining: int


class Account(_Doc):
    email: str
    plan: str
    key: AccountKey
    usage: AccountUsage


# --- projects (project-log 5.1-5.18) ------------------------------------------------------


class ProjectOwner(_Doc):
    user_id: int
    name: str


class SnapshotSummary(_Doc):
    snapshot_id: str
    at_seq: int
    doc_version: int
    created_at: str


class Project(_Doc):
    """The project record (5.1-5.4)."""

    project_id: str
    name: str
    role: Literal["viewer", "editor", "owner"]
    owner: ProjectOwner | None
    org_id: str | None = None
    created_at: str
    updated_at: str | None = None
    head_seq: int
    latest_snapshot: SnapshotSummary | None
    doc_version: int
    members: int
    bytes: int


class ProjectList(_Doc):
    projects: list[Project]
    next_cursor: str | None


class Member(_Doc):
    user_id: int | None
    email: str
    name: str | None = None
    author_id: str | None = Field(default=None, description="The member's author id, as on their operations (PF9); null until they have one")
    role: Literal["viewer", "editor", "owner"]
    state: Literal["active", "invited"]
    invited_at: str | None = None
    accepted_at: str | None = None


class MemberList(_Doc):
    members: list[Member]


class Quota(_Doc):
    bytes: int | None
    bytes_used: int


class ProjectDetail(Project):
    """5.3: the record with its members and the owner's storage quota."""

    members: list[Member]  # type: ignore[assignment]
    quota: Quota


class ProjectCreate(_projects.CreateIn):
    """5.1: a new project."""


class ProjectRename(_projects.RenameIn):
    """5.4: a new name."""


class AgentAction(_Doc):
    tool: str
    args: dict[str, Any]
    permission: Literal["edit"]
    session: str
    request_id: str


class Operation(_Doc):
    """An operation of the log (project-log §6.2)."""

    op_id: str
    author: str | None = Field(default=None, description="A key's pushes carry its own author id; omit it")
    author_kind: Literal["person", "agent"] | None = Field(default=None, description="agent for a key; omit it")
    at: str
    touched: list[str] = Field(description="32-hex entity ids, sorted and unique")
    kind: Literal["delta", "action", "restore"]
    name: str = ""
    base_seq: int
    replica_id: str | None = None
    server_seq: int | None = None
    delta_format: str | None = None
    delta: str | None = Field(default=None, description="base64 O5 delta (kind delta)")
    action: AgentAction | None = None
    restore: dict[str, Any] | None = None


class PushRequest(_Doc):
    replica_id: str
    ops: list[Operation] = Field(max_length=200)


class PushResultItem(_Doc):
    op_id: str
    status: Literal["accepted", "duplicate", "rejected", "not_processed"]
    server_seq: int | None = None
    reason: str | None = None
    winning: list[Operation] | None = None


class PushResult(_Doc):
    head_seq: int
    results: list[PushResultItem]


class PullResult(_Doc):
    ops: list[Operation]
    head_seq: int
    more: bool


class SnapshotFileUrl(_Doc):
    sha256: str
    bytes: int
    url: str
    url_expires_at: str


class SnapshotFiles(_Doc):
    """The snapshot's files: `tbxp`, `tbxpack` and `digest`, the project digest (`truebex-project-digest/1`: rooms,
    walls, products, themes, for light clients; PF9). `tbxpack` and `digest` are null when the snapshot has none."""

    tbxp: SnapshotFileUrl
    tbxpack: SnapshotFileUrl | None
    digest: SnapshotFileUrl | None


class Snapshot(_Doc):
    snapshot_id: str
    at_seq: int
    doc_version: int
    created_by: int
    created_at: str
    files: SnapshotFiles


class SnapshotRequest(_projects.SnapshotIn):
    """5.8: register an uploaded snapshot (files from /v1/uploads, purpose snapshot)."""


class Version(_Doc):
    version_id: str
    name: str
    note: str
    at_seq: int
    snapshot_id: str
    created_by: int
    created_at: str


class VersionList(_Doc):
    versions: list[Version]


class VersionRequest(_projects.VersionIn):
    """5.11: name a version at a snapshot."""


class RestoreResult(_Doc):
    op: Operation


class MemberInvite(_projects.InviteIn):
    """5.14: invite by e-mail with a role."""


class MemberRole(_projects.RoleIn):
    """5.15: a new role."""


class PresenceHeartbeat(_presence.PresenceIn):
    """5.17: where this client is and what it has selected."""


class Presence(_Doc):
    user_id: int
    name: str
    replica_id: str
    client: str
    seen_at: str
    view: dict[str, Any] | None = None
    selection: list[str] = []
    editing: list[str] = []


class HeartbeatResult(_Doc):
    ttl_s: int
    others: list[Presence]


class PresenceList(_Doc):
    present: list[Presence]


# --- followed panorama sets (PF12a: PF9's member reads, a render-jobs §5 MINOR proposal) ----------------


class PanoramaSet(_Doc):
    """A followed panorama set of the project: a `follow: true` panorama job (render-jobs 5.1) that a member's
    account keeps current from the log."""

    set_id: str = Field(description="32 hex: the follow job's id")
    rev: int = Field(description="Moves each time a render of the set finishes; wait for it with the set's read")
    at_seq: int = Field(description="The log position the newest render shows")
    views: list[str] = Field(description="The saved views (32 hex ids) the set renders")
    following: bool = Field(description="false once the set stopped following; its last render still shows")
    mine: bool = Field(description="true when the key's own account keeps the set")
    updated_at: str


class PanoramaSetList(_Doc):
    """The sets of the project's active members, those still following first, then the newest first."""

    sets: list[PanoramaSet]


class TileFace(_Doc):
    """One cube face: `tiles[L]` lists level L's tile hashes row by row from the top-left."""

    rendered: bool
    reason: str = Field(description="full, changed or light when this render drew the face; carried when it kept the last one")
    tiles: list[list[str]]


class TileView(_Doc):
    """A saved view's cube: faces n, e, s and w look north (+Y), east, south and west from `eye_mm`; u looks up and
    d down. Level L is `levels[L]` px square, cut into tiles of `tile_px`."""

    view: str = Field(description="The saved view's id (32 hex)")
    title: str | None = None
    eye_mm: list[float]
    face_px: int
    tile_px: int
    levels: list[int]
    faces: dict[str, TileFace]


class TileManifest(_Doc):
    """The render's tile manifest (render-jobs §6.2): its `schema` is `truebex-tiles/1` (refuse a major version you
    do not know). A tile is `<tiles_base>/<sha256>.jpg`: immutable and shared between renders, so a client fetches
    only the hashes it has not seen."""

    # `schema` is left out of the fields: the Python SDK's type generator would name it `schema_`.
    job_id: str
    project_id: str | None = None
    at_seq: int
    tiles_base: str
    views: list[TileView]
    faces_rendered: int | None = None
    faces_reused: int | None = None


class PanoramaSetState(_Doc):
    """A set's newest render; `manifest` and `job_id` are null until its first render finishes."""

    rev: int
    job_id: str | None = Field(description="The job whose output is the newest manifest")
    follow_job_id: str = Field(description="The set's id")
    at_seq: int
    following: bool
    manifest: TileManifest | None


# --- jobs (render-jobs 5.1-5.6) -------------------------------------------------------------


class JobInputs(_Doc):
    upload_id: str | None = None
    files: dict[str, str] = {}


class JobRequest(_Doc):
    """5.1: a job. `pack` (exports) takes `params.items` from renders, panoramas, sheets, boq."""

    kind: Literal["panorama", "tiles", "pack", "wind", "energy"]
    project_id: str | None = Field(default=None, description="32 hex; panorama, tiles and pack need it, an analysis may name none")
    at_seq: int = Field(default=0, description="With project_id, the snapshot reference; panorama, tiles and pack need it")
    views: list[str] = []
    changed: list[str] = []
    base_job_id: str | None = None
    quality: Literal["draft", "standard", "high"] = "standard"
    follow: bool = False
    inputs: JobInputs | None = None
    params: dict[str, Any] = {}


class JobError(_Doc):
    code: str
    message: str


class Job(_Doc):
    """The job record."""

    job_id: str
    kind: str
    state: Literal["queued", "claimed", "running", "succeeded", "failed", "cancelled", "expired"]
    rev: int
    project_id: str | None = Field(description="null for an analysis that named no project")
    at_seq: int
    progress: float
    message: str
    created_at: str
    started_at: str | None
    finished_at: str | None
    attempts: int
    cost_units_estimate: float | None
    cost_units: float | None
    output_ready: bool
    error: JobError | None


class JobList(_Doc):
    jobs: list[Job]
    next_cursor: str | None


class JobUsage(_Doc):
    period_start: str
    period_end: str
    used_cu: float
    limit_cu: float | None
    remaining_cu: float | None
    classes: dict[str, float]
    by_kind: dict[str, float]


class JobOutput(_Doc):
    """§6.2 tile manifest (`truebex-tiles/1`), §6.3 analysis result
    (`truebex-analysis/1`) or a pack's files, each file with a URL."""


# --- uploads and shares (share-bundle 5.1-5.9) ----------------------------------------------


class UploadRequest(_uploads.OpenUploadIn):
    """5.1: `purpose` share (needs shares:write), snapshot (projects:write) or job-input (jobs:write)."""

    upload_id: SkipJsonSchema[str | None] = Field(default=None, max_length=32)


class UploadFileState(_Doc):
    sha256: str
    state: Literal["missing", "partial", "complete", "present"]
    parts: int | None = None
    received: list[int] = []


class Upload(_Doc):
    upload_id: str
    part_bytes: int | None = None
    expires_at: str
    files: list[UploadFileState]


class ShareVisits(_Doc):
    total: int
    unique: int
    last_at: str | None
    by_day: list[dict[str, Any]] | None = None


class Share(_Doc):
    """The share record (§6.2)."""

    share_id: str
    slug: str
    url: str | None
    title: str
    state: Literal["uploading", "live", "expired", "revoked"]
    created_at: str
    published_at: str | None
    expires_at: str | None
    bytes: int
    watermark: bool
    visits: ShareVisits


class ShareRequest(_shares.CreateShareIn):
    """5.4: a share from a bundle manifest (truebex-share/1); the same `bundle_id` again returns the same share."""


class ShareCreated(_Doc):
    share: Share
    upload: Upload | None


class SharePublished(_Doc):
    share: Share


class ShareList(_Doc):
    shares: list[Share]
    limits: dict[str, Any]


class ShareUpdate(_shares.PatchShareIn):
    """5.8: a new title, a new expiry, or both."""


# --- webhooks -------------------------------------------------------------------------------


class WebhookEndpoint(_Doc):
    endpoint_id: str
    url: str
    events: list[str]
    active: bool
    description: str
    failing_since: str | None
    disabled_reason: str | None
    created_at: str
    last_delivery: dict[str, Any] | None = None


class WebhookEndpointWithSecret(WebhookEndpoint):
    secret: str = Field(description="whsec_… — shown at creation and on rotate only")


class WebhookEndpointList(_Doc):
    endpoints: list[WebhookEndpoint]
    events: list[str]


class WebhookDelivery(_Doc):
    delivery_id: str
    endpoint_id: str
    event_id: str
    event_type: str
    attempt: int
    status: Literal["pending", "succeeded", "failed", "cancelled"]
    next_attempt_at: str | None
    response_code: int | None
    response_ms: int | None
    error: str | None
    delivered_at: str | None
    created_at: str
    manual: bool


class WebhookDeliveryList(_Doc):
    deliveries: list[WebhookDelivery]


class WebhookSecret(_Doc):
    endpoint_id: str
    secret: str


# --- marketplace reads and supplier feeds (marketplace-api 5.1-5.6, 5.11-5.13) -----------------
# PF7's and PF8's routes answer these; the export (scripts/export_openapi.py)
# names them in the developer document.


class Money(_Doc):
    """Minor units with the ISO 4217 code and exponent (§6.3); never a float."""

    amount: int
    currency: str
    exponent: int
    region: str | None = None
    includes_tax: bool | None = None
    tax_rate_bp: int | None = None
    at: str | None = None


class Availability(_Doc):
    state: Literal["in_stock", "low_stock", "made_to_order", "out_of_stock", "discontinued"]
    stock: int | None = None
    lead_time_days: int | None = None
    updated_at: str | None = None


class MarketCategory(_Doc):
    path: str
    label: str
    app_path: str
    products: int


class MarketCategories(_Doc):
    taxonomy_sha256: str
    categories: list[MarketCategory]


class MarketRegion(_Doc):
    region: str
    name: str
    currency: str
    exponent: int
    tax: dict[str, Any]


class MarketRegions(_Doc):
    regions: list[MarketRegion]


class SearchResult(_Doc):
    product_id: str
    supplier_id: str
    supplier_name: str
    name: str
    kind: str
    category: str
    app_path: str
    thumbnail_url: str | None
    dims_mm: list[int] | None
    variants: int
    price: Money | None
    availability: Availability | None


class MarketSearch(_Doc):
    results: list[SearchResult]
    facets: dict[str, dict[str, int]]
    next_cursor: str | None


class MarketProduct(_Doc):
    """§6.1: a product with its variants, geometry, the region's price and availability."""

    product_id: str
    supplier_id: str
    sku: str
    name: str
    kind: str
    category: str
    app_path: str
    description: str
    images: list[str]
    variants: list[dict[str, Any]]


class PriceLine(_Doc):
    supplier_id: str
    sku: str
    variant_id: str
    price: Money | None
    availability: Availability | None
    substitutes: list[dict[str, Any]] = []


class PriceBatch(_Doc):
    region: str
    at: str
    stale_after: str
    items: list[PriceLine]


class SupplierProfile(_Doc):
    supplier_id: str
    name: str
    country: str
    website: str | None
    logo_url: str | None
    regions: list[str]
    verified: bool


class FeedQueued(_Doc):
    feed_id: str
    state: Literal["queued", "running", "done", "failed"]


class FeedError(_Doc):
    row: int
    column: str
    code: str
    value: str | None = None


class FeedReport(_Doc):
    """5.13: the import report (≤ 200 row errors)."""

    feed_id: str
    state: Literal["queued", "running", "done", "failed"]
    rows: int
    created: int
    updated: int
    unchanged: int
    rejected: int
    errors: list[FeedError]


class FeedSource(_Doc):
    url: str
    format: Literal["csv", "json"]
    mode: Literal["upsert", "replace"]


MARKET_RESPONSES = {
    ("get", "/market/categories"): MarketCategories,
    ("get", "/market/regions"): MarketRegions,
    ("get", "/market/search"): MarketSearch,
    ("get", "/market/products/{product_id}"): MarketProduct,
    ("post", "/market/prices"): PriceBatch,
    ("get", "/market/suppliers/{supplier_id}"): SupplierProfile,
    ("post", "/market/feeds"): FeedQueued,
    ("put", "/market/feeds/source"): FeedSource,
    ("get", "/market/feeds/{feed_id}"): FeedReport,
}
