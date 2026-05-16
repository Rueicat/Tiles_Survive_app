import subprocess
from pathlib import Path

ADB = Path(__file__).parent.parent / "tools" / "adb.exe"

## 中文編碼問題
def _run_adb(args: list[str]) -> tuple[str, str]:
    
    result = subprocess.run(
        [str(ADB)] + args,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    return stdout, stderr

def connect_bluestacks(port: int) -> tuple[bool, str]:

    target = f"127.0.0.1:{port}"

    ##try to connect
    stdout, stderr = _run_adb(["connect", target])
    low = stdout.lower()

    if "cannot connect" in low or "failed to connect" in low:
        return False, stdout.splitlines()[0] if stdout else stderr

    ##connect- with connected or already connected two situations
    if "connected" not in low:
        return False, f"unexpected adb output: {stdout or stderr}"


    ##check again when connected
    stdout, _ = _run_adb(["devices"])

    for line in stdout.splitlines():
        if not line or line .startswith("List of"):
            continue

        parts = line.split()

        if len(parts) >= 2 and parts[0] == target:
            state = parts[1]
            if state == "device":
                return True, target
            else:
                return False, f"{target} state: {state}"

    return False, f"{target} not found in devices list"
        
def disconnect_all() -> tuple[bool, str]:
    stdout, stderr = _run_adb(["disconnect"])

    output = (stdout + stderr).lower()

    if "disconnected everything" in output:
        return True, stdout or "disconnected everything"

    if not stdout and not stderr:
        return True, "no active connections"

    return False, f"非預期錯誤: {stdout or stderr}"




## unit test
if __name__ == "__main__":

    ok, msg = disconnect_all()
    print(f"{'OK' if ok else 'FAIL'} {msg}")
