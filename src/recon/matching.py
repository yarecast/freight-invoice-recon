"""Load the register and match invoices to loads. Exact matching only; suggestions are informational."""
import csv
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

REQUIRED_COLUMNS = ("load_id", "ship_date", "carrier", "origin", "destination",
                    "commodity", "agreed_rate", "currency")
_LOAD_REF_RE = re.compile(r"TRQ[\s\-_]*(\d{4})")
_DASHES = "\u2010\u2011\u2012\u2013\u2014\u2212"
_SUFFIX_RE = re.compile(r"(?: (?:s a de c v|sa de cv|inc|llc))+$")


class RegistryError(Exception):
    """The load register cannot be used. The message is in Spanish."""


@dataclass(frozen=True)
class Load:
    load_id: str
    ship_date: date
    carrier: str
    origin: str
    destination: str
    commodity: str
    agreed_rate: Decimal
    currency: str


@dataclass(frozen=True)
class MatchResult:
    load_ref: str | None  # normalized reference as read from the invoice
    load: Load | None  # None means no match
    suggestions: tuple[Load, ...]  # informational only, never auto-accepted


def normalize_load_ref(text: str | None) -> str | None:
    if text is None:
        return None
    cleaned = text.strip().upper()
    for dash in _DASHES:
        cleaned = cleaned.replace(dash, "-")
    found = _LOAD_REF_RE.fullmatch(cleaned)
    if found:
        return f"TRQ-{found.group(1)}"
    return cleaned or None


def normalize_name(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    no_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    words = " ".join(re.sub(r"[^a-z0-9]+", " ", no_accents.lower()).split())
    return _SUFFIX_RE.sub("", words)


def same_carrier(a: str, b: str, aliases: dict[str, list[str]]) -> bool:
    norm_a, norm_b = normalize_name(a), normalize_name(b)
    if norm_a == norm_b:
        return True
    for canonical, others in aliases.items():
        group = {normalize_name(canonical), *(normalize_name(x) for x in others)}
        if norm_a in group and norm_b in group:
            return True
    return False


def load_registry(path: Path) -> list[Load]:
    try:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
            if missing:
                raise RegistryError(f"Al registro le faltan columnas: {', '.join(missing)}.")
            loads: list[Load] = []
            seen: set[str] = set()
            for number, row in enumerate(reader, start=2):
                try:
                    load = Load(
                        load_id=normalize_load_ref(row["load_id"]) or "",
                        ship_date=date.fromisoformat(row["ship_date"].strip()),
                        carrier=row["carrier"].strip(),
                        origin=row["origin"].strip(),
                        destination=row["destination"].strip(),
                        commodity=row["commodity"].strip(),
                        agreed_rate=Decimal(row["agreed_rate"].strip()),
                        currency=row["currency"].strip().upper(),
                    )
                except (ValueError, InvalidOperation, AttributeError):
                    raise RegistryError(f"La fila {number} del registro tiene un valor invalido.") from None
                if not load.load_id or load.load_id in seen:
                    raise RegistryError(f"La fila {number} del registro tiene un load_id vacio o repetido.")
                seen.add(load.load_id)
                loads.append(load)
            return loads
    except OSError:
        raise RegistryError(f"No se pudo leer el registro de cargas: {path.name}.") from None


def suggest_loads(registry: list[Load], carrier: str | None, invoice_date: date | None,
                  window_days: int, aliases: dict[str, list[str]]) -> tuple[Load, ...]:
    if not carrier or invoice_date is None:
        return ()
    close = [ld for ld in registry
             if same_carrier(carrier, ld.carrier, aliases)
             and abs((ld.ship_date - invoice_date).days) <= window_days]
    close.sort(key=lambda ld: (abs((ld.ship_date - invoice_date).days), ld.load_id))
    return tuple(close)


def match_invoice(load_ref: str | None, invoice_date: date | None, carrier: str | None,
                  registry: list[Load], window_days: int,
                  aliases: dict[str, list[str]]) -> MatchResult:
    ref = normalize_load_ref(load_ref)
    by_id = {ld.load_id: ld for ld in registry}
    load = by_id.get(ref) if ref else None
    if load is not None:
        return MatchResult(ref, load, ())
    return MatchResult(ref, None, suggest_loads(registry, carrier, invoice_date, window_days, aliases))