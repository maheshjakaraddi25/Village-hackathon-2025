import torch
from torchvision import transforms, models
from PIL import Image

_model = None

def _load():
    global _model
    if _model is None:
        m = models.resnet50()
        m.fc = torch.nn.Linear(2048, 2)
        m.load_state_dict(torch.load('weights/kid34k_resnet50.pth', map_location='cpu'))
        m.eval()
        _model = m
    return _model

_transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485,0.456,0.406],[0.229,0.224,0.225])
])

def score_authenticity(img_bytes: bytes) -> dict:
    img = Image.open(__import__('io').BytesIO(img_bytes)).convert('RGB')
    with torch.no_grad():
        logits = _load()(_transform(img).unsqueeze(0))
        prob = torch.softmax(logits, dim=1)[0][0].item()
    verdict = 'PASS' if prob > 0.7 else 'WARN' if prob > 0.4 else 'FAIL'
    return {'score': round(prob, 3), 'verdict': verdict}