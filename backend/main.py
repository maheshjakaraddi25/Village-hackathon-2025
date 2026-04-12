"""
ID Verify AI — FastAPI Backend
VillageHacks 2026 · Notary Everyday

Pipeline:
- Local Models (fast): authenticity + OCR + liveness + face match + barcode check
- Claude Vision (structured LV1-LV4 JSON)
- Deterministic rules engine (compliance + cross-doc matching)
"""

import base64
import json
import re
import time
from datetime import date, datetime
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from starlette.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

try:
    import anthropic
except ImportError:
    anthropic = None

try:
    from .models.pipeline import run_local_pipeline
    from .rules.schema_patch import ensure_schema
    from .rules.compliance import enforce_compliance_rules
    from .rules.cross_doc import run_cross_doc_matching
except ImportError:
    from models.pipeline import run_local_pipeline
    from rules.schema_patch import ensure_schema
    from rules.compliance import enforce_compliance_rules
    from rules.cross_doc import run_cross_doc_matching


# ──────────────────────────────────────────────────────────────────────────────

app = FastAPI(title="ID Verify AI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = anthropic.Anthropic() if anthropic is not None else None

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE_MB = 10


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def encode_image(content: bytes, mime_type: str) -> dict:
    b64 = base64.standard_b64encode(content).decode("utf-8")
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": mime_type, "data": b64},
    }


def parse_claude_json(raw: str) -> dict:
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start == -1 or end <= 0:
        raise ValueError("No JSON object found in Claude response")
    return json.loads(cleaned[start:end])


def compute_expiration_details(expiry_str: Optional[str]) -> dict:
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


# ──────────────────────────────────────────────────────────────────────────────
# Claude prompts
# ──────────────────────────────────────────────────────────────────────────────

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
    if client is None:
        raise RuntimeError("anthropic is not installed. Add it to your environment to enable Claude analysis.")

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


# ──────────────────────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "model": "claude-sonnet-4-20250514"}


@app.post("/verify")
async def verify(
    id_doc: UploadFile = File(...),
    support_doc: Optional[UploadFile] = File(None),
    selfie: Optional[UploadFile] = File(None),
):
    t0 = time.time()

    if id_doc.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(400, f"Unsupported ID mime type: {id_doc.content_type}")

    id_bytes = await id_doc.read()
    selfie_bytes = await selfie.read() if selfie else None
    doc2_bytes = await support_doc.read() if support_doc else None
    doc2_mime = support_doc.content_type if support_doc else None

    # ── Stage A: local pipeline (fast)
    local = await run_local_pipeline(id_bytes, selfie_bytes)

    auth_score = local["local"]["authenticity"]["score"]
    live_ok = local["local"]["liveness"]["verdict"] == "LIVE" if selfie_bytes else True

    if auth_score < 0.25 and not live_ok:
        raise HTTPException(400, "Document failed authenticity and liveness checks")

    # ── Stage B: Claude structured analysis
    claude_result = await call_claude(id_bytes, id_doc.content_type, doc2_bytes, doc2_mime)
    claude_result = ensure_schema(claude_result)

    # ── Stage C: merge local model output
    claude_result["local_models"] = local["local"]

    # ── Stage D: enforce expiration calculation server-side
    expiry = claude_result.get("level2", {}).get("extracted_fields", {}).get("expiration")
    claude_result["level4"]["expiration_status"] = compute_expiration_details(expiry)

    # ── Stage E: deterministic cross-doc matching (optional enhancement)
    if doc2_bytes:
        cross_doc = run_cross_doc_matching(
            id_fields=claude_result["level2"]["extracted_fields"],
            support_doc_bytes=doc2_bytes
        )
        claude_result["level3"] = cross_doc

    # ── Stage F: deterministic compliance enforcement (override Claude if needed)
    claude_result = enforce_compliance_rules(claude_result)

    claude_result["processing_time_ms"] = int((time.time() - t0) * 1000)

    return JSONResponse(content=claude_result)
