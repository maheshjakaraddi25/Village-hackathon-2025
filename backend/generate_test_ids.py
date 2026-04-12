"""
Synthetic ID Generator — VillageHacks 2026
Generates fake driver's license images for testing without using real PII.
Usage: python generate_test_ids.py
Output: synthetic_data/ directory with labeled genuine/fraud samples.
"""

import json
import os
import random
from datetime import date, timedelta
from pathlib import Path

from faker import Faker
from PIL import Image, ImageDraw, ImageFont

fake = Faker()
OUT_DIR = Path(__file__).parent / "synthetic_data"
OUT_DIR.mkdir(exist_ok=True)

STATES = ["CO", "CA", "TX", "FL", "NY", "WA", "AZ", "OR", "NV", "UT"]
LICENSE_CLASSES = ["A", "B", "C", "D", "M"]
EYE_COLORS = ["BRN", "BLU", "GRN", "HZL", "GRY", "AMB"]
HAIR_COLORS = ["BRN", "BLK", "BLD", "RED", "GRY", "WHI"]

# Colors
BG_COLORS = {
    "CO": "#e8f4f8",
    "CA": "#fef9e7",
    "TX": "#f0f8ff",
    "FL": "#fff0f5",
    "NY": "#f0fff0",
}
ACCENT_COLORS = {
    "CO": "#1a5276",
    "CA": "#922b21",
    "TX": "#1a5276",
    "FL": "#0e6655",
    "NY": "#1a5276",
}


def random_license_number(state: str) -> str:
    patterns = {
        "CO": lambda: f"{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}{random.randint(100000000, 999999999)}",
        "CA": lambda: f"{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}{random.randint(1000000, 9999999)}",
        "TX": lambda: f"{random.randint(10000000, 99999999)}",
        "FL": lambda: f"{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}{random.randint(100000000, 999999999):09d}",
        "NY": lambda: f"{random.randint(100000000, 999999999)}",
    }
    fn = patterns.get(state, patterns["CO"])
    return fn()


def make_id(fraud_type: str = "none") -> dict:
    """Generate a synthetic ID record. fraud_type: none | expired | wrong_format | mismatch"""
    state = random.choice(STATES)
    dob = fake.date_of_birth(minimum_age=18, maximum_age=75)

    if fraud_type == "expired":
        exp = date.today() - timedelta(days=random.randint(10, 1000))
    elif fraud_type == "expiring_soon":
        exp = date.today() + timedelta(days=random.randint(1, 29))
    else:
        exp = date.today() + timedelta(days=random.randint(90, 1825))

    if fraud_type == "wrong_format":
        dob_str = dob.strftime("%m/%d/%y")  # Wrong: should be MM/DD/YYYY
    else:
        dob_str = dob.strftime("%m/%d/%Y")

    license_num = random_license_number(state)

    return {
        "first_name": fake.first_name(),
        "last_name": fake.last_name(),
        "middle_name": fake.first_name() if random.random() > 0.4 else "",
        "dob": dob_str,
        "dob_iso": dob.isoformat(),
        "address": fake.street_address(),
        "city": fake.city(),
        "state": state,
        "zip": fake.zipcode(),
        "license_number": license_num,
        "expiration": exp.strftime("%m/%d/%Y"),
        "expiration_iso": exp.isoformat(),
        "license_class": random.choice(LICENSE_CLASSES),
        "sex": random.choice(["M", "F"]),
        "height": f"{random.randint(4, 6)}-{random.randint(0, 11):02d}",
        "weight": str(random.randint(100, 250)),
        "eye_color": random.choice(EYE_COLORS),
        "hair_color": random.choice(HAIR_COLORS),
        "dd": f"{random.randint(100000000, 999999999):09d}/{random.randint(10000, 99999)}",
        "label": "genuine" if fraud_type == "none" else f"fraud_{fraud_type}",
        "fraud_type": fraud_type,
    }


def draw_id_card(data: dict, fraud_type: str = "none") -> Image.Image:
    """Render a fake driver's license image."""
    W, H = 856, 540  # Standard DL aspect ratio (85.6mm × 54mm at 254dpi)
    state = data["state"]

    bg_color = BG_COLORS.get(state, "#f0f4f8")
    accent = ACCENT_COLORS.get(state, "#1a5276")

    img = Image.new("RGB", (W, H), bg_color)
    draw = ImageDraw.Draw(img)

    # Header bar
    draw.rectangle([(0, 0), (W, 70)], fill=accent)

    # Deliberately bad font for fraud simulation
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        label_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
        value_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 15)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
        if fraud_type == "font_mismatch":
            # Use a noticeably different font for some fields to simulate fraud
            value_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 15)
    except OSError:
        title_font = label_font = value_font = small_font = ImageFont.load_default()

    # State name and DL title
    draw.text((20, 15), f"STATE OF {state}", font=title_font, fill="white")
    draw.text((20, 42), "DRIVER LICENSE", font=label_font, fill="#aed6f1")

    # Photo placeholder
    draw.rectangle([(20, 85), (195, 295)], fill="#d5d8dc", outline=accent, width=2)
    draw.text((55, 175), "PHOTO", font=label_font, fill="#808b96")
    draw.text((35, 195), "SYNTHETIC ID", font=small_font, fill="#808b96")

    # Watermark for synthetic
    draw.text((30, 440), "⚠ SYNTHETIC TEST DOCUMENT — NOT A REAL ID", font=small_font, fill="#e74c3c")

    # Fields — right panel
    x_label = 215
    x_val = 215
    y = 90

    def field(label: str, value: str, color: str = "#1a1a2e"):
        nonlocal y
        draw.text((x_label, y), label, font=label_font, fill="#717d7e")
        y += 18
        draw.text((x_val, y), value, font=value_font, fill=color)
        y += 26

    full_name = f"{data['last_name']}, {data['first_name']}"
    if data.get("middle_name"):
        full_name += f" {data['middle_name'][0]}"

    field("NAME", full_name)
    field("ADDRESS", data["address"])
    field("", f"{data['city']}, {data['state']} {data['zip']}")
    field("DOB", data["dob"], color="#e74c3c" if fraud_type == "wrong_format" else "#1a1a2e")
    field("DL NO.", data["license_number"])
    field("EXPIRES", data["expiration"], color="#e74c3c" if data["fraud_type"] in ("expired", "expiring_soon") else "#1a1a2e")
    field("CLASS", data["license_class"])

    # Right column
    y2 = 90
    x2 = 540

    def field2(label: str, value: str):
        nonlocal y2
        draw.text((x2, y2), label, font=label_font, fill="#717d7e")
        y2 += 18
        draw.text((x2, y2), value, font=value_font, fill="#1a1a2e")
        y2 += 26

    field2("SEX", data["sex"])
    field2("HGT", data["height"])
    field2("WGT", f"{data['weight']} lb")
    field2("EYES", data["eye_color"])
    field2("HAIR", data["hair_color"])

    # PDF417 barcode placeholder
    for i in range(0, 200, 4):
        h = random.randint(20, 60)
        draw.rectangle([(215 + i, H - 90), (215 + i + 2, H - 90 + h)], fill="#1a1a2e")

    draw.text((215, H - 25), f"DD {data['dd']}", font=small_font, fill="#808b96")

    # Fraud overlay effects
    if fraud_type == "glare":
        # Simulate glare
        for _ in range(3):
            gx = random.randint(0, W)
            gy = random.randint(0, H)
            for r in range(30, 0, -5):
                draw.ellipse([(gx - r, gy - r), (gx + r, gy + r)],
                             fill=(255, 255, 255, max(0, 60 - r * 2)))

    return img


def generate_dataset(n_per_type: int = 5):
    """Generate n samples per fraud type."""
    fraud_types = ["none", "expired", "expiring_soon", "wrong_format", "font_mismatch", "glare"]
    manifest = []

    for ft in fraud_types:
        for i in range(n_per_type):
            data = make_id(fraud_type=ft)
            img = draw_id_card(data, fraud_type=ft)
            fname = f"{ft}_{i:03d}.png"
            fpath = OUT_DIR / fname
            img.save(fpath, "PNG")

            record = {**data, "image_path": str(fpath), "filename": fname}
            manifest.append(record)
            print(f"  ✓ {fname}")

    manifest_path = OUT_DIR / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n✅ Generated {len(manifest)} synthetic IDs → {OUT_DIR}")
    print(f"📋 Manifest → {manifest_path}")
    return manifest


if __name__ == "__main__":
    print("🪪 Synthetic ID Generator — VillageHacks 2026\n")
    generate_dataset(n_per_type=5)