from rapidfuzz import fuzz
from paddleocr import PaddleOCR
import cv2
import numpy as np
import re

_ocr = None


def _load_ocr():
    global _ocr
    if _ocr is None:
        _ocr = PaddleOCR(use_angle_cls=True, lang="en", use_gpu=False)
    return _ocr


def _normalize(s: str | None) -> str:
    if not s:
        return ""
    return re.sub(r"[^a-z0-9]", "", s.lower().strip())


def _fuzzy_match(a: str | None, b: str | None) -> dict:
    if not a or not b:
        return {"match": False, "confidence": 0.0, "flag": "UNAVAILABLE"}

    na, nb = _normalize(a), _normalize(b)
    if na == nb:
        return {"match": True, "confidence": 0.99, "flag": "MATCH"}

    score = fuzz.ratio(na, nb) / 100.0

    if score >= 0.85:
        return {"match": True, "confidence": round(score, 3), "flag": "MATCH"}
    elif score >= 0.60:
        return {"match": False, "confidence": round(score, 3), "flag": "PARTIAL_MATCH"}
    else:
        return {"match": False, "confidence": round(score, 3), "flag": "MISMATCH"}


def _ocr_text(img_bytes: bytes) -> str:
    arr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return ""

    result = _load_ocr().ocr(img, cls=True)
    lines = [w[1][0] for line in result for w in line]
    return "\n".join(lines)


def run_cross_doc_matching(id_fields: dict, support_doc_bytes: bytes) -> dict:
    text = _ocr_text(support_doc_bytes)

    # naive extraction from support doc
    doc_name = None
    doc_dob = None
    doc_address = None

    m = re.search(r"Name[:\s]+([A-Za-z\s]+)", text, re.IGNORECASE)
    if m:
        doc_name = m.group(1).strip()

    m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if m:
        doc_dob = m.group(1)

    m = re.search(r"(\d+\s+\w[\w\s,]+(?:ST|AVE|DR|RD|BLVD|LN)[,.\s]+\w[\w\s]+\d{5})", text, re.IGNORECASE)
    if m:
        doc_address = m.group(1).strip()

    comparisons = []

    # last name match
    id_last = id_fields.get("last_name")
    doc_last = doc_name.split()[-1] if doc_name else None
    r = _fuzzy_match(id_last, doc_last)
    comparisons.append({
        "field": "last_name",
        "id_value": id_last,
        "doc_value": doc_last,
        "match": r["match"],
        "confidence": r["confidence"],
        "flag": r["flag"]
    })

    # first name match
    id_first = id_fields.get("first_name")
    doc_first = doc_name.split()[0] if doc_name else None
    r = _fuzzy_match(id_first, doc_first)
    comparisons.append({
        "field": "first_name",
        "id_value": id_first,
        "doc_value": doc_first,
        "match": r["match"],
        "confidence": r["confidence"],
        "flag": r["flag"]
    })

    # dob exact match
    id_dob = id_fields.get("dob")
    if id_dob and doc_dob:
        match = id_dob == doc_dob
        comparisons.append({
            "field": "dob",
            "id_value": id_dob,
            "doc_value": doc_dob,
            "match": match,
            "confidence": 0.99 if match else 0.0,
            "flag": "MATCH" if match else "MISMATCH"
        })
    else:
        comparisons.append({
            "field": "dob",
            "id_value": id_dob,
            "doc_value": doc_dob,
            "match": False,
            "confidence": 0.0,
            "flag": "UNAVAILABLE"
        })

    # address fuzzy
    id_addr = id_fields.get("address")
    r = _fuzzy_match(id_addr, doc_address)
    comparisons.append({
        "field": "address",
        "id_value": id_addr,
        "doc_value": doc_address,
        "match": r["match"],
        "confidence": r["confidence"],
        "flag": r["flag"]
    })

    score = sum(c["confidence"] for c in comparisons) / len(comparisons)

    if score >= 0.85:
        consistency = "CONSISTENT"
    elif score >= 0.60:
        consistency = "PARTIAL"
    elif score > 0.0:
        consistency = "INCONSISTENT"
    else:
        consistency = "INSUFFICIENT_DATA"

    return {
        "cross_doc_available": True,
        "comparisons": comparisons,
        "overall_match_score": round(score, 3),
        "identity_consistency": consistency
    }