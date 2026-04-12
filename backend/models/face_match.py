from deepface import DeepFace
import tempfile
import os
import cv2
import numpy as np


def _bytes_to_imgfile(img_bytes: bytes) -> str:
    arr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)

    f = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    cv2.imwrite(f.name, img)
    return f.name


def _crop_best_face(img_path: str) -> str | None:
    faces = DeepFace.extract_faces(
        img_path=img_path,
        detector_backend="retinaface",
        enforce_detection=False
    )

    if not faces:
        return None

    best = max(faces, key=lambda f: f["facial_area"]["w"] * f["facial_area"]["h"])
    face_img = (best["face"] * 255).astype(np.uint8)

    out = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    cv2.imwrite(out.name, face_img)
    return out.name


def match_faces(id_img_bytes: bytes, selfie_bytes: bytes) -> dict:
    id_path = _bytes_to_imgfile(id_img_bytes)
    selfie_path = _bytes_to_imgfile(selfie_bytes)
    crop_path = None

    try:
        crop_path = _crop_best_face(id_path)
        if not crop_path:
            return {
                "match": False,
                "distance": None,
                "confidence": 0.0,
                "flag": "NO_FACE_IN_ID"
            }

        r = DeepFace.verify(
            img1_path=crop_path,
            img2_path=selfie_path,
            model_name="ArcFace",
            detector_backend="retinaface",
            distance_metric="cosine",
            enforce_detection=False
        )

        dist = r["distance"]
        conf = round(max(0, 1 - dist / 0.40), 3)

        return {
            "match": bool(r["verified"]),
            "distance": round(dist, 4),
            "confidence": conf,
            "flag": "MATCH" if r["verified"] else ("PARTIAL_MATCH" if conf > 0.55 else "MISMATCH")
        }

    except Exception as e:
        return {
            "match": False,
            "distance": None,
            "confidence": 0.0,
            "flag": "ERROR",
            "error": str(e)
        }

    finally:
        for p in [id_path, selfie_path, crop_path]:
            if p and os.path.exists(p):
                os.unlink(p)