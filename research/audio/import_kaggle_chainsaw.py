from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

from research.audio.manifest import ManifestRow, write_manifest
from research.audio.prepare_manifest import AUDIO_SUFFIXES, assign_balanced_splits

DEFAULT_DATASET = "tuanhaanh/chainsaw-dataset-with-forest-ambiance"


def download_kaggle_dataset(dataset: str = DEFAULT_DATASET) -> Path:
    try:
        import kagglehub
    except ImportError as exc:
        raise RuntimeError("Install kagglehub first: python3 -m pip install 'kagglehub<1.0'") from exc
    return Path(kagglehub.dataset_download(dataset))


def build_kaggle_chainsaw_rows(root: Path, *, dataset: str = DEFAULT_DATASET) -> list[ManifestRow]:
    rows = []
    for audio_path in _audio_files(root):
        relative = audio_path.relative_to(root)
        split = _split_from_path(relative)
        source_recording_id = _source_recording_id(relative)
        rows.append(
            ManifestRow(
                path=str(audio_path.resolve()),
                label="chainsaw",
                source="kaggle_chainsaw_rainforest",
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


def write_kaggle_chainsaw_manifest(
    root: Path,
    output: Path,
    *,
    dataset: str = DEFAULT_DATASET,
) -> list[ManifestRow]:
    rows = build_kaggle_chainsaw_rows(root, dataset=dataset)
    if not rows:
        raise ValueError(f"No supported audio files found under {root}")
    rows = assign_balanced_splits(rows)
    write_manifest(output, rows)
    return rows


def write_kaggle_chainsaw_curation(rows: list[ManifestRow], output: Path) -> None:
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


def _source_recording_id(relative: Path) -> str:
    parts = [_normalize(part) for part in relative.with_suffix("").parts]
    return "__".join(part for part in parts if part) or "chainsaw"


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download/import a Kaggle chainsaw rainforest dataset into Canopy manifests.")
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--root", type=Path, help="Existing extracted dataset root. If omitted, kagglehub downloads the dataset.")
    parser.add_argument("--output", type=Path, default=Path("data/audio/manifests/kaggle_chainsaw_manifest.csv"))
    parser.add_argument("--curation-output", type=Path, default=Path("data/audio/curation/kaggle_chainsaw_curation.csv"))
    args = parser.parse_args()

    root = args.root or download_kaggle_dataset(args.dataset)
    rows = write_kaggle_chainsaw_manifest(root, args.output, dataset=args.dataset)
    write_kaggle_chainsaw_curation(rows, args.curation_output)
    print(json.dumps({"root": str(root), "manifest": str(args.output), "curation": str(args.curation_output), "rows": len(rows)}, indent=2))


if __name__ == "__main__":
    main()
