"""
POST /extract endpoint.

Accepts a PDF file upload and returns structured JSON extraction
with per-field confidence scores. The endpoint always returns valid
JSON, even if the underlying extraction partially fails.
"""

import time
from fastapi import APIRouter, UploadFile, File, HTTPException

from core.config import get_settings
from core.logging import get_logger
from core.exceptions import FileTooLargeError, FileProcessingError, ValidationError
from schemas.extraction import ExtractionResponse
from services.extraction.orchestrator import ExtractionOrchestrator

router = APIRouter()
logger = get_logger("api.extract")


@router.post(
    "/extract",
    response_model=ExtractionResponse,
    summary="Extract structured data from a logistics PDF",
    description=(
        "Upload a PDF containing a commercial invoice and/or packing list. "
        "Returns structured JSON with per-field confidence scores. "
        "The API always returns valid JSON, even if extraction partially fails."
    ),
    responses={
        200: {"description": "Successful extraction with structured data"},
        400: {"description": "Invalid request (missing file, wrong format)"},
        413: {"description": "File exceeds size limit"},
        422: {"description": "File could not be processed (corrupt PDF)"},
        500: {"description": "Internal extraction error"},
    },
)
async def extract_document(
    file: UploadFile = File(
        ...,
        description="PDF file to extract data from (max 50MB)"
    ),
):
    """
    Extract structured data from a scanned logistics document.

    Accepts a PDF file and runs it through the hybrid extraction pipeline:
    1. PDF → page images (with image enhancement)
    2. Page classification (invoice vs packing list)
    3. VLM extraction (Gemini 2.5 Flash)
    4. OCR cross-validation (PaddleOCR)
    5. Confidence scoring (multi-signal)
    6. Structured JSON response

    The response includes per-field confidence scores and processing metadata.
    """
    settings = get_settings()

    # --- Input Validation ---
    if not file.filename:
        raise ValidationError(
            message="No file uploaded",
            details={"field": "file"}
        )

    if not file.filename.lower().endswith(".pdf"):
        raise ValidationError(
            message="Only PDF files are supported",
            details={
                "field": "file",
                "filename": file.filename,
                "supported_formats": [".pdf"],
            }
        )

    # Read file bytes
    file_bytes = await file.read()

    if not file_bytes:
        raise ValidationError(
            message="Uploaded file is empty",
            details={"field": "file"}
        )

    # Check file size
    file_size_mb = len(file_bytes) / (1024 * 1024)
    if file_size_mb > settings.max_file_size_mb:
        raise FileTooLargeError(
            message=f"File size ({file_size_mb:.1f}MB) exceeds limit ({settings.max_file_size_mb}MB)",
            details={
                "file_size_mb": round(file_size_mb, 1),
                "max_size_mb": settings.max_file_size_mb,
            }
        )

    logger.info(
        "extraction_request_received",
        filename=file.filename,
        file_size_mb=round(file_size_mb, 2),
    )

    # --- Run Extraction Pipeline ---
    orchestrator = ExtractionOrchestrator()
    result = await orchestrator.extract(file_bytes)

    logger.info(
        "extraction_request_complete",
        filename=file.filename,
        processing_time=result.metadata.processing_time_seconds,
        invoice_items=len(result.invoice.line_items),
        packing_list_items=len(result.packing_list.line_items),
    )

    return result
