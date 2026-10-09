"""Make a new Ed25519 signing key for entitlements (lic) or releases (rel).

    cd server
    .venv\\Scripts\\python.exe scripts\\make_signing_key.py --kind lic
    .venv\\Scripts\\python.exe scripts\\make_signing_key.py --kind rel --out D:\\keys\\rel-2026-10.json

Prints the kid, the public key and the private seed, and the server/.env
lines to add. Contract §3: the public half goes into the app's pinned keys
(Config/LicenceKeys.json) first; sign with a new kid no earlier than 30 days
after an app release pins it.

* lic: the seed goes into server/.env as LICENCE_SIGNING_KEY (never commit it).
* rel: the seed NEVER goes on the API host. Keep the --out file somewhere
  only you can read (not in the repo); publish_release.py --key-file reads
  it. server/.env gets only the public half, in RELEASE_PUBLIC_KEYS.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.licence import signing  # noqa: E402


def make(kind: str, kid: str | None = None) -> dict:
    kid = kid or f"{kind}-{datetime.now(timezone.utc):%Y-%m}"
    if not kid.startswith(f"{kind}-"):
        raise SystemExit(f"a {kind} key's kid must start with '{kind}-'")
    seed = signing.new_seed()
    public = signing.public_key_b64url(signing.private_key_from_seed(seed))
    use = "entitlement" if kind == "lic" else "release"
    return {"kid": kid, "alg": "Ed25519", "use": use, "public_key": public, "private_key": seed}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--kind", choices=("lic", "rel"), required=True)
    ap.add_argument("--kid", help="default: <kind>-YYYY-MM")
    ap.add_argument("--out", help="also write the key (with its private seed) to this JSON file")
    args = ap.parse_args(argv)

    key = make(args.kind, args.kid)
    if args.out:
        out = Path(args.out)
        if out.exists():
            raise SystemExit(f"{out} exists; refusing to overwrite a key")
        out.write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")

    print(f"kid:         {key['kid']}")
    print(f"public key:  {key['public_key']}")
    print(f"private seed (secret): {key['private_key']}")
    print()
    if args.kind == "lic":
        print("Add to server/.env (never commit it):")
        print(f"LICENCE_SIGNING_KEY={key['private_key']}")
        print(f"LICENCE_KEY_ID={key['kid']}")
    else:
        print("Keep the seed OFF the API host: save the key file outside the repo"
              + (f" (written to {args.out})." if args.out else " (re-run with --out <file>)."))
        print("Add the public half to server/.env (comma-separate several):")
        print(f"RELEASE_PUBLIC_KEYS={key['kid']}:{key['public_key']}")
    print()
    print("Pin the public key in the app (Config/LicenceKeys.json) before signing with this kid.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
