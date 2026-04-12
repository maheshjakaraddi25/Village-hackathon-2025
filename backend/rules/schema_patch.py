def ensure_schema(result: dict) -> dict:
    if "level1" not in result:
        result["level1"] = {}
    if "level2" not in result:
        result["level2"] = {}
    if "level3" not in result:
        result["level3"] = {}
    if "level4" not in result:
        result["level4"] = {}
    if "summary" not in result:
        result["summary"] = {}

    if "compliance_flags" not in result["level4"]:
        result["level4"]["compliance_flags"] = []

    if "checks" not in result["level1"]:
        result["level1"]["checks"] = []

    if "flags" not in result["level1"]:
        result["level1"]["flags"] = []

    if "suspicious_elements" not in result["level1"]:
        result["level1"]["suspicious_elements"] = []

    return result