from __future__ import annotations


def build_model(num_labels: int, model_config: dict | None = None):
    torch = _torch()
    model_config = model_config or {}
    architecture = str(model_config.get("architecture", "cnn")).lower()
    dropout = float(model_config.get("dropout", 0.0))

    if architecture in {"cnn", "threat_cnn"}:
        return _build_cnn(torch, num_labels, dropout=dropout)
    if architecture in {"resnet18", "resnet"}:
        return _build_resnet18(torch, num_labels, dropout=dropout)
    if architecture in {"wav2vec2_frozen", "wav2vec2"}:
        return _build_wav2vec2_frozen(torch, num_labels, model_config=model_config, dropout=dropout)
    if architecture in {"se_attention_cnn", "se_cnn", "attention_cnn"}:
        return _build_se_attention_cnn(torch, num_labels, model_config=model_config, dropout=dropout)
    raise ValueError(f"Unsupported audio model architecture: {architecture}")


def model_config_from_checkpoint(checkpoint: dict, fallback_config: dict | None = None) -> dict:
    artifact_config = checkpoint.get("artifact", {}).get("model")
    if artifact_config:
        return artifact_config
    fallback_config = fallback_config or {}
    state_dict = checkpoint.get("state_dict", {})
    if any(key.startswith("encoder.") for key in state_dict):
        return fallback_config or {"architecture": "wav2vec2_frozen", "input": "waveform"}
    if any(key.startswith("attention_pool.") for key in state_dict):
        dropout = float(fallback_config.get("dropout", 0.0)) if "classifier.0.weight" in state_dict else 0.0
        return {"architecture": "se_attention_cnn", "dropout": dropout}
    if any(key.startswith("features.") or key.startswith("classifier.") for key in state_dict):
        dropout = float(fallback_config.get("dropout", 0.0)) if "classifier.0.weight" in state_dict else 0.0
        return {"architecture": "cnn", "dropout": dropout}
    if any(key.startswith("resnet.") for key in state_dict):
        dropout = float(fallback_config.get("dropout", 0.0)) if "resnet.fc.1.weight" in state_dict else 0.0
        return {"architecture": "resnet18", "dropout": dropout}
    return fallback_config


def _build_cnn(torch, num_labels: int, *, dropout: float):
    class ThreatAudioCNN(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.features = torch.nn.Sequential(
                torch.nn.Conv2d(1, 16, kernel_size=3, padding=1),
                torch.nn.BatchNorm2d(16),
                torch.nn.ReLU(),
                torch.nn.MaxPool2d(2),
                torch.nn.Conv2d(16, 32, kernel_size=3, padding=1),
                torch.nn.BatchNorm2d(32),
                torch.nn.ReLU(),
                torch.nn.MaxPool2d(2),
                torch.nn.Conv2d(32, 64, kernel_size=3, padding=1),
                torch.nn.BatchNorm2d(64),
                torch.nn.ReLU(),
                torch.nn.AdaptiveAvgPool2d((1, 1)),
            )
            if dropout > 0:
                self.classifier = torch.nn.Sequential(
                    torch.nn.Dropout(dropout),
                    torch.nn.Linear(64, num_labels),
                )
            else:
                self.classifier = torch.nn.Linear(64, num_labels)

        def forward(self, inputs):
            features = self.features(inputs)
            return self.classifier(features.flatten(1))

    return ThreatAudioCNN()


def _build_se_attention_cnn(torch, num_labels: int, *, model_config: dict, dropout: float):
    """CNN with squeeze-and-excitation channel recalibration and learned
    attention pooling over time-frequency frames, in place of the plain
    conv-stack + global-average-pool used by ``_build_cnn``.

    Motivation (see research/audio/MODEL_STATUS.md, 2026-07-07 entry): the
    plain CNN's pre-classifier embedding does not separate threat sounds
    from background across held-out sites (score AUC ~ chance), while a
    frozen general-purpose CNN with SE blocks (PANNs/CNN14) does. SE blocks
    let the network recalibrate which channels matter per-input rather than
    always averaging every channel/frame equally, and attention pooling lets
    it learn to weight the specific time-frequency region carrying the
    threat signature instead of diluting it across the whole clip (e.g. a
    long clip where the chainsaw is audible for only a few seconds).
    """
    channels = model_config.get("se_channels", [16, 32, 64])
    se_reduction = int(model_config.get("se_reduction", 8))
    attention_hidden = int(model_config.get("attention_hidden", 32))

    class SqueezeExcite(torch.nn.Module):
        def __init__(self, num_channels: int, reduction: int) -> None:
            super().__init__()
            hidden = max(num_channels // reduction, 4)
            self.pool = torch.nn.AdaptiveAvgPool2d(1)
            self.fc = torch.nn.Sequential(
                torch.nn.Linear(num_channels, hidden),
                torch.nn.ReLU(),
                torch.nn.Linear(hidden, num_channels),
                torch.nn.Sigmoid(),
            )

        def forward(self, inputs):
            batch, channels, _, _ = inputs.shape
            weights = self.pool(inputs).view(batch, channels)
            weights = self.fc(weights).view(batch, channels, 1, 1)
            return inputs * weights

    class SEConvBlock(torch.nn.Module):
        def __init__(self, in_channels: int, out_channels: int, reduction: int) -> None:
            super().__init__()
            self.conv = torch.nn.Sequential(
                torch.nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1),
                torch.nn.BatchNorm2d(out_channels),
                torch.nn.ReLU(),
            )
            self.se = SqueezeExcite(out_channels, reduction)
            self.pool = torch.nn.MaxPool2d(2)

        def forward(self, inputs):
            return self.pool(self.se(self.conv(inputs)))

    class AttentionPool2d(torch.nn.Module):
        """Learned attention over the flattened time-frequency grid, replacing
        AdaptiveAvgPool2d((1, 1)). Produces a single embedding per clip that
        is a weighted sum of frame features rather than a uniform average."""

        def __init__(self, in_channels: int, hidden: int) -> None:
            super().__init__()
            self.score = torch.nn.Sequential(
                torch.nn.Linear(in_channels, hidden),
                torch.nn.Tanh(),
                torch.nn.Linear(hidden, 1),
            )

        def forward(self, inputs):
            batch, channels, freq, time = inputs.shape
            frames = inputs.view(batch, channels, freq * time).transpose(1, 2)  # (B, F*T, C)
            weights = torch.softmax(self.score(frames), dim=1)  # (B, F*T, 1)
            pooled = (frames * weights).sum(dim=1)  # (B, C)
            return pooled

    class SEAttentionAudioCNN(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            in_channels = 1
            blocks = []
            for out_channels in channels:
                blocks.append(SEConvBlock(in_channels, out_channels, se_reduction))
                in_channels = out_channels
            self.features = torch.nn.Sequential(*blocks)
            self.attention_pool = AttentionPool2d(in_channels, attention_hidden)
            if dropout > 0:
                self.classifier = torch.nn.Sequential(
                    torch.nn.Dropout(dropout),
                    torch.nn.Linear(in_channels, num_labels),
                )
            else:
                self.classifier = torch.nn.Linear(in_channels, num_labels)

        def forward(self, inputs):
            features = self.features(inputs)
            pooled = self.attention_pool(features)
            return self.classifier(pooled)

    return SEAttentionAudioCNN()


def _build_resnet18(torch, num_labels: int, *, dropout: float):
    import torchvision

    class ThreatAudioResNet(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.resnet = torchvision.models.resnet18(weights="DEFAULT")
            original_conv1 = self.resnet.conv1
            self.resnet.conv1 = torch.nn.Conv2d(
                1, 64, kernel_size=(7, 7), stride=(2, 2), padding=(3, 3), bias=False
            )
            with torch.no_grad():
                self.resnet.conv1.weight[:] = original_conv1.weight.sum(dim=1, keepdim=True)
            in_features = self.resnet.fc.in_features
            if dropout > 0:
                self.resnet.fc = torch.nn.Sequential(
                    torch.nn.Dropout(dropout),
                    torch.nn.Linear(in_features, num_labels),
                )
            else:
                self.resnet.fc = torch.nn.Linear(in_features, num_labels)

        def forward(self, inputs):
            return self.resnet(inputs)

    return ThreatAudioResNet()


def _build_wav2vec2_frozen(torch, num_labels: int, *, model_config: dict, dropout: float):
    try:
        import torchaudio
    except (ImportError, OSError) as exc:
        raise RuntimeError(
            "Install matching torch/torchaudio builds before using wav2vec2_frozen. "
            "The active environment has a torchaudio binary that cannot load against the installed torch."
        ) from exc

    bundle_name = str(model_config.get("bundle", "WAV2VEC2_BASE"))
    bundle = getattr(torchaudio.pipelines, bundle_name)

    class FrozenWav2Vec2Classifier(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.encoder = bundle.get_model()
            for parameter in self.encoder.parameters():
                parameter.requires_grad = False
            embedding_dim = int(model_config.get("embedding_dim", 768))
            hidden_dim = int(model_config.get("hidden_dim", 256))
            self.classifier = torch.nn.Sequential(
                torch.nn.LayerNorm(embedding_dim),
                torch.nn.Dropout(dropout),
                torch.nn.Linear(embedding_dim, hidden_dim),
                torch.nn.ReLU(),
                torch.nn.Dropout(dropout),
                torch.nn.Linear(hidden_dim, num_labels),
            )

        def forward(self, inputs):
            waveforms = inputs.squeeze(1) if inputs.ndim == 3 else inputs
            with torch.no_grad():
                features, _ = self.encoder.extract_features(waveforms)
            embeddings = features[-1].mean(dim=1)
            return self.classifier(embeddings)

    return FrozenWav2Vec2Classifier()


def _torch():
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("Install research/audio/requirements-audio.txt to use audio model code") from exc
    return torch