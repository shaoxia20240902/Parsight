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
        try:
            qa_result = await self.ai.quick_qa(
                question,
                sheets_summary,
                table_schemas,
                conversation_history=conversation_history or [],
            )
        except Exception as exc:
            return self._fallback_answer(question, sheets_summary, table_schemas, exc)

        # 如果有 SQL，尝试执行
        data = qa_result.get("data", [])
        sql = qa_result.get("sql")
        if sql and isinstance(sql, str) and sql.strip():
            safe_sql = SQLValidator.sanitize_sql(sql)
            if safe_sql:
                try:
                    data = await self.db.execute_query(safe_sql)
                except Exception:
                    data = qa_result.get("data", [])

        return {
            "answer": qa_result.get("answer", ""),
            "data": data,
            "recommended_questions": qa_result.get("recommended_questions", []),
            "target_sheet": qa_result.get("target_sheet"),
        }

    def _fallback_answer(
        self,
        question: str,
        sheets_summary: List[Dict[str, Any]],
        table_schemas: Dict[str, Any],
        error: Exception,
    ) -> Dict[str, Any]:
        sheet_names = [s.get("sheet_name") or s.get("table_name") for s in sheets_summary if s.get("sheet_name") or s.get("table_name")]
        matched = [name for name in sheet_names if name and name in question]
        target = matched[0] if matched else (sheet_names[0] if sheet_names else None)
        answer = "洞察智能体暂时调用失败，已保留你的问题。"
        if target:
            answer += f" 当前文件里可用的数据表包括「{target}」等，可以切换到构建者模式创建或重做对应 BI 报表。"
        return {
            "type": "answer",
            "answer": answer,
            "data": [],
            "recommended_questions": [
                "这份数据能做什么分析？",
                "帮我推荐几个适合生成的 BI 图表",
                "切换到构建者模式重新创建相关模块",
            ],
            "target_sheet": target,
            "error": str(error),
        }
