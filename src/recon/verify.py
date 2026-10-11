"""Deterministic checks on what the LLM read. No network and no matching decisions."""
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pymupdf

from .models import InvoiceExtraction

LOAD_REF_RE = re.compile(r"TRQ-\d{4}")
MIN_TEXT_CHARS = 20  # fewer characters than this means the PDF has no usable text layer
_AMOUNT_RE = re.compile(r"\d{1,3}(,\d{3})+(\.\d+)?|\d+(\.\d+)?")
_ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


@dataclass(frozen=True)
class VerifyResult:
    has_text_layer: bool  # False means image-only: a single read by the model
    mismatched_fields: tuple[str, ...]  # fields not found in the text layer
    amount: Decimal | None
    invoice_date: date | None
    load_ref_format_ok: bool


def parse_amount(text: str | None) -> Decimal | None:
    """Accepts 1,000.00 style only (comma thousands, dot decimals). Anything else returns None."""
    if text is None:
        return None
    cleaned = re.sub(r"[^\d.,]", "", text)
    if not _AMOUNT_RE.fullmatch(cleaned):
        return None
    try:
        return Decimal(cleaned.replace(",", ""))
    except InvalidOperation:
        return None


def parse_iso_date(text: str | None) -> date | None:
    if text is None or not _ISO_DATE_RE.fullmatch(text.strip()):
        return None
    try:
        return date.fromisoformat(text.strip())
    except ValueError:
        return None


def _squash(text: str) -> str:
    return "".join(text.split()).lower()


def read_text_layer(pdf_path: Path) -> str:
    with pymupdf.open(pdf_path) as doc:
        return _squash("".join(page.get_text() for page in doc))


def verify(pdf_path: Path, extraction: InvoiceExtraction) -> VerifyResult:
    layer = read_text_layer(pdf_path)
    has_layer = len(layer) >= MIN_TEXT_CHARS
    mismatched: list[str] = []
    if has_layer:
        for name in ("invoice_number", "load_ref", "amount_printed"):
            value = getattr(extraction, name).value
            if value is not None and _squash(value) not in layer:
                mismatched.append(name)
    load_ref = extraction.load_ref.value
    return VerifyResult(
        has_text_layer=has_layer,
        mismatched_fields=tuple(mismatched),
        amount=parse_amount(extraction.amount_printed.value),
        invoice_date=parse_iso_date(extraction.invoice_date.value),
        load_ref_format_ok=bool(load_ref and LOAD_REF_RE.fullmatch(load_ref.strip().upper())),
    )