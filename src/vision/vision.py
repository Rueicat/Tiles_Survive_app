import cv2
import numpy as np
from pathlib import Path

TARGET_W = 1080
TARGET_H = 1920


## add black pad to avoid it crash
def zoom_to_fit(img: np.ndarray, pad_value: int = 0) -> tuple[np.ndarray, float]:
    h, w = img.shape[:2]
    scale = min(TARGET_W / w, TARGET_H / h)

    new_w = int(w * scale)
    new_h = int(h * scale)

    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
    scaled = cv2.resize(img, (new_w, new_h), interpolation=interp)

    ## place in the middle
    canvas = np.full((TARGET_H, TARGET_W), pad_value, dtype=np.uint8)    
    offset_y = (TARGET_H - new_h) // 2
    offset_x = (TARGET_W - new_w) // 2
    canvas[offset_y:offset_y + new_h, offset_x: offset_x + new_w] = scaled

    print(
        f"[ZOOM] original={w}x{h} | scale={scale:.2f} "
        f"| scaled={new_w}x{new_h} "
    )
    return canvas, scale



def match_template(original_bytes: bytes, template: str, threshold: float = 0.8) -> tuple:

    nparr = np.frombuffer(original_bytes, np.uint8)
    original_img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
    template_img = cv2.imread(template, cv2.IMREAD_GRAYSCALE)
    
    if original_img is None:
        raise FileNotFoundError("Cannot decode original bytes (empty or corrupted)")
    if template_img is None:
        raise FileNotFoundError(f"Cannot open template image: {template}")

    original_img, scale = zoom_to_fit(original_img)

    
    result = cv2.matchTemplate(original_img, template_img, cv2.TM_CCOEFF_NORMED)
    _, max_score, _, max_loc = cv2.minMaxLoc(result)

    print(f"template={Path(template).name} | score={max_score:.2f} | threshold={threshold}")
    
    
    ## like lua, it can return muti values
    if max_score < threshold:
        return False, None

    ##5/29 匹配的座標, 是""左上角""那個點
    th, tw = template_img.shape[:2]
    center_x = max_loc[0] + tw // 2
    center_y = max_loc[1] + th // 2

    #記得還原成原始圖片比例的座標
    original_x = int(center_x / scale )
    original_y = int(center_y / scale )
    original_loc = (original_x, original_y)
    

    print(max_loc)
    return True, original_loc
    

## unit test    
if __name__ == "__main__":
    with open("../../temp/big_screen.png", "rb") as f:
        image_bytes = f.read()
    found, location = match_template(
        image_bytes,    
        "../../image_templates/inside_town_icon.png"
    )
    print(found,location)
