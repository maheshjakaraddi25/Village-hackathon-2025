import cv2
import numpy as np
from typing import Optional

# OpenCV face detector — no tensorflow needed
_face_cascade = None
_recognizer = None


def _get_cascade():
    global _face_cascade
    if _face_cascade is None:
        _face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
    return _face_cascade


def _decode_image(img_bytes: bytes) -> Optional[np.ndarray]:
    arr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img


def _detect_and_crop_face(img: np.ndarray) -> Optional[np.ndarray]:
    """Detect largest face in image and return cropped grayscale."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = _get_cascade().detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
    )
    if len(faces) == 0:
        return None
    # Pick largest face
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    face = gray[y:y+h, x:x+w]
    return cv2.resize(face, (100, 100))


def _histogram_similarity(face1: np.ndarray, face2: np.ndarray) -> float:
    """Compare two face crops using histogram correlation."""
    hist1 = cv2.calcHist([face1], [0], None, [256], [0, 256])
    hist2 = cv2.calcHist([face2], [0], None, [256], [0, 256])
    cv2.normalize(hist1, hist1)
    cv2.normalize(hist2, hist2)
    return float(cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL))


def _lbph_similarity(face1: np.ndarray, face2: np.ndarray) -> float:
    """Compare using Local Binary Pattern Histogram — more robust than raw histogram."""
    def lbph(img):
        rows, cols = img.shape
        result = np.zeros_like(img)
        for i in range(1, rows - 1):
            for j in range(1, cols - 1):
                center = img[i, j]
                code = 0
                neighbors = [
                    img[i-1,j-1], img[i-1,j], img[i-1,j+1],
                    img[i,  j+1], img[i+1,j+1], img[i+1,j],
                    img[i+1,j-1], img[i,  j-1]
                ]
                for k, n in enumerate(neighbors):
                    if n >= center:
                        code |= (1 << k)
                result[i, j] = code
        hist, _ = np.histogram(result.ravel(), bins=256, range=(0, 256), density=True)
        return hist

    h1 = lbph(face1)
    h2 = lbph(face2)
    # Chi-square distance — lower = more similar
    eps = 1e-10
    chi2 = float(np.sum((h1 - h2) ** 2 / (h1 + h2 + eps)))
    # Convert to similarity score 0-1
    similarity = 1.0 / (1.0 + chi2)
    return similarity


def match_faces(id_img_bytes: bytes, selfie_bytes: bytes) -> dict:
    """
    Compare face on ID document against a selfie using OpenCV.
    No tensorflow or deepface required.
    """
    id_img   = _decode_image(id_img_bytes)
    selfie   = _decode_image(selfie_bytes)

    if id_img is None or selfie is None:
        return {"match": False, "distance": None, "confidence": 0.0,
                "flag": "ERROR", "note": "Could not decode image"}

    id_face   = _detect_and_crop_face(id_img)
    self_face = _detect_and_crop_face(selfie)

    if id_face is None:
        return {"match": False, "distance": None, "confidence": 0.0,
                "flag": "NO_FACE_IN_ID", "note": "No face detected in ID image"}

    if self_face is None:
        return {"match": False, "distance": None, "confidence": 0.0,
                "flag": "NO_FACE_IN_SELFIE", "note": "No face detected in selfie"}

    # Combine histogram and LBPH scores
    hist_score = _histogram_similarity(id_face, self_face)
    lbph_score = _lbph_similarity(id_face, self_face)
    combined   = round((hist_score * 0.4 + lbph_score * 0.6), 3)

    matched = combined >= 0.6
    flag    = "MATCH" if combined >= 0.75 else \
              "PARTIAL_MATCH" if combined >= 0.6 else \
              "MISMATCH"

    return {
        "match":      matched,
        "distance":   round(1.0 - combined, 3),
        "confidence": combined,
        "flag":       flag,
        "scores": {
            "histogram": round(hist_score, 3),
            "lbph":      round(lbph_score, 3),
        }
    }
