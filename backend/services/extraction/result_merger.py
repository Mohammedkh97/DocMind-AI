"""
Result merger: converts raw VLM/OCR dicts into validated Pydantic models.

This is the translation layer between the messy world of model outputs
and the clean world of typed Pydantic schemas. It handles:
- Mapping raw dict keys to Pydantic field names
- Applying confidence scoring to each field
- Handling missing/null values gracefully
- Building ConfidenceField[T] instances for every field
"""

from typing import Any

from schemas.common import ConfidenceField
from schemas.extraction import (
    InvoiceData,
    InvoiceLineItem,
    PackingListData,
    PackingListLineItem,
    SellerInfo,
    BuyerInfo,
    BankDetails,
    ShipmentInfo,
)
from services.extraction.confidence_scorer import ConfidenceScorer
from core.logging import get_logger

logger = get_logger("result_merger")


class ResultMerger:
    """Merges raw extraction data into validated Pydantic models with confidence scores."""

    def __init__(self, scorer: ConfidenceScorer):
        self.scorer = scorer

    def build_invoice(self, raw: dict[str, Any]) -> InvoiceData:
        """Build an InvoiceData model from raw VLM extraction output."""

        def cf(field_name: str, field_type: str = "text") -> ConfidenceField:
            """Helper to create a ConfidenceField from raw data."""
            raw_field = raw.get(field_name, {})
            if isinstance(raw_field, dict):
                value = raw_field.get("value")
                vlm_conf = float(raw_field.get("confidence", 0.0))
            else:
                value = raw_field
                vlm_conf = 0.7  # Reasonable default if model didn't report confidence

            confidence = self.scorer.score_field(
                field_name=field_name,
                value=value,
                vlm_confidence=vlm_conf,
                field_type=field_type,
            )
            return ConfidenceField(value=value, confidence=confidence)

        # Build seller info
        seller_raw = raw.get("seller", {})
        seller = SellerInfo(
            name=self._build_cf("name", seller_raw, "text"),
            address=self._build_cf("address", seller_raw, "text"),
            phone=self._build_cf("phone", seller_raw, "text"),
            vat_number=self._build_cf("vat_number", seller_raw, "text"),
        )

        # Build buyer info
        buyer_raw = raw.get("buyer", {})
        buyer = BuyerInfo(
            name=self._build_cf("name", buyer_raw, "text"),
            address=self._build_cf("address", buyer_raw, "text"),
            phone=self._build_cf("phone", buyer_raw, "text"),
            trn=self._build_cf("trn", buyer_raw, "text"),
        )

        # Build bank details
        bank_raw = raw.get("bank_details", {})
        bank = BankDetails(
            bank_name=self._build_cf("bank_name", bank_raw, "text"),
            account_name=self._build_cf("account_name", bank_raw, "text"),
            account_number=self._build_cf("account_number", bank_raw, "text"),
            swift_code=self._build_cf("swift_code", bank_raw, "text"),
            iban=self._build_cf("iban", bank_raw, "text"),
        )

        # Build shipment info
        shipment_raw = raw.get("shipment", {})
        shipment = ShipmentInfo(
            vessel_name=self._build_cf("vessel_name", shipment_raw, "text"),
            port_of_loading=self._build_cf("port_of_loading", shipment_raw, "text"),
            etd=self._build_cf("etd", shipment_raw, "date"),
        )

        # Build line items
        line_items = []
        raw_items = raw.get("line_items", [])
        for idx, item_raw in enumerate(raw_items):
            line_item = InvoiceLineItem(
                item_no=self._build_cf("item_no", item_raw, "number"),
                description=self._build_cf("description", item_raw, "text"),
                hs_code=self._build_cf("hs_code", item_raw, "hs_code"),
                quantity=self._build_cf("quantity", item_raw, "number"),
                unit=self._build_cf("unit", item_raw, "unit"),
                unit_price=self._build_cf("unit_price", item_raw, "number"),
                amount=self._build_cf("amount", item_raw, "number"),
            )
            line_items.append(line_item)

        logger.info("invoice_built", line_items_count=len(line_items))

        return InvoiceData(
            invoice_number=cf("invoice_number", "invoice_number"),
            invoice_date=cf("invoice_date", "date"),
            payment_terms=cf("payment_terms", "text"),
            currency=cf("currency", "currency"),
            port_of_loading=cf("port_of_loading", "text"),
            port_of_discharge=cf("port_of_discharge", "text"),
            incoterms=cf("incoterms", "text"),
            lc_number=cf("lc_number", "text"),
            seller=seller,
            buyer=buyer,
            bank_details=bank,
            shipment=shipment,
            line_items=line_items,
            subtotal=cf("subtotal", "number"),
            freight=cf("freight", "number"),
            insurance=cf("insurance", "number"),
            grand_total=cf("grand_total", "number"),
        )

    def build_packing_list(self, raw: dict[str, Any]) -> PackingListData:
        """Build a PackingListData model from raw VLM extraction output."""

        def cf(field_name: str, field_type: str = "text") -> ConfidenceField:
            raw_field = raw.get(field_name, {})
            if isinstance(raw_field, dict):
                value = raw_field.get("value")
                vlm_conf = float(raw_field.get("confidence", 0.0))
            else:
                value = raw_field
                vlm_conf = 0.7

            confidence = self.scorer.score_field(
                field_name=field_name,
                value=value,
                vlm_confidence=vlm_conf,
                field_type=field_type,
            )
            return ConfidenceField(value=value, confidence=confidence)

        # Build line items
        line_items = []
        raw_items = raw.get("line_items", [])
        for idx, item_raw in enumerate(raw_items):
            line_item = PackingListLineItem(
                item_no=self._build_cf("item_no", item_raw, "number"),
                description=self._build_cf("description", item_raw, "text"),
                cartons=self._build_cf("cartons", item_raw, "number"),
                quantity=self._build_cf("quantity", item_raw, "number"),
                unit=self._build_cf("unit", item_raw, "unit"),
                net_weight_kg=self._build_cf("net_weight_kg", item_raw, "number"),
                gross_weight_kg=self._build_cf("gross_weight_kg", item_raw, "number"),
            )
            line_items.append(line_item)

        logger.info("packing_list_built", line_items_count=len(line_items))

        return PackingListData(
            packing_list_number=cf("packing_list_number", "text"),
            ref_invoice=cf("ref_invoice", "invoice_number"),
            date=cf("date", "date"),
            line_items=line_items,
            total_cartons=cf("total_cartons", "number"),
            total_net_weight=cf("total_net_weight", "number"),
            total_gross_weight=cf("total_gross_weight", "number"),
        )

    def _build_cf(
        self,
        field_name: str,
        parent_dict: dict,
        field_type: str,
    ) -> ConfidenceField:
        """
        Build a ConfidenceField from a nested dict.

        Handles both formats:
        - {"value": ..., "confidence": ...} (model reported confidence)
        - plain value (model didn't report confidence)
        """
        raw_field = parent_dict.get(field_name, {})

        if isinstance(raw_field, dict) and "value" in raw_field:
            value = raw_field.get("value")
            vlm_conf = float(raw_field.get("confidence", 0.0))
        else:
            value = raw_field if raw_field != {} else None
            vlm_conf = 0.7

        confidence = self.scorer.score_field(
            field_name=field_name,
            value=value,
            vlm_confidence=vlm_conf,
            field_type=field_type,
        )

        return ConfidenceField(value=value, confidence=confidence)
