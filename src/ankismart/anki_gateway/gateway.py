from __future__ import annotations

from typing import Any, Iterable, Literal

from ankismart.anki_gateway.client import AnkiConnectClient
from ankismart.anki_gateway.styling import MODERN_CARD_CSS
from ankismart.anki_gateway.validator import validate_card_draft
from ankismart.core.errors import AnkiGatewayError
from ankismart.core.logging import get_logger
from ankismart.core.models import CardDraft, CardPushStatus, PushResult
from ankismart.core.tracing import metrics, timed, trace_context

logger = get_logger("anki_gateway")

UpdateMode = Literal["create_only", "update_only", "create_or_update"]

_BASIC_LIKE_MODELS = {
    "Basic",
    "Basic (and reversed card)",
    "Basic (optional reversed card)",
    "Basic (type in the answer)",
}
_STYLEABLE_MODELS = _BASIC_LIKE_MODELS | {"Cloze"}

_ANKI_TEMPLATE_FORMATTER_SCRIPT = """
<script>
(function () {
  function escapeHtml(text) {
    return String(text || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function toText(html) {
    return String(html || "")
      .replace(/<br\\s*\\/?>/gi, "\\n")
      .replace(/<\\/p\\s*>/gi, "\\n")
      .replace(/<[^>]+>/g, " ")
      .replace(/\\u00a0/g, " ")
      .replace(/\\r/g, "")
      .trim();
  }

  function formatWithBreaks(text) {
    return escapeHtml(text).replace(/\\n/g, "<br>");
  }

  function parseFront(raw) {
    var compact = raw.replace(/\\s+/g, " ").trim();
    var re = /(^|\\s)([A-Ea-e])[\\.、\\):：\\-]\\s*/g;
    var hits = [];
    var m;
    while ((m = re.exec(compact)) !== null) {
      hits.push({
        labelStart: m.index + m[1].length,
        valueStart: re.lastIndex,
        key: m[2].toUpperCase()
      });
    }
    if (hits.length < 2) {
      return null;
    }

    var question = compact.slice(0, hits[0].labelStart).trim();
    var options = [];
    for (var i = 0; i < hits.length; i++) {
      var end = i + 1 < hits.length ? hits[i + 1].labelStart : compact.length;
      var value = compact.slice(hits[i].valueStart, end).trim();
      if (value) {
        options.push({ key: hits[i].key, text: value });
      }
    }
    return options.length ? { question: question, options: options } : null;
  }

  function normalizeAnswerKeys(raw) {
    var keys = [];
    String(raw || "").replace(/[A-Ea-e]/g, function (key) {
      key = key.toUpperCase();
      if (keys.indexOf(key) < 0) {
        keys.push(key);
      }
      return key;
    });
    return keys.join("、");
  }

  function parseBack(raw) {
    var text = String(raw || "").trim();
    if (!text) {
      return { answer: "（未标注）", explanation: "" };
    }

    function stripLeadingIndex(line) {
      return String(line || "")
        .replace(/^\\s*\\d+[\\.、\\):：-]\\s*/, "")
        .trim();
    }

    var lines = text.split(/\\n+/).map(function (line) {
      return line.trim();
    }).filter(Boolean);
    var normalizedLines = lines.map(stripLeadingIndex);

    function normalizeExplanation(rawText) {
      var normalized = String(rawText || "");
      var explanationLines = normalized.split(/\\n+/).map(function (line) {
        return stripLeadingIndex(line);
      }).filter(Boolean);

      if (!explanationLines.length) {
        return "";
      }

      var firstLineWithText = explanationLines[0].match(/^(?:解析|explanation)\\s*[:：]\\s*(.+)$/i);
      if (firstLineWithText) {
        explanationLines[0] = firstLineWithText[1].trim();
      }
      while (explanationLines.length && /^(?:解析|explanation)\\s*[:：]?\\s*$/i.test(explanationLines[0])) {
        explanationLines.shift();
      }
      return explanationLines.join("\\n").trim();
    }

    var first = normalizedLines[0] || "";
    var match = first.match(/^(?:答案|正确答案|answer)?\\s*[:：]?\\s*([A-Ea-e](?:\\s*[,，、/]\\s*[A-Ea-e])*)$/i);
    if (match) {
      return {
        answer: normalizeAnswerKeys(match[1]) || "（未标注）",
        explanation: normalizeExplanation(normalizedLines.slice(1).join("\\n"))
      };
    }

    var answerLine = first.match(/^(?:答案|正确答案|answer)\\s*[:：]\\s*(.+)$/i);
    if (answerLine) {
      return {
        answer: answerLine[1].trim() || "（未标注）",
        explanation: normalizeExplanation(normalizedLines.slice(1).join("\\n"))
      };
    }

    var prefixed = first.match(/^([A-Ea-e](?:\\s*[,，、/]\\s*[A-Ea-e])*)(?:[\\.、\\):：\\-]\\s*|\\s+)(.+)$/);
    if (prefixed) {
      return {
        answer: normalizeAnswerKeys(prefixed[1]) || "（未标注）",
        explanation: normalizeExplanation([prefixed[2]].concat(normalizedLines.slice(1)).join("\\n"))
      };
    }

    var inline = text.match(/(?:答案|正确答案|answer)\\s*[:：]?\\s*([A-Ea-e](?:\\s*[,，、/]\\s*[A-Ea-e])*)/i);
    if (inline) {
      return {
        answer: normalizeAnswerKeys(inline[1]) || "（未标注）",
        explanation: normalizeExplanation(text.replace(inline[0], "").trim())
      };
    }

    if (normalizedLines.length >= 2) {
      return {
        answer: normalizedLines[0] || "（未标注）",
        explanation: normalizeExplanation(normalizedLines.slice(1).join("\\n"))
      };
    }

    return { answer: "（未标注）", explanation: normalizeExplanation(normalizedLines.join("\\n")) };
  }

  function splitExplanation(text) {
    if (!text) {
      return [];
    }
    var lines = text.split(/\\n+/).map(function (line) {
      return line.trim();
    }).filter(Boolean);
    if (lines.length >= 2) {
      return lines;
    }

    var sentenceMatches = lines[0].match(/[^。！？!?；;]+[。！？!?；;]?/g) || [lines[0]];
    var sentences = sentenceMatches.map(function (item) {
      return item.trim();
    }).filter(Boolean);
    if (sentences.length <= 1) {
      return lines;
    }

    var sections = [];
    var buffer = "";
    sentences.forEach(function (sentence) {
      if (buffer && (buffer.length + sentence.length) > 56) {
        sections.push(buffer.trim());
        buffer = sentence;
      } else {
        buffer = (buffer + " " + sentence).trim();
      }
    });
    if (buffer) {
      sections.push(buffer.trim());
    }
    return sections;
  }

  function renderExplanation(sections) {
    if (!sections.length) {
      return '<div class="as-explain-item">（无解析）</div>';
    }
    if (sections.length === 1) {
      return '<div class="as-explain-item">' + formatWithBreaks(sections[0]) + "</div>";
    }
    return (
      '<div class="as-explain-stack">' +
      sections.map(function (section) {
        return '<div class="as-explain-item">' + formatWithBreaks(section) + "</div>";
      }).join("") +
      "</div>"
    );
  }

  function formatFrontById(id) {
    var el = document.getElementById(id);
    if (!el) {
      return;
    }
    var parsed = parseFront(toText(el.innerHTML));
    if (!parsed) {
      return;
    }
    var rows = parsed.options.map(function (opt) {
      return (
        '<div class="as-choice-row">' +
        '<span class="as-choice-key">' + escapeHtml(opt.key) + '.</span>' +
        '<span class="as-choice-text">' + formatWithBreaks(opt.text) + "</span>" +
        "</div>"
      );
    }).join("");
    el.innerHTML =
      '<div class="as-question-text">' + formatWithBreaks(parsed.question) + "</div>" +
      '<div class="as-choice-list">' + rows + "</div>";
  }

  function formatBackByIds(answerId, explanationId) {
    var answerEl = document.getElementById(answerId);
    var explanationEl = document.getElementById(explanationId);
    if (!answerEl || !explanationEl) {
      return;
    }
    var parsed = parseBack(toText(answerEl.innerHTML));
    answerEl.innerHTML =
      '<div class="as-answer-line">' +
      '<span class="as-answer-label">答案：</span>' +
      '<span class="as-answer-value">' + formatWithBreaks(parsed.answer) + "</span>" +
      "</div>";
    explanationEl.innerHTML = renderExplanation(splitExplanation(parsed.explanation));
  }

  function formatExplainById(id) {
    var el = document.getElementById(id);
    if (!el) {
      return;
    }
    el.innerHTML = renderExplanation(splitExplanation(toText(el.innerHTML)));
  }

  formatFrontById("as-front-content");
  formatFrontById("as-front-side");
  formatBackByIds("as-back-answer", "as-back-explain");
  formatExplainById("as-cloze-explain");
})();
</script>
""".strip()

_ANKI_BASIC_QFMT = (
    '<div class="as-card as-card-front">'
    '<section class="as-block as-question-block">'
    '<div class="as-block-title">问题</div>'
    '<div id="as-front-content" class="as-block-content">{{Front}}</div>'
    "</section>"
    "</div>"
    + _ANKI_TEMPLATE_FORMATTER_SCRIPT
)

_ANKI_BASIC_AFMT = (
    '<div class="as-card as-card-back">'
    '<section class="as-block as-question-block">'
    '<div class="as-block-title">问题</div>'
    '<div id="as-front-side" class="as-block-content">{{Front}}</div>'
    "</section>"
    '<section class="as-block as-answer-block">'
    '<div class="as-block-title">答案</div>'
    '<div id="as-back-answer" class="as-block-content as-answer-box">{{Back}}</div>'
    "</section>"
    '<section class="as-block as-extra-block">'
    '<div class="as-block-title">解析</div>'
    '<div id="as-back-explain" class="as-block-content as-extra">（无解析）</div>'
    "</section>"
    "</div>"
    + _ANKI_TEMPLATE_FORMATTER_SCRIPT
)

_ANKI_CLOZE_QFMT = (
    '<div class="as-card as-card-front">'
    '<section class="as-block as-question-block">'
    '<div class="as-block-title">问题</div>'
    '<div class="as-block-content">{{cloze:Text}}</div>'
    "</section>"
    "</div>"
)

_ANKI_CLOZE_AFMT = (
    '<div class="as-card as-card-back">'
    '<section class="as-block as-question-block">'
    '<div class="as-block-title">问题</div>'
    '<div class="as-block-content">{{cloze:Text}}</div>'
    "</section>"
    '<section class="as-block as-answer-block">'
    '<div class="as-block-title">答案</div>'
    '<div class="as-answer-line">'
    '<span class="as-answer-label">答案：</span>'
    '<span class="as-answer-value">{{cloze:Text}}</span>'
    "</div>"
    "</section>"
    '<section class="as-block as-extra-block">'
    '<div class="as-block-title">解析</div>'
    '<div id="as-cloze-explain" class="as-block-content as-extra">'
    '{{#Extra}}{{Extra}}{{/Extra}}{{^Extra}}（无解析）{{/Extra}}'
    "</div>"
    "</section>"
    "</div>"
    + _ANKI_TEMPLATE_FORMATTER_SCRIPT
)


def _build_anki_templates_payload(
    note_type: str,
    template_names: Iterable[str],
) -> dict[str, dict[str, str]]:
    names = [name for name in template_names if name]
    if note_type in _BASIC_LIKE_MODELS:
        if not names:
            names = ["Card 1"]
        return {name: {"Front": _ANKI_BASIC_QFMT, "Back": _ANKI_BASIC_AFMT} for name in names}
    if note_type == "Cloze":
        if not names:
            names = ["Cloze"]
        return {name: {"Front": _ANKI_CLOZE_QFMT, "Back": _ANKI_CLOZE_AFMT} for name in names}
    return {}


def _card_to_note_params(card: CardDraft) -> dict[str, Any]:
    """Convert a CardDraft to AnkiConnect note params."""
    params: dict[str, Any] = {
        "deckName": card.deck_name,
        "modelName": card.note_type,
        "fields": card.fields,
        "tags": card.tags,
        "options": {
            "allowDuplicate": card.options.allow_duplicate,
            "duplicateScope": card.options.duplicate_scope,
            "duplicateScopeOptions": {
                "deckName": card.options.duplicate_scope_options.deck_name,
                "checkChildren": card.options.duplicate_scope_options.check_children,
                "checkAllModels": card.options.duplicate_scope_options.check_all_models,
            },
        },
    }

    # Add media if present
    for media_type in ("audio", "video", "picture"):
        items = getattr(card.media, media_type, [])
        if items:
            params[media_type] = [
                {k: v for k, v in item.model_dump().items() if v is not None and v != []}
                for item in items
            ]

    return params


class AnkiGateway:
    def __init__(self, client: AnkiConnectClient) -> None:
        self._client = client

    def check_connection(self) -> bool:
        return self._client.check_connection()

    def get_deck_names(self) -> list[str]:
        return self._client.get_deck_names()

    def get_model_names(self) -> list[str]:
        return self._client.get_model_names()

    def get_model_field_names(self, model_name: str) -> list[str]:
        return self._client.get_model_field_names(model_name)

    # ------------------------------------------------------------------
    # Single-note operations
    # ------------------------------------------------------------------

    def find_notes(self, query: str) -> list[int]:
        """Find note IDs matching an Anki search query."""
        return self._client.find_notes(query)

    def update_note(self, note_id: int, fields: dict[str, str]) -> None:
        """Update fields of an existing note by ID."""
        self._client.update_note_fields(note_id, fields)
        logger.info("Note updated", extra={"note_id": note_id})

    def create_or_update_note(self, card: CardDraft) -> CardPushStatus:
        """Create a note or update it if a duplicate front field exists."""
        deck_cache = self._fetch_deck_cache()
        self._ensure_deck_exists(card.deck_name, deck_cache)
        self._sync_model_styling([card])
        validate_card_draft(card, self._client)
        existing_id = self._find_existing_note(card)
        if existing_id is not None:
            self._client.update_note_fields(existing_id, card.fields)
            logger.info("Updated existing note", extra={"note_id": existing_id})
            return CardPushStatus(index=0, note_id=existing_id, success=True)
        note_params = _card_to_note_params(card)
        note_id = self._client.add_note(note_params)
        return CardPushStatus(index=0, note_id=note_id, success=True)

    # ------------------------------------------------------------------
    # Batch push with update_mode
    # ------------------------------------------------------------------

    def push(
        self,
        cards: list[CardDraft],
        update_mode: UpdateMode = "create_only",
    ) -> PushResult:
        metrics.increment("anki_push_batches_total")
        metrics.increment("anki_push_cards_total", value=len(cards))
        initial_trace_id = cards[0].trace_id if cards else None
        with trace_context(initial_trace_id) as trace_id:
            with timed("anki_push_total"):
                results: list[CardPushStatus] = []
                succeeded = 0
                failed = 0
                deck_cache = self._fetch_deck_cache()
                self._sync_model_styling(cards)

                for i, card in enumerate(cards):
                    try:
                        self._ensure_deck_exists(card.deck_name, deck_cache)
                        validate_card_draft(card, self._client)
                        status = self._push_single(i, card, update_mode, trace_id)
                        results.append(status)
                        if status.success:
                            succeeded += 1
                            metrics.increment("anki_push_succeeded_total")
                        else:
                            failed += 1
                            metrics.increment("anki_push_failed_total")
                    except AnkiGatewayError as exc:
                        logger.warning(
                            "Card push failed",
                            extra={"index": i, "error": exc.message, "trace_id": trace_id},
                        )
                        results.append(CardPushStatus(index=i, success=False, error=exc.message))
                        failed += 1
                        metrics.increment("anki_push_failed_total")

                total_processed = succeeded + failed
                success_ratio = (succeeded / total_processed) if total_processed else 0.0
                metrics.set_gauge("anki_push_success_ratio", success_ratio)

                logger.info(
                    "Push completed",
                    extra={
                        "trace_id": trace_id,
                        "update_mode": update_mode,
                        "total": len(cards),
                        "succeeded": succeeded,
                        "failed": failed,
                    },
                )

                return PushResult(
                    total=len(cards),
                    succeeded=succeeded,
                    failed=failed,
                    results=results,
                    trace_id=trace_id,
                )

    def push_or_update(self, cards: list[CardDraft]) -> PushResult:
        """Backward-compatible alias for ``push(cards, update_mode="create_or_update")``."""
        return self.push(cards, update_mode="create_or_update")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _push_single(
        self,
        index: int,
        card: CardDraft,
        update_mode: UpdateMode,
        trace_id: str,
    ) -> CardPushStatus:
        """Process a single card according to *update_mode*."""
        existing_id = (
            self._find_existing_note(card)
            if update_mode != "create_only"
            else None
        )

        if update_mode == "create_only":
            note_params = _card_to_note_params(card)
            note_id = self._client.add_note(note_params)
            return CardPushStatus(index=index, note_id=note_id, success=True)

        if update_mode == "update_only":
            if existing_id is None:
                msg = "No existing note found to update"
                logger.warning(msg, extra={"index": index, "trace_id": trace_id})
                return CardPushStatus(index=index, success=False, error=msg)
            self._client.update_note_fields(existing_id, card.fields)
            logger.info("Updated existing note", extra={"index": index, "note_id": existing_id, "trace_id": trace_id})
            return CardPushStatus(index=index, note_id=existing_id, success=True)

        # create_or_update
        if existing_id is not None:
            self._client.update_note_fields(existing_id, card.fields)
            logger.info("Updated existing note", extra={"index": index, "note_id": existing_id, "trace_id": trace_id})
            return CardPushStatus(index=index, note_id=existing_id, success=True)
        note_params = _card_to_note_params(card)
        note_id = self._client.add_note(note_params)
        return CardPushStatus(index=index, note_id=note_id, success=True)

    def _find_existing_note(self, card: CardDraft) -> int | None:
        """Search for an existing note matching the card's front field in the same deck."""
        front = card.fields.get("Front") or card.fields.get("Text")
        if not front:
            return None
        escaped = front.replace('"', '\\"')
        field_name = "Front" if "Front" in card.fields else "Text"
        model_name = card.note_type.replace('"', '\\"')
        query = f'note:"{model_name}" deck:"{card.deck_name}" "{field_name}:{escaped}"'
        try:
            note_ids = self._client.find_notes(query)
            return note_ids[0] if note_ids else None
        except AnkiGatewayError:
            return None

    def _fetch_deck_cache(self) -> set[str]:
        """Fetch existing deck names, falling back to an empty cache on gateway errors."""
        try:
            return set(self._client.get_deck_names())
        except AnkiGatewayError as exc:
            logger.warning("Failed to query deck names before push", extra={"error": exc.message})
            return set()

    def _ensure_deck_exists(self, deck_name: str, cache: set[str]) -> None:
        """Ensure a target deck exists before card validation/push."""
        name = (deck_name or "").strip()
        if not name or name in cache:
            return

        self._client.create_deck(name)
        cache.add(name)
        logger.info("Deck created automatically", extra={"deck_name": name})

    def _sync_model_styling(self, cards: list[CardDraft]) -> None:
        """Best-effort sync of Anki note templates/CSS to Ankismart style."""
        if not cards:
            return
        model_names = {
            (card.note_type or "").strip()
            for card in cards
            if (card.note_type or "").strip() in _STYLEABLE_MODELS
        }
        for model_name in model_names:
            try:
                raw_templates = self._client.get_model_templates(model_name)
                template_names = (
                    list(raw_templates.keys())
                    if isinstance(raw_templates, dict)
                    else []
                )
                payload = _build_anki_templates_payload(model_name, template_names)
                if not payload:
                    continue
                self._client.update_model_templates(model_name, payload)
                self._client.update_model_styling(model_name, MODERN_CARD_CSS)
                logger.info(
                    "Synchronized Anki model style",
                    extra={
                        "model_name": model_name,
                        "template_count": len(payload),
                    },
                )
            except AnkiGatewayError as exc:
                logger.warning(
                    "Failed to sync model style, continue pushing",
                    extra={"model_name": model_name, "error": exc.message},
                )
