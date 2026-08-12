import os
import sys
import time
from functools import lru_cache
from pathlib import Path
from typing import List

from app.core.config import settings
from app.paths import DATA_DIR

# Короткие имена faster-whisper → репозитории Hugging Face
_WHISPER_REPO_IDS = {
    "tiny": "Systran/faster-whisper-tiny",
    "tiny.en": "Systran/faster-whisper-tiny.en",
    "base": "Systran/faster-whisper-base",
    "base.en": "Systran/faster-whisper-base.en",
    "small": "Systran/faster-whisper-small",
    "small.en": "Systran/faster-whisper-small.en",
    "medium": "Systran/faster-whisper-medium",
    "medium.en": "Systran/faster-whisper-medium.en",
    "large-v1": "Systran/faster-whisper-large-v1",
    "large-v2": "Systran/faster-whisper-large-v2",
    "large-v3": "Systran/faster-whisper-large-v3",
    "large": "Systran/faster-whisper-large-v3",
    "distil-large-v2": "Systran/faster-distil-whisper-large-v2",
    "distil-large-v3": "Systran/faster-distil-whisper-large-v3",
    "distil-medium.en": "Systran/faster-distil-whisper-medium.en",
    "distil-small.en": "Systran/faster-distil-whisper-small.en",
}

_cuda_path_configured = False


def configure_cuda_runtime_path() -> list[str]:
    """Добавляет pip-пакеты CUDA 12 (cuBLAS/cuDNN) в PATH процесса.

    CTranslate2 грузит cublas64_12.dll через LoadLibrary, поэтому
    os.add_dll_directory недостаточно — нужен PATH.
    """
    global _cuda_path_configured
    bin_dirs: list[str] = []

    for pkg_name in ("nvidia.cublas", "nvidia.cudnn", "nvidia.cuda_nvrtc"):
        try:
            mod = __import__(pkg_name, fromlist=["__path__"])
        except ImportError:
            continue

        pkg_dir = next(iter(getattr(mod, "__path__", [])), None)
        if not pkg_dir:
            continue

        candidate = os.path.join(pkg_dir, "bin" if sys.platform == "win32" else "lib")
        if os.path.isdir(candidate):
            bin_dirs.append(candidate)

    if not bin_dirs:
        if not _cuda_path_configured:
            print(
                "--- CUDA pip packages not found. "
                "Install: pip install nvidia-cublas-cu12 nvidia-cudnn-cu12 nvidia-cuda-nvrtc-cu12 ---"
            )
        _cuda_path_configured = True
        return bin_dirs

    if not _cuda_path_configured:
        if sys.platform == "win32":
            os.environ["PATH"] = (
                os.pathsep.join(bin_dirs) + os.pathsep + os.environ.get("PATH", "")
            )
            for directory in bin_dirs:
                os.add_dll_directory(directory)
        else:
            existing = os.environ.get("LD_LIBRARY_PATH", "")
            os.environ["LD_LIBRARY_PATH"] = os.pathsep.join(
                bin_dirs + ([existing] if existing else [])
            )
        print(f"--- CUDA runtime PATH configured ({len(bin_dirs)} dirs) ---")
        for directory in bin_dirs:
            print(f"    {directory}")
        _cuda_path_configured = True

    return bin_dirs


def _resolve_device() -> str:
    if settings.ASR_DEVICE != "auto":
        return settings.ASR_DEVICE
    try:
        import ctranslate2

        return "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
    except Exception:
        return "cpu"


def _resolve_compute_type(device: str) -> str:
    if settings.ASR_COMPUTE_TYPE != "auto":
        return settings.ASR_COMPUTE_TYPE
    return "float16" if device == "cuda" else "int8"


def _download_root() -> Path:
    root = (
        Path(settings.ASR_DOWNLOAD_ROOT)
        if settings.ASR_DOWNLOAD_ROOT
        else (DATA_DIR / "whisper_models")
    )
    root.mkdir(parents=True, exist_ok=True)
    return root


def _resolve_repo_id(model_name: str) -> str:
    if "/" in model_name:
        return model_name
    return _WHISPER_REPO_IDS.get(model_name, f"Systran/faster-whisper-{model_name}")


def _ensure_model_files(model_name: str, retries: int = 5) -> str:
    """Скачивает веса Whisper с Hugging Face (с докачкой) и возвращает локальный путь."""
    from huggingface_hub import snapshot_download

    repo_id = _resolve_repo_id(model_name)
    local_dir = _download_root() / repo_id.replace("/", "--")
    last_error: Exception | None = None

    # Уже есть локальные файлы — не ходим в сеть без нужды
    if (local_dir / "model.bin").exists() or (local_dir / "model.safetensors").exists():
        print(f"--- Whisper model already on disk: {local_dir} ---")
        return str(local_dir)

    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "300")

    for attempt in range(1, retries + 1):
        try:
            print(
                f"--- Downloading Whisper '{repo_id}' "
                f"(attempt {attempt}/{retries}) → {local_dir} ---"
            )
            path = snapshot_download(
                repo_id=repo_id,
                local_dir=str(local_dir),
            )
            print(f"--- Whisper download complete: {path} ---")
            return path
        except Exception as e:
            last_error = e
            print(f"!!! Whisper download failed (attempt {attempt}/{retries}): {e}")
            if attempt < retries:
                wait_s = min(2**attempt, 30)
                print(f"--- Retrying in {wait_s}s ---")
                time.sleep(wait_s)

    raise RuntimeError(
        f"Failed to download Whisper model '{repo_id}' after {retries} attempts. "
        "Check internet access to huggingface.co (or set a working proxy), "
        "then restart the server."
    ) from last_error


def _warmup_model(model) -> None:
    """Прогоняет короткий инференс, чтобы cuBLAS подгрузился при старте."""
    import numpy as np

    audio = np.zeros(16000, dtype=np.float32)
    segments, _info = model.transcribe(
        audio,
        language="en",
        vad_filter=False,
        beam_size=1,
    )
    list(segments)


def _load_whisper_model(device: str, compute_type: str, model_path: str):
    from faster_whisper import WhisperModel

    print(
        f"--- Loading Whisper from '{model_path}' " f"on {device} ({compute_type}) ---"
    )
    model = WhisperModel(
        model_path,
        device=device,
        compute_type=compute_type,
        local_files_only=True,
    )
    _warmup_model(model)
    return model


@lru_cache(maxsize=1)
def _get_whisper_model():
    configure_cuda_runtime_path()
    requested = _resolve_device()
    model_path = _ensure_model_files(settings.WHISPER_MODEL)

    if requested == "cuda":
        try:
            model = _load_whisper_model(
                "cuda", _resolve_compute_type("cuda"), model_path
            )
            print("--- Whisper GPU warmup OK ---")
            return model
        except Exception as e:
            print(f"!!! Whisper CUDA failed: {e}")
            print("--- Falling back to CPU (int8). GPU will not be used. ---")

    model = _load_whisper_model("cpu", "int8", model_path)
    print("--- Whisper CPU warmup OK ---")
    return model


def preload_whisper_model() -> None:
    """Скачивает и загружает модель при старте сервера, с проверкой GPU."""
    print("--- Preloading Whisper ASR model at startup ---")
    configure_cuda_runtime_path()
    _get_whisper_model()
    print("--- Whisper ASR model ready ---")


class LocalTranscriber:
    """Локальное распознавание речи через faster-whisper (GPU при наличии CUDA)."""

    def transcribe_files(self, audio_paths: List[str]) -> List[str]:
        transcriptions: List[str] = []
        model = _get_whisper_model()

        for path in audio_paths:
            if not path or not os.path.exists(path):
                transcriptions.append("")
                continue

            segments, _info = model.transcribe(
                path,
                language="en",
                beam_size=5,
                vad_filter=True,
            )
            text = " ".join(segment.text.strip() for segment in segments).strip()
            transcriptions.append(text)
            print(f"[ASR] {os.path.basename(path)} -> {text!r}")

        return transcriptions
