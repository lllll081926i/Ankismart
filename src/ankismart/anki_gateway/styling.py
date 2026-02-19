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
    font-size: 19px;
    line-height: 1.7;
    color: var(--as-text);
    background:
        radial-gradient(900px 540px at -10% -10%, var(--as-bg-grad-a) 0%, rgba(217, 233, 255, 0) 60%),
        radial-gradient(760px 420px at 110% 15%, var(--as-bg-grad-b) 0%, rgba(223, 247, 236, 0) 60%),
        var(--as-bg);
    margin: 0;
    padding: 16px;
    text-align: left;
}

.card.nightMode,
.nightMode .card {
    --as-bg: #0f1724;
    --as-bg-grad-a: #1a2a40;
    --as-bg-grad-b: #1b3345;
    --as-surface: #111b2b;
    --as-text: #e5edf7;
    --as-text-soft: #95a3b8;
    --as-border: #2a3951;
    --as-shadow: 0 10px 24px rgba(0, 0, 0, 0.35);
    --as-primary: #88c0ff;
    --as-primary-soft: rgba(53, 93, 142, 0.5);
    --as-success: #88d0ab;
    --as-success-soft: rgba(34, 73, 56, 0.78);
    --as-warn: #f1b876;
    --as-warn-soft: rgba(73, 49, 27, 0.78);
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
    background: rgba(20, 32, 48, 0.92);
}

.as-chip {
    display: inline-block;
    border-radius: 999px;
    border: 1px solid #bdd1eb;
    background: #edf5ff;
    color: #265083;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.25px;
    padding: 3px 11px;
}

.card.nightMode .as-chip,
.nightMode .as-chip {
    border-color: #4d6f97;
    background: rgba(36, 71, 110, 0.55);
    color: #cbe2ff;
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
    font-size: 11px;
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
    background: rgba(18, 29, 44, 0.9);
}

.as-answer-box {
    border-color: #b7e1c7;
    background: #f3fcf6;
}

.card.nightMode .as-answer-box,
.nightMode .as-answer-box {
    border-color: #3d6e58;
    background: rgba(24, 53, 43, 0.9);
}

.as-extra {
    border-color: var(--as-border);
    background: #f9fbff;
    color: var(--as-text-soft);
}

.card.nightMode .as-extra,
.nightMode .as-extra {
    background: rgba(22, 35, 53, 0.9);
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
    font-size: 0.9em;
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
    background: rgba(25, 39, 58, 0.88);
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
    background: rgba(33, 56, 85, 0.55);
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
    background: rgba(30, 48, 72, 0.7);
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
    border-color: rgba(137, 191, 255, 0.55);
    background: rgba(42, 87, 141, 0.5);
    color: #b7d9ff;
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
        font-size: 17px;
        padding: 10px;
    }

    .as-head,
    .as-section {
        padding-left: 12px;
        padding-right: 12px;
    }
}
""".strip()
