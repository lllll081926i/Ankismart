from __future__ import annotations

import re

_CLOZE_PATTERN = re.compile(r"\{\{c\d+::.*?\}\}", re.IGNORECASE | re.DOTALL)
_OPTION_LINE_PATTERN = re.compile(r"^\s*([A-Ea-e])[\.、\):：\-]\s*(.+?)\s*$")
_ANSWER_LINE_PATTERN = re.compile(
    r"^(?:答案|正确答案|answer)?\s*[:：]?\s*([A-Ea-e](?:\s*[,，、/]\s*[A-Ea-e])*)\s*$",
    re.IGNORECASE,
)


def has_valid_cloze(text: str) -> bool:
    return bool(_CLOZE_PATTERN.search(str(text or "")))


def normalize_html_to_text(text: str) -> str:
    if not text:
        return ""
    plain = re.sub(r"<br\s*/?>", "\n", str(text), flags=re.IGNORECASE)
    plain = re.sub(r"</p\s*>", "\n", plain, flags=re.IGNORECASE)
    plain = re.sub(r"<[^>]+>", " ", plain)
    plain = plain.replace("&nbsp;", " ").replace("\r", "")
    plain = re.sub(r"\n{3,}", "\n\n", plain)
    return plain.strip()


def strip_leading_index(text: str) -> str:
    return re.sub(r"^\s*\d+[\.、\):：\-]\s*", "", str(text or "")).strip()


def _extract_plain_lines(text: str) -> list[str]:
    plain = normalize_html_to_text(text)
    return [line.strip() for line in plain.splitlines() if line.strip()]


def _extract_answer_keys(raw: str) -> list[str]:
    keys: list[str] = []
    for key in re.findall(r"[A-Ea-e]", str(raw or "")):
        normalized = key.upper()
        if normalized not in keys:
            keys.append(normalized)
    return keys


def parse_choice_front(front: str) -> tuple[str, list[tuple[str, str]]]:
    plain = normalize_html_to_text(front)
    compact = re.sub(r"\s+", " ", plain).strip()
    inline_matches = list(re.finditer(r"(^|\s)([A-Ea-e])[\.、\):：\-]\s*", compact))
    if len(inline_matches) >= 2:
        question = compact[: inline_matches[0].start(2)].strip()
        options: list[tuple[str, str]] = []
        for index, match in enumerate(inline_matches):
            key = match.group(2).upper()
            start = match.end()
            end = (
                inline_matches[index + 1].start(2)
                if index + 1 < len(inline_matches)
                else len(compact)
            )
            option_text = compact[start:end].strip(" ;；")
            if option_text:
                options.append((key, option_text))
        if options:
            return question, options

    lines = [line.strip() for line in plain.splitlines() if line.strip()]
    options: list[tuple[str, str]] = []
    question_lines: list[str] = []

    for line in lines:
        match = _OPTION_LINE_PATTERN.match(line)
        if match:
            options.append((match.group(1).upper(), match.group(2).strip()))
        elif not options:
            question_lines.append(line)

    if options:
        question = "\n".join(question_lines) if question_lines else (lines[0] if lines else "")
        return question.strip(), options

    return plain, []


def parse_choice_back(back: str) -> tuple[list[str], list[str]]:
    lines = [strip_leading_index(line) for line in _extract_plain_lines(back)]
    lines = [line for line in lines if line]
    if not lines:
        return [], []

    first = lines[0]
    match = _ANSWER_LINE_PATTERN.match(first)
    if match:
        return _extract_answer_keys(match.group(1)), _normalize_explanation_lines(lines[1:])

    labeled = re.match(r"^(?:答案|正确答案|answer)\s*[:：]\s*(.+)$", first, re.IGNORECASE)
    if labeled:
        body = labeled.group(1).strip()
        prefixed = re.match(
            r"^([A-Ea-e](?:\s*[,，、/]\s*[A-Ea-e])*)(?:[\.、\):：\-]\s*|\s+)(.+)$",
            body,
        )
        if prefixed:
            return _extract_answer_keys(prefixed.group(1)), _normalize_explanation_lines(
                [prefixed.group(2), *lines[1:]]
            )
        return _extract_answer_keys(body), _normalize_explanation_lines(lines[1:])

    if re.fullmatch(r"[A-Ea-e](?:\s*[,，、/]\s*[A-Ea-e])*", first):
        return _extract_answer_keys(first), _normalize_explanation_lines(lines[1:])

    prefixed = re.match(
        r"^([A-Ea-e](?:\s*[,，、/]\s*[A-Ea-e])*)(?:[\.、\):：\-]\s*|\s+)(.+)$",
        first,
    )
    if prefixed:
        return _extract_answer_keys(prefixed.group(1)), _normalize_explanation_lines(
            [prefixed.group(2), *lines[1:]]
        )

    whole = "\n".join(lines)
    inline = re.search(
        r"(?:答案|正确答案|answer)\s*[:：]?\s*([A-Ea-e](?:\s*[,，、/]\s*[A-Ea-e])*)",
        whole,
        re.IGNORECASE,
    )
    if inline:
        explanation = whole.replace(inline.group(0), "", 1).strip(" \n:：")
        return _extract_answer_keys(inline.group(1)), _normalize_explanation_lines(
            explanation.splitlines()
        )

    return [], _normalize_explanation_lines(lines)


def _normalize_explanation_lines(lines: list[str]) -> list[str]:
    normalized = [strip_leading_index(line) for line in lines if str(line).strip()]
    while normalized and re.match(
        r"^(?:解析|explanation)\s*[:：]?\s*$", normalized[0], re.IGNORECASE
    ):
        normalized.pop(0)
    if normalized:
        with_text = re.match(r"^(?:解析|explanation)\s*[:：]\s*(.+)$", normalized[0], re.IGNORECASE)
        if with_text:
            normalized[0] = with_text.group(1).strip()
    return [line for line in normalized if line]


def parse_answer_block(raw: str) -> tuple[str, str]:
    plain = normalize_html_to_text(raw)
    if not plain:
        return "", ""

    lines = [strip_leading_index(line) for line in plain.splitlines() if line.strip()]
    lines = [line for line in lines if line]
    if not lines:
        return "", ""

    joined = "\n".join(lines)
    labeled = re.match(
        r"^(?:答案|正确答案|answer)\s*[:：]\s*(.+?)(?:\n(?:解析|explanation)\s*[:：]?\s*([\s\S]*))?$",
        joined,
        re.IGNORECASE,
    )
    if labeled:
        answer = labeled.group(1).strip()
        explanation = (labeled.group(2) or "").strip()
        return answer, explanation

    first = lines[0]
    inline = re.match(
        r"^(?:答案|正确答案|answer)\s*[:：]?\s*(.+?)(?:\s*(?:解析|explanation)\s*[:：]\s*(.+))$",
        first,
        re.IGNORECASE,
    )
    if inline:
        return inline.group(1).strip(), inline.group(2).strip()

    split_inline = re.split(r"(?:解析|explanation)\s*[:：]", first, maxsplit=1, flags=re.IGNORECASE)
    if len(split_inline) == 2:
        answer = re.sub(
            r"^(?:答案|正确答案|answer)\s*[:：]?\s*", "", split_inline[0], flags=re.IGNORECASE
        ).strip()
        explanation_parts = [split_inline[1].strip(), *lines[1:]]
        return answer, "\n".join(part for part in explanation_parts if part).strip()

    answer = re.sub(
        r"^(?:答案|正确答案|answer)\s*[:：]?\s*", "", first, flags=re.IGNORECASE
    ).strip()
    explanation = "\n".join(_normalize_explanation_lines(lines[1:])).strip()
    if explanation:
        return answer, explanation

    sentences = [
        part.strip()
        for part in re.split(r"(?<=[。！？!?；;])\s*", answer)
        if part.strip()
    ]
    if len(sentences) >= 2:
        return sentences[0], "\n".join(sentences[1:]).strip()
    return answer, ""
