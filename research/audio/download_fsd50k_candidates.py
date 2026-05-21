from __future__ import annotations

import argparse
import csv
import random
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

from research.audio.labels import LABELS
from research.audio.manifest import read_manifest

TARGET_LABEL_TERMS = {
    "chainsaw": {"Chainsaw", "Sawing", "Power_tool"},
    "gunshot": {"Gunshot_and_gunfire"},
    "fire_crackle": {"Fire", "Crackle"},
}

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


def select_fsd50k_candidates(
    metadata_csv: Path,
    *,
    needed_by_label: dict[str, int],
    seed: int = 42,
    exclude_fnames: set[str] | None = None,
    metadata_split: str | None = None,
) -> dict[str, list[dict[str, str]]]:
    selected: dict[str, list[dict[str, str]]] = {label: [] for label in needed_by_label}
    candidates: dict[str, list[dict[str, str]]] = defaultdict(list)
    exclude_fnames = exclude_fnames or set()
    expected_metadata_split = metadata_split.strip().lower() if metadata_split else ""

    with metadata_csv.open(newline="") as handle:
        for record in csv.DictReader(handle):
            fname = str(record.get("fname", "")).strip()
            if fname in exclude_fnames:
                continue
            if expected_metadata_split and str(record.get("split", "")).strip().lower() != expected_metadata_split:
                continue
            labels = _labels(record)
            label = _candidate_label(labels)
            if label in needed_by_label:
                record = dict(record)
                record["canopy_label"] = label
                record["labels"] = ",".join(labels)
                candidates[label].append(record)

    rng = random.Random(seed)
    for label, label_candidates in candidates.items():
        rng.shuffle(label_candidates)
        selected[label] = label_candidates[: max(0, needed_by_label[label])]
    return selected


def current_support_by_label(manifest: Path | None, *, split: str) -> Counter:
    if manifest is None or not manifest.exists():
        return Counter()
    return Counter(row["label"] for row in read_manifest(manifest) if row["split"] == split)


def read_selection_input(path: Path) -> dict[str, list[dict[str, str]]]:
    selected: dict[str, list[dict[str, str]]] = defaultdict(list)
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            label = str(row.get("label", "")).strip()
            raw_path = str(row.get("path", "")).strip()
            fname = str(row.get("fname", "")).strip() or Path(raw_path).stem
            if not label or not fname:
                continue
            selected[label].append(
                {
                    "fname": fname,
                    "canopy_label": label,
                    "labels": _note_value(row.get("notes", ""), "fsd50k_labels") or label,
                }
            )
    return dict(selected)


def selected_override_fnames(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open(newline="") as handle:
        return {str(record.get("fname", "")).strip() for record in csv.DictReader(handle) if str(record.get("fname", "")).strip()}


def download_selected_candidates(
    selected: dict[str, list[dict[str, str]]],
    *,
    output_root: Path,
    hf_base_url: str,
    hf_split: str,
    retries: int = 3,
    sleep_seconds: float = 1.0,
) -> list[Path]:
    output_dir = output_root / f"FSD50K.{hf_split}_audio"
    output_dir.mkdir(parents=True, exist_ok=True)
    downloaded = []

    for label in sorted(selected):
        for record in selected[label]:
            fname = str(record["fname"])
            output_path = output_dir / f"{fname}.wav"
            if output_path.exists() and output_path.stat().st_size > 0:
                downloaded.append(output_path)
                continue
            url = f"{hf_base_url.rstrip('/')}/{hf_split}/{fname}.wav?download=true"
            _download_file(url, output_path, retries=retries, sleep_seconds=sleep_seconds)
            downloaded.append(output_path)
            print(f"downloaded label={label} fname={fname} path={output_path}", flush=True)
    return downloaded


def write_candidate_curation_sheet(
    output: Path,
    selected: dict[str, list[dict[str, str]]],
    *,
    audio_root: Path,
    audio_split: str,
    manifest_split: str,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CURATION_COLUMNS)
        writer.writeheader()
        for label in sorted(selected):
            for record in selected[label]:
                fname = str(record["fname"])
                writer.writerow(
                    {
                        "path": str(audio_root / f"FSD50K.{audio_split}_audio" / f"{fname}.wav"),
                        "label": label,
                        "split": manifest_split,
                        "source_recording_id": f"fsd50k-{fname}",
                        "site_id": "",
                        "license": "see FSD50K metadata",
                        "reviewer": "",
                        "decision": "needs_review",
                        "notes": f"fsd50k_labels={record['labels']}",
                    }
                )


def write_split_overrides(
    output: Path,
    selected: dict[str, list[dict[str, str]]],
    *,
    audio_split: str,
    manifest_split: str,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, dict[str, str]] = {}
    if output.exists():
        with output.open(newline="") as handle:
            for record in csv.DictReader(handle):
                fname = str(record.get("fname", "")).strip()
                if fname:
                    existing[fname] = record
    for label in sorted(selected):
        for record in selected[label]:
            fname = str(record["fname"])
            existing[fname] = {
                "fname": fname,
                "label": label,
                "split": manifest_split,
                "audio_split": audio_split,
                "notes": f"fsd50k_labels={record['labels']}",
            }
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["fname", "label", "split", "audio_split", "notes"])
        writer.writeheader()
        writer.writerows(existing[fname] for fname in sorted(existing, key=lambda value: (existing[value]["split"], existing[value]["label"], value)))


def _download_file(url: str, output_path: Path, *, retries: int, sleep_seconds: float) -> None:
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    request = urllib.request.Request(url, headers={"User-Agent": "canopy-audio-data-prep/1.0"})
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=120) as response, tmp_path.open("wb") as handle:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
            tmp_path.replace(output_path)
            return
        except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            last_error = exc
            if tmp_path.exists():
                tmp_path.unlink()
            if attempt < retries:
                time.sleep(sleep_seconds * attempt)
    raise RuntimeError(f"failed to download {url}: {last_error}")


def _candidate_label(labels: list[str]) -> str:
    matches = []
    label_set = set(labels)
    for label, terms in TARGET_LABEL_TERMS.items():
        if label_set & terms:
            matches.append(label)
    return matches[0] if len(matches) == 1 else ""


def _labels(record: dict[str, str]) -> list[str]:
    return [value.strip() for value in record.get("labels", "").split(",") if value.strip()]


def _note_value(notes: str, key: str) -> str:
    marker = f"{key}="
    if marker not in notes:
        return ""
    return notes.split(marker, 1)[1].split(";", 1)[0].strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Download targeted FSD50K scarce-class candidate audio.")
    parser.add_argument("--fsd50k-root", type=Path, default=Path("data/audio/raw/FSD50K"))
    parser.add_argument("--metadata-csv", type=Path)
    parser.add_argument("--existing-manifest", type=Path)
    parser.add_argument("--min-test-support", type=int, default=100)
    parser.add_argument("--labels", nargs="+", default=["chainsaw", "fire_crackle", "gunshot"])
    parser.add_argument("--per-label", type=int, help="Download this many per label instead of using --existing-manifest support gaps.")
    parser.add_argument("--hf-base-url", default="https://huggingface.co/datasets/Fhrozen/FSD50k/resolve/main/clips")
    parser.add_argument("--hf-split", choices=["dev", "eval"], default="eval")
    parser.add_argument("--manifest-split", choices=["train", "val", "test"], default="test")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--curation-output", type=Path, default=Path("data/audio/curation/fsd50k_selected_candidates.csv"))
    parser.add_argument("--split-overrides-output", type=Path)
    parser.add_argument("--metadata-split", choices=["train", "val", "test"], help="Only select records from this FSD50K metadata split.")
    parser.add_argument("--allow-reselect", action="store_true", help="Allow selecting files already present in the split override sidecar.")
    parser.add_argument("--selection-input", type=Path, help="Download an existing curation/split selection CSV instead of selecting new rows.")
    args = parser.parse_args()

    labels = [label for label in args.labels if label in LABELS]
    if not labels:
        raise ValueError("No supported labels requested")
    split_overrides_output = args.split_overrides_output or args.fsd50k_root / "FSD50K.selected_splits.csv"
    if args.selection_input:
        selected = read_selection_input(args.selection_input)
        needed = {label: len(records) for label, records in selected.items()}
    else:
        metadata_csv = args.metadata_csv or args.fsd50k_root / "FSD50K.ground_truth" / f"{args.hf_split}.csv"
        support = current_support_by_label(args.existing_manifest, split=args.manifest_split)
        needed = {
            label: args.per_label if args.per_label is not None else max(0, args.min_test_support - support[label])
            for label in labels
        }
        selected = select_fsd50k_candidates(
            metadata_csv,
            needed_by_label=needed,
            seed=args.seed,
            exclude_fnames=set() if args.allow_reselect else selected_override_fnames(split_overrides_output),
            metadata_split=args.metadata_split,
        )
    selected_counts = {label: len(records) for label, records in selected.items()}
    print(f"needed={needed}")
    print(f"selected={selected_counts}")

    if args.dry_run:
        return

    write_candidate_curation_sheet(
        args.curation_output,
        selected,
        audio_root=args.fsd50k_root,
        audio_split=args.hf_split,
        manifest_split=args.manifest_split,
    )
    print(f"wrote curation sheet: {args.curation_output}")
    write_split_overrides(
        split_overrides_output,
        selected,
        audio_split=args.hf_split,
        manifest_split=args.manifest_split,
    )
    print(f"wrote split overrides: {split_overrides_output}")

    if args.dry_run:
        return
    download_selected_candidates(
        selected,
        output_root=args.fsd50k_root,
        hf_base_url=args.hf_base_url,
        hf_split=args.hf_split,
    )


if __name__ == "__main__":
    main()
