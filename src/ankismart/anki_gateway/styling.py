"""
Modern card styling for Anki cards.

This stylesheet is embedded into generated APKG models and is also reused by
in-app preview pages to keep visual language consistent.
"""

MODERN_CARD_CSS = """
/* ===== Theme Tokens ===== */
.card {
    --as-bg: #f3f7fc;
    --as-bg-grad-a: #d9e9ff;
    --as-bg-grad-b: #dff7ec;
    --as-surface: #ffffff;
    --as-text: #0f1c2e;
    --as-text-soft: #4b5a72;
    --as-border: #d8e2f0;
    --as-shadow: 0 10px 24px rgba(16, 39, 72, 0.12);
    --as-radius-lg: 16px;
    --as-radius-md: 12px;
    --as-primary: #1f6fd6;
    --as-primary-soft: #edf5ff;
    --as-success: #16824f;
    --as-success-soft: #e8f7ee;
    --as-warn: #ad5b08;
    --as-warn-soft: #fff3e5;

    font-family: "Noto Sans SC", "PingFang SC", "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 15px;
    line-height: 1.7;
    color: var(--as-text);
    background:
        radial-gradient(
            900px 540px at -10% -10%,
            var(--as-bg-grad-a) 0%,
            rgba(217, 233, 255, 0) 60%
        ),
        radial-gradient(
            760px 420px at 110% 15%,
            var(--as-bg-grad-b) 0%,
            rgba(223, 247, 236, 0) 60%
        ),
        var(--as-bg);
    margin: 0;
    padding: 16px;
    text-align: left;
}

.card.nightMode,
.nightMode .card {
    --as-bg: #202020;
    --as-bg-grad-a: #2a2a2a;
    --as-bg-grad-b: #323232;
    --as-surface: #2b2b2b;
    --as-text: #e6e6e6;
    --as-text-soft: #a8a8a8;
    --as-border: #464646;
    --as-shadow: 0 10px 24px rgba(0, 0, 0, 0.35);
    --as-primary: #cccccc;
    --as-primary-soft: rgba(255, 255, 255, 0.08);
    --as-success: #cfcfcf;
    --as-success-soft: rgba(255, 255, 255, 0.08);
    --as-warn: #c8c8c8;
    --as-warn-soft: rgba(255, 255, 255, 0.08);
}

/* ===== Layout Containers ===== */
.as-wrap {
    max-width: 940px;
    margin: 0 auto;
    border: 1px solid var(--as-border);
    border-radius: var(--as-radius-lg);
    background: var(--as-surface);
    box-shadow: var(--as-shadow);
    overflow: hidden;
}

.as-head {
    padding: 12px 16px;
    border-bottom: 1px solid var(--as-border);
    background: #f8fbff;
}

.card.nightMode .as-head,
.nightMode .as-head {
    background: rgba(52, 52, 52, 0.92);
}

.as-chip {
    display: inline-block;
    border-radius: 999px;
    border: 1px solid #bdd1eb;
    background: #edf5ff;
    color: #265083;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.25px;
    padding: 3px 11px;
}

.card.nightMode .as-chip,
.nightMode .as-chip {
    border-color: #5a5a5a;
    background: rgba(70, 70, 70, 0.55);
    color: #e2e2e2;
}

.as-section {
    padding: 12px 16px;
}

.as-section + .as-section {
    padding-top: 6px;
}

.as-label {
    display: inline-block;
    margin: 0 0 7px;
    padding: 2px 10px;
    border-radius: 999px;
    border: 1px solid var(--as-border);
    background: #f5f9ff;
    color: var(--as-text-soft);
    text-transform: uppercase;
    letter-spacing: 0.35px;
    font-size: 9px;
    font-weight: 700;
}

.as-box {
    border: 1px solid var(--as-border);
    background: #fbfdff;
    border-radius: var(--as-radius-md);
    padding: 10px 12px;
    color: var(--as-text);
}

.card.nightMode .as-box,
.nightMode .as-box {
    background: rgba(56, 56, 56, 0.9);
}

.as-answer-box {
    border-color: #b7e1c7;
    background: #f3fcf6;
}

.card.nightMode .as-answer-box,
.nightMode .as-answer-box {
    border-color: #4d4d4d;
    background: rgba(58, 58, 58, 0.9);
}

.as-extra {
    border-color: var(--as-border);
    background: #f9fbff;
    color: var(--as-text-soft);
}

.card.nightMode .as-extra,
.nightMode .as-extra {
    background: rgba(54, 54, 54, 0.9);
}

.as-card {
    max-width: 940px;
    margin: 0 auto;
}

.as-block {
    border: 1px solid var(--as-border);
    border-radius: var(--as-radius-md);
    background: var(--as-surface);
    box-shadow: var(--as-shadow);
    padding: 12px 14px;
}

.as-block + .as-block {
    margin-top: 12px;
}

.as-block-title {
    margin: 0 0 8px;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.2px;
    color: var(--as-text-soft);
}

.as-block-content {
    font-size: 16px;
    line-height: 1.8;
}

.as-choice-list {
    margin-top: 10px;
}

.as-choice-row {
    display: flex;
    gap: 8px;
    margin-top: 6px;
}

.as-choice-key {
    min-width: 24px;
    font-weight: 700;
}

.as-choice-text {
    flex: 1;
}

.as-answer-line {
    font-size: 16px;
    line-height: 1.8;
}

.as-answer-label {
    font-weight: 700;
}

.as-explain-wrap {
    margin-top: 10px;
    border-top: 1px dashed var(--as-border);
    padding-top: 10px;
}

.as-explain-title {
    margin: 0 0 6px;
    font-size: 12px;
    font-weight: 700;
    color: var(--as-text-soft);
}

.as-explain-list {
    margin: 0;
    padding-left: 0;
    list-style: none;
}

.as-explain-stack {
    display: grid;
    gap: 8px;
}

.as-explain-item {
    margin: 0;
    line-height: 1.75;
}

/* ===== Typography ===== */
h1, h2, h3, h4, h5, h6 {
    margin-top: 0.85em;
    margin-bottom: 0.45em;
    line-height: 1.35;
    color: var(--as-text);
    font-weight: 700;
}

p {
    margin: 0.65em 0;
}

strong, b {
    font-weight: 700;
}

em, i {
    font-style: italic;
}

/* ===== Links ===== */
a {
    color: var(--as-primary);
    text-decoration: none;
}

a:hover {
    text-decoration: underline;
}

/* ===== Code ===== */
code {
    font-family: "JetBrains Mono", "Consolas", "Courier New", monospace;
    font-size: 0.72em;
    border: 1px solid var(--as-border);
    background: var(--as-primary-soft);
    border-radius: 6px;
    padding: 2px 6px;
}

pre {
    margin: 0.9em 0;
    border: 1px solid var(--as-border);
    background: #f7faff;
    border-radius: 10px;
    padding: 10px 12px;
    overflow-x: auto;
}

pre code {
    border: none;
    background: transparent;
    padding: 0;
}

.card.nightMode pre,
.nightMode pre {
    background: rgba(50, 50, 50, 0.88);
}

/* ===== Lists & Quotes ===== */
ul, ol {
    margin: 0.6em 0;
    padding-left: 1.5em;
}

li {
    margin: 0.28em 0;
}

blockquote {
    margin: 0.85em 0;
    border-left: 4px solid var(--as-primary);
    background: #f4f9ff;
    border-radius: 0 8px 8px 0;
    padding: 8px 12px;
    color: var(--as-text-soft);
}

.card.nightMode blockquote,
.nightMode blockquote {
    background: rgba(58, 58, 58, 0.55);
}

/* ===== Tables ===== */
table {
    border-collapse: collapse;
    width: 100%;
    margin: 0.85em 0;
}

th, td {
    border: 1px solid var(--as-border);
    padding: 8px 10px;
    text-align: left;
}

th {
    background: #f5f9ff;
}

.card.nightMode th,
.nightMode th {
    background: rgba(60, 60, 60, 0.7);
}

/* ===== Media ===== */
img {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 0.8em auto;
    border-radius: 10px;
}

/* ===== Cloze ===== */
.cloze,
.as-cloze {
    display: inline-block;
    border-radius: 6px;
    border: 1px solid rgba(31, 111, 214, 0.35);
    background: rgba(31, 111, 214, 0.12);
    color: #225ea8;
    font-weight: 700;
    padding: 2px 8px;
}

.card.nightMode .cloze,
.nightMode .cloze,
.card.nightMode .as-cloze,
.nightMode .as-cloze {
    border-color: rgba(255, 255, 255, 0.28);
    background: rgba(255, 255, 255, 0.08);
    color: #e2e2e2;
}

/* ===== Answer Divider ===== */
hr#answer {
    border: none;
    border-top: 1px solid var(--as-border);
    margin: 4px 16px 0;
}

/* ===== Utility ===== */
.as-muted {
    color: var(--as-text-soft);
}

/* ===== Mobile ===== */
@media (max-width: 600px) {
    .card {
        font-size: 14px;
        padding: 10px;
    }

    .as-head,
    .as-section {
        padding-left: 12px;
        padding-right: 12px;
    }
}
""".strip()


PREVIEW_CARD_EXTRA_CSS = """
/* ===== Preview Card Type Layout ===== */
.card[data-card-type] {
    --bg: #f3f7fc;
    --bg-grad-a: #d9e9ff;
    --bg-grad-b: #dff7ec;
    --surface: #ffffff;
    --text-primary: #0f1c2e;
    --text-secondary: #4b5a72;
    --border: #d8e2f0;
    --shadow-sm: 0 10px 24px rgba(16, 39, 72, 0.12);
    --radius-lg: 16px;
    --radius-md: 12px;
    --q1-border: #d14343;
    --q2-border: #e38a17;
    --q3-border: #2d7fd3;
    --q4-border: #3b8f4f;

    background:
        radial-gradient(900px 540px at -10% -10%, var(--bg-grad-a) 0%, rgba(217, 233, 255, 0) 60%),
        radial-gradient(760px 420px at 110% 15%, var(--bg-grad-b) 0%, rgba(223, 247, 236, 0) 60%),
        var(--bg);
    color: var(--text-primary);
    padding: 18px;
}

.night_mode .card[data-card-type],
.nightMode .card[data-card-type] {
    --bg: #202020;
    --bg-grad-a: #2b2b2b;
    --bg-grad-b: #333333;
    --surface: #2b2b2b;
    --text-primary: #e6e6e6;
    --text-secondary: #a8a8a8;
    --border: #464646;
    --shadow-sm: 0 10px 24px rgba(0, 0, 0, 0.32);
    --q1-border: #696969;
    --q2-border: #727272;
    --q3-border: #7a7a7a;
    --q4-border: #828282;
}

.card-basic, .card-reversed, .card-cloze, .card-concept,
.card-keyterm, .card-choice, .card-image, .card-generic {
    max-width: 960px;
    margin: 0 auto;
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
    background: var(--surface);
    overflow: hidden;
    padding: 16px 18px 20px;
}

.card[data-card-type="basic"] .card-basic,
.card[data-card-type="choice"] .card-choice {
    border-top: 4px solid var(--q1-border);
}

.card[data-card-type="concept"] .card-concept,
.card[data-card-type="image"] .card-image {
    border-top: 4px solid var(--q2-border);
}

.card[data-card-type="cloze"] .card-cloze,
.card[data-card-type="reversed"] .card-reversed {
    border-top: 4px solid var(--q3-border);
}

.card[data-card-type="keyterm"] .card-keyterm,
.card[data-card-type="generic"] .card-generic {
    border-top: 4px solid var(--q4-border);
}

/* ===== Preview Components ===== */
.reversed-notice, .cloze-notice, .concept-notice,
.keyterm-notice, .choice-notice, .image-notice {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 4px 12px;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--text-secondary);
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.3px;
    margin-bottom: 14px;
}

.notice-icon {
    font-size: 11px;
}

.question-section, .answer-section,
.concept-term, .concept-explanation,
.keyterm-term, .keyterm-definition,
.choice-question, .choice-answer,
.image-question, .image-answer {
    margin: 0;
}

.section-label {
    display: inline-block;
    margin: 0 0 8px;
    border-radius: 999px;
    padding: 2px 10px;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--text-secondary);
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.4px;
    text-transform: uppercase;
}

.label-icon {
    display: none;
}

.section-content {
    font-size: 16px;
    line-height: 1.75;
    padding: 14px;
    border: 1px solid var(--border);
    background: #fbfdff;
    border-radius: var(--radius-md);
    color: var(--text-primary);
}

.night_mode .section-content,
.nightMode .section-content {
    background: rgba(58, 58, 58, 0.9);
    border-color: var(--border);
}

.concept-name,
.keyterm-name {
    font-size: 15px;
    color: #1f6fd6;
}

.night_mode .concept-name,
.night_mode .keyterm-name,
.nightMode .concept-name,
.nightMode .keyterm-name {
    color: #d3d3d3;
}

.choice-options {
    margin-top: 12px;
    display: grid;
    gap: 8px;
}

.choice-option {
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 8px 10px;
    background: #fbfdff;
    display: grid;
    grid-template-columns: 22px 1fr;
    gap: 8px;
    align-items: start;
}

.choice-option.is-correct {
    border-color: #8fd1ac;
    background: #eaf8ef;
}

.night_mode .choice-option,
.nightMode .choice-option {
    background: rgba(56, 56, 56, 0.88);
}

.night_mode .choice-option.is-correct,
.nightMode .choice-option.is-correct {
    background: rgba(62, 62, 62, 0.85);
}

.choice-option-key {
    width: 22px;
    height: 22px;
    border-radius: 6px;
    border: 1px solid #bdd1eb;
    background: #eef5ff;
    color: #245189;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 10px;
    font-weight: 700;
}

.choice-option-text {
    font-size: 15px;
    line-height: 1.7;
}

.choice-answer-box {
    border: 1px solid #b7e1c7;
    background: #f3fcf6;
}

.choice-explain {
    border: 1px solid var(--border);
    border-radius: 10px;
    background: #f9fbff;
    padding: 12px 14px;
    font-size: 14px;
    line-height: 1.7;
    color: var(--text-secondary);
}

.choice-explain-wrap .section-label {
    margin-bottom: 10px;
}

.night_mode .choice-explain,
.nightMode .choice-explain {
    background: rgba(54, 54, 54, 0.9);
}

.cloze-content-wrapper {
    background: #eef5ff;
    border: 1px solid #bdd4f5;
    border-radius: var(--radius-md);
    font-size: 15px;
    line-height: 1.8;
    padding: 14px;
}

.cloze {
    font-size: 14px;
    font-weight: 700;
    color: #225ea8;
    background: rgba(31, 111, 214, 0.12);
    border: 1px solid rgba(31, 111, 214, 0.35);
    border-radius: 6px;
    box-shadow: none;
    margin: 0 2px;
    padding: 2px 8px;
}

.cloze-emphasis {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    margin: 2px 2px;
    padding: 2px 8px 2px 6px;
    border-radius: 8px;
    border: 1px solid rgba(31, 111, 214, 0.38);
    background: linear-gradient(90deg, rgba(31, 111, 214, 0.12) 0%, rgba(31, 111, 214, 0.06) 100%);
}

.cloze-index {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 24px;
    height: 20px;
    border-radius: 6px;
    padding: 0 6px;
    border: 1px solid #8ab3ea;
    background: #ddeeff;
    color: #1b4f87;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.2px;
}

.cloze-gap {
    color: #2a5f97;
    font-weight: 700;
    font-size: 12px;
    letter-spacing: 0.5px;
}

.cloze-content {
    color: #1f5fa7;
    font-weight: 800;
    font-size: 15px;
}

.cloze-hint {
    margin-left: 4px;
    color: #4f6a89;
    font-size: 12px;
    font-weight: 600;
}

.cloze-answer-wrap .section-label {
    margin-bottom: 10px;
}

.cloze-answer-list {
    display: grid;
    gap: 8px;
}

.cloze-chip {
    display: grid;
    grid-template-columns: auto 1fr;
    align-items: center;
    gap: 8px;
    border: 1px solid #bfd5f4;
    border-radius: 10px;
    padding: 8px 10px;
    background: #f8fbff;
}

.cloze-chip-index {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 28px;
    height: 22px;
    border-radius: 7px;
    padding: 0 8px;
    border: 1px solid #9abce7;
    background: #e6f1ff;
    color: #255a95;
    font-size: 11px;
    font-weight: 800;
}

.cloze-chip-answer {
    font-size: 15px;
    line-height: 1.65;
    color: var(--text-primary);
    font-weight: 700;
}

.cloze-chip-hint {
    grid-column: 1 / -1;
    margin-left: 36px;
    font-size: 12px;
    line-height: 1.55;
    color: var(--text-secondary);
}

.cloze-empty-note {
    border: 1px dashed var(--border);
    border-radius: 10px;
    padding: 10px 12px;
    color: var(--text-secondary);
    background: #f8fbff;
    font-size: 13px;
}

.divider {
    height: 1px;
    background: var(--border);
    margin: 16px 2px;
    box-shadow: none;
}

.divider-subtle {
    margin: 12px 0 10px;
    opacity: 0.9;
}

.field {
    margin-bottom: 12px;
    padding: 0;
    border: none;
    background: transparent;
}

.field-name {
    font-size: 10px;
    color: var(--text-secondary);
    margin-bottom: 6px;
}

.field-content {
    font-size: 13px;
    line-height: 1.65;
    border: 1px solid var(--border);
    background: #fbfdff;
    border-radius: 10px;
    padding: 10px 12px;
}

.night_mode .field-content,
.nightMode .field-content {
    background: rgba(58, 58, 58, 0.9);
    border-color: var(--border);
}

.night_mode .choice-option-key,
.nightMode .choice-option-key {
    border-color: #5f5f5f;
    background: rgba(70, 70, 70, 0.9);
    color: #e0e0e0;
}

.night_mode .cloze-content-wrapper,
.nightMode .cloze-content-wrapper {
    background: rgba(62, 62, 62, 0.9);
    border-color: #5a5a5a;
}

.night_mode .cloze,
.nightMode .cloze {
    color: #e2e2e2;
    background: rgba(255, 255, 255, 0.08);
    border-color: rgba(255, 255, 255, 0.24);
}

.night_mode .cloze-emphasis,
.nightMode .cloze-emphasis {
    background: rgba(255, 255, 255, 0.06);
    border-color: rgba(255, 255, 255, 0.26);
}

.night_mode .cloze-index,
.nightMode .cloze-index,
.night_mode .cloze-chip-index,
.nightMode .cloze-chip-index {
    background: rgba(92, 92, 92, 0.95);
    border-color: #777777;
    color: #efefef;
}

.night_mode .cloze-gap,
.nightMode .cloze-gap,
.night_mode .cloze-content,
.nightMode .cloze-content {
    color: #f0f0f0;
}

.night_mode .cloze-hint,
.nightMode .cloze-hint {
    color: #c8c8c8;
}

.night_mode .cloze-chip,
.nightMode .cloze-chip {
    background: rgba(56, 56, 56, 0.88);
    border-color: #5f5f5f;
}

.night_mode .cloze-chip-answer,
.nightMode .cloze-chip-answer {
    color: #f0f0f0;
}

.night_mode .cloze-empty-note,
.nightMode .cloze-empty-note {
    background: rgba(56, 56, 56, 0.86);
}

.empty-placeholder {
    color: var(--text-secondary);
    font-style: italic;
}

@media (max-width: 640px) {
    .card[data-card-type] {
        padding: 10px;
    }

    .card-basic, .card-reversed, .card-cloze, .card-concept,
    .card-keyterm, .card-choice, .card-image, .card-generic {
        padding: 12px;
    }
}
""".strip()
