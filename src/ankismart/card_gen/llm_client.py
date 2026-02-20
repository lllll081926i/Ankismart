from __future__ import annotations

import threading
import time
from collections import deque

import httpx
from openai import (
    APIError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)

from ankismart.core.errors import CardGenError, ErrorCode
from ankismart.core.logging import get_logger
from ankismart.core.tracing import get_trace_id, metrics, timed

logger = get_logger("llm_client")

_RETRYABLE_ERRORS = (APITimeoutError, RateLimitError)
_MAX_RETRIES = 3
_BASE_DELAY = 1.0  # seconds


class _RpmThrottle:
    """Thread-safe sliding-window RPM throttle."""

    def __init__(self, rpm: int) -> None:
        self._rpm = max(0, int(rpm))
        self._lock = threading.Lock()
        self._timestamps: deque[float] = deque()

    def wait(self) -> float:
        if self._rpm <= 0:
            return 0.0

        total_waited = 0.0

        while True:
            now = time.monotonic()
            wait_for = 0.0

            with self._lock:
                window_start = now - 60.0
                while self._timestamps and self._timestamps[0] <= window_start:
                    self._timestamps.popleft()

                if len(self._timestamps) < self._rpm:
                    self._timestamps.append(now)
                    return total_waited

                wait_for = 60.0 - (now - self._timestamps[0])

            if wait_for > 0:
                time.sleep(wait_for)
                total_waited += wait_for
            else:
                # Yield to avoid busy spin on edge timing.
                time.sleep(0)


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
        metrics.increment("llm_validate_requests_total")
        try:
            self._client.models.list()
            metrics.increment("llm_validate_success_total")
            return True
        except Exception as exc:
            trace_id = get_trace_id()
            converted = self._convert_to_card_error(exc, trace_id=trace_id, context="validate connection")
            metrics.increment("llm_validate_failed_total", labels={"code": converted.code.value})
            raise converted from exc

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
        metrics.increment("llm_requests_total")

        for attempt in range(_MAX_RETRIES):
            waited_raw = self._throttle.wait()
            try:
                waited = float(waited_raw)
            except (TypeError, ValueError):
                waited = 0.0
            metrics.increment("llm_attempts_total")
            if waited > 0:
                metrics.increment("llm_throttle_wait_seconds_total", value=waited)
                metrics.set_gauge("llm_throttle_last_wait_seconds", waited)
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
                    metrics.increment("llm_prompt_tokens_total", value=usage.prompt_tokens)
                    metrics.increment("llm_completion_tokens_total", value=usage.completion_tokens)
                    metrics.increment("llm_total_tokens_total", value=usage.total_tokens)
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
                    metrics.increment(
                        "llm_requests_failed_total",
                        labels={"code": ErrorCode.E_LLM_ERROR.value},
                    )
                    raise CardGenError(
                        "LLM returned empty response",
                        code=ErrorCode.E_LLM_ERROR,
                        trace_id=trace_id,
                    )
                metrics.increment("llm_requests_succeeded_total")
                return content

            except CardGenError:
                raise

            except _RETRYABLE_ERRORS as exc:
                if attempt < _MAX_RETRIES - 1:
                    delay = _BASE_DELAY * (2 ** attempt)
                    converted = self._convert_to_card_error(
                        exc,
                        trace_id=trace_id,
                        context="chat completion",
                    )
                    logger.warning(
                        "LLM call failed, retrying",
                        extra={
                            "trace_id": trace_id,
                            "attempt": attempt + 1,
                            "delay": delay,
                            "error": str(exc),
                            "error_code": str(converted.code),
                        },
                    )
                    metrics.increment("llm_retries_total")
                    time.sleep(delay)
                else:
                    converted = self._convert_to_card_error(
                        exc,
                        trace_id=trace_id,
                        context="chat completion",
                    )
                    metrics.increment(
                        "llm_requests_failed_total",
                        labels={"code": converted.code.value},
                    )
                    raise CardGenError(
                        f"LLM call failed after {_MAX_RETRIES} attempts: {converted.message}",
                        code=converted.code,
                        trace_id=trace_id,
                    ) from exc

            except Exception as exc:
                converted = self._convert_to_card_error(exc, trace_id=trace_id, context="chat completion")
                metrics.increment(
                    "llm_requests_failed_total",
                    labels={"code": converted.code.value},
                )
                raise converted from exc

        # Should not reach here, but just in case
        metrics.increment(
            "llm_requests_failed_total",
            labels={"code": ErrorCode.E_LLM_ERROR.value},
        )
        raise CardGenError(
            "LLM call failed: exhausted retries",
            code=ErrorCode.E_LLM_ERROR,
            trace_id=trace_id,
        )

    @staticmethod
    def _extract_status_code(exc: Exception) -> int | None:
        if isinstance(exc, APIStatusError):
            return getattr(exc, "status_code", None)
        response = getattr(exc, "response", None)
        if response is not None:
            return getattr(response, "status_code", None)
        return None

    def _convert_to_card_error(
        self,
        exc: Exception,
        *,
        trace_id: str,
        context: str,
    ) -> CardGenError:
        if isinstance(exc, CardGenError):
            return exc

        status_code = self._extract_status_code(exc)

        if isinstance(exc, AuthenticationError) or status_code == 401:
            return CardGenError(
                f"LLM authentication failed (HTTP 401) during {context}: {exc}",
                code=ErrorCode.E_LLM_AUTH_ERROR,
                trace_id=trace_id,
            )

        if isinstance(exc, PermissionDeniedError) or status_code == 403:
            return CardGenError(
                f"LLM permission denied (HTTP 403) during {context}: {exc}",
                code=ErrorCode.E_LLM_PERMISSION_ERROR,
                trace_id=trace_id,
            )

        if isinstance(exc, APIStatusError):
            return CardGenError(
                f"LLM API status error (HTTP {status_code}) during {context}: {exc}",
                code=ErrorCode.E_LLM_ERROR,
                trace_id=trace_id,
            )

        if isinstance(exc, APIError):
            return CardGenError(
                f"LLM API error during {context}: {exc}",
                code=ErrorCode.E_LLM_ERROR,
                trace_id=trace_id,
            )

        return CardGenError(
            f"Unexpected LLM error during {context}: {exc}",
            code=ErrorCode.E_LLM_ERROR,
            trace_id=trace_id,
        )
