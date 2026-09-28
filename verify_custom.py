"""
Interactive & Command-Line Utility for Verifying Custom Documents
Supports single document CLI flags, interactive terminal prompts, and batch JSON mode.
Saves annotated images and cropped field snippets for immediate visual inspection.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import cv2
import numpy as np

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_automation.pipeline import VerificationEngine


# Ensure UTF-8 output on Windows terminals
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def draw_bounding_boxes(image: np.ndarray, fields_data: Dict[str, Any]) -> np.ndarray:
    """Overlays color-coded bounding boxes and field confidence labels on document."""
    annotated = image.copy()
    color_map = {
        "name": (0, 140, 255),       # Orange
        "dob": (0, 200, 0),          # Green
        "document_id": (255, 50, 50),# Blue
        "gender": (255, 105, 180),   # Pink
        "address": (200, 0, 200),    # Magenta
    }

    for fname, fdata in fields_data.items():
        bbox = fdata.get("bbox")
        if not bbox or len(bbox) != 4:
            continue
        x, y, w, h = bbox
        if w <= 0 or h <= 0:
            continue

        color = color_map.get(fname, (0, 255, 255))
        # Draw bounding rectangle
        cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)

        # Draw label tag
        score = fdata.get("score", 0)
        label = f"{fname.upper()} ({score}%)"
        (text_w, text_h), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        tag_y = max(20, y - 4)
        cv2.putText(
            annotated,
            label,
            (x + 2, tag_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            2,
            cv2.LINE_AA,
        )

    return annotated


def print_terminal_report(result: Dict[str, Any], output_dir: Path, image_name: str) -> None:
    """Prints a clear, formatted summary report to stdout."""
    overall_score = result.get("overall_score", 0.0)
    tier = result.get("tier", "UNKNOWN")
    critical_flag = result.get("critical_flag", False)
    fields = result.get("fields", {})

    print("\n" + "=" * 80)
    print(f" VERIFICATION REPORT: {image_name}")
    print("=" * 80)
    print(f"Overall Match Score : {overall_score:.1f}%")
    print(f"Confidence Tier     : {tier}")
    print(f"Critical Conflict   : {'YES (Audit Priority)' if critical_flag else 'NO'}")
    if result.get("review_reason"):
        print(f"Routing Reason      : {result.get('review_reason')}")
    print(f"Governance Notice   : {result.get('policy_notice', 'N/A')}")
    print("-" * 80)

    # Table Header
    print(f"{'FIELD':<12} | {'SCORE':<7} | {'STATUS':<13} | {'SUBMITTED':<20} | {'OCR EXTRACTED'}")
    print("-" * 80)
    for fname, fdata in fields.items():
        sub = str(fdata.get("submitted", ""))[:18]
        ocr = str(fdata.get("ocr_text", ""))[:25]
        score = f"{fdata.get('score', 0):.1f}%"
        status = fdata.get("status", "")
        print(f"{fname:<12} | {score:<7} | {status:<13} | {sub:<20} | {ocr}")
        if "diff" in fdata and fdata["diff"]:
            print(f"  |-- Diff: {fdata['diff']}")
        print(f"  |-- Bounding Box [x, y, w, h]: {fdata.get('bbox')}")

    print("-" * 80)
    print(f"Annotated preview and field crops saved to: {output_dir.resolve()}")
    print("=" * 80 + "\n")


def verify_file(
    engine: VerificationEngine,
    doc_path: Path,
    submitted_data: Dict[str, str],
    output_dir: Path,
    back_doc_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Runs the verification on a single or two-sided document and saves crops/annotations."""
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = doc_path.stem

    pipeline_res = engine.verify_with_audit(
        doc_path, submitted_data, back_document_source=back_doc_path, deskew=True
    )
    audit_json = pipeline_res.audit_json
    preprocessed_front = pipeline_res.preprocessed
    preprocessed_back = pipeline_res.back_preprocessed

    # 1. Save annotated front image with bounding box rectangles
    front_fields = {k: v for k, v in audit_json["fields"].items() if v.get("doc_side", "front") == "front"}
    annotated_front = draw_bounding_boxes(preprocessed_front.deskewed_color_image, front_fields)
    annotated_path = output_dir / f"{stem}_front_annotated.png"
    cv2.imwrite(str(annotated_path), annotated_front)

    # 2. Save annotated back image if back document was provided
    if pipeline_res.has_back_document and preprocessed_back is not None:
        back_fields = {k: v for k, v in audit_json["fields"].items() if v.get("doc_side", "front") == "back"}
        annotated_back = draw_bounding_boxes(preprocessed_back.deskewed_color_image, back_fields)
        back_stem = back_doc_path.stem if back_doc_path else "back"
        annotated_back_path = output_dir / f"{back_stem}_back_annotated.png"
        cv2.imwrite(str(annotated_back_path), annotated_back)

    # 3. Save individual cropped field images for UI compare
    crops_dir = output_dir / f"{stem}_crops"
    crops_dir.mkdir(exist_ok=True)
    for fname, fdata in audit_json["fields"].items():
        bbox = fdata.get("bbox")
        doc_side = fdata.get("doc_side", "front")
        target_img = (
            preprocessed_back.deskewed_color_image
            if (doc_side == "back" and preprocessed_back is not None)
            else preprocessed_front.deskewed_color_image
        )
        if bbox and len(bbox) == 4 and bbox[2] > 0 and bbox[3] > 0:
            crop = engine.crop_field(target_img, bbox, padding=6)
            if crop is not None:
                cv2.imwrite(str(crops_dir / f"{fname}_{doc_side}.png"), crop)

    # 4. Save JSON result
    json_path = output_dir / f"{stem}_result.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(audit_json, f, indent=2)

    doc_display = doc_path.name + (f" + {back_doc_path.name}" if back_doc_path else "")
    print_terminal_report(audit_json, output_dir, doc_display)
    return audit_json


def interactive_prompt() -> None:
    """Interactive mode prompting user for document path and citizen details."""
    print("=" * 80)
    print(" AUTOMATED CREDENTIAL VERIFICATION ENGINE - CUSTOM DATA INPUT")
    print("=" * 80)

    while True:
        doc_input = input("Enter path to FRONT document image or PDF (Mandatory): ").strip().strip('"').strip("'")
        doc_path = Path(doc_input)
        if doc_path.exists():
            break
        print(f"Error: File '{doc_path}' not found. Please try again.\n")

    back_input = input("Enter path to BACK document (Optional, press Enter to skip if all details on front): ").strip().strip('"').strip("'")
    back_doc_path = Path(back_input) if back_input and Path(back_input).exists() else None

    print("\nEnter submitted citizen details (press Enter to skip any optional field):")
    name = input("  Full Name           : ").strip()
    dob = input("  Date of Birth       : ").strip()
    gender = input("  Gender (M/F/Other)  : ").strip()
    doc_id = input("  Document ID Number  : ").strip()
    address = input("  Address             : ").strip()

    submitted: Dict[str, str] = {}
    if name:
        submitted["name"] = name
    if dob:
        submitted["dob"] = dob
    if gender:
        submitted["gender"] = gender
    if doc_id:
        submitted["document_id"] = doc_id
    if address:
        submitted["address"] = address

    if not submitted:
        print("\nWarning: No submitted data provided. Running extraction-only inspection.")

    output_dir = Path("custom_output")
    engine = VerificationEngine()
    print("\nProcessing document through deskewing, noise reduction, and OCR pipeline...")
    verify_file(engine, doc_path, submitted, output_dir, back_doc_path=back_doc_path)


def main():
    parser = argparse.ArgumentParser(
        description="Verify custom document images/PDFs using Automated Credential Verification Engine."
    )
    parser.add_argument(
        "--doc", "--front", "-d", type=str, help="Path to front document image or PDF file (mandatory)."
    )
    parser.add_argument(
        "--back", "--back-doc", type=str, help="Optional path to back document image or PDF file."
    )
    parser.add_argument("--name", "-n", type=str, help="Submitted applicant full name.")
    parser.add_argument(
        "--dob", type=str, help="Submitted date of birth (e.g. YYYY-MM-DD or DD/MM/YYYY)."
    )
    parser.add_argument(
        "--gender", "-g", type=str, help="Submitted applicant gender (Male, Female, Transgender)."
    )
    parser.add_argument(
        "--id", type=str, help="Submitted document ID (PAN, Aadhaar, Passport, DL, etc.)."
    )
    parser.add_argument("--address", "-a", type=str, help="Submitted physical address.")
    parser.add_argument(
        "--output", "-o", type=str, default="custom_output", help="Directory to save crops and results."
    )
    parser.add_argument(
        "--batch", type=str, help="Path to JSON file containing a list of records to test."
    )

    args = parser.parse_args()

    # 1. Batch mode
    if args.batch:
        batch_path = Path(args.batch)
        if not batch_path.exists():
            print(f"Error: Batch JSON file not found: {batch_path}")
            sys.exit(1)

        with open(batch_path, "r", encoding="utf-8") as f:
            records = json.load(f)

        engine = VerificationEngine()
        out_dir = Path(args.output)
        for i, rec in enumerate(records, 1):
            p = Path(rec.get("document_path", ""))
            if not p.exists():
                print(f"[{i}/{len(records)}] Skipping '{p}': File not found.")
                continue
            bp = Path(rec.get("back_document_path", "")) if rec.get("back_document_path") else None
            sub = rec.get("submitted", {})
            print(f"[{i}/{len(records)}] Verifying '{p.name}'...")
            verify_file(engine, p, sub, out_dir / p.stem, back_doc_path=bp)
        return

    # 2. Single/Two-sided document CLI mode
    if args.doc:
        doc_path = Path(args.doc)
        if not doc_path.exists():
            print(f"Error: Document file not found: {doc_path}")
            sys.exit(1)

        back_doc_path = Path(args.back) if args.back and Path(args.back).exists() else None

        submitted = {}
        if args.name:
            submitted["name"] = args.name
        if args.dob:
            submitted["dob"] = args.dob
        if args.gender:
            submitted["gender"] = args.gender
        if args.id:
            submitted["document_id"] = args.id
        if args.address:
            submitted["address"] = args.address

        engine = VerificationEngine()
        verify_file(engine, doc_path, submitted, Path(args.output), back_doc_path=back_doc_path)
        return

    # 3. Interactive prompt mode if executed without CLI arguments
    interactive_prompt()


if __name__ == "__main__":
    main()
