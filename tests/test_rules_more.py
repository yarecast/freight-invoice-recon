from decimal import Decimal

from helpers import make_item, make_load
from recon.rules import evaluate

TOL = Decimal("0.00")


def run_many(items):
    return evaluate(items, tolerance=TOL, aliases={})


def codes(findings):
    return {f.code for f in findings}


def test_same_invoice_number_is_merged_into_duplicate_invoice_number():
    load = make_load()
    a = make_item(source_file="f07.pdf", load=load)
    b = make_item(source_file="f08.pdf", load=load, has_text_layer=False)
    result = run_many([a, b])
    assert codes(result["f07.pdf"]) == {"DUPLICATE_INVOICE_NUMBER"}
    assert codes(result["f08.pdf"]) == {"DUPLICATE_INVOICE_NUMBER"}


def test_different_invoice_numbers_same_load_is_duplicate_load_invoice():
    load = make_load()
    a = make_item(source_file="f09.pdf", invoice_number="A-1001", load=load)
    b = make_item(source_file="f10.pdf", invoice_number="A-1002", load=load)
    result = run_many([a, b])
    assert codes(result["f09.pdf"]) == {"DUPLICATE_LOAD_INVOICE"}
    assert codes(result["f10.pdf"]) == {"DUPLICATE_LOAD_INVOICE"}


def test_extraction_mismatch_is_medium():
    item = make_item(load=make_load(), mismatched=("invoice_number",))
    findings = run_many([item])["f01.pdf"]
    assert codes(findings) == {"EXTRACTION_MISMATCH"}
    assert findings[0].severity == "MEDIUM"


def test_single_read_with_legibility_notes_is_flagged():
    item = make_item(load=make_load(), has_text_layer=False,
                     legibility="Texto borroso en el monto")
    assert "SINGLE_READ_LOW_LEGIBILITY" in codes(run_many([item])["f01.pdf"])


def test_single_read_without_legibility_notes_is_not_flagged():
    item = make_item(load=make_load(), has_text_layer=False, legibility=None)
    assert "SINGLE_READ_LOW_LEGIBILITY" not in codes(run_many([item])["f01.pdf"])


def test_invoice_before_shipment_is_medium():
    item = make_item(invoice_date="2026-08-20", load=make_load())
    findings = run_many([item])["f01.pdf"]
    assert codes(findings) == {"INVOICE_BEFORE_SHIPMENT"}
    assert findings[0].severity == "MEDIUM"


def test_currency_mismatch_is_high():
    item = make_item(currency="USD", load=make_load(currency="MXN"))
    assert "CURRENCY_MISMATCH" in codes(run_many([item])["f01.pdf"])


def test_missing_invoice_number_is_flagged():
    item = make_item(invoice_number=None, load=make_load())
    assert "MISSING_FIELD" in codes(run_many([item])["f01.pdf"])