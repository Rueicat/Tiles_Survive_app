import cv2
import numpy as np

TARGET_W = 1080
TARGET_H = 1920


## add black pad to avoid it crash
def zoom_to_fit(img: np.ndarray, pad_value: int = 0) -> np.ndarray:
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
    canvas[offset_y:offset_x + new_h, offset_x: offset_x + new_w] = scaled

    print(
        f"[ZOOM] original={w}x{h} | scale={scale:.4f} "
        f"| scaled={new_w}x{new_h} "
    )
    return canvas



def match_template(original_bytes: bytes, template: str, threshold: float = 0.8) -> tuple:

    nparr = np.frombuffer(original_bytes, np.uint8)
    original_img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
    template_img = cv2.imread(template, cv2.IMREAD_GRAYSCALE)
    
    if original_img is None:
        raise FileNotFoundError("Cannot decode original bytes (empty or corrupted)")
    if template_img is None:
        raise FileNotFoundError(f"Cannot open template image: {template}")

    original_img = zoom_to_fit(original_img)
    
    result = cv2.matchTemplate(original_img, template_img, cv2.TM_CCOEFF_NORMED)
    _, max_score, _, max_loc = cv2.minMaxLoc(result)

    print(f"template={template} | score={max_score:.3f} | threshold={threshold}")
    
    
    ## like lua, it can return muti values
    if max_score < threshold:
        return False, None
    return True, max_loc
    
    
    
## unit test    
if __name__ == "__main__":
    with open("../../temp/big_screen.png", "rb") as f:
        image_byyes = f.read()
    found, location = match_template(
        image_byyes,    
        "../../image_templates/inside_town_icon.png"
    )
    print(found,location)
