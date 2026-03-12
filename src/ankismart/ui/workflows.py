from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ankismart.core.config import AppConfig


@dataclass(frozen=True, slots=True)
class StartupPrecheckItem:
    key: str
    status: str
    title: str
    detail: str


@dataclass(frozen=True, slots=True)
class StartupPrecheckReport:
    summary: str
    items: tuple[StartupPrecheckItem, ...]


@dataclass(frozen=True, slots=True)
class ConvertWorkflowRequest:
    language: str
    file_paths: tuple[Path, ...]
    deck_name: str
    strategy_mix: tuple[dict[str, object], ...]
    provider_name: str
    provider_api_key: str
    allow_keyless_provider: bool = False


@dataclass(frozen=True, slots=True)
class WorkflowValidationIssue:
    title: str
    content: str
    focus_target: str | None = None


def build_startup_precheck_report(
    config: AppConfig,
    *,
    get_missing_ocr_models: Callable[..., list[str]],
    runtime_error_types: tuple[type[BaseException], ...] = (),
) -> StartupPrecheckReport:
    is_zh = config.language == "zh"
    items: list[StartupPrecheckItem] = []

    provider = config.active_provider
    if provider is None:
        items.append(
            StartupPrecheckItem(
                key="llm",
                status="warning",
                title="LLM",
                detail=(
                    "未配置 LLM 提供商，请先在设置页添加。"
                    if is_zh
                    else "No LLM provider configured. Add one in Settings."
                ),
            )
        )
    elif "Ollama" not in provider.name and not provider.api_key.strip():
        items.append(
            StartupPrecheckItem(
                key="llm",
                status="warning",
                title="LLM",
                detail=(
                    f"{provider.name} 缺少 API Key。"
                    if is_zh
                    else f"{provider.name} is missing an API key."
                ),
            )
        )
    else:
        model_text = provider.model.strip() or ("未设置模型" if is_zh else "model not set")
        items.append(
            StartupPrecheckItem(
                key="llm",
                status="success",
                title="LLM",
                detail=f"{provider.name} / {model_text}",
            )
        )

    anki_url = str(getattr(config, "anki_connect_url", "")).strip()
    if not anki_url:
        items.append(
            StartupPrecheckItem(
                key="anki",
                status="warning",
                title="Anki",
                detail=(
                    "未配置 AnkiConnect URL。"
                    if is_zh
                    else "AnkiConnect URL is not configured."
                ),
            )
        )
    else:
        items.append(
            StartupPrecheckItem(
                key="anki",
                status="info",
                title="Anki",
                detail=(
                    f"{anki_url}；可在设置页执行连通性测试。"
                    if is_zh
                    else f"{anki_url}; run connectivity test in Settings."
                ),
            )
        )

    ocr_mode = str(getattr(config, "ocr_mode", "local")).strip().lower()
    if ocr_mode == "cloud":
        endpoint = str(getattr(config, "ocr_cloud_endpoint", "")).strip()
        api_key = str(getattr(config, "ocr_cloud_api_key", "")).strip()
        if not endpoint or not api_key:
            items.append(
                StartupPrecheckItem(
                    key="ocr",
                    status="warning",
                    title="OCR",
                    detail=(
                        "云 OCR 配置不完整，请补全 Endpoint 和 API Key。"
                        if is_zh
                        else "Cloud OCR config is incomplete. Fill endpoint and API key."
                    ),
                )
            )
        else:
            items.append(
                StartupPrecheckItem(
                    key="ocr",
                    status="info",
                    title="OCR",
                    detail=(
                        f"云 OCR 已配置：{endpoint}"
                        if is_zh
                        else f"Cloud OCR configured: {endpoint}"
                    ),
                )
            )
        return StartupPrecheckReport(
            summary=_build_precheck_summary(is_zh, items),
            items=tuple(items),
        )

    try:
        missing_models = get_missing_ocr_models(
            model_tier=str(getattr(config, "ocr_model_tier", "lite")),
            model_source=str(getattr(config, "ocr_model_source", "official")),
        )
    except runtime_error_types:
        items.append(
            StartupPrecheckItem(
                key="ocr",
                status="warning",
                title="OCR",
                detail=(
                    "当前环境未包含本地 OCR 运行时。"
                    if is_zh
                    else "Local OCR runtime is not bundled in this environment."
                ),
            )
        )
        return StartupPrecheckReport(
            summary=_build_precheck_summary(is_zh, items),
            items=tuple(items),
        )
    except Exception as exc:
        items.append(
            StartupPrecheckItem(
                key="ocr",
                status="info",
                title="OCR",
                detail=(
                    f"OCR 状态暂无法确认：{exc}"
                    if is_zh
                    else f"OCR status is temporarily unavailable: {exc}"
                ),
            )
        )
        return StartupPrecheckReport(
            summary=_build_precheck_summary(is_zh, items),
            items=tuple(items),
        )

    if missing_models:
        missing_text = ", ".join(missing_models)
        items.append(
            StartupPrecheckItem(
                key="ocr",
                status="warning",
                title="OCR",
                detail=(
                    f"缺少本地 OCR 模型：{missing_text}"
                    if is_zh
                    else f"Missing local OCR models: {missing_text}"
                ),
            )
        )
    else:
        items.append(
            StartupPrecheckItem(
                key="ocr",
                status="success",
                title="OCR",
                detail="本地 OCR 模型已就绪。" if is_zh else "Local OCR models are ready.",
            )
        )

    return StartupPrecheckReport(
        summary=_build_precheck_summary(is_zh, items),
        items=tuple(items),
    )


def _build_precheck_summary(is_zh: bool, items: list[StartupPrecheckItem]) -> str:
    pending_count = sum(1 for item in items if item.status == "warning")
    if pending_count == 0:
        return (
            "首次使用预检已通过，可以直接开始导入。"
            if is_zh
            else "Preflight passed. You can start importing now."
        )
    return (
        f"首次使用预检：还有 {pending_count} 项待确认。"
        if is_zh
        else f"Preflight: {pending_count} items still need attention."
    )


def format_startup_precheck_item(item: StartupPrecheckItem) -> str:
    icon = {
        "success": "OK",
        "warning": "!",
        "info": "...",
    }.get(item.status, "-")
    return f"[{icon}] {item.title}: {item.detail}"


def validate_convert_request(request: ConvertWorkflowRequest) -> WorkflowValidationIssue | None:
    is_zh = request.language == "zh"

    if not request.file_paths:
        return WorkflowValidationIssue(
            title="警告" if is_zh else "Warning",
            content="请先选择要转换的文件"
            if is_zh
            else "Please select files to convert first",
            focus_target="files",
        )

    if not request.deck_name.strip():
        return WorkflowValidationIssue(
            title="警告" if is_zh else "Warning",
            content="请填写有效的牌组名称。"
            if is_zh
            else "Please enter a valid deck name.",
            focus_target="deck",
        )

    if not request.provider_name.strip():
        return WorkflowValidationIssue(
            title="警告" if is_zh else "Warning",
            content="请先在设置中配置 LLM 提供商。"
            if is_zh
            else "Configure an LLM provider in Settings first.",
            focus_target="provider",
        )

    if not request.allow_keyless_provider and not request.provider_api_key.strip():
        return WorkflowValidationIssue(
            title="警告" if is_zh else "Warning",
            content="当前提供商缺少 API Key，请先在设置中补全。"
            if is_zh
            else "The selected provider is missing an API key. Update it in Settings first.",
            focus_target="provider",
        )

    if not request.strategy_mix:
        return WorkflowValidationIssue(
            title="警告" if is_zh else "Warning",
            content="请至少选择一种卡片策略并设置占比。"
            if is_zh
            else "Select at least one card strategy with a positive ratio.",
            focus_target="strategy",
        )

    return None
