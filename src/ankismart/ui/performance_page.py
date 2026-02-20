from __future__ import annotations

from PyQt6.QtWidgets import QMessageBox, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    PushSettingCard,
    SettingCard,
    SettingCardGroup,
    SubtitleLabel,
)
from qfluentwidgets import (
    FluentIcon as FIF,
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
        layout.setContentsMargins(MARGIN_STANDARD, MARGIN_STANDARD, MARGIN_STANDARD, MARGIN_STANDARD)
        layout.setSpacing(SPACING_MEDIUM)

        title = SubtitleLabel("性能统计" if self._main.config.language == "zh" else "Performance Statistics")
        apply_page_title_style(title)
        layout.addWidget(title)

        self._stats_group = SettingCardGroup(
            "统计信息" if self._main.config.language == "zh" else "Statistics",
            self,
        )

        self._total_files_card = SettingCard(
            FIF.DOCUMENT,
            "总处理文件数" if self._main.config.language == "zh" else "Total Files Processed",
            "已成功处理的文件总数" if self._main.config.language == "zh" else "Total number of processed files",
            self,
        )
        self._total_files_label = BodyLabel("0")
        self._total_files_label.setMinimumWidth(160)
        self._total_files_card.hBoxLayout.addWidget(self._total_files_label)
        self._total_files_card.hBoxLayout.addSpacing(16)
        self._stats_group.addSettingCard(self._total_files_card)

        self._avg_conversion_card = SettingCard(
            FIF.SPEED_OFF,
            "平均转换时间" if self._main.config.language == "zh" else "Average Conversion Time",
            "每个文件的平均转换时间（秒）" if self._main.config.language == "zh" else "Average conversion time per file (s)",
            self,
        )
        self._avg_conversion_label = BodyLabel("0.0")
        self._avg_conversion_label.setMinimumWidth(160)
        self._avg_conversion_card.hBoxLayout.addWidget(self._avg_conversion_label)
        self._avg_conversion_card.hBoxLayout.addSpacing(16)
        self._stats_group.addSettingCard(self._avg_conversion_card)

        self._avg_generation_card = SettingCard(
            FIF.SPEED_HIGH,
            "平均生成时间" if self._main.config.language == "zh" else "Average Generation Time",
            "每张卡片的平均生成时间（秒）" if self._main.config.language == "zh" else "Average generation time per card (s)",
            self,
        )
        self._avg_generation_label = BodyLabel("0.0")
        self._avg_generation_label.setMinimumWidth(160)
        self._avg_generation_card.hBoxLayout.addWidget(self._avg_generation_label)
        self._avg_generation_card.hBoxLayout.addSpacing(16)
        self._stats_group.addSettingCard(self._avg_generation_card)

        self._total_cards_card = SettingCard(
            FIF.TILES,
            "总生成卡片数" if self._main.config.language == "zh" else "Total Cards Generated",
            "已成功生成的卡片总数" if self._main.config.language == "zh" else "Total number of generated cards",
            self,
        )
        self._total_cards_label = BodyLabel("0")
        self._total_cards_label.setMinimumWidth(160)
        self._total_cards_card.hBoxLayout.addWidget(self._total_cards_label)
        self._total_cards_card.hBoxLayout.addSpacing(16)
        self._stats_group.addSettingCard(self._total_cards_card)

        self._reset_stats_card = PushSettingCard(
            "重置统计" if self._main.config.language == "zh" else "Reset Stats",
            FIF.DELETE,
            "重置统计数据" if self._main.config.language == "zh" else "Reset Statistics",
            "清除所有性能统计数据" if self._main.config.language == "zh" else "Clear all performance statistics",
        )
        self._reset_stats_card.clicked.connect(self._reset_statistics)
        self._stats_group.addSettingCard(self._reset_stats_card)

        layout.addWidget(self._stats_group)
        layout.addStretch(1)

    def refresh_statistics(self) -> None:
        config = self._main.config
        is_zh = config.language == "zh"

        files_text = f"{config.total_files_processed} 个文件" if is_zh else f"{config.total_files_processed} files"
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

        cards_text = f"{config.total_cards_generated} 张卡片" if is_zh else f"{config.total_cards_generated} cards"
        self._total_cards_label.setText(cards_text)

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

    def showEvent(self, event) -> None:
        self.refresh_statistics()
        super().showEvent(event)

    def retranslate_ui(self) -> None:
        self.refresh_statistics()

    def update_theme(self) -> None:
        pass
