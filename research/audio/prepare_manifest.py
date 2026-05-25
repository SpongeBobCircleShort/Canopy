from __future__ import annotations

import argparse
import csv
import random
import re
from dataclasses import replace
from pathlib import Path

from research.audio.labels import LABEL_ALIASES, canonical_label
from research.audio.manifest import ManifestRow, validate_manifest_rows, write_manifest

MANUAL_SPLITS = {"train", "val", "test"}

ESC50_CLASS_MAP = {
    "chainsaw": "chainsaw",
    "crackling_fire": "fire_crackle",
    "engine": "vehicle",
    "siren": "vehicle",
    "helicopter": "vehicle",
    "airplane": "vehicle",
    "train": "vehicle",
}

ESC50_BACKGROUND_CLASSES = {
    "rain",
    "sea_waves",
    "crickets",
    "chirping_birds",
    "water_drops",
    "wind",
    "pouring_water",
    "toilet_flush",
    "thunderstorm",
    "brushing_teeth",
    "snoring",
    "drinking_sipping",
    "door_wood_knock",
    "mouse_click",
    "keyboard_typing",
    "can_opening",
    "washing_machine",
    "vacuum_cleaner",
}

URBANSOUND8K_CLASS_MAP = {
    "gun_shot": "gunshot",
    "engine_idling": "vehicle",
    "car_horn": "vehicle",
    "siren": "vehicle",
}

URBANSOUND8K_BACKGROUND_CLASSES = {
    "air_conditioner",
    "children_playing",
    "dog_bark",
    "drilling",
    "jackhammer",
    "street_music",
}

FSD50K_LABEL_MAP = {
    "gunshot": "gunshot",
    "gunshot_and_gunfire": "gunshot",
    "gunshot_gunfire": "gunshot",
    "gunfire": "gunshot",
    "sawing": "chainsaw",
    "power_tool": "chainsaw",
    "chainsaw": "chainsaw",
    "fire": "fire_crackle",
    "crackle": "fire_crackle",
    "crackling": "fire_crackle",
    "vehicle": "vehicle",
    "motor_vehicle": "vehicle",
    "motor_vehicle_road": "vehicle",
    "truck": "vehicle",
    "car": "vehicle",
    "car_horn": "vehicle",
    "bus": "vehicle",
    "vehicle_horn_car_horn_honking": "vehicle",
}

RFCX_FRUGALAI_LABEL_MAP = {
    "chainsaw": "chainsaw",
    "environment": "background_unknown",
    "background": "background_unknown",
    "background_unknown": "background_unknown",
}

DCASE_GUNSHOT_LABELS = {"gunshot", "gun_shot"}
SPLIT_ALIASES = {
    "train": "train",
    "training": "train",
    "dev": "train",
    "development": "train",
    "val": "val",
    "valid": "val",
    "validation": "val",
    "test": "test",
    "testing": "test",
    "eval": "test",
    "evaluation": "test",
}

AUDIO_SUFFIXES = {".wav", ".flac", ".mp3", ".ogg", ".m4a"}
CURATED_FILENAME_PATTERN = re.compile(
    r"^(?P<label>[a-zA-Z0-9_]+)__"
    r"(?P<source_recording_id>[^_]+(?:_[^_]+)*)__"
    r"(?P<start_seconds>\d+(?:\.\d+)?)_(?P<end_seconds>\d+(?:\.\d+)?)__"
    r"(?P<curation_note>.+)$"
)


def build_rows(
    esc50_root: Path | None,
    urbansound8k_root: Path | None,
    canopy_root: Path | None,
    fsd50k_root: Path | None = None,
    hard_negative_manifests: list[Path] | None = None,
    *,
    rfcx_frugalai_root: Path | None = None,
    zenodo_gunshot_root: Path | None = None,
    dcase2017_task2_root: Path | None = None,
) -> list[ManifestRow]:
    rows: list[ManifestRow] = []
    if esc50_root:
        rows.extend(_rows_from_esc50(esc50_root))
    if urbansound8k_root:
        rows.extend(_rows_from_urbansound8k(urbansound8k_root))
    if fsd50k_root:
        rows.extend(_rows_from_fsd50k(fsd50k_root))
    if rfcx_frugalai_root:
        rows.extend(_rows_from_rfcx_frugalai(rfcx_frugalai_root))
    if zenodo_gunshot_root:
        rows.extend(_rows_from_zenodo_gunshot(zenodo_gunshot_root))
    if dcase2017_task2_root:
        rows.extend(_rows_from_dcase2017_task2(dcase2017_task2_root))
    if canopy_root:
        rows.extend(_rows_from_canopy_tree(canopy_root))
    for manifest_path in hard_negative_manifests or []:
        rows.extend(_rows_from_manifest(manifest_path, source_override="hard_negative"))
    if not rows:
        raise ValueError("No dataset roots were provided or no supported labels were found")
    return assign_balanced_splits(rows, locked_train_sources={"hard_negative"})


def _rows_from_esc50(root: Path) -> list[ManifestRow]:
    meta_path = root / "meta" / "esc50.csv"
    audio_dir = root / "audio"
    rows: list[ManifestRow] = []
    with meta_path.open(newline="") as handle:
        for record in csv.DictReader(handle):
            category = record["category"]
            label = ESC50_CLASS_MAP.get(category)
            if label is None and category in ESC50_BACKGROUND_CLASSES:
                label = "background_unknown"
            if label is None:
                continue
            fold = int(record["fold"])
            rows.append(
                ManifestRow(
                    path=str((audio_dir / record["filename"]).resolve()),
                    label=label,
                    source="esc50",
                    split=_fold_to_split(fold),
                    duration_seconds=5.0,
                    license="CC BY-NC",
                    notes=f"esc50_category={category}; fold={fold}",
                )
            )
    return rows


def _rows_from_urbansound8k(root: Path) -> list[ManifestRow]:
    meta_path = root / "metadata" / "UrbanSound8K.csv"
    audio_root = root / "audio"
    rows: list[ManifestRow] = []
    with meta_path.open(newline="") as handle:
        for record in csv.DictReader(handle):
            class_name = record["class"]
            label = URBANSOUND8K_CLASS_MAP.get(class_name)
            if label is None and class_name in URBANSOUND8K_BACKGROUND_CLASSES:
                label = "background_unknown"
            if label is None:
                continue
            fold = int(record["fold"])
            rows.append(
                ManifestRow(
                    path=str((audio_root / f"fold{fold}" / record["slice_file_name"]).resolve()),
                    label=label,
                    source="urbansound8k",
                    split=_fold_to_split(fold),
                    duration_seconds=None,
                    license="see-dataset-license",
                    notes=f"urbansound_class={class_name}; fold={fold}",
                )
            )
    return rows


def _rows_from_fsd50k(root: Path) -> list[ManifestRow]:
    audio_index = _index_audio_files(root)
    split_overrides = _fsd50k_split_overrides(root)
    rows: list[ManifestRow] = []
    for metadata_path in _fsd50k_metadata_files(root):
        is_eval_metadata = "eval" in metadata_path.stem.lower()
        default_split = "test" if is_eval_metadata else "train"
        with metadata_path.open(newline="") as handle:
            for record in csv.DictReader(handle):
                labels = _fsd50k_record_labels(record)
                if not labels:
                    continue
                audio_path = _fsd50k_audio_path(record, audio_index)
                if audio_path is None:
                    continue
                fname = _record_value(record, "fname", "filename", "file_name", "clip_id")
                override = split_overrides.get(Path(fname).stem)
                label = override.get("label") if override and override.get("label") else _canonical_fsd50k_label(labels)
                split = override.get("split") if override and override.get("split") else _canonical_split(record.get("split") or record.get("subset") or default_split)
                manual_split_note = f"; manual_split={split}" if override else f"{'; manual_split=test' if is_eval_metadata else ''}"
                rows.append(
                    ManifestRow(
                        path=str(audio_path.resolve()),
                        label=label,
                        source="fsd50k",
                        split=split,
                        duration_seconds=None,
                        license="see-dataset-license",
                        notes=(
                            f"fsd50k_labels={','.join(labels)}; metadata={metadata_path.name}"
                            f"{manual_split_note}"
                        ),
                    )
                )
    return rows


def _rows_from_rfcx_frugalai(root: Path) -> list[ManifestRow]:
    rows: list[ManifestRow] = []
    for audio_path in _audio_files(root):
        relative = audio_path.relative_to(root)
        label_dir = _first_matching_part(relative, set(RFCX_FRUGALAI_LABEL_MAP))
        if label_dir is None:
            continue
        label = RFCX_FRUGALAI_LABEL_MAP[label_dir]
        split = _split_from_path(relative)
        manual_split_note = f"; manual_split={split}" if split else ""
        rows.append(
            ManifestRow(
                path=str(audio_path.resolve()),
                label=label,
                source="rfcx_frugalai",
                split=split or "train",
                duration_seconds=3.0,
                license="CC BY-NC 4.0",
                notes=(
                    f"rfcx_label={label_dir}; source_recording_id={audio_path.stem}"
                    f"{manual_split_note}"
                ),
            )
        )
    return rows


def _rows_from_zenodo_gunshot(root: Path) -> list[ManifestRow]:
    metadata = _metadata_by_audio_stem(root)
    rows: list[ManifestRow] = []
    for audio_path in _audio_files(root):
        relative = audio_path.relative_to(root)
        split = _split_from_path(relative)
        manual_split_note = f"; manual_split={split}" if split else ""
        metadata_notes = _metadata_notes(metadata.get(audio_path.stem, {}))
        rows.append(
            ManifestRow(
                path=str(audio_path.resolve()),
                label="gunshot",
                source="zenodo_gunshot_gunfire",
                split=split or "train",
                duration_seconds=None,
                license="CC BY 4.0",
                notes=(
                    f"zenodo_record=7004819; source_recording_id={audio_path.stem}"
                    f"{manual_split_note}{metadata_notes}"
                ),
            )
        )
    return rows


def _rows_from_dcase2017_task2(root: Path) -> list[ManifestRow]:
    audio_index = _index_audio_files(root)
    rows: list[ManifestRow] = []
    for metadata_path in sorted(root.rglob("*.csv")):
        with metadata_path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            for record in reader:
                event_label = _record_value(record, "event_label", "event", "label", "class", "event_class")
                if _normalize_dataset_label(event_label) not in DCASE_GUNSHOT_LABELS:
                    continue
                audio_path = _record_audio_path(record, audio_index)
                if audio_path is None:
                    continue
                split = _canonical_split(
                    _record_value(record, "split", "subset", "set") or _split_from_path(audio_path.relative_to(root))
                )
                rows.append(
                    ManifestRow(
                        path=str(audio_path.resolve()),
                        label="gunshot",
                        source="dcase2017_task2",
                        split=split,
                        duration_seconds=None,
                        license="see-dataset-license",
                        notes=(
                            f"dcase_event={event_label}; metadata={metadata_path.name}; "
                            f"source_recording_id={audio_path.stem}; manual_split={split}"
                            f"{_metadata_notes(record, include={'onset', 'offset', 'event_onset', 'event_offset'})}"
                        ),
                    )
                )
    return rows


def assign_balanced_splits(
    rows: list[ManifestRow],
    *,
    seed: int = 42,
    val_fraction: float = 0.15,
    test_fraction: float = 0.15,
    locked_train_sources: set[str] | None = None,
) -> list[ManifestRow]:
    locked_train_sources = locked_train_sources or set()
    locked_rows = [replace(row, split="train") for row in rows if row.source in locked_train_sources]
    manual_split_rows = [
        replace(row, split=_manual_split(row) or row.split)
        for row in rows
        if row.source not in locked_train_sources and _manual_split(row)
    ]
    unlocked_rows = [
        row
        for row in rows
        if row.source not in locked_train_sources and not _manual_split(row)
    ]
    grouped: dict[str, list[ManifestRow]] = {}
    for row in unlocked_rows:
        grouped.setdefault(row.label, []).append(row)

    rng = random.Random(seed)
    balanced_rows: list[ManifestRow] = []
    for label, label_rows in sorted(grouped.items()):
        row_groups: dict[str, list[ManifestRow]] = {}
        for row in label_rows:
            row_groups.setdefault(_split_group_key(row), []).append(row)
        shuffled_groups = list(row_groups.items())
        rng.shuffle(shuffled_groups)
        group_count = len(shuffled_groups)
        row_count = len(label_rows)
        if group_count >= 3:
            test_target = max(1, round(row_count * test_fraction))
            val_target = max(1, round(row_count * val_fraction))
            split_by_group: dict[str, str] = {}
            test_rows = 0
            val_rows = 0
            for group_key, group_rows in shuffled_groups:
                if test_rows < test_target:
                    split_by_group[group_key] = "test"
                    test_rows += len(group_rows)
                elif val_rows < val_target:
                    split_by_group[group_key] = "val"
                    val_rows += len(group_rows)
                else:
                    split_by_group[group_key] = "train"
        elif group_count == 2:
            split_by_group = {shuffled_groups[0][0]: "test", shuffled_groups[1][0]: "train"}
        else:
            split_by_group = {shuffled_groups[0][0]: "train"} if shuffled_groups else {}
        for group_key, group_rows in shuffled_groups:
            split = split_by_group[group_key]
            balanced_rows.extend(
                replace(
                    row,
                    split=split,
                    notes=f"{row.notes}; split_group={group_key}; stratified_split_seed={seed}".strip("; "),
                )
                for row in group_rows
            )
    return sorted([*balanced_rows, *locked_rows, *manual_split_rows], key=lambda row: (row.source, row.label, row.path))


def _manual_split(row: ManifestRow) -> str:
    split = _note_value(row.notes, "manual_split")
    return split if split in MANUAL_SPLITS else ""


def _split_group_key(row: ManifestRow) -> str:
    for metadata_key in (
        "source_recording_id",
        "recording_id",
        "source_recording",
        "source_file",
        "site_id",
        "video_id",
        "clip_id",
    ):
        value = _note_value(row.notes, metadata_key)
        if value:
            return f"{row.source}:{metadata_key}:{value}"

    stem = Path(row.path).stem
    if row.source == "urbansound8k":
        return f"{row.source}:fsid:{stem.split('-', 1)[0]}"
    if row.source == "esc50":
        parts = stem.split("-")
        if len(parts) >= 2:
            return f"{row.source}:source:{parts[1]}"
    if row.source == "canopy":
        source_like_stem = re.sub(r"(_clip)?[_-]?\d+$", "", stem)
        return f"{row.source}:stem:{source_like_stem or stem}"
    return f"{row.source}:stem:{stem}"


def _note_value(notes: str, key: str) -> str:
    marker = f"{key}="
    if marker not in notes:
        return ""
    return notes.split(marker, 1)[1].split(";", 1)[0].strip()


def _rows_from_canopy_tree(root: Path) -> list[ManifestRow]:
    rows: list[ManifestRow] = []
    for audio_path in sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in AUDIO_SUFFIXES):
        relative = audio_path.relative_to(root)
        if not relative.parts:
            continue
        parsed = _parse_canopy_relative_path(relative)
        if parsed is None:
            continue
        label_dir, split, subcategory = parsed
        label = canonical_label(label_dir)
        manual_split_note = f"; manual_split={split}" if split else ""
        filename_notes = _curated_filename_notes(audio_path, expected_label=label)
        rows.append(
            ManifestRow(
                path=str(audio_path.resolve()),
                label=label,
                source="canopy",
                split=split or "train",
                license="canopy-internal",
                notes=f"canopy_label_dir={label_dir}; canopy_subcategory={subcategory}{manual_split_note}{filename_notes}",
            )
        )
    return rows


def _parse_canopy_relative_path(relative: Path) -> tuple[str, str, str] | None:
    parts = relative.parts
    # Check split/label layout before label-only layout so "train/fire_crackle/..." is not
    # parsed as label_dir="train" (vehicle alias in LABEL_ALIASES).
    if parts[0] in MANUAL_SPLITS and len(parts) > 2 and parts[1] in LABEL_ALIASES:
        split = parts[0]
        label_dir = parts[1]
        return label_dir, split, "/".join(parts[2:-1])
    if parts[0] in LABEL_ALIASES:
        label_dir = parts[0]
        split = parts[1] if len(parts) > 2 and parts[1] in MANUAL_SPLITS else ""
        subcategory_start = 2 if split else 1
        return label_dir, split, "/".join(parts[subcategory_start:-1])
    return None


def _curated_filename_notes(audio_path: Path, *, expected_label: str) -> str:
    match = CURATED_FILENAME_PATTERN.match(audio_path.stem)
    if not match:
        return ""
    parsed_label = _safe_canonical_label(match.group("label"))
    mismatch_note = "; filename_label_mismatch=true" if parsed_label and parsed_label != expected_label else ""
    curation_note = match.group("curation_note").replace("_", " ").strip()
    return (
        f"; source_recording_id={match.group('source_recording_id')}"
        f"; start_seconds={match.group('start_seconds')}"
        f"; end_seconds={match.group('end_seconds')}"
        f"; curation_note={curation_note}"
        f"{mismatch_note}"
    )


def _safe_canonical_label(value: str) -> str:
    try:
        return canonical_label(value)
    except ValueError:
        return ""


def _rows_from_manifest(path: Path, *, source_override: str | None = None) -> list[ManifestRow]:
    with path.open(newline="") as handle:
        source_rows = [dict(row) for row in csv.DictReader(handle)]
    if not source_rows:
        return []
    validate_manifest_rows(source_rows, base_dir=path.parent)
    rows = []
    for row in source_rows:
        rows.append(
            ManifestRow(
                path=row["path"],
                label=row["label"],
                source=source_override or row["source"],
                split=row["split"],
                duration_seconds=float(row["duration_seconds"]) if row["duration_seconds"] else None,
                license=row["license"],
                notes=f"{row['notes']}; imported_manifest={path.name}".strip("; "),
            )
        )
    return rows


def _index_audio_files(root: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in AUDIO_SUFFIXES:
            index.setdefault(path.name, path)
            index.setdefault(path.stem, path)
    return index


def _audio_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in AUDIO_SUFFIXES)


def _first_matching_part(path: Path, candidates: set[str]) -> str | None:
    for part in path.parts[:-1]:
        normalized = _normalize_dataset_label(part)
        if normalized in candidates:
            return normalized
    return None


def _split_from_path(path: Path) -> str:
    for part in path.parts[:-1]:
        split = SPLIT_ALIASES.get(_normalize_dataset_label(part))
        if split:
            return split
    return ""


def _metadata_by_audio_stem(root: Path) -> dict[str, dict[str, str]]:
    metadata: dict[str, dict[str, str]] = {}
    for csv_path in sorted(root.rglob("*.csv")):
        with csv_path.open(newline="") as handle:
            for record in csv.DictReader(handle):
                raw_name = _record_value(record, "filename", "file", "audio_file", "recording", "name")
                if not raw_name:
                    continue
                stem = Path(raw_name).stem
                if stem:
                    metadata.setdefault(stem, record)
    return metadata


def _metadata_notes(record: dict[str, str], *, include: set[str] | None = None) -> str:
    if not record:
        return ""
    allowed = include or {"device", "device_id", "firearm", "model", "shot_count", "num_gunshots", "timestamps"}
    parts = []
    for key, value in sorted(record.items()):
        normalized_key = _normalize_dataset_label(key)
        if normalized_key in allowed and value:
            clean_value = str(value).replace(";", ",").strip()
            parts.append(f"{normalized_key}={clean_value}")
    return f"; {'; '.join(parts)}" if parts else ""


def _record_value(record: dict[str, str], *keys: str) -> str:
    normalized_record = {_normalize_dataset_label(key): value for key, value in record.items()}
    for key in keys:
        value = normalized_record.get(_normalize_dataset_label(key), "")
        if value:
            return value.strip()
    return ""


def _record_audio_path(record: dict[str, str], audio_index: dict[str, Path]) -> Path | None:
    raw_name = _record_value(record, "filename", "file", "audio_file", "audio_filename", "mixture_file", "recording")
    if not raw_name:
        return None
    path = Path(raw_name)
    candidates = [path.name, path.stem]
    if not path.suffix:
        candidates.extend(f"{path.name}{suffix}" for suffix in AUDIO_SUFFIXES)
    for candidate in candidates:
        if candidate in audio_index:
            return audio_index[candidate]
    return None


def _fsd50k_metadata_files(root: Path) -> list[Path]:
    candidates = []
    for path in root.rglob("*.csv"):
        name = path.name.lower()
        if name in {"dev.csv", "eval.csv"}:
            candidates.append(path)
    return sorted(candidates)


def _fsd50k_record_labels(record: dict[str, str]) -> list[str]:
    raw = record.get("labels") or record.get("label") or record.get("tags") or ""
    labels = []
    for value in raw.replace(";", ",").split(","):
        label = value.strip()
        if label:
            labels.append(label)
    return labels


def _fsd50k_split_overrides(root: Path) -> dict[str, dict[str, str]]:
    overrides: dict[str, dict[str, str]] = {}
    for path in sorted(root.glob("FSD50K.selected_splits*.csv")):
        with path.open(newline="") as handle:
            for record in csv.DictReader(handle):
                fname = _record_value(record, "fname", "filename", "file_name", "clip_id")
                if not fname:
                    continue
                split = _canonical_split(_record_value(record, "split", "manifest_split", "subset"))
                label = _safe_canonical_label(_record_value(record, "label", "canopy_label"))
                overrides[Path(fname).stem] = {"split": split, "label": label}
    return overrides


def _fsd50k_audio_path(record: dict[str, str], audio_index: dict[str, Path]) -> Path | None:
    raw_name = record.get("fname") or record.get("filename") or record.get("file_name") or record.get("clip_id") or ""
    if not raw_name:
        return None
    path = Path(raw_name)
    candidates = [path.name, path.stem]
    if path.suffix:
        candidates.insert(0, path.name)
    else:
        candidates.extend(f"{path.name}{suffix}" for suffix in AUDIO_SUFFIXES)
    for candidate in candidates:
        if candidate in audio_index:
            return audio_index[candidate]
    return None


def _canonical_fsd50k_label(labels: list[str]) -> str:
    mapped = []
    for label in labels:
        normalized = _normalize_dataset_label(label)
        if normalized in FSD50K_LABEL_MAP:
            mapped.append(FSD50K_LABEL_MAP[normalized])
    for preferred_label in ["gunshot", "chainsaw", "fire_crackle", "vehicle"]:
        if preferred_label in mapped:
            return preferred_label
    return "background_unknown"


def _normalize_dataset_label(label: str) -> str:
    normalized = label.strip().lower().replace("&", "and")
    normalized = re.sub(r"[\(\)\[\],]", " ", normalized)
    normalized = re.sub(r"[/\-]", " ", normalized)
    normalized = re.sub(r"\s+", "_", normalized).strip("_")
    return normalized


def _canonical_split(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"val", "valid", "validation"}:
        return "val"
    if normalized in {"test", "eval", "evaluation"}:
        return "test"
    return "train"


def _fold_to_split(fold: int) -> str:
    if fold == 10:
        return "test"
    if fold == 9:
        return "val"
    return "train"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a Canopy audio threat manifest from local datasets.")
    parser.add_argument("--esc50-root", type=Path)
    parser.add_argument("--urbansound8k-root", type=Path)
    parser.add_argument("--fsd50k-root", type=Path)
    parser.add_argument("--rfcx-frugalai-root", type=Path)
    parser.add_argument("--zenodo-gunshot-root", type=Path)
    parser.add_argument("--dcase2017-task2-root", type=Path)
    parser.add_argument("--canopy-root", type=Path)
    parser.add_argument("--hard-negative-manifest", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows = build_rows(
        args.esc50_root,
        args.urbansound8k_root,
        args.canopy_root,
        args.fsd50k_root,
        args.hard_negative_manifest,
        rfcx_frugalai_root=args.rfcx_frugalai_root,
        zenodo_gunshot_root=args.zenodo_gunshot_root,
        dcase2017_task2_root=args.dcase2017_task2_root,
    )
    write_manifest(args.output, rows)
    print(f"Wrote {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
