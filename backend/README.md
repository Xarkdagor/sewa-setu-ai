# ⚙️ Backend & Storage API — Sewa Setu

> **FastAPI REST API & Persistent SQLite Audit Manager**  
> *Handles document verification requests, runs the AI engine, and archives results into SQLite.*

---

## 📂 Backend Structure

```text
backend/
├── main.py               # FastAPI application, route handlers, and static mounting
├── storage.py            # SQLite3 database manager & file storage handler
├── requirements.txt      # Backend Python dependencies
└── README.md             # This documentation
```

---

## 🚀 Running the Backend

You can run the backend from the root directory or directly from the `backend/` folder:

### Option 1: Root Launcher (Recommended)
```powershell
python server.py
```

### Option 2: Run Backend Directly
```powershell
python backend/main.py
```

### Option 3: Using Uvicorn CLI
```powershell
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

---

## 📡 REST API Reference

The server exposes the following endpoints on `http://localhost:8000`:

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/verify` | Upload document(s) and citizen data; returns verification scores and crop URLs. |
| `GET` | `/api/records` | Paginated list of past verification records. Supports `?search=` and `?tier=`. |
| `GET` | `/api/records/{id}` | Complete verification record with full audit JSON. |
| `DELETE` | `/api/records/{id}` | Permanently deletes record and associated crop files from disk. |
| `GET` | `/api/storage/stats` | System storage metrics (total records, breakdown by tier, disk location). |
| `GET` | `/api/health` | Health check and device capabilities. |
| `GET` | `/docs` | Interactive Swagger API documentation. |

---

## 💾 Storage System Layout

All files are stored in the root `storage/` directory:

```text
storage/
├── database.sqlite      # SQLite3 indexed verification history
├── uploads/             # Raw citizen uploaded images/PDFs
├── annotations/         # Highlighted documents with bounding boxes
└── crops/               # Field crop snippets (name, dob, id, address, gender)
```

---

## 🧪 Testing with Python Requests

```python
import requests

with open("path/to/front.png", "rb") as f:
    files = {"front_file": ("front.png", f, "image/png")}
    data = {
        "name": "Bokam Leeladhar",
        "dob": "2003",
        "document_id": "5513 1404 1007",
        "deskew": "true"
    }
    response = requests.post("http://localhost:8000/api/verify", files=files, data=data)
    print(response.json())
```
