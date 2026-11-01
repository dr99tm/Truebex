#!/usr/bin/env bash
# Sets up this repo on Linux (cloud sessions, CI, a Linux server) and checks it. The Windows-only parts
# (Autopilot gates, sync scripts, the mobile app) are in setup\setup.ps1; setup/README.md lists everything.
#   bash setup/setup.sh            install what's missing, then check
#   bash setup/setup.sh --check    check only
#   bash setup/setup.sh --quiet    less output (the cloud SessionStart hook)
set -uo pipefail
cd "$(dirname "$0")/.."
CHECK=0; QUIET=0
for a in "$@"; do case "$a" in --check) CHECK=1;; --quiet) QUIET=1;; esac; done
log() { [ "$QUIET" = 1 ] || echo "== $*"; }
SUDO=""; [ "$(id -u)" = 0 ] || SUDO="sudo"
missing=0

ver() { "$@" 2>&1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1; }
at_least() { [ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -1)" = "$2" ]; }  # at_least have min
report() { printf '%-8s %-10s %-12s %s\n' "$1" "$2" "$3" "$4"; [ "$1" = MISSING ] && missing=$((missing+1)); return 0; }

apt_install() {
  command -v apt-get >/dev/null || return 1
  $SUDO apt-get update -qq >/dev/null 2>&1 || true
  DEBIAN_FRONTEND=noninteractive $SUDO apt-get install -y -qq "$@" >/dev/null 2>&1
}

# node >=22 <26
nv=$(command -v node >/dev/null && ver node --version)
if { [ -z "$nv" ] || ! at_least "$nv" 22.0 || at_least "$nv" 26.0; } && [ "$CHECK" = 0 ]; then
  log "installing node 24 with fnm"
  curl -fsSL https://fnm.vercel.app/install | bash -s -- --skip-shell >/dev/null 2>&1
  export PATH="$HOME/.local/share/fnm:$PATH"; eval "$(fnm env)"; fnm install 24 >/dev/null && fnm default 24
  nv=$(ver node --version)
fi

# python 3.12 (the pins don't install on 3.13+)
PY=""
for c in python3.12 python3; do
  command -v $c >/dev/null && v=$(ver $c --version) && at_least "$v" 3.12 && ! at_least "$v" 3.13 && { PY=$c; break; }
done
if [ -z "$PY" ] && [ "$CHECK" = 0 ]; then
  log "installing python 3.12"
  apt_install python3.12 python3.12-venv || { command -v uv >/dev/null && uv python install 3.12 >/dev/null; }
  command -v python3.12 >/dev/null && PY=python3.12
  [ -z "$PY" ] && command -v uv >/dev/null && PY="$(uv python find 3.12 2>/dev/null)"
fi

if [ "$CHECK" = 0 ]; then
  if [ -n "$nv" ]; then log "npm ci"; npm ci --no-audit --no-fund >/dev/null 2>&1 || npm ci --no-audit --no-fund; fi
  if [ -n "$PY" ]; then
    [ -x server/.venv/bin/python ] || { log "server venv"; "$PY" -m venv server/.venv || { apt_install python3.12-venv && "$PY" -m venv server/.venv; }; }
    log "server packages"; server/.venv/bin/python -m pip install --disable-pip-version-check -q -r server/requirements-dev.txt
  fi
  [ -f .env.local ] || cp .env.example .env.local
fi

[ "$QUIET" = 1 ] && [ "$missing" = 0 ] && [ -n "$nv" ] && [ -n "$PY" ] && exit 0
echo "Truebex platform: setup check"
[ -n "$nv" ] && at_least "$nv" 22.0 && ! at_least "$nv" 26.0 && report ok tool node "$nv" || report MISSING tool node ">=22 <26 (have ${nv:-none})"
[ -n "$PY" ] && report ok tool python "$(ver $PY --version) ($PY)" || report MISSING tool python "3.12.x"
[ -x server/.venv/bin/python ] && report ok venv server/.venv "" || report MISSING venv server/.venv "run without --check"
[ -d node_modules ] && report ok deps node_modules "" || report MISSING deps node_modules "npm ci"
command -v pg_ctl >/dev/null || ls /usr/lib/postgresql/*/bin/pg_ctl >/dev/null 2>&1 \
  && report ok tool postgres "binaries" || report warn tool postgres "optional: postgres-marked tests (apt install postgresql)"
command -v msedge >/dev/null || command -v microsoft-edge >/dev/null || command -v chromium >/dev/null \
  && report ok tool browser "" || report warn tool browser "optional: headless self-test drivers"
[ -d /t/unreal5_7_4_projects/truebex_compact ] || report warn repo truebex_compact "app checkout absent: contract-fixture tests skip"
[ "$missing" = 0 ] || { echo "$missing required item(s) missing"; exit 1; }
