"""
Comprehensive Automated Test Suite for Credential Verification Engine.
Generates synthetic document images and PDFs, exercises preprocessing,
deskewing, OCR extraction, fuzzy matching, and confidence tier classification.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

import cv2
import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_automation.pipeline import VerificationEngine
from ai_automation.preprocessor import DocumentPreprocessor

OUTPUT_DIR = PROJECT_ROOT / "tests" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def create_mock_id_card(
    name: str = "JONATHAN DOE",
    dob: str = "15/05/1990",
    doc_id: str = "ABCDE1234F",
    address: str = "123 Main Rd, Apt 4B, Metro City 110001",
    skew_angle: float = 0.0,
    add_noise: bool = False,
) -> np.ndarray:
    width, height = 800, 500
    img = np.full((height, width, 3), 248, dtype=np.uint8)

    cv2.rectangle(img, (20, 20), (width - 20, height - 20), (60, 60, 60), 2)
    cv2.rectangle(img, (20, 20), (width - 20, 90), (45, 85, 150), -1)

    cv2.putText(
        img,
        "GOVERNMENT CITIZEN IDENTITY CARD",
        (50, 60),
        cv2.FONT_HERSHEY_DUPLEX,
        0.8,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    cv2.rectangle(img, (50, 120), (190, 290), (180, 180, 180), -1)
    cv2.putText(img, "[PHOTO]", (85, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 100, 100), 1, cv2.LINE_AA)

    cv2.putText(img, f"Name: {name}", (220, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (20, 20, 20), 2, cv2.LINE_AA)
    cv2.putText(img, f"DOB: {dob}", (220, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (20, 20, 20), 2, cv2.LINE_AA)
    cv2.putText(img, f"Doc ID: {doc_id}", (220, 250), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (20, 20, 20), 2, cv2.LINE_AA)
    cv2.putText(img, f"Address: {address}", (50, 350), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (30, 30, 30), 2, cv2.LINE_AA)

    cv2.rectangle(img, (20, height - 60), (width - 20, height - 20), (220, 225, 230), -1)
    cv2.putText(
        img,
        "VERIFIED CITIZEN CREDENTIAL - SEWA SETU PORTAL",
        (120, height - 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (70, 70, 70),
        1,
        cv2.LINE_AA,
    )

    if add_noise:
        noise = np.random.normal(0, 15, img.shape).astype(np.float32)
        img = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    if abs(skew_angle) > 0.01:
        prep = DocumentPreprocessor()
        img = prep.rotate_image(img, skew_angle, border_color=(255, 255, 255))

    return img


def draw_bounding_boxes(image: np.ndarray, fields_data: Dict[str, Any]) -> np.ndarray:
    annotated = image.copy()
    colors = {
        "name": (0, 150, 255),
        "dob": (0, 200, 0),
        "document_id": (255, 0, 0),
        "address": (200, 0, 200),
    }

    for fname, fdata in fields_data.items():
        bbox = fdata.get("bbox")
        if not bbox or len(bbox) != 4 or bbox[2] <= 0 or bbox[3] <= 0:
            continue
        x, y, w, h = bbox
        color = colors.get(fname, (0, 255, 255))
        cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)
        cv2.putText(
            annotated,
            f"{fname}: {fdata.get('score', 0)}%",
            (x, max(15, y - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            2,
            cv2.LINE_AA,
        )
    return annotated


def test_high_confidence_tier():
    engine = VerificationEngine(ocr_backend="auto")
    img = create_mock_id_card(
        name="JONATHAN DOE",
        dob="15/05/1990",
        doc_id="ABCDE1234F",
        address="123 Main Road, Apt 4B, Metro City 110001",
    )
    img_path = OUTPUT_DIR / "test1_high_confidence.png"
    cv2.imwrite(str(img_path), img)

    submitted = {
        "name": "Jonathan Doe",
        "dob": "1990-05-15",
        "document_id": "ABCDE1234F",
        "address": "123 Main Road, Apt 4B, Metro City 110001",
    }

    res, prep, _, _ = engine.verify_with_audit(img_path, submitted)
    annotated = draw_bounding_boxes(prep.deskewed_color_image, res["fields"])
    cv2.imwrite(str(OUTPUT_DIR / "test1_annotated_bboxes.png"), annotated)

    assert res["tier"] == "HIGH"
    assert res["overall_score"] >= 95.0
    assert not res["critical_flag"]


def test_medium_fuzzy_tier():
    engine = VerificationEngine(ocr_backend="auto")
    img = create_mock_id_card(
        name="JONATHAN DOE",
        dob="15/05/1990",
        doc_id="ABCDE1234F",
        address="123 Main Rd, Apt 4B, Metro City 110001",
        skew_angle=4.5,
        add_noise=True,
    )
    img_path = OUTPUT_DIR / "test2_skewed_fuzzy.png"
    cv2.imwrite(str(img_path), img)

    submitted = {
        "name": "Johnny Doe",
        "dob": "1990-05-15",
        "document_id": "ABCDE1234F",
        "address": "123 Main Road, Apt 4B",
    }

    res, prep, _, _ = engine.verify_with_audit(img_path, submitted, deskew=True)
    crop = engine.crop_field(prep.deskewed_color_image, res["fields"]["address"]["bbox"])
    assert crop is not None and crop.shape[0] > 0 and crop.shape[1] > 0

    assert res["tier"] == "MEDIUM"
    assert 50.0 <= res["overall_score"] < 95.0
    assert not res["critical_flag"]


def test_critical_mismatch_tier():
    engine = VerificationEngine(ocr_backend="auto")
    img = create_mock_id_card(
        name="JONATHAN DOE",
        dob="15/05/1990",
        doc_id="ABCDE1234F",
        address="123 Main Road, Metro City 110001",
    )
    img_path = OUTPUT_DIR / "test3_critical_mismatch.png"
    cv2.imwrite(str(img_path), img)

    submitted = {
        "name": "Jonathan Doe",
        "dob": "1985-01-20",
        "document_id": "WXYZ9999Q",
        "address": "123 Main Road, Metro City 110001",
    }

    res, _, _, _ = engine.verify_with_audit(img_path, submitted)
    assert res["critical_flag"] is True
    assert res["tier"] == "CRITICAL_MISMATCH"
    assert res["manual_review_priority"] is True


def test_low_confidence_tier():
    engine = VerificationEngine(ocr_backend="auto")
    img = create_mock_id_card(
        name="JONATHAN DOE",
        dob="15/05/1990",
        doc_id="ABCDE1234F",
        address="123 Main Road, Metro City 110001",
    )
    img_path = OUTPUT_DIR / "test4_low_score.png"
    cv2.imwrite(str(img_path), img)

    submitted = {
        "name": "Sarah Connor",
        "address": "99 Cyberdyne Blvd, Los Angeles 90001",
    }

    res, _, _, _ = engine.verify_with_audit(img_path, submitted)
    assert res["tier"] == "LOW"
    assert res["overall_score"] < 50.0
    assert res["manual_review_priority"] is True


def test_pdf_processing():
    engine = VerificationEngine(ocr_backend="auto")
    img = create_mock_id_card(
        name="JONATHAN DOE",
        dob="15/05/1990",
        doc_id="ABCDE1234F",
        address="123 Main Road, Apt 4B, Metro City 110001",
    )
    pdf_path = OUTPUT_DIR / "test5_credential.pdf"
    pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    pil_img.save(str(pdf_path), "PDF", resolution=300.0)

    submitted = {
        "name": "Jonathan Doe",
        "dob": "1990-05-15",
        "document_id": "ABCDE1234F",
        "address": "123 Main Road, Apt 4B, Metro City 110001",
    }

    res = engine.verify(pdf_path, submitted)
    assert res["tier"] == "HIGH"
    assert res["overall_score"] >= 95.0


def run_tests() -> Dict[str, Any]:
    test_results = {}
    engine = VerificationEngine()

    test_high_confidence_tier()
    img1_path = OUTPUT_DIR / "test1_high_confidence.png"
    submitted1 = {
        "name": "Jonathan Doe",
        "dob": "1990-05-15",
        "document_id": "ABCDE1234F",
        "address": "123 Main Road, Apt 4B, Metro City 110001",
    }
    r1, _, _, _ = engine.verify_with_audit(img1_path, submitted1)
    test_results["test_1_high_confidence"] = r1

    test_medium_fuzzy_tier()
    img2_path = OUTPUT_DIR / "test2_skewed_fuzzy.png"
    submitted2 = {
        "name": "Johnny Doe",
        "dob": "1990-05-15",
        "document_id": "ABCDE1234F",
        "address": "123 Main Road, Apt 4B",
    }
    r2, _, _, _ = engine.verify_with_audit(img2_path, submitted2, deskew=True)
    test_results["test_2_skewed_fuzzy"] = r2

def test_front_and_optional_back_document():
    """
    Test verifying front document (mandatory) and optional back document.
    Ensures:
    1. Single-sided front verification functions when back is omitted.
    2. Two-sided verification correctly maps fields: name from front, address from back.
    """
    engine = VerificationEngine()

    # Front card: has Name, DOB, Gender, Doc ID (NO address)
    front_img = np.full((400, 700, 3), 250, dtype=np.uint8)
    cv2.putText(front_img, "GOVERNMENT CITIZEN CARD FRONT", (30, 40), cv2.FONT_HERSHEY_DUPLEX, 0.6, (50, 50, 50), 2)
    cv2.putText(front_img, "Name: PRIYA SHARMA", (40, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 20), 2)
    cv2.putText(front_img, "DOB: 12/04/1995", (40, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 20), 2)
    cv2.putText(front_img, "Gender: Female", (40, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 20), 2)
    cv2.putText(front_img, "Doc ID: 987654321098", (40, 250), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 20), 2)

    # Back card: has Address and Doc ID
    back_img = np.full((400, 700, 3), 250, dtype=np.uint8)
    cv2.putText(back_img, "GOVERNMENT CITIZEN CARD BACK", (30, 40), cv2.FONT_HERSHEY_DUPLEX, 0.6, (50, 50, 50), 2)
    cv2.putText(back_img, "Address: C/O Sharma, HNO 42, Park Street, Kolkata - 700016", (40, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (20, 20, 20), 2)
    cv2.putText(back_img, "Doc ID: 987654321098", (40, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 20), 2)

    submitted_front_only = {
        "name": "Priya Sharma",
        "dob": "12/04/1995",
        "gender": "Female",
        "document_id": "987654321098",
    }

    # 1. Front only (back omitted) - should succeed
    res_front_only, _, _, _ = engine.verify_with_audit(front_img, submitted_front_only)
    assert res_front_only["tier"] == "HIGH", f"Front only should be HIGH tier, got {res_front_only['tier']}"
    assert res_front_only["fields"]["name"]["doc_side"] == "front"

    # 2. Both front and back provided
    submitted_both = {
        "name": "Priya Sharma",
        "dob": "12/04/1995",
        "gender": "Female",
        "document_id": "987654321098",
        "address": "Park Street, Kolkata 700016",
    }
    pipe_res = engine.verify_with_audit(front_img, submitted_both, back_document_source=back_img)
    audit = pipe_res.audit_json

    assert pipe_res.has_back_document is True
    assert audit["fields"]["name"]["doc_side"] == "front"
    assert audit["fields"]["name"]["score"] == 100.0
    assert audit["fields"]["address"]["doc_side"] == "back"
    assert audit["fields"]["address"]["score"] >= 80.0
    assert audit["tier"] == "HIGH"


def run_tests() -> Dict[str, Any]:
    engine = VerificationEngine()
    test_results = {}

    test_high_confidence_tier()
    img1_path = OUTPUT_DIR / "test1_high_confidence.png"
    submitted1 = {
        "name": "Jonathan Doe",
        "dob": "1990-05-15",
        "document_id": "ABCDE1234F",
        "address": "123 Main Road, Apt 4B, Metro City 110001",
    }
    r1, _, _, _ = engine.verify_with_audit(img1_path, submitted1)
    test_results["test_1_high_confidence"] = r1

    test_medium_fuzzy_tier()
    img2_path = OUTPUT_DIR / "test2_skewed_fuzzy.png"
    submitted2 = {
        "name": "John Doe",
        "dob": "15/05/1990",
        "document_id": "ABCDE1234F",
        "address": "123 Main Road, Apt 4B, Metro City 110001",
    }
    r2, _, _, _ = engine.verify_with_audit(img2_path, submitted2, deskew=True)
    test_results["test_2_medium_fuzzy"] = r2

    test_critical_mismatch_tier()
    img3_path = OUTPUT_DIR / "test3_critical_mismatch.png"
    submitted3 = {
        "name": "Jonathan Doe",
        "dob": "1985-01-20",
        "document_id": "WXYZ9999Q",
        "address": "123 Main Road, Metro City 110001",
    }
    r3, _, _, _ = engine.verify_with_audit(img3_path, submitted3)
    test_results["test_3_critical_mismatch"] = r3

    test_low_confidence_tier()
    img4_path = OUTPUT_DIR / "test4_low_score.png"
    submitted4 = {
        "name": "Sarah Connor",
        "address": "99 Cyberdyne Blvd, Los Angeles 90001",
    }
    r4, _, _, _ = engine.verify_with_audit(img4_path, submitted4)
    test_results["test_4_low_confidence"] = r4

    test_pdf_processing()
    pdf_path = OUTPUT_DIR / "test5_credential.pdf"
    r5 = engine.verify(pdf_path, submitted1)
    test_results["test_5_pdf_credential"] = r5

    test_front_and_optional_back_document()

    with open(OUTPUT_DIR / "verification_results.json", "w", encoding="utf-8") as f:
        json.dump(test_results, f, indent=2)

    return test_results


if __name__ == "__main__":
    run_tests()
    print("All tests executed successfully!")
