"""
Native Windows Graphical File Picker for Credential Verification.
Opens a Windows File Explorer dialog so you can click and select your document without typing!
Supports front document (mandatory) and optional back document.
"""

import sys
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path

# Add root directory to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_automation.pipeline import VerificationEngine
from verify_custom import verify_file


def pick_file_graphically():
    # Hide the main Tkinter root window
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)  # Bring file picker window to front

    print("Opening Windows File Selection Window for FRONT side...")
    front_file = filedialog.askopenfilename(
        title="Select FRONT Side Credential Document (Mandatory)",
        filetypes=[
            ("Document & Image Files", "*.pdf;*.png;*.jpg;*.jpeg;*.webp;*.tif;*.tiff"),
            ("PDF Documents (*.pdf)", "*.pdf"),
            ("Image Files (*.png;*.jpg;*.jpeg)", "*.png;*.jpg;*.jpeg"),
            ("All Files (*.*)", "*.*"),
        ],
    )

    if not front_file:
        print("No front document selected. Operation cancelled.")
        return

    doc_path = Path(front_file)
    print(f"\n[Selected Front File]: {doc_path.resolve()}")

    # Ask if user wants to select an optional back side
    want_back = messagebox.askyesno(
        "Back Side Document (Optional)",
        "Do you want to select a BACK side image/document?\n\n"
        "(Select 'No' if all details are already on the front side, like PAN cards or e-slips.)"
    )

    back_doc_path = None
    if want_back:
        back_file = filedialog.askopenfilename(
            title="Select BACK Side Credential Document (Optional)",
            filetypes=[
                ("Document & Image Files", "*.pdf;*.png;*.jpg;*.jpeg;*.webp;*.tif;*.tiff"),
                ("PDF Documents (*.pdf)", "*.pdf"),
                ("Image Files (*.png;*.jpg;*.jpeg)", "*.png;*.jpg;*.jpeg"),
                ("All Files (*.*)", "*.*"),
            ],
        )
        if back_file:
            back_doc_path = Path(back_file)
            print(f"[Selected Back File]: {back_doc_path.resolve()}")
        else:
            print("[Back File]: Skipped (None selected).")

    print("\nEnter submitted citizen details (or press Enter to skip any field):")
    name = input("  Full Name           : ").strip()
    dob = input("  Date of Birth       : ").strip()
    gender = input("  Gender (M/F/Other)  : ").strip()
    doc_id = input("  Document ID Number  : ").strip()
    address = input("  Address             : ").strip()

    submitted = {}
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

    engine = VerificationEngine()
    out_dir = Path("custom_output")
    print("\nRunning verification pipeline...")
    verify_file(engine, doc_path, submitted, out_dir, back_doc_path=back_doc_path)


if __name__ == "__main__":
    pick_file_graphically()
