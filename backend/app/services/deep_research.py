import asyncio
import json
from typing import Any, Dict, List, Optional, AsyncGenerator
from .ai_service import AIService
from .db_service import DBService
from app.utils.sql_validator import SQLValidator


class DeepResearchService:
    """深度调研服务 - 完整的5步流水线"""

    def __init__(self, db_service: DBService, ai_service: AIService):
        self.db = db_service
        self.ai = ai_service

    async def run_pipeline(
        self,
        file_id: str,
        question: str,
        table_schemas: Dict[str, Any],
        sheets_summary: List[Dict[str, Any]]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        执行深度调研完整流程

        Yields:
            SSE事件数据
        """
        # Step 1a: 关键词匹配确认
        yield {"step": "keyword_match", "status": "processing", "message": "正在匹配关键词..."}

        # 构建可用字段信息（含实际枚举值）
        available_fields = []
        for tn, info in table_schemas.items():
            columns = info.get("columns", info) if isinstance(info, dict) else info
            if isinstance(columns, list):
                for col in columns:
                    if isinstance(col, dict):
                        available_fields.append({
                            "sheet": info.get("sheet_name", tn) if isinstance(info, dict) else tn,
                            "field": col.get("name", ""),
                            "type": col.get("type", "text"),
                            "unique_values": col.get("sample_values", [])[:20],
                        })

        keyword_result = await self.ai.confirm_keyword(question, {
            "available_fields": available_fields,
            "sheets_summary": sheets_summary,
        })

        # 初始化筛选条件
        confirmed_filters: list = []

        if keyword_result["match_type"] == "fuzzy" and keyword_result.get("options"):
            # 需要用户确认
            yield {
                "step": "keyword_match",
                "status": "need_confirm",
                "message": "检测到模糊匹配，请确认筛选条件",
                "options": keyword_result["options"],
                "session_id": file_id,
            }
            # 自动选择第一个选项
            if keyword_result.get("matched_fields"):
                confirmed_filters = keyword_result["matched_fields"]
            yield {
                "step": "keyword_match",
                "status": "confirmed",
                "message": f"已确认筛选条件: {confirmed_filters}",
                "condition": confirmed_filters,
            }
        elif keyword_result["match_type"] == "exact" and keyword_result.get("matched_fields"):
            confirmed_filters = keyword_result["matched_fields"]
            yield {
                "step": "keyword_match",
                "status": "completed",
                "message": "关键词精确匹配完成",
                "condition": confirmed_filters,
            }
        else:
            yield {"step": "keyword_match", "status": "completed", "message": "关键词匹配完成"}

        # Step 1b: 多角色并行拆解
        yield {"step": "role_decomposition", "status": "processing", "message": "多角度拆解问题中..."}

        role_results = await self.ai.decompose_by_roles(
            question,
            confirmed_filters,
            {
                "table_schemas": table_schemas,
                "sheets_summary": sheets_summary,
            },
        )

        yield {
            "step": "role_decomposition",
            "status": "completed",
            "message": f"已完成3个角色的问题拆解",
            "roles": [r["role"] for r in role_results]
        }

        # Step 1c: 子问题筛选整合
        yield {"step": "sub_questions", "status": "processing", "message": "筛选最优子问题..."}

        selection_result = await self.ai.select_sub_questions(role_results)
        selected_questions = selection_result["selected_questions"]

        yield {
            "step": "sub_questions",
            "status": "completed",
            "message": f"已筛选出{len(selected_questions)}个子问题",
            "questions": [q["question"] for q in selected_questions]
        }

        # Step 2: SQL生成
        yield {"step": "sql_generation", "status": "processing", "message": "生成查询语句..."}

        sql_result = await self.ai.generate_sql(
            selected_questions, table_schemas,
            filters=confirmed_filters,
        )
        queries = sql_result["queries"]

        yield {
            "step": "sql_generation",
            "status": "completed",
            "message": f"已生成{len(queries)}条SQL查询",
            "queries": queries
        }

        # Step 3: 并行执行SQL
        yield {"step": "sql_execution", "status": "processing", "message": "执行数据查询..."}

        data_results = []
        for query in queries:
            sql = query["sql"]
            # 安全校验
            safe_sql = SQLValidator.sanitize_sql(sql)
            if safe_sql:
                try:
                    result = await self.db.execute_query(safe_sql)
                    data_results.append({
                        "question": query["question"],
                        "data": result,
                        "sql": safe_sql
                    })
                except Exception as e:
                    data_results.append({
                        "question": query["question"],
                        "data": [],
                        "error": str(e)
                    })
            else:
                data_results.append({
                    "question": query["question"],
                    "data": [],
                    "error": "SQL安全校验失败"
                })

        yield {
            "step": "sql_execution",
            "status": "completed",
            "message": f"已执行{len(data_results)}条查询",
            "results_count": sum(len(r["data"]) for r in data_results)
        }

        # Step 4: 图表生成
        yield {"step": "chart_generation", "status": "processing", "message": "生成图表..."}

        chart_tasks = [
            self._generate_chart_safe(dr)
            for dr in data_results
            if dr.get("data")
        ]
        charts = await asyncio.gather(*chart_tasks) if chart_tasks else []

        yield {
            "step": "chart_generation",
            "status": "completed",
            "message": f"已生成{len(charts)}个图表",
            "charts": charts
        }

        # Step 5: 总结报告
        yield {"step": "report_generation", "status": "processing", "message": "生成分析报告..."}

        try:
            report_result = await asyncio.wait_for(
                self.ai.generate_report(
                    question,
                    selected_questions,
                    data_results
                ),
                timeout=45,
            )
            report = report_result["report"]
        except Exception as e:
            report = self._fallback_report(question, selected_questions, data_results, str(e))

        yield {
            "step": "report_generation",
            "status": "completed",
            "message": "报告生成完成",
            "report": report
        }

        # 完成
        yield {
            "step": "completed",
            "status": "completed",
            "message": "深度调研完成",
            "result": {
                "question": question,
                "condition": confirmed_filters,
                "sub_questions": selected_questions,
                "charts": charts,
                "report": report,
                "data_results": data_results
            }
        }

    def _fallback_report(
        self,
        question: str,
        selected_questions: List[Dict[str, Any]],
        data_results: List[Dict[str, Any]],
        error: str,
    ) -> str:
        lines = [
            f"# 深度洞察报告",
            "",
            f"## 分析问题",
            question,
            "",
            "## 关键发现",
        ]
        for index, result in enumerate(data_results[:5], start=1):
            rows = result.get("data") or []
            if not rows:
                lines.append(f"{index}. {result.get('question', '子问题')}：未查询到有效数据。")
                continue
            preview = "；".join(
                "，".join(f"{key}={value}" for key, value in row.items())
                for row in rows[:3]
            )
            lines.append(f"{index}. {result.get('question', '子问题')}：{preview}")

        lines.extend([
            "",
            "## 推理路径",
            f"本轮共筛选 {len(selected_questions)} 个子问题，执行 {len(data_results)} 条查询，并基于查询结果生成结论。",
            "",
            "## 说明",
            f"模型报告生成超时或失败，系统已使用查询证据生成兜底报告。错误信息：{error}",
        ])
        return "\n".join(lines)

    async def _generate_chart_safe(self, data_result: Dict[str, Any]) -> Dict[str, Any]:
        data = data_result.get("data") or []
        columns = list(data[0].keys()) if data else []
        try:
            return await asyncio.wait_for(
                self.ai.generate_chart(data_result.get("question", "数据"), data, columns),
                timeout=25,
            )
        except Exception as e:
            return {
                "chart_type": "table",
                "title": data_result.get("question", "数据"),
                "error": str(e),
                "data": data[:20],
            }
