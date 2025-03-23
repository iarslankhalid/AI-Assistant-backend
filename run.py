import uvicorn
import threading
import time
import requests
import os

# Determine environment: "prod" or "local"
ENV = os.getenv("ENV", "local").lower()

# Default settings
HOST = "localhost"
PORT = 8000
RELOAD = True  # Enable live reload in local development

# Production config
if ENV == "prod":
    HOST = "0.0.0.0"
    RELOAD = False  # Disable reload in production
    KEEP_ALIVE_URL = f"http://localhost:{PORT}/ping"  # Adjust this if hosted on a public URL
    PING_INTERVAL_SECONDS = 10 * 60  # 10 minutes

    def keep_alive():
        """Periodically ping the service to keep it awake."""
        while True:
            try:
                response = requests.get(KEEP_ALIVE_URL)
                print(f"[KeepAlive] Pinged {KEEP_ALIVE_URL} — Status Code: {response.status_code}")
            except Exception as e:
                print(f"[KeepAlive] Failed to ping {KEEP_ALIVE_URL}: {e}")
            time.sleep(PING_INTERVAL_SECONDS)

    # Start keep-alive thread only in production
    threading.Thread(target=keep_alive, daemon=True).start()
else:
    print("[Info] Running in local mode — Keep-alive disabled.")

# Start the FastAPI app
if __name__ == "__main__":
    uvicorn.run("main:app", host=HOST, port=PORT, reload=RELOAD)
