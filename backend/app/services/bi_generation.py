"""
BI 看板生成 v3：理解门禁 → 行业推断 → 总览 → 角色→场景→问题→审视 → SQL+单次修复。
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any, Dict, List, Optional, Tuple

from app.agents.bi_pipeline_agents import BIChartRepairAgent, BIIndustryInferenceAgent
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

logger = logging.getLogger(__name__)


class BIBusinessGenerator:
    MAX_WAREHOUSE = 40
    MAX_BOARD_PER_CATEGORY = 10

    def __init__(self, db_service: DBService, concurrency: int = 4):
        self.db = db_service
        self.profiler = BIProfiler(db_service)
        self.planner = BIPlanner()
        self.industry_agent = BIIndustryInferenceAgent()
        self.blueprint_pipeline = BIBlueprintPipeline(concurrency=concurrency)
        self.repair_agent = BIChartRepairAgent()
        self.spec_compiler = MetricSpecCompiler()
        self.sql_builder = BISQLBuilder()
        self.sem = asyncio.Semaphore(concurrency)

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
                    "单 Sheet 流水线失败",
                    run_ctx=run_ctx,
                    table_name=profile.get("table_name"),
                    sheet_name=profile.get("sheet_name"),
                    exc=e,
                )
                raise

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

        valid_charts = []
        for chart in all_charts:
            result = await self._limited(
                self._execute_chart_with_repair(chart, profiles, understanding_map, charts_dropped, run_ctx)
            )
            if result:
                valid_charts.append(result)

        valid_charts = self._rank_and_layout(valid_charts)

        log_step_ok(
            STEP_GENERATE_END,
            "BI 生成完成",
            run_ctx=run_ctx,
            extra={
                "sheet_count": len(profiles),
                "chart_count": min(len(valid_charts), self.MAX_WAREHOUSE),
                "charts_dropped_count": len(charts_dropped),
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
            "charts": valid_charts[: self.MAX_WAREHOUSE],
            "relationships": relationships,
            "generation_report": {
                "sheet_count": len(profiles),
                "relationship_count": len(relationships),
                "chart_count": min(len(valid_charts), self.MAX_WAREHOUSE),
                "strategy": "v3_stepped_blueprint_repair",
                "pipeline_run_id": run_ctx.run_id,
                "sheet_plan_warnings": sheet_plan.get("warnings", []),
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

        blueprint = await self.blueprint_pipeline.run(
            profile, understanding_text, industry_guess, run_ctx=run_ctx,
        )

        for perspective in blueprint.get("perspectives", []):
            for scenario in perspective.get("scenarios", []):
                for question in scenario.get("questions", []):
                    chart = self._question_to_chart_draft(
                        profile, category_id, perspective, scenario, question, run_ctx,
                    )
                    if chart:
                        charts.append(chart)

        log_step_ok(
            STEP_SHEET_PIPELINE,
            f"单 Sheet 流水线结束，产出 {len(charts)} 张图草稿",
            run_ctx=run_ctx,
            table_name=table_name,
            sheet_name=sheet_name,
            extra={"blueprint_warnings": blueprint.get("warnings")},
        )
        return charts

    def _question_to_chart_draft(
        self,
        profile: Dict[str, Any],
        category_id: str,
        perspective: Dict[str, Any],
        scenario: Dict[str, Any],
        question: Dict[str, Any],
        run_ctx: BIPipelineRunContext,
    ) -> Optional[Dict[str, Any]]:
        qid = question.get("question_id")
        try:
            spec = self.spec_compiler.compile(profile, question, scenario, perspective)
            spec = self._apply_analysis_guards(spec, profile, question)
            sql, summary_sql, chart_type = self.sql_builder.build(spec, profile)
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
            question.get("preferred_chart_types", [chart_type])[0]
            if question.get("preferred_chart_types") else chart_type,
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
            "metric_spec": spec,
            "from_review": bool(question.get("from_review")),
        })
        preferred = question.get("preferred_chart_types")
        if preferred and preferred[0] in ("bar", "line", "pie", "table", "kpi"):
            chart["chart_type"] = preferred[0]
            chart["chartType"] = preferred[0]
        return chart

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
            chart["sql"] = repair["revised_sql"].strip()
        elif repair.get("repair_action") == "fix_question":
            revised = dict(chart.get("metric_spec") or {})
            q_patch = {
                "question_id": chart.get("question_id"),
                "question": repair.get("revised_question") or chart.get("question"),
                "analysis_type": repair.get("revised_analysis_type") or chart.get("analysis_type"),
                "analysis_intent": repair.get("revised_analysis_intent") or chart.get("analysis_intent", ""),
                "sql_template_hint": repair.get("revised_sql_template_hint"),
                "metrics": [m.get("field") if isinstance(m, dict) else m for m in repair.get("revised_metrics", [])],
                "dimensions": [d.get("field") if isinstance(d, dict) else d for d in repair.get("revised_dimensions", [])],
                "time_field": repair.get("revised_time_field"),
            }
            scenario = {
                "scenario_context": chart.get("scenario_context", ""),
            }
            perspective = {"role_name": chart.get("role_name", "")}
            try:
                spec = self.spec_compiler.compile(profile, q_patch, scenario, perspective)
                sql, summary_sql, chart_type = self.sql_builder.build(spec, profile)
                chart["sql"] = sql
                chart["summary_sql"] = summary_sql
                chart["chart_type"] = chart_type
                chart["chartType"] = chart_type
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
                "repair_attempted": repair_attempted,
                "role_name": chart.get("role_name"),
                "scenario_name": chart.get("scenario_name"),
                "analysis_type": chart.get("analysis_type"),
                "repair_diagnosis": (repair or {}).get("diagnosis"),
            },
        )

    def _build_summary_charts(self, profile: Dict[str, Any], category_id: str) -> List[Dict[str, Any]]:
        table_name = profile["table_name"]
        charts = []
        count_metric = {"field": "*", "aggregation": "count", "label": "记录数"}
        charts.append(self._chart(
            profile, category_id, "kpi", f"{profile['sheet_name']}·记录数",
            f"{profile['sheet_name']}共有多少条业务记录？",
            f"SELECT COUNT(*) AS `记录数` FROM {quote_ident(table_name)}",
            count_metric, [], None, 100,
            summary_sql=f"SELECT COUNT(*) AS `总记录数` FROM {quote_ident(table_name)}",
            layer="summary",
        ))
        for metric in self._metric_fields(profile)[:3]:
            expr = numeric_expr(metric["field"])
            label = metric["label"]
            charts.append(self._chart(
                profile, category_id, "kpi", f"总{label}",
                f"{profile['sheet_name']}核心指标「{label}」总量是多少？",
                f"SELECT SUM({expr}) AS `{safe_alias('总' + label)}` FROM {quote_ident(table_name)}",
                {"field": metric["field"], "aggregation": "sum", "label": label},
                [], None, max(90, 99 - len(charts)),
                summary_sql=f"SELECT SUM({expr}) AS `{safe_alias('总' + label)}` FROM {quote_ident(table_name)}",
                layer="summary",
            ))
        target_pair = self._find_target_pair(self._metric_fields(profile))
        if target_pair:
            actual, target = target_pair
            a_expr = numeric_expr(actual["field"])
            t_expr = numeric_expr(target["field"])
            charts.append(self._chart(
                profile, category_id, "kpi", f"{actual['label']}达成率",
                f"{profile['sheet_name']}实际相对目标的达成率是多少？",
                f"SELECT ROUND(SUM({a_expr}) / NULLIF(SUM({t_expr}), 0) * 100, 2) AS `达成率` "
                f"FROM {quote_ident(table_name)}",
                {"field": actual["field"], "aggregation": "achievement_rate", "label": "达成率"},
                [], None, 98,
                layer="summary",
            ))
        for c in charts:
            c["perspective_id"] = "sheet_summary"
            c["role_name"] = "经营总览"
            c["layer"] = "summary"
        return charts

    async def _limited(self, coro):
        async with self.sem:
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
            lv = "COUNT(*)" if left_metric["field"] == "*" else f"SUM({numeric_expr(left_metric['field'])})"
            rv = "COUNT(*)" if right_metric["field"] == "*" else f"SUM({numeric_expr(right_metric['field'])})"
            sql = (
                f"SELECT a.{quote_ident(rel['left_field'])} AS `关联对象`, {lv} AS `左表指标`, {rv} AS `右表指标` "
                f"FROM {quote_ident(rel['left_table'])} a "
                f"INNER JOIN {quote_ident(rel['right_table'])} b "
                f"ON a.{quote_ident(rel['left_field'])} = b.{quote_ident(rel['right_field'])} "
                f"GROUP BY a.{quote_ident(rel['left_field'])} LIMIT 20"
            )
            charts.append(self._chart(
                left, category_id, "table", f"{rel['left_sheet']}×{rel['right_sheet']}",
                f"关联对比：{rel['left_field']} / {rel['right_field']}",
                sql,
                {"field": left_metric["field"], "aggregation": "join_compare", "label": "关联"},
                [rel["left_field"]], None, 82,
                table_name=rel["left_table"],
                layer="custom",
            ))
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
