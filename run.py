"""Entry point. For now only --live (re-extract with Gemini). Demo mode is added in M4."""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from recon.cache import CacheError, read_cache, write_cache  # noqa: E402
from recon.config import ROOT, ConfigError, load_dotenv, load_settings  # noqa: E402
from recon.extract_llm import (ExtractionError, extract_invoice, load_prompt,  # noqa: E402
                               make_client, read_env)
from recon.ingest import ingest  # noqa: E402


def run_live(only_missing: bool) -> int:
    load_dotenv()
    settings = load_settings()
    api_key, model = read_env()
    files = ingest(ROOT / "data" / "facturas",
                   settings.max_file_size_bytes / (1024 * 1024), settings.max_pages)
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Conciliacion de facturas de transportistas.")
    parser.add_argument("--live", action="store_true",
                        help="Extraer de nuevo con Gemini (necesita GEMINI_API_KEY y GEMINI_MODEL).")
    parser.add_argument("--only-missing", action="store_true",
                        help="Con --live: saltar los PDFs que ya tienen JSON en extractions/.")
    args = parser.parse_args()
    if not args.live:
        print("El modo demo se agrega en M4. Por ahora usa: python run.py --live")
        return 0
    try:
        return run_live(args.only_missing)
    except ConfigError as exc:
        print(f"Error de configuracion: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())