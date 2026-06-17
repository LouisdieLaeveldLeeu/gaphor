#!/usr/bin/env bash
#
# run-tests.sh - canonical headless test run for SysML v2 work.
#
# Builds the Ubuntu 25.10 image (libadwaita >= 1.8) and runs pytest inside it
# against the live source tree (bind-mounted), headless via xvfb. This is the
# authoritative local equivalent of CI: same image, same deps from poetry.lock.
#
# Target contract (full suite is always intentional, never accidental):
#   docker/run-tests.sh                    # SysML2 subset (fast default)
#   docker/run-tests.sh -q                 # SysML2 subset with pytest flags
#   docker/run-tests.sh gaphor/SysML2 -q   # explicit subset/path with flags
#   docker/run-tests.sh --full             # whole Gaphor suite
#   docker/run-tests.sh --full -q          # whole suite with pytest flags
#
# `--full` is a wrapper-only flag (consumed here, not forwarded). When it is
# absent and no explicit path is given, the SysML2 subset is used -- so a
# flag-only invocation like `-q` runs the subset, NOT an accidental full suite.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="gaphor-sysml2-test"

echo "Building $IMAGE (Ubuntu 25.10, libadwaita >= 1.8)..."
docker build -t "$IMAGE" -f "$REPO_ROOT/docker/Dockerfile" "$REPO_ROOT"

# Parse the wrapper-only --full flag; forward the rest to pytest.
FULL=0
FORWARDED=()
has_path=0
for arg in "$@"; do
    if [[ "$arg" == "--full" ]]; then
        FULL=1
    else
        FORWARDED+=("$arg")
        # A path/node-id is any forwarded arg not starting with '-'.
        [[ "$arg" != -* ]] && has_path=1
    fi
done

# Decide the pytest target: --full -> whole suite; else an explicit path is
# honoured; else the SysML2 subset (so a flag-only run like `-q` is the subset,
# never an accidental full suite).
PYTEST_ARGS=()
[[ ${#FORWARDED[@]} -gt 0 ]] && PYTEST_ARGS=("${FORWARDED[@]}")
if [[ "$FULL" -eq 1 ]]; then
    PYTEST_ARGS+=("gaphor")
elif [[ "$has_path" -eq 0 ]]; then
    PYTEST_ARGS+=("gaphor/SysML2/tests")
fi

echo "Running pytest headless (xvfb): ${PYTEST_ARGS[*]}"
# --init runs tini as PID 1 so xvfb-run's child reaping and Xvfb readiness
# signalling work correctly (xvfb-run can hang as PID 1 in a container).
#
# --no-root was used at build time; install the project itself now (cheap) so
# `import gaphor.SysML2` resolves against the bind-mounted source.
#
# pytest args are passed as positional parameters ("$@") into the inner shell,
# not interpolated into the command string, so quoted args (e.g. -k "a or b")
# survive intact.
# Compile the shipped GSettings schema into a dir on GSETTINGS_SCHEMA_DIR before
# running, so tests that touch Gaphor settings find org.gaphor.Gaphor (the schema
# source is in the bind-mounted repo, not baked into the image).
docker run --rm --init \
    --volume "$REPO_ROOT:/workspace:Z" \
    --workdir /workspace \
    --env GSETTINGS_SCHEMA_DIR=/tmp/glib-schemas \
    "$IMAGE" \
    bash -lc '
        poetry install --with dev >/dev/null
        mkdir -p /tmp/glib-schemas
        cp gaphor/ui/installschemas/org.gaphor.Gaphor.gschema.xml /tmp/glib-schemas/
        glib-compile-schemas /tmp/glib-schemas
        xvfb-run -a poetry run pytest "$@"
    ' _ "${PYTEST_ARGS[@]}"
