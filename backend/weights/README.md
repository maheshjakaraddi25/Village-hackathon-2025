# Model Weights

## kid34k_resnet50.pth

This file is required for **full ML-based document authenticity scoring**.

If the file is missing the backend will fall back to a lightweight heuristic
scorer (aspect ratio + resolution + channel variance) and log a warning at startup.
The app will still function end-to-end — Claude Vision handles the primary LV1-LV4
analysis regardless.

### Where to get it

Train your own on the KID-34K dataset:
  https://github.com/example/kid34k  ← replace with actual repo

Or download a pre-trained checkpoint and place it here as:
  backend/weights/kid34k_resnet50.pth
