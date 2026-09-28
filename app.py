"""
Streamlit Web Application for Automated Credential Verification
Provides two-sided document upload (Front required, Back optional),
interactive form inputs, real-time spatial bounding box visualization,
and side-by-side field crop inspection.
"""

from __future__ import annotations

import io
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
import streamlit as st

from ai_automation.pipeline import VerificationEngine

# Page configuration
st.set_page_config(
    page_title="Sewa Setu - Credential Verification Engine",
    page_icon="🛡️",
    layout="wide",
)

st.title("🛡️ Automated Credential Verification Engine")
st.caption("Gov-AI Citizen Identity Verification with Non-Punitive Assurance Routing")

# Initialize Engine
@st.cache_resource
def get_engine():
    return VerificationEngine(ocr_backend="auto")

engine = get_engine()

# Layout: Two columns (Left: Upload & Input Form, Right: Results & Bounding Boxes)
col_left, col_right = st.columns([1, 1], gap="medium")

with col_left:
    st.subheader("1. Upload Credential Document")

    # Front and Back Uploaders
    col_u1, col_u2 = st.columns(2)
    with col_u1:
        st.markdown("##### 📄 Front Side *(Mandatory)*")
        uploaded_front = st.file_uploader(
            "Upload Front Side:",
            type=["png", "jpg", "jpeg", "pdf", "tif", "webp"],
            key="front_file_uploader",
            help="Mandatory: Scanned front side of document (Name, Photo, DOB, Gender, ID).",
        )
    with col_u2:
        st.markdown("##### 📄 Back Side *(Optional)*")
        uploaded_back = st.file_uploader(
            "Upload Back Side:",
            type=["png", "jpg", "jpeg", "pdf", "tif", "webp"],
            key="back_file_uploader",
            help="Optional: Upload back side if address is on the back. Not mandatory if all details are already on the front side (e.g. PAN card, e-Aadhaar slip).",
        )

    st.info(
        "💡 **Note**: Front side is **mandatory**. Back side is **optional** because documents such as "
        "PAN cards, passports, or single-page e-slips have all details on the front side only."
    )

    st.subheader("2. Citizen Application Data")
    sub_name = st.text_input("Applicant Full Name:", placeholder="e.g. Jonathan Doe or Bokam Leeladhar")
    sub_dob = st.text_input("Date of Birth / Year of Birth:", placeholder="e.g. 1990-05-15, 15/05/1990, or 2003")
    sub_gender = st.selectbox("Applicant Gender (Optional):", ["", "Male", "Female", "Transgender"], index=0)
    sub_id = st.text_input("Document ID Number:", placeholder="e.g. ABCDE1234F or 1234 5678 9012")
    sub_address = st.text_area("Permanent / Current Address:", placeholder="e.g. 1-63/b, Gullepalli, Sabbavaram or 123 Main Road")

    deskew_option = st.checkbox("Enable Automatic Rotation Deskewing", value=True)
    verify_button = st.button("🚀 Verify Credential", type="primary", use_container_width=True)

with col_right:
    st.subheader("3. Verification Results & Visual Audit")

    if uploaded_front is not None and verify_button:
        # Prepare submitted dictionary
        submitted_data = {}
        if sub_name.strip():
            submitted_data["name"] = sub_name.strip()
        if sub_dob.strip():
            submitted_data["dob"] = sub_dob.strip()
        if sub_gender.strip():
            submitted_data["gender"] = sub_gender.strip()
        if sub_id.strip():
            submitted_data["document_id"] = sub_id.strip()
        if sub_address.strip():
            submitted_data["address"] = sub_address.strip()

        with st.spinner("Processing document(s) (deskewing, noise reduction, spatial OCR tokenization)..."):
            front_bytes = uploaded_front.read()
            back_bytes = uploaded_back.read() if uploaded_back is not None else None

            pipeline_res = engine.verify_with_audit(
                front_bytes,
                submitted_data,
                back_document_source=back_bytes,
                deskew=deskew_option,
            )
            audit_json = pipeline_res.audit_json
            preprocessed_front = pipeline_res.preprocessed
            preprocessed_back = pipeline_res.back_preprocessed

        # Tier Banner Display
        tier = audit_json.get("tier", "UNKNOWN")
        overall_score = audit_json.get("overall_score", 0.0)
        critical_flag = audit_json.get("critical_flag", False)

        if tier == "HIGH":
            st.success(f"### Tier: HIGH Confidence ({overall_score:.1f}%)\nZero critical discrepancies detected. Eligible for automated validation.")
        elif tier == "MEDIUM":
            st.warning(f"### Tier: MEDIUM Confidence ({overall_score:.1f}%)\nMinor variations detected. Logged for standard audit.")
        elif tier == "CRITICAL_MISMATCH":
            st.error(f"### Tier: CRITICAL MISMATCH ({overall_score:.1f}%)\nDiscrepancy detected in critical identity numbers or date of birth. Routed to priority audit.")
        else:
            st.info(f"### Tier: LOW Confidence ({overall_score:.1f}%)\nTechnical clarity or imaging uncertainty requires priority manual officer review. Never auto-rejected.")

        # Governance Assurance Banner
        st.markdown(
            f"> **Policy Notice:** {audit_json.get('policy_notice', '')}"
        )

        color_map = {
            "name": (0, 150, 255),        # Orange
            "dob": (0, 200, 0),           # Green
            "document_id": (255, 50, 50), # Blue
            "gender": (255, 105, 180),    # Pink
            "address": (200, 0, 200),     # Magenta
        }

        # Visual Bounding Box Rendering
        if pipeline_res.has_back_document and preprocessed_back is not None:
            tab_front, tab_back = st.tabs(["📄 Front Side Document", "📄 Back Side Document"])

            with tab_front:
                annotated_front = preprocessed_front.deskewed_color_image.copy()
                for fname, fdata in audit_json["fields"].items():
                    if fdata.get("doc_side", "front") == "front":
                        bbox = fdata.get("bbox")
                        if bbox and len(bbox) == 4 and bbox[2] > 0 and bbox[3] > 0:
                            x, y, w, h = bbox
                            c = color_map.get(fname, (0, 255, 255))
                            cv2.rectangle(annotated_front, (x, y), (x + w, y + h), c, 2)
                            cv2.putText(
                                annotated_front,
                                f"{fname.upper()} ({fdata.get('score', 0)}%)",
                                (x, max(15, y - 5)),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.5,
                                c,
                                2,
                            )
                rgb_front = cv2.cvtColor(annotated_front, cv2.COLOR_BGR2RGB)
                st.image(rgb_front, caption="Front Side — Spatial Bounding Boxes", use_container_width=True)

            with tab_back:
                annotated_back = preprocessed_back.deskewed_color_image.copy()
                for fname, fdata in audit_json["fields"].items():
                    if fdata.get("doc_side", "front") == "back":
                        bbox = fdata.get("bbox")
                        if bbox and len(bbox) == 4 and bbox[2] > 0 and bbox[3] > 0:
                            x, y, w, h = bbox
                            c = color_map.get(fname, (0, 255, 255))
                            cv2.rectangle(annotated_back, (x, y), (x + w, y + h), c, 2)
                            cv2.putText(
                                annotated_back,
                                f"{fname.upper()} ({fdata.get('score', 0)}%)",
                                (x, max(15, y - 5)),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.5,
                                c,
                                2,
                            )
                rgb_back = cv2.cvtColor(annotated_back, cv2.COLOR_BGR2RGB)
                st.image(rgb_back, caption="Back Side — Spatial Bounding Boxes", use_container_width=True)

        else:
            # Single / Front Document
            annotated = preprocessed_front.deskewed_color_image.copy()
            for fname, fdata in audit_json["fields"].items():
                bbox = fdata.get("bbox")
                if bbox and len(bbox) == 4 and bbox[2] > 0 and bbox[3] > 0:
                    x, y, w, h = bbox
                    c = color_map.get(fname, (0, 255, 255))
                    cv2.rectangle(annotated, (x, y), (x + w, y + h), c, 2)
                    cv2.putText(
                        annotated,
                        f"{fname.upper()} ({fdata.get('score', 0)}%)",
                        (x, max(15, y - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        c,
                        2,
                    )
            rgb_annotated = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
            st.image(rgb_annotated, caption="Extracted Spatial Bounding Boxes on Deskewed Document", use_container_width=True)

        # Field-by-field breakdown with crops
        st.write("---")
        st.subheader("Field Crop-and-Compare Audit")

        for fname, fdata in audit_json["fields"].items():
            doc_side = fdata.get("doc_side", "front")
            side_badge = "Front Side" if doc_side == "front" else "Back Side"
            side_icon = "📄 Front" if doc_side == "front" else "📑 Back"

            with st.expander(f"📌 {fname.upper()} — Score: {fdata.get('score', 0)}% [{side_icon}] ({fdata.get('status', '').upper()})", expanded=True):
                c1, c2 = st.columns([1, 1])
                with c1:
                    st.markdown(f"**Document Origin:** `{side_badge}`")
                    st.markdown(f"**Submitted Value:** `{fdata.get('submitted', 'N/A')}`")
                    st.markdown(f"**OCR Extracted:** `{fdata.get('ocr_text', 'N/A')}`")
                    if fdata.get("diff"):
                        st.markdown(f"**Reviewer Diff:** :orange[{fdata.get('diff')}]")
                    st.markdown(f"**Bounding Box [x, y, w, h]:** `{fdata.get('bbox')}`")
                with c2:
                    bbox = fdata.get("bbox")
                    target_image = (
                        preprocessed_back.deskewed_color_image
                        if (doc_side == "back" and preprocessed_back is not None)
                        else preprocessed_front.deskewed_color_image
                    )
                    if bbox and len(bbox) == 4 and bbox[2] > 0 and bbox[3] > 0:
                        crop = engine.crop_field(target_image, bbox, padding=8)
                        if crop is not None:
                            crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
                            st.image(crop_rgb, caption=f"Physical Document Crop: {fname} ({side_badge})", use_container_width=True)
                    else:
                        st.info(f"No spatial bounding box detected on {side_badge}.")

        # Full JSON Artifact
        st.write("---")
        st.subheader("Structured JSON Payload")
        st.json(audit_json)

    elif uploaded_front is None:
        st.info("👈 Upload at least the Front Side document on the left and enter citizen details to run verification.")
