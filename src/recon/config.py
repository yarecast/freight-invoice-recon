"""Configuration: config.toml settings and .env loading."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class ConfigError(Exception):
    """Expected configuration problem. The message is shown to the user (Spanish)."""


@dataclass(frozen=True)
class Settings:
    max_file_size_bytes: int
    max_pages: int
    amount_tolerance: Decimal
    suggestion_window_days: int
    prompt_version: str
    request_timeout_s: int
    delay_between_calls_s: float
    max_retries: int
    carrier_aliases: dict[str, list[str]]


def load_dotenv(path: Path | None = None) -> None:
    """Load KEY=VALUE lines from .env into os.environ without overriding existing values."""
    path = path or ROOT / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip())


def load_settings(path: Path | None = None) -> Settings:
    path = path or ROOT / "config.toml"
    try:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    except FileNotFoundError:
        raise ConfigError(f"No se encontró el archivo de configuración: {path.name}") from None
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"El archivo {path.name} tiene un error de formato: {exc}") from None

    try:
        return Settings(
            max_file_size_bytes=int(float(raw["limits"]["max_file_size_mb"]) * 1024 * 1024),
            max_pages=int(raw["limits"]["max_pages"]),
            amount_tolerance=Decimal(str(raw["matching"]["amount_tolerance"])),
            suggestion_window_days=int(raw["matching"]["suggestion_window_days"]),
            prompt_version=str(raw["extraction"]["prompt_version"]),
            request_timeout_s=int(raw["extraction"]["request_timeout_s"]),
            delay_between_calls_s=float(raw["extraction"]["delay_between_calls_s"]),
            max_retries=int(raw["extraction"]["max_retries"]),
            carrier_aliases={k: list(v) for k, v in raw.get("carrier_aliases", {}).items()},
        )
    except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
        raise ConfigError(
            f"Falta un valor o es inválido en {path.name}: {type(exc).__name__} {exc}"
        ) from None