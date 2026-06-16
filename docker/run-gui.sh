#!/usr/bin/env bash
#
# run-gui.sh - launch Gaphor interactively from the container on the host display.
#
# This is a convenience, NOT the test foundation: correctness is proven by
# docker/run-tests.sh (headless). Use this when you want to click around the
# real app from the same reproducible environment the tests run in.
#
# Assumes an X11 host session (the dev host is X11: DISPLAY is set and
# /tmp/.X11-unix exists). For a Wayland host, mount $XDG_RUNTIME_DIR/$WAYLAND_DISPLAY
# and set GDK_BACKEND=wayland instead.
#
# Usage:
#   docker/run-gui.sh            # launch `gaphor`
#   docker/run-gui.sh <args...>  # pass args to gaphor (e.g. a .gaphor file)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="gaphor-sysml2-test"

if [[ -z "${DISPLAY:-}" ]]; then
    echo "ERROR: DISPLAY is unset - no X11 session to render into." >&2
    echo "       On Wayland, adapt this script to mount the wayland socket." >&2
    exit 1
fi

echo "Building $IMAGE (Ubuntu 25.10, libadwaita >= 1.8)..."
docker build -t "$IMAGE" -f "$REPO_ROOT/docker/Dockerfile" "$REPO_ROOT"

# Allow the container's X client to connect to the host X server. Scoped to
# local connections; revoke afterwards.
xhost +local: >/dev/null 2>&1 || true
trap 'xhost -local: >/dev/null 2>&1 || true' EXIT

# GPU is optional. Default to software rendering (GSK_RENDERER=cairo, baked into
# the image) for reliability. To try hardware accel, add: --device /dev/dri .
docker run --rm -it \
    --volume "$REPO_ROOT:/workspace:Z" \
    --volume /tmp/.X11-unix:/tmp/.X11-unix:rw \
    --env "DISPLAY=$DISPLAY" \
    --workdir /workspace \
    "$IMAGE" \
    bash -lc "poetry install --with dev >/dev/null && poetry run gaphor $*"
