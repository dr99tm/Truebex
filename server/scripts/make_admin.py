"""Make an account an admin (or take it back): admins open /admin/* and the
dashboard's Telemetry page. Run where the API's settings are:

    cd server
    .venv\\Scripts\\python.exe -m scripts.make_admin owner@example.com
    .venv\\Scripts\\python.exe -m scripts.make_admin owner@example.com --revoke
"""

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a file: make `app` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal, init_db  # noqa: E402
from app.models import User  # noqa: E402


def set_admin(email: str, admin: bool = True) -> bool:
    init_db()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email.strip().lower()))
        if user is None:
            return False
        user.is_admin = admin
        db.commit()
        return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("email")
    parser.add_argument("--revoke", action="store_true", help="remove admin rights instead")
    args = parser.parse_args(argv)
    if not set_admin(args.email, not args.revoke):
        print(f"no account with the email {args.email}")
        return 1
    print(f"{args.email}: {'no longer an admin' if args.revoke else 'admin'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
