"""Existing BI report matching for the builder flow."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

from app.services.bi_builder_context import BuilderContext


class ExistingReportMatcher:
    def match(self, message: str, context: BuilderContext, limit: int = 3) -> List[Dict[str, Any]]:
        query_tokens = self._tokens(message)
        if not query_tokens:
            return []

        scored: List[Dict[str, Any]] = []
        for chart in context.charts:
            text = self._chart_text(chart)
            tokens = self._tokens(text)
            overlap = len(query_tokens & tokens)
            score = min(1.0, overlap / max(1, len(query_tokens)))
            if score < 0.35 and not any(token in text for token in query_tokens):
                continue
            category_id = chart.get("category_id") or chart.get("categoryId")
            category = self._find_category(context.bi_config, category_id)
            scored.append({
                "chart_id": chart.get("id"),
                "title": chart.get("title", "未命名图表"),
                "category_id": category_id,
                "category_name": (category or {}).get("name") or (category or {}).get("display_name") or "",
                "chart_type": chart.get("chart_type") or chart.get("type") or "bar",
                "reason": "指标、维度或分析意图与需求接近",
                "differences": ["可基于此图调整图表类型、筛选条件、字段或分类"],
                "score": round(score, 2),
            })
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:limit]

    def find_chart(self, context: BuilderContext, chart_id: Optional[str]) -> Optional[Dict[str, Any]]:
        if not chart_id:
            return None
        for chart in context.charts:
            if chart.get("id") == chart_id:
                return chart
        return None

    def _chart_text(self, chart: Dict[str, Any]) -> str:
        parts = [str(chart.get(k, "")) for k in ("title", "question", "description", "chart_type", "type", "x_field", "y_field")]
        parts.extend(chart.get("dimensions") or [])
        metric = chart.get("metric") or {}
        parts.extend([str(metric.get("field", "")), str(metric.get("label", ""))])
        return " ".join(parts)

    def _tokens(self, text: str) -> Set[str]:
        parts = set(re.findall(r"[A-Za-z0-9_]+", text.lower()))
        for token in re.findall(r"[\u4e00-\u9fff]{2,}", text):
            parts.add(token)
            for i in range(max(0, len(token) - 1)):
                parts.add(token[i:i + 2])
        return {part for part in parts if part}

    def _find_category(self, bi_config: Dict[str, Any], category_id: Optional[str]) -> Optional[Dict[str, Any]]:
        for category in bi_config.get("categories", []):
            if category.get("id") == category_id:
                return category
        return None
