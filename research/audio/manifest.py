from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from research.audio.labels import LABELS, canonical_label

MANIFEST_COLUMNS = ["path", "label", "source", "split", "duration_seconds", "license", "notes"]
VALID_SPLITS = {"train", "val", "test"}


@dataclass(frozen=True)
class ManifestRow:
    path: str
    label: str
    source: str
    split: str
    duration_seconds: float | None = None
    license: str = ""
    notes: str = ""

    def to_csv_row(self) -> dict[str, str]:
        return {
            "path": self.path,
            "label": canonical_label(self.label),
            "source": self.source,
            "split": self.split,
            "duration_seconds": "" if self.duration_seconds is None else f"{self.duration_seconds:.6g}",
            "license": self.license,
            "notes": self.notes,
        }


def read_manifest(path: str | Path) -> list[dict[str, str]]:
    manifest_path = Path(path)
    with manifest_path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [dict(row) for row in reader]
    validate_manifest_rows(rows, base_dir=manifest_path.parent)
    return rows


def write_manifest(path: str | Path, rows: list[ManifestRow | dict[str, str]]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    csv_rows = [row.to_csv_row() if isinstance(row, ManifestRow) else _normalize_row(row) for row in rows]
    validate_manifest_rows(csv_rows, require_files=False)
    with output_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        writer.writerows(csv_rows)


def validate_manifest_rows(rows: list[dict[str, str]], *, base_dir: Path | None = None, require_files: bool = True) -> None:
    if not rows:
        raise ValueError("Manifest must contain at least one row")
    for index, row in enumerate(rows, start=2):
        missing = [column for column in MANIFEST_COLUMNS if column not in row]
        if missing:
            raise ValueError(f"Row {index}: missing manifest columns: {', '.join(missing)}")
        row["label"] = canonical_label(row["label"])
        if row["label"] not in LABELS:
            raise ValueError(f"Row {index}: unsupported label {row['label']}")
        if row["split"] not in VALID_SPLITS:
            raise ValueError(f"Row {index}: split must be one of {sorted(VALID_SPLITS)}")
        if row["duration_seconds"]:
            duration = float(row["duration_seconds"])
            if duration <= 0:
                raise ValueError(f"Row {index}: duration_seconds must be positive")
        if require_files:
            audio_path = Path(row["path"])
            if not audio_path.is_absolute() and base_dir is not None:
                audio_path = base_dir / audio_path
            if not audio_path.exists():
                raise ValueError(f"Row {index}: audio file does not exist: {row['path']}")


def _normalize_row(row: dict[str, str]) -> dict[str, str]:
    return {column: str(row.get(column, "")) for column in MANIFEST_COLUMNS}
