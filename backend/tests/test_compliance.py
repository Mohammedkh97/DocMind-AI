import pytest
from fastapi.testclient import TestClient

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import app

client = TestClient(app)

def test_compliance_score_endpoint():
    """Test that the compliance score endpoint correctly processes extraction data."""
    # Construct a minimal ExtractionResponse payload matching the Pydantic schema
    payload = {
        "invoice": {
            "invoice_number": {"value": "INV-123", "confidence": 0.99},
            "subtotal": {"value": 100.0, "confidence": 0.9},
            "line_items": [
                {
                    "item_no": {"value": 1, "confidence": 1.0},
                    "description": {"value": "Test Item", "confidence": 1.0},
                    "quantity": {"value": 2.0, "confidence": 1.0},
                    "unit_price": {"value": 50.0, "confidence": 1.0},
                    "amount": {"value": 100.0, "confidence": 1.0}
                }
            ]
        },
        "packing_list": {},
        "metadata": {
            "processing_time_seconds": 1.0,
            "primary_model": "test-model",
            "fallback_used": False,
            "ocr_validation_used": False,
            "pages_processed": 1,
            "json_repair_applied": False,
            "warnings": []
        }
    }

    response = client.post("/compliance-score", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    
    # Assert expected compliance response structure
    assert "score" in data
    assert "grade" in data
    assert "total_issues" in data
    assert "issues" in data
    assert "summary" in data

def test_compliance_score_invalid_payload():
    """Test that invalid payload structure returns 422 Validation Error."""
    # Missing required metadata field according to schemas
    payload = {
        "invoice": {}
    }
    
    response = client.post("/compliance-score", json=payload)
    assert response.status_code == 422
