"""Upload a release's private Breakpad symbols (PF14), run on the API host or
any machine with the production settings:

    cd server
    .venv\\Scripts\\python.exe -m scripts.upload_symbols --version 1.1.0 <folder or files>

Takes `.sym` files as they are and `.pdb` files through `dump_syms` (MIT /
Apache-2.0; `--dump-syms` or on PATH). Each file lands in storage at
`symbols/{module}/{debug_id}/{module stem}.sym` with a `symbol_files` row, and
the `crash.symbolicate` job names the frames of that version's crashes within
a minute. Symbols are private: nothing serves them.

PF1's `publish_release.py --symbols <dir>` calls `upload()` with the Shipping
PDBs from the package gate.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a file: make `app` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, init_db  # noqa: E402
from app.models import SymbolFile  # noqa: E402
from app.routers.admin_telemetry import store_symbols  # noqa: E402


def _files(paths: list[Path]) -> list[Path]:
    out = []
    for path in paths:
        if path.is_dir():
            out += sorted(p for p in path.rglob("*") if p.suffix.lower() in (".sym", ".pdb"))
        elif path.suffix.lower() in (".sym", ".pdb"):
            out.append(path)
    return out


def _dump(pdb: Path, dump_syms: str) -> bytes:
    try:
        proc = subprocess.run([dump_syms, str(pdb)], capture_output=True, timeout=600, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"could not run dump_syms ({dump_syms}): {exc}") from exc
    if proc.returncode != 0:
        raise RuntimeError(f"dump_syms failed on {pdb.name}: {proc.stderr.decode(errors='replace')[:400]}")
    return proc.stdout


def upload(paths: list[Path], version: str, dump_syms: str | None = None) -> list[SymbolFile]:
    """Store every .sym (and dumped .pdb) under `version`; returns the rows."""
    exe = dump_syms or shutil.which("dump_syms")
    init_db()
    rows = []
    with SessionLocal() as db:
        for path in _files(paths):
            if path.suffix.lower() == ".pdb":
                if not exe:
                    raise RuntimeError("found .pdb files but no dump_syms (pass --dump-syms)")
                data = _dump(path, exe)
            else:
                data = path.read_bytes()
            row = store_symbols(db, data, version)
            db.refresh(row)
            db.expunge(row)
            rows.append(row)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", required=True, help="the app version these symbols belong to, e.g. 1.1.0")
    parser.add_argument("--dump-syms", help="path to dump_syms (default: on PATH)")
    parser.add_argument("paths", nargs="+", type=Path, help=".sym / .pdb files or folders holding them")
    args = parser.parse_args(argv)
    try:
        rows = upload(args.paths, args.version, args.dump_syms)
    except (RuntimeError, ValueError) as exc:
        print(f"FAIL: {exc}")
        return 1
    if not rows:
        print("no .sym or .pdb files found")
        return 1
    for row in rows:
        print(f"{row.version}  {row.module}  {row.debug_id}  {row.key}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
