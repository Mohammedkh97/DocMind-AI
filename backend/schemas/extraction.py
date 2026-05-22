"""
Pydantic models for the /extract endpoint request and response.

These schemas serve triple duty:
1. API response serialization (FastAPI auto-generates OpenAPI docs from these)
2. Internal data validation (extraction results are validated before returning)
3. Data contract for the compliance engine (compliance rules operate on these types)
"""

from pydantic import BaseModel, Field
from schemas.common import ConfidenceField, ProcessingMetadata


# ─── Invoice Models ───────────────────────────────────────────────────────────


class InvoiceLineItem(BaseModel):
    """A single line item from the commercial invoice."""
    item_no: ConfidenceField[int] = Field(default_factory=lambda: ConfidenceField[int]())
    description: ConfidenceField[str] = Field(default_factory=lambda: ConfidenceField[str]())
    hs_code: ConfidenceField[str] = Field(default_factory=lambda: ConfidenceField[str]())
    quantity: ConfidenceField[float] = Field(default_factory=lambda: ConfidenceField[float]())
    unit: ConfidenceField[str] = Field(default_factory=lambda: ConfidenceField[str]())
    unit_price: ConfidenceField[float] = Field(default_factory=lambda: ConfidenceField[float]())
    amount: ConfidenceField[float] = Field(default_factory=lambda: ConfidenceField[float]())


class BankDetails(BaseModel):
    """Bank details from the invoice footer."""
    bank_name: ConfidenceField[str] = Field(default_factory=lambda: ConfidenceField[str]())
    account_name: ConfidenceField[str] = Field(default_factory=lambda: ConfidenceField[str]())
    account_number: ConfidenceField[str] = Field(default_factory=lambda: ConfidenceField[str]())
    swift_code: ConfidenceField[str] = Field(default_factory=lambda: ConfidenceField[str]())
    iban: ConfidenceField[str] = Field(default_factory=lambda: ConfidenceField[str]())


class SellerInfo(BaseModel):
    """Seller/shipper details."""
    name: ConfidenceField[str] = Field(default_factory=lambda: ConfidenceField[str]())
    address: ConfidenceField[str] = Field(default_factory=lambda: ConfidenceField[str]())
    phone: ConfidenceField[str] = Field(default_factory=lambda: ConfidenceField[str]())
    vat_number: ConfidenceField[str] = Field(default_factory=lambda: ConfidenceField[str]())


class BuyerInfo(BaseModel):
    """Buyer/consignee details."""
    name: ConfidenceField[str] = Field(default_factory=lambda: ConfidenceField[str]())
    address: ConfidenceField[str] = Field(default_factory=lambda: ConfidenceField[str]())
    phone: ConfidenceField[str] = Field(default_factory=lambda: ConfidenceField[str]())
    trn: ConfidenceField[str] = Field(default_factory=lambda: ConfidenceField[str]())


class ShipmentInfo(BaseModel):
    """Shipment/vessel details from the invoice footer."""
    vessel_name: ConfidenceField[str] = Field(default_factory=lambda: ConfidenceField[str]())
    port_of_loading: ConfidenceField[str] = Field(default_factory=lambda: ConfidenceField[str]())
    etd: ConfidenceField[str] = Field(default_factory=lambda: ConfidenceField[str]())


class InvoiceData(BaseModel):
    """Complete structured extraction from a commercial invoice."""
    invoice_number: ConfidenceField[str] = Field(default_factory=lambda: ConfidenceField[str]())
    invoice_date: ConfidenceField[str] = Field(default_factory=lambda: ConfidenceField[str]())
    payment_terms: ConfidenceField[str] = Field(default_factory=lambda: ConfidenceField[str]())
    currency: ConfidenceField[str] = Field(default_factory=lambda: ConfidenceField[str]())
    port_of_loading: ConfidenceField[str] = Field(default_factory=lambda: ConfidenceField[str]())
    port_of_discharge: ConfidenceField[str] = Field(default_factory=lambda: ConfidenceField[str]())
    incoterms: ConfidenceField[str] = Field(default_factory=lambda: ConfidenceField[str]())
    lc_number: ConfidenceField[str] = Field(default_factory=lambda: ConfidenceField[str]())

    seller: SellerInfo = Field(default_factory=SellerInfo)
    buyer: BuyerInfo = Field(default_factory=BuyerInfo)
    shipment: ShipmentInfo = Field(default_factory=ShipmentInfo)
    bank_details: BankDetails = Field(default_factory=BankDetails)

    line_items: list[InvoiceLineItem] = Field(default_factory=list)

    subtotal: ConfidenceField[float] = Field(default_factory=lambda: ConfidenceField[float]())
    freight: ConfidenceField[float] = Field(default_factory=lambda: ConfidenceField[float]())
    insurance: ConfidenceField[float] = Field(default_factory=lambda: ConfidenceField[float]())
    grand_total: ConfidenceField[float] = Field(default_factory=lambda: ConfidenceField[float]())


# ─── Packing List Models ─────────────────────────────────────────────────────


class PackingListLineItem(BaseModel):
    """A single line item from the packing list."""
    item_no: ConfidenceField[int] = Field(default_factory=lambda: ConfidenceField[int]())
    description: ConfidenceField[str] = Field(default_factory=lambda: ConfidenceField[str]())
    cartons: ConfidenceField[int] = Field(default_factory=lambda: ConfidenceField[int]())
    quantity: ConfidenceField[float] = Field(default_factory=lambda: ConfidenceField[float]())
    unit: ConfidenceField[str] = Field(default_factory=lambda: ConfidenceField[str]())
    net_weight_kg: ConfidenceField[float] = Field(default_factory=lambda: ConfidenceField[float]())
    gross_weight_kg: ConfidenceField[float] = Field(default_factory=lambda: ConfidenceField[float]())


class PackingListData(BaseModel):
    """Complete structured extraction from a packing list."""
    packing_list_number: ConfidenceField[str] = Field(default_factory=lambda: ConfidenceField[str]())
    ref_invoice: ConfidenceField[str] = Field(default_factory=lambda: ConfidenceField[str]())
    date: ConfidenceField[str] = Field(default_factory=lambda: ConfidenceField[str]())

    line_items: list[PackingListLineItem] = Field(default_factory=list)

    total_cartons: ConfidenceField[int] = Field(default_factory=lambda: ConfidenceField[int]())
    total_net_weight: ConfidenceField[float] = Field(default_factory=lambda: ConfidenceField[float]())
    total_gross_weight: ConfidenceField[float] = Field(default_factory=lambda: ConfidenceField[float]())


# ─── Combined Response ────────────────────────────────────────────────────────


class ExtractionResponse(BaseModel):
    """
    Complete response from the /extract endpoint.

    Contains structured data from both the commercial invoice and packing list,
    with per-field confidence scores and processing metadata.
    """
    invoice: InvoiceData = Field(default_factory=InvoiceData)
    packing_list: PackingListData = Field(default_factory=PackingListData)
    metadata: ProcessingMetadata
