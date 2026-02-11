"""Tests for ankismart.card_gen.llm_client module."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from ankismart.card_gen.llm_client import _BASE_DELAY, _MAX_RETRIES, LLMClient
from ankismart.core.errors import CardGenError, ErrorCode


def _make_response(content: str, prompt_tokens: int = 10, completion_tokens: int = 20):
    """Build a fake OpenAI ChatCompletion response."""
    usage = SimpleNamespace(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
    )
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice], usage=usage)


def _make_response_no_usage(content: str):
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice], usage=None)


def _make_response_empty():
    message = SimpleNamespace(content=None)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice], usage=None)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLLMClientChat:
    """Tests for LLMClient.chat."""

    @patch("ankismart.card_gen.llm_client.OpenAI")
    def test_successful_call(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_response("hello")

        client = LLMClient(api_key="sk-test", model="gpt-4o")
        result = client.chat("system", "user")

        assert result == "hello"
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "gpt-4o"
        assert call_kwargs["temperature"] == 0.3
        assert len(call_kwargs["messages"]) == 2
        assert call_kwargs["messages"][0]["role"] == "system"
        assert call_kwargs["messages"][1]["role"] == "user"

    @patch("ankismart.card_gen.llm_client.OpenAI")
    def test_successful_call_no_usage(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_response_no_usage("ok")

        client = LLMClient(api_key="sk-test")
        result = client.chat("sys", "usr")
        assert result == "ok"

    @patch("ankismart.card_gen.llm_client.OpenAI")
    def test_empty_response_raises_error(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_response_empty()

        client = LLMClient(api_key="sk-test")
        with pytest.raises(CardGenError) as exc_info:
            client.chat("sys", "usr")
        assert exc_info.value.code == ErrorCode.E_LLM_ERROR
        assert "empty response" in exc_info.value.message.lower()

    @patch("ankismart.card_gen.llm_client.time.sleep")
    @patch("ankismart.card_gen.llm_client.OpenAI")
    def test_retry_on_timeout_then_success(self, mock_openai_cls, mock_sleep):
        from openai import APITimeoutError

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_client.chat.completions.create.side_effect = [
            APITimeoutError(request=MagicMock()),
            _make_response("recovered"),
        ]

        client = LLMClient(api_key="sk-test")
        result = client.chat("sys", "usr")

        assert result == "recovered"
        assert mock_client.chat.completions.create.call_count == 2
        mock_sleep.assert_called_once_with(_BASE_DELAY * (2 ** 0))

    @patch("ankismart.card_gen.llm_client.time.sleep")
    @patch("ankismart.card_gen.llm_client.OpenAI")
    def test_retry_on_rate_limit_then_success(self, mock_openai_cls, mock_sleep):
        from openai import RateLimitError

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        response_mock = MagicMock()
        response_mock.status_code = 429
        response_mock.headers = {}
        mock_client.chat.completions.create.side_effect = [
            RateLimitError(
                message="rate limited",
                response=response_mock,
                body=None,
            ),
            _make_response("ok after retry"),
        ]

        client = LLMClient(api_key="sk-test")
        result = client.chat("sys", "usr")

        assert result == "ok after retry"
        assert mock_sleep.call_count == 1

    @patch("ankismart.card_gen.llm_client.time.sleep")
    @patch("ankismart.card_gen.llm_client.OpenAI")
    def test_exhausted_retries_raises_error(self, mock_openai_cls, mock_sleep):
        from openai import APITimeoutError

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_client.chat.completions.create.side_effect = APITimeoutError(
            request=MagicMock(),
        )

        client = LLMClient(api_key="sk-test")
        with pytest.raises(CardGenError) as exc_info:
            client.chat("sys", "usr")

        assert exc_info.value.code == ErrorCode.E_LLM_ERROR
        assert f"{_MAX_RETRIES} attempts" in exc_info.value.message
        assert mock_client.chat.completions.create.call_count == _MAX_RETRIES
        assert mock_sleep.call_count == _MAX_RETRIES - 1

    @patch("ankismart.card_gen.llm_client.time.sleep")
    @patch("ankismart.card_gen.llm_client.OpenAI")
    def test_exponential_backoff_delays(self, mock_openai_cls, mock_sleep):
        from openai import APITimeoutError

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = APITimeoutError(
            request=MagicMock(),
        )

        client = LLMClient(api_key="sk-test")
        with pytest.raises(CardGenError):
            client.chat("sys", "usr")

        expected_delays = [_BASE_DELAY * (2 ** i) for i in range(_MAX_RETRIES - 1)]
        actual_delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert actual_delays == expected_delays

    @patch("ankismart.card_gen.llm_client.OpenAI")
    def test_api_error_no_retry(self, mock_openai_cls):
        from openai import APIError

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_client.chat.completions.create.side_effect = APIError(
            message="server error",
            request=MagicMock(),
            body=None,
        )

        client = LLMClient(api_key="sk-test")
        with pytest.raises(CardGenError) as exc_info:
            client.chat("sys", "usr")

        assert exc_info.value.code == ErrorCode.E_LLM_ERROR
        assert "API error" in exc_info.value.message
        # Should NOT retry -- only 1 call
        assert mock_client.chat.completions.create.call_count == 1

    @patch("ankismart.card_gen.llm_client.OpenAI")
    def test_unexpected_exception_wraps_in_card_gen_error(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = RuntimeError("boom")

        client = LLMClient(api_key="sk-test")
        with pytest.raises(CardGenError) as exc_info:
            client.chat("sys", "usr")

        assert exc_info.value.code == ErrorCode.E_LLM_ERROR
        assert "Unexpected" in exc_info.value.message

    @patch("ankismart.card_gen.llm_client.OpenAI")
    def test_default_model_is_gpt4o(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_response("x")

        client = LLMClient(api_key="sk-test")
        client.chat("sys", "usr")

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "gpt-4o"


class TestLLMClientGenerationParams:
    """Tests for temperature and max_tokens parameter passing."""

    @patch("ankismart.card_gen.llm_client.OpenAI")
    def test_llm_client_stores_temperature_and_max_tokens(self, mock_openai_cls):
        client = LLMClient(api_key="test-key", temperature=0.7, max_tokens=1024)
        assert client._temperature == 0.7
        assert client._max_tokens == 1024

    @patch("ankismart.card_gen.llm_client.OpenAI")
    def test_llm_client_default_temperature(self, mock_openai_cls):
        client = LLMClient(api_key="test-key")
        assert client._temperature == 0.3
        assert client._max_tokens == 0


class TestLLMClientProxy:
    """Tests for proxy_url parameter passing."""

    @patch("ankismart.card_gen.llm_client.OpenAI")
    def test_llm_client_with_proxy_url(self, mock_openai_cls):
        client = LLMClient(api_key="test-key", proxy_url="http://proxy:8080")
        # Verify the client was created without error
        assert client._model == "gpt-4o"
        # Verify http_client was passed to OpenAI constructor
        call_kwargs = mock_openai_cls.call_args[1]
        assert "http_client" in call_kwargs

    @patch("ankismart.card_gen.llm_client.OpenAI")
    def test_llm_client_without_proxy_url(self, mock_openai_cls):
        client = LLMClient(api_key="test-key")
        assert client._model == "gpt-4o"
        # Verify http_client was NOT passed to OpenAI constructor
        call_kwargs = mock_openai_cls.call_args[1]
        assert "http_client" not in call_kwargs
