from __future__ import annotations

import gc
import ipaddress
import json
import os
import re
import socket
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlparse

import httpx
import numpy as np
from PIL import Image

from ankismart.converter import ocr_device as _device
from ankismart.converter import ocr_models as _models
from ankismart.converter import ocr_pdf as _pdf
from ankismart.core.errors import ConvertError, ErrorCode
from ankismart.core.logging import get_logger
from ankismart.core.models import MarkdownResult
from ankismart.core.tracing import get_trace_id, timed

if TYPE_CHECKING:
    from paddleocr import PaddleOCR

logger = get_logger("ocr_converter")

# Keep this env setup in facade for compatibility with existing runtime behavior.
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "1")

# Backward-compatible symbol exposed for tests/patches.
pdfium = _pdf.pdfium

# Re-export presets for existing callers.
OCR_MODEL_PRESETS = _models.OCR_MODEL_PRESETS
OCR_MODEL_SOURCE_MAP = _models.OCR_MODEL_SOURCE_MAP

# Test-friendly hook for monkeypatching OCR class without importing heavy deps.
PaddleOCR = None

# OCR engine singleton state
_ocr_instance: "PaddleOCR | None" = None
_ocr_lock = threading.Lock()
_mkldnn_fallback_applied = False
_gpu_fallback_applied = False
_ocr_runtime_device: str | None = None
_ocr_users_lock = threading.Lock()
_ocr_active_users = 0
_ocr_release_deferred = False

_PAGE_MARKER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^[\s\-—–_·.。]*第\s*\d{1,4}\s*[页頁][\s\-—–_·.。]*$", re.IGNORECASE),
    re.compile(r"^[\s\-—–_·.。]*(?:page|p\.?)\s*\d{1,4}[\s\-—–_·.。]*$", re.IGNORECASE),
    re.compile(r"^[\s\-—–_·.。]*\d{1,4}\s*/\s*\d{1,4}[\s\-—–_·.。]*$"),
)

_OCR_CLOUD_DEFAULT_PROVIDER = "mineru"
_OCR_CLOUD_DEFAULT_ENDPOINT = "https://mineru.net"
_OCR_CLOUD_DEFAULT_MODEL_VERSION = "vlm"
_OCR_CLOUD_POLL_INTERVAL_SECONDS = 2.0
_OCR_CLOUD_TIMEOUT_SECONDS = 600.0
_OCR_CLOUD_MAX_FILE_SIZE_BYTES = 200 * 1024 * 1024
_OCR_CLOUD_MAX_PDF_PAGES = 600
_OCR_CLOUD_MAX_MARKDOWN_BYTES = 20 * 1024 * 1024
_OCR_CLOUD_MAX_REDIRECTS = 3


def _normalize_marker_candidate(line: str) -> str:
    candidate = " ".join(line.strip().split())
    return candidate.strip("()[]{}（）【】")


def _is_page_marker_line(line: str) -> bool:
    candidate = _normalize_marker_candidate(line)
    if not candidate:
        return False

    for pattern in _PAGE_MARKER_PATTERNS:
        if not pattern.fullmatch(candidate):
            continue
        if "/" in candidate:
            parts = [part.strip() for part in candidate.split("/", maxsplit=1)]
            if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
                return False
            left = int(parts[0])
            right = int(parts[1])
            return 1 <= left <= right
        return True

    return False


def _remove_page_marker_lines(text: str) -> str:
    if not text:
        return text
    lines = [line for line in text.splitlines() if not _is_page_marker_line(line)]
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _normalize_cloud_provider(provider: str | None) -> str:
    value = (provider or "").strip().lower()
    return value or _OCR_CLOUD_DEFAULT_PROVIDER


def _normalize_cloud_endpoint(endpoint: str | None) -> str:
    value = (endpoint or "").strip()
    if not value:
        value = _OCR_CLOUD_DEFAULT_ENDPOINT
    if "://" not in value:
        value = f"https://{value}"
    return value.rstrip("/")


def _normalize_proxy_url(proxy_url: str | None) -> str:
    value = (proxy_url or "").strip()
    return value


def _candidate_cloud_api_bases(endpoint: str) -> list[str]:
    normalized = _normalize_cloud_endpoint(endpoint)
    bases: list[str] = []
    if normalized.endswith("/api/v4"):
        bases.extend([normalized, normalized[: -len("/api/v4")]])
    else:
        bases.extend([f"{normalized}/api/v4", normalized])

    unique: list[str] = []
    seen: set[str] = set()
    for base in bases:
        clean = base.rstrip("/")
        if not clean or clean in seen:
            continue
        seen.add(clean)
        unique.append(clean)
    return unique


def _build_cloud_headers(api_key: str) -> dict[str, str]:
    token = api_key.strip()
    return {
        "Authorization": f"Bearer {token}",
        "X-MinerU-User-Token": token,
    }


def _raise_cloud_http_error(
    *,
    response: httpx.Response,
    trace_id: str,
    context: str,
) -> None:
    details = ""
    try:
        payload = response.json()
        details = json.dumps(payload, ensure_ascii=False)[:240]
    except Exception:
        details = (response.text or "").strip()[:240]

    status = response.status_code
    if status in {401, 403}:
        message = "Cloud OCR authentication failed. Please check API key."
        code = ErrorCode.E_CONFIG_INVALID
    elif status == 429:
        message = "Cloud OCR request rate limited. Please retry later."
        code = ErrorCode.E_OCR_FAILED
    else:
        message = f"Cloud OCR HTTP {status} during {context}"
        code = ErrorCode.E_OCR_FAILED
    if details:
        message = f"{message}: {details}"

    raise ConvertError(
        message,
        code=code,
        trace_id=trace_id,
    )


def _request_cloud_json(
    client: httpx.Client,
    *,
    method: str,
    endpoint: str,
    path: str,
    api_key: str,
    trace_id: str,
    context: str,
    payload: dict[str, object] | None = None,
    timeout: float = 60.0,
) -> tuple[dict[str, object], str]:
    request_headers = _build_cloud_headers(api_key)
    request_path = path.lstrip("/")
    last_http_error: httpx.HTTPError | None = None

    for base in _candidate_cloud_api_bases(endpoint):
        url = f"{base}/{request_path}"
        try:
            response = client.request(
                method=method.upper(),
                url=url,
                headers=request_headers,
                json=payload,
                timeout=timeout,
            )
        except httpx.HTTPError as exc:
            last_http_error = exc
            continue

        if response.status_code in {404, 405}:
            continue
        if response.status_code >= 400:
            _raise_cloud_http_error(response=response, trace_id=trace_id, context=context)

        try:
            data = response.json()
        except ValueError as exc:
            raise ConvertError(
                f"Cloud OCR returned invalid JSON during {context}",
                code=ErrorCode.E_OCR_FAILED,
                trace_id=trace_id,
            ) from exc

        if not isinstance(data, dict):
            raise ConvertError(
                f"Cloud OCR returned invalid payload type during {context}: "
                f"{type(data).__name__}",
                code=ErrorCode.E_OCR_FAILED,
                trace_id=trace_id,
            )
        return data, url

    if last_http_error is not None:
        raise ConvertError(
            f"Cloud OCR request failed during {context}: {last_http_error}",
            code=ErrorCode.E_OCR_FAILED,
            trace_id=trace_id,
        ) from last_http_error

    raise ConvertError(
        f"Cloud OCR endpoint not found during {context}. Please check endpoint configuration.",
        code=ErrorCode.E_CONFIG_INVALID,
        trace_id=trace_id,
    )


def _extract_response_data(
    payload: dict[str, object],
    trace_id: str,
    *,
    context: str,
) -> dict[str, object]:
    code = payload.get("code")
    if code not in (None, 0, "0"):
        message = str(payload.get("msg") or payload.get("message") or "unknown error")
        raise ConvertError(
            f"Cloud OCR API error during {context}: {message}",
            code=ErrorCode.E_OCR_FAILED,
            trace_id=trace_id,
        )

    data = payload.get("data")
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConvertError(
            f"Cloud OCR returned invalid data field during {context}",
            code=ErrorCode.E_OCR_FAILED,
            trace_id=trace_id,
        )
    return data


def _extract_upload_url(data: dict[str, object]) -> str | None:
    file_urls = data.get("file_urls")
    if isinstance(file_urls, list) and file_urls:
        first = file_urls[0]
        if isinstance(first, str):
            return first.strip() or None
        if isinstance(first, dict):
            for key in ("url", "file_url", "upload_url"):
                value = first.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    return None


def _upload_cloud_file(
    client: httpx.Client,
    *,
    upload_url: str,
    file_path: Path,
    trace_id: str,
) -> None:
    try:
        with file_path.open("rb") as fp:
            response = client.put(upload_url, content=fp.read(), timeout=120)
    except httpx.HTTPError as exc:
        raise ConvertError(
            f"Cloud OCR file upload failed: {exc}",
            code=ErrorCode.E_OCR_FAILED,
            trace_id=trace_id,
        ) from exc

    if response.status_code >= 400:
        _raise_cloud_http_error(response=response, trace_id=trace_id, context="file upload")


def _find_first_string_value(payload: object, keys: tuple[str, ...]) -> str | None:
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        for value in payload.values():
            found = _find_first_string_value(value, keys)
            if found:
                return found
        return None

    if isinstance(payload, list):
        for item in payload:
            found = _find_first_string_value(item, keys)
            if found:
                return found
    return None


def _is_disallowed_remote_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _validate_cloud_result_url(url: str, *, trace_id: str, context: str) -> str:
    parsed = urlparse(str(url).strip())
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").strip().lower()

    if scheme != "https":
        raise ConvertError(
            f"Cloud OCR returned non-HTTPS URL during {context}",
            code=ErrorCode.E_CONFIG_INVALID,
            trace_id=trace_id,
        )
    if not host:
        raise ConvertError(
            f"Cloud OCR returned invalid URL during {context}",
            code=ErrorCode.E_CONFIG_INVALID,
            trace_id=trace_id,
        )
    if parsed.username or parsed.password:
        raise ConvertError(
            f"Cloud OCR returned URL with credentials during {context}",
            code=ErrorCode.E_CONFIG_INVALID,
            trace_id=trace_id,
        )

    try:
        ip_obj = ipaddress.ip_address(host)
        ip_list = [ip_obj]
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise ConvertError(
                f"Cloud OCR result host resolve failed during {context}: {exc}",
                code=ErrorCode.E_CONFIG_INVALID,
                trace_id=trace_id,
            ) from exc

        ip_list = []
        for info in infos:
            address = info[4][0]
            try:
                ip_list.append(ipaddress.ip_address(address))
            except ValueError:
                continue
        if not ip_list:
            raise ConvertError(
                f"Cloud OCR result host resolve returned no IP during {context}",
                code=ErrorCode.E_CONFIG_INVALID,
                trace_id=trace_id,
            )

    for ip_obj in ip_list:
        if _is_disallowed_remote_ip(ip_obj):
            raise ConvertError(
                f"Cloud OCR result URL points to disallowed network during {context}",
                code=ErrorCode.E_CONFIG_INVALID,
                trace_id=trace_id,
            )

    return parsed.geturl()


def _download_cloud_text_with_limit(
    client: httpx.Client,
    *,
    url: str,
    trace_id: str,
    context: str,
    max_bytes: int = _OCR_CLOUD_MAX_MARKDOWN_BYTES,
) -> str:
    current_url = _validate_cloud_result_url(url, trace_id=trace_id, context=context)

    for _ in range(_OCR_CLOUD_MAX_REDIRECTS + 1):
        with client.stream("GET", current_url, timeout=120, follow_redirects=False) as response:
            if 300 <= response.status_code < 400:
                redirect_target = response.headers.get("location", "").strip()
                if not redirect_target:
                    raise ConvertError(
                        f"Cloud OCR redirect missing location during {context}",
                        code=ErrorCode.E_OCR_FAILED,
                        trace_id=trace_id,
                    )
                current_url = _validate_cloud_result_url(
                    urljoin(current_url, redirect_target),
                    trace_id=trace_id,
                    context=context,
                )
                continue

            if response.status_code >= 400:
                _raise_cloud_http_error(response=response, trace_id=trace_id, context=context)

            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_bytes():
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    raise ConvertError(
                        f"Cloud OCR markdown result exceeds {max_bytes} bytes during {context}",
                        code=ErrorCode.E_OCR_FAILED,
                        trace_id=trace_id,
                    )
                chunks.append(chunk)
            return b"".join(chunks).decode("utf-8", errors="ignore").strip()

    raise ConvertError(
        f"Cloud OCR too many redirects during {context}",
        code=ErrorCode.E_OCR_FAILED,
        trace_id=trace_id,
    )


def _resolve_cloud_result_entry(data: dict[str, object], data_id: str) -> dict[str, object]:
    result_items = data.get("extract_result")
    if not isinstance(result_items, list):
        result_items = data.get("results")
    if isinstance(result_items, dict):
        result_items = list(result_items.values())
    if not isinstance(result_items, list):
        return data

    if not result_items:
        return {}

    for item in result_items:
        if not isinstance(item, dict):
            continue
        if str(item.get("data_id", "")).strip() == data_id:
            return item
    for item in result_items:
        if isinstance(item, dict):
            return item
    return {}


def _normalize_state(state: str | None) -> str:
    value = (state or "").strip().lower()
    if value == "success":
        return "done"
    return value


def _emit_cloud_progress(progress_callback, step: int, total: int, message: str) -> None:
    if progress_callback is None:
        return
    progress_callback(step, total, message)


def _validate_cloud_input_constraints(
    *,
    file_path: Path,
    source_format: str,
    trace_id: str,
) -> None:
    try:
        file_size = file_path.stat().st_size
    except OSError as exc:
        raise ConvertError(
            f"Cloud OCR cannot read file size: {exc}",
            code=ErrorCode.E_OCR_FAILED,
            trace_id=trace_id,
        ) from exc

    if file_size > _OCR_CLOUD_MAX_FILE_SIZE_BYTES:
        raise ConvertError(
            "Cloud OCR file size exceeds 200MB limit",
            code=ErrorCode.E_CONFIG_INVALID,
            trace_id=trace_id,
        )

    if source_format != "pdf":
        return

    try:
        page_count = _pdf.count_pdf_pages(file_path, pdfium_module=pdfium)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ConvertError(
            f"Cloud OCR cannot validate PDF page count: {exc}",
            code=ErrorCode.E_CONFIG_INVALID,
            trace_id=trace_id,
        ) from exc

    if page_count > _OCR_CLOUD_MAX_PDF_PAGES:
        raise ConvertError(
            "Cloud OCR PDF pages exceed 600-page limit",
            code=ErrorCode.E_CONFIG_INVALID,
            trace_id=trace_id,
        )


def _convert_via_cloud(
    *,
    file_path: Path,
    source_format: str,
    trace_id: str,
    progress_callback=None,
    cloud_provider: str = "",
    cloud_endpoint: str = "",
    cloud_api_key: str = "",
    proxy_url: str = "",
) -> MarkdownResult:
    provider = _normalize_cloud_provider(cloud_provider)
    if provider != "mineru":
        raise ConvertError(
            f"Unsupported cloud OCR provider: {provider}",
            code=ErrorCode.E_CONFIG_INVALID,
            trace_id=trace_id,
        )

    api_key = cloud_api_key.strip()
    if not api_key:
        raise ConvertError(
            "Cloud OCR API key is required. Please set OCR cloud API key in Settings.",
            code=ErrorCode.E_CONFIG_INVALID,
            trace_id=trace_id,
        )

    endpoint = _normalize_cloud_endpoint(cloud_endpoint)
    proxy = _normalize_proxy_url(proxy_url)
    _validate_cloud_input_constraints(
        file_path=file_path,
        source_format=source_format,
        trace_id=trace_id,
    )
    poll_interval = max(
        0.5,
        _get_env_int(
            "ANKISMART_OCR_CLOUD_POLL_INTERVAL_SECONDS",
            int(_OCR_CLOUD_POLL_INTERVAL_SECONDS),
        ),
    )
    timeout_seconds = max(
        30.0,
        float(_get_env_int("ANKISMART_OCR_CLOUD_TIMEOUT_SECONDS", int(_OCR_CLOUD_TIMEOUT_SECONDS))),
    )

    _emit_cloud_progress(progress_callback, 0, 3, "云端 OCR: 创建上传任务...")
    transport = httpx.Client(proxy=proxy) if proxy else httpx.Client()
    data_id = uuid.uuid4().hex[:12]

    try:
        with transport as client:
            create_payload = {
                "files": [{"name": file_path.name, "data_id": data_id}],
                "model_version": _OCR_CLOUD_DEFAULT_MODEL_VERSION,
            }
            create_response, _ = _request_cloud_json(
                client,
                method="POST",
                endpoint=endpoint,
                path="file-urls/batch",
                api_key=api_key,
                trace_id=trace_id,
                context="create upload url",
                payload=create_payload,
            )
            create_data = _extract_response_data(
                create_response, trace_id, context="create upload url"
            )
            upload_url = _extract_upload_url(create_data)
            if not upload_url:
                raise ConvertError(
                    "Cloud OCR did not return upload URL",
                    code=ErrorCode.E_OCR_FAILED,
                    trace_id=trace_id,
                )

            _emit_cloud_progress(progress_callback, 1, 3, "云端 OCR: 上传文件中...")
            _upload_cloud_file(
                client,
                upload_url=upload_url,
                file_path=file_path,
                trace_id=trace_id,
            )

            batch_id = _find_first_string_value(create_data, ("batch_id", "batchId")) or ""
            if not batch_id:
                raise ConvertError(
                    "Cloud OCR did not return batch_id after upload-url creation",
                    code=ErrorCode.E_OCR_FAILED,
                    trace_id=trace_id,
                )

            _emit_cloud_progress(progress_callback, 2, 3, "云端 OCR: 等待解析结果...")
            start = time.monotonic()
            result_entry: dict[str, object] = {}
            while True:
                if (time.monotonic() - start) >= timeout_seconds:
                    raise ConvertError(
                        "Cloud OCR result polling timeout",
                        code=ErrorCode.E_OCR_FAILED,
                        trace_id=trace_id,
                    )

                result_response, _ = _request_cloud_json(
                    client,
                    method="GET",
                    endpoint=endpoint,
                    path=f"extract-results/batch/{batch_id}",
                    api_key=api_key,
                    trace_id=trace_id,
                    context="poll extract result",
                    payload=None,
                )
                result_data = _extract_response_data(
                    result_response, trace_id, context="poll extract result"
                )
                result_entry = _resolve_cloud_result_entry(result_data, data_id)
                state = _normalize_state(str(result_entry.get("state", "")))
                if state in {"done", "finished"}:
                    break
                if state in {"failed", "cancelled"}:
                    reason = str(
                        result_entry.get("error")
                        or result_entry.get("err_msg")
                        or result_entry.get("message")
                        or "Cloud OCR task failed"
                    )
                    raise ConvertError(
                        reason,
                        code=ErrorCode.E_OCR_FAILED,
                        trace_id=trace_id,
                    )
                time.sleep(poll_interval)

            md_url = _find_first_string_value(
                result_entry,
                ("full_md_url", "md_url", "markdown_url"),
            ) or _find_first_string_value(result_data, ("full_md_url", "md_url", "markdown_url"))
            markdown_content = _find_first_string_value(
                result_entry,
                ("md_content", "markdown", "content"),
            )

            if not markdown_content and md_url:
                markdown_content = _download_cloud_text_with_limit(
                    client,
                    url=md_url,
                    trace_id=trace_id,
                    context="download markdown result",
                )

            if not markdown_content:
                raise ConvertError(
                    "Cloud OCR returned no markdown content or markdown URL",
                    code=ErrorCode.E_OCR_FAILED,
                    trace_id=trace_id,
                )
    except ConvertError:
        raise
    except Exception as exc:
        raise ConvertError(
            f"Cloud OCR failed: {exc}",
            code=ErrorCode.E_OCR_FAILED,
            trace_id=trace_id,
        ) from exc

    _emit_cloud_progress(progress_callback, 3, 3, "云端 OCR: 解析完成")
    return MarkdownResult(
        content=_remove_page_marker_lines(markdown_content),
        source_path=str(file_path),
        source_format=source_format,
        trace_id=trace_id,
    )


def test_cloud_connectivity(
    *,
    cloud_provider: str = "",
    cloud_endpoint: str = "",
    cloud_api_key: str = "",
    proxy_url: str = "",
) -> tuple[bool, str]:
    provider = _normalize_cloud_provider(cloud_provider)
    if provider != "mineru":
        return False, f"Unsupported cloud OCR provider: {provider}"

    api_key = cloud_api_key.strip()
    if not api_key:
        return False, "Cloud OCR API key is required"

    endpoint = _normalize_cloud_endpoint(cloud_endpoint)
    proxy = _normalize_proxy_url(proxy_url)
    data_id = "connectivity-check"
    payload = {
        "files": [{"name": "connectivity-check.pdf", "data_id": data_id}],
        "model_version": _OCR_CLOUD_DEFAULT_MODEL_VERSION,
    }

    client = httpx.Client(proxy=proxy) if proxy else httpx.Client()
    try:
        with client:
            response, _ = _request_cloud_json(
                client,
                method="POST",
                endpoint=endpoint,
                path="file-urls/batch",
                api_key=api_key,
                trace_id="",
                context="cloud connectivity check",
                payload=payload,
                timeout=20.0,
            )
            _extract_response_data(response, "", context="cloud connectivity check")
            return True, ""
    except ConvertError as exc:
        return False, str(exc)


def _reset_ocr_runtime_state() -> None:
    release_ocr_runtime(reason="runtime_reset")


def release_ocr_runtime(*, reason: str = "manual", force_gc: bool = True) -> bool:
    """Release global OCR runtime instance and return whether an instance existed."""
    global _ocr_instance, _mkldnn_fallback_applied, _gpu_fallback_applied
    global _ocr_runtime_device, _ocr_release_deferred

    with _ocr_users_lock:
        if _ocr_active_users > 0:
            _ocr_release_deferred = True
            logger.info(
                "OCR runtime release deferred until active tasks finish",
                extra={
                    "event": "ocr.engine.release_deferred",
                    "reason": reason,
                    "active_users": _ocr_active_users,
                },
            )
            return False

    with _ocr_lock:
        instance = _ocr_instance
        _ocr_instance = None
        _mkldnn_fallback_applied = False
        _gpu_fallback_applied = False
        _ocr_runtime_device = None

    if instance is None:
        return False

    close_fn = getattr(instance, "close", None)
    if callable(close_fn):
        try:
            close_fn()
        except Exception as exc:
            logger.debug(f"Failed to close OCR runtime gracefully: {exc}")

    del instance

    if force_gc:
        gc.collect()

    logger.info(
        "Released PaddleOCR runtime",
        extra={"event": "ocr.engine.released", "reason": reason},
    )
    return True


def _mark_ocr_user_enter() -> None:
    global _ocr_active_users
    with _ocr_users_lock:
        _ocr_active_users += 1


def _mark_ocr_user_leave() -> None:
    global _ocr_active_users, _ocr_release_deferred
    should_release = False

    with _ocr_users_lock:
        _ocr_active_users = max(0, _ocr_active_users - 1)
        if _ocr_active_users == 0 and _ocr_release_deferred:
            _ocr_release_deferred = False
            should_release = True

    if should_release:
        release_ocr_runtime(reason="deferred_release")


@contextmanager
def _borrow_ocr():
    _mark_ocr_user_enter()
    try:
        yield _get_ocr()
    finally:
        _mark_ocr_user_leave()


def get_ocr_model_presets() -> dict[str, dict[str, str]]:
    return _models.get_ocr_model_presets()


def resolve_ocr_model_pair(model_tier: str | None = None) -> tuple[str, str]:
    return _models.resolve_ocr_model_pair(model_tier)


def resolve_ocr_model_source(model_source: str | None = None) -> str:
    return _models.resolve_ocr_model_source(model_source)


def configure_ocr_runtime(
    *,
    model_tier: str | None = None,
    model_source: str | None = None,
    reset_ocr_instance: bool = False,
) -> dict[str, str]:
    return _models.configure_ocr_runtime(
        model_tier=model_tier,
        model_source=model_source,
        reset_ocr_instance=reset_ocr_instance,
        on_reset_runtime=_reset_ocr_runtime_state,
    )


def _resolve_project_root() -> Path:
    return _models._resolve_project_root()


def _ensure_local_dependency_env() -> None:
    _models._ensure_local_dependency_env()


def _has_paddlex_model_files(model_dir: Path) -> bool:
    return _models._has_paddlex_model_files(model_dir)


def _model_candidates(model_name: str, env_var_name: str, model_root: Path) -> list[Path]:
    return _models._model_candidates(model_name, env_var_name, model_root)


def _find_existing_model_dir(model_name: str, env_var_name: str, model_root: Path) -> str | None:
    return _models._find_existing_model_dir(model_name, env_var_name, model_root)


def get_missing_ocr_models(
    *,
    model_tier: str | None = None,
    model_source: str | None = None,
) -> list[str]:
    return _models.get_missing_ocr_models(
        model_tier=model_tier,
        model_source=model_source,
        configure_runtime_fn=configure_ocr_runtime,
    )


def download_missing_ocr_models(
    progress_callback=None,
    *,
    model_tier: str | None = None,
    model_source: str | None = None,
) -> list[str]:
    return _models.download_missing_ocr_models(
        progress_callback=progress_callback,
        model_tier=model_tier,
        model_source=model_source,
        configure_runtime_fn=configure_ocr_runtime,
        get_missing_fn=get_missing_ocr_models,
        on_models_ready=_reset_ocr_runtime_state,
    )


def _choose_model_dir(
    model_name: str,
    env_var_name: str,
    model_root: Path,
    role: str,
) -> str | None:
    return _models._choose_model_dir(model_name, env_var_name, model_root, role)


def _resolve_model_root() -> Path:
    return _models._resolve_model_root()


def _cuda_devices_visible() -> bool:
    return _device._cuda_devices_visible()


def _has_nvidia_smi_gpu() -> bool:
    return _device._has_nvidia_smi_gpu()


def _perform_cuda_detection() -> bool:
    return _device._perform_cuda_detection()


def detect_cuda_environment(*, force_refresh: bool = False) -> bool:
    return _device.detect_cuda_environment(force_refresh=force_refresh)


def _cuda_available() -> bool:
    return _device._cuda_available()


def is_cuda_available(*, force_refresh: bool = False) -> bool:
    if _cuda_available():
        return True
    if _has_nvidia_smi_gpu():
        return True
    return detect_cuda_environment(force_refresh=force_refresh)


def preload_cuda_detection() -> None:
    _device.preload_cuda_detection()


def _get_env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_env_int(name: str, default: int, *, min_value: int | None = None) -> int:
    raw = os.getenv(name)
    if raw is None:
        value = default
    else:
        text = raw.strip()
        if not text:
            value = default
        else:
            try:
                value = int(text)
            except ValueError:
                logger.warning(
                    "Invalid integer environment variable, fallback to default",
                    extra={"env_var": name, "raw_value": raw, "default_value": default},
                )
                value = default

    if min_value is not None and value < min_value:
        logger.warning(
            "Integer environment variable below minimum, clamp to minimum",
            extra={
                "env_var": name,
                "resolved_value": value,
                "minimum": min_value,
            },
        )
        return min_value
    return value


def _resolve_ocr_device() -> str:
    requested = os.getenv("ANKISMART_OCR_DEVICE", "auto").strip().lower()
    has_cuda = _cuda_available()

    if requested in {"gpu", "gpu:0"}:
        if has_cuda:
            return "gpu:0"
        logger.warning("CUDA unavailable, fallback to CPU", extra={"requested_device": requested})
        return "cpu"

    if requested == "cpu":
        return "cpu"

    if requested not in {"auto", ""}:
        logger.warning(
            "Unknown ANKISMART_OCR_DEVICE, using auto mode",
            extra={"requested": requested},
        )

    return "gpu:0" if has_cuda else "cpu"


def _build_ocr_kwargs(device: str) -> dict[str, object]:
    det_model = os.getenv("ANKISMART_OCR_DET_MODEL", OCR_MODEL_PRESETS["lite"]["det"])
    rec_model = os.getenv("ANKISMART_OCR_REC_MODEL", OCR_MODEL_PRESETS["lite"]["rec"])
    model_root = _resolve_model_root()
    model_root.mkdir(parents=True, exist_ok=True)

    det_model_dir = _choose_model_dir(
        model_name=det_model,
        env_var_name="ANKISMART_OCR_DET_MODEL_DIR",
        model_root=model_root,
        role="det",
    )
    rec_model_dir = _choose_model_dir(
        model_name=rec_model,
        env_var_name="ANKISMART_OCR_REC_MODEL_DIR",
        model_root=model_root,
        role="rec",
    )

    kwargs: dict[str, object] = {
        "text_detection_model_name": det_model,
        "text_recognition_model_name": rec_model,
        "use_doc_orientation_classify": False,
        "use_doc_unwarping": False,
        "use_textline_orientation": False,
        "text_det_limit_type": os.getenv("ANKISMART_OCR_DET_LIMIT_TYPE", "max"),
        "text_det_limit_side_len": _get_env_int(
            "ANKISMART_OCR_DET_LIMIT_SIDE_LEN",
            640,
            min_value=1,
        ),
        "text_recognition_batch_size": _get_env_int(
            "ANKISMART_OCR_REC_BATCH_SIZE",
            1,
            min_value=1,
        ),
        "device": device,
    }

    if det_model_dir is not None:
        kwargs["text_detection_model_dir"] = det_model_dir
    if rec_model_dir is not None:
        kwargs["text_recognition_model_dir"] = rec_model_dir

    if device == "cpu":
        kwargs["enable_mkldnn"] = _get_env_bool("ANKISMART_OCR_CPU_MKLDNN", True)
        kwargs["cpu_threads"] = _get_env_int(
            "ANKISMART_OCR_CPU_THREADS",
            min(4, os.cpu_count() or 1),
            min_value=1,
        )

    return kwargs


def _is_onednn_unimplemented_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "onednn" in message
        and (
            "unimplemented" in message
            or "convertpirattribute2runtimeattribute" in message
        )
    )


def _is_gpu_runtime_error(exc: Exception) -> bool:
    message = str(exc).lower()
    gpu_markers = (
        "cuda",
        "cudnn",
        "cublas",
        "gpu",
        "out of memory",
        "memory alloc",
        "device-side assert",
        "driver",
    )
    return any(marker in message for marker in gpu_markers)


def _get_runtime_device_for_retry() -> str:
    runtime_device = _ocr_runtime_device
    if runtime_device:
        return runtime_device
    return _resolve_ocr_device()


def _should_retry_without_mkldnn(exc: Exception) -> bool:
    if _mkldnn_fallback_applied:
        return False
    if _get_runtime_device_for_retry() != "cpu":
        return False
    if not _get_env_bool("ANKISMART_OCR_CPU_MKLDNN", True):
        return False
    return _is_onednn_unimplemented_error(exc)


def _should_retry_with_cpu(exc: Exception) -> bool:
    runtime_device = _get_runtime_device_for_retry()
    if not runtime_device.startswith("gpu"):
        return False
    return _is_gpu_runtime_error(exc)


def _reload_ocr_on_cpu(*, reason: str, original_error: Exception | None = None) -> "PaddleOCR":
    global _ocr_instance, _gpu_fallback_applied, _ocr_runtime_device

    with _ocr_lock:
        kwargs = _build_ocr_kwargs("cpu")
        logger.warning(
            "Retrying OCR on CPU after CUDA runtime failure",
            extra={
                "reason": reason,
                "error": str(original_error) if original_error is not None else "",
                "det_model": kwargs.get("text_detection_model_name"),
                "rec_model": kwargs.get("text_recognition_model_name"),
            },
        )
        _ocr_instance = _load_paddle_ocr_class()(**kwargs)
        _gpu_fallback_applied = True
        _ocr_runtime_device = "cpu"
        return _ocr_instance


def _load_paddle_ocr_class():
    global PaddleOCR
    if PaddleOCR is None:
        from paddleocr import PaddleOCR as PaddleOCRClass

        PaddleOCR = PaddleOCRClass
    return PaddleOCR


def _reload_ocr_without_mkldnn() -> "PaddleOCR":
    global _ocr_instance, _mkldnn_fallback_applied, _ocr_runtime_device

    with _ocr_lock:
        os.environ["ANKISMART_OCR_CPU_MKLDNN"] = "0"
        kwargs = _build_ocr_kwargs("cpu")
        kwargs["enable_mkldnn"] = False
        logger.warning(
            "Retrying OCR with MKLDNN disabled due to oneDNN runtime error",
            extra={
                "det_model": kwargs.get("text_detection_model_name"),
                "rec_model": kwargs.get("text_recognition_model_name"),
            },
        )
        _ocr_instance = _load_paddle_ocr_class()(**kwargs)
        _mkldnn_fallback_applied = True
        _ocr_runtime_device = "cpu"
        return _ocr_instance


def _get_ocr() -> "PaddleOCR":
    global _ocr_instance, _gpu_fallback_applied, _ocr_runtime_device
    if _ocr_instance is not None:
        return _ocr_instance

    with _ocr_lock:
        if _ocr_instance is None:
            device = _resolve_ocr_device()
            if _gpu_fallback_applied and device.startswith("gpu"):
                device = "cpu"
            kwargs = _build_ocr_kwargs(device)
            logger.info(
                "Initializing PaddleOCR",
                extra={
                    "event": "ocr.engine.init",
                    "device": device,
                    "det_model": kwargs.get("text_detection_model_name"),
                    "det_model_dir": kwargs.get("text_detection_model_dir"),
                    "rec_model": kwargs.get("text_recognition_model_name"),
                    "rec_model_dir": kwargs.get("text_recognition_model_dir"),
                    "det_limit_side_len": kwargs.get("text_det_limit_side_len"),
                    "det_limit_type": kwargs.get("text_det_limit_type"),
                },
            )
            try:
                _ocr_instance = _load_paddle_ocr_class()(**kwargs)
                _ocr_runtime_device = device
            except Exception as exc:
                if not device.startswith("gpu"):
                    raise
                logger.warning(
                    "Failed to initialize PaddleOCR on CUDA, fallback to CPU runtime",
                    extra={"error": str(exc), "requested_device": device},
                )
                cpu_kwargs = _build_ocr_kwargs("cpu")
                _ocr_instance = _load_paddle_ocr_class()(**cpu_kwargs)
                _ocr_runtime_device = "cpu"
                _gpu_fallback_applied = True

    return _ocr_instance


def preload_ocr() -> None:
    thread = threading.Thread(target=_get_ocr, daemon=True)
    thread.start()


def _pdf_to_images(file_path: Path):
    return _pdf._pdf_to_images(file_path, pdfium_module=pdfium)


def _extract_pdf_text(file_path: Path) -> str | None:
    return _pdf._extract_pdf_text(file_path, pdfium_module=pdfium)


def _is_meaningful_text(content: str) -> bool:
    return _pdf._is_meaningful_text(content)


def _ocr_image(ocr: "PaddleOCR", image: Image.Image) -> str:
    img_array = np.array(image)
    try:
        result = ocr.predict(img_array, use_textline_orientation=False)
    except Exception as exc:
        if _should_retry_with_cpu(exc):
            logger.warning(
                "CUDA OCR error detected, fallback to CPU OCR runtime",
                extra={"error": str(exc)},
            )
            retry_ocr = _reload_ocr_on_cpu(reason="predict_failure", original_error=exc)
            result = retry_ocr.predict(img_array, use_textline_orientation=False)
        elif not _should_retry_without_mkldnn(exc):
            raise
        else:
            logger.warning(
                "oneDNN error detected, fallback to non-MKLDNN OCR runtime",
                extra={"error": str(exc)},
            )
            retry_ocr = _reload_ocr_without_mkldnn()
            result = retry_ocr.predict(img_array, use_textline_orientation=False)
    finally:
        del img_array

    if not result:
        return ""

    page_result = result[0]
    if not page_result:
        return ""

    rec_texts = None
    if hasattr(page_result, "get"):
        rec_texts = page_result.get("rec_texts")

    if not rec_texts and hasattr(page_result, "json"):
        try:
            rec_texts = page_result.json.get("res", {}).get("rec_texts")
        except (AttributeError, TypeError, KeyError) as exc:
            logger.warning(f"Failed to extract rec_texts from page_result.json: {exc}")
            rec_texts = None

    if not rec_texts:
        return ""

    lines: list[str] = []
    for text in rec_texts:
        line = str(text).strip()
        if not line:
            continue
        if _is_page_marker_line(line):
            continue
        lines.append(line)
    return "\n".join(lines)


def convert(
    file_path: Path,
    trace_id: str = "",
    *,
    ocr_correction_fn=None,
    progress_callback=None,
    ocr_mode: str = "local",
    cloud_provider: str = "",
    cloud_endpoint: str = "",
    cloud_api_key: str = "",
    proxy_url: str = "",
) -> MarkdownResult:
    trace_id = trace_id or get_trace_id()

    if not file_path.exists():
        raise ConvertError(
            f"File not found: {file_path}",
            code=ErrorCode.E_FILE_NOT_FOUND,
            trace_id=trace_id,
        )

    if str(ocr_mode).strip().lower() == "cloud":
        return _convert_via_cloud(
            file_path=file_path,
            source_format="pdf",
            trace_id=trace_id,
            progress_callback=progress_callback,
            cloud_provider=cloud_provider,
            cloud_endpoint=cloud_endpoint,
            cloud_api_key=cloud_api_key,
            proxy_url=proxy_url,
        )

    if progress_callback is not None:
        progress_callback(0, 1, "检测 PDF 文字层...")

    extracted_text = _extract_pdf_text(file_path)
    if extracted_text is not None:
        extracted_text = _remove_page_marker_lines(extracted_text)
    if extracted_text:
        logger.info(
            "PDF has text layer, using direct extraction",
            extra={"trace_id": trace_id, "event": "ocr.pdf.text_layer"},
        )
        if progress_callback is not None:
            progress_callback(1, 1, "文字提取完成")
        return MarkdownResult(
            content=extracted_text,
            source_path=str(file_path),
            source_format="pdf",
            trace_id=trace_id,
        )

    logger.info(
        "PDF has no text layer, using OCR",
        extra={"trace_id": trace_id, "event": "ocr.pdf.fallback_to_image"},
    )

    with timed("ocr_convert"):
        try:
            total_pages = _pdf.count_pdf_pages(file_path, pdfium_module=pdfium)
        except (OSError, RuntimeError, ValueError) as exc:
            logger.warning(f"Failed to get PDF page count: {exc}", extra={"trace_id": trace_id})
            total_pages = 0

        sections: list[str] = []
        page_count = 0
        for i, image in enumerate(_pdf_to_images(file_path), 1):
            try:
                page_count += 1
                if progress_callback is not None:
                    progress_callback(i, total_pages, f"正在识别第 {i}/{total_pages} 页")

                with timed(f"ocr_page_{i}"):
                    with _borrow_ocr() as ocr:
                        page_text = _ocr_image(ocr, image)

                if page_text.strip():
                    sections.append(f"## Page {i}\n\n{page_text}")
                else:
                    logger.warning(
                        "Empty OCR result for page",
                        extra={"page": i, "trace_id": trace_id},
                    )
            finally:
                close_fn = getattr(image, "close", None)
                if callable(close_fn):
                    close_fn()

        if page_count == 0:
            raise ConvertError(
                "PDF contains no pages",
                code=ErrorCode.E_OCR_FAILED,
                trace_id=trace_id,
            )

        if progress_callback is not None:
            progress_callback(page_count, page_count, f"OCR 识别完成，共 {page_count} 页")

        content = "\n\n---\n\n".join(sections) if sections else ""
        if content.strip() and ocr_correction_fn is not None:
            try:
                with timed("ocr_correction"):
                    content = ocr_correction_fn(content)
            except (ValueError, RuntimeError, OSError) as exc:
                logger.warning(
                    f"OCR correction failed, using raw text: {exc}",
                    extra={"trace_id": trace_id},
                )
        content = _remove_page_marker_lines(content)

        if not content.strip():
            logger.warning(
                "OCR produced no text from PDF",
                extra={"trace_id": trace_id},
            )

    return MarkdownResult(
        content=content,
        source_path=str(file_path),
        source_format="pdf",
        trace_id=trace_id,
    )


def convert_image(
    file_path: Path,
    trace_id: str = "",
    *,
    ocr_correction_fn=None,
    progress_callback=None,
    ocr_mode: str = "local",
    cloud_provider: str = "",
    cloud_endpoint: str = "",
    cloud_api_key: str = "",
    proxy_url: str = "",
) -> MarkdownResult:
    trace_id = trace_id or get_trace_id()

    if not file_path.exists():
        raise ConvertError(
            f"File not found: {file_path}",
            code=ErrorCode.E_FILE_NOT_FOUND,
            trace_id=trace_id,
        )

    if str(ocr_mode).strip().lower() == "cloud":
        return _convert_via_cloud(
            file_path=file_path,
            source_format="image",
            trace_id=trace_id,
            progress_callback=progress_callback,
            cloud_provider=cloud_provider,
            cloud_endpoint=cloud_endpoint,
            cloud_api_key=cloud_api_key,
            proxy_url=proxy_url,
        )

    with timed("ocr_image_convert"):
        with Image.open(file_path) as image:
            with _borrow_ocr() as ocr:
                if progress_callback is not None:
                    progress_callback("OCR 正在识别图片...")
                text = _ocr_image(ocr, image)
                if progress_callback is not None:
                    progress_callback("OCR 图片识别完成")

        if text.strip() and ocr_correction_fn is not None:
            try:
                with timed("ocr_correction"):
                    text = ocr_correction_fn(text)
            except (ValueError, RuntimeError, OSError) as exc:
                logger.warning(
                    f"OCR correction failed, using raw text: {exc}",
                    extra={"trace_id": trace_id},
                )
        text = _remove_page_marker_lines(text)

    return MarkdownResult(
        content=text,
        source_path=str(file_path),
        source_format="image",
        trace_id=trace_id,
    )
