import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")
PROXY_URL = os.getenv("PROXY_URL")
if PROXY_URL:
    print(f"--- Applying Proxy Settings: {PROXY_URL} ---")
    os.environ["http_proxy"] = PROXY_URL
    os.environ["https_proxy"] = PROXY_URL
    os.environ["GRPC_PROXY_EXP"] = PROXY_URL

    # Исключаем локальные адреса из проксирования.
    # Это решит проблему ERR_CONTENT_LENGTH_MISMATCH и обрыва связи при передаче медиафайлов.
    os.environ["no_proxy"] = "localhost,127.0.0.1,::1"
else:
    print("--- No Proxy Settings found, running directly ---")

if __name__ == "__main__":
    from app.ui import build_ui

    demo = build_ui()
    demo.launch(server_name="0.0.0.0", server_port=8000)
