from deepface import DeepFace
import tempfile, os

def match_faces(id_img_bytes: bytes, selfie_bytes: bytes) -> dict:
    # DeepFace needs file paths
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f1, \
         tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f2:
        f1.write(id_img_bytes);  p1 = f1.name
        f2.write(selfie_bytes);  p2 = f2.name

    try:
        r = DeepFace.verify(p1, p2,
                            model_name='ArcFace',
                            detector_backend='retinaface',
                            distance_metric='cosine',
                            enforce_detection=False)
        dist = r['distance']
        conf = round(max(0, 1 - dist / 0.40), 3)
        return {
            'match':      r['verified'],
            'distance':   round(dist, 4),
            'confidence': conf,
            'flag': 'MATCH' if r['verified'] and conf > 0.8
                    else 'PARTIAL_MATCH' if conf > 0.5
                    else 'MISMATCH'
        }
    except Exception as e:
        return {'match': False, 'distance': None, 'confidence': 0.0,
                'flag': 'ERROR', 'error': str(e)}
    finally:
        os.unlink(p1); os.unlink(p2)