from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
DEMO_RUNTIME_ROOT = PROJECT_ROOT / ".local" / "dev-demo"
DEMO_CONFIG_DIR = DEMO_RUNTIME_ROOT / "config"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


@dataclass(slots=True)
class DemoPayload:
    file_paths: list[Path]
    config: object
    batch_result: object
    cards: list[object]
    push_result: object


def configure_demo_environment() -> Path:
    """Route demo runtime state into a dedicated local folder."""
    os.environ["ANKISMART_APP_DIR"] = str(DEMO_CONFIG_DIR)
    DEMO_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return DEMO_CONFIG_DIR


def _example_paths() -> list[Path]:
    paths = [
        PROJECT_ROOT / "examples" / "sample.md",
        PROJECT_ROOT / "examples" / "sample-math.md",
        PROJECT_ROOT / "examples" / "sample-biology.md",
    ]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing demo example files: {', '.join(missing)}")
    return paths


def build_demo_config(language: str = "zh", theme: str = "light"):
    from ankismart.core.config import AppConfig, LLMProviderConfig

    today = date.today()
    return AppConfig(
        llm_providers=[
            LLMProviderConfig(
                id="demo-openai",
                name="OpenAI",
                api_key="demo-key",
                base_url="https://api.openai.com/v1",
                model="gpt-4o-mini",
                rpm_limit=60,
            ),
            LLMProviderConfig(
                id="demo-ollama",
                name="Ollama (本地)",
                api_key="",
                base_url="http://127.0.0.1:11434/v1",
                model="qwen2.5:7b",
                rpm_limit=0,
            ),
        ],
        active_provider_id="demo-openai",
        anki_connect_url="http://127.0.0.1:8765",
        default_deck="Ankismart::Demo",
        default_tags=["ankismart", "demo", "showcase"],
        last_deck="Ankismart::Demo",
        last_tags="ankismart,demo,showcase",
        last_strategy="mixed",
        last_update_mode="create_or_update",
        llm_temperature=0.4,
        llm_concurrency=3,
        llm_concurrency_max=6,
        ocr_mode="cloud",
        ocr_cloud_provider="mineru",
        ocr_cloud_endpoint="https://mineru.net",
        ocr_model_tier="standard",
        ocr_model_source="official",
        duplicate_scope="deck",
        duplicate_check_model=True,
        allow_duplicate=False,
        semantic_duplicate_threshold=0.88,
        proxy_mode="manual",
        proxy_url="http://127.0.0.1:7890",
        language=language,
        theme=theme,
        total_files_processed=18,
        total_conversion_time=94.5,
        total_generation_time=37.2,
        total_cards_generated=146,
        ocr_cloud_priority_daily_quota=2000,
        ocr_cloud_priority_pages_used_today=236,
        ocr_cloud_usage_date=today.isoformat(),
        ocr_cloud_total_pages=1284,
        ocr_cloud_cost_per_1k_pages=5.2,
        ocr_resume_file_paths=[str(path) for path in _example_paths()],
        ocr_resume_updated_at=f"{today.isoformat()}T10:15:00",
        task_history=[
            {
                "id": "demo-task-1",
                "time": f"{today.isoformat()}T09:40:00",
                "event": "batch_convert",
                "status": "success",
                "summary": "批量转换 3 个示例文档",
            },
            {
                "id": "demo-task-2",
                "time": f"{today.isoformat()}T09:43:00",
                "event": "batch_generate",
                "status": "partial",
                "summary": "生成 6 张卡片，其中 1 张待复核",
            },
            {
                "id": "demo-task-3",
                "time": f"{today.isoformat()}T09:48:00",
                "event": "push",
                "status": "partial",
                "summary": "推送成功 4 张，失败 1 张，跳过 1 张",
            },
        ],
        ops_error_counters={
            "convert:ocr_timeout": 2,
            "generate:quality_retry": 1,
            "push:duplicate_note": 3,
        },
        ops_conversion_durations=[2.7, 3.1, 4.4, 5.0, 6.2, 7.4],
        ops_generation_durations=[0.9, 1.1, 1.4, 1.8, 2.1, 2.6],
        ops_push_durations=[0.4, 0.6, 0.8, 0.9, 1.2],
        ops_export_durations=[1.3, 1.8],
        ops_cloud_pages_daily=[
            {"date": (today - timedelta(days=6)).isoformat(), "pages": 88},
            {"date": (today - timedelta(days=5)).isoformat(), "pages": 104},
            {"date": (today - timedelta(days=4)).isoformat(), "pages": 129},
            {"date": (today - timedelta(days=3)).isoformat(), "pages": 156},
            {"date": (today - timedelta(days=2)).isoformat(), "pages": 141},
            {"date": (today - timedelta(days=1)).isoformat(), "pages": 183},
            {"date": today.isoformat(), "pages": 236},
        ],
    )


def build_demo_batch_result(file_paths: list[Path] | None = None):
    from ankismart.core.models import BatchConvertResult, ConvertedDocument, MarkdownResult

    resolved_paths = file_paths or _example_paths()
    documents = []
    for index, file_path in enumerate(resolved_paths, start=1):
        documents.append(
            ConvertedDocument(
                result=MarkdownResult(
                    content=file_path.read_text(encoding="utf-8"),
                    source_path=str(file_path),
                    source_format="markdown",
                    trace_id=f"demo-doc-{index}",
                ),
                file_name=file_path.name,
            )
        )
    return BatchConvertResult(
        documents=documents,
        warnings=["sample-scan.pdf: OCR 演示样例未纳入当前开发脚本"],
    )


def build_demo_cards(batch_result=None):
    from ankismart.core.models import CardDraft, CardMetadata

    if batch_result is None:
        batch_result = build_demo_batch_result()

    documents = list(batch_result.documents)
    if len(documents) < 3:
        raise ValueError("Demo batch result requires at least 3 documents")

    return [
        CardDraft(
            trace_id=documents[0].result.trace_id,
            deck_name="Ankismart::Demo",
            note_type="Basic",
            fields={
                "Front": "什么是 Markdown 中的二级标题？",
                "Back": "以两个 # 开头的标题\n解析：常用于章节级小节。",
            },
            tags=["ankismart", "demo", "basic"],
            metadata=CardMetadata(
                source_format=documents[0].result.source_format,
                source_path=documents[0].result.source_path,
                generated_at="2026-03-17T09:42:00",
            ),
        ),
        CardDraft(
            trace_id=documents[0].result.trace_id,
            deck_name="Ankismart::Demo",
            note_type="Cloze",
            fields={
                "Text": "在 Ankismart 中，{{c1::Preview Page}} 用于检查转换后的 Markdown。",
                "Extra": "对应导航中的“预览”页面。",
            },
            tags=["ankismart", "demo", "cloze"],
            metadata=CardMetadata(
                source_format=documents[0].result.source_format,
                source_path=documents[0].result.source_path,
                generated_at="2026-03-17T09:42:20",
            ),
        ),
        CardDraft(
            trace_id=documents[1].result.trace_id,
            deck_name="Ankismart::Math",
            note_type="Basic",
            fields={
                "Front": "概念：导数的几何意义是什么？",
                "Back": "函数图像在该点切线的斜率\n解析：表示瞬时变化率。",
            },
            tags=["ankismart", "demo", "concept", "math"],
            metadata=CardMetadata(
                source_format=documents[1].result.source_format,
                source_path=documents[1].result.source_path,
                generated_at="2026-03-17T09:43:00",
            ),
        ),
        CardDraft(
            trace_id=documents[2].result.trace_id,
            deck_name="Ankismart::Biology",
            note_type="Basic",
            fields={
                "Front": "术语：细胞膜的主要功能",
                "Back": "控制物质进出并维持细胞内环境稳定",
            },
            tags=["ankismart", "demo", "key_terms", "biology"],
            metadata=CardMetadata(
                source_format=documents[2].result.source_format,
                source_path=documents[2].result.source_path,
                generated_at="2026-03-17T09:43:20",
            ),
        ),
        CardDraft(
            trace_id=documents[1].result.trace_id,
            deck_name="Ankismart::Math",
            note_type="Basic",
            fields={
                "Front": (
                    "一元二次方程 ax^2+bx+c=0 的求根公式是？\n"
                    "A. x=b/a\n"
                    "B. x=(-b±√(b^2-4ac))/2a\n"
                    "C. x=c/a\n"
                    "D. x=(a+b)/c"
                ),
                "Back": "答案：B\n解析：判别式为 b^2-4ac。",
            },
            tags=["ankismart", "demo", "single_choice", "math"],
            metadata=CardMetadata(
                source_format=documents[1].result.source_format,
                source_path=documents[1].result.source_path,
                generated_at="2026-03-17T09:44:10",
            ),
        ),
        CardDraft(
            trace_id=documents[2].result.trace_id,
            deck_name="Ankismart::Biology",
            note_type="Basic",
            fields={
                "Front": "下列哪些属于细胞器？\nA. 线粒体\nB. 核糖体\nC. 叶绿体\nD. 细胞壁",
                "Back": "答案：A, B, C\n解析：细胞壁通常不归类为细胞器。",
            },
            tags=["ankismart", "demo", "multiple_choice", "biology"],
            metadata=CardMetadata(
                source_format=documents[2].result.source_format,
                source_path=documents[2].result.source_path,
                generated_at="2026-03-17T09:44:40",
            ),
        ),
    ]


def build_demo_push_result(cards=None):
    from ankismart.core.models import CardPushStatus, PushResult

    demo_cards = cards or build_demo_cards()
    results = []
    for index, _ in enumerate(demo_cards):
        if index < 4:
            results.append(CardPushStatus(index=index, note_id=30001 + index, success=True))
        elif index == 4:
            results.append(
                CardPushStatus(
                    index=index,
                    success=False,
                    error="Duplicate note detected in deck Ankismart::Math",
                )
            )
        else:
            results.append(CardPushStatus(index=index, success=False, error=""))

    succeeded = sum(1 for item in results if item.success)
    failed = sum(1 for item in results if (not item.success) and bool(item.error))
    return PushResult(
        total=len(results),
        succeeded=succeeded,
        failed=failed,
        results=results,
        trace_id="demo-push-20260317",
    )


def build_demo_payload(language: str = "zh", theme: str = "light") -> DemoPayload:
    file_paths = _example_paths()
    batch_result = build_demo_batch_result(file_paths)
    cards = build_demo_cards(batch_result)
    return DemoPayload(
        file_paths=file_paths,
        config=build_demo_config(language=language, theme=theme),
        batch_result=batch_result,
        cards=cards,
        push_result=build_demo_push_result(cards),
    )


def prime_demo_window(window) -> DemoPayload:
    """Populate a live MainWindow with demo data for local development."""
    payload = build_demo_payload(language=window.config.language, theme=window.config.theme)
    window.apply_runtime_config(payload.config, persist=False)
    window.import_page._add_files(payload.file_paths)
    window.batch_result = payload.batch_result
    window.preview_page.load_documents(
        payload.batch_result,
        pending_files_count=1,
        total_expected=len(payload.batch_result.documents) + 1,
    )
    window.cards = payload.cards
    window.card_preview_page.load_cards(payload.cards)
    window.result_page.load_result(payload.push_result, payload.cards)
    window.switchTo(window.import_page)
    return payload


def launch_demo(language: str = "zh", theme: str = "light") -> int:
    configure_demo_environment()

    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import QApplication

    from ankismart.core.logging import setup_logging
    from ankismart.ui.app import _apply_text_clarity_profile, _apply_theme, _get_icon_path
    from ankismart.ui.main_window import MainWindow

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Ankismart Dev Demo")
    app.setOrganizationName("Ankismart")
    _apply_text_clarity_profile(app)
    setup_logging(level=logging.INFO)

    icon_path = _get_icon_path()
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    payload = build_demo_payload(language=language, theme=theme)
    _apply_theme(theme)

    window = MainWindow(payload.config)
    window.show()
    prime_demo_window(window)

    return app.exec()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Launch Ankismart with development-only showcase data."
    )
    parser.add_argument("--language", choices=("zh", "en"), default="zh")
    parser.add_argument("--theme", choices=("light", "dark", "auto"), default="light")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    return launch_demo(language=args.language, theme=args.theme)


if __name__ == "__main__":
    raise SystemExit(main())
