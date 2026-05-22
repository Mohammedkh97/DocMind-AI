"""
Pydantic models for the /compliance-score endpoint.

The compliance response is designed for full traceability — every point
deducted can be traced back to a specific rule, field, found value, and
expected value. This is critical for customs compliance where auditors
need to understand exactly why a document was flagged.
"""

from typing import Literal
from pydantic import BaseModel, Field


class ComplianceIssue(BaseModel):
    """
    A single compliance issue found during scoring.

    Each issue is fully traceable: which rule fired, what was found,
    what was expected, and how many points were deducted.
    """
    rule_id: str = Field(description="Unique rule identifier (e.g., MATH-001)")
    rule_name: str = Field(description="Human-readable rule name")
    field: str = Field(description="Dot-path to the field (e.g., invoice.line_items[3].unit_price)")
    severity: Literal["critical", "major", "minor", "warning"] = Field(
        description="Issue severity level"
    )
    category: str = Field(description="Rule category (e.g., mathematical_accuracy)")
    found: str | None = Field(
        default=None,
        description="The actual value found in the document"
    )
    expected: str | None = Field(
        default=None,
        description="What the value should be or the rule expectation"
    )
    deduction: int = Field(
        ge=0,
        description="Points deducted for this issue"
    )
    description: str = Field(description="Human-readable explanation of the issue")


class ComplianceCategorySummary(BaseModel):
    """Summary of issues within a compliance category."""
    category: str
    max_score: int
    score: int
    issues_found: int
    deductions: int


class ComplianceResponse(BaseModel):
    """
    Complete response from the /compliance-score endpoint.

    The score is deterministic: same extracted data → same rules →
    same deductions → same score. The model is never used to generate
    the score directly.
    """
    score: int = Field(
        ge=0, le=100,
        description="Overall compliance score (0-100)"
    )
    grade: str = Field(
        description="Letter grade: A (90-100), B (80-89), C (70-79), D (60-69), F (<60)"
    )
    total_issues: int = Field(description="Total number of issues found")
    critical_issues: int = Field(description="Number of critical severity issues")
    major_issues: int = Field(description="Number of major severity issues")
    minor_issues: int = Field(description="Number of minor severity issues")
    warnings: int = Field(description="Number of warnings (no deduction)")
    issues: list[ComplianceIssue] = Field(
        default_factory=list,
        description="Detailed list of all issues found"
    )
    category_summary: list[ComplianceCategorySummary] = Field(
        default_factory=list,
        description="Score breakdown by category"
    )
    rules_evaluated: int = Field(description="Total number of rules evaluated")
    summary: str = Field(description="Human-readable summary of compliance findings")
