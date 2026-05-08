import subprocess
from pathlib import Path
import time

from src.vision.vision import match_template
from src.adb_client_v2 import connect_bluestacks

##------------- path

ADB = Path(__file__).parent.parent.parent / "tools" / "adb.exe"
PROJECT_ROOT = Path(__file__).parent.parent.parent
TEMPLATES = PROJECT_ROOT / "image_templates"


##----actions

def _adb(device: str, command: str) -> str:
    result = subprocess.run(
        [str(ADB), "-s", device] + command.split(),
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()

def _take_screenshot(device: str) -> bytes:
    result = subprocess.run(
        [str(ADB), "-s", device, "exec-out", "screencap", "-p"],
        capture_output=True,
    )
    return result.stdout

def _tap(device: str, x: int, y: int) -> None:
    _adb(device, f"shell input tap {x} {y}")

##----------------------------steps main

def go_to_wild(device: str) -> str:
    wild_template = str(TEMPLATES / "wild_icon.png")
    town_template = str(TEMPLATES / "inside_town_icon.png")
    
    # 拍照
    screen_bytes = _take_screenshot(device)
    
    # 看右下角圖片是不是在外面(在外面的情況)
    found_wild, _ = match_template(screen_bytes, wild_template)
    if found_wild:
        return "In the wild"
    
    # 在家
    found_town, town_loc = match_template(screen_bytes, town_template)
    if not found_town:
        return "Not in the town, either in the wild, please check it"
    x, y = town_loc
    _tap(device, x, y)
    
    
    time.sleep(3)
    
    # 從家裡出來, 再確認一次是不是在外面
    screen_bytes = _take_screenshot(device)
    found_wild_after, _ = match_template(screen_bytes, wild_template)
    if found_wild_after:
        return "In the wild"
    else:
        return "Tapped town icon but not outside the wild, please check it"
    



## unit test

if __name__ == "__main__":
    ok, device_or_err = connect_bluestacks()
    if not ok:
        print(f"[FAIL] connect: {device_or_err}")
        raise SystemExit(1)
    
    device = device_or_err
    print(f"[OK] device = {device}")

    result = go_to_wild(device)
    print(result)
