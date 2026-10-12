"""Compare hand-written expectations (tests/golden/expected.csv) with the system output.

Read-only: never edits the golden file or the extractions.
Run: python scripts/compare_golden.py
"""
import csv
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from recon.config import load_settings  # noqa: E402
from recon.matching import normalize_name  # noqa: E402
from recon.rules import annotated_amounts  # noqa: E402
from recon.verify import parse_amount  # noqa: E402
from run import analyze  # noqa: E402

GOLDEN = ROOT / "tests" / "golden" / "expected.csv"
FIELDS = ("carrier", "invoice_number", "load_ref", "invoice_date", "amount_printed",
          "currency", "has_handwriting", "annotated_amount", "status", "codes")


def to_decimal(text):
    try:
        return Decimal(text)
    except (InvalidOperation, TypeError):
        return None


def system_decimal(text):
    if not text:
        return None
    value = to_decimal(text)
    return value if value is not None else parse_amount(text)


def same(field, expected, got):
    if field == "carrier":
        return normalize_name(expected or "") == normalize_name(got or "")
    if field in ("amount_printed", "annotated_amount"):
        if not expected and not got:
            return True
        a, b = to_decimal(expected), system_decimal(got)
        return a is not None and a == b
    if field == "codes":
        return set(filter(None, (expected or "").split(";"))) == set(filter(None, (got or "").split(";")))
    return (expected or "") == (got or "")


def main():
    settings = load_settings()
    items, rows, _unmatched, _metas, _warnings = analyze(settings)
    by_file = {r.source_file: r for r in rows}
    ext_by_file = {i.source_file: i.extraction for i in items}
    with GOLDEN.open(encoding="utf-8-sig", newline="") as fh:
        golden = [r for r in csv.DictReader(fh) if r.get("source_file")]

    total = {f: 0 for f in FIELDS}
    ok = {f: 0 for f in FIELDS}
    diffs = []
    for g in golden:
        row = by_file.get(g["source_file"])
        if row is None:
            diffs.append((g["source_file"], "(archivo)", g["source_file"], "no aparece en el sistema"))
            continue
        x = ext_by_file.get(g["source_file"])
        notes = x.handwritten_annotations if x else []
        extra = annotated_amounts(x) if x else []
        got = {
            "carrier": row.carrier, "invoice_number": row.invoice_number,
            "load_ref": row.load_ref, "invoice_date": row.invoice_date,
            "amount_printed": row.amount_printed, "currency": row.currency,
            "has_handwriting": "yes" if notes else "no",
            "annotated_amount": str(max(extra)) if extra else "",
            "status": row.status, "codes": ";".join(f.code for f in row.findings),
        }
        expected = {
            "carrier": g["carrier"], "invoice_number": g["invoice_number"],
            "load_ref": g["load_ref"], "invoice_date": g["invoice_date"],
            "amount_printed": g["amount_printed"], "currency": g["currency"],
            "has_handwriting": g["has_handwriting"], "annotated_amount": g["annotated_amount"],
            "status": g["expected_status"], "codes": g["expected_codes"],
        }
        for f in FIELDS:
            total[f] += 1
            if same(f, expected[f], got[f]):
                ok[f] += 1
            else:
                diffs.append((g["source_file"], f, expected[f], got[f]))

    print(f"Facturas en el golden: {len(golden)}\n")
    print("Exactitud por campo:")
    for f in FIELDS:
        print(f"  {f:<16} {ok[f]}/{total[f]}")
    print(f"\nDiferencias: {len(diffs)}")
    for name, field, exp, got in diffs:
        print(f"- {name} | {field}\n    golden : {exp!r}\n    sistema: {got!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())