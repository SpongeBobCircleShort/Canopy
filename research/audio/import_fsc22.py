from __future__ import annotations

import argparse
import csv
import json
import random
import re
import subprocess
from collections import defaultdict
from pathlib import Path

from research.audio.manifest import ManifestRow, write_manifest
from research.audio.prepare_manifest import AUDIO_SUFFIXES, assign_balanced_splits

DEFAULT_REPO = "https://github.com/IRMIOT/FSC22.git"
DEFAULT_LICENSE = "CC0-1.0; see FSC22 LICENSE for clip attributions"

# FSC22 class names from Metadata V1.0 FSC22.csv (27 classes × 75 clips).
FSC22_THREAT_CLASSES = frozenset(
    {
        "fire",
        "firework",
        "chainsaw",
        "gunshot",
        "handsaw",
        "axe",
        "woodchop",
    }
)

FSC22_VEHICLE_CLASSES = frozenset({"vehicleengine", "helicopter"})

FSC22_BACKGROUND_CLASSES = frozenset(
    {
        "birdchirping",
        "clapping",
        "footsteps",
        "frog",
        "generator",
        "insect",
        "lion",
        "rain",
        "silence",
        "speaking",
        "squirrel",
        "thunderstorm",
        "treefalling",
        "waterdrops",
        "whistling",
        "wind",
        "wingflaping",
        "wolfhowl",
    }
)

CANOPY_LABEL_FOR_FSC22_CLASS = {
    **{name: "background_unknown" for name in FSC22_BACKGROUND_CLASSES},
    **{name: "vehicle" for name in FSC22_VEHICLE_CLASSES},
    "fire": "fire_crackle",
    "firework": "gunshot",
    "chainsaw": "chainsaw",
    "gunshot": "gunshot",
    "handsaw": "chainsaw",
    "axe": "chainsaw",
    "woodchop": "chainsaw",
}


def download_fsc22(root: Path, *, repo: str = DEFAULT_REPO) -> Path:
    root = Path(root)
    if _dataset_ready(root):
        return root
    root.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "--depth", "1", repo, str(root)], check=True)
    if not _dataset_ready(root):
        raise ValueError(
            f"FSC22 checkout at {root} is missing Audios/ or metadata. "
            "Download the dataset zip from https://github.com/IRMIOT/FSC22 and extract it to this path."
        )
    return root


def build_fsc22_rows(
    root: Path,
    *,
    negatives_only: bool = True,
    train_only: bool = True,
    max_per_class: int | None = None,
    seed: int = 46,
) -> list[ManifestRow]:
    root = Path(root)
    metadata_rows = _read_metadata(root)
    audio_root = _audio_root(root)
    grouped: dict[str, list[ManifestRow]] = defaultdict(list)
    skipped_threat = 0
    unknown_class = 0

    for record in metadata_rows:
        class_name = _normalize_class_name(record["class_name"])
        canopy_label = CANOPY_LABEL_FOR_FSC22_CLASS.get(class_name)
        if canopy_label is None:
            unknown_class += 1
            continue
        if negatives_only and class_name in FSC22_THREAT_CLASSES:
            skipped_threat += 1
            continue

        dataset_file = record["dataset_file_name"].strip()
        audio_path = audio_root / dataset_file
        if not audio_path.is_file():
            continue

        source_recording_id = _source_recording_id(record["source_file_name"], class_name)
        relative = audio_path.relative_to(root)
        grouped[class_name].append(
            ManifestRow(
                path=str(audio_path.resolve()),
                label=canopy_label,
                source="fsc22",
                split="train" if train_only else "",
                duration_seconds=5.0,
                license=DEFAULT_LICENSE,
                notes=(
                    f"fsc22_class={record['class_name']}; fsc22_class_id={record['class_id']}; "
                    f"fsc22_dataset_file={dataset_file}; "
                    f"fsc22_source_file={record['source_file_name']}; "
                    f"source_recording_id={source_recording_id}; "
                    f"relative_path={relative.as_posix()}; "
                    f"negatives_only={negatives_only}"
                ),
            )
        )

    rows = _cap_per_class(grouped, max_per_class=max_per_class, seed=seed)
    if not rows:
        raise ValueError(
            f"No FSC22 audio rows found under {root}. "
            f"skipped_threat={skipped_threat}, unknown_class={unknown_class}"
        )
    if not train_only:
        rows = assign_balanced_splits(rows)
    else:
        rows = _lock_train_split(rows)
    return rows


def write_fsc22_manifest(
    root: Path,
    output: Path,
    *,
    negatives_only: bool = True,
    train_only: bool = True,
    max_per_class: int | None = None,
    seed: int = 46,
) -> list[ManifestRow]:
    rows = build_fsc22_rows(
        root,
        negatives_only=negatives_only,
        train_only=train_only,
        max_per_class=max_per_class,
        seed=seed,
    )
    write_manifest(output, rows)
    return rows


def write_fsc22_curation(rows: list[ManifestRow], output: Path) -> None:
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


def fsc22_class_summary(rows: list[ManifestRow]) -> dict[str, int]:
    summary: dict[str, int] = defaultdict(int)
    for row in rows:
        marker = "fsc22_class="
        if marker in row.notes:
            class_name = row.notes.split(marker, 1)[1].split(";", 1)[0]
            summary[class_name] += 1
    return dict(sorted(summary.items()))


def _read_metadata(root: Path) -> list[dict[str, str]]:
    metadata_path = _metadata_path(root)
    with metadata_path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
            class_name = (row.get("Class Name") or row.get("Class Name ") or "").strip()
            dataset_file = (row.get("Dataset File Name") or "").strip()
            if not class_name or not dataset_file:
                continue
            rows.append(
                {
                    "source_file_name": (row.get("Source File Name") or "").strip(),
                    "dataset_file_name": dataset_file,
                    "class_id": (row.get("Class ID") or "").strip(),
                    "class_name": class_name,
                }
            )
    if not rows:
        raise ValueError(f"No metadata rows found in {metadata_path}")
    return rows


def _metadata_path(root: Path) -> Path:
    metadata_dir = root / "Metadata"
    candidates = sorted(metadata_dir.glob("Metadata*.csv"))
    if not candidates:
        raise ValueError(f"Missing FSC22 metadata CSV under {metadata_dir}")
    return candidates[0]


def _audio_root(root: Path) -> Path:
    audios = root / "Audios"
    return audios if audios.is_dir() else root


def _dataset_ready(root: Path) -> bool:
    try:
        _read_metadata(root)
    except ValueError:
        return False
    audio_root = _audio_root(root)
    return any(audio_root.glob("*.wav"))


def _cap_per_class(
    grouped: dict[str, list[ManifestRow]],
    *,
    max_per_class: int | None,
    seed: int,
) -> list[ManifestRow]:
    if max_per_class is None:
        rows: list[ManifestRow] = []
        for class_rows in grouped.values():
            rows.extend(sorted(class_rows, key=lambda row: row.path))
        return rows

    rng = random.Random(seed)
    rows = []
    for class_name in sorted(grouped):
        class_rows = sorted(grouped[class_name], key=lambda row: row.path)
        rng.shuffle(class_rows)
        rows.extend(class_rows[:max_per_class])
    return rows


def _lock_train_split(rows: list[ManifestRow]) -> list[ManifestRow]:
    locked = []
    for row in rows:
        original_split = row.split or "train"
        notes = row.notes
        if "fsc22_train_only=true" not in notes:
            notes = f"{notes}; fsc22_train_only=true; original_split={original_split}"
        locked.append(
            ManifestRow(
                path=row.path,
                label=row.label,
                source=row.source,
                split="train",
                duration_seconds=row.duration_seconds,
                license=row.license,
                notes=notes,
            )
        )
    return locked


def _source_recording_id(source_file_name: str, class_name: str) -> str:
    stem = Path(source_file_name).stem
    base = re.sub(r"[_-]+[a-z]$", "", stem, flags=re.IGNORECASE)
    base = re.sub(r"[^a-z0-9]+", "_", base.lower()).strip("_") or stem.lower()
    return f"fsc22_{class_name}_{base}"


def _normalize_class_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.strip().lower())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import FSC22 forest audio into Canopy manifests (background negatives by default)."
    )
    parser.add_argument("--root", type=Path, default=Path("data/audio/raw/FSC22"), help="Extracted FSC22 dataset root.")
    parser.add_argument("--download", action="store_true", help="Clone https://github.com/IRMIOT/FSC22 into --root if missing.")
    parser.add_argument("--output", type=Path, default=Path("data/audio/manifests/fsc22_negatives_manifest.csv"))
    parser.add_argument("--curation-output", type=Path, default=Path("data/audio/curation/fsc22_negatives_curation.csv"))
    parser.add_argument(
        "--include-threat-classes",
        action="store_true",
        help="Also import FSC22 threat classes (fire, chainsaw, gunshot, etc.). Default is negatives-only.",
    )
    parser.add_argument(
        "--balanced-splits",
        action="store_true",
        help="Assign train/val/test splits instead of locking all rows to train.",
    )
    parser.add_argument("--max-per-class", type=int, help="Optional cap per FSC22 class (useful before merging into training manifest).")
    parser.add_argument("--seed", type=int, default=46)
    args = parser.parse_args()

    root = download_fsc22(args.root) if args.download else args.root
    rows = write_fsc22_manifest(
        root,
        args.output,
        negatives_only=not args.include_threat_classes,
        train_only=not args.balanced_splits,
        max_per_class=args.max_per_class,
        seed=args.seed,
    )
    write_fsc22_curation(rows, args.curation_output)
    by_label: dict[str, int] = defaultdict(int)
    for row in rows:
        by_label[row.label] += 1
    print(
        json.dumps(
            {
                "root": str(root.resolve()),
                "manifest": str(args.output),
                "curation": str(args.curation_output),
                "rows": len(rows),
                "negatives_only": not args.include_threat_classes,
                "train_only": not args.balanced_splits,
                "by_label": dict(by_label),
                "by_fsc22_class": fsc22_class_summary(rows),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
