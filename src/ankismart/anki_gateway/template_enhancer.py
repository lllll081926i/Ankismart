from __future__ import annotations

# Post-processes the existing template output to add:
# 1) robust Answer/Explanation parsing (case-insensitive, same-line or multiline)
# 2) lightweight code highlighting for inline and fenced code blocks
TEMPLATE_ENHANCER_SCRIPT = r"""
<script>
(function () {
  var UNLABELED_ANSWER = "\uFF08\u672A\u6807\u6CE8\uFF09";
  var NO_EXPLANATION = "\uFF08\u65E0\u89E3\u6790\uFF09";
  var ANSWER_LABEL = "\u7B54\u6848\uFF1A";

  function escapeHtml(text) {
    return String(text || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function extractText(html) {
    return String(html || "")
      .replace(/<br\s*\/?>/gi, "\n")
      .replace(/<\/p\s*>/gi, "\n")
      .replace(/<[^>]+>/g, " ")
      .replace(/\u00a0/g, " ")
      .replace(/\r/g, "")
      .trim();
  }

  function escapeRegExp(text) {
    return String(text || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function containsLatex(text) {
    var latexRe = /(\$\$[\s\S]*?\$\$|\\\\\[[\s\S]*?\\\\\]|\\\\\([\s\S]*?\\\\\)|\\begin\{[a-zA-Z*]+\}[\s\S]*?\\end\{[a-zA-Z*]+\}|\$[^$\n]+\$)/;
    return latexRe.test(String(text || ""));
  }

  function detectCodeLanguage(hint, codeText) {
    var h = String(hint || "").toLowerCase();
    if (/cpp|c\+\+|cc|cxx/.test(h)) return "cpp";
    if (/python|py\b/.test(h)) return "python";
    if (/javascript|typescript|js\b|ts\b/.test(h)) return "javascript";
    if (/java\b/.test(h)) return "java";
    if (/rust|rs\b/.test(h)) return "rust";

    var s = String(codeText || "");
    if (/(#include\s*<|std::|->|\bnullptr\b)/.test(s)) return "cpp";
    if (/\bdef\s+\w+\s*\(|\bimport\s+\w+|\bself\b/.test(s)) return "python";
    if (/\b(function|const|let|var)\b|=>/.test(s)) return "javascript";
    if (/\bpublic\s+class\b|System\.out\./.test(s)) return "java";
    if (/\bfn\s+\w+\s*\(|\blet\s+mut\b|println!/.test(s)) return "rust";

    return "plain";
  }

  function highlightCodeText(code, language) {
    var source = String(code || "");
    var tokens = [];

    function stash(pattern, cssClass) {
      source = source.replace(pattern, function (matched) {
        var key = "@@AS_HL_" + tokens.length + "@@";
        tokens.push({
          key: key,
          html: '<span class="as-code-' + cssClass + '">' + escapeHtml(matched) + "</span>",
        });
        return key;
      });
    }

    stash(/\/\*[\s\S]*?\*\//g, "comment");
    stash(/\/\/[^\n]*/g, "comment");
    stash(/#[^\n]*/g, "comment");
    stash(/\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`/g, "string");

    var escaped = escapeHtml(source);
    var lang = detectCodeLanguage(language, code);
    if (lang !== "plain") {
      var keywords = [
        "and", "as", "auto", "await", "bool", "break", "case", "catch", "class", "const",
        "constexpr", "continue", "crate", "def", "default", "delete", "do", "else", "enum",
        "export", "extern", "false", "final", "fn", "for", "function", "if", "impl", "import",
        "in", "inline", "interface", "let", "match", "module", "mut", "namespace", "new", "null",
        "nullptr", "override", "package", "private", "protected", "public", "pub", "raise", "return",
        "self", "static", "struct", "super", "switch", "template", "this", "throw", "trait", "true",
        "try", "type", "typedef", "typename", "union", "use", "using", "var", "virtual", "void",
        "while"
      ];
      var keywordRe = new RegExp("\\b(" + keywords.join("|") + ")\\b", "g");
      escaped = escaped.replace(keywordRe, '<span class="as-code-kw">$1</span>');
    }

    escaped = escaped.replace(/\b(\d+(?:\.\d+)?)\b/g, '<span class="as-code-num">$1</span>');

    tokens.forEach(function (token) {
      var tokenRe = new RegExp(escapeRegExp(token.key), "g");
      escaped = escaped.replace(tokenRe, token.html);
    });

    return escaped;
  }

  function renderInlineCodeAndBreaks(text) {
    var raw = String(text || "");
    if (!raw) {
      return "";
    }

    var inlineCodeRe = /`([^`\n]+)`/g;
    var out = "";
    var last = 0;
    var m;

    while ((m = inlineCodeRe.exec(raw)) !== null) {
      out += escapeHtml(raw.slice(last, m.index)).replace(/\n/g, "<br>");
      var lang = detectCodeLanguage("", m[1]);
      out +=
        '<code class="as-code as-inline-code as-lang-' +
        escapeHtml(lang) +
        '" data-lang="' +
        escapeHtml(lang) +
        '" data-as-highlighted="1">' +
        highlightCodeText(m[1], lang) +
        "</code>";
      last = inlineCodeRe.lastIndex;
    }

    out += escapeHtml(raw.slice(last)).replace(/\n/g, "<br>");
    return out;
  }

  function renderRichText(text) {
    var raw = String(text || "");
    if (!raw) {
      return "";
    }

    var fenceRe = /```([a-zA-Z0-9_+\-]*)\n([\s\S]*?)```/g;
    var out = "";
    var last = 0;
    var m;

    while ((m = fenceRe.exec(raw)) !== null) {
      out += renderInlineCodeAndBreaks(raw.slice(last, m.index));
      var lang = detectCodeLanguage(m[1], m[2]);
      out +=
        '<pre class="as-code-block"><code class="as-code as-lang-' +
        escapeHtml(lang) +
        '" data-lang="' +
        escapeHtml(lang) +
        '" data-as-highlighted="1">' +
        highlightCodeText(m[2], lang) +
        "</code></pre>";
      last = fenceRe.lastIndex;
    }

    out += renderInlineCodeAndBreaks(raw.slice(last));
    return out;
  }

  function parseAnswerExplanation(rawText) {
    var text = String(rawText || "").trim();
    if (!text) {
      return { answer: UNLABELED_ANSWER, explanation: "" };
    }

    var markers = [];
    var markerRe = /(\u7B54\u6848|\u6B63\u786E\u7B54\u6848|\u89E3\u6790|answer|ans|explanation|explain)\s*[:\uFF1A]/gi;
    var marker;
    while ((marker = markerRe.exec(text)) !== null) {
      var label = String(marker[1] || "").toLowerCase();
      var isAnswer =
        label === "answer" ||
        label === "ans" ||
        label === "\u7b54\u6848" ||
        label === "\u6b63\u786e\u7b54\u6848";
      markers.push({
        type: isAnswer ? "answer" : "explanation",
        start: marker.index,
        valueStart: markerRe.lastIndex,
      });
    }

    if (!markers.length) {
      return { answer: text, explanation: "" };
    }

    var answerParts = [];
    var explainParts = [];

    var prefix = text.slice(0, markers[0].start).trim();
    if (prefix) {
      answerParts.push(prefix);
    }

    for (var i = 0; i < markers.length; i++) {
      var end = i + 1 < markers.length ? markers[i + 1].start : text.length;
      var seg = text.slice(markers[i].valueStart, end).trim();
      if (!seg) {
        continue;
      }
      if (markers[i].type === "answer") {
        answerParts.push(seg);
      } else {
        explainParts.push(seg);
      }
    }

    var answer = answerParts.join("\n").trim();
    var explanation = explainParts.join("\n").trim();
    if (!answer) {
      answer = UNLABELED_ANSWER;
    }

    return { answer: answer, explanation: explanation };
  }

  function looksLikeEmptyExplanation(text) {
    var t = String(text || "").trim();
    if (!t) {
      return true;
    }
    return /^(?:\uFF08?\s*\u65E0\u89E3\u6790\s*\uFF09?|no\s+explanation)$/i.test(t);
  }

  function isRichHtmlNode(node) {
    var html = String((node && node.innerHTML) || "");
    var withoutBreak = html.replace(/<br\s*\/?>/gi, "").trim();
    return /<(?:img|audio|video|svg|math|table|thead|tbody|tr|td|th|ul|ol|li|blockquote)\b/i.test(withoutBreak);
  }

  function enhanceBackBlock() {
    var answerBlock = document.getElementById("as-back-answer");
    var explainBlock = document.getElementById("as-back-explain");
    if (!answerBlock || !explainBlock) {
      return;
    }

    var answerValue = answerBlock.querySelector(".as-answer-value");
    var answerText = answerValue ? extractText(answerValue.innerHTML) : extractText(answerBlock.innerHTML);
    var explainText = extractText(explainBlock.innerHTML);

    var parsed = parseAnswerExplanation(answerText);
    if (!parsed.explanation && !looksLikeEmptyExplanation(explainText)) {
      parsed.explanation = explainText;
    }

    answerBlock.innerHTML =
      '<div class="as-answer-line">' +
      '<span class="as-answer-label">' + ANSWER_LABEL + "</span>" +
      '<span class="as-answer-value">' + renderRichText(parsed.answer) + "</span>" +
      "</div>";

    explainBlock.innerHTML =
      '<div class="as-explain-item">' +
      (parsed.explanation ? renderRichText(parsed.explanation) : NO_EXPLANATION) +
      "</div>";

    answerBlock.setAttribute("data-as-enhanced", "1");
    explainBlock.setAttribute("data-as-enhanced", "1");
  }

  function enhanceTextNodes() {
    var selectors = [
      "#as-front-content",
      "#as-front-side",
      ".as-question-text",
      ".as-choice-text",
      "#as-cloze-explain"
    ];

    var nodes = document.querySelectorAll(selectors.join(","));
    for (var i = 0; i < nodes.length; i++) {
      var node = nodes[i];
      if (!node) {
        continue;
      }
      if (node.getAttribute("data-as-enhanced") === "1") {
        continue;
      }
      if (node.closest('[data-as-enhanced="1"]')) {
        continue;
      }
      if (isRichHtmlNode(node)) {
        continue;
      }

      var text = extractText(node.innerHTML);
      if (!text || containsLatex(text)) {
        continue;
      }

      node.innerHTML = renderRichText(text);
      node.setAttribute("data-as-enhanced", "1");
    }
  }

  enhanceBackBlock();
  enhanceTextNodes();
})();
</script>
""".strip()
