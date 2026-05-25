import json
from typing import Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from core.config import get_settings
from core.logging import get_logger
from services.common.json_repair import safe_parse_json

logger = get_logger("openai_parser")

class OpenAIParser:
    """
    Parses unstructured Markdown text (e.g., from Landing AI) into 
    the strictly structured JSON schema expected by DocMind AI.
    """

    def __init__(self, model_name: str = "gpt-4o-mini"):
        self.settings = get_settings()
        if not self.settings.openai_api_key:
            logger.warning("OpenAI API key is not set. OpenAIParser will fail.")
        
        self.llm = ChatOpenAI(
            model=model_name,
            api_key=self.settings.openai_api_key,
            temperature=0.0,
        )

    async def parse(self, markdown_text: str, extraction_prompt: str) -> tuple[dict[str, Any], bool]:
        """
        Takes raw markdown and an extraction prompt containing the JSON schema,
        and returns the parsed JSON dict and a boolean indicating if repair was needed.
        """
        try:
            logger.info("openai_parsing_starting", model=self.llm.model_name)
            
            system_prompt = (
                "You are an expert data extraction AI. "
                "You will be provided with raw extracted text/markdown from a document. "
                "Your task is to extract the requested fields and output ONLY a valid JSON object matching the provided schema. "
                "Do not include markdown code blocks around the JSON output, just the raw JSON."
            )
            
            user_prompt = f"""
            {extraction_prompt}
            
            --- RAW DOCUMENT TEXT ---
            {markdown_text}
            """

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            raw_response = response.content
            
            parsed, repair_needed = safe_parse_json(raw_response)
            
            logger.info("openai_parsing_complete", repair_needed=repair_needed)
            return parsed, repair_needed
            
        except Exception as e:
            logger.error("openai_parsing_failed", error=str(e))
            return {}, True
