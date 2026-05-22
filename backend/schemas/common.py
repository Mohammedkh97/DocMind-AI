"""
Shared types used across extraction and compliance schemas.

The ConfidenceField[T] generic is the core building block — every extracted
value carries a confidence score, making uncertainty a first-class citizen
in the API response rather than something silently hidden.
"""

from typing import Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class ConfidenceField(BaseModel, Generic[T]):
    """
    A field value paired with its extraction confidence score.

    Confidence is computed from multiple signals:
    - VLM self-reported confidence
    - OCR cross-validation agreement
    - Format validation (regex, type checks)
    - Business rule validation

    Args:
        value: The extracted value, or None if extraction failed.
        confidence: Score from 0.0 (no confidence) to 1.0 (fully certain).
    """
    value: T | None = None
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Extraction confidence score (0.0 to 1.0)"
    )

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence >= 0.85

    @property
    def is_low_confidence(self) -> bool:
        return self.confidence < 0.60

    @property
    def is_empty(self) -> bool:
        return self.value is None or (isinstance(self.value, str) and self.value.strip() == "")


class ProcessingMetadata(BaseModel):
    """Metadata about the extraction process — useful for debugging and monitoring."""
    processing_time_seconds: float = Field(
        description="Total wall-clock time for extraction"
    )
    primary_model: str = Field(
        description="Primary model used for extraction"
    )
    fallback_used: bool = Field(
        default=False,
        description="Whether fallback extraction was triggered"
    )
    ocr_validation_used: bool = Field(
        default=False,
        description="Whether OCR was used for cross-validation"
    )
    pages_processed: int = Field(
        description="Number of pages processed"
    )
    json_repair_applied: bool = Field(
        default=False,
        description="Whether JSON repair was needed"
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal warnings during processing"
    )
