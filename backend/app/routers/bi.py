"""
BI 看板路由 - 智能分类 & 图表数据查询
"""

import asyncio
import json
import logging
import re
import traceback
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import async_session, get_db
from app.services.db_service import DBService
from app.agents.bi_agent import BIClassificationAgent
from app.services.bi_generation import BIBusinessGenerator, UnderstandingNotReadyError
from app.services.bi_understanding_gate import check_understanding_ready, understanding_gate_http_detail
from app.services.bi_profiler import quote_ident
from app.services.bi_pipeline_logger import (
    BIPipelineRunContext,
    STEP_REPAIR,
    STEP_SQL_PREVIEW,
    log_step_error,
    log_step_ok,
)
from app.services.db_service import _json_default, json_safe
from app.utils.sql_validator import SQLValidator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bi", tags=["bi"])

# 全局 BI 智能体实例
bi_agent = BIClassificationAgent()
_generation_locks: Dict[str, asyncio.Lock] = {}


class ChartDataRequest(BaseModel):
    file_id: str
    chart_id: str
    filters: Optional[Dict[str, Any]] = None
    chart_filters: Optional[Dict[str, Any]] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=5, le=200)


class RegenerateChartRequest(BaseModel):
    file_id: str
    chart_id: str
    user_requirement: str = Field(..., max_length=50)


class CreateCategoryRequest(BaseModel):
    file_id: str
    name: str = Field(..., min_length=1, max_length=12)


class UpdateCategoryRequest(BaseModel):
    file_id: str
    name: str = Field(..., min_length=1, max_length=12)


class UpdateChartRequest(BaseModel):
    file_id: str
    title: str = Field(..., min_length=1, max_length=80)
    description: str = Field("", max_length=500)
    category_id: str = Field(..., min_length=1)
    items: Optional[List[Dict[str, Any]]] = None
    encoding: Optional[Dict[str, Any]] = None
    layout: Optional[Dict[str, Any]] = None


@router.post("/generate/{file_id}")
async def generate_bi_config(file_id: str, db: AsyncSession = Depends(get_db)):
    """启动 BI 图表生成（SSE 流式返回进度）"""
    db_service = DBService(db)

    # 验证文件存在
    file_record = await db_service.get_file_record(file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="文件不存在")

    # 获取 Sheet 元数据
    sheet_metas = await db_service.get_sheet_metas(file_id)
    if not sheet_metas:
        raise HTTPException(status_code=400, detail="文件尚未导入任何 Sheet，无法生成 BI 看板")

    ready, pending = await check_understanding_ready(db_service, file_id)
    if not ready:
        raise HTTPException(status_code=409, detail=understanding_gate_http_detail(pending))

    existing_status = await db_service.get_bi_status(file_id)
    if existing_status == "generating":
        raise HTTPException(status_code=409, detail="BI 看板正在生成中，请等待当前任务完成后再重新生成")

    lock = _generation_locks.setdefault(file_id, asyncio.Lock())
    if lock.locked():
        raise HTTPException(status_code=409, detail="BI 看板正在生成中，请等待当前任务完成后再重新生成")

    await lock.acquire()
    await db_service.update_bi_status(file_id, "generating")

    async def event_generator():
        try:
            async for event in _generate_bi_events(file_id, file_record, sheet_metas):
                yield event
        finally:
            lock.release()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _generate_bi_events(file_id: str, file_record: Any, sheet_metas: List[Any]):
    async with async_session() as event_db:
        db_service = DBService(event_db)
        try:
            await db_service.clear_bi_thinking_journal(file_id)
            yield f"data: {json.dumps({'step': 'bi_start', 'status': 'processing'}, ensure_ascii=False, default=_json_default)}\n\n"
            persist_lock = asyncio.Lock()

            async def persist_thinking_entry(entry: Dict[str, Any]) -> None:
                async with persist_lock:
                    async with async_session() as persist_db:
                        await DBService(persist_db).append_bi_thinking_entry(file_id, entry)

            sheets_data = []
            for meta in sheet_metas:
                columns_raw = meta.columns
                if isinstance(columns_raw, str):
                    try:
                        columns = json.loads(columns_raw)
                        if isinstance(columns, str):
                            columns = json.loads(columns)
                    except json.JSONDecodeError:
                        columns = []
                elif isinstance(columns_raw, list):
                    columns = columns_raw
                else:
                    columns = []

                key_dimensions = meta.key_dimensions
                if isinstance(key_dimensions, str):
                    try:
                        key_dimensions = json.loads(key_dimensions)
                    except json.JSONDecodeError:
                        key_dimensions = []

                key_metrics = meta.key_metrics
                if isinstance(key_metrics, str):
                    try:
                        key_metrics = json.loads(key_metrics)
                    except json.JSONDecodeError:
                        key_metrics = []

                sheets_data.append({
                    "sheet_name": meta.sheet_name,
                    "sheet_index": meta.sheet_index,
                    "table_name": meta.table_name,
                    "columns": columns,
                    "row_count": meta.row_count,
                    "summary": meta.summary or "",
                    "key_dimensions": key_dimensions or [],
                    "key_metrics": key_metrics or [],
                    "data_granularity": meta.data_granularity or "未知",
                    "time_range": meta.time_range or "未知",
                })

            yield f"data: {json.dumps({'step': 'bi_generating', 'status': 'processing'}, ensure_ascii=False, default=_json_default)}\n\n"

            try:
                bi_config = await BIBusinessGenerator(db_service).generate(
                    file_id,
                    sheets_data,
                    on_thinking_entry=persist_thinking_entry,
                )
            except UnderstandingNotReadyError as e:
                yield f"data: {json.dumps({'step': 'error', 'status': 'error', 'message': '表理解尚未完成', **understanding_gate_http_detail(e.pending_sheets)}, ensure_ascii=False, default=_json_default)}\n\n"
                return

            thinking = bi_config.pop("thinking_journal", None)
            if thinking:
                await db_service.set_bi_thinking_journal(file_id, thinking)

            bi_config = json_safe(bi_config)
            await db_service.update_bi_config(file_id, bi_config)
            await db_service.update_bi_status(file_id, "completed")
            if file_record.status != "analyzed":
                await db_service.update_file_status(file_id, "analyzed")

            # 返回结果预览
            categories_count = len(bi_config.get("categories", []))
            charts_count = len(bi_config.get("charts", []))

            yield f"data: {json.dumps(json_safe({'step': 'bi_completed', 'status': 'completed', 'categories_count': categories_count, 'charts_count': charts_count, 'data': bi_config}), ensure_ascii=False, default=_json_default)}\n\n"

        except asyncio.CancelledError:
            logger.warning("BI生成连接已取消，重置生成状态: file_id=%s", file_id)
            await db_service.update_bi_status(file_id, "failed")
            raise
        except Exception as e:
            error_detail = traceback.format_exc()
            logger.error(f"BI生成错误: {error_detail}")
            await db_service.update_bi_status(file_id, "failed")
            yield f"data: {json.dumps({'step': 'error', 'status': 'error', 'message': str(e)}, ensure_ascii=False, default=_json_default)}\n\n"


@router.get("/thinking/{file_id}")
async def get_bi_thinking(
    file_id: str,
    q: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """获取 BI 生成思考过程（自然语言），支持关键词搜索。"""
    db_service = DBService(db)

    file_record = await db_service.get_file_record(file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="文件不存在")

    entries = await db_service.get_bi_thinking_journal(file_id)
    if q and q.strip():
        from app.services.bi_thinking_journal import BIThinkingJournal

        journal = BIThinkingJournal(file_id, "")
        journal.entries = entries
        entries = journal.search(q.strip())

    return {
        "code": 200,
        "data": {
            "entries": entries,
            "total": len(entries),
        },
    }


@router.get("/status/{file_id}")
async def get_bi_status(file_id: str, db: AsyncSession = Depends(get_db)):
    """查询 BI 看板生成状态（只读，不触发生成）"""
    db_service = DBService(db)

    file_record = await db_service.get_file_record(file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="文件不存在")

    bi_status = await db_service.get_bi_status(file_id)
    bi_config = await db_service.get_bi_config(file_id)

    # 有配置且状态已完成
    if bi_config and bi_status == "completed":
        return {
            "code": 200,
            "data": {
                "status": "completed",
                "categories_count": len(bi_config.get("categories", [])),
                "charts_count": len(bi_config.get("charts", [])),
            },
        }

    # 正在生成中
    if bi_status == "generating":
        return {
            "code": 200,
            "data": {
                "status": "generating",
            },
        }

    # 生成失败
    if bi_status == "failed":
        return {
            "code": 200,
            "data": {
                "status": "failed",
            },
        }

    ready, pending = await check_understanding_ready(db_service, file_id)
    if not ready:
        return {
            "code": 200,
            "data": {
                "status": "blocked",
                **understanding_gate_http_detail(pending),
            },
        }

    return {
        "code": 200,
        "data": {
            "status": "none",
        },
    }


@router.get("/config/{file_id}")
async def get_bi_config(file_id: str, db: AsyncSession = Depends(get_db)):
    """获取已生成的 BI 看板配置"""
    db_service = DBService(db)

    file_record = await db_service.get_file_record(file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="文件不存在")

    bi_config = await db_service.get_bi_config(file_id)
    if not bi_config:
        raise HTTPException(status_code=404, detail="BI配置尚未生成，请先调用 POST /api/bi/generate/{file_id}")

    return {
        "code": 200,
        "data": bi_config,
    }


@router.post("/chart-data")
async def get_bi_chart_data(
    req: ChartDataRequest,
    db: AsyncSession = Depends(get_db),
):
    """获取 BI 图表数据（支持动态筛选条件）"""
    db_service = DBService(db)

    # 获取 BI 配置
    bi_config = await db_service.get_bi_config(req.file_id)
    if not bi_config:
        raise HTTPException(status_code=404, detail="BI配置尚未生成")

    # 查找对应图表
    charts = bi_config.get("charts", [])
    target_chart = None
    for chart in charts:
        if chart.get("id") == req.chart_id:
            target_chart = chart
            break

    if not target_chart:
        raise HTTPException(status_code=404, detail=f"未找到图表: {req.chart_id}")

    base_sql = target_chart.get("sql", "")
    if not base_sql:
        raise HTTPException(status_code=400, detail="图表缺少SQL查询")

    chart_type = target_chart.get("chart_type", "bar")
    table_name = target_chart.get("table_name", "")

    # 处理 ranking 类型：需要生成 Bottom N 查询
    filter_registry = bi_config.get("global_filters", [])
    effective_filters = _resolve_effective_filters(
        target_chart,
        filter_registry,
        req.filters or {},
        req.chart_filters or {},
    )

    if chart_type == "ranking":
        result = await _execute_ranking_query(
            db_service, target_chart, effective_filters
        )
        return {
            "code": 200,
            "data": {
                "chart_type": chart_type,
                "chart_id": req.chart_id,
                "rows": result.get("rows", []),
                "bottom_rows": result.get("bottom_rows", []),
                "row_count": result.get("row_count", 0),
                "effective_filters": effective_filters,
            },
        }

    # 处理 gauge 类型：返回单一汇总值（不需要分页）
    if chart_type == "gauge":
        result = await _execute_standard_query(
            db_service, base_sql, table_name, effective_filters
        )
        return {
            "code": 200,
            "data": {
                "chart_type": chart_type,
                "chart_id": req.chart_id,
                "rows": result,
                "row_count": len(result),
                "comparison": await _execute_comparison_query(db_service, target_chart, effective_filters),
                "effective_filters": effective_filters,
            },
        }

    # 标准查询（bar, line, pie, funnel, table）— 支持分页
    total, rows = await _execute_paginated_query(
        db_service, base_sql, table_name, effective_filters, req.page, req.page_size
    )
    return {
        "code": 200,
        "data": {
            "chart_type": chart_type,
            "chart_id": req.chart_id,
            "rows": rows,
            "row_count": len(rows),
            "total": total,
            "page": req.page,
            "page_size": req.page_size,
            "comparison": await _execute_comparison_query(db_service, target_chart, effective_filters),
            "effective_filters": effective_filters,
        },
    }


def _resolve_effective_filters(
    chart: Dict[str, Any],
    filter_registry: List[Dict[str, Any]],
    global_filters: Dict[str, Any],
    chart_filters: Dict[str, Any],
) -> Dict[str, Any]:
    """Map canonical global/chart filters to the chart table's physical fields."""
    table_name = chart.get("table_name", "")
    resolved: Dict[str, Any] = {}
    merged = {**(global_filters or {}), **(chart_filters or {})}
    for key, value in merged.items():
        if value in (None, ""):
            continue
        physical_field = None
        for filter_def in filter_registry or []:
            if key not in (filter_def.get("canonical_key"), filter_def.get("field"), filter_def.get("label")):
                continue
            for applies in filter_def.get("applies_to", []):
                if applies.get("table_name") == table_name:
                    physical_field = applies.get("field")
                    break
            if physical_field:
                break
        if physical_field:
            resolved[physical_field] = value
        elif key in chart.get("global_filter_fields", []) or key in [f.get("field") for f in chart.get("filters", [])]:
            resolved[key] = value
    return resolved


def _build_where_clause(
    base_sql: str,
    filters: Optional[Dict[str, Any]],
) -> tuple[str, Dict[str, Any]]:
    """将筛选条件注入 SQL，返回 (带筛选的SQL, 参数字典)"""
    sql = base_sql
    params: Dict[str, Any] = {}

    if not filters:
        return sql, params

    where_parts = []
    for i, (field, value) in enumerate(filters.items()):
        if value is None or value == "":
            continue
        safe_field = field.replace('"', '').replace('`', '')
        param_name = f"filter_{i}"
        if isinstance(value, list):
            placeholders = ", ".join([f":{param_name}_{j}" for j in range(len(value))])
            where_parts.append(f'`{safe_field}` IN ({placeholders})')
            for j, v in enumerate(value):
                params[f"{param_name}_{j}"] = v
        else:
            where_parts.append(f'`{safe_field}` = :{param_name}')
            params[param_name] = value

    if not where_parts:
        return sql, params

    where_clause = " AND ".join(where_parts)
    sql_upper = sql.upper()
    insert_pos = len(sql)
    for keyword in ["GROUP BY", "ORDER BY", "LIMIT"]:
        pos = sql_upper.rfind(keyword)
        if pos != -1 and pos < insert_pos:
            insert_pos = pos

    if "WHERE" in sql_upper:
        sql = sql[:insert_pos] + f" AND {where_clause} " + sql[insert_pos:]
    else:
        sql = sql[:insert_pos] + f" WHERE {where_clause} " + sql[insert_pos:]

    return sql, params


def _strip_limit_from_sql(sql: str) -> str:
    """移除 SQL 末尾的 LIMIT 子句（兼容有无空格、有无分号）"""
    return re.sub(r'(?i)\s*LIMIT\s+\d+\s*;?\s*$', '', sql).rstrip()


async def _execute_standard_query(
    db_service: DBService,
    base_sql: str,
    table_name: str,
    filters: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """执行标准带筛选的 SQL 查询（不分页）"""
    sql, params = _build_where_clause(base_sql, filters)
    logger.debug(f"BI图表查询SQL: {sql}")
    logger.debug(f"参数: {params}")
    return await db_service.execute_query_with_params(sql, params)


async def _execute_comparison_query(
    db_service: DBService,
    chart: Dict[str, Any],
    filters: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    summary_sql = chart.get("summary_sql")
    if not summary_sql:
        return {}
    sql, params = _build_where_clause(summary_sql, filters)
    rows = await db_service.execute_query_with_params(sql, params)
    return rows[0] if rows else {}


async def _execute_paginated_query(
    db_service: DBService,
    base_sql: str,
    table_name: str,
    filters: Optional[Dict[str, Any]],
    page: int,
    page_size: int,
) -> tuple[int, List[Dict[str, Any]]]:
    """执行分页查询，返回 (总数, 当前页数据)"""
    # 先注入筛选条件
    sql_with_filters, params = _build_where_clause(base_sql, filters)

    # 移除原始 LIMIT，用子查询计算总数
    sql_no_limit = _strip_limit_from_sql(sql_with_filters)
    count_sql = f"SELECT COUNT(*) as cnt FROM ({sql_no_limit}) AS bi_count_subquery"

    count_result = await db_service.execute_query_with_params(count_sql, params)
    total = count_result[0]["cnt"] if count_result else 0

    # 分页查询
    offset = (page - 1) * page_size
    paginated_sql = f"{sql_no_limit} LIMIT :_page_size OFFSET :_offset"
    paginated_params = {**params, "_page_size": page_size, "_offset": offset}

    logger.debug(f"BI分页查询SQL: {paginated_sql}")
    rows = await db_service.execute_query_with_params(paginated_sql, paginated_params)

    return total, rows


async def _execute_ranking_query(
    db_service: DBService,
    chart: Dict[str, Any],
    filters: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """执行排名查询（Top N + Bottom N）"""
    base_sql = chart.get("sql", "")
    table_name = chart.get("table_name", "")

    # 生成 Bottom SQL：将 ORDER BY 子句中的 DESC 替换为 ASC
    bottom_sql = re.sub(
        r'(?i)(ORDER\s+BY\s+.*?)DESC',
        r'\1ASC',
        base_sql,
        count=1,
    )

    # 执行 Top N 查询
    top_rows = await _execute_standard_query(
        db_service, base_sql, table_name, filters
    )

    # 执行 Bottom N 查询
    bottom_rows_raw = await _execute_standard_query(
        db_service, bottom_sql, table_name, filters
    )

    # 去重：从 Bottom 结果中排除已在 Top 中出现的条目
    top_keys = set()
    if top_rows:
        first_key = list(top_rows[0].keys())[0]
        top_keys = {row.get(first_key) for row in top_rows if first_key in row}

    bottom_rows = []
    if bottom_rows_raw and top_rows:
        first_key = list(bottom_rows_raw[0].keys())[0]
        bottom_rows = [row for row in bottom_rows_raw if row.get(first_key) not in top_keys]
    else:
        bottom_rows = bottom_rows_raw

    return {
        "rows": top_rows,
        "bottom_rows": bottom_rows,
        "row_count": len(top_rows) + len(bottom_rows),
    }


@router.get("/filter-options/{file_id}")
async def get_filter_options(file_id: str, db: AsyncSession = Depends(get_db)):
    """获取全局筛选选项 - 从所有图表的 filters 字段中收集去重的筛选项"""
    db_service = DBService(db)

    bi_config = await db_service.get_bi_config(file_id)
    if not bi_config:
        raise HTTPException(status_code=404, detail="BI配置尚未生成")

    if bi_config.get("version") == 2 and bi_config.get("global_filters"):
        return {
            "code": 200,
            "data": [
                {
                    "field": f.get("field") or f.get("canonical_key"),
                    "canonical_key": f.get("canonical_key") or f.get("field"),
                    "label": f.get("label") or f.get("field"),
                    "type": f.get("type", "enum"),
                    "sample_values": f.get("options", []),
                    "options": f.get("options", []),
                    "applies_to": f.get("applies_to", []),
                }
                for f in bi_config.get("global_filters", [])
            ],
        }

    charts = bi_config.get("charts", [])

    # 收集所有图表的 filters（去重合并）
    field_map: Dict[str, Dict[str, Any]] = {}

    for chart in charts:
        chart_filters = chart.get("filters", [])
        for f in chart_filters:
            field = f.get("field", "")
            if not field:
                continue
            if field not in field_map:
                field_map[field] = {
                    "field": field,
                    "type": f.get("type", "string"),
                    "sample_values": list(f.get("sample_values", [])),
                }
            else:
                # 合并 sample_values（去重）
                existing_vals = set(str(v) for v in field_map[field]["sample_values"])
                for v in f.get("sample_values", []):
                    if str(v) not in existing_vals:
                        field_map[field]["sample_values"].append(v)
                        existing_vals.add(str(v))

    # 如果图表没有 filters，尝试从 x_field 中提取维度字段
    if not field_map:
        table_names = set()
        x_fields = set()
        for chart in charts:
            x = chart.get("x_field")
            t = chart.get("table_name")
            if x:
                x_fields.add(x)
            if t:
                table_names.add(t)

        # 从数据库中获取这些字段的唯一值
        for table_name in table_names:
            for field in x_fields:
                try:
                    safe_field = field.replace('"', '').replace('`', '')
                    sql = (
                        f"SELECT DISTINCT {quote_ident(safe_field)} "
                        f"FROM {quote_ident(table_name)} "
                        f"WHERE {quote_ident(safe_field)} IS NOT NULL LIMIT 50"
                    )
                    rows = await db_service.execute_query_with_params(sql, {})
                    values = [row.get(field) for row in rows if row.get(field) is not None]
                    if values:
                        field_map[field] = {
                            "field": field,
                            "type": "enum",
                            "sample_values": values,
                        }
                except Exception:
                    continue

    return {
        "code": 200,
        "data": list(field_map.values()),
    }


@router.post("/categories")
async def create_custom_category(
    req: CreateCategoryRequest,
    db: AsyncSession = Depends(get_db),
):
    db_service = DBService(db)
    bi_config = await db_service.get_bi_config(req.file_id)
    if not bi_config:
        raise HTTPException(status_code=404, detail="BI配置尚未生成")

    custom_categories = [c for c in bi_config.get("custom_categories", []) if c.get("source") == "custom"]
    if len(custom_categories) >= 3:
        raise HTTPException(status_code=400, detail="自定义分类最多 3 个")

    category_id = f"custom_user_{len(custom_categories) + 1}_{abs(hash(req.name)) % 100000}"
    category = {
        "id": category_id,
        "name": req.name,
        "display_name": req.name,
        "icon": "chart",
        "source": "custom",
        "locked": False,
        "created_by": "user",
        "chart_ids": [],
    }
    bi_config.setdefault("custom_categories", []).append(category)
    bi_config.setdefault("categories", []).append(category)
    await db_service.update_bi_config(req.file_id, bi_config)
    return {"code": 200, "data": category}


@router.patch("/categories/{category_id}")
async def update_custom_category(
    category_id: str,
    req: UpdateCategoryRequest,
    db: AsyncSession = Depends(get_db),
):
    db_service = DBService(db)
    bi_config = await db_service.get_bi_config(req.file_id)
    if not bi_config:
        raise HTTPException(status_code=404, detail="BI配置尚未生成")

    category = _find_custom_category(bi_config, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="未找到可编辑的自定义分类")

    for bucket in ("categories", "custom_categories"):
        for item in bi_config.get(bucket, []):
            if item.get("id") == category_id:
                item["name"] = req.name
                item["display_name"] = req.name

    await db_service.update_bi_config(req.file_id, bi_config)
    return {"code": 200, "data": _find_custom_category(bi_config, category_id)}


@router.delete("/categories/{category_id}")
async def delete_custom_category(
    category_id: str,
    file_id: str,
    db: AsyncSession = Depends(get_db),
):
    db_service = DBService(db)
    bi_config = await db_service.get_bi_config(file_id)
    if not bi_config:
        raise HTTPException(status_code=404, detail="BI配置尚未生成")

    category = _find_custom_category(bi_config, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="未找到可删除的自定义分类")

    bi_config["categories"] = [c for c in bi_config.get("categories", []) if c.get("id") != category_id]
    bi_config["custom_categories"] = [c for c in bi_config.get("custom_categories", []) if c.get("id") != category_id]

    for chart in bi_config.get("charts", []):
        if chart.get("category_id") == category_id or chart.get("categoryId") == category_id:
            fallback = chart.get("default_category_id") or chart.get("defaultCategoryId")
            if not fallback:
                raise HTTPException(status_code=400, detail=f"图表 {chart.get('id')} 缺少默认 Sheet 分类，无法删除分类")
            chart["category_id"] = fallback
            chart["categoryId"] = fallback

    await db_service.update_bi_config(file_id, bi_config)
    return {"code": 200, "data": {"deleted": category_id}}


def _find_custom_category(bi_config: Dict[str, Any], category_id: str) -> Optional[Dict[str, Any]]:
    for category in bi_config.get("custom_categories", []):
        if category.get("id") == category_id and category.get("source") == "custom" and not category.get("locked"):
            return category
    return None


def _find_category(bi_config: Dict[str, Any], category_id: str) -> Optional[Dict[str, Any]]:
    for category in bi_config.get("categories", []):
        if category.get("id") == category_id:
            return category
    return None


def _chart_category_id(chart: Dict[str, Any]) -> str:
    return chart.get("category_id") or chart.get("categoryId") or ""


def _chart_on_board(chart: Dict[str, Any]) -> bool:
    return bool(chart.get("on_board") if "on_board" in chart else chart.get("onBoard", False))


@router.patch("/charts/{chart_id}")
async def update_chart_metadata(
    chart_id: str,
    req: UpdateChartRequest,
    db: AsyncSession = Depends(get_db),
):
    """更新图表元数据（标题、说明、分类），不调用 LLM。"""
    db_service = DBService(db)
    bi_config = await db_service.get_bi_config(req.file_id)
    if not bi_config:
        raise HTTPException(status_code=404, detail="BI配置尚未生成")

    if not _find_category(bi_config, req.category_id):
        raise HTTPException(status_code=400, detail="目标分类不存在")

    charts = bi_config.get("charts", [])
    target_chart = None
    for chart in charts:
        if chart.get("id") == chart_id:
            target_chart = chart
            break

    if target_chart is None:
        raise HTTPException(status_code=404, detail=f"未找到图表: {chart_id}")

    old_category_id = _chart_category_id(target_chart)
    new_category_id = req.category_id
    on_board = _chart_on_board(target_chart)

    if on_board and new_category_id != old_category_id:
        count_in_target = sum(
            1
            for c in charts
            if c.get("id") != chart_id
            and _chart_on_board(c)
            and _chart_category_id(c) == new_category_id
        )
        if count_in_target >= 10:
            raise HTTPException(
                status_code=400,
                detail="目标分类看板展示已满（最多 10 个），请先从看板移出部分图表",
            )

    title = req.title.strip()
    description = req.description.strip()

    target_chart["title"] = title
    target_chart["question"] = description
    target_chart["description"] = description
    target_chart["category_id"] = new_category_id
    target_chart["categoryId"] = new_category_id
    if req.items is not None:
        target_chart["items"] = req.items[:10]
    if req.encoding is not None:
        target_chart["encoding"] = req.encoding
    if req.layout is not None:
        target_chart["layout"] = req.layout

    await db_service.update_bi_config(req.file_id, bi_config)
    return {
        "code": 200,
        "data": {
            "id": chart_id,
            "title": title,
            "question": description,
            "description": description,
            "category_id": new_category_id,
            "categoryId": new_category_id,
            "items": target_chart.get("items"),
            "encoding": target_chart.get("encoding"),
            "layout": target_chart.get("layout"),
        },
    }


@router.post("/regenerate-chart")
async def regenerate_chart(
    req: RegenerateChartRequest,
    db: AsyncSession = Depends(get_db),
):
    """根据用户需求重新生成单个图表配置"""
    db_service = DBService(db)
    run_ctx = BIPipelineRunContext(req.file_id)

    # 验证文件存在
    file_record = await db_service.get_file_record(req.file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="文件不存在")

    # 获取 BI 配置
    bi_config = await db_service.get_bi_config(req.file_id)
    if not bi_config:
        raise HTTPException(status_code=404, detail="BI配置尚未生成")

    # 查找目标图表
    charts = bi_config.get("charts", [])
    target_idx = None
    target_chart = None
    for i, chart in enumerate(charts):
        if chart.get("id") == req.chart_id:
            target_idx = i
            target_chart = chart
            break

    if target_chart is None:
        raise HTTPException(status_code=404, detail=f"未找到图表: {req.chart_id}")

    # 获取对应的 sheet 元数据
    table_name = target_chart.get("table_name", "")
    sheet_meta = await db_service.get_sheet_meta_by_table(table_name)
    if not sheet_meta:
        raise HTTPException(status_code=404, detail=f"未找到表 {table_name} 的元数据")

    # 调用 BI Agent 重新生成
    try:
        log_step_ok(
            STEP_REPAIR,
            "开始单图重新生成",
            run_ctx=run_ctx,
            table_name=target_chart.get("table_name"),
            sheet_name=target_chart.get("sheet_name"),
            chart_id=req.chart_id,
            question_id=target_chart.get("question_id"),
            extra={
                "user_requirement": req.user_requirement,
                "old_chart_type": target_chart.get("chart_type") or target_chart.get("chartType"),
                "old_sql_preview": (target_chart.get("sql") or "")[:600],
            },
        )
        new_chart = await bi_agent.regenerate_chart(
            user_requirement=req.user_requirement,
            current_chart=target_chart,
            sheet_meta=sheet_meta,
        )
        sanitized_sql = SQLValidator.sanitize_sql(new_chart.get("sql", ""))
        if not sanitized_sql:
            raise ValueError("重生成 SQL 未通过只读安全校验")
        new_chart["sql"] = sanitized_sql
        preview_rows = await db_service.execute_query(new_chart["sql"])
        if not preview_rows:
            raise ValueError("新图表 SQL 执行成功但结果为空")
        new_chart["preview"] = {
            "columns": list(preview_rows[0].keys()),
            "rows": preview_rows[:20],
        }
        new_chart["tablePreview"] = new_chart["preview"]
        new_chart["chartType"] = new_chart.get("chart_type")
        new_chart["category_id"] = target_chart.get("category_id") or target_chart.get("categoryId")
        new_chart["categoryId"] = new_chart["category_id"]
        new_chart["sheet_name"] = target_chart.get("sheet_name")
        new_chart["summary_sql"] = new_chart.get("summary_sql") or target_chart.get("summary_sql")
        new_chart["role_name"] = target_chart.get("role_name")
        new_chart["scenario_name"] = target_chart.get("scenario_name")
        new_chart["question_id"] = target_chart.get("question_id")
        new_chart["on_board"] = target_chart.get("on_board", target_chart.get("onBoard", True))
        new_chart["onBoard"] = new_chart["on_board"]
        new_chart["board_order"] = target_chart.get("board_order", target_chart.get("boardOrder", 0))
        new_chart["boardOrder"] = new_chart["board_order"]
        new_chart["default_category_id"] = target_chart.get("default_category_id")
        new_chart["layer"] = target_chart.get("layer")
        log_step_ok(
            STEP_SQL_PREVIEW,
            "单图重新生成 SQL 预执行通过",
            run_ctx=run_ctx,
            table_name=new_chart.get("table_name"),
            sheet_name=new_chart.get("sheet_name"),
            chart_id=req.chart_id,
            question_id=new_chart.get("question_id"),
            extra={
                "chart_type": new_chart.get("chart_type"),
                "row_count": len(preview_rows),
                "columns": list(preview_rows[0].keys()),
                "sql_preview": sanitized_sql[:600],
            },
        )
    except Exception as e:
        error_detail = traceback.format_exc()
        logger.error(f"图表重新生成错误: {error_detail}")
        log_step_error(
            STEP_REPAIR,
            f"单图重新生成失败: {e}",
            run_ctx=run_ctx,
            table_name=(target_chart or {}).get("table_name"),
            sheet_name=(target_chart or {}).get("sheet_name"),
            chart_id=req.chart_id,
            question_id=(target_chart or {}).get("question_id"),
            exc=e,
            extra={
                "user_requirement": req.user_requirement,
                "old_sql_preview": ((target_chart or {}).get("sql") or "")[:600],
            },
        )
        raise HTTPException(status_code=500, detail=f"AI生成失败: {str(e)}")

    # 保留原图表 ID
    new_chart["id"] = req.chart_id

    # 替换原图表（保持位置不变）
    charts[target_idx] = new_chart
    bi_config["charts"] = charts

    # 保存更新后的配置
    await db_service.update_bi_config(req.file_id, bi_config)

    return {
        "code": 200,
        "data": {
            "chart": new_chart,
        },
    }
