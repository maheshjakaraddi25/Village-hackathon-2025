def match_faces(id_img_bytes: bytes, selfie_bytes: bytes) -> dict:
    return {
        "match": False,
        "distance": None,
        "confidence": 0.0,
        "flag": "UNAVAILABLE",
        "note": "Face matching disabled — deepface/tensorflow not required"
    }
