import subprocess
from pathlib import Path

ADB = Path(__file__).parent.parent / "tools" / "adb.exe"

def _run_adb(args: list[str], timeout: int = 10) -> tuple[int, str, str]:
    
    result = subprocess.run(
        [str(ADB)] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def connect_bluestacks(port: int) -> tuple[bool, str]:

    target = f"127.0.0.1:{port}"

    ##check
    try:
        rc, stdout, stderr = _run_adb(["devices"])
    except subprocess.TimeoutExpired:
        return False, "adb devices command time out"

    if rc != 0:
        return False, f"adb devces failed: {stderr}"

    ##connect
    rc, stdout, stderr = _run_adb(["connect", target])
    if rc != 0:
        return False, f"adb connect failed: {stderr or stdout}"

    if "connected" not in stdout.lower() and "already" not in stdout.lower():
        return False, f"adb connect rejected: {stdout}"

    ##check again when connected
    rc, stdout, _ = _run_adb(["devices"])

    for line in stdout.splitlines():
        if not line or line .startswith("List of"):
            continue

        parts = line.split()

        if len(parts) >= 2 and parts[0] == target:
            state = parts[1]
            if state == "device":
                return True, target
            else:
                return False, F"Device {target} is in state: {state}"
    return False, f"Device {target} not found in adb devices list"
        

## unit test
if __name__ == "__main__":
    port = 5555

    success, message = connect_bluestacks(port)

    if success:
        print(f"[OK] connected to {message}")
    else:
        print(f"[False] {message}")
