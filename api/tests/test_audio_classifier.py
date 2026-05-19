import os
from pathlib import Path

from app.config import get_settings
from app.services import audio_classifier
from app.services.audio_classifier import ClassificationResult, choose_thresholded_label, classify_clip


def setup_function() -> None:
    get_settings.cache_clear()
    audio_classifier._get_local_model_classifier.cache_clear()
    os.environ.pop("AUDIO_CLASSIFIER_BACKEND", None)
    os.environ.pop("AUDIO_MODEL_DIR", None)


def test_placeholder_backend_remains_default() -> None:
    result = classify_clip(Path("chainsaw-demo.wav"))

    assert result.label == "chainsaw"
    assert result.confidence == 0.82
    assert result.model_version == "placeholder-v0"


def test_local_model_backend_uses_configured_classifier(monkeypatch) -> None:
    class FakeClassifier:
        def classify(self, file_path: Path) -> ClassificationResult:
            assert file_path == Path("clip.wav")
            return ClassificationResult(label="gunshot", confidence=0.91, model_version="fake-local")

    os.environ["AUDIO_CLASSIFIER_BACKEND"] = "local_model"
    os.environ["AUDIO_MODEL_DIR"] = "/tmp/fake-audio-model"
    get_settings.cache_clear()
    monkeypatch.setattr(audio_classifier, "_get_local_model_classifier", lambda model_dir: FakeClassifier())

    result = classify_clip(Path("clip.wav"))

    assert result.label == "gunshot"
    assert result.confidence == 0.91
    assert result.model_version == "fake-local"


def test_threshold_decision_suppresses_low_confidence_threat() -> None:
    label, confidence = choose_thresholded_label(
        scores={
            "chainsaw": 0.31,
            "gunshot": 0.44,
            "vehicle": 0.18,
            "fire_crackle": 0.03,
            "background_unknown": 0.04,
        },
        thresholds={
            "chainsaw": 0.4,
            "gunshot": 0.95,
            "vehicle": 0.7,
            "fire_crackle": 0.15,
            "background_unknown": 0.2,
        },
    )

    assert label == "background_unknown"
    assert confidence == 0.44


def test_threshold_decision_uses_highest_passing_class() -> None:
    label, confidence = choose_thresholded_label(
        scores={
            "chainsaw": 0.41,
            "gunshot": 0.72,
            "vehicle": 0.76,
            "fire_crackle": 0.01,
            "background_unknown": 0.2,
        },
        thresholds={
            "chainsaw": 0.4,
            "gunshot": 0.95,
            "vehicle": 0.7,
            "fire_crackle": 0.15,
            "background_unknown": 0.2,
        },
    )

    assert label == "vehicle"
    assert confidence == 0.76
