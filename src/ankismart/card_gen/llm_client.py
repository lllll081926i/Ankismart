from __future__ import annotations

import time

from openai import APIError, APITimeoutError, OpenAI, RateLimitError

from ankismart.core.errors import CardGenError, ErrorCode
from ankismart.core.logging import get_logger
from ankismart.core.tracing import get_trace_id, timed

logger = get_logger("llm_client")

_RETRYABLE_ERRORS = (APITimeoutError, RateLimitError)
_MAX_RETRIES = 3
_BASE_DELAY = 1.0  # seconds


_DEEPSEEK_BASE_URL = "https://api.deepseek.com"


class LLMClient:
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        *,
        base_url: str | None = None,
    ) -> None:
        kwargs: dict[str, object] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = OpenAI(**kwargs)
        self._model = model

    @classmethod
    def from_config(cls, config) -> LLMClient:
        """Create an LLMClient from AppConfig, dispatching by provider."""
        if config.llm_provider == "deepseek":
            return cls(
                api_key=config.deepseek_api_key,
                model=config.deepseek_model,
                base_url=_DEEPSEEK_BASE_URL,
            )
        return cls(api_key=config.openai_api_key, model=config.openai_model)

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        """Send a chat completion request with retry logic."""
        trace_id = get_trace_id()

        for attempt in range(_MAX_RETRIES):
            try:
                with timed(f"llm_call_attempt_{attempt + 1}"):
                    response = self._client.chat.completions.create(
                        model=self._model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=0.3,
                        timeout=60,
                    )

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
