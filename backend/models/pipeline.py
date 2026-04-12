# from backend.models.authenticity import score_authenticity
# from backend.models.ocr_extractor import extract_id_fields
# from backend.models.face_match import match_faces
# from backend.models.liveness import passive_liveness
# from backend.models.barcode import detect_pdf417_barcode
from models.authenticity import score_authenticity
from models.ocr_extractor import extract_id_fields
from models.face_match import match_faces
from models.liveness import passive_liveness
from models.barcode import detect_pdf417_barcode


async def run_local_pipeline(id_bytes: bytes, selfie_bytes: bytes | None = None) -> dict:
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