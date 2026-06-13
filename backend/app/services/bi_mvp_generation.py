"""Minimal LLM-driven BI generation pipeline.

This MVP keeps the existing SSE/API contract but replaces the heavy multi-agent
pipeline with three direct LLM stages:
1. categories + global filters
2. category question plan
3. per-question chart type + SQL
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from app.services.bi_exceptions import UnderstandingNotReadyError
from app.services.bi_profiler import BIProfiler, quote_ident
from app.services.bi_understanding_gate import check_understanding_ready, resolve_understanding_text
from app.services.db_service import DBService
from app.services.db.utils import json_safe
from app.services.llm_client import LLMClient
from app.utils.sql_validator import SQLValidator


B1_SYSTEM = """你是 BI 看板信息架构师。请根据 Excel 的 Sheet、字段、样本、单表理解和跨表关联总结，生成 BI 看板分类与公共筛选参数。

必须遵守：
1. 只输出 JSON 对象，不要 Markdown。
2. 所有 table_name 和 field 必须来自输入，禁止编造。
3. categories 最多 8 个：先为每张 Sheet 生成一个 source=sheet 的分类；如果 Sheet 少于 8 个，继续生成最多 3 个 source=custom 的跨表高维分类。
4. source=custom 必须来自多表关联视角，例如经营总览、目标达成、客户产品、销售团队绩效、区域经营健康；必须填写 primary_table_name 和 related_tables。
5. custom 分类可以先绑定一张 primary_table_name 作为 MVP 图表 SQL 的主表，但 description 必须说明它如何参考多个表的关联信息。
6. global_filters 只选择能跨多个图表复用、适合筛选的字段，如区域、产品类别、客户等级、时间、状态。
7. 不要输出筛选选项值，选项值由系统从数据库读取。
8. thinking 写自然语言，说明你如何识别 Sheet 分类、跨表分类和公共筛选。

返回格式：
{
  "thinking": "…",
  "categories": [
    {
      "id": "sheet_0",
      "name": "销售明细",
      "display_name": "销售明细",
      "source": "sheet",
      "table_name": "实际表名",
      "primary_table_name": "实际表名",
      "related_tables": ["实际表名"],
      "description": "这个分类要回答什么"
    }
  ],
  "global_filters": [
    {
      "canonical_key": "区域",
      "field": "区域",
      "label": "区域",
      "applies_to": [
        {"table_name": "实际表名", "field": "区域"}
      ],
      "priority": 90
    }
  ]
}"""


B2_SYSTEM = """你是 BI 分析问题设计专家。请根据已经确定的看板分类，为每个分类设计适合放进 BI 看板的问题清单。

必须遵守：
1. 只输出 JSON 对象，不要 Markdown。
2. category_id 必须来自输入 categories。
3. 每个分类输出 6～8 个问题；若字段太少，至少 3 个。
4. 每个分类的问题和 thinking 都必须贴合该分类的表、字段、单表理解、关联表和业务目标；禁止所有分类使用同一套泛化表述。
5. Sheet 分类重点围绕单表字段能直接回答的问题；custom 分类重点围绕多个表的关联视角，但问题最终仍要能落到 primary_table_name 上做 MVP SQL。
6. 问题名称要业务化，不能只写字段名。
7. 只定义问题，不要写 SQL。
8. 顶层 thinking 写整体规划说明；每个 category_plan 也必须写独立 thinking，说明这个分类为什么设计这些问题。

返回格式：
{
  "thinking": "…",
  "category_plans": [
    {
      "category_id": "sheet_0",
      "category_name": "销售明细",
      "thinking": "这个分类聚焦交易事实表，所以先覆盖销售额、利润、订单、区域、时间和异常订单。",
      "questions": [
        {
          "id": "q_sales_kpi",
          "title": "销售核心指标",
          "question": "整体销售额、利润、订单与客户规模是否健康？",
          "priority": 100
        }
      ]
    }
  ]
}"""


B3_SYSTEM = """你是资深 BI SQL 与可视化专家。请为一个已确定的业务问题生成图表类型、MySQL SELECT SQL 和前端渲染契约。

必须遵守：
1. 只输出 JSON 对象，不要 Markdown。
2. SQL 只能是 SELECT 或 WITH ... SELECT，禁止任何写操作。
3. 只能查询输入 table_name 这一张表，禁止跨表 JOIN。
4. 表名、列名必须来自输入，并使用反引号。
5. chart_type 只能是：kpi_group, bar, line, pie, donut, combo, ranking, table, detail_table, gauge。
6. SQL 输出列 alias 必须与 encoding/items 中引用的 field 一致。
7. 占比结构优先 donut/pie；趋势优先 line；排名优先 ranking/bar；明细优先 detail_table；总览优先 kpi_group。
8. 数值列可能是文本时，用 CAST(REPLACE(REPLACE(REPLACE(`字段`, ',', ''), '￥', ''), '%', '') AS DECIMAL(18,4))。
9. 兼容 MySQL only_full_group_by：SELECT 非聚合列必须出现在 GROUP BY。
10. thinking 写自然语言，说明为什么选择该图表和 SQL。

返回格式：
{
  "thinking": "…",
  "chart": {
    "title": "区域销售额对比",
    "question": "不同区域销售贡献是否均衡？",
    "chart_type": "bar",
    "sql": "SELECT ...",
    "encoding": {
      "x": {"field": "区域", "label": "区域", "role": "dimension"},
      "y": [
        {"field": "销售额", "label": "销售额", "axis": "left", "series_type": "bar", "format": "number"}
      ]
    },
    "items": []
  }
}"""


B3_REPAIR_SYSTEM = """你是 MySQL SQL 修复专家。请根据错误信息修复一个 BI 图表 SQL，并保持原图表意图。

必须遵守：
1. 只输出 JSON 对象，不要 Markdown。
2. SQL 只能是 SELECT 或 WITH ... SELECT，禁止任何写操作。
3. 只能查询输入 table_name 这一张表，禁止跨表 JOIN。
4. 表名、列名必须来自输入，并使用反引号。
5. 禁止使用 MySQL 不兼容或高风险函数，例如 PERCENTILE_CONT。
6. 兼容 only_full_group_by，SELECT 非聚合列必须出现在 GROUP BY。
7. 如果原 SQL 过于复杂，降级为简单聚合、排名或明细查询，优先保证可执行。

返回格式：
{
  "thinking": "说明如何修复",
  "chart": {
    "title": "修复后的标题",
    "question": "原问题",
    "chart_type": "bar",
    "sql": "SELECT ...",
    "encoding": {},
    "items": []
  }
}"""


PROMPT_VERSION = "2026-05-29.3"
LLM_JSON_TIMEOUT = 600.0


class BILlmMVPGenerator:
    MAX_CATEGORIES = 8
    MAX_QUESTIONS_PER_CATEGORY = 8
    MAX_WAREHOUSE = 64
    CONCURRENCY = 4

    def __init__(self, db_service: DBService):
        self.db = db_service
        self.llm = LLMClient()
        self.profiler = BIProfiler(db_service)
        self.sem = asyncio.Semaphore(self.CONCURRENCY)

    async def generate(
        self,
        file_id: str,
        sheets_data: Optional[List[Dict[str, Any]]] = None,
        *,
        on_thinking_entry: Optional[Any] = None,
        on_progress_event: Optional[Any] = None,
    ) -> Dict[str, Any]:
        async def emit(event: Dict[str, Any]) -> None:
            if on_progress_event:
                result = on_progress_event(json_safe(event))
                if asyncio.iscoroutine(result):
                    await result

        async def think(step: str, text: str, **extra: Any) -> None:
            if not text:
                return
            entry = {
                "id": self._stable_id(f"{step}:{text}:{datetime.utcnow().isoformat()}"),
                "ts": datetime.utcnow().isoformat(),
                "step": step,
                "level": "info",
                "text": text,
                **extra,
            }
            if on_thinking_entry:
                result = on_thinking_entry(entry)
                if asyncio.iscoroutine(result):
                    await result

        ready, pending = await check_understanding_ready(self.db, file_id)
        if not ready:
            raise UnderstandingNotReadyError([p["table_name"] for p in pending], pending)

        if sheets_data is None:
            sheets_data = await self._load_sheets_data(file_id)

        file_record = await self.db.get_file_record(file_id)
        profiles = [await self.profiler.profile_sheet(sheet) for sheet in sheets_data]
        understanding_map: Dict[str, str] = {}
        for sheet in sheets_data:
            text = await resolve_understanding_text(self.db, sheet["table_name"])
            if not text:
                raise UnderstandingNotReadyError([sheet["table_name"]], [])
            understanding_map[sheet["table_name"]] = text
            await emit({
                "step": "understanding_loaded",
                "status": "processing",
                "table_name": sheet["table_name"],
                "sheet_name": sheet["sheet_name"],
                "understanding_preview": text[:280],
                "understanding_length": len(text),
            })

        relations = {}
        if file_record and file_record.space_id:
            relations = await self.db.get_space_relations(file_record.space_id) or {}

        context = self._build_context(file_record, profiles, understanding_map, relations)

        await emit({
            "step": "category_planning",
            "status": "processing",
            "message": "正在调用模型生成分类和公共筛选",
            "sheet_count": len(profiles),
        })
        b1 = await self._call_json(B1_SYSTEM, context, max_tokens=8192)
        await think("category_planning", str(b1.get("thinking") or "已生成分类与公共筛选。"))
        categories = self._normalize_categories(b1, profiles)
        global_filters = await self._normalize_filters(b1, profiles)
        await emit({
            "step": "categories_ready",
            "status": "completed",
            "message": "分类和公共筛选参数已生成",
            "categories_count": len(categories),
            "categories": categories,
            "global_filters": global_filters,
        })

        await emit({
            "step": "chart_planning",
            "status": "processing",
            "message": "正在调用模型定义各分类问题",
            "categories": categories,
        })
        b2_payload = {
            **context,
            "categories": categories,
            "global_filters": global_filters,
        }
        b2 = await self._call_json(B2_SYSTEM, b2_payload, max_tokens=12288)
        await think("question_planning", str(b2.get("thinking") or "已生成分类问题清单。"))
        question_plans = self._normalize_question_plans(b2, categories)
        for plan in question_plans:
            await emit({
                "step": "category_plan_start",
                "status": "processing",
                "category_id": plan["category_id"],
                "category_name": plan["category_name"],
                "message": f"正在规划「{plan['category_name']}」的问题清单",
            })
            await think(
                "question_planning",
                plan.get("thinking") or f"已为「{plan['category_name']}」生成差异化问题清单。",
                category_id=plan["category_id"],
                category_name=plan["category_name"],
            )
            await emit({
                "step": "category_plan_done",
                "status": "completed",
                "category_id": plan["category_id"],
                "category_name": plan["category_name"],
                "questions_count": len(plan.get("questions") or []),
                "message": f"「{plan['category_name']}」的问题清单已确定",
            })
        placeholders = self._build_placeholders(question_plans, categories)
        chart_plan = self._build_chart_plan(categories, placeholders, global_filters)
        await emit({
            "step": "chart_plan_ready",
            "status": "completed",
            "message": "问题清单已确定，开始并行生成图表类型与 SQL",
            "categories": categories,
            "global_filters": global_filters,
            "chart_plan": chart_plan,
            "charts_count": len(placeholders),
        })

        table_names = {p["table_name"] for p in profiles}
        profile_by_category = {
            c["id"]: next((p for p in profiles if p["table_name"] == c.get("table_name")), None)
            for c in categories
        }
        charts: List[Dict[str, Any]] = []
        failed: List[Dict[str, Any]] = []

        async def build_one(placeholder: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            category_id = placeholder["category_id"]
            profile = profile_by_category.get(category_id)
            if not profile:
                return None
            await emit({
                "step": "chart_start",
                "status": "processing",
                "category_id": category_id,
                "chart_id": placeholder["id"],
                "chart_type": "table",
                "title": placeholder["title"],
                "message": f"正在为「{placeholder['title']}」生成图表类型与 SQL",
            })
            try:
                chart = await self._limited(self._generate_chart(
                    placeholder, profile, understanding_map.get(profile["table_name"], ""),
                    relations.get("content") or "", global_filters, table_names,
                ))
                await think(
                    "chart_sql",
                    chart.get("thinking") or f"「{chart['title']}」图表与 SQL 已生成。",
                    sheet_name=profile.get("sheet_name"),
                    table_name=profile.get("table_name"),
                )
                chart.pop("thinking", None)
                await emit({
                    "step": "chart_done",
                    "status": "completed",
                    "category_id": category_id,
                    "chart_id": chart["id"],
                    "chart_type": chart["chart_type"],
                    "title": chart["title"],
                    "chart": chart,
                })
                return chart
            except Exception as e:
                failed_item = {
                    "chart_id": placeholder["id"],
                    "title": placeholder["title"],
                    "category_id": category_id,
                    "error": str(e),
                }
                failed.append(failed_item)
                failed_chart = self._failed_chart(placeholder, profile, str(e))
                await emit({
                    "step": "chart_failed",
                    "status": "failed",
                    "category_id": category_id,
                    "chart_id": placeholder["id"],
                    "chart_type": "table",
                    "title": placeholder["title"],
                    "message": str(e),
                    "chart": failed_chart,
                })
                return failed_chart

        results = await asyncio.gather(*[build_one(item) for item in placeholders[: self.MAX_WAREHOUSE]])
        charts = [item for item in results if item]
        if not charts:
            raise RuntimeError("BI MVP 生成失败：没有任何图表成功生成")

        charts = self._layout_charts(charts)
        return {
            "version": 4,
            "file_id": file_id,
            "dialect": "mysql",
            "categories": [c for c in categories if c.get("source") == "sheet"],
            "custom_categories": [c for c in categories if c.get("source") == "custom"],
            "global_filters": global_filters,
            "charts": charts,
            "generation_report": {
                "strategy": "llm_mvp_three_stage",
                "prompt_version": PROMPT_VERSION,
                "custom_category_mode": "cross_table_theme_single_table_sql",
                "sheet_count": len(profiles),
                "category_count": len(categories),
                "planned_chart_count": len(placeholders[: self.MAX_WAREHOUSE]),
                "chart_count": len(charts),
                "success_chart_count": len([chart for chart in charts if chart.get("status") != "failed"]),
                "failed_chart_count": len(failed),
                "failed_charts": failed,
            },
        }

    async def _call_json(self, system: str, payload: Dict[str, Any], max_tokens: int) -> Dict[str, Any]:
        return await self.llm.chat_completion_json(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(json_safe(payload), ensure_ascii=False)},
            ],
            temperature=0.2,
            max_tokens=max_tokens,
            timeout=LLM_JSON_TIMEOUT,
        )

    async def _generate_chart(
        self,
        placeholder: Dict[str, Any],
        profile: Dict[str, Any],
        understanding: str,
        relations_content: str,
        global_filters: List[Dict[str, Any]],
        allowed_tables: Set[str],
    ) -> Dict[str, Any]:
        payload = {
            "question": {
                "id": placeholder["question_id"],
                "title": placeholder["title"],
                "question": placeholder["question"],
                "priority": placeholder.get("priority", 80),
            },
            "category_id": placeholder["category_id"],
            "sheet_name": profile["sheet_name"],
            "table_name": profile["table_name"],
            "fields": profile["fields"],
            "sample_rows": (await self.db.fetch_sample_rows_from_table(profile["table_name"])).get("rows", [])[:20],
            "understanding_content": understanding,
            "relations_content": relations_content,
            "global_filters": global_filters,
        }
        result = await self._call_json(B3_SYSTEM, payload, max_tokens=8192)
        try:
            return await self._chart_from_result(result, placeholder, profile, allowed_tables)
        except Exception as first_error:
            repaired = await self._repair_chart_sql(result, payload, str(first_error))
            try:
                return await self._chart_from_result(repaired, placeholder, profile, allowed_tables, repaired=True)
            except Exception as repair_error:
                fallback = await self._fallback_detail_chart(placeholder, profile, str(repair_error))
                fallback["thinking"] = (
                    f"原 SQL 生成和修复均失败，已降级为安全明细表。最后错误：{repair_error}"
                )
                return fallback

    async def _chart_from_result(
        self,
        result: Dict[str, Any],
        placeholder: Dict[str, Any],
        profile: Dict[str, Any],
        allowed_tables: Set[str],
        *,
        repaired: bool = False,
    ) -> Dict[str, Any]:
        raw_chart = result.get("chart") or {}
        sql = SQLValidator.sanitize_sql(str(raw_chart.get("sql") or ""))
        if not sql:
            raise ValueError("LLM 生成 SQL 未通过只读校验")
        self._validate_sql_tables(sql, allowed_tables, profile["table_name"])
        rows = await self._preview_rows(sql)
        if not rows:
            raise ValueError("SQL 预执行结果为空")
        chart_type = self._normalize_chart_type(raw_chart.get("chart_type"))
        preview = {"columns": list(rows[0].keys()), "rows": rows[:20]}
        title = str(raw_chart.get("title") or placeholder["title"])[:80]
        question = str(raw_chart.get("question") or placeholder["question"])
        chart = {
            "id": placeholder["id"],
            "category_id": placeholder["category_id"],
            "categoryId": placeholder["category_id"],
            "default_category_id": placeholder["category_id"],
            "title": title,
            "question": question,
            "description": question,
            "chart_type": chart_type,
            "chartType": chart_type,
            "sheet_name": profile["sheet_name"],
            "table_name": profile["table_name"],
            "sql": sql,
            "summary_sql": None,
            "encoding": raw_chart.get("encoding") if isinstance(raw_chart.get("encoding"), dict) else {},
            "items": raw_chart.get("items") if isinstance(raw_chart.get("items"), list) else [],
            "on_board": True,
            "onBoard": True,
            "board_order": 0,
            "boardOrder": 0,
            "priority": int(placeholder.get("priority") or 80),
            "expanded": self._expanded_for(chart_type),
            "collapsed": False,
            "preview": preview,
            "tablePreview": preview,
            "chartFilters": {},
            "intent_type": "llm_mvp",
            "status": "completed",
            "fallback_used": False,
            "sql_repaired": repaired,
            "thinking": result.get("thinking") or "",
        }
        return chart

    async def _repair_chart_sql(
        self,
        result: Dict[str, Any],
        payload: Dict[str, Any],
        error_message: str,
    ) -> Dict[str, Any]:
        repair_payload = {
            **payload,
            "failed_chart": result.get("chart") or {},
            "error_message": error_message,
            "mysql_constraints": {
                "only_full_group_by": True,
                "forbidden_functions": ["PERCENTILE_CONT"],
                "single_table_only": True,
            },
        }
        return await self._call_json(B3_REPAIR_SYSTEM, repair_payload, max_tokens=8192)

    async def _fallback_detail_chart(
        self,
        placeholder: Dict[str, Any],
        profile: Dict[str, Any],
        error_message: str,
    ) -> Dict[str, Any]:
        sql = f"SELECT * FROM {quote_ident(profile['table_name'])} LIMIT 20"
        rows = await self._preview_rows(sql)
        preview = {"columns": list(rows[0].keys()) if rows else [], "rows": rows[:20]}
        return {
            "id": placeholder["id"],
            "category_id": placeholder["category_id"],
            "categoryId": placeholder["category_id"],
            "default_category_id": placeholder["category_id"],
            "title": str(placeholder["title"])[:80],
            "question": placeholder["question"],
            "description": placeholder["question"],
            "chart_type": "detail_table",
            "chartType": "detail_table",
            "sheet_name": profile["sheet_name"],
            "table_name": profile["table_name"],
            "sql": sql,
            "summary_sql": None,
            "encoding": {},
            "items": [],
            "on_board": True,
            "onBoard": True,
            "board_order": 0,
            "boardOrder": 0,
            "priority": int(placeholder.get("priority") or 80),
            "expanded": True,
            "collapsed": False,
            "preview": preview,
            "tablePreview": preview,
            "chartFilters": {},
            "intent_type": "llm_mvp_fallback",
            "status": "completed",
            "fallback_used": True,
            "sql_repaired": False,
            "error_message": error_message,
        }

    def _failed_chart(
        self,
        placeholder: Dict[str, Any],
        profile: Optional[Dict[str, Any]],
        error_message: str,
    ) -> Dict[str, Any]:
        return {
            "id": placeholder["id"],
            "category_id": placeholder["category_id"],
            "categoryId": placeholder["category_id"],
            "default_category_id": placeholder["category_id"],
            "title": placeholder["title"],
            "question": placeholder["question"],
            "description": placeholder["question"],
            "chart_type": "detail_table",
            "chartType": "detail_table",
            "sheet_name": (profile or {}).get("sheet_name", ""),
            "table_name": (profile or {}).get("table_name", placeholder.get("table_name", "")),
            "sql": "",
            "summary_sql": None,
            "encoding": {},
            "items": [],
            "on_board": True,
            "onBoard": True,
            "board_order": 0,
            "boardOrder": 0,
            "priority": int(placeholder.get("priority") or 80),
            "expanded": True,
            "collapsed": False,
            "preview": {"columns": ["错误"], "rows": [{"错误": error_message}]},
            "tablePreview": {"columns": ["错误"], "rows": [{"错误": error_message}]},
            "chartFilters": {},
            "intent_type": "llm_mvp_failed",
            "status": "failed",
            "error_message": error_message,
        }

    async def _preview_rows(self, sql: str) -> List[Dict[str, Any]]:
        preview_sql = sql if re.search(r"\blimit\b", sql, flags=re.I) else f"{sql} LIMIT 200"
        return await self.db.execute_query(preview_sql)

    def _build_context(
        self,
        file_record: Any,
        profiles: List[Dict[str, Any]],
        understanding_map: Dict[str, str],
        relations: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "file": {
                "id": getattr(file_record, "id", ""),
                "filename": getattr(file_record, "filename", ""),
                "sheet_count": getattr(file_record, "sheet_count", len(profiles)),
            },
            "sheets": [
                {
                    "sheet_name": p["sheet_name"],
                    "sheet_index": p["sheet_index"],
                    "table_name": p["table_name"],
                    "row_count": p["row_count"],
                    "fields": p["fields"],
                    "sample_rows": [],
                    "understanding_content": understanding_map.get(p["table_name"], ""),
                }
                for p in profiles
            ],
            "relations_content": relations.get("content") or "",
        }

    async def _load_sheets_data(self, file_id: str) -> List[Dict[str, Any]]:
        metas = await self.db.get_sheet_metas(file_id)
        sheets_data = []
        for meta in metas:
            columns = meta.columns
            if isinstance(columns, str):
                columns = json.loads(columns)
            sheets_data.append({
                "sheet_name": meta.sheet_name,
                "sheet_index": meta.sheet_index,
                "table_name": meta.table_name,
                "columns": columns or [],
                "row_count": meta.row_count,
                "summary": meta.summary or "",
                "key_dimensions": self._json_load(meta.key_dimensions, []),
                "key_metrics": self._json_load(meta.key_metrics, []),
                "data_granularity": meta.data_granularity or "",
                "time_range": meta.time_range or "",
            })
        return sheets_data

    def _normalize_categories(self, b1: Dict[str, Any], profiles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        profile_by_table = {p["table_name"]: p for p in profiles}
        categories: List[Dict[str, Any]] = []
        raw_categories = b1.get("categories") or []

        for idx, profile in enumerate(profiles[: self.MAX_CATEGORIES]):
            generated = next(
                (
                    item for item in raw_categories
                    if item.get("source") != "custom" and item.get("table_name") == profile["table_name"]
                ),
                {},
            )
            table_name = profile["table_name"]
            category_id = self._category_id(profile, generated.get("id"))
            name = str(generated.get("display_name") or generated.get("name") or profile["sheet_name"])[:12]
            categories.append({
                "id": category_id,
                "name": name,
                "display_name": name,
                "icon": "sheet",
                "source": "sheet",
                "sheet_key": profile["sheet_name"],
                "table_name": table_name,
                "primary_table_name": table_name,
                "related_tables": [table_name],
                "sheet_index": profile["sheet_index"],
                "description": str(generated.get("description") or f"围绕「{profile['sheet_name']}」的数据字段回答业务问题。"),
                "locked": True,
            })

        custom_seen = set()
        for item in raw_categories:
            if item.get("source") != "custom":
                continue
            if len(categories) >= self.MAX_CATEGORIES:
                break
            table_name = item.get("table_name")
            primary_table = item.get("primary_table_name") or table_name
            profile = profile_by_table.get(primary_table)
            if not profile:
                continue
            raw_related = item.get("related_tables") or []
            related_tables = [
                table for table in raw_related
                if table in profile_by_table
            ]
            if primary_table not in related_tables:
                related_tables.insert(0, primary_table)
            if len(set(related_tables)) < 2 and len(profiles) > 1:
                continue
            name = str(item.get("display_name") or item.get("name") or "").strip()[:12]
            if not name or name in custom_seen:
                continue
            custom_seen.add(name)
            category_id = self._custom_category_id(item, name)
            categories.append({
                "id": category_id,
                "name": name,
                "display_name": name,
                "icon": "layers",
                "source": "custom",
                "sheet_key": profile["sheet_name"],
                "table_name": primary_table,
                "primary_table_name": primary_table,
                "related_tables": related_tables[:5],
                "sheet_index": profile["sheet_index"],
                "description": str(item.get("description") or f"跨 {len(related_tables)} 张表观察「{name}」。"),
                "locked": False,
            })

        for item in self._fallback_custom_categories(profiles):
            if len(categories) >= self.MAX_CATEGORIES:
                break
            if item["name"] in custom_seen:
                continue
            custom_seen.add(item["name"])
            categories.append(item)

        if not categories:
            raise ValueError("LLM 未生成有效分类")
        return categories

    def _fallback_custom_categories(self, profiles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if len(profiles) < 2:
            return []

        def find_profile(*keywords: str) -> Optional[Dict[str, Any]]:
            for p in profiles:
                haystack = f"{p.get('sheet_name', '')} {p.get('table_name', '')}"
                if any(keyword in haystack for keyword in keywords):
                    return p
            return profiles[0]

        sales = find_profile("销售明细", "订单", "销售")
        target = find_profile("区域目标", "目标")
        customer = find_profile("客户信息", "客户")
        product = find_profile("产品信息", "产品")
        seller = find_profile("销售员", "人员", "团队")

        specs = [
            {
                "id": "custom_business_overview",
                "name": "经营总览",
                "primary": sales,
                "related": [sales, target, customer, product],
                "description": "综合交易、客户、产品与区域目标信息，回答整体经营健康、收入结构和关键风险。",
            },
            {
                "id": "custom_target_attainment",
                "name": "目标达成",
                "primary": target or sales,
                "related": [target, sales, seller],
                "description": "结合区域目标、销售明细和销售团队信息，观察目标拆解、区域压力与达成风险。",
            },
            {
                "id": "custom_customer_product",
                "name": "客户产品",
                "primary": sales,
                "related": [sales, customer, product],
                "description": "从客户等级、产品类别和交易表现的交叉视角，识别客户价值与产品组合机会。",
            },
        ]

        categories = []
        for spec in specs:
            primary = spec["primary"]
            if not primary:
                continue
            related = []
            for profile in spec["related"]:
                if profile and profile["table_name"] not in related:
                    related.append(profile["table_name"])
            if len(related) < 2:
                continue
            categories.append({
                "id": spec["id"],
                "name": spec["name"],
                "display_name": spec["name"],
                "icon": "layers",
                "source": "custom",
                "sheet_key": primary["sheet_name"],
                "table_name": primary["table_name"],
                "primary_table_name": primary["table_name"],
                "related_tables": related[:5],
                "sheet_index": primary["sheet_index"],
                "description": spec["description"],
                "locked": False,
            })
        return categories

    async def _normalize_filters(self, b1: Dict[str, Any], profiles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        fields_by_table = {p["table_name"]: {f["field"] for f in p["fields"]} for p in profiles}
        filters = []
        seen = set()
        for item in b1.get("global_filters") or []:
            applies = []
            for ap in item.get("applies_to") or []:
                table_name = ap.get("table_name")
                field = ap.get("field")
                if table_name in fields_by_table and field in fields_by_table[table_name]:
                    applies.append({"table_name": table_name, "field": field})
            if not applies:
                table_name = item.get("table_name")
                field = item.get("field")
                if table_name in fields_by_table and field in fields_by_table[table_name]:
                    applies.append({"table_name": table_name, "field": field})
            if not applies:
                continue
            key = str(item.get("canonical_key") or item.get("field") or applies[0]["field"])[:32]
            if key in seen:
                continue
            seen.add(key)
            first = applies[0]
            allowed = list(fields_by_table[first["table_name"]])
            options = await self.db.fetch_distinct_field_values(first["table_name"], first["field"], allowed, limit=50)
            options = [v for v in options if v not in (None, "")][:50]
            if not options:
                continue
            filters.append({
                "canonical_key": key,
                "field": key,
                "label": str(item.get("label") or key)[:20],
                "type": "enum",
                "sample_values": options,
                "options": options,
                "applies_to": applies,
                "priority": int(item.get("priority") or 50),
            })
            if len(filters) >= 6:
                break
        return filters

    def _normalize_question_plans(self, b2: Dict[str, Any], categories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        valid = {c["id"]: c for c in categories}
        plans = []
        for item in b2.get("category_plans") or []:
            category_id = item.get("category_id")
            if category_id not in valid:
                continue
            questions = []
            for idx, q in enumerate((item.get("questions") or [])[: self.MAX_QUESTIONS_PER_CATEGORY]):
                title = str(q.get("title") or q.get("question") or "").strip()
                question = str(q.get("question") or title).strip()
                if not title or not question:
                    continue
                questions.append({
                    "id": str(q.get("id") or f"q_{idx + 1}"),
                    "title": title[:80],
                    "question": question,
                    "priority": int(q.get("priority") or max(10, 100 - idx * 5)),
                })
            if questions:
                plans.append({
                    "category_id": category_id,
                    "category_name": valid[category_id]["display_name"],
                    "thinking": str(item.get("thinking") or self._fallback_category_thinking(valid[category_id])),
                    "questions": questions,
                })
        planned = {plan["category_id"] for plan in plans}
        for category in categories:
            if category["id"] in planned:
                continue
            questions = self._fallback_questions_for_category(category)
            if questions:
                plans.append({
                    "category_id": category["id"],
                    "category_name": category["display_name"],
                    "thinking": self._fallback_category_thinking(category),
                    "questions": questions,
                })
        if not plans:
            raise ValueError("LLM 未生成有效问题清单")
        return plans

    def _fallback_category_thinking(self, category: Dict[str, Any]) -> str:
        if category.get("source") == "custom":
            related = "、".join(category.get("related_tables") or [])
            return (
                f"「{category['display_name']}」是跨表高维分类，MVP 先绑定主表 {category.get('primary_table_name') or category.get('table_name')} "
                f"生成可执行 SQL，同时参考关联表 {related} 的业务含义来设计问题，优先覆盖经营总览、结构拆解和风险识别。"
            )
        return (
            f"「{category['display_name']}」是 Sheet 分类，问题主要围绕 {category.get('table_name')} 的可用字段展开，"
            "优先选择能直接聚合、对比、趋势化或排名的问题，避免脱离单表语义。"
        )

    def _fallback_questions_for_category(self, category: Dict[str, Any]) -> List[Dict[str, Any]]:
        name = category["display_name"]
        if category.get("source") == "custom":
            templates = [
                (f"{name}核心指标总览", f"{name}下最关键的规模、效率和结构指标分别表现如何？"),
                (f"{name}结构贡献分析", f"{name}中哪些维度贡献最高，是否存在明显头部集中？"),
                (f"{name}区域差异分析", f"{name}在不同区域或组织单元之间是否均衡？"),
                (f"{name}趋势与波动", f"{name}随时间变化是否稳定，是否存在异常波动？"),
                (f"{name}机会与风险识别", f"{name}中哪些对象需要优先关注或进一步下钻？"),
                (f"{name}明细样例", f"{name}对应的关键明细记录有哪些代表性样本？"),
            ]
        else:
            templates = [
                (f"{name}核心指标", f"{name}中最关键的规模、数量和金额指标整体表现如何？"),
                (f"{name}维度对比", f"{name}按主要业务维度拆分后，贡献差异是否明显？"),
                (f"{name}排名分析", f"{name}中排名靠前和靠后的对象分别是谁？"),
                (f"{name}趋势分析", f"{name}是否存在时间变化趋势或阶段性波动？"),
                (f"{name}结构占比", f"{name}内部结构占比是否健康，是否过度集中？"),
                (f"{name}明细样例", f"{name}的关键记录样例有哪些？"),
            ]
        return [
            {
                "id": f"q_{idx + 1}",
                "title": title,
                "question": question,
                "priority": max(10, 100 - idx * 5),
            }
            for idx, (title, question) in enumerate(templates[: self.MAX_QUESTIONS_PER_CATEGORY])
        ]

    def _build_placeholders(self, plans: List[Dict[str, Any]], categories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        category_by_id = {c["id"]: c for c in categories}
        charts = []
        for plan in plans:
            category = category_by_id[plan["category_id"]]
            for idx, q in enumerate(plan["questions"]):
                chart_id = self._stable_id(f"{plan['category_id']}:{q['id']}:{q['title']}", prefix="chart")
                charts.append({
                    "id": chart_id,
                    "question_id": q["id"],
                    "category_id": plan["category_id"],
                    "categoryId": plan["category_id"],
                    "title": q["title"],
                    "question": q["question"],
                    "description": q["question"],
                    "chart_type": "table",
                    "chartType": "table",
                    "table_name": category["table_name"],
                    "priority": q["priority"],
                    "board_order": idx,
                    "boardOrder": idx,
                })
        return charts

    def _build_chart_plan(
        self,
        categories: List[Dict[str, Any]],
        charts: List[Dict[str, Any]],
        global_filters: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        by_cat: Dict[str, List[Dict[str, Any]]] = {}
        for chart in charts:
            by_cat.setdefault(chart["category_id"], []).append(chart)
        return [
            {
                "category_id": c["id"],
                "category_name": c.get("display_name") or c.get("name"),
                "table_name": c.get("table_name"),
                "source": c.get("source") or "sheet",
                "description": c.get("description") or "",
                "related_tables": c.get("related_tables") or [c.get("table_name")],
                "charts_count": len(by_cat.get(c["id"], [])),
                "type_counts": {"table": len(by_cat.get(c["id"], []))},
                "global_filter_count": len(global_filters),
                "charts": [
                    {
                        "id": chart["id"],
                        "title": chart["title"],
                        "question": chart.get("question") or chart.get("description") or "",
                        "chart_type": chart.get("chart_type") or "table",
                        "category_id": c["id"],
                        "status": "waiting",
                    }
                    for chart in by_cat.get(c["id"], [])
                ],
            }
            for c in categories
        ]

    def _layout_charts(self, charts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        charts.sort(key=lambda c: (c["category_id"], -int(c.get("priority") or 0), c["title"]))
        per_category: Dict[str, int] = {}
        for chart in charts:
            idx = per_category.get(chart["category_id"], 0)
            chart["board_order"] = idx
            chart["boardOrder"] = idx
            chart["on_board"] = idx < self.MAX_QUESTIONS_PER_CATEGORY
            chart["onBoard"] = chart["on_board"]
            per_category[chart["category_id"]] = idx + 1
        return charts[: self.MAX_WAREHOUSE]

    def _validate_sql_tables(self, sql: str, allowed_tables: Set[str], expected_table: str) -> None:
        quoted = set(re.findall(r"`([^`]+)`", sql))
        table_refs = {name for name in quoted if name in allowed_tables}
        if table_refs and table_refs != {expected_table}:
            raise ValueError("SQL 引用了当前分类以外的数据表")
        if expected_table not in sql:
            raise ValueError("SQL 未引用当前分类绑定的数据表")

    def _normalize_chart_type(self, value: Any) -> str:
        valid = {"kpi_group", "bar", "line", "pie", "donut", "combo", "ranking", "table", "detail_table", "gauge"}
        chart_type = str(value or "table")
        return chart_type if chart_type in valid else "table"

    def _expanded_for(self, chart_type: str) -> bool:
        return chart_type not in {"kpi", "kpi_group", "pie", "donut", "gauge"}

    def _category_id(self, profile: Dict[str, Any], proposed: Any = None) -> str:
        if proposed:
            raw = re.sub(r"[^a-zA-Z0-9_]+", "_", str(proposed)).strip("_").lower()
            if raw:
                return raw[:40]
        return f"sheet_{int(profile.get('sheet_index') or 0)}"

    def _custom_category_id(self, item: Dict[str, Any], name: str) -> str:
        proposed = item.get("id")
        if proposed:
            raw = re.sub(r"[^a-zA-Z0-9_]+", "_", str(proposed)).strip("_").lower()
            if raw:
                return raw[:40]
        return self._stable_id(f"custom:{name}", prefix="custom")

    def _stable_id(self, seed: str, prefix: str = "bi") -> str:
        return f"{prefix}_{hashlib.md5(seed.encode('utf-8')).hexdigest()[:12]}"

    def _json_load(self, value: Any, default: Any) -> Any:
        if value is None:
            return default
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return default
        return value

    async def _limited(self, coro):
        async with self.sem:
            return await coro
