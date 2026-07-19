"""Patch Canopy's noise fields into a Keploy config.

Keploy replays recorded calls and diffs the responses field by field, so
anything that legitimately changes between runs has to be declared as noise or
every run fails on it. For Canopy that is the JWT (new `iat`/`exp` each signup),
the server-set timestamps, and the HTTP `Date` header.

Run `keploy config --generate` first and then this script, rather than
committing a hand-written keploy.yml: the config schema moves between Keploy
versions, so starting from the installed version's own defaults and editing one
key is the version-proof way to do it.

    keploy config --generate
    python scripts/keploy_config.py

Idempotent; safe to re-run.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

CONFIG = Path(__file__).resolve().parents[1] / "keploy.yml"

# Empty list = ignore the field entirely. A list of regexes would ignore only
# matching values.
NOISE_BODY = {
    "access_token": [],    # JWT: new iat/exp on every signup
    "created_at": [],
    "updated_at": [],
    "last_heard_at": [],   # sensor heartbeat
}
NOISE_HEADER = {
    "date": [],
    "Date": [],
}


def main() -> int:
    if not CONFIG.exists():
        print(f"{CONFIG} not found. Run `keploy config --generate` first.", file=sys.stderr)
        return 1

    config = yaml.safe_load(CONFIG.read_text()) or {}

    test = config.setdefault("test", {})
    global_noise = test.setdefault("globalNoise", {})
    scope = global_noise.setdefault("global", {})
    scope.setdefault("body", {}).update(NOISE_BODY)
    scope.setdefault("header", {}).update(NOISE_HEADER)

    CONFIG.write_text(yaml.safe_dump(config, sort_keys=False))
    fields = ", ".join(list(NOISE_BODY) + ["Date (header)"])
    print(f"patched {CONFIG.name}, noise fields: {fields}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
