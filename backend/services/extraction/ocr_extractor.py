"""
OCR extraction fallback using PaddleOCR.

This serves two purposes:
1. FALLBACK: If VLM extraction fails entirely, OCR provides raw text
   that can be sent to an LLM for structured parsing
2. VALIDATION: OCR results cross-validate VLM extraction for confidence
   scoring — if both agree on a value, confidence is higher

PaddleOCR v4 is chosen over Tesseract for significantly better accuracy
on degraded scans and native bounding box output.
"""

import asyncio
from typing import Any

import numpy as np
from PIL import Image

from core.config import get_settings
from core.logging import get_logger
from core.exceptions import OCRExtractionError

logger = get_logger("ocr_extractor")


class OCRExtractor:
    """
    Extracts raw text with bounding boxes from document images using PaddleOCR.

    Used as a fallback and validation layer alongside the primary VLM extraction.
    """

    def __init__(self):
        self.settings = get_settings()
        self._engine = None
        self._lock = asyncio.Lock()  # Ensure thread-safety for initialization and inference

    def _get_engine(self):
        """Lazy load the OCR engine to save memory and avoid slow startup."""
        if self._engine is None:
            try:
                import os
                # Prevent Paddle 3.x backend PIR segfaults (harmless on 2.x)
                os.environ["FLAGS_use_mkldnn"] = "0"
                os.environ["FLAGS_use_onednn"] = "0"
                os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] = "0"
                os.environ["FLAGS_enable_pir_api"] = "0"
                
                # Prevent PaddleX from hanging on model source checks
                os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
                os.environ["DISABLE_MODEL_SOURCE_CHECK"] = "True"

                from paddleocr import PaddleOCR
                self._engine = PaddleOCR(
                    use_angle_cls=True,
                    lang=self.settings.ocr_language,
                )
                logger.info("paddleocr_engine_initialized")
            except ImportError:
                logger.error("paddleocr_not_installed")
                raise OCRExtractionError(
                    message="PaddleOCR is not installed",
                    details={"install": "pip install paddleocr"}
                )
        return self._engine

    async def extract_text(self, image: Image.Image) -> dict[str, Any]:
        """
        Run OCR on a document image.

        Returns:
            Dict with:
            - 'full_text': concatenated text from all detected regions
            - 'lines': list of dicts with 'text', 'confidence', 'bbox'
            - 'avg_confidence': average OCR confidence across all detections
        """
        try:
            img_array = np.array(image)
            async with self._lock:
                result = await asyncio.to_thread(
                    self._run_ocr, img_array
                )
            return result
        except OCRExtractionError:
            raise
        except Exception as e:
            logger.error("ocr_extraction_failed", error=str(e))
            raise OCRExtractionError(
                message=f"OCR extraction failed: {str(e)}",
                details={"error_type": type(e).__name__}
            )

    def _run_ocr(self, img_array: np.ndarray) -> dict[str, Any]:
        """Run PaddleOCR synchronously (called via asyncio.to_thread)."""
        engine = self._get_engine()
        results = engine.ocr(img_array)

        lines = []
        all_text_parts = []
        total_confidence = 0.0

        if results and results[0]:
            for line in results[0]:
                bbox = line[0]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                text = line[1][0]
                confidence = float(line[1][1])

                lines.append({
                    "text": text,
                    "confidence": round(confidence, 4),
                    "bbox": bbox,
                })
                all_text_parts.append(text)
                total_confidence += confidence

        avg_confidence = (
            total_confidence / len(lines) if lines else 0.0
        )

        full_text = "\n".join(all_text_parts)

        logger.info(
            "ocr_extraction_complete",
            lines_detected=len(lines),
            avg_confidence=round(avg_confidence, 3),
            text_length=len(full_text),
        )

        return {
            "full_text": full_text,
            "lines": lines,
            "avg_confidence": round(avg_confidence, 4),
        }

    def find_text_match(
        self,
        ocr_lines: list[dict],
        target_value: str,
        fuzzy_threshold: float = 0.8,
    ) -> dict | None:
        """
        Search OCR results for a specific value.

        Used for cross-validation: check if the VLM-extracted value
        appears in the OCR results. If so, confidence is boosted.

        Args:
            ocr_lines: List of OCR line dicts from extract_text()
            target_value: The value to search for
            fuzzy_threshold: Minimum similarity ratio for fuzzy matching

        Returns:
            Matching OCR line dict, or None if not found
        """
        if not target_value or not ocr_lines:
            return None

        target_lower = str(target_value).lower().strip()

        # Exact substring match first
        for line in ocr_lines:
            if target_lower in line["text"].lower():
                return line

        # Fuzzy match for OCR errors
        for line in ocr_lines:
            similarity = self._string_similarity(target_lower, line["text"].lower())
            if similarity >= fuzzy_threshold:
                return line

        return None

    @staticmethod
    def _string_similarity(s1: str, s2: str) -> float:
        """Simple character-level similarity ratio."""
        if not s1 or not s2:
            return 0.0
        # Use longest common subsequence ratio
        len1, len2 = len(s1), len(s2)
        if len1 == 0 or len2 == 0:
            return 0.0

        # Simple overlap check
        shorter = s1 if len1 <= len2 else s2
        longer = s1 if len1 > len2 else s2

        if shorter in longer:
            return len(shorter) / len(longer)

        # Character-level matching
        matches = sum(1 for c in shorter if c in longer)
        return matches / max(len1, len2)
