# ID Verify AI — Notary Everyday x VillageHacks 2026

Full-stack AI identity verification: React frontend + FastAPI backend.

## ✅ Quick Start (5 minutes)

### Step 1 — Backend
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env and paste your ANTHROPIC_API_KEY
uvicorn main:app --reload --port 8000
```

### Step 2 — Frontend (new terminal)
```bash
cd frontend
npm install
npm run dev
```

### Step 3 — Open browser
```
http://localhost:5173
```

Click **LOAD DEMO RESULT** to test instantly without uploading anything.

---

## ⚠️ The Error You Were Hitting
```
ERROR: Could not import module "main"
```
**Cause**: Running `uvicorn main:app` from the project root.
**Fix**: Always `cd backend` first, then run uvicorn.

---

## Features

### 4 Verification Levels
| Level | What it checks |
|-------|---------------|
| LV1 | Font consistency, field formats, security features, AAMVA layout, barcode |
| LV2 | Extract all fields: name, DOB, ID#, address, expiry, state, class, height... |
| LV3 | Cross-document match against second uploaded doc (loan app, deed, bill) |
| LV4 | Expiration, NIST IAL2, MISMO compliance, in-state requirements, citations |

### Voice Interview
Click "Add Voice Interview" to:
- Play the AI notary's question via browser TTS
- Record subject's verbal answer via microphone
- Claude cross-references verbal answer vs document fields

### History Dashboard
- All verifications saved to SQLite (`backend/verifications.db`)
- Stats: total / pass / warn / fail
- Filter by verdict, delete records

### Export
- Download full JSON result
- Download plain-text report for closing package
- Print-friendly layout

## API Endpoints
```
POST /verify          — Run full pipeline (multipart: id_doc, support_doc)
POST /synthetic-test  — Demo result, no API key needed
GET  /api/history     — All past verifications
GET  /api/stats       — Summary counts
DELETE /api/history/:id — Delete a record
GET  /health          — Backend health check
```
