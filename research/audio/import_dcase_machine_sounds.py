from __future__ import annotations

import argparse
import csv
import json
import random
import re
import subprocess
import zipfile
from collections import defaultdict
from pathlib import Path

from research.audio.manifest import ManifestRow, write_manifest

DEFAULT_LICENSE = "CC BY-NC-SA 4.0; DCASE 2020 Task 2 development dataset"
DEFAULT_ROOT = Path("data/audio/raw/DCASE2020Task2")
DEFAULT_OUTPUT = Path("data/audio/manifests/dcase2020_machine_negatives_manifest.csv")

DCASE2020_MACHINE_URLS = {
    "fan": "https://zenodo.org/records/3678171/files/dev_data_fan.zip?download=1",
    "pump": "https://zenodo.org/records/3678171/files/dev_data_pump.zip?download=1",
    "slider": "https://zenodo.org/records/3678171/files/dev_data_slider.zip?download=1",
    "ToyCar": "https://zenodo.org/records/3678171/files/dev_data_ToyCar.zip?download=1",
    "ToyConveyor": "https://zenodo.org/records/3678171/files/dev_data_ToyConveyor.zip?download=1",
    "valve": "https://zenodo.org/records/3678171/files/dev_data_valve.zip?download=1",
}

DEFAULT_MACHINES = ("fan", "pump", "slider", "valve")
FILENAME_PATTERN = re.compile(
    r"^(?P<condition>normal|anomaly)_id_(?P<machine_id>[0-9]+)_(?P<clip_id>[0-9]+)\.wav$"
)


def download_dcase2020_machines(
    root: Path,
    *,
    machines: list[str] | tuple[str, ...] = DEFAULT_MACHINES,
    keep_archives: bool = False,
) -> list[Path]:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    archive_dir = root / "_downloads"
    archive_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []

    for machine in machines:
        url = DCASE2020_MACHINE_URLS[machine]
        archive = archive_dir / f"dev_data_{machine}.zip"
        subprocess.run(["curl", "-L", url, "-o", str(archive)], check=True)
        with zipfile.ZipFile(archive) as handle:
            handle.extractall(root)
        extracted.append(archive)
        if not keep_archives:
            archive.unlink()

    if not keep_archives:
        try:
            archive_dir.rmdir()
        except OSError:
            pass
    return extracted


def build_dcase_machine_rows(
    root: Path,
    *,
    machines: list[str] | tuple[str, ...] | None = None,
    include_test_normal: bool = False,
    include_anomaly: bool = False,
    max_per_machine: int | None = None,
    seed: int = 50,
) -> list[ManifestRow]:
    root = Path(root)
    dev_root = _dev_data_root(root)
    selected_machines = tuple(machines or DEFAULT_MACHINES)
    grouped: dict[str, list[ManifestRow]] = defaultdict(list)

    for machine in selected_machines:
        machine_root = dev_root / machine
        if not machine_root.is_dir():
            continue
        for subset in _subsets(include_test_normal=include_test_normal):
            subset_root = machine_root / subset
            if not subset_root.is_dir():
                continue
            for audio_path in sorted(subset_root.glob("*.wav")):
                parsed = _parse_filename(audio_path.name)
                if parsed is None:
                    continue
                if parsed["condition"] == "anomaly" and not include_anomaly:
                    continue
                if subset == "test" and parsed["condition"] != "normal" and not include_anomaly:
                    continue
                relative = audio_path.relative_to(root)
                source_recording_id = (
                    f"dcase2020_{_slug(machine)}_{parsed['condition']}_"
                    f"id_{parsed['machine_id']}_{parsed['clip_id']}"
                )
                grouped[machine].append(
                    ManifestRow(
                        path=str(audio_path.resolve()),
                        label="background_unknown",
                        source="dcase_machine",
                        split="train",
                        duration_seconds=10.0,
                        license=DEFAULT_LICENSE,
                        notes=(
                            f"dcase_dataset=2020_task2_dev; machine_type={machine}; "
                            f"machine_id={parsed['machine_id']}; condition={parsed['condition']}; "
                            f"dcase_subset={subset}; clip_id={parsed['clip_id']}; "
                            f"source_recording_id={source_recording_id}; "
                            f"relative_path={relative.as_posix()}; hard_negative=true"
                        ),
                    )
                )

    rows = _cap_per_machine(grouped, max_per_machine=max_per_machine, seed=seed)
    if not rows:
        raise ValueError(
            f"No DCASE machine audio rows found under {root}. "
            f"Expected paths like dev_data/<machine>/train/normal_id_*.wav"
        )
    return rows


def write_dcase_machine_manifest(
    root: Path,
    output: Path,
    *,
    machines: list[str] | tuple[str, ...] | None = None,
    include_test_normal: bool = False,
    include_anomaly: bool = False,
    max_per_machine: int | None = None,
    seed: int = 50,
) -> list[ManifestRow]:
    rows = build_dcase_machine_rows(
        root,
        machines=machines,
        include_test_normal=include_test_normal,
        include_anomaly=include_anomaly,
        max_per_machine=max_per_machine,
        seed=seed,
    )
    write_manifest(output, rows)
    return rows


def write_dcase_machine_curation(rows: list[ManifestRow], output: Path) -> None:
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


def dcase_machine_summary(rows: list[ManifestRow]) -> dict[str, int]:
    summary: dict[str, int] = defaultdict(int)
    for row in rows:
        machine = _note_value(row.notes, "machine_type") or "unknown"
        summary[machine] += 1
    return dict(sorted(summary.items()))


def _dev_data_root(root: Path) -> Path:
    return root / "dev_data" if (root / "dev_data").is_dir() else root


def _subsets(*, include_test_normal: bool) -> tuple[str, ...]:
    return ("train", "test") if include_test_normal else ("train",)


def _parse_filename(filename: str) -> dict[str, str] | None:
    match = FILENAME_PATTERN.match(filename)
    return match.groupdict() if match else None


def _cap_per_machine(
    grouped: dict[str, list[ManifestRow]],
    *,
    max_per_machine: int | None,
    seed: int,
) -> list[ManifestRow]:
    rng = random.Random(seed)
    rows: list[ManifestRow] = []
    for machine in sorted(grouped):
        machine_rows = grouped[machine]
        rng.shuffle(machine_rows)
        rows.extend(machine_rows[:max_per_machine] if max_per_machine is not None else machine_rows)
    return rows


def _note_value(notes: str, key: str) -> str | None:
    marker = f"{key}="
    if marker not in notes:
        return None
    return notes.split(marker, 1)[1].split(";", 1)[0]


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import DCASE 2020 Task 2 machine sounds as Canopy background hard negatives."
    )
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--machine",
        action="append",
        choices=sorted(DCASE2020_MACHINE_URLS),
        dest="machines",
        help="Machine type to include. Defaults to fan, pump, slider, and valve.",
    )
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--keep-archives", action="store_true")
    parser.add_argument("--include-test-normal", action="store_true")
    parser.add_argument("--include-anomaly", action="store_true")
    parser.add_argument("--max-per-machine", type=int, default=500)
    parser.add_argument("--seed", type=int, default=50)
    parser.add_argument(
        "--curation-output",
        type=Path,
        default=Path("data/audio/curation/dcase2020_machine_negatives.csv"),
    )
    args = parser.parse_args()

    machines = args.machines or list(DEFAULT_MACHINES)
    if args.download:
        download_dcase2020_machines(args.root, machines=machines, keep_archives=args.keep_archives)

    rows = write_dcase_machine_manifest(
        args.root,
        args.output,
        machines=machines,
        include_test_normal=args.include_test_normal,
        include_anomaly=args.include_anomaly,
        max_per_machine=args.max_per_machine,
        seed=args.seed,
    )
    write_dcase_machine_curation(rows, args.curation_output)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "rows": len(rows),
                "summary": dcase_machine_summary(rows),
                "curation_output": str(args.curation_output),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
