"""
FastAPI Backend Server for Automated Credential Verification Engine.
Provides REST API endpoints, SQLite storage management, and serves the modern Web Frontend.
Can be run via: python backend/main.py or python server.py
"""

from __future__ import annotations

import base64
import io
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure safe UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import cv2
import numpy as np
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ai_automation.pipeline import VerificationEngine
from backend.storage import StorageManager

FRONTEND_DIR = PROJECT_ROOT / "frontend"

app = FastAPI(
    title="Sewa Setu - Credential Verification Engine API",
    description="Gov-AI Citizen Identity Verification API with Non-Punitive Assurance Routing & Persistent Storage",
    version="2.0.0",
)

# Enable CORS for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Engine and Storage singletons
engine = VerificationEngine(ocr_backend="auto")
storage = StorageManager()

COLOR_MAP = {
    "name": (0, 150, 255),        # Orange
    "dob": (0, 200, 0),           # Green
    "document_id": (255, 50, 50), # Blue
    "gender": (255, 105, 180),    # Pink
    "address": (200, 0, 200),     # Magenta
}


def image_to_base64(img: np.ndarray, ext: str = ".png") -> str:
    """Encodes an OpenCV BGR image array into a base64 Data URL."""
    success, buffer = cv2.imencode(ext, img)
    if not success:
        return ""
    b64_str = base64.b64encode(buffer).decode("utf-8")
    return f"data:image/png;base64,{b64_str}"


def draw_bounding_boxes(
    image: np.ndarray, fields: Dict[str, Any], filter_side: Optional[str] = None
) -> np.ndarray:
    """Draws high-visibility colored bounding boxes with filled label badges."""
    annotated = image.copy()
    for fname, fdata in fields.items():
        if filter_side and fdata.get("doc_side", "front") != filter_side:
            continue
        bbox = fdata.get("bbox")
        if bbox and len(bbox) == 4 and bbox[2] > 0 and bbox[3] > 0:
            x, y, w, h = bbox
            color = COLOR_MAP.get(fname, (0, 220, 255))
            # Draw primary bounding box outline
            cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 3)

            label = f"{fname.replace('_', ' ').upper()} ({fdata.get('score', 0):.0f}%)"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.50
            thickness = 1
            (tw, th), baseline = cv2.getTextSize(label, font, font_scale, thickness)

            # Draw filled header pill for label so text is always 100% visible
            label_y = max(th + 6, y)
            cv2.rectangle(
                annotated,
                (x, label_y - th - 6),
                (x + tw + 8, label_y + 2),
                color,
                -1,
            )
            # Text drawn in white over colored pill
            cv2.putText(
                annotated,
                label,
                (x + 4, label_y - 2),
                font,
                font_scale,
                (255, 255, 255),
                thickness,
                cv2.LINE_AA,
            )
    return annotated


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Sewa Setu Credential Verification Engine",
        "version": "2.0.0",
        "features": [
            "spatial_ocr",
            "non_punitive_assurance",
            "front_mandatory_back_optional",
            "multi_metric_fuzzy_matching",
            "persistent_sqlite_storage",
        ],
    }


@app.post("/api/verify")
async def verify_credential(
    front_file: UploadFile = File(..., description="Mandatory Front-side document image or PDF"),
    back_file: Optional[UploadFile] = File(None, description="Optional Back-side document image or PDF"),
    name: Optional[str] = Form(None),
    dob: Optional[str] = Form(None),
    gender: Optional[str] = Form(None),
    document_id: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    deskew: bool = Form(True),
):
    """
    Core verification endpoint.
    Ingests Front image (mandatory) and Back image (optional),
    runs extraction, fuzzy/exact matching, persists audit data to SQLite,
    and returns annotated images & crops.
    """
    try:
        front_bytes = await front_file.read()
        if not front_bytes:
            raise HTTPException(status_code=400, detail="Front document file is empty.")

        back_bytes = None
        if back_file is not None and back_file.filename:
            raw_back = await back_file.read()
            if raw_back:
                back_bytes = raw_back

        # Construct submitted data dict
        submitted_data: Dict[str, str] = {}
        if name and name.strip():
            submitted_data["name"] = name.strip()
        if dob and dob.strip():
            submitted_data["dob"] = dob.strip()
        if gender and gender.strip():
            submitted_data["gender"] = gender.strip()
        if document_id and document_id.strip():
            submitted_data["document_id"] = document_id.strip()
        if address and address.strip():
            submitted_data["address"] = address.strip()

        # Run verification engine
        pipeline_res = engine.verify_with_audit(
            document_source=front_bytes,
            submitted_data=submitted_data,
            back_document_source=back_bytes,
            deskew=deskew,
        )

        audit_json = pipeline_res.audit_json
        preprocessed_front = pipeline_res.preprocessed
        preprocessed_back = pipeline_res.back_preprocessed

        # Generate annotated front image
        annotated_front = draw_bounding_boxes(
            preprocessed_front.deskewed_color_image,
            audit_json["fields"],
            filter_side="front" if pipeline_res.has_back_document else None,
        )
        front_b64 = image_to_base64(annotated_front)

        # Generate annotated back image if provided
        annotated_back = None
        back_b64 = None
        if pipeline_res.has_back_document and preprocessed_back is not None:
            annotated_back = draw_bounding_boxes(
                preprocessed_back.deskewed_color_image,
                audit_json["fields"],
                filter_side="back",
            )
            back_b64 = image_to_base64(annotated_back)

        # Generate individual field crops
        crops: Dict[str, Optional[str]] = {}
        raw_crop_mats: Dict[str, np.ndarray] = {}
        for fname, fdata in audit_json["fields"].items():
            bbox = fdata.get("bbox")
            doc_side = fdata.get("doc_side", "front")
            target_img = (
                preprocessed_back.deskewed_color_image
                if (doc_side == "back" and preprocessed_back is not None)
                else preprocessed_front.deskewed_color_image
            )
            if bbox and len(bbox) == 4 and bbox[2] > 0 and bbox[3] > 0:
                crop = engine.crop_field(target_img, bbox, padding=8)
                if crop is not None:
                    crops[fname] = image_to_base64(crop)
                    raw_crop_mats[fname] = crop
                else:
                    crops[fname] = None
            else:
                crops[fname] = None

        # Persist full verification record to Storage System
        record_id = storage.save_verification(
            submitted_data=submitted_data,
            audit_json=audit_json,
            front_bytes=front_bytes,
            front_filename=front_file.filename or "front.jpg",
            back_bytes=back_bytes,
            back_filename=back_file.filename if back_file else None,
            annotated_front_img=annotated_front,
            annotated_back_img=annotated_back,
            crop_images=raw_crop_mats,
        )

        return {
            "success": True,
            "record_id": record_id,
            "audit": audit_json,
            "images": {
                "front_annotated": front_b64,
                "back_annotated": back_b64,
            },
            "crops": crops,
            "meta": {
                "has_back_document": pipeline_res.has_back_document,
                "front_filename": front_file.filename,
                "back_filename": back_file.filename if back_file else None,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")


# -----------------------------------------------------------------------------
# Storage & Records API Endpoints
# -----------------------------------------------------------------------------

@app.get("/api/records")
async def list_verification_records(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    tier: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    """Retrieves list of stored verification records with optional filters."""
    records = storage.list_records(limit=limit, offset=offset, tier=tier, search=search)
    return {
        "success": True,
        "count": len(records),
        "records": records,
    }


@app.get("/api/records/{record_id}")
async def get_verification_record(record_id: str):
    """Retrieves full details of a specific stored verification record."""
    record = storage.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Record '{record_id}' not found.")
    return {
        "success": True,
        "record": record,
    }


@app.delete("/api/records/{record_id}")
async def delete_verification_record(record_id: str):
    """Deletes a stored verification record and its files from storage."""
    deleted = storage.delete_record(record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Record '{record_id}' not found.")
    return {
        "success": True,
        "deleted_id": record_id,
    }


@app.get("/api/storage/stats")
async def get_storage_stats():
    """Retrieves storage system summary metrics."""
    stats = storage.get_stats()
    return {
        "success": True,
        "stats": stats,
    }


# Serve frontend static assets
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(FRONTEND_DIR / "index.html")


def start_server(host: str = "127.0.0.1", port: int = 8000, reload: bool = False):
    """Starts the Uvicorn web server."""
    print("=" * 70)
    print(" [*] STARTING SEWA SETU CREDENTIAL VERIFICATION SERVER")
    print("=" * 70)
    print(f" Backend API  : http://{host}:{port}/api/health")
    print(f" Records API  : http://{host}:{port}/api/records")
    print(f" Storage Stats: http://{host}:{port}/api/storage/stats")
    print(f" Swagger Docs : http://{host}:{port}/docs")
    print(f" Web Frontend : http://{host}:{port}")
    print("=" * 70)
    uvicorn.run("backend.main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    start_server()
