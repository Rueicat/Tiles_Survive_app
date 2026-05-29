import subprocess
from pathlib import Path
import time

from src.actions.outside_mv import go_to_wild
from src.vision.vision import match_template

###--path

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

def _swipe(device: str, x1: int, y1: int, x2: int, y2: int, duration_ms: int) -> None:
    _adb(device, f"shell input swipe {x1} {y1} {x2} {y2} {duration_ms}")

##-----steps of kill_zombie   main

# 1. process outside_mv.py first
# 2. if return "在城外" (or rebuild the function go_to_wild as it can return bool)
#     then process the def kill_zombie_big()
# 3. if not, return the go_to_wild logs what happened it not go to wild

def kill_zombie_big(device: str) -> str:
    wild_result = go_to_wild(device)
    if wild_result != "在城外":
        return f"無法打殭屍. {wild_result}"

    TARGET_TEAMS = 4

    dispatched = 0

    for i in range(TARGET_TEAMS):
        result = _do_kill_zombie(device)
        
        if result != "已派出隊伍打喪屍首領":
            return F"第{i + 1}隊失敗:{result}, 成功派出{dispatched}隊"

        dispatched += 1
        time.sleep(2)

    return _verify_four_teams(device, dispatched)

def _verify_four_teams(device: str, dispatched: int) -> str:
    team_four = str(TEMPLATES / "team_4.png")

    screen_bytes = _take_screenshot(device)

    found, _ = match_template(screen_bytes, team_four)
    if found:
        return f"成功派出4隊打喪屍首領"
    else:
        return f"派遣{dispatched}隊, 但畫面找不到四個隊伍出勤的圖"
        
    


def _do_kill_zombie(device: str) -> str:
    zoom_in = str(TEMPLATES / "zoom_in.png")
    leader = str(TEMPLATES / "leader.png")
    minus_bar = str(TEMPLATES / "minus_bar.png")
    lv1_bar = str(TEMPLATES / "lv1_bar.png")
    search_button = str(TEMPLATES / "search_button.png")
    come = str(TEMPLATES / "come.png")
    big_come = str(TEMPLATES / "big_come.png")

    # 拍照
    screen_bytes = _take_screenshot(device)
    
    # 按搜尋按鈕
    search, search_loc = match_template(screen_bytes, zoom_in )
    if not search:
        return "找不到放大鏡, 幫我確認"
    x, y = search_loc
    _tap(device, x, y)

    time.sleep(1)
    ## 滑動搜尋列, 可能停在右邊的資源list
    ##水平滑動　(x,y) = ( 98,1527 ) -> (900, 1527)
    _swipe(device, 121, 1381, 1030, 1381, duration_ms=800)

    time.sleep(3)
    
    # 再拍照一次, 對, 之前的照片就不需要了, 直接覆蓋
    screen_bytes = _take_screenshot(device)

    # 按海屍首領
    leader_pic, leader_pic_loc = match_template(screen_bytes, leader )
    if not leader_pic:
        return "喪屍首領圖片看不到"
    x, y = leader_pic_loc
    _tap(device, x, y)

    time.sleep(1)

    # push minus bar
    minus_pic, minus_pic_loc = match_template(screen_bytes, minus_bar )
    if not minus_pic:
        return "沒看到選擇等級按鈕"

    # 按10次, 先這樣設計 -> using loop
    x, y = minus_pic_loc
    for _ in range(10):
        _tap(device, x, y)

    time.sleep(1)

    # 再拍照一次, 並確認真的選了等級1
    screen_bytes = _take_screenshot(device)
    
    lv1_pic, _ = match_template(screen_bytes, lv1_bar )
    if not lv1_pic:
        return "沒選到等級1, 不知道怎麼了"

    # 按搜尋按鈕
    search_button_pic, search_button_loc = match_template(screen_bytes, search_button )
    if not search_button_pic:
        return "看不到綠色的搜尋按鈕, 不知道怎麼了"
    x, y = search_button_loc
    _tap(device, x, y)
    time.sleep(2)
    # 可能和人家搜尋同一隻, 再按一次, 我還沒確認這個對不對
    _tap(device, x, y)

    time.sleep(2)

    # 再拍照一次, 準備按集結按鈕(有消耗體力畫面的)
    screen_bytes = _take_screenshot(device)

    come_pic, come_loc = match_template(screen_bytes, come )
    if not come_pic:
        return "看不到綠色的搜尋按鈕, 不知道怎麼了"
    x, y = come_loc
    _tap(device, x, y)

    time.sleep(2)

    # again, 按集結(最後要出發了)
    screen_bytes = _take_screenshot(device)
    
    big_come_pic, big_come_loc = match_template(screen_bytes, big_come )
    if not big_come_pic:
        return "看不到綠色大的搜尋按鈕, 不知道怎麼了"
    x, y = big_come_loc
    _tap(device, x, y)

    return "已派出隊伍打喪屍首領"

# unit test
if __name__ == "__main__":
    from src.adb_client_v2 import connect_bluestacks

    ok, device_or_err = connect_bluestacks(5555)
    if not ok:
        print(f"fail: {device_or_err}")
        raise SystemError(1)

    print(f"[OK] {device_or_err}")
    print(kill_zombie_big(device_or_err))



    

