"""List and validate invoice PDFs. A bad file becomes a result with an error, never a crash."""
import hashlib
from dataclasses import dataclass
from pathlib import Path

import pymupdf


@dataclass(frozen=True)
class IngestedFile:
    path: Path
    sha256: str | None
    page_count: int | None
    error: str | None  # reason in Spanish; None when the file is usable


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check(path: Path, max_file_size_mb: float, max_pages: int) -> IngestedFile:
    try:
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > max_file_size_mb:
            return IngestedFile(path, None, None,
                f"El archivo pesa {size_mb:.1f} MB y el limite es {max_file_size_mb} MB.")
        with pymupdf.open(path) as doc:
            if doc.needs_pass:
                return IngestedFile(path, None, None, "El PDF esta protegido con contrasena.")
            pages = doc.page_count
        if pages < 1 or pages > max_pages:
            return IngestedFile(path, None, pages,
                f"El PDF tiene {pages} paginas y el limite es {max_pages}.")
        return IngestedFile(path, sha256_of(path), pages, None)
    except Exception:
        return IngestedFile(path, None, None, "No se pudo abrir el archivo como PDF.")


def ingest(folder: Path, max_file_size_mb: float, max_pages: int) -> list[IngestedFile]:
    pdfs = sorted(p for p in folder.iterdir() if p.suffix.lower() == ".pdf")
    return [_check(p, max_file_size_mb, max_pages) for p in pdfs]