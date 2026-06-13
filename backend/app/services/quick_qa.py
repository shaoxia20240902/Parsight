from typing import Any, Dict, List, Optional
from .ai_service import AIService
from .db_service import DBService
from app.utils.sql_validator import SQLValidator


class QuickQAService:
    """快速问答服务"""

    def __init__(self, db_service: DBService, ai_service: AIService):
        self.db = db_service
        self.ai = ai_service

    async def answer_question(
        self,
        file_id: str,
        question: str,
        table_schemas: Dict[str, Any],
        sheets_summary: List[Dict[str, Any]],
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        快速问答

        Returns:
            {
                "answer": str,
                "data": List[Dict],
                "recommended_questions": List[str]
            }
        """
        qa_result = await self.ai.quick_qa(
            question,
            sheets_summary,
            table_schemas,
            conversation_history=conversation_history or [],
        )

        data = qa_result.get("data", [])
        sql = qa_result.get("sql")
        answer = qa_result.get("answer", "")
        query_detail = "无需额外 SQL 查询"
        if sql and isinstance(sql, str) and sql.strip():
            safe_sql = SQLValidator.sanitize_sql(sql)
            if safe_sql:
                data = await self.db.execute_query(safe_sql)
                query_detail = f"已执行安全查询，返回 {len(data)} 行"
                if data:
                    answer = self._compose_answer_from_data(question, data)
                else:
                    answer = "已完成查询，但没有找到符合条件的数据。"
            else:
                query_detail = "SQL 未通过安全校验，未执行查询"

        return {
            "answer": answer,
            "data": data,
            "recommended_questions": qa_result.get("recommended_questions", []),
            "target_sheet": qa_result.get("target_sheet"),
            "agent_steps": [
                {"name": "意图识别", "status": "completed", "detail": "已确认按快速问答执行"},
                {"name": "字段定位", "status": "completed", "detail": qa_result.get("target_sheet") or "已从表理解中选择相关数据"},
                {"name": "数据查询", "status": "completed", "detail": query_detail},
                {"name": "答案生成", "status": "completed", "detail": "已整理结论和推荐追问"},
            ],
        }

    def _compose_answer_from_data(self, question: str, data: List[Dict[str, Any]]) -> str:
        rows = data[:5]
        if not rows:
            return "已完成查询，但没有找到符合条件的数据。"

        parts = []
        for index, row in enumerate(rows, start=1):
            fields = [f"{key}：{self._format_value(value)}" for key, value in row.items()]
            parts.append(f"{index}. " + "，".join(fields))

        suffix = "。" if len(data) <= 5 else f"。结果共 {len(data)} 行，以上展示前 5 行。"
        if any(token in question for token in ("最高", "前", "Top", "top", "排名")):
            return "根据查询结果，排名靠前的是：" + "；".join(parts) + suffix
        if any(token in question for token in ("最低", "倒数", "Bottom", "bottom")):
            return "根据查询结果，排名靠后的是：" + "；".join(parts) + suffix
        return "根据查询结果：" + "；".join(parts) + suffix

    def _format_value(self, value: Any) -> str:
        if isinstance(value, float):
            if value.is_integer():
                return f"{int(value):,}"
            return f"{value:,.2f}"
        if isinstance(value, int):
            return f"{value:,}"
        return str(value)
