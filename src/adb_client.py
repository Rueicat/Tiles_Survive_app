"""ADB client for connecting to BlueStacks Android VM (pure Python, no adb.exe)."""
from adb_shell.adb_device import AdbDeviceTcp
from adb_shell.exceptions import TcpTimeoutException, InvalidResponseError


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------
class AdbError(Exception):
    """Raised when an ADB operation fails."""


# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------
# Cache of live device handles. Why cache? `adb-shell` keeps an open TCP
# socket per device — recreating it on every call is slow and wastes file
# descriptors (浪費資源). Keyed by serial string 'host:port'.
_DEVICES: dict[str, AdbDeviceTcp] = {}

# BlueStacks 5 spawns each instance on its own ADB port. Probe these in order.
COMMON_BLUESTACKS_PORTS: list[int] = [5555, 5556, 5557, 5565, 5575, 5585]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _open_device(host: str, port: int, timeout: float = 5.0) -> AdbDeviceTcp:
    """
    Open (or reuse) a TCP ADB device handle.

    Re-uses a cached handle if it is still .available, otherwise creates a
    fresh one and stores it. All `adb-shell` exceptions are wrapped into
    AdbError so callers only need to catch one type.
    """
    serial = f"{host}:{port}"
    cached = _DEVICES.get(serial)
    if cached is not None and cached.available:
        return cached

    device = AdbDeviceTcp(host, port, default_transport_timeout_s=timeout)
    try:
        # auth_timeout_s=0.1 → BlueStacks normally allows unauth localhost.
        # If your instance demands RSA, see the `connect` docstring below.
        device.connect(auth_timeout_s=0.1)
    except (TcpTimeoutException, ConnectionRefusedError, OSError) as e:
        raise AdbError(f"Cannot reach {serial}: {e}") from e
    except InvalidResponseError as e:
        raise AdbError(f"ADB handshake failed at {serial}: {e}") from e

    _DEVICES[serial] = device
    return device


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def connect_bluestacks(host: str = "127.0.0.1", port: int = 5555) -> str:
    """
    Connect to a BlueStacks instance via ADB.

    Pre-conditions (前置條件):
      1. The user has opened BlueStacks and launched the game.
      2. ADB is enabled in BlueStacks → Settings → Advanced.

    Returns the serial string 'host:port' on success.
    Raises AdbError on any failure (network, handshake, or shell sanity test).
    """
    serial = f"{host}:{port}"
    device = _open_device(host, port)

    # Sanity check: a tiny shell command proves the link actually works.
    try:
        out = device.shell("echo READY", timeout_s=3.0).strip()
    except Exception as e:                       # adb-shell may raise various
        raise AdbError(f"Connected but shell test failed on {serial}: {e}") from e

    if out != "READY":
        raise AdbError(f"Unexpected shell response from {serial}: {out!r}")
    return serial


def disconnect(serial: str) -> None:
    """Close the TCP connection to one device. Best-effort (盡力)."""
    device = _DEVICES.pop(serial, None)
    if device is None:
        return
    try:
        device.close()
    except Exception:
        pass


def disconnect_all() -> None:
    """Close every cached device. Useful on app shutdown."""
    for serial in list(_DEVICES):
        disconnect(serial)


def list_devices_raw() -> list[tuple[str, str]]:
    """
    Return [(serial, state), ...] for everything currently in the cache.

    Note: pure-Python ADB has no global daemon, so this only knows about
    devices we have already touched. For initial discovery, use
    `scan_bluestacks()` first.
    """
    return [
        (serial, "device" if dev.available else "offline")
        for serial, dev in _DEVICES.items()
    ]


def scan_bluestacks(host: str = "127.0.0.1") -> list[str]:
    """
    Probe COMMON_BLUESTACKS_PORTS and return serials that responded.
    Side-effect: every successful probe is added to the cache, so a later
    `list_devices_raw()` will include them.
    """
    found: list[str] = []
    for port in COMMON_BLUESTACKS_PORTS:
        try:
            _open_device(host, port, timeout=1.0)
            found.append(f"{host}:{port}")
        except AdbError:
            continue                             # silent — port not open
    return found


def is_game_running(serial: str, package: str) -> bool:
    """
    Return True if `package` (e.g. 'com.example.tilessurvive') has a PID
    on the given device.
    """
    device = _DEVICES.get(serial)
    if device is None:
        raise AdbError(f"Not connected to {serial}. Call connect_bluestacks first.")
    out = device.shell(f"pidof {package}", timeout_s=3.0).strip()
    return bool(out)


def shell(serial: str, command: str, timeout: float = 5.0) -> str:
    """
    Run an arbitrary shell command on the device and return stdout.
    Convenience wrapper so other modules don't reach into _DEVICES directly.
    """
    device = _DEVICES.get(serial)
    if device is None:
        raise AdbError(f"Not connected to {serial}. Call connect_bluestacks first.")
    try:
        return device.shell(command, timeout_s=timeout)
    except Exception as e:
        raise AdbError(f"shell({command!r}) failed on {serial}: {e}") from e


# ---------------------------------------------------------------------------
# Manual smoke test (手動測試): `python src/adb_client.py`
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    try:
        print("Scanning BlueStacks ports...")
        serials = scan_bluestacks()
        if not serials:
            raise AdbError("No BlueStacks instance answered on common ports.")
        print(f"Found: {serials}")

        chosen = serials[0]
        host, _, port_str = chosen.partition(":")
        confirmed = connect_bluestacks(host=host, port=int(port_str))
        print(f"[OK] Connected: {confirmed}")
        print("Devices in cache:", list_devices_raw())
    except AdbError as e:
        print(f"[FAIL] {e}")
    finally:
        disconnect_all()
