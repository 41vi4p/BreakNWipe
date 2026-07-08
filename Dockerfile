# BreakNWipe container image
#
# Runs the full web GUI (FastAPI + built Next.js bundle) so users can pull the
# image, attach a physical drive, and drive everything from a host browser --
# no install on the host system. See docs/DOCKER.md for per-platform usage and
# honest limitations (full device access on Linux only; USB-only via usbipd-win
# on Windows; UI/API demo only on macOS -- Docker Desktop VMs have no block
# device passthrough).
#
#   docker build -t breaknwipe .
#   docker run --rm --privileged -v /dev:/dev -v /run/udev:/run/udev:ro \
#     -p 8000:8000 breaknwipe
#
# The vendoring layout deliberately mirrors scripts/build_packages.sh /
# scripts/install.sh: source + uv-managed venv + uv-managed Python all under
# /opt/breaknwipe. `uv sync` bakes absolute paths (managed-Python symlink,
# editable-install reference), so the build stage and runtime stage MUST use
# identical paths -- that's why everything is staged at its real final path.

# ---------------------------------------------------------------------------
# Stage 1: build the Next.js GUI static export (Node is build-time only;
# nothing from this stage ships except the out/ bundle).
# ---------------------------------------------------------------------------
FROM node:20-slim AS gui-builder

WORKDIR /gui
COPY breaknwipe/breaknwipe-gui/package.json breaknwipe/breaknwipe-gui/package-lock.json ./
RUN npm ci
COPY breaknwipe/breaknwipe-gui/ ./
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2: vendor the Python side with uv (managed Python + venv), same
# pattern and paths as scripts/build_packages.sh:prepare_build_environment.
# ---------------------------------------------------------------------------
FROM ubuntu:24.04 AS python-builder

RUN apt-get update -qq \
    && apt-get install -y -qq --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# --managed-python: uv downloads its own interpreter (deterministic, no
# dependency on the base image's Python), installed under /opt/breaknwipe/python.
ENV UV_PYTHON_INSTALL_DIR="/opt/breaknwipe/python"

COPY . /opt/breaknwipe/src/
RUN cd /opt/breaknwipe/src && uv sync --no-dev --managed-python

# ---------------------------------------------------------------------------
# Stage 3: runtime. Only the system tools BreakNWipe shells out to, plus the
# vendored /opt/breaknwipe tree and the built GUI bundle.
#
# Deliberately NOT installed (headless container; features self-disable via
# shutil.which): gparted (desktop escape hatch), adb/fastboot (Android wiping).
# ---------------------------------------------------------------------------
FROM ubuntu:24.04

LABEL org.opencontainers.image.title="BreakNWipe" \
      org.opencontainers.image.description="Secure data wiping utility with web GUI, verification, recovery, and blockchain-anchored certificates" \
      org.opencontainers.image.url="https://github.com/41vi4p/BreakNWipe" \
      org.opencontainers.image.source="https://github.com/41vi4p/BreakNWipe" \
      org.opencontainers.image.licenses="GPL-3.0-or-later"

# Same set as the .deb dependencies (scripts/build_packages.sh) plus the
# fsck.py binaries missing from that list: e2fsprogs (e2fsck/resize2fs),
# dosfstools (fsck.fat), exfatprogs (fsck.exfat).
RUN apt-get update -qq \
    && apt-get install -y -qq --no-install-recommends \
        ca-certificates \
        smartmontools \
        hdparm \
        nvme-cli \
        util-linux \
        parted \
        cloud-guest-utils \
        lvm2 \
        e2fsprogs \
        xfsprogs \
        btrfs-progs \
        ntfs-3g \
        dosfstools \
        exfatprogs \
        sleuthkit \
        testdisk \
    && rm -rf /var/lib/apt/lists/*

COPY --from=python-builder /opt/breaknwipe /opt/breaknwipe
COPY --from=gui-builder /gui/out /opt/breaknwipe/src/breaknwipe/breaknwipe-gui/out

# Convenience wrappers, matching the .deb layout (`docker exec ... breaknwipe`).
RUN printf '#!/bin/bash\nexec /opt/breaknwipe/src/.venv/bin/python -m breaknwipe.cli.main "$@"\n' \
        > /usr/bin/breaknwipe \
    && chmod +x /usr/bin/breaknwipe \
    && ln -sf breaknwipe /usr/bin/bwipe

# Certificates/reports land here (already on the server's download allowlist);
# mount a volume at this path to persist them across container runs.
VOLUME ["/root/breaknwipe_reports"]

EXPOSE 8000

# ENTRYPOINT/CMD split: default run serves the GUI, but any CLI invocation
# works too, e.g. `docker run --rm breaknwipe --list-devices` or `... wipe ...`.
ENTRYPOINT ["/opt/breaknwipe/src/.venv/bin/python", "-m", "breaknwipe.cli.main"]
CMD ["--gui", "--host", "0.0.0.0", "--port", "8000"]
