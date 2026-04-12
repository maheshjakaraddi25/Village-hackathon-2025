import torch
from torchvision import transforms, models
from PIL import Image
from pathlib import Path
import io
import logging

logger = logging.getLogger(__name__)

_model = None

BASE_DIR = Path(__file__).resolve().parent.parent
WEIGHT_PATH = BASE_DIR / "weights" / "kid34k_resnet50.pth"


def _load():
    global _model
    if _model is None:
        m = models.resnet50(weights=None)
        m.fc = torch.nn.Linear(2048, 2)
        if WEIGHT_PATH.exists():
            m.load_state_dict(torch.load(WEIGHT_PATH, map_location="cpu"))
            logger.info("Loaded authenticity weights from %s", WEIGHT_PATH)
        else:
            logger.warning(
                "Weight file not found at %s — using heuristic scoring. "
                "Place kid34k_resnet50.pth in backend/weights/ for full ML scoring.",
                WEIGHT_PATH,
            )
        m.eval()
        _model = m
    return _model


_transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])


def _heuristic_score(img: Image.Image) -> float:
    """
    Lightweight fallback when ML weights are unavailable.
    Checks basic image properties: resolution, aspect ratio, and channel variance.
    """
    w, h = img.size
    aspect = w / max(h, 1)
    # Standard ID card is ~1.586:1 (ISO/IEC 7810 ID-1)
    aspect_ok = 1.3 <= aspect <= 1.9
    res_ok = w >= 300 and h >= 190

    import numpy as np
    arr = transforms.ToTensor()(img).numpy()
    channel_var = float(arr.var())
    not_blank = channel_var > 0.002

    score = (0.4 if aspect_ok else 0.1) + (0.3 if res_ok else 0.0) + (0.3 if not_blank else 0.0)
    return round(score, 3)


def score_authenticity(img_bytes: bytes) -> dict:
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")

    if not WEIGHT_PATH.exists():
        score = _heuristic_score(img)
        verdict = "PASS" if score > 0.7 else "WARN" if score > 0.4 else "FAIL"
        return {
            "score": score,
            "verdict": verdict,
            "note": "heuristic_only — weights file missing",
        }

    with torch.no_grad():
        logits = _load()(_transform(img).unsqueeze(0))
        prob_genuine = torch.softmax(logits, dim=1)[0][0].item()

    verdict = "PASS" if prob_genuine > 0.7 else "WARN" if prob_genuine > 0.4 else "FAIL"

    return {
        "score": round(prob_genuine, 3),
        "verdict": verdict,
    }
