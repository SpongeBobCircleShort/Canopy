import csv
import json
from pathlib import Path

import pytest

from research.audio.labels import canonical_label
from research.audio.calibrate_thresholds import _candidate_rank
from research.audio.curation_sheet import build_curation_rows, validate_curation_sheet, write_curation_sheet
from research.audio.error_audit import build_audit_rows, summarize_top_confusions
from research.audio.evaluate import _threshold_recommendations
from research.audio.infer import _load_thresholds, _thresholded_label
from research.audio.build_kaggle_balanced_manifest import build_manifest as build_kaggle_balanced_manifest
from research.audio.import_fsc22 import (
    CANOPY_LABEL_FOR_FSC22_CLASS,
    build_fsc22_rows,
    write_fsc22_manifest,
)
from research.audio.import_kaggle_fire import build_kaggle_fire_rows, write_kaggle_fire_manifest
from research.audio.import_kaggle_gunshot import build_kaggle_gunshot_rows, write_kaggle_gunshot_manifest
from research.audio.import_kaggle_vehicle import build_kaggle_vehicle_rows, write_kaggle_vehicle_manifest
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
from research.audio.review_app import _audit_sort_order, filter_rows, load_decisions, merge_decisions, save_decision


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


def test_inference_thresholds_default_to_background_when_no_class_passes(tmp_path: Path) -> None:
    (tmp_path / "val_metrics.json").write_text(
        json.dumps(
            {
                "threshold_recommendations": {
                    "chainsaw": {"threshold": 0.8},
                    "gunshot": {"threshold": 0.75},
                    "background_unknown": {"threshold": 0.5},
                }
            }
        )
    )

    thresholds = _load_thresholds(tmp_path)
    label = _thresholded_label(
        {"chainsaw": 0.62, "gunshot": 0.2, "background_unknown": 0.18},
        thresholds,
        default_label="background_unknown",
    )

    assert thresholds["chainsaw"] == 0.8
    assert label == "background_unknown"


def test_deployment_thresholds_take_precedence_over_validation_metrics(tmp_path: Path) -> None:
    (tmp_path / "deployment_thresholds.json").write_text(
        json.dumps({"thresholds": {"chainsaw": 0.35, "gunshot": 0.65}})
    )
    (tmp_path / "val_metrics.json").write_text(
        json.dumps(
            {
                "threshold_recommendations": {
                    "chainsaw": {"threshold": 0.8},
                    "gunshot": {"threshold": 0.75},
                }
            }
        )
    )

    thresholds = _load_thresholds(tmp_path)

    assert thresholds == {"chainsaw": 0.35, "gunshot": 0.65}


def test_calibration_rank_prefers_constraint_satisfying_candidate() -> None:
    constrained = {
        "thresholded_metrics": {
            "macro_f1": 0.7,
            "per_class_recall": {
                "chainsaw": 0.6,
                "gunshot": 0.7,
                "vehicle": 0.5,
                "fire_crackle": 0.5,
                "background_unknown": 0.8,
            },
        },
        "background_false_positive_summary": {"thresholded": {"threat_false_positive_rate": 0.1}},
    }
    unconstrained_higher_f1 = {
        "thresholded_metrics": {
            "macro_f1": 0.8,
            "per_class_recall": {
                "chainsaw": 0.6,
                "gunshot": 0.7,
                "vehicle": 0.1,
                "fire_crackle": 0.5,
                "background_unknown": 0.9,
            },
        },
        "background_false_positive_summary": {"thresholded": {"threat_false_positive_rate": 0.1}},
    }

    min_recall = {"chainsaw": 0.55, "gunshot": 0.65, "vehicle": 0.4, "fire_crackle": 0.4}

    assert _candidate_rank(constrained, max_background_fp_rate=0.2, min_recall=min_recall) > _candidate_rank(
        unconstrained_higher_f1,
        max_background_fp_rate=0.2,
        min_recall=min_recall,
    )


def test_calibration_rank_penalizes_background_false_positive_overage() -> None:
    low_background_fp = {
        "thresholded_metrics": {
            "macro_f1": 0.7,
            "per_class_recall": {
                "chainsaw": 0.6,
                "gunshot": 0.7,
                "vehicle": 0.5,
                "fire_crackle": 0.5,
                "background_unknown": 0.8,
            },
        },
        "background_false_positive_summary": {"thresholded": {"threat_false_positive_rate": 0.1}},
    }
    high_background_fp = {
        "thresholded_metrics": {
            "macro_f1": 0.8,
            "per_class_recall": {
                "chainsaw": 0.6,
                "gunshot": 0.7,
                "vehicle": 0.5,
                "fire_crackle": 0.5,
                "background_unknown": 0.8,
            },
        },
        "background_false_positive_summary": {"thresholded": {"threat_false_positive_rate": 0.3}},
    }
    min_recall = {"chainsaw": 0.55, "gunshot": 0.65, "vehicle": 0.4, "fire_crackle": 0.4}

    assert _candidate_rank(low_background_fp, max_background_fp_rate=0.2, min_recall=min_recall) > _candidate_rank(
        high_background_fp,
        max_background_fp_rate=0.2,
        min_recall=min_recall,
    )


def test_error_audit_rows_include_thresholded_predictions_and_review_priority() -> None:
    rows = [
        {
            "path": "/tmp/background.wav",
            "label": "background_unknown",
            "source": "unit",
            "split": "test",
            "duration_seconds": "2.0",
            "license": "test",
            "notes": "background",
        },
        {
            "path": "/tmp/vehicle.wav",
            "label": "vehicle",
            "source": "unit",
            "split": "test",
            "duration_seconds": "2.0",
            "license": "test",
            "notes": "vehicle",
        },
        {
            "path": "/tmp/fire.wav",
            "label": "fire_crackle",
            "source": "unit",
            "split": "test",
            "duration_seconds": "2.0",
            "license": "test",
            "notes": "fire",
        },
    ]
    scores = [
        [0.05, 0.7, 0.1, 0.05, 0.1],
        [0.05, 0.1, 0.25, 0.05, 0.55],
        [0.05, 0.7, 0.1, 0.2, 0.05],
    ]

    audit_rows = build_audit_rows(
        rows,
        scores,
        labels=["chainsaw", "gunshot", "vehicle", "fire_crackle", "background_unknown"],
        thresholds={"chainsaw": 0.5, "gunshot": 0.65, "vehicle": 0.6, "fire_crackle": 0.6, "background_unknown": 0.05},
    )

    assert audit_rows[0]["error_type"] == "background_false_positive"
    assert audit_rows[0]["review_priority"] == "1"
    assert audit_rows[0]["thresholded_predicted_label"] == "gunshot"
    assert audit_rows[1]["error_type"] == "threat_false_negative"
    assert audit_rows[1]["review_priority"] == "2"
    assert audit_rows[1]["thresholded_predicted_label"] == "background_unknown"
    assert audit_rows[2]["error_type"] == "threat_confusion"
    assert audit_rows[2]["review_priority"] == "3"
    assert audit_rows[2]["score_fire_crackle"] == "0.200000"


def test_error_audit_top_confusions_counts_errors_only() -> None:
    rows = [
        {"is_error": "1", "true_label": "background_unknown", "predicted_label": "gunshot", "error_type": "background_false_positive"},
        {"is_error": "1", "true_label": "background_unknown", "predicted_label": "gunshot", "error_type": "background_false_positive"},
        {"is_error": "1", "true_label": "vehicle", "predicted_label": "background_unknown", "error_type": "threat_false_negative"},
        {"is_error": "0", "true_label": "vehicle", "predicted_label": "vehicle", "error_type": "correct"},
    ]

    assert summarize_top_confusions(rows) == [
        {
            "true_label": "background_unknown",
            "predicted_label": "gunshot",
            "error_type": "background_false_positive",
            "count": 2,
        },
        {
            "true_label": "vehicle",
            "predicted_label": "background_unknown",
            "error_type": "threat_false_negative",
            "count": 1,
        },
    ]


def test_review_app_saves_and_merges_decisions(tmp_path: Path) -> None:
    decisions_path = tmp_path / "decisions.csv"

    saved = save_decision(
        decisions_path,
        {
            "audit": "audit.csv",
            "path": "/tmp/clip.wav",
            "true_label": "background_unknown",
            "predicted_label": "gunshot",
            "decision": "relabel",
            "corrected_label": "gun_shot",
            "target_split": "train",
            "reviewer": "unit",
            "review_notes": "sounds like a shot",
        },
    )

    decisions = load_decisions(decisions_path)
    merged = merge_decisions(
        [{"path": "/tmp/clip.wav", "true_label": "background_unknown", "predicted_label": "gunshot"}],
        decisions,
        "audit.csv",
    )

    assert saved["corrected_label"] == "gunshot"
    assert merged[0]["review_decision"] == "relabel"
    assert merged[0]["target_split"] == "train"
    assert merged[0]["review_notes"] == "sounds like a shot"


def test_review_app_filters_rows_by_priority_label_decision_and_query() -> None:
    rows = [
        {
            "path": "/tmp/esc50-gunlike.wav",
            "source": "esc50",
            "true_label": "background_unknown",
            "predicted_label": "gunshot",
            "error_type": "background_false_positive",
            "review_priority": "1",
            "review_decision": "needs_review",
            "split": "val",
            "notes": "metal hit",
        },
        {
            "path": "/tmp/vehicle.wav",
            "source": "canopy",
            "true_label": "vehicle",
            "predicted_label": "background_unknown",
            "error_type": "threat_false_negative",
            "review_priority": "2",
            "review_decision": "accepted",
            "split": "val",
            "notes": "distant engine",
        },
    ]

    filtered = filter_rows(
        rows,
        {
            "review_priority": "1",
            "true_label": "background_unknown",
            "review_decision": "needs_review",
            "q": "gunlike",
        },
    )

    assert filtered == [rows[0]]


def test_review_app_prefers_validation_audits_first() -> None:
    audits = [
        "model_test_error_audit.csv",
        "model_train_error_audit.csv",
        "model_val_error_audit.csv",
        "model_train_full_error_audit.csv",
    ]

    assert sorted(audits, key=_audit_sort_order) == [
        "model_val_error_audit.csv",
        "model_train_full_error_audit.csv",
        "model_train_error_audit.csv",
        "model_test_error_audit.csv",
    ]


def test_kaggle_gunshot_importer_builds_grouped_rows_from_audio_tree(tmp_path: Path) -> None:
    root = tmp_path / "kaggle-gunshot"
    train_dir = root / "train"
    train_dir.mkdir(parents=True)
    (train_dir / "youtubeabc_clip001.wav").write_bytes(b"not-real-audio")
    (train_dir / "youtubeabc_clip002.wav").write_bytes(b"not-real-audio")
    (root / "metadata.csv").write_text("filename,youtube_id,firearm\ntrain/youtubeabc_clip001.wav,yt-abc,pistol\n")

    rows = build_kaggle_gunshot_rows(root)

    assert len(rows) == 2
    assert {row.label for row in rows} == {"gunshot"}
    assert rows[0].source == "kaggle_gunshot"
    assert "kaggle_dataset=emrahaydemr/gunshot-audio-dataset" in rows[0].notes
    assert any("source_recording_id=yt-abc" in row.notes for row in rows)
    assert all(row.split == "train" for row in rows)


def test_kaggle_gunshot_importer_writes_manifest(tmp_path: Path) -> None:
    root = tmp_path / "kaggle-gunshot"
    root.mkdir()
    for index in range(4):
        (root / f"source{index}shot.wav").write_bytes(b"not-real-audio")
    output = tmp_path / "manifest.csv"

    rows = write_kaggle_gunshot_manifest(root, output)

    written = read_manifest(output)
    assert len(rows) == 4
    assert len(written) == 4
    assert {row["label"] for row in written} == {"gunshot"}
    assert {row["split"] for row in written} >= {"train", "val", "test"}


def test_kaggle_vehicle_importer_groups_sequential_vehicle_noise_files(tmp_path: Path) -> None:
    root = tmp_path / "vehicle_type_sound_dataset"
    audio_dir = root / "cutted_files"
    audio_dir.mkdir(parents=True)
    (audio_dir / "VehicleNoise001.wav").write_bytes(b"not-real-audio")
    (audio_dir / "VehicleNoise099.wav").write_bytes(b"not-real-audio")
    (audio_dir / "VehicleNoise101.wav").write_bytes(b"not-real-audio")

    rows = build_kaggle_vehicle_rows(root, group_size=100)

    assert len(rows) == 3
    assert {row.label for row in rows} == {"vehicle"}
    assert {row.source for row in rows} == {"kaggle_vehicle_type"}
    assert "source_recording_id=vehiclenoise_0000" in rows[0].notes
    assert "source_recording_id=vehiclenoise_0001" in rows[2].notes


def test_kaggle_vehicle_importer_writes_manifest(tmp_path: Path) -> None:
    root = tmp_path / "vehicle_type_sound_dataset"
    root.mkdir()
    for index in [1, 101, 201, 301]:
        (root / f"VehicleNoise{index}.wav").write_bytes(b"not-real-audio")
    output = tmp_path / "vehicle_manifest.csv"

    rows = write_kaggle_vehicle_manifest(root, output, group_size=100)

    written = read_manifest(output)
    assert len(rows) == 4
    assert len(written) == 4
    assert {row["label"] for row in written} == {"vehicle"}
    assert {row["split"] for row in written} >= {"train", "val", "test"}


def test_kaggle_fire_importer_builds_rows_from_audio_tree(tmp_path: Path) -> None:
    root = tmp_path / "forest-wildfire"
    fire_dir = root / "train" / "forest_fire"
    fire_dir.mkdir(parents=True)
    (fire_dir / "burning-001.wav").write_bytes(b"not-real-audio")
    (fire_dir / "burning-002.wav").write_bytes(b"not-real-audio")

    rows = build_kaggle_fire_rows(root)

    assert len(rows) == 2
    assert {row.label for row in rows} == {"fire_crackle"}
    assert {row.source for row in rows} == {"kaggle_forest_wildfire"}
    assert all(row.split == "train" for row in rows)
    assert "kaggle_dataset=forestprotection/forest-wild-fire-sound-dataset" in rows[0].notes


def test_kaggle_fire_importer_writes_manifest(tmp_path: Path) -> None:
    root = tmp_path / "forest-wildfire"
    root.mkdir()
    for index in range(4):
        (root / f"fire-{index}.wav").write_bytes(b"not-real-audio")
    output = tmp_path / "fire_manifest.csv"

    rows = write_kaggle_fire_manifest(root, output)

    written = read_manifest(output)
    assert len(rows) == 4
    assert len(written) == 4
    assert {row["label"] for row in written} == {"fire_crackle"}
    assert {row["split"] for row in written} >= {"train", "val", "test"}


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


def test_fsc22_importer_maps_negatives_and_skips_threat_classes(tmp_path: Path) -> None:
    root = tmp_path / "FSC22"
    audio_dir = root / "Audios"
    audio_dir.mkdir(parents=True)
    metadata_path = root / "Metadata" / "Metadata V1.0 FSC22.csv"
    metadata_path.parent.mkdir(parents=True)

    samples = [
        ("17548__A.wav", "1_10101.wav", "1", "Fire"),
        ("99999_A.wav", "2_10201.wav", "2", "BirdChirping"),
        ("88888_A.wav", "3_10301.wav", "3", "VehicleEngine"),
    ]
    with metadata_path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["Source File Name", "Dataset File Name", "Class ID", "Class Name "],
        )
        writer.writeheader()
        for source_name, dataset_name, class_id, class_name in samples:
            writer.writerow(
                {
                    "Source File Name": source_name,
                    "Dataset File Name": dataset_name,
                    "Class ID": class_id,
                    "Class Name ": class_name,
                }
            )
            (audio_dir / dataset_name).write_bytes(b"not-real-audio")

    rows = build_fsc22_rows(root, negatives_only=True, train_only=True)
    labels = {row.label for row in rows}
    assert labels == {"background_unknown", "vehicle"}
    assert all(row.split == "train" for row in rows)
    assert all(row.source == "fsc22" for row in rows)
    assert "fsc22_train_only=true" in rows[0].notes
    assert len(CANOPY_LABEL_FOR_FSC22_CLASS) == 27

    threat_rows = build_fsc22_rows(root, negatives_only=False, train_only=True)
    assert {row.label for row in threat_rows} == {"background_unknown", "vehicle", "fire_crackle"}


def test_fsc22_importer_writes_manifest(tmp_path: Path) -> None:
    root = tmp_path / "FSC22"
    audio_dir = root / "Audios"
    audio_dir.mkdir(parents=True)
    metadata_path = root / "Metadata" / "Metadata V1.0 FSC22.csv"
    metadata_path.parent.mkdir(parents=True)
    with metadata_path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["Source File Name", "Dataset File Name", "Class ID", "Class Name "],
        )
        writer.writeheader()
        writer.writerow(
            {
                "Source File Name": "wind_A.wav",
                "Dataset File Name": "4_10401.wav",
                "Class ID": "4",
                "Class Name ": "Wind",
            }
        )
    (audio_dir / "4_10401.wav").write_bytes(b"not-real-audio")
    output = tmp_path / "fsc22.csv"

    rows = write_fsc22_manifest(root, output, negatives_only=True, train_only=True)
    written = read_manifest(output)

    assert len(rows) == 1
    assert len(written) == 1
    assert written[0]["label"] == "background_unknown"


def test_kaggle_balanced_manifest_keeps_kaggle_rows_train_only_and_caps_vehicle(tmp_path: Path) -> None:
    def write_mini_manifest(path: Path, rows: list[dict[str, str]]) -> None:
        write_manifest(path, rows)

    base_rows = []
    for split in ["train", "val", "test"]:
        audio_file = tmp_path / f"base-{split}.wav"
        audio_file.write_bytes(b"not-real-audio")
        base_rows.append(
            {
                "path": str(audio_file),
                "label": "background_unknown",
                "source": "esc50",
                "split": split,
                "duration_seconds": "",
                "license": "",
                "notes": "",
            }
        )
    base_manifest = tmp_path / "base.csv"
    write_mini_manifest(base_manifest, base_rows)

    def kaggle_manifest(source: str, label: str, count: int) -> Path:
        rows = []
        for index in range(count):
            audio_file = tmp_path / f"{source}-{index}.wav"
            audio_file.write_bytes(b"not-real-audio")
            rows.append(
                {
                    "path": str(audio_file),
                    "label": label,
                    "source": source,
                    "split": "train",
                    "duration_seconds": "",
                    "license": "",
                    "notes": f"source_recording_id={source}-group-{index // 2}; relative_path=cat{index % 2}/clip.wav",
                }
            )
        path = tmp_path / f"{source}.csv"
        write_mini_manifest(path, rows)
        return path

    output = tmp_path / "balanced.csv"
    summary = build_kaggle_balanced_manifest(
        base_manifest=base_manifest,
        kaggle_chainsaw_manifest=kaggle_manifest("kaggle_chainsaw_rainforest", "chainsaw", 6),
        kaggle_gunshot_manifest=kaggle_manifest("kaggle_gunshot", "gunshot", 8),
        kaggle_fire_manifest=kaggle_manifest("kaggle_forest_wildfire", "fire_crackle", 5),
        kaggle_vehicle_manifest=kaggle_manifest("kaggle_vehicle_type", "vehicle", 12),
        output=output,
        chainsaw_target_rows=3,
        gunshot_target_rows=4,
        fire_target_rows=3,
        vehicle_target_rows=5,
        seed=1,
    )

    written = read_manifest(output)
    kaggle_rows = [row for row in written if row["source"].startswith("kaggle_")]
    assert summary["kaggle_vehicle_rows"] == 5
    assert all(row["split"] == "train" for row in kaggle_rows)
    assert "kaggle_balanced_v2=train_only" in kaggle_rows[0]["notes"]
    assert {row["split"] for row in written if row["source"] == "esc50"} == {"train", "val", "test"}


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
