"""Marketplace search on the production stack (PF7a): the Postgres full-text
adapter `PgIndex` behind `SearchIndex`, the index as derived data in the
SQLite -> Postgres copy, and the picture-search model volume on the VM.

Tests marked `postgres` run only when TEST_DATABASE_URL points at a
disposable Postgres database (see conftest.py); they drop and recreate its
`public` schema.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session

from app.database import init_db
from app.market import search, seed
from app.market.models import FTS_TABLE, PG_TABLE, Product, Supplier
from app.market.search import SearchParams

from .conftest import TEST_DATABASE_URL
from .market_helpers import AKER, FIXTURES, FJORD, PAINT, PRODUCT, SOFA

REPO = Path(__file__).resolve().parents[2]
WALLPAPER = PRODUCT["WP-LATTICE"]
THEME = PRODUCT["THEME-NORDIC-LIVING"]
ALL = {p["product_id"] for p in PRODUCT.values()}


def _catalogue(engine) -> None:
    init_db(engine)
    with Session(engine) as db:
        seed.load_fixture(db, FIXTURES)


@pytest.fixture()
def pg_engine():
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    yield engine
    engine.dispose()


@pytest.fixture()
def pg_catalogue(pg_engine):
    """The contract's fixture catalogue (six products of Nord Living) on Postgres."""
    _catalogue(pg_engine)
    return pg_engine


def _match(engine, query: str) -> dict[str, float]:
    with Session(engine) as db:
        index = search.index_for(db)
        assert isinstance(index, search.PgIndex)
        return index.match(db, query)


def _ids(engine, query: str) -> set[str]:
    return set(_match(engine, query))


# --- picking the adapter -------------------------------------------------------------


def test_index_for_picks_fts5_on_sqlite_and_pg_index_on_postgresql():
    sqlite = Session(create_engine("sqlite://"))
    assert isinstance(search.index_for(sqlite), search.Fts5Index)
    # Only the dialect is read: no Postgres server is needed for this.
    postgres = Session(create_engine("postgresql+psycopg://truebex:x@127.0.0.1:1/none"))
    assert isinstance(search.index_for(postgres), search.PgIndex)
    other = SimpleNamespace(get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name="mssql")))
    assert isinstance(search.index_for(other), search.LikeIndex)


def test_fold_drops_case_and_accents():
    assert search.fold("Café CRÈME Ünïcode") == "cafe creme unicode"
    # Arabic: the hamza on the alef and the short-vowel marks go, the letters stay.
    assert search.fold("الأَثاث") == "الاثاث"
    assert search.fold("") == ""


def test_sqlite_has_only_the_fts5_index(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'a.db'}")
    init_db(engine)
    names = set(inspect(engine).get_table_names())
    assert FTS_TABLE in names and PG_TABLE not in names
    engine.dispose()


@pytest.mark.postgres
def test_pg_index_table_created_and_dropped_on_postgresql_only(pg_engine):
    init_db(pg_engine)
    init_db(pg_engine)  # twice: the DDL is idempotent
    insp = inspect(pg_engine)
    assert PG_TABLE in insp.get_table_names() and FTS_TABLE not in insp.get_table_names()
    assert {c["name"] for c in insp.get_columns(PG_TABLE)} == {"product_id", "name", "body", "tsv"}
    assert insp.get_pk_constraint(PG_TABLE)["constrained_columns"] == ["product_id"]
    with pg_engine.connect() as conn:
        indexdef = conn.execute(
            text("SELECT indexdef FROM pg_indexes WHERE tablename = :t AND indexdef ILIKE '%USING gin%'"), {"t": PG_TABLE}
        ).scalar()
    assert indexdef and "(tsv)" in indexdef

    from app.database import Base

    Base.metadata.drop_all(bind=pg_engine)
    assert PG_TABLE not in inspect(pg_engine).get_table_names()


# --- PgIndex on the fixture catalogue ---------------------------------------------------


@pytest.mark.postgres
def test_pg_index_finds_the_fixture_by_its_whole_document(pg_catalogue):
    pid = SOFA["product_id"]
    assert _ids(pg_catalogue, "linen") == {pid}  # a material
    assert _ids(pg_catalogue, "ash") == {FJORD["product_id"]}
    assert _ids(pg_catalogue, "seating") == {pid}  # a category label (furniture/seating)
    assert _ids(pg_catalogue, "coffee tables") == {AKER["product_id"], FJORD["product_id"]}  # the leaf's label
    assert _ids(pg_catalogue, "decoration") == {THEME["product_id"]}
    assert _ids(pg_catalogue, "charcoal") == {pid}  # a variant option
    assert _ids(pg_catalogue, "sage") == {WALLPAPER["product_id"], THEME["product_id"]}
    assert _ids(pg_catalogue, "9501101530010") == {pid}  # a GTIN (the second variant's)
    assert _ids(pg_catalogue, "uniclass Pr_40_50_12_81") == {pid}  # a classification code
    assert _ids(pg_catalogue, "Nord Living") == ALL  # the supplier

    # The supplier's name is indexed, not only the brand (which here is the same).
    with Session(pg_catalogue) as db:
        paint = db.get(Product, PAINT["product_id"])
        paint.brand = None
        supplier = db.get(Supplier, paint.supplier_id)
        supplier.name = "Nord Living Studio"
        for product in db.scalars(select(Product)):
            search.reindex(db, product, supplier)
        db.commit()
    assert PAINT["product_id"] in _ids(pg_catalogue, "studio")


@pytest.mark.postgres
def test_pg_index_prefix_case_and_accents(pg_catalogue):
    pid = SOFA["product_id"]
    assert _ids(pg_catalogue, "lin") == {pid}
    assert _ids(pg_catalogue, "LINEN") == {pid}
    assert _ids(pg_catalogue, "coff tab") == {AKER["product_id"], FJORD["product_id"]}
    assert _ids(pg_catalogue, "pr_40_5") == {pid}  # the code's last part is a prefix too
    assert _ids(pg_catalogue, "línen") == {pid}  # an accent in the query
    with Session(pg_catalogue) as db:
        theme = db.get(Product, THEME["product_id"])
        theme.description = "Café crème walls and an Oslo sofa."
        search.reindex(db, theme)
        db.commit()
    assert THEME["product_id"] in _ids(pg_catalogue, "cafe creme")  # an accent in the catalogue
    assert THEME["product_id"] in _ids(pg_catalogue, "CAFÉ")
    # Punctuation and words with no letter or digit match nothing rather than everything.
    assert _match(pg_catalogue, "___") == {} and _match(pg_catalogue, "&|!:*'") == {}


@pytest.mark.postgres
def test_pg_index_needs_every_word(pg_catalogue):
    assert _ids(pg_catalogue, "oak linen") == {SOFA["product_id"]}
    assert _ids(pg_catalogue, "oak") >= {SOFA["product_id"], AKER["product_id"]}
    assert _ids(pg_catalogue, "oak ash") == set()
    assert _ids(pg_catalogue, "sofa nothingmatchesthis") == set()


@pytest.mark.postgres
def test_pg_index_ranks_a_name_hit_above_a_body_hit(pg_catalogue):
    # "Oslo" is in the sofa's name and in the theme's description.
    scores = _match(pg_catalogue, "oslo")
    assert set(scores) == {SOFA["product_id"], THEME["product_id"]}
    assert scores[SOFA["product_id"]] > scores[THEME["product_id"]]
    # "Chalk" names the paint; the theme mentions Chalk White walls.
    scores = _match(pg_catalogue, "chalk")
    assert scores[PAINT["product_id"]] > scores[THEME["product_id"]]
    # In 5.3 the name hit comes first, ahead of the availability and rating boosts.
    with Session(pg_catalogue) as db:
        for region in ("GB", "AE"):
            results = search.search(db, SearchParams(q="oslo", region=region))["results"]
            assert [r["product_id"] for r in results][:1] == [SOFA["product_id"]], region


@pytest.mark.postgres
def test_pg_index_reindex_after_a_text_change_and_remove(pg_catalogue):
    pid = SOFA["product_id"]
    assert _ids(pg_catalogue, "removable") == {pid}
    with Session(pg_catalogue) as db:
        sofa = db.get(Product, pid)
        sofa.name, sofa.description = "Oslo daybed", "A daybed on a solid oak frame."
        search.reindex(db, sofa)
        db.commit()
    assert _ids(pg_catalogue, "removable") == set()
    assert _ids(pg_catalogue, "daybed") == {pid}
    assert _ids(pg_catalogue, "linen") == {pid}  # variants and materials are still indexed

    with Session(pg_catalogue) as db:
        search.index_for(db).remove(db, pid)
        db.commit()
        assert db.execute(text(f"SELECT count(*) FROM {PG_TABLE}")).scalar() == len(ALL) - 1
    assert _ids(pg_catalogue, "daybed") == set() and _ids(pg_catalogue, "linen") == set()
    # A rebuild indexes every product again.
    with Session(pg_catalogue) as db:
        assert search.rebuild(db) == len(ALL)
    assert _ids(pg_catalogue, "daybed") == {pid}


@pytest.mark.postgres
def test_search_answers_alike_on_sqlite_and_postgres(pg_catalogue, tmp_path):
    """5.3 keeps its shape, and the same queries find the same products."""
    lite = create_engine(f"sqlite:///{tmp_path / 'lite.db'}")
    _catalogue(lite)
    queries = [
        ("linen", "GB"), ("oak", "GB"), ("oak", None), ("seating", "AE"), ("coffee tables", "GB"),
        ("9501101530003", "AE"), ("nord living", "GB"), ("lattice wallpaper", None), ("oslo", "GB"),
        ("chalk", "AE"), ("nothingmatchesthis", "GB"),
    ]  # fmt: skip
    try:
        with Session(lite) as a, Session(pg_catalogue) as b:
            for q, region in queries:
                on_sqlite = search.search(a, SearchParams(q=q, region=region))
                on_pg = search.search(b, SearchParams(q=q, region=region))
                assert set(on_pg) == set(on_sqlite) == {"results", "facets", "next_cursor"}
                assert {r["product_id"] for r in on_pg["results"]} == {r["product_id"] for r in on_sqlite["results"]}, q
                assert [sorted(r) for r in on_pg["results"]] == [sorted(r) for r in on_sqlite["results"]], q
                assert on_pg["facets"] == on_sqlite["facets"], q
    finally:
        lite.dispose()


# --- an empty index next to products is filled ----------------------------------------


def _empty_index_is_filled(engine, table: str) -> None:
    _catalogue(engine)
    with engine.begin() as conn:
        conn.execute(text(f"DELETE FROM {table}"))
    with Session(engine) as db:
        assert search.index_for(db).match(db, "linen") == {}
    init_db(engine)  # the next start (a database from before the index, or a restore)
    with Session(engine) as db:
        assert set(search.index_for(db).match(db, "linen")) == {SOFA["product_id"]}
        assert db.execute(text(f"SELECT count(*) FROM {table}")).scalar() == len(ALL)
    # An index holding rows is left alone; so is a database with no products.
    assert search.fill_if_empty(engine) is None
    with engine.begin() as conn:
        conn.execute(text(f"DELETE FROM {table}"))
        conn.execute(text("UPDATE products SET status = 'draft'"))
    assert search.fill_if_empty(engine) == len(ALL)  # drafts are indexed too (status filters run in SQL)


def test_empty_index_filled_at_start_on_sqlite(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'a.db'}")
    try:
        _empty_index_is_filled(engine, FTS_TABLE)
    finally:
        engine.dispose()


@pytest.mark.postgres
def test_empty_index_filled_at_start_on_postgres(pg_engine):
    _empty_index_is_filled(pg_engine, PG_TABLE)


# --- the SQLite -> Postgres copy: the index is derived, rebuilt on the target ------------


def _copied_or_derived(engine) -> list[str]:
    from scripts import sqlite_to_postgres as s2p

    copied = {t.name for t in s2p._models()}
    return [
        name
        for name in inspect(engine).get_table_names()
        if name not in copied and not any(name == d or name.startswith(f"{d}_") for d in s2p.DERIVED)
    ]


def test_sqlite_to_postgres_copies_or_derives_every_table(tmp_path):
    """Every table init_db makes is copied, or named as derived (the search
    indexes; FTS5's own shadow tables carry its name)."""
    from scripts import sqlite_to_postgres as s2p

    assert set(s2p.DERIVED) == {FTS_TABLE, PG_TABLE}
    engine = create_engine(f"sqlite:///{tmp_path / 'a.db'}")
    init_db(engine)
    try:
        assert _copied_or_derived(engine) == []
    finally:
        engine.dispose()


@pytest.mark.postgres
def test_postgres_tables_are_copied_or_derived(pg_engine):
    init_db(pg_engine)
    assert _copied_or_derived(pg_engine) == []


def test_sqlite_to_postgres_rebuilds_the_search_index(tmp_path):
    from scripts import sqlite_to_postgres as s2p

    src = create_engine(f"sqlite:///{tmp_path / 'auth.db'}")
    _catalogue(src)
    src.dispose()
    dst_url = f"sqlite:///{tmp_path / 'copy.db'}"
    report = s2p.copy_database(f"sqlite:///{tmp_path / 'auth.db'}", dst_url)
    assert report.ok, report.render()
    assert report.indexed == len(ALL)
    assert f"search index rebuilt: {len(ALL)} products" in report.render()
    assert report.render().endswith("ALL TABLES MATCH")
    assert FTS_TABLE not in {t.table for t in report.tables}
    dst = create_engine(dst_url)
    try:
        with Session(dst) as db:
            assert set(search.index_for(db).match(db, "linen")) == {SOFA["product_id"]}
    finally:
        dst.dispose()


@pytest.mark.postgres
def test_sqlite_to_postgres_rebuilds_the_search_index_on_postgres(tmp_path, pg_engine):
    from scripts import sqlite_to_postgres as s2p

    src = create_engine(f"sqlite:///{tmp_path / 'auth.db'}")
    _catalogue(src)
    src.dispose()
    report = s2p.copy_database(f"sqlite:///{tmp_path / 'auth.db'}", TEST_DATABASE_URL)
    assert report.ok, report.render()
    assert report.indexed == len(ALL)
    assert _ids(pg_engine, "linen") == {SOFA["product_id"]}
    assert _ids(pg_engine, "9501101530003") == {SOFA["product_id"]}


# --- the picture-search model files on the VM ------------------------------------------


def _volume_target(entry) -> tuple[str, str]:
    if isinstance(entry, dict):
        return entry["source"], entry["target"]
    source, target, *_ = str(entry).split(":")
    return source, target


def test_compose_mounts_one_model_volume_at_embedding_dir():
    yaml = pytest.importorskip("yaml")
    compose = yaml.safe_load((REPO / "infra" / "host" / "compose.yaml").read_text("utf-8"))
    services = compose["services"]
    mounts = {}
    for name in ("api", "worker"):
        directory = services[name]["environment"]["EMBEDDING_DIR"]
        assert directory.startswith("/"), name
        mounted = [source for source, target in map(_volume_target, services[name].get("volumes", [])) if target == directory]
        assert len(mounted) == 1, (name, services[name].get("volumes"))
        mounts[name] = (mounted[0], directory)
    assert mounts["api"] == mounts["worker"]
    volume, directory = mounts["api"]
    assert volume in compose["volumes"]  # a named volume, not a host folder
    # The local trial keeps it (no override drops the mount). Its `!override`
    # and `!reset` are Compose's merge tags: read as plain values here.
    class Loader(yaml.SafeLoader):
        pass

    def plain(loader, _suffix, node):
        if isinstance(node, yaml.SequenceNode):
            return loader.construct_sequence(node, deep=True)
        if isinstance(node, yaml.MappingNode):
            return loader.construct_mapping(node, deep=True)
        return loader.construct_scalar(node)

    Loader.add_multi_constructor("!", plain)
    local = yaml.load((REPO / "infra" / "host" / "compose.local.yaml").read_text("utf-8"), Loader=Loader)  # noqa: S506
    for name in ("api", "worker"):
        assert "volumes" not in (local["services"].get(name) or {}), name
    # The image makes the folder for its non-root user, so a new volume is writable by it.
    dockerfile = (REPO / "server" / "Dockerfile").read_text("utf-8")
    assert f"mkdir -p {directory}" in dockerfile and f"chown truebex:truebex {directory}" in dockerfile
    assert dockerfile.index(f"chown truebex:truebex {directory}") < dockerfile.index("\nUSER truebex")
    # fetch_models.py's default --dir is that folder in the image (/app is server/).
    assert directory == "/app/models"
