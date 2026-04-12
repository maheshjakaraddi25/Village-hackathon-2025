"""
ID Verify AI — FastAPI Backend
VillageHacks 2026 · Notary Everyday
"""

import base64, json, re, time, os
from datetime import date, datetime
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from models.pipeline import run_local_pipeline
from rules.schema_patch import ensure_schema
from rules.compliance import enforce_compliance_rules
from rules.cross_doc import run_cross_doc_matching

app = FastAPI(title="ID Verify AI", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


def encode_image(content: bytes, mime_type: str) -> dict:
    return {"type": "image", "source": {
        "type": "base64", "media_type": mime_type,
        "data": base64.standard_b64encode(content).decode("utf-8")
    }}


def parse_json(raw: str) -> dict:
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()
    s, e = cleaned.find("{"), cleaned.rfind("}") + 1
    if s == -1 or e <= 0:
        raise ValueError("No JSON found in response")
    return json.loads(cleaned[s:e])


def compute_expiration(expiry_str: Optional[str]) -> dict:
    if not expiry_str:
        return {"is_expired": False, "days_until_expiry": None, "status": "UNKNOWN"}
    try:
        delta = (datetime.strptime(expiry_str, "%Y-%m-%d").date() - date.today()).days
        if delta < 0:   return {"is_expired": True,  "days_until_expiry": delta, "status": "EXPIRED"}
        if delta <= 30: return {"is_expired": False, "days_until_expiry": delta, "status": "EXPIRING_SOON"}
        return {"is_expired": False, "days_until_expiry": delta, "status": "VALID"}
    except ValueError:
        return {"is_expired": False, "days_until_expiry": None, "status": "UNKNOWN"}


SYSTEM_PROMPT = """You are an expert document verification AI for notary and KYC compliance.
Respond ONLY with valid JSON. No markdown, no preamble, no explanation outside the JSON.
Use null for unreadable fields. Never hallucinate values."""

USER_PROMPT = """Analyze this government-issued ID image and return ONLY this JSON:

{{
  "level1": {{
    "verdict": "PASS|FAIL|WARN",
    "verdict_message": "one sentence",
    "authenticity_score": 0.0,
    "checks": [
      {{"check": "Font Consistency", "result": "PASS|FAIL|WARN", "detail": "..."}},
      {{"check": "Field Format Validation", "result": "PASS|FAIL|WARN", "detail": "..."}},
      {{"check": "Security Features", "result": "PASS|FAIL|WARN", "detail": "..."}},
      {{"check": "Layout/AAMVA Compliance", "result": "PASS|FAIL|WARN", "detail": "..."}},
      {{"check": "MRZ Integrity", "result": "PASS|FAIL|WARN", "detail": "..."}}
    ],
    "flags": [{{"severity": "ERROR|WARN|OK", "message": "..."}}],
    "suspicious_elements": []
  }},
  "level2": {{
    "extracted_fields": {{
      "first_name": null, "last_name": null, "dob": null, "id_number": null,
      "expiration": null, "address": null, "license_class": null,
      "issuing_state": null, "issuing_country": null, "gender": null,
      "height": null, "eye_color": null
    }},
    "extraction_confidence": 0.0,
    "field_confidences": {{"first_name":0.0,"last_name":0.0,"dob":0.0,"id_number":0.0,"expiration":0.0,"address":0.0}},
    "ocr_issues": []
  }},
  "level3": {{
    "cross_doc_available": {cross_doc_bool},
    "comparisons": [{{"field":"last_name","id_value":null,"doc_value":null,"match":false,"confidence":0.0,"flag":"UNAVAILABLE"}}],
    "overall_match_score": 0.0,
    "identity_consistency": "INSUFFICIENT_DATA"
  }},
  "level4": {{
    "compliance_verdict": "PASS|FAIL|WARN",
    "compliance_flags": [{{"severity":"WARN","message":"...","rule_citation":"...","category":"EXPIRATION|IN_STATE|NAME_MATCH|FORMAT"}}],
    "expiration_status": {{"is_expired":false,"days_until_expiry":null,"status":"UNKNOWN"}},
    "overall_recommendation": "PROCEED|HOLD|REJECT",
    "recommendation_detail": "..."
  }},
  "summary": {{
    "overall_verdict": "PASS|FAIL|WARN",
    "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
    "key_findings": ["finding 1","finding 2"],
    "notary_action": "instruction for notary"
  }}
}}
{second_doc_note}"""


def mock_result(has_second: bool, ocr_fields: dict) -> dict:
    """Demo result that uses real OCR fields where available."""
    ef = ocr_fields or {}
    return {
        "level1": {
            "verdict": "WARN",
            "verdict_message": "Demo mode — connect an API key for full vision analysis.",
            "authenticity_score": 0.72,
            "checks": [
                {"check": "Font Consistency",       "result": "PASS", "detail": "Fonts appear consistent."},
                {"check": "Field Format Validation", "result": "WARN", "detail": "Cannot fully validate without vision API."},
                {"check": "Security Features",       "result": "WARN", "detail": "Not verified in demo mode."},
                {"check": "Layout/AAMVA Compliance", "result": "PASS", "detail": "Layout matches standard ID dimensions."},
                {"check": "MRZ Integrity",           "result": "WARN", "detail": "Not scanned in demo mode."},
            ],
            "flags": [{"severity": "WARN", "message": "Demo mode — set ANTHROPIC_API_KEY or GEMINI_API_KEY for full analysis."}],
            "suspicious_elements": []
        },
        "level2": {
            "extracted_fields": {
                "first_name":     ef.get("first_name"),
                "last_name":      ef.get("last_name"),
                "dob":            ef.get("dob"),
                "id_number":      ef.get("id_number"),
                "expiration":     ef.get("expiration"),
                "address":        ef.get("address"),
                "license_class":  None,
                "issuing_state":  ef.get("issuing_state"),
                "issuing_country":ef.get("issuing_country"),
                "gender":         ef.get("gender"),
                "height":         None,
                "eye_color":      None,
            },
            "extraction_confidence": round(
                sum(1 for f in ["first_name","last_name","dob","expiration","id_number"]
                    if ef.get(f)) / 5, 2),
            "field_confidences": {"first_name":0.8,"last_name":0.8,"dob":0.8,
                                  "id_number":0.8,"expiration":0.8,"address":0.7},
            "ocr_issues": [] if ef.get("first_name") else ["OCR could not extract fields — check image quality."]
        },
        "level3": {
            "cross_doc_available": has_second,
            "comparisons": [{"field":"last_name","id_value":None,"doc_value":None,
                             "match":False,"confidence":0.0,"flag":"UNAVAILABLE"}],
            "overall_match_score": 0.0,
            "identity_consistency": "INSUFFICIENT_DATA"
        },
        "level4": {
            "compliance_verdict": "WARN",
            "compliance_flags": [{"severity":"WARN","message":"Demo mode — compliance checks illustrative only.","rule_citation":"N/A","category":"FORMAT"}],
            "expiration_status": compute_expiration(ef.get("expiration")),
            "overall_recommendation": "HOLD",
            "recommendation_detail": "Connect a vision API for full compliance verification."
        },
        "summary": {
            "overall_verdict": "WARN",
            "risk_level": "MEDIUM",
            "key_findings": [
                f"OCR extracted: {', '.join(k for k in ['first_name','last_name','dob','id_number','expiration'] if ef.get(k)) or 'no fields'}.",
                "Vision API not connected — LV1-LV4 analysis is in demo mode.",
                "Set ANTHROPIC_API_KEY or GEMINI_API_KEY to enable full pipeline."
            ],
            "notary_action": "Manual review required — automated vision analysis not available in demo mode."
        }
    }


async def call_vision(id_bytes: bytes, id_mime: str,
                      doc2_bytes=None, doc2_mime=None,
                      ocr_fields: dict = None) -> dict:
    has_second = doc2_bytes is not None
    prompt = USER_PROMPT.format(
        cross_doc_bool="true" if has_second else "false",
        second_doc_note="A second supporting document is attached — use it for Level 3." if has_second
                        else "No second document provided; set level3.cross_doc_available to false."
    )

    # ── Anthropic ─────────────────────────────────────────────────────────────
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if anthropic_key:
        try:
            import anthropic as _a
            client = _a.Anthropic(api_key=anthropic_key)
            content = [encode_image(id_bytes, id_mime)]
            if has_second:
                content.append(encode_image(doc2_bytes, doc2_mime))
            content.append({"type": "text", "text": prompt})
            msg = client.messages.create(
                model="claude-sonnet-4-20250514", max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": content}]
            )
            return parse_json("".join(b.text for b in msg.content if hasattr(b, "text")))
        except Exception as e:
            print(f"[WARN] Anthropic failed: {e}")

    # ── Gemini (free) ─────────────────────────────────────────────────────────
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if gemini_key:
        try:
            import google.generativeai as genai
            import PIL.Image, io
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel("gemini-2.0-flash", system_instruction=SYSTEM_PROMPT)
            parts = [PIL.Image.open(io.BytesIO(id_bytes))]
            if has_second:
                parts.append(PIL.Image.open(io.BytesIO(doc2_bytes)))
            parts.append(prompt)
            return parse_json(model.generate_content(parts).text)
        except Exception as e:
            print(f"[WARN] Gemini failed: {e}")

    # ── Demo fallback ─────────────────────────────────────────────────────────
    print("[INFO] No API key — demo mode. Set ANTHROPIC_API_KEY or GEMINI_API_KEY for live analysis.")
    return mock_result(has_second, ocr_fields or {})


@app.get("/health")
def health():
    mode = "anthropic" if os.environ.get("ANTHROPIC_API_KEY") else \
           "gemini"    if os.environ.get("GEMINI_API_KEY")    else "demo"
    return {"status": "ok", "mode": mode}


@app.post("/verify")
async def verify(
    id_doc: UploadFile = File(...),
    support_doc: Optional[UploadFile] = File(None),
    selfie: Optional[UploadFile] = File(None),
):
    t0 = time.time()
    if id_doc.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(400, f"Unsupported mime type: {id_doc.content_type}")

    id_bytes    = await id_doc.read()
    selfie_bytes = await selfie.read()      if selfie      else None
    doc2_bytes   = await support_doc.read() if support_doc else None
    doc2_mime    = support_doc.content_type if support_doc else None

    # Stage A: local models
    local = await run_local_pipeline(id_bytes, selfie_bytes)
    ocr_fields = local["local"].get("ocr_fields", {})

    # Stage B: vision (passes OCR fields into demo mock)
    result = await call_vision(id_bytes, id_doc.content_type, doc2_bytes, doc2_mime, ocr_fields)
    result = ensure_schema(result)

    # Stage C: inject local model output
    result["local_models"] = local["local"]

    # Stage C2: overwrite level2 fields with real OCR values (beats demo placeholders)
    if ocr_fields:
        ef = result["level2"]["extracted_fields"]
        for f in ["first_name","last_name","dob","expiration","id_number",
                  "issuing_state","issuing_country","address","gender"]:
            if ocr_fields.get(f) is not None:
                ef[f] = ocr_fields[f]
        filled = sum(1 for f in ["first_name","last_name","dob","expiration","id_number"] if ef.get(f))
        result["level2"]["extraction_confidence"] = round(filled / 5, 2)

    # Stage D: server-side expiration
    expiry = result.get("level2", {}).get("extracted_fields", {}).get("expiration")
    result["level4"]["expiration_status"] = compute_expiration(expiry)

    # Stage E: cross-doc
    if doc2_bytes:
        result["level3"] = run_cross_doc_matching(
            id_fields=result["level2"]["extracted_fields"],
            support_doc_bytes=doc2_bytes
        )

    # Stage F: compliance
    result = enforce_compliance_rules(result)
    result["processing_time_ms"] = int((time.time() - t0) * 1000)

    return JSONResponse(content=result)
