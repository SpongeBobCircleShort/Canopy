from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

from research.audio.manifest import ManifestRow, write_manifest
from research.audio.prepare_manifest import AUDIO_SUFFIXES, assign_balanced_splits

DEFAULT_DATASET = "brinkor/vehicle-type-sound-dataset"


def download_kaggle_dataset(dataset: str = DEFAULT_DATASET) -> Path:
    try:
        import kagglehub
    except ImportError as exc:
        raise RuntimeError("Install kagglehub first: python3 -m pip install 'kagglehub<1.0'") from exc
    return Path(kagglehub.dataset_download(dataset))


def build_kaggle_vehicle_rows(root: Path, *, dataset: str = DEFAULT_DATASET, group_size: int = 100) -> list[ManifestRow]:
    rows = []
    for audio_path in _audio_files(root):
        relative = audio_path.relative_to(root)
        split = _split_from_path(relative)
        source_recording_id = _source_group(audio_path, group_size=group_size)
        rows.append(
            ManifestRow(
                path=str(audio_path.resolve()),
                label="vehicle",
                source="kaggle_vehicle_type",
                split=split or "train",
                duration_seconds=None,
                license="see-kaggle-dataset-license",
                notes=(
                    f"kaggle_dataset={dataset}; source_recording_id={source_recording_id}; "
                    f"relative_path={relative.as_posix()}{'; manual_split=' + split if split else ''}"
                ),
            )
        )
    return rows


def write_kaggle_vehicle_manifest(
    root: Path,
    output: Path,
    *,
    dataset: str = DEFAULT_DATASET,
    group_size: int = 100,
) -> list[ManifestRow]:
    rows = build_kaggle_vehicle_rows(root, dataset=dataset, group_size=group_size)
    if not rows:
        raise ValueError(f"No supported audio files found under {root}")
    rows = assign_balanced_splits(rows)
    write_manifest(output, rows)
    return rows


def write_kaggle_vehicle_curation(rows: list[ManifestRow], output: Path) -> None:
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


def _audio_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in AUDIO_SUFFIXES)


def _split_from_path(relative: Path) -> str:
    for part in relative.parts[:-1]:
        normalized = _normalize(part)
        if normalized in {"train", "training"}:
            return "train"
        if normalized in {"val", "valid", "validation"}:
            return "val"
        if normalized in {"test", "testing", "eval", "evaluation"}:
            return "test"
    return ""


def _source_group(audio_path: Path, *, group_size: int) -> str:
    match = re.search(r"(\d+)", audio_path.stem)
    if match:
        number = int(match.group(1))
        bucket = number // max(1, group_size)
        return f"{_normalize(audio_path.stem[: match.start(1)] or 'vehicle_noise')}_{bucket:04d}"
    return _normalize(audio_path.stem)


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download/import a Kaggle vehicle sound dataset into Canopy manifests.")
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--root", type=Path, help="Existing extracted dataset root. If omitted, kagglehub downloads the dataset.")
    parser.add_argument("--output", type=Path, default=Path("data/audio/manifests/kaggle_vehicle_manifest.csv"))
    parser.add_argument("--curation-output", type=Path, default=Path("data/audio/curation/kaggle_vehicle_curation.csv"))
    parser.add_argument(
        "--group-size",
        type=int,
        default=100,
        help="Group sequential VehicleNoise-style filenames to reduce adjacent-clip split leakage.",
    )
    args = parser.parse_args()

    root = args.root or download_kaggle_dataset(args.dataset)
    rows = write_kaggle_vehicle_manifest(root, args.output, dataset=args.dataset, group_size=args.group_size)
    write_kaggle_vehicle_curation(rows, args.curation_output)
    print(json.dumps({"root": str(root), "manifest": str(args.output), "curation": str(args.curation_output), "rows": len(rows)}, indent=2))


if __name__ == "__main__":
    main()
