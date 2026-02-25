from __future__ import annotations

from datetime import date

from PyQt6.QtWidgets import QMessageBox, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    FluentIcon,
    PushSettingCard,
    SettingCard,
    SettingCardGroup,
    SubtitleLabel,
)

from ankismart.core.config import save_config
from ankismart.ui.styles import MARGIN_STANDARD, SPACING_MEDIUM, apply_page_title_style


class PerformancePage(QWidget):
    """Standalone page for performance statistics."""

    def __init__(self, main_window):
        super().__init__()
        self._main = main_window
        self.setObjectName("performancePage")
        self._init_ui()
        self.refresh_statistics()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            MARGIN_STANDARD, MARGIN_STANDARD, MARGIN_STANDARD, MARGIN_STANDARD
        )
        layout.setSpacing(SPACING_MEDIUM)

        title = SubtitleLabel(
            "性能统计" if self._main.config.language == "zh" else "Performance Statistics"
        )
        apply_page_title_style(title)
        layout.addWidget(title)

        self._stats_group = SettingCardGroup(
            "统计信息" if self._main.config.language == "zh" else "Statistics",
            self,
        )

        self._total_files_card = SettingCard(
            FluentIcon.DOCUMENT,
            "总处理文件数" if self._main.config.language == "zh" else "Total Files Processed",
            "已成功处理的文件总数"
            if self._main.config.language == "zh"
            else "Total number of processed files",
            self,
        )
        self._total_files_label = BodyLabel("0")
        self._total_files_label.setMinimumWidth(160)
        self._total_files_card.hBoxLayout.addWidget(self._total_files_label)
        self._total_files_card.hBoxLayout.addSpacing(16)
        self._stats_group.addSettingCard(self._total_files_card)

        self._avg_conversion_card = SettingCard(
            FluentIcon.SPEED_OFF,
            "平均转换时间" if self._main.config.language == "zh" else "Average Conversion Time",
            "每个文件的平均转换时间（秒）"
            if self._main.config.language == "zh"
            else "Average conversion time per file (s)",
            self,
        )
        self._avg_conversion_label = BodyLabel("0.0")
        self._avg_conversion_label.setMinimumWidth(160)
        self._avg_conversion_card.hBoxLayout.addWidget(self._avg_conversion_label)
        self._avg_conversion_card.hBoxLayout.addSpacing(16)
        self._stats_group.addSettingCard(self._avg_conversion_card)

        self._avg_generation_card = SettingCard(
            FluentIcon.SPEED_HIGH,
            "平均生成时间" if self._main.config.language == "zh" else "Average Generation Time",
            "每张卡片的平均生成时间（秒）"
            if self._main.config.language == "zh"
            else "Average generation time per card (s)",
            self,
        )
        self._avg_generation_label = BodyLabel("0.0")
        self._avg_generation_label.setMinimumWidth(160)
        self._avg_generation_card.hBoxLayout.addWidget(self._avg_generation_label)
        self._avg_generation_card.hBoxLayout.addSpacing(16)
        self._stats_group.addSettingCard(self._avg_generation_card)

        self._total_cards_card = SettingCard(
            FluentIcon.TILES,
            "总生成卡片数" if self._main.config.language == "zh" else "Total Cards Generated",
            "已成功生成的卡片总数"
            if self._main.config.language == "zh"
            else "Total number of generated cards",
            self,
        )
        self._total_cards_label = BodyLabel("0")
        self._total_cards_label.setMinimumWidth(160)
        self._total_cards_card.hBoxLayout.addWidget(self._total_cards_label)
        self._total_cards_card.hBoxLayout.addSpacing(16)
        self._stats_group.addSettingCard(self._total_cards_card)

        self._reset_stats_card = PushSettingCard(
            "重置统计" if self._main.config.language == "zh" else "Reset Stats",
            FluentIcon.DELETE,
            "重置统计数据" if self._main.config.language == "zh" else "Reset Statistics",
            "清除所有性能统计数据"
            if self._main.config.language == "zh"
            else "Clear all performance statistics",
        )
        self._reset_stats_card.clicked.connect(self._reset_statistics)
        self._stats_group.addSettingCard(self._reset_stats_card)

        layout.addWidget(self._stats_group)

        self._cloud_group = SettingCardGroup(
            "云 OCR 配额与成本" if self._main.config.language == "zh" else "Cloud OCR Quota & Cost",
            self,
        )
        self._cloud_quota_card = SettingCard(
            FluentIcon.CLOUD,
            "今日优先级额度" if self._main.config.language == "zh" else "Today's Priority Quota",
            "按官方说明每日 2000 页为最高优先级"
            if self._main.config.language == "zh"
            else "Officially, first 2000 pages/day are high-priority",
            self,
        )
        self._cloud_quota_label = BodyLabel("-")
        self._cloud_quota_label.setMinimumWidth(220)
        self._cloud_quota_card.hBoxLayout.addWidget(self._cloud_quota_label)
        self._cloud_quota_card.hBoxLayout.addSpacing(16)
        self._cloud_group.addSettingCard(self._cloud_quota_card)

        self._cloud_total_card = SettingCard(
            FluentIcon.DICTIONARY,
            "累计云 OCR 页数" if self._main.config.language == "zh" else "Total Cloud OCR Pages",
            "仅统计本客户端记录到的成功转换页数估算"
            if self._main.config.language == "zh"
            else "Estimated from successful conversions recorded by this client",
            self,
        )
        self._cloud_total_label = BodyLabel("-")
        self._cloud_total_label.setMinimumWidth(220)
        self._cloud_total_card.hBoxLayout.addWidget(self._cloud_total_label)
        self._cloud_total_card.hBoxLayout.addSpacing(16)
        self._cloud_group.addSettingCard(self._cloud_total_card)

        self._cloud_cost_card = SettingCard(
            FluentIcon.INFO,
            "估算成本" if self._main.config.language == "zh" else "Estimated Cost",
            "按配置的每千页成本估算（默认 0）"
            if self._main.config.language == "zh"
            else "Estimated using configured cost per 1k pages (default 0)",
            self,
        )
        self._cloud_cost_label = BodyLabel("-")
        self._cloud_cost_label.setMinimumWidth(220)
        self._cloud_cost_card.hBoxLayout.addWidget(self._cloud_cost_label)
        self._cloud_cost_card.hBoxLayout.addSpacing(16)
        self._cloud_group.addSettingCard(self._cloud_cost_card)
        layout.addWidget(self._cloud_group)

        self._history_group = SettingCardGroup(
            "批处理任务历史" if self._main.config.language == "zh" else "Batch Task History",
            self,
        )
        self._history_card = SettingCard(
            FluentIcon.DOCUMENT,
            "最近记录" if self._main.config.language == "zh" else "Recent Records",
            "显示最近 10 条任务记录"
            if self._main.config.language == "zh"
            else "Show latest 10 tasks",
            self,
        )
        self._history_label = BodyLabel("-")
        self._history_label.setWordWrap(True)
        self._history_label.setMinimumWidth(360)
        self._history_card.hBoxLayout.addWidget(self._history_label)
        self._history_card.hBoxLayout.addSpacing(16)
        self._history_group.addSettingCard(self._history_card)

        self._clear_history_card = PushSettingCard(
            "清空历史" if self._main.config.language == "zh" else "Clear History",
            FluentIcon.DELETE,
            "清空批处理历史" if self._main.config.language == "zh" else "Clear Batch History",
            "只清除历史记录，不影响卡片和配置"
            if self._main.config.language == "zh"
            else "Only clears history records, keeps cards and config",
        )
        self._clear_history_card.clicked.connect(self._clear_task_history)
        self._history_group.addSettingCard(self._clear_history_card)
        layout.addWidget(self._history_group)
        layout.addStretch(1)

    def refresh_statistics(self) -> None:
        config = self._main.config
        is_zh = config.language == "zh"

        today = date.today().isoformat()
        if getattr(config, "ocr_cloud_usage_date", "") != today:
            config.ocr_cloud_usage_date = today
            config.ocr_cloud_priority_pages_used_today = 0

        files_text = (
            f"{config.total_files_processed} 个文件"
            if is_zh
            else f"{config.total_files_processed} files"
        )
        self._total_files_label.setText(files_text)

        avg_conversion = 0.0
        if config.total_files_processed > 0:
            avg_conversion = config.total_conversion_time / config.total_files_processed
        conv_text = f"{avg_conversion:.1f} 秒" if is_zh else f"{avg_conversion:.1f} s"
        self._avg_conversion_label.setText(conv_text)

        avg_generation = 0.0
        if config.total_cards_generated > 0:
            avg_generation = config.total_generation_time / config.total_cards_generated
        gen_text = f"{avg_generation:.1f} 秒" if is_zh else f"{avg_generation:.1f} s"
        self._avg_generation_label.setText(gen_text)

        cards_text = (
            f"{config.total_cards_generated} 张卡片"
            if is_zh
            else f"{config.total_cards_generated} cards"
        )
        self._total_cards_label.setText(cards_text)

        daily_quota = max(1, int(getattr(config, "ocr_cloud_priority_daily_quota", 2000)))
        used_today = max(0, int(getattr(config, "ocr_cloud_priority_pages_used_today", 0)))
        remaining = max(0, daily_quota - used_today)
        self._cloud_quota_label.setText(
            f"{used_today}/{daily_quota} 页（剩余 {remaining}）"
            if is_zh
            else f"{used_today}/{daily_quota} pages (remaining {remaining})"
        )

        total_cloud_pages = max(0, int(getattr(config, "ocr_cloud_total_pages", 0)))
        self._cloud_total_label.setText(
            f"{total_cloud_pages} 页" if is_zh else f"{total_cloud_pages} pages"
        )

        per_1k = max(0.0, float(getattr(config, "ocr_cloud_cost_per_1k_pages", 0.0)))
        cost_today = used_today / 1000.0 * per_1k
        cost_total = total_cloud_pages / 1000.0 * per_1k
        self._cloud_cost_label.setText(
            f"今日 {cost_today:.2f} / 累计 {cost_total:.2f}"
            if is_zh
            else f"Today {cost_today:.2f} / Total {cost_total:.2f}"
        )

        history = list(getattr(config, "task_history", []) or [])[:10]
        if not history:
            self._history_label.setText("暂无任务历史" if is_zh else "No task history yet")
        else:
            lines: list[str] = []
            for item in history:
                timestamp = str(item.get("time", "-"))
                event = str(item.get("event", "-"))
                status = str(item.get("status", "-"))
                summary = str(item.get("summary", ""))
                lines.append(f"[{timestamp}] {event}/{status}: {summary}")
            self._history_label.setText("\n".join(lines))

    def _reset_statistics(self) -> None:
        is_zh = self._main.config.language == "zh"
        reply = QMessageBox.question(
            self,
            "确认重置" if is_zh else "Confirm Reset",
            "确定要重置所有统计数据吗？" if is_zh else "Reset all statistics?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._main.config.total_files_processed = 0
        self._main.config.total_conversion_time = 0.0
        self._main.config.total_generation_time = 0.0
        self._main.config.total_cards_generated = 0
        save_config(self._main.config)
        self.refresh_statistics()

    def _clear_task_history(self) -> None:
        is_zh = self._main.config.language == "zh"
        reply = QMessageBox.question(
            self,
            "确认清空" if is_zh else "Confirm Clear",
            "确定要清空批处理任务历史吗？" if is_zh else "Clear batch task history?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._main.config.task_history = []
        save_config(self._main.config)
        self.refresh_statistics()

    def showEvent(self, event) -> None:  # noqa: N802
        self.refresh_statistics()
        super().showEvent(event)

    def retranslate_ui(self) -> None:
        self.refresh_statistics()

    def update_theme(self) -> None:
        pass
