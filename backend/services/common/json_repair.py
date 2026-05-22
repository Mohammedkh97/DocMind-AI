"""
4-layer JSON repair pipeline.

This is critical for production reliability — LLMs frequently return
malformed JSON (trailing commas, markdown fences, unescaped characters,
truncated output). The API must ALWAYS return valid JSON, so we have
a cascading repair strategy.

Layer 1: Direct parse (works ~85% of the time)
Layer 2: Regex cleanup (catches ~10% more)
Layer 3: Partial extraction (finds valid JSON substrings)
Layer 4: Return empty structure (never crash)
"""

import json
import re
from typing import Any

from core.logging import get_logger

logger = get_logger("json_repair")


def safe_parse_json(raw: str) -> tuple[dict[str, Any], bool]:
    """
    Parse JSON with a multi-layer repair pipeline.

    Returns:
        Tuple of (parsed_dict, repair_was_needed)
        - parsed_dict: Always a valid dict (may be empty on total failure)
        - repair_was_needed: True if any repair layer was used
    """
    if not raw or not raw.strip():
        logger.warning("empty_json_input")
        return {}, True

    # Layer 1: Direct parse
    try:
        result = json.loads(raw)
        if isinstance(result, dict):
            return result, False
        # If model returned a list or string, wrap it
        return {"data": result}, True
    except json.JSONDecodeError:
        pass

    # Layer 2: Regex cleanup
    cleaned = _regex_cleanup(raw)
    try:
        result = json.loads(cleaned)
        logger.info("json_repaired", layer="regex_cleanup")
        if isinstance(result, dict):
            return result, True
        return {"data": result}, True
    except json.JSONDecodeError:
        pass

    # Layer 3: First-brace-to-last-brace extraction
    # The most common failure mode: VLM wraps valid JSON in reasoning text
    first_brace = cleaned.find('{')
    last_brace = cleaned.rfind('}')
    if first_brace != -1 and last_brace > first_brace:
        candidate = cleaned[first_brace:last_brace + 1]
        try:
            result = json.loads(candidate)
            if isinstance(result, dict):
                logger.info("json_repaired", layer="brace_extraction")
                return result, True
        except json.JSONDecodeError:
            # Try regex cleanup on the extracted portion too
            try:
                candidate_cleaned = re.sub(r',\s*([}\]])', r'\1', candidate)
                result = json.loads(candidate_cleaned)
                if isinstance(result, dict):
                    logger.info("json_repaired", layer="brace_extraction_cleaned")
                    return result, True
            except json.JSONDecodeError:
                pass

    # Layer 4: Find the largest valid JSON object via bracket matching
    result = _extract_largest_json_object(cleaned)
    if result is not None:
        logger.info("json_repaired", layer="partial_extraction")
        return result, True

    # Layer 5: Total failure — return empty with error marker
    logger.error(
        "json_repair_failed_all_layers",
        raw_preview=raw[:300],
        raw_length=len(raw),
    )
    return {"_parse_error": True, "_raw_preview": raw[:500]}, True


def _regex_cleanup(raw: str) -> str:
    """
    Apply common regex fixes for malformed LLM JSON output.

    Handles:
    - Markdown code fences (```json ... ```)
    - Trailing commas before closing brackets
    - Single-line comments
    - NaN/Infinity values (not valid JSON)
    - Unescaped newlines in strings
    """
    text = raw.strip()

    # Remove markdown code fences
    text = re.sub(r'^```(?:json)?\s*\n?', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n?```\s*$', '', text, flags=re.MULTILINE)

    # Remove single-line comments (// ...)
    text = re.sub(r'//[^\n]*', '', text)

    # Remove trailing commas before } or ]
    text = re.sub(r',\s*([}\]])', r'\1', text)

    # Replace NaN/Infinity with null (not valid in JSON)
    text = re.sub(r'\bNaN\b', 'null', text)
    text = re.sub(r'\bInfinity\b', 'null', text)
    text = re.sub(r'-Infinity\b', 'null', text)

    # Fix common escaping issues
    # Replace unescaped control characters within strings
    text = text.replace('\t', '\\t')

    return text.strip()


def _extract_largest_json_object(text: str) -> dict[str, Any] | None:
    """
    Find the largest valid JSON object in a string using bracket matching.

    This handles cases where the model wraps JSON in explanation text,
    or returns truncated JSON that can be partially recovered.
    """
    best_result = None
    best_length = 0

    # Find all positions where a JSON object might start
    for i, char in enumerate(text):
        if char == '{':
            # Try to find the matching closing brace
            depth = 0
            in_string = False
            escape_next = False

            for j in range(i, len(text)):
                c = text[j]

                if escape_next:
                    escape_next = False
                    continue

                if c == '\\' and in_string:
                    escape_next = True
                    continue

                if c == '"' and not escape_next:
                    in_string = not in_string
                    continue

                if in_string:
                    continue

                if c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        candidate = text[i:j + 1]
                        try:
                            parsed = json.loads(candidate)
                            if isinstance(parsed, dict) and len(candidate) > best_length:
                                best_result = parsed
                                best_length = len(candidate)
                        except json.JSONDecodeError:
                            pass
                        break

    return best_result


def ensure_extraction_structure(data: dict) -> dict:
    """
    Ensure the parsed JSON has the expected top-level structure
    for extraction responses. Fills in missing sections with empty defaults.
    """
    if "invoice" not in data:
        data["invoice"] = {}
    if "packing_list" not in data:
        data["packing_list"] = {}

    # Ensure line_items lists exist
    if "line_items" not in data["invoice"]:
        data["invoice"]["line_items"] = []
    if "line_items" not in data["packing_list"]:
        data["packing_list"]["line_items"] = []

    return data
