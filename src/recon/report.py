"""Report writers: self-contained HTML (no JavaScript, no external requests) and CSV (UTF-8 with BOM)."""
import csv
import html
from dataclasses import dataclass
from pathlib import Path

from .matching import Load
from .rules import HIGH, LOW, MEDIUM, NO_FINDINGS, SEVERITY_ORDER, Finding, InvoiceInput, status_of

STATUS_ORDER = (HIGH, MEDIUM, LOW, NO_FINDINGS)
LABELS = {HIGH: "ALTA", MEDIUM: "MEDIA", LOW: "BAJA", NO_FINDINGS: "SIN HALLAZGOS"}
CSV_DANGEROUS = ("=", "+", "-", "@", "\t", "\r")
CSV_COLUMNS = ("source_file", "carrier", "invoice_number", "load_ref", "invoice_date",
               "amount_printed", "currency", "read_mode", "status", "codes", "reasons", "actions")

CSS = """
:root{--bg:#fff;--fg:#1a1a1a;--muted:#555;--line:#d0d0d0;--head:#f1f1f1;
--high:#b00020;--medium:#9a5b00;--low:#1f5f8b;--ok:#2e6b2e}
body{font-family:Segoe UI,Arial,sans-serif;background:var(--bg);color:var(--fg);
margin:0 auto;max-width:1200px;padding:24px;line-height:1.45}
h1{font-size:26px;margin:0 0 4px}h2{font-size:19px;margin:32px 0 8px;border-bottom:2px solid var(--line);padding-bottom:4px}
p.note{color:var(--muted);margin:4px 0 12px}
.wrap{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{border:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{background:var(--head)}
.badge{display:inline-block;padding:2px 8px;border-radius:3px;font-size:12px;font-weight:700;color:#fff;white-space:nowrap}
.high{background:var(--high)}.medium{background:var(--medium)}.low{background:var(--low)}.sin_hallazgos{background:var(--ok)}
code{font-size:13px}
"""


class _Raw(str):
    """Marks a string that is already safe HTML."""


@dataclass(frozen=True)
class InvoiceRow:
    source_file: str
    carrier: str
    invoice_number: str
    load_ref: str
    invoice_date: str
    amount_printed: str
    currency: str
    read_mode: str
    status: str
    findings: tuple[Finding, ...]


def safe_cell(value: object) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(CSV_DANGEROUS) else text


def build_rows(items: list[InvoiceInput], results: dict[str, list[Finding]]) -> list[InvoiceRow]:
    rows: list[InvoiceRow] = []
    for it in items:
        findings = results[it.source_file]
        x, v = it.extraction, it.verify
        if x is None:
            fields = ("", "", "", "", "", "")
        else:
            fields = tuple(f.value or "" for f in (x.carrier, x.invoice_number, x.load_ref,
                                                   x.invoice_date, x.amount_printed, x.currency))
        if v is None:
            read_mode = "no disponible"
        elif v.has_text_layer:
            read_mode = "texto del PDF verificado"
        else:
            read_mode = "lectura unica (imagen)"
        rows.append(InvoiceRow(it.source_file, *fields, read_mode, status_of(findings), tuple(findings)))
    return rows


def write_csv(path: Path, rows: list[InvoiceRow]) -> None:
    ordered = sorted(rows, key=lambda r: (STATUS_ORDER.index(r.status), r.source_file))
    with path.open("w", newline="", encoding="utf-8-sig") as handle:  # utf-8-sig writes the BOM
        writer = csv.writer(handle)
        writer.writerow(CSV_COLUMNS)
        for r in ordered:
            writer.writerow([safe_cell(c) for c in (
                r.source_file, r.carrier, r.invoice_number, r.load_ref, r.invoice_date,
                r.amount_printed, r.currency, r.read_mode, r.status,
                ";".join(f.code for f in r.findings),
                " | ".join(f.reason for f in r.findings),
                " | ".join(f.action for f in r.findings))])


def _cell(value: object) -> str:
    return str(value) if isinstance(value, _Raw) else html.escape(str(value))


def _tr(*cells: object) -> str:
    return "<tr>" + "".join(f"<td>{_cell(c)}</td>" for c in cells) + "</tr>"


def _table(headers: tuple[str, ...], body: list[str]) -> str:
    head = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    return f'<div class="wrap"><table><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def _badge(status: str) -> _Raw:
    return _Raw(f'<span class="badge {status.lower()}">{html.escape(LABELS[status])}</span>')


def render_html(rows: list[InvoiceRow], unmatched: list[Load], meta: dict) -> str:
    counts = {s: 0 for s in STATUS_ORDER}
    for r in rows:
        counts[r.status] += 1
    parts = [
        "<!DOCTYPE html>", '<html lang="es">', "<head>", '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>Reporte de conciliacion de facturas</title>", f"<style>{CSS}</style>",
        "</head>", "<body>",
        "<h1>Reporte de conciliacion de facturas</h1>",
        '<p class="note">Lista lo que una persona debe revisar y por que. La herramienta no aprueba ni paga nada.</p>',
        "<h2>Resumen</h2>",
        _table(("Estado", "Facturas"), [_tr(_badge(s), counts[s]) for s in STATUS_ORDER]
               + [_tr("Total de facturas", len(rows)),
                  _tr("Cargas del registro sin factura (informativo)", len(unmatched))]),
        "<h2>Excepciones por severidad</h2>",
    ]
    flat = sorted(((r, f) for r in rows for f in r.findings),
                  key=lambda p: (SEVERITY_ORDER[p[1].severity], p[0].source_file, p[1].code))
    if flat:
        parts.append(_table(("Severidad", "Factura", "Codigo", "Razon", "Accion sugerida"),
                            [_tr(_badge(f.severity), r.source_file, _Raw(f"<code>{html.escape(f.code)}</code>"),
                                 f.reason, f.action) for r, f in flat]))
    else:
        parts.append("<p>No hay excepciones.</p>")
    parts += [
        "<h2>Todas las facturas</h2>",
        _table(("Archivo", "Transportista", "No. factura", "Carga", "Fecha", "Monto impreso",
                "Moneda", "Lectura", "Estado", "Codigos"),
               [_tr(r.source_file, r.carrier or "-", r.invoice_number or "-", r.load_ref or "-",
                    r.invoice_date or "-", r.amount_printed or "-", r.currency or "-", r.read_mode,
                    _badge(r.status), ";".join(f.code for f in r.findings) or "-") for r in rows]),
        "<h2>Cargas del registro sin factura</h2>",
        '<p class="note">Informativo. No es una excepcion: puede que la factura aun no llegue.</p>',
    ]
    if unmatched:
        parts.append(_table(("Carga", "Embarque", "Transportista", "Ruta", "Producto", "Tarifa pactada"),
                            [_tr(ld.load_id, ld.ship_date.isoformat(), ld.carrier,
                                 f"{ld.origin} a {ld.destination}", ld.commodity,
                                 f"{ld.agreed_rate:,.2f} {ld.currency}") for ld in unmatched]))
    else:
        parts.append("<p>Todas las cargas tienen factura.</p>")
    meta_rows = [
        _tr("Modo", meta["mode"]),
        _tr("Modelo(s) de extraccion", ", ".join(meta["models"]) or "-"),
        _tr("Version del prompt", ", ".join(meta["prompt_versions"]) or "-"),
        _tr("Extracciones (primera a ultima)", f'{meta["extracted_first"] or "-"} a {meta["extracted_last"] or "-"}'),
        _tr("Reporte generado", meta["generated_at"]),
    ]
    for w in meta["warnings"]:
        meta_rows.append(_tr("Aviso", w))
    parts += ["<h2>Datos de la corrida</h2>", _table(("Dato", "Valor"), meta_rows), "</body>", "</html>"]
    return "\n".join(parts) + "\n"


def write_reports(output_dir: Path, rows: list[InvoiceRow], unmatched: list[Load],
                  meta: dict) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / "reporte.html"
    csv_path = output_dir / "reporte.csv"
    html_path.write_text(render_html(rows, unmatched, meta), encoding="utf-8")
    write_csv(csv_path, rows)
    return html_path, csv_path