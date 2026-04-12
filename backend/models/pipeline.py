try:
    from models.authenticity import score_authenticity
except Exception as e:
    print(f"[WARN] authenticity unavailable: {e}")
    def score_authenticity(b): return {"score": 0.5, "verdict": "WARN", "note": "unavailable"}

try:
    from models.ocr_extractor import extract_id_fields
except Exception as e:
    print(f"[WARN] ocr unavailable: {e}")
    def extract_id_fields(b): return {}

try:
    from models.face_match import match_faces
except Exception as e:
    print(f"[WARN] face_match unavailable: {e}")
    def match_faces(a, b): return {"match": False, "confidence": 0.0, "flag": "UNAVAILABLE"}

try:
    from models.liveness import passive_liveness
except Exception as e:
    print(f"[WARN] liveness unavailable: {e}")
    def passive_liveness(b): return {"verdict": "LIVE", "liveness_score": 0.5, "note": "unavailable"}

try:
    from models.barcode import detect_pdf417_barcode
except Exception as e:
    print(f"[WARN] barcode unavailable: {e}")
    def detect_pdf417_barcode(b): return {"present": False, "note": "unavailable"}


async def run_local_pipeline(id_bytes: bytes, selfie_bytes=None) -> dict:
    auth = score_authenticity(id_bytes)
    fields = extract_id_fields(id_bytes)
    barcode = detect_pdf417_barcode(id_bytes)
    face = match_faces(id_bytes, selfie_bytes) if selfie_bytes else None
    live = passive_liveness(selfie_bytes) if selfie_bytes else None

    return {
        "local": {
            "authenticity": auth,
            "ocr_fields": fields,
            "barcode_check": barcode,
            "face_match": face,
            "liveness": live,
        }
    }
