from __future__ import annotations

import base64
import ipaddress
import random
import socket
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urljoin, urlparse

import genanki
import httpx

from ankismart.core.errors import AnkiGatewayError, ErrorCode
from ankismart.core.logging import get_logger
from ankismart.core.models import CardDraft, MediaItem
from ankismart.core.tracing import get_trace_id, timed

from .styling import MODERN_CARD_CSS

logger = get_logger("anki_gateway.apkg_exporter")

ANKISMART_BASIC_MODEL = "AnkiSmart Basic"
ANKISMART_CLOZE_MODEL = "AnkiSmart Cloze"

_CHOICE_FORMATTER_SCRIPT = """
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
    var raw = String(text || "");
    if (!raw) {
      return "";
    }

    var mathRe = new RegExp(
      "(\\\\$\\\\$[\\\\s\\\\S]*?\\\\$\\\\$|\\\\\\\\\\\\[[\\\\s\\\\S]*?\\\\\\\\\\\\]|" +
      "\\\\\\\\\\([\\\\s\\\\S]*?\\\\\\\\\\\\)|\\\\\\\\begin\\\\{[a-zA-Z*]+\\\\}[\\\\s\\\\S]*?" +
      "\\\\\\\\end\\\\{[a-zA-Z*]+\\\\}|\\\\$[^$\\\\n]+\\\\$)",
      "g"
    );
    var output = "";
    var lastIndex = 0;
    var match;
    while ((match = mathRe.exec(raw)) !== null) {
      output += escapeHtml(raw.slice(lastIndex, match.index)).replace(/\\n/g, "<br>");
      output += escapeHtml(match[0]);
      lastIndex = mathRe.lastIndex;
    }
    output += escapeHtml(raw.slice(lastIndex)).replace(/\\n/g, "<br>");
    return output;
  }

  function containsLatex(text) {
    var latexRe = new RegExp(
      "(\\\\$\\\\$[\\\\s\\\\S]*?\\\\$\\\\$|\\\\\\\\\\\\[[\\\\s\\\\S]*?\\\\\\\\\\\\]|" +
      "\\\\\\\\\\([\\\\s\\\\S]*?\\\\\\\\\\\\)|\\\\\\\\begin\\\\{[a-zA-Z*]+\\\\}|" +
      "\\\\\\\\[a-zA-Z]{2,})"
    );
    return latexRe.test(String(text || ""));
  }

  function parseFront(raw) {
    if (containsLatex(raw)) {
      return null;
    }
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

    var labeled = text.match(
      /^(?:答案|正确答案|answer)\\s*[:：]\\s*([\\s\\S]+?)\\n(?:解析|explanation)\\s*[:：]\\s*([\\s\\S]+)$/i
    );
    if (labeled) {
      return {
        answer: labeled[1].trim() || "（未标注）",
        explanation: labeled[2].trim()
      };
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
      var explanationLines = String(rawText || "").split(/\\n+/).map(function (line) {
        return stripLeadingIndex(line);
      }).filter(Boolean);

      if (!explanationLines.length) {
        return "";
      }

      var markerWithText = explanationLines[0].match(/^(?:解析|explanation)\\s*[:：]\\s*(.+)$/i);
      if (markerWithText) {
        explanationLines[0] = markerWithText[1].trim();
      }
      while (
        explanationLines.length &&
        /^(?:解析|explanation)\\s*[:：]?\\s*$/i.test(explanationLines[0])
      ) {
        explanationLines.shift();
      }
      return explanationLines.join("\\n").trim();
    }

    var first = normalizedLines[0] || "";
    var match = first.match(
      /^(?:答案|正确答案|answer)?\\s*[:：]?\\s*([A-Ea-e](?:\\s*[,，、/]\\s*[A-Ea-e])*)$/i
    );
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

    var prefixed = first.match(
      /^([A-Ea-e](?:\\s*[,，、/]\\s*[A-Ea-e])*)(?:[\\.、\\):：\\-]\\s*|\\s+)(.+)$/
    );
    if (prefixed) {
      return {
        answer: normalizeAnswerKeys(prefixed[1]) || "（未标注）",
        explanation: normalizeExplanation(
          [prefixed[2]].concat(normalizedLines.slice(1)).join("\\n")
        )
      };
    }

    var inline = text.match(
      /(?:答案|正确答案|answer)\\s*[:：]?\\s*([A-Ea-e](?:\\s*[,，、/]\\s*[A-Ea-e])*)/i
    );
    if (inline) {
      return {
        answer: normalizeAnswerKeys(inline[1]) || "（未标注）",
        explanation: normalizeExplanation(text.replace(inline[0], "").trim())
      };
    }

    return { answer: text, explanation: "" };
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
          '<span class="as-choice-text">' + formatWithBreaks(opt.text) + '</span>' +
        '</div>'
      );
    }).join("");
    el.innerHTML =
      '<div class="as-question-text">' + formatWithBreaks(parsed.question) + '</div>' +
      '<div class="as-choice-list">' + rows + "</div>";
  }

  function formatBackByIds(answerId, explanationId) {
    var answerEl = document.getElementById(answerId);
    var explanationEl = document.getElementById(explanationId);
    if (!answerEl || !explanationEl) {
      return;
    }
    var parsed = parseBack(toText(answerEl.innerHTML));
    var sections = splitExplanation(parsed.explanation);
    var explanationHtml = '<div class="as-explain-item">（无解析）</div>';
    if (sections.length === 1) {
      explanationHtml = '<div class="as-explain-item">' + formatWithBreaks(sections[0]) + "</div>";
    } else if (sections.length > 1) {
      explanationHtml =
        '<div class="as-explain-stack">' +
          sections.map(function (section) {
            return '<div class="as-explain-item">' + formatWithBreaks(section) + "</div>";
          }).join("") +
        "</div>";
    }

    answerEl.innerHTML =
      '<div class="as-answer-line">' +
        '<span class="as-answer-label">答案：</span>' +
        '<span class="as-answer-value">' + formatWithBreaks(parsed.answer) + "</span>" +
      "</div>";
    explanationEl.innerHTML = explanationHtml;
  }

  formatFrontById("as-front-content");
  formatFrontById("as-front-side");
  formatBackByIds("as-back-answer", "as-back-explain");
})();
</script>
""".strip()

# Pre-defined genanki models for standard note types
_BASIC_MODEL = genanki.Model(
    1607392319,  # Fixed ID for consistency
    ANKISMART_BASIC_MODEL,
    fields=[{"name": "Front"}, {"name": "Back"}],
    templates=[
        {
            "name": "Card 1",
            "qfmt": (
                '<div class="as-card as-card-front">'
                '<section class="as-block as-question-block">'
                '<div class="as-block-title">问题</div>'
                '<div id="as-front-content" class="as-block-content">{{Front}}</div>'
                "</section>"
                "</div>" + _CHOICE_FORMATTER_SCRIPT
            ),
            "afmt": (
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
                "</div>" + _CHOICE_FORMATTER_SCRIPT
            ),
        },
    ],
    css=MODERN_CARD_CSS,
)

_CLOZE_MODEL = genanki.Model(
    1607392320,
    ANKISMART_CLOZE_MODEL,
    fields=[{"name": "Text"}, {"name": "Extra"}],
    templates=[
        {
            "name": "Cloze",
            "qfmt": (
                '<div class="as-card as-card-front">'
                '<section class="as-block as-question-block">'
                '<div class="as-block-title">问题</div>'
                '<div class="as-block-content">{{cloze:Text}}</div>'
                "</section>"
                "</div>"
            ),
            "afmt": (
                '<div class="as-card as-card-back">'
                '<section class="as-block as-question-block">'
                '<div class="as-block-title">问题</div>'
                '<div class="as-block-content">{{cloze:Text}}</div>'
                "</section>"
                '<section class="as-block as-answer-block">'
                '<div class="as-block-title">答案</div>'
                '<div class="as-block-content as-answer-box">{{cloze:Text}}</div>'
                "</section>"
                '<section class="as-block as-extra-block">'
                '<div class="as-block-title">解析</div>'
                '{{#Extra}}<div class="as-block-content as-extra">{{Extra}}</div>{{/Extra}}'
                '{{^Extra}}<div class="as-block-content as-extra">（无解析）</div>{{/Extra}}'
                "</section>"
                "</div>"
            ),
        },
    ],
    model_type=genanki.Model.CLOZE,
    css=MODERN_CARD_CSS,
)

_MODEL_MAP: dict[str, genanki.Model] = {
    ANKISMART_BASIC_MODEL: _BASIC_MODEL,
    ANKISMART_CLOZE_MODEL: _CLOZE_MODEL,
    "Basic": _BASIC_MODEL,
    "Basic (and reversed card)": _BASIC_MODEL,
    "Basic (optional reversed card)": _BASIC_MODEL,
    "Basic (type in the answer)": _BASIC_MODEL,
    "Cloze": _CLOZE_MODEL,
}

_MEDIA_MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024
_MEDIA_MAX_REDIRECTS = 3


def _get_model(note_type: str) -> genanki.Model:
    model = _MODEL_MAP.get(note_type)
    if model is None:
        raise AnkiGatewayError(
            f"No APKG model template for note type: {note_type}",
            code=ErrorCode.E_MODEL_NOT_FOUND,
        )
    return model


def _next_available_path(path: Path) -> Path:
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent

    index = 1
    while True:
        candidate = parent / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def _is_disallowed_remote_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _validate_media_url(url: str) -> str:
    parsed = urlparse(str(url).strip())
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").strip().lower()
    if scheme not in {"http", "https"}:
        raise ValueError("unsupported media URL scheme")
    if not host:
        raise ValueError("invalid media URL host")
    if parsed.username or parsed.password:
        raise ValueError("media URL credentials are not allowed")

    try:
        ip_obj = ipaddress.ip_address(host)
        ip_list = [ip_obj]
    except ValueError:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        ip_list = []
        for info in infos:
            address = info[4][0]
            try:
                ip_list.append(ipaddress.ip_address(address))
            except ValueError:
                continue
        if not ip_list:
            raise ValueError("media URL host resolve returned no IP")

    for ip_obj in ip_list:
        if _is_disallowed_remote_ip(ip_obj):
            raise ValueError("media URL points to disallowed network")
    return parsed.geturl()


def _download_media_to_path(url: str, out_path: Path) -> Path:
    current_url = _validate_media_url(url)
    with httpx.Client(timeout=10, follow_redirects=False) as client:
        for _ in range(_MEDIA_MAX_REDIRECTS + 1):
            with client.stream("GET", current_url, follow_redirects=False) as response:
                if 300 <= response.status_code < 400:
                    redirect_target = response.headers.get("location", "").strip()
                    if not redirect_target:
                        raise ValueError("redirect response without location")
                    current_url = _validate_media_url(urljoin(current_url, redirect_target))
                    continue

                response.raise_for_status()

                content_length = response.headers.get("content-length")
                if content_length:
                    try:
                        if int(content_length) > _MEDIA_MAX_DOWNLOAD_BYTES:
                            raise ValueError("media file exceeds maximum allowed size")
                    except ValueError as exc:
                        if "maximum allowed size" in str(exc):
                            raise

                total = 0
                with out_path.open("wb") as fp:
                    for chunk in response.iter_bytes():
                        if not chunk:
                            continue
                        total += len(chunk)
                        if total > _MEDIA_MAX_DOWNLOAD_BYTES:
                            raise ValueError("media file exceeds maximum allowed size")
                        fp.write(chunk)
                return out_path

    raise ValueError("too many redirects for media URL")


def _materialize_media_file(media: MediaItem, temp_dir: Path) -> Path | None:
    media_path_value = getattr(media, "path", None)
    media_filename = getattr(media, "filename", "")
    media_data = getattr(media, "data", None)
    media_url = getattr(media, "url", None)

    if media_path_value:
        media_path = Path(media_path_value)
        if media_path.exists():
            return media_path
        logger.warning(
            "Media path does not exist, skipping",
            extra={"media_path": str(media_path), "media_filename": media_filename},
        )

    filename = Path(media_filename).name if media_filename else "media.bin"
    if not filename:
        filename = "media.bin"
    out_path = _next_available_path(temp_dir / filename)

    if media_data:
        try:
            raw = base64.b64decode(media_data, validate=True)
            out_path.write_bytes(raw)
            return out_path
        except (ValueError, OSError) as e:
            logger.warning(
                f"Invalid media data, skipping: {e}",
                extra={"media_filename": media_filename},
            )

    if media_url:
        try:
            return _download_media_to_path(media_url, out_path)
        except (ValueError, httpx.HTTPError, OSError) as e:
            logger.warning(
                f"Failed to download media url, skipping: {e}",
                extra={"media_url": media_url, "media_filename": media_filename},
            )

    return None


class ApkgExporter:
    def export(self, cards: list[CardDraft], output_path: Path) -> Path:
        trace_id = get_trace_id()
        if not cards:
            raise AnkiGatewayError(
                "No cards to export",
                code=ErrorCode.E_ANKICONNECT_ERROR,
                trace_id=trace_id,
            )

        with timed("apkg_export"):
            with TemporaryDirectory(prefix="ankismart-media-") as temp_dir:
                temp_dir_path = Path(temp_dir)

                # Group cards by deck
                decks_map: dict[str, genanki.Deck] = {}
                media_files: set[str] = set()
                for card in cards:
                    if card.deck_name not in decks_map:
                        deck_id = random.randrange(1 << 30, 1 << 31)
                        decks_map[card.deck_name] = genanki.Deck(deck_id, card.deck_name)

                    deck = decks_map[card.deck_name]
                    model = _get_model(card.note_type)

                    # Build field values in model field order
                    field_values = [card.fields.get(f["name"], "") for f in model.fields]

                    note = genanki.Note(
                        model=model,
                        fields=field_values,
                        tags=card.tags,
                    )
                    deck.add_note(note)

                    for media_items in (
                        card.media.picture,
                        card.media.audio,
                        card.media.video,
                    ):
                        for media in media_items:
                            media_path = _materialize_media_file(media, temp_dir_path)
                            if media_path is not None:
                                media_files.add(str(media_path))

                # Write to .apkg
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)

                package = genanki.Package(list(decks_map.values()))
                package.media_files = sorted(media_files)
                package.write_to_file(str(output_path))

            logger.info(
                "APKG exported",
                extra={
                    "trace_id": trace_id,
                    "card_count": len(cards),
                    "deck_count": len(decks_map),
                    "path": str(output_path),
                },
            )
            return output_path
