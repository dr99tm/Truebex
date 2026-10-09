"""Grant or remove the admin flag (`users.is_admin`), which is set by hand.

    .venv\\Scripts\\python.exe -m app.admin_cli you@example.com          (grant)
    .venv\\Scripts\\python.exe -m app.admin_cli you@example.com --off    (remove)

Uses DATABASE_URL from server/.env like the API. The account must exist
(sign up first).
"""

import sys

from sqlalchemy import select

from .database import SessionLocal, init_db
from .models import User


def set_admin(email: str, on: bool = True) -> bool:
    """Set the flag; False when no account has that e-mail address."""
    init_db()  # adds the is_admin column to an older database
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email.strip().lower()))
        if user is None:
            return False
        user.is_admin = on
        db.commit()
        return True


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__)
        return 2
    on = "--off" not in argv
    if not set_admin(args[0], on):
        print(f"no account for {args[0]}")
        return 1
    print(f"{args[0]}: admin {'on' if on else 'off'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
