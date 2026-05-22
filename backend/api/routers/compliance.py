"""
POST /compliance-score endpoint.

Accepts extracted JSON data (from /extract) and returns a deterministic
compliance score with full issue breakdown.
"""

from fastapi import APIRouter

from core.logging import get_logger
from schemas.extraction import ExtractionResponse
from schemas.compliance import ComplianceResponse
from services.compliance.engine import ComplianceEngine

router = APIRouter()
logger = get_logger("api.compliance")


@router.post(
    "/compliance-score",
    response_model=ComplianceResponse,
    summary="Score extracted data for customs compliance",
    description=(
        "Takes the structured JSON output from /extract and evaluates it "
        "against a deterministic set of compliance rules. Returns a score "
        "from 0-100 with a detailed breakdown of all issues found. "
        "The score is deterministic: same input = same output."
    ),
    responses={
        200: {"description": "Compliance score with detailed issue breakdown"},
        422: {"description": "Invalid input data structure"},
        500: {"description": "Compliance engine error"},
    },
)
async def score_compliance(extracted: ExtractionResponse):
    """
    Evaluate extracted document data for customs compliance.

    The scoring process:
    1. Receives structured extraction data (output of /extract)
    2. Evaluates against all registered compliance rules
    3. Computes a deterministic weighted score
    4. Returns detailed issue breakdown with full traceability

    DETERMINISM GUARANTEE:
    The same extracted data will always produce the same score.
    The model is NOT used for scoring — only pure Python rules.
    """
    logger.info(
        "compliance_scoring_requested",
        invoice_items=len(extracted.invoice.line_items),
        packing_list_items=len(extracted.packing_list.line_items),
    )

    engine = ComplianceEngine()
    result = engine.evaluate(extracted)

    logger.info(
        "compliance_scoring_complete",
        score=result.score,
        grade=result.grade,
        issues=result.total_issues,
    )

    return result
