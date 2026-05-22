"""
PDF preprocessing: conversion to images and image enhancement.

Design decisions:
- PyMuPDF (fitz) for PDF→image: fast, no external dependencies like poppler
- OpenCV for image enhancement: industry standard, extensive toolkit
- Enhancement pipeline is tuned for scanned logistics documents:
  mild denoising + CLAHE contrast + mild sharpening
"""

import io
import tempfile
from pathlib import Path

import cv2
import pymupdf as fitz  # PyMuPDF
import numpy as np
from PIL import Image

from core.config import get_settings
from core.logging import get_logger
from core.exceptions import FileProcessingError

logger = get_logger("preprocessor")


class DocumentPreprocessor:
    """Converts PDFs to enhanced page images ready for extraction."""

    def __init__(self):
        self.settings = get_settings()

    async def process_pdf(self, file_bytes: bytes) -> list[dict]:
        """
        Convert a PDF to a list of page images with metadata.

        Returns:
            List of dicts with:
            - 'page_number': 1-indexed page number
            - 'original_image': PIL.Image (unmodified)
            - 'enhanced_image': PIL.Image (preprocessed for better extraction)
            - 'image_bytes': bytes of the enhanced image as PNG
            - 'width': image width in pixels
            - 'height': image height in pixels
        """
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
        except Exception as e:
            raise FileProcessingError(
                message=f"Failed to open PDF: {str(e)}",
                details={"error_type": type(e).__name__}
            )

        if len(doc) == 0:
            raise FileProcessingError(
                message="PDF has no pages",
                details={"page_count": 0}
            )

        pages = []
        for page_idx in range(len(doc)):
            page_num = page_idx + 1
            logger.info("processing_page", page=page_num, total_pages=len(doc))

            try:
                page = doc[page_idx]
                pix = page.get_pixmap(dpi=self.settings.pdf_render_dpi)

                # Convert to PIL Image
                img_bytes = pix.tobytes("png")
                original_image = Image.open(io.BytesIO(img_bytes)).convert("RGB")

                # Enhance image
                if self.settings.enable_image_enhancement:
                    enhanced_image = self._enhance_image(original_image)
                else:
                    enhanced_image = original_image.copy()

                # Convert enhanced image to bytes for API calls
                enhanced_bytes = io.BytesIO()
                enhanced_image.save(enhanced_bytes, format="PNG")
                enhanced_bytes = enhanced_bytes.getvalue()

                pages.append({
                    "page_number": page_num,
                    "original_image": original_image,
                    "enhanced_image": enhanced_image,
                    "image_bytes": enhanced_bytes,
                    "width": pix.width,
                    "height": pix.height,
                })

            except Exception as e:
                logger.error("page_processing_failed", page=page_num, error=str(e))
                raise FileProcessingError(
                    message=f"Failed to process page {page_num}: {str(e)}",
                    details={"page": page_num, "error_type": type(e).__name__}
                )

        doc.close()
        logger.info("pdf_processing_complete", pages_processed=len(pages))
        return pages

    def _enhance_image(self, image: Image.Image) -> Image.Image:
        """
        Apply image enhancement pipeline for better OCR/VLM extraction.

        Pipeline:
        1. Convert to grayscale for processing
        2. Bilateral denoising (preserves edges while removing noise)
        3. CLAHE contrast enhancement (adaptive, handles uneven lighting)
        4. Mild sharpening
        5. Convert back to RGB

        These parameters are tuned for scanned logistics documents —
        too aggressive and you lose detail, too mild and blur remains.
        """
        img_array = np.array(image)

        # Convert to grayscale for enhancement operations
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array

        # Step 1: Bilateral denoising — removes noise while preserving edges
        denoised = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)

        # Step 2: CLAHE — Contrast Limited Adaptive Histogram Equalization
        # Handles uneven scan lighting better than global histogram equalization
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(denoised)

        # Step 3: Mild sharpening kernel
        sharpen_kernel = np.array([
            [0, -0.5, 0],
            [-0.5, 3, -0.5],
            [0, -0.5, 0]
        ])
        sharpened = cv2.filter2D(enhanced, -1, sharpen_kernel)

        # Clamp values to valid range
        sharpened = np.clip(sharpened, 0, 255).astype(np.uint8)

        # Convert back to RGB (3-channel) for VLM compatibility
        rgb_enhanced = cv2.cvtColor(sharpened, cv2.COLOR_GRAY2RGB)

        return Image.fromarray(rgb_enhanced)
