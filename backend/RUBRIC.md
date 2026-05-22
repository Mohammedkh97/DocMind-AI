# Compliance Scoring Rubric

This document defines the deterministic compliance scoring rules used by DocMind AI.
Every deduction is traceable — no AI model generates the score.

## Scoring Philosophy

```
Score = 100 - sum(deductions)
Grade: A (90-100) | B (80-89) | C (70-79) | D (60-69) | F (<60)
```

The model is used **only** for extraction (finding data in the document).
The compliance **score** is computed by pure Python code executing this fixed ruleset.
Same extracted data → same rules → same deductions → same score. **Always.**

---

## Category Breakdown

| Category | Weight | Focus |
|----------|--------|-------|
| Document Completeness | 25% | Are all required fields present? |
| Mathematical Accuracy | 25% | Do the numbers add up correctly? |
| Cross-Document Consistency | 20% | Do invoice and packing list agree? |
| Regulatory Compliance | 20% | Valid HS codes, Incoterms, currency? |
| Data Quality | 10% | Zero values, low confidence, weight logic? |

---

## Rules

### Document Completeness

| Rule ID | Name | Severity | Max Deduction | What It Checks |
|---------|------|----------|---------------|----------------|
| COMP-001 | required_invoice_fields | Critical | 10 | Invoice number, date, currency, ports, grand total must be present |
| COMP-002 | required_packing_list_fields | Major | 5 | PL number, reference invoice, date must be present |
| COMP-003 | line_items_exist | Critical | 18 | Both documents must have at least one line item |
| COMP-005 | seller_buyer_info | Major | 10 | Seller and buyer names must be present |

### Mathematical Accuracy

| Rule ID | Name | Severity | Max Deduction | What It Checks |
|---------|------|----------|---------------|----------------|
| MATH-001 | line_item_calculations | Critical | 30 | qty × unit_price = amount for each line item |
| MATH-002 | subtotal_sum | Critical | 15 | Subtotal = sum of all line item amounts |
| MATH-003 | grand_total_calculation | Critical | 10 | Grand total = subtotal + freight + insurance |
| MATH-004 | packing_list_totals | Major | 15 | PL totals match sum of line item values |

### Cross-Document Consistency

| Rule ID | Name | Severity | Max Deduction | What It Checks |
|---------|------|----------|---------------|----------------|
| CROSS-001 | quantity_match | Major | 25 | Invoice and packing list quantities match |
| CROSS-003 | description_match | Minor | 6 | Item descriptions match across documents |
| CROSS-004 | unit_consistency | Major | 10 | Units are consistent (e.g., not LBS vs KG) |
| CROSS-005 | invoice_reference | Critical | 10 | PL references the correct invoice number |

### Regulatory Compliance

| Rule ID | Name | Severity | Max Deduction | What It Checks |
|---------|------|----------|---------------|----------------|
| REG-001 | hs_codes | Major | 30 | All items have valid 6-8 digit HS codes |
| REG-003 | incoterms | Minor | 5 | Incoterms are present and valid (FOB, CIF, etc.) |
| REG-005 | currency_declared | Major | 5 | Currency is explicitly stated |

### Data Quality

| Rule ID | Name | Severity | Max Deduction | What It Checks |
|---------|------|----------|---------------|----------------|
| DATA-001 | zero_values | Major | 8 | No zero unit price or amount on items with quantity |
| DATA-003 | low_confidence_fields | Warning | 0 | Flags fields with < 60% extraction confidence |
| DATA-005 | weight_consistency | Major | 6 | Gross weight ≥ net weight for all items |

---

## Severity Levels

| Severity | Deduction Range | Meaning |
|----------|----------------|---------|
| **Critical** | 5-15 pts | Must-fix issue that blocks customs clearance |
| **Major** | 3-8 pts | Significant problem requiring review |
| **Minor** | 1-3 pts | Cosmetic or informational inconsistency |
| **Warning** | 0 pts | Informational only (e.g., low confidence) |

---

## Deduction Caps

Each rule has a maximum deduction cap to prevent a single category from
dominating the score. For example, if there are 6 line items with
calculation errors at 5 points each (30 total), the cap limits the
deduction to the rule's max_deduction value.

---

## Adding New Rules

To add a compliance rule:

1. Define a pure function in `services/compliance/rules.py`:
   ```python
   def check_my_rule(data: ExtractionResponse) -> list[ComplianceIssue]:
       # Pure function — no model calls, no randomness
       ...
   ```

2. Register it in the `ALL_RULES` list with metadata.

3. Add it to this RUBRIC.md document.

The rule engine automatically picks up new entries in `ALL_RULES`.
