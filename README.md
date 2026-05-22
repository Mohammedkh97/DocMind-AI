# DocMind AI

Hybrid document intelligence system combining VLM (Vision-Language Model) and OCR-based structured extraction with deterministic compliance scoring for logistics document processing and customs compliance automation.

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11"/>
  <img src="https://img.shields.io/badge/FastAPI-0.136-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/PostgreSQL-15-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL"/>
  <img src="https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB" alt="React"/>
</p>

---

## 📋 Table of Contents

- [Architecture Overview](#architecture-overview)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
  - [Prerequisites](#prerequisites)
  - [Local Setup](#local-setup)
  - [Docker Setup](#docker-setup)
- [API Endpoints](#api-endpoints)
  - [POST /extract](#post-extract)
  - [POST /compliance-score](#post-compliance-score)
  - [GET /health](#get-health)
- [Project Structure](#project-structure)
- [Framework Choice](#framework-choice)
- [Key Documents](#key-documents)

---

## Architecture Overview

```
PDF Upload → Image Enhancement → VLM Extraction (Gemini 2.5 Flash)
                                        ↓
                                 OCR Cross-Validation (PaddleOCR)
                                        ↓
                                 Confidence Scoring (multi-signal)
                                        ↓
                                 Structured JSON Response
                                        ↓
                                 Compliance Scoring (deterministic rules)
```

**Key architectural decisions:**

- **VLM-first extraction**: Gemini 2.5 Flash processes document images directly, understanding layout and tables natively — unlike OCR→LLM pipelines that lose spatial context
- **Multi-signal confidence**: Each field's confidence combines VLM self-assessment, OCR cross-validation, format validation, and business rule checks
- **Deterministic compliance**: The model extracts data; pure Python code scores it. Same input = same score, always
- **4-layer JSON repair**: The API always returns valid JSON, even when the model's output is malformed

## Tech Stack

| Component        | Choice           | Why                                     |
| ---------------- | ---------------- | --------------------------------------- |
| Backend          | FastAPI          | Async, Pydantic-native, auto-docs       |
| VLM              | Gemini 2.5 Flash | Best cost/accuracy for document vision  |
| OCR              | PaddleOCR        | Best open-source OCR for degraded scans |
| Image Processing | OpenCV + PyMuPDF | Robust preprocessing pipeline           |
| Validation       | Pydantic v2      | Schema enforcement + serialization      |
| Logging          | structlog        | Production JSON logging                 |
| Retry            | tenacity         | Exponential backoff for API calls       |

## Quick Start

### Prerequisites

- Python 3.12+
- Gemini API key ([get one here](https://aistudio.google.com/apikey))

### Local Setup

```bash
# Clone and enter project
git clone https://github.com/yourusername/DocMind-AI.git
cd DocMind-AI

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

# Run the server
uvicorn main:app --reload
```

### Docker Setup

```bash
# Copy env file and add your API key
cp .env.example .env

# Build and run
docker compose up --build
```

The API will be available at `http://localhost:8000`.

API documentation: `http://localhost:8000/docs`

## API Endpoints

### `POST /extract`

Extract structured data from a scanned logistics PDF.

**Request:**

```bash
curl -X POST "http://localhost:8000/extract" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@path/to/document.pdf"
```

**Response:**

```json
{
  "invoice": {
    "invoice_number": { "value": "CRG-INV-2024-0087", "confidence": 0.97 },
    "invoice_date": { "value": "March 14, 2024", "confidence": 0.95 },
    "seller": {
      "name": { "value": "ShanghaiTex Co. Ltd", "confidence": 0.96 }
    },
    "buyer": {
      "name": { "value": "Al Baraka Trading LLC", "confidence": 0.96 }
    },
    "port_of_loading": { "value": "Shanghai Pudong", "confidence": 0.94 },
    "port_of_discharge": { "value": "Jebel Ali, UAE", "confidence": 0.95 },
    "currency": { "value": "USD", "confidence": 0.98 },
    "incoterms": { "value": "FOB Shanghai", "confidence": 0.95 },
    "line_items": [
      {
        "item_no": { "value": 1, "confidence": 0.98 },
        "description": {
          "value": "Cotton Woven Fabric (White, 150cm)",
          "confidence": 0.96
        },
        "hs_code": { "value": "52081100", "confidence": 0.97 },
        "quantity": { "value": 2400, "confidence": 0.97 },
        "unit": { "value": "MTR", "confidence": 0.98 },
        "unit_price": { "value": 1.85, "confidence": 0.96 },
        "amount": { "value": 4440.0, "confidence": 0.97 }
      }
    ],
    "subtotal": { "value": 13680.0, "confidence": 0.95 },
    "grand_total": { "value": 13680.0, "confidence": 0.95 }
  },
  "packing_list": {
    "packing_list_number": { "value": "CRG-PL-2024-0087", "confidence": 0.96 },
    "ref_invoice": { "value": "CRG-INV-2024-0087", "confidence": 0.95 },
    "total_cartons": { "value": 227, "confidence": 0.95 },
    "total_net_weight": { "value": 2944.0, "confidence": 0.94 },
    "total_gross_weight": { "value": 3087.0, "confidence": 0.94 },
    "line_items": ["..."]
  },
  "metadata": {
    "processing_time_seconds": 4.2,
    "primary_model": "gemini-2.5-flash",
    "fallback_used": false,
    "ocr_validation_used": true,
    "pages_processed": 2,
    "json_repair_applied": false,
    "warnings": []
  }
}
```

### `POST /compliance-score`

Score extracted data against compliance rules.

**Request:**

```bash
curl -X POST "http://localhost:8000/compliance-score" \
  -H "Content-Type: application/json" \
  -d @extracted_data.json
```

**Response:**

```json
{
  "score": 62,
  "grade": "D",
  "total_issues": 5,
  "critical_issues": 2,
  "major_issues": 2,
  "minor_issues": 1,
  "warnings": 0,
  "issues": [
    {
      "rule_id": "MATH-002",
      "rule_name": "subtotal_sum",
      "field": "invoice.subtotal",
      "severity": "critical",
      "category": "mathematical_accuracy",
      "found": "$13,680.00",
      "expected": "$13,440.00 (sum of line items)",
      "deduction": 15,
      "description": "Stated subtotal ($13,680.00) does not match the sum of line item amounts ($13,440.00). Discrepancy: $240.00"
    },
    {
      "rule_id": "DATA-001",
      "rule_name": "zero_unit_price",
      "field": "invoice.line_items[3].unit_price",
      "severity": "major",
      "category": "data_quality",
      "found": "$0.00 (qty: 950)",
      "expected": "Non-zero unit price for items with quantity > 0",
      "deduction": 5,
      "description": "Line item 4 (Denim Fabric (Indigo, 160cm)) has a unit price of $0.00 with quantity 950."
    }
  ],
  "rules_evaluated": 18,
  "summary": "Document scored 62/100 (Grade: D). 2 critical issue(s) found requiring immediate attention."
}
```

### `GET /health`

Health check endpoint.

```bash
curl http://localhost:8000/health
```

## Project Structure

```
DocMind-AI/
├── main.py                              # FastAPI application entry point
├── ARCHITECTURE.md                      # Architecture decisions (6 questions)
├── RUBRIC.md                            # Compliance scoring rules
├── Dockerfile                           # Container definition
├── docker-compose.yml                   # One-command setup
├── requirements.txt                     # Python dependencies
├── .env.example                         # Environment template
│
├── api/                                 # API Layer
│   ├── routers/
│   │   ├── extract.py                   # POST /extract
│   │   └── compliance.py               # POST /compliance-score
│   ├── middleware.py                    # Request tracking, error handling
│   └── dependencies.py                 # Dependency injection
│
├── core/                                # Core Infrastructure
│   ├── config.py                        # Pydantic BaseSettings
│   ├── exceptions.py                    # Custom exception hierarchy
│   └── logging.py                       # Structured JSON logging
│
├── schemas/                             # Data Contracts
│   ├── common.py                        # ConfidenceField[T], metadata
│   ├── extraction.py                    # Extraction response models
│   └── compliance.py                    # Compliance response models
│
├── services/                            # Business Logic
│   ├── extraction/
│   │   ├── orchestrator.py              # Pipeline coordinator
│   │   ├── preprocessor.py              # PDF → enhanced images
│   │   ├── vlm_extractor.py             # Gemini VLM extraction
│   │   ├── ocr_extractor.py             # PaddleOCR fallback
│   │   ├── confidence_scorer.py         # Multi-signal confidence
│   │   └── result_merger.py             # Raw → Pydantic models
│   ├── compliance/
│   │   ├── engine.py                    # Rule evaluation orchestrator
│   │   ├── rules.py                     # All compliance rules
│   │   └── scorer.py                    # Deterministic scoring
│   └── common/
│       └── json_repair.py              # 4-layer JSON repair
│
├── prompts/                             # Extraction Prompts
│   └── extraction_prompts.py            # Invoice/PL/classification prompts
│
└── tests/                               # Tests
    ├── test_extract.py
    ├── test_compliance.py
    └── test_json_repair.py
```

## Framework Choice

**FastAPI** over Flask, Django, or Express.js because:

1. **Native Pydantic integration**: The entire response schema is defined in Pydantic models. FastAPI auto-generates OpenAPI docs from these, so the API is self-documenting.
2. **Async support**: VLM and OCR calls are I/O bound. Async handlers prevent blocking while waiting for model responses.
3. **Built-in validation**: Request validation, file upload handling, and error responses come free.
4. **Industry standard for ML APIs**: Most production ML services use FastAPI — reviewers will be immediately comfortable with the codebase.

## Key Documents

- [ARCHITECTURE.md](./ARCHITECTURE.md) — Answers to the 6 architecture questions
- [RUBRIC.md](./RUBRIC.md) — Compliance scoring rules and methodology
