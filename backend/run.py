import os
import uvicorn
from dotenv import load_dotenv

load_dotenv()
PROXY_URL = os.getenv("PROXY_URL")
if PROXY_URL:
    print(f"--- Applying Proxy Settings: {PROXY_URL} ---")
    os.environ["http_proxy"] = PROXY_URL
    os.environ["https_proxy"] = PROXY_URL
    os.environ["GRPC_PROXY_EXP"] = PROXY_URL
else:
    print("--- No Proxy Settings found, running directly ---")
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app", host="0.0.0.0", port=8000, reload=True, log_level="info"
    )
