from decimal import Decimal

from helpers import make_item, make_load
from recon.report import InvoiceRow, build_rows, render_html, write_csv
from recon.rules import Finding, evaluate

META = {
    "mode": "demo", "models": ["test-model"], "prompt_versions": ["v1"],
    "extracted_first": "2026-10-01", "extracted_last": "2026-10-02",
    "generated_at": "2026-10-11", "warnings": [],
}


def make_row(carrier="Transportes Ejemplo", reason="Razon normal"):
    finding = Finding("AMOUNT_MISMATCH", "HIGH", reason, "Accion normal")
    return InvoiceRow(source_file="f01.pdf", carrier=carrier, invoice_number="A-1",
                      load_ref="TRQ-4470", invoice_date="2026-09-05",
                      amount_printed="100.00", currency="MXN", read_mode="texto",
                      status="HIGH", findings=(finding,))


def test_html_escapes_extracted_text():
    row = make_row(carrier="<script>alert(1)</script>", reason="<b>negrita</b>")
    html_out = render_html([row], [], META)
    assert "<script>alert(1)</script>" not in html_out
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html_out
    assert "<b>negrita</b>" not in html_out
    assert "&lt;b&gt;negrita&lt;/b&gt;" in html_out


def test_html_has_no_javascript_or_external_requests():
    item = make_item(amount="9200.00", load=make_load(rate="7500.00"))
    results = evaluate([item], tolerance=Decimal("0.00"), aliases={})
    rows = build_rows([item], results)
    html_out = render_html(rows, [], META)
    assert "<script" not in html_out.lower()
    assert "http://" not in html_out
    assert "https://" not in html_out


def test_csv_has_bom_and_neutralizes_formulas(tmp_path):
    path = tmp_path / "reporte.csv"
    write_csv(path, [make_row(carrier="=HYPERLINK(\"x\")")])
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    assert "'=HYPERLINK" in text