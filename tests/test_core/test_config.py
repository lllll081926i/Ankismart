"""Tests for ankismart.core.config module."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from ankismart.core.config import (
    _ENCRYPTED_PREFIX,
    AppConfig,
    LLMProviderConfig,
    load_config,
    save_config,
)
from ankismart.core.errors import ConfigError


class TestAppConfig:
    def test_defaults(self):
        cfg = AppConfig()
        assert cfg.llm_providers == []
        assert cfg.active_provider_id == ""
        assert cfg.anki_connect_url == "http://127.0.0.1:8765"
        assert cfg.anki_connect_key == ""
        assert cfg.default_deck == "Default"
        assert cfg.default_tags == ["ankismart"]
        assert cfg.log_level == "INFO"

    def test_active_provider_returns_matching(self):
        p1 = LLMProviderConfig(id="aaa", name="A")
        p2 = LLMProviderConfig(id="bbb", name="B")
        cfg = AppConfig(llm_providers=[p1, p2], active_provider_id="bbb")
        assert cfg.active_provider is p2

    def test_active_provider_falls_back_to_first(self):
        p1 = LLMProviderConfig(id="aaa", name="A")
        cfg = AppConfig(llm_providers=[p1], active_provider_id="missing")
        assert cfg.active_provider is p1

    def test_active_provider_none_when_empty(self):
        cfg = AppConfig()
        assert cfg.active_provider is None

    def test_provider_config_defaults(self):
        p = LLMProviderConfig()
        assert p.id  # auto-generated
        assert p.name == ""
        assert p.api_key == ""
        assert p.base_url == ""
        assert p.model == ""
        assert p.rpm_limit == 0

    def test_persistence_fields_defaults(self):
        cfg = AppConfig()
        assert cfg.last_deck == ""
        assert cfg.last_tags == ""
        assert cfg.last_strategy == ""
        assert cfg.last_update_mode == ""
        assert cfg.window_geometry == ""

    def test_persistence_fields_round_trip(self):
        cfg = AppConfig(
            last_deck="MyDeck",
            last_tags="tag1,tag2",
            last_strategy="cloze",
            last_update_mode="update_only",
            window_geometry="01020304abcd",
        )
        data = cfg.model_dump()
        restored = AppConfig(**data)
        assert restored.last_deck == "MyDeck"
        assert restored.last_tags == "tag1,tag2"
        assert restored.last_strategy == "cloze"
        assert restored.last_update_mode == "update_only"
        assert restored.window_geometry == "01020304abcd"


class TestLoadConfig:
    def test_returns_defaults_when_file_missing(self):
        with patch("ankismart.core.config.CONFIG_PATH") as mock_path:
            mock_path.exists.return_value = False
            cfg = load_config()
        assert cfg == AppConfig()

    def test_loads_plain_yaml(self, tmp_path: Path):
        config_file = tmp_path / "config.yaml"
        data = {
            "llm_providers": [
                {"id": "p1", "name": "OpenAI", "model": "gpt-3.5-turbo"},
            ],
            "active_provider_id": "p1",
            "default_deck": "TestDeck",
        }
        config_file.write_text(yaml.safe_dump(data), encoding="utf-8")

        with patch("ankismart.core.config.CONFIG_PATH", config_file):
            cfg = load_config()
        assert cfg.llm_providers[0].model == "gpt-3.5-turbo"
        assert cfg.default_deck == "TestDeck"

    def test_decrypts_encrypted_fields(self, tmp_path: Path):
        from ankismart.core.crypto import encrypt

        encrypted_key = encrypt("my-secret-key")
        config_file = tmp_path / "config.yaml"
        data = {"anki_connect_key": f"encrypted:{encrypted_key}"}
        config_file.write_text(yaml.safe_dump(data), encoding="utf-8")

        with patch("ankismart.core.config.CONFIG_PATH", config_file):
            cfg = load_config()
        assert cfg.anki_connect_key == "my-secret-key"

    def test_decrypts_provider_api_keys(self, tmp_path: Path):
        from ankismart.core.crypto import encrypt

        encrypted_key = encrypt("sk-provider-secret")
        config_file = tmp_path / "config.yaml"
        data = {
            "llm_providers": [
                {
                    "id": "p1",
                    "name": "OpenAI",
                    "api_key": f"encrypted:{encrypted_key}",
                    "model": "gpt-4o",
                },
            ],
            "active_provider_id": "p1",
        }
        config_file.write_text(yaml.safe_dump(data), encoding="utf-8")

        with patch("ankismart.core.config.CONFIG_PATH", config_file):
            cfg = load_config()
        assert cfg.llm_providers[0].api_key == "sk-provider-secret"

    def test_decrypt_failure_falls_back_to_empty(self, tmp_path: Path):
        config_file = tmp_path / "config.yaml"
        data = {"anki_connect_key": "encrypted:INVALID_CIPHERTEXT"}
        config_file.write_text(yaml.safe_dump(data), encoding="utf-8")

        with patch("ankismart.core.config.CONFIG_PATH", config_file):
            cfg = load_config()
        assert cfg.anki_connect_key == ""

    def test_raises_config_error_on_bad_yaml(self, tmp_path: Path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("{{{{not valid yaml", encoding="utf-8")

        with (
            patch("ankismart.core.config.CONFIG_PATH", config_file),
            pytest.raises(ConfigError, match="Failed to read config file"),
        ):
            load_config()

    def test_raises_config_error_on_invalid_values(self, tmp_path: Path):
        config_file = tmp_path / "config.yaml"
        # default_tags expects a list, give it an int to trigger validation error
        data = {"default_tags": 12345}
        config_file.write_text(yaml.safe_dump(data), encoding="utf-8")

        with (
            patch("ankismart.core.config.CONFIG_PATH", config_file),
            pytest.raises(ConfigError, match="Invalid configuration values"),
        ):
            load_config()

    def test_empty_yaml_returns_defaults(self, tmp_path: Path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("", encoding="utf-8")

        with patch("ankismart.core.config.CONFIG_PATH", config_file):
            cfg = load_config()
        assert cfg == AppConfig()

    def test_invalid_ocr_mode_falls_back_to_local(self, tmp_path: Path):
        config_file = tmp_path / "config.yaml"
        data = {"ocr_mode": "invalid_mode"}
        config_file.write_text(yaml.safe_dump(data), encoding="utf-8")

        with patch("ankismart.core.config.CONFIG_PATH", config_file):
            cfg = load_config()
        assert cfg.ocr_mode == "local"


class TestMigration:
    def test_migrates_openai_legacy(self, tmp_path: Path):
        config_file = tmp_path / "config.yaml"
        data = {
            "llm_provider": "openai",
            "openai_api_key": "sk-old",
            "openai_model": "gpt-4o",
            "deepseek_api_key": "",
            "deepseek_model": "deepseek-chat",
            "default_deck": "MyDeck",
        }
        config_file.write_text(yaml.safe_dump(data), encoding="utf-8")

        with patch("ankismart.core.config.CONFIG_PATH", config_file):
            cfg = load_config()

        assert len(cfg.llm_providers) >= 1
        openai_p = next(p for p in cfg.llm_providers if p.name == "OpenAI")
        assert openai_p.api_key == "sk-old"
        assert openai_p.model == "gpt-4o"
        assert cfg.active_provider_id == openai_p.id
        assert cfg.default_deck == "MyDeck"

    def test_migrates_deepseek_active(self, tmp_path: Path):
        config_file = tmp_path / "config.yaml"
        data = {
            "llm_provider": "deepseek",
            "openai_api_key": "sk-openai",
            "openai_model": "gpt-4o",
            "deepseek_api_key": "sk-ds",
            "deepseek_model": "deepseek-chat",
        }
        config_file.write_text(yaml.safe_dump(data), encoding="utf-8")

        with patch("ankismart.core.config.CONFIG_PATH", config_file):
            cfg = load_config()

        assert len(cfg.llm_providers) == 2
        ds_p = next(p for p in cfg.llm_providers if p.name == "DeepSeek")
        assert ds_p.api_key == "sk-ds"
        assert cfg.active_provider_id == ds_p.id

    def test_migrates_encrypted_legacy_keys(self, tmp_path: Path):
        from ankismart.core.crypto import encrypt

        encrypted_key = encrypt("sk-encrypted-old")
        config_file = tmp_path / "config.yaml"
        data = {
            "llm_provider": "openai",
            "openai_api_key": f"encrypted:{encrypted_key}",
            "openai_model": "gpt-4o",
        }
        config_file.write_text(yaml.safe_dump(data), encoding="utf-8")

        with patch("ankismart.core.config.CONFIG_PATH", config_file):
            cfg = load_config()

        openai_p = next(p for p in cfg.llm_providers if p.name == "OpenAI")
        assert openai_p.api_key == "sk-encrypted-old"

    def test_no_migration_when_new_format(self, tmp_path: Path):
        config_file = tmp_path / "config.yaml"
        data = {
            "llm_providers": [
                {"id": "x", "name": "Test", "api_key": "k", "model": "m"},
            ],
            "active_provider_id": "x",
        }
        config_file.write_text(yaml.safe_dump(data), encoding="utf-8")

        with patch("ankismart.core.config.CONFIG_PATH", config_file):
            cfg = load_config()

        assert len(cfg.llm_providers) == 1
        assert cfg.llm_providers[0].name == "Test"


class TestSaveConfig:
    def test_saves_yaml_with_encrypted_fields(self, tmp_path: Path):
        config_dir = tmp_path / ".ankismart"
        config_file = config_dir / "config.yaml"

        cfg = AppConfig(
            llm_providers=[
                LLMProviderConfig(id="p1", name="OpenAI", api_key="sk-secret", model="gpt-4o"),
            ],
            active_provider_id="p1",
            anki_connect_key="conn-key",
        )

        with (
            patch("ankismart.core.config.CONFIG_DIR", config_dir),
            patch("ankismart.core.config.CONFIG_PATH", config_file),
        ):
            save_config(cfg)

        assert config_file.exists()
        saved = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        assert saved["anki_connect_key"].startswith(_ENCRYPTED_PREFIX)
        assert saved["llm_providers"][0]["api_key"].startswith(_ENCRYPTED_PREFIX)

    def test_empty_sensitive_fields_not_encrypted(self, tmp_path: Path):
        config_dir = tmp_path / ".ankismart"
        config_file = config_dir / "config.yaml"

        cfg = AppConfig()

        with (
            patch("ankismart.core.config.CONFIG_DIR", config_dir),
            patch("ankismart.core.config.CONFIG_PATH", config_file),
        ):
            save_config(cfg)

        saved = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        assert saved["anki_connect_key"] == ""

    def test_round_trip(self, tmp_path: Path):
        config_dir = tmp_path / ".ankismart"
        config_file = config_dir / "config.yaml"

        original = AppConfig(
            llm_providers=[
                LLMProviderConfig(
                    id="p1", name="OpenAI", api_key="sk-round-trip",
                    base_url="https://api.openai.com/v1", model="gpt-4o",
                ),
            ],
            active_provider_id="p1",
            default_deck="RoundTrip",
            default_tags=["a", "b"],
        )

        with (
            patch("ankismart.core.config.CONFIG_DIR", config_dir),
            patch("ankismart.core.config.CONFIG_PATH", config_file),
        ):
            save_config(original)
            loaded = load_config()

        assert loaded.llm_providers[0].api_key == "sk-round-trip"
        assert loaded.default_deck == "RoundTrip"
        assert loaded.default_tags == ["a", "b"]

    def test_raises_config_error_on_write_failure(self):
        cfg = AppConfig()
        with (
            patch("ankismart.core.config.CONFIG_DIR") as mock_dir,
            patch("ankismart.core.config.CONFIG_PATH") as mock_path,
            pytest.raises(ConfigError, match="Failed to save config file"),
        ):
            mock_dir.mkdir = MagicMock()
            mock_path.write_text = MagicMock(side_effect=OSError("disk full"))
            save_config(cfg)
