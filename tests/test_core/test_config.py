"""Tests for ankismart.core.config module."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from ankismart.core.config import _ENCRYPTED_PREFIX, AppConfig, load_config, save_config
from ankismart.core.errors import ConfigError


class TestAppConfig:
    def test_defaults(self):
        cfg = AppConfig()
        assert cfg.openai_api_key == ""
        assert cfg.openai_model == "gpt-4o"
        assert cfg.anki_connect_url == "http://127.0.0.1:8765"
        assert cfg.anki_connect_key == ""
        assert cfg.default_deck == "Default"
        assert cfg.default_tags == ["ankismart"]
        assert cfg.log_level == "INFO"

    def test_custom_values(self):
        cfg = AppConfig(openai_api_key="sk-test", default_deck="MyDeck")
        assert cfg.openai_api_key == "sk-test"
        assert cfg.default_deck == "MyDeck"


class TestLoadConfig:
    def test_returns_defaults_when_file_missing(self):
        with patch("ankismart.core.config.CONFIG_PATH") as mock_path:
            mock_path.exists.return_value = False
            cfg = load_config()
        assert cfg == AppConfig()

    def test_loads_plain_yaml(self, tmp_path: Path):
        config_file = tmp_path / "config.yaml"
        data = {"openai_model": "gpt-3.5-turbo", "default_deck": "TestDeck"}
        config_file.write_text(yaml.safe_dump(data), encoding="utf-8")

        with (
            patch("ankismart.core.config.CONFIG_PATH", config_file),
        ):
            cfg = load_config()
        assert cfg.openai_model == "gpt-3.5-turbo"
        assert cfg.default_deck == "TestDeck"
        # Non-specified fields keep defaults
        assert cfg.openai_api_key == ""

    def test_decrypts_encrypted_fields(self, tmp_path: Path):
        from ankismart.core.crypto import encrypt

        encrypted_key = encrypt("my-secret-key")
        config_file = tmp_path / "config.yaml"
        data = {"openai_api_key": f"encrypted:{encrypted_key}"}
        config_file.write_text(yaml.safe_dump(data), encoding="utf-8")

        with patch("ankismart.core.config.CONFIG_PATH", config_file):
            cfg = load_config()
        assert cfg.openai_api_key == "my-secret-key"

    def test_decrypt_failure_falls_back_to_empty(self, tmp_path: Path):
        config_file = tmp_path / "config.yaml"
        data = {"openai_api_key": "encrypted:INVALID_CIPHERTEXT"}
        config_file.write_text(yaml.safe_dump(data), encoding="utf-8")

        with patch("ankismart.core.config.CONFIG_PATH", config_file):
            cfg = load_config()
        assert cfg.openai_api_key == ""

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

    def test_non_encrypted_sensitive_field_kept_as_is(self, tmp_path: Path):
        config_file = tmp_path / "config.yaml"
        data = {"openai_api_key": "plain-key-no-prefix"}
        config_file.write_text(yaml.safe_dump(data), encoding="utf-8")

        with patch("ankismart.core.config.CONFIG_PATH", config_file):
            cfg = load_config()
        assert cfg.openai_api_key == "plain-key-no-prefix"


class TestSaveConfig:
    def test_saves_yaml_with_encrypted_fields(self, tmp_path: Path):
        config_dir = tmp_path / ".ankismart"
        config_file = config_dir / "config.yaml"

        cfg = AppConfig(openai_api_key="sk-secret", anki_connect_key="conn-key")

        with (
            patch("ankismart.core.config.CONFIG_DIR", config_dir),
            patch("ankismart.core.config.CONFIG_PATH", config_file),
        ):
            save_config(cfg)

        assert config_file.exists()
        saved = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        assert saved["openai_api_key"].startswith(_ENCRYPTED_PREFIX)
        assert saved["anki_connect_key"].startswith(_ENCRYPTED_PREFIX)
        # Non-sensitive fields are plain
        assert saved["openai_model"] == "gpt-4o"

    def test_empty_sensitive_fields_not_encrypted(self, tmp_path: Path):
        config_dir = tmp_path / ".ankismart"
        config_file = config_dir / "config.yaml"

        cfg = AppConfig()  # api keys are empty by default

        with (
            patch("ankismart.core.config.CONFIG_DIR", config_dir),
            patch("ankismart.core.config.CONFIG_PATH", config_file),
        ):
            save_config(cfg)

        saved = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        assert saved["openai_api_key"] == ""
        assert saved["anki_connect_key"] == ""

    def test_round_trip(self, tmp_path: Path):
        config_dir = tmp_path / ".ankismart"
        config_file = config_dir / "config.yaml"

        original = AppConfig(
            openai_api_key="sk-round-trip",
            default_deck="RoundTrip",
            default_tags=["a", "b"],
        )

        with (
            patch("ankismart.core.config.CONFIG_DIR", config_dir),
            patch("ankismart.core.config.CONFIG_PATH", config_file),
        ):
            save_config(original)
            loaded = load_config()

        assert loaded.openai_api_key == "sk-round-trip"
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
