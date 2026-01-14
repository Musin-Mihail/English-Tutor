import os
import uvicorn

# --- НАЧАЛО ВСТАВКИ ---
# Принудительно направляем Python через твой Hiddify (порт 12334 из скриншота)
PROXY_URL = "http://127.0.0.1:12334"

os.environ["http_proxy"] = PROXY_URL
os.environ["https_proxy"] = PROXY_URL
os.environ["GRPC_PROXY_EXP"] = PROXY_URL
# --- КОНЕЦ ВСТАВКИ ---

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app", host="0.0.0.0", port=8000, reload=True, log_level="info"
    )
