from __future__ import annotations

import threading
import time

import httpx
from openai import APIError, APITimeoutError, OpenAI, RateLimitError

from ankismart.core.errors import CardGenError, ErrorCode
from ankismart.core.logging import get_logger
from ankismart.core.tracing import get_trace_id, timed

logger = get_logger("llm_client")

_RETRYABLE_ERRORS = (APITimeoutError, RateLimitError)
_MAX_RETRIES = 3
_BASE_DELAY = 1.0  # seconds


class _RpmThrottle:
    """Simple per-minute request throttle (thread-safe)."""

    def __init__(self, rpm: int) -> None:
        self._interval = 60.0 / rpm if rpm > 0 else 0.0
        self._lock = threading.Lock()
        self._last: float = 0.0

    def wait(self) -> None:
        if self._interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            wait = self._last + self._interval - now
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()


class LLMClient:
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        *,
        base_url: str | None = None,
        rpm_limit: int = 0,
        temperature: float = 0.3,
        max_tokens: int = 0,
        proxy_url: str = "",
    ) -> None:
        kwargs: dict[str, object] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        if proxy_url:
            kwargs["http_client"] = httpx.Client(proxy=proxy_url)
        self._client = OpenAI(**kwargs)
        self._model = model
        self._throttle = _RpmThrottle(rpm_limit)
        self._temperature = temperature
        self._max_tokens = max_tokens

    def validate_connection(self) -> bool:
        """Test if the LLM endpoint is reachable by listing models."""
        try:
            self._client.models.list()
            return True
        except Exception:
            return False

    @classmethod
    def from_config(cls, config) -> LLMClient:
        """Create an LLMClient from AppConfig using the active provider."""
        provider = config.active_provider
        if provider is None:
            raise CardGenError(
                "No LLM provider configured",
                code=ErrorCode.E_LLM_ERROR,
            )
        return cls(
            api_key=provider.api_key,
            model=provider.model,
            base_url=provider.base_url or None,
            rpm_limit=provider.rpm_limit,
            temperature=getattr(config, 'llm_temperature', 0.3),
            max_tokens=getattr(config, 'llm_max_tokens', 0),
            proxy_url=getattr(config, 'proxy_url', ''),
        )

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        """Send a chat completion request with retry logic."""
        trace_id = get_trace_id()
        self._throttle.wait()

        for attempt in range(_MAX_RETRIES):
            try:
                with timed(f"llm_call_attempt_{attempt + 1}"):
                    kwargs = {
                        "model": self._model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": self._temperature,
                        "timeout": 60,
                    }
                    if self._max_tokens > 0:
                        kwargs["max_tokens"] = self._max_tokens
                    response = self._client.chat.completions.create(**kwargs)

                usage = response.usage
                if usage:
                    logger.info(
                        "LLM call completed",
                        extra={
                            "trace_id": trace_id,
                            "model": self._model,
                            "prompt_tokens": usage.prompt_tokens,
                            "completion_tokens": usage.completion_tokens,
                            "total_tokens": usage.total_tokens,
                        },
                    )

                content = response.choices[0].message.content
                if content is None:
                    raise CardGenError(
                        "LLM returned empty response",
                        code=ErrorCode.E_LLM_ERROR,
                        trace_id=trace_id,
                    )
                return content

            except _RETRYABLE_ERRORS as exc:
                if attempt < _MAX_RETRIES - 1:
                    delay = _BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        "LLM call failed, retrying",
                        extra={
                            "trace_id": trace_id,
                            "attempt": attempt + 1,
                            "delay": delay,
                            "error": str(exc),
                        },
                    )
                    time.sleep(delay)
                else:
                    raise CardGenError(
                        f"LLM call failed after {_MAX_RETRIES} attempts: {exc}",
                        code=ErrorCode.E_LLM_ERROR,
                        trace_id=trace_id,
                    ) from exc

            except APIError as exc:
                raise CardGenError(
                    f"LLM API error: {exc}",
                    code=ErrorCode.E_LLM_ERROR,
                    trace_id=trace_id,
                ) from exc

            except CardGenError:
                raise

            except Exception as exc:
                raise CardGenError(
                    f"Unexpected LLM error: {exc}",
                    code=ErrorCode.E_LLM_ERROR,
                    trace_id=trace_id,
                ) from exc

        # Should not reach here, but just in case
        raise CardGenError(
            "LLM call failed: exhausted retries",
            code=ErrorCode.E_LLM_ERROR,
            trace_id=trace_id,
        )
