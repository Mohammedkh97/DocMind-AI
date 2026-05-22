"""
Multi-signal confidence scoring engine.

Confidence is computed from MULTIPLE independent signals, not just the
model's self-reported confidence (which is unreliable). This is a key
differentiator from naive implementations.

Signals:
1. VLM self-reported confidence (from the extraction prompt)
2. OCR cross-validation (does OCR agree with VLM?)
3. Format validation (does the value match expected patterns?)
4. Business rule validation (does the math check out?)

Each signal is weighted, and the composite score is more trustworthy
than any single signal alone.
"""

import re
from datetime import datetime
from typing import Any

from core.logging import get_logger

logger = get_logger("confidence_scorer")

# Weight distribution for composite confidence
CONFIDENCE_WEIGHTS = {
    "vlm_confidence": 0.40,      # Model's self-assessment
    "ocr_agreement": 0.25,       # Cross-validation with OCR
    "format_valid": 0.20,        # Does the value match expected format?
    "business_valid": 0.15,      # Does the value pass business rules?
}


class ConfidenceScorer:
    """Computes multi-signal confidence scores for extracted fields."""

    def __init__(self, ocr_lines: list[dict] | None = None):
        """
        Args:
            ocr_lines: OCR results for cross-validation. If None, OCR
                      signal is neutral (0.5).
        """
        self.ocr_lines = ocr_lines or []

    def score_field(
        self,
        field_name: str,
        value: Any,
        vlm_confidence: float,
        field_type: str = "text",
    ) -> float:
        """
        Compute composite confidence for a single field.

        Args:
            field_name: Name of the field (for logging)
            value: The extracted value
            vlm_confidence: Model's self-reported confidence (0-1)
            field_type: One of 'text', 'number', 'date', 'hs_code',
                       'invoice_number', 'currency', 'unit'

        Returns:
            Composite confidence score (0.0 to 1.0)
        """
        if value is None:
            return 0.0

        # Signal 1: VLM confidence (clamped to 0-1)
        vlm_score = max(0.0, min(1.0, vlm_confidence))

        # Signal 2: OCR cross-validation
        ocr_score = self._check_ocr_agreement(value)

        # Signal 3: Format validation
        format_score = self._validate_format(value, field_type)

        # Signal 4: Business rule validation
        business_score = self._validate_business_rule(value, field_type)

        # Composite score
        composite = (
            CONFIDENCE_WEIGHTS["vlm_confidence"] * vlm_score
            + CONFIDENCE_WEIGHTS["ocr_agreement"] * ocr_score
            + CONFIDENCE_WEIGHTS["format_valid"] * format_score
            + CONFIDENCE_WEIGHTS["business_valid"] * business_score
        )

        final_score = round(max(0.0, min(1.0, composite)), 2)

        logger.debug(
            "confidence_computed",
            field=field_name,
            vlm=vlm_score,
            ocr=ocr_score,
            format=format_score,
            business=business_score,
            composite=final_score,
        )

        return final_score

    def _check_ocr_agreement(self, value: Any) -> float:
        """
        Check if the VLM-extracted value appears in OCR results.

        Returns:
            1.0 if value found in OCR text
            0.5 if no OCR data available (neutral)
            0.3 if value NOT found in OCR text (mild penalty)
        """
        if not self.ocr_lines:
            return 0.5  # No OCR data — neutral

        value_str = str(value).strip().lower()
        if not value_str:
            return 0.5

        # Check for exact or substring match
        for line in self.ocr_lines:
            ocr_text = line.get("text", "").lower()
            if value_str in ocr_text or ocr_text in value_str:
                return 1.0

        # Check for numeric match (OCR might format numbers differently)
        try:
            value_num = float(str(value).replace(",", "").replace("$", ""))
            for line in self.ocr_lines:
                try:
                    ocr_num = float(
                        line.get("text", "")
                        .replace(",", "")
                        .replace("$", "")
                        .strip()
                    )
                    if abs(value_num - ocr_num) < 0.01:
                        return 1.0
                except (ValueError, TypeError):
                    continue
        except (ValueError, TypeError):
            pass

        return 0.3  # Not found — mild confidence penalty

    def _validate_format(self, value: Any, field_type: str) -> float:
        """
        Validate that the extracted value matches expected format.

        Returns 1.0 for valid format, 0.0 for invalid.
        """
        value_str = str(value).strip()

        validators = {
            "hs_code": self._is_valid_hs_code,
            "invoice_number": self._is_valid_invoice_number,
            "date": self._is_valid_date,
            "currency": self._is_valid_currency,
            "unit": self._is_valid_unit,
            "number": self._is_valid_number,
        }

        validator = validators.get(field_type)
        if validator:
            return 1.0 if validator(value_str) else 0.0

        # Default: any non-empty string is valid
        return 1.0 if value_str else 0.0

    def _validate_business_rule(self, value: Any, field_type: str) -> float:
        """
        Apply simple business rules for validation.

        Returns 1.0 for reasonable values, 0.0 for unreasonable.
        """
        if field_type == "number":
            try:
                num = float(str(value).replace(",", "").replace("$", ""))
                # Negative amounts are suspicious for invoices
                if num < 0:
                    return 0.0
                return 1.0
            except (ValueError, TypeError):
                return 0.0

        return 1.0  # Default: no business rule applies

    # --- Format Validators ---

    @staticmethod
    def _is_valid_hs_code(value: str) -> bool:
        """HS codes should be 6-8 digits."""
        clean = value.replace(".", "").replace(" ", "").strip()
        return bool(re.match(r'^\d{6,8}$', clean))

    @staticmethod
    def _is_valid_invoice_number(value: str) -> bool:
        """Invoice numbers should be non-empty alphanumeric with separators."""
        return bool(re.match(r'^[A-Za-z0-9\-/_]+$', value.strip()))

    @staticmethod
    def _is_valid_date(value: str) -> bool:
        """Try common date formats."""
        date_formats = [
            "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y",
            "%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y",
            "%Y/%m/%d", "%d-%b-%Y", "%B %d %Y", "%d-%B-%Y",
            "%b. %d, %Y", "%d-%m-%y", "%m-%d-%Y",
            "%d %B, %Y", "%B %d,%Y", "%d %b, %Y",
        ]
        # Also accept "March 14, 2024" style
        for fmt in date_formats:
            try:
                datetime.strptime(value.strip(), fmt)
                return True
            except ValueError:
                continue
        return False

    @staticmethod
    def _is_valid_currency(value: str) -> bool:
        """Common currency codes."""
        valid_currencies = {
            "USD", "EUR", "GBP", "AED", "CNY", "JPY", "INR", "SAR",
            "QAR", "KWD", "BHD", "OMR", "SGD", "HKD", "CHF", "CAD",
            "AUD", "NZD",
        }
        return value.strip().upper() in valid_currencies

    @staticmethod
    def _is_valid_unit(value: str) -> bool:
        """Common trade units."""
        valid_units = {
            "MTR", "KG", "KGS", "LBS", "PCS", "CTN", "SET", "SETS",
            "DOZ", "PAIR", "PAIRS", "BOX", "BOXES", "ROLL", "ROLLS",
            "METER", "METERS", "YARD", "YARDS", "TON", "TONS",
            "BALE", "BALES", "CARTON", "CARTONS", "PKG", "PKGS",
        }
        return value.strip().upper() in valid_units

    @staticmethod
    def _is_valid_number(value: str) -> bool:
        """Valid numeric value."""
        try:
            float(str(value).replace(",", "").replace("$", ""))
            return True
        except (ValueError, TypeError):
            return False
