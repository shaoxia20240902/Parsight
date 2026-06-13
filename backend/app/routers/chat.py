import json
import uuid
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional
from app.models.database import get_db
from app.models.chat_history import ChatHistory
from app.services.db_service import DBService
from app.services.ai_service import AIService
from app.services.deep_research import DeepResearchService
from app.services.quick_qa import QuickQAService
from app.services.bi_builder_service import BIBuilderService
from app.services.chat_intent import ChatIntentService

router = APIRouter(prefix="/api/chat", tags=["chat"])

# 全局AI服务实例
ai_service = AIService()


class DeepResearchRequest(BaseModel):
    file_id: str
    question: str
    space_id: Optional[str] = None
    session_id: Optional[str] = None


class QuickQARequest(BaseModel):
    file_id: str
    question: str
    space_id: Optional[str] = None
    session_id: Optional[str] = None
    conversation_history: Optional[List[dict]] = None


class ChatIntentRequest(BaseModel):
    file_id: str
    question: str
    mode: str = "quick"
    space_id: Optional[str] = None


class ConfirmKeywordRequest(BaseModel):
    file_id: str
    session_id: str
    selected_option: int


class DashboardBuildRequest(BaseModel):
    file_id: str
    message: str
    space_id: Optional[str] = None
    # 多轮对话上下文（前端维护）
    conversation_history: Optional[List[dict]] = None


class DashboardLayoutRequest(BaseModel):
    file_id: str
    config: dict  # Agent L 输出的 ready config
    space_id: Optional[str] = None


class BIBuilderRequest(BaseModel):
    file_id: str
    message: str = ""
    session_id: Optional[str] = None
    space_id: Optional[str] = None
    event: Optional[dict] = None


async def save_chat_message(
    db: AsyncSession,
    space_id: str,
    file_id: str,
    role: str,
    content: str,
    mode: str = "insight",
    session_id: str = None,
):
    """保存聊天记录"""
    if space_id:
        msg = ChatHistory(
            id=str(uuid.uuid4()),
            space_id=space_id,
            file_id=file_id,
            mode=mode,
            session_id=session_id,
            role=role,
            content=content
        )
        db.add(msg)
        await db.commit()


async def load_chat_data_context(db_service: DBService, file_id: str):
    file_record = await db_service.get_file_record(file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="文件不存在")

    if file_record.status not in ("analyzed", "understanding_ready"):
        raise HTTPException(status_code=400, detail="文件尚未完成分析，请先执行分析")

    sheet_metas = await db_service.get_sheet_metas(file_id)
    table_schemas = {}
    sheets_summary = []
    for meta in sheet_metas:
        columns = json.loads(meta.columns) if isinstance(meta.columns, str) else meta.columns
        table_schemas[meta.table_name] = {
            "sheet_name": meta.sheet_name,
            "columns": columns,
        }
        sheets_summary.append({
            "sheet_name": meta.sheet_name,
            "table_name": meta.table_name,
            "summary": meta.summary,
            "key_dimensions": json.loads(meta.key_dimensions) if isinstance(meta.key_dimensions, str) else (meta.key_dimensions or []),
            "key_metrics": json.loads(meta.key_metrics) if isinstance(meta.key_metrics, str) else (meta.key_metrics or []),
        })
    return file_record, table_schemas, sheets_summary


@router.post("/intent")
async def detect_chat_intent(request: ChatIntentRequest, db: AsyncSession = Depends(get_db)):
    """统一意图识别：三种问答在执行前先与用户确认是否继续。"""
    db_service = DBService(db)
    _, table_schemas, sheets_summary = await load_chat_data_context(db_service, request.file_id)
    result = ChatIntentService().classify(
        question=request.question,
        mode=request.mode,
        table_schemas=table_schemas,
        sheets_summary=sheets_summary,
    )
    return {"code": 200, "data": result}


@router.post("/deep-research")
async def deep_research(request: DeepResearchRequest, db: AsyncSession = Depends(get_db)):
    """深度调研模式（SSE流式返回）"""

    db_service = DBService(db)

    # 保存用户消息
    session_id = request.session_id or str(uuid.uuid4())
    await save_chat_message(db, request.space_id, request.file_id, "user", request.question, mode="deep", session_id=session_id)

    _, table_schemas, sheets_summary = await load_chat_data_context(db_service, request.file_id)

    # 创建深度调研服务
    deep_research_service = DeepResearchService(db_service, ai_service)

    async def event_generator():
        final_report = ""
        async for event in deep_research_service.run_pipeline(
            file_id=request.file_id,
            question=request.question,
            table_schemas=table_schemas,
            sheets_summary=sheets_summary
        ):
            if event.get("step") == "completed":
                final_report = ((event.get("result") or {}).get("report") or event.get("message") or "")
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        if final_report:
            await save_chat_message(db, request.space_id, request.file_id, "assistant", final_report, mode="deep", session_id=session_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/quick-qa")
async def quick_qa(request: QuickQARequest, db: AsyncSession = Depends(get_db)):
    """快速问答模式"""

    db_service = DBService(db)

    # 保存用户消息
    session_id = request.session_id or str(uuid.uuid4())
    await save_chat_message(db, request.space_id, request.file_id, "user", request.question, mode="insight", session_id=session_id)

    _, table_schemas, sheets_summary = await load_chat_data_context(db_service, request.file_id)

    # 创建快速问答服务
    quick_qa_service = QuickQAService(db_service, ai_service)

    # 执行问答（LLM/数据库失败直接向上抛出，不做静默兜底）
    try:
        result = await quick_qa_service.answer_question(
            file_id=request.file_id,
            question=request.question,
            table_schemas=table_schemas,
            sheets_summary=sheets_summary,
            conversation_history=request.conversation_history or [],
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # 保存助手回复
    answer_text = result.get("answer", "") if isinstance(result, dict) else str(result)
    await save_chat_message(db, request.space_id, request.file_id, "assistant", answer_text, mode="insight", session_id=session_id)

    return {
        "code": 200,
        "data": {**result, "session_id": session_id}
    }


@router.post("/bi-builder")
async def bi_builder(request: BIBuilderRequest, db: AsyncSession = Depends(get_db)):
    """BI 构建者模式：候选复用、ScopePlanning、确认和图表写入。"""
    db_service = DBService(db)

    builder_session_id = request.session_id or str(uuid.uuid4())
    request.session_id = builder_session_id
    event_type = (request.event or {}).get("type", "user_message")
    if event_type == "user_message" and request.message.strip():
        await save_chat_message(db, request.space_id, request.file_id, "user", request.message, mode="builder", session_id=builder_session_id)

    file_record = await db_service.get_file_record(request.file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="文件不存在")

    if file_record.status not in ("analyzed", "understanding_ready"):
        raise HTTPException(status_code=400, detail="文件尚未完成分析，请先执行分析")

    result = await BIBuilderService(db_service).handle(request)
    assistant_content = result.get("reply", {}).get("content") or json.dumps(result, ensure_ascii=False)
    await save_chat_message(db, request.space_id, request.file_id, "assistant", assistant_content, mode="builder", session_id=builder_session_id)

    return {"code": 200, "data": result}


@router.get("/history")
async def get_chat_history(
    space_id: str = None,
    mode: str = None,
    db: AsyncSession = Depends(get_db)
):
    """获取聊天历史"""
    query = select(ChatHistory).order_by(ChatHistory.created_at)
    if space_id:
        query = query.where(ChatHistory.space_id == space_id)
    if mode:
        query = query.where(ChatHistory.mode == mode)
    result = await db.execute(query)
    messages = result.scalars().all()
    return {
        "code": 200,
        "data": [
            {
                "id": m.id,
                "space_id": m.space_id,
                "file_id": m.file_id,
                "mode": m.mode or "insight",
                "session_id": m.session_id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else ""
            }
            for m in messages
        ]
    }


@router.post("/confirm-keyword")
async def confirm_keyword(request: ConfirmKeywordRequest, db: AsyncSession = Depends(get_db)):
    """确认关键词选项（调用真实 Agent）"""
    db_service = DBService(db)
    file_record = await db_service.get_file_record(request.file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="文件不存在")

    sheet_metas = await db_service.get_sheet_metas(request.file_id)
    sheets_summary = []
    for meta in sheet_metas:
        cols = meta.columns
        if isinstance(cols, str):
            cols = json.loads(cols)
        sheets_summary.append({
            "sheet_name": meta.sheet_name,
            "summary": meta.summary or "",
            "key_dimensions": json.loads(meta.key_dimensions) if isinstance(meta.key_dimensions, str) else (meta.key_dimensions or []),
            "key_metrics": json.loads(meta.key_metrics) if isinstance(meta.key_metrics, str) else (meta.key_metrics or []),
        })

    result = await ai_service.confirm_keyword(
        question="",
        context={"sheets_summary": sheets_summary, "selected_option": request.selected_option},
    )

    return {"code": 200, "data": result}


# ============================================================
#  看板构建模式 (Agent L + M)
# ============================================================

@router.post("/dashboard-build")
async def dashboard_build(request: DashboardBuildRequest, db: AsyncSession = Depends(get_db)):
    """
    看板构建模式 — 多轮对话交互式收集看板配置 (Agent L)

    前端发送用户消息和对话历史，后端返回：
    - status: "need_input" → 需要反问用户（带有选项）
    - status: "ready"     → 配置完整，可调用布局生成
    """

    db_service = DBService(db)

    # 保存用户消息
    await save_chat_message(db, request.space_id, request.file_id, "user", request.message)

    # 验证文件存在且已分析
    file_record = await db_service.get_file_record(request.file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="文件不存在")

    if file_record.status not in ("analyzed", "understanding_ready"):
        raise HTTPException(status_code=400, detail="文件尚未完成分析，请先执行分析")

    # 获取 Sheet 元数据
    sheet_metas = await db_service.get_sheet_metas(request.file_id)

    table_schemas = {}
    sheets_summary = []
    for meta in sheet_metas:
        columns = json.loads(meta.columns) if isinstance(meta.columns, str) else meta.columns
        table_schemas[meta.table_name] = {
            "sheet_name": meta.sheet_name,
            "columns": columns,
        }
        sheets_summary.append({
            "sheet_name": meta.sheet_name,
            "table_name": meta.table_name,
            "summary": meta.summary,
            "key_dimensions": json.loads(meta.key_dimensions) if isinstance(meta.key_dimensions, str) else (meta.key_dimensions or []),
            "key_metrics": json.loads(meta.key_metrics) if isinstance(meta.key_metrics, str) else (meta.key_metrics or []),
        })

    # 调用 Agent L：看板构建助手
    result = await ai_service.build_dashboard(
        question=request.message,
        table_schemas=table_schemas,
        sheets_summary=sheets_summary,
        conversation_history=request.conversation_history or [],
    )

    # 保存助手回复
    assistant_content = json.dumps(result, ensure_ascii=False)
    await save_chat_message(db, request.space_id, request.file_id, "assistant", assistant_content)

    return {
        "code": 200,
        "data": result,
    }


@router.post("/dashboard-layout")
async def dashboard_layout(request: DashboardLayoutRequest, db: AsyncSession = Depends(get_db)):
    """
    看板布局生成 (Agent M) — SSE 流式返回

    当 Agent L 输出 status=ready 后，前端调用此接口生成完整看板。
    返回多图表看板配置（含 SQL、图表、布局、全局筛选器）。
    """

    db_service = DBService(db)

    # 验证文件存在且已分析
    file_record = await db_service.get_file_record(request.file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="文件不存在")

    # 获取 Sheet 元数据和表结构
    sheet_metas = await db_service.get_sheet_metas(request.file_id)

    table_schemas = {}
    for meta in sheet_metas:
        columns = json.loads(meta.columns) if isinstance(meta.columns, str) else meta.columns
        table_schemas[meta.table_name] = {
            "sheet_name": meta.sheet_name,
            "columns": columns,
        }

    async def event_generator():
        try:
            # Step 1: 开始生成
            yield f"data: {json.dumps({'step': 'layout_start', 'status': 'processing', 'message': '开始生成看板布局...'}, ensure_ascii=False)}\n\n"

            # Step 2: 调用 Agent M
            yield f"data: {json.dumps({'step': 'layout_generating', 'status': 'processing', 'message': '正在生成多图表看板...'}, ensure_ascii=False)}\n\n"

            result = await ai_service.generate_dashboard_layout(
                config=request.config,
                table_schemas=table_schemas,
            )

            dashboard = result.get("dashboard", result)
            row_count = len(dashboard.get("rows", [])) if isinstance(dashboard, dict) else 0

            yield f"data: {json.dumps({'step': 'layout_completed', 'status': 'completed', 'message': f'看板生成完成：{row_count} 行布局', 'dashboard': dashboard}, ensure_ascii=False)}\n\n"

        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"Dashboard layout error: {error_detail}")
            yield f"data: {json.dumps({'step': 'error', 'status': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/recommendations")
async def get_chat_recommendations(file_id: str, db: AsyncSession = Depends(get_db)):
    """获取对话推荐问题（基于数据理解动态生成）"""
    db_service = DBService(db)
    result = await db_service.get_recommended_questions(file_id)
    return {
        "code": 200,
        "data": {
            "questions": result.get("questions"),
            "status": result.get("status", "idle"),
        }
    }
