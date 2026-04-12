from typing import Optional
from rapidfuzz import fuzz
from paddleocr import PaddleOCR
import cv2
import numpy as np
import re

_ocr = None


def _load_ocr():
    global _ocr
    if _ocr is None:
        _ocr = PaddleOCR(use_angle_cls=True, lang="en")
    return _ocr


def _normalize(s: Optional[str]) -> str:
    if not s:
        return ""
    return re.sub(r"[^a-z0-9]", "", s.lower().strip())


def _fuzzy_match(a: Optional[str], b: Optional[str]) -> dict:
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

    result = _load_ocr().ocr(img)
    lines = [w[1][0] for line in result for w in line]
    return "\n".join(lines)


# ── Label synonym patterns ─────────────────────────────────────────────────────

NAME_PATTERN = (
    r"(?:full\s*name|complete\s*name|test\s*name|holder|applicant\s*name|"
    r"sur\s*name|family\s*name|last\s*name|given\s*name s?|first\s*name|"
    r"fore\s*name|pr[eé]nom|vorname|apellido|nom\s*de\s*famille|nachname|"
    r"cognome|nombre|nome|(?<!\w)name(?!\s*\d)(?!\s*of\s*(?:document|state|country|post)))"
)

DOB_PATTERN = (
    r"(?:date\s*of\s*birth|birth\s*date|birth\s*day|born|"
    r"d\.?\s*o\.?\s*b\.?|dob|fecha\s*de\s*nacimiento|"
    r"date\s*naissance|geburtsdatum|data\s*di\s*nascita|"
    r"geboortedatum|dt\.?\s*of\s*birth)"
)

ADDRESS_PATTERN = (
    r"(?:(?<!\w)address(?!\w)|residence|domicile|home\s*address|"
    r"mailing\s*address|permanent\s*address|residential\s*address|"
    r"direcci[oó]n|adresse|indirizzo|wohnort|wohnanschrift)"
)


def _extract_by_label(text: str, pattern: str) -> Optional[str]:
    """Extract value appearing after a label on same or next line."""
    # Same line: "Name: John Doe"
    m = re.search(pattern + r'[\s:]+([^\n\r]{1,80})', text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


def run_cross_doc_matching(id_fields: dict, support_doc_bytes: bytes) -> dict:
    text = _ocr_text(support_doc_bytes)

    # ── Extract fields from supporting doc using synonyms ─────────────────────
    doc_name    = _extract_by_label(text, NAME_PATTERN)
    doc_dob     = None
    doc_address = _extract_by_label(text, ADDRESS_PATTERN)

    # DOB: try label-based first, then bare date pattern
    dob_raw = _extract_by_label(text, DOB_PATTERN)
    if dob_raw:
        m = re.search(r'\b(\d{4}-\d{2}-\d{2}|\d{2}[-/]\d{2}[-/]\d{4})\b', dob_raw)
        if m:
            doc_dob = m.group(1)
    if not doc_dob:
        m = re.search(r'\b(\d{4}-\d{2}-\d{2})\b', text)
        if m:
            doc_dob = m.group(1)

    # Fallback address: street pattern
    if not doc_address:
        m = re.search(
            r'(\d+\s+\w[\w\s,]+(?:ST|AVE|DR|RD|BLVD|LN|STREET|ROAD|LANE)[,.\s][\w\s,]+\d{4,6})',
            text, re.IGNORECASE
        )
        if m:
            doc_address = m.group(1).strip()

    # Split doc_name into first/last
    doc_last  = doc_name.split()[-1] if doc_name else None
    doc_first = doc_name.split()[0]  if doc_name else None

    # ── Comparisons ───────────────────────────────────────────────────────────
    comparisons = []

    r = _fuzzy_match(id_fields.get("last_name"), doc_last)
    comparisons.append({"field": "last_name",  "id_value": id_fields.get("last_name"),
                         "doc_value": doc_last,  **r})

    r = _fuzzy_match(id_fields.get("first_name"), doc_first)
    comparisons.append({"field": "first_name", "id_value": id_fields.get("first_name"),
                         "doc_value": doc_first, **r})

    id_dob = id_fields.get("dob")
    if id_dob and doc_dob:
        match = id_dob == doc_dob
        comparisons.append({"field": "dob", "id_value": id_dob, "doc_value": doc_dob,
                             "match": match, "confidence": 0.99 if match else 0.0,
                             "flag": "MATCH" if match else "MISMATCH"})
    else:
        comparisons.append({"field": "dob", "id_value": id_dob, "doc_value": doc_dob,
                             "match": False, "confidence": 0.0, "flag": "UNAVAILABLE"})

    r = _fuzzy_match(id_fields.get("address"), doc_address)
    comparisons.append({"field": "address", "id_value": id_fields.get("address"),
                         "doc_value": doc_address, **r})

    score = sum(c["confidence"] for c in comparisons) / len(comparisons)
    consistency = (
        "CONSISTENT"        if score >= 0.85 else
        "PARTIAL"           if score >= 0.60 else
        "INCONSISTENT"      if score >  0.0  else
        "INSUFFICIENT_DATA"
    )

    return {
        "cross_doc_available":  True,
        "comparisons":          comparisons,
        "overall_match_score":  round(score, 3),
        "identity_consistency": consistency,
    }