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
        if sql and isinstance(sql, str) and sql.strip():
            safe_sql = SQLValidator.sanitize_sql(sql)
            if safe_sql:
                data = await self.db.execute_query(safe_sql)

        return {
            "answer": qa_result.get("answer", ""),
            "data": data,
            "recommended_questions": qa_result.get("recommended_questions", []),
            "target_sheet": qa_result.get("target_sheet"),
        }
