from __future__ import annotations

from pathlib import Path


def load_and_preprocess_audio(path: str | Path, *, sample_rate: int, clip_seconds: float, crop_mode: str = "start"):
    torch, torchaudio = _torch_modules()
    try:
        waveform, source_rate = torchaudio.load(str(path))
    except RuntimeError:
        waveform, source_rate = _load_audio_fallback(path, torch)
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)
    if source_rate != sample_rate:
        waveform = torchaudio.functional.resample(waveform, source_rate, sample_rate)
    target_frames = int(sample_rate * clip_seconds)
    current_frames = waveform.shape[1]
    if current_frames < target_frames:
        waveform = torch.nn.functional.pad(waveform, (0, target_frames - current_frames))
    elif current_frames > target_frames:
        max_start = current_frames - target_frames
        if crop_mode == "random":
            start = int(torch.randint(0, max_start + 1, (1,)).item())
        elif crop_mode == "center":
            start = max_start // 2
        else:
            start = 0
        waveform = waveform[:, start : start + target_frames]
    return waveform


def augment_waveform(
    waveform,
    *,
    sample_rate: int,
    gain_min: float = 0.85,
    gain_max: float = 1.15,
    noise_std: float = 0.003,
    max_shift_fraction: float = 0.08,
    pitch_shift_semitones: float = 0.0,
    background_mix_waveform=None,
    background_snr_db_min: float = 5.0,
    background_snr_db_max: float = 20.0,
):
    torch, torchaudio = _torch_modules()
    if gain_max > 0 and gain_min > 0:
        gain = torch.empty(1).uniform_(gain_min, gain_max).item()
        waveform = waveform * gain
    if max_shift_fraction > 0:
        max_shift = int(waveform.shape[1] * max_shift_fraction)
        if max_shift > 0:
            shift = int(torch.randint(-max_shift, max_shift + 1, (1,)).item())
            waveform = torch.roll(waveform, shifts=shift, dims=1)
    if noise_std > 0:
        waveform = waveform + torch.randn_like(waveform) * noise_std
    if pitch_shift_semitones > 0:
        steps = torch.empty(1).uniform_(-pitch_shift_semitones, pitch_shift_semitones).item()
        waveform = torchaudio.functional.pitch_shift(waveform, sample_rate, steps)
    if background_mix_waveform is not None:
        signal_rms = waveform.pow(2).mean().sqrt().clamp_min(1e-9)
        snr_db = torch.empty(1).uniform_(background_snr_db_min, background_snr_db_max).item()
        snr_linear = 10 ** (snr_db / 20.0)
        bg = background_mix_waveform
        bg_rms = bg.pow(2).mean().sqrt().clamp_min(1e-9)
        bg_scaled = bg * (signal_rms / (bg_rms * snr_linear))
        if bg_scaled.shape[1] < waveform.shape[1]:
            repeats = (waveform.shape[1] // bg_scaled.shape[1]) + 1
            bg_scaled = bg_scaled.repeat(1, repeats)
        waveform = waveform + bg_scaled[:, :waveform.shape[1]]
    return waveform.clamp(-1.0, 1.0)


def waveform_to_log_mel(waveform, *, sample_rate: int, n_mels: int):
    torch, torchaudio = _torch_modules()
    transform = torchaudio.transforms.MelSpectrogram(
        sample_rate=sample_rate,
        n_fft=1024,
        hop_length=320,
        n_mels=n_mels,
        power=2.0,
    )
    mel = transform(waveform)
    log_mel = torch.log(mel + 1e-6)
    mean = log_mel.mean()
    std = log_mel.std().clamp_min(1e-6)
    return (log_mel - mean) / std


def apply_spec_augment(log_mel, *, max_time_mask_frames: int = 12, max_freq_mask_bins: int = 8):
    torch, _ = _torch_modules()
    augmented = log_mel.clone()
    if max_freq_mask_bins > 0 and augmented.shape[1] > 1:
        width = int(torch.randint(0, min(max_freq_mask_bins, augmented.shape[1]) + 1, (1,)).item())
        if width > 0:
            start = int(torch.randint(0, augmented.shape[1] - width + 1, (1,)).item())
            augmented[:, start : start + width, :] = 0
    if max_time_mask_frames > 0 and augmented.shape[2] > 1:
        width = int(torch.randint(0, min(max_time_mask_frames, augmented.shape[2]) + 1, (1,)).item())
        if width > 0:
            start = int(torch.randint(0, augmented.shape[2] - width + 1, (1,)).item())
            augmented[:, :, start : start + width] = 0
    return augmented


def load_log_mel(
    path: str | Path,
    *,
    sample_rate: int,
    clip_seconds: float,
    n_mels: int,
    augment: bool = False,
    augmentation: dict | None = None,
    background_waveforms: list | None = None,
    crop_mode: str = "center",
):
    torch, _ = _torch_modules()
    waveform = load_and_preprocess_audio(path, sample_rate=sample_rate, clip_seconds=clip_seconds, crop_mode=crop_mode)
    augmentation = augmentation or {}
    if augment:
        bg_waveform = None
        if background_waveforms and float(augmentation.get("background_mix_prob", 0.0)) > 0:
            if torch.rand(1).item() < float(augmentation.get("background_mix_prob", 0.0)):
                import random
                bg_waveform = random.choice(background_waveforms)
        waveform = augment_waveform(
            waveform,
            sample_rate=sample_rate,
            gain_min=float(augmentation.get("gain_min", 0.85)),
            gain_max=float(augmentation.get("gain_max", 1.15)),
            noise_std=float(augmentation.get("noise_std", 0.003)),
            max_shift_fraction=float(augmentation.get("max_shift_fraction", 0.08)),
            pitch_shift_semitones=float(augmentation.get("pitch_shift_semitones", 0.0)),
            background_mix_waveform=bg_waveform,
            background_snr_db_min=float(augmentation.get("background_snr_db_min", 5.0)),
            background_snr_db_max=float(augmentation.get("background_snr_db_max", 20.0)),
        )
    log_mel = waveform_to_log_mel(waveform, sample_rate=sample_rate, n_mels=n_mels)
    if augment:
        log_mel = apply_spec_augment(
            log_mel,
            max_time_mask_frames=int(augmentation.get("max_time_mask_frames", 12)),
            max_freq_mask_bins=int(augmentation.get("max_freq_mask_bins", 8)),
        )
    return log_mel


def load_waveform_feature(
    path: str | Path,
    *,
    sample_rate: int,
    clip_seconds: float,
    augment: bool = False,
    augmentation: dict | None = None,
    background_waveforms: list | None = None,
    crop_mode: str = "center",
):
    torch, _ = _torch_modules()
    waveform = load_and_preprocess_audio(path, sample_rate=sample_rate, clip_seconds=clip_seconds, crop_mode=crop_mode)
    augmentation = augmentation or {}
    if augment:
        bg_waveform = None
        if background_waveforms and float(augmentation.get("background_mix_prob", 0.0)) > 0:
            if torch.rand(1).item() < float(augmentation.get("background_mix_prob", 0.0)):
                import random

                bg_waveform = random.choice(background_waveforms)
        waveform = augment_waveform(
            waveform,
            sample_rate=sample_rate,
            gain_min=float(augmentation.get("gain_min", 0.85)),
            gain_max=float(augmentation.get("gain_max", 1.15)),
            noise_std=float(augmentation.get("noise_std", 0.003)),
            max_shift_fraction=float(augmentation.get("max_shift_fraction", 0.08)),
            pitch_shift_semitones=float(augmentation.get("pitch_shift_semitones", 0.0)),
            background_mix_waveform=bg_waveform,
            background_snr_db_min=float(augmentation.get("background_snr_db_min", 5.0)),
            background_snr_db_max=float(augmentation.get("background_snr_db_max", 20.0)),
        )
    return waveform


def _torch_modules():
    try:
        import torch
        import torchaudio
    except (ImportError, OSError) as exc:
        raise RuntimeError(
            "Install matching torch/torchaudio builds from research/audio/requirements-audio.txt. "
            "If torchaudio fails with a missing symbol, torch and torchaudio are binary-incompatible "
            "in the active Python environment."
        ) from exc
    return torch, torchaudio


def _load_audio_fallback(path: str | Path, torch):
    soundfile_error: Exception | None = None
    try:
        return _load_with_soundfile(path, torch)
    except (ImportError, RuntimeError) as exc:
        soundfile_error = exc
    try:
        return _load_wav_with_scipy(path, torch)
    except RuntimeError as exc:
        if soundfile_error is not None:
            raise RuntimeError(
                f"Could not decode audio file {path}. Install soundfile/libsndfile to decode non-PCM WAV files "
                "such as ADPCM UrbanSound8K clips."
            ) from exc
        raise


def _load_with_soundfile(path: str | Path, torch):
    try:
        import soundfile as sf
    except ImportError as exc:
        raise ImportError("soundfile is not installed") from exc

    data, sample_rate = sf.read(str(path), always_2d=True, dtype="float32")
    tensor = torch.as_tensor(data).transpose(0, 1).contiguous()
    return tensor, sample_rate


def _load_wav_with_scipy(path: str | Path, torch):
    try:
        from scipy.io import wavfile
    except ImportError as exc:
        raise RuntimeError("Install scipy or a torchaudio backend that can decode WAV files") from exc

    try:
        sample_rate, data = wavfile.read(str(path))
    except ValueError as exc:
        raise RuntimeError("scipy can only decode PCM/float WAV files; install soundfile for this audio format") from exc
    tensor = torch.as_tensor(data)
    if tensor.ndim == 1:
        tensor = tensor.unsqueeze(0)
    else:
        tensor = tensor.transpose(0, 1)
    if tensor.dtype.is_floating_point:
        waveform = tensor.float()
    else:
        info = torch.iinfo(tensor.dtype)
        scale = max(abs(info.min), info.max)
        waveform = tensor.float() / scale
    return waveform, sample_rate
