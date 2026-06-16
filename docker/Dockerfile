# Canonical, reproducible test/dev environment for SysML v2 work in Gaphor.
#
# Why Ubuntu 25.10: Gaphor requires libadwaita >= 1.8 (verified against
# gaphor/conftest.py importing the UI stack). The development host is Ubuntu
# 24.04 LTS, whose repos cap libadwaita at 1.5.0 with no newer candidate, so the
# host Poetry venv cannot import gaphor.ui. Of the bases checked on 2026-06-16,
# only Ubuntu 25.10 cleared the floor: libadwaita 1.8.0, GTK 4.20, PyGObject
# 3.50 (Fedora 41 had 1.6.10, Fedora 42 had 1.7.12 - both too old). This image
# is the source of truth for the runtime; poetry.lock is the source of truth for
# Python dependencies. Both CI and local dev run THIS image so "verified" means
# the same thing everywhere.
# Pinned by digest for reproducibility. Refresh the digest deliberately when
# picking up security updates (tag `25.10` would otherwise drift silently):
#   docker pull ubuntu:25.10 && docker images --digests ubuntu:25.10
FROM ubuntu:25.10@sha256:4a9232cc47bf99defcc8860ef6222c99773330367fcecbf21ba2edb0b810a31e

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    # GTK4 software renderer: reliable in headless and X11-passthrough cases
    # without depending on host GPU/driver specifics. Override at run time for
    # hardware acceleration if desired.
    GSK_RENDERER=cairo

# System runtime: GTK4 + libadwaita >= 1.8 + GObject introspection so
# `import gaphor.ui` and the GTK-dependent test suite work. xvfb provides a
# virtual display for headless pytest (this is how Gaphor's own CI runs GUI
# tests). git + curl support poetry and local workflows.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-dev python3-venv python3-pip pipx \
        libgtk-4-1 gir1.2-gtk-4.0 \
        libadwaita-1-0 gir1.2-adw-1 \
        gir1.2-gtksource-5 \
        libgirepository-2.0-dev gobject-introspection \
        libcairo2-dev pkg-config \
        graphviz \
        xvfb \
        git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Pin Poetry via pipx (decoupled from the project venv). virtualenvs.in-project
# keeps the resolved environment next to the checkout for transparency.
ENV PATH="/root/.local/bin:${PATH}"
# Make pip resilient to transient network blips during the build (the install
# layer otherwise fails the whole image build on a single dropped download,
# which made docker/run-tests.sh non-deterministic).
ENV PIP_RETRIES=5 \
    PIP_TIMEOUT=60 \
    PIP_DEFAULT_TIMEOUT=60
# Poetry pinned to match the project's existing pin in
# .github/github-requirements.txt and the version that resolved poetry.lock.
RUN pipx install poetry==2.4.1 \
    && poetry config virtualenvs.in-project true \
    && poetry config installer.max-workers 4

WORKDIR /workspace

# Install dependencies in a cached layer keyed on the lockfile, so source edits
# do not trigger a reinstall. Dependencies come from poetry.lock (the dep source
# of truth); --with dev pulls pytest, pytest-asyncio, pytest-cov, etc.
COPY pyproject.toml poetry.lock ./
RUN poetry install --with dev --no-root

# The full source is bind-mounted at run time (see docker/run-tests.sh and
# docker/run-gui.sh), so it is not COPYed here - that keeps the image stable
# across edits and avoids stale copies.

CMD ["bash"]
