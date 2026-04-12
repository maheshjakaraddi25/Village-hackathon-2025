from typing import Optional
from datetime import datetime, date


def _days_until(expiry: Optional[str]) -> Optional[int]:
    if not expiry:
        return None
    try:
        exp = datetime.strptime(expiry, "%Y-%m-%d").date()
        return (exp - date.today()).days
    except:
        return None


def enforce_compliance_rules(result: dict) -> dict:
    level2 = result.get("level2", {}).get("extracted_fields", {})
    level4 = result.get("level4", {})
    flags = level4.get("compliance_flags", [])

    expiry = level2.get("expiration")
    state = level2.get("issuing_state")

    days = _days_until(expiry)

    # Expiration rules
    if days is not None:
        if days < 0:
            flags.insert(0, {
                "severity": "ERROR",
                "message": f"ID expired {abs(days)} days ago — automatic FAIL under NIST IAL2",
                "rule_citation": "NIST SP 800-63-3 IAL2",
                "category": "EXPIRATION"
            })
            level4["compliance_verdict"] = "FAIL"
            level4["overall_recommendation"] = "REJECT"
            level4["recommendation_detail"] = "Signer must provide a valid unexpired government ID."

            result["summary"]["overall_verdict"] = "FAIL"
            result["summary"]["risk_level"] = "CRITICAL"

        elif days <= 30:
            flags.insert(0, {
                "severity": "WARN",
                "message": f"⚠ ID expires in {days} days — warn signer and record in package",
                "rule_citation": "MISMO Closing Package Requirements",
                "category": "EXPIRATION"
            })
            if level4.get("compliance_verdict") != "FAIL":
                level4["compliance_verdict"] = "WARN"
                level4["overall_recommendation"] = "HOLD"
                level4["recommendation_detail"] = "Proceed with caution — ID expiring soon."

    # In-state TX/FL simplified enforcement
    # (If your support doc includes property state, you can compare properly later)
    if state in ["TX", "FL"]:
        flags.append({
            "severity": "OK",
            "message": f"In-state issuing state detected: {state}",
            "rule_citation": f"{state} notary guidance (simplified)",
            "category": "IN_STATE"
        })

    level4["compliance_flags"] = flags
    result["level4"] = level4
    return result