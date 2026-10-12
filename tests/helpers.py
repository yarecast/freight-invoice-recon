from datetime import date
from decimal import Decimal

from recon.matching import Load, MatchResult
from recon.models import Evidenced, InvoiceExtraction
from recon.rules import InvoiceInput
from recon.verify import VerifyResult


def ev(value):
    """Build an Evidenced field; evidence equals the value (good enough for rule tests)."""
    return Evidenced(value=value, evidence=value)


def make_load(load_id="TRQ-4470", carrier="Transportes Ejemplo S.A. de C.V.",
              rate="7500.00", currency="MXN", ship_date=date(2026, 9, 1)):
    return Load(load_id=load_id, ship_date=ship_date, carrier=carrier,
                origin="Monterrey", destination="Laredo", commodity="Auto parts",
                agreed_rate=Decimal(rate), currency=currency)


def make_item(source_file="f01.pdf", carrier="Transportes Ejemplo S.A. de C.V.",
              invoice_number="A-1001", load_ref="TRQ-4470", invoice_date="2026-09-05",
              amount="7500.00", currency="MXN", load=None, has_text_layer=True,
              mismatched=(), legibility=None):
    extraction = InvoiceExtraction(
        carrier=ev(carrier), invoice_number=ev(invoice_number), load_ref=ev(load_ref),
        invoice_date=ev(invoice_date), amount_printed=ev(amount), currency=ev(currency),
        handwritten_annotations=[], document_type="invoice", legibility_notes=legibility,
    )
    verify = VerifyResult(
        has_text_layer=has_text_layer, mismatched_fields=tuple(mismatched),
        amount=Decimal(amount) if amount is not None else None,
        invoice_date=date.fromisoformat(invoice_date) if invoice_date else None,
        load_ref_format_ok=True,
    )
    match = MatchResult(load_ref=load_ref, load=load, suggestions=())
    return InvoiceInput(source_file=source_file, extraction=extraction,
                        verify=verify, match=match)