import dataclasses
from decimal import Decimal

from helpers import make_item, make_load
from recon.models import Annotation
from recon.rules import evaluate

TOL = Decimal("0.00")


def with_notes(item, notes):
    extraction = item.extraction.model_copy(update={"handwritten_annotations": notes})
    return dataclasses.replace(item, extraction=extraction)


def run(item):
    return evaluate([item], tolerance=TOL, aliases={})[item.source_file]


def test_handwritten_total_differs_from_printed_and_agreed():
    load = make_load(load_id="TRQ-4490", carrier="Rio Grande", rate="850.00", currency="USD")
    item = make_item(source_file="f17.pdf", carrier="Rio Grande", load_ref="TRQ-4490",
                     amount="850.00", currency="USD", load=load, has_text_layer=False)
    item = with_notes(item, [
        Annotation(text="+ 150 detention", amounts=["150.00"]),
        Annotation(text="TOTAL 1,000", amounts=["1,000.00"]),
    ])
    findings = run(item)
    assert {f.code for f in findings} == {"ANNOTATED_AMOUNT"}
    assert findings[0].severity == "HIGH"
    assert "+150.00" in findings[0].reason


def test_annotation_equal_to_printed_amount_is_not_flagged():
    load = make_load(rate="850.00", currency="USD")
    item = make_item(amount="850.00", currency="USD", load=load)
    item = with_notes(item, [Annotation(text="OK 850", amounts=["850.00"])])
    assert run(item) == []