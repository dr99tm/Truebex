#!/bin/bash
# The analysis images' entrypoint (PF11): run.sh <kind> [job dir]
# The worker wrapper mounts the job folder at /job; the runner reads
# /job/job.json and writes /job/out/ (server/app/analysis/runners/).
set -e
KIND="${1:?usage: run.sh <wind|energy|acoustics|texture|airflow> [job dir]}"
JOB="${2:-/job}"
if [ "$KIND" = "wind" ]; then
  for rc in /usr/lib/openfoam/openfoam2406/etc/bashrc /opt/openfoam2406/etc/bashrc; do
    if [ -f "$rc" ]; then set +eu; . "$rc"; set -e; break; fi
  done
fi
export TRUEBEX_KIND="$KIND"
exec python3 -m "runners.$KIND" "$JOB"
