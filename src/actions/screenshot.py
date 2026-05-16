"""Take a BlueStacks screenshot and briefly display it — no disk I/O."""
import base64
import threading

import cv2
import numpy as np

from adb_client import shell, AdbError

DISPLAY_SECONDS = 5
WINDOW_TITLE = "BlueStacks Screenshot"


def capture_png(serial: str) -> bytes:
    """
    Pull a PNG screenshot from the device. Returns raw PNG bytes.

    Uses base64 transport to avoid Android's shell mangling \\n into \\r\\n,
    which would corrupt the PNG (常見陷阱).
    """
    b64 = shell(serial, "screencap -p | base64", timeout=10.0)
    if not b64:
        raise AdbError("Empty screencap output — is the device awake?")
    return base64.b64decode(b64)


def show_for_n_seconds(png_bytes: bytes, seconds: int = DISPLAY_SECONDS) -> None:
    """
    Display the in-memory PNG in a popup window for `seconds`, then close.
    Runs on a daemon thread so the caller (the TUI) is never blocked.
    """
    def _runner() -> None:
        arr = np.frombuffer(png_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return                                  # silently bail if decode failed
        cv2.imshow(WINDOW_TITLE, img)
        cv2.waitKey(seconds * 1000)                 # blocks this thread only
        cv2.destroyWindow(WINDOW_TITLE)

    threading.Thread(target=_runner, daemon=True).start()


def screenshot_and_show(serial: str) -> None:
    """High-level convenience: capture, then display for DISPLAY_SECONDS."""
    png = capture_png(serial)
    show_for_n_seconds(png)
