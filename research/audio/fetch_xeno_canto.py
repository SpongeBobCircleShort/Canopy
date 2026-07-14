"""Fetch India-native forest soundscapes from Xeno-canto as neutral background.

Xeno-canto (https://xeno-canto.org) has an open, no-auth API. We pull the
``soundscape`` recording type from India (``cnt:india type:soundscape``), which is
whole-scene ambient audio rather than a single foregrounded bird, so it is a
reasonable secondary "normal forest" source behind real AudioMoth field audio.

Two important guards, per the pipeline design:

* Licensing. Recordings carry per-clip Creative Commons licenses. With
  ``--commercial-safe`` we keep only CC0, public-domain, CC-BY and CC-BY-SA and
  skip NonCommercial (NC) and NoDerivatives (ND), since Canopy is heading
  commercial and training is a derivative use.
* These clips are NOT yet known-clean. A soundscape near a road or village can
  contain the very chainsaw/vehicle/voice you want to flag. So this fetcher only
  labels them ``background_unknown`` provisionally; run ``screen_soundscapes``
  afterward to move contaminated clips out of the neutral set.

The pure helpers (query building, license classification, response -> manifest
rows) have no network dependency and are unit-tested; only ``fetch_page`` and
``download_clip`` touch the network.

Example:

    python -m research.audio.fetch_xeno_canto \
        --out-dir data/audio/xeno_india_soundscapes \
        --commercial-safe --max 500
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from research.audio.manifest import ManifestRow, write_manifest

# Xeno-canto moved to the v3 API, which requires an API key (free for any
# registered member with a verified email: xeno-canto.org -> account -> API key).
# Set it via XENO_CANTO_KEY or --key.
_API_BASE = "https://xeno-canto.org/api/3/recordings"
_HTTP_TIMEOUT = 30
_USER_AGENT = "canopy-research/1.0 (conservation acoustic monitoring)"
BACKGROUND_LABEL = "background_unknown"
SOURCE = "xeno_canto"

# License URL fragments that permit commercial + derivative (training) use.
_COMMERCIAL_SAFE_FRAGMENTS = ("publicdomain", "/zero/", "/by/", "/by-sa/")
# Fragments that forbid it: NonCommercial or NoDerivatives.
_RESTRICTED_FRAGMENTS = ("-nc", "/nc", "-nd", "/nd")


# ---------------------------------------------------------------------------
# Pure helpers (no network)
# ---------------------------------------------------------------------------

def build_query(country: str = "india", rec_type: str = "soundscape") -> str:
    """Xeno-canto query string, e.g. ``cnt:india type:soundscape``."""
    parts = []
    if country:
        parts.append(f"cnt:{country.lower()}")
    if rec_type:
        parts.append(f"type:{rec_type.lower()}")
    return " ".join(parts)


def api_url(query: str, page: int = 1, *, key: str | None = None, per_page: int = 100) -> str:
    params: dict[str, Any] = {"query": query, "page": page, "per_page": per_page}
    if key:
        params["key"] = key
    return f"{_API_BASE}?{urllib.parse.urlencode(params)}"


def is_commercial_safe(license_url: str | None) -> bool:
    """True if a Creative Commons license permits commercial derivative use."""
    if not license_url:
        return False
    lic = license_url.lower()
    if any(fragment in lic for fragment in _RESTRICTED_FRAGMENTS):
        return False
    return any(fragment in lic for fragment in _COMMERCIAL_SAFE_FRAGMENTS)


def parse_length_seconds(length: str | None) -> float | None:
    """Xeno-canto ``length`` is ``m:ss`` (or ``h:mm:ss``). Return seconds."""
    if not length:
        return None
    try:
        parts = [int(p) for p in str(length).split(":")]
    except ValueError:
        return None
    seconds = 0
    for part in parts:
        seconds = seconds * 60 + part
    return float(seconds) if seconds > 0 else None


def _clip_filename(recording: dict[str, Any]) -> str:
    xc_id = str(recording.get("id", "")).strip()
    file_name = str(recording.get("file-name", "")).strip()
    suffix = Path(file_name).suffix.lower() if file_name else ".mp3"
    if suffix not in {".mp3", ".wav", ".flac", ".ogg"}:
        suffix = ".mp3"
    return f"xc{xc_id}{suffix}"


def clip_url(recording: dict[str, Any]) -> str | None:
    """Resolve a recording's downloadable audio URL."""
    url = str(recording.get("file", "")).strip()
    if not url:
        return None
    if url.startswith("//"):
        return f"https:{url}"
    return url


def recordings_to_rows(
    recordings: list[dict[str, Any]],
    *,
    commercial_safe: bool = True,
) -> list[ManifestRow]:
    """Convert API records into provisional ``background_unknown`` manifest rows.

    Skips records without a usable audio URL, and (when ``commercial_safe``)
    records whose license forbids commercial derivative use.
    """
    rows: list[ManifestRow] = []
    for rec in recordings:
        if clip_url(rec) is None:
            continue
        lic = rec.get("lic")
        if commercial_safe and not is_commercial_safe(lic):
            continue
        xc_id = str(rec.get("id", "")).strip()
        loc = str(rec.get("loc", "")).strip()
        rows.append(
            ManifestRow(
                path=_clip_filename(rec),
                label=BACKGROUND_LABEL,
                source=SOURCE,
                split="train",
                duration_seconds=parse_length_seconds(rec.get("length")),
                license=str(lic or ""),
                notes=f"xc:{xc_id} loc:{loc} type:soundscape unscreened",
            )
        )
    return rows


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------

def fetch_page(query: str, page: int = 1, *, key: str | None = None) -> dict[str, Any]:
    if not key:
        raise ValueError(
            "Xeno-canto API v3 requires an API key. Register at xeno-canto.org (free), "
            "get your key from your account page, and set XENO_CANTO_KEY or pass --key."
        )
    request = urllib.request.Request(api_url(query, page, key=key), headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT) as response:
        return json.loads(response.read())


def download_clip(url: str, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return True
    try:
        request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT) as response:
            data = response.read()
        dest.write_bytes(data)
        return True
    except Exception as exc:  # noqa: BLE001 - keep the batch going on a single failure
        print(f"  download failed for {url}: {exc}")
        return False


def run(
    out_dir: Path,
    *,
    key: str,
    country: str = "india",
    rec_type: str = "soundscape",
    commercial_safe: bool = True,
    max_clips: int | None = None,
    sleep_seconds: float = 0.5,
) -> Path:
    query = build_query(country, rec_type)
    out_dir.mkdir(parents=True, exist_ok=True)

    first = fetch_page(query, 1, key=key)
    num_pages = int(first.get("numPages", 1))
    print(f"Query '{query}': {first.get('numRecordings', '?')} recordings across {num_pages} pages")

    all_recordings: list[dict[str, Any]] = list(first.get("recordings", []))
    for page in range(2, num_pages + 1):
        if max_clips is not None and len(all_recordings) >= max_clips * 3:
            break  # plenty gathered before license/URL filtering
        time.sleep(sleep_seconds)
        all_recordings.extend(fetch_page(query, page, key=key).get("recordings", []))

    rows = recordings_to_rows(all_recordings, commercial_safe=commercial_safe)
    if max_clips is not None:
        rows = rows[:max_clips]

    kept_rows: list[ManifestRow] = []
    url_by_name = {_clip_filename(r): clip_url(r) for r in all_recordings}
    for row in rows:
        url = url_by_name.get(row.path)
        if url and download_clip(url, out_dir / row.path):
            kept_rows.append(row)

    manifest_path = out_dir / "manifest.csv"
    if kept_rows:
        write_manifest(manifest_path, kept_rows)
    print(
        f"Downloaded {len(kept_rows)} clips -> {out_dir}\n"
        f"  manifest: {manifest_path}\n"
        f"  NOTE: these are UNSCREENED. Run screen_soundscapes next to remove contaminated clips."
    )
    return manifest_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch India soundscapes from Xeno-canto as neutral background.")
    parser.add_argument("--out-dir", type=Path, required=True, help="Directory for clips + manifest.csv")
    parser.add_argument("--country", default="india", help="Xeno-canto country filter (default: india)")
    parser.add_argument("--type", dest="rec_type", default="soundscape", help="Recording type (default: soundscape)")
    parser.add_argument("--max", dest="max_clips", type=int, default=None, help="Maximum clips to download")
    parser.add_argument(
        "--commercial-safe",
        action="store_true",
        help="Keep only CC0/PD/BY/BY-SA (drop NonCommercial and NoDerivatives)",
    )
    parser.add_argument(
        "--key",
        default=os.environ.get("XENO_CANTO_KEY"),
        help="Xeno-canto API v3 key (or set XENO_CANTO_KEY)",
    )
    args = parser.parse_args()
    if not args.key:
        parser.error("A Xeno-canto API key is required. Set XENO_CANTO_KEY or pass --key. Register free at xeno-canto.org.")
    run(
        args.out_dir,
        key=args.key,
        country=args.country,
        rec_type=args.rec_type,
        commercial_safe=args.commercial_safe,
        max_clips=args.max_clips,
    )


if __name__ == "__main__":
    main()
