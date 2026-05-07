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

    target = f"127.0.0.1:[port]"

    ##check
    try:
        rc, stdout, stderr = _run_adb("devices")
    except subprocess.TimeoutExpired:
        return False, "adb devices command time out"

    if rc != 0:
        return False, f"adb devces failed: {stderr}"

    ##connect
    rc, stdout, stderr = 
