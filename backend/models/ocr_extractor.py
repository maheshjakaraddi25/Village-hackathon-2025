from typing import Optional
import re
import cv2
import numpy as np
from datetime import datetime

try:
    from paddleocr import PaddleOCR
    _PADDLE_AVAILABLE = True
except ImportError:
    _PADDLE_AVAILABLE = False

try:
    import pytesseract
    from PIL import Image
    import io as _io
    _TESSERACT_AVAILABLE = True
except ImportError:
    _TESSERACT_AVAILABLE = False

_ocr = None

LABEL_SYNONYMS = {
    "last_name":         r"sur\s*name|family\s*name|last\s*name|apellido|nom\s*de\s*famille|nachname|cognome|name\s*1",
    "first_name":        r"given\s*names?|first\s*name|fore\s*name|pr[eé]nom|vorname|nome|nombre|name\s*2",
    "full_name":         r"full\s*name|complete\s*name|test\s*name|holder|applicant\s*name",
    "dob":               r"date\s*of\s*birth|birth\s*date|d\.?\s*o\.?\s*b\.?|(?<!\w)dob(?!\w)|fecha\s*de\s*nacimiento|geburtsdatum",
    "expiration":        r"expir\w*|expiretion|valid\s*(?:until|thru|to|upto)",
    "issue_date":        r"issue\s*(?:date|d\.?|cat)|date\s*of\s*issue|issued\s*(?:on|date)?",
    "id_number":         r"passport\s*num\w*|passport\s*no|document\s*no|id\s*num\w*|id\s*no|control\s*num\w*|licence\s*no|license\s*no|card\s*no",
    "nationality":       r"nationalit\w*|citizenship|country\s*of\s*(?:birth|origin|citizenship)",
    "issuing_authority": r"issuing\s*(?:post|authority|office|state|place)|place\s*of\s*issue|issued\s*by",
    "gender":            r"(?<!\w)sex(?!\w)|(?<!\w)gender(?!\w)",
    "address":           r"(?<!\w)address(?!\w)|residence|domicile|home\s*address",
    "visa_type":         r"visa\s*type|visa\s*class|type\s*of\s*visa",
    "license_class":     r"licen[sc]e\s*class|dl\s*class",
    "height":            r"(?<!\w)h(?:ei)?g?ht(?!\w)|(?<!\w)hgt(?!\w)",
    "eye_color":         r"eye\s*colou?r|(?<!\w)eyes(?!\w)",
    "place_of_birth":    r"place\s*of\s*birth|birth\s*place|born\s*in",
}

# Fields that commonly appear as short standalone labels on ID cards
# These should NOT be used as name/value extractors since they confuse the parser
SKIP_AS_VALUE = {
    "issue date", "issue cat", "expiry date", "expiration date", "birth date",
    "date of birth", "given name", "given names", "surname", "family name",
    "last name", "first name", "full name", "passport number", "passport no",
    "id number", "id no", "control number", "nationality", "gender", "sex",
    "address", "place of issue", "issuing post", "visa type", "license class",
    "eye color", "height", "place of birth", "dob", "expiretion date",
}


def _load_paddle():
    global _ocr
    if _ocr is None:
        _ocr = PaddleOCR(use_angle_cls=True, lang="en")
    return _ocr


def _extract_from_ocr_result(item) -> list:
    texts = []
    try:
        raw = dict(item)
        def _dig(obj):
            if isinstance(obj, str) and len(obj) > 1:
                texts.append(obj)
            elif isinstance(obj, list):
                for el in obj: _dig(el)
            elif isinstance(obj, dict):
                if 'rec_texts' in obj:
                    for t in obj['rec_texts']:
                        if isinstance(t, str) and len(t.strip()) > 1:
                            texts.append(t.strip())
                    return
                for v in obj.values(): _dig(v)
        _dig(raw)
    except Exception as e:
        print(f"[OCR] parse error: {e}")
    return texts


def _run_ocr(img_bytes: bytes) -> list:
    arr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return []
    if _PADDLE_AVAILABLE:
        try:
            result = _load_paddle().ocr(img)
            lines = []
            if result:
                for item in result:
                    if item is None:
                        continue
                    if isinstance(item, list):
                        for word in item:
                            if isinstance(word, (list, tuple)) and len(word) >= 2:
                                tc = word[1]
                                if isinstance(tc, (list, tuple)) and len(tc) >= 1:
                                    t = str(tc[0]).strip()
                                    if len(t) > 1:
                                        lines.append(t)
                    else:
                        lines.extend(_extract_from_ocr_result(item))
            print(f"[OCR] Raw lines: {lines}")
            return lines
        except Exception as e:
            print(f"[OCR] PaddleOCR error: {e}")
    if _TESSERACT_AVAILABLE:
        try:
            pil_img = Image.open(_io.BytesIO(img_bytes))
            text = pytesseract.image_to_string(pil_img)
            return [l.strip() for l in text.splitlines() if len(l.strip()) > 1]
        except Exception as e:
            print(f"[OCR] Tesseract error: {e}")
    return []


def normalize_date(s) -> Optional[str]:
    if not s:
        return None
    s = s.strip()
    m = re.match(r'^(\d{1,2})([A-Z]{3})(\d{4})$', s.upper())
    if m:
        months = {'JAN':'01','FEB':'02','MAR':'03','APR':'04','MAY':'05','JUN':'06',
                  'JUL':'07','AUG':'08','SEP':'09','OCT':'10','NOV':'11','DEC':'12'}
        mon = months.get(m.group(2))
        if mon:
            return f"{m.group(3)}-{mon}-{int(m.group(1)):02d}"
    for fmt in ["%m/%d/%Y","%m-%d-%Y","%d/%m/%Y","%d-%m-%Y",
                "%Y-%m-%d","%d/%m/%y","%m/%d/%y","%d-%m-%y","%d.%m.%Y"]:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except Exception:
            pass
    return None


def _is_label_line(line: str) -> bool:
    """Return True if this line is purely a label (should not be used as a value)."""
    return line.strip().lower() in SKIP_AS_VALUE


def _is_any_label(line: str) -> bool:
    """Return True if line matches any known label pattern."""
    for pat in LABEL_SYNONYMS.values():
        try:
            if re.fullmatch(r'\s*(?:' + pat + r')\s*', line.strip(), re.IGNORECASE):
                return True
        except re.error:
            pass
    return _is_label_line(line)


def value_after_label(lines: list, pattern: str) -> Optional[str]:
    """
    Find a label line and return the next non-label, non-empty value.
    Only matches lines that are EXACTLY the label (fullmatch), not lines
    that merely contain the label word.
    """
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Must be an exact label match, not a partial word inside a value
        try:
            is_exact_label = bool(re.fullmatch(r'\s*(?:' + pattern + r')\s*',
                                               stripped, re.IGNORECASE))
        except re.error:
            is_exact_label = bool(re.search(pattern, stripped, re.IGNORECASE))

        if is_exact_label:
            for j in range(i + 1, min(i + 3, len(lines))):
                val = lines[j].strip()
                if val and not _is_any_label(val):
                    return val
    return None


def extract_id_fields(img_bytes: bytes) -> dict:
    lines = _run_ocr(img_bytes)
    text  = "\n".join(lines)
    print(f"[OCR] Extracted {len(lines)} lines: {lines}")

    def get(field: str) -> Optional[str]:
        pat = LABEL_SYNONYMS[field]
        # 1. Exact label on its own line, value on next line
        val = value_after_label(lines, pat)
        if val:
            return val
        # 2. Inline: "DOB: 14JAN2000" — only if label is at start of line
        try:
            m = re.search(r'(?:^|\n)\s*(?:' + pat + r')\s*[:\-\/]\s*([^\n\r]{1,60})',
                          text, re.IGNORECASE | re.MULTILINE)
            if m:
                val = m.group(1).strip()
                if not _is_any_label(val):
                    return val
        except re.error:
            pass
        return None

    # ── Name ──────────────────────────────────────────────────────────────────
    surname    = get("last_name")
    given_name = get("first_name")
    if not surname and not given_name:
        full = get("full_name")
        if full:
            parts = full.split()
            given_name = parts[0]  if parts        else None
            surname    = parts[-1] if len(parts)>1 else None

    # ── Dates ─────────────────────────────────────────────────────────────────
    date_tokens = re.findall(
        r'\b(\d{1,2}[A-Z]{3}\d{4}|\d{2}[-/.]\d{2}[-/.]\d{2,4}|\d{4}[-/.]\d{2}[-/.]\d{2})\b',
        text, re.IGNORECASE)
    norm_dates = [d for d in date_tokens if normalize_date(d)]

    dob_raw   = get("dob")
    exp_raw   = get("expiration")
    issue_raw = get("issue_date")

    # Positional fallback — only if labels not found
    if not dob_raw and norm_dates:
        dob_raw = norm_dates[0]
    if not exp_raw and len(norm_dates) >= 2:
        exp_raw = norm_dates[-1]

    # ── Other fields ──────────────────────────────────────────────────────────
    id_number         = get("id_number")
    nationality       = get("nationality")
    issuing_authority = get("issuing_authority")
    issuing_state_m   = re.search(r'\b(CA|TX|FL|NY|CO|WA|OR|AZ|NV|IL|OH|GA)\b', text)
    address           = get("address")
    visa_type         = get("visa_type")
    license_class     = get("license_class")
    height            = get("height")
    eye_color         = get("eye_color")
    place_of_birth    = get("place_of_birth")

    gender_raw = get("gender")
    gender = None
    if gender_raw:
        g = gender_raw.strip().upper()
        gender = "M" if g in ("M","MALE","MASCULIN") else \
                 "F" if g in ("F","FEMALE","FEMININ") else g[:1]

    # MRZ fallback for id_number
    if not id_number:
        mrz = [l for l in lines if re.match(r'^[A-Z0-9<]{20,}$', l)]
        if mrz:
            id_number = mrz[0][:9].replace('<','').strip()

    return {
        "first_name":      given_name.title() if given_name else None,
        "last_name":       surname.title()    if surname    else None,
        "dob":             normalize_date(dob_raw),
        "expiration":      normalize_date(exp_raw),
        "issue_date":      normalize_date(issue_raw),
        "id_number":       id_number,
        "issuing_state":   issuing_authority or (issuing_state_m.group(1) if issuing_state_m else None),
        "issuing_country": nationality,
        "address":         address,
        "gender":          gender,
        "visa_type":       visa_type,
        "license_class":   license_class,
        "height":          height,
        "eye_color":       eye_color,
        "place_of_birth":  place_of_birth,
        "ocr_engine":      "paddleocr" if _PADDLE_AVAILABLE else ("tesseract" if _TESSERACT_AVAILABLE else "none"),
        "raw_lines":       lines,
    }