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
import asyncio
from typing import Any

from core.config import get_settings
from core.logging import get_logger
from core.exceptions import ExtractionError
from schemas.common import ProcessingMetadata
from schemas.extraction import ExtractionResponse, InvoiceData, PackingListData
from services.extraction.preprocessor import DocumentPreprocessor
from services.extraction.vlm_extractor import VLMExtractor
from services.extraction.ocr_extractor import OCRExtractor
from services.extraction.agentic_doc_extractor import AgenticDocumentExtractor
from services.extraction.confidence_scorer import ConfidenceScorer
from services.extraction.result_merger import ResultMerger
from services.extraction.output_saver import save_pipeline_outputs

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
        self.agentic_extractor = AgenticDocumentExtractor()

    async def extract(
        self, file_bytes: bytes, filename: str = "document.pdf"
    ) -> ExtractionResponse:
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
        execution_times = {
            "preprocessing": 0.0,
            "classification": 0.0,
            "ocr_validation": 0.0,
            "vlm_extraction": 0.0,
        }
        raw_vlm_texts = {}

        # --- Stage 1: Preprocessing ---
        logger.info("pipeline_stage", stage="preprocessing")
        t0 = time.time()
        pages = await self.preprocessor.process_pdf(file_bytes)
        execution_times["preprocessing"] += time.time() - t0

        # --- Stage 2: Classification & Extraction ---
        # Process all pages concurrently
        tasks = [self._process_page(page_info) for page_info in pages]
        page_results = await asyncio.gather(*tasks)

        invoice_data = None
        packing_list_data = None
        ocr_validation_used = False

        for res in page_results:
            page_num = res["page_num"]
            if res["invoice_data"] and invoice_data is None:
                invoice_data = res["invoice_data"]
            if res["packing_list_data"] and packing_list_data is None:
                packing_list_data = res["packing_list_data"]

            json_repair_applied = json_repair_applied or res["json_repair_applied"]
            ocr_validation_used = ocr_validation_used or res["ocr_validation_used"]
            warnings.extend(res["warnings"])
            if res["raw_text"]:
                raw_vlm_texts[page_num] = res["raw_text"]

            # Since pages run concurrently, the wall-clock time is roughly the max
            execution_times["classification"] = max(
                execution_times["classification"],
                res["execution_times"]["classification"],
            )
            execution_times["ocr_validation"] = max(
                execution_times["ocr_validation"],
                res["execution_times"]["ocr_validation"],
            )
            execution_times["vlm_extraction"] = max(
                execution_times["vlm_extraction"],
                res["execution_times"]["vlm_extraction"],
            )

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

        # Round the execution times for clean output
        execution_times = {k: round(v, 2) for k, v in execution_times.items()}

        metadata = ProcessingMetadata(
            processing_time_seconds=round(processing_time, 2),
            primary_model=self.settings.primary_model,
            fallback_used=fallback_used,
            ocr_validation_used=ocr_validation_used,
            pages_processed=len(pages),
            json_repair_applied=json_repair_applied,
            warnings=warnings,
            execution_times=execution_times,
        )

        response = ExtractionResponse(
            invoice=invoice_data,
            packing_list=packing_list_data,
            metadata=metadata,
        )

        # --- Stage 4: Save Pipeline Outputs ---
        save_pipeline_outputs(
            filename=filename,
            pages=pages,
            raw_vlm_texts=raw_vlm_texts,
            extraction_response=response.model_dump(),
        )

        logger.info(
            "extraction_pipeline_complete",
            processing_time=round(processing_time, 2),
            invoice_line_items=len(invoice_data.line_items),
            packing_list_line_items=len(packing_list_data.line_items),
            step_times=execution_times,
        )

        return response

    async def _extract_invoice(
        self,
        image_bytes: bytes,
        merger: ResultMerger,
        page_num: int,
    ) -> tuple[InvoiceData, bool, float, str]:
        """
        Extract invoice data with VLM, falling back to ADE if needed.

        Returns:
            Tuple of (InvoiceData, json_repair_was_needed)
        """
        try:
            logger.info(
                "pipeline_stage",
                stage="vlm_extraction",
                page=page_num,
                doc_type="invoice",
            )
            t0 = time.time()
            raw_data, json_repair, raw_text = await self.vlm_extractor.extract_invoice(
                image_bytes
            )
            invoice = merger.build_invoice(raw_data)

            # Note: The time is tracked, but we need to return it to add to the total
            return invoice, json_repair, time.time() - t0, raw_text

        except Exception as e:
            logger.warning(
                "primary_invoice_extraction_failed_triggering_agentic_fallback",
                page=page_num,
                error=str(e),
            )
            try:
                t_fallback = time.time()
                raw_data, json_repair, raw_text = (
                    await self.agentic_extractor.extract_invoice(image_bytes)
                )
                invoice = merger.build_invoice(raw_data)
                return invoice, json_repair, time.time() - t_fallback, raw_text
            except Exception as fallback_e:
                logger.error(
                    "agentic_fallback_invoice_extraction_failed",
                    page=page_num,
                    error=str(fallback_e),
                )
                # Return empty invoice with warning rather than crashing
                return InvoiceData(), True, 0.0, ""

    async def _extract_packing_list(
        self,
        image_bytes: bytes,
        merger: ResultMerger,
        page_num: int,
    ) -> tuple[PackingListData, bool, float, str]:
        """
        Extract packing list data with VLM, falling back to ADE if needed.

        Returns:
            Tuple of (PackingListData, json_repair_was_needed)
        """
        try:
            logger.info(
                "pipeline_stage",
                stage="vlm_extraction",
                page=page_num,
                doc_type="packing_list",
            )
            t0 = time.time()
            raw_data, json_repair, raw_text = (
                await self.vlm_extractor.extract_packing_list(image_bytes)
            )
            packing_list = merger.build_packing_list(raw_data)
            return packing_list, json_repair, time.time() - t0, raw_text

        except Exception as e:
            logger.warning(
                "primary_packing_list_extraction_failed_triggering_agentic_fallback",
                page=page_num,
                error=str(e),
            )
            try:
                t_fallback = time.time()
                raw_data, json_repair, raw_text = (
                    await self.agentic_extractor.extract_packing_list(image_bytes)
                )
                packing_list = merger.build_packing_list(raw_data)
                return packing_list, json_repair, time.time() - t_fallback, raw_text
            except Exception as fallback_e:
                logger.error(
                    "agentic_fallback_packing_list_extraction_failed",
                    page=page_num,
                    error=str(fallback_e),
                )
                return PackingListData(), True, 0.0, ""

    async def _process_page(self, page_info: dict) -> dict:
        """Process a single page, running classification, OCR, and extraction."""
        page_num = page_info["page_number"]
        image_bytes = page_info["image_bytes"]

        result = {
            "page_num": page_num,
            "invoice_data": None,
            "packing_list_data": None,
            "json_repair_applied": False,
            "ocr_validation_used": False,
            "raw_text": None,
            "warnings": [],
            "execution_times": {
                "classification": 0.0,
                "ocr_validation": 0.0,
                "vlm_extraction": 0.0,
            },
        }

        # Concurrently run classification and OCR validation
        logger.info("pipeline_stage", stage="classification_and_ocr", page=page_num)

        async def run_classification():
            t0 = time.time()
            ptype = await self.vlm_extractor.classify_page(image_bytes)
            return ptype, time.time() - t0

        async def run_ocr():
            if not self.settings.enable_ocr_validation:
                return [], 0.0, False
            try:
                t0 = time.time()
                ocr_res = await self.ocr_extractor.extract_text(
                    page_info["enhanced_image"]
                )
                return ocr_res.get("lines", []), time.time() - t0, True
            except Exception as e:
                logger.warning("ocr_validation_skipped", page=page_num, error=str(e))
                result["warnings"].append(
                    f"OCR validation failed for page {page_num}: {str(e)}"
                )
                return [], 0.0, False

        class_result, ocr_result_data = await asyncio.gather(
            run_classification(), run_ocr()
        )

        page_type, class_time = class_result
        ocr_lines, ocr_time, ocr_used = ocr_result_data

        result["execution_times"]["classification"] = class_time
        result["execution_times"]["ocr_validation"] = ocr_time
        result["ocr_validation_used"] = ocr_used

        logger.info("page_type_determined", page=page_num, type=page_type)
        if ocr_used:
            logger.info("ocr_validation_complete", page=page_num, lines=len(ocr_lines))

        scorer = ConfidenceScorer(ocr_lines=ocr_lines)
        merger = ResultMerger(scorer=scorer)

        # Extract based on page type
        if page_type == "commercial_invoice":
            inv, repair, ext_time, raw = await self._extract_invoice(
                image_bytes, merger, page_num
            )
            result["invoice_data"] = inv
            result["json_repair_applied"] = repair
            result["execution_times"]["vlm_extraction"] = ext_time
            result["raw_text"] = raw
        elif page_type == "packing_list":
            pl, repair, ext_time, raw = await self._extract_packing_list(
                image_bytes, merger, page_num
            )
            result["packing_list_data"] = pl
            result["json_repair_applied"] = repair
            result["execution_times"]["vlm_extraction"] = ext_time
            result["raw_text"] = raw
        else:
            logger.warning("unknown_page_type", page=page_num, type=page_type)
            result["warnings"].append(
                f"Page {page_num} classified as '{page_type}', attempting invoice extraction"
            )

            # Default fallback try
            if page_num == 1:
                inv, repair, ext_time, raw = await self._extract_invoice(
                    image_bytes, merger, page_num
                )
                result["invoice_data"] = inv
                result["json_repair_applied"] = repair
                result["execution_times"]["vlm_extraction"] = ext_time
                result["raw_text"] = raw
            else:
                pl, repair, ext_time, raw = await self._extract_packing_list(
                    image_bytes, merger, page_num
                )
                result["packing_list_data"] = pl
                result["json_repair_applied"] = repair
                result["execution_times"]["vlm_extraction"] = ext_time
                result["raw_text"] = raw

        return result
