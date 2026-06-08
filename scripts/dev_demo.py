from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
EXAMPLES_DIR = PROJECT_ROOT / "examples"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ankismart.core.models import (  # noqa: E402
    BatchConvertResult,
    CardDraft,
    CardMetadata,
    CardPushStatus,
    ConvertedDocument,
    MarkdownResult,
    PushResult,
)


@dataclass(frozen=True, slots=True)
class DemoPayload:
    file_paths: list[Path]
    batch_result: BatchConvertResult
    cards: list[CardDraft]
    push_result: PushResult


def _example_file_paths() -> list[Path]:
    paths = [
        EXAMPLES_DIR / "sample.md",
        EXAMPLES_DIR / "sample-biology.md",
        EXAMPLES_DIR / "sample-math.md",
    ]
    missing = [path for path in paths if not path.exists()]
    if missing:
        missing_text = ", ".join(str(path) for path in missing)
        raise FileNotFoundError(f"Missing demo example files: {missing_text}")
    return paths


def _build_batch_result(file_paths: list[Path]) -> BatchConvertResult:
    documents: list[ConvertedDocument] = []
    for path in file_paths:
        documents.append(
            ConvertedDocument(
                file_name=path.name,
                result=MarkdownResult(
                    content=path.read_text(encoding="utf-8"),
                    source_path=str(path),
                    source_format="markdown",
                    trace_id=f"dev-demo-{path.stem}",
                ),
            )
        )
    return BatchConvertResult(documents=documents)


def _basic_card(
    index: int,
    *,
    front: str,
    back: str,
    source_path: Path,
) -> CardDraft:
    return CardDraft(
        trace_id=f"dev-demo-card-{index}",
        deck_name="Ankismart Demo",
        note_type="Basic",
        fields={"Front": front, "Back": back},
        tags=["ankismart", "dev-demo"],
        metadata=CardMetadata(
            source_format="markdown",
            source_path=str(source_path),
            strategy_id="basic",
            source_document=source_path.name,
        ),
    )


def _build_cards(file_paths: list[Path]) -> list[CardDraft]:
    sample, biology, math = file_paths
    return [
        _basic_card(
            1,
            front="What is Ankismart's demo workflow based on?",
            back=(
                "Local markdown examples converted into flashcard drafts "
                "without network services."
            ),
            source_path=sample,
        ),
        _basic_card(
            2,
            front="What does Big O notation describe?",
            back="The worst-case growth of an algorithm's time or space cost.",
            source_path=sample,
        ),
        _basic_card(
            3,
            front="What is the role of mitochondria?",
            back="They perform aerobic respiration and generate ATP for the cell.",
            source_path=biology,
        ),
        _basic_card(
            4,
            front="What is the central dogma of molecular biology?",
            back="Genetic information flows from DNA to RNA to protein.",
            source_path=biology,
        ),
        _basic_card(
            5,
            front="What does the derivative of a function measure?",
            back="The instantaneous rate of change of that function.",
            source_path=math,
        ),
    ]


def _build_push_result(cards: list[CardDraft]) -> PushResult:
    results = [
        CardPushStatus(index=index, note_id=9000 + index, success=True)
        for index, _card in enumerate(cards, start=1)
    ]
    return PushResult(
        total=len(cards),
        succeeded=len(cards),
        failed=0,
        results=results,
        trace_id="dev-demo-push",
    )


def build_demo_payload() -> DemoPayload:
    file_paths = _example_file_paths()
    batch_result = _build_batch_result(file_paths)
    cards = _build_cards(file_paths)
    push_result = _build_push_result(cards)
    return DemoPayload(
        file_paths=file_paths,
        batch_result=batch_result,
        cards=cards,
        push_result=push_result,
    )


if __name__ == "__main__":
    payload = build_demo_payload()
    print(
        "Demo payload: "
        f"{len(payload.file_paths)} files, "
        f"{len(payload.batch_result.documents)} documents, "
        f"{len(payload.cards)} cards, "
        f"{payload.push_result.succeeded} pushed"
    )
