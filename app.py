"""SceneForge - personal scene-synced video editor. Runs only on this computer (http://127.0.0.1:7860)."""
import os
import socket
import sys
import threading
import time
import webbrowser

# Nothing leaves this computer: no usage statistics from the speech-model library.
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")


def free_port(preferred=7860):
    for port in range(preferred, preferred + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return preferred


def main():
    import uvicorn
    from sceneforge.server import app

    port = free_port()
    url = f"http://127.0.0.1:{port}/"
    print(f"\n  SceneForge is running at {url}\n  Keep this window open while you work - closing it stops SceneForge.\n")
    if "--no-browser" not in sys.argv:
        threading.Thread(target=lambda: (time.sleep(1.5), webbrowser.open(url)), daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
