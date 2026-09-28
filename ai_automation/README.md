# 🧠 AI Automation Engine — Sewa Setu

> **Core Document Vision, Spatial OCR, Fuzzy Matching & Scoring Pipeline**  
> *A self-contained Python package for Indian identity document processing.*

---

## 📂 Modules & Architecture

```text
ai_automation/
├── preprocessor.py      # Photo deskewing, noise filtering, 300 DPI PDF rendering
├── extractor.py         # RapidOCR spatial tokenization & Indian document parsers
├── matcher.py           # RapidFuzz similarity scoring & decision tier classification
├── pipeline.py          # Unified VerificationEngine orchestrator & image cropper
├── requirements.txt     # AI engine dependencies
└── README.md            # This documentation
```

---

## ⚙️ Module Responsibilities

| File | Core Role |
| :--- | :--- |
| **`preprocessor.py`** | Multi-format loading (Pillow, OpenCV), 300 DPI PDF rasterization via `pypdfium2`, contour foreground `minAreaRect` affine deskewing (up to 45 degrees) without corner clipping, and bilateral edge-preserving noise reduction. |
| **`extractor.py`** | Spatial OCR tokenization with exact bounding boxes `[x, y, w, h]`, clarity confidence scores, fused-word repair, and domain regex/context parsers for `full_name`, `dob`, `gender`, `document_id`, and multi-line Indian `address` blocks. |
| **`matcher.py`** | RapidFuzz similarity algorithms (Token Sort, Jaro-Winkler, Levenshtein), subset address matching (`token_set_ratio`), exact critical gating (DOB/YOB, gender, ID), and non-punitive confidence tier classification (`HIGH`, `MEDIUM`, `LOW`, `CRITICAL_MISMATCH`). |
| **`pipeline.py`** | `VerificationEngine` orchestrator integrating preprocessing, extraction, cross-side evaluation (`evaluate_multi` for front mandatory + back optional), and `crop_field()` safety bounding-box cropper. |

---

## 🚀 Standalone Python Usage

```python
from ai_automation.pipeline import VerificationEngine

# Initialize engine (loads RapidOCR ONNX models once)
engine = VerificationEngine(ocr_backend="auto")

# Run verification
result = engine.verify(
    document_source="path/to/front.jpg",
    submitted_data={
        "name": "Bokam Leeladhar",
        "dob": "2003",
        "gender": "Male",
        "document_id": "5513 1404 1007",
        "address": "1-63/b, Gullepalli, Sabbavaram Mandalam, Visakhapatnam"
    },
    back_document_source="path/to/back.jpg",  # Optional reverse side
    deskew=True
)

print(f"Overall Match Score: {result['overall_score']}%")
print(f"Decision Tier: {result['tier']}")
print(f"Fields Analyzed: {len(result['fields'])}")
```

---

## 🧪 Testing the Engine

Run pytest to execute all engine benchmarks:

```powershell
pytest -v test_engine.py
```
