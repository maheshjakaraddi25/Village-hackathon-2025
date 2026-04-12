from models.authenticity import score_authenticity
from models.ocr_extractor import extract_id_fields
from models.face_match    import match_faces
from models.liveness      import passive_liveness
from compliance           import enrich_expiration

async def run_local_pipeline(id_bytes: bytes,
                              selfie_bytes: bytes | None = None) -> dict:
    # Runs stages 1-4 locally (no API cost)
    auth    = score_authenticity(id_bytes)
    fields  = extract_id_fields(id_bytes)
    face    = match_faces(id_bytes, selfie_bytes) if selfie_bytes else None
    live    = passive_liveness(selfie_bytes)      if selfie_bytes else None

    return {
        'local': {
            'authenticity': auth,
            'ocr_fields':   fields,
            'face_match':   face,
            'liveness':     live,
        }
    }