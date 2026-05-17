"""Create BI chart config entries from confirmed BI builder drafts."""

from __future__ import annotations

import copy
import uuid
from typing import Any, Dict, List, Optional, Tuple

from app.services.bi_builder_context import BuilderContext
from app.services.bi_profiler import numeric_expr, quote_ident, safe_alias
from app.services.bi_sql_builder import BISQLBuilder, MetricSpecCompiler
from app.services.db_service import DBService


class BIBuilderCreator:
    def __init__(self, db_service: DBService):
        self.db = db_service
        self.compiler = MetricSpecCompiler()
        self.sql_builder = BISQLBuilder()

    async def create(self, chart_list: List[Dict[str, Any]], context: BuilderContext) -> Dict[str, Any]:
        bi_config = copy.deepcopy(context.bi_config)
        bi_config.setdefault("charts", [])
        created: List[Dict[str, Any]] = []
        failed: List[Dict[str, Any]] = []

        for draft in chart_list:
            try:
                chart = await self._draft_to_chart(draft, context)
                if not chart.get("preview", {}).get("rows"):
                    raise ValueError("SQL 预览为空")
                bi_config["charts"].append(chart)
                created.append(chart)
            except Exception as exc:
                failed.append({"client_chart_id": draft.get("client_chart_id"), "title": draft.get("title"), "reason": str(exc)})
                if draft.get("required", True):
                    break

        if created:
            await self.db.update_bi_config(context.file_id, bi_config)
        return {"created": created, "failed": failed}

    async def _draft_to_chart(self, draft: Dict[str, Any], context: BuilderContext) -> Dict[str, Any]:
        if draft.get("source") == "adjust_existing" and draft.get("base_chart_id"):
            base = self._find_chart(context, draft["base_chart_id"])
            if base:
                return await self._adjust_existing(base, draft, context)

        profile = self._profile_for_draft(draft, context)
        sql, chart_type = self._build_sql_from_spec(draft, profile)
        rows = await self.db.execute_query(sql)
        return self._chart_from_draft(draft, context, sql, rows, chart_type)

    async def _adjust_existing(
        self,
        base: Dict[str, Any],
        draft: Dict[str, Any],
        context: BuilderContext,
    ) -> Dict[str, Any]:
        chart = copy.deepcopy(base)
        category = self._find_category(context, draft.get("target_category_id") or chart.get("category_id"))
        chart["id"] = f"chart_builder_{uuid.uuid4().hex[:10]}"
        chart["title"] = draft.get("title") or chart.get("title")
        chart["chart_type"] = draft.get("chart_type") or chart.get("chart_type") or chart.get("type")
        chart["type"] = chart["chart_type"]
        chart["category_id"] = draft.get("target_category_id") or chart.get("category_id")
        chart["categoryId"] = chart["category_id"]
        rows = await self.db.execute_query(chart["sql"])
        chart["preview"] = {"columns": list(rows[0].keys()) if rows else [], "rows": rows[:20]}
        chart["tablePreview"] = chart["preview"]
        chart["source"] = "bi_builder_adjust"
        if category:
            chart["category"] = category.get("name") or category.get("display_name")
        return chart

    def _build_sql_from_spec(self, draft: Dict[str, Any], profile: Dict[str, Any]) -> Tuple[str, str]:
        question = {
            "question": draft.get("title") or "",
            "analysis_type": draft.get("analysis_type") or "ranking",
            "sql_template_hint": self._sql_template_hint(draft),
            "metrics": [((draft.get("metric") or {}).get("field") or "*")],
            "dimensions": draft.get("dimensions") or [],
            "time_field": draft.get("time_field"),
        }
        try:
            spec = self.compiler.compile(profile, question)
            sql, _summary_sql, chart_type = self.sql_builder.build(spec, profile)
            if draft.get("analysis_type") == "ranking_bottom":
                sql = self._force_ascending(sql)
            if draft.get("limit"):
                sql = self._replace_limit(sql, int(draft["limit"]))
            return sql, draft.get("chart_type") or chart_type
        except Exception:
            return self._fallback_sql(draft)

    def _fallback_sql(self, draft: Dict[str, Any]) -> Tuple[str, str]:
        table = quote_ident(draft["table_name"])
        metric = (draft.get("metric") or {}).get("field")
        dimension = (draft.get("dimensions") or [None])[0]
        analysis_type = draft.get("analysis_type")
        chart_type = draft.get("chart_type") or "bar"
        if analysis_type == "detail":
            return f"SELECT * FROM {table} LIMIT 100", "table"
        if analysis_type == "trend" and draft.get("time_field") and metric:
            tf = draft["time_field"]
            expr = numeric_expr(metric)
            bucket = f"DATE_FORMAT({quote_ident(tf)}, '%Y-%m')"
            return (
                f"SELECT {bucket} AS `时间`, SUM({expr}) AS `{safe_alias(metric)}` "
                f"FROM {table} WHERE {quote_ident(tf)} IS NOT NULL AND {quote_ident(tf)} <> '' "
                f"GROUP BY {bucket} ORDER BY `时间` ASC LIMIT 24",
                "line",
            )
        if dimension and metric:
            expr = "COUNT(*)" if metric == "*" else numeric_expr(metric)
            metric_alias = "记录数" if metric == "*" else metric
            order = "ASC" if analysis_type == "ranking_bottom" else "DESC"
            return (
                f"SELECT {quote_ident(dimension)} AS `{safe_alias(dimension)}`, "
                f"{'COUNT(*)' if metric == '*' else f'SUM({expr})'} AS `{safe_alias(metric_alias)}` "
                f"FROM {table} WHERE {quote_ident(dimension)} IS NOT NULL AND {quote_ident(dimension)} <> '' "
                f"GROUP BY {quote_ident(dimension)} ORDER BY `{safe_alias(metric_alias)}` {order} LIMIT {int(draft.get('limit') or 5)}",
                chart_type,
            )
        if metric:
            return f"SELECT SUM({numeric_expr(metric)}) AS `{safe_alias(metric)}` FROM {table}", "kpi"
        return f"SELECT COUNT(*) AS `记录数` FROM {table}", "kpi"

    def _chart_from_draft(
        self,
        draft: Dict[str, Any],
        context: BuilderContext,
        sql: str,
        rows: List[Dict[str, Any]],
        chart_type: str,
    ) -> Dict[str, Any]:
        category_id = draft.get("target_category_id")
        category = self._find_category(context, category_id)
        metric = draft.get("metric") or {}
        dimensions = draft.get("dimensions") or []
        preview = {"columns": list(rows[0].keys()) if rows else [], "rows": rows[:20]}
        return {
            "id": f"chart_builder_{uuid.uuid4().hex[:10]}",
            "title": draft.get("title") or "新建图表",
            "question": draft.get("title") or "",
            "description": draft.get("title") or "",
            "chart_type": draft.get("chart_type") or chart_type,
            "type": draft.get("chart_type") or chart_type,
            "table_name": draft.get("table_name"),
            "category_id": category_id,
            "categoryId": category_id,
            "category": (category or {}).get("name") or (category or {}).get("display_name") or category_id,
            "default_category_id": category_id,
            "sql": sql,
            "metric": metric,
            "dimensions": dimensions,
            "x_field": dimensions[0] if dimensions else draft.get("time_field"),
            "y_field": metric.get("field"),
            "time_field": draft.get("time_field"),
            "filters": draft.get("filters") or [],
            "on_board": True,
            "onBoard": True,
            "collapsed": False,
            "expanded": False,
            "preview": preview,
            "tablePreview": preview,
            "source": "bi_builder",
        }

    def _profile_for_draft(self, draft: Dict[str, Any], context: BuilderContext) -> Dict[str, Any]:
        table_name = draft.get("table_name")
        for profile in context.profiles:
            if profile.get("table_name") == table_name:
                return profile
        if context.profiles:
            return context.profiles[0]
        raise ValueError("缺少可用字段画像")

    def _sql_template_hint(self, draft: Dict[str, Any]) -> str:
        mapping = {
            "ranking_top": "ranking",
            "ranking_bottom": "ranking",
            "trend": "trend",
            "structure": "structure",
            "detail": "detail",
        }
        return mapping.get(draft.get("analysis_type"), draft.get("analysis_type") or "kpi")

    def _force_ascending(self, sql: str) -> str:
        return sql.replace(" DESC LIMIT", " ASC LIMIT")

    def _replace_limit(self, sql: str, limit: int) -> str:
        import re

        safe_limit = max(1, min(limit, 100))
        if re.search(r"LIMIT\s+\d+", sql, flags=re.IGNORECASE):
            return re.sub(r"LIMIT\s+\d+", f"LIMIT {safe_limit}", sql, flags=re.IGNORECASE)
        return f"{sql.rstrip()} LIMIT {safe_limit}"

    def _find_chart(self, context: BuilderContext, chart_id: Optional[str]) -> Optional[Dict[str, Any]]:
        for chart in context.charts:
            if chart.get("id") == chart_id:
                return chart
        return None

    def _find_category(self, context: BuilderContext, category_id: Optional[str]) -> Optional[Dict[str, Any]]:
        for category in context.categories:
            if category.get("id") == category_id:
                return category
        return None
