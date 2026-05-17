import re
import winreg
import subprocess
from pathlib import Path

ADB = Path(__file__).parent.parent / "tools" / "adb.exe"

MAX_VMS = 5

## 抓reg path
_REG_ROOT = r"SOFTWARE"
_BLUESTACKS_PREFIX = "BlueStacks"

_ADB_PORT_RE = re.compile(
    r'\.status\.adb_port="(\d+)"'
)

## 中文編碼處理
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


#-------------local log, search and locate
def find_bluestacks_conf() -> Path | None:
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _REG_ROOT) as software_key:
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(software_key, i)
                except OSError:
                    break
                i += 1

                if not subkey_name.startswith(_BLUESTACKS_PREFIX):
                    continue

                ## read LogDir, look for conf file
                try:
                    with winreg.OpenKey(software_key, subkey_name) as bs_key:
                        log_dir, _ = winreg.QueryValueEx(bs_key, "LogDir")
                        log_path = Path(log_dir)
                        if not log_path.is_dir():
                            continue
                        
                        # the same ./
                        conf = log_path / "bluestacks.conf"
                        if conf.is_file():
                            return conf

                        # parent folder
                        conf = log_path.parent / "bluestacks.conf"
                        if conf.is_file():
                            return conf

                except FileNotFoundError:
                    continue
                except OSError:
                    continue
    except OSError:
        return None

    return None


#-----------------parse conf, and get ports

def parse_adb_ports_from_conf(conf_path: Path) -> list[int]:
    if not conf_path.is_file():
        return []
    
    try:
        text = conf_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    ports: list[int] = []
    seen: set[int] = set()
    for match in _ADB_PORT_RE.finditer(text):
        port = int(match.group(1))
        if port not in seen:
            seen.add(port)
            ports.append(port)
    return ports



#---------
def discover_vm_ports() -> tuple[list[int], str]:
    conf_path = find_bluestacks_conf()
    if conf_path is None:
        return [], "bluestacks.conf not found (check registry / install path)"

    ports = parse_adb_ports_from_conf(conf_path)
    if not ports:
        return [], f"no port found in: {conf_path}"

    return ports, f"found {len(ports)} ports in {conf_path}"


#------------
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
        if not line or line.startswith("List of"):
            continue

        parts = line.split()

        if len(parts) >= 2 and parts[0] == target:
            state = parts[1]
            if state == "device":
                return True, target
            else:
                return False, f"{target} state: {state}"

    return False, f"{target} not found in devices list"


#-----------connect the found ports list one by one
def connect_discovered_vms(
    on_progress=None,
    max_vms: int = MAX_VMS,
) -> tuple[list[int], list[tuple[int, str]], str]:

    ports, msg = discover_vm_ports()
    if not ports:
        return [], [], msg

    connected: list[int] = []
    failed: list[tuple[int, str]] = []

    for port in ports:
        if len(connected) >= max_vms:
            break
        
        ok, info = connect_bluestacks(port)
        if on_progress is not None:
            on_progress(port, ok, info)

        if ok:
            connected.append(port)
        else:
            failed.append((port, info))

    return connected, failed, msg


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
    
    ports, msg = discover_vm_ports()
    print(f"{msg}")
    print(f"ports: {ports}")

    def _log(p, ok, info):
        tag = "OK" if ok else "FAIL"
        print(f"{tag} {p}: {info}")
    connected, failed, _ = connect_discovered_vms(on_progress=_log)
    print(f"connected: {connected}")
    print(f"failed: {failed}")

    ok, msg = disconnect_all()
    print(f"{'OK' if ok else 'FAIL'} {msg}")
