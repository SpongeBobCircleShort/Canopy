from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")

from research.audio.model import build_model, model_config_from_checkpoint


def test_se_attention_cnn_forward_shape() -> None:
    model = build_model(5, {"architecture": "se_attention_cnn", "dropout": 0.2})
    output = model(torch.randn(4, 1, 64, 200))
    assert output.shape == (4, 5)


def test_se_attention_cnn_accepts_config_overrides() -> None:
    model = build_model(
        3,
        {
            "architecture": "se_cnn",
            "se_channels": [8, 16],
            "se_reduction": 4,
            "attention_hidden": 16,
        },
    )
    output = model(torch.randn(2, 1, 64, 100))
    assert output.shape == (2, 3)


def test_se_attention_cnn_handles_variable_time_length() -> None:
    # Attention pooling must work over arbitrary time-frame counts, unlike a
    # fixed-size linear classifier would.
    model = build_model(4, {"architecture": "attention_cnn"})
    short = model(torch.randn(1, 1, 64, 50))
    long = model(torch.randn(1, 1, 64, 400))
    assert short.shape == (1, 4)
    assert long.shape == (1, 4)


def test_checkpoint_architecture_inferred_as_se_attention_cnn() -> None:
    model = build_model(5, {"architecture": "se_attention_cnn"})
    fake_state_dict = dict.fromkeys(model.state_dict().keys())
    inferred = model_config_from_checkpoint({"state_dict": fake_state_dict})
    assert inferred["architecture"] == "se_attention_cnn"


def test_unsupported_architecture_raises() -> None:
    with pytest.raises(ValueError):
        build_model(5, {"architecture": "not_a_real_architecture"})