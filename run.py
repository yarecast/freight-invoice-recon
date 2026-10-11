"""Entry point. Default: demo (reads extractions/, no network, no key). --live re-extracts with Gemini."""
import argparse
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from recon.cache import CacheError, read_cache, write_cache  # noqa: E402
from recon.config import ROOT, ConfigError, Settings, load_dotenv, load_settings  # noqa: E402
from recon.extract_llm import (ExtractionError, extract_invoice, load_prompt,  # noqa: E402
                               make_client, read_env)
from recon.ingest import ingest  # noqa: E402
from recon.matching import RegistryError, load_registry, match_invoice  # noqa: E402
from recon.report import LABELS, STATUS_ORDER, build_rows, write_reports  # noqa: E402
from recon.rules import InvoiceInput, evaluate, loads_without_invoice  # noqa: E402
from recon.verify import parse_iso_date, verify  # noqa: E402


def ingest_all(settings: Settings):
    return ingest(ROOT / "data" / "facturas",
                  settings.max_file_size_bytes / (1024 * 1024), settings.max_pages)


def run_live(settings: Settings, only_missing: bool) -> int:
    load_dotenv()
    api_key, model = read_env()
    files = ingest_all(settings)
    client = make_client(api_key, settings.request_timeout_s)
    prompt = load_prompt(settings.prompt_version)
    extractions_dir = ROOT / "extractions"
    done = failed = skipped = 0
    called = False
    for item in files:
        name = item.path.name
        if item.error:
            print(f"[omitido] {name}: {item.error}")
            failed += 1
            continue
        if only_missing:
            try:
                if read_cache(extractions_dir, item.path, item.sha256) is not None:
                    print(f"[ya existe] {name}")
                    skipped += 1
                    continue
            except CacheError:
                pass  # damaged JSON: extract again
        if called:
            time.sleep(settings.delay_between_calls_s)
        called = True
        try:
            extraction = extract_invoice(client, model, item.path, prompt, settings.max_retries)
        except ExtractionError as exc:
            print(f"[error] {name}: {exc}")
            failed += 1
            if exc.code == 429:
                print("Cuota agotada: se detiene la corrida para no gastar mas llamadas.")
                break
            continue
        write_cache(extractions_dir, item.path, item.sha256, model,
                    settings.prompt_version, extraction)
        print(f"[ok] {name}")
        done += 1
    print(f"Listo: {done} extraidas, {skipped} ya existian, {failed} con problemas.")
    return 0 if failed == 0 else 1


def make_report(settings: Settings, mode: str) -> None:
    registry = load_registry(ROOT / "data" / "registro_de_cargas.csv")
    items: list[InvoiceInput] = []
    metas: list[dict] = []
    warnings: list[str] = []
    for f in ingest_all(settings):
        name = f.path.name
        if f.error:
            items.append(InvoiceInput(name, None, None, None, f.error))
            continue
        try:
            entry = read_cache(ROOT / "extractions", f.path, f.sha256)
        except CacheError as exc:
            items.append(InvoiceInput(name, None, None, None, str(exc)))
            continue
        if entry is None:
            items.append(InvoiceInput(name, None, None, None))
            continue
        if entry.warning:
            warnings.append(entry.warning)
        metas.append(entry.meta)
        x = entry.extraction
        try:
            verified = verify(f.path, x)
        except Exception:
            items.append(InvoiceInput(name, None, None, None, "No se pudo leer el texto del PDF."))
            continue
        match = match_invoice(x.load_ref.value, parse_iso_date(x.invoice_date.value), x.carrier.value,
                              registry, settings.suggestion_window_days, settings.carrier_aliases)
        items.append(InvoiceInput(name, x, verified, match))

    results = evaluate(items, settings.amount_tolerance, settings.carrier_aliases)
    rows = build_rows(items, results)
    unmatched = loads_without_invoice(registry, items)
    dates = sorted(m["extracted_at"] for m in metas if m.get("extracted_at"))
    meta = {
        "mode": "demo (lee extractions/, sin red ni clave)" if mode == "demo"
                else "live (extraccion nueva con Gemini)",
        "models": sorted({m["model"] for m in metas if m.get("model")}),
        "prompt_versions": sorted({m["prompt_version"] for m in metas if m.get("prompt_version")}),
        "extracted_first": dates[0] if dates else None,
        "extracted_last": dates[-1] if dates else None,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "warnings": warnings,
    }
    html_path, csv_path = write_reports(ROOT / "output", rows, unmatched, meta)
    counts = Counter(r.status for r in rows)
    print(f"Reporte generado en modo {mode}: {len(rows)} facturas.")
    print("  " + " | ".join(f"{LABELS[s]}: {counts[s]}" for s in STATUS_ORDER))
    print(f"  Cargas sin factura (informativo): {len(unmatched)}")
    for w in warnings:
        print(f"  Aviso: {w}")
    print(f"  {html_path.relative_to(ROOT)}")
    print(f"  {csv_path.relative_to(ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Conciliacion de facturas de transportistas.")
    parser.add_argument("--live", action="store_true",
                        help="Extraer de nuevo con Gemini (necesita GEMINI_API_KEY y GEMINI_MODEL).")
    parser.add_argument("--only-missing", action="store_true",
                        help="Con --live: saltar los PDFs que ya tienen JSON en extractions/.")
    args = parser.parse_args()
    if args.only_missing and not args.live:
        parser.error("--only-missing solo se usa junto con --live.")
    try:
        settings = load_settings()
        if args.live:
            status = run_live(settings, args.only_missing)
            make_report(settings, "live")
            return status
        make_report(settings, "demo")
        return 0
    except (ConfigError, RegistryError) as exc:
        print(f"Error: {exc}")
        return 1
    except OSError:
        print("Error: no se pudo leer o escribir un archivo del proyecto "
              "(revisa las carpetas data/, extractions/ y output/).")
        return 1


if __name__ == "__main__":
    sys.exit(main())