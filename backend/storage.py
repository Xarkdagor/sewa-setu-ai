"""
Storage System for Sewa Setu Credential Verification Engine.
Provides persistent SQLite database storage for audit records,
file storage for uploaded documents, annotated images, and cropped snippets.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np


def _safe_imwrite(path: Path, img: np.ndarray) -> bool:
    """Safely writes an image file across arbitrary Unicode paths on Windows."""
    try:
        success, buffer = cv2.imencode(".png", img)
        if success:
            path.write_bytes(buffer.tobytes())
            return True
        return False
    except Exception:
        return False


class StorageManager:
    """
    Manages persistent SQLite records and document file artifacts.
    """

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = (base_dir or Path(__file__).resolve().parent.parent / "storage").resolve()
        self.uploads_dir = self.base_dir / "uploads"
        self.annotations_dir = self.base_dir / "annotations"
        self.crops_dir = self.base_dir / "crops"
        self.db_path = self.base_dir / "database.sqlite"

        # Ensure directory structures exist
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.annotations_dir.mkdir(parents=True, exist_ok=True)
        self.crops_dir.mkdir(parents=True, exist_ok=True)

        self._init_db()

    @contextmanager
    def _connection(self):
        """Context manager yielding a SQLite connection and guaranteeing closure on exit."""
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initializes tables and indexes if they do not exist."""
        with self._connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS verification_records (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    applicant_name TEXT,
                    dob TEXT,
                    gender TEXT,
                    document_id TEXT,
                    address TEXT,
                    overall_score REAL NOT NULL,
                    tier TEXT NOT NULL,
                    critical_flag INTEGER NOT NULL,
                    manual_review_priority INTEGER NOT NULL,
                    has_back_document INTEGER NOT NULL,
                    front_filename TEXT,
                    back_filename TEXT,
                    front_file_path TEXT,
                    back_file_path TEXT,
                    annotated_front_path TEXT,
                    annotated_back_path TEXT,
                    crops_dir TEXT,
                    audit_json TEXT NOT NULL
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_records_time ON verification_records(timestamp DESC);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_records_tier ON verification_records(tier);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_records_name ON verification_records(applicant_name);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_records_docid ON verification_records(document_id);")

    def save_verification(
        self,
        submitted_data: Dict[str, str],
        audit_json: Dict[str, Any],
        front_bytes: bytes,
        front_filename: str,
        back_bytes: Optional[bytes] = None,
        back_filename: Optional[str] = None,
        annotated_front_img: Optional[np.ndarray] = None,
        annotated_back_img: Optional[np.ndarray] = None,
        crop_images: Optional[Dict[str, np.ndarray]] = None,
    ) -> str:
        """
        Persists a complete verification event:
        1. Saves raw uploaded files.
        2. Saves annotated bounding-box images.
        3. Saves individual cropped field snippets.
        4. Inserts indexed audit record into SQLite.
        """
        now = datetime.now()
        record_id = f"VERIF-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"

        # 1. Save uploaded documents
        front_ext = Path(front_filename).suffix or ".jpg"
        front_save_name = f"{record_id}_front{front_ext}"
        front_save_path = self.uploads_dir / front_save_name
        front_save_path.write_bytes(front_bytes)

        back_save_path = None
        if back_bytes and back_filename:
            back_ext = Path(back_filename).suffix or ".jpg"
            back_save_name = f"{record_id}_back{back_ext}"
            back_save_path = self.uploads_dir / back_save_name
            back_save_path.write_bytes(back_bytes)

        # 2. Save annotated bounding-box images
        annotated_front_path = None
        if annotated_front_img is not None:
            front_ann_name = f"{record_id}_front_annotated.png"
            annotated_front_path = self.annotations_dir / front_ann_name
            _safe_imwrite(annotated_front_path, annotated_front_img)

        annotated_back_path = None
        if annotated_back_img is not None:
            back_ann_name = f"{record_id}_back_annotated.png"
            annotated_back_path = self.annotations_dir / back_ann_name
            _safe_imwrite(annotated_back_path, annotated_back_img)

        # 3. Save field crops
        record_crops_dir = self.crops_dir / record_id
        record_crops_dir.mkdir(parents=True, exist_ok=True)
        if crop_images:
            for fname, crop_mat in crop_images.items():
                if crop_mat is not None and crop_mat.size > 0:
                    _safe_imwrite(record_crops_dir / f"{fname}.png", crop_mat)

        # 4. Insert into SQLite database
        overall_score = float(audit_json.get("overall_score", 0.0))
        tier = str(audit_json.get("tier", "UNKNOWN"))
        critical_flag = 1 if audit_json.get("critical_flag") else 0
        manual_review = 1 if audit_json.get("manual_review_priority") else 0
        has_back = 1 if back_bytes else 0

        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO verification_records (
                    id, timestamp, applicant_name, dob, gender, document_id, address,
                    overall_score, tier, critical_flag, manual_review_priority, has_back_document,
                    front_filename, back_filename, front_file_path, back_file_path,
                    annotated_front_path, annotated_back_path, crops_dir, audit_json
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?
                );
                """,
                (
                    record_id,
                    now.isoformat(),
                    submitted_data.get("name", ""),
                    submitted_data.get("dob", ""),
                    submitted_data.get("gender", ""),
                    submitted_data.get("document_id", ""),
                    submitted_data.get("address", ""),
                    overall_score,
                    tier,
                    critical_flag,
                    manual_review,
                    has_back,
                    front_filename,
                    back_filename or "",
                    str(front_save_path),
                    str(back_save_path) if back_save_path else "",
                    str(annotated_front_path) if annotated_front_path else "",
                    str(annotated_back_path) if annotated_back_path else "",
                    str(record_crops_dir),
                    json.dumps(audit_json),
                ),
            )

        return record_id

    def list_records(
        self,
        limit: int = 50,
        offset: int = 0,
        tier: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Queries stored verification records with filtering and search."""
        query = "SELECT * FROM verification_records WHERE 1=1"
        params: List[Any] = []

        if tier and tier.upper() != "ALL":
            query += " AND tier = ?"
            params.append(tier.upper())

        if search and search.strip():
            term = f"%{search.strip()}%"
            query += " AND (applicant_name LIKE ? OR document_id LIKE ? OR id LIKE ?)"
            params.extend([term, term, term])

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._connection() as conn:
            rows = conn.execute(query, params).fetchall()
            records = []
            for row in rows:
                d = dict(row)
                # Parse JSON string back to dict
                try:
                    d["audit_json"] = json.loads(d["audit_json"])
                except Exception:
                    pass
                records.append(d)
            return records

    def get_record(self, record_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single complete verification record by ID."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM verification_records WHERE id = ?", (record_id,)
            ).fetchone()
            if not row:
                return None
            d = dict(row)
            try:
                d["audit_json"] = json.loads(d["audit_json"])
            except Exception:
                pass
            return d

    def delete_record(self, record_id: str) -> bool:
        """Deletes a record and its associated files."""
        record = self.get_record(record_id)
        if not record:
            return False

        # Remove files safely
        for key in ["front_file_path", "back_file_path", "annotated_front_path", "annotated_back_path"]:
            p_str = record.get(key)
            if p_str:
                p = Path(p_str)
                if p.exists() and p.is_file():
                    try:
                        p.unlink()
                    except Exception:
                        pass

        # Remove crops dir
        crops_p_str = record.get("crops_dir")
        if crops_p_str:
            cdir = Path(crops_p_str)
            if cdir.exists() and cdir.is_dir():
                for f in cdir.glob("*"):
                    try:
                        f.unlink()
                    except Exception:
                        pass
                try:
                    cdir.rmdir()
                except Exception:
                    pass

        with self._connection() as conn:
            conn.execute("DELETE FROM verification_records WHERE id = ?", (record_id,))

        return True

    def get_stats(self) -> Dict[str, Any]:
        """Returns aggregate storage metrics (total records, tier breakdown)."""
        with self._connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM verification_records").fetchone()[0]
            tier_rows = conn.execute(
                "SELECT tier, COUNT(*) as count FROM verification_records GROUP BY tier"
            ).fetchall()
            tier_counts = {r["tier"]: r["count"] for r in tier_rows}

            return {
                "total_records": total,
                "tier_breakdown": tier_counts,
                "database_path": str(self.db_path),
                "storage_directory": str(self.base_dir),
            }
