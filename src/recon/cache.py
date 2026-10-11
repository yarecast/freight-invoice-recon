"""Cache of real model output: extractions/<pdf_stem>.json. Demo mode reads only these files."""
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .models import InvoiceExtraction

META_KEYS = ("source_file", "source_sha256", "extracted_at", "model", "prompt_version")


class CacheError(Exception):
    """A cached JSON exists but cannot be used. The message is in Spanish."""


@dataclass(frozen=True)
class CacheEntry:
    meta: dict
    extraction: InvoiceExtraction
    warning: str | None  # set when the PDF changed after the extraction


def cache_path(extractions_dir: Path, pdf_path: Path) -> Path:
    return extractions_dir / f"{pdf_path.stem}.json"


def write_cache(extractions_dir: Path, pdf_path: Path, sha256: str, model: str,
                prompt_version: str, extraction: InvoiceExtraction) -> Path:
    record = {
        "source_file": pdf_path.name,
        "source_sha256": sha256,
        "extracted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": model,
        "prompt_version": prompt_version,
        **extraction.model_dump(),
    }
    extractions_dir.mkdir(parents=True, exist_ok=True)
    path = cache_path(extractions_dir, pdf_path)
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def read_cache(extractions_dir: Path, pdf_path: Path, current_sha256: str | None) -> CacheEntry | None:
    path = cache_path(extractions_dir, pdf_path)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        extraction = InvoiceExtraction.model_validate(raw)
    except (ValueError, OSError):
        raise CacheError(f"No se pudo leer {path.name}: esta danado o no coincide con el esquema.") from None
    meta = {key: raw.get(key) for key in META_KEYS}
    warning = None
    if current_sha256 is not None and meta["source_sha256"] != current_sha256:
        warning = (f"El PDF {pdf_path.name} cambio desde que se extrajo "
                   f"(el hash no coincide con {path.name}). Conviene correr --live otra vez.")
    return CacheEntry(meta, extraction, warning)