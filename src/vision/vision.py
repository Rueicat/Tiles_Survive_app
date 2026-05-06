import cv2
import numpy as np


def match_template(original_bytes: bytes, template: str, threshold: float = 0.8) -> tuple:

    nparr = np.frombuffer(original_bytes, np.uint8)
    original_img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
    template_img = cv2.imread(template, cv2.IMREAD_GRAYSCALE)
    
    if original_img is None:
        raise FileNotFoundError("Cannot decode original bytes (empty or corrupted)")
    if template_img is None:
        raise FileNotFoundError(f"Cannot open template image: {template}")
    
    result = cv2.matchTemplate(original_img, template_img, cv2.TM_CCOEFF_NORMED)
    _, max_score, _, max_loc = cv2.minMaxLoc(result)


    # debug
    print(f"[DEBUG] template={template} | score={max_score:.3f} | threshold={threshold}")
    
    
    ## like lua, it can return muti values
    if max_score < threshold:
        return False, None
    return True, max_loc
    
    
    
## unit test    
if __name__ == "__main__":
    with open("../../temp/6.png", "rb") as f:
        image_byyes = f.read()
    found, location = match_template(
        image_byyes,    
        "../../image_templates/zoom_in.png"
    )
    print(found,location)
