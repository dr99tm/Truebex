"""Copy the SQLite database into Postgres (PF14 cutover, infra/CUTOVER.md step 3).

    cd server
    .venv\\Scripts\\python.exe -m scripts.sqlite_to_postgres --check-only --sqlite sqlite:///./auth.db
    .venv\\Scripts\\python.exe -m scripts.sqlite_to_postgres --sqlite sqlite:///./auth.db \\
        --postgres postgresql+psycopg://truebex:<password>@127.0.0.1:15432/truebex

1. Precheck: values Postgres would refuse (strings longer than their column,
   foreign keys pointing nowhere, NULL in a required column) are listed and
   the copy stops. Nothing is truncated silently.
2. The target's schema is created (`init_db`); it must hold no rows.
3. Tables are copied in foreign-key order with their ids.
4. Postgres sequences are reset to max(id) + 1.
5. Row counts and a per-table checksum (SHA-256 over every row in key order)
   are compared; the exit code is 0 only when every table matches.
"""

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import Integer, MetaData, String, Table, create_engine, exists, func, select, text

if __package__ in (None, ""):  # run as a file: make `app` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Base, init_db, make_engine  # noqa: E402


class CopyError(Exception):
    pass


@dataclass
class TableReport:
    table: str
    source_rows: int
    target_rows: int
    source_checksum: str
    target_checksum: str

    @property
    def ok(self) -> bool:
        return self.source_rows == self.target_rows and self.source_checksum == self.target_checksum


@dataclass
class Report:
    tables: list[TableReport] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(t.ok for t in self.tables)

    def render(self) -> str:
        lines = [f"{'table':<24} {'rows':>14}  checksum"]
        for t in self.tables:
            mark = "ok" if t.ok else "MISMATCH"
            lines.append(
                f"{t.table:<24} {t.source_rows:>6} -> {t.target_rows:<6} {t.source_checksum[:12]} "
                f"{t.target_checksum[:12]}  {mark}"
            )
        lines.append("ALL TABLES MATCH" if self.ok else "TABLES DIFFER")
        return "\n".join(lines)


def _models() -> list[Table]:
    # Every module with tables (the same set init_db creates), so a fresh
    # process sees PF1's devices and releases too.
    from app import models  # noqa: F401
    from app.licence import models as _licence  # noqa: F401
    from app.releases import models as _releases  # noqa: F401

    return list(Base.metadata.sorted_tables)  # parents before children


def _reflect(engine) -> MetaData:
    meta = MetaData()
    meta.reflect(bind=engine)
    return meta


def _label(row, pk: list[str]) -> str:
    return ",".join(f"{name}={row._mapping[name]}" for name in pk)


def precheck(source_url: str) -> list[str]:
    """Rows Postgres would refuse, as `table.column pk=…: reason` lines."""
    engine = create_engine(source_url)
    problems: list[str] = []
    try:
        meta = _reflect(engine)
        with engine.connect() as conn:
            for model in _models():
                src = meta.tables.get(model.name)
                if src is None:
                    continue
                pk = [c.name for c in model.primary_key.columns if c.name in src.c]
                for col in model.columns:
                    if col.name not in src.c:
                        continue
                    scol = src.c[col.name]
                    if isinstance(col.type, String) and col.type.length:
                        for row in conn.execute(
                            select(*[src.c[p] for p in pk], func.length(scol).label("n")).where(
                                func.length(scol) > col.type.length
                            )
                        ):
                            problems.append(
                                f"{model.name}.{col.name} {_label(row, pk)}: {row.n} characters > {col.type.length}"
                            )
                    if not col.nullable and not col.primary_key and col.default is None:
                        for row in conn.execute(select(*[src.c[p] for p in pk]).where(scol.is_(None))):
                            problems.append(f"{model.name}.{col.name} {_label(row, pk)}: empty but required")
                    for fk in col.foreign_keys:
                        parent = meta.tables.get(fk.column.table.name)
                        if parent is None:
                            continue
                        pcol = parent.c[fk.column.name]
                        orphan = select(*[src.c[p] for p in pk], scol.label("ref")).where(
                            scol.is_not(None), ~exists().where(pcol == scol)
                        )
                        for row in conn.execute(orphan):
                            problems.append(
                                f"{model.name}.{col.name} {_label(row, pk)}: no {parent.name} row {row.ref}"
                            )
    finally:
        engine.dispose()
    return problems


def _norm(value):
    if isinstance(value, datetime):
        aware = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return aware.astimezone(timezone.utc).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return value


def _to_target(value):
    # SQLite hands back naive datetimes; everything stored is UTC.
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _rows(conn, table: Table, columns: list[str]):
    order = [table.c[c.name] for c in table.primary_key.columns]
    return conn.execute(select(*[table.c[c] for c in columns]).order_by(*order))


def _checksum(conn, table: Table, columns: list[str]) -> tuple[int, str]:
    digest = hashlib.sha256()
    count = 0
    for row in _rows(conn, table, columns):
        digest.update(json.dumps([_norm(v) for v in row], default=str).encode("utf-8"))
        digest.update(b"\n")
        count += 1
    return count, digest.hexdigest()


def _reset_sequences(conn, table: Table) -> None:
    pk = list(table.primary_key.columns)
    if len(pk) != 1 or not isinstance(pk[0].type, Integer):
        return
    name = pk[0].name
    conn.execute(
        text(
            f"SELECT setval(pg_get_serial_sequence('{table.name}', '{name}'), "
            f'COALESCE((SELECT MAX("{name}") FROM "{table.name}"), 0) + 1, false)'
        )
    )


def copy_database(source_url: str, target_url: str, batch: int = 1000) -> Report:
    problems = precheck(source_url)
    if problems:
        raise CopyError("Fix these rows before the copy:\n" + "\n".join(problems))
    src = create_engine(source_url)
    dst = make_engine(target_url)
    try:
        init_db(dst)
        source_tables = set(_reflect(src).tables)
        with dst.connect() as conn:
            busy = [t.name for t in _models() if conn.execute(select(func.count()).select_from(t)).scalar()]
        if busy:
            raise CopyError(f"The target already holds rows in: {', '.join(busy)}")

        report = Report()
        src_meta = _reflect(src)
        with src.connect() as sconn, dst.begin() as dconn:
            for model in _models():
                if model.name not in source_tables:
                    continue
                columns = [c.name for c in model.columns if c.name in src_meta.tables[model.name].c]
                chunk = []
                for row in _rows(sconn, model, columns):
                    chunk.append({c: _to_target(v) for c, v in zip(columns, row)})
                    if len(chunk) >= batch:
                        dconn.execute(model.insert(), chunk)
                        chunk = []
                if chunk:
                    dconn.execute(model.insert(), chunk)
                if dst.dialect.name == "postgresql":
                    _reset_sequences(dconn, model)

        with src.connect() as sconn, dst.connect() as dconn:
            for model in _models():
                if model.name not in source_tables:
                    continue
                columns = [c.name for c in model.columns if c.name in src_meta.tables[model.name].c]
                s_rows, s_sum = _checksum(sconn, model, columns)
                t_rows, t_sum = _checksum(dconn, model, columns)
                report.tables.append(TableReport(model.name, s_rows, t_rows, s_sum, t_sum))
        return report
    finally:
        src.dispose()
        dst.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sqlite", default="sqlite:///./auth.db", help="source (default sqlite:///./auth.db)")
    parser.add_argument("--postgres", help="target, postgresql+psycopg://user:pass@host:port/db")
    parser.add_argument("--check-only", action="store_true", help="list problem rows and stop")
    args = parser.parse_args(argv)

    problems = precheck(args.sqlite)
    for line in problems:
        print(line)
    if args.check_only:
        print("precheck: no problems" if not problems else f"precheck: {len(problems)} problem rows")
        return 1 if problems else 0
    if not args.postgres:
        parser.error("--postgres is required unless --check-only")
    try:
        report = copy_database(args.sqlite, args.postgres)
    except CopyError as exc:
        print(exc)
        return 1
    print(report.render())
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
