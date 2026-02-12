"""Internationalization support for Ankismart UI.

Provides translation dictionaries and utilities for Chinese and English locales.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ankismart.core.config import AppConfig

# Global current language
_current_language = "zh"


def set_language(lang: str) -> None:
    """Set the current language globally.

    Args:
        lang: Language code ("zh" or "en")
    """
    global _current_language
    _current_language = lang


def get_current_language() -> str:
    """Get the current language code."""
    return _current_language


# Translation dictionary: key -> {language_code: translated_text}
TRANSLATIONS: dict[str, dict[str, str]] = {
    # Navigation labels
    "nav.import": {"zh": "导入", "en": "Import"},
    "nav.preview": {"zh": "预览", "en": "Preview"},
    "nav.result": {"zh": "结果", "en": "Result"},
    "nav.settings": {"zh": "设置", "en": "Settings"},

    # Import page - File selection
    "import.file_selection": {"zh": "文件选择", "en": "File Selection"},
    "import.files_selected": {"zh": "已选择 {count} 个文件", "en": "{count} files selected"},
    "import.drag_hint": {"zh": "拖拽文件到此处或点击选择文件", "en": "Drag files here or click to select"},
    "import.clear_all_files": {"zh": "清空所有文件", "en": "Clear All Files"},
    "import.select_files": {"zh": "选择文件", "en": "Select Files"},
    "import.delete": {"zh": "删除", "en": "Delete"},

    # Import page - Configuration
    "import.generation_config": {"zh": "生成配置", "en": "Generation Config"},
    "import.target_card_count": {"zh": "目标卡片数量", "en": "Target Card Count"},
    "import.target_card_count_desc": {"zh": "设置要生成的卡片总数", "en": "Set total number of cards to generate"},
    "import.deck_name": {"zh": "卡片组名称", "en": "Deck Name"},
    "import.deck_name_desc": {"zh": "选择或输入 Anki 卡片组名称", "en": "Select or enter Anki deck name"},
    "import.tags": {"zh": "标签", "en": "Tags"},
    "import.tags_desc": {"zh": "添加标签，用逗号分隔", "en": "Add tags, separated by commas"},

    # Import page - Strategy
    "import.generation_strategy": {"zh": "生成策略", "en": "Generation Strategy"},
    "import.strategy.basic": {"zh": "基础问答", "en": "Basic Q&A"},
    "import.strategy.basic_desc": {"zh": "生成基础问答卡片", "en": "Generate basic Q&A cards"},
    "import.strategy.cloze": {"zh": "填空题", "en": "Cloze"},
    "import.strategy.cloze_desc": {"zh": "生成填空题卡片", "en": "Generate cloze cards"},
    "import.strategy.concept": {"zh": "概念解释", "en": "Concept"},
    "import.strategy.concept_desc": {"zh": "生成概念解释卡片", "en": "Generate concept cards"},
    "import.strategy.key_terms": {"zh": "关键术语", "en": "Key Terms"},
    "import.strategy.key_terms_desc": {"zh": "生成关键术语卡片", "en": "Generate key term cards"},
    "import.strategy.single_choice": {"zh": "单选题", "en": "Single Choice"},
    "import.strategy.single_choice_desc": {"zh": "生成单选题卡片", "en": "Generate single choice cards"},
    "import.strategy.multiple_choice": {"zh": "多选题", "en": "Multiple Choice"},
    "import.strategy.multiple_choice_desc": {"zh": "生成多选题卡片", "en": "Generate multiple choice cards"},

    # Import page - Actions
    "import.start_generation": {"zh": "开始生成", "en": "Start Generation"},
    "import.clear": {"zh": "清除", "en": "Clear"},
    "import.load_example": {"zh": "加载示例", "en": "Load Example"},
    "import.recommend_strategy": {"zh": "推荐策略", "en": "Recommend Strategy"},
    "import.converting": {"zh": "正在转换文件...", "en": "Converting files..."},
    "import.converting_file": {"zh": "正在转换: {filename} ({current}/{total})", "en": "Converting: {filename} ({current}/{total})"},
    "import.converting_file_with_page": {"zh": "正在转换: {filename} (第 {page}/{total_pages} 页)", "en": "Converting: {filename} (Page {page}/{total_pages})"},
    "import.overall_progress": {"zh": "{percentage}% ({current}/{total} 文件)", "en": "{percentage}% ({current}/{total} files)"},
    "import.ocr_page_progress": {"zh": "正在识别第 {page}/{total_pages} 页", "en": "Recognizing page {page}/{total_pages}"},
    "import.conversion_complete": {"zh": "转换完成: {count} 个文件", "en": "Conversion completed: {count} files"},
    "import.no_files_converted": {"zh": "没有成功转换的文件", "en": "No files converted successfully"},
    "import.conversion_failed": {"zh": "转换失败: {error}", "en": "Conversion failed: {error}"},

    # Import page - Validation
    "import.warning": {"zh": "警告", "en": "Warning"},
    "import.please_select_files": {"zh": "请先选择文件", "en": "Please select files first"},
    "import.please_configure_provider": {"zh": "请先配置 LLM 提供商", "en": "Please configure LLM provider first"},
    "import.please_configure_api_key": {"zh": "请先配置 API Key", "en": "Please configure API Key first"},
    "import.please_enter_deck_name": {"zh": "请输入牌组名称", "en": "Please enter deck name"},
    "import.please_select_strategy": {"zh": "请至少选择一个生成策略（占比 > 0）", "en": "Please select at least one strategy (ratio > 0)"},
    "import.conversion_errors": {"zh": "转换错误", "en": "Conversion Errors"},
    "import.some_files_failed": {"zh": "部分文件转换失败:\n{errors}", "en": "Some files failed to convert:\n{errors}"},

    # Import page - Input validation errors
    "import.validation_error": {"zh": "输入验证失败", "en": "Validation Error"},
    "import.invalid_card_count": {"zh": "目标卡片数量无效", "en": "Invalid Card Count"},
    "import.card_count_must_be_number": {"zh": "目标卡片数量必须是正整数", "en": "Target card count must be a positive integer"},
    "import.card_count_out_of_range": {"zh": "目标卡片数量必须在 1-1000 之间", "en": "Target card count must be between 1 and 1000"},
    "import.invalid_tags": {"zh": "标签格式无效", "en": "Invalid Tags Format"},
    "import.tags_contain_invalid_chars": {"zh": "标签包含非法字符。\n\n标签只能包含字母、数字、中文、下划线和连字符。\n多个标签请用逗号分隔。\n\n示例：ankismart, 重要, review_2024", "en": "Tags contain invalid characters.\n\nTags can only contain letters, numbers, Chinese characters, underscores, and hyphens.\nSeparate multiple tags with commas.\n\nExample: ankismart, important, review_2024"},
    "import.invalid_deck_name": {"zh": "牌组名称无效", "en": "Invalid Deck Name"},
    "import.deck_name_empty": {"zh": "牌组名称不能为空", "en": "Deck name cannot be empty"},
    "import.deck_name_invalid_chars": {"zh": "牌组名称包含非法字符。\n\n牌组名称不能包含以下字符：< > : \" / \\ | ? *\n\n示例：Default, 英语学习, Math_2024", "en": "Deck name contains invalid characters.\n\nDeck name cannot contain: < > : \" / \\ | ? *\n\nExample: Default, English, Math_2024"},

    # Import page - Input placeholders and tooltips
    "import.card_count_placeholder": {"zh": "输入 1-1000 之间的数字", "en": "Enter a number between 1-1000"},
    "import.card_count_tooltip": {"zh": "设置要生成的卡片总数（1-1000）", "en": "Set total number of cards to generate (1-1000)"},
    "import.deck_name_placeholder": {"zh": "输入牌组名称", "en": "Enter deck name"},
    "import.deck_name_tooltip": {"zh": "选择或输入 Anki 牌组名称\n不能包含特殊字符：< > : \" / \\ | ? *", "en": "Select or enter Anki deck name\nCannot contain: < > : \" / \\ | ? *"},
    "import.tags_placeholder": {"zh": "例如：ankismart, 重要, 复习", "en": "Example: ankismart, important, review"},
    "import.tags_tooltip": {"zh": "添加标签，用逗号分隔\n只能包含字母、数字、中文、下划线和连字符", "en": "Add tags, separated by commas\nCan only contain letters, numbers, Chinese, underscores, and hyphens"},

    # Import page - OCR Models
    "import.download_ocr_models": {"zh": "下载 OCR 模型", "en": "Download OCR Models"},
    "import.missing_ocr_models": {"zh": "检测到缺失的 OCR 模型：{models}\n\n是否立即下载？（首次使用需要下载约 20MB 数据）", "en": "Missing OCR models detected: {models}\n\nDownload now? (First-time use requires ~20MB download)"},
    "import.downloading_ocr_models": {"zh": "正在下载 OCR 模型", "en": "Downloading OCR Models"},
    "import.please_wait": {"zh": "请稍候...", "en": "Please wait..."},
    "import.download_complete": {"zh": "模型下载完成！已下载 {count} 个模型", "en": "Download complete! {count} model(s) downloaded"},
    "import.download_success": {"zh": "下载成功", "en": "Download Successful"},
    "import.ocr_models_ready": {"zh": "OCR 模型已成功下载，现在可以开始转换文件了。", "en": "OCR models downloaded successfully. You can now start converting files."},
    "import.download_failed": {"zh": "下载失败", "en": "Download Failed"},
    "import.ocr_download_error": {"zh": "OCR 模型下载失败：\n\n{error}\n\n请检查网络连接后重试，或手动下载模型文件。", "en": "OCR model download failed:\n\n{error}\n\nPlease check your network connection and try again, or manually download the model files."},

    # Import page - Examples
    "import.select_example": {"zh": "选择示例文档", "en": "Select Example Document"},
    "import.example_comprehensive": {"zh": "综合知识示例", "en": "Comprehensive Knowledge"},
    "import.example_comprehensive_desc": {"zh": "包含数学公式、代码块、列表等多种内容", "en": "Contains math formulas, code blocks, lists, etc."},
    "import.example_math": {"zh": "数学公式专题", "en": "Mathematics Formulas"},
    "import.example_math_desc": {"zh": "微积分、线性代数、概率论等数学内容", "en": "Calculus, linear algebra, probability, etc."},
    "import.example_biology": {"zh": "生物学知识", "en": "Biology Knowledge"},
    "import.example_biology_desc": {"zh": "细胞、遗传、生态、进化等生物学内容", "en": "Cell biology, genetics, ecology, evolution, etc."},
    "import.example_loaded": {"zh": "示例已加载", "en": "Example Loaded"},
    "import.example_loaded_msg": {"zh": "已加载示例文档：{name}", "en": "Example document loaded: {name}"},

    # Import page - Strategy Recommendations
    "import.strategy_recommendation": {"zh": "策略推荐", "en": "Strategy Recommendation"},
    "import.no_files_for_recommendation": {"zh": "请先选择文件", "en": "Please select files first"},
    "import.analyzing_content": {"zh": "分析中", "en": "Analyzing"},
    "import.analyzing_content_msg": {"zh": "正在分析文档内容...", "en": "Analyzing document content..."},
    "import.recommendation_ready": {"zh": "推荐完成", "en": "Recommendation Ready"},
    "import.apply_recommendation": {"zh": "应用推荐", "en": "Apply Recommendation"},
    "import.recommendation_applied": {"zh": "已应用推荐策略", "en": "Recommendation Applied"},
    "import.recommendation_applied_msg": {"zh": "已根据文档类型应用推荐的生成策略", "en": "Applied recommended strategy based on document type"},

    # Strategy recommendation types
    "import.rec_math_science": {"zh": "数学/理科内容", "en": "Math/Science Content"},
    "import.rec_math_science_desc": {"zh": "检测到数学公式、科学概念等内容", "en": "Detected math formulas, scientific concepts, etc."},
    "import.rec_liberal_arts": {"zh": "文科/历史内容", "en": "Liberal Arts/History Content"},
    "import.rec_liberal_arts_desc": {"zh": "检测到历史事件、人文知识等内容", "en": "Detected historical events, humanities knowledge, etc."},
    "import.rec_programming": {"zh": "编程/技术内容", "en": "Programming/Technical Content"},
    "import.rec_programming_desc": {"zh": "检测到代码块、技术文档等内容", "en": "Detected code blocks, technical documentation, etc."},
    "import.rec_general": {"zh": "通用内容", "en": "General Content"},
    "import.rec_general_desc": {"zh": "混合类型内容，使用平衡策略", "en": "Mixed content type, using balanced strategy"},

    # Preview page
    "preview.title": {"zh": "文档预览与编辑", "en": "Document Preview & Edit"},
    "preview.edit_placeholder": {"zh": "在此编辑 Markdown 内容...", "en": "Edit Markdown content here..."},
    "preview.save_edit": {"zh": "保存编辑", "en": "Save Edit"},
    "preview.generate_cards": {"zh": "生成卡片", "en": "Generate Cards"},

    # Result page - Title and stats
    "result.title": {"zh": "推送结果", "en": "Push Result"},
    "result.total_cards": {"zh": "总卡片数", "en": "Total Cards"},
    "result.success_pushed": {"zh": "成功推送", "en": "Success"},
    "result.failed": {"zh": "失败", "en": "Failed"},
    "result.skipped": {"zh": "跳过", "en": "Skipped"},
    "result.detail_results": {"zh": "详细结果", "en": "Detail Results"},

    # Result page - Table
    "result.card_title": {"zh": "卡片标题", "en": "Card Title"},
    "result.status": {"zh": "状态", "en": "Status"},
    "result.error_message": {"zh": "错误信息", "en": "Error Message"},
    "result.status_success": {"zh": "成功", "en": "Success"},
    "result.status_failed": {"zh": "失败", "en": "Failed"},
    "result.status_skipped": {"zh": "跳过", "en": "Skipped"},
    "result.unknown_card": {"zh": "未知卡片", "en": "Unknown Card"},

    # Result page - Actions
    "result.update_strategy": {"zh": "更新策略", "en": "Update Strategy"},
    "result.create_only": {"zh": "仅新增", "en": "Create Only"},
    "result.update_only": {"zh": "仅更新", "en": "Update Only"},
    "result.create_or_update": {"zh": "新增或更新", "en": "Create or Update"},
    "result.retry_failed": {"zh": "重试失败卡片", "en": "Retry Failed Cards"},
    "result.export_failed": {"zh": "导出失败卡片", "en": "Export Failed Cards"},
    "result.back_to_preview": {"zh": "返回预览", "en": "Back to Preview"},

    # Result page - Batch Edit
    "result.batch_edit_tags": {"zh": "批量编辑标签", "en": "Batch Edit Tags"},
    "result.batch_edit_deck": {"zh": "批量修改牌组", "en": "Batch Edit Deck"},
    "result.batch_edit_tags_title": {"zh": "批量编辑标签", "en": "Batch Edit Tags"},
    "result.batch_edit_deck_title": {"zh": "批量修改牌组", "en": "Batch Edit Deck"},
    "result.selected_cards_count": {"zh": "已选择 {count} 张卡片", "en": "{count} cards selected"},
    "result.tags_placeholder": {"zh": "输入标签，用逗号分隔", "en": "Enter tags, separated by commas"},
    "result.tags_hint": {"zh": "例如：重要, 复习, 考试", "en": "Example: important, review, exam"},
    "result.deck_placeholder": {"zh": "输入牌组名称", "en": "Enter deck name"},
    "result.deck_hint": {"zh": "例如：Default, 英语学习, 数学", "en": "Example: Default, English, Math"},
    "result.batch_edit_success": {"zh": "批量编辑成功", "en": "Batch Edit Success"},
    "result.batch_tags_updated": {"zh": "已更新 {count} 张卡片的标签", "en": "Updated tags for {count} cards"},
    "result.batch_deck_updated": {"zh": "已更新 {count} 张卡片的牌组", "en": "Updated deck for {count} cards"},

    # Result page - Duplicate Check Settings
    "result.duplicate_check_settings": {"zh": "重复检查设置", "en": "Duplicate Check Settings"},
    "result.duplicate_scope": {"zh": "检查范围", "en": "Check Scope"},
    "result.duplicate_scope_desc": {"zh": "设置重复检查的范围", "en": "Set the scope for duplicate checking"},
    "result.duplicate_scope_deck": {"zh": "当前牌组", "en": "Current Deck"},
    "result.duplicate_scope_collection": {"zh": "所有牌组", "en": "All Decks"},
    "result.duplicate_check_model": {"zh": "检查模型", "en": "Check Model"},
    "result.duplicate_check_model_desc": {"zh": "是否检查笔记类型是否相同", "en": "Whether to check if note type matches"},
    "result.allow_duplicate": {"zh": "允许重复", "en": "Allow Duplicates"},
    "result.allow_duplicate_desc": {"zh": "允许创建重复的卡片", "en": "Allow creating duplicate cards"},

    # Result page - Messages
    "result.push_success_msg": {"zh": "推送成功", "en": "Push Success"},
    "result.push_success_detail": {"zh": "成功推送 {count} 张卡片", "en": "Successfully pushed {count} cards"},
    "result.partial_failure": {"zh": "部分失败", "en": "Partial Failure"},
    "result.partial_failure_detail": {"zh": "成功 {succeeded} 张，失败 {failed} 张", "en": "Success {succeeded}, Failed {failed}"},
    "result.no_failed_cards": {"zh": "提示", "en": "Info"},
    "result.no_failed_cards_msg": {"zh": "没有失败的卡片需要重试", "en": "No failed cards to retry"},
    "result.retrying": {"zh": "重试中", "en": "Retrying"},
    "result.retrying_msg": {"zh": "正在重试 {count} 张失败卡片...", "en": "Retrying {count} failed cards..."},
    "result.retry_success": {"zh": "重试成功", "en": "Retry Success"},
    "result.retry_success_msg": {"zh": "成功推送 {count} 张卡片", "en": "Successfully pushed {count} cards"},
    "result.retry_all_failed": {"zh": "重试失败", "en": "Retry Failed"},
    "result.retry_all_failed_msg": {"zh": "所有卡片重试失败", "en": "All cards retry failed"},
    "result.retry_error": {"zh": "重试错误", "en": "Retry Error"},
    "result.no_failed_to_export": {"zh": "没有失败的卡片需要导出", "en": "No failed cards to export"},
    "result.export_failed_cards": {"zh": "导出失败卡片", "en": "Export Failed Cards"},
    "result.exporting": {"zh": "导出中", "en": "Exporting"},
    "result.exporting_msg": {"zh": "正在导出 {count} 张失败卡片...", "en": "Exporting {count} failed cards..."},
    "result.export_success": {"zh": "导出成功", "en": "Export Success"},
    "result.export_success_msg": {"zh": "已导出到 {path}", "en": "Exported to {path}"},
    "result.export_error": {"zh": "导出错误", "en": "Export Error"},
    "result.confirm_back": {"zh": "确认返回", "en": "Confirm Back"},
    "result.confirm_back_msg": {"zh": "返回预览页面将丢失当前结果，是否继续？", "en": "Going back will lose current results. Continue?"},

    # Settings page - Groups
    "settings.llm_config": {"zh": "LLM 配置", "en": "LLM Configuration"},
    "settings.llm_params": {"zh": "LLM 参数", "en": "LLM Parameters"},
    "settings.anki_config": {"zh": "Anki 配置", "en": "Anki Configuration"},
    "settings.other_settings": {"zh": "其他设置", "en": "Other Settings"},
    "settings.actions": {"zh": "操作", "en": "Actions"},

    # Settings page - LLM Provider
    "settings.add_provider": {"zh": "添加提供商", "en": "Add Provider"},
    "settings.add_provider_desc": {"zh": "添加新的 LLM 提供商配置", "en": "Add new LLM provider configuration"},
    "settings.provider_dialog_title": {"zh": "LLM 提供商配置", "en": "LLM Provider Configuration"},
    "settings.provider_name_placeholder": {"zh": "提供商名称（例如：OpenAI）", "en": "Provider name (e.g., OpenAI)"},
    "settings.base_url_placeholder": {"zh": "基础 URL（例如：https://api.openai.com/v1）", "en": "Base URL (e.g., https://api.openai.com/v1)"},
    "settings.api_key_placeholder": {"zh": "API 密钥", "en": "API Key"},
    "settings.model_placeholder": {"zh": "模型（例如：gpt-4o）", "en": "Model (e.g., gpt-4o)"},
    "settings.rpm_limit_prefix": {"zh": "RPM 限制: ", "en": "RPM Limit: "},
    "settings.provider_name_required": {"zh": "提供商名称为必填项", "en": "Provider name is required"},
    "settings.activate": {"zh": "激活", "en": "Activate"},
    "settings.current_active": {"zh": "当前使用", "en": "Current"},
    "settings.edit": {"zh": "修改", "en": "Edit"},
    "settings.test": {"zh": "测试", "en": "Test"},
    "settings.delete": {"zh": "删除", "en": "Delete"},
    "settings.model_label": {"zh": "模型：{model}", "en": "Model: {model}"},
    "settings.url_label": {"zh": "地址：{url}", "en": "URL: {url}"},
    "settings.rpm_label": {"zh": "RPM：{rpm}", "en": "RPM: {rpm}"},
    "settings.not_set": {"zh": "未设置", "en": "Not set"},
    "settings.default": {"zh": "默认", "en": "Default"},
    "settings.cannot_delete": {"zh": "无法删除", "en": "Cannot Delete"},
    "settings.must_keep_one": {"zh": "至少需要保留一个提供商配置", "en": "At least one provider must be kept"},
    "settings.confirm_delete": {"zh": "确认删除", "en": "Confirm Delete"},
    "settings.confirm_delete_provider": {"zh": "确定要删除提供商 '{name}' 吗？", "en": "Delete provider '{name}'?"},
    "settings.testing": {"zh": "测试中", "en": "Testing"},
    "settings.testing_provider": {"zh": "正在测试提供商「{name}」连通性...", "en": "Testing provider '{name}' connectivity..."},
    "settings.connection_success": {"zh": "连接成功", "en": "Connection Success"},
    "settings.provider_connected": {"zh": "提供商「{name}」连通正常", "en": "Provider '{name}' connected successfully"},
    "settings.connection_failed": {"zh": "连接失败", "en": "Connection Failed"},
    "settings.provider_failed": {"zh": "提供商「{name}」连接失败：{error}", "en": "Provider '{name}' failed: {error}"},
    "settings.provider_test_failed": {"zh": "提供商「{name}」未通过连通性测试", "en": "Provider '{name}' connectivity test failed"},

    # Settings page - LLM Parameters
    "settings.temperature": {"zh": "温度", "en": "Temperature"},
    "settings.temperature_desc": {"zh": "控制生成的随机性（0.0 = 确定性，2.0 = 创造性）", "en": "Control randomness (0.0 = deterministic, 2.0 = creative)"},
    "settings.max_tokens": {"zh": "最大令牌数", "en": "Max Tokens"},
    "settings.max_tokens_desc": {"zh": "生成的最大令牌数（0 = 使用提供商默认值）", "en": "Maximum tokens to generate (0 = use provider default)"},
    "settings.max_tokens_default": {"zh": "默认", "en": "Default"},

    # Settings page - Anki
    "settings.anki_url": {"zh": "AnkiConnect URL", "en": "AnkiConnect URL"},
    "settings.anki_url_desc": {"zh": "AnkiConnect API 的 URL 地址", "en": "URL address of AnkiConnect API"},
    "settings.anki_url_placeholder": {"zh": "http://127.0.0.1:8765", "en": "http://127.0.0.1:8765"},
    "settings.anki_key": {"zh": "AnkiConnect 密钥", "en": "AnkiConnect Key"},
    "settings.anki_key_desc": {"zh": "AnkiConnect 的可选 API 密钥", "en": "Optional API key for AnkiConnect"},
    "settings.anki_key_placeholder": {"zh": "可选的 API 密钥", "en": "Optional API key"},
    "settings.default_deck": {"zh": "默认牌组", "en": "Default Deck"},
    "settings.default_deck_desc": {"zh": "新卡片的默认 Anki 牌组", "en": "Default Anki deck for new cards"},
    "settings.default_deck_placeholder": {"zh": "默认", "en": "Default"},
    "settings.default_tags": {"zh": "默认标签", "en": "Default Tags"},
    "settings.default_tags_desc": {"zh": "新卡片的默认标签（逗号分隔）", "en": "Default tags for new cards (comma separated)"},
    "settings.default_tags_placeholder": {"zh": "ankismart, imported", "en": "ankismart, imported"},
    "settings.test_connection": {"zh": "测试连接", "en": "Test Connection"},
    "settings.test_connection_desc": {"zh": "测试与 AnkiConnect 的连接", "en": "Test connection to AnkiConnect"},
    "settings.testing_anki": {"zh": "正在检测 AnkiConnect 连接...", "en": "Testing AnkiConnect connection..."},
    "settings.anki_connected": {"zh": "AnkiConnect 连通正常", "en": "AnkiConnect connected successfully"},
    "settings.anki_failed": {"zh": "无法连接到 AnkiConnect，请检查 URL/密钥与代理设置", "en": "Cannot connect to AnkiConnect, check URL/key and proxy settings"},

    # Settings page - Other
    "settings.theme": {"zh": "主题", "en": "Theme"},
    "settings.theme_desc": {"zh": "应用程序主题", "en": "Application theme"},
    "settings.theme_light": {"zh": "浅色", "en": "Light"},
    "settings.theme_dark": {"zh": "深色", "en": "Dark"},
    "settings.theme_auto": {"zh": "自动", "en": "Auto"},
    "settings.language": {"zh": "语言", "en": "Language"},
    "settings.language_desc": {"zh": "应用程序语言", "en": "Application language"},
    "settings.language_zh": {"zh": "中文", "en": "Chinese"},
    "settings.language_en": {"zh": "English", "en": "English"},
    "settings.proxy": {"zh": "代理设置", "en": "Proxy Settings"},
    "settings.proxy_desc": {"zh": "HTTP/HTTPS 代理 URL（可选）", "en": "HTTP/HTTPS proxy URL (optional)"},
    "settings.proxy_placeholder": {"zh": "http://proxy.example.com:8080", "en": "http://proxy.example.com:8080"},
    "settings.ocr_correction": {"zh": "OCR 校正", "en": "OCR Correction"},
    "settings.ocr_correction_desc": {"zh": "启用基于 LLM 的 OCR 文本校正", "en": "Enable LLM-based OCR text correction"},

    # Settings page - Experimental Features
    "settings.experimental_features": {"zh": "实验性功能", "en": "Experimental Features"},
    "settings.auto_split_enable": {"zh": "启用长文档自动分割", "en": "Enable Auto-Split for Long Documents"},
    "settings.auto_split_enable_desc": {"zh": "当文档超过阈值时自动分割为多个片段处理", "en": "Automatically split documents into chunks when exceeding threshold"},
    "settings.auto_split_threshold": {"zh": "分割阈值", "en": "Split Threshold"},
    "settings.auto_split_threshold_desc": {"zh": "触发自动分割的字符数阈值", "en": "Character count threshold for triggering auto-split"},
    "settings.auto_split_warning": {"zh": "⚠️ 警告：这是实验性功能，可能影响卡片质量和生成时间。建议仅在处理超长文档时启用。", "en": "⚠️ Warning: This is an experimental feature that may affect card quality and generation time. Enable only for very long documents."},

    # Settings page - Cache Management
    "settings.cache_management": {"zh": "缓存管理", "en": "Cache Management"},
    "settings.cache_size": {"zh": "缓存大小", "en": "Cache Size"},
    "settings.cache_size_desc": {"zh": "当前缓存占用的磁盘空间", "en": "Current cache disk usage"},
    "settings.cache_count": {"zh": "缓存文件数", "en": "Cache Files"},
    "settings.cache_count_desc": {"zh": "缓存文件总数量", "en": "Total number of cache files"},
    "settings.clear_cache": {"zh": "清空缓存", "en": "Clear Cache"},
    "settings.refresh_cache": {"zh": "刷新", "en": "Refresh"},
    "settings.cache_size_value": {"zh": "{size:.2f} MB", "en": "{size:.2f} MB"},
    "settings.cache_count_value": {"zh": "{count} 个文件", "en": "{count} files"},
    "settings.confirm_clear_cache": {"zh": "确认清空缓存", "en": "Confirm Clear Cache"},
    "settings.confirm_clear_cache_msg": {"zh": "确定要清空所有缓存文件吗？这将删除 {count} 个文件（{size:.2f} MB）。", "en": "Clear all cache files? This will delete {count} files ({size:.2f} MB)."},
    "settings.cache_cleared": {"zh": "缓存已清空", "en": "Cache Cleared"},
    "settings.cache_cleared_msg": {"zh": "成功清空缓存，释放了 {size:.2f} MB 空间", "en": "Cache cleared successfully, freed {size:.2f} MB"},
    "settings.cache_clear_failed": {"zh": "清空缓存失败", "en": "Failed to Clear Cache"},
    "settings.cache_clear_failed_msg": {"zh": "清空缓存时发生错误", "en": "Error occurred while clearing cache"},
    "settings.cache_empty": {"zh": "缓存为空", "en": "Cache Empty"},
    "settings.cache_empty_msg": {"zh": "当前没有缓存文件", "en": "No cache files currently"},

    # Settings page - Performance Statistics
    "settings.performance_stats": {"zh": "性能统计", "en": "Performance Statistics"},
    "settings.total_files": {"zh": "总处理文件数", "en": "Total Files Processed"},
    "settings.total_files_desc": {"zh": "已成功处理的文件总数", "en": "Total number of files successfully processed"},
    "settings.avg_conversion_time": {"zh": "平均转换时间", "en": "Average Conversion Time"},
    "settings.avg_conversion_time_desc": {"zh": "每个文件的平均转换时间（秒）", "en": "Average conversion time per file (seconds)"},
    "settings.avg_generation_time": {"zh": "平均生成时间", "en": "Average Generation Time"},
    "settings.avg_generation_time_desc": {"zh": "每张卡片的平均生成时间（秒）", "en": "Average generation time per card (seconds)"},
    "settings.total_cards": {"zh": "总生成卡片数", "en": "Total Cards Generated"},
    "settings.total_cards_desc": {"zh": "已成功生成的卡片总数", "en": "Total number of cards successfully generated"},
    "settings.reset_stats": {"zh": "重置统计", "en": "Reset Statistics"},
    "settings.reset_stats_title": {"zh": "重置统计数据", "en": "Reset Statistics"},
    "settings.reset_stats_desc": {"zh": "清除所有性能统计数据", "en": "Clear all performance statistics data"},
    "settings.confirm_reset_stats": {"zh": "确认重置统计", "en": "Confirm Reset Statistics"},
    "settings.confirm_reset_stats_msg": {"zh": "确定要清除所有性能统计数据吗？", "en": "Clear all performance statistics data?"},
    "settings.stats_reset_success": {"zh": "统计数据已重置", "en": "Statistics Reset"},
    "settings.stats_reset_success_msg": {"zh": "性能统计数据已清除", "en": "Performance statistics data cleared"},
    "settings.files_unit": {"zh": "个文件", "en": "files"},
    "settings.seconds_unit": {"zh": "秒", "en": "s"},
    "settings.cards_unit": {"zh": "张卡片", "en": "cards"},
    "settings.no_data": {"zh": "暂无数据", "en": "No data"},

    # Settings page - Actions
    "settings.reset": {"zh": "恢复默认", "en": "Reset to Default"},
    "settings.reset_title": {"zh": "重置设置", "en": "Reset Settings"},
    "settings.reset_desc": {"zh": "将所有设置恢复为默认值", "en": "Restore all settings to default values"},
    "settings.save": {"zh": "保存配置", "en": "Save Configuration"},
    "settings.save_title": {"zh": "保存设置", "en": "Save Settings"},
    "settings.save_desc": {"zh": "保存所有配置更改", "en": "Save all configuration changes"},
    "settings.confirm_reset": {"zh": "确认重置", "en": "Confirm Reset"},
    "settings.confirm_reset_msg": {"zh": "确定要将所有设置恢复为默认值吗？", "en": "Reset all settings to default values?"},
    "settings.reset_complete": {"zh": "重置完成", "en": "Reset Complete"},
    "settings.reset_complete_msg": {"zh": "设置已恢复为默认值", "en": "Settings restored to default values"},
    "settings.error": {"zh": "错误", "en": "Error"},
    "settings.must_have_provider": {"zh": "至少需要配置一个 LLM 提供商", "en": "At least one LLM provider must be configured"},
    "settings.success": {"zh": "成功", "en": "Success"},
    "settings.save_success": {"zh": "配置保存成功", "en": "Configuration saved successfully"},
    "settings.save_failed": {"zh": "保存配置失败：{error}", "en": "Failed to save configuration: {error}"},

    # Common buttons
    "common.ok": {"zh": "确定", "en": "OK"},
    "common.cancel": {"zh": "取消", "en": "Cancel"},
    "common.yes": {"zh": "是", "en": "Yes"},
    "common.no": {"zh": "否", "en": "No"},
    "common.close": {"zh": "关闭", "en": "Close"},
    "common.save": {"zh": "保存", "en": "Save"},
    "common.apply": {"zh": "应用", "en": "Apply"},
    "common.reset": {"zh": "重置", "en": "Reset"},

    # File filters
    "file.all_supported": {"zh": "All Supported (*.md *.txt *.docx *.pptx *.pdf *.png *.jpg *.jpeg);;All Files (*.*)", "en": "All Supported (*.md *.txt *.docx *.pptx *.pdf *.png *.jpg *.jpeg);;All Files (*.*)"},
    "file.anki_package": {"zh": "Anki Package (*.apkg)", "en": "Anki Package (*.apkg)"},

    # Keyboard shortcuts
    "shortcuts.open_file": {"zh": "打开文件", "en": "Open File"},
    "shortcuts.start_generation": {"zh": "开始生成", "en": "Start Generation"},
    "shortcuts.save_edit": {"zh": "保存编辑", "en": "Save Edit"},
    "shortcuts.export_cards": {"zh": "导出卡片", "en": "Export Cards"},
    "shortcuts.open_settings": {"zh": "打开设置", "en": "Open Settings"},
    "shortcuts.help": {"zh": "帮助文档", "en": "Help"},
    "shortcuts.quit": {"zh": "退出应用", "en": "Quit Application"},
    "shortcuts.help_title": {"zh": "快捷键帮助", "en": "Keyboard Shortcuts"},
    "shortcuts.help_desc": {"zh": "查看所有可用的快捷键", "en": "View all available shortcuts"},

    # Error messages - Network
    "error.network.title": {"zh": "网络连接失败", "en": "Network Connection Failed"},
    "error.network.message": {"zh": "无法连接到服务器，请检查网络连接", "en": "Cannot connect to server, please check network connection"},
    "error.network.suggestion": {"zh": "• 检查网络连接是否正常\n• 检查代理设置\n• 确认服务器地址正确", "en": "• Check network connection\n• Verify proxy settings\n• Confirm server address is correct"},
    "error.timeout.title": {"zh": "请求超时", "en": "Request Timeout"},
    "error.timeout.message": {"zh": "服务器响应超时，请稍后重试", "en": "Server response timeout, please retry later"},
    "error.timeout.suggestion": {"zh": "• 检查网络速度\n• 尝试使用代理\n• 稍后重试", "en": "• Check network speed\n• Try using a proxy\n• Retry later"},
    "error.proxy.title": {"zh": "代理连接失败", "en": "Proxy Connection Failed"},
    "error.proxy.message": {"zh": "无法通过代理连接，请检查代理设置", "en": "Cannot connect through proxy, please check proxy settings"},
    "error.proxy.suggestion": {"zh": "• 检查代理地址格式\n• 确认代理服务可用\n• 尝试关闭代理", "en": "• Check proxy address format\n• Confirm proxy service is available\n• Try disabling proxy"},

    # Error messages - API Key
    "error.api_key.title": {"zh": "API Key 无效", "en": "Invalid API Key"},
    "error.api_key.message": {"zh": "API Key 无效或已过期，请在设置中检查配置", "en": "API Key is invalid or expired, please check configuration in settings"},
    "error.api_key.suggestion": {"zh": "• 检查 API Key 是否正确\n• 确认 API Key 未过期\n• 检查账户余额", "en": "• Verify API Key is correct\n• Confirm API Key is not expired\n• Check account balance"},
    "error.unauthorized.title": {"zh": "认证失败", "en": "Authentication Failed"},
    "error.unauthorized.message": {"zh": "API 认证失败，请检查 API Key 配置", "en": "API authentication failed, please check API Key configuration"},
    "error.unauthorized.suggestion": {"zh": "• 重新输入 API Key\n• 确认使用正确的提供商\n• 检查 API Key 权限", "en": "• Re-enter API Key\n• Confirm using correct provider\n• Check API Key permissions"},

    # Error messages - File Format
    "error.file_format.title": {"zh": "文件格式错误", "en": "File Format Error"},
    "error.file_format.message": {"zh": "不支持的文件格式，请选择 PDF、Word、PPT 或图片", "en": "Unsupported file format, please select PDF, Word, PPT or images"},
    "error.file_format.suggestion": {"zh": "• 支持的格式：PDF、DOCX、PPTX、PNG、JPG\n• 检查文件是否损坏\n• 尝试转换为支持的格式", "en": "• Supported formats: PDF, DOCX, PPTX, PNG, JPG\n• Check if file is corrupted\n• Try converting to supported format"},
    "error.file_corrupted.title": {"zh": "文件损坏", "en": "File Corrupted"},
    "error.file_corrupted.message": {"zh": "文件可能已损坏，无法读取", "en": "File may be corrupted and cannot be read"},
    "error.file_corrupted.suggestion": {"zh": "• 尝试重新下载文件\n• 使用其他工具打开验证\n• 选择其他文件", "en": "• Try re-downloading the file\n• Verify with other tools\n• Select another file"},
    "error.file_too_large.title": {"zh": "文件过大", "en": "File Too Large"},
    "error.file_too_large.message": {"zh": "文件大小超过限制，可能导致处理缓慢", "en": "File size exceeds limit, may cause slow processing"},
    "error.file_too_large.suggestion": {"zh": "• 尝试分割文件\n• 压缩文件大小\n• 启用自动分割功能", "en": "• Try splitting the file\n• Compress file size\n• Enable auto-split feature"},

    # Error messages - OCR
    "error.ocr.title": {"zh": "OCR 识别失败", "en": "OCR Recognition Failed"},
    "error.ocr.message": {"zh": "OCR 识别失败，请确保图片清晰", "en": "OCR recognition failed, please ensure image is clear"},
    "error.ocr.suggestion": {"zh": "• 使用更清晰的图片\n• 确保文字可读\n• 尝试调整图片亮度/对比度", "en": "• Use clearer images\n• Ensure text is readable\n• Try adjusting image brightness/contrast"},
    "error.ocr_model.title": {"zh": "OCR 模型缺失", "en": "OCR Model Missing"},
    "error.ocr_model.message": {"zh": "OCR 模型文件缺失，需要下载", "en": "OCR model files are missing and need to be downloaded"},
    "error.ocr_model.suggestion": {"zh": "• 点击下载按钮获取模型\n• 检查网络连接\n• 确保有足够磁盘空间", "en": "• Click download button to get models\n• Check network connection\n• Ensure sufficient disk space"},

    # Error messages - Anki
    "error.anki_connection.title": {"zh": "无法连接到 Anki", "en": "Cannot Connect to Anki"},
    "error.anki_connection.message": {"zh": "无法连接到 AnkiConnect，请确保 Anki 正在运行", "en": "Cannot connect to AnkiConnect, please ensure Anki is running"},
    "error.anki_connection.suggestion": {"zh": "• 启动 Anki 桌面应用\n• 安装 AnkiConnect 插件\n• 检查 AnkiConnect 设置", "en": "• Start Anki desktop application\n• Install AnkiConnect add-on\n• Check AnkiConnect settings"},
    "error.anki_permission.title": {"zh": "Anki 权限错误", "en": "Anki Permission Error"},
    "error.anki_permission.message": {"zh": "AnkiConnect 拒绝访问，请检查权限设置", "en": "AnkiConnect denied access, please check permission settings"},
    "error.anki_permission.suggestion": {"zh": "• 检查 AnkiConnect 配置\n• 确认 API Key 正确\n• 重启 Anki", "en": "• Check AnkiConnect configuration\n• Confirm API Key is correct\n• Restart Anki"},

    # Error messages - LLM Provider
    "error.llm_provider.title": {"zh": "LLM 提供商错误", "en": "LLM Provider Error"},
    "error.llm_provider.message": {"zh": "LLM 服务调用失败，请检查配置", "en": "LLM service call failed, please check configuration"},
    "error.llm_provider.suggestion": {"zh": "• 检查提供商配置\n• 确认 API Key 有效\n• 检查账户额度", "en": "• Check provider configuration\n• Confirm API Key is valid\n• Check account quota"},
    "error.rate_limit.title": {"zh": "请求频率限制", "en": "Rate Limit Exceeded"},
    "error.rate_limit.message": {"zh": "请求过于频繁，请稍后重试", "en": "Too many requests, please retry later"},
    "error.rate_limit.suggestion": {"zh": "• 等待一段时间后重试\n• 降低并发请求数\n• 升级 API 套餐", "en": "• Wait a moment and retry\n• Reduce concurrent requests\n• Upgrade API plan"},
    "error.quota_exceeded.title": {"zh": "配额已用尽", "en": "Quota Exceeded"},
    "error.quota_exceeded.message": {"zh": "API 配额已用尽，请充值或更换提供商", "en": "API quota exhausted, please recharge or switch provider"},
    "error.quota_exceeded.suggestion": {"zh": "• 充值账户\n• 更换其他提供商\n• 检查账户状态", "en": "• Recharge account\n• Switch to another provider\n• Check account status"},

    # Error messages - Permission
    "error.permission.title": {"zh": "权限不足", "en": "Permission Denied"},
    "error.permission.message": {"zh": "没有足够的权限执行此操作", "en": "Insufficient permissions to perform this operation"},
    "error.permission.suggestion": {"zh": "• 以管理员身份运行\n• 检查文件/文件夹权限\n• 更改保存位置", "en": "• Run as administrator\n• Check file/folder permissions\n• Change save location"},

    # Error messages - Validation
    "error.validation.title": {"zh": "输入验证失败", "en": "Validation Failed"},
    "error.validation.message": {"zh": "输入的数据格式不正确", "en": "Input data format is incorrect"},
    "error.validation.suggestion": {"zh": "• 检查输入格式\n• 确保必填项已填写\n• 参考示例格式", "en": "• Check input format\n• Ensure required fields are filled\n• Refer to example format"},

    # Error messages - Unknown
    "error.unknown.title": {"zh": "未知错误", "en": "Unknown Error"},
    "error.unknown.message": {"zh": "发生了未知错误", "en": "An unknown error occurred"},
    "error.unknown.suggestion": {"zh": "• 查看详细错误信息\n• 尝试重启应用\n• 联系技术支持", "en": "• Check detailed error message\n• Try restarting application\n• Contact technical support"},
    "error.technical_details": {"zh": "技术详情：", "en": "Technical Details:"},

    # Error action buttons
    "error.action.go_to_settings": {"zh": "去设置", "en": "Go to Settings"},
    "error.action.retry": {"zh": "重试", "en": "Retry"},
    "error.action.download_models": {"zh": "下载模型", "en": "Download Models"},

    # Log export
    "log.export_title": {"zh": "导出日志", "en": "Export Logs"},
    "log.export_desc": {"zh": "导出应用日志文件用于问题排查", "en": "Export application logs for troubleshooting"},
    "log.exporting": {"zh": "正在导出日志...", "en": "Exporting logs..."},
    "log.export_success": {"zh": "日志导出成功", "en": "Logs Exported Successfully"},
    "log.export_success_msg": {"zh": "日志已导出到：{path}", "en": "Logs exported to: {path}"},
    "log.export_failed": {"zh": "日志导出失败", "en": "Log Export Failed"},
    "log.export_failed_msg": {"zh": "导出日志时发生错误：{error}", "en": "Error occurred while exporting logs: {error}"},
    "log.no_logs_found": {"zh": "未找到日志文件", "en": "No log files found"},
    "log.select_location": {"zh": "选择保存位置", "en": "Select Save Location"},
    "log.zip_file": {"zh": "日志压缩包 (*.zip)", "en": "Log Archive (*.zip)"},

    # Log level settings
    "log.level": {"zh": "日志级别", "en": "Log Level"},
    "log.level_desc": {"zh": "设置应用程序日志记录级别", "en": "Set application logging level"},
    "log.level_debug": {"zh": "DEBUG - 调试", "en": "DEBUG - Debug"},
    "log.level_info": {"zh": "INFO - 信息", "en": "INFO - Information"},
    "log.level_warning": {"zh": "WARNING - 警告", "en": "WARNING - Warning"},
    "log.level_error": {"zh": "ERROR - 错误", "en": "ERROR - Error"},
    "log.view_logs": {"zh": "查看日志", "en": "View Logs"},
    "log.view_logs_desc": {"zh": "打开日志文件所在目录", "en": "Open log files directory"},
    "log.open_folder": {"zh": "打开文件夹", "en": "Open Folder"},
    "log.level_changed": {"zh": "日志级别已更改", "en": "Log Level Changed"},
    "log.level_changed_msg": {"zh": "日志级别已设置为 {level}", "en": "Log level set to {level}"},
}


def get_text(key: str, lang: str | None = None, **kwargs) -> str:
    """Get translated text for a given key.

    Args:
        key: Translation key (e.g., "nav.import", "import.title")
        lang: Language code ("zh" or "en"), defaults to current language
        **kwargs: Placeholder values for string formatting

    Returns:
        Translated text with placeholders replaced. If key is not found,
        returns the key itself as fallback.

    Examples:
        >>> get_text("nav.import", "zh")
        '导入'
        >>> get_text("import.files_selected", "en", count=5)
        '5 files selected'
        >>> get_text("import.converting_file", "zh", filename="test.pdf", current=1, total=3)
        '正在转换: test.pdf (1/3)'
    """
    if lang is None:
        lang = _current_language

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
