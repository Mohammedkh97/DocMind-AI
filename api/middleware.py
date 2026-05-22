"""
API middleware for request tracking, timing, and error handling.

Every request gets a unique ID for tracing through logs. Processing time
is tracked and returned in headers. All unhandled exceptions are caught
and converted to structured JSON error responses.
"""

import time
import uuid

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
import structlog

from core.exceptions import (
    DocMindError,
    ValidationError,
    FileProcessingError,
    FileTooLargeError,
    ExtractionError,
    ModelAPIError,
    ModelTimeoutError,
    ModelRateLimitError,
    ComplianceError,
)

logger = structlog.get_logger("middleware")


class RequestTrackingMiddleware(BaseHTTPMiddleware):
    """
    Adds request ID and processing time to every request.

    - X-Request-ID header for distributed tracing
    - X-Processing-Time header for performance monitoring
    - Structured log entry for each request
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        # Bind request context for structured logging
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        try:
            response = await call_next(request)
            processing_time = time.time() - start_time

            response.headers["X-Request-ID"] = request_id
            response.headers["X-Processing-Time"] = f"{processing_time:.3f}s"

            logger.info(
                "request_completed",
                status_code=response.status_code,
                processing_time=round(processing_time, 3),
            )
            return response

        except Exception as exc:
            processing_time = time.time() - start_time
            logger.error(
                "request_failed",
                error=str(exc),
                processing_time=round(processing_time, 3),
            )
            raise


def create_exception_handlers() -> dict:
    """
    Create exception handlers that map our exception hierarchy to HTTP responses.

    Returns a dict suitable for passing to FastAPI's exception_handlers parameter.
    """
    handlers = {}

    # --- Client Errors ---
    async def handle_validation_error(request: Request, exc: ValidationError):
        return JSONResponse(
            status_code=400,
            content={
                "error": "validation_error",
                "message": exc.message,
                "details": exc.details,
            },
        )

    async def handle_file_too_large(request: Request, exc: FileTooLargeError):
        return JSONResponse(
            status_code=413,
            content={
                "error": "file_too_large",
                "message": exc.message,
                "details": exc.details,
            },
        )

    async def handle_file_processing_error(request: Request, exc: FileProcessingError):
        return JSONResponse(
            status_code=422,
            content={
                "error": "file_processing_error",
                "message": exc.message,
                "details": exc.details,
            },
        )

    # --- Extraction Errors ---
    async def handle_extraction_error(request: Request, exc: ExtractionError):
        return JSONResponse(
            status_code=500,
            content={
                "error": "extraction_error",
                "message": exc.message,
                "details": exc.details,
            },
        )

    # --- Model API Errors ---
    async def handle_model_timeout(request: Request, exc: ModelTimeoutError):
        return JSONResponse(
            status_code=504,
            content={
                "error": "model_timeout",
                "message": exc.message,
                "model": exc.model,
            },
        )

    async def handle_model_rate_limit(request: Request, exc: ModelRateLimitError):
        return JSONResponse(
            status_code=429,
            content={
                "error": "rate_limit_exceeded",
                "message": exc.message,
                "model": exc.model,
            },
        )

    async def handle_model_api_error(request: Request, exc: ModelAPIError):
        return JSONResponse(
            status_code=502,
            content={
                "error": "model_api_error",
                "message": exc.message,
                "model": exc.model,
            },
        )

    # --- Compliance Errors ---
    async def handle_compliance_error(request: Request, exc: ComplianceError):
        return JSONResponse(
            status_code=500,
            content={
                "error": "compliance_error",
                "message": exc.message,
                "details": exc.details,
            },
        )

    # --- Catch-All ---
    async def handle_generic_docmind_error(request: Request, exc: DocMindError):
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "message": exc.message,
            },
        )

    async def handle_unexpected_error(request: Request, exc: Exception):
        logger.exception("unhandled_exception", error=str(exc))
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "message": "An unexpected error occurred. Check logs for details.",
            },
        )

    # Register handlers — order matters (most specific first)
    handlers[ValidationError] = handle_validation_error
    handlers[FileTooLargeError] = handle_file_too_large
    handlers[FileProcessingError] = handle_file_processing_error
    handlers[ModelTimeoutError] = handle_model_timeout
    handlers[ModelRateLimitError] = handle_model_rate_limit
    handlers[ModelAPIError] = handle_model_api_error
    handlers[ExtractionError] = handle_extraction_error
    handlers[ComplianceError] = handle_compliance_error
    handlers[DocMindError] = handle_generic_docmind_error
    handlers[Exception] = handle_unexpected_error

    return handlers
