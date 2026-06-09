#!/bin/sh
set -eu

cd "$(dirname "$0")/back"

export UV_CACHE_DIR="${UV_CACHE_DIR:-${TMPDIR:-/tmp}/bejas-uv-cache}"

uv sync --dev --frozen
.venv/bin/python -m pytest -q
