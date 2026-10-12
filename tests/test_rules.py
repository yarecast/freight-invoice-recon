from decimal import Decimal

from helpers import make_item, make_load
from recon.rules import evaluate

TOL = Decimal("0.00")


def run(item, aliases=None):
    return evaluate([item], tolerance=TOL, aliases=aliases or {})[item.source_file]


def codes(findings):
    return {f.code for f in findings}


def test_clean_match_has_no_findings():
    item = make_item(load=make_load())
    assert run(item) == []


def test_amount_mismatch_is_high():
    item = make_item(amount="9200.00", load=make_load(rate="7500.00"))
    findings = run(item)
    assert codes(findings) == {"AMOUNT_MISMATCH"}
    assert findings[0].severity == "HIGH"


def test_no_load_match_is_high():
    item = make_item(load_ref="TRQ-9902", load=None)
    findings = run(item)
    assert "NO_LOAD_MATCH" in codes(findings)
    assert {f.severity for f in findings if f.code == "NO_LOAD_MATCH"} == {"HIGH"}


def test_currency_not_printed_is_low_only():
    item = make_item(currency=None, load=make_load(currency="MXN"))
    findings = run(item)
    assert codes(findings) == {"CURRENCY_NOT_PRINTED"}
    assert findings[0].severity == "LOW"


def test_carrier_alias_is_accepted_and_without_alias_is_flagged():
    load = make_load(carrier="Pena Hermanos")
    item = make_item(carrier="Autotransportes Pena Hnos.", load=load)
    aliases = {"Autotransportes Pena Hnos.": ["Pena Hermanos"]}
    assert "CARRIER_MISMATCH" not in codes(run(item, aliases))
    assert "CARRIER_MISMATCH" in codes(run(item, {}))