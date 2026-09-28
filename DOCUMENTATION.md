# 📚 Technical Documentation — Sewa Setu Credential Verification Engine

> **Project:** Sewa Setu Innovation — Automated Credential Verification Engine  
> **Classification:** Gov-AI Identity Assurance, Spatial OCR & Storage Pipeline  
> **Technologies:** Python 3.10+, OpenCV, RapidOCR (ONNX), RapidFuzz, FastAPI, SQLite3, Vanilla HTML5/CSS3  

---

## 📑 Table of Contents

1. [Introduction & Governance Mandate](#1-introduction--governance-mandate)
2. [System Architecture & Dataflow](#2-system-architecture--dataflow)
3. [Decoupled Multi-Tier Structure](#3-decoupled-multi-tier-structure)
4. [AI Automation Pipeline Deep Dive](#4-ai-automation-pipeline-deep-dive)
   - [4.1 Preprocessing & Straightening (`preprocessor.py`)](#41-preprocessing--straightening)
   - [4.2 Spatial OCR & Token Extraction (`extractor.py`)](#42-spatial-ocr--token-extraction)
   - [4.3 Domain Identity Parsers](#43-domain-identity-parsers)
   - [4.4 Fuzzy Matching & Scoring (`matcher.py`)](#44-fuzzy-matching--scoring)
5. [Persistent Storage System & SQLite Schema](#5-persistent-storage-system--sqlite-schema)
6. [REST API Specification](#6-rest-api-specification)
7. [Decision Tiers & Routing Matrix](#7-decision-tiers--routing-matrix)
8. [Color View & Theme System](#8-color-view--theme-system)
9. [Automated Test Suite & Benchmarks](#9-automated-test-suite--benchmarks)
10. [Troubleshooting & Operations Guide](#10-troubleshooting--operations-guide)

---

## 1. Introduction & Governance Mandate

Public administration platforms require identity verification for millions of citizens uploading smartphone photos of official credentials (**Aadhaar cards, PAN cards, Voter IDs, Driving Licenses**).

Traditional validation pipelines frequently fail or trigger unfair automated rejections because:
- Smartphone cameras are held at an angle (rotation tilt/skew).
- Document lighting is uneven or images are slightly blurry.
- Official cards feature complex background Guilloche patterns.
- Names and addresses contain minor abbreviations (e.g. `Rd` vs `Road`, `Dist` vs `District`).

### The Non-Punitive Assurance Mandate
> **Core Policy:** *A low match score measures imaging degradation, contrast, or technical uncertainty—never citizen guilt or fraudulent intent.*

Under this engine's governance rules:
- Clean credentials with high confidence (>= 95%) are **instantly approved**.
- Credentials with minor textual differences (50% to 94%) are **accepted with routine audit logging**.
- Low-confidence credentials (< 50%) are **routed to a human officer for manual check**—**never automatically rejected**.
- Conflicting ID numbers or dates of birth are flagged as a **critical mismatch** for explicit officer inspection.

---

## 2. System Architecture & Dataflow

```mermaid
flowchart TD
    subgraph Ingestion ["1. Document Ingestion"]
        Upload[Citizen Upload\nFront: Required | Back: Optional] --> Pre[DocumentPreprocessor]
    end

    subgraph Preprocess ["2. Vision Preprocessing"]
        Pre --> Deskew[Contour Analysis & minAreaRect Deskew]
        Pre --> Denoise[Bilateral Filtering Noise Reduction]
        Pre --> PDF[300 DPI PDF Rasterization]
    end

    subgraph OCR ["3. Spatial OCR & Tokenization"]
        Deskew & Denoise & PDF --> Rapid[RapidOCR ONNX Engine]
        Rapid --> Tokens[Spatial Tokens with [x, y, w, h] Coordinates]
    end

    subgraph Parsing ["4. Domain Identity Parsers"]
        Tokens --> Parsers[Name, DOB/YOB, Gender, ID Number, Address Parsers]
    end

    subgraph Scoring ["5. Fuzzy Matching & Tier Routing"]
        Parsers --> Matcher[RapidFuzz Token Sort & Set Ratio]
        Form[Submitted Application Data] --> Matcher
        Matcher --> Tier{Decision Tier Evaluation}
    end

    subgraph Persistence ["6. Storage & Audit Vault"]
        Tier --> SQLite[(storage/database.sqlite)]
        Tier --> Files[storage/uploads/ & storage/crops/]
    end
```

---

## 3. Decoupled Multi-Tier Structure

The repository maintains strict separation of concerns across four clean directories:

| Directory | Layer | Purpose |
| :--- | :--- | :--- |
| **`ai_automation/`** | Core AI Engine | Standalone OCR, rotation deskewing, fuzzy matching, and field cropping. Zero web dependencies. |
| **`backend/`** | Web Server & Storage | FastAPI REST API, request validation, SQLite persistence, and static asset serving. |
| **`frontend/`** | User Interface | Vanilla HTML5/CSS3/JS interface with 1-click demos, live bounding boxes, and records vault. |
| **`storage/`** | Persistent Archive | Zero-configuration local storage containing `database.sqlite`, raw uploads, and crop snippets. |

---

## 4. AI Automation Pipeline Deep Dive

### 4.1 Preprocessing & Straightening
- **File:** [`ai_automation/preprocessor.py`](file:///e:/SEWA-SETU-INNOVATION/ai_automation/preprocessor.py)
- **Multi-Format Ingestion:** Accepts image files (`.png`, `.jpg`, `.webp`, `.tiff`), raw byte streams, and multi-page PDFs (rendered at 300 DPI via `pypdfium2`).
- **Rotation Deskewing:** Uses OpenCV contour analysis and `minAreaRect` to calculate document tilt (up to 45 degrees). Applies affine matrix rotation with expanded bounds so document corners are never clipped.
- **Color Preservation:** Keeps images in full color for deep-learning OCR models, while applying bilateral filtering (`cv2.bilateralFilter`) to smooth background noise while keeping font edges razor-sharp.

### 4.2 Spatial OCR & Token Extraction
- **File:** [`ai_automation/extractor.py`](file:///e:/SEWA-SETU-INNOVATION/ai_automation/extractor.py)
- **RapidOCR ONNX Models:** Uses lightweight ONNX models for text detection (DBNet) and text recognition (CRNN/SVTR).
- **Spatial Bounding Boxes:** Every detected word/token retains its exact bounding box:
  $$\text{bbox} = [x, y, \text{width}, \text{height}]$$
- **Fused-Word Repair:** Automatically fixes common OCR spacing fusion (e.g. `BokamLeeladhar` -> `Bokam Leeladhar`, `HNO1-63/b` -> `HNO 1-63/b`).

### 4.3 Domain Identity Parsers
- **Full Name:** Detects labeled names (`Name: ...`), lines following `To`, or text preceding `Year of Birth`, `Gender`, or `S/O`.
- **Date / Year of Birth:** Supports full dates (`DD/MM/YYYY`) and 4-digit `Year of Birth: YYYY`. If the 4-digit year matches, it is treated as a valid canonical match.
- **Gender:** Recognizes `Male`, `Female`, `Transgender`, Aadhaar `/Male`, `/Female`, and bilingual Hindi/regional terms (`पुरुष`, `महिला`).
- **Document ID:** Identifies Aadhaar (12-digit spaced/compact), PAN (5 letters + 4 digits + 1 letter), Voter ID, and Driving Licenses.
- **Address:** Extracts complete multi-line address spans from parentage markers (`S/O`, `D/O`, `W/O`, `C/O`, `HNO`) down to the 6-digit postal PIN code (`531035`).

### 4.4 Fuzzy Matching & Scoring
- **File:** [`ai_automation/matcher.py`](file:///e:/SEWA-SETU-INNOVATION/ai_automation/matcher.py)
- **Name Similarity:** Evaluates Token Sort Ratio and Jaro-Winkler distance to handle reversed name order (e.g. `Leeladhar Bokam` vs `Bokam Leeladhar`).
- **Address Similarity:** Uses Token Set Ratio to compare concise citizen submissions with verbose postal card lines.
- **Critical Gating:** Enforces strict validation on ID Number and Date of Birth. If either conflicts, a critical mismatch flag is raised.

---

## 5. Persistent Storage System & SQLite Schema

All verification runs, uploaded files, and generated snippets are saved automatically to the `storage/` folder.

### Directory Layout
```text
storage/
├── database.sqlite             # SQLite3 database containing full audit logs
├── uploads/                    # Original uploaded front & back documents
│   └── VERIF-<ID>_front.png
├── annotations/                # Highlighted document views with bounding boxes
│   └── VERIF-<ID>_front_annotated.png
└── crops/                      # High-resolution snippets of each field
    └── VERIF-<ID>/
        ├── name.png
        ├── dob.png
        ├── document_id.png
        ├── gender.png
        └── address.png
```

### SQLite Database Table (`verification_records`)
```sql
CREATE TABLE IF NOT EXISTS verification_records (
    id TEXT PRIMARY KEY,                       -- e.g. VERIF-20260928012705-81A4CD
    timestamp DATETIME NOT NULL,               -- ISO timestamp
    applicant_name TEXT,                       -- Name entered by applicant
    dob TEXT,                                  -- Date/year of birth
    gender TEXT,                               -- Gender
    document_id TEXT,                          -- ID number
    address TEXT,                              -- Residential address
    overall_score REAL NOT NULL,               -- Composite match score (0.0 to 100.0)
    tier TEXT NOT NULL,                        -- HIGH, MEDIUM, LOW, CRITICAL_MISMATCH
    critical_flag INTEGER NOT NULL,            -- 1 if critical discrepancy, else 0
    manual_review_priority INTEGER NOT NULL,   -- 1 if queued for manual review
    has_back_document INTEGER NOT NULL,        -- 1 if back document was provided
    front_filename TEXT,
    back_filename TEXT,
    front_file_path TEXT,
    back_file_path TEXT,
    annotated_front_path TEXT,
    annotated_back_path TEXT,
    crops_dir TEXT,
    audit_json TEXT NOT NULL                   -- Full JSON audit snapshot
);

CREATE INDEX IF NOT EXISTS idx_timestamp ON verification_records (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_tier ON verification_records (tier);
CREATE INDEX IF NOT EXISTS idx_name ON verification_records (applicant_name);
CREATE INDEX IF NOT EXISTS idx_doc_id ON verification_records (document_id);
```

---

## 6. REST API Specification

Base URL: `http://localhost:8000`

### 6.1 Run Verification: `POST /api/verify`
Accepts `multipart/form-data`:

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `front_file` | File | **Yes** | Front photo of document (`.png`, `.jpg`, `.pdf`) |
| `back_file` | File | No | Back photo of document (used for address) |
| `name` | String | No | Applicant name |
| `dob` | String | No | Applicant date or year of birth |
| `gender` | String | No | Applicant gender (`Male`, `Female`, etc.) |
| `document_id` | String | No | Document ID number |
| `address` | String | No | Residential address |
| `deskew` | Boolean | No | Enable rotation straightening (default: `true`) |

#### Response:
```json
{
  "record_id": "VERIF-20260928012705-81A4CD",
  "audit": {
    "overall_score": 99.1,
    "tier": "HIGH",
    "critical_flag": false,
    "manual_review_priority": false,
    "fields": {
      "name": {
        "submitted": "Bokam Leeladhar",
        "ocr_text": "Bokam Leeladhar",
        "score": 100.0,
        "status": "match",
        "bbox": [230, 160, 240, 28],
        "doc_side": "front"
      },
      "dob": { "score": 100.0, "status": "match" },
      "document_id": { "score": 100.0, "status": "match" },
      "gender": { "score": 100.0, "status": "match" },
      "address": { "score": 96.5, "status": "match", "doc_side": "back" }
    }
  },
  "images": {
    "front_annotated": "data:image/png;base64,...",
    "back_annotated": "data:image/png;base64,..."
  },
  "crops": {
    "name": "/api/records/VERIF-.../crops/name.png",
    "dob": "/api/records/VERIF-.../crops/dob.png",
    "address": "/api/records/VERIF-.../crops/address.png"
  }
}
```

### 6.2 Get Records: `GET /api/records`
- **Query Params:**
  - `limit` (int, default: 50): Number of records.
  - `offset` (int, default: 0): Paging offset.
  - `tier` (str, optional): Filter by `HIGH`, `MEDIUM`, `LOW`, or `CRITICAL_MISMATCH`.
  - `search` (str, optional): Search keyword matching applicant name or ID number.

### 6.3 Get Single Record: `GET /api/records/{id}`
Returns the full stored record and JSON audit.

### 6.4 Delete Record: `DELETE /api/records/{id}`
Deletes the SQLite database row and purges the associated image crops from disk.

### 6.5 Storage Stats: `GET /api/storage/stats`
Returns total records count, breakdown by tier, and database location.

---

## 7. Decision Tiers & Routing Matrix

| Tier | Score Range | Meaning | System Action |
| :--- | :--- | :--- | :--- |
| **HIGH** | >= 95.0% | Clean document, exact or near-exact match. | **Automated Validation** (Instant pass) |
| **MEDIUM** | 50.0% to 94.9% | Minor textual differences (abbreviations, spacing). | **Standard Acceptance** (Routine audit log) |
| **LOW** | < 50.0% | Photo was blurry, dark, or low resolution. | **Priority Manual Review** *(Never auto-rejected)* |
| **CRITICAL_MISMATCH** | Any Score | Conflicting ID number or birth date. | **Flagged for Officer Fraud Review** |

---

## 8. Color View & Theme System

### 8.1 Website Themes
Users can toggle between three visual themes in the header:
- **🌙 Dark Obsidian:** `#080c14` background with cyber-indigo highlights.
- **☀️ Clean Light:** `#f8fafc` background with crisp jet-black text (`#0f172a`) and white elevated cards.
- **💎 Royal Sapphire:** `#060e22` background with deep royal-blue tones.

### 8.2 Document Bounding Box Color Scheme
Bounding boxes on documents are drawn with filled label pills for maximum legibility over Guilloche background patterns:
- 🟠 **Full Name:** Vibrant Orange (`#f97316`)
- 🟢 **Birth Date / Year:** Emerald Green (`#10b981`)
- 🔵 **Document ID Number:** Royal Electric Blue (`#2563eb`)
- 🌸 **Gender:** Vivid Pink (`#ec4899`)
- 🟣 **Address Block:** Rich Purple (`#a855f7`)

---

## 9. Automated Test Suite & Benchmarks

Run all automated unit and integration tests:

```powershell
pytest -v test_engine.py
```

### Verified Benchmark Scenarios
| Test ID | Test Scenario | Verified Outcome |
| :--- | :--- | :--- |
| `test_case_1_high_confidence` | Clean ID document with exact fields | **Tier: HIGH** (Score: 100%) |
| `test_case_2_skewed_and_fuzzy` | 7-degree camera tilt with address abbreviations | **Tier: MEDIUM** (Deskewed, Score >= 80%) |
| `test_case_3_critical_mismatch` | Matching name & address, but conflicting ID number | **Tier: CRITICAL_MISMATCH** (Score capped to 0.0) |
| `test_case_4_low_score_non_punitive` | Severe imaging noise and low contrast | **Tier: LOW** (Manual review priority = True, no auto-reject) |
| `test_case_5_pdf_processing` | Vector & raster PDF rendered at 300 DPI | **Tier: HIGH** (Correct spatial bounding boxes) |

---

## 10. Troubleshooting & Operations Guide

### Issue: "Port 8000 is already in use"
Run on another port or terminate the existing process:
```powershell
# Windows PowerShell
Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process -Force
```

### Issue: Bounding boxes look tilted
Ensure `deskew: true` is enabled in the upload form (checked by default).

### Issue: Windows console character display
If terminal displays question marks for symbols, configure UTF-8 output:
```python
import sys
sys.stdout.reconfigure(encoding="utf-8")
```
*(Handled automatically in `backend/main.py` and `server.py`).*
