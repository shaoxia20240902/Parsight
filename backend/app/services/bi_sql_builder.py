"""将业务问题编译为 metric_spec 并生成 MySQL SQL。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.services.bi_profiler import numeric_expr, quote_ident, safe_alias


SQL_TEMPLATE_KEYS = {
    "kpi", "trend", "growth_rate", "mom", "yoy", "share", "structure",
    "ranking", "target_achievement", "derived_kpi", "anomaly_list", "detail",
    "distribution", "funnel", "cohort",
}


def resolve_sql_template(question: Dict[str, Any]) -> str:
    """
    将自由的 analysis_type 映射为 SQL 模板键。
    优先 sql_template_hint，其次关键词推断，默认可聚合 KPI。
    """
    hint = (question.get("sql_template_hint") or "").strip().lower()
    if hint in SQL_TEMPLATE_KEYS:
        return hint

    raw = (question.get("analysis_type") or "").strip().lower()
    if raw in SQL_TEMPLATE_KEYS:
        return raw

    intent = " ".join([
        question.get("analysis_intent") or "",
        question.get("user_intent") or "",
        question.get("question") or "",
        raw,
    ]).lower()

    rules = [
        (("环比", "mom", "month_over_month", "上月"), "mom"),
        (("同比", "yoy", "year_over_year", "去年同"), "yoy"),
        (("趋势", "走势", "trend", "时间序列", "按月", "逐月"), "trend"),
        (("增速", "增长率", "growth"), "growth_rate"),
        (("占比", "份额", "share", "比例", "结构"), "structure"),
        (("排名", "top", "bottom", "ranking"), "ranking"),
        (("达成", "目标", "预算", "完成率", "achievement"), "target_achievement"),
        (("异常", "下滑", "跌幅", "预警", "anomaly"), "anomaly_list"),
        (("明细", "清单", "detail", "列表"), "detail"),
        (("留存", "复购", "cohort", "漏斗", "funnel"), "derived_kpi"),
    ]
    for keywords, template in rules:
        if any(k in intent for k in keywords):
            return template
    return "kpi"


class MetricSpecCompiler:
    def compile(
        self,
        profile: Dict[str, Any],
        question: Dict[str, Any],
        scenario: Dict[str, Any] | None = None,
        perspective: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        analysis_type_business = (question.get("analysis_type") or "business_metric").strip()
        sql_template = resolve_sql_template(question)

        metrics = self._resolve_fields(profile, question.get("metrics") or [], "metric")
        dimensions = self._resolve_fields(profile, question.get("dimensions") or [], "dimension")
        time_field = self._resolve_time_field(profile, question.get("time_field"))

        spec: Dict[str, Any] = {
            "analysis_type": sql_template,
            "analysis_type_business": analysis_type_business,
            "analysis_intent": question.get("analysis_intent") or "",
            "sql_template_hint": question.get("sql_template_hint"),
            "table_name": profile["table_name"],
            "metrics": metrics,
            "dimensions": dimensions,
            "time_field": time_field,
            "scenario_context": (scenario or {}).get("scenario_context") or "",
            "role_name": (perspective or {}).get("role_name") or "",
            "question": question.get("question") or "",
            "derived_kpi_hint": question.get("derived_kpi_hint"),
        }
        return spec

    def _resolve_fields(self, profile: Dict[str, Any], names: List[str], role: str) -> List[Dict[str, Any]]:
        by_name = {f["field"]: f for f in profile.get("fields", [])}
        out = []
        for name in names:
            if name in by_name and by_name[name].get("data_role") == role:
                out.append({"field": name, "label": name})
            elif name in by_name and role == "metric" and by_name[name].get("data_role") == "metric":
                out.append({"field": name, "label": name})
        if not out and role == "metric":
            for f in profile.get("fields", []):
                if f.get("data_role") == "metric":
                    out.append({"field": f["field"], "label": f["field"]})
                    break
        if not out and role == "dimension":
            for f in profile.get("fields", []):
                if f.get("data_role") == "dimension" and f.get("groupable"):
                    out.append({"field": f["field"], "label": f["field"]})
                    break
        return out

    def _resolve_time_field(self, profile: Dict[str, Any], name: Optional[str]) -> Optional[Dict[str, Any]]:
        if name:
            for f in profile.get("fields", []):
                if f["field"] == name and f.get("data_role") == "time":
                    return {"field": name, "label": name}
        for f in profile.get("fields", []):
            if f.get("data_role") == "time":
                return {"field": f["field"], "label": f["field"]}
        return None


class BISQLBuilder:
    def build(self, spec: Dict[str, Any], profile: Dict[str, Any]) -> Tuple[str, Optional[str], str]:
        """返回 (sql, summary_sql, chart_type)。"""
        analysis_type = spec["analysis_type"]
        table = quote_ident(spec["table_name"])
        time_cov = profile.get("time_coverage") or {}

        if analysis_type == "kpi":
            return self._kpi_sql(spec, table)
        if analysis_type in ("trend", "growth_rate"):
            return self._trend_sql(spec, table, growth=(analysis_type == "growth_rate"))
        if analysis_type == "mom":
            return self._period_compare_sql(spec, profile, table, mode="mom")
        if analysis_type == "yoy":
            return self._period_compare_sql(spec, profile, table, mode="yoy")
        if analysis_type in ("share", "structure", "ranking"):
            return self._dimension_agg_sql(spec, table, with_share=(analysis_type in ("share", "structure")))
        if analysis_type == "target_achievement":
            return self._achievement_sql(spec, profile, table)
        if analysis_type == "detail":
            return self._detail_sql(table), None, "table"
        if analysis_type == "anomaly_list":
            return self._ranking_sql(spec, table, ascending=True)
        if analysis_type == "derived_kpi":
            hint = (spec.get("derived_kpi_hint") or "").lower()
            if "客单" in hint or "单价" in hint:
                return self._avg_order_sql(spec, profile, table)
        return self._kpi_sql(spec, table)

    def _kpi_sql(self, spec: Dict[str, Any], table: str) -> Tuple[str, Optional[str], str]:
        metric = spec["metrics"][0] if spec["metrics"] else {"field": "*", "label": "记录数"}
        if metric["field"] == "*":
            sql = f"SELECT COUNT(*) AS `记录数` FROM {table}"
            return sql, sql, "kpi"
        expr = numeric_expr(metric["field"])
        label = safe_alias(metric.get("label") or metric["field"])
        sql = f"SELECT SUM({expr}) AS `{label}` FROM {table}"
        return sql, sql, "kpi"

    def _trend_sql(self, spec: Dict[str, Any], table: str, growth: bool = False) -> Tuple[str, Optional[str], str]:
        if not spec.get("time_field") or not spec.get("metrics"):
            raise ValueError("趋势分析需要时间字段和指标字段")
        tf = spec["time_field"]["field"]
        metric = spec["metrics"][0]
        expr = numeric_expr(metric["field"])
        bucket = self._time_bucket(tf)
        sql = (
            f"SELECT {bucket} AS `时间`, SUM({expr}) AS `{safe_alias(metric['label'])}` "
            f"FROM {table} WHERE {quote_ident(tf)} IS NOT NULL AND {quote_ident(tf)} <> '' "
            f"GROUP BY {bucket} ORDER BY `时间` ASC LIMIT 24"
        )
        return sql, None, "line"

    def _period_compare_sql(
        self, spec: Dict[str, Any], profile: Dict[str, Any], table: str, mode: str
    ) -> Tuple[str, Optional[str], str]:
        if not spec.get("time_field") or not spec.get("metrics"):
            raise ValueError("周期对比需要时间字段和指标字段")
        period_count = int((profile.get("time_coverage") or {}).get("period_count") or 0)
        if mode == "mom" and period_count < 2:
            raise ValueError("时间周期不足，无法计算环比")
        if mode == "yoy" and period_count < 13:
            raise ValueError("时间跨度不足，无法计算同比")
        tf = spec["time_field"]["field"]
        metric = spec["metrics"][0]
        expr = numeric_expr(metric["field"])
        bucket = self._time_bucket(tf)
        label = safe_alias(metric["label"])
        lag_n = 1 if mode == "mom" else 12
        sql = f"""
WITH monthly AS (
  SELECT {bucket} AS period, SUM({expr}) AS value
  FROM {table}
  WHERE {quote_ident(tf)} IS NOT NULL AND {quote_ident(tf)} <> ''
  GROUP BY period
),
ranked AS (
  SELECT period, value, LAG(value, {lag_n}) OVER (ORDER BY period) AS prev_value
  FROM monthly
)
SELECT period AS `当前周期`, value AS `{label}`,
  prev_value AS `上期值`,
  ROUND((value - prev_value) / NULLIF(prev_value, 0) * 100, 2) AS `变化率`
FROM ranked
ORDER BY period DESC
LIMIT 3
""".strip()
        summary = f"SELECT SUM({expr}) AS `总计` FROM {table}"
        return sql, summary, "kpi"

    def _dimension_agg_sql(
        self, spec: Dict[str, Any], table: str, with_share: bool = False
    ) -> Tuple[str, Optional[str], str]:
        if not spec.get("metrics") or not spec.get("dimensions"):
            raise ValueError("结构分析需要维度和指标")
        dim = spec["dimensions"][0]
        metric = spec["metrics"][0]
        expr = numeric_expr(metric["field"])
        dim_ident = quote_ident(dim["field"])
        dim_label = safe_alias(dim["label"])
        metric_label = safe_alias(metric["label"])
        share_col = ""
        if with_share:
            share_col = (
                f", ROUND(SUM({expr}) / NULLIF((SELECT SUM({expr}) FROM {table}), 0) * 100, 2) AS `占比`"
            )
        sql = (
            f"SELECT {dim_ident} AS `{dim_label}`, SUM({expr}) AS `{metric_label}`{share_col} "
            f"FROM {table} WHERE {dim_ident} IS NOT NULL AND {dim_ident} <> '' "
            f"GROUP BY {dim_ident} ORDER BY `{metric_label}` DESC LIMIT 10"
        )
        summary = f"SELECT SUM({expr}) AS `总{metric_label}` FROM {table}"
        chart = "pie" if with_share else "bar"
        return sql, summary, chart

    def _ranking_sql(
        self, spec: Dict[str, Any], table: str, ascending: bool = False
    ) -> Tuple[str, Optional[str], str]:
        if not spec.get("metrics") or not spec.get("dimensions"):
            raise ValueError("排名分析需要维度和指标")
        dim = spec["dimensions"][0]
        metric = spec["metrics"][0]
        expr = numeric_expr(metric["field"])
        order = "ASC" if ascending else "DESC"
        sql = (
            f"SELECT {quote_ident(dim['field'])} AS `{safe_alias(dim['label'])}`, "
            f"SUM({expr}) AS `{safe_alias(metric['label'])}` "
            f"FROM {table} WHERE {quote_ident(dim['field'])} IS NOT NULL "
            f"GROUP BY {quote_ident(dim['field'])} ORDER BY `{safe_alias(metric['label'])}` {order} LIMIT 10"
        )
        return sql, None, "bar"

    def _achievement_sql(
        self, spec: Dict[str, Any], profile: Dict[str, Any], table: str
    ) -> Tuple[str, Optional[str], str]:
        actual, target = self._find_target_pair(profile)
        if not actual or not target:
            raise ValueError("达成率需要实际与目标字段")
        a_expr = numeric_expr(actual["field"])
        t_expr = numeric_expr(target["field"])
        sql = (
            f"SELECT ROUND(SUM({a_expr}) / NULLIF(SUM({t_expr}), 0) * 100, 2) AS `达成率` FROM {table}"
        )
        return sql, None, "kpi"

    def _avg_order_sql(
        self, spec: Dict[str, Any], profile: Dict[str, Any], table: str
    ) -> Tuple[str, Optional[str], str]:
        metrics = [f for f in profile.get("fields", []) if f.get("data_role") == "metric"]
        amount = next((m for m in metrics if "金额" in m["field"] or "sales" in m["field"].lower()), metrics[0] if metrics else None)
        if not amount:
            raise ValueError("无法推导客单价：缺少金额类指标")
        expr = numeric_expr(amount["field"])
        sql = f"SELECT ROUND(SUM({expr}) / NULLIF(COUNT(*), 0), 2) AS `客单价` FROM {table}"
        return sql, None, "kpi"

    def _detail_sql(self, table: str) -> str:
        return f"SELECT * FROM {table} LIMIT 100"

    def _time_bucket(self, field: str) -> str:
        return f"DATE_FORMAT({quote_ident(field)}, '%Y-%m')"

    def _find_target_pair(self, profile: Dict[str, Any]):
        metrics = [f for f in profile.get("fields", []) if f.get("data_role") == "metric"]
        targets = [m for m in metrics if any(k in m["field"].lower() for k in ("目标", "预算", "target", "budget"))]
        actuals = [m for m in metrics if m not in targets]
        if targets and actuals:
            return actuals[0], targets[0]
        return None, None


def inject_period_count(spec: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
    spec = dict(spec)
    spec["_period_count"] = int((profile.get("time_coverage") or {}).get("period_count") or 0)
    return spec
