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
    raise ValueError(f"Unsupported audio model architecture: {architecture}")


def model_config_from_checkpoint(checkpoint: dict, fallback_config: dict | None = None) -> dict:
    artifact_config = checkpoint.get("artifact", {}).get("model")
    if artifact_config:
        return artifact_config
    fallback_config = fallback_config or {}
    state_dict = checkpoint.get("state_dict", {})
    if any(key.startswith("encoder.") for key in state_dict):
        return fallback_config or {"architecture": "wav2vec2_frozen", "input": "waveform"}
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
