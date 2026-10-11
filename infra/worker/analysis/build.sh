#!/usr/bin/env bash
# Build an analysis runner image (PF11):
#   build.sh <wind|energy|acoustics|texture> [tag] [--build-arg K=V ...]
set -euo pipefail
KIND="${1:?usage: build.sh <wind|energy|acoustics|texture> [tag] [--build-arg K=V ...]}"
shift
TAG="1"
if [ "$#" -gt 0 ] && [ "${1#--}" = "$1" ]; then TAG="$1"; shift; fi
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
command -v docker >/dev/null || { echo "docker is not installed" >&2; exit 1; }
CTX="$(mktemp -d)"
trap 'rm -rf "$CTX"' EXIT
cp -r "$REPO/server/app/analysis/runners" "$CTX/runners"
find "$CTX/runners" -name __pycache__ -type d -prune -exec rm -rf {} +
tr -d '\r' < "$HERE/run.sh" > "$CTX/run.sh"
cp "$HERE/$KIND/Dockerfile" "$CTX/Dockerfile"
IMAGE="truebex-analysis-$KIND:$TAG"
docker build -t "$IMAGE" --build-arg "TRUEBEX_IMAGE=$IMAGE" "$@" "$CTX"
echo "built $IMAGE"
