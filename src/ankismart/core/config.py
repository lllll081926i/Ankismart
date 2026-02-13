from __future__ import annotations

import os
import sys
import threading
import uuid
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from ankismart.core.crypto import decrypt, encrypt
from ankismart.core.errors import ConfigError, ErrorCode
from ankismart.core.logging import get_logger

logger = get_logger("config")


def _resolve_project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def _is_portable_mode() -> bool:
    """检查是否为便携版模式"""
    root = _resolve_project_root()
    portable_flag = root / ".portable"
    return portable_flag.exists()


def _resolve_app_dir() -> Path:
    """解析应用数据目录

    优先级:
    1. 环境变量 ANKISMART_APP_DIR
    2. 便携版模式: 应用目录下的 config/
    3. 开发模式: 项目根目录下的 .local/ankismart/
    4. 安装版: 用户本地数据目录
    """
    # 环境变量优先
    env_app_dir = os.getenv("ANKISMART_APP_DIR", "").strip()
    if env_app_dir:
        return Path(env_app_dir).expanduser().resolve()

    root = _resolve_project_root()

    # 便携版模式
    if _is_portable_mode():
        logger.info("Running in portable mode")
        return root / "config"

    # 打包后的安装版
    if getattr(sys, "frozen", False):
        # Windows: %LOCALAPPDATA%\ankismart
        # Linux/Mac: ~/.local/share/ankismart
        if sys.platform == "win32":
            app_data = Path(os.getenv("LOCALAPPDATA", "~/.local"))
        else:
            app_data = Path.home() / ".local" / "share"
        return (app_data / "ankismart").expanduser().resolve()

    # 开发模式
    return root / ".local" / "ankismart"


CONFIG_DIR: Path = _resolve_app_dir()
CONFIG_PATH: Path = Path(
    os.getenv("ANKISMART_CONFIG_PATH", str(CONFIG_DIR / "config.yaml"))
).expanduser().resolve()

_ENCRYPTED_FIELDS: set[str] = {"anki_connect_key", "ocr_cloud_api_key"}
_ENCRYPTED_PREFIX: str = "encrypted:"

_CONFIG_CACHE_LOCK = threading.Lock()
_CONFIG_CACHE: dict[str, object] = {
    "path": "",
    "exists": False,
    "mtime_ns": None,
    "config": None,
}

KNOWN_PROVIDERS: dict[str, str] = {
    "OpenAI": "https://api.openai.com/v1",
    "DeepSeek": "https://api.deepseek.com",
    "Moonshot": "https://api.moonshot.cn/v1",
    "智谱 (Zhipu)": "https://open.bigmodel.cn/api/paas/v4",
    "通义千问 (Qwen)": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "Ollama (本地)": "http://localhost:11434/v1",
}


class LLMProviderConfig(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    rpm_limit: int = 0


class AppConfig(BaseModel):
    llm_providers: list[LLMProviderConfig] = []
    active_provider_id: str = ""
    anki_connect_url: str = "http://127.0.0.1:8765"
    anki_connect_key: str = ""
    default_deck: str = "Default"
    default_tags: list[str] = ["ankismart"]
    ocr_correction: bool = False
    ocr_mode: str = "local"  # "local" or "cloud" (cloud mode is frontend-only for now)
    ocr_model_tier: str = "lite"  # "lite" | "standard" | "accuracy"
    ocr_model_source: str = "official"  # "official" | "cn_mirror"
    ocr_auto_cuda_upgrade: bool = True
    ocr_model_locked_by_user: bool = False
    ocr_cuda_checked_once: bool = False
    ocr_cloud_provider: str = ""
    ocr_cloud_endpoint: str = ""
    ocr_cloud_api_key: str = ""
    log_level: str = "INFO"
    llm_temperature: float = 0.3
    llm_max_tokens: int = 0  # 0 means use provider default

    # Persistence: last-used values
    last_deck: str = ""
    last_tags: str = ""
    last_strategy: str = ""
    last_update_mode: str = ""
    window_geometry: str = ""  # hex-encoded QByteArray
    proxy_url: str = ""
    theme: str = "light"
    language: str = "zh"

    # Experimental features
    enable_auto_split: bool = False  # Experimental: Auto-split long documents
    split_threshold: int = 70000  # Character count threshold for splitting

    # Performance statistics
    total_files_processed: int = 0
    total_conversion_time: float = 0.0
    total_generation_time: float = 0.0
    total_cards_generated: int = 0

    # Duplicate check settings
    duplicate_scope: str = "deck"  # "deck" or "collection"
    duplicate_check_model: bool = True
    allow_duplicate: bool = False

    @property
    def active_provider(self) -> LLMProviderConfig | None:
        for p in self.llm_providers:
            if p.id == self.active_provider_id:
                return p
        return self.llm_providers[0] if self.llm_providers else None


def _migrate_legacy(data: dict) -> dict:
    """Migrate old hardcoded provider fields to llm_providers list."""
    if "llm_providers" in data:
        return data

    # Detect legacy format by presence of old fields
    old_keys = {
        "openai_api_key", "deepseek_api_key",
        "llm_provider", "openai_model", "deepseek_model",
    }
    if not old_keys & data.keys():
        return data

    providers: list[dict] = []
    active_id = ""

    active_provider = data.pop("llm_provider", "openai")

    openai_key = data.pop("openai_api_key", "")
    openai_model = data.pop("openai_model", "gpt-4o")
    if openai_key or active_provider == "openai":
        oid = uuid.uuid4().hex[:12]
        providers.append({
            "id": oid,
            "name": "OpenAI",
            "api_key": openai_key,
            "base_url": KNOWN_PROVIDERS["OpenAI"],
            "model": openai_model,
            "rpm_limit": 0,
        })
        if active_provider == "openai":
            active_id = oid

    ds_key = data.pop("deepseek_api_key", "")
    ds_model = data.pop("deepseek_model", "deepseek-chat")
    if ds_key or active_provider == "deepseek":
        did = uuid.uuid4().hex[:12]
        providers.append({
            "id": did,
            "name": "DeepSeek",
            "api_key": ds_key,
            "base_url": KNOWN_PROVIDERS["DeepSeek"],
            "model": ds_model,
            "rpm_limit": 0,
        })
        if active_provider == "deepseek":
            active_id = did

    data["llm_providers"] = providers
    data["active_provider_id"] = active_id
    logger.info("Migrated legacy config to llm_providers format")
    return data


def _decrypt_field(value: str, field_name: str) -> str:
    if isinstance(value, str) and value.startswith(_ENCRYPTED_PREFIX):
        ciphertext = value[len(_ENCRYPTED_PREFIX):]
        try:
            return decrypt(ciphertext)
        except Exception as e:
            logger.warning(
                f"Failed to decrypt field, resetting to empty: {e}",
                extra={"field": field_name},
            )
            return ""
    return value


def _read_cached_config(path: Path, exists: bool, mtime_ns: int | None) -> AppConfig | None:
    """Return cached config snapshot when file state is unchanged."""
    cache_path = str(path)
    with _CONFIG_CACHE_LOCK:
        if (
            _CONFIG_CACHE["path"] == cache_path
            and _CONFIG_CACHE["exists"] == exists
            and _CONFIG_CACHE["mtime_ns"] == mtime_ns
            and isinstance(_CONFIG_CACHE["config"], AppConfig)
        ):
            return _CONFIG_CACHE["config"].model_copy(deep=True)
    return None


def _update_config_cache(path: Path, exists: bool, mtime_ns: int | None, config: AppConfig) -> None:
    """Persist latest config snapshot in memory cache."""
    with _CONFIG_CACHE_LOCK:
        _CONFIG_CACHE["path"] = str(path)
        _CONFIG_CACHE["exists"] = exists
        _CONFIG_CACHE["mtime_ns"] = mtime_ns
        _CONFIG_CACHE["config"] = config.model_copy(deep=True)


def load_config() -> AppConfig:
    """Load configuration from YAML file.

    Returns a default ``AppConfig`` when the file does not exist.  Encrypted
    fields are transparently decrypted; decryption failures fall back to an
    empty string so the application can still start.
    """
    config_path = CONFIG_PATH
    exists = config_path.exists()
    mtime_ns = config_path.stat().st_mtime_ns if exists else None

    cached = _read_cached_config(config_path, exists, mtime_ns)
    if cached is not None:
        return cached

    if not exists:
        logger.info("Config file not found, using defaults", extra={"path": str(config_path)})
        default_config = AppConfig()
        _update_config_cache(config_path, False, None, default_config)
        return default_config

    try:
        raw = config_path.read_text(encoding="utf-8")
        data: dict = yaml.safe_load(raw) or {}
    except Exception as exc:
        raise ConfigError(
            f"Failed to read config file: {exc}",
            code=ErrorCode.E_CONFIG_INVALID,
        ) from exc

    # Decrypt top-level encrypted fields (anki_connect_key)
    for field in _ENCRYPTED_FIELDS:
        value = data.get(field, "")
        data[field] = _decrypt_field(value, field)

    # Decrypt legacy provider api_key fields before migration
    for legacy_field in ("openai_api_key", "deepseek_api_key"):
        if legacy_field in data:
            data[legacy_field] = _decrypt_field(data[legacy_field], legacy_field)

    # Migrate legacy format
    data = _migrate_legacy(data)

    # Decrypt provider api_keys
    for provider in data.get("llm_providers", []):
        if isinstance(provider, dict):
            provider["api_key"] = _decrypt_field(
                provider.get("api_key", ""), f"provider:{provider.get('name', '?')}"
            )

    try:
        config = AppConfig(**data)
        _update_config_cache(config_path, True, mtime_ns, config)
        return config
    except Exception as exc:
        raise ConfigError(
            f"Invalid configuration values: {exc}",
            code=ErrorCode.E_CONFIG_INVALID,
        ) from exc


def save_config(config: AppConfig) -> None:
    """Encrypt sensitive fields and persist configuration as YAML."""
    data = config.model_dump()

    # Encrypt top-level sensitive fields
    for field in _ENCRYPTED_FIELDS:
        value = data.get(field, "")
        if value:
            data[field] = _ENCRYPTED_PREFIX + encrypt(value)

    # Encrypt provider api_keys
    for provider in data.get("llm_providers", []):
        key = provider.get("api_key", "")
        if key:
            provider["api_key"] = _ENCRYPTED_PREFIX + encrypt(key)

    try:
        config_path = CONFIG_PATH
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            yaml.safe_dump(data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
        mtime_ns = config_path.stat().st_mtime_ns if config_path.exists() else None
        _update_config_cache(config_path, config_path.exists(), mtime_ns, config)
        logger.info("Configuration saved", extra={"path": str(config_path)})
    except Exception as exc:
        raise ConfigError(
            f"Failed to save config file: {exc}",
            code=ErrorCode.E_CONFIG_INVALID,
        ) from exc
