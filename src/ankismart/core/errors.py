from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    E_DECK_NOT_FOUND = "E_DECK_NOT_FOUND"
    E_MODEL_NOT_FOUND = "E_MODEL_NOT_FOUND"
    E_REQUIRED_FIELD_MISSING = "E_REQUIRED_FIELD_MISSING"
    E_CLOZE_SYNTAX_INVALID = "E_CLOZE_SYNTAX_INVALID"
    E_MEDIA_INVALID = "E_MEDIA_INVALID"
    E_ANKICONNECT_ERROR = "E_ANKICONNECT_ERROR"
    E_CONVERT_FAILED = "E_CONVERT_FAILED"
    E_OCR_FAILED = "E_OCR_FAILED"
    E_LLM_ERROR = "E_LLM_ERROR"
    E_LLM_AUTH_ERROR = "E_LLM_AUTH_ERROR"
    E_LLM_PERMISSION_ERROR = "E_LLM_PERMISSION_ERROR"
    E_LLM_PARSE_ERROR = "E_LLM_PARSE_ERROR"
    E_CONFIG_INVALID = "E_CONFIG_INVALID"
    E_FILE_NOT_FOUND = "E_FILE_NOT_FOUND"
    E_FILE_TYPE_UNSUPPORTED = "E_FILE_TYPE_UNSUPPORTED"
    E_UNKNOWN = "E_UNKNOWN"


class AnkiSmartError(Exception):
    def __init__(
        self,
        code: ErrorCode = ErrorCode.E_UNKNOWN,
        message: str = "",
        trace_id: str | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.trace_id = trace_id
        super().__init__(message)

    def to_dict(self) -> dict[str, str]:
        return {
            "code": str(self.code),
            "message": self.message,
            "traceId": self.trace_id or "",
        }


class ConvertError(AnkiSmartError):
    def __init__(
        self,
        message: str = "Document conversion failed",
        *,
        code: ErrorCode = ErrorCode.E_CONVERT_FAILED,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(code=code, message=message, trace_id=trace_id)


class CardGenError(AnkiSmartError):
    def __init__(
        self,
        message: str = "Card generation failed",
        *,
        code: ErrorCode = ErrorCode.E_LLM_ERROR,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(code=code, message=message, trace_id=trace_id)


class AnkiGatewayError(AnkiSmartError):
    def __init__(
        self,
        message: str = "AnkiConnect communication error",
        *,
        code: ErrorCode = ErrorCode.E_ANKICONNECT_ERROR,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(code=code, message=message, trace_id=trace_id)


class ConfigError(AnkiSmartError):
    def __init__(
        self,
        message: str = "Configuration validation failed",
        *,
        code: ErrorCode = ErrorCode.E_CONFIG_INVALID,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(code=code, message=message, trace_id=trace_id)


# Error code to user-friendly message mappings
ERROR_MESSAGES = {
    "zh": {
        ErrorCode.E_DECK_NOT_FOUND: {
            "title": "牌组未找到",
            "message": "指定的 Anki 牌组不存在",
            "solution": "• 在 Anki 中创建该牌组\n• 检查牌组名称是否正确\n• 在设置中选择其他牌组",
        },
        ErrorCode.E_MODEL_NOT_FOUND: {
            "title": "笔记类型未找到",
            "message": "指定的 Anki 笔记类型不存在",
            "solution": "• 确认笔记类型已在 Anki 中创建\n• 检查笔记类型名称拼写\n• 使用默认笔记类型",
        },
        ErrorCode.E_REQUIRED_FIELD_MISSING: {
            "title": "必填字段缺失",
            "message": "卡片缺少必填字段内容",
            "solution": "• 检查卡片内容是否完整\n• 确认笔记类型字段配置\n• 重新生成卡片",
        },
        ErrorCode.E_CLOZE_SYNTAX_INVALID: {
            "title": "填空语法错误",
            "message": "填空卡片的语法格式不正确",
            "solution": "• 检查 {{c1::}} 格式是否正确\n• 确保填空编号连续\n• 参考 Anki 填空语法文档",
        },
        ErrorCode.E_MEDIA_INVALID: {
            "title": "媒体文件无效",
            "message": "卡片中的图片或音频文件无效",
            "solution": "• 检查文件是否存在\n• 确认文件格式支持\n• 重新添加媒体文件",
        },
        ErrorCode.E_ANKICONNECT_ERROR: {
            "title": "AnkiConnect 连接失败",
            "message": "无法连接到 AnkiConnect，请确保 Anki 正在运行",
            "solution": "• 启动 Anki 桌面应用\n• 安装 AnkiConnect 插件（代码：2055492159）\n• 检查 AnkiConnect 端口设置（默认 8765）\n• 确认防火墙未阻止连接",
        },
        ErrorCode.E_CONVERT_FAILED: {
            "title": "文档转换失败",
            "message": "无法将文档转换为可处理的格式",
            "solution": "• 检查文件是否损坏\n• 确认文件格式支持（PDF、DOCX、PPTX）\n• 尝试使用其他文件\n• 检查文件是否有密码保护",
        },
        ErrorCode.E_OCR_FAILED: {
            "title": "OCR 识别失败",
            "message": "图片文字识别失败",
            "solution": "• 使用更清晰的图片\n• 确保图片中有可识别的文字\n• 调整图片亮度和对比度\n• 检查 OCR 模型是否已下载",
        },
        ErrorCode.E_LLM_ERROR: {
            "title": "AI 生成失败",
            "message": "AI 模型调用失败，无法生成卡片",
            "solution": "• 检查网络连接\n• 验证 API Key 是否有效\n• 确认账户余额充足\n• 检查 API 服务状态\n• 尝试切换其他 AI 提供商",
        },
        ErrorCode.E_LLM_AUTH_ERROR: {
            "title": "LLM 认证失败",
            "message": "LLM 接口认证失败（401），请检查 API Key 或 Token",
            "solution": "• 检查 API Key 是否正确\n• 确认密钥未过期或被吊销\n• 确认请求的 Base URL 与提供商一致",
        },
        ErrorCode.E_LLM_PERMISSION_ERROR: {
            "title": "LLM 权限不足",
            "message": "LLM 接口拒绝访问（403），当前账户或密钥无权限",
            "solution": "• 检查账号/项目权限\n• 确认模型访问权限已开通\n• 检查组织或项目配额策略",
        },
        ErrorCode.E_LLM_PARSE_ERROR: {
            "title": "AI 响应解析失败",
            "message": "无法解析 AI 返回的内容",
            "solution": "• 重试生成操作\n• 简化输入内容\n• 调整提示词设置\n• 切换其他 AI 模型",
        },
        ErrorCode.E_CONFIG_INVALID: {
            "title": "配置无效",
            "message": "应用配置验证失败",
            "solution": "• 检查设置中的必填项\n• 验证 API Key 格式\n• 确认 URL 地址正确\n• 重置为默认配置",
        },
        ErrorCode.E_FILE_NOT_FOUND: {
            "title": "文件未找到",
            "message": "指定的文件不存在或已被删除",
            "solution": "• 确认文件路径正确\n• 检查文件是否被移动或删除\n• 重新选择文件",
        },
        ErrorCode.E_FILE_TYPE_UNSUPPORTED: {
            "title": "文件类型不支持",
            "message": "不支持该文件类型",
            "solution": "• 支持的格式：PDF、DOCX、PPTX、PNG、JPG、JPEG\n• 转换为支持的格式\n• 使用其他文件",
        },
        ErrorCode.E_UNKNOWN: {
            "title": "未知错误",
            "message": "发生了未知错误",
            "solution": "• 查看详细日志了解更多信息\n• 尝试重启应用\n• 检查系统资源是否充足\n• 联系技术支持",
        },
    },
    "en": {
        ErrorCode.E_DECK_NOT_FOUND: {
            "title": "Deck Not Found",
            "message": "The specified Anki deck does not exist",
            "solution": "• Create the deck in Anki\n• Check if deck name is correct\n• Select another deck in settings",
        },
        ErrorCode.E_MODEL_NOT_FOUND: {
            "title": "Note Type Not Found",
            "message": "The specified Anki note type does not exist",
            "solution": "• Confirm note type is created in Anki\n• Check note type name spelling\n• Use default note type",
        },
        ErrorCode.E_REQUIRED_FIELD_MISSING: {
            "title": "Required Field Missing",
            "message": "Card is missing required field content",
            "solution": "• Check if card content is complete\n• Verify note type field configuration\n• Regenerate the card",
        },
        ErrorCode.E_CLOZE_SYNTAX_INVALID: {
            "title": "Cloze Syntax Error",
            "message": "Cloze card syntax format is incorrect",
            "solution": "• Check if {{c1::}} format is correct\n• Ensure cloze numbers are consecutive\n• Refer to Anki cloze syntax documentation",
        },
        ErrorCode.E_MEDIA_INVALID: {
            "title": "Invalid Media File",
            "message": "Image or audio file in card is invalid",
            "solution": "• Check if file exists\n• Verify file format is supported\n• Re-add media file",
        },
        ErrorCode.E_ANKICONNECT_ERROR: {
            "title": "AnkiConnect Connection Failed",
            "message": "Cannot connect to AnkiConnect, please ensure Anki is running",
            "solution": "• Start Anki desktop application\n• Install AnkiConnect add-on (code: 2055492159)\n• Check AnkiConnect port settings (default 8765)\n• Confirm firewall is not blocking connection",
        },
        ErrorCode.E_CONVERT_FAILED: {
            "title": "Document Conversion Failed",
            "message": "Cannot convert document to processable format",
            "solution": "• Check if file is corrupted\n• Verify file format is supported (PDF, DOCX, PPTX)\n• Try using another file\n• Check if file is password protected",
        },
        ErrorCode.E_OCR_FAILED: {
            "title": "OCR Recognition Failed",
            "message": "Image text recognition failed",
            "solution": "• Use clearer images\n• Ensure image contains recognizable text\n• Adjust image brightness and contrast\n• Check if OCR model is downloaded",
        },
        ErrorCode.E_LLM_ERROR: {
            "title": "AI Generation Failed",
            "message": "AI model call failed, cannot generate cards",
            "solution": "• Check network connection\n• Verify API Key is valid\n• Confirm account has sufficient balance\n• Check API service status\n• Try switching to another AI provider",
        },
        ErrorCode.E_LLM_AUTH_ERROR: {
            "title": "LLM Authentication Failed",
            "message": "LLM API authentication failed (401). Check API key or token.",
            "solution": "• Verify API key/token is correct\n• Confirm key is not expired or revoked\n• Ensure Base URL matches provider endpoint",
        },
        ErrorCode.E_LLM_PERMISSION_ERROR: {
            "title": "LLM Permission Denied",
            "message": "LLM API access denied (403). Current account/key lacks permission.",
            "solution": "• Check account/project permissions\n• Confirm model access is enabled\n• Review organization/project policy and quota",
        },
        ErrorCode.E_LLM_PARSE_ERROR: {
            "title": "AI Response Parse Failed",
            "message": "Cannot parse content returned by AI",
            "solution": "• Retry generation operation\n• Simplify input content\n• Adjust prompt settings\n• Switch to another AI model",
        },
        ErrorCode.E_CONFIG_INVALID: {
            "title": "Invalid Configuration",
            "message": "Application configuration validation failed",
            "solution": "• Check required fields in settings\n• Verify API Key format\n• Confirm URL addresses are correct\n• Reset to default configuration",
        },
        ErrorCode.E_FILE_NOT_FOUND: {
            "title": "File Not Found",
            "message": "The specified file does not exist or has been deleted",
            "solution": "• Confirm file path is correct\n• Check if file was moved or deleted\n• Select another file",
        },
        ErrorCode.E_FILE_TYPE_UNSUPPORTED: {
            "title": "File Type Not Supported",
            "message": "This file type is not supported",
            "solution": "• Supported formats: PDF, DOCX, PPTX, PNG, JPG, JPEG\n• Convert to supported format\n• Use another file",
        },
        ErrorCode.E_UNKNOWN: {
            "title": "Unknown Error",
            "message": "An unknown error occurred",
            "solution": "• View detailed logs for more information\n• Try restarting the application\n• Check if system resources are sufficient\n• Contact technical support",
        },
    },
}


def get_error_info(code: ErrorCode, language: str = "zh") -> dict[str, str]:
    """Get user-friendly error information for an error code.

    Args:
        code: Error code
        language: Language code ("zh" or "en")

    Returns:
        Dictionary with title, message, and solution
    """
    lang = "zh" if language == "zh" else "en"
    return ERROR_MESSAGES[lang].get(
        code,
        ERROR_MESSAGES[lang][ErrorCode.E_UNKNOWN],
    )
