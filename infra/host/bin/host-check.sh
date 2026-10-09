#!/bin/sh
# Host checks every minute (systemd: truebex-host-check.timer). The hosted
# uptime monitor watches /health and /health/deep from outside; this covers
# what it cannot see, and pings its heartbeat so a dead host alerts too.
#
#   disk > 85 % · memory available < 10 % · 5-min load > 2 x cores ·
#   a container restarted or unhealthy · Caddy 5xx > 5 % of the last 5 min
#   (at least 20 requests) · origin certificate expiring within 14 days ·
#   PF6's queue depth when /opt/truebex/bin/queue-depth exists
#
# Alerts (once per change of the problem list): phone push to ALERT_PUSH_URL
# and e-mail through the worker's mail adapter. Settings: /opt/truebex/secrets/host.env.
set -u
cd /opt/truebex
[ -f secrets/host.env ] && . secrets/host.env
STATE=/var/lib/truebex
mkdir -p "$STATE"
problems=""
add() { problems="${problems}${1}
"; }

disk=$(df --output=pcent / | tail -1 | tr -dc '0-9')
[ "${disk:-0}" -gt 85 ] && add "disk ${disk}% full"

mem=$(awk '/MemTotal/ {t=$2} /MemAvailable/ {a=$2} END {printf "%d", a * 100 / t}' /proc/meminfo)
[ "${mem:-100}" -lt 10 ] && add "memory: only ${mem}% available"

cores=$(nproc)
load=$(cut -d' ' -f2 /proc/loadavg)
awk -v l="$load" -v c="$cores" 'BEGIN { exit !(l > 2 * c) }' && add "load ${load} on ${cores} cores"

for id in $(docker compose ps -q); do
  name=$(docker inspect -f '{{.Name}}' "$id" | tr -d /)
  restarts=$(docker inspect -f '{{.RestartCount}}' "$id")
  health=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$id")
  last=$(cat "$STATE/restarts-$name" 2>/dev/null || echo "$restarts")
  [ "$restarts" -gt "$last" ] && add "$name restarted ($((restarts - last))x)"
  echo "$restarts" > "$STATE/restarts-$name"
  [ "$health" = "unhealthy" ] && add "$name is unhealthy"
done
for svc in api worker postgres caddy; do
  docker compose ps --status running --services | grep -qx "$svc" || add "$svc is not running"
done

LOG=/var/log/truebex/caddy/access.log
if [ -f "$LOG" ]; then
  since=$(($(date +%s) - 300))
  rate=$(tail -n 20000 "$LOG" | jq -r --argjson since "$since" 'select(.ts >= $since) | .status' 2>/dev/null |
    awk '{ n++; if ($1 >= 500) e++ } END { if (n >= 20 && e * 100 / n > 5) printf "%d%% of %d", e * 100 / n, n }')
  [ -n "$rate" ] && add "5xx responses: $rate requests in 5 min"
fi

if [ -f secrets/origin.pem ] && ! openssl x509 -checkend $((14 * 86400)) -noout -in secrets/origin.pem >/dev/null; then
  add "origin certificate expires within 14 days"
fi

if [ -x bin/queue-depth ]; then
  depth=$(bin/queue-depth 2>/dev/null || echo 0)
  [ "${depth:-0}" -gt "${QUEUE_DEPTH_MAX:-50}" ] && add "job queue depth $depth"
fi

previous=$(cat "$STATE/problems" 2>/dev/null || true)
printf '%s' "$problems" > "$STATE/problems"
notify() {
  if [ -n "${ALERT_PUSH_URL:-}" ]; then
    curl -fsS -m 10 -H "Title: $1" -H "Priority: high" -d "$2" "$ALERT_PUSH_URL" >/dev/null || true
  fi
  docker compose exec -T worker python -m app.ops alert "$1" "$2" >/dev/null 2>&1 || true
}
if [ -n "$problems" ] && [ "$problems" != "$previous" ]; then
  notify "Truebex host needs attention" "$problems"
elif [ -z "$problems" ] && [ -n "$previous" ]; then
  notify "Truebex host is healthy again" "All host checks pass."
fi

# Dead man's switch: the monitor alerts when these pings stop.
if [ -z "$problems" ] && [ -n "${HEARTBEAT_URL:-}" ]; then
  curl -fsS -m 10 "$HEARTBEAT_URL" >/dev/null || true
fi
exit 0
