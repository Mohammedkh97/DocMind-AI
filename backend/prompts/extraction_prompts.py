"""
Prompt templates for document extraction.

Design principles:
- Extremely specific field-by-field instructions (reduces hallucination)
- JSON schema embedded in the prompt (constrains output format)
- Confidence self-assessment requested per field
- Instructions for handling unreadable/missing fields explicitly
- No hardcoded values — prompts are generalizable to unseen documents
"""

INVOICE_EXTRACTION_PROMPT = """You are a document extraction specialist. Extract ALL fields from this commercial invoice image into structured JSON.

CRITICAL RULES:
1. Extract EXACTLY what you see in the document — never guess or fabricate values.
2. For EVERY field, provide a confidence score from 0.0 to 1.0 based on how clearly readable the value is.
3. If a field is blurry, partially obscured, or unreadable, still provide your best guess but set confidence LOW (below 0.5).
4. If a field is completely unreadable or missing, set "value" to null and confidence to 0.0.
5. For numerical values, extract the exact number (no currency symbols in numeric fields).
6. For dates, extract in the format shown in the document.
7. Extract ALL line items from the table — do not skip any rows.

8. Include a full, pure text transcription of the document formatted nicely in markdown under the 'markdown_transcription' key.

Return a JSON object with this EXACT structure:
{
  "markdown_transcription": "The full text of the document transcribed exactly as seen, formatted in markdown",
  "structured_data": {
    "invoice_number": {"value": "string or null", "confidence": 0.0},
  "invoice_date": {"value": "string or null", "confidence": 0.0},
  "payment_terms": {"value": "string or null", "confidence": 0.0},
  "currency": {"value": "string or null", "confidence": 0.0},
  "port_of_loading": {"value": "string or null", "confidence": 0.0},
  "port_of_discharge": {"value": "string or null", "confidence": 0.0},
  "incoterms": {"value": "string or null", "confidence": 0.0},
  "lc_number": {"value": "string or null", "confidence": 0.0},
  "seller": {
    "name": {"value": "string or null", "confidence": 0.0},
    "address": {"value": "full address string or null", "confidence": 0.0},
    "phone": {"value": "string or null", "confidence": 0.0},
    "vat_number": {"value": "string or null", "confidence": 0.0}
  },
  "buyer": {
    "name": {"value": "string or null", "confidence": 0.0},
    "address": {"value": "full address string or null", "confidence": 0.0},
    "phone": {"value": "string or null", "confidence": 0.0},
    "trn": {"value": "string or null", "confidence": 0.0}
  },
  "line_items": [
    {
      "item_no": {"value": 1, "confidence": 0.0},
      "description": {"value": "string", "confidence": 0.0},
      "hs_code": {"value": "string", "confidence": 0.0},
      "quantity": {"value": 0.0, "confidence": 0.0},
      "unit": {"value": "string", "confidence": 0.0},
      "unit_price": {"value": 0.0, "confidence": 0.0},
      "amount": {"value": 0.0, "confidence": 0.0}
    }
  ],
  "subtotal": {"value": 0.0, "confidence": 0.0},
  "freight": {"value": 0.0, "confidence": 0.0},
  "insurance": {"value": 0.0, "confidence": 0.0},
  "grand_total": {"value": 0.0, "confidence": 0.0},
  "bank_details": {
    "bank_name": {"value": "string or null", "confidence": 0.0},
    "account_name": {"value": "string or null", "confidence": 0.0},
    "account_number": {"value": "string or null", "confidence": 0.0},
    "swift_code": {"value": "string or null", "confidence": 0.0},
    "iban": {"value": "string or null", "confidence": 0.0}
  },
  "shipment": {
    "vessel_name": {"value": "string or null", "confidence": 0.0},
    "port_of_loading": {"value": "string or null", "confidence": 0.0},
    "etd": {"value": "string or null", "confidence": 0.0}
  }
}
}

Return ONLY the JSON object. No explanations, no markdown fences, no extra text."""


PACKING_LIST_EXTRACTION_PROMPT = """You are a document extraction specialist. Extract ALL fields from this packing list image into structured JSON.

CRITICAL RULES:
1. Extract EXACTLY what you see in the document — never guess or fabricate values.
2. For EVERY field, provide a confidence score from 0.0 to 1.0 based on how clearly readable the value is.
3. If a field is blurry, partially obscured, or unreadable, still provide your best guess but set confidence LOW (below 0.5).
4. If a field is completely unreadable or missing, set "value" to null and confidence to 0.0.
5. For numerical values, extract the exact number.
6. Extract ALL line items from the table — do not skip any rows.
7. Weights should be in KG as shown in the document.

8. Include a full, pure text transcription of the document formatted nicely in markdown under the 'markdown_transcription' key.

Return a JSON object with this EXACT structure:
{
  "markdown_transcription": "The full text of the document transcribed exactly as seen, formatted in markdown",
  "structured_data": {
    "packing_list_number": {"value": "string or null", "confidence": 0.0},
  "ref_invoice": {"value": "string or null", "confidence": 0.0},
  "date": {"value": "string or null", "confidence": 0.0},
  "line_items": [
    {
      "item_no": {"value": 1, "confidence": 0.0},
      "description": {"value": "string", "confidence": 0.0},
      "cartons": {"value": 0, "confidence": 0.0},
      "quantity": {"value": 0.0, "confidence": 0.0},
      "unit": {"value": "string", "confidence": 0.0},
      "net_weight_kg": {"value": 0.0, "confidence": 0.0},
      "gross_weight_kg": {"value": 0.0, "confidence": 0.0}
    }
  ],
  "total_cartons": {"value": 0, "confidence": 0.0},
  "total_net_weight": {"value": 0.0, "confidence": 0.0},
  "total_gross_weight": {"value": 0.0, "confidence": 0.0}
}
}

Return ONLY the JSON object. No explanations, no markdown fences, no extra text."""


PAGE_CLASSIFICATION_PROMPT = """Look at this document image and classify it.

Return ONLY one of these exact strings:
- "commercial_invoice" — if this is a commercial invoice
- "packing_list" — if this is a packing list
- "bill_of_lading" — if this is a bill of lading
- "unknown" — if you cannot determine the document type

Return ONLY the classification string, nothing else."""
