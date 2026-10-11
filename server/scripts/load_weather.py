"""Add an EPW weather file to the energy kind's library (PF11).

    py -3.12 scripts\\load_weather.py gbr-london-tmyx path\\to\\file.epw ^
        --name "London Heathrow, typical year" --source "<URL or dataset>" --licence "<licence>"

Runs against the database and storage of server/.env (like the API). The
source and licence of every file are recorded for GD2; nothing is committed
to the repository. The same as PUT /admin/analysis/weather/{id} for admins.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.analysis import weather  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("weather_id", help="3 to 64 lowercase letters, digits and dashes (what params.weather names)")
    parser.add_argument("epw", type=Path)
    parser.add_argument("--name", required=True)
    parser.add_argument("--source", required=True, help="where the file came from (a URL or a dataset name)")
    parser.add_argument("--licence", required=True, help="the licence it is used under")
    parser.add_argument("--location", help="override the EPW's LOCATION line")
    args = parser.parse_args(argv)
    init_db()
    with SessionLocal() as db:
        row = weather.put(
            db, args.weather_id, args.epw.read_bytes(), name=args.name, source=args.source, licence=args.licence,
            location=args.location,
        )
        print(f"{row.weather_id}: {row.location} ({row.bytes} bytes, sha256 {row.sha256[:12]}…)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
