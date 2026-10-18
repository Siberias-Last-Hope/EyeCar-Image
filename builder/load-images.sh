#!/usr/bin/env bash
# Copyright (C) 2026 MaxX-Akela, MIT License
#
# Loads /opt/eyecar/images/*.tar.zst into Docker, then removes the archives.
set -euo pipefail
shopt -s nullglob
for archive in /opt/eyecar/images/*.tar.zst; do
    echo "loading ${archive}"
    zstd -dc "${archive}" | docker load
    rm -f "${archive}"
done
