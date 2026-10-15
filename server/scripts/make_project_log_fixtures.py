"""Retired (PF4a, 2026-10-15): the project-log contract fixtures are the app's.

PF4 wrote a stand-in set into server/tests/contracts/project-log/ here while
the app repository had none (stand-in deltas, PF4's own entity ids). CL1 now
writes the set from the app's own code (`-mwcl1fixtures`) into
`Docs/roadmap/fixtures/contracts/project-log/`, and the platform copies it
byte for byte:

    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\sync-contract-fixtures.ps1 -Contract project-log

then updates `APP_BLOBS` in server/tests/test_pf4a_project_log_1_1.py and the
folder's README. Writing a set here would overwrite the app's, so this script
only says so. PF4's stand-in set is in git history (before PF4a).
"""

import sys

if __name__ == "__main__":
    print(__doc__.strip(), file=sys.stderr)
    sys.exit(1)
