#!/usr/bin/env bash
# Launch the Canopy API the way Keploy records and replays it.
#
# Record and replay must start the app identically or the diff is meaningless,
# so both phases go through this script. SQLite keeps the run self-contained
# (no Postgres), and rate limiting is off because its sliding window is wall
# clock state: replay fires the same calls faster than a human did, and a 429
# where a 200 was recorded would fail the test for no real reason.
set -euo pipefail

cd "$(dirname "$0")/../api"

export DATABASE_URL="${DATABASE_URL:-sqlite:///./keploy.db}"
export JWT_SECRET="${JWT_SECRET:-keploy-fixed-secret}"
export AUDIO_STORAGE_PATH="${AUDIO_STORAGE_PATH:-/tmp/canopy-audio-keploy}"
export RATE_LIMIT_ENABLED="${RATE_LIMIT_ENABLED:-false}"
export PYTHONPATH=.

exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port "${API_PORT:-8000}"
