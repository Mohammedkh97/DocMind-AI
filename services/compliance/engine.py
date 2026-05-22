"""
Compliance engine — orchestrates rule evaluation and scoring.

Design: The engine iterates over ALL registered rules, evaluates each
against the extracted data, collects all issues, and passes them to
the scorer. The model is NEVER involved in scoring — only in the
upstream extraction.
"""

from schemas.extraction import ExtractionResponse
from schemas.compliance import ComplianceResponse, ComplianceIssue
from services.compliance.rules import ALL_RULES
from services.compliance.scorer import compute_compliance_score
from core.logging import get_logger
from core.exceptions import ComplianceError, RuleEvaluationError

logger = get_logger("compliance.engine")


class ComplianceEngine:
    """
    Evaluates extracted document data against compliance rules
    and produces a deterministic score.

    The engine guarantees:
    - Same input → same output (deterministic)
    - Every deduction is traceable to a specific rule
    - No model/AI is used for scoring
    - All rules are evaluated (no short-circuit)
    """

    def __init__(self):
        self.rules = ALL_RULES

    def evaluate(self, extracted_data: ExtractionResponse) -> ComplianceResponse:
        """
        Run all compliance rules and compute the final score.

        Args:
            extracted_data: The structured extraction from /extract

        Returns:
            ComplianceResponse with score, grade, and detailed issues
        """
        all_issues: list[ComplianceIssue] = []
        rules_evaluated = 0

        for rule in self.rules:
            try:
                logger.debug("evaluating_rule", rule_id=rule.rule_id, rule_name=rule.rule_name)
                issues = rule.evaluate(extracted_data)

                # Apply max deduction cap per rule
                rule_total_deduction = sum(i.deduction for i in issues)
                if rule_total_deduction > rule.max_deduction:
                    # Scale down deductions proportionally to stay within cap
                    scale_factor = rule.max_deduction / rule_total_deduction
                    for issue in issues:
                        issue.deduction = max(1, int(issue.deduction * scale_factor))

                all_issues.extend(issues)
                rules_evaluated += 1

                if issues:
                    logger.info(
                        "rule_triggered",
                        rule_id=rule.rule_id,
                        issues_found=len(issues),
                        total_deduction=sum(i.deduction for i in issues),
                    )

            except Exception as e:
                logger.error(
                    "rule_evaluation_failed",
                    rule_id=rule.rule_id,
                    error=str(e),
                )
                # Don't let one broken rule crash the entire scoring
                # Log the error but continue evaluating other rules
                all_issues.append(ComplianceIssue(
                    rule_id=rule.rule_id,
                    rule_name=rule.rule_name,
                    field="system",
                    severity="warning",
                    category=rule.category,
                    found=f"Rule evaluation error: {str(e)}",
                    expected="Successful rule evaluation",
                    deduction=0,
                    description=f"Rule {rule.rule_id} could not be evaluated: {str(e)}",
                ))
                rules_evaluated += 1

        # Sort issues: critical first, then by deduction (highest first)
        severity_order = {"critical": 0, "major": 1, "minor": 2, "warning": 3}
        all_issues.sort(
            key=lambda i: (severity_order.get(i.severity, 4), -i.deduction)
        )

        # Compute deterministic score
        result = compute_compliance_score(
            issues=all_issues,
            rules_evaluated=rules_evaluated,
        )

        logger.info(
            "compliance_evaluation_complete",
            score=result.score,
            grade=result.grade,
            total_issues=result.total_issues,
            rules_evaluated=rules_evaluated,
        )

        return result
