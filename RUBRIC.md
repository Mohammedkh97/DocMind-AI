# Compliance Scoring Rubric

The DocMind AI Compliance Engine evaluates extracted document data against a deterministic set of business rules. The scoring starts at 100 points, and deductions are applied for every failed rule, up to a category's maximum weight.

## Grading Scale

- **A**: 90 - 100
- **B**: 80 - 89
- **C**: 70 - 79
- **D**: 60 - 69
- **F**: < 60

## Scoring Philosophy

```
Score = 100 - sum(deductions)
```

---

## 1. Document Completeness (25% Weight)

Ensures that all critical header and structural information is present across the documents.

| Rule ID      | Rule Name                      | Description                                                                                      | Severity | Max Deduction |
| ------------ | ------------------------------ | ------------------------------------------------------------------------------------------------ | -------- | ------------- |
| **COMP-001** | `required_invoice_fields`      | All critical invoice fields must be present (invoice number, date, currency, ports, total).      | Critical | 10 pts        |
| **COMP-002** | `required_packing_list_fields` | All critical packing list fields must be present (packing list number, reference invoice, date). | Major    | 5 pts         |
| **COMP-003** | `line_items_exist`             | Both documents must contain at least one line item.                                              | Critical | 18 pts        |
| **COMP-005** | `seller_buyer_info`            | Seller and buyer information must be present on the invoice.                                     | Major    | 10 pts        |

---

## 2. Mathematical Accuracy (25% Weight)

Validates all arithmetic across the documents. Discrepancies here often indicate fraud or severe data entry errors.

| Rule ID      | Rule Name                 | Description                                                                              | Severity | Max Deduction |
| ------------ | ------------------------- | ---------------------------------------------------------------------------------------- | -------- | ------------- |
| **MATH-001** | `line_item_calculations`  | Line item amounts must equal `quantity × unit_price`.                                    | Critical | 30 pts        |
| **MATH-002** | `subtotal_sum`            | Subtotal must exactly equal the sum of all individual line item amounts.                 | Critical | 15 pts        |
| **MATH-003** | `grand_total_calculation` | Grand total must equal `subtotal + freight + insurance`.                                 | Critical | 10 pts        |
| **MATH-004** | `packing_list_totals`     | Packing list total weight and cartons must match the sum of their respective line items. | Major    | 15 pts        |

---

## 3. Cross-Document Consistency (20% Weight)

Ensures that the Commercial Invoice and the Packing List are describing the exact same shipment.

| Rule ID       | Rule Name           | Description                                                                            | Severity | Max Deduction |
| ------------- | ------------------- | -------------------------------------------------------------------------------------- | -------- | ------------- |
| **CROSS-001** | `quantity_match`    | Quantities for corresponding items must match between the invoice and packing list.    | Major    | 25 pts        |
| **CROSS-003** | `description_match` | Descriptions for corresponding items must be semantically similar between documents.   | Minor    | 6 pts         |
| **CROSS-004** | `unit_consistency`  | Units of measure must be consistent (or mathematically convertible) between documents. | Major    | 10 pts        |
| **CROSS-005** | `invoice_reference` | The packing list must reference the correct commercial invoice number.                 | Critical | 10 pts        |

---

## 4. Regulatory Compliance (20% Weight)

Checks for customs and international trade requirements.

| Rule ID     | Rule Name           | Description                                                                               | Severity | Max Deduction |
| ----------- | ------------------- | ----------------------------------------------------------------------------------------- | -------- | ------------- |
| **REG-001** | `hs_codes`          | All line items must have valid 6-8 digit numeric HS (Harmonized System) codes.            | Major    | 30 pts        |
| **REG-003** | `incoterms`         | Incoterms must be present and match standard Incoterms 2020 definitions (e.g., FOB, CIF). | Minor    | 5 pts         |
| **REG-005** | `currency_declared` | Currency must be explicitly stated using standard ISO codes.                              | Major    | 5 pts         |

---

## 5. Data Quality (10% Weight)

Flags suspicious data anomalies and low-confidence AI extractions that require human review.

| Rule ID      | Rule Name               | Description                                                                       | Severity | Max Deduction |
| ------------ | ----------------------- | --------------------------------------------------------------------------------- | -------- | ------------- |
| **DATA-001** | `zero_values`           | Line items with non-zero quantities must not have $0.00 pricing.                  | Major    | 8 pts         |
| **DATA-003** | `low_confidence_fields` | Flags fields where the AI extraction confidence is below 60%.                     | Warning  | 0 pts         |
| **DATA-005** | `weight_consistency`    | Gross weight must logically be greater than or equal to net weight for all items. | Major    | 6 pts         |
