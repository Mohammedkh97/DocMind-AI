"""
Deterministic compliance scorer.

Takes the list of issues from rule evaluation and computes a final
score with full traceability. The scoring formula is simple and auditable:
  score = 100 - sum(deductions), clamped to [0, 100]

Grade boundaries: A(90+), B(80+), C(70+), D(60+), F(<60)
"""

from schemas.compliance import ComplianceResponse, ComplianceIssue, ComplianceCategorySummary
from core.logging import get_logger

logger = get_logger("compliance.scorer")

# Category weight allocations (for reporting, not score calculation)
CATEGORY_WEIGHTS = {
    "document_completeness": 25,
    "mathematical_accuracy": 25,
    "cross_document_consistency": 20,
    "regulatory_compliance": 20,
    "data_quality": 10,
}


def compute_grade(score: int) -> str:
    """Map numeric score to letter grade."""
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 60:
        return "D"
    else:
        return "F"


def compute_compliance_score(
    issues: list[ComplianceIssue],
    rules_evaluated: int,
) -> ComplianceResponse:
    """
    Compute the deterministic compliance score.

    Formula: score = 100 - sum(all deductions), clamped to [0, 100]

    This is a PURE FUNCTION: same issues → same score. No model, no
    randomness, no external state.
    """
    # Sum all deductions
    total_deduction = sum(issue.deduction for issue in issues)

    # Clamp score
    score = max(0, min(100, 100 - total_deduction))

    # Grade
    grade = compute_grade(score)

    # Count by severity
    critical_count = sum(1 for i in issues if i.severity == "critical")
    major_count = sum(1 for i in issues if i.severity == "major")
    minor_count = sum(1 for i in issues if i.severity == "minor")
    warning_count = sum(1 for i in issues if i.severity == "warning")

    # Build category summaries
    category_summaries = []
    for category, max_points in CATEGORY_WEIGHTS.items():
        cat_issues = [i for i in issues if i.category == category]
        cat_deductions = sum(i.deduction for i in cat_issues)
        category_summaries.append(ComplianceCategorySummary(
            category=category,
            max_score=max_points,
            score=max(0, max_points - cat_deductions),
            issues_found=len(cat_issues),
            deductions=cat_deductions,
        ))

    # Build summary text
    summary = _build_summary(score, grade, issues, critical_count, major_count)

    logger.info(
        "compliance_score_computed",
        score=score,
        grade=grade,
        total_issues=len(issues),
        critical=critical_count,
        major=major_count,
        total_deduction=total_deduction,
    )

    return ComplianceResponse(
        score=score,
        grade=grade,
        total_issues=len(issues),
        critical_issues=critical_count,
        major_issues=major_count,
        minor_issues=minor_count,
        warnings=warning_count,
        issues=issues,
        category_summary=category_summaries,
        rules_evaluated=rules_evaluated,
        summary=summary,
    )


def _build_summary(
    score: int,
    grade: str,
    issues: list[ComplianceIssue],
    critical_count: int,
    major_count: int,
) -> str:
    """Build a human-readable compliance summary."""
    parts = [f"Document scored {score}/100 (Grade: {grade})."]

    if critical_count > 0:
        critical_descriptions = [
            i.description for i in issues if i.severity == "critical"
        ]
        parts.append(
            f"{critical_count} critical issue(s) found requiring immediate attention: "
            + "; ".join(critical_descriptions[:3])  # Cap at 3 for readability
        )

    if major_count > 0:
        parts.append(f"{major_count} major issue(s) found that should be reviewed.")

    if not issues:
        parts.append("No compliance issues detected.")

    return " ".join(parts)
