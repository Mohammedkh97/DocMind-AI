"""
Custom exception hierarchy for DocMind AI.

Using a typed exception hierarchy allows:
- Precise error handling in middleware (different HTTP status codes)
- Structured error responses to API consumers
- Clear separation between client errors and system errors
- Easy identification of error source during debugging
"""


class DocMindError(Exception):
    """Base exception for all DocMind AI errors."""

    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


# --- Client Errors (4xx) ---

class ValidationError(DocMindError):
    """Input validation failed (e.g., invalid file type, missing fields)."""
    pass


class FileProcessingError(DocMindError):
    """The uploaded file could not be processed (corrupt PDF, unsupported format)."""
    pass


class FileTooLargeError(DocMindError):
    """The uploaded file exceeds the maximum allowed size."""
    pass


# --- Extraction Errors (5xx but recoverable) ---

class ExtractionError(DocMindError):
    """General extraction pipeline failure."""
    pass


class VLMExtractionError(ExtractionError):
    """VLM (Vision-Language Model) extraction failed."""
    pass


class OCRExtractionError(ExtractionError):
    """OCR extraction failed."""
    pass


class JSONRepairError(ExtractionError):
    """All JSON repair attempts failed."""
    pass


# --- External Service Errors ---

class ModelAPIError(DocMindError):
    """External model API call failed (timeout, rate limit, etc.)."""

    def __init__(self, message: str, model: str, status_code: int | None = None, details: dict | None = None):
        self.model = model
        self.status_code = status_code
        super().__init__(message, details)


class ModelTimeoutError(ModelAPIError):
    """Model API call timed out."""
    pass


class ModelRateLimitError(ModelAPIError):
    """Model API rate limit exceeded."""
    pass


# --- Compliance Errors ---

class ComplianceError(DocMindError):
    """Compliance scoring engine error."""
    pass


class RuleEvaluationError(ComplianceError):
    """A specific compliance rule failed to evaluate."""

    def __init__(self, message: str, rule_id: str, details: dict | None = None):
        self.rule_id = rule_id
        super().__init__(message, details)
