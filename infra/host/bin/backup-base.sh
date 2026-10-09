#!/bin/sh
# Nightly base backup (systemd: truebex-backup.timer). WAL is archived
# continuously by Postgres itself (archive_command = wal-g wal-push).
# Keeps 30 nightly bases and the WAL they need (placeholder from GD3), then
# records `backup.base` so the API's backup.check job can alert on staleness.
set -eu
cd /opt/truebex
dc() { docker compose "$@"; }

dc exec -T postgres sh -c 'su postgres -s /bin/sh -c "wal-g backup-push \"$PGDATA\""'
dc exec -T postgres sh -c 'su postgres -s /bin/sh -c "wal-g delete retain FULL 30 --confirm"'
dc exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "INSERT INTO ops_status (name, at, detail) VALUES ('"'"'backup.base'"'"', now(), NULL) ON CONFLICT (name) DO UPDATE SET at = excluded.at"'
echo "base backup OK $(date -u +%Y-%m-%dT%H:%M:%SZ)"
