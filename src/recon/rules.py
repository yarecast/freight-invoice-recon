"""Business rules. Deterministic: every finding comes from code, never from the LLM."""
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .matching import Load, MatchResult, normalize_name, same_carrier
from .models import InvoiceExtraction
from .verify import VerifyResult, parse_amount

HIGH, MEDIUM, LOW = "HIGH", "MEDIUM", "LOW"
SEVERITY_ORDER = {HIGH: 0, MEDIUM: 1, LOW: 2}
NO_FINDINGS = "SIN_HALLAZGOS"  # never "approved": the tool does not approve anything

# Only normalizes currency TEXT that is printed on the invoice. It never infers a missing one.
_CURRENCY_TEXT = {
    "MXN": {"mxn", "mn", "peso", "pesos", "peso mexicano", "pesos mexicanos"},
    "USD": {"usd", "us", "dolar", "dolares", "dolares americanos", "dls", "dlls", "dollar", "dollars"},
}


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    reason: str  # plain Spanish
    action: str  # suggested action, plain Spanish


@dataclass(frozen=True)
class InvoiceInput:
    source_file: str
    extraction: InvoiceExtraction | None
    verify: VerifyResult | None
    match: MatchResult | None
    file_error: str | None = None


def money(value: Decimal) -> str:
    return f"{value:,.2f}"


def normalize_currency(text: str) -> str:
    key = normalize_name(text)
    for code, names in _CURRENCY_TEXT.items():
        if key in names:
            return code
    return text.strip().upper()


def annotated_amounts(extraction: InvoiceExtraction) -> list[Decimal]:
    found: list[Decimal] = []
    for note in extraction.handwritten_annotations:
        for text in note.amounts:
            amount = parse_amount(text)
            if amount is not None:
                found.append(amount)
    return found


_NUMERIC_DATE_RE = re.compile(r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})")


def _date_reason(x: InvoiceExtraction, invoice_date: date, ship_date: date) -> str:
    text = f"La factura tiene fecha {invoice_date.isoformat()}"
    evidence = (x.invoice_date.evidence or "").strip()
    found = _NUMERIC_DATE_RE.search(evidence)
    if found:
        a, b, year = int(found.group(1)), int(found.group(2)), int(found.group(3))
        if a <= 12 and b <= 12 and a != b:
            text += f" (el PDF dice '{evidence}', formato ambiguo: puede ser dia/mes o mes/dia)"
            if date(year, a, b) < ship_date and date(year, b, a) < ship_date:
                text += f" y la carga salio el {ship_date.isoformat()}. Con cualquiera de las dos lecturas es anterior al embarque."
                return text
    return text + f" y la carga salio el {ship_date.isoformat()}."


def _annotation_reason(x: InvoiceExtraction, printed_text: str, extra: list[Decimal], load: Load) -> str:
    notes = "; ".join(f"'{n.text}'" for n in x.handwritten_annotations)
    top = max(extra)
    diff = top - load.agreed_rate
    return (f"Monto impreso {printed_text}, pactado {money(load.agreed_rate)} {load.currency}. "
            f"Notas manuscritas leidas: {notes}. "
            f"El mayor monto manuscrito ({money(top)}) se toma como total manuscrito, {diff:+,.2f} contra lo pactado.")


def _carrier_key(name: str, aliases: dict[str, list[str]]) -> str:
    for canonical in aliases:
        if same_carrier(name, canonical, aliases):
            return normalize_name(canonical)
    return normalize_name(name)


def _invoice_findings(item: InvoiceInput, tolerance: Decimal,
                      aliases: dict[str, list[str]]) -> list[Finding]:
    if item.file_error or item.extraction is None or item.verify is None or item.match is None:
        reason = item.file_error or "No hay una extraccion guardada para este archivo."
        return [Finding("FILE_UNREADABLE", MEDIUM, reason,
                        "Revisar el archivo a mano o pedir una copia legible al transportista.")]
    x, v, m = item.extraction, item.verify, item.match
    out: list[Finding] = []

    # Missing or unreadable fields
    problems: list[str] = []
    if not x.carrier.value:
        problems.append("transportista")
    if not x.invoice_number.value:
        problems.append("numero de factura")
    if not x.load_ref.value:
        problems.append("referencia de carga")
    elif not v.load_ref_format_ok:
        problems.append("referencia de carga (formato invalido)")
    if x.amount_printed.value is None:
        problems.append("monto")
    elif v.amount is None:
        problems.append("monto (formato no reconocido)")
    if x.invoice_date.value is None:
        problems.append("fecha de factura")
    elif v.invoice_date is None:
        problems.append("fecha de factura (formato no reconocido)")
    if problems:
        out.append(Finding("MISSING_FIELD", MEDIUM,
                           "Falta o no se pudo interpretar: " + ", ".join(problems) + ".",
                           "Revisar la factura a mano y completar el dato."))

    # Cross-check against the PDF text layer
    if v.mismatched_fields:
        labels = {"invoice_number": "numero de factura", "load_ref": "referencia de carga",
                  "amount_printed": "monto"}
        names = ", ".join(labels[f] for f in v.mismatched_fields)
        out.append(Finding("EXTRACTION_MISMATCH", MEDIUM,
                           f"Lo leido por el modelo no aparece en el texto del PDF: {names}.",
                           "Comparar la factura a mano contra la lectura del sistema."))

    # Photo or scan with a single read and a legibility problem
    notes = (x.legibility_notes or "").strip()
    if not v.has_text_layer and notes:
        out.append(Finding("SINGLE_READ_LOW_LEGIBILITY", MEDIUM,
                           "Es una foto o escaneo con una sola lectura y el modelo reporto problemas de legibilidad.",
                           "Revisar la imagen a mano antes de confiar en los datos."))

    # No load match: stop here, there is nothing to compare against
    if m.load is None:
        if m.load_ref:
            reason = f"La referencia de carga {m.load_ref} no existe en el registro."
        else:
            reason = "La factura no trae referencia de carga, no se puede ligar a una carga."
        if m.suggestions:
            ids = ", ".join(ld.load_id for ld in m.suggestions)
            reason += (" Cargas posibles del mismo transportista con fechas cercanas "
                       f"(solo sugerencia, no se aceptan solas): {ids}.")
        out.append(Finding("NO_LOAD_MATCH", HIGH, reason,
                           "Buscar la carga correcta con el transportista y no pagar hasta confirmarla."))
        return out

    load: Load = m.load

    if x.carrier.value and not same_carrier(x.carrier.value, load.carrier, aliases):
        out.append(Finding("CARRIER_MISMATCH", HIGH,
                           f"La factura dice '{x.carrier.value}' y el registro dice '{load.carrier}' para {load.load_id}.",
                           "Confirmar que el transportista de la factura es el de la carga."))

    currency_ok = True
    printed_currency = (x.currency.value or "").strip()
    if not printed_currency:
        out.append(Finding("CURRENCY_NOT_PRINTED", LOW,
                           f"La factura no imprime la moneda. Se compara suponiendo {load.currency}, la del registro.",
                           "Confirmar la moneda con el transportista si el monto es relevante."))
    else:
        currency = normalize_currency(printed_currency)
        if currency != load.currency:
            currency_ok = False
            out.append(Finding("CURRENCY_MISMATCH", HIGH,
                               f"La factura esta en {currency} y la carga se pacto en {load.currency}. No se compara el monto.",
                               "Pedir al transportista que corrija la moneda o confirmar el cambio."))

    if v.amount is not None and currency_ok and abs(v.amount - load.agreed_rate) > tolerance:
        diff = v.amount - load.agreed_rate
        out.append(Finding("AMOUNT_MISMATCH", HIGH,
                           f"Monto impreso {money(v.amount)} {load.currency}, pactado {money(load.agreed_rate)} {load.currency}, diferencia {diff:+,.2f}.",
                           "No pagar la diferencia sin una aprobacion. Pedir aclaracion al transportista."))

    extra = [a for a in annotated_amounts(x) if v.amount is None or a != v.amount]
    if extra:
        printed_text = money(v.amount) if v.amount is not None else "no legible"
        out.append(Finding("ANNOTATED_AMOUNT", HIGH,
                           _annotation_reason(x, printed_text, extra, load),
                           "Pedir sustento del cargo extra y autorizarlo por escrito antes de pagar."))

    if v.invoice_date is not None and v.invoice_date < load.ship_date:
        out.append(Finding("INVOICE_BEFORE_SHIPMENT", MEDIUM,
                           _date_reason(x, v.invoice_date, load.ship_date),
                           "Revisar la fecha de la factura: cobrar antes del embarque es inusual."))
    return out


def _duplicates(items: list[InvoiceInput], aliases: dict[str, list[str]]) -> dict[str, list[Finding]]:
    by_load: dict[str, list[str]] = defaultdict(list)
    by_number: dict[tuple[str, str], list[str]] = defaultdict(list)
    for it in items:
        if it.extraction is None or it.match is None:
            continue
        if it.match.load is not None:
            by_load[it.match.load.load_id].append(it.source_file)
        number = (it.extraction.invoice_number.value or "").strip().upper()  # leading zeros kept
        carrier = it.extraction.carrier.value
        if number and carrier:
            by_number[(_carrier_key(carrier, aliases), number)].append(it.source_file)

    same_number: dict[str, set[str]] = {}  # file -> files that repeat its invoice number
    for files in by_number.values():
        if len(files) > 1:
            for f in files:
                same_number[f] = set(files)

    out: dict[str, list[Finding]] = defaultdict(list)
    for load_id, files in by_load.items():
        if len(files) > 1:
            # If every file on this load repeats the same invoice number, the number
            # duplicate already explains it: do not emit a second finding for the load.
            if all(same_number.get(f) == set(files) for f in files):
                continue
            for f in files:
                others = ", ".join(o for o in files if o != f)
                out[f].append(Finding("DUPLICATE_LOAD_INVOICE", HIGH,
                                      f"La carga {load_id} tiene mas de una factura. Tambien aparece en: {others}.",
                                      "Confirmar cual factura es la valida y rechazar la otra para no pagar dos veces."))
    for (_, number), files in by_number.items():
        if len(files) > 1:
            for f in files:
                others = ", ".join(o for o in files if o != f)
                out[f].append(Finding("DUPLICATE_INVOICE_NUMBER", HIGH,
                                      f"El numero de factura {number} aparece en mas de un archivo (tambien en: {others}). Parece la misma factura recibida dos veces.",
                                      "Conservar una sola copia y pagar una vez."))
    return out


def evaluate(items: list[InvoiceInput], tolerance: Decimal,
             aliases: dict[str, list[str]]) -> dict[str, list[Finding]]:
    duplicates = _duplicates(items, aliases)
    result: dict[str, list[Finding]] = {}
    for it in items:
        findings = _invoice_findings(it, tolerance, aliases) + duplicates.get(it.source_file, [])
        findings.sort(key=lambda f: (SEVERITY_ORDER[f.severity], f.code))
        result[it.source_file] = findings
    return result


def status_of(findings: list[Finding]) -> str:
    if not findings:
        return NO_FINDINGS
    return min((f.severity for f in findings), key=lambda s: SEVERITY_ORDER[s])


def loads_without_invoice(registry: list[Load], items: list[InvoiceInput]) -> list[Load]:
    """Informational only, not an exception."""
    used = {it.match.load.load_id for it in items if it.match and it.match.load}
    return [ld for ld in registry if ld.load_id not in used]