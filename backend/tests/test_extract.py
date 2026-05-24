import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import app
from schemas.extraction import ExtractionResponse, InvoiceData, PackingListData
from schemas.common import ProcessingMetadata

client = TestClient(app)

def test_extract_endpoint_no_file():
    """Test that missing file results in a validation error."""
    response = client.post("/extract")
    assert response.status_code == 422

def test_extract_endpoint_invalid_extension():
    """Test that non-PDF files are rejected."""
    response = client.post(
        "/extract",
        files={"file": ("test.txt", b"dummy content", "text/plain")}
    )
    assert response.status_code == 422
    assert "Only PDF files are supported" in response.text

@patch("api.routers.extract.ExtractionOrchestrator")
def test_extract_endpoint_success(mock_orchestrator_class):
    """Test successful extraction with a mocked orchestrator."""
    mock_orchestrator = MagicMock()
    mock_orchestrator_class.return_value = mock_orchestrator
    
    # Create a dummy ExtractionResponse
    dummy_response = ExtractionResponse(
        invoice=InvoiceData(),
        packing_list=PackingListData(),
        metadata=ProcessingMetadata(
            processing_time_seconds=1.0,
            primary_model="test-model",
            fallback_used=False,
            ocr_validation_used=False,
            pages_processed=1,
            json_repair_applied=False,
            warnings=[]
        )
    )
    
    # Mock the async extract method
    async def mock_extract(*args, **kwargs):
        return dummy_response
        
    mock_orchestrator.extract = mock_extract

    # Provide a valid dummy PDF file
    response = client.post(
        "/extract",
        files={"file": ("test.pdf", b"%PDF-1.4 dummy content", "application/pdf")}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "invoice" in data
    assert "packing_list" in data
    assert "metadata" in data
