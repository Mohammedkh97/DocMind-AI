import time
import os
import tempfile
import asyncio
from pathlib import Path
from typing import Any

from landingai_ade import LandingAIADE

from core.config import get_settings
from core.logging import get_logger
from core.exceptions import ExtractionError
from services.extraction.openai_parser import OpenAIParser
from prompts.extraction_prompts import (
    INVOICE_EXTRACTION_PROMPT,
    PACKING_LIST_EXTRACTION_PROMPT,
)

logger = get_logger("agentic_doc_extractor")

class AgenticDocumentExtractor:
    """
    Extracts document information using Landing AI's Agentic Document Extraction (ADE).
    This serves as a secondary fallback to the primary Gemini VLM extractor.
    """

    def __init__(self):
        self.settings = get_settings()
        # Initialize LandingAIADE client using the API key from config
        # By default LandingAIADE checks the LANDING_AI_API_KEY environment variable.
        # We ensure it's set here for the client to pick up if loaded dynamically.
        if self.settings.landing_ai_api_key:
            os.environ["VISION_AGENT_API_KEY"] = self.settings.landing_ai_api_key
            self.client = LandingAIADE(apikey=self.settings.landing_ai_api_key)
        else:
            self.client = None
            logger.warning("Landing AI API key is not set. ADE extraction will fail.")
            
        if self.settings.openai_api_key:
            self.openai_parser = OpenAIParser(model_name="gpt-4o-mini")
        else:
            self.openai_parser = None
            logger.warning("OpenAI API key is not set. Schema parsing will fail, returning empty JSON.")

    async def extract_invoice(self, image_bytes: bytes | None = None, raw_text: str | None = None) -> tuple[dict, bool, str]:
        """
        Extract invoice data.
        Returns parsed structured data and the raw markdown text extracted by Landing AI.
        """
        return await self._run_landing_ai(image_bytes, doc_type="invoice", extraction_prompt=INVOICE_EXTRACTION_PROMPT)

    async def extract_packing_list(self, image_bytes: bytes | None = None, raw_text: str | None = None) -> tuple[dict, bool, str]:
        """
        Extract packing list data.
        Returns parsed structured data and the raw markdown text extracted by Landing AI.
        """
        return await self._run_landing_ai(image_bytes, doc_type="packing_list", extraction_prompt=PACKING_LIST_EXTRACTION_PROMPT)
        
    async def _run_landing_ai(self, image_bytes: bytes | None, doc_type: str, extraction_prompt: str) -> tuple[dict, bool, str]:
        if not self.client:
            raise ExtractionError(message="Landing AI Client is not initialized.")

        if not image_bytes:
            raise ExtractionError(message="image_bytes must be provided for ADE.")

        logger.info("agentic_extraction_starting", doc_type=doc_type)

        # Write bytes to a temporary file because LandingAIADE takes a Path
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_path = Path(tmp.name)

        try:
            # Create parse job (wrapping synchronous SDK calls in asyncio.to_thread if we want true async, 
            # but for now we can run synchronously or use to_thread)
            job = await asyncio.to_thread(
                self.client.parse_jobs.create,
                document=tmp_path,
                model="dpt-2-latest"
            )
            
            job_id = job.job_id
            logger.info("agentic_job_created", job_id=job_id)

            # Poll for completion
            while True:
                response = await asyncio.to_thread(self.client.parse_jobs.get, job_id)
                if response.status == "completed":
                    logger.info("agentic_job_completed", job_id=job_id)
                    break
                
                # Check for failure states
                if response.status in ["failed", "error"]:
                    raise ExtractionError(message=f"Landing AI job {job_id} failed with status: {response.status}")
                
                logger.debug(f"Job {job_id}: {response.status} ({response.progress * 100:.0f}% complete)")
                await asyncio.sleep(5)
            
            markdown_text = response.data.markdown
            
            structured_data = {}
            repair_needed = False
            
            # Use OpenAI to map the ADE markdown into the DocMind AI JSON schema
            if self.openai_parser and markdown_text:
                structured_data, repair_needed = await self.openai_parser.parse(
                    markdown_text=markdown_text,
                    extraction_prompt=extraction_prompt
                )
            
            
            return structured_data, repair_needed, markdown_text

        except Exception as e:
            logger.error("agentic_extraction_failed", error=str(e))
            raise ExtractionError(message=f"Landing AI extraction failed: {str(e)}")
            
        finally:
            # Clean up temporary file
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
