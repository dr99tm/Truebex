#!/bin/sh
# Weekly restore test (systemd: truebex-restore-test.timer; on demand:
# infra/restore-test.ps1). Restores the latest base backup plus the archived
# WAL into a scratch container and compares row counts with production.
# Prints "restore OK" and exits 0 only when they match.
set -eu
cd /opt/truebex
NAME=truebex-restore-test
VOLUME=truebex-restore-test-data
# Tables that change every minute are compared loosely (restored <= production + 5 %).
VOLATILE="ops_status ratelimit_buckets telemetry_events telemetry_batches telemetry_daily crash_reports crash_groups feedback"

cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; docker volume rm "$VOLUME" >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup

psql_prod() { docker compose exec -T postgres sh -c "psql -At -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -c \"$1\""; }
psql_copy() { docker exec "$NAME" sh -c "psql -At -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -c \"$1\""; }
tables() { psql_prod "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY 1"; }

# 1. Production counts, then close the current WAL segment so it is archived.
PROD=$(mktemp)
for t in $(tables); do echo "$t $(psql_prod "SELECT count(*) FROM \\\"$t\\\"")"; done > "$PROD"
psql_prod "SELECT pg_switch_wal()" >/dev/null
sleep 20

# 2. Restore into a scratch container (no published port, no archiving).
docker run -d --name "$NAME" --env-file secrets/postgres.env \
  -e PGDATA=/var/lib/postgresql/18/docker -v "$VOLUME:/var/lib/postgresql" \
  --entrypoint /usr/local/bin/restore-into.sh truebex-postgres:18 >/dev/null
i=0
until docker exec "$NAME" sh -c 'pg_isready -q -U "$POSTGRES_USER"' && \
      [ "$(psql_copy 'SELECT pg_is_in_recovery()')" = "f" ]; do
  i=$((i + 1)); [ "$i" -gt 180 ] && { echo "restore FAILED: not ready after 15 min"; docker logs --tail 50 "$NAME"; exit 1; }
  sleep 5
done

# 3. Compare.
fail=0
while read -r t n; do
  m=$(psql_copy "SELECT count(*) FROM \\\"$t\\\"")
  case " $VOLATILE " in
    *" $t "*) ok=$(awk -v m="$m" -v n="$n" 'BEGIN { print (m <= n * 1.05 + 5 && (n == 0 || m > 0)) ? 1 : 0 }') ;;
    *) ok=$([ "$m" = "$n" ] && echo 1 || echo 0) ;;
  esac
  printf '%-24s production %8s  restored %8s  %s\n' "$t" "$n" "$m" "$([ "$ok" = 1 ] && echo ok || echo DIFFERS)"
  [ "$ok" = 1 ] || fail=1
done < "$PROD"
rm -f "$PROD"
if [ "$fail" = 0 ]; then
  docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "INSERT INTO ops_status (name, at) VALUES ('"'"'backup.restore_test'"'"', now()) ON CONFLICT (name) DO UPDATE SET at = excluded.at"' >/dev/null
  echo "restore OK"
else
  echo "restore FAILED: row counts differ"
  exit 1
fi
