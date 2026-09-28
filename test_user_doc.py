"""
Test script for verifying user document extraction and pipeline processing.
Uses the unified ai_automation module.
"""
from ai_automation.extractor import DocumentExtractor, OCRToken, ExtractedField, ExtractionResult
from ai_automation.pipeline import VerificationEngine, AuditPipelineResult
from ai_automation.matcher import CredentialMatcher, MatchResult
from ai_automation.preprocessor import DocumentPreprocessor, PreprocessResult

def test_pipeline_smoke():
    engine = VerificationEngine()
    assert engine.extractor is not None
    assert engine.preprocessor is not None
    assert engine.matcher is not None
    print("[PASS] AI Automation VerificationEngine, Preprocessor, Extractor & Matcher initialized successfully.")

if __name__ == "__main__":
    test_pipeline_smoke()
