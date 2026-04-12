"""
ID Verify AI — FastAPI Backend
VillageHacks 2026 · Notary Everyday

Full pipeline: Level 1 (Authenticity) → Level 2 (Extraction) → Level 3 (Cross-Doc) → Level 4 (Compliance)
Run from THIS directory: uvicorn main:app --reload --port 8000
"""

import base64
import json
import re
import sqlite3
import os
import uuid
import time
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import anthropic
import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = FastAPI(title="ID Verify AI", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_FILE_SIZE_MB = 10

# ─── Database ─────────────────────────────────────────────────────────────────

DB_PATH = Path(__file__).parent / "verifications.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS verifications (
        id TEXT PRIMARY KEY,
        created_at TEXT,
        overall_verdict TEXT,
        risk_level TEXT,
        recommendation TEXT,
        extracted_name TEXT,
        extracted_state TEXT,
        expiration TEXT,
        processing_ms INTEGER,
        result_json TEXT
    )""")
    conn.commit()
    conn.close()

init_db()

def db_save(ver_id: str, result: dict):
    s = result.get("summary", {})
    f = result.get("level2", {}).get("extracted_fields", {})
    exp = result.get("level4", {}).get("expiration_status", {})
    name = " ".join(filter(None, [f.get("first_name"), f.get("last_name")])) or ""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR REPLACE INTO verifications VALUES (?,?,?,?,?,?,?,?,?,?)", (
        ver_id, datetime.now().isoformat(),
        s.get("overall_verdict", ""), s.get("risk_level", ""),
        result.get("level4", {}).get("overall_recommendation", ""),
        name, f.get("issuing_state", ""),
        exp.get("status", ""),
        result.get("processing_time_ms", 0),
        json.dumps(result)
    ))
    conn.commit()
    conn.close()


# ─── Pydantic models ──────────────────────────────────────────────────────────

class FlagItem(BaseModel):
    severity: str
    message: str
    rule_citation: Optional[str] = None
    category: Optional[str] = None

class CheckItem(BaseModel):
    check: str
    result: str
    detail: str

class Level1Result(BaseModel):
    verdict: str
    verdict_message: str
    authenticity_score: float
    checks: list[CheckItem]
    flags: list[FlagItem]
    suspicious_elements: list[str]

class ExtractedFields(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    dob: Optional[str] = None
    id_number: Optional[str] = None
    expiration: Optional[str] = None
    address: Optional[str] = None
    license_class: Optional[str] = None
    issuing_state: Optional[str] = None
    issuing_country: Optional[str] = None
    gender: Optional[str] = None
    height: Optional[str] = None
    eye_color: Optional[str] = None

class Level2Result(BaseModel):
    extracted_fields: ExtractedFields
    extraction_confidence: float
    field_confidences: dict[str, float]
    ocr_issues: list[str]

class ComparisonItem(BaseModel):
    field: str
    id_value: Optional[str] = None
    doc_value: Optional[str] = None
    match: bool
    confidence: float
    flag: str

class Level3Result(BaseModel):
    cross_doc_available: bool
    comparisons: list[ComparisonItem]
    overall_match_score: float
    identity_consistency: str

class ExpirationStatus(BaseModel):
    is_expired: bool
    days_until_expiry: Optional[int] = None
    status: str

class Level4Result(BaseModel):
    compliance_verdict: str
    compliance_flags: list[FlagItem]
    expiration_status: ExpirationStatus
    overall_recommendation: str
    recommendation_detail: str

class Summary(BaseModel):
    overall_verdict: str
    risk_level: str
    key_findings: list[str]
    notary_action: str

class VerificationResult(BaseModel):
    id: str
    level1: Level1Result
    level2: Level2Result
    level3: Level3Result
    level4: Level4Result
    summary: Summary
    processing_time_ms: int


# ─── Helpers ──────────────────────────────────────────────────────────────────

def encode_image(content: bytes, mime_type: str) -> dict:
    b64 = base64.standard_b64encode(content).decode("utf-8")
    return {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": b64}}

def parse_claude_json(raw: str) -> dict:
    cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON in Claude response. Got: {cleaned[:200]}")
    return json.loads(cleaned[start:end])

def compute_expiration_details(expiry_str: Optional[str]) -> dict:
    if not expiry_str:
        return {"is_expired": False, "days_until_expiry": None, "status": "UNKNOWN"}
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"):
        try:
            exp_date = datetime.strptime(expiry_str, fmt).date()
            delta = (exp_date - date.today()).days
            if delta < 0:
                return {"is_expired": True, "days_until_expiry": delta, "status": "EXPIRED"}
            elif delta <= 90:
                return {"is_expired": False, "days_until_expiry": delta, "status": "EXPIRING_SOON"}
            else:
                return {"is_expired": False, "days_until_expiry": delta, "status": "VALID"}
        except ValueError:
            continue
    return {"is_expired": False, "days_until_expiry": None, "status": "UNKNOWN"}

def enrich_expiration(result: dict) -> dict:
    expiry = result.get("level2", {}).get("extracted_fields", {}).get("expiration")
    computed = compute_expiration_details(expiry)
    result.setdefault("level4", {})["expiration_status"] = computed

    flags = result["level4"].get("compliance_flags", [])
    if computed["status"] == "EXPIRING_SOON":
        days = computed["days_until_expiry"]
        flags.insert(0, {"severity": "WARN",
            "message": f"⚠ ID expires in {days} days — must be noted in closing package",
            "rule_citation": "MISMO closing requirements", "category": "EXPIRATION"})
    elif computed["status"] == "EXPIRED":
        flags.insert(0, {"severity": "ERROR",
            "message": f"ID expired {abs(computed['days_until_expiry'])} days ago — FAIL per NIST IAL2",
            "rule_citation": "NIST SP 800-63-3 IAL2", "category": "EXPIRATION"})
        result["level4"]["compliance_verdict"] = "FAIL"
        result["level4"]["overall_recommendation"] = "REJECT"
        result.setdefault("summary", {})["overall_verdict"] = "FAIL"
        result.setdefault("summary", {})["risk_level"] = "CRITICAL"
    result["level4"]["compliance_flags"] = flags
    return result


# ─── Claude prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert document verification AI for notary and KYC compliance.
You analyze government-issued ID documents for authenticity, data extraction, cross-document matching, and compliance.
CRITICAL: Respond ONLY with valid JSON matching the exact schema. No markdown, no preamble, no trailing text.
Use null for unreadable fields. Never hallucinate values. Use WARN when uncertain."""

USER_PROMPT_TEMPLATE = """Analyze this government-issued ID for a notarization workflow.
{second_doc_note}

Return ONLY this JSON (all fields required):
{{
  "level1": {{
    "verdict": "PASS"|"FAIL"|"WARN",
    "verdict_message": "one sentence",
    "authenticity_score": 0.0-1.0,
    "checks": [
      {{"check": "Font Consistency", "result": "PASS|FAIL|WARN", "detail": "..."}},
      {{"check": "Field Format Validation", "result": "PASS|FAIL|WARN", "detail": "..."}},
      {{"check": "Security Features", "result": "PASS|FAIL|WARN", "detail": "..."}},
      {{"check": "Layout/AAMVA Compliance", "result": "PASS|FAIL|WARN", "detail": "..."}},
      {{"check": "MRZ/Barcode Integrity", "result": "PASS|FAIL|WARN", "detail": "..."}}
    ],
    "flags": [{{"severity": "ERROR|WARN|OK", "message": "...", "rule_citation": null, "category": null}}],
    "suspicious_elements": []
  }},
  "level2": {{
    "extracted_fields": {{
      "first_name": null, "last_name": null, "dob": "YYYY-MM-DD or null",
      "id_number": null, "expiration": "YYYY-MM-DD or null", "address": null,
      "license_class": null, "issuing_state": "2-letter or null",
      "issuing_country": null, "gender": null, "height": null, "eye_color": null
    }},
    "extraction_confidence": 0.0-1.0,
    "field_confidences": {{"first_name": 0.0, "last_name": 0.0, "dob": 0.0, "id_number": 0.0, "expiration": 0.0, "address": 0.0}},
    "ocr_issues": []
  }},
  "level3": {{
    "cross_doc_available": {cross_doc_bool},
    "comparisons": [{{"field": "last_name", "id_value": null, "doc_value": null, "match": false, "confidence": 0.0, "flag": "MATCH|MISMATCH|PARTIAL_MATCH|UNAVAILABLE"}}],
    "overall_match_score": 0.0,
    "identity_consistency": "CONSISTENT|INCONSISTENT|PARTIAL|INSUFFICIENT_DATA"
  }},
  "level4": {{
    "compliance_verdict": "PASS"|"FAIL"|"WARN",
    "compliance_flags": [{{"severity": "ERROR|WARN|OK", "message": "...", "rule_citation": "NIST/MISMO/state law", "category": "EXPIRATION|IN_STATE|NAME_MATCH|FORMAT"}}],
    "expiration_status": {{"is_expired": false, "days_until_expiry": null, "status": "VALID|EXPIRED|EXPIRING_SOON|UNKNOWN"}},
    "overall_recommendation": "PROCEED|HOLD|REJECT",
    "recommendation_detail": "specific notary instruction"
  }},
  "summary": {{
    "overall_verdict": "PASS"|"FAIL"|"WARN",
    "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
    "key_findings": ["finding 1", "finding 2", "finding 3"],
    "notary_action": "specific action for notary"
  }}
}}

Rules: NIST IAL2 expired=FAIL. Flag expiry within 90 days WARN. TX/FL require in-state ID for property.
MISMO: record ID type+expiration. "Jen"/"Jennifer" = PARTIAL_MATCH. Middle name omission = soft flag."""


async def call_claude(id_bytes: bytes, id_mime: str,
                      doc2_bytes: Optional[bytes] = None,
                      doc2_mime: Optional[str] = None) -> dict:
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise HTTPException(400, "ANTHROPIC_API_KEY not set. Create a .env file with ANTHROPIC_API_KEY=sk-ant-...")

    client = anthropic.Anthropic(api_key=api_key)
    has_second = doc2_bytes is not None

    content = [encode_image(id_bytes, id_mime)]
    if has_second:
        content.append(encode_image(doc2_bytes, doc2_mime))

    prompt = USER_PROMPT_TEMPLATE.format(
        second_doc_note=(
            "A second supporting document is attached. Use it for Level 3 cross-document analysis."
            if has_second else
            "No second document. Set level3.cross_doc_available to false and comparisons to empty array."
        ),
        cross_doc_bool="true" if has_second else "false",
    )
    content.append({"type": "text", "text": prompt})

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )

    raw = "".join(b.text for b in message.content if hasattr(b, "text"))
    return parse_claude_json(raw)


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    has_key = bool(os.getenv("ANTHROPIC_API_KEY"))
    return {"status": "ok", "model": "claude-opus-4-5", "api_key_set": has_key}


@app.post("/verify", response_model=VerificationResult)
async def verify(
    id_doc: UploadFile = File(...),
    support_doc: Optional[UploadFile] = File(None),
):
    t0 = time.time()

    if id_doc.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(400, f"Unsupported type: {id_doc.content_type}. Use JPEG, PNG, or WebP.")

    id_bytes = await id_doc.read()
    if len(id_bytes) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(413, f"File too large (max {MAX_FILE_SIZE_MB}MB)")

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

    ver_id = str(uuid.uuid4())[:8].upper()
    raw_result["id"] = ver_id
    db_save(ver_id, raw_result)

    return JSONResponse(content=raw_result)


@app.post("/synthetic-test")
async def synthetic_test():
    """Pre-baked demo result — no API key needed."""
    result = dict(SYNTHETIC_DEMO_RESULT)
    result["id"] = "DEMO-" + str(uuid.uuid4())[:4].upper()
    return JSONResponse(content=result)


@app.get("/api/history")
async def get_history(limit: int = 50):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id,created_at,overall_verdict,risk_level,recommendation,"
        "extracted_name,extracted_state,expiration,processing_ms "
        "FROM verifications ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/stats")
async def get_stats():
    conn = sqlite3.connect(DB_PATH)
    total = conn.execute("SELECT COUNT(*) FROM verifications").fetchone()[0]
    passed = conn.execute("SELECT COUNT(*) FROM verifications WHERE overall_verdict='PASS'").fetchone()[0]
    warned = conn.execute("SELECT COUNT(*) FROM verifications WHERE overall_verdict='WARN'").fetchone()[0]
    failed = conn.execute("SELECT COUNT(*) FROM verifications WHERE overall_verdict='FAIL'").fetchone()[0]
    conn.close()
    return {"total": total, "passed": passed, "warned": warned, "failed": failed}


@app.delete("/api/history/{ver_id}")
async def delete_record(ver_id: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM verifications WHERE id=?", (ver_id,))
    conn.commit()
    conn.close()
    return {"deleted": ver_id}


# ─── Synthetic demo data ──────────────────────────────────────────────────────

SYNTHETIC_DEMO_RESULT = {
    "processing_time_ms": 3241,
    "level1": {
        "verdict": "WARN",
        "verdict_message": "Document appears genuine with minor font inconsistency on DOB field.",
        "authenticity_score": 0.74,
        "checks": [
            {"check": "Font Consistency", "result": "WARN", "detail": "DOB field uses slightly lighter weight than adjacent fields — possible reprint artifact"},
            {"check": "Field Format Validation", "result": "PASS", "detail": "All field formats match Colorado DL standards (AAMVA 2020)"},
            {"check": "Security Features", "result": "PASS", "detail": "Ghost image present, holographic overlay visible, microprint zone intact"},
            {"check": "Layout/AAMVA Compliance", "result": "PASS", "detail": "Field zones and barcode placement conform to AAMVA D20 layout"},
            {"check": "MRZ/Barcode Integrity", "result": "WARN", "detail": "PDF417 barcode partially obscured — could not fully verify checksum"},
        ],
        "flags": [
            {"severity": "WARN", "message": "DOB font weight inconsistency — recommend manual secondary check", "rule_citation": None, "category": None},
            {"severity": "WARN", "message": "PDF417 barcode partially unreadable", "rule_citation": None, "category": None},
            {"severity": "OK", "message": "No signs of digital manipulation detected", "rule_citation": None, "category": None},
        ],
        "suspicious_elements": ["DOB font weight", "PDF417 partial occlusion"],
    },
    "level2": {
        "extracted_fields": {
            "first_name": "Jane", "last_name": "Doe", "dob": "1985-04-12",
            "id_number": "D123-456-78-901-0", "expiration": "2026-04-23",
            "address": "1420 Elm St, Denver CO 80203", "license_class": "D",
            "issuing_state": "CO", "issuing_country": "USA",
            "gender": "F", "height": "5-06", "eye_color": "BRN",
        },
        "extraction_confidence": 0.88,
        "field_confidences": {"first_name": 0.97, "last_name": 0.97, "dob": 0.91, "id_number": 0.85, "expiration": 0.94, "address": 0.82},
        "ocr_issues": ["ID number partially obscured by glare"],
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
            {"severity": "WARN", "message": "⚠ ID expires in 12 days — must be noted in closing package", "rule_citation": "MISMO closing requirements", "category": "EXPIRATION"},
            {"severity": "WARN", "message": "First name partial match: 'Jane' (ID) vs 'Jennifer' (loan app) — confirm legal name", "rule_citation": "MISMO closing requirements", "category": "NAME_MATCH"},
            {"severity": "OK", "message": "In-state ID confirmed for Colorado transaction", "rule_citation": "CO Rev. Stat. § 12-55-110", "category": "IN_STATE"},
        ],
        "expiration_status": {"is_expired": False, "days_until_expiry": 12, "status": "EXPIRING_SOON"},
        "overall_recommendation": "HOLD",
        "recommendation_detail": "Confirm legal name matches loan documents; note expiring ID in closing package per MISMO.",
    },
    "summary": {
        "overall_verdict": "WARN",
        "risk_level": "MEDIUM",
        "key_findings": [
            "ID expires in 12 days — must be noted in closing package",
            "First name 'Jane' vs 'Jennifer' on loan app — likely nickname, confirm with signer",
            "PDF417 barcode partially unreadable — request secondary ID if possible",
            "DOB and address match across documents",
            "No signs of document forgery detected",
        ],
        "notary_action": "Request signer confirm legal name 'Jennifer'; note expiring ID in closing package; proceed if name confirmed.",
    },
}
