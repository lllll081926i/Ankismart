"""Internationalization support for Ankismart UI.

Provides translation dictionaries and utilities for Chinese and English locales.
"""

from __future__ import annotations

# Translation dictionary: key -> {language_code: translated_text}
TRANSLATIONS: dict[str, dict[str, str]] = {
    # Navigation labels
    "nav.import": {"zh": "导入", "en": "Import"},
    "nav.preview": {"zh": "预览", "en": "Preview"},
    "nav.result": {"zh": "结果", "en": "Result"},
    "nav.settings": {"zh": "设置", "en": "Settings"},

    # Import page
    "import.title": {"zh": "导入文档", "en": "Import Document"},
    "import.select_file": {"zh": "选择文件", "en": "Select File"},
    "import.file_path": {"zh": "文件路径", "en": "File Path"},
    "import.browse": {"zh": "浏览...", "en": "Browse..."},
    "import.deck_name": {"zh": "牌组名称", "en": "Deck Name"},
    "import.tags": {"zh": "标签", "en": "Tags"},
    "import.tags_placeholder": {"zh": "用逗号分隔多个标签", "en": "Separate tags with commas"},
    "import.strategy": {"zh": "生成策略", "en": "Generation Strategy"},
    "import.start_generate": {"zh": "开始生成", "en": "Start Generation"},
    "import.generating": {"zh": "生成中...", "en": "Generating..."},
    "import.ocr_progress": {"zh": "OCR 进度: {progress}%", "en": "OCR Progress: {progress}%"},
    "import.llm_progress": {"zh": "LLM 生成进度: {current}/{total}", "en": "LLM Progress: {current}/{total}"},

    # Preview page
    "preview.title": {"zh": "预览卡片", "en": "Preview Cards"},
    "preview.card_count": {"zh": "共 {count} 张卡片", "en": "{count} cards total"},
    "preview.edit": {"zh": "编辑", "en": "Edit"},
    "preview.delete": {"zh": "删除", "en": "Delete"},
    "preview.save": {"zh": "保存", "en": "Save"},
    "preview.cancel": {"zh": "取消", "en": "Cancel"},
    "preview.front": {"zh": "正面", "en": "Front"},
    "preview.back": {"zh": "背面", "en": "Back"},
    "preview.tags": {"zh": "标签", "en": "Tags"},
    "preview.confirm_delete": {"zh": "确认删除", "en": "Confirm Delete"},
    "preview.delete_message": {"zh": "确定要删除这张卡片吗？", "en": "Are you sure you want to delete this card?"},
    "preview.next_step": {"zh": "下一步", "en": "Next Step"},
    "preview.update_mode": {"zh": "更新模式", "en": "Update Mode"},
    "preview.update_mode.skip": {"zh": "跳过重复", "en": "Skip Duplicates"},
    "preview.update_mode.update": {"zh": "更新现有", "en": "Update Existing"},
    "preview.update_mode.add_new": {"zh": "全部添加", "en": "Add All"},

    # Result page
    "result.title": {"zh": "生成结果", "en": "Generation Result"},
    "result.success": {"zh": "成功", "en": "Success"},
    "result.failed": {"zh": "失败", "en": "Failed"},
    "result.cards_generated": {"zh": "已生成 {count} 张卡片", "en": "{count} cards generated"},
    "result.export_apkg": {"zh": "导出 .apkg", "en": "Export .apkg"},
    "result.push_anki": {"zh": "推送到 Anki", "en": "Push to Anki"},
    "result.export_success": {"zh": "导出成功", "en": "Export Successful"},
    "result.export_failed": {"zh": "导出失败", "en": "Export Failed"},
    "result.push_success": {"zh": "推送成功", "en": "Push Successful"},
    "result.push_failed": {"zh": "推送失败", "en": "Push Failed"},
    "result.new_import": {"zh": "新建导入", "en": "New Import"},
    "result.pushed_count": {"zh": "已推送 {count} 张卡片", "en": "{count} cards pushed"},
    "result.skipped_count": {"zh": "跳过 {count} 张重复卡片", "en": "{count} duplicates skipped"},
    "result.updated_count": {"zh": "更新 {count} 张卡片", "en": "{count} cards updated"},

    # Settings page
    "settings.title": {"zh": "设置", "en": "Settings"},
    "settings.llm": {"zh": "LLM 配置", "en": "LLM Configuration"},
    "settings.llm_provider": {"zh": "LLM 提供商", "en": "LLM Provider"},
    "settings.add_provider": {"zh": "添加提供商", "en": "Add Provider"},
    "settings.edit_provider": {"zh": "编辑提供商", "en": "Edit Provider"},
    "settings.delete_provider": {"zh": "删除提供商", "en": "Delete Provider"},
    "settings.provider_name": {"zh": "提供商名称", "en": "Provider Name"},
    "settings.api_key": {"zh": "API Key", "en": "API Key"},
    "settings.base_url": {"zh": "Base URL", "en": "Base URL"},
    "settings.model": {"zh": "模型", "en": "Model"},
    "settings.rpm_limit": {"zh": "RPM 限制", "en": "RPM Limit"},
    "settings.temperature": {"zh": "Temperature", "en": "Temperature"},
    "settings.max_tokens": {"zh": "最大 Token 数", "en": "Max Tokens"},
    "settings.max_tokens_hint": {"zh": "0 表示使用默认值", "en": "0 means use default"},

    "settings.anki": {"zh": "Anki 配置", "en": "Anki Configuration"},
    "settings.anki_connect_url": {"zh": "AnkiConnect URL", "en": "AnkiConnect URL"},
    "settings.anki_connect_key": {"zh": "AnkiConnect Key", "en": "AnkiConnect Key"},
    "settings.default_deck": {"zh": "默认牌组", "en": "Default Deck"},
    "settings.default_tags": {"zh": "默认标签", "en": "Default Tags"},

    "settings.general": {"zh": "通用设置", "en": "General Settings"},
    "settings.theme": {"zh": "主题", "en": "Theme"},
    "settings.theme.light": {"zh": "浅色", "en": "Light"},
    "settings.theme.dark": {"zh": "深色", "en": "Dark"},
    "settings.language": {"zh": "语言", "en": "Language"},
    "settings.language.zh": {"zh": "中文", "en": "Chinese"},
    "settings.language.en": {"zh": "English", "en": "English"},
    "settings.proxy_url": {"zh": "代理 URL", "en": "Proxy URL"},
    "settings.proxy_hint": {"zh": "留空表示不使用代理", "en": "Leave empty to disable proxy"},
    "settings.ocr_correction": {"zh": "OCR 纠错", "en": "OCR Correction"},
    "settings.log_level": {"zh": "日志级别", "en": "Log Level"},

    "settings.save": {"zh": "保存设置", "en": "Save Settings"},
    "settings.save_success": {"zh": "设置已保存", "en": "Settings saved"},
    "settings.save_failed": {"zh": "保存失败", "en": "Save failed"},
    "settings.test_connection": {"zh": "测试连接", "en": "Test Connection"},
    "settings.connection_success": {"zh": "连接成功", "en": "Connection successful"},
    "settings.connection_failed": {"zh": "连接失败", "en": "Connection failed"},

    # Common buttons
    "common.ok": {"zh": "确定", "en": "OK"},
    "common.cancel": {"zh": "取消", "en": "Cancel"},
    "common.yes": {"zh": "是", "en": "Yes"},
    "common.no": {"zh": "否", "en": "No"},
    "common.close": {"zh": "关闭", "en": "Close"},
    "common.apply": {"zh": "应用", "en": "Apply"},
    "common.reset": {"zh": "重置", "en": "Reset"},

    # Messages
    "msg.error": {"zh": "错误", "en": "Error"},
    "msg.warning": {"zh": "警告", "en": "Warning"},
    "msg.info": {"zh": "信息", "en": "Information"},
    "msg.success": {"zh": "成功", "en": "Success"},
    "msg.file_not_found": {"zh": "文件未找到", "en": "File not found"},
    "msg.invalid_file": {"zh": "无效的文件格式", "en": "Invalid file format"},
    "msg.no_cards": {"zh": "没有生成任何卡片", "en": "No cards generated"},
    "msg.generation_failed": {"zh": "生成失败: {error}", "en": "Generation failed: {error}"},
    "msg.please_select_file": {"zh": "请先选择文件", "en": "Please select a file first"},
    "msg.please_configure_llm": {"zh": "请先配置 LLM 提供商", "en": "Please configure LLM provider first"},
    "msg.anki_not_running": {"zh": "Anki 未运行或 AnkiConnect 未安装", "en": "Anki is not running or AnkiConnect is not installed"},
    "msg.restart_required": {"zh": "需要重启应用以应用更改", "en": "Restart required to apply changes"},

    # File filters
    "file.all_supported": {"zh": "所有支持的文件", "en": "All Supported Files"},
    "file.pdf": {"zh": "PDF 文件", "en": "PDF Files"},
    "file.word": {"zh": "Word 文档", "en": "Word Documents"},
    "file.ppt": {"zh": "PowerPoint 文件", "en": "PowerPoint Files"},
    "file.image": {"zh": "图片文件", "en": "Image Files"},
    "file.apkg": {"zh": "Anki 包", "en": "Anki Package"},
}


def get_text(key: str, lang: str = "zh", **kwargs) -> str:
    """Get translated text for a given key.

    Args:
        key: Translation key (e.g., "nav.import", "import.title")
        lang: Language code ("zh" or "en"), defaults to "zh"
        **kwargs: Placeholder values for string formatting

    Returns:
        Translated text with placeholders replaced. If key is not found,
        returns the key itself as fallback.

    Examples:
        >>> get_text("nav.import", "zh")
        '导入'
        >>> get_text("preview.card_count", "en", count=5)
        '5 cards total'
        >>> get_text("import.ocr_progress", "zh", progress=75)
        'OCR 进度: 75%'
    """
    translations = TRANSLATIONS.get(key, {})
    text = translations.get(lang, translations.get("zh", key))

    # Replace placeholders if any kwargs provided
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError):
            # If formatting fails, return text as-is
            pass

    return text


def get_all_keys() -> list[str]:
    """Get all available translation keys.

    Returns:
        List of all translation keys in the dictionary.
    """
    return list(TRANSLATIONS.keys())


def has_translation(key: str, lang: str = "zh") -> bool:
    """Check if a translation exists for a given key and language.

    Args:
        key: Translation key
        lang: Language code

    Returns:
        True if translation exists, False otherwise.
    """
    return key in TRANSLATIONS and lang in TRANSLATIONS[key]


# Alias for convenience
t = get_text
