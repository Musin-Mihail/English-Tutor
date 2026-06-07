import os


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
    from app.ui import build_ui

    demo = build_ui()
    demo.launch(server_name="0.0.0.0", server_port=8000)
