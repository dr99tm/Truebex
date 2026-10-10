"""SQLAlchemy engine, session factory, and declarative base.

Runs on SQLite (local development, tests) and Postgres (production, PF14).
Code that needs a dialect-specific construct goes through a helper here
(`dialect_insert`), never `sqlalchemy.dialects.*` directly.
"""

import logging
from collections.abc import Generator

from sqlalchemy import Engine, create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

settings = get_settings()


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        # check_same_thread is a SQLite-specific flag required because FastAPI
        # may touch the connection from different threads.
        eng = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(eng, "connect")
        def _sqlite_pragmas(dbapi_conn, _record) -> None:  # pragma: no cover
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        return eng
    # Postgres: survive the database restarting under a long-lived pool.
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)


engine = make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a request-scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def dialect_insert(db: Session, model):
    """An INSERT supporting `on_conflict_do_update` / `on_conflict_do_nothing`
    for the session's dialect (SQLite and Postgres share that API)."""
    name = db.get_bind().dialect.name
    if name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:  # pragma: no cover - only the two dialects are deployed
        raise NotImplementedError(f"no upsert for dialect {name}")
    return insert(model)


# DateTime(timezone=True): Postgres has no DATETIME; SQLite takes any name.
_TIMESTAMP = "TIMESTAMP WITH TIME ZONE"

# Columns added to existing tables after the first release. create_all only
# creates missing *tables*, so these are added by hand on startup. SQLite can
# only ADD nullable columns this way; that's all these are. Every DDL here is
# valid on SQLite and Postgres.
_ADDED_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "users": [
        ("google_sub", "VARCHAR(64)"),
        ("name", "VARCHAR(200)"),
        ("avatar_url", "VARCHAR(1024)"),
        # PF1 / PF14: set by hand for the owner; gates /admin/*.
        ("is_admin", "BOOLEAN"),
    ],
    # PF1 (seats) and PF2 (billing through the UK company).
    "subscriptions": [
        ("seats", "INTEGER"),
        ("interval", "VARCHAR(8)"),
        ("currency", "VARCHAR(3)"),
        ("cancel_at_period_end", "BOOLEAN"),
        ("founding", "BOOLEAN"),
        ("provider_price_id", "VARCHAR(128)"),
        ("last_event_at", _TIMESTAMP),
    ],
    "payments": [
        ("interval", "VARCHAR(8)"),
        ("seats", "INTEGER"),
        ("tax_minor", "INTEGER"),
        ("consent_version", "VARCHAR(32)"),
        ("consent_at", _TIMESTAMP),
        ("invoice_id", "VARCHAR(128)"),
    ],
}

# PF1 (licence API), in its own block so parallel features add theirs beside it.
_ADDED_COLUMNS["users"] += [("author_id", "VARCHAR(32)"), ("trial_used_at", _TIMESTAMP)]
# subscriptions.seats (NULL = 1) is in the PF2 block above: PF2 writes it.

# PF3 (organisations): an organisation's paid tier; PF2 sets it from
# custom_data.org_id. NULL = the user's own (personal) subscription.
_ADDED_COLUMNS.setdefault("subscriptions", []).append(("organisation_id", "VARCHAR(32)"))
# PF8 (supplier portal): keys bound to a supplier; the carrier and reference
# a supplier gives when it ships its part of an order.
_ADDED_COLUMNS.setdefault("api_keys", []).append(("supplier_id", "VARCHAR(32)"))
_ADDED_COLUMNS.setdefault("market_order_suppliers", []).extend(
    [("carrier", "VARCHAR(80)"), ("tracking_ref", "VARCHAR(120)")]
)


def _migrate(bind: Engine) -> None:
    insp = inspect(bind)
    with bind.begin() as conn:
        for table, cols in _ADDED_COLUMNS.items():
            if not insp.has_table(table):
                continue
            have = {c["name"] for c in insp.get_columns(table)}
            for name, ddl in cols:
                if name not in have:
                    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN "{name}" {ddl}'))
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_sub "
                "ON users (google_sub)"
            )
        )
        # PF1
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_author_id "
                "ON users (author_id)"
            )
        )
        # PF3
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_subscriptions_organisation_id "
                "ON subscriptions (organisation_id)"
            )
        )
        # PF8
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_api_keys_supplier_id ON api_keys (supplier_id)")
        )
    # PF2: one row per provider subscription. Files with duplicates from before
    # keep working without the index (logged); billing.service retries on it.
    try:
        with bind.begin() as conn:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_subscriptions_provider_sub "
                    "ON subscriptions (provider, provider_subscription_id)"
                )
            )
    except Exception:  # pragma: no cover - only with duplicate legacy rows
        logging.getLogger("truebex.db").exception("could not add uq_subscriptions_provider_sub")


def init_db(bind: Engine | None = None, *, seed: bool = True) -> None:
    """Create tables and apply additive migrations (safe to run repeatedly)."""
    from . import models  # noqa: F401  (ensures models are registered)
    from .licence import models as _licence_models  # noqa: F401  (PF1)
    from .releases import models as _release_models  # noqa: F401  (PF1)
    from .shares import models as _share_models  # noqa: F401  (PF5)
    from .uploads import models as _upload_models  # noqa: F401  (PF5)
    from .orgs import models as _org_models  # noqa: F401  (PF3)
    from .sso import models as _sso_models  # noqa: F401  (PF3)
    from .market import models as _market_models  # noqa: F401  (PF7)
    from .supplier import models as _supplier_models  # noqa: F401  (PF8)

    bind = bind or engine
    Base.metadata.create_all(bind=bind)
    _migrate(bind)

    # PF7: the marketplace's categories (rooted on the app's taxonomy) and
    # regions. The Postgres copy (scripts/sqlite_to_postgres.py) brings the
    # source's rows instead, so it passes seed=False.
    if seed:
        from sqlalchemy.orm import Session

        from .market import taxonomy as _market_taxonomy

        with Session(bind) as db:
            _market_taxonomy.seed(db)
