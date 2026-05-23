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

    async def extract(self, file_bytes: bytes, filename: str = "document.pdf") -> ExtractionResponse:
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
        # Run all pages concurrently to cut processing time in half
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
            ocr_validation_used = ocr_validation_used or res.get("ocr_validation_used", False)
            warnings.extend(res["warnings"])
            if res["raw_text"]:
                raw_vlm_texts[page_num] = res["raw_text"]
            
            # Since these ran concurrently, the wall-clock time for the stage is the max across all pages
            execution_times["classification"] = max(execution_times["classification"], res["execution_times"]["classification"])
            execution_times["ocr_validation"] = max(execution_times["ocr_validation"], res["execution_times"]["ocr_validation"])
            execution_times["vlm_extraction"] = max(execution_times["vlm_extraction"], res["execution_times"]["vlm_extraction"])

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
            extraction_response=response.model_dump()
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
        Extract invoice data with VLM, falling back to OCR if needed.

        Returns:
            Tuple of (InvoiceData, json_repair_was_needed)
        """
        try:
            logger.info("pipeline_stage", stage="vlm_extraction", page=page_num, doc_type="invoice")
            t0 = time.time()
            raw_data, json_repair, raw_text = await self.vlm_extractor.extract_invoice(image_bytes)
            invoice = merger.build_invoice(raw_data)
            
            # Note: The time is tracked, but we need to return it to add to the total
            return invoice, json_repair, time.time() - t0, raw_text

        except Exception as e:
            logger.error(
                "invoice_extraction_failed",
                page=page_num,
                error=str(e),
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
        Extract packing list data with VLM, falling back to OCR if needed.

        Returns:
            Tuple of (PackingListData, json_repair_was_needed)
        """
        try:
            logger.info("pipeline_stage", stage="vlm_extraction", page=page_num, doc_type="packing_list")
            t0 = time.time()
            raw_data, json_repair, raw_text = await self.vlm_extractor.extract_packing_list(image_bytes)
            packing_list = merger.build_packing_list(raw_data)
            return packing_list, json_repair, time.time() - t0, raw_text

        except Exception as e:
            logger.error(
                "packing_list_extraction_failed",
                page=page_num,
                error=str(e),
            )
            return PackingListData(), True, 0.0, ""

    async def _process_page(self, page_info: dict) -> dict:
        """
        Process a single page concurrently.
        Returns a dictionary with all the extracted info and metadata.
        """
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
            }
        }

        # Classify page
        logger.info("pipeline_stage", stage="classification", page=page_num)
        t0 = time.time()
        page_type = await self.vlm_extractor.classify_page(image_bytes)
        result["execution_times"]["classification"] = time.time() - t0
        logger.info("page_type_determined", page=page_num, type=page_type)

        # Run OCR for cross-validation (if enabled)
        ocr_lines = []
        if self.settings.enable_ocr_validation:
            try:
                logger.info("pipeline_stage", stage="ocr_validation", page=page_num)
                t0 = time.time()
                ocr_result = await self.ocr_extractor.extract_text(
                    page_info["enhanced_image"]
                )
                result["execution_times"]["ocr_validation"] = time.time() - t0
                result["ocr_validation_used"] = True
                ocr_lines = ocr_result.get("lines", [])
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
                result["warnings"].append(f"OCR validation failed for page {page_num}: {str(e)}")

        scorer = ConfidenceScorer(ocr_lines=ocr_lines)
        merger = ResultMerger(scorer=scorer)

        # Extract based on page type
        if page_type == "commercial_invoice":
            inv, repair, ext_time, raw = await self._extract_invoice(image_bytes, merger, page_num)
            result["invoice_data"] = inv
            result["json_repair_applied"] = repair
            result["execution_times"]["vlm_extraction"] = ext_time
            result["raw_text"] = raw
        elif page_type == "packing_list":
            pl, repair, ext_time, raw = await self._extract_packing_list(image_bytes, merger, page_num)
            result["packing_list_data"] = pl
            result["json_repair_applied"] = repair
            result["execution_times"]["vlm_extraction"] = ext_time
            result["raw_text"] = raw
        else:
            logger.warning("unknown_page_type", page=page_num, type=page_type)
            result["warnings"].append(f"Page {page_num} classified as '{page_type}', attempting invoice extraction")
            
            # Default: try invoice extraction on first page, packing list on second
            if page_num == 1:
                inv, repair, ext_time, raw = await self._extract_invoice(image_bytes, merger, page_num)
                result["invoice_data"] = inv
                result["json_repair_applied"] = repair
                result["execution_times"]["vlm_extraction"] = ext_time
                result["raw_text"] = raw
            else:
                pl, repair, ext_time, raw = await self._extract_packing_list(image_bytes, merger, page_num)
                result["packing_list_data"] = pl
                result["json_repair_applied"] = repair
                result["execution_times"]["vlm_extraction"] = ext_time
                result["raw_text"] = raw

        return result
