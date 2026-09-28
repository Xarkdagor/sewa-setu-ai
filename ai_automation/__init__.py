"""
Automated Credential Verification Engine
Package initialization
"""

from .preprocessor import DocumentPreprocessor, PreprocessResult
from .extractor import DocumentExtractor, ExtractedField, ExtractionResult, OCRToken
from .matcher import CredentialMatcher, MatchResult, FieldMatchResult
from .pipeline import VerificationEngine, AuditPipelineResult

__all__ = [
    "DocumentPreprocessor",
    "PreprocessResult",
    "DocumentExtractor",
    "ExtractedField",
    "ExtractionResult",
    "OCRToken",
    "CredentialMatcher",
    "MatchResult",
    "FieldMatchResult",
    "VerificationEngine",
    "AuditPipelineResult",
]
