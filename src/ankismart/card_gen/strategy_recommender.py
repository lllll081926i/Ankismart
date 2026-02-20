"""Strategy recommender for intelligent card generation strategy selection."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ankismart.core.logging import get_logger

if TYPE_CHECKING:
    from ankismart.card_gen.llm_client import LLMClient

logger = get_logger("strategy_recommender")


class StrategyRecommendation:
    """Recommendation result with strategy mix and reasoning."""

    def __init__(
        self,
        strategy_mix: list[dict[str, any]],
        reasoning: str,
        confidence: float,
        document_type: str,
    ):
        self.strategy_mix = strategy_mix
        self.reasoning = reasoning
        self.confidence = confidence
        self.document_type = document_type


class StrategyRecommender:
    """Intelligent strategy recommender using LLM analysis."""

    # Document type patterns
    TEXTBOOK_PATTERNS = [
        r"第[一二三四五六七八九十\d]+章",
        r"chapter\s+\d+",
        r"定义[:：]",
        r"定理[:：]",
        r"例题[:：]",
        r"习题",
        r"练习",
    ]

    PAPER_PATTERNS = [
        r"abstract",
        r"摘要",
        r"introduction",
        r"引言",
        r"methodology",
        r"方法",
        r"conclusion",
        r"结论",
        r"references",
        r"参考文献",
    ]

    NOTE_PATTERNS = [
        r"笔记",
        r"notes?",
        r"总结",
        r"summary",
        r"要点",
        r"key\s+points?",
    ]

    def __init__(self, llm_client: LLMClient | None = None):
        """Initialize recommender with optional LLM client.

        Args:
            llm_client: Optional LLM client for advanced analysis
        """
        self._llm_client = llm_client

    def recommend(self, content: str, max_length: int = 3000) -> StrategyRecommendation:
        """Recommend strategy mix based on document content.

        Args:
            content: Document content (markdown)
            max_length: Maximum content length to analyze

        Returns:
            StrategyRecommendation with suggested strategy mix
        """
        # Truncate content for analysis
        analysis_content = content[:max_length]

        # Detect document type
        doc_type = self._detect_document_type(analysis_content)

        # Use LLM for advanced analysis if available
        if self._llm_client:
            try:
                return self._llm_recommend(analysis_content, doc_type)
            except Exception as e:
                logger.warning(f"LLM recommendation failed, falling back to rule-based: {e}")

        # Fallback to rule-based recommendation
        return self._rule_based_recommend(analysis_content, doc_type)

    def _detect_document_type(self, content: str) -> str:
        """Detect document type from content patterns.

        Args:
            content: Document content

        Returns:
            Document type: "textbook", "paper", "notes", or "general"
        """
        # Count pattern matches
        textbook_score = sum(
            1 for pattern in self.TEXTBOOK_PATTERNS if re.search(pattern, content, re.IGNORECASE)
        )
        paper_score = sum(
            1 for pattern in self.PAPER_PATTERNS if re.search(pattern, content, re.IGNORECASE)
        )
        note_score = sum(
            1 for pattern in self.NOTE_PATTERNS if re.search(pattern, content, re.IGNORECASE)
        )

        # Determine type by highest score
        scores = {
            "textbook": textbook_score,
            "paper": paper_score,
            "notes": note_score,
        }

        max_score = max(scores.values())
        if max_score == 0:
            return "general"

        return max(scores, key=scores.get)

    def _rule_based_recommend(
        self, content: str, doc_type: str
    ) -> StrategyRecommendation:
        """Generate recommendation using rule-based heuristics.

        Args:
            content: Document content
            doc_type: Detected document type

        Returns:
            StrategyRecommendation
        """
        # Analyze content characteristics
        has_definitions = bool(re.search(r"定义[:：]|definition:", content, re.IGNORECASE))
        has_examples = bool(re.search(r"例[题如]|example", content, re.IGNORECASE))
        has_lists = content.count("\n- ") + content.count("\n* ") + content.count("\n1. ")

        # Strategy mix based on document type
        if doc_type == "textbook":
            strategy_mix = [
                {"strategy": "concept_explanation", "ratio": 30},
                {"strategy": "basic_qa", "ratio": 25},
                {"strategy": "fill_blank", "ratio": 20},
                {"strategy": "key_terms", "ratio": 15},
                {"strategy": "single_choice", "ratio": 10},
            ]
            reasoning = "教材类文档：重点关注概念解释和基础问答，辅以填空题巩固知识点。"
            confidence = 0.8

        elif doc_type == "paper":
            strategy_mix = [
                {"strategy": "concept_explanation", "ratio": 35},
                {"strategy": "key_terms", "ratio": 30},
                {"strategy": "basic_qa", "ratio": 25},
                {"strategy": "fill_blank", "ratio": 10},
            ]
            reasoning = "论文类文档：强调概念理解和关键术语，适合深度学习。"
            confidence = 0.75

        elif doc_type == "notes":
            strategy_mix = [
                {"strategy": "basic_qa", "ratio": 35},
                {"strategy": "fill_blank", "ratio": 30},
                {"strategy": "key_terms", "ratio": 20},
                {"strategy": "concept_explanation", "ratio": 15},
            ]
            reasoning = "笔记类文档：侧重快速回顾和记忆，使用问答和填空题。"
            confidence = 0.7

        else:  # general
            strategy_mix = [
                {"strategy": "basic_qa", "ratio": 30},
                {"strategy": "concept_explanation", "ratio": 25},
                {"strategy": "fill_blank", "ratio": 20},
                {"strategy": "key_terms", "ratio": 15},
                {"strategy": "single_choice", "ratio": 10},
            ]
            reasoning = "通用文档：平衡各种策略，适应多样化内容。"
            confidence = 0.6

        # Adjust based on content characteristics
        if has_definitions:
            # Increase concept_explanation ratio
            for item in strategy_mix:
                if item["strategy"] == "concept_explanation":
                    item["ratio"] += 5
                    break

        if has_examples:
            # Increase basic_qa ratio
            for item in strategy_mix:
                if item["strategy"] == "basic_qa":
                    item["ratio"] += 5
                    break

        if has_lists > 5:
            # Increase fill_blank ratio
            for item in strategy_mix:
                if item["strategy"] == "fill_blank":
                    item["ratio"] += 5
                    break

        # Normalize ratios to sum to 100
        total_ratio = sum(item["ratio"] for item in strategy_mix)
        for item in strategy_mix:
            item["ratio"] = int(item["ratio"] * 100 / total_ratio)

        return StrategyRecommendation(
            strategy_mix=strategy_mix,
            reasoning=reasoning,
            confidence=confidence,
            document_type=doc_type,
        )

    def _llm_recommend(
        self, content: str, doc_type: str
    ) -> StrategyRecommendation:
        """Generate recommendation using LLM analysis.

        Args:
            content: Document content
            doc_type: Detected document type

        Returns:
            StrategyRecommendation
        """
        system_prompt = """你是一个 Anki 卡片生成策略专家。分析文档内容，推荐最佳的卡片生成策略组合。

可用策略：
1. basic_qa - 基础问答：适合事实性知识和概念理解
2. fill_blank - 填空题：适合记忆关键术语和定义
3. concept_explanation - 概念解释：适合深度理解复杂概念
4. key_terms - 关键术语：适合专业词汇和术语记忆
5. single_choice - 单选题：适合辨析相似概念
6. multiple_choice - 多选题：适合综合知识点

请分析文档特征，推荐策略组合（比例总和为100），并说明理由。"""

        user_prompt = f"""文档类型：{doc_type}

文档内容（前3000字）：
{content}

请以JSON格式返回推荐结果：
{{
    "strategy_mix": [
        {{"strategy": "basic_qa", "ratio": 30}},
        {{"strategy": "concept_explanation", "ratio": 25}},
        ...
    ],
    "reasoning": "推荐理由",
    "confidence": 0.85
}}"""

        try:
            response = self._llm_client.chat(system_prompt, user_prompt)

            # Parse JSON response
            import json
            # Extract JSON from markdown code block if present
            json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = response

            result = json.loads(json_str)

            return StrategyRecommendation(
                strategy_mix=result.get("strategy_mix", []),
                reasoning=result.get("reasoning", "LLM 分析推荐"),
                confidence=result.get("confidence", 0.8),
                document_type=doc_type,
            )

        except Exception as e:
            logger.error(f"Failed to parse LLM recommendation: {e}")
            # Fallback to rule-based
            return self._rule_based_recommend(content, doc_type)
