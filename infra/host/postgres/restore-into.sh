#!/bin/sh
# Entry point of the scratch container the weekly restore test starts
# (infra/host/bin/restore-test.sh): fetch the latest base backup, replay the
# archived WAL to its end, then run Postgres without archiving.
set -eu
: "${PGDATA:?}"
if [ ! -s "$PGDATA/PG_VERSION" ]; then
  mkdir -p "$PGDATA"
  chown postgres:postgres "$PGDATA"
  chmod 0700 "$PGDATA"
  su postgres -s /bin/sh -c "wal-g backup-fetch '$PGDATA' LATEST"
  su postgres -s /bin/sh -c "touch '$PGDATA/recovery.signal'"
  cat >> "$PGDATA/postgresql.auto.conf" <<CONF
restore_command = 'wal-g wal-fetch %f %p'
recovery_target_action = 'promote'
CONF
fi
exec docker-entrypoint.sh postgres -c archive_mode=off
