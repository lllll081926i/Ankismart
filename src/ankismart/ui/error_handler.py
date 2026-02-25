"""Error handling utilities for Ankismart UI.

Provides user-friendly error messages, recovery suggestions, and error classification.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox, QWidget
from qfluentwidgets import InfoBar, InfoBarPosition, MessageBox

logger = logging.getLogger(__name__)


class ErrorLevel(Enum):
    """Error severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for classification."""

    NETWORK = "network"
    API_KEY = "api_key"
    FILE_FORMAT = "file_format"
    OCR = "ocr"
    ANKI_CONNECTION = "anki_connection"
    LLM_PROVIDER = "llm_provider"
    PERMISSION = "permission"
    VALIDATION = "validation"
    UNKNOWN = "unknown"


@dataclass
class ErrorInfo:
    """Structured error information."""

    category: ErrorCategory
    level: ErrorLevel
    title: str
    message: str
    suggestion: str
    technical_details: str = ""
    action_button: str | None = None
    action_callback: Callable | None = None


class ErrorHandler:
    """Centralized error handler with user-friendly messages."""

    def __init__(self, language: str = "zh"):
        """Initialize error handler.

        Args:
            language: Language code ("zh" or "en")
        """
        self.language = language
        self._error_patterns = self._build_error_patterns()

    def _build_error_patterns(self) -> dict[str, ErrorInfo]:
        """Build error pattern matching rules."""
        is_zh = self.language == "zh"

        return {
            # Network errors
            "connection": ErrorInfo(
                category=ErrorCategory.NETWORK,
                level=ErrorLevel.ERROR,
                title="网络连接失败" if is_zh else "Network Connection Failed",
                message="无法连接到服务器，请检查网络连接"
                if is_zh
                else "Cannot connect to server, please check network connection",
                suggestion="• 检查网络连接是否正常\n• 检查代理设置\n• 确认服务器地址正确"
                if is_zh
                else (
                    "• Check network connection\n• Verify proxy settings\n"
                    "• Confirm server address is correct"
                ),
                action_button="去设置" if is_zh else "Go to Settings",
            ),
            "timeout": ErrorInfo(
                category=ErrorCategory.NETWORK,
                level=ErrorLevel.WARNING,
                title="请求超时" if is_zh else "Request Timeout",
                message="服务器响应超时，请稍后重试"
                if is_zh
                else "Server response timeout, please retry later",
                suggestion="• 检查网络速度\n• 尝试使用代理\n• 稍后重试"
                if is_zh
                else "• Check network speed\n• Try using a proxy\n• Retry later",
                action_button="重试" if is_zh else "Retry",
            ),
            "proxy": ErrorInfo(
                category=ErrorCategory.NETWORK,
                level=ErrorLevel.ERROR,
                title="代理连接失败" if is_zh else "Proxy Connection Failed",
                message="无法通过代理连接，请检查代理设置"
                if is_zh
                else "Cannot connect through proxy, please check proxy settings",
                suggestion="• 检查代理地址格式\n• 确认代理服务可用\n• 尝试关闭代理"
                if is_zh
                else (
                    "• Check proxy address format\n• Confirm proxy service is available\n"
                    "• Try disabling proxy"
                ),
                action_button="去设置" if is_zh else "Go to Settings",
            ),
            # API Key errors
            "api_key": ErrorInfo(
                category=ErrorCategory.API_KEY,
                level=ErrorLevel.ERROR,
                title="API Key 无效" if is_zh else "Invalid API Key",
                message="API Key 无效或已过期，请在设置中检查配置"
                if is_zh
                else "API Key is invalid or expired, please check configuration in settings",
                suggestion="• 检查 API Key 是否正确\n• 确认 API Key 未过期\n• 检查账户余额"
                if is_zh
                else (
                    "• Verify API Key is correct\n• Confirm API Key is not expired\n"
                    "• Check account balance"
                ),
                action_button="去设置" if is_zh else "Go to Settings",
            ),
            "unauthorized": ErrorInfo(
                category=ErrorCategory.API_KEY,
                level=ErrorLevel.ERROR,
                title="认证失败" if is_zh else "Authentication Failed",
                message="API 认证失败，请检查 API Key 配置"
                if is_zh
                else "API authentication failed, please check API Key configuration",
                suggestion="• 重新输入 API Key\n• 确认使用正确的提供商\n• 检查 API Key 权限"
                if is_zh
                else (
                    "• Re-enter API Key\n• Confirm using correct provider\n"
                    "• Check API Key permissions"
                ),
                action_button="去设置" if is_zh else "Go to Settings",
            ),
            # File format errors
            "file_format": ErrorInfo(
                category=ErrorCategory.FILE_FORMAT,
                level=ErrorLevel.WARNING,
                title="文件格式错误" if is_zh else "File Format Error",
                message="不支持的文件格式，请选择 PDF、Word、PPT 或图片"
                if is_zh
                else "Unsupported file format, please select PDF, Word, PPT or images",
                suggestion=(
                    "• 支持的格式：PDF、DOCX、PPTX、PNG、JPG\n"
                    "• 检查文件是否损坏\n"
                    "• 尝试转换为支持的格式"
                )
                if is_zh
                else (
                    "• Supported formats: PDF, DOCX, PPTX, PNG, JPG\n"
                    "• Check if file is corrupted\n• Try converting to supported format"
                ),
            ),
            "file_corrupted": ErrorInfo(
                category=ErrorCategory.FILE_FORMAT,
                level=ErrorLevel.ERROR,
                title="文件损坏" if is_zh else "File Corrupted",
                message="文件可能已损坏，无法读取"
                if is_zh
                else "File may be corrupted and cannot be read",
                suggestion="• 尝试重新下载文件\n• 使用其他工具打开验证\n• 选择其他文件"
                if is_zh
                else (
                    "• Try re-downloading the file\n• Verify with other tools\n"
                    "• Select another file"
                ),
            ),
            "file_too_large": ErrorInfo(
                category=ErrorCategory.FILE_FORMAT,
                level=ErrorLevel.WARNING,
                title="文件过大" if is_zh else "File Too Large",
                message="超出云 OCR 文件限制：单文件不超过 200MB，PDF 不超过 600 页"
                if is_zh
                else "Cloud OCR file limit exceeded: max 200MB per file and max 600 PDF pages",
                suggestion=(
                    "• 压缩或拆分文件（<=200MB）\n"
                    "• 拆分 PDF，确保每个文件 <=600 页\n"
                    "• 云端模式下建议按章节分批导入"
                )
                if is_zh
                else (
                    "• Compress or split files (<=200MB)\n"
                    "• Split PDF to keep each file <=600 pages\n"
                    "• In cloud mode, import by chapter in smaller batches"
                ),
                action_button="去设置" if is_zh else "Go to Settings",
            ),
            # OCR errors
            "ocr": ErrorInfo(
                category=ErrorCategory.OCR,
                level=ErrorLevel.WARNING,
                title="OCR 识别失败" if is_zh else "OCR Recognition Failed",
                message="OCR 识别失败，请确保图片清晰"
                if is_zh
                else "OCR recognition failed, please ensure image is clear",
                suggestion="• 使用更清晰的图片\n• 确保文字可读\n• 尝试调整图片亮度/对比度"
                if is_zh
                else (
                    "• Use clearer images\n• Ensure text is readable\n"
                    "• Try adjusting image brightness/contrast"
                ),
                action_button="重试" if is_zh else "Retry",
            ),
            "ocr_model": ErrorInfo(
                category=ErrorCategory.OCR,
                level=ErrorLevel.ERROR,
                title="OCR 模型缺失" if is_zh else "OCR Model Missing",
                message="OCR 模型文件缺失，需要下载"
                if is_zh
                else "OCR model files are missing and need to be downloaded",
                suggestion="• 点击下载按钮获取模型\n• 检查网络连接\n• 确保有足够磁盘空间"
                if is_zh
                else (
                    "• Click download button to get models\n• Check network connection\n"
                    "• Ensure sufficient disk space"
                ),
                action_button="下载模型" if is_zh else "Download Models",
            ),
            # Anki connection errors
            "anki_connection": ErrorInfo(
                category=ErrorCategory.ANKI_CONNECTION,
                level=ErrorLevel.ERROR,
                title="无法连接到 Anki" if is_zh else "Cannot Connect to Anki",
                message="无法连接到 AnkiConnect，请确保 Anki 正在运行"
                if is_zh
                else "Cannot connect to AnkiConnect, please ensure Anki is running",
                suggestion="• 启动 Anki 桌面应用\n• 安装 AnkiConnect 插件\n• 检查 AnkiConnect 设置"
                if is_zh
                else (
                    "• Start Anki desktop application\n• Install AnkiConnect add-on\n"
                    "• Check AnkiConnect settings"
                ),
                action_button="去设置" if is_zh else "Go to Settings",
            ),
            "anki_permission": ErrorInfo(
                category=ErrorCategory.ANKI_CONNECTION,
                level=ErrorLevel.ERROR,
                title="Anki 权限错误" if is_zh else "Anki Permission Error",
                message="AnkiConnect 拒绝访问，请检查权限设置"
                if is_zh
                else "AnkiConnect denied access, please check permission settings",
                suggestion="• 检查 AnkiConnect 配置\n• 确认 API Key 正确\n• 重启 Anki"
                if is_zh
                else (
                    "• Check AnkiConnect configuration\n• Confirm API Key is correct\n"
                    "• Restart Anki"
                ),
                action_button="去设置" if is_zh else "Go to Settings",
            ),
            # LLM provider errors
            "llm_provider": ErrorInfo(
                category=ErrorCategory.LLM_PROVIDER,
                level=ErrorLevel.ERROR,
                title="LLM 提供商错误" if is_zh else "LLM Provider Error",
                message="LLM 服务调用失败，请检查配置"
                if is_zh
                else "LLM service call failed, please check configuration",
                suggestion="• 检查提供商配置\n• 确认 API Key 有效\n• 检查账户额度"
                if is_zh
                else (
                    "• Check provider configuration\n• Confirm API Key is valid\n"
                    "• Check account quota"
                ),
                action_button="去设置" if is_zh else "Go to Settings",
            ),
            "rate_limit": ErrorInfo(
                category=ErrorCategory.LLM_PROVIDER,
                level=ErrorLevel.WARNING,
                title="接口限频" if is_zh else "Rate Limit Exceeded",
                message="触发接口限频（Rate Limit），请稍后重试"
                if is_zh
                else "API rate limit reached, please retry later",
                suggestion=(
                    "• 降低并发和轮询频率后重试\n"
                    "• MinerU 参考限频：提交 300 req/min，结果查询 1000 req/min\n"
                    "• 必要时升级套餐或错峰处理"
                )
                if is_zh
                else (
                    "• Reduce concurrency/polling frequency and retry\n"
                    "• MinerU reference limits: submit 300 req/min, query 1000 req/min\n"
                    "• Upgrade plan or retry at off-peak hours"
                ),
                action_button="重试" if is_zh else "Retry",
            ),
            "quota_exceeded": ErrorInfo(
                category=ErrorCategory.LLM_PROVIDER,
                level=ErrorLevel.ERROR,
                title="配额已用尽" if is_zh else "Quota Exceeded",
                message="账户可用配额不足或已用尽"
                if is_zh
                else "Insufficient or exhausted account quota",
                suggestion=(
                    "• 检查 MinerU 配额页与账户状态\n"
                    "• 免费账户每天 2000 页为最高优先级，超出后仅降优先级\n"
                    "• 如需更高吞吐可充值或升级套餐"
                )
                if is_zh
                else (
                    "• Check MinerU quota page and account status\n"
                    "• Free tier has 2000 high-priority pages/day, then lower priority\n"
                    "• Recharge or upgrade plan for higher throughput"
                ),
                action_button="去设置" if is_zh else "Go to Settings",
            ),
            # Permission errors
            "permission": ErrorInfo(
                category=ErrorCategory.PERMISSION,
                level=ErrorLevel.ERROR,
                title="权限不足" if is_zh else "Permission Denied",
                message="没有足够的权限执行此操作"
                if is_zh
                else "Insufficient permissions to perform this operation",
                suggestion="• 以管理员身份运行\n• 检查文件/文件夹权限\n• 更改保存位置"
                if is_zh
                else (
                    "• Run as administrator\n• Check file/folder permissions\n"
                    "• Change save location"
                ),
            ),
            # Validation errors
            "validation": ErrorInfo(
                category=ErrorCategory.VALIDATION,
                level=ErrorLevel.WARNING,
                title="输入验证失败" if is_zh else "Validation Failed",
                message="输入的数据格式不正确" if is_zh else "Input data format is incorrect",
                suggestion="• 检查输入格式\n• 确保必填项已填写\n• 参考示例格式"
                if is_zh
                else (
                    "• Check input format\n• Ensure required fields are filled\n"
                    "• Refer to example format"
                ),
            ),
        }

    def classify_error(self, error: Exception | str) -> ErrorInfo:
        """Classify error and return structured error information.

        Args:
            error: Exception object or error message string

        Returns:
            ErrorInfo object with classification and suggestions
        """
        raw_error = str(error).strip()
        error_str = raw_error.lower()
        is_zh = self.language == "zh"

        # Explicit structured error code from worker, e.g. "[E_LLM_AUTH_ERROR] ...".
        if raw_error.startswith("[") and "]" in raw_error:
            code_token, _, detail = raw_error.partition("]")
            code = code_token.lstrip("[").strip()
            detail_lower = detail.strip().lower()
            if code in {"E_LLM_AUTH_ERROR"}:
                return self._error_patterns["unauthorized"]
            if code in {"E_LLM_PERMISSION_ERROR"}:
                return self._error_patterns["permission"]
            if code in {"E_FILE_TYPE_UNSUPPORTED"}:
                return self._error_patterns["file_format"]
            if code in {"E_OCR_FAILED"}:
                if any(
                    keyword in detail_lower
                    for keyword in ["rate limit", "rate limited", "429", "too many"]
                ):
                    return self._error_patterns["rate_limit"]
                if any(
                    keyword in detail_lower
                    for keyword in [
                        "200mb",
                        "600-page",
                        "600 pages",
                        "600页",
                        "pages exceed",
                        "file size exceeds",
                    ]
                ):
                    return self._error_patterns["file_too_large"]
                if any(keyword in detail_lower for keyword in ["quota", "balance", "配额", "余额"]):
                    return self._error_patterns["quota_exceeded"]
                if any(
                    keyword in detail_lower
                    for keyword in ["auth", "unauthorized", "api key", "token", "401", "403"]
                ):
                    return self._error_patterns["unauthorized"]
                if any(keyword in detail_lower for keyword in ["timeout", "timed out", "超时"]):
                    return self._error_patterns["timeout"]
                return self._error_patterns["ocr"]
            if code in {"E_CONFIG_INVALID"}:
                if any(
                    keyword in detail_lower
                    for keyword in [
                        "200mb",
                        "600-page",
                        "600 pages",
                        "600页",
                        "pages exceed",
                        "file size exceeds",
                    ]
                ):
                    return self._error_patterns["file_too_large"]
                if any(
                    keyword in detail_lower
                    for keyword in ["api key", "token", "auth", "unauthorized", "401", "403"]
                ):
                    return self._error_patterns["api_key"]
                if any(
                    keyword in detail_lower
                    for keyword in ["endpoint", "url", "host", "dns", "connect", "connection"]
                ):
                    return self._error_patterns["connection"]
                return self._error_patterns["validation"]

        # Match error patterns
        if any(keyword in error_str for keyword in ["connection", "connect", "网络", "连接"]):
            if "proxy" in error_str or "代理" in error_str:
                return self._error_patterns["proxy"]
            if "timeout" in error_str or "超时" in error_str:
                return self._error_patterns["timeout"]
            if "anki" in error_str:
                return self._error_patterns["anki_connection"]
            return self._error_patterns["connection"]

        if any(
            keyword in error_str
            for keyword in ["api key", "api_key", "unauthorized", "401", "认证", "密钥"]
        ):
            if "unauthorized" in error_str or "401" in error_str:
                return self._error_patterns["unauthorized"]
            return self._error_patterns["api_key"]

        if any(keyword in error_str for keyword in ["format", "unsupported", "格式", "不支持"]):
            if "corrupt" in error_str or "损坏" in error_str:
                return self._error_patterns["file_corrupted"]
            if "large" in error_str or "size" in error_str or "过大" in error_str:
                return self._error_patterns["file_too_large"]
            return self._error_patterns["file_format"]

        if any(
            keyword in error_str
            for keyword in [
                "200mb",
                "600-page",
                "600 pages",
                "600页",
                "pages exceed",
                "file size exceeds",
            ]
        ):
            return self._error_patterns["file_too_large"]

        if any(keyword in error_str for keyword in ["ocr", "识别", "recognition"]):
            if any(
                keyword in error_str
                for keyword in ["rate limit", "rate limited", "429", "too many", "请求频率"]
            ):
                return self._error_patterns["rate_limit"]
            if any(keyword in error_str for keyword in ["quota", "配额", "余额"]):
                return self._error_patterns["quota_exceeded"]
            if any(
                keyword in error_str
                for keyword in ["auth", "unauthorized", "api key", "token", "401", "403"]
            ):
                return self._error_patterns["unauthorized"]
            if "model" in error_str or "模型" in error_str:
                return self._error_patterns["ocr_model"]
            return self._error_patterns["ocr"]

        if any(keyword in error_str for keyword in ["anki", "ankiconnect"]):
            if "permission" in error_str or "权限" in error_str:
                return self._error_patterns["anki_permission"]
            return self._error_patterns["anki_connection"]

        if any(keyword in error_str for keyword in ["rate limit", "too many", "频率", "过于频繁"]):
            return self._error_patterns["rate_limit"]

        if any(keyword in error_str for keyword in ["quota", "配额", "余额"]):
            return self._error_patterns["quota_exceeded"]

        if any(keyword in error_str for keyword in ["llm", "provider", "提供商"]):
            return self._error_patterns["llm_provider"]

        if any(keyword in error_str for keyword in ["permission", "denied", "权限"]):
            return self._error_patterns["permission"]

        if any(keyword in error_str for keyword in ["validation", "invalid", "验证", "无效"]):
            return self._error_patterns["validation"]

        # Unknown error
        return ErrorInfo(
            category=ErrorCategory.UNKNOWN,
            level=ErrorLevel.ERROR,
            title="未知错误" if is_zh else "Unknown Error",
            message="发生了未知错误" if is_zh else "An unknown error occurred",
            suggestion="• 查看详细错误信息\n• 尝试重启应用\n• 联系技术支持"
            if is_zh
            else (
                "• Check detailed error message\n• Try restarting application\n"
                "• Contact technical support"
            ),
            technical_details=str(error),
        )

    def show_error(
        self,
        parent: QWidget,
        error: Exception | str,
        use_infobar: bool = False,
        action_callback: Callable | None = None,
    ) -> None:
        """Show error message to user with appropriate UI component.

        Args:
            parent: Parent widget
            error: Exception object or error message
            use_infobar: If True, use InfoBar for non-critical errors; otherwise use MessageBox
            action_callback: Optional callback for action button
        """
        error_info = self.classify_error(error)

        # Log technical details
        logger.error(
            f"Error occurred: {error_info.category.value} - {error_info.title}",
            exc_info=isinstance(error, Exception),
        )

        # Store action callback if provided
        if action_callback:
            error_info.action_callback = action_callback

        # Choose display method based on severity and preference
        if use_infobar and error_info.level in (ErrorLevel.INFO, ErrorLevel.WARNING):
            self._show_infobar(parent, error_info)
        else:
            self._show_messagebox(parent, error_info)

    def _show_infobar(self, parent: QWidget, error_info: ErrorInfo) -> None:
        """Show error as InfoBar (for non-critical errors)."""
        # Map error level to InfoBar type
        level_map = {
            ErrorLevel.INFO: InfoBar.info,
            ErrorLevel.WARNING: InfoBar.warning,
            ErrorLevel.ERROR: InfoBar.error,
            ErrorLevel.CRITICAL: InfoBar.error,
        }

        show_func = level_map.get(error_info.level, InfoBar.warning)

        # Combine message and first suggestion line
        content = error_info.message
        if error_info.suggestion:
            first_suggestion = error_info.suggestion.split("\n")[0].strip("• ")
            content = f"{error_info.message}\n{first_suggestion}"

        show_func(
            title=error_info.title,
            content=content,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000 if error_info.level == ErrorLevel.WARNING else 7000,
            parent=parent,
        )

    def _show_messagebox(self, parent: QWidget, error_info: ErrorInfo) -> None:
        """Show error as MessageBox (for critical errors or detailed info)."""
        # Combine message and suggestions
        full_message = f"{error_info.message}\n\n{error_info.suggestion}"

        if error_info.technical_details:
            full_message += (
                f"\n\n技术详情：\n{error_info.technical_details}"
                if self.language == "zh"
                else f"\n\nTechnical Details:\n{error_info.technical_details}"
            )

        # Create message box
        msg_box = MessageBox(error_info.title, full_message, parent)

        # Set icon based on level
        if error_info.level == ErrorLevel.CRITICAL:
            msg_box.setIcon(QMessageBox.Icon.Critical)
        elif error_info.level == ErrorLevel.ERROR:
            msg_box.setIcon(QMessageBox.Icon.Warning)
        elif error_info.level == ErrorLevel.WARNING:
            msg_box.setIcon(QMessageBox.Icon.Warning)
        else:
            msg_box.setIcon(QMessageBox.Icon.Information)

        # Add action button if specified
        if error_info.action_button and error_info.action_callback:
            msg_box.yesButton.setText(error_info.action_button)
            msg_box.cancelButton.setText("取消" if self.language == "zh" else "Cancel")
            if msg_box.exec():
                error_info.action_callback()
        else:
            msg_box.cancelButton.hide()
            msg_box.yesButton.setText("确定" if self.language == "zh" else "OK")
            msg_box.exec()

    def log_error(self, error: Exception | str, context: str = "") -> None:
        """Log error with context information.

        Args:
            error: Exception object or error message
            context: Additional context information
        """
        error_info = self.classify_error(error)

        log_message = f"[{error_info.category.value}] {error_info.title}"
        if context:
            log_message += f" | Context: {context}"

        if isinstance(error, Exception):
            logger.error(log_message, exc_info=True)
        else:
            logger.error(f"{log_message} | Details: {error}")
