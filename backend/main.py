"""
ID Verify AI — FastAPI Backend
VillageHacks 2026 · Notary Everyday

Full pipeline: Level 1 (Authenticity) → Level 2 (Extraction) → Level 3 (Cross-Doc) → Level 4 (Compliance)
"""

import base64
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import anthropic
import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(title="ID Verify AI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_FILE_SIZE_MB = 10


# ─── Pydantic models ──────────────────────────────────────────────────────────

class FlagItem(BaseModel):
    severity: str  # ERROR | WARN | OK
    message: str
    rule_citation: Optional[str] = None
    category: Optional[str] = None


class CheckItem(BaseModel):
    check: str
    result: str  # PASS | FAIL | WARN
    detail: str


class Level1Result(BaseModel):
    verdict: str
    verdict_message: str
    authenticity_score: float
    checks: list[CheckItem]
    flags: list[FlagItem]
    suspicious_elements: list[str]


class ExtractedFields(BaseModel):
    first_name: Optional[str]
    last_name: Optional[str]
    dob: Optional[str]
    id_number: Optional[str]
    expiration: Optional[str]
    address: Optional[str]
    license_class: Optional[str]
    issuing_state: Optional[str]
    issuing_country: Optional[str]
    gender: Optional[str]
    height: Optional[str]
    eye_color: Optional[str]


class Level2Result(BaseModel):
    extracted_fields: ExtractedFields
    extraction_confidence: float
    field_confidences: dict[str, float]
    ocr_issues: list[str]


class ComparisonItem(BaseModel):
    field: str
    id_value: Optional[str]
    doc_value: Optional[str]
    match: bool
    confidence: float
    flag: str  # MATCH | MISMATCH | PARTIAL_MATCH | UNAVAILABLE


class Level3Result(BaseModel):
    cross_doc_available: bool
    comparisons: list[ComparisonItem]
    overall_match_score: float
    identity_consistency: str  # CONSISTENT | INCONSISTENT | PARTIAL | INSUFFICIENT_DATA


class ExpirationStatus(BaseModel):
    is_expired: bool
    days_until_expiry: Optional[int]
    status: str  # VALID | EXPIRED | EXPIRING_SOON | UNKNOWN


class Level4Result(BaseModel):
    compliance_verdict: str
    compliance_flags: list[FlagItem]
    expiration_status: ExpirationStatus
    overall_recommendation: str  # PROCEED | HOLD | REJECT
    recommendation_detail: str


class Summary(BaseModel):
    overall_verdict: str
    risk_level: str  # LOW | MEDIUM | HIGH | CRITICAL
    key_findings: list[str]
    notary_action: str


class VerificationResult(BaseModel):
    level1: Level1Result
    level2: Level2Result
    level3: Level3Result
    level4: Level4Result
    summary: Summary
    processing_time_ms: int


# ─── Helpers ──────────────────────────────────────────────────────────────────

def encode_image(content: bytes, mime_type: str) -> dict:
    """Encode image bytes to Anthropic vision content block."""
    b64 = base64.standard_b64encode(content).decode("utf-8")
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": mime_type, "data": b64},
    }


def parse_claude_json(raw: str) -> dict:
    """Strip markdown fences and parse JSON from Claude response."""
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()
    # Find first { ... } block
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON object found in Claude response")
    return json.loads(cleaned[start:end])


def compute_expiration_details(expiry_str: Optional[str]) -> dict:
    """Calculate days until expiry from YYYY-MM-DD string."""
    if not expiry_str:
        return {"is_expired": False, "days_until_expiry": None, "status": "UNKNOWN"}
    try:
        exp_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
        today = date.today()
        delta = (exp_date - today).days
        if delta < 0:
            return {"is_expired": True, "days_until_expiry": delta, "status": "EXPIRED"}
        elif delta <= 30:
            return {"is_expired": False, "days_until_expiry": delta, "status": "EXPIRING_SOON"}
        else:
            return {"is_expired": False, "days_until_expiry": delta, "status": "VALID"}
    except ValueError:
        return {"is_expired": False, "days_until_expiry": None, "status": "UNKNOWN"}


# ─── Core Claude call ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert document verification AI for notary and KYC compliance.
You analyze government-issued ID documents and supporting documents for:
- Document authenticity (font consistency, field formats, security features, layout)
- Data extraction into structured fields
- Cross-document identity matching
- Compliance flagging (expiration, in-state requirements, name mismatches)

CRITICAL: Respond ONLY with valid JSON matching the exact schema requested.
No markdown, no preamble, no explanation outside the JSON object.
Use null for fields you cannot read. Never hallucinate field values.
When uncertain, use WARN verdicts rather than hard PASS or FAIL."""

USER_PROMPT_TEMPLATE = """Analyze the provided government-issued ID document image for a notarization/KYC workflow.
{second_doc_note}

Perform ALL four verification levels and return a single JSON object with this EXACT structure:

{{
  "level1": {{
    "verdict": "PASS" | "FAIL" | "WARN",
    "verdict_message": "one sentence",
    "authenticity_score": 0.0-1.0,
    "checks": [
      {{"check": "Font Consistency", "result": "PASS|FAIL|WARN", "detail": "..."}},
      {{"check": "Field Format Validation", "result": "PASS|FAIL|WARN", "detail": "..."}},
      {{"check": "Security Features", "result": "PASS|FAIL|WARN", "detail": "..."}},
      {{"check": "Layout/AAMVA Compliance", "result": "PASS|FAIL|WARN", "detail": "..."}},
      {{"check": "MRZ Integrity", "result": "PASS|FAIL|WARN", "detail": "..."}}
    ],
    "flags": [
      {{"severity": "ERROR|WARN|OK", "message": "..."}}
    ],
    "suspicious_elements": []
  }},
  "level2": {{
    "extracted_fields": {{
      "first_name": null,
      "last_name": null,
      "dob": "YYYY-MM-DD or null",
      "id_number": null,
      "expiration": "YYYY-MM-DD or null",
      "address": null,
      "license_class": null,
      "issuing_state": "2-letter or null",
      "issuing_country": null,
      "gender": null,
      "height": null,
      "eye_color": null
    }},
    "extraction_confidence": 0.0-1.0,
    "field_confidences": {{
      "first_name": 0.0-1.0,
      "last_name": 0.0-1.0,
      "dob": 0.0-1.0,
      "id_number": 0.0-1.0,
      "expiration": 0.0-1.0,
      "address": 0.0-1.0
    }},
    "ocr_issues": []
  }},
  "level3": {{
    "cross_doc_available": {cross_doc_bool},
    "comparisons": [
      {{
        "field": "last_name",
        "id_value": null,
        "doc_value": null,
        "match": false,
        "confidence": 0.0,
        "flag": "MATCH|MISMATCH|PARTIAL_MATCH|UNAVAILABLE"
      }}
    ],
    "overall_match_score": 0.0,
    "identity_consistency": "CONSISTENT|INCONSISTENT|PARTIAL|INSUFFICIENT_DATA"
  }},
  "level4": {{
    "compliance_verdict": "PASS" | "FAIL" | "WARN",
    "compliance_flags": [
      {{
        "severity": "ERROR|WARN|OK",
        "message": "...",
        "rule_citation": "NIST IAL2 / MISMO / state law / etc.",
        "category": "EXPIRATION|IN_STATE|NAME_MATCH|NOTARY_COMMISSION|FORMAT"
      }}
    ],
    "expiration_status": {{
      "is_expired": false,
      "days_until_expiry": null,
      "status": "VALID|EXPIRED|EXPIRING_SOON|UNKNOWN"
    }},
    "overall_recommendation": "PROCEED|HOLD|REJECT",
    "recommendation_detail": "..."
  }},
  "summary": {{
    "overall_verdict": "PASS" | "FAIL" | "WARN",
    "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
    "key_findings": ["finding 1", "finding 2", "finding 3"],
    "notary_action": "specific instruction for notary"
  }}
}}

Key compliance rules to apply:
- NIST IAL2: expired IDs are automatic FAIL for RON platforms
- Most states allow IDs expired within 5 years for in-person notarization
- Flag IDs expiring within 30 days as EXPIRING_SOON (⚠ warn, not hard fail)
- TX and FL require in-state ID for certain property transactions
- MISMO: notary must record ID type + expiration in closing package
- Name mismatches: "Jennifer" vs "Jen" = PARTIAL_MATCH, not MISMATCH
- Middle name omissions = PARTIAL_MATCH, suffix mismatches = flag but soft fail
"""


async def call_claude(id_bytes: bytes, id_mime: str,
                      doc2_bytes: Optional[bytes] = None,
                      doc2_mime: Optional[str] = None) -> dict:
    """Call Claude claude-sonnet-4-20250514 with vision for full pipeline analysis."""
    has_second = doc2_bytes is not None

    content = [encode_image(id_bytes, id_mime)]
    if has_second:
        content.append(encode_image(doc2_bytes, doc2_mime))

    prompt = USER_PROMPT_TEMPLATE.format(
        second_doc_note=(
            "A second supporting document is also attached. Use it for Level 3 cross-document analysis."
            if has_second else
            "No second document provided; set level3.cross_doc_available to false."
        ),
        cross_doc_bool="true" if has_second else "false",
    )
    content.append({"type": "text", "text": prompt})

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )

    raw = "".join(b.text for b in message.content if hasattr(b, "text"))
    return parse_claude_json(raw)


# ─── Post-processing: enrich expiration from extracted fields ─────────────────

def enrich_expiration(result: dict) -> dict:
    """Recalculate expiration details server-side using today's real date."""
    expiry = result.get("level2", {}).get("extracted_fields", {}).get("expiration")
    computed = compute_expiration_details(expiry)
    if "level4" not in result:
        result["level4"] = {}
    result["level4"]["expiration_status"] = computed

    # Also add expiring-soon compliance flag if needed
    if computed["status"] == "EXPIRING_SOON":
        days = computed["days_until_expiry"]
        flags = result["level4"].get("compliance_flags", [])
        flags.insert(0, {
            "severity": "WARN",
            "message": f"⚠ ID expires in {days} days — verify acceptability with signing parties",
            "rule_citation": "General notary best practice",
            "category": "EXPIRATION",
        })
        result["level4"]["compliance_flags"] = flags
    elif computed["status"] == "EXPIRED":
        flags = result["level4"].get("compliance_flags", [])
        flags.insert(0, {
            "severity": "ERROR",
            "message": f"ID is expired (expired {abs(computed['days_until_expiry'])} days ago) — automatic FAIL under NIST IAL2",
            "rule_citation": "NIST SP 800-63-3 IAL2",
            "category": "EXPIRATION",
        })
        result["level4"]["compliance_flags"] = flags
        result["level4"]["compliance_verdict"] = "FAIL"
        result["level4"]["overall_recommendation"] = "REJECT"
        result["summary"]["overall_verdict"] = "FAIL"
        result["summary"]["risk_level"] = "CRITICAL"

    return result


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "model": "claude-sonnet-4-20250514"}


@app.post("/verify", response_model=VerificationResult)
async def verify(
    id_doc: UploadFile = File(..., description="Primary ID image"),
    support_doc: Optional[UploadFile] = File(None, description="Second doc (loan app, deed, etc.)"),
):
    import time
    t0 = time.time()

    # Validate primary ID
    if id_doc.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(400, f"Unsupported file type: {id_doc.content_type}. Use JPEG, PNG, or WebP.")

    id_bytes = await id_doc.read()
    if len(id_bytes) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(413, f"ID file too large (max {MAX_FILE_SIZE_MB}MB)")

    doc2_bytes, doc2_mime = None, None
    if support_doc and support_doc.filename:
        if support_doc.content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(400, f"Unsupported second doc type: {support_doc.content_type}")
        doc2_bytes = await support_doc.read()
        doc2_mime = support_doc.content_type

    try:
        raw_result = await call_claude(id_bytes, id_doc.content_type, doc2_bytes, doc2_mime)
    except json.JSONDecodeError as e:
        raise HTTPException(502, f"Claude returned invalid JSON: {e}")
    except anthropic.APIError as e:
        raise HTTPException(502, f"Anthropic API error: {e}")

    raw_result = enrich_expiration(raw_result)
    raw_result["processing_time_ms"] = int((time.time() - t0) * 1000)

    return JSONResponse(content=raw_result)


@app.post("/synthetic-test")
async def synthetic_test():
    """Return a pre-baked synthetic result for demo/testing without uploading a real image."""
    return JSONResponse(content=SYNTHETIC_DEMO_RESULT)


# ─── Synthetic demo data ──────────────────────────────────────────────────────

SYNTHETIC_DEMO_RESULT = {
    "level1": {
        "verdict": "WARN",
        "verdict_message": "Document appears genuine with minor inconsistencies in font rendering on DOB field.",
        "authenticity_score": 0.74,
        "checks": [
            {"check": "Font Consistency", "result": "WARN", "detail": "DOB field uses slightly lighter weight than adjacent fields — possible reprint artifact"},
            {"check": "Field Format Validation", "result": "PASS", "detail": "All field formats match Colorado DL standards (AAMVA 2020)"},
            {"check": "Security Features", "result": "PASS", "detail": "Ghost image present, holographic overlay visible, microprint zone intact"},
            {"check": "Layout/AAMVA Compliance", "result": "PASS", "detail": "Field zones and barcode placement conform to AAMVA D20 layout"},
            {"check": "MRZ Integrity", "result": "WARN", "detail": "PDF417 barcode partially obscured — could not fully verify checksum"},
        ],
        "flags": [
            {"severity": "WARN", "message": "DOB font weight inconsistency — recommend manual secondary check"},
            {"severity": "WARN", "message": "PDF417 barcode partially unreadable — request alternative ID if possible"},
            {"severity": "OK", "message": "No signs of digital manipulation or layer artifacts detected"},
        ],
        "suspicious_elements": ["DOB font weight", "PDF417 partial occlusion"],
    },
    "level2": {
        "extracted_fields": {
            "first_name": "Jane",
            "last_name": "Doe",
            "dob": "1985-04-12",
            "id_number": "D123-456-78-901-0",
            "expiration": "2026-04-23",
            "address": "1420 Elm St, Denver CO 80203",
            "license_class": "D",
            "issuing_state": "CO",
            "issuing_country": "USA",
            "gender": "F",
            "height": "5-06",
            "eye_color": "BRN",
        },
        "extraction_confidence": 0.88,
        "field_confidences": {
            "first_name": 0.97,
            "last_name": 0.97,
            "dob": 0.91,
            "id_number": 0.85,
            "expiration": 0.94,
            "address": 0.82,
        },
        "ocr_issues": ["ID number partially obscured by glare", "Address line 2 not present"],
    },
    "level3": {
        "cross_doc_available": True,
        "comparisons": [
            {"field": "last_name", "id_value": "Doe", "doc_value": "Doe", "match": True, "confidence": 0.99, "flag": "MATCH"},
            {"field": "first_name", "id_value": "Jane", "doc_value": "Jennifer", "match": False, "confidence": 0.61, "flag": "PARTIAL_MATCH"},
            {"field": "dob", "id_value": "1985-04-12", "doc_value": "1985-04-12", "match": True, "confidence": 0.99, "flag": "MATCH"},
            {"field": "address", "id_value": "1420 Elm St, Denver CO 80203", "doc_value": "1420 Elm Street, Denver, CO 80203", "match": True, "confidence": 0.93, "flag": "MATCH"},
            {"field": "id_number", "id_value": "D123-456-78-901-0", "doc_value": None, "match": False, "confidence": 0.0, "flag": "UNAVAILABLE"},
        ],
        "overall_match_score": 0.81,
        "identity_consistency": "PARTIAL",
    },
    "level4": {
        "compliance_verdict": "WARN",
        "compliance_flags": [
            {"severity": "WARN", "message": "⚠ ID expires in 12 days — verify acceptability with signing parties", "rule_citation": "General notary best practice", "category": "EXPIRATION"},
            {"severity": "WARN", "message": "First name partial match: 'Jane' (ID) vs 'Jennifer' (loan app) — confirm legal name with signer", "rule_citation": "MISMO closing requirements", "category": "NAME_MATCH"},
            {"severity": "OK", "message": "In-state ID confirmed for Colorado property transaction", "rule_citation": "CO Rev. Stat. § 12-55-110", "category": "IN_STATE"},
            {"severity": "OK", "message": "License class D is valid for standard identification purposes", "rule_citation": "AAMVA DL/ID Card Design Standard", "category": "FORMAT"},
        ],
        "expiration_status": {"is_expired": False, "days_until_expiry": 12, "status": "EXPIRING_SOON"},
        "overall_recommendation": "HOLD",
        "recommendation_detail": "Proceed with caution — confirm signer's legal name matches loan documents and flag expiring ID in closing package per MISMO requirements.",
    },
    "summary": {
        "overall_verdict": "WARN",
        "risk_level": "MEDIUM",
        "key_findings": [
            "ID expires in 12 days — must be noted in closing package",
            "First name 'Jane' vs 'Jennifer' on loan app — likely nickname, confirm with signer",
            "PDF417 barcode partially unreadable — recommend secondary ID if available",
            "DOB and address match across documents",
            "No signs of document forgery detected",
        ],
        "notary_action": "Request signer confirm legal name 'Jennifer'; note expiring ID in closing package; proceed if name confirmed and second ID available.",
    },
    "processing_time_ms": 3241,
}