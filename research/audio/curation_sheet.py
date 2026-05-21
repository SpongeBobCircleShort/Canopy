from __future__ import annotations

import argparse
import csv
from pathlib import Path

from research.audio.labels import LABEL_ALIASES, canonical_label
from research.audio.prepare_manifest import AUDIO_SUFFIXES

CURATION_COLUMNS = [
    "path",
    "label",
    "split",
    "source_recording_id",
    "site_id",
    "license",
    "reviewer",
    "decision",
    "notes",
]
VALID_DECISIONS = {"accepted", "rejected", "unsure", "needs_review", ""}
VALID_SPLITS = {"train", "val", "test", ""}


def build_curation_rows(canopy_root: Path) -> list[dict[str, str]]:
    rows = []
    for audio_path in sorted(path for path in canopy_root.rglob("*") if path.is_file() and path.suffix.lower() in AUDIO_SUFFIXES):
        parsed = _parse_curated_path(canopy_root, audio_path)
        if parsed is None:
            continue
        label, split = parsed
        rows.append(
            {
                "path": str(audio_path),
                "label": label,
                "split": split,
                "source_recording_id": _source_recording_from_name(audio_path),
                "site_id": "",
                "license": "",
                "reviewer": "",
                "decision": "needs_review",
                "notes": "",
            }
        )
    return rows


def write_curation_sheet(output: Path, rows: list[dict[str, str]]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CURATION_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def validate_curation_sheet(path: Path) -> list[str]:
    failures = []
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        missing_columns = [column for column in CURATION_COLUMNS if column not in (reader.fieldnames or [])]
        if missing_columns:
            return [f"missing curation sheet columns: {', '.join(missing_columns)}"]
        for index, row in enumerate(reader, start=2):
            if row["label"] not in LABEL_ALIASES:
                failures.append(f"row {index}: unsupported label {row['label']}")
            if row["split"] not in VALID_SPLITS:
                failures.append(f"row {index}: split must be train, val, test, or blank")
            if row["decision"] not in VALID_DECISIONS:
                failures.append(f"row {index}: decision must be one of {sorted(VALID_DECISIONS)}")
            if row["decision"] == "accepted" and not row["source_recording_id"]:
                failures.append(f"row {index}: accepted clips require source_recording_id")
            if row["decision"] == "accepted" and not Path(row["path"]).exists():
                failures.append(f"row {index}: accepted clip path does not exist: {row['path']}")
    return failures


def _parse_curated_path(root: Path, audio_path: Path) -> tuple[str, str] | None:
    relative = audio_path.relative_to(root)
    parts = relative.parts
    if not parts:
        return None
    if parts[0] in LABEL_ALIASES:
        label = canonical_label(parts[0])
        split = parts[1] if len(parts) > 2 and parts[1] in VALID_SPLITS else ""
        return label, split
    if parts[0] in VALID_SPLITS and len(parts) > 2 and parts[1] in LABEL_ALIASES:
        return canonical_label(parts[1]), parts[0]
    return None


def _source_recording_from_name(path: Path) -> str:
    parts = path.stem.split("__")
    if len(parts) >= 4:
        return parts[1]
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or validate a local Canopy audio curation sheet.")
    parser.add_argument("--canopy-root", type=Path, default=Path("data/audio/raw/canopy-labeled"))
    parser.add_argument("--output", type=Path, default=Path("data/audio/curation/canopy_audio_curation.csv"))
    parser.add_argument("--validate", type=Path)
    args = parser.parse_args()

    if args.validate:
        failures = validate_curation_sheet(args.validate)
        if failures:
            for failure in failures:
                print(failure)
            raise SystemExit(1)
        print(f"Curation sheet is valid: {args.validate}")
        return

    rows = build_curation_rows(args.canopy_root)
    write_curation_sheet(args.output, rows)
    print(f"Wrote {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
