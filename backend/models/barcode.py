import cv2
import numpy as np

try:
    from pyzbar.pyzbar import decode
except ImportError:
    decode = None


def detect_pdf417_barcode(img_bytes: bytes) -> dict:
    if decode is None:
        return {"present": False, "type": None, "note": "pyzbar not installed"}

    arr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)

    if img is None:
        return {"present": False, "type": None, "note": "invalid image"}

    barcodes = decode(img)

    for b in barcodes:
        if b.type.upper() == "PDF417":
            return {"present": True, "type": "PDF417"}

    return {"present": False, "type": None}