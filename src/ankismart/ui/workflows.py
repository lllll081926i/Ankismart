from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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
