"""SQLAlchemy engine, session factory, and declarative base."""

from collections.abc import Generator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

settings = get_settings()

# check_same_thread is a SQLite-specific flag required because FastAPI may
# touch the connection from different threads.
connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record) -> None:  # pragma: no cover
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a request-scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Columns added to existing tables after the first release. create_all only
# creates missing *tables*, so these are added by hand on startup. SQLite can
# only ADD nullable columns this way; that's all these are.
_ADDED_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "users": [
        ("google_sub", "VARCHAR(64)"),
        ("name", "VARCHAR(200)"),
        ("avatar_url", "VARCHAR(1024)"),
        ("is_admin", "BOOLEAN"),
    ],
}

# PF1 (licence API), in its own block so parallel features add theirs beside it.
_ADDED_COLUMNS["users"] += [("author_id", "VARCHAR(32)"), ("trial_used_at", "DATETIME")]
# Seats bought (PF2 writes it); NULL = 1.
_ADDED_COLUMNS.setdefault("subscriptions", []).append(("seats", "INTEGER"))


def _migrate() -> None:
    insp = inspect(engine)
    with engine.begin() as conn:
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


def init_db() -> None:
    """Create tables and apply additive migrations."""
    from . import models  # noqa: F401  (ensures models are registered)
    from .licence import models as _licence_models  # noqa: F401  (PF1)
    from .releases import models as _release_models  # noqa: F401  (PF1)
    from .market import models as _market_models  # noqa: F401  (PF7)

    Base.metadata.create_all(bind=engine)
    _migrate()

    # PF7: the marketplace's categories (rooted on the app's taxonomy) and regions.
    from .market import taxonomy as _market_taxonomy

    with SessionLocal() as db:
        _market_taxonomy.seed(db)
