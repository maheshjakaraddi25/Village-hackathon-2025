import cv2, numpy as np, mediapipe as mp

mp_face = mp.solutions.face_mesh
EYE_L = [33,160,158,133,153,144]
EYE_R = [362,385,387,263,373,380]

def _ear(lm, pts, W, H):
    p = [(int(lm[i].x*W), int(lm[i].y*H)) for i in pts]
    A = np.linalg.norm(np.array(p[1])-np.array(p[5]))
    B = np.linalg.norm(np.array(p[2])-np.array(p[4]))
    C = np.linalg.norm(np.array(p[0])-np.array(p[3]))
    return (A+B)/(2.0*C)

def passive_liveness(img_bytes: bytes) -> dict:
    arr  = np.frombuffer(img_bytes, np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    blur  = cv2.Laplacian(gray, cv2.CV_64F).var()

    from skimage.feature import local_binary_pattern
    lbp   = local_binary_pattern(gray, P=8, R=1, method='uniform')
    hist,_ = np.histogram(lbp.ravel(), bins=59, range=(0,59), density=True)
    textr = float(np.std(hist))

    score = min(1.0, (blur/500)*0.5 + (textr/0.05)*0.5)
    return {
        'blur_score':     round(blur, 2),
        'texture_score':  round(textr, 4),
        'liveness_score': round(score, 3),
        'verdict': 'LIVE' if score > 0.5 else 'SPOOF'
    }

def active_liveness_from_frames(frame_bytes_list: list[bytes]) -> dict:
    """Pass a sequence of webcam frames; returns blink count."""
    blinks, consec = 0, 0
    with mp_face.FaceMesh(refine_landmarks=True) as mesh:
        for raw in frame_bytes_list:
            arr   = np.frombuffer(raw, np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            H, W  = frame.shape[:2]
            res   = mesh.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if res.multi_face_landmarks:
                lm  = res.multi_face_landmarks[0].landmark
                ear = (_ear(lm, EYE_L, W, H) + _ear(lm, EYE_R, W, H)) / 2
                if ear < 0.20:
                    consec += 1
                elif consec >= 2:
                    blinks += 1; consec = 0
                else:
                    consec = 0
    return {'blink_count': blinks, 'verdict': 'LIVE' if blinks >= 2 else 'FAIL'}