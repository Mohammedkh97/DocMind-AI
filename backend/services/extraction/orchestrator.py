"""
Extraction pipeline orchestrator.

This is the main coordinator that runs the complete extraction workflow:
1. Preprocess PDF → page images
2. Classify each page (invoice vs packing list)
3. Run VLM extraction on each page
4. Optionally run OCR for cross-validation
5. Merge results into typed Pydantic models
6. Apply confidence scoring

The orchestrator implements the fallback chain:
  VLM → OCR+LLM → partial extraction with low confidence
"""

import time
from typing import Any

from core.config import get_settings
from core.logging import get_logger
from core.exceptions import ExtractionError
from schemas.common import ProcessingMetadata
from schemas.extraction import ExtractionResponse, InvoiceData, PackingListData
from services.extraction.preprocessor import DocumentPreprocessor
from services.extraction.vlm_extractor import VLMExtractor
from services.extraction.ocr_extractor import OCRExtractor
from services.extraction.confidence_scorer import ConfidenceScorer
from services.extraction.result_merger import ResultMerger

logger = get_logger("orchestrator")


class ExtractionOrchestrator:
    """
    Coordinates the full document extraction pipeline.

    Manages the lifecycle from PDF upload to structured JSON response,
    handling classification, extraction, validation, and confidence scoring.
    """

    def __init__(self):
        self.settings = get_settings()
        self.preprocessor = DocumentPreprocessor()
        self.vlm_extractor = VLMExtractor()
        self.ocr_extractor = OCRExtractor()

    async def extract(self, file_bytes: bytes) -> ExtractionResponse:
        """
        Run the complete extraction pipeline on a PDF.

        Args:
            file_bytes: Raw PDF file bytes

        Returns:
            ExtractionResponse with structured data and metadata
        """
        start_time = time.time()
        warnings = []
        fallback_used = False
        ocr_validation_used = False
        json_repair_applied = False

        # --- Stage 1: Preprocessing ---
        logger.info("pipeline_stage", stage="preprocessing")
        pages = await self.preprocessor.process_pdf(file_bytes)

        # --- Stage 2: Classification & Extraction ---
        invoice_data = None
        packing_list_data = None

        for page_info in pages:
            page_num = page_info["page_number"]
            image_bytes = page_info["image_bytes"]

            # Classify page
            logger.info("pipeline_stage", stage="classification", page=page_num)
            page_type = await self.vlm_extractor.classify_page(image_bytes)
            logger.info("page_type_determined", page=page_num, type=page_type)

            # Run OCR for cross-validation (if enabled)
            ocr_lines = []
            if self.settings.enable_ocr_validation:
                try:
                    logger.info("pipeline_stage", stage="ocr_validation", page=page_num)
                    ocr_result = await self.ocr_extractor.extract_text(
                        page_info["enhanced_image"]
                    )
                    ocr_lines = ocr_result.get("lines", [])
                    ocr_validation_used = True
                    logger.info(
                        "ocr_validation_complete",
                        page=page_num,
                        lines=len(ocr_lines),
                        avg_confidence=ocr_result.get("avg_confidence", 0),
                    )
                except Exception as e:
                    logger.warning(
                        "ocr_validation_skipped",
                        page=page_num,
                        error=str(e),
                    )
                    warnings.append(f"OCR validation failed for page {page_num}: {str(e)}")

            # Create scorer with OCR data for cross-validation
            scorer = ConfidenceScorer(ocr_lines=ocr_lines)
            merger = ResultMerger(scorer=scorer)

            # Extract based on page type
            if page_type == "commercial_invoice":
                invoice_data, json_repair = await self._extract_invoice(
                    image_bytes, merger, page_num
                )
                json_repair_applied = json_repair_applied or json_repair

            elif page_type == "packing_list":
                packing_list_data, json_repair = await self._extract_packing_list(
                    image_bytes, merger, page_num
                )
                json_repair_applied = json_repair_applied or json_repair

            else:
                # Unknown page type — try both extraction methods
                logger.warning("unknown_page_type", page=page_num, type=page_type)
                warnings.append(f"Page {page_num} classified as '{page_type}', attempting invoice extraction")

                # Default: try invoice extraction on first page, packing list on second
                if page_num == 1 and invoice_data is None:
                    invoice_data, json_repair = await self._extract_invoice(
                        image_bytes, merger, page_num
                    )
                    json_repair_applied = json_repair_applied or json_repair
                elif packing_list_data is None:
                    packing_list_data, json_repair = await self._extract_packing_list(
                        image_bytes, merger, page_num
                    )
                    json_repair_applied = json_repair_applied or json_repair

        # --- Stage 3: Fill defaults for missing data ---
        if invoice_data is None:
            logger.warning("no_invoice_found")
            warnings.append("No commercial invoice page detected")
            invoice_data = InvoiceData()

        if packing_list_data is None:
            logger.warning("no_packing_list_found")
            warnings.append("No packing list page detected")
            packing_list_data = PackingListData()

        # --- Build final response ---
        processing_time = time.time() - start_time

        metadata = ProcessingMetadata(
            processing_time_seconds=round(processing_time, 2),
            primary_model=self.settings.primary_model,
            fallback_used=fallback_used,
            ocr_validation_used=ocr_validation_used,
            pages_processed=len(pages),
            json_repair_applied=json_repair_applied,
            warnings=warnings,
        )

        response = ExtractionResponse(
            invoice=invoice_data,
            packing_list=packing_list_data,
            metadata=metadata,
        )

        logger.info(
            "extraction_pipeline_complete",
            processing_time=round(processing_time, 2),
            invoice_line_items=len(invoice_data.line_items),
            packing_list_line_items=len(packing_list_data.line_items),
        )

        return response

    async def _extract_invoice(
        self,
        image_bytes: bytes,
        merger: ResultMerger,
        page_num: int,
    ) -> tuple[InvoiceData, bool]:
        """
        Extract invoice data with VLM, falling back to OCR if needed.

        Returns:
            Tuple of (InvoiceData, json_repair_was_needed)
        """
        try:
            logger.info("pipeline_stage", stage="vlm_extraction", page=page_num, doc_type="invoice")
            raw_data, json_repair = await self.vlm_extractor.extract_invoice(image_bytes)
            invoice = merger.build_invoice(raw_data)
            return invoice, json_repair

        except Exception as e:
            logger.error(
                "invoice_extraction_failed",
                page=page_num,
                error=str(e),
            )
            # Return empty invoice with warning rather than crashing
            return InvoiceData(), True

    async def _extract_packing_list(
        self,
        image_bytes: bytes,
        merger: ResultMerger,
        page_num: int,
    ) -> tuple[PackingListData, bool]:
        """
        Extract packing list data with VLM, falling back to OCR if needed.

        Returns:
            Tuple of (PackingListData, json_repair_was_needed)
        """
        try:
            logger.info("pipeline_stage", stage="vlm_extraction", page=page_num, doc_type="packing_list")
            raw_data, json_repair = await self.vlm_extractor.extract_packing_list(image_bytes)
            packing_list = merger.build_packing_list(raw_data)
            return packing_list, json_repair

        except Exception as e:
            logger.error(
                "packing_list_extraction_failed",
                page=page_num,
                error=str(e),
            )
            return PackingListData(), True
