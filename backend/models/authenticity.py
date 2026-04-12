import cv2
import numpy as np
from PIL import Image
import io


def score_authenticity(img_bytes: bytes) -> dict:
    try:
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        w, h = img.size
        aspect = w / max(h, 1)
        aspect_ok = 1.2 <= aspect <= 2.0
        res_ok = w >= 300 and h >= 180
        arr = np.array(img).astype(float)
        not_blank = float(arr.var()) > 100
        gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        has_structure = float(edges.sum()) / (w * h * 255) > 0.005
        score = round((0.3 if aspect_ok else 0.0) + (0.2 if res_ok else 0.0) +
                      (0.3 if not_blank else 0.0) + (0.2 if has_structure else 0.0), 3)
        return {"score": score, "verdict": "PASS" if score >= 0.7 else "WARN" if score >= 0.4 else "FAIL",
                "checks": {"aspect_ratio": aspect_ok, "resolution": res_ok,
                            "not_blank": not_blank, "has_structure": has_structure}}
    except Exception as e:
        return {"score": 0.5, "verdict": "WARN", "note": f"error: {e}"}
