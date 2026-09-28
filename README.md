#  Sewa Setu — Automated Credential Verification Engine

> **Gov-AI Identity Verification & Spatial Document Extraction Pipeline**  
> *A fast, fair, and reliable identity assurance system designed for citizen governance portals.*

[![Python Version](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![RapidOCR](https://img.shields.io/badge/RapidOCR-ONNX%20Runtime-orange)](https://github.com/RapidAI/RapidOCR)
[![SQLite](https://img.shields.io/badge/Storage-SQLite3%20Embedded-003B57?logo=sqlite)](https://sqlite.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## What is Sewa Setu Verification Engine?

In public governance platforms, citizens frequently upload photos or scanned copies of national credentials (e.g., **Aadhaar cards, PAN cards, Voter IDs, Driving Licenses**). These photos often suffer from:
- Camera tilt and rotation skew from hand-held smartphones
- Poor lighting, blurriness, or low resolution
- Background pattern noise (e.g., Aadhaar Guilloche waves)
- Minor textual differences (e.g., abbreviations like `Rd` vs `Road`)

Traditional portals rely on strict string matching or reject documents automatically when scans are imperfect. **Sewa Setu replaces brittle validation with:**
1. **Automatic Photo Straightening (Deskewing)** via OpenCV contour analysis.
2. **Spatial Deep-Learning OCR** via RapidOCR ONNX to extract exact bounding boxes `[x, y, width, height]`.
3. **Multi-Metric Fuzzy Matching** via RapidFuzz to handle real-world variations.
4. **Fair Citizen Guarantee**: Blurry or hard-to-read documents route to an officer for manual check—**never automatically rejected**.
5. **Built-in Storage & Audit Vault**: Every verification transaction, photo crop, and JSON audit log is saved automatically into a local SQLite database.

---

## Quickstart — Run in 3 Easy Steps

### Step 1: Install Dependencies
```powershell
pip install -r backend/requirements.txt
```

### Step 2: Start the Unified Server
```powershell
python server.py
```

### Step 3: Open in Browser
- **Web Application:** [http://localhost:8000](http://localhost:8000)
- **Interactive API Docs (Swagger):** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Storage Statistics:** [http://localhost:8000/api/storage/stats](http://localhost:8000/api/storage/stats)

---

## Project Architecture

The codebase is organized into **three independent tiers** plus persistent storage:

```text
SEWA-SETU-INNOVATION/
│
├──  ai_automation/          # Tier 1: Core AI & Document Processing
│   ├── preprocessor.py        # Photo deskewing, noise filtering, 300 DPI PDF rendering
│   ├── extractor.py           # Spatial OCR tokenization & Indian document parsing
│   ├── matcher.py             # RapidFuzz similarity scoring & classification tiers
│   ├── pipeline.py            # Unified VerificationEngine orchestrator & image cropper
│   ├── requirements.txt       # AI engine dependencies
│   └── README.md              # AI engine usage guide
│
├──  backend/                # Tier 2: FastAPI REST API & Storage
│   ├── main.py                # Server routes (/api/verify, /api/records, /api/storage/stats)
│   ├── storage.py             # SQLite3 persistent database & media file manager
│   ├── requirements.txt       # Backend dependencies
│   └── README.md              # Backend developer guide
│
├──  frontend/               # Tier 3: Modern Web Client
│   ├── index.html             # Clean UI with 2-sided dropzones & Audit Vault
│   ├── style.css              # Modern design system (Dark, Light, Sapphire themes)
│   ├── app.js                 # 1-Click demos, live bounding boxes & records viewer
│   ├── samples/               # 1-click test cards (Aadhaar & Citizen ID)
│   └── README.md              # Frontend guide
│
├──  storage/                # Tier 4: Persistent Data Storage
│   ├── database.sqlite        # SQLite3 verification history database
│   ├── uploads/               # Raw uploaded front & back citizen documents
│   ├── annotations/           # Highlighted documents with bounding boxes
│   └── crops/                 # High-resolution snippets of each field
│
├── server.py                  # Root launcher (python server.py)
├── test_engine.py             # Comprehensive test suite (pytest)
├── sample_batch.json          # Template for batch document processing
└── DOCUMENTATION.md           # Complete technical and developer documentation
```

---

##  Key Features

| Feature | Description |
| :--- | :--- |
| **Two-Sided Upload** | Front side is mandatory. Back side is optional (used when address or parent's name is on the reverse). |
| **1-Click Test Demos** | Click **"Sample Aadhaar"** or **"Sample ID"** to test with preloaded sample images and form data in 1 click. |
| **Auto-Straighten** | Automatically corrects photo rotation (up to 45 degrees) and filters out scanner noise. |
| **Exact Bounding Boxes** | Displays color-coded highlight boxes on the physical document so you can see where each detail was found. |
| **Field-by-Field Snippets** | Automatically crops Name, Birth Date, ID Number, Gender, and Address from the document for side-by-side comparison. |
| **Persistent Audit Vault** | Search and inspect past verification records, view match percentages, and delete old entries. |
| **Color View Themes** | Toggle between **🌙 Dark Obsidian**, **☀️ Clean Light**, and **💎 Royal Sapphire** themes with 1 click. |

---

##  Verification Results & Decision Tiers

| Result Tier | Match Score | What It Means | Action Taken |
| :--- | :--- | :--- | :--- |
| **HIGH MATCH** | 95% to 100% | All details match the physical card tokens. | **Instant Automated Approval** |
| **MEDIUM MATCH** | 50% to 94% | Minor variations found (e.g. abbreviations). | **Accepted with routine audit log** |
| **NEEDS REVIEW** | Below 50% | Photo was blurry, dark, or hard to read. | **Sent to officer for manual check** *(Never auto-rejected!)* |
| **DIFFERENCE FOUND** | Any Score | Explicit conflict in ID Number or Birth Date. | **Flagged for officer inspection** |

---

##  Core API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/verify` | Upload front/back documents + form data; runs AI check and saves record |
| `GET` | `/api/records` | List saved records (supports `?search=` and `?tier=` filters) |
| `GET` | `/api/records/{id}` | Get full record details, audit JSON, and photo snippet URLs |
| `DELETE` | `/api/records/{id}` | Delete a record and its saved photo crops |
| `GET` | `/api/storage/stats` | View total records, breakdown by tier, and database path |
| `GET` | `/api/health` | Health check and engine status |

---

##  Running Automated Tests

Run the full pytest suite covering deskewing, fuzzy matching, PDF processing, and critical gating:

```powershell
pytest -v test_engine.py
```

---

##  Additional Documentation

- **[DOCUMENTATION.md](file:///e:/SEWA-SETU-INNOVATION/DOCUMENTATION.md):** Complete technical guide, algorithms, database schema, and REST API specification.
- **[ai_automation/README.md](file:///e:/SEWA-SETU-INNOVATION/ai_automation/README.md):** Standalone AI engine documentation and Python usage examples.
- **[backend/README.md](file:///e:/SEWA-SETU-INNOVATION/backend/README.md):** Backend server guide, storage operations, and Swagger docs.
- **[frontend/README.md](file:///e:/SEWA-SETU-INNOVATION/frontend/README.md):** Frontend design system, themes, and client controller guide.
