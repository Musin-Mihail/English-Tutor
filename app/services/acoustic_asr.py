import os
from functools import lru_cache
from typing import List, Optional, Tuple

import numpy as np
import soundfile as sf

from app.core.config import settings
from app.paths import WAV2VEC2_DIR

_TARGET_SR = 16000


def _resolve_device() -> str:
    requested = (settings.ACOUSTIC_ASR_DEVICE or "auto").lower()
    if requested != "auto":
        return requested
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def _load_mono_16k(path: str) -> np.ndarray:
    audio, sr = sf.read(path, dtype="float32", always_2d=False)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    audio = np.asarray(audio, dtype=np.float32)
    if sr == _TARGET_SR:
        return audio
    if len(audio) == 0 or sr <= 0:
        return np.zeros(0, dtype=np.float32)
    n_out = int(round(len(audio) * _TARGET_SR / sr))
    if n_out <= 0:
        return np.zeros(0, dtype=np.float32)
    x_old = np.linspace(0.0, 1.0, num=len(audio), endpoint=False)
    x_new = np.linspace(0.0, 1.0, num=n_out, endpoint=False)
    return np.interp(x_new, x_old, audio).astype(np.float32)


def _load_model(device: str) -> Tuple[object, object, str]:
    import torch
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

    WAV2VEC2_DIR.mkdir(parents=True, exist_ok=True)
    model_id = settings.ACOUSTIC_ASR_MODEL
    cache_dir = str(WAV2VEC2_DIR)
    print(f"--- Loading acoustic ASR '{model_id}' on {device} ---")
    processor = Wav2Vec2Processor.from_pretrained(model_id, cache_dir=cache_dir)
    model = Wav2Vec2ForCTC.from_pretrained(model_id, cache_dir=cache_dir)
    model.to(device)
    model.eval()
    return processor, model, device


@lru_cache(maxsize=1)
def _get_acoustic_model():
    requested = _resolve_device()
    if requested == "cuda":
        try:
            return _load_model("cuda")
        except Exception as e:
            print(f"!!! Acoustic ASR CUDA failed: {e}")
            print("--- Falling back to CPU for wav2vec2 ---")
    return _load_model("cpu")


def preload_acoustic_asr() -> None:
    if not settings.ACOUSTIC_ASR:
        return
    print("--- Preloading acoustic ASR (wav2vec2) ---")
    _get_acoustic_model()
    print("--- Acoustic ASR ready ---")


class AcousticTranscriber:
    """CTC-расшифровка без сильного языкового модели — ближе к тому, что сказано."""

    def transcribe_files(self, audio_paths: List[str]) -> List[str]:
        if not settings.ACOUSTIC_ASR:
            return [""] * len(audio_paths)

        import torch

        processor, model, device = _get_acoustic_model()
        texts: List[str] = []

        for path in audio_paths:
            text = self._transcribe_one(path, processor, model, device, torch)
            texts.append(text)
            if path:
                print(f"[AcousticASR] {os.path.basename(path)} -> {text!r}")

        return texts

    def _transcribe_one(
        self,
        path: Optional[str],
        processor,
        model,
        device: str,
        torch_mod,
    ) -> str:
        if not path or not os.path.exists(path):
            return ""
        try:
            audio = _load_mono_16k(path)
            if audio.size == 0:
                return ""
            inputs = processor(
                audio,
                sampling_rate=_TARGET_SR,
                return_tensors="pt",
                padding=True,
            )
            input_values = inputs.input_values.to(device)
            attention_mask = None
            if getattr(inputs, "attention_mask", None) is not None:
                attention_mask = inputs.attention_mask.to(device)
            with torch_mod.no_grad():
                if attention_mask is not None:
                    logits = model(input_values, attention_mask=attention_mask).logits
                else:
                    logits = model(input_values).logits
            pred_ids = torch_mod.argmax(logits, dim=-1)
            text = processor.batch_decode(pred_ids)[0]
            return " ".join(text.lower().split())
        except Exception as e:
            print(f"!!! Acoustic ASR failed for {path}: {e}")
            return ""
