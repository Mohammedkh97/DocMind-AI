"""
VLM (Vision-Language Model) extractor using Google Gemini.

This is the PRIMARY extraction method. Gemini 2.5 Flash processes the
document image directly, understanding layout, tables, and spatial
relationships natively — unlike OCR→LLM pipelines that lose this context.

Key design decisions:
- Temperature 0 for deterministic extraction
- Explicit JSON schema in the prompt to constrain output
- Retry with exponential backoff for API reliability
- Fallback to secondary model if primary fails
- Image sent as inline data (not file URI) for simplicity
"""

import base64
import asyncio
from typing import Any

from google import genai
from google.genai import types
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from core.config import get_settings
from core.logging import get_logger
from core.exceptions import VLMExtractionError, ModelAPIError, ModelTimeoutError
from services.common.json_repair import safe_parse_json
from prompts.extraction_prompts import (
    INVOICE_EXTRACTION_PROMPT,
    PACKING_LIST_EXTRACTION_PROMPT,
    PAGE_CLASSIFICATION_PROMPT,
)

logger = get_logger("vlm_extractor")


class VLMExtractor:
    """
    Extracts structured data from document images using Gemini VLM.

    The extractor sends the actual page image to the VLM with a structured
    prompt, and parses the response into a dict. JSON repair is applied
    if the model output is malformed.
    """

    def __init__(self):
        self.settings = get_settings()
        self.client = genai.Client(api_key=self.settings.gemini_api_key)

    async def classify_page(self, image_bytes: bytes) -> str:
        """
        Classify a page as 'commercial_invoice', 'packing_list', etc.

        Uses VLM to look at the document image and determine its type.
        This enables correct prompt selection for extraction.
        """
        try:
            raw_response = await self._call_model(
                prompt=PAGE_CLASSIFICATION_PROMPT,
                image_bytes=image_bytes,
                model_name=self.settings.primary_model,
            )
            classification = raw_response.strip().strip('"').lower()

            valid_types = {"commercial_invoice", "packing_list", "bill_of_lading", "unknown"}
            if classification not in valid_types:
                logger.warning("unexpected_classification", raw=classification)
                return "unknown"

            logger.info("page_classified", classification=classification)
            return classification

        except Exception as e:
            logger.error("classification_failed", error=str(e))
            return "unknown"

    async def extract_invoice(self, image_bytes: bytes) -> tuple[dict[str, Any], bool]:
        """
        Extract structured data from a commercial invoice image.

        Returns:
            Tuple of (extracted_data_dict, json_repair_was_needed)
        """
        return await self._extract_with_prompt(
            image_bytes=image_bytes,
            prompt=INVOICE_EXTRACTION_PROMPT,
            doc_type="invoice",
        )

    async def extract_packing_list(self, image_bytes: bytes) -> tuple[dict[str, Any], bool]:
        """
        Extract structured data from a packing list image.

        Returns:
            Tuple of (extracted_data_dict, json_repair_was_needed)
        """
        return await self._extract_with_prompt(
            image_bytes=image_bytes,
            prompt=PACKING_LIST_EXTRACTION_PROMPT,
            doc_type="packing_list",
        )

    async def _extract_with_prompt(
        self,
        image_bytes: bytes,
        prompt: str,
        doc_type: str,
    ) -> tuple[dict[str, Any], bool]:
        """
        Run extraction using VLM with retry and fallback logic.

        Strategy:
        1. Try primary model (Gemini 2.5 Flash)
        2. If primary fails, try fallback model (Gemini 2.0 Flash)
        3. Parse response through JSON repair pipeline
        """
        models_to_try = [self.settings.primary_model, self.settings.fallback_model]

        last_error = None
        for model_name in models_to_try:
            try:
                logger.info(
                    "vlm_extraction_starting",
                    doc_type=doc_type,
                    model=model_name,
                )

                raw_response = await self._call_model(
                    prompt=prompt,
                    image_bytes=image_bytes,
                    model_name=model_name,
                )

                # Parse through JSON repair pipeline
                parsed, repair_needed = safe_parse_json(raw_response)

                if repair_needed:
                    logger.warning(
                        "json_repair_applied",
                        doc_type=doc_type,
                        model=model_name,
                    )

                logger.info(
                    "vlm_extraction_complete",
                    doc_type=doc_type,
                    model=model_name,
                    fields_extracted=len(parsed),
                    repair_needed=repair_needed,
                )

                return parsed, repair_needed

            except Exception as e:
                last_error = e
                logger.warning(
                    "vlm_model_failed",
                    model=model_name,
                    doc_type=doc_type,
                    error=str(e),
                )
                continue

        raise VLMExtractionError(
            message=f"All VLM models failed for {doc_type}",
            details={"last_error": str(last_error)},
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, Exception)),
        before_sleep=lambda retry_state: logger.warning(
            "vlm_retry",
            attempt=retry_state.attempt_number,
        ),
    )
    async def _call_model(
        self,
        prompt: str,
        image_bytes: bytes,
        model_name: str,
    ) -> str:
        """
        Make a single API call to Gemini with image + text prompt.

        Uses retry with exponential backoff for transient failures.
        """
        try:
            # Prepare image as inline Part
            image_part = types.Part.from_bytes(
                data=image_bytes,
                mime_type="image/png",
            )

            # Call Gemini
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=model_name,
                contents=[image_part, prompt],
                config=types.GenerateContentConfig(
                    temperature=self.settings.model_temperature,
                    max_output_tokens=8192,
                    response_mime_type="application/json",
                ),
            )

            if not response.text:
                raise VLMExtractionError(
                    message="Empty response from VLM",
                    details={"model": model_name},
                )

            return response.text

        except asyncio.TimeoutError:
            raise ModelTimeoutError(
                message=f"Model {model_name} timed out",
                model=model_name,
            )
        except VLMExtractionError:
            raise
        except ModelTimeoutError:
            raise
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "rate" in error_msg.lower():
                raise ModelAPIError(
                    message=f"Rate limit hit for {model_name}",
                    model=model_name,
                    status_code=429,
                )
            raise ModelAPIError(
                message=f"Gemini API error: {error_msg}",
                model=model_name,
                details={"error_type": type(e).__name__},
            )
