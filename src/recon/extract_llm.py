"""Gemini extraction. The LLM only reads the invoice; it never matches or decides."""
import os
import time
from pathlib import Path

from google import genai
from google.genai import errors, types

from .config import ROOT, ConfigError
from .models import InvoiceExtraction

RETRYABLE_CODES = {500, 502, 503, 504}  # 429 is a quota: retrying only burns requests


class ExtractionError(Exception):
    """Extraction failed. The message is in Spanish and never contains the API key."""

    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.code = code


def read_env() -> tuple[str, str]:
    """Return (api_key, model) from environment variables, or raise a friendly ConfigError."""
    model = os.environ.get("GEMINI_MODEL")
    key = os.environ.get("GEMINI_API_KEY")
    if not model:
        raise ConfigError("Falta GEMINI_MODEL. Definela en tu archivo .env (ver .env.example).")
    if not key:
        raise ConfigError("Falta GEMINI_API_KEY. Definela en tu archivo .env (ver .env.example).")
    return key, model


def load_prompt(version: str) -> str:
    return (ROOT / "prompts" / f"extract_{version}.md").read_text(encoding="utf-8")


def make_client(api_key: str, timeout_s: float) -> genai.Client:
    return genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=int(timeout_s * 1000)))


def extract_invoice(client: genai.Client, model: str, pdf_path: Path,
                    prompt: str, max_retries: int) -> InvoiceExtraction:
    pdf_part = types.Part.from_bytes(data=pdf_path.read_bytes(), mime_type="application/pdf")
    config = types.GenerateContentConfig(
        temperature=0,
        response_mime_type="application/json",
        response_schema=InvoiceExtraction,
    )
    response = None
    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(model=model, contents=[pdf_part, prompt], config=config)
            break
        except errors.APIError as exc:
            if exc.code not in RETRYABLE_CODES or attempt == max_retries:
                raise ExtractionError(f"La API devolvio el codigo {exc.code}.", exc.code) from None
        except Exception as exc:  # timeouts and network failures
            if attempt == max_retries:
                raise ExtractionError(f"Fallo de red o tiempo de espera ({type(exc).__name__}).") from None
        time.sleep(5 * 2 ** attempt)  # backoff: 5, 10, 20, 40 s
    parsed = response.parsed if response is not None else None
    if not isinstance(parsed, InvoiceExtraction):
        raise ExtractionError("El modelo no devolvio un JSON valido segun el esquema.")
    return parsed