"""
Modern card styling for Anki cards.

This module provides CSS styling that works across Anki Desktop, AnkiDroid, and AnkiWeb.
Designed with responsiveness, readability, and dark mode support in mind.
"""

MODERN_CARD_CSS = """
/* ===== Base Styles ===== */
.card {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Microsoft YaHei', sans-serif;
    font-size: 18px;
    line-height: 1.8;
    color: #2c3e50;
    background-color: transparent;
    padding: 24px;
    max-width: 100%;
    margin: 0;
    text-align: left;
}

/* ===== Typography ===== */
h1, h2, h3, h4, h5, h6 {
    margin-top: 1.2em;
    margin-bottom: 0.6em;
    font-weight: 600;
    line-height: 1.4;
    color: #1a252f;
}

h1 { font-size: 2em; }
h2 { font-size: 1.7em; }
h3 { font-size: 1.5em; }
h4 { font-size: 1.3em; }
h5 { font-size: 1.1em; }
h6 { font-size: 1em; }

p {
    margin: 0.8em 0;
}

strong, b {
    font-weight: 600;
    color: #1a252f;
}

em, i {
    font-style: italic;
}

/* ===== Links ===== */
a {
    color: #0078d4;
    text-decoration: none;
}

a:hover {
    text-decoration: underline;
}

/* ===== Code Blocks ===== */
code {
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
    font-size: 0.95em;
    background-color: transparent;
    padding: 2px 4px;
    border-radius: 3px;
    color: #d73a49;
    border: 1px solid rgba(0, 0, 0, 0.1);
}

pre {
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
    font-size: 0.9em;
    background-color: transparent;
    padding: 16px 20px;
    border-radius: 8px;
    overflow-x: auto;
    margin: 1.2em 0;
    border: 1px solid rgba(0, 0, 0, 0.1);
}

pre code {
    background-color: transparent;
    padding: 0;
    color: #24292e;
    border-radius: 0;
    border: none;
}

/* ===== Lists ===== */
ul, ol {
    margin: 0.8em 0;
    padding-left: 2em;
}

li {
    margin: 0.4em 0;
}

ul ul, ol ol, ul ol, ol ul {
    margin: 0.2em 0;
}

/* ===== Blockquotes ===== */
blockquote {
    margin: 1.2em 0;
    padding: 0.8em 1.2em;
    border-left: 4px solid #0078d4;
    background-color: transparent;
    color: #495057;
    font-style: italic;
}

blockquote p {
    margin: 0.5em 0;
}

/* ===== Horizontal Rules ===== */
hr {
    border: none;
    border-top: 2px solid #e1e4e8;
    margin: 1.5em 0;
}

/* ===== Tables ===== */
table {
    border-collapse: collapse;
    width: 100%;
    margin: 1.2em 0;
}

th, td {
    border: 1px solid #d0d7de;
    padding: 10px 14px;
    text-align: left;
}

th {
    background-color: transparent;
    font-weight: 600;
    border-bottom: 2px solid #d0d7de;
}

tr:nth-child(even) {
    background-color: transparent;
}

/* ===== Images ===== */
img {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 1em auto;
    border-radius: 8px;
}

/* ===== Math (MathJax/KaTeX) ===== */
.MathJax, .katex {
    font-size: 1.1em !important;
}

.MathJax_Display {
    margin: 1em 0 !important;
}

/* ===== Cloze Deletions ===== */
.cloze {
    font-weight: 600;
    color: #0078d4;
}

/* ===== Dark Mode ===== */
.night_mode .card {
    color: #e4e4e4;
    background-color: transparent;
}

.night_mode h1,
.night_mode h2,
.night_mode h3,
.night_mode h4,
.night_mode h5,
.night_mode h6 {
    color: #ffffff;
}

.night_mode strong,
.night_mode b {
    color: #ffffff;
}

.night_mode a {
    color: #4db8ff;
}

.night_mode code {
    background-color: transparent;
    color: #ff7b72;
    border-color: rgba(255, 255, 255, 0.15);
}

.night_mode pre {
    background-color: transparent;
    border-color: rgba(255, 255, 255, 0.15);
}

.night_mode pre code {
    color: #e4e4e4;
    border: none;
}

.night_mode blockquote {
    border-left-color: #4db8ff;
    background-color: transparent;
    color: #c9d1d9;
}

.night_mode hr {
    border-top-color: rgba(255, 255, 255, 0.15);
}

.night_mode th {
    background-color: transparent;
    border-bottom: 2px solid rgba(255, 255, 255, 0.15);
}

.night_mode th, .night_mode td {
    border-color: rgba(255, 255, 255, 0.15);
}

.night_mode tr:nth-child(even) {
    background-color: transparent;
}

.night_mode .cloze {
    color: #4db8ff;
}

/* ===== Mobile Optimization ===== */
@media (max-width: 600px) {
    .card {
        padding: 12px;
        font-size: 16px;
    }

    h1 { font-size: 1.5em; }
    h2 { font-size: 1.3em; }
    h3 { font-size: 1.2em; }
    h4 { font-size: 1.1em; }

    pre {
        padding: 8px 12px;
        font-size: 0.8em;
    }

    table {
        font-size: 0.9em;
    }

    th, td {
        padding: 6px 8px;
    }

    ul, ol {
        padding-left: 1.5em;
    }
}

/* ===== Print Styles ===== */
@media print {
    .card {
        color: #000000;
        background-color: #ffffff;
    }

    a {
        color: #000000;
        text-decoration: underline;
    }
}
""".strip()
