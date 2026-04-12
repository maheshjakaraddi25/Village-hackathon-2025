from paddleocr import PaddleOCR
import re
import cv2
import numpy as np
from datetime import datetime


_ocr = None


def _load():
    global _ocr
    if _ocr is None:
        _ocr = PaddleOCR(use_angle_cls=True, lang="en", use_gpu=False)
    return _ocr


def normalize_date(s: str | None) -> str | None:
    if not s:
        return None

    s = s.strip()

    for fmt in ["%m/%d/%Y", "%m-%d-%Y", "%d/%m/%Y"]:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except Exception:
            pass

    return None


def extract_id_fields(img_bytes: bytes) -> dict:
    arr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)

    if img is None:
        return {}

    result = _load().ocr(img, cls=True)
    lines = [w[1][0] for line in result for w in line]
    text = "\n".join(lines)

    def find(pat):
        m = re.search(pat, text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    dob_raw = find(r"\b(\d{2}[/-]\d{2}[/-]\d{4})\b")
    exp_raw = find(r"(?:EXP|EXPIRES?)[:\s]+(\d{2}[/-]\d{2}[/-]\d{4})")

    # naive name guess
    name_lines = [l for l in lines if not re.search(r"\d{2}[/-]\d{2}", l)][:2]
    parts = name_lines[0].split() if name_lines else []

    return {
        "first_name": parts[0] if parts else None,
        "last_name": parts[-1] if len(parts) > 1 else None,
        "dob": normalize_date(dob_raw),
        "expiration": normalize_date(exp_raw),
        "id_number": find(r"(?:DL|ID)[#:\s]+([A-Z0-9\-]{6,20})"),
        "issuing_state": find(r"\b(CA|TX|FL|NY|CO|WA|OR|AZ|NV|IL|OH|GA)\b"),
        "address": find(r"(\d+\s+\w[\w\s,]+(?:ST|AVE|DR|RD|BLVD|LN)[,.\s]+\w[\w\s]+\d{5})"),
    }