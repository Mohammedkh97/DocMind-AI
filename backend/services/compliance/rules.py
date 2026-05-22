"""
Compliance rules — deterministic evaluation functions.

CRITICAL DESIGN PRINCIPLE:
Each rule is a PURE FUNCTION: (extracted_data) → list[ComplianceIssue]
No model is called. No randomness. Same input = same output.

Rules are organized by category and each has:
- A unique ID for traceability
- A severity level (critical/major/minor/warning)
- A maximum deduction (caps the point loss)
- A pure evaluation function
"""

from dataclasses import dataclass, field
from typing import Callable, Any
import re
import math

from schemas.extraction import ExtractionResponse
from schemas.compliance import ComplianceIssue
from core.logging import get_logger

logger = get_logger("compliance.rules")


@dataclass
class ComplianceRule:
    """Definition of a single compliance rule."""
    rule_id: str
    rule_name: str
    category: str
    description: str
    severity: str  # critical, major, minor, warning
    max_deduction: int
    evaluate: Callable[[ExtractionResponse], list[ComplianceIssue]]


def _safe_float(value: Any) -> float | None:
    """Safely convert a value to float, handling various formats."""
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").replace("$", "").strip())
    except (ValueError, TypeError):
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# CATEGORY: Document Completeness (25% weight)
# ═══════════════════════════════════════════════════════════════════════════════

def check_required_invoice_fields(data: ExtractionResponse) -> list[ComplianceIssue]:
    """Check that all critical invoice header fields are present."""
    issues = []
    required_fields = {
        "invoice_number": data.invoice.invoice_number,
        "invoice_date": data.invoice.invoice_date,
        "currency": data.invoice.currency,
        "port_of_loading": data.invoice.port_of_loading,
        "port_of_discharge": data.invoice.port_of_discharge,
        "grand_total": data.invoice.grand_total,
    }

    missing = []
    for name, cf in required_fields.items():
        if cf.is_empty:
            missing.append(name)

    if missing:
        deduction = min(len(missing) * 3, 10)
        issues.append(ComplianceIssue(
            rule_id="COMP-001",
            rule_name="required_invoice_fields",
            field=f"invoice.[{', '.join(missing)}]",
            severity="critical",
            category="document_completeness",
            found=f"Missing: {', '.join(missing)}",
            expected="All required fields present",
            deduction=deduction,
            description=f"{len(missing)} required invoice field(s) missing: {', '.join(missing)}",
        ))

    return issues


def check_required_packing_list_fields(data: ExtractionResponse) -> list[ComplianceIssue]:
    """Check that critical packing list fields are present."""
    issues = []
    required_fields = {
        "packing_list_number": data.packing_list.packing_list_number,
        "ref_invoice": data.packing_list.ref_invoice,
        "date": data.packing_list.date,
    }

    missing = [name for name, cf in required_fields.items() if cf.is_empty]

    if missing:
        deduction = min(len(missing) * 2, 5)
        issues.append(ComplianceIssue(
            rule_id="COMP-002",
            rule_name="required_packing_list_fields",
            field=f"packing_list.[{', '.join(missing)}]",
            severity="major",
            category="document_completeness",
            found=f"Missing: {', '.join(missing)}",
            expected="All required fields present",
            deduction=deduction,
            description=f"{len(missing)} required packing list field(s) missing: {', '.join(missing)}",
        ))

    return issues


def check_line_items_exist(data: ExtractionResponse) -> list[ComplianceIssue]:
    """Both documents must have line items."""
    issues = []

    if len(data.invoice.line_items) == 0:
        issues.append(ComplianceIssue(
            rule_id="COMP-003",
            rule_name="invoice_line_items_exist",
            field="invoice.line_items",
            severity="critical",
            category="document_completeness",
            found="0 line items",
            expected="At least 1 line item",
            deduction=10,
            description="No line items found in the invoice",
        ))

    if len(data.packing_list.line_items) == 0:
        issues.append(ComplianceIssue(
            rule_id="COMP-004",
            rule_name="packing_list_line_items_exist",
            field="packing_list.line_items",
            severity="critical",
            category="document_completeness",
            found="0 line items",
            expected="At least 1 line item",
            deduction=8,
            description="No line items found in the packing list",
        ))

    return issues


def check_seller_buyer_info(data: ExtractionResponse) -> list[ComplianceIssue]:
    """Seller and buyer names must be present."""
    issues = []

    if data.invoice.seller.name.is_empty:
        issues.append(ComplianceIssue(
            rule_id="COMP-005",
            rule_name="seller_name_present",
            field="invoice.seller.name",
            severity="major",
            category="document_completeness",
            found="Missing",
            expected="Seller/shipper name",
            deduction=5,
            description="Seller/shipper name is missing from the invoice",
        ))

    if data.invoice.buyer.name.is_empty:
        issues.append(ComplianceIssue(
            rule_id="COMP-006",
            rule_name="buyer_name_present",
            field="invoice.buyer.name",
            severity="major",
            category="document_completeness",
            found="Missing",
            expected="Buyer/consignee name",
            deduction=5,
            description="Buyer/consignee name is missing from the invoice",
        ))

    return issues


# ═══════════════════════════════════════════════════════════════════════════════
# CATEGORY: Mathematical Accuracy (25% weight)
# ═══════════════════════════════════════════════════════════════════════════════

def check_line_item_calculations(data: ExtractionResponse) -> list[ComplianceIssue]:
    """Verify qty × unit_price = amount for each line item."""
    issues = []

    for idx, item in enumerate(data.invoice.line_items):
        qty = _safe_float(item.quantity.value)
        price = _safe_float(item.unit_price.value)
        amount = _safe_float(item.amount.value)

        if qty is not None and price is not None and amount is not None:
            expected_amount = round(qty * price, 2)
            if abs(expected_amount - amount) > 0.01:
                issues.append(ComplianceIssue(
                    rule_id="MATH-001",
                    rule_name="line_item_calculation",
                    field=f"invoice.line_items[{idx}].amount",
                    severity="critical",
                    category="mathematical_accuracy",
                    found=f"${amount:,.2f}",
                    expected=f"${expected_amount:,.2f} (qty:{qty} × price:${price})",
                    deduction=5,
                    description=(
                        f"Line item {idx + 1} amount (${amount:,.2f}) does not match "
                        f"qty ({qty}) × unit_price (${price}) = ${expected_amount:,.2f}"
                    ),
                ))

    return issues


def check_subtotal_sum(data: ExtractionResponse) -> list[ComplianceIssue]:
    """Verify subtotal = sum of all line item amounts."""
    issues = []
    subtotal = _safe_float(data.invoice.subtotal.value)

    if subtotal is None:
        return issues

    line_amounts = []
    for item in data.invoice.line_items:
        amt = _safe_float(item.amount.value)
        if amt is not None:
            line_amounts.append(amt)

    if not line_amounts:
        return issues

    calculated_sum = round(sum(line_amounts), 2)

    if abs(calculated_sum - subtotal) > 0.01:
        discrepancy = abs(calculated_sum - subtotal)
        issues.append(ComplianceIssue(
            rule_id="MATH-002",
            rule_name="subtotal_sum",
            field="invoice.subtotal",
            severity="critical",
            category="mathematical_accuracy",
            found=f"${subtotal:,.2f}",
            expected=f"${calculated_sum:,.2f} (sum of line items: {' + '.join(f'${a:,.2f}' for a in line_amounts)})",
            deduction=15,
            description=(
                f"Stated subtotal (${subtotal:,.2f}) does not match the sum of line item "
                f"amounts (${calculated_sum:,.2f}). Discrepancy: ${discrepancy:,.2f}"
            ),
        ))

    return issues


def check_grand_total(data: ExtractionResponse) -> list[ComplianceIssue]:
    """Verify grand_total = subtotal + freight + insurance."""
    issues = []
    subtotal = _safe_float(data.invoice.subtotal.value)
    freight = _safe_float(data.invoice.freight.value) or 0.0
    insurance = _safe_float(data.invoice.insurance.value) or 0.0
    grand_total = _safe_float(data.invoice.grand_total.value)

    if subtotal is not None and grand_total is not None:
        expected_total = round(subtotal + freight + insurance, 2)
        if abs(expected_total - grand_total) > 0.01:
            issues.append(ComplianceIssue(
                rule_id="MATH-003",
                rule_name="grand_total_calculation",
                field="invoice.grand_total",
                severity="critical",
                category="mathematical_accuracy",
                found=f"${grand_total:,.2f}",
                expected=f"${expected_total:,.2f} (subtotal:${subtotal:,.2f} + freight:${freight:,.2f} + insurance:${insurance:,.2f})",
                deduction=10,
                description=(
                    f"Grand total (${grand_total:,.2f}) does not match "
                    f"subtotal + freight + insurance (${expected_total:,.2f})"
                ),
            ))

    return issues


def check_packing_list_totals(data: ExtractionResponse) -> list[ComplianceIssue]:
    """Verify packing list totals match sum of line items."""
    issues = []

    # Check total cartons
    total_cartons = _safe_float(data.packing_list.total_cartons.value)
    if total_cartons is not None and data.packing_list.line_items:
        calculated = sum(
            _safe_float(item.cartons.value) or 0
            for item in data.packing_list.line_items
        )
        if abs(calculated - total_cartons) > 0.5:
            issues.append(ComplianceIssue(
                rule_id="MATH-004",
                rule_name="packing_list_cartons_total",
                field="packing_list.total_cartons",
                severity="major",
                category="mathematical_accuracy",
                found=str(int(total_cartons)),
                expected=str(int(calculated)),
                deduction=5,
                description=f"Total cartons ({int(total_cartons)}) does not match sum of line items ({int(calculated)})",
            ))

    # Check total net weight
    total_net = _safe_float(data.packing_list.total_net_weight.value)
    if total_net is not None and data.packing_list.line_items:
        calculated_net = round(sum(
            _safe_float(item.net_weight_kg.value) or 0
            for item in data.packing_list.line_items
        ), 1)
        if abs(calculated_net - total_net) > 0.5:
            issues.append(ComplianceIssue(
                rule_id="MATH-005",
                rule_name="packing_list_net_weight_total",
                field="packing_list.total_net_weight",
                severity="major",
                category="mathematical_accuracy",
                found=f"{total_net} KG",
                expected=f"{calculated_net} KG",
                deduction=5,
                description=f"Total net weight ({total_net} KG) does not match sum of line items ({calculated_net} KG)",
            ))

    # Check total gross weight
    total_gross = _safe_float(data.packing_list.total_gross_weight.value)
    if total_gross is not None and data.packing_list.line_items:
        calculated_gross = round(sum(
            _safe_float(item.gross_weight_kg.value) or 0
            for item in data.packing_list.line_items
        ), 1)
        if abs(calculated_gross - total_gross) > 0.5:
            issues.append(ComplianceIssue(
                rule_id="MATH-006",
                rule_name="packing_list_gross_weight_total",
                field="packing_list.total_gross_weight",
                severity="major",
                category="mathematical_accuracy",
                found=f"{total_gross} KG",
                expected=f"{calculated_gross} KG",
                deduction=5,
                description=f"Total gross weight ({total_gross} KG) does not match sum of line items ({calculated_gross} KG)",
            ))

    return issues


# ═══════════════════════════════════════════════════════════════════════════════
# CATEGORY: Cross-Document Consistency (20% weight)
# ═══════════════════════════════════════════════════════════════════════════════

def check_quantity_match(data: ExtractionResponse) -> list[ComplianceIssue]:
    """Compare quantities between invoice and packing list."""
    issues = []

    inv_items = data.invoice.line_items
    pl_items = data.packing_list.line_items

    for inv_item in inv_items:
        inv_no = inv_item.item_no.value
        if inv_no is None:
            continue

        # Find matching packing list item
        matching_pl = None
        for pl_item in pl_items:
            if pl_item.item_no.value == inv_no:
                matching_pl = pl_item
                break

        if matching_pl is None:
            issues.append(ComplianceIssue(
                rule_id="CROSS-001",
                rule_name="item_exists_in_packing_list",
                field=f"packing_list.line_items (item {inv_no})",
                severity="major",
                category="cross_document_consistency",
                found="Item not found in packing list",
                expected=f"Item {inv_no} should exist in both documents",
                deduction=5,
                description=f"Invoice item {inv_no} has no corresponding entry in the packing list",
            ))
            continue

        # Compare quantities (they should match if same units)
        inv_qty = _safe_float(inv_item.quantity.value)
        pl_qty = _safe_float(matching_pl.quantity.value)
        inv_unit = str(inv_item.unit.value or "").upper().strip()
        pl_unit = str(matching_pl.unit.value or "").upper().strip()

        if inv_qty is not None and pl_qty is not None:
            if inv_unit == pl_unit and abs(inv_qty - pl_qty) > 0.5:
                issues.append(ComplianceIssue(
                    rule_id="CROSS-002",
                    rule_name="quantity_match",
                    field=f"line_items[{inv_no - 1 if isinstance(inv_no, int) else inv_no}].quantity",
                    severity="major",
                    category="cross_document_consistency",
                    found=f"Invoice: {inv_qty} {inv_unit}, Packing List: {pl_qty} {pl_unit}",
                    expected="Matching quantities between documents",
                    deduction=5,
                    description=(
                        f"Item {inv_no} quantity mismatch: Invoice has {inv_qty} {inv_unit}, "
                        f"Packing List has {pl_qty} {pl_unit}"
                    ),
                ))

    return issues


def check_description_match(data: ExtractionResponse) -> list[ComplianceIssue]:
    """Compare item descriptions between invoice and packing list."""
    issues = []

    inv_items = data.invoice.line_items
    pl_items = data.packing_list.line_items

    for inv_item in inv_items:
        inv_no = inv_item.item_no.value
        if inv_no is None:
            continue

        matching_pl = None
        for pl_item in pl_items:
            if pl_item.item_no.value == inv_no:
                matching_pl = pl_item
                break

        if matching_pl is None:
            continue

        inv_desc = str(inv_item.description.value or "").strip()
        pl_desc = str(matching_pl.description.value or "").strip()

        if inv_desc and pl_desc and inv_desc.lower() != pl_desc.lower():
            # Check if it's a minor difference (e.g., extra details in one)
            if inv_desc.lower().split("(")[0].strip() != pl_desc.lower().split("(")[0].strip():
                severity = "major"
                deduction = 3
            else:
                severity = "minor"
                deduction = 1

            issues.append(ComplianceIssue(
                rule_id="CROSS-003",
                rule_name="description_match",
                field=f"line_items[{inv_no - 1 if isinstance(inv_no, int) else inv_no}].description",
                severity=severity,
                category="cross_document_consistency",
                found=f"Invoice: '{inv_desc}', Packing List: '{pl_desc}'",
                expected="Matching descriptions",
                deduction=deduction,
                description=(
                    f"Item {inv_no} description mismatch between invoice and packing list"
                ),
            ))

    return issues


def check_unit_consistency(data: ExtractionResponse) -> list[ComplianceIssue]:
    """Check for unit mismatches between invoice and packing list."""
    issues = []

    inv_items = data.invoice.line_items
    pl_items = data.packing_list.line_items

    for inv_item in inv_items:
        inv_no = inv_item.item_no.value
        if inv_no is None:
            continue

        matching_pl = None
        for pl_item in pl_items:
            if pl_item.item_no.value == inv_no:
                matching_pl = pl_item
                break

        if matching_pl is None:
            continue

        inv_unit = str(inv_item.unit.value or "").upper().strip()
        pl_unit = str(matching_pl.unit.value or "").upper().strip()

        if inv_unit and pl_unit and inv_unit != pl_unit:
            # Some unit conversions are acceptable (LBS/KG)
            convertible_pairs = [
                ({"LBS", "KG"}, "weight"),
                ({"MTR", "METER", "METERS"}, "length"),
            ]

            is_convertible = False
            for pair, _ in convertible_pairs:
                if inv_unit in pair and pl_unit in pair:
                    is_convertible = True
                    break

            severity = "minor" if is_convertible else "major"
            deduction = 2 if is_convertible else 5

            issues.append(ComplianceIssue(
                rule_id="CROSS-004",
                rule_name="unit_consistency",
                field=f"line_items[{inv_no - 1 if isinstance(inv_no, int) else inv_no}].unit",
                severity=severity,
                category="cross_document_consistency",
                found=f"Invoice: {inv_unit}, Packing List: {pl_unit}",
                expected="Consistent units between documents",
                deduction=deduction,
                description=(
                    f"Item {inv_no} uses different units: Invoice has {inv_unit}, "
                    f"Packing List has {pl_unit}"
                    + (" (convertible but inconsistent)" if is_convertible else "")
                ),
            ))

    return issues


def check_invoice_reference(data: ExtractionResponse) -> list[ComplianceIssue]:
    """Packing list should reference the correct invoice number."""
    issues = []

    inv_num = str(data.invoice.invoice_number.value or "").strip()
    ref_inv = str(data.packing_list.ref_invoice.value or "").strip()

    if inv_num and ref_inv and inv_num.lower() != ref_inv.lower():
        issues.append(ComplianceIssue(
            rule_id="CROSS-005",
            rule_name="invoice_reference_match",
            field="packing_list.ref_invoice",
            severity="critical",
            category="cross_document_consistency",
            found=ref_inv,
            expected=inv_num,
            deduction=10,
            description=(
                f"Packing list references invoice '{ref_inv}' but the actual "
                f"invoice number is '{inv_num}'"
            ),
        ))

    return issues


# ═══════════════════════════════════════════════════════════════════════════════
# CATEGORY: Regulatory Compliance (20% weight)
# ═══════════════════════════════════════════════════════════════════════════════

def check_hs_codes(data: ExtractionResponse) -> list[ComplianceIssue]:
    """All line items must have valid HS codes."""
    issues = []

    for idx, item in enumerate(data.invoice.line_items):
        hs_code = str(item.hs_code.value or "").strip()

        if not hs_code:
            issues.append(ComplianceIssue(
                rule_id="REG-001",
                rule_name="hs_code_present",
                field=f"invoice.line_items[{idx}].hs_code",
                severity="major",
                category="regulatory_compliance",
                found="Missing",
                expected="Valid 6-8 digit HS code",
                deduction=5,
                description=f"Line item {idx + 1} is missing an HS code",
            ))
        elif not re.match(r'^\d{6,8}$', hs_code.replace(".", "").replace(" ", "")):
            issues.append(ComplianceIssue(
                rule_id="REG-002",
                rule_name="hs_code_format",
                field=f"invoice.line_items[{idx}].hs_code",
                severity="major",
                category="regulatory_compliance",
                found=hs_code,
                expected="Valid 6-8 digit numeric HS code",
                deduction=5,
                description=f"Line item {idx + 1} has an invalid HS code format: '{hs_code}'",
            ))

    return issues


def check_incoterms(data: ExtractionResponse) -> list[ComplianceIssue]:
    """Incoterms should be present and valid."""
    issues = []
    incoterms = str(data.invoice.incoterms.value or "").strip()

    valid_incoterms = {
        "EXW", "FCA", "CPT", "CIP", "DAP", "DPU", "DDP",
        "FAS", "FOB", "CFR", "CIF",
    }

    if not incoterms:
        issues.append(ComplianceIssue(
            rule_id="REG-003",
            rule_name="incoterms_present",
            field="invoice.incoterms",
            severity="minor",
            category="regulatory_compliance",
            found="Missing",
            expected="Valid Incoterms 2020 term",
            deduction=3,
            description="Incoterms not specified on the invoice",
        ))
    else:
        # Extract the Incoterms code (e.g., "FOB" from "FOB Shanghai")
        incoterm_code = incoterms.split()[0].upper() if incoterms else ""
        if incoterm_code not in valid_incoterms:
            issues.append(ComplianceIssue(
                rule_id="REG-004",
                rule_name="incoterms_valid",
                field="invoice.incoterms",
                severity="minor",
                category="regulatory_compliance",
                found=incoterms,
                expected=f"One of: {', '.join(sorted(valid_incoterms))}",
                deduction=2,
                description=f"Incoterms value '{incoterms}' may not be a standard Incoterms 2020 term",
            ))

    return issues


def check_currency_declared(data: ExtractionResponse) -> list[ComplianceIssue]:
    """Currency must be explicitly stated."""
    issues = []

    if data.invoice.currency.is_empty:
        issues.append(ComplianceIssue(
            rule_id="REG-005",
            rule_name="currency_declared",
            field="invoice.currency",
            severity="major",
            category="regulatory_compliance",
            found="Missing",
            expected="ISO 4217 currency code (e.g., USD, EUR)",
            deduction=5,
            description="Invoice currency is not declared",
        ))

    return issues


# ═══════════════════════════════════════════════════════════════════════════════
# CATEGORY: Data Quality (10% weight)
# ═══════════════════════════════════════════════════════════════════════════════

def check_zero_values(data: ExtractionResponse) -> list[ComplianceIssue]:
    """Flag line items with zero unit price or amount (data entry error)."""
    issues = []

    for idx, item in enumerate(data.invoice.line_items):
        price = _safe_float(item.unit_price.value)
        amount = _safe_float(item.amount.value)
        qty = _safe_float(item.quantity.value)

        # Zero price with non-zero quantity is suspicious
        if price is not None and price == 0.0 and qty is not None and qty > 0:
            issues.append(ComplianceIssue(
                rule_id="DATA-001",
                rule_name="zero_unit_price",
                field=f"invoice.line_items[{idx}].unit_price",
                severity="major",
                category="data_quality",
                found=f"$0.00 (qty: {qty})",
                expected="Non-zero unit price for items with quantity > 0",
                deduction=5,
                description=(
                    f"Line item {idx + 1} ({item.description.value or 'unknown'}) has a "
                    f"unit price of $0.00 with quantity {qty}. This may indicate a data entry error "
                    f"or missing pricing information."
                ),
            ))

        if amount is not None and amount == 0.0 and qty is not None and qty > 0:
            issues.append(ComplianceIssue(
                rule_id="DATA-002",
                rule_name="zero_amount",
                field=f"invoice.line_items[{idx}].amount",
                severity="major",
                category="data_quality",
                found=f"$0.00",
                expected="Non-zero amount for items with quantity > 0",
                deduction=3,
                description=(
                    f"Line item {idx + 1} ({item.description.value or 'unknown'}) has a "
                    f"total amount of $0.00 despite having a non-zero quantity."
                ),
            ))

    return issues


def check_low_confidence_fields(data: ExtractionResponse) -> list[ComplianceIssue]:
    """Flag fields with low extraction confidence (informational warnings)."""
    issues = []

    # Check critical invoice fields
    critical_fields = {
        "invoice_number": data.invoice.invoice_number,
        "invoice_date": data.invoice.invoice_date,
        "grand_total": data.invoice.grand_total,
        "subtotal": data.invoice.subtotal,
    }

    for name, cf in critical_fields.items():
        if cf.confidence > 0 and cf.confidence < 0.60:
            issues.append(ComplianceIssue(
                rule_id="DATA-003",
                rule_name="low_confidence_field",
                field=f"invoice.{name}",
                severity="warning",
                category="data_quality",
                found=f"Confidence: {cf.confidence:.0%}",
                expected="Confidence ≥ 60%",
                deduction=0,  # Warnings don't deduct points
                description=(
                    f"Field '{name}' has low extraction confidence ({cf.confidence:.0%}). "
                    f"Value may be inaccurate due to poor scan quality."
                ),
            ))

    # Check HS codes for low confidence
    for idx, item in enumerate(data.invoice.line_items):
        if item.hs_code.confidence > 0 and item.hs_code.confidence < 0.60:
            issues.append(ComplianceIssue(
                rule_id="DATA-004",
                rule_name="low_confidence_hs_code",
                field=f"invoice.line_items[{idx}].hs_code",
                severity="warning",
                category="data_quality",
                found=f"'{item.hs_code.value}' (confidence: {item.hs_code.confidence:.0%})",
                expected="High confidence HS code",
                deduction=0,
                description=(
                    f"Line item {idx + 1} HS code has low confidence ({item.hs_code.confidence:.0%}). "
                    f"The extracted value '{item.hs_code.value}' may be incorrect."
                ),
            ))

    return issues


def check_weight_consistency(data: ExtractionResponse) -> list[ComplianceIssue]:
    """Gross weight must be greater than or equal to net weight."""
    issues = []

    for idx, item in enumerate(data.packing_list.line_items):
        net = _safe_float(item.net_weight_kg.value)
        gross = _safe_float(item.gross_weight_kg.value)

        if net is not None and gross is not None and gross < net:
            issues.append(ComplianceIssue(
                rule_id="DATA-005",
                rule_name="weight_consistency",
                field=f"packing_list.line_items[{idx}]",
                severity="major",
                category="data_quality",
                found=f"Net: {net} KG, Gross: {gross} KG",
                expected="Gross weight ≥ Net weight",
                deduction=3,
                description=(
                    f"Line item {idx + 1}: gross weight ({gross} KG) is less than "
                    f"net weight ({net} KG), which is physically impossible"
                ),
            ))

    return issues


# ═══════════════════════════════════════════════════════════════════════════════
# RULE REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

ALL_RULES: list[ComplianceRule] = [
    # Document Completeness
    ComplianceRule("COMP-001", "required_invoice_fields", "document_completeness",
                   "All critical invoice fields must be present", "critical", 10,
                   check_required_invoice_fields),
    ComplianceRule("COMP-002", "required_packing_list_fields", "document_completeness",
                   "All critical packing list fields must be present", "major", 5,
                   check_required_packing_list_fields),
    ComplianceRule("COMP-003", "line_items_exist", "document_completeness",
                   "Both documents must contain line items", "critical", 18,
                   check_line_items_exist),
    ComplianceRule("COMP-005", "seller_buyer_info", "document_completeness",
                   "Seller and buyer information must be present", "major", 10,
                   check_seller_buyer_info),

    # Mathematical Accuracy
    ComplianceRule("MATH-001", "line_item_calculations", "mathematical_accuracy",
                   "Line item amounts must equal qty × unit_price", "critical", 30,
                   check_line_item_calculations),
    ComplianceRule("MATH-002", "subtotal_sum", "mathematical_accuracy",
                   "Subtotal must equal sum of line item amounts", "critical", 15,
                   check_subtotal_sum),
    ComplianceRule("MATH-003", "grand_total_calculation", "mathematical_accuracy",
                   "Grand total must equal subtotal + freight + insurance", "critical", 10,
                   check_grand_total),
    ComplianceRule("MATH-004", "packing_list_totals", "mathematical_accuracy",
                   "Packing list totals must match line item sums", "major", 15,
                   check_packing_list_totals),

    # Cross-Document Consistency
    ComplianceRule("CROSS-001", "quantity_match", "cross_document_consistency",
                   "Quantities must match between invoice and packing list", "major", 25,
                   check_quantity_match),
    ComplianceRule("CROSS-003", "description_match", "cross_document_consistency",
                   "Descriptions must match between documents", "minor", 6,
                   check_description_match),
    ComplianceRule("CROSS-004", "unit_consistency", "cross_document_consistency",
                   "Units must be consistent between documents", "major", 10,
                   check_unit_consistency),
    ComplianceRule("CROSS-005", "invoice_reference", "cross_document_consistency",
                   "Packing list must reference correct invoice number", "critical", 10,
                   check_invoice_reference),

    # Regulatory Compliance
    ComplianceRule("REG-001", "hs_codes", "regulatory_compliance",
                   "All items must have valid HS codes", "major", 30,
                   check_hs_codes),
    ComplianceRule("REG-003", "incoterms", "regulatory_compliance",
                   "Incoterms must be present and valid", "minor", 5,
                   check_incoterms),
    ComplianceRule("REG-005", "currency_declared", "regulatory_compliance",
                   "Currency must be explicitly stated", "major", 5,
                   check_currency_declared),

    # Data Quality
    ComplianceRule("DATA-001", "zero_values", "data_quality",
                   "Line items must not have zero pricing", "major", 8,
                   check_zero_values),
    ComplianceRule("DATA-003", "low_confidence_fields", "data_quality",
                   "Flag fields with low extraction confidence", "warning", 0,
                   check_low_confidence_fields),
    ComplianceRule("DATA-005", "weight_consistency", "data_quality",
                   "Gross weight must be ≥ net weight", "major", 6,
                   check_weight_consistency),
]
