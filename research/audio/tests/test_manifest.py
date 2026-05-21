from pathlib import Path

import pytest

from research.audio.labels import canonical_label
from research.audio.curation_sheet import build_curation_rows, validate_curation_sheet, write_curation_sheet
from research.audio.evaluate import _threshold_recommendations
from research.audio.manifest import MANIFEST_COLUMNS, ManifestRow, read_manifest, validate_manifest_rows, write_manifest
from research.audio.mine_hard_negatives import hard_negative_from_prediction
from research.audio.prepare_manifest import (
    _canonical_fsd50k_label,
    _rows_from_dcase2017_task2,
    _rows_from_fsd50k,
    _rows_from_rfcx_frugalai,
    _rows_from_zenodo_gunshot,
    assign_balanced_splits,
    build_rows,
)
from research.audio.report_manifest import build_manifest_report


def test_label_aliases_map_to_canopy_taxonomy() -> None:
    assert canonical_label("gun_shot") == "gunshot"
    assert canonical_label("crackling fire") == "fire_crackle"
    assert canonical_label("engine_idling") == "vehicle"
    with pytest.raises(ValueError, match="Unsupported audio label"):
        canonical_label("birdsong")


def test_manifest_round_trip_and_validation(tmp_path: Path) -> None:
    audio_file = tmp_path / "clip.wav"
    audio_file.write_bytes(b"not-real-audio")
    manifest_path = tmp_path / "manifest.csv"

    write_manifest(
        manifest_path,
        [
            ManifestRow(
                path=str(audio_file),
                label="gun_shot",
                source="unit",
                split="train",
                duration_seconds=1.2,
                license="test",
                notes="synthetic",
            )
        ],
    )

    rows = read_manifest(manifest_path)
    assert rows[0]["label"] == "gunshot"
    assert rows[0]["split"] == "train"


def test_manifest_rejects_bad_split() -> None:
    with pytest.raises(ValueError, match="split must be one of"):
        validate_manifest_rows(
            [
                {
                    "path": "missing.wav",
                    "label": "chainsaw",
                    "source": "unit",
                    "split": "holdout",
                    "duration_seconds": "",
                    "license": "",
                    "notes": "",
                }
            ],
            require_files=False,
        )


def test_balanced_split_assigner_covers_each_label() -> None:
    rows = []
    for label in ["chainsaw", "gunshot", "vehicle", "fire_crackle", "background_unknown"]:
        for index in range(10):
            rows.append(ManifestRow(path=f"/tmp/{label}-{index}.wav", label=label, source="unit", split="train"))

    split_rows = assign_balanced_splits(rows, seed=1, val_fraction=0.2, test_fraction=0.2)
    observed = {(row.label, row.split) for row in split_rows}

    for label in ["chainsaw", "gunshot", "vehicle", "fire_crackle", "background_unknown"]:
        assert (label, "train") in observed
        assert (label, "val") in observed
        assert (label, "test") in observed


def test_balanced_split_assigner_keeps_recording_groups_together() -> None:
    rows = []
    for recording_index in range(8):
        for clip_index in range(2):
            rows.append(
                ManifestRow(
                    path=f"/tmp/chainsaw-recording-{recording_index}-clip-{clip_index}.wav",
                    label="chainsaw",
                    source="unit",
                    split="train",
                    notes=f"recording_id=rec-{recording_index}",
                )
            )

    split_rows = assign_balanced_splits(rows, seed=1, val_fraction=0.25, test_fraction=0.25)
    splits_by_recording: dict[str, set[str]] = {}
    for row in split_rows:
        recording_id = row.notes.split("recording_id=", 1)[1].split(";", 1)[0]
        splits_by_recording.setdefault(recording_id, set()).add(row.split)

    assert all(len(splits) == 1 for splits in splits_by_recording.values())


def test_balanced_split_assigner_uses_curated_source_recording_id() -> None:
    rows = []
    for recording_index in range(8):
        for clip_index in range(2):
            rows.append(
                ManifestRow(
                    path=f"/tmp/fire-recording-{recording_index}-clip-{clip_index}.wav",
                    label="fire_crackle",
                    source="canopy",
                    split="train",
                    notes=f"source_recording_id=fire-src-{recording_index}",
                )
            )

    split_rows = assign_balanced_splits(rows, seed=1, val_fraction=0.25, test_fraction=0.25)
    splits_by_recording: dict[str, set[str]] = {}
    for row in split_rows:
        recording_id = row.notes.split("source_recording_id=", 1)[1].split(";", 1)[0]
        splits_by_recording.setdefault(recording_id, set()).add(row.split)

    assert all(len(splits) == 1 for splits in splits_by_recording.values())


def test_canopy_manual_split_folders_are_preserved(tmp_path: Path) -> None:
    canopy_root = tmp_path / "canopy-labeled"
    chainsaw_test = canopy_root / "chainsaw" / "test"
    fire_train = canopy_root / "train" / "fire_crackle"
    chainsaw_test.mkdir(parents=True)
    fire_train.mkdir(parents=True)
    (chainsaw_test / "chainsaw__yt-abc123__031.0_035.0__distant-idle.wav").write_bytes(b"not-real-audio")
    (fire_train / "verified-fire.wav").write_bytes(b"not-real-audio")

    rows = build_rows(None, None, canopy_root)

    by_name = {Path(row.path).name: row for row in rows}
    assert by_name["chainsaw__yt-abc123__031.0_035.0__distant-idle.wav"].label == "chainsaw"
    assert by_name["chainsaw__yt-abc123__031.0_035.0__distant-idle.wav"].split == "test"
    assert "manual_split=test" in by_name["chainsaw__yt-abc123__031.0_035.0__distant-idle.wav"].notes
    assert "source_recording_id=yt-abc123" in by_name["chainsaw__yt-abc123__031.0_035.0__distant-idle.wav"].notes
    assert "start_seconds=031.0" in by_name["chainsaw__yt-abc123__031.0_035.0__distant-idle.wav"].notes
    assert by_name["verified-fire.wav"].label == "fire_crackle"
    assert by_name["verified-fire.wav"].split == "train"


def test_curation_sheet_generation_and_validation(tmp_path: Path) -> None:
    canopy_root = tmp_path / "canopy-labeled"
    clip_dir = canopy_root / "gunshot" / "test"
    clip_dir.mkdir(parents=True)
    clip_path = clip_dir / "gunshot__field-001__010.0_014.0__clear-shot.wav"
    clip_path.write_bytes(b"not-real-audio")
    sheet_path = tmp_path / "curation.csv"

    rows = build_curation_rows(canopy_root)
    rows[0]["decision"] = "accepted"
    write_curation_sheet(sheet_path, rows)

    assert rows[0]["label"] == "gunshot"
    assert rows[0]["split"] == "test"
    assert rows[0]["source_recording_id"] == "field-001"
    assert validate_curation_sheet(sheet_path) == []


def test_fsd50k_label_mapping_is_conservative() -> None:
    assert _canonical_fsd50k_label(["Gunshot", "gunfire"]) == "gunshot"
    assert _canonical_fsd50k_label(["Gunshot_and_gunfire"]) == "gunshot"
    assert _canonical_fsd50k_label(["Sawing"]) == "chainsaw"
    assert _canonical_fsd50k_label(["Fire"]) == "fire_crackle"
    assert _canonical_fsd50k_label(["Truck"]) == "vehicle"
    assert _canonical_fsd50k_label(["Speech", "Music"]) == "background_unknown"


def test_fsd50k_rows_from_local_metadata(tmp_path: Path) -> None:
    audio_dir = tmp_path / "FSD50K.dev_audio"
    audio_dir.mkdir()
    audio_file = audio_dir / "123.wav"
    audio_file.write_bytes(b"not-real-audio")
    metadata_dir = tmp_path / "FSD50K.ground_truth"
    metadata_dir.mkdir()
    (metadata_dir / "dev.csv").write_text("fname,labels,split\n123,\"Gunshot,gunfire\",train\n")

    rows = _rows_from_fsd50k(tmp_path)

    assert len(rows) == 1
    assert rows[0].label == "gunshot"
    assert rows[0].source == "fsd50k"
    assert "fsd50k_labels=Gunshot,gunfire" in rows[0].notes


def test_fsd50k_eval_metadata_is_locked_to_test(tmp_path: Path) -> None:
    audio_dir = tmp_path / "FSD50K.eval_audio"
    audio_dir.mkdir()
    audio_file = audio_dir / "456.wav"
    audio_file.write_bytes(b"not-real-audio")
    metadata_dir = tmp_path / "FSD50K.ground_truth"
    metadata_dir.mkdir()
    (metadata_dir / "eval.csv").write_text("fname,labels,mids\n456,Gunshot_and_gunfire,/m/test\n")

    rows = build_rows(None, None, None, tmp_path)

    assert len(rows) == 1
    assert rows[0].label == "gunshot"
    assert rows[0].split == "test"
    assert "manual_split=test" in rows[0].notes


def test_fsd50k_selected_split_override_locks_dev_rows_to_val(tmp_path: Path) -> None:
    audio_dir = tmp_path / "FSD50K.dev_audio"
    audio_dir.mkdir()
    audio_file = audio_dir / "789.wav"
    audio_file.write_bytes(b"not-real-audio")
    metadata_dir = tmp_path / "FSD50K.ground_truth"
    metadata_dir.mkdir()
    (metadata_dir / "dev.csv").write_text("fname,labels,mids,split\n789,Sawing,/m/test,train\n")
    (tmp_path / "FSD50K.selected_splits.csv").write_text("fname,label,split,audio_split,notes\n789,chainsaw,val,dev,manual validation row\n")

    rows = build_rows(None, None, None, tmp_path)

    assert len(rows) == 1
    assert rows[0].label == "chainsaw"
    assert rows[0].split == "val"
    assert "manual_split=val" in rows[0].notes


def test_rfcx_frugalai_rows_from_local_layout(tmp_path: Path) -> None:
    root = tmp_path / "RFCx-FrugalAI"
    chainsaw = root / "train" / "chainsaw" / "chainsaw-001.wav"
    background = root / "test" / "environment" / "forest-001.wav"
    chainsaw.parent.mkdir(parents=True)
    background.parent.mkdir(parents=True)
    chainsaw.write_bytes(b"not-real-audio")
    background.write_bytes(b"not-real-audio")

    rows = _rows_from_rfcx_frugalai(root)
    by_name = {Path(row.path).name: row for row in rows}

    assert by_name["chainsaw-001.wav"].label == "chainsaw"
    assert by_name["chainsaw-001.wav"].source == "rfcx_frugalai"
    assert by_name["chainsaw-001.wav"].split == "train"
    assert by_name["forest-001.wav"].label == "background_unknown"
    assert by_name["forest-001.wav"].split == "test"


def test_zenodo_gunshot_rows_from_local_audio(tmp_path: Path) -> None:
    root = tmp_path / "zenodo-gunshot"
    audio = root / "testing" / "field-shot.wav"
    audio.parent.mkdir(parents=True)
    audio.write_bytes(b"not-real-audio")

    rows = _rows_from_zenodo_gunshot(root)

    assert len(rows) == 1
    assert rows[0].label == "gunshot"
    assert rows[0].source == "zenodo_gunshot_gunfire"
    assert rows[0].split == "test"
    assert "manual_split=test" in rows[0].notes


def test_dcase2017_task2_rows_from_event_metadata(tmp_path: Path) -> None:
    root = tmp_path / "dcase2017-task2"
    audio = root / "audio" / "mixture001.wav"
    audio.parent.mkdir(parents=True)
    audio.write_bytes(b"not-real-audio")
    metadata = root / "meta.csv"
    metadata.write_text("filename,event_label,split,onset,offset\nmixture001.wav,gunshot,test,1.0,1.5\n")

    rows = _rows_from_dcase2017_task2(root)

    assert len(rows) == 1
    assert rows[0].label == "gunshot"
    assert rows[0].source == "dcase2017_task2"
    assert rows[0].split == "test"
    assert "event_onset" not in rows[0].notes
    assert "onset=1.0" in rows[0].notes


def test_hard_negative_manifest_rows_remain_training_only(tmp_path: Path) -> None:
    audio_file = tmp_path / "background.wav"
    audio_file.write_bytes(b"not-real-audio")
    hard_manifest = tmp_path / "hard.csv"
    write_manifest(
        hard_manifest,
        [
            ManifestRow(
                path=str(audio_file),
                label="background_unknown",
                source="hard_negative",
                split="train",
                notes="predicted=gunshot",
            )
        ],
    )

    rows = build_rows(None, None, None, None, [hard_manifest])

    assert len(rows) == 1
    assert rows[0].source == "hard_negative"
    assert rows[0].split == "train"


def test_empty_hard_negative_manifest_is_allowed(tmp_path: Path) -> None:
    hard_manifest = tmp_path / "empty-hard.csv"
    hard_manifest.write_text(",".join(MANIFEST_COLUMNS) + "\n")
    canopy_dir = tmp_path / "canopy" / "background_unknown"
    canopy_dir.mkdir(parents=True)
    (canopy_dir / "background.wav").write_bytes(b"not-real-audio")

    rows = build_rows(None, None, tmp_path / "canopy", None, [hard_manifest])

    assert len(rows) == 1
    assert rows[0].source == "canopy"


def test_hard_negative_from_prediction_filters_and_builds_row() -> None:
    source_row = {
        "path": "/tmp/background.wav",
        "label": "background_unknown",
        "source": "unit",
        "split": "train",
        "duration_seconds": "",
        "license": "test",
        "notes": "unit background",
    }

    assert hard_negative_from_prediction(
        source_row,
        predicted_label="fire_crackle",
        confidence=0.99,
        target_labels={"gunshot"},
        count_for_label=0,
        max_per_label=10,
        min_confidence=0.5,
    ) is None

    row = hard_negative_from_prediction(
        source_row,
        predicted_label="gunshot",
        confidence=0.91,
        target_labels={"gunshot"},
        count_for_label=0,
        max_per_label=10,
        min_confidence=0.5,
    )

    assert row is not None
    assert row.label == "background_unknown"
    assert row.source == "hard_negative"
    assert "predicted=gunshot" in row.notes


def test_threshold_recommendations_can_prioritize_recall_floor() -> None:
    targets = [1, 1, 4, 4, 4, 4]
    score_rows = [
        [0.0, 0.90, 0.0, 0.0, 0.10],
        [0.0, 0.40, 0.0, 0.0, 0.60],
        [0.0, 0.70, 0.0, 0.0, 0.30],
        [0.0, 0.70, 0.0, 0.0, 0.30],
        [0.0, 0.70, 0.0, 0.0, 0.30],
        [0.0, 0.70, 0.0, 0.0, 0.30],
    ]

    thresholds = _threshold_recommendations(
        targets,
        score_rows,
        {"threshold_step": 0.05, "min_precision": {"gunshot": 0.0}, "min_recall": {"gunshot": 1.0}},
    )

    assert thresholds["gunshot"]["recall"] == 1.0
    assert thresholds["gunshot"]["threshold"] <= 0.4


def test_threshold_recommendations_can_limit_background_false_positives() -> None:
    targets = [1, 1, 4, 4, 4, 4]
    score_rows = [
        [0.0, 0.90, 0.0, 0.0, 0.10],
        [0.0, 0.70, 0.0, 0.0, 0.30],
        [0.0, 0.80, 0.0, 0.0, 0.20],
        [0.0, 0.60, 0.0, 0.0, 0.40],
        [0.0, 0.20, 0.0, 0.0, 0.80],
        [0.0, 0.10, 0.0, 0.0, 0.90],
    ]

    thresholds = _threshold_recommendations(
        targets,
        score_rows,
        {
            "threshold_step": 0.05,
            "min_precision": {"gunshot": 0.0},
            "max_background_fp_rate": {"gunshot": 0.25},
        },
    )

    assert thresholds["gunshot"]["background_fp_rate"] <= 0.25
    assert thresholds["gunshot"]["threshold"] >= 0.65


def test_threshold_recommendations_fallback_prefers_lowest_background_false_positive_rate() -> None:
    targets = [1, 1, 4, 4, 4, 4]
    score_rows = [
        [0.0, 0.90, 0.0, 0.0, 0.10],
        [0.0, 0.20, 0.0, 0.0, 0.80],
        [0.0, 0.80, 0.0, 0.0, 0.20],
        [0.0, 0.60, 0.0, 0.0, 0.40],
        [0.0, 0.20, 0.0, 0.0, 0.80],
        [0.0, 0.10, 0.0, 0.0, 0.90],
    ]

    thresholds = _threshold_recommendations(
        targets,
        score_rows,
        {
            "threshold_step": 0.05,
            "min_precision": {"gunshot": 0.95},
            "min_recall": {"gunshot": 1.0},
            "max_background_fp_rate": {"gunshot": 0.0},
        },
    )

    assert thresholds["gunshot"]["background_fp_rate"] == 0
    assert thresholds["gunshot"]["threshold"] > 0.8


def test_manifest_report_flags_low_test_support(tmp_path: Path) -> None:
    rows = []
    for label in ["chainsaw", "gunshot", "vehicle", "fire_crackle", "background_unknown"]:
        for split in ["train", "val", "test"]:
            audio_file = tmp_path / f"{label}-{split}.wav"
            audio_file.write_bytes(b"not-real-audio")
            rows.append(ManifestRow(path=str(audio_file), label=label, source="unit", split=split, notes=f"unit_class={label}"))
    manifest_path = tmp_path / "manifest.csv"
    write_manifest(manifest_path, rows)

    report = build_manifest_report(manifest_path, min_test_support=50, experimental=False)

    assert report["validation"]["passed"] is False
    assert "chainsaw has 1 test rows" in report["validation"]["failures"][0]
    assert report["validation"]["collection_targets"]["chainsaw"]["additional_verified_test_rows_needed"] == 49
    assert build_manifest_report(manifest_path, min_test_support=50, experimental=True)["validation"]["passed"] is True


def test_manifest_report_flags_source_recording_split_leak(tmp_path: Path) -> None:
    train_clip = tmp_path / "chainsaw-train.wav"
    test_clip = tmp_path / "chainsaw-test.wav"
    train_clip.write_bytes(b"not-real-audio")
    test_clip.write_bytes(b"not-real-audio")
    manifest_path = tmp_path / "manifest.csv"
    write_manifest(
        manifest_path,
        [
            ManifestRow(path=str(train_clip), label="chainsaw", source="unit", split="train", notes="source_recording_id=rec-1"),
            ManifestRow(path=str(test_clip), label="chainsaw", source="unit", split="test", notes="source_recording_id=rec-1"),
        ],
    )

    report = build_manifest_report(manifest_path, min_test_support=1, experimental=False)

    assert report["validation"]["passed"] is False
    assert report["counts"]["source_recording_split_leaks"] == {"unit:source_recording_id:rec-1": ["test", "train"]}
