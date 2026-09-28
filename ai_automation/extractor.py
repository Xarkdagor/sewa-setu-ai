"""
Document Extractor Module
Extracts OCR tokens with spatial bounding boxes ([x, y, width, height]),
confidences, and parses key identity fields (full_name, dob, address, document_id)
using regular expressions and token alignment.
"""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from PIL import Image

# Import preprocessor result
from .preprocessor import PreprocessResult


@dataclass
class OCRToken:
    """Represents a single word or text unit detected by OCR."""
    text: str
    bbox: List[int]  # [x, y, width, height]
    confidence: float  # 0.0 - 100.0
    line_num: int = 0
    block_num: int = 0

    @property
    def x(self) -> int:
        return self.bbox[0]

    @property
    def y(self) -> int:
        return self.bbox[1]

    @property
    def width(self) -> int:
        return self.bbox[2]

    @property
    def height(self) -> int:
        return self.bbox[3]

    @property
    def x2(self) -> int:
        return self.bbox[0] + self.bbox[2]

    @property
    def y2(self) -> int:
        return self.bbox[1] + self.bbox[3]


@dataclass
class ExtractedField:
    """Represents an extracted document field with text, bounding box, and OCR confidence."""
    field_name: str
    raw_text: str
    normalized_text: str
    bbox: List[int]  # [x, y, width, height]
    confidence: float  # OCR clarity/confidence score [0.0 - 100.0]
    matched_pattern: Optional[str] = None
    tokens: List[OCRToken] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_name": self.field_name,
            "raw_text": self.raw_text,
            "normalized_text": self.normalized_text,
            "bbox": self.bbox,
            "confidence": round(self.confidence, 2),
            "matched_pattern": self.matched_pattern,
        }


@dataclass
class ExtractionResult:
    """Encapsulates the complete extraction response for an image/document."""
    full_text: str
    tokens: List[OCRToken]
    fields: Dict[str, ExtractedField]
    image_shape: Tuple[int, int]  # (height, width)
    backend_used: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "full_text": self.full_text,
            "fields": {k: v.to_dict() for k, v in self.fields.items()},
            "image_shape": list(self.image_shape),
            "backend_used": self.backend_used,
            "token_count": len(self.tokens),
        }


class DocumentExtractor:
    """
    OCR Extractor supporting Tesseract and RapidOCR engines.
    Extracts text tokens with spatial bounding boxes [x, y, width, height]
    and applies domain regex parsers to map full_name, dob, address, and document_id.
    """

    # Common Tesseract Windows installation paths
    DEFAULT_TESSERACT_PATHS = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
    ]

    def __init__(
        self,
        backend: str = "auto",  # "auto", "pytesseract", "rapidocr"
        tesseract_cmd: Optional[str] = None,
    ):
        self.backend = backend.lower()
        self.tesseract_cmd = tesseract_cmd or self._find_tesseract()
        self._init_backend()

    def _find_tesseract(self) -> Optional[str]:
        """Locates tesseract executable from PATH or common directories."""
        which_path = shutil.which("tesseract")
        if which_path:
            return which_path
        for candidate in self.DEFAULT_TESSERACT_PATHS:
            if os.path.isfile(candidate):
                return candidate
        return None

    def _init_backend(self):
        """Initializes the active OCR backend."""
        self._pytesseract = None
        self._rapidocr = None

        if self.backend in ("auto", "pytesseract") and self.tesseract_cmd:
            try:
                import pytesseract
                pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd
                self._pytesseract = pytesseract
                self.active_backend = "pytesseract"
                return
            except Exception:
                pass

        # Try RapidOCR
        if self.backend in ("auto", "rapidocr"):
            try:
                from rapidocr_onnxruntime import RapidOCR
                self._rapidocr = RapidOCR()
                self.active_backend = "rapidocr"
                return
            except Exception:
                pass

        if self.backend == "pytesseract" and not self.tesseract_cmd:
            raise RuntimeError(
                "PyTesseract requested but tesseract binary not found in PATH or standard locations."
            )

        # Fallback to simulated / rapidocr if available
        self.active_backend = "rapidocr"
        from rapidocr_onnxruntime import RapidOCR
        self._rapidocr = RapidOCR()

    def extract_tokens(self, image: Union[np.ndarray, Image.Image, PreprocessResult]) -> List[OCRToken]:
        """
        Extracts words/tokens with exact bounding box [x, y, w, h] and confidence.
        """
        if isinstance(image, PreprocessResult):
            # For modern deep-learning OCR models (RapidOCR), color/grayscale preserves full character gradients
            if self.active_backend == "rapidocr":
                img_np = image.deskewed_color_image
            else:
                img_np = image.processed_image
        elif isinstance(image, Image.Image):
            img_np = np.array(image)
        else:
            img_np = image

        if self.active_backend == "pytesseract" and self._pytesseract:
            return self._extract_pytesseract(img_np)
        else:
            return self._extract_rapidocr(img_np)

    def _extract_pytesseract(self, image: np.ndarray) -> List[OCRToken]:
        """Extracts OCR tokens via pytesseract image_to_data."""
        from pytesseract import Output
        data = self._pytesseract.image_to_data(image, output_type=Output.DICT)
        tokens: List[OCRToken] = []
        n_boxes = len(data["text"])
        for i in range(n_boxes):
            text = (data["text"][i] or "").strip()
            conf_val = float(data["conf"][i]) if "conf" in data else 0.0
            if not text or conf_val < 0:
                continue

            x = int(data["left"][i])
            y = int(data["top"][i])
            w = int(data["width"][i])
            h = int(data["height"][i])
            lines_list = data.get("line_num", [])
            line = int(lines_list[i]) if i < len(lines_list) else 0
            blocks_list = data.get("block_num", [])
            block = int(blocks_list[i]) if i < len(blocks_list) else 0

            tokens.append(
                OCRToken(
                    text=text,
                    bbox=[x, y, w, h],
                    confidence=max(0.0, min(100.0, conf_val)),
                    line_num=line,
                    block_num=block,
                )
            )
        return tokens

    def _extract_rapidocr(self, image: np.ndarray) -> List[OCRToken]:
        """Extracts OCR tokens via RapidOCR."""
        # Ensure 3-channel BGR/RGB image for RapidOCR
        if len(image.shape) == 2:
            img_input = np.stack([image] * 3, axis=-1)
        else:
            img_input = image

        results, _ = self._rapidocr(img_input)
        if not results:
            return []

        tokens: List[OCRToken] = []
        for line_idx, item in enumerate(results):
            # item format: [polygon_points, text, confidence]
            poly, line_text, conf = item
            conf_pct = float(conf) * 100.0 if conf <= 1.0 else float(conf)
            line_text = (line_text or "").strip()
            if not line_text:
                continue

            pts = np.array(poly, dtype=np.float32)
            min_x = int(np.min(pts[:, 0]))
            min_y = int(np.min(pts[:, 1]))
            max_x = int(np.max(pts[:, 0]))
            max_y = int(np.max(pts[:, 1]))
            w = max(1, max_x - min_x)
            h = max(1, max_y - min_y)

            # Split line into words while approximating word spatial bounding boxes
            words = line_text.split()
            if len(words) <= 1:
                tokens.append(
                    OCRToken(
                        text=line_text,
                        bbox=[min_x, min_y, w, h],
                        confidence=conf_pct,
                        line_num=line_idx,
                    )
                )
            else:
                total_chars = sum(len(wrd) for wrd in words)
                cur_x = min_x
                for word in words:
                    word_w = max(1, int(w * (len(word) / max(1, total_chars))))
                    tokens.append(
                        OCRToken(
                            text=word,
                            bbox=[cur_x, min_y, word_w, h],
                            confidence=conf_pct,
                            line_num=line_idx,
                        )
                    )
                    cur_x += word_w + int(w * 0.02)  # small space offset
        return tokens

    @staticmethod
    def _compute_bounding_box(tokens: List[OCRToken]) -> List[int]:
        """Calculates enclosing [x, y, w, h] bounding box for a group of tokens."""
        if not tokens:
            return [0, 0, 0, 0]
        min_x = min(t.x for t in tokens)
        min_y = min(t.y for t in tokens)
        max_x = max(t.x2 for t in tokens)
        max_y = max(t.y2 for t in tokens)
        return [int(min_x), int(min_y), int(max(1, max_x - min_x)), int(max(1, max_y - min_y))]

    @staticmethod
    def _average_confidence(tokens: List[OCRToken]) -> float:
        """Returns average confidence score for tokens."""
        if not tokens:
            return 0.0
        return float(sum(t.confidence for t in tokens) / len(tokens))

    def _find_tokens_for_span(
        self,
        full_text: str,
        match_start: int,
        match_end: int,
        token_spans: List[Tuple[int, int, OCRToken]],
    ) -> List[OCRToken]:
        """Finds OCRTokens overlapping a given character start and end span."""
        matched: List[OCRToken] = []
        for span_start, span_end, token in token_spans:
            # Check overlap
            if max(match_start, span_start) < min(match_end, span_end):
                matched.append(token)
        return matched

    # -------------------------------------------------------------------------
    # Field Parsing Logic
    # -------------------------------------------------------------------------

    @staticmethod
    def _clean_spacing(text: str) -> str:
        """Separates fused CamelCase words and numbers for optimal readability."""
        if not text:
            return ""
        # Separate lower followed by uppercase (e.g. BokamHaritha -> Bokam Haritha)
        s = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
        # Separate care-of prefixes (e.g. D/OBokam -> D/O Bokam)
        s = re.sub(r"(?i)\b([dswc]\/o)([a-zA-Z])", r"\1 \2", s)
        # Separate house numbers (e.g. HNO1 -> HNO 1)
        s = re.sub(r"(?i)\b(hno|h\.no|house\s*no)([0-9])", r"\1 \2", s)
        # Clean consecutive spaces
        return " ".join(s.split())

    def parse_full_name(
        self, full_text: str, token_spans: List[Tuple[int, int, OCRToken]]
    ) -> Optional[ExtractedField]:
        """Parses citizen/applicant full name across standard IDs and Aadhaar/PAN formats."""
        lines = [line.strip() for line in full_text.splitlines() if line.strip()]

        # 1. Standard Labeled: "Name: John Doe", "Citizen Name: Alice Smith"
        pat_labeled = r"(?i)(?:full\s*name|citizen\s*name|applicant\s*name|holder\s*name|name\s*of\s*holder|name)\s*[:\-\.]\s*([^\n\r,;|]+)"
        match = re.search(pat_labeled, full_text)
        if match:
            raw_val = match.group(1).strip()
            cleaned = re.sub(r"(?i)^(?:shri|smt|dr|mr|mrs|ms)\.?\s*", "", raw_val)
            cleaned = re.sub(r"[^A-Za-z\s\.\'\-]", "", cleaned).strip()
            if len(cleaned) >= 2 and not re.search(r"(?i)government|india|department", cleaned):
                matched_tokens = self._find_tokens_for_span(
                    full_text, match.start(1), match.end(1), token_spans
                )
                bbox = self._compute_bounding_box(matched_tokens)
                conf = self._average_confidence(matched_tokens)
                return ExtractedField(
                    field_name="name",
                    raw_text=raw_val,
                    normalized_text=self._clean_spacing(cleaned),
                    bbox=bbox,
                    confidence=conf,
                    matched_pattern="labeled_name",
                    tokens=matched_tokens,
                )

        # 2. Aadhaar / PAN card layout patterns:
        for idx, line in enumerate(lines):
            # 2a. Line following "To" (Aadhaar card address letter block)
            if re.match(r"(?i)^to\b", line) and idx + 1 < len(lines):
                cand = lines[idx + 1]
                cand_clean = re.sub(r"[^A-Za-z\s\.\'\-]", "", self._clean_spacing(cand)).strip()
                if len(cand_clean) >= 3 and not re.search(r"(?i)government|india|authority|enrollment", cand_clean):
                    pos = full_text.find(cand)
                    matched_tokens = self._find_tokens_for_span(
                        full_text, pos, pos + len(cand), token_spans
                    )
                    return ExtractedField(
                        field_name="name",
                        raw_text=cand,
                        normalized_text=cand_clean,
                        bbox=self._compute_bounding_box(matched_tokens),
                        confidence=self._average_confidence(matched_tokens),
                        matched_pattern="aadhaar_to_name",
                        tokens=matched_tokens,
                    )

            # 2b. Line immediately preceding "Year of Birth" or "DOB" or Gender (Aadhaar front card)
            if re.search(r"(?i)(?:year\s*of\s*birth|yearof\s*birth|yob|dob|gender|male|female)", line) and idx > 0:
                cand = lines[idx - 1]
                cand_clean = re.sub(r"[^A-Za-z\s\.\'\-]", "", self._clean_spacing(cand)).strip()
                if len(cand_clean) >= 3 and not re.search(r"(?i)government|india|authority|enrollment|republic", cand_clean):
                    pos = full_text.find(cand)
                    matched_tokens = self._find_tokens_for_span(
                        full_text, pos, pos + len(cand), token_spans
                    )
                    return ExtractedField(
                        field_name="name",
                        raw_text=cand,
                        normalized_text=cand_clean,
                        bbox=self._compute_bounding_box(matched_tokens),
                        confidence=self._average_confidence(matched_tokens),
                        matched_pattern="aadhaar_pre_dob_name",
                        tokens=matched_tokens,
                    )

            # 2c. Line immediately preceding "D/O", "S/O", "W/O", "C/O"
            if re.search(r"(?i)\b[dswc]\/o\b", line) and idx > 0:
                cand = lines[idx - 1]
                cand_clean = re.sub(r"[^A-Za-z\s\.\'\-]", "", self._clean_spacing(cand)).strip()
                if len(cand_clean) >= 3 and not re.search(r"(?i)government|india|authority|to\b", cand_clean):
                    pos = full_text.find(cand)
                    matched_tokens = self._find_tokens_for_span(
                        full_text, pos, pos + len(cand), token_spans
                    )
                    return ExtractedField(
                        field_name="name",
                        raw_text=cand,
                        normalized_text=cand_clean,
                        bbox=self._compute_bounding_box(matched_tokens),
                        confidence=self._average_confidence(matched_tokens),
                        matched_pattern="aadhaar_pre_careof_name",
                        tokens=matched_tokens,
                    )

        return None

    def parse_dob(
        self, full_text: str, token_spans: List[Tuple[int, int, OCRToken]]
    ) -> Optional[ExtractedField]:
        """Parses Date of Birth or Year of Birth and normalizes to canonical standard."""
        # 1. Labeled Year of Birth (e.g. "Year of Birth: 1998", "Yearof Birth: 1998", "YearofBirth: 2003", "YOB: 1990")
        yob_match = re.search(
            r"(?i)(?:year\s*of\s*birth|yearof\s*birth|yearofbirth|birth\s*year|yob)[\s:\-\.\/]*([12][0-9]{3})\b",
            full_text,
        )
        if yob_match:
            raw_val = yob_match.group(1).strip()
            matched_tokens = self._find_tokens_for_span(
                full_text, yob_match.start(1), yob_match.end(1), token_spans
            )
            return ExtractedField(
                field_name="dob",
                raw_text=raw_val,
                normalized_text=raw_val,
                bbox=self._compute_bounding_box(matched_tokens),
                confidence=self._average_confidence(matched_tokens),
                matched_pattern="year_of_birth",
                tokens=matched_tokens,
            )

        # 2. Labeled DOB: "DOB: 15/05/1990", "Date of Birth: 1990-05-15"
        dob_match = re.search(
            r"(?i)(?:dob|d0b|d\.o\.b|date\s*of\s*birth|birth\s*date)[\s:\-\.\/]*([0-3]?[0-9][\/\-\.][0-1]?[0-9][\/\-\.][12][0-9]{3}|[12][0-9]{3}[\/\-\.][0-1]?[0-9][\/\-\.][0-3]?[0-9]|[0-3]?[0-9]\s+[A-Za-z]{3,9}\s+[12][0-9]{3})",
            full_text,
        )
        if dob_match:
            raw_val = dob_match.group(1).strip()
            matched_tokens = self._find_tokens_for_span(
                full_text, dob_match.start(1), dob_match.end(1), token_spans
            )
            return ExtractedField(
                field_name="dob",
                raw_text=raw_val,
                normalized_text=self._normalize_date(raw_val),
                bbox=self._compute_bounding_box(matched_tokens),
                confidence=self._average_confidence(matched_tokens),
                matched_pattern="labeled_dob",
                tokens=matched_tokens,
            )

        # 3. Standalone date in document (fallback)
        for date_match in re.finditer(r"\b([0-3]?[0-9][\/\-\.][0-1]?[0-9][\/\-\.][12][0-9]{3})\b", full_text):
            # Skip if it is right after Enrollment No or dispatch stamps
            prefix = full_text[max(0, date_match.start() - 30):date_match.start()]
            if re.search(r"(?i)enrollment|enrolment|issued|valid", prefix):
                continue
            raw_val = date_match.group(1).strip()
            matched_tokens = self._find_tokens_for_span(
                full_text, date_match.start(1), date_match.end(1), token_spans
            )
            return ExtractedField(
                field_name="dob",
                raw_text=raw_val,
                normalized_text=self._normalize_date(raw_val),
                bbox=self._compute_bounding_box(matched_tokens),
                confidence=self._average_confidence(matched_tokens),
                matched_pattern="standalone_date",
                tokens=matched_tokens,
            )

        return None

    @staticmethod
    def _normalize_date(date_str: str) -> str:
        """Normalizes various date string formats to canonical YYYY-MM-DD."""
        cleaned = date_str.strip().strip(".,;:()")
        cleaned = re.sub(r"[\.\/]", "-", cleaned)
        formats = [
            "%d-%m-%Y",
            "%Y-%m-%d",
            "%m-%d-%Y",
            "%d-%b-%Y",
            "%d-%B-%Y",
            "%d %b %Y",
            "%d %B %Y",
            "%Y",
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(cleaned, fmt)
                if fmt == "%Y":
                    return dt.strftime("%Y")
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return cleaned

    def parse_document_id(
        self, full_text: str, token_spans: List[Tuple[int, int, OCRToken]]
    ) -> Optional[ExtractedField]:
        """Parses national document IDs (Aadhaar, PAN, Passport, Voter ID, DL, etc.)."""
        patterns = [
            # Aadhaar: 12 digits (often 4 4 4 separated by space or hyphen)
            (r"\b(\d{4}[-\s]\d{4}[-\s]\d{4})\b", "aadhaar_spaced"),
            (r"\b(\d{12})\b", "aadhaar_compact"),
            # PAN Card: 5 uppercase letters, 4 digits, 1 uppercase letter
            (r"\b([A-Z]{5}[0-9]{4}[A-Z])\b", "pan_card"),
            # Voter ID / EPIC: 3 letters followed by 7 digits
            (r"\b([A-Z]{3}[0-9]{7})\b", "voter_id"),
            # Passport: 1 letter followed by 7-8 digits (optional space)
            (r"\b([A-PR-WYa-pr-wy]\s?[0-9]{7,8})\b", "passport"),
            # Driving License: State code (2 letters) + digits (optional hyphens or spaces)
            (r"\b([A-Z]{2}[-\s]?[0-9]{2}[-\s]?[0-9]{4,11})\b", "driving_license"),
            # Generic labeled ID: "Doc ID: ABCDE1234F", "ID No: 987654"
            (
                r"(?i)(?:id\s*number|id\s*no|doc\s*id|document\s*id|identity\s*no|card\s*no|aadhaar\s*no)\s*[:\-\.]*\s*([A-Za-z0-9][A-Za-z0-9\-\/ ]{3,24})",
                "generic_id",
            ),
        ]

        for pat, tag in patterns:
            # Exclude matches preceded by enrollment or phone numbers
            for match in re.finditer(pat, full_text):
                raw_val = match.group(1).strip()
                prefix = full_text[max(0, match.start() - 25):match.start()]
                if re.search(r"(?i)enrollment|enrolment|phone|mobile|help", prefix):
                    continue

                normalized = re.sub(r"[\s\-]", "", raw_val).upper()
                # Skip if invalid length
                if len(normalized) < 5:
                    continue

                matched_tokens = self._find_tokens_for_span(
                    full_text, match.start(1), match.end(1), token_spans
                )
                bbox = self._compute_bounding_box(matched_tokens)
                conf = self._average_confidence(matched_tokens)
                return ExtractedField(
                    field_name="document_id",
                    raw_text=raw_val,
                    normalized_text=normalized,
                    bbox=bbox,
                    confidence=conf,
                    matched_pattern=f"{tag}:{pat}",
                    tokens=matched_tokens,
                )
        return None

    def parse_address(
        self, full_text: str, token_spans: List[Tuple[int, int, OCRToken]]
    ) -> Optional[ExtractedField]:
        """Parses citizen physical/postal address supporting Indian Aadhaar address blocks."""
        lines = [line.strip() for line in full_text.splitlines() if line.strip()]

        # 1. Indian Aadhaar Card multi-line address block:
        # Starts with D/O, S/O, W/O, C/O, HNO, House No, Address
        # Continues down to the line with 6-digit Indian PIN code (e.g. 531035)
        addr_start_idx = -1
        addr_end_idx = -1

        start_markers = [
            r"(?i)[dswc]\/o",
            r"(?i)\b(?:care\s*of|c\/o|s\/o|d\/o|w\/o)\b",
            r"(?i)\b(?:hno|h\.no|house\s*no|flat\s*no|door\s*no|plot\s*no)\b",
            r"(?i)\baddress\b",
        ]

        for idx, line in enumerate(lines):
            if addr_start_idx == -1:
                if any(re.search(pat, line) for pat in start_markers):
                    addr_start_idx = idx

            if addr_start_idx != -1:
                # Check if this line contains a 6-digit PIN code (allowing optional internal space or hyphen)
                if re.search(r"\b[1-9][0-9]{2}[\s\-]?[0-9]{3}\b", line):
                    addr_end_idx = idx
                    break

        if addr_start_idx != -1 and addr_end_idx != -1 and addr_end_idx >= addr_start_idx:
            selected_lines = lines[addr_start_idx:addr_end_idx + 1]
            clean_lines = [self._clean_spacing(l) for l in selected_lines if not re.search(r"(?i)verified|portal|signature|government|aadhaar\s*no", l)]
            if clean_lines:
                raw_val = ", ".join(clean_lines)
                start_pos = full_text.find(selected_lines[0])
                end_pos = full_text.find(selected_lines[-1], start_pos) + len(selected_lines[-1])
                matched_tokens = self._find_tokens_for_span(
                    full_text, start_pos, end_pos, token_spans
                )
                return ExtractedField(
                    field_name="address",
                    raw_text=raw_val,
                    normalized_text=" ".join(raw_val.split()),
                    bbox=self._compute_bounding_box(matched_tokens),
                    confidence=self._average_confidence(matched_tokens),
                    matched_pattern="aadhaar_address_block",
                    tokens=matched_tokens,
                )

        # 2. Labeled pattern: Address: <lines> until next major field or card footer
        addr_match = re.search(
            r"(?i)(?:address|perm\s*address|residential\s*address|res\.\s*address)\s*[:\-\.]([\s\S]+?)(?=(?:\n\s*(?:DOB|Date|Phone|Mobile|PIN|Pin\s*Code|ID|Doc\s*ID|Gender)\b)|\n\s*\n|$)",
            full_text,
        )

        if addr_match:
            raw_match_text = addr_match.group(1).strip()
            raw_lines = [l.strip() for l in raw_match_text.splitlines() if l.strip()]
            clean_lines = []
            for l in raw_lines:
                if re.search(r"(?i)verified|portal|signature|government|credential|authority", l):
                    break
                clean_lines.append(self._clean_spacing(l))

            if clean_lines:
                cleaned = " ".join(" ".join(clean_lines).split())
                if len(cleaned) > 5:
                    start_pos = full_text.find(raw_lines[0], addr_match.start(1))
                    end_pos = full_text.find(raw_lines[-1], start_pos) + len(raw_lines[-1])
                    matched_tokens = self._find_tokens_for_span(
                        full_text, start_pos, end_pos, token_spans
                    )
                    return ExtractedField(
                        field_name="address",
                        raw_text=", ".join(clean_lines),
                        normalized_text=cleaned,
                        bbox=self._compute_bounding_box(matched_tokens),
                        confidence=self._average_confidence(matched_tokens),
                        matched_pattern="labeled_address",
                        tokens=matched_tokens,
                    )

        # 3. Heuristic scan for address keywords and PIN codes
        address_lines = []
        start_char = -1
        end_char = -1

        address_keywords = [
            "road", "rd", "street", "st", "lane", "nagar", "colony",
            "sector", "plot", "apt", "apartment", "flat", "floor",
            "cross", "main", "district", "post", "near", "opposite",
            "mandalam", "mandal", "taluk", "village"
        ]

        for line in lines:
            line_lower = line.lower()
            if re.search(r"(?i)verified|portal|signature|government|credential|authority", line_lower):
                continue
            has_keyword = any(kw in line_lower for kw in address_keywords)
            has_pincode = bool(re.search(r"\b[1-9][0-9]{2}[\s\-]?[0-9]{3}\b", line))
            if has_keyword or has_pincode:
                address_lines.append(self._clean_spacing(line))
                pos = full_text.find(line)
                if pos != -1:
                    if start_char == -1 or pos < start_char:
                        start_char = pos
                    end_char = max(end_char, pos + len(line))

        if address_lines and start_char != -1:
            raw_val = ", ".join(address_lines)
            cleaned = " ".join(raw_val.split())
            matched_tokens = self._find_tokens_for_span(
                full_text, start_char, end_char, token_spans
            )
            return ExtractedField(
                field_name="address",
                raw_text=raw_val,
                normalized_text=cleaned,
                bbox=self._compute_bounding_box(matched_tokens),
                confidence=self._average_confidence(matched_tokens),
                matched_pattern="heuristic_address",
                tokens=matched_tokens,
            )

    def parse_gender(
        self, full_text: str, token_spans: List[Tuple[int, int, OCRToken]]
    ) -> Optional[ExtractedField]:
        """Parses citizen Gender (Male, Female, Transgender)."""
        patterns = [
            # Labeled: Gender: Male, Sex: Female, Gender / लिंग : MALE
            r"(?i)(?:gender|sex)[\s:\-\.\/]*\b(female|male|transgender)\b",
            # Single letter labeled: Sex: F, Gender: M
            r"(?i)\b(?:gender|sex)\b[\s:\-\.\/]*([FMT])\b",
            # Aadhaar card style: /Male, /Female, / Male, / Female
            r"(?i)\/\s*(female|male|transgender)\b",
            # Standalone Female (must check Female first so 'male' doesn't partially match 'female')
            r"\b(Female|FEMALE)\b",
            # Standalone Male (only if line contains gender context or right after birth year)
            r"(?i)(?:birth|year|yob|dob|y\/o)[\s\S]{1,40}?\b(Male|MALE)\b",
            r"\b(Male|MALE)\b",
        ]

        for pat in patterns:
            match = re.search(pat, full_text)
            if match:
                raw_val = match.group(1).strip()
                normalized = self._normalize_gender(raw_val)
                matched_tokens = self._find_tokens_for_span(
                    full_text, match.start(1), match.end(1), token_spans
                )
                bbox = self._compute_bounding_box(matched_tokens)
                conf = self._average_confidence(matched_tokens)
                return ExtractedField(
                    field_name="gender",
                    raw_text=raw_val,
                    normalized_text=normalized,
                    bbox=bbox,
                    confidence=conf,
                    matched_pattern=f"gender:{pat}",
                    tokens=matched_tokens,
                )
        return None

    @staticmethod
    def _normalize_gender(g: str) -> str:
        """Normalizes various gender representations to standard English."""
        s = g.strip().lower()
        if re.search(r"female|^f$", s):
            return "Female"
        if re.search(r"male|^m$", s):
            return "Male"
        if re.search(r"trans|^t$", s):
            return "Transgender"
        return g.strip().capitalize()

    def extract(self, document_input: Union[np.ndarray, Image.Image, PreprocessResult]) -> ExtractionResult:
        """
        Executes full extraction pipeline:
        1. Tokenizes image into OCRTokens with bounding boxes and confidences.
        2. Constructs full text layout and maps token character spans.
        3. Parses full_name, dob, gender, address, and document_id with associated bounding boxes.
        """
        tokens = self.extract_tokens(document_input)

        if isinstance(document_input, PreprocessResult):
            h, w = document_input.height, document_input.width
        elif isinstance(document_input, Image.Image):
            w, h = document_input.size
        else:
            h, w = document_input.shape[:2]

        # Build full text representation and maintain character offsets for each token
        full_text_parts = []
        token_spans: List[Tuple[int, int, OCRToken]] = []
        current_char = 0

        # Group tokens into lines by line_num or y-proximity
        tokens_by_line: Dict[int, List[OCRToken]] = {}
        for token in tokens:
            tokens_by_line.setdefault(token.line_num, []).append(token)

        sorted_line_keys = sorted(tokens_by_line.keys())
        for line_k in sorted_line_keys:
            line_tokens = sorted(tokens_by_line[line_k], key=lambda t: t.x)
            for i, token in enumerate(line_tokens):
                start = current_char
                full_text_parts.append(token.text)
                current_char += len(token.text)
                end = current_char
                token_spans.append((start, end, token))

                # Add space between words
                if i < len(line_tokens) - 1:
                    full_text_parts.append(" ")
                    current_char += 1
            # Add newline between lines
            full_text_parts.append("\n")
            current_char += 1

        full_text = "".join(full_text_parts)

        # Parse key fields
        fields: Dict[str, ExtractedField] = {}
        name_field = self.parse_full_name(full_text, token_spans)
        if name_field:
            fields["name"] = name_field

        dob_field = self.parse_dob(full_text, token_spans)
        if dob_field:
            fields["dob"] = dob_field

        doc_id_field = self.parse_document_id(full_text, token_spans)
        if doc_id_field:
            fields["document_id"] = doc_id_field

        gender_field = self.parse_gender(full_text, token_spans)
        if gender_field:
            fields["gender"] = gender_field

        address_field = self.parse_address(full_text, token_spans)
        if address_field:
            fields["address"] = address_field

        return ExtractionResult(
            full_text=full_text,
            tokens=tokens,
            fields=fields,
            image_shape=(h, w),
            backend_used=self.active_backend,
        )
