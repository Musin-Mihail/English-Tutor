import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

# Hugging Face: длинный таймаут для больших моделей (large-v3 ~3 ГБ)
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "300")

PROXY_URL = os.getenv("PROXY_URL")
AI_PROVIDER = (os.getenv("AI_PROVIDER") or "cursor").lower()

if PROXY_URL:
    print(f"--- Applying Proxy Settings: {PROXY_URL} ---")
    os.environ["http_proxy"] = PROXY_URL
    os.environ["https_proxy"] = PROXY_URL
    os.environ["GRPC_PROXY_EXP"] = PROXY_URL

    # Локальные адреса + Hugging Face (скачивание Whisper не должно ломаться прокси)
    no_proxy_hosts = [
        "localhost",
        "127.0.0.1",
        "::1",
        "huggingface.co",
        "hf.co",
        "cdn-lfs.huggingface.co",
    ]
    existing = os.environ.get("no_proxy") or os.environ.get("NO_PROXY") or ""
    merged = ",".join(
        h
        for h in (
            [*existing.split(","), *no_proxy_hosts] if existing else no_proxy_hosts
        )
        if h.strip()
    )
    os.environ["no_proxy"] = merged
    os.environ["NO_PROXY"] = merged
else:
    print("--- No Proxy Settings found, running directly ---")

if __name__ == "__main__":
    from app.core.config import settings
    from app.services.asr import configure_cuda_runtime_path

    # PATH к cublas64_12.dll нужно выставить до первого CUDA-инференса
    configure_cuda_runtime_path()

    if settings.AI_PROVIDER == "cursor" and settings.ASR_PRELOAD:
        from app.services.asr import preload_whisper_model

        try:
            preload_whisper_model()
        except Exception as e:
            print(f"!!! FATAL: Whisper preload failed: {e}")
            print(
                "Сервер не запущен. Проверьте доступ к huggingface.co "
                "и CUDA-библиотеки (nvidia-cublas-cu12), затем перезапустите."
            )
            sys.exit(1)

    from app.ui import build_ui

    demo = build_ui()
    demo.launch(server_name="0.0.0.0", server_port=8000)
