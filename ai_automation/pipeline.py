"""
Automated Credential Verification Pipeline Orchestrator
Connects preprocessing, OCR spatial token extraction, regex field parsing,
and rapidfuzz confidence scoring into an integrated end-to-end interface.
Supports both single-sided and two-sided (front + back) citizen documents.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
from PIL import Image

from .extractor import DocumentExtractor, ExtractionResult
from .matcher import CredentialMatcher, MatchResult
from .preprocessor import DocumentPreprocessor, PreprocessResult


class AuditPipelineResult:
    """
    Structured container for full verification pipeline audit objects.
    Preserves backward compatibility: unpacks as a 4-tuple:
      (audit_json, preprocessed, extraction, match_res).
    Also provides attributes:
      - .audit_json
      - .preprocessed (front side)
      - .extraction (front side)
      - .match_res
      - .back_preprocessed (optional back side)
      - .back_extraction (optional back side)
      - .has_back_document (bool)
    """

    def __init__(
        self,
        audit_json: Dict[str, Any],
        preprocessed: PreprocessResult,
        extraction: ExtractionResult,
        match_res: MatchResult,
        back_preprocessed: Optional[PreprocessResult] = None,
        back_extraction: Optional[ExtractionResult] = None,
    ):
        self.audit_json = audit_json
        self.preprocessed = preprocessed
        self.extraction = extraction
        self.match_res = match_res
        self.back_preprocessed = back_preprocessed
        self.back_extraction = back_extraction
        self.has_back_document = back_preprocessed is not None

    def __iter__(self):
        return iter((self.audit_json, self.preprocessed, self.extraction, self.match_res))

    def __getitem__(self, idx):
        return (self.audit_json, self.preprocessed, self.extraction, self.match_res)[idx]

    def __len__(self):
        return 4


class VerificationEngine:
    """
    Unified Automated Credential Verification Engine.
    Executes:
    1. Preprocessing (deskew, denoise, adaptive thresholding).
    2. Spatial OCR Tokenization & Regex Field Parsing (with [x, y, w, h] boxes).
    3. RapidFuzz and Exact Attribute Matching & Non-punitive Tier Classification.
    4. Two-sided document support (front required, back optional).
    """

    def __init__(
        self,
        ocr_backend: str = "auto",
        target_dpi: int = 300,
        weights: Optional[Dict[str, float]] = None,
    ):
        self.preprocessor = DocumentPreprocessor(target_dpi=target_dpi)
        self.extractor = DocumentExtractor(backend=ocr_backend)
        self.matcher = CredentialMatcher(weights=weights)

    def verify(
        self,
        document_source: Union[str, Path, bytes, io.BytesIO, Image.Image, np.ndarray],
        submitted_data: Dict[str, str],
        back_document_source: Optional[Union[str, Path, bytes, io.BytesIO, Image.Image, np.ndarray]] = None,
        deskew: bool = True,
        page_index: int = 0,
    ) -> Dict[str, Any]:
        """
        Runs the full verification pipeline and returns structured JSON output.
        Supports optional back_document_source for two-sided documents.
        """
        audit_res = self.verify_with_audit(
            document_source=document_source,
            submitted_data=submitted_data,
            back_document_source=back_document_source,
            deskew=deskew,
            page_index=page_index,
        )
        res_dict = audit_res.match_res.to_dict()
        res_dict["has_back_document"] = audit_res.has_back_document
        return res_dict

    def verify_with_audit(
        self,
        document_source: Union[str, Path, bytes, io.BytesIO, Image.Image, np.ndarray],
        submitted_data: Dict[str, str],
        back_document_source: Optional[Union[str, Path, bytes, io.BytesIO, Image.Image, np.ndarray]] = None,
        deskew: bool = True,
        page_index: int = 0,
    ) -> AuditPipelineResult:
        """
        Runs the full verification pipeline across front and optional back documents,
        and returns both structured JSON and full pipeline objects for visualization
        and UI crop-and-compare.
        """
        preprocess_res = self.preprocessor.process(
            document_source, deskew=deskew, page_index=page_index
        )
        extraction_res = self.extractor.extract(preprocess_res)

        back_preprocess_res = None
        back_extraction = None
        if back_document_source is not None:
            back_preprocess_res = self.preprocessor.process(
                back_document_source, deskew=deskew, page_index=page_index
            )
            back_extraction = self.extractor.extract(back_preprocess_res)

        match_res = self.matcher.evaluate_multi(
            submitted_data, extraction_res, back_extraction=back_extraction
        )

        audit_json = match_res.to_extended_dict()
        audit_json["has_back_document"] = bool(back_document_source is not None)

        return AuditPipelineResult(
            audit_json=audit_json,
            preprocessed=preprocess_res,
            extraction=extraction_res,
            match_res=match_res,
            back_preprocessed=back_preprocess_res,
            back_extraction=back_extraction,
        )

    def crop_field(
        self, image: np.ndarray, bbox: List[int], padding: int = 4
    ) -> Optional[np.ndarray]:
        """
        Crops exact spatial field region from the document image for UI comparison.
        bbox is in [x, y, width, height] format.
        """
        x, y, w, h = bbox
        if w <= 0 or h <= 0:
            return None

        img_h, img_w = image.shape[:2]
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(img_w, x + w + padding)
        y2 = min(img_h, y + h + padding)

        return image[y1:y2, x1:x2].copy()
