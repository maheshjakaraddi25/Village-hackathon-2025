from typing import Optional
import re
import cv2
import numpy as np
from rapidfuzz import fuzz

# Reuse the same extraction logic as the primary ID
from models.ocr_extractor import extract_id_fields, normalize_date


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
        return {"match": True,  "confidence": round(score, 3), "flag": "MATCH"}
    elif score >= 0.60:
        return {"match": False, "confidence": round(score, 3), "flag": "PARTIAL_MATCH"}
    else:
        return {"match": False, "confidence": round(score, 3), "flag": "MISMATCH"}


def run_cross_doc_matching(id_fields: dict, support_doc_bytes: bytes) -> dict:
    # Use exact same extractor as primary ID — consistent parsing guaranteed
    doc_fields = extract_id_fields(support_doc_bytes)

    comparisons = []

    # ── Last name ─────────────────────────────────────────────────────────────
    r = _fuzzy_match(id_fields.get("last_name"), doc_fields.get("last_name"))
    comparisons.append({"field": "last_name",
                        "id_value": id_fields.get("last_name"),
                        "doc_value": doc_fields.get("last_name"), **r})

    # ── First name ────────────────────────────────────────────────────────────
    r = _fuzzy_match(id_fields.get("first_name"), doc_fields.get("first_name"))
    comparisons.append({"field": "first_name",
                        "id_value": id_fields.get("first_name"),
                        "doc_value": doc_fields.get("first_name"), **r})

    # ── DOB ───────────────────────────────────────────────────────────────────
    id_dob, doc_dob = id_fields.get("dob"), doc_fields.get("dob")
    if id_dob and doc_dob:
        match = id_dob == doc_dob
        comparisons.append({"field": "dob", "id_value": id_dob, "doc_value": doc_dob,
                             "match": match, "confidence": 0.99 if match else 0.0,
                             "flag": "MATCH" if match else "MISMATCH"})
    else:
        comparisons.append({"field": "dob", "id_value": id_dob, "doc_value": doc_dob,
                             "match": False, "confidence": 0.0, "flag": "UNAVAILABLE"})

    # ── Address ───────────────────────────────────────────────────────────────
    r = _fuzzy_match(id_fields.get("address"), doc_fields.get("address"))
    comparisons.append({"field": "address",
                        "id_value": id_fields.get("address"),
                        "doc_value": doc_fields.get("address"), **r})

    # ── ID number ─────────────────────────────────────────────────────────────
    r = _fuzzy_match(id_fields.get("id_number"), doc_fields.get("id_number"))
    comparisons.append({"field": "id_number",
                        "id_value": id_fields.get("id_number"),
                        "doc_value": doc_fields.get("id_number"), **r})

    # ── Nationality ───────────────────────────────────────────────────────────
    r = _fuzzy_match(id_fields.get("issuing_country"), doc_fields.get("issuing_country"))
    comparisons.append({"field": "nationality",
                        "id_value": id_fields.get("issuing_country"),
                        "doc_value": doc_fields.get("issuing_country"), **r})

    score = sum(c["confidence"] for c in comparisons) / len(comparisons)
    consistency = (
        "CONSISTENT"        if score >= 0.85 else
        "PARTIAL"           if score >= 0.60 else
        "INCONSISTENT"      if score >  0.0  else
        "INSUFFICIENT_DATA"
    )

    return {
        "cross_doc_available":  True,
        "doc_extracted_fields": doc_fields,
        "comparisons":          comparisons,
        "overall_match_score":  round(score, 3),
        "identity_consistency": consistency,
    }