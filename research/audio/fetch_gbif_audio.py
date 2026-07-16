"""Fetch Indian audio occurrences from GBIF (including the India Biodiversity Portal).

The India Biodiversity Portal (IBP) has no clean public audio API, but it publishes
to GBIF, which does: a documented, no-auth occurrence API that returns Sound media
with per-record license metadata. GBIF also aggregates other Indian audio sources,
so this fetcher reaches IBP plus more in one place.

By default we restrict to the IBP dataset; pass ``--all-datasets`` to pull every
Indian Sound occurrence GBIF has. Since Canopy is open-source / internal for now,
NonCommercial licenses are kept by default (``--commercial-safe`` opts back into
CC0/BY/BY-SA only).

Downloaded clips are labelled ``background_unknown`` provisionally; run
``screen_soundscapes`` afterward, exactly as with the Xeno-canto path.

Pure helpers (URL building, license classification, occurrence -> rows) have no
network dependency and are unit-tested; only ``fetch_page`` and ``download_clip``
touch the network.

Example:

    python -m research.audio.fetch_gbif_audio --out-dir data/audio/gbif_india --max 200
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from dataclasses import replace
from pathlib import Path
from typing import Any

from research.audio.manifest import ManifestRow, write_manifest

# Formats the training loader (soundfile) cannot decode; we transcode these to
# WAV on download so no clip is wasted. librosa uses the OS decoder (CoreAudio on
# macOS), so no ffmpeg install is required.
_TRANSCODE_SUFFIXES = {".m4a", ".aac", ".mp4"}

_API_BASE = "https://api.gbif.org/v1/occurrence/search"
_HTTP_TIMEOUT = 30
_USER_AGENT = "canopy-research/1.0 (conservation acoustic monitoring)"
BACKGROUND_LABEL = "background_unknown"
# The "India Biodiversity Portal publication grade dataset" on GBIF.
IBP_DATASET_KEY = "c6b86c40-ff71-4e5e-902c-111f400d0d56"

_AUDIO_FORMATS = {
    "audio/mpeg": ".mp3", "audio/mp3": ".mp3", "audio/x-wav": ".wav",
    "audio/wav": ".wav", "audio/wave": ".wav", "audio/x-flac": ".flac",
    "audio/flac": ".flac", "audio/ogg": ".ogg", "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a", "audio/aac": ".aac",
}
_AUDIO_SUFFIXES = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"}
_COMMERCIAL_SAFE_FRAGMENTS = ("publicdomain", "/zero/", "cc0", "/by/", "/by-sa/", "cc_by_4", "cc_by_sa")
_RESTRICTED_FRAGMENTS = ("-nc", "/nc", "_nc_", "_nc", "-nd", "/nd", "_nd")


# ---------------------------------------------------------------------------
# Pure helpers (no network)
# ---------------------------------------------------------------------------

def api_url(
    country: str = "IN",
    media_type: str = "Sound",
    *,
    limit: int = 100,
    offset: int = 0,
    dataset_key: str | None = IBP_DATASET_KEY,
) -> str:
    params: dict[str, Any] = {"country": country, "mediaType": media_type, "limit": limit, "offset": offset}
    if dataset_key:
        params["datasetKey"] = dataset_key
    return f"{_API_BASE}?{urllib.parse.urlencode(params)}"


def is_commercial_safe(license_str: str | None) -> bool:
    """True if a GBIF license (URL or code like CC_BY_NC_4_0) permits commercial use."""
    if not license_str:
        return False
    lic = license_str.lower()
    if any(fragment in lic for fragment in _RESTRICTED_FRAGMENTS):
        return False
    return any(fragment in lic for fragment in _COMMERCIAL_SAFE_FRAGMENTS)


def _audio_suffix(media: dict[str, Any]) -> str:
    fmt = str(media.get("format", "")).lower()
    if fmt in _AUDIO_FORMATS:
        return _AUDIO_FORMATS[fmt]
    identifier = str(media.get("identifier", ""))
    suffix = Path(urllib.parse.urlparse(identifier).path).suffix.lower()
    return suffix if suffix in _AUDIO_SUFFIXES else ".mp3"


def _sound_media(occurrence: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        m for m in (occurrence.get("media") or [])
        if str(m.get("type", "")).lower() == "sound" and m.get("identifier")
    ]


def occurrences_to_rows(
    occurrences: list[dict[str, Any]],
    *,
    commercial_safe: bool = False,
    source: str = "gbif",
) -> list[tuple[ManifestRow, str]]:
    """Convert GBIF occurrences into (ManifestRow, download_url) pairs.

    One row per Sound media with a usable URL. The media-level license wins over
    the occurrence-level one; records are skipped when ``commercial_safe`` and the
    license does not permit commercial use.
    """
    pairs: list[tuple[ManifestRow, str]] = []
    for occ in occurrences:
        gbif_id = str(occ.get("gbifID", "")).strip()
        species = str(occ.get("species") or occ.get("scientificName") or "").strip()
        locality = str(occ.get("verbatimLocality") or occ.get("locality") or "").strip()
        for idx, media in enumerate(_sound_media(occ)):
            lic = media.get("license") or occ.get("license")
            if commercial_safe and not is_commercial_safe(lic):
                continue
            filename = f"gbif{gbif_id}_{idx}{_audio_suffix(media)}"
            note = f"gbif:{gbif_id} sp:{species} loc:{locality} unscreened".strip()
            pairs.append((
                ManifestRow(
                    path=filename,
                    label=BACKGROUND_LABEL,
                    source=source,
                    split="train",
                    duration_seconds=None,
                    license=str(lic or ""),
                    notes=note,
                ),
                str(media["identifier"]),
            ))
    return pairs


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------

def fetch_page(
    country: str = "IN",
    media_type: str = "Sound",
    *,
    offset: int = 0,
    limit: int = 100,
    dataset_key: str | None = IBP_DATASET_KEY,
) -> dict[str, Any]:
    url = api_url(country, media_type, limit=limit, offset=offset, dataset_key=dataset_key)
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT) as response:
        return json.loads(response.read())


def transcode_to_wav_if_needed(path: Path) -> Path:
    """Transcode m4a/aac to WAV (via librosa/OS decoder) so the loader can read it.

    Returns the WAV path on success, or the original path if transcoding is not
    needed or fails (those clips are then skipped downstream rather than crashing).
    """
    if path.suffix.lower() not in _TRANSCODE_SUFFIXES:
        return path
    try:
        import librosa
        import soundfile as sf

        waveform, sample_rate = librosa.load(str(path), sr=None, mono=True)
        wav_path = path.with_suffix(".wav")
        sf.write(str(wav_path), waveform, sample_rate)
        path.unlink(missing_ok=True)
        return wav_path
    except Exception as exc:  # noqa: BLE001
        print(f"  transcode failed for {path.name}: {exc}")
        return path


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
    country: str = "IN",
    dataset_key: str | None = IBP_DATASET_KEY,
    commercial_safe: bool = False,
    max_clips: int | None = None,
    source_label: str = "gbif_ibp",
    page_size: int = 100,
    sleep_seconds: float = 0.3,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    pairs: list[tuple[ManifestRow, str]] = []
    offset = 0
    total = None
    while True:
        page = fetch_page(country, "Sound", offset=offset, limit=page_size, dataset_key=dataset_key)
        if total is None:
            total = page.get("count")
            print(f"GBIF country={country} dataset={dataset_key or 'ALL'}: {total} Sound occurrences")
        pairs.extend(occurrences_to_rows(page.get("results", []), commercial_safe=commercial_safe, source=source_label))
        if max_clips is not None and len(pairs) >= max_clips:
            pairs = pairs[:max_clips]
            break
        if page.get("endOfRecords"):
            break
        offset += page_size
        time.sleep(sleep_seconds)

    kept: list[ManifestRow] = []
    for row, url in pairs:
        dest = out_dir / row.path
        if download_clip(url, dest):
            final = transcode_to_wav_if_needed(dest)
            kept.append(row if final.name == row.path else replace(row, path=final.name))

    manifest_path = out_dir / "manifest.csv"
    if kept:
        write_manifest(manifest_path, kept)
    print(
        f"Downloaded {len(kept)} clips -> {out_dir}\n"
        f"  manifest: {manifest_path}\n"
        f"  NOTE: these are UNSCREENED. Run screen_soundscapes next."
    )
    return manifest_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Indian audio from GBIF (India Biodiversity Portal + more).")
    parser.add_argument("--out-dir", type=Path, required=True, help="Directory for clips + manifest.csv")
    parser.add_argument("--country", default="IN", help="ISO country code (default: IN)")
    parser.add_argument("--all-datasets", action="store_true", help="Pull all Indian Sound occurrences, not just IBP")
    parser.add_argument("--max", dest="max_clips", type=int, default=None, help="Maximum clips to download")
    parser.add_argument("--commercial-safe", action="store_true", help="Keep only CC0/BY/BY-SA licenses")
    args = parser.parse_args()
    run(
        args.out_dir,
        country=args.country,
        dataset_key=None if args.all_datasets else IBP_DATASET_KEY,
        commercial_safe=args.commercial_safe,
        max_clips=args.max_clips,
        source_label="gbif_all" if args.all_datasets else "gbif_ibp",
    )


if __name__ == "__main__":
    main()
