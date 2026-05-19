"""
BI 看板生成 v3：理解门禁 → 行业推断 → 总览 → 角色→场景→问题→审视 → SQL+单次修复。
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any, Dict, List, Optional, Tuple

from app.agents.bi_pipeline_agents import BIChartRepairAgent, BIChartSQLAgent, BIIndustryInferenceAgent
from app.services.bi_blueprint_pipeline import BIBlueprintPipeline
from app.services.bi_context import file_payload_for_industry, full_field_profiles, sheet_payload_for_llm
from app.services.bi_planner import BIPlanner
from app.services.bi_profiler import BIProfiler, numeric_expr, quote_ident, safe_alias
from app.services.bi_sql_builder import BISQLBuilder, MetricSpecCompiler
from app.services.bi_understanding_gate import check_understanding_ready, resolve_understanding_text
from app.services.bi_thinking_journal import BIThinkingJournal
from app.services.bi_pipeline_logger import (
    BIPipelineRunContext,
    STEP_CHART_DROPPED,
    STEP_COMPILE_SQL,
    STEP_GENERATE_END,
    STEP_GENERATE_START,
    STEP_INDUSTRY,
    STEP_REPAIR,
    STEP_SHEET_PIPELINE,
    STEP_SQL_PREVIEW,
    log_step_error,
    log_step_ok,
    log_step_warn,
)
from app.services.db_service import DBService
from app.utils.sql_validator import SQLValidator

logger = logging.getLogger(__name__)


class BIChartTypeResolver:
    """Turns question/spec intent into a renderable chart contract."""

    VALID_TYPES = {"kpi_group", "bar", "line", "pie", "combo", "ranking", "table", "detail_table"}

    def resolve(
        self,
        spec: Dict[str, Any],
        profile: Dict[str, Any],
        default_chart_type: str,
        sql: str,
        summary_sql: Optional[str],
    ) -> Tuple[str, str, Optional[str], Dict[str, Any], str]:
        metrics = spec.get("metrics") or []
        dimensions = spec.get("dimensions") or []
        time_field = spec.get("time_field")
        analysis_type = spec.get("analysis_type") or ""
        visual_intent = spec.get("visual_intent") or ""

        chart_type = default_chart_type if default_chart_type in self.VALID_TYPES else "bar"
        intent_type = visual_intent or analysis_type or "business_analysis"

        if analysis_type in {"detail", "anomaly_list"} or visual_intent == "detail_list":
            chart_type = "detail_table"
        elif analysis_type == "ranking" or visual_intent == "ranking":
            chart_type = "ranking"
        elif analysis_type in {"share", "structure"} or visual_intent == "share_structure":
            chart_type = "pie"
        elif analysis_type in {"trend", "growth_rate"} or visual_intent in {"time_trend", "time_structure_trend"}:
            chart_type = "line"
        elif self._needs_combo(metrics, spec):
            chart_type = "combo"

        if chart_type == "combo":
            sql = self._combo_sql(spec, profile) or sql
        encoding = self._encoding(chart_type, spec, profile)
        return chart_type, sql, summary_sql, encoding, intent_type

    def is_rate_field(self, field: str) -> bool:
        text = str(field).lower()
        return any(k in text for k in ("率", "占比", "比例", "percent", "percentage", "rate", "ratio", "margin"))

    def _needs_combo(self, metrics: List[Dict[str, Any]], spec: Dict[str, Any]) -> bool:
        preferred = spec.get("preferred_chart_types") or []
        if len(metrics) < 2:
            return False
        if "combo" in preferred:
            return True
        has_rate = any(self.is_rate_field(m.get("field") or m.get("label", "")) for m in metrics)
        has_value = any(not self.is_rate_field(m.get("field") or m.get("label", "")) for m in metrics)
        return has_rate and has_value

    def _encoding(self, chart_type: str, spec: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
        metrics = spec.get("metrics") or []
        dimensions = spec.get("dimensions") or []
        time_field = spec.get("time_field")
        x_field = time_field or (dimensions[0] if dimensions else None)
        encoding: Dict[str, Any] = {}
        if x_field:
            encoding["x"] = {
                "field": x_field["field"],
                "label": x_field.get("label") or x_field["field"],
                "role": "time" if time_field and x_field["field"] == time_field["field"] else "dimension",
            }
        y_items = []
        for idx, metric in enumerate(metrics[:4]):
            label = metric.get("label") or metric.get("field")
            is_rate = self.is_rate_field(label)
            y_items.append({
                "field": label,
                "label": label,
                "axis": "right" if chart_type == "combo" and is_rate else "left",
                "series_type": "line" if chart_type == "combo" and is_rate else ("line" if chart_type == "line" else "bar"),
                "format": "percent" if is_rate else "number",
            })
        if y_items:
            encoding["y"] = y_items
        if chart_type == "pie" and len(metrics) == 1:
            encoding["share"] = {"field": "占比", "label": "占比", "format": "percent"}
        if chart_type == "ranking" and metrics:
            encoding["sort"] = {"field": metrics[0].get("label") or metrics[0].get("field"), "direction": "desc"}
            encoding["limit"] = 10
        return encoding

    def _combo_sql(self, spec: Dict[str, Any], profile: Dict[str, Any]) -> Optional[str]:
        metrics = spec.get("metrics") or []
        dimensions = spec.get("dimensions") or []
        time_field = spec.get("time_field")
        x = time_field or (dimensions[0] if dimensions else None)
        if not x or len(metrics) < 2:
            return None
        table = quote_ident(spec["table_name"])
        x_expr = (
            f"DATE_FORMAT({quote_ident(x['field'])}, '%Y-%m')"
            if time_field and x["field"] == time_field["field"]
            else quote_ident(x["field"])
        )
        select_parts = [f"{x_expr} AS `{safe_alias(x.get('label') or x['field'])}`"]
        for metric in metrics[:2]:
            expr = numeric_expr(metric["field"])
            alias = safe_alias(metric.get("label") or metric["field"])
            if self.is_rate_field(alias):
                select_parts.append(f"ROUND(AVG({expr}), 0) AS `{alias}`")
            else:
                select_parts.append(f"SUM({expr}) AS `{alias}`")
        where = f"WHERE {quote_ident(x['field'])} IS NOT NULL AND {quote_ident(x['field'])} <> ''"
        order_alias = safe_alias(metrics[0].get("label") or metrics[0]["field"])
        order = f"`{safe_alias(x.get('label') or x['field'])}` ASC" if time_field else f"`{order_alias}` DESC"
        return (
            f"SELECT {', '.join(select_parts)} FROM {table} {where} "
            f"GROUP BY {x_expr} ORDER BY {order} LIMIT 10"
        )


class BIBusinessGenerator:
    MAX_WAREHOUSE = 50
    MAX_BOARD_PER_CATEGORY = 8

    def __init__(self, db_service: DBService, concurrency: int = 4):
        self.db = db_service
        self.profiler = BIProfiler(db_service)
        self.planner = BIPlanner()
        self.industry_agent = BIIndustryInferenceAgent()
        self.blueprint_pipeline = BIBlueprintPipeline(concurrency=concurrency)
        self.repair_agent = BIChartRepairAgent()
        self.sql_agent = BIChartSQLAgent()
        self.spec_compiler = MetricSpecCompiler()
        self.sql_builder = BISQLBuilder()
        self.chart_resolver = BIChartTypeResolver()
        self.sem = asyncio.Semaphore(concurrency)
        self.chart_draft_sem = asyncio.Semaphore(concurrency)

    async def generate(
        self,
        file_id: str,
        sheets_data: Optional[List[Dict[str, Any]]] = None,
        *,
        on_thinking_entry: Optional[Any] = None,
    ) -> Dict[str, Any]:
        run_ctx = BIPipelineRunContext(file_id)
        journal = BIThinkingJournal(file_id, run_ctx.run_id)
        run_ctx.journal = journal
        if on_thinking_entry:
            run_ctx.persist_journal_entry = on_thinking_entry
        log_step_ok(
            STEP_GENERATE_START,
            f"开始 BI 生成，sheet 数待加载",
            run_ctx=run_ctx,
            extra={"file_id": file_id},
        )

        ready, pending = await check_understanding_ready(self.db, file_id)
        if not ready:
            tables = [p["table_name"] for p in pending]
            log_step_error(
                "understanding_gate",
                "六维理解未就绪，生成中止",
                run_ctx=run_ctx,
                extra={"pending_tables": tables, "pending": pending},
            )
            raise UnderstandingNotReadyError(tables, pending)

        if sheets_data is None:
            sheets_data = await self._load_sheets_data(file_id)

        profiles = []
        for sheet in sheets_data:
            profiles.append(await self.profiler.profile_sheet(sheet))
        sheet_by_table = {s["table_name"]: s for s in sheets_data}
        understanding_map = {}
        for sheet in sheets_data:
            text = await resolve_understanding_text(self.db, sheet["table_name"])
            if not text:
                raise UnderstandingNotReadyError([sheet["table_name"]], [])
            understanding_map[sheet["table_name"]] = text
            for p in profiles:
                if p["table_name"] == sheet["table_name"]:
                    p["understanding_text"] = text
                    src = sheet_by_table.get(sheet["table_name"], {})
                    p["key_dimensions"] = src.get("key_dimensions") or []
                    p["key_metrics"] = src.get("key_metrics") or []
                    p["data_granularity"] = src.get("data_granularity") or ""
                    p["time_range"] = src.get("time_range") or ""

        try:
            industry_result = await self.industry_agent.run({
                "file_payload": file_payload_for_industry(profiles, understanding_map),
            })
        except Exception as e:
            log_step_error(
                STEP_INDUSTRY,
                "行业推断失败",
                run_ctx=run_ctx,
                exc=e,
                extra={"sheet_count": len(profiles)},
            )
            raise
        industry_guess = industry_result.get("industry_guess", {})
        log_step_ok(
            STEP_INDUSTRY,
            f"行业推断完成: {industry_guess.get('primary', 'unknown')}",
            run_ctx=run_ctx,
            extra={"industry_guess": industry_guess, "file_summary": industry_result.get("file_summary")},
        )

        relationships = await self.profiler.detect_relationships(profiles)
        filter_candidates = self.profiler.build_filter_candidates(profiles)
        sheet_plan = await self.planner.plan_sheet_categories(
            profiles, filter_candidates, understanding_map
        )
        global_filters = await self._hydrate_filter_options(
            self._apply_filter_plan(filter_candidates, sheet_plan.get("global_filter_labels", []))
        )
        categories = self._build_sheet_categories(profiles, sheet_plan)

        charts_dropped: List[Dict[str, Any]] = []
        sheet_errors: List[Dict[str, Any]] = []
        all_charts: List[Dict[str, Any]] = []

        async def _run_sheet(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
            try:
                return await self._limited(self._generate_sheet_pipeline(
                    profile,
                    understanding_map[profile["table_name"]],
                    industry_guess,
                    charts_dropped,
                    run_ctx,
                ))
            except Exception as e:
                log_step_error(
                    STEP_SHEET_PIPELINE,
                    "单 Sheet 流水线失败，已跳过该 Sheet",
                    run_ctx=run_ctx,
                    table_name=profile.get("table_name"),
                    sheet_name=profile.get("sheet_name"),
                    exc=e,
                )
                sheet_errors.append({
                    "table_name": profile.get("table_name"),
                    "sheet_name": profile.get("sheet_name"),
                    "error": str(e),
                })
                return []

        sheet_chart_groups = await asyncio.gather(*[_run_sheet(p) for p in profiles])
        for group in sheet_chart_groups:
            all_charts.extend(group)

        relation_categories: List[Dict[str, Any]] = []
        if relationships:
            custom_plan = await self.planner.plan_custom_categories(
                relationships, profiles, understanding_map
            )
            relation_categories, relation_charts = await self._generate_relation_categories(
                relationships, profiles, global_filters, custom_plan, charts_dropped,
            )
            categories.extend(relation_categories)
            all_charts.extend(relation_charts)

        # 并发执行图表 SQL 预览与修复（受信号量限制并发数）
        chart_results = await asyncio.gather(*[
            self._limited(
                self._execute_chart_with_repair(chart, profiles, understanding_map, charts_dropped, run_ctx)
            )
            for chart in all_charts
        ])
        valid_charts = [r for r in chart_results if r]

        valid_charts = self._rank_and_layout(valid_charts)
        valid_charts = self._limit_warehouse_balanced(valid_charts)

        log_step_ok(
            STEP_GENERATE_END,
            "BI 生成完成",
            run_ctx=run_ctx,
            extra={
                "sheet_count": len(profiles),
                "chart_count": len(valid_charts),
                "charts_dropped_count": len(charts_dropped),
                "sheet_errors_count": len(sheet_errors),
                "relationship_count": len(relationships),
            },
        )

        return {
            "version": 3,
            "file_id": file_id,
            "dialect": "mysql",
            "industry_guess": industry_guess,
            "categories": categories,
            "custom_categories": relation_categories,
            "global_filters": global_filters,
            "charts": valid_charts,
            "relationships": relationships,
            "generation_report": {
                "sheet_count": len(profiles),
                "relationship_count": len(relationships),
                "chart_count": len(valid_charts),
                "strategy": "v3_stepped_blueprint_repair",
                "pipeline_run_id": run_ctx.run_id,
                "max_board_per_category": self.MAX_BOARD_PER_CATEGORY,
                "max_warehouse": self.MAX_WAREHOUSE,
                "sheet_plan_warnings": sheet_plan.get("warnings", []),
                "sheet_errors": sheet_errors,
                "charts_dropped": charts_dropped,
                "thinking_entry_count": len(journal.entries),
            },
            "thinking_journal": journal.to_list(),
        }

    async def _generate_sheet_pipeline(
        self,
        profile: Dict[str, Any],
        understanding_text: str,
        industry_guess: Dict[str, Any],
        charts_dropped: List[Dict[str, Any]],
        run_ctx: BIPipelineRunContext,
    ) -> List[Dict[str, Any]]:
        category_id = self._category_id_for(profile)
        table_name = profile.get("table_name", "")
        sheet_name = profile.get("sheet_name", "")
        charts: List[Dict[str, Any]] = []

        log_step_ok(
            STEP_SHEET_PIPELINE,
            "开始单 Sheet 流水线",
            run_ctx=run_ctx,
            table_name=table_name,
            sheet_name=sheet_name,
        )

        charts.extend(self._build_summary_charts(profile, category_id))

        try:
            blueprint = await self.blueprint_pipeline.run(
                profile, understanding_text, industry_guess, run_ctx=run_ctx,
            )
        except Exception as e:
            log_step_warn(
                STEP_SHEET_PIPELINE,
                "蓝图生成失败，保留 Sheet 总览图并继续",
                run_ctx=run_ctx,
                table_name=table_name,
                sheet_name=sheet_name,
                exc=e,
            )
            return charts

        question_contexts = [
            (perspective, scenario, question)
            for perspective in blueprint.get("perspectives", [])
            for scenario in perspective.get("scenarios", [])
            for question in scenario.get("questions", [])
        ]
        chart_drafts = await asyncio.gather(*[
            self._limited_chart_draft(
                self._question_to_chart_draft(
                    profile, category_id, perspective, scenario, question, run_ctx,
                    understanding_text, industry_guess,
                )
            )
            for perspective, scenario, question in question_contexts
        ])
        charts.extend([chart for chart in chart_drafts if chart])

        log_step_ok(
            STEP_SHEET_PIPELINE,
            f"单 Sheet 流水线结束，产出 {len(charts)} 张图草稿",
            run_ctx=run_ctx,
            table_name=table_name,
            sheet_name=sheet_name,
            extra={
                "blueprint_warnings": blueprint.get("warnings"),
                "selected_question_count": len(question_contexts),
            },
        )
        return charts

    async def _question_to_chart_draft(
        self,
        profile: Dict[str, Any],
        category_id: str,
        perspective: Dict[str, Any],
        scenario: Dict[str, Any],
        question: Dict[str, Any],
        run_ctx: BIPipelineRunContext,
        understanding_text: str,
        industry_guess: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        qid = question.get("question_id")
        try:
            spec = self.spec_compiler.compile(profile, question, scenario, perspective)
            spec = self._apply_analysis_guards(spec, profile, question)
            template_sql, template_summary_sql, template_chart_type = self.sql_builder.build(spec, profile)
            chart_type, sql, summary_sql, encoding, intent_type = await self._generate_sql_with_llm(
                profile,
                understanding_text,
                industry_guess,
                perspective,
                scenario,
                question,
                spec,
                template_sql,
                template_summary_sql,
                template_chart_type,
                run_ctx,
            )
        except ValueError as e:
            logger.info("跳过问题（无法编译 SQL）: %s — %s", qid, e)
            log_step_warn(
                STEP_COMPILE_SQL,
                f"问题无法编译 SQL，已跳过: {e}",
                run_ctx=run_ctx,
                table_name=profile.get("table_name"),
                sheet_name=profile.get("sheet_name"),
                perspective_id=perspective.get("perspective_id"),
                role_name=perspective.get("role_name"),
                scenario_id=scenario.get("scenario_id"),
                scenario_name=scenario.get("scenario_name"),
                question_id=qid,
                exc=e,
                extra={
                    "question": question.get("question"),
                    "analysis_type": question.get("analysis_type"),
                    "metrics": question.get("metrics"),
                    "dimensions": question.get("dimensions"),
                },
            )
            return None

        title = question.get("title") or question.get("question", "")[:40]
        qtext = question.get("question", "")
        metric = spec["metrics"][0] if spec.get("metrics") else {"field": "*", "label": "记录数"}
        dims = [d["field"] for d in spec.get("dimensions", [])]
        time_field = spec["time_field"]["field"] if spec.get("time_field") else None

        chart = self._chart(
            profile, category_id,
            chart_type,
            title[:80], qtext, sql, metric, dims, time_field,
            int(question.get("priority") or 80),
            summary_sql=summary_sql,
            layer="role_analysis",
        )
        chart.update({
            "perspective_id": perspective.get("perspective_id"),
            "role_name": perspective.get("role_name"),
            "scenario_id": scenario.get("scenario_id"),
            "scenario_name": scenario.get("scenario_name"),
            "scenario_context": scenario.get("scenario_context"),
            "question_id": question.get("question_id"),
            "analysis_type": spec.get("analysis_type_business") or spec.get("analysis_type"),
            "analysis_intent": spec.get("analysis_intent"),
            "intent_type": intent_type,
            "visual_intent": spec.get("visual_intent"),
            "field_display_policy": spec.get("field_display_policy"),
            "required_fields": spec.get("required_fields"),
            "encoding": encoding,
            "sql_source": "llm_sql",
            "metric_spec": spec,
            "from_review": bool(question.get("from_review")),
        })
        return chart

    async def _generate_sql_with_llm(
        self,
        profile: Dict[str, Any],
        understanding_text: str,
        industry_guess: Dict[str, Any],
        perspective: Dict[str, Any],
        scenario: Dict[str, Any],
        question: Dict[str, Any],
        spec: Dict[str, Any],
        template_sql: str,
        template_summary_sql: Optional[str],
        template_chart_type: str,
        run_ctx: BIPipelineRunContext,
    ) -> Tuple[str, str, Optional[str], Dict[str, Any], str]:
        fallback = self.chart_resolver.resolve(
            spec, profile, template_chart_type, template_sql, template_summary_sql,
        )
        if self._can_use_template_sql(spec, fallback[0]):
            log_step_ok(
                STEP_COMPILE_SQL,
                "模板 SQL 生成完成，跳过 SQL LLM",
                run_ctx=run_ctx,
                table_name=profile.get("table_name"),
                sheet_name=profile.get("sheet_name"),
                perspective_id=perspective.get("perspective_id"),
                role_name=perspective.get("role_name"),
                scenario_id=scenario.get("scenario_id"),
                scenario_name=scenario.get("scenario_name"),
                question_id=question.get("question_id"),
                extra={
                    "chart_type": fallback[0],
                    "intent_type": fallback[4],
                    "sql_preview": fallback[1][:600],
                    "summary_sql_preview": fallback[2][:400] if fallback[2] else None,
                    "sql_source": "template_sql",
                },
            )
            return fallback
        try:
            result = await self.sql_agent.run({
                "question": question,
                "metric_spec": spec,
                "scenario_context": scenario.get("scenario_context", ""),
                "role_name": perspective.get("role_name", ""),
                "sheet_payload": sheet_payload_for_llm(profile, understanding_text, industry_guess),
                "chart_type_hint": fallback[0],
                "template_sql_fallback": template_sql,
            })
            sql = SQLValidator.sanitize_sql(result.get("sql", ""))
            if not sql:
                raise ValueError("LLM SQL 未通过安全校验")
            summary_sql = result.get("summary_sql")
            if summary_sql:
                summary_sql = SQLValidator.sanitize_sql(summary_sql)
                if not summary_sql:
                    summary_sql = None
            chart_type = result.get("chart_type") or fallback[0]
            if chart_type not in self.chart_resolver.VALID_TYPES:
                chart_type = fallback[0]
            encoding = result.get("encoding") or fallback[3]
            intent_type = result.get("intent_type") or fallback[4]
            log_step_ok(
                STEP_COMPILE_SQL,
                "LLM SQL 生成完成",
                run_ctx=run_ctx,
                table_name=profile.get("table_name"),
                sheet_name=profile.get("sheet_name"),
                perspective_id=perspective.get("perspective_id"),
                role_name=perspective.get("role_name"),
                scenario_id=scenario.get("scenario_id"),
                scenario_name=scenario.get("scenario_name"),
                question_id=question.get("question_id"),
                extra={
                    "chart_type": chart_type,
                    "intent_type": intent_type,
                    "calculation_note": result.get("calculation_note"),
                    "sql_preview": sql[:600],
                    "summary_sql_preview": summary_sql[:400] if summary_sql else None,
                },
            )
            return chart_type, sql, summary_sql, encoding, intent_type
        except Exception as e:
            log_step_warn(
                STEP_COMPILE_SQL,
                f"LLM SQL 生成失败，回退模板 SQL: {e}",
                run_ctx=run_ctx,
                table_name=profile.get("table_name"),
                sheet_name=profile.get("sheet_name"),
                question_id=question.get("question_id"),
                exc=e,
                extra={"question": question.get("question"), "template_sql": template_sql[:500]},
            )
            return fallback

    def _can_use_template_sql(self, spec: Dict[str, Any], chart_type: str) -> bool:
        analysis_type = spec.get("analysis_type")
        if spec.get("derived_kpi_hint") or analysis_type in {"derived_kpi", "target_achievement", "funnel", "cohort"}:
            return False
        if chart_type == "combo":
            return False
        return analysis_type in {
            "kpi",
            "trend",
            "growth_rate",
            "share",
            "structure",
            "ranking",
            "detail",
            "anomaly_list",
        }

    def _apply_analysis_guards(
        self, spec: Dict[str, Any], profile: Dict[str, Any], question: Dict[str, Any]
    ) -> Dict[str, Any]:
        tc = profile.get("time_coverage") or {}
        pc = int(tc.get("period_count") or 0)
        at = spec.get("analysis_type")
        if at == "mom" and pc < 2:
            spec = dict(spec)
            spec["analysis_type"] = "trend"
        if at == "yoy" and pc < 13:
            spec = dict(spec)
            spec["analysis_type"] = "trend"
        return spec

    async def _execute_chart_with_repair(
        self,
        chart: Dict[str, Any],
        profiles: List[Dict[str, Any]],
        understanding_map: Dict[str, str],
        charts_dropped: List[Dict[str, Any]],
        run_ctx: BIPipelineRunContext,
    ) -> Optional[Dict[str, Any]]:
        profile = next((p for p in profiles if p["table_name"] == chart["table_name"]), None)
        if not profile:
            return None

        failure_type, error_message = await self._try_preview(chart, run_ctx)
        if failure_type is None:
            return chart

        log_step_warn(
            STEP_SQL_PREVIEW,
            f"图表预览失败，进入修复: {failure_type}",
            run_ctx=run_ctx,
            table_name=chart.get("table_name"),
            chart_id=chart.get("id"),
            question_id=chart.get("question_id"),
            extra={"error_message": error_message, "sql_preview": (chart.get("sql") or "")[:500]},
        )

        repair_input = {
            "failure_type": failure_type,
            "error_message": error_message,
            "question": {
                "question_id": chart.get("question_id"),
                "question": chart.get("question"),
                "analysis_type": chart.get("analysis_type"),
                "metrics": chart.get("metric_spec", {}).get("metrics", []),
                "dimensions": chart.get("metric_spec", {}).get("dimensions", []),
            },
            "scenario_context": chart.get("scenario_context", ""),
            "metric_spec": chart.get("metric_spec", {}),
            "sql": chart.get("sql", ""),
            "understanding_content": understanding_map.get(chart["table_name"], ""),
            "fields": full_field_profiles(profile),
            "sheet_payload": sheet_payload_for_llm(
                profile,
                understanding_map.get(chart["table_name"], ""),
            ),
        }
        try:
            repair = await self.repair_agent.run(repair_input)
        except Exception as e:
            logger.warning("修复智能体失败: %s", e)
            log_step_error(
                STEP_REPAIR,
                "修复智能体调用失败",
                run_ctx=run_ctx,
                table_name=chart.get("table_name"),
                chart_id=chart.get("id"),
                question_id=chart.get("question_id"),
                exc=e,
            )
            self._record_drop(charts_dropped, chart, failure_type, str(e), False, run_ctx)
            return None

        log_step_ok(
            STEP_REPAIR,
            f"修复建议: {repair.get('repair_action')} — {repair.get('diagnosis')}",
            run_ctx=run_ctx,
            table_name=chart.get("table_name"),
            chart_id=chart.get("id"),
            question_id=chart.get("question_id"),
            extra={
                "diagnosis_reason": repair.get("diagnosis_reason"),
                "repair_action": repair.get("repair_action"),
            },
        )

        if repair.get("repair_action") == "fix_sql" and repair.get("revised_sql"):
            revised_sql = SQLValidator.sanitize_sql(repair["revised_sql"].strip())
            if not revised_sql:
                self._record_drop(
                    charts_dropped, chart, failure_type,
                    "修复 SQL 未通过安全校验", True, run_ctx, repair,
                )
                return None
            chart["sql"] = revised_sql
        elif repair.get("repair_action") == "fix_question":
            revised = dict(chart.get("metric_spec") or {})
            q_patch = {
                "question_id": chart.get("question_id"),
                "question": repair.get("revised_question") or chart.get("question"),
                "analysis_type": repair.get("revised_analysis_type") or chart.get("analysis_type"),
                "analysis_intent": repair.get("revised_analysis_intent") or chart.get("analysis_intent", ""),
                "visual_intent": repair.get("revised_visual_intent") or chart.get("visual_intent", ""),
                "sql_template_hint": repair.get("revised_sql_template_hint"),
                "metrics": [m.get("field") if isinstance(m, dict) else m for m in repair.get("revised_metrics", [])],
                "dimensions": [d.get("field") if isinstance(d, dict) else d for d in repair.get("revised_dimensions", [])],
                "time_field": repair.get("revised_time_field"),
                "preferred_chart_types": repair.get("revised_preferred_chart_types") or [],
                "field_display_policy": repair.get("revised_field_display_policy") or "",
                "required_fields": repair.get("revised_required_fields") or {},
            }
            scenario = {
                "scenario_context": chart.get("scenario_context", ""),
            }
            perspective = {"role_name": chart.get("role_name", "")}
            try:
                spec = self.spec_compiler.compile(profile, q_patch, scenario, perspective)
                sql, summary_sql, chart_type = self.sql_builder.build(spec, profile)
                chart_type, sql, summary_sql, encoding, intent_type = self.chart_resolver.resolve(
                    spec, profile, chart_type, sql, summary_sql,
                )
                chart["sql"] = sql
                chart["summary_sql"] = summary_sql
                chart["chart_type"] = chart_type
                chart["chartType"] = chart_type
                chart["encoding"] = encoding
                chart["intent_type"] = intent_type
                chart["question"] = q_patch["question"]
                chart["metric_spec"] = spec
            except ValueError as e:
                log_step_warn(
                    STEP_COMPILE_SQL,
                    f"修复后重新编译 SQL 失败: {e}",
                    run_ctx=run_ctx,
                    table_name=chart.get("table_name"),
                    chart_id=chart.get("id"),
                    question_id=chart.get("question_id"),
                    exc=e,
                )
                self._record_drop(charts_dropped, chart, failure_type, str(e), True, run_ctx, repair)
                return None
        else:
            self._record_drop(
                charts_dropped, chart, failure_type,
                repair.get("diagnosis_reason", ""), True, run_ctx, repair,
            )
            return None

        failure_type2, err2 = await self._try_preview(chart, run_ctx)
        if failure_type2 is None:
            log_step_ok(
                STEP_REPAIR,
                "修复后预览成功",
                run_ctx=run_ctx,
                table_name=chart.get("table_name"),
                chart_id=chart.get("id"),
                question_id=chart.get("question_id"),
            )
            return chart
        self._record_drop(charts_dropped, chart, failure_type2, err2, True, run_ctx, repair)
        return None

    async def _try_preview(
        self, chart: Dict[str, Any], run_ctx: Optional[BIPipelineRunContext] = None,
    ) -> Tuple[Optional[str], str]:
        try:
            rows = await self.db.execute_query(chart["sql"])
        except Exception as e:
            if run_ctx:
                log_step_warn(
                    STEP_SQL_PREVIEW,
                    f"SQL 执行异常: {e}",
                    run_ctx=run_ctx,
                    table_name=chart.get("table_name"),
                    chart_id=chart.get("id"),
                    question_id=chart.get("question_id"),
                    exc=e,
                    extra={"sql": (chart.get("sql") or "")[:800]},
                )
            return "sql_error", str(e)
        if not rows or self._rows_effectively_empty(rows):
            if run_ctx:
                log_step_warn(
                    STEP_SQL_PREVIEW,
                    "SQL 预执行结果为空",
                    run_ctx=run_ctx,
                    table_name=chart.get("table_name"),
                    chart_id=chart.get("id"),
                    question_id=chart.get("question_id"),
                    extra={"sql": (chart.get("sql") or "")[:800]},
                )
            return "empty_result", "查询结果为空"
        preview_rows = rows[:20]
        chart["preview"] = {"columns": list(preview_rows[0].keys()), "rows": preview_rows}
        chart["tablePreview"] = chart["preview"]
        comparison = {}
        if chart.get("summary_sql"):
            try:
                summary_rows = await self.db.execute_query(chart["summary_sql"])
                comparison = summary_rows[0] if summary_rows else {}
            except Exception:
                comparison = {}
        chart["comparison"] = comparison
        if run_ctx:
            log_step_ok(
                STEP_SQL_PREVIEW,
                "SQL 预执行通过",
                run_ctx=run_ctx,
                table_name=chart.get("table_name"),
                sheet_name=chart.get("sheet_name"),
                chart_id=chart.get("id"),
                question_id=chart.get("question_id"),
                extra={
                    "row_count": len(rows),
                    "columns": list(preview_rows[0].keys()),
                    "chart_type": chart.get("chart_type") or chart.get("chartType"),
                },
            )
        return None, ""

    def _rows_effectively_empty(self, rows: List[Dict[str, Any]]) -> bool:
        if not rows:
            return True
        for row in rows:
            if any(v is not None and str(v).strip() != "" for v in row.values()):
                return False
        return True

    def _record_drop(
        self,
        charts_dropped: List[Dict[str, Any]],
        chart: Dict[str, Any],
        failure_type: str,
        reason: str,
        repair_attempted: bool,
        run_ctx: BIPipelineRunContext,
        repair: Optional[Dict[str, Any]] = None,
    ) -> None:
        entry = {
            "chart_id": chart.get("id"),
            "question_id": chart.get("question_id"),
            "title": chart.get("title"),
            "table_name": chart.get("table_name"),
            "failure_type": failure_type,
            "diagnosis": (repair or {}).get("diagnosis"),
            "diagnosis_reason": reason or (repair or {}).get("diagnosis_reason"),
            "repair_attempted": repair_attempted,
            "final_status": "dropped_after_repair" if repair_attempted else "dropped",
        }
        charts_dropped.append(entry)
        log_step_warn(
            STEP_CHART_DROPPED,
            f"图表已丢弃: {failure_type} — {entry['diagnosis_reason']}",
            run_ctx=run_ctx,
            table_name=chart.get("table_name"),
            chart_id=chart.get("id"),
            question_id=chart.get("question_id"),
            extra={
                "failure_type": failure_type,
                "error_message": entry["diagnosis_reason"],
                "repair_attempted": repair_attempted,
                "role_name": chart.get("role_name"),
                "scenario_name": chart.get("scenario_name"),
                "analysis_type": chart.get("analysis_type"),
                "repair_diagnosis": (repair or {}).get("diagnosis"),
            },
        )

    def _build_summary_charts(self, profile: Dict[str, Any], category_id: str) -> List[Dict[str, Any]]:
        table_name = profile["table_name"]
        select_parts = ["COUNT(*) AS `记录数`"]
        items = [{"label": "记录数", "value_field": "记录数", "format": "integer"}]
        for metric in self._metric_fields(profile)[:4]:
            expr = numeric_expr(metric["field"])
            label = metric["label"]
            alias = safe_alias("总" + label)
            fmt = "percent" if self.chart_resolver.is_rate_field(label) else "number"
            if fmt == "percent":
                alias = safe_alias(label)
                select_parts.append(f"ROUND(AVG({expr}), 0) AS `{alias}`")
            else:
                select_parts.append(f"SUM({expr}) AS `{alias}`")
            items.append({"label": alias, "value_field": alias, "format": fmt})
            if len(items) >= 5:
                break
        target_pair = self._find_target_pair(self._metric_fields(profile))
        if target_pair and len(items) < 5:
            actual, target = target_pair
            a_expr = numeric_expr(actual["field"])
            t_expr = numeric_expr(target["field"])
            select_parts.append(
                f"ROUND(SUM({a_expr}) / NULLIF(SUM({t_expr}), 0) * 100, 0) AS `达成率`"
            )
            items.append({"label": "达成率", "value_field": "达成率", "format": "percent"})
        sql = f"SELECT {', '.join(select_parts)} FROM {quote_ident(table_name)}"
        metric = {"field": "*", "aggregation": "kpi_group", "label": "核心指标"}
        chart = self._chart(
            profile, category_id, "kpi_group", f"{profile['sheet_name']}核心指标",
            f"{profile['sheet_name']}核心经营指标总览。",
            sql,
            metric, [], None, 100,
            summary_sql=sql,
            layer="summary",
        )
        chart.update({
            "perspective_id": "sheet_summary",
            "role_name": "经营总览",
            "layer": "summary",
            "intent_type": "kpi_overview",
            "items": items,
            "layout": {"max_per_row": 5},
            "encoding": {
                "y": [
                    {"field": item["value_field"], "label": item["label"], "format": item["format"]}
                    for item in items
                ]
            },
        })
        return [chart]

    async def _limited(self, coro):
        async with self.sem:
            return await coro

    async def _limited_chart_draft(self, coro):
        async with self.chart_draft_sem:
            return await coro

    async def _load_sheets_data(self, file_id: str) -> List[Dict[str, Any]]:
        import json
        metas = await self.db.get_sheet_metas(file_id)
        sheets_data = []
        for meta in metas:
            columns_raw = meta.columns
            if isinstance(columns_raw, str):
                columns = json.loads(columns_raw)
            else:
                columns = columns_raw or []
            key_dimensions = meta.key_dimensions
            key_metrics = meta.key_metrics
            if isinstance(key_dimensions, str):
                key_dimensions = json.loads(key_dimensions)
            if isinstance(key_metrics, str):
                key_metrics = json.loads(key_metrics)
            sheets_data.append({
                "sheet_name": meta.sheet_name,
                "sheet_index": meta.sheet_index,
                "table_name": meta.table_name,
                "columns": columns,
                "row_count": meta.row_count,
                "summary": meta.summary or "",
                "key_dimensions": key_dimensions or [],
                "key_metrics": key_metrics or [],
                "data_granularity": meta.data_granularity or "",
                "time_range": meta.time_range or "",
            })
        return sheets_data

    # ── 保留 v2 辅助：分类、筛选、关联、布局 ─────────────────

    def _build_sheet_categories(self, profiles: List[Dict[str, Any]], sheet_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        plan_by_index = {int(item["sheet_index"]): item for item in sheet_plan.get("sheet_categories", [])}
        return [
            {
                "id": self._category_id_for(p),
                "name": plan_by_index[int(p.get("sheet_index") or idx)].get("display_name") or p["sheet_name"],
                "display_name": plan_by_index[int(p.get("sheet_index") or idx)].get("display_name") or p["sheet_name"],
                "icon": "sheet",
                "source": "sheet",
                "sheet_key": p["sheet_name"],
                "table_name": p["table_name"],
                "sheet_index": int(p.get("sheet_index") or idx),
                "description": plan_by_index[int(p.get("sheet_index") or idx)].get("description", ""),
                "business_theme": plan_by_index[int(p.get("sheet_index") or idx)].get("business_theme", ""),
                "primary_kpis": plan_by_index[int(p.get("sheet_index") or idx)].get("primary_kpis", []),
                "locked": True,
            }
            for idx, p in enumerate(profiles)
        ]

    def _apply_filter_plan(self, filters, filter_labels):
        label_by_key = {item.get("canonical_key"): item for item in filter_labels or [] if item.get("canonical_key")}
        for item in filters:
            planned = label_by_key.get(item.get("canonical_key"))
            if not planned:
                continue
            if planned.get("label"):
                item["label"] = planned["label"]
            if planned.get("priority") is not None:
                item["priority"] = int(planned["priority"])
        filters.sort(key=lambda f: (len(f["applies_to"]), f["priority"]), reverse=True)
        return filters[:6]

    async def _hydrate_filter_options(self, filters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for item in filters:
            applies_to = item.get("applies_to", [])
            if applies_to:
                first = applies_to[0]
                rows = await self.db.execute_query(
                    f"SELECT DISTINCT {quote_ident(first['field'])} AS val "
                    f"FROM {quote_ident(first['table_name'])} "
                    f"WHERE {quote_ident(first['field'])} IS NOT NULL "
                    f"AND {quote_ident(first['field'])} <> '' LIMIT 50"
                )
                item["options"] = [row.get("val") for row in rows if row.get("val") not in (None, "")][:50]
            item["field"] = item["canonical_key"]
        return [f for f in filters if f.get("options")]

    async def _generate_relation_categories(
        self, relationships, profiles, global_filters, custom_plan, charts_dropped,
    ):
        profile_map = {p["table_name"]: p for p in profiles}
        categories = []
        charts = []
        plan_by_rel = {item.get("relationship_id"): item for item in custom_plan.get("custom_categories", [])}
        selected = [rel for rel in relationships if rel["id"] in plan_by_rel][:3]
        for idx, rel in enumerate(selected):
            category_id = f"custom_relation_{idx + 1}"
            plan = plan_by_rel[rel["id"]]
            name = plan.get("display_name") or plan.get("name") or "关联分析"
            categories.append({
                "id": category_id,
                "name": name,
                "display_name": name,
                "icon": "chart",
                "source": "custom",
                "locked": False,
                "created_by": "system",
                "relationship_id": rel["id"],
                "sheet_keys": [rel["left_sheet"], rel["right_sheet"]],
            })
            left = profile_map[rel["left_table"]]
            left_metric = (self._metric_fields(left) or [{"field": "*", "label": "记录数"}])[0]
            right = profile_map[rel["right_table"]]
            right_metric = (self._metric_fields(right) or [{"field": "*", "label": "记录数"}])[0]
            if left_metric["field"] == "*":
                lv = "COUNT(*)"
            else:
                left_expr = numeric_expr(left_metric["field"]).replace(
                    quote_ident(left_metric["field"]),
                    f"a.{quote_ident(left_metric['field'])}",
                )
                lv = f"SUM({left_expr})"
            if right_metric["field"] == "*":
                rv = "COUNT(*)"
            else:
                right_expr = numeric_expr(right_metric["field"]).replace(
                    quote_ident(right_metric["field"]),
                    f"b.{quote_ident(right_metric['field'])}",
                )
                rv = f"SUM({right_expr})"
            object_alias = safe_alias(rel["left_field"])
            left_alias = safe_alias(f"{rel['left_sheet']}_{left_metric['label']}")
            right_alias = safe_alias(f"{rel['right_sheet']}_{right_metric['label']}")
            sql = (
                f"SELECT a.{quote_ident(rel['left_field'])} AS `{object_alias}`, "
                f"{lv} AS `{left_alias}`, {rv} AS `{right_alias}` "
                f"FROM {quote_ident(rel['left_table'])} a "
                f"INNER JOIN {quote_ident(rel['right_table'])} b "
                f"ON a.{quote_ident(rel['left_field'])} = b.{quote_ident(rel['right_field'])} "
                f"GROUP BY a.{quote_ident(rel['left_field'])} LIMIT 20"
            )
            chart = self._chart(
                left, category_id, "table", f"{rel['left_sheet']}×{rel['right_sheet']}",
                f"按 {rel['left_field']} 关联{rel['left_sheet']}与{rel['right_sheet']}。",
                sql,
                {"field": left_metric["field"], "aggregation": "join_compare", "label": "关联"},
                [rel["left_field"]], None, 82,
                table_name=rel["left_table"],
                layer="custom",
            )
            chart["encoding"] = {
                "x": {"field": object_alias, "label": object_alias, "role": "dimension"},
                "y": [
                    {"field": left_alias, "label": left_alias, "axis": "left", "series_type": "bar", "format": "number"},
                    {"field": right_alias, "label": right_alias, "axis": "left", "series_type": "bar", "format": "number"},
                ],
            }
            chart["intent_type"] = "relation_compare"
            charts.append(chart)
        return categories, charts

    def _rank_and_layout(self, charts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        def sort_key(c):
            layer = c.get("layer", "role_analysis")
            layer_order = 0 if layer == "summary" else 1
            return (c["category_id"], layer_order, -c["priority"], c.get("chart_type", ""))

        charts.sort(key=sort_key)
        per_category: Dict[str, int] = {}
        for chart in charts:
            count = per_category.get(chart["category_id"], 0)
            chart["board_order"] = count
            chart["boardOrder"] = count
            if count >= self.MAX_BOARD_PER_CATEGORY:
                chart["on_board"] = False
                chart["onBoard"] = False
            else:
                chart["onBoard"] = chart["on_board"]
                per_category[chart["category_id"]] = count + 1 if chart["on_board"] else count
        return charts

    def _limit_warehouse_balanced(self, charts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if len(charts) <= self.MAX_WAREHOUSE:
            return charts
        buckets: Dict[str, List[Dict[str, Any]]] = {}
        for chart in charts:
            buckets.setdefault(chart["category_id"], []).append(chart)
        selected: List[Dict[str, Any]] = []
        while len(selected) < self.MAX_WAREHOUSE and any(buckets.values()):
            for category_id in sorted(buckets.keys()):
                bucket = buckets[category_id]
                if not bucket:
                    continue
                selected.append(bucket.pop(0))
                if len(selected) >= self.MAX_WAREHOUSE:
                    break
        return selected

    def _chart(
        self, profile, category_id, chart_type, title, question, sql, metric, dimensions,
        time_field, priority, summary_sql=None, on_board=True, table_name=None,
        related_tables=None, layer="role_analysis",
    ) -> Dict[str, Any]:
        digest = hashlib.md5(f"{category_id}:{title}:{sql}".encode()).hexdigest()[:10]
        chart_id = f"chart_{category_id}_{digest}"
        filters = self._chart_filters(profile, dimensions, time_field)
        return {
            "id": chart_id,
            "category_id": category_id,
            "categoryId": category_id,
            "default_category_id": self._category_id_for(profile),
            "title": title,
            "question": question,
            "description": question,
            "chart_type": chart_type,
            "chartType": chart_type,
            "layer": layer,
            "sheet_name": profile.get("sheet_name"),
            "table_name": table_name or profile["table_name"],
            "related_tables": related_tables or [],
            "sql": sql,
            "summary_sql": summary_sql,
            "x_field": dimensions[0] if dimensions else time_field,
            "y_field": metric.get("label"),
            "metric": metric,
            "dimensions": dimensions,
            "time_field": time_field,
            "filters": filters,
            "global_filter_fields": [f["field"] for f in filters],
            "on_board": on_board,
            "onBoard": on_board,
            "board_order": 0,
            "boardOrder": 0,
            "priority": priority,
            "preview": {"columns": [], "rows": []},
            "tablePreview": {"columns": [], "rows": []},
            "chartFilters": {},
        }

    def _chart_filters(self, profile, dimensions, time_field):
        fields = {f["field"]: f for f in profile["fields"]}
        selected = []
        for field_name in list(dimensions) + ([time_field] if time_field else []):
            field = fields.get(field_name)
            if field and field.get("filterable"):
                selected.append({
                    "field": field["field"],
                    "type": "enum",
                    "sample_values": field.get("sample_values", [])[:10],
                })
        return selected[:3]

    def _metric_fields(self, profile):
        metrics = [f for f in profile["fields"] if f["data_role"] == "metric"]
        return [{"field": f["field"], "label": f["field"], **f} for f in metrics]

    def _find_target_pair(self, metrics):
        targets = [m for m in metrics if any(k in m["field"].lower() for k in ("目标", "预算", "target", "budget"))]
        actuals = [m for m in metrics if m not in targets]
        if targets and actuals:
            return actuals[0], targets[0]
        return None

    def _category_id_for(self, profile):
        return f"sheet_{int(profile.get('sheet_index') or 0)}"


class UnderstandingNotReadyError(Exception):
    def __init__(self, pending_tables: List[str], pending_sheets: List[Dict[str, Any]]):
        self.pending_tables = pending_tables
        self.pending_sheets = pending_sheets
        super().__init__(f"六维理解未就绪: {', '.join(pending_tables)}")
