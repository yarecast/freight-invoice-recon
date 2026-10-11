"""Pydantic schema for what the LLM reads from an invoice. Strings only: parsing happens in verify.py."""
from pydantic import BaseModel


class Evidenced(BaseModel):
    value: str | None  # null when not visible or unreadable
    evidence: str | None  # short verbatim text from the document


class Annotation(BaseModel):
    text: str  # handwritten or non-printed-form text, verbatim
    amounts: list[str]  # amounts mentioned in that text, as written


class InvoiceExtraction(BaseModel):
    carrier: Evidenced
    invoice_number: Evidenced  # keep leading zeros
    load_ref: Evidenced
    invoice_date: Evidenced  # ISO yyyy-mm-dd, reading the document's own date format
    amount_printed: Evidenced  # as printed, never computed
    currency: Evidenced  # null if not printed; never inferred
    handwritten_annotations: list[Annotation]
    document_type: str | None
    legibility_notes: str | None