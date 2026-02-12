"""
Modern card styling for Anki cards.

This module provides CSS styling that works across Anki Desktop, AnkiDroid, and AnkiWeb.
Designed with responsiveness, readability, and dark mode support in mind.
"""

MODERN_CARD_CSS = """
/* ===== Base Styles ===== */
.card {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    font-size: clamp(16px, 4vw, 20px);
    line-height: 1.6;
    color: #2c3e50;
    background-color: #ffffff;
    padding: 20px;
    max-width: 800px;
    margin: 0 auto;
    text-align: left;
}

/* ===== Typography ===== */
h1, h2, h3, h4, h5, h6 {
    margin-top: 1.5em;
    margin-bottom: 0.5em;
    font-weight: 600;
    line-height: 1.3;
    color: #1a252f;
}

h1 { font-size: 1.8em; }
h2 { font-size: 1.5em; }
h3 { font-size: 1.3em; }
h4 { font-size: 1.1em; }
h5 { font-size: 1em; }
h6 { font-size: 0.9em; }

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
    font-size: 0.9em;
    background-color: #f5f5f5;
    padding: 2px 6px;
    border-radius: 3px;
    color: #d73a49;
}

pre {
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
    font-size: 0.85em;
    background-color: #f6f8fa;
    padding: 12px 16px;
    border-radius: 6px;
    overflow-x: auto;
    margin: 1em 0;
    border: 1px solid #e1e4e8;
}

pre code {
    background-color: transparent;
    padding: 0;
    color: #24292e;
    border-radius: 0;
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
    margin: 1em 0;
    padding: 0.5em 1em;
    border-left: 4px solid #0078d4;
    background-color: #f8f9fa;
    color: #495057;
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
    margin: 1em 0;
}

th, td {
    border: 1px solid #d0d7de;
    padding: 8px 12px;
    text-align: left;
}

th {
    background-color: #f6f8fa;
    font-weight: 600;
}

tr:nth-child(even) {
    background-color: #f6f8fa;
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
    background-color: #1e1e1e;
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
    background-color: #2d2d2d;
    color: #ff7b72;
}

.night_mode pre {
    background-color: #2d2d2d;
    border-color: #444444;
}

.night_mode pre code {
    color: #e4e4e4;
}

.night_mode blockquote {
    border-left-color: #4db8ff;
    background-color: #2d2d2d;
    color: #c9d1d9;
}

.night_mode hr {
    border-top-color: #444444;
}

.night_mode th {
    background-color: #2d2d2d;
}

.night_mode th, .night_mode td {
    border-color: #444444;
}

.night_mode tr:nth-child(even) {
    background-color: #2d2d2d;
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
