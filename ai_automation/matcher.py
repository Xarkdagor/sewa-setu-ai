"""
Credential Matcher and Scoring Pipeline Module
Implements fuzzy matching using rapidfuzz (Jaro-Winkler, Levenshtein, Token Sort)
for names and addresses, exact matching for DOB and Document IDs,
and confidence tier classification with non-punitive citizen routing.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from rapidfuzz import distance, fuzz

from .extractor import ExtractedField, ExtractionResult


@dataclass
class FieldMatchResult:
    """Detailed matching result for a single field."""
    field_name: str
    submitted: str
    ocr_text: str
    score: float  # 0.0 - 100.0
    status: str  # "match", "partial_match", "mismatch", "missing"
    bbox: List[int]  # [x, y, w, h] from OCR token extraction
    diff: Optional[str] = None
    is_critical: bool = False
    ocr_confidence: float = 0.0
    doc_side: str = "front"  # "front" or "back"

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "submitted": self.submitted,
            "ocr_text": self.ocr_text,
            "score": round(self.score, 1),
            "status": self.status,
            "bbox": self.bbox,
            "doc_side": self.doc_side,
        }
        if self.diff:
            data["diff"] = self.diff
        return data


@dataclass
class MatchResult:
    """Complete scoring, tier classification, and audit artifact."""
    fields: Dict[str, FieldMatchResult]
    overall_score: float
    tier: str  # "HIGH", "MEDIUM", "LOW", "CRITICAL_MISMATCH"
    critical_flag: bool
    manual_review_priority: bool
    review_reason: Optional[str] = None
    policy_notice: str = (
        "Confidence measures technical clarity and imaging uncertainty, not citizen guilt. "
        "Low confidence routes to manual priority review and is never auto-rejected."
    )

    def to_dict(self) -> Dict[str, Any]:
        """Returns JSON-compatible dictionary conforming strictly to the required schema."""
        return {
            "fields": {k: v.to_dict() for k, v in self.fields.items()},
            "overall_score": round(self.overall_score, 1),
            "tier": self.tier,
            "critical_flag": self.critical_flag,
        }

    def to_extended_dict(self) -> Dict[str, Any]:
        """Returns detailed JSON dictionary with governance audit notes."""
        base = self.to_dict()
        base.update({
            "manual_review_priority": self.manual_review_priority,
            "review_reason": self.review_reason,
            "policy_notice": self.policy_notice,
        })
        return base


class CredentialMatcher:
    """
    Automated Credential Verification Matcher.
    Applies rapidfuzz (Jaro-Winkler, Levenshtein, token algorithms) for names/addresses,
    exact matching for critical identity attributes (DOB, Document ID),
    and assigns confidence tiers according to governance policy.
    """

    CRITICAL_FIELDS = {"dob", "document_id"}

    # Field importance weights in overall verification score calculation
    DEFAULT_WEIGHTS = {
        "name": 0.30,
        "dob": 0.20,
        "document_id": 0.20,
        "gender": 0.15,
        "address": 0.15,
    }

    # Standard address abbreviation mappings for intelligent normalization & diffing
    ADDRESS_ABBREVIATIONS = {
        r"\brd\b": "road",
        r"\bst\b": "street",
        r"\bave\b": "avenue",
        r"\bapt\b": "apartment",
        r"\bfl\b": "floor",
        r"\bblvd\b": "boulevard",
        r"\bln\b": "lane",
        r"\bct\b": "court",
        r"\bpl\b": "place",
        r"\bste\b": "suite",
        r"\bsec\b": "sector",
        r"\bno\b": "number",
    }

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()

    # -------------------------------------------------------------------------
    # String Normalization & Diffing Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def normalize_string(text: str) -> str:
        """Removes extra spaces, punctuation, and converts to lower case."""
        if not text:
            return ""
        # Remove non-alphanumeric except spaces
        cleaned = re.sub(r"[^\w\s]", " ", text)
        return " ".join(cleaned.lower().split())

    @classmethod
    def normalize_address(cls, address: str) -> str:
        """Expands common address abbreviations and standardizes whitespace."""
        normalized = cls.normalize_string(address)
        for pattern, replacement in cls.ADDRESS_ABBREVIATIONS.items():
            normalized = re.sub(pattern, replacement, normalized)
        return " ".join(normalized.split())

    @staticmethod
    def generate_token_diff(submitted: str, ocr_text: str) -> Optional[str]:
        """
        Generates human-readable difference between two strings (e.g., 'Rd vs Road', 'Jonathan vs Johnathan').
        """
        words_sub = [w.strip(".,;:()") for w in submitted.split() if w.strip(".,;:()")]
        words_ocr = [w.strip(".,;:()") for w in ocr_text.split() if w.strip(".,;:()")]

        diffs: List[str] = []
        matcher = difflib.SequenceMatcher(
            None, [w.lower() for w in words_ocr], [w.lower() for w in words_sub]
        )
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "replace":
                w_ocr_str = " ".join(words_ocr[i1:i2])
                w_sub_str = " ".join(words_sub[j1:j2])
                diffs.append(f"{w_ocr_str} vs {w_sub_str}")
            elif tag == "delete":
                diffs.append(f"Extra in OCR: '{' '.join(words_ocr[i1:i2])}'")
            elif tag == "insert":
                diffs.append(f"Missing in OCR: '{' '.join(words_sub[j1:j2])}'")

        if diffs:
            return ", ".join(diffs[:2])
        return None

    # -------------------------------------------------------------------------
    # Field Matchers
    # -------------------------------------------------------------------------

    def match_name(
        self, submitted: str, extracted: Optional[ExtractedField]
    ) -> FieldMatchResult:
        """
        Fuzzy matches applicant full name using rapidfuzz Jaro-Winkler, Levenshtein,
        and Token Sort similarity.
        """
        ocr_text = extracted.normalized_text if extracted else ""
        bbox = extracted.bbox if extracted else [0, 0, 0, 0]
        ocr_conf = extracted.confidence if extracted else 0.0

        if not extracted or not ocr_text:
            return FieldMatchResult(
                field_name="name",
                submitted=submitted,
                ocr_text="",
                score=0.0,
                status="missing",
                bbox=[0, 0, 0, 0],
                diff="Field not detected in document",
                ocr_confidence=0.0,
            )

        norm_sub = self.normalize_string(submitted)
        norm_ocr = self.normalize_string(ocr_text)

        # 1. Exact string match after normalization
        if norm_sub == norm_ocr:
            return FieldMatchResult(
                field_name="name",
                submitted=submitted,
                ocr_text=extracted.raw_text,
                score=100.0,
                status="match",
                bbox=bbox,
                ocr_confidence=ocr_conf,
            )

        # 2. Rapidfuzz metrics: Token Sort Ratio, Levenshtein ratio & Jaro-Winkler
        token_sort = float(fuzz.token_sort_ratio(norm_sub, norm_ocr))
        lev_ratio = float(fuzz.ratio(norm_sub, norm_ocr))
        jw_sim = float(distance.JaroWinkler.similarity(norm_sub, norm_ocr) * 100.0)

        # If strings share substantial tokens/characters, combine with Jaro-Winkler
        if token_sort >= 60.0:
            score = max(token_sort, lev_ratio, (0.5 * token_sort) + (0.5 * jw_sim))
        else:
            score = min(token_sort, lev_ratio)

        score = min(100.0, max(0.0, score))

        diff_str = self.generate_token_diff(submitted, extracted.raw_text)

        status = "match" if score >= 85.0 else ("partial_match" if score >= 50.0 else "mismatch")

        return FieldMatchResult(
            field_name="name",
            submitted=submitted,
            ocr_text=extracted.raw_text,
            score=score,
            status=status,
            bbox=bbox,
            diff=diff_str,
            ocr_confidence=ocr_conf,
        )

    def match_address(
        self, submitted: str, extracted: Optional[ExtractedField]
    ) -> FieldMatchResult:
        """
        Fuzzy matches physical address with abbreviation expansion and rapidfuzz token similarity.
        """
        ocr_text = extracted.normalized_text if extracted else ""
        bbox = extracted.bbox if extracted else [0, 0, 0, 0]
        ocr_conf = extracted.confidence if extracted else 0.0

        if not extracted or not ocr_text:
            return FieldMatchResult(
                field_name="address",
                submitted=submitted,
                ocr_text="",
                score=0.0,
                status="missing",
                bbox=[0, 0, 0, 0],
                diff="Address field not detected in document",
                ocr_confidence=0.0,
            )

        norm_sub_addr = self.normalize_address(submitted)
        norm_ocr_addr = self.normalize_address(ocr_text)

        diff_str = self.generate_token_diff(submitted, extracted.raw_text)

        # Exact normalized match
        if norm_sub_addr == norm_ocr_addr:
            return FieldMatchResult(
                field_name="address",
                submitted=submitted,
                ocr_text=extracted.raw_text,
                score=100.0,
                status="match",
                bbox=bbox,
                diff=diff_str,
                ocr_confidence=ocr_conf,
            )

        # Token set ratio handles address subsets (e.g. submitted street/village within full postal address)
        token_set = float(fuzz.token_set_ratio(norm_sub_addr, norm_ocr_addr))
        token_sort = float(fuzz.token_sort_ratio(norm_sub_addr, norm_ocr_addr))
        partial_ratio = float(fuzz.partial_ratio(norm_sub_addr, norm_ocr_addr))
        lev_ratio = float(fuzz.ratio(norm_sub_addr, norm_ocr_addr))

        if token_set >= 70.0:
            score = max(
                (0.5 * token_set) + (0.3 * partial_ratio) + (0.2 * token_sort),
                (0.6 * token_set) + (0.4 * token_sort),
            )
        elif token_sort >= 40.0:
            score = (0.5 * token_set) + (0.3 * token_sort) + (0.2 * lev_ratio)
        else:
            score = min(token_sort, lev_ratio)

        score = min(100.0, max(0.0, score))

        status = "match" if score >= 80.0 else ("partial_match" if score >= 50.0 else "mismatch")

        return FieldMatchResult(
            field_name="address",
            submitted=submitted,
            ocr_text=extracted.raw_text,
            score=score,
            status=status,
            bbox=bbox,
            diff=diff_str,
            ocr_confidence=ocr_conf,
        )

    def match_dob(
        self, submitted: str, extracted: Optional[ExtractedField]
    ) -> FieldMatchResult:
        """
        Exact matching for Date of Birth. Supports both full YYYY-MM-DD dates and Year-of-Birth.
        Any mismatch triggers critical flag.
        """
        ocr_text = extracted.normalized_text if extracted else ""
        bbox = extracted.bbox if extracted else [0, 0, 0, 0]
        ocr_conf = extracted.confidence if extracted else 0.0

        if not extracted or not ocr_text:
            return FieldMatchResult(
                field_name="dob",
                submitted=submitted,
                ocr_text="",
                score=0.0,
                status="missing",
                bbox=[0, 0, 0, 0],
                diff="DOB not detected on credential",
                is_critical=True,
                ocr_confidence=0.0,
            )

        from .extractor import DocumentExtractor
        clean_sub_dob = DocumentExtractor._normalize_date(submitted)
        clean_ocr_dob = extracted.normalized_text

        # 1. Exact match check
        if clean_sub_dob == clean_ocr_dob:
            return FieldMatchResult(
                field_name="dob",
                submitted=submitted,
                ocr_text=extracted.raw_text,
                score=100.0,
                status="match",
                bbox=bbox,
                is_critical=True,
                ocr_confidence=ocr_conf,
            )

        # 2. Check Year-of-Birth compatibility (when document only contains YOB, e.g. 1998)
        sub_year_match = re.search(r"\b(19\d{2}|20\d{2})\b", clean_sub_dob)
        ocr_year_match = re.search(r"\b(19\d{2}|20\d{2})\b", clean_ocr_dob)

        if sub_year_match and ocr_year_match:
            sub_year = sub_year_match.group(1)
            ocr_year = ocr_year_match.group(1)
            # If one of them is only year or year matches
            if (len(clean_ocr_dob) == 4 or len(clean_sub_dob) == 4) and sub_year == ocr_year:
                return FieldMatchResult(
                    field_name="dob",
                    submitted=submitted,
                    ocr_text=extracted.raw_text,
                    score=100.0,
                    status="match",
                    bbox=bbox,
                    is_critical=True,
                    ocr_confidence=ocr_conf,
                )

        # Mismatch
        return FieldMatchResult(
            field_name="dob",
            submitted=submitted,
            ocr_text=extracted.raw_text,
            score=0.0,
            status="mismatch",
            bbox=bbox,
            diff=f"Submitted '{submitted}' != document '{extracted.raw_text}'",
            is_critical=True,
            ocr_confidence=ocr_conf,
        )

    def match_document_id(
        self, submitted: str, extracted: Optional[ExtractedField]
    ) -> FieldMatchResult:
        """
        Exact matching for Document ID numbers (Aadhaar, PAN, Passport, etc.).
        Any mismatch triggers critical flag.
        """
        ocr_text = extracted.normalized_text if extracted else ""
        bbox = extracted.bbox if extracted else [0, 0, 0, 0]
        ocr_conf = extracted.confidence if extracted else 0.0

        if not extracted or not ocr_text:
            return FieldMatchResult(
                field_name="document_id",
                submitted=submitted,
                ocr_text="",
                score=0.0,
                status="missing",
                bbox=[0, 0, 0, 0],
                diff="Document ID not found on credential",
                is_critical=True,
                ocr_confidence=0.0,
            )

        # Normalize IDs: uppercase, alphanumeric only (strip hyphens, spaces, slashes)
        clean_sub_id = re.sub(r"[^A-Za-z0-9]", "", submitted).upper()
        clean_ocr_id = re.sub(r"[^A-Za-z0-9]", "", ocr_text).upper()

        if clean_sub_id == clean_ocr_id:
            return FieldMatchResult(
                field_name="document_id",
                submitted=submitted,
                ocr_text=extracted.raw_text,
                score=100.0,
                status="match",
                bbox=bbox,
                is_critical=True,
                ocr_confidence=ocr_conf,
            )

        return FieldMatchResult(
            field_name="document_id",
            submitted=submitted,
            ocr_text=extracted.raw_text,
            score=0.0,
            status="mismatch",
            bbox=bbox,
            diff=f"ID mismatch: submitted '{submitted}' != document '{extracted.raw_text}'",
            is_critical=True,
            ocr_confidence=ocr_conf,
        )

    def match_gender(
        self, submitted: str, extracted: Optional[ExtractedField]
    ) -> FieldMatchResult:
        """
        Exact matching for citizen Gender (Male, Female, Transgender).
        """
        ocr_text = extracted.normalized_text if extracted else ""
        bbox = extracted.bbox if extracted else [0, 0, 0, 0]
        ocr_conf = extracted.confidence if extracted else 0.0

        if not extracted or not ocr_text:
            return FieldMatchResult(
                field_name="gender",
                submitted=submitted,
                ocr_text="",
                score=0.0,
                status="missing",
                bbox=[0, 0, 0, 0],
                diff="Gender not detected on credential",
                ocr_confidence=0.0,
            )

        norm_sub = self.normalize_gender(submitted)
        norm_ocr = self.normalize_gender(ocr_text)

        if norm_sub == norm_ocr:
            return FieldMatchResult(
                field_name="gender",
                submitted=submitted,
                ocr_text=extracted.raw_text,
                score=100.0,
                status="match",
                bbox=bbox,
                ocr_confidence=ocr_conf,
            )

        return FieldMatchResult(
            field_name="gender",
            submitted=submitted,
            ocr_text=extracted.raw_text,
            score=0.0,
            status="mismatch",
            bbox=bbox,
            diff=f"Submitted '{submitted}' != document '{extracted.raw_text}'",
            ocr_confidence=ocr_conf,
        )

    @staticmethod
    def normalize_gender(g: str) -> str:
        """Standardizes gender representation."""
        s = g.strip().lower()
        if re.search(r"\bfemale\b|^f$", s):
            return "Female"
        if re.search(r"\bmale\b|^m$", s):
            return "Male"
        if re.search(r"\btransgender\b|^t$", s):
            return "Transgender"
        return g.strip().capitalize()

    # -------------------------------------------------------------------------
    # Core Pipeline Evaluation & Tier Classification
    # -------------------------------------------------------------------------

    def evaluate(
        self,
        submitted_data: Dict[str, str],
        extraction_result: ExtractionResult,
    ) -> MatchResult:
        """
        Compares all submitted citizen fields against OCR extracted fields,
        computes fuzzy/exact field similarity, determines overall score,
        and assigns confidence tiers according to governance policy.
        """
        field_results: Dict[str, FieldMatchResult] = {}
        critical_flag = False
        extracted_fields = extraction_result.fields

        # 1. Full Name
        if "name" in submitted_data or "full_name" in submitted_data:
            sub_name = submitted_data.get("name") or submitted_data.get("full_name", "")
            res_name = self.match_name(sub_name, extracted_fields.get("name"))
            field_results["name"] = res_name

        # 2. Date of Birth (Critical)
        if "dob" in submitted_data or "date_of_birth" in submitted_data:
            sub_dob = submitted_data.get("dob") or submitted_data.get("date_of_birth", "")
            res_dob = self.match_dob(sub_dob, extracted_fields.get("dob"))
            field_results["dob"] = res_dob
            if res_dob.status == "mismatch":
                critical_flag = True

        # 3. Document ID (Critical)
        if "document_id" in submitted_data or "id_number" in submitted_data:
            sub_id = submitted_data.get("document_id") or submitted_data.get("id_number", "")
            res_id = self.match_document_id(sub_id, extracted_fields.get("document_id"))
            field_results["document_id"] = res_id
            if res_id.status == "mismatch":
                critical_flag = True

        # 4. Gender
        if "gender" in submitted_data or "sex" in submitted_data:
            sub_gen = submitted_data.get("gender") or submitted_data.get("sex", "")
            res_gen = self.match_gender(sub_gen, extracted_fields.get("gender"))
            field_results["gender"] = res_gen

        # 5. Address
        if "address" in submitted_data:
            sub_addr = submitted_data["address"]
            res_addr = self.match_address(sub_addr, extracted_fields.get("address"))
            field_results["address"] = res_addr

        # Compute overall weighted score
        total_weight = 0.0
        weighted_sum = 0.0

        for fname, f_match in field_results.items():
            weight = self.weights.get(fname, 0.25)
            weighted_sum += f_match.score * weight
            total_weight += weight

        overall_score = (weighted_sum / total_weight) if total_weight > 0 else 0.0
        overall_score = min(100.0, max(0.0, overall_score))

        # Assign confidence tier
        # CRITICAL_MISMATCH: Flag if critical fields (DOB, ID) conflict.
        # HIGH: >= 95% with zero critical field discrepancies.
        # MEDIUM: 50% - 94%.
        # LOW: < 50% (routes to manual priority review).
        if critical_flag:
            tier = "CRITICAL_MISMATCH"
            manual_review_priority = True
            review_reason = "Critical mismatch in identity numbers or date of birth"
        elif overall_score >= 95.0:
            tier = "HIGH"
            manual_review_priority = False
            review_reason = None
        elif overall_score >= 50.0:
            tier = "MEDIUM"
            manual_review_priority = False
            review_reason = "Moderate confidence match; minor formatting or OCR variations"
        else:
            tier = "LOW"
            manual_review_priority = True
            review_reason = (
                "Technical clarity/scan uncertainty requires manual priority officer verification; "
                "not an automated rejection."
            )

        return MatchResult(
            fields=field_results,
            overall_score=overall_score,
            tier=tier,
            critical_flag=critical_flag,
            manual_review_priority=manual_review_priority,
            review_reason=review_reason,
        )

    def evaluate_multi(
        self,
        submitted_data: Dict[str, str],
        front_extraction: ExtractionResult,
        back_extraction: Optional[ExtractionResult] = None,
    ) -> MatchResult:
        """
        Evaluates submitted citizen fields across front and optional back document sides.
        For each field, selects the best matching candidate (e.g. name/DOB/gender from front,
        and address from back), tagging each field with its doc_side ('front' or 'back').
        """
        if back_extraction is None:
            res = self.evaluate(submitted_data, front_extraction)
            for f in res.fields.values():
                f.doc_side = "front"
            return res

        res_front = self.evaluate(submitted_data, front_extraction)
        res_back = self.evaluate(submitted_data, back_extraction)

        merged_fields: Dict[str, FieldMatchResult] = {}
        all_field_names = set(res_front.fields.keys()) | set(res_back.fields.keys())
        critical_flag = False

        for fname in all_field_names:
            f_front = res_front.fields.get(fname)
            f_back = res_back.fields.get(fname)

            chosen: FieldMatchResult
            if f_front is None and f_back is not None:
                chosen = f_back
                chosen.doc_side = "back"
            elif f_back is None and f_front is not None:
                chosen = f_front
                chosen.doc_side = "front"
            else:
                # Both present: choose higher score, or front if equal
                # If front is missing or score 0 while back has non-zero score, choose back
                if f_back.score > f_front.score:
                    chosen = f_back
                    chosen.doc_side = "back"
                elif f_front.status == "missing" and f_back.status != "missing":
                    chosen = f_back
                    chosen.doc_side = "back"
                else:
                    chosen = f_front
                    chosen.doc_side = "front"

            merged_fields[fname] = chosen
            if chosen.is_critical and chosen.status == "mismatch":
                critical_flag = True

        # Recompute overall weighted score from merged fields
        total_weight = 0.0
        weighted_sum = 0.0
        for fname, f_match in merged_fields.items():
            weight = self.weights.get(fname, 0.25)
            weighted_sum += f_match.score * weight
            total_weight += weight

        overall_score = (weighted_sum / total_weight) if total_weight > 0 else 0.0
        overall_score = min(100.0, max(0.0, overall_score))

        if critical_flag:
            tier = "CRITICAL_MISMATCH"
            manual_review_priority = True
            review_reason = "Critical mismatch in identity numbers or date of birth"
        elif overall_score >= 95.0:
            tier = "HIGH"
            manual_review_priority = False
            review_reason = None
        elif overall_score >= 50.0:
            tier = "MEDIUM"
            manual_review_priority = False
            review_reason = "Moderate confidence match; minor formatting or OCR variations"
        else:
            tier = "LOW"
            manual_review_priority = True
            review_reason = (
                "Technical clarity/scan uncertainty requires manual priority officer verification; "
                "not an automated rejection."
            )

        return MatchResult(
            fields=merged_fields,
            overall_score=overall_score,
            tier=tier,
            critical_flag=critical_flag,
            manual_review_priority=manual_review_priority,
            review_reason=review_reason,
        )
