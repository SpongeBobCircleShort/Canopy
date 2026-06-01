from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

from research.audio.manifest import ManifestRow, write_manifest
from research.audio.prepare_manifest import AUDIO_SUFFIXES, assign_balanced_splits

DEFAULT_DATASET = "emrahaydemr/gunshot-audio-dataset"


def download_kaggle_dataset(dataset: str = DEFAULT_DATASET) -> Path:
    try:
        import kagglehub
    except ImportError as exc:
        raise RuntimeError("Install kagglehub first: python3 -m pip install kagglehub") from exc
    return Path(kagglehub.dataset_download(dataset))


def build_kaggle_gunshot_rows(root: Path, *, dataset: str = DEFAULT_DATASET) -> list[ManifestRow]:
    metadata = _metadata_by_stem(root)
    rows = []
    for audio_path in _audio_files(root):
        relative = audio_path.relative_to(root)
        record = metadata.get(audio_path.stem, {})
        split = _split_from_path(relative, record)
        source_recording_id = _source_recording_id(audio_path, record)
        rows.append(
            ManifestRow(
                path=str(audio_path.resolve()),
                label="gunshot",
                source="kaggle_gunshot",
                split=split or "train",
                duration_seconds=_optional_float(_record_value(record, "duration", "duration_seconds", "length")),
                license="see-kaggle-dataset-license",
                notes=(
                    f"kaggle_dataset={dataset}; source_recording_id={source_recording_id}; "
                    f"relative_path={relative.as_posix()}{'; manual_split=' + split if split else ''}"
                    f"{_metadata_notes(record)}"
                ),
            )
        )
    return rows


def write_kaggle_gunshot_manifest(root: Path, output: Path, *, dataset: str = DEFAULT_DATASET) -> list[ManifestRow]:
    rows = build_kaggle_gunshot_rows(root, dataset=dataset)
    if not rows:
        raise ValueError(f"No supported audio files found under {root}")
    rows = assign_balanced_splits(rows)
    write_manifest(output, rows)
    return rows


def write_kaggle_gunshot_curation(rows: list[ManifestRow], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "path",
                "label",
                "split",
                "source",
                "reviewer",
                "decision",
                "corrected_label",
                "notes",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "path": row.path,
                    "label": row.label,
                    "split": row.split,
                    "source": row.source,
                    "reviewer": "",
                    "decision": "needs_review",
                    "corrected_label": "",
                    "notes": row.notes,
                }
            )


def _metadata_by_stem(root: Path) -> dict[str, dict[str, str]]:
    metadata: dict[str, dict[str, str]] = {}
    for csv_path in sorted(root.rglob("*.csv")):
        with csv_path.open(newline="") as handle:
            for record in csv.DictReader(handle):
                filename = _record_value(record, "filename", "file", "path", "audio", "audio_file", "fname")
                if not filename:
                    continue
                metadata[Path(filename).stem] = record
    for json_path in sorted(root.rglob("*.json")):
        try:
            payload = json.loads(json_path.read_text())
        except json.JSONDecodeError:
            continue
        records = payload if isinstance(payload, list) else payload.get("records", []) if isinstance(payload, dict) else []
        for record in records:
            if not isinstance(record, dict):
                continue
            filename = _record_value(record, "filename", "file", "path", "audio", "audio_file", "fname")
            if filename:
                metadata[Path(filename).stem] = {str(key): str(value) for key, value in record.items()}
    return metadata


def _audio_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in AUDIO_SUFFIXES)


def _split_from_path(relative: Path, record: dict[str, str]) -> str:
    for value in [*_record_values(record, "split", "subset", "set"), *relative.parts[:-1]]:
        normalized = _normalize(value)
        if normalized in {"train", "training"}:
            return "train"
        if normalized in {"val", "valid", "validation"}:
            return "val"
        if normalized in {"test", "testing", "eval", "evaluation"}:
            return "test"
    return ""


def _source_recording_id(audio_path: Path, record: dict[str, str]) -> str:
    value = _record_value(record, "youtube_id", "video_id", "source_recording_id", "recording_id", "source", "url")
    if value:
        return _safe_note_value(value)
    stem = audio_path.stem
    # Keep common clip suffixes together so train/val/test cannot share one source recording.
    stem = re.sub(r"([_-](clip|segment|part)?\d{1,5})+$", "", stem, flags=re.IGNORECASE)
    return _safe_note_value(stem or audio_path.stem)


def _metadata_notes(record: dict[str, str]) -> str:
    if not record:
        return ""
    useful = []
    for key, value in sorted(record.items()):
        normalized_key = _normalize(key)
        if normalized_key in {"filename", "file", "path", "audio", "audio_file", "fname"}:
            continue
        if value:
            useful.append(f"{normalized_key}={_safe_note_value(str(value))}")
    return f"; {'; '.join(useful[:12])}" if useful else ""


def _record_value(record: dict[str, str], *keys: str) -> str:
    values = _record_values(record, *keys)
    return values[0] if values else ""


def _record_values(record: dict[str, str], *keys: str) -> list[str]:
    normalized = {_normalize(str(key)): str(value).strip() for key, value in record.items()}
    values = []
    for key in keys:
        value = normalized.get(_normalize(key), "")
        if value:
            values.append(value)
    return values


def _optional_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def _safe_note_value(value: str) -> str:
    return str(value).replace(";", ",").replace("\n", " ").strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Download/import a Kaggle gunshot dataset into Canopy manifests.")
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--root", type=Path, help="Existing extracted dataset root. If omitted, kagglehub downloads the dataset.")
    parser.add_argument("--output", type=Path, default=Path("data/audio/manifests/kaggle_gunshot_manifest.csv"))
    parser.add_argument("--curation-output", type=Path, default=Path("data/audio/curation/kaggle_gunshot_curation.csv"))
    args = parser.parse_args()

    root = args.root or download_kaggle_dataset(args.dataset)
    rows = write_kaggle_gunshot_manifest(root, args.output, dataset=args.dataset)
    write_kaggle_gunshot_curation(rows, args.curation_output)
    print(json.dumps({"root": str(root), "manifest": str(args.output), "curation": str(args.curation_output), "rows": len(rows)}, indent=2))


if __name__ == "__main__":
    main()
