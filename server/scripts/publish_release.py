"""Publish an installer to the release feed (contract licence-api 5.13, §6.4).

    cd server
    .venv\\Scripts\\python.exe scripts\\publish_release.py --version 1.1.0 --channel stable ^
        --platform win64 --file D:\\builds\\Truebex-Setup-1.1.0.exe --notes notes.md ^
        --key-file D:\\keys\\rel-2026-10.json --symbols D:\\builds\\1.1.0\\Symbols

Runs against the API's own database and storage (server/.env, or the
production settings in the environment): hashes the installer, writes the
truebex-release/1 manifest, signs it with the rel-* key from --key-file (made
by make_signing_key.py --kind rel; the seed never lives in server/.env),
stores the file at releases/{version}/{platform}/{file} and registers the
row. Prints the version, SHA-256 and storage key. The website picks it up
after `npm run sync:releases` and a rebuild.

--symbols <dir> (PF14): the build's private .sym / .pdb files, handed to
scripts.upload_symbols.upload() once the release is published, so that
version's crash reports get function names. The folder is checked before
anything is published; a failed upload leaves the release published and
prints the upload_symbols command that retries it.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.contract_http import ContractError  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402
from app.licence import signing  # noqa: E402
from app.releases import service  # noqa: E402
from app.storage import get_store  # noqa: E402
from scripts import upload_symbols  # noqa: E402


def load_key(path: str, kid: str | None = None):
    """A make_signing_key.py JSON file, or a text file holding just the seed (then --kid)."""
    text = Path(path).read_text(encoding="utf-8-sig").strip()
    if text.startswith("{"):
        data = json.loads(text)
        seed, kid = data["private_key"], kid or data["kid"]
    else:
        seed = text.split()[0]
    if not kid or not kid.startswith("rel-"):
        raise SystemExit("release keys have a kid starting 'rel-' (pass --kid with a seed-only file)")
    return signing.private_key_from_seed(seed), kid


def publish(
    *,
    version: str,
    channel: str,
    platform: str,
    file: str,
    notes_md: str,
    key_file: str,
    kid: str | None = None,
    mandatory: bool = False,
    min_update_from: str | None = None,
):
    key, kid = load_key(key_file, kid)
    published = signing.keys_by_use("release")
    if published.get(kid) != signing.public_key_b64url(key):
        print(
            f"warning: {kid} is not in RELEASE_PUBLIC_KEYS in server/.env; GET /licence/keys will not list it "
            f"(add RELEASE_PUBLIC_KEYS={kid}:{signing.public_key_b64url(key)})",
            file=sys.stderr,
        )
    init_db()
    with SessionLocal() as db:
        return service.publish(
            db,
            get_store(),
            version=version,
            channel=channel,
            platform=platform,
            file_path=file,
            notes_md=notes_md,
            private_key=key,
            kid=kid,
            mandatory=mandatory,
            min_update_from=min_update_from,
        )


def symbols_problem(folder: Path, dump_syms: str | None) -> str | None:
    """Why --symbols cannot be uploaded, found before the release is published."""
    if not folder.is_dir():
        return f"--symbols {folder} is not a folder"
    files = upload_symbols._files([folder])
    if not files:
        return f"--symbols {folder} holds no .sym or .pdb files"
    if any(f.suffix.lower() == ".pdb" for f in files):
        exe = dump_syms or "dump_syms"
        if not (shutil.which(exe) or Path(exe).is_file()):
            return f"--symbols {folder} holds .pdb files but {exe} was not found (install dump_syms or pass --dump-syms)"
    return None


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Publish an installer to the release feed.")
    ap.add_argument("--version", required=True, help="SemVer 2.0.0, e.g. 1.1.0 or 1.2.0-beta.3")
    ap.add_argument("--channel", choices=service.CHANNELS, required=True)
    ap.add_argument("--platform", choices=service.PLATFORMS, default="win64")
    ap.add_argument("--file", required=True, help="the installer")
    ap.add_argument("--notes", required=True, help="release notes in Markdown (headings, bullets, bold, links)")
    ap.add_argument("--key-file", required=True, help="the rel-* key file (kept off the API host)")
    ap.add_argument("--kid", help="the key id when --key-file holds only a seed")
    ap.add_argument("--mandatory", action="store_true")
    ap.add_argument("--min-update-from", help="the oldest version that may update straight to this one")
    ap.add_argument("--symbols", type=Path, help="folder of the build's .sym / .pdb files, uploaded after publishing")
    ap.add_argument("--dump-syms", help="dump_syms for the .pdb files under --symbols (default: on PATH)")
    args = ap.parse_args(argv)
    if args.symbols is not None and (problem := symbols_problem(args.symbols, args.dump_syms)):
        ap.error(problem)

    notes = Path(args.notes).read_text(encoding="utf-8-sig")
    try:
        row = publish(
            version=args.version,
            channel=args.channel,
            platform=args.platform,
            file=args.file,
            notes_md=notes,
            key_file=args.key_file,
            kid=args.kid,
            mandatory=args.mandatory,
            min_update_from=args.min_update_from,
        )
    except ContractError as exc:
        print(f"error: {exc.detail}", file=sys.stderr)
        return 1
    manifest = json.loads(row.manifest)
    print(f"version:     {row.version} ({row.channel}, {row.platform})")
    print(f"bytes:       {manifest['installer']['bytes']}")
    print(f"sha256:      {manifest['installer']['sha256']}")
    print(f"storage key: {row.storage_key}")
    print(f"signed by:   {row.kid}")
    if args.symbols is None:
        return 0
    try:
        symbols = upload_symbols.upload([args.symbols], args.version, args.dump_syms)
    except (RuntimeError, ValueError) as exc:
        print(f"error: {args.version} is published, but its symbols were not uploaded: {exc}", file=sys.stderr)
        dump = f" --dump-syms {args.dump_syms}" if args.dump_syms else ""
        print(f"retry: python -m scripts.upload_symbols --version {args.version}{dump} {args.symbols}", file=sys.stderr)
        return 1
    for sym in symbols:
        print(f"symbols:     {sym.module}  {sym.debug_id}  {sym.key}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
