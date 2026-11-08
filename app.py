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
os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")  # no warning spam in the black window


def disable_quickedit():
    """Windows: clicking inside the black SceneForge window starts "QuickEdit" text selection, which PAUSES
    the program until a key is pressed (previews and renders seem to hang). Switch that mode off."""
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        handle = k32.GetStdHandle(-10)  # console input
        mode = ctypes.c_uint32()
        if k32.GetConsoleMode(handle, ctypes.byref(mode)):
            k32.SetConsoleMode(handle, (mode.value & ~0x0040) | 0x0080)  # QuickEdit off, keep extended flags
    except Exception:
        pass


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
    disable_quickedit()
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
