# Keploy API testing for Canopy

[Keploy](https://keploy.io) records real API traffic at the network layer and turns it
into replayable test cases plus data mocks, with no test code written by hand. For
Canopy it covers the endpoints rangers depend on: auth, sensors, regions, the alert
lifecycle, CSV export, satellite changes, and fusion runs.

## What is wired up

| Piece | File | Role |
| --- | --- | --- |
| CI job | `.github/workflows/keploy.yml` | records or replays on every PR |
| Traffic generator | `scripts/keploy_traffic.py` | 19 calls that become the test cases |
| App launcher | `scripts/keploy_app.sh` | starts the API identically for record and replay |
| Noise config | `scripts/keploy_config.py` | declares the fields that legitimately change |
| Test cases | `keploy/` | committed YAML, replayed as the regression suite |

## Platform requirement (read first)

Keploy captures traffic with **eBPF, which is Linux-only**.

| Platform | How it runs |
| --- | --- |
| Linux | natively, no container needed |
| macOS / Windows | through Docker (Docker Desktop 4.25.2+), [docs](https://keploy.io/docs/server/macos/installation/) |
| GitHub Actions | natively, runners are Linux |

On an Apple Silicon Mac without Docker, Keploy cannot run at all. That is why the CI
job is the primary integration: it is the one environment the whole team has where
Keploy runs natively.

## How CI works

The job at `.github/workflows/keploy.yml` branches on whether test cases exist:

- **`keploy/test-set-*` committed**: runs `keploy test` only. Every recorded call is
  replayed against the app and the responses are diffed. This is the regression suite.
- **Nothing committed yet**: records a set first from the traffic generator, uploads it
  as the `keploy-recorded-tests` artifact, then replays it in the same run.

So the job is green on the first push and gets stronger once cases are committed.

### Committing the recorded cases

Recording happens in CI because it cannot happen on macOS. To promote a recording into
the permanent suite:

1. Open the Keploy workflow run in Actions.
2. Download the `keploy-recorded-tests` artifact.
3. Unzip it to `keploy/` at the repo root and commit it.

From the next run onward CI replays those exact cases instead of re-recording, which is
what turns this from a smoke test into a regression test.

## Running it locally (Linux or Docker only)

```bash
# 1. install
curl --silent -O -L https://keploy.io/install.sh && source install.sh

# 2. configure the noise fields
keploy config --generate && python scripts/keploy_config.py

# 3. record: terminal 1
rm -f api/keploy.db
sudo -E env PATH="$PATH" keploy record -c "./scripts/keploy_app.sh" --delay 20

#    record: terminal 2
python scripts/keploy_traffic.py --base-url http://localhost:8000

# 4. replay
rm -f api/keploy.db
sudo -E env PATH="$PATH" keploy test -c "./scripts/keploy_app.sh" --delay 20
```

## The two things that make replay actually pass

Both are easy to get wrong and both produce confusing red builds.

**Noise fields.** Keploy diffs responses field by field, so anything that legitimately
changes between runs has to be declared or every run fails on it. Canopy's are the JWT
(`access_token`, new `iat`/`exp` on every signup), the server-set timestamps
(`created_at`, `updated_at`, `last_heard_at`), and the HTTP `Date` header.
`scripts/keploy_config.py` patches these into the config. It edits the config that
`keploy config --generate` produced rather than committing a hand-written one, because
the config schema moves between Keploy versions and starting from the installed
version's own defaults is version proof.

**A fresh database.** The traffic generator suffixes emails and names with a UUID, so a
recording contains one specific email. Replaying it against a database that already has
that user returns 400 instead of the recorded 201. Both phases therefore delete
`api/keploy.db` first. The launcher also disables rate limiting, whose sliding window is
wall clock state: replay fires the same calls faster than a human did, and a 429 where a
200 was recorded would fail for no real reason.

## Why this and not just pytest

The existing pytest suite asserts what we thought to assert. Keploy replays what the API
actually did, including response shapes and downstream calls we never wrote assertions
for, and it regenerates mocks automatically when the schema moves. It is cheapest
insurance against silently breaking the alert contract that field teams depend on. It
runs alongside the pytest job in `ci.yml` rather than replacing it.
