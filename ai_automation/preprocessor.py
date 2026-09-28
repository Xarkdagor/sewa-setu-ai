"""
Document Preprocessor Module
Loads images and PDFs, performs rotation deskewing, noise reduction, and grayscale thresholding.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, Union

import cv2
import numpy as np
from PIL import Image


@dataclass
class PreprocessResult:
    """Structured container for preprocessed document image artifacts."""
    original_image: np.ndarray  # Original image in BGR format
    processed_image: np.ndarray  # Cleaned, thresholded binary image for OCR
    grayscale_image: np.ndarray  # Denoised grayscale image
    deskewed_color_image: np.ndarray  # Deskewed color image (useful for UI crop-and-compare)
    skew_angle: float  # Angle in degrees by which the document was rotated to deskew
    width: int
    height: int

    @property
    def pil_processed(self) -> Image.Image:
        """Return processed binary image as PIL Image."""
        return Image.fromarray(self.processed_image)

    @property
    def pil_original(self) -> Image.Image:
        """Return original image as PIL Image (RGB)."""
        rgb = cv2.cvtColor(self.original_image, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb)

    @property
    def pil_deskewed_color(self) -> Image.Image:
        """Return deskewed color image as PIL Image (RGB)."""
        rgb = cv2.cvtColor(self.deskewed_color_image, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb)


class DocumentPreprocessor:
    """
    Advanced Document Preprocessor using OpenCV and Pillow.
    Handles loading (Images, PDFs), rotation deskewing, noise reduction,
    and adaptive/Otsu grayscale thresholding.
    """

    def __init__(
        self,
        target_dpi: int = 300,
        max_skew_angle: float = 45.0,
        adaptive_threshold: bool = True,
        denoise_kernel_size: int = 3,
    ):
        self.target_dpi = target_dpi
        self.max_skew_angle = max_skew_angle
        self.adaptive_threshold = adaptive_threshold
        self.denoise_kernel_size = denoise_kernel_size

    def load_document(self, source: Union[str, Path, bytes, io.BytesIO, Image.Image, np.ndarray], page_index: int = 0) -> np.ndarray:
        """
        Loads document from multiple source types into a BGR numpy array.
        Supports file paths, raw bytes, Pillow Image, or existing numpy array.
        Automatically renders PDF documents via pypdfium2 if PDF format is detected.
        """
        # 1. Already numpy array
        if isinstance(source, np.ndarray):
            if len(source.shape) == 2:
                return cv2.cvtColor(source, cv2.COLOR_GRAY2BGR)
            elif source.shape[2] == 4:
                return cv2.cvtColor(source, cv2.COLOR_RGBA2BGR)
            return source.copy()

        # 2. PIL Image
        if isinstance(source, Image.Image):
            rgb = source.convert("RGB")
            return cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2BGR)

        # 3. Path or string
        if isinstance(source, (str, Path)):
            path = Path(source)
            if not path.exists():
                raise FileNotFoundError(f"Document file not found: {path}")

            raw_bytes = path.read_bytes()
            if path.suffix.lower() == ".pdf":
                return self._load_pdf(raw_bytes, page_index=page_index)
            
            # Read via OpenCV buffer decoding to support arbitrary Windows Unicode paths
            nparr = np.frombuffer(raw_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is not None:
                return img
            
            # Fallback to Pillow for formats OpenCV might struggle with
            pil_img = Image.open(io.BytesIO(raw_bytes))
            return cv2.cvtColor(np.array(pil_img.convert("RGB")), cv2.COLOR_RGB2BGR)

        # 4. Raw bytes or BytesIO
        if isinstance(source, (bytes, io.BytesIO)):
            raw_bytes = source.getvalue() if isinstance(source, io.BytesIO) else source
            if raw_bytes.startswith(b"%PDF"):
                return self._load_pdf(raw_bytes, page_index=page_index)
            
            nparr = np.frombuffer(raw_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is not None:
                return img
            
            pil_img = Image.open(io.BytesIO(raw_bytes))
            return cv2.cvtColor(np.array(pil_img.convert("RGB")), cv2.COLOR_RGB2BGR)

        raise ValueError(f"Unsupported document source type: {type(source)}")

    def _load_pdf(self, pdf_bytes: bytes, page_index: int = 0) -> np.ndarray:
        """Renders a PDF page to a high-resolution BGR numpy array using pypdfium2."""
        try:
            import pypdfium2 as pdfium
            pdf = pdfium.PdfDocument(pdf_bytes)
            if page_index >= len(pdf):
                raise IndexError(f"PDF page {page_index} out of range (total pages: {len(pdf)})")
            
            page = pdf[page_index]
            # Standard PDF is 72 dpi, scale to target_dpi (e.g. 300 dpi -> scale = 300 / 72 ≈ 4.166)
            scale = self.target_dpi / 72.0
            bitmap = page.render(scale=scale)
            pil_image = bitmap.to_pil()
            return cv2.cvtColor(np.array(pil_image.convert("RGB")), cv2.COLOR_RGB2BGR)
        except ImportError:
            # Fallback if pdf2image or fitz is present
            try:
                import importlib
                pdf2image_mod = importlib.import_module("pdf2image")
                images = pdf2image_mod.convert_from_bytes(
                    pdf_bytes, dpi=self.target_dpi, first_page=page_index + 1, last_page=page_index + 1
                )
                return cv2.cvtColor(np.array(images[0].convert("RGB")), cv2.COLOR_RGB2BGR)
            except Exception as e:
                raise RuntimeError(f"Failed to load PDF. Please install pypdfium2 or pdf2image: {e}")

    def detect_skew_angle(self, gray: np.ndarray) -> float:
        """
        Calculates the skew angle of the text in the image.
        Uses Otsu thresholding and minAreaRect on foreground coordinates.
        """
        # Threshold: text/foreground as 255, background as 0
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]

        # Dilate slightly horizontally to group text lines into contiguous blocks
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 3))
        dilated = cv2.dilate(thresh, kernel, iterations=1)

        # Find coordinates of all foreground pixels
        pts = cv2.findNonZero(dilated)
        if pts is None or len(pts) < 100:
            return 0.0

        # Compute minimum area bounding box
        rect = cv2.minAreaRect(pts)
        angle = rect[-1]

        # cv2.minAreaRect returns angle in [-90, 0) or [0, 90) depending on OpenCV version
        if angle < -45.0:
            angle = -(90.0 + angle)
        elif angle > 45.0:
            angle = 90.0 - angle
        else:
            angle = -angle

        # If angle is negligible or outside reasonable document skew limits, do not rotate
        if abs(angle) < 0.2 or abs(angle) > self.max_skew_angle:
            return 0.0

        return float(angle)

    def rotate_image(self, image: np.ndarray, angle: float, border_color: Tuple[int, int, int] = (255, 255, 255)) -> np.ndarray:
        """
        Rotates image around its center by angle degrees while expanding boundaries
        so no document content is clipped.
        """
        if abs(angle) < 0.01:
            return image.copy()

        h, w = image.shape[:2]
        center = (w / 2.0, h / 2.0)

        # Rotation matrix
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        cos = np.abs(M[0, 0])
        sin = np.abs(M[0, 1])

        # Compute new bounding dimensions of the rotated image
        new_w = int((h * sin) + (w * cos))
        new_h = int((h * cos) + (w * sin))

        # Adjust transformation matrix center translation
        M[0, 2] += (new_w / 2.0) - center[0]
        M[1, 2] += (new_h / 2.0) - center[1]

        is_gray = len(image.shape) == 2
        fill = border_color[0] if is_gray else border_color

        rotated = cv2.warpAffine(
            image,
            M,
            (new_w, new_h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=fill,
        )
        return rotated

    def reduce_noise(self, gray: np.ndarray) -> np.ndarray:
        """
        Applies bilateral filtering and median blur to eliminate grain, speckles,
        and scanner sensor noise while preserving sharp text edges.
        """
        # Bilateral filter smoothens textures while preserving sharp line edges
        denoised = cv2.bilateralFilter(gray, d=7, sigmaColor=75, sigmaSpace=75)
        
        # Optional subtle median blur if kernel > 1
        if self.denoise_kernel_size > 1:
            k = self.denoise_kernel_size if self.denoise_kernel_size % 2 == 1 else self.denoise_kernel_size + 1
            denoised = cv2.medianBlur(denoised, k)

        return denoised

    def apply_thresholding(self, gray: np.ndarray) -> np.ndarray:
        """
        Converts grayscale image into optimal binary black & white image for OCR.
        Uses adaptive thresholding or Otsu's binarization.
        """
        if self.adaptive_threshold:
            # Adaptive threshold handles uneven document lighting / shadows
            binary = cv2.adaptiveThreshold(
                gray,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                blockSize=21,
                C=11,
            )
        else:
            # Otsu's thresholding for uniform contrast scans
            _, binary = cv2.threshold(
                gray,
                0,
                255,
                cv2.THRESH_BINARY + cv2.THRESH_OTSU,
            )

        return binary

    def process(
        self,
        source: Union[str, Path, bytes, io.BytesIO, Image.Image, np.ndarray],
        deskew: bool = True,
        page_index: int = 0,
    ) -> PreprocessResult:
        """
        Executes full preprocessing pipeline:
        1. Load image / PDF
        2. Detect skew and rotate
        3. Convert to grayscale & denoise
        4. Apply thresholding for optimal OCR recognition
        """
        original = self.load_document(source, page_index=page_index)

        # Convert to grayscale for skew analysis
        initial_gray = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY)

        skew_angle = 0.0
        if deskew:
            skew_angle = self.detect_skew_angle(initial_gray)

        # Rotate color and grayscale if skew detected
        if abs(skew_angle) > 0.01:
            deskewed_color = self.rotate_image(original, skew_angle, border_color=(255, 255, 255))
            deskewed_gray = cv2.cvtColor(deskewed_color, cv2.COLOR_BGR2GRAY)
        else:
            deskewed_color = original.copy()
            deskewed_gray = initial_gray.copy()

        # Noise reduction
        denoised_gray = self.reduce_noise(deskewed_gray)

        # Grayscale thresholding
        thresholded = self.apply_thresholding(denoised_gray)

        h, w = thresholded.shape[:2]
        return PreprocessResult(
            original_image=original,
            processed_image=thresholded,
            grayscale_image=denoised_gray,
            deskewed_color_image=deskewed_color,
            skew_angle=skew_angle,
            width=w,
            height=h,
        )
