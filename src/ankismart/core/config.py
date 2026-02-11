from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel

from ankismart.core.crypto import decrypt, encrypt
from ankismart.core.errors import ConfigError, ErrorCode
from ankismart.core.logging import get_logger

logger = get_logger("config")

CONFIG_DIR: Path = Path.home() / ".ankismart"
CONFIG_PATH: Path = CONFIG_DIR / "config.yaml"

_ENCRYPTED_FIELDS: set[str] = {"openai_api_key", "deepseek_api_key", "anki_connect_key"}
_ENCRYPTED_PREFIX: str = "encrypted:"


class AppConfig(BaseModel):
    llm_provider: str = "openai"  # "openai" or "deepseek"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    anki_connect_url: str = "http://127.0.0.1:8765"
    anki_connect_key: str = ""
    default_deck: str = "Default"
    default_tags: list[str] = ["ankismart"]
    ocr_correction: bool = False
    log_level: str = "INFO"


def load_config() -> AppConfig:
    """Load configuration from YAML file.

    Returns a default ``AppConfig`` when the file does not exist.  Encrypted
    fields are transparently decrypted; decryption failures fall back to an
    empty string so the application can still start.
    """
    if not CONFIG_PATH.exists():
        logger.info("Config file not found, using defaults", extra={"path": str(CONFIG_PATH)})
        return AppConfig()

    try:
        raw = CONFIG_PATH.read_text(encoding="utf-8")
        data: dict = yaml.safe_load(raw) or {}
    except Exception as exc:
        raise ConfigError(
            f"Failed to read config file: {exc}",
            code=ErrorCode.E_CONFIG_INVALID,
        ) from exc

    # Decrypt encrypted fields
    for field in _ENCRYPTED_FIELDS:
        value = data.get(field, "")
        if isinstance(value, str) and value.startswith(_ENCRYPTED_PREFIX):
            ciphertext = value[len(_ENCRYPTED_PREFIX):]
            try:
                data[field] = decrypt(ciphertext)
            except Exception:
                logger.warning(
                    "Failed to decrypt field, resetting to empty",
                    extra={"field": field},
                )
                data[field] = ""

    try:
        return AppConfig(**data)
    except Exception as exc:
        raise ConfigError(
            f"Invalid configuration values: {exc}",
            code=ErrorCode.E_CONFIG_INVALID,
        ) from exc


def save_config(config: AppConfig) -> None:
    """Encrypt sensitive fields and persist configuration as YAML."""
    data = config.model_dump()

    # Encrypt sensitive fields
    for field in _ENCRYPTED_FIELDS:
        value = data.get(field, "")
        if value:
            data[field] = _ENCRYPTED_PREFIX + encrypt(value)

    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            yaml.safe_dump(data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
        logger.info("Configuration saved", extra={"path": str(CONFIG_PATH)})
    except Exception as exc:
        raise ConfigError(
            f"Failed to save config file: {exc}",
            code=ErrorCode.E_CONFIG_INVALID,
        ) from exc
