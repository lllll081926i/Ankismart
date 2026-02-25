from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

# ---------------------------------------------------------------------------
# CardDraft sub-models (matches 闪卡格式规范 §3.2)
# ---------------------------------------------------------------------------

class MediaItem(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    filename: str
    path: str | None = None
    url: str | None = None
    data: str | None = None  # Base64
    fields: list[str] = Field(default_factory=list)


class MediaAttachments(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    audio: list[MediaItem] = Field(default_factory=list)
    video: list[MediaItem] = Field(default_factory=list)
    picture: list[MediaItem] = Field(default_factory=list)


class DuplicateScopeOptions(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    deck_name: str = "Default"
    check_children: bool = False
    check_all_models: bool = False


class CardOptions(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    allow_duplicate: bool = False
    duplicate_scope: str = "deck"
    duplicate_scope_options: DuplicateScopeOptions = Field(
        default_factory=DuplicateScopeOptions,
    )


class CardMetadata(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    source_format: str = ""
    source_path: str = ""
    generated_at: str = ""


class CardDraft(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    schema_version: str = "1.0"
    trace_id: str = ""
    deck_name: str = "Default"
    note_type: str = "Basic"
    fields: dict[str, str]
    tags: list[str] = Field(default_factory=list)
    media: MediaAttachments = Field(default_factory=MediaAttachments)
    options: CardOptions = Field(default_factory=CardOptions)
    metadata: CardMetadata = Field(default_factory=CardMetadata)


# ---------------------------------------------------------------------------
# MarkdownResult -- output of converter
# ---------------------------------------------------------------------------

class MarkdownResult(BaseModel):
    content: str
    source_path: str
    source_format: str
    trace_id: str = ""


# ---------------------------------------------------------------------------
# PushResult -- output of anki gateway
# ---------------------------------------------------------------------------

class CardPushStatus(BaseModel):
    index: int
    note_id: int | None = None
    success: bool
    error: str = ""


class PushResult(BaseModel):
    total: int
    succeeded: int
    failed: int
    results: list[CardPushStatus] = Field(default_factory=list)
    trace_id: str = ""


# ---------------------------------------------------------------------------
# GenerateRequest -- input for card generator
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    markdown: str
    strategy: str = "basic"  # "basic", "cloze", "image_qa" (兼容 "image_occlusion")
    deck_name: str = "Default"
    tags: list[str] = Field(default_factory=list)
    trace_id: str = ""
    source_path: str = ""  # Original file path, used for image attachment
    target_count: int = 0  # 0 means keep strategy default card count
    enable_auto_split: bool = False  # Experimental: Enable auto-split for long documents
    split_threshold: int = 70000  # Character count threshold for splitting


# ---------------------------------------------------------------------------
# Batch conversion -- output of batch converter
# ---------------------------------------------------------------------------

class ConvertedDocument(BaseModel):
    result: MarkdownResult
    file_name: str


class BatchConvertResult(BaseModel):
    documents: list[ConvertedDocument] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
