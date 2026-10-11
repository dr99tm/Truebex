"""A stand-in for the docker CLI (PF11 tests).

`run [flags] -v <host dir>:/job <image>` runs the stub solver on <host dir>
(and records the arguments in `<host dir>/docker-args.json`); `kill <name>`
does nothing.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run as stub  # noqa: E402

args = sys.argv[1:]
if not args or args[0] == "kill":
    sys.exit(0)
mount = args[args.index("-v") + 1]
host = Path(mount.rsplit(":/job", 1)[0])
(host / "docker-args.json").write_text(json.dumps(args), encoding="utf-8")
sys.exit(stub.main(host))
